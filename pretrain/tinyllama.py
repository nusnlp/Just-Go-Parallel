import glob
import math
import sys
import time
from pathlib import Path
from typing import Optional, Tuple, Union
import math
import lightning as L
import torch
from lightning.fabric.strategies import FSDPStrategy, XLAStrategy
from torch.utils.data import DataLoader
from functools import partial
# support running without installing as a package
wd = Path(__file__).parent.parent.resolve()
sys.path.append(str(wd))
# from apex.optimizers import FusedAdam #torch optimizer has a cuda backend, which is faster actually
from lit_gpt.model import GPT, Block, Config, CausalSelfAttention
from lit_gpt.packed_dataset import CombinedDataset, PackedDataset
from lit_gpt.speed_monitor import SpeedMonitorFabric as Monitor
from lit_gpt.speed_monitor import estimate_flops, measure_flops
from lit_gpt.utils import chunked_cross_entropy, get_default_supported_precision, num_parameters, step_csv_logger, lazy_load
from pytorch_lightning.loggers import WandbLogger
from lit_gpt import FusedCrossEntropyLoss
import random


name = "tinyllama_1b_parallel"

# Hyperparameters
num_of_devices = 8
global_batch_size = 512 # 1024
learning_rate = 4e-4
micro_batch_size = 16 # 8
warmup_steps = 2000
log_step_interval = 10
eval_iters = 100


weight_decay = 1e-1
beta1 = 0.9
beta2 = 0.95
grad_clip = 1.0
decay_lr = True
min_lr = 4e-5

batch_size = global_batch_size // num_of_devices
gradient_accumulation_steps = batch_size // micro_batch_size
assert gradient_accumulation_steps > 0
warmup_iters = warmup_steps * gradient_accumulation_steps

log_iter_interval = log_step_interval * gradient_accumulation_steps
logger = step_csv_logger("out", name, flush_logs_every_n_steps=log_iter_interval)


max_step = 715256 * 2
max_iters = max_step * gradient_accumulation_steps
lr_decay_iters = max_iters



# Treat all dataset equally by their size. If you want to use a different weight for a dataset, add it to the list with the weight.
train_data_config = [
    ("train_slim", 1.0)
    # ("train_slim", 0.693584),
    # ("train_star", 0.306416),
]

val_data_config = [
    ("validation", 1.0),
]

hparams = {k: v for k, v in locals().items() if isinstance(v, (int, float, str)) and not k.startswith("_")}


def setup(
    model_name: str = "tiny_LLaMA_1b",
    devices: int = 8,
    train_data_dir: Path = Path("data/redpajama_sample"),
    val_data_dir: Optional[Path] = None,
    parallel_data_dir: Optional[Path] = None,
    parallel_location: str = "start", 
    precision: Optional[str] = None,
    tpu: bool = False,
    resume: Union[bool, Path] = False,
    project_name: Optional[str] = "tinyLlama_default",
    eval_step_interval: Optional[int] = 5000,
    slim_perc: Optional[float] = 1.0,
    parallel_upsample: Optional[int] = 1,
    slim_offset: Optional[int] = 0,
    ensure_last_parallel: Optional[bool] = False,
    reset_dataloader: bool = False,
) -> None:
    precision = precision or get_default_supported_precision(training=True, tpu=tpu)
    wandb_logger = WandbLogger(project=project_name)
    out_dir = Path("out") / project_name

    if devices > 1:
        if tpu:
            # For multi-host TPU training, the device count for Fabric is limited to the count on a single host.
            devices = "auto"
            strategy = XLAStrategy(sync_module_states=False)
        else:
            strategy = FSDPStrategy(
                auto_wrap_policy={Block},
                activation_checkpointing_policy=None,
                state_dict_type="full",
                limit_all_gathers=True,
                cpu_offload=False,
            )
    else:
        strategy = "auto"

    fabric = L.Fabric(devices=devices, strategy=strategy, precision=precision, loggers=[logger, wandb_logger])
    fabric.print(hparams)
    #fabric.launch(main, train_data_dir, val_data_dir, resume)
    main(model_name, fabric, train_data_dir, val_data_dir, parallel_data_dir, parallel_location, resume, out_dir, eval_step_interval, slim_perc, reset_dataloader, parallel_upsample, slim_offset, ensure_last_parallel)


def main(model_name, fabric, train_data_dir, val_data_dir, parallel_data_dir, parallel_location, resume, out_dir, eval_step_interval, slim_perc, reset_dataloader, parallel_upsample, slim_offset, ensure_last_parallel):
    monitor = Monitor(fabric, window_size=2, time_unit="seconds", log_iter_interval=log_iter_interval)
    fabric.print(f"train_data_dir: {train_data_dir}, val_data_dir: {val_data_dir}, parallel_data_dir: {parallel_data_dir}, parallel_location: {parallel_location}, resume: {resume}, out_dir: {out_dir}, eval_step_interval: {eval_step_interval}, slim_perc: {slim_perc}, reset_dataloader: {reset_dataloader}, parallel_upsample: {parallel_upsample}, slim_offset: {slim_offset}, ensure_last_parallel: {ensure_last_parallel}")
    if fabric.global_rank == 0:
        out_dir.mkdir(parents=True, exist_ok=True)

    config = Config.from_name(model_name)

    train_dataloader, val_dataloader = create_dataloaders(
        batch_size=micro_batch_size,
        block_size=config.block_size,
        fabric=fabric,
        train_data_dir=train_data_dir,
        parallel_data_dir=parallel_data_dir,
        parallel_location=parallel_location,
        val_data_dir=val_data_dir,
        slim_perc=slim_perc,
        slim_offset=slim_offset,
        parallel_upsample=parallel_upsample,
        ensure_last_parallel=ensure_last_parallel,
        seed=3407,
    )
    if val_dataloader is None:
        train_dataloader = fabric.setup_dataloaders(train_dataloader)
    else:
        train_dataloader, val_dataloader = fabric.setup_dataloaders(train_dataloader, val_dataloader)

    fabric.seed_everything(3407)  # same seed for every process to init model (FSDP)

    fabric.print(f"Loading model with {config.__dict__}")
    t0 = time.perf_counter()
    with fabric.init_module(empty_init=False):
        model = GPT(config)
        model.apply(partial(model._init_weights ,n_layer=config.n_layer))
 

    fabric.print(f"Time to instantiate model: {time.perf_counter() - t0:.02f} seconds.")
    fabric.print(f"Total parameters {num_parameters(model):,}")

    model = fabric.setup(model)
    optimizer = torch.optim.AdamW(
        model.parameters(), lr=learning_rate, weight_decay=weight_decay, betas=(beta1, beta2), foreach=False
    )
    # optimizer = FusedAdam(model.parameters(), lr=learning_rate, weight_decay=weight_decay, betas=(beta1, beta2),adam_w_mode=True)
    optimizer = fabric.setup_optimizers(optimizer)

    state = {"model": model, "optimizer": optimizer, "hparams": hparams, "iter_num": 0, "step_count": 0}

    if resume is True:
        ckpts = out_dir.glob("*.pth")
        iters = {int(str(c.name).split('-')[1]):c for c in ckpts}
        last_iter = sorted(list(iters.keys()))[-1]
        resume = iters[last_iter]
    if resume :
        fabric.print(f"Resuming training from {resume}")
        fabric.load(resume, state)

    if reset_dataloader:
        fabric.print(f"Data loader and num iteration reset to the start.")
        state["iter_num"] = 0
    
    fabric.print(torch.cuda.get_device_name(0))
    train_time = time.perf_counter()
    train(fabric, state, train_dataloader, val_dataloader, monitor, resume, out_dir, eval_step_interval)
    fabric.print(f"Training time: {(time.perf_counter()-train_time):.2f}s")
    if fabric.device.type == "cuda":
        fabric.print(f"Memory used: {torch.cuda.max_memory_allocated() / 1e9:.02f} GB")


def train(fabric, state, train_dataloader, val_dataloader, monitor, resume, out_dir, eval_step_interval):
    model = state["model"]
    optimizer = state["optimizer"]

    if val_dataloader is not None:
        validate(fabric, model, val_dataloader)  # sanity check

    with torch.device("meta"):
        meta_model = GPT(model.config)
        # "estimated" is not as precise as "measured". Estimated is optimistic but widely used in the wild.
        # When comparing MFU or FLOP numbers with other projects that use estimated FLOPs,
        # consider passing `SpeedMonitor(flops_per_batch=estimated_flops)` instead
        estimated_flops = estimate_flops(meta_model) * micro_batch_size
        fabric.print(f"Estimated TFLOPs: {estimated_flops * fabric.world_size / 1e12:.2f}")
        x = torch.randint(0, 1, (micro_batch_size, model.config.block_size))
        # measured_flos run in meta. Will trigger fusedRMSNorm error
        #measured_flops = measure_flops(meta_model, x)
        #fabric.print(f"Measured TFLOPs: {measured_flops * fabric.world_size / 1e12:.2f}")
        del meta_model, x

    total_lengths = 0
    total_t0 = time.perf_counter()

    if fabric.device.type == "xla":
        import torch_xla.core.xla_model as xm

        xm.mark_step()
    
    
    initial_iter = state["iter_num"]
    curr_iter = 0
            
    loss_func = FusedCrossEntropyLoss()
    for  train_data in train_dataloader:
        # resume loader state. This is not elegant but it works. Should rewrite it in the future.
        if resume:
            if curr_iter < initial_iter:
                curr_iter += 1
                continue
            else:
                resume = False
                curr_iter = -1
                fabric.barrier()
                fabric.print("resume finished, taken {} seconds".format(time.perf_counter() - total_t0))
        if state["iter_num"] >= max_iters:
            break
        
        # determine and set the learning rate for this iteration
        lr = get_lr(state["iter_num"]) if decay_lr else learning_rate
        for param_group in optimizer.param_groups:
            param_group["lr"] = lr

        iter_t0 = time.perf_counter()

        input_ids = train_data[:, 0 : model.config.block_size].contiguous()
        targets = train_data[:, 1 : model.config.block_size + 1].contiguous()
        is_accumulating = (state["iter_num"] + 1) % gradient_accumulation_steps != 0
        with fabric.no_backward_sync(model, enabled=is_accumulating):
            logits = model(input_ids)
            loss = loss_func(logits, targets)
            # loss = chunked_cross_entropy(logits, targets, chunk_size=0)
            fabric.backward(loss / gradient_accumulation_steps)

        if not is_accumulating:
            fabric.clip_gradients(model, optimizer, max_norm=grad_clip)
            optimizer.step()
            optimizer.zero_grad()
            state["step_count"] += 1
        elif fabric.device.type == "xla":
            xm.mark_step()
        state["iter_num"] += 1
        # input_id: B L 
        total_lengths += input_ids.size(1)
        t1 = time.perf_counter()
        fabric.print(
                f"iter {state['iter_num']} step {state['step_count']}: loss {loss.item():.4f}, iter time:"
                f" {(t1 - iter_t0) * 1000:.2f}ms{' (optimizer.step)' if not is_accumulating else ''}"
                f" remaining time: {(t1 - total_t0) / (state['iter_num'] - initial_iter) * (max_iters - state['iter_num']) / 3600:.2f} hours. " 
                # print days as well
                f" or {(t1 - total_t0) / (state['iter_num'] - initial_iter) * (max_iters - state['iter_num']) / 3600 / 24:.2f} days. "
            )
 
        monitor.on_train_batch_end(
            state["iter_num"] * micro_batch_size,
            t1 - total_t0,
            # this assumes that device FLOPs are the same and that all devices have the same batch size
            fabric.world_size,
            state["step_count"],
            flops_per_batch=estimated_flops,
            lengths=total_lengths,
            train_loss = loss.item()
        )

            
            
        num_tokens = model.config.block_size * (state["iter_num"] + 1) * micro_batch_size * fabric.world_size    
        if val_dataloader is not None and not is_accumulating and state["step_count"] % eval_step_interval == 0:
            
            t0 = time.perf_counter()
            val_loss = validate(fabric, model, val_dataloader)
            t1 = time.perf_counter() - t0
            monitor.eval_end(t1)
            fabric.print(f"step {state['iter_num']}: val loss {val_loss:.4f}, val time: {t1 * 1000:.2f}ms")
            fabric.log_dict({"metric/val_loss": val_loss.item(), "total_tokens": model.config.block_size * (state["iter_num"] + 1) * micro_batch_size * fabric.world_size}, state["step_count"])
            fabric.log_dict({"metric/val_ppl": math.exp(val_loss.item()), "total_tokens": model.config.block_size * (state["iter_num"] + 1) * micro_batch_size * fabric.world_size}, state["step_count"])
            fabric.barrier()
        if not is_accumulating and state["step_count"] % eval_step_interval == 0:
            checkpoint_path = out_dir / f"iter-{state['iter_num']:06d}-token-{num_tokens}-ckpt.pth"
            fabric.print(f"Saving checkpoint to {str(checkpoint_path)!r}")
            fabric.save(checkpoint_path, state)

        
@torch.no_grad()
def validate(fabric: L.Fabric, model: torch.nn.Module, val_dataloader: DataLoader) -> torch.Tensor:
    fabric.print("Validating ...")
    model.eval()

    losses = torch.zeros(eval_iters, device=fabric.device)
    for k, val_data in enumerate(val_dataloader):
        if k >= eval_iters:
            break
        input_ids = val_data[:, 0 : model.config.block_size].contiguous()
        targets = val_data[:, 1 : model.config.block_size + 1].contiguous()
        logits = model(input_ids)
        loss = chunked_cross_entropy(logits, targets, chunk_size=0)

        # loss_func = FusedCrossEntropyLoss()
        # loss = loss_func(logits, targets)
        losses[k] = loss.item()
        
    out = losses.mean()

    model.train()
    return out


def create_dataloader(
    batch_size: int, block_size: int, data_dir: Path, fabric, shuffle: bool = True, seed: int = 12345, split="train",
    parallel_data_dir: Optional[Path] = None, parallel_location: str = "start", slim_perc: float = 1.0, parallel_upsample: int = 1,
    slim_offset: int = 0, ensure_last_parallel: bool = False,
) -> DataLoader:
    datasets = []
    data_config = train_data_config if split == "train" else val_data_config
    for prefix, _ in data_config:
        filenames = sorted(glob.glob(str(data_dir / f"{prefix}*")))
        if parallel_data_dir is not None:
            parallel_files = sorted(glob.glob(str(parallel_data_dir / f"parallel*")))
            if parallel_upsample > 1:
                parallel_files = parallel_files * parallel_upsample
            
            if parallel_location == "start":
                filenames = parallel_files + filenames
            elif parallel_location == "end":
                filenames += parallel_files
            elif parallel_location == "interleave":
                new_filenames = []
                if slim_offset > 0:
                    new_filenames = filenames[:slim_offset]
                    filenames = filenames[slim_offset:]
                
                if ensure_last_parallel:
                    last = parallel_files[-1:]
                    parallel_files = parallel_files[:-1]
                else:
                    last = []
                
                num_slim = 0
                ratio = slim_perc * len(filenames) / float(len(parallel_files))
                for idx, parallel_file in enumerate(parallel_files):
                    new_filenames.append(parallel_file)
                    num_to_be_achieved = round(ratio * (idx + 1))
                    num_to_be_added = num_to_be_achieved - num_slim
                    slim_to_add = filenames[:num_to_be_added]
                    new_filenames.extend(slim_to_add)
                    num_slim += len(slim_to_add)
                    filenames = filenames[num_to_be_added:]
                filenames = new_filenames + filenames + last
            elif parallel_location == "inter-last":
                new_filenames = []
                num_slim = 0
                if slim_offset > 0:
                    raise NotImplementedError("No implementation for inter-last yet")
                elif slim_offset < 0:
                    last = filenames[slim_offset:]
                    filenames = filenames[:slim_offset]

                ratio = slim_perc * len(filenames) / float(len(parallel_files))
                for idx, parallel_file in enumerate(parallel_files[::-1]):
                    new_filenames.append(parallel_file)
                    num_to_be_achieved = round(ratio * (idx + 1))
                    num_to_be_added = num_to_be_achieved - num_slim
                    if num_to_be_added > 0:
                        slim_to_add = filenames[-num_to_be_added:]
                        new_filenames.extend(slim_to_add[::-1])
                        num_slim += len(slim_to_add)
                        filenames = filenames[:-num_to_be_added]

                filenames = filenames + new_filenames[::-1] + last

            elif parallel_location == "repeat-insert":
                new_filenames = parallel_files
            else:
                raise ValueError("Unrecognized value for parallel location: {}".format(parallel_location))
        random.seed(seed)
        if shuffle:
            random.shuffle(filenames)

        dataset = PackedDataset(
            filenames,
            # n_chunks control the buffer size. 
            # Note that the buffer size also impacts the random shuffle
            # (PackedDataset is an IterableDataset. So the shuffle is done by prefetch a buffer and shuffle the buffer)
            n_chunks=8,
            block_size=block_size,
            shuffle=shuffle,
            seed=seed+fabric.global_rank,
            num_processes=fabric.world_size,
            process_rank=fabric.global_rank,
        )
        datasets.append(dataset)

    if not datasets:
        raise RuntimeError(
            f"No data found at {data_dir}. Make sure you ran prepare_redpajama.py to create the dataset."
        )

    weights = [weight for _, weight in data_config]
    sum_weights = sum(weights)
    weights = [el / sum_weights for el in weights]

    combined_dataset = CombinedDataset(datasets=datasets, seed=seed, weights=weights)

    return DataLoader(combined_dataset, batch_size=batch_size, shuffle=False, pin_memory=True)


def create_dataloaders(
    batch_size: int,
    block_size: int,
    fabric,
    train_data_dir: Path = Path("data/redpajama_sample"),
    parallel_data_dir: Optional[Path] = None,
    parallel_location: str = "start",
    val_data_dir: Optional[Path] = None,
    seed: int = 12345,
    slim_perc: float = 1.0,
    parallel_upsample: float = 1.0,
    slim_offset: int = 0,
    ensure_last_parallel: bool = False,
) -> Tuple[DataLoader, DataLoader]:
    # Increase by one because we need the next word as well
    effective_block_size = block_size + 1
    train_dataloader = create_dataloader(
        batch_size=batch_size,
        block_size=effective_block_size,
        fabric=fabric,
        data_dir=train_data_dir,
        parallel_data_dir=parallel_data_dir,
        parallel_location=parallel_location,
        shuffle=False,
        seed=seed,
        slim_perc=slim_perc,
        parallel_upsample=parallel_upsample,
        slim_offset=slim_offset,
        ensure_last_parallel=ensure_last_parallel,
        split="train"
    )
    val_dataloader = (
        create_dataloader(
            batch_size=batch_size,
            block_size=effective_block_size,
            fabric=fabric,
            data_dir=val_data_dir,
            shuffle=False,
            seed=seed,
            split="validation"
        )
        if val_data_dir
        else None
    )
    return train_dataloader, val_dataloader


# learning rate decay scheduler (cosine with warmup)
def get_lr(it):
    # 1) linear warmup for warmup_iters steps
    if it < warmup_iters:
        return learning_rate * it / warmup_iters
    # 2) if it > lr_decay_iters, return min learning rate
    if it > lr_decay_iters:
        return min_lr
    # 3) in between, use cosine decay down to min learning rate
    decay_ratio = (it - warmup_iters) / (lr_decay_iters - warmup_iters)
    assert 0 <= decay_ratio <= 1
    coeff = 0.5 * (1.0 + math.cos(math.pi * decay_ratio))  # coeff ranges 0..1
    return min_lr + coeff * (learning_rate - min_lr)


if __name__ == "__main__":
    # Uncomment this line if you see an error: "Expected is_sm80 to be true, but got false"
    # torch.backends.cuda.enable_flash_sdp(False)
    torch.set_float32_matmul_precision("high")

    from jsonargparse import CLI

    CLI(setup)
