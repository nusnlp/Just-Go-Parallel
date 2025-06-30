## Training Commands for Just-Go-Parallel
This document lists the commands used to perform the training for each experimental setting in our paper.

### Preparation
Please download the datasets specified in the [README](README.md), and follow the instructions in each respective repository to extract the files. In this document, we assume that all data are located in a directory called `data`.

### No Parallel
```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir data/JGP-SlimPajama --val_data_dir data/JGP-SlimPajama --eval_step_interval 5000 --project_name No-Parallel
```

### Multilingual
```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir data/JGP-SlimPajama --val_data_dir data/JGP-SlimPajama --parallel_data_dir data/JGP-Multilingual --parallel_location interleave --project_name Multilingual
```

### Parallel Non-Adjacent
```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir data/JGP-SlimPajama --val_data_dir data/JGP-SlimPajama --parallel_data_dir data/JGP-Parallel-Non-Adjacent --parallel_location interleave --project_name Parallel-Non-Adjacent
```

### Parallel First
```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir data/JGP-SlimPajama --val_data_dir data/JGP-SlimPajama --parallel_data_dir data/JGP-Parallel --parallel_location start --project_name Parallel-First
```

### Parallel Distributed
```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir data/JGP-SlimPajama --val_data_dir data/JGP-SlimPajama --parallel_data_dir data/JGP-Parallel --parallel_location interleave --project_name Parallel-Distributed
```

### Parallel Last
For **Parallel Last (all)**, set `training_data=data/JGP-Parallel` and `exp_id=Parallel-Last-all`.
For **Parallel Last (uni)**, use the dataset specified in the [README](README.md) and name the experiment ID appropriately.

The Parallel Last experiments continue from the No Parallel experiment. Create the experiment folder `out/$exp_id` and copy the checkpoint for the 155,000th training step (`iter-620000` if trained on 8 GPUs) to this folder.

```bash
PL_DISABLE_UPGRADE_MESSAGE=1 lightning run model --node-rank=0 --accelerator=cuda --devices=8 --num-nodes=1 pretrain/tinyllama.py --train_data_dir $training_data --val_data_dir data/JGP-SlimPajama --parallel_data_dir $training_data --parallel_location start --project_name $exp_id --resume True --reset_dataloader True --eval_step_interval 1000
```

