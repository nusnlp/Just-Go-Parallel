import json
import glob
import os
from pathlib import Path
import random
import sys
from typing import List
import numpy as np
from tqdm import tqdm
from multiprocessing import Process, cpu_count

# support running without installing as a package
wd = Path(__file__).parent.parent.resolve()
sys.path.append(str(wd))

import lit_gpt.packed_dataset as packed_dataset
from lit_gpt import Tokenizer


TEXT_FORMAT = "{lang}: {text}"


def generate_text(
    json_datum: dict,
    reverse: bool = False,
    sep: str = '\n'
) -> str:
    text = []
    lang_ids = sorted(list(json_datum.keys()), reverse=reverse)
    for lang in lang_ids:
        l_text = json_datum[lang]
        text.append(TEXT_FORMAT.format(lang=lang, text=l_text))
        
    return sep.join(text)


def prepare_full(
    json_data: List[str],
    tokenizer_path: Path,
    destination_path: Path,
    chunk_size: int,
    out_filename: str,
) -> None:

    destination_path.mkdir(parents=True, exist_ok=True)

    tokenizer = Tokenizer(tokenizer_path)

    builder = packed_dataset.PackedDatasetBuilder(
        outdir=destination_path,
        prefix=out_filename,
        chunk_size=chunk_size,
        sep_token=tokenizer.bos_id,
        dtype="auto",
        vocab_size=tokenizer.vocab_size,
    )
    total_tokens = 0
    for idx, (json_datum, reverse) in enumerate(json_data):
        text = generate_text(json_datum, reverse=reverse)
        if idx % 1000 == 0:
            print('> [{}] generated text:\n{}'.format(idx, text), flush=True)
        text_ids = tokenizer.encode(text)
        total_tokens += len(text_ids)
        builder.add_array(np.array(text_ids, dtype=builder.dtype))
    print('>> Finished writing {} tokens. Probably wasted {} tokens.'.format(total_tokens, total_tokens % 2049), flush=True)
    # we throw away the final corpus to avoid meaningless corpus filled with bos_ids, see https://github.com/jzhang38/TinyLlama/issues/83 for more details
    # builder.write_reminder()
    return total_tokens


def prepare(
    source_paths: str = "",
    tokenizer_path: Path = Path("checkpoints/lit-llama/tokenizer.model"),
    destination_path: Path = Path("data/parallel"),
    chunk_size: int = 2049 * 8,
    percentage: float = 1.0,
    out_filename: str="parallel",
    shuffle: bool=True,
    indices: str=None,
    should_swap: bool=True,
    first_swap: bool=False,
) -> None:
    import time

    print('Path: ', source_paths, flush=True)
    source_paths = json.loads(source_paths)
    data = {}
    for path in source_paths:
        print('Loading {}...'.format(path), flush=True)
        split, _ = os.path.splitext(path)
        data[split] = []
        if not path:
            raise RuntimeError(
                f"No files matching {path} found.\n"
            )
        with open(path, encoding='utf-8') as f:
            for line in f:
                data[split].append(json.loads(line))
        print('Finished loading {}'.format(path), flush=True)

    
    if indices is not None:
        assert not shuffle, "Shuffle and indices cannot be used together"
        with open(indices) as f:
            indices = json.load(f)
    elif shuffle:
        for split, path in data.items():
            indices = list(range(len(data[split])))
            rng = random.Random(0)
            rng.shuffle(indices)
            idx_path = '{}_idx.json'.format(destination_path.stem)
            with open(idx_path, 'w') as out:
                json.dump(indices, out)
    
    if indices is not None:
        data[split] = [data[split][_i] for _i in indices]

    chunked_filenames = []


    start_time = time.time()
    splits = list(data.keys())
    data_idx = {k: 0 for k in splits}
    CONSECUTIVE = 1000
    BATCH_SIZE = 100000 # so that the truncation from every writing is minimal
    split_idx = 0
    # Use the provided filenames_subset or default to all filenames
    finished = False
    swap_order = first_swap
    cur_counter = 0
    num_all_tokens = 0

    batch = []
    while not finished:
        # for key, filepaths in filenames.items():
        split_name = splits[split_idx]
        cur_data = data[split_name]
        start_idx = data_idx[split_name]
        end_idx = min(len(cur_data), start_idx + CONSECUTIVE)
        print('Adding {} from {} to {} (swap key? {}) to batch'.format(split_name, start_idx, end_idx, swap_order), flush=True)
        if start_idx < end_idx:
            batch.extend([(d, swap_order) for d in cur_data[start_idx:end_idx]])
            data_idx[split_name] = end_idx
        
        if len(batch) >= BATCH_SIZE:
            cur_name = "{}_{}".format(out_filename, cur_counter)
            print('Writing {}...'.format(cur_name), flush=True)
            num_all_tokens += prepare_full(batch, tokenizer_path, destination_path, chunk_size, cur_name)
            cur_counter += 1
            batch = []
        split_idx += 1

        if split_idx >= len(splits):
            finished = True
            for split in splits:
                if data_idx[split] < len(data[split]):
                    finished = False

            split_idx = 0
            if should_swap:
                swap_order = not swap_order
    
    if len(batch) > 0:
        cur_name = "{}_{}".format(out_filename, cur_counter)
        num_all_tokens += prepare_full(batch, tokenizer_path, destination_path, chunk_size, cur_name)

    end_time = time.time()
    elapsed_time = end_time - start_time
    print(f"Time taken: {elapsed_time:.2f} seconds")
    print(f"Total tokens: {num_all_tokens}")


if __name__ == "__main__":
    from jsonargparse import CLI
    CLI(prepare)