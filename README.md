# Just Go Parallel: Improving the Multilingual Capabilities of Large Language Models

This repository provides the code to systematically investigate the the impact of adding parallel data on LLMs' multilingual capabilities, as reported in the following publication:

> [Just Go Parallel: Improving the Multilingual Capabilities of Large Language Models](https://aclanthology.org/2025.acl-long.1602/)  
> [Muhammad Reza Qorib](https://mrqorib.github.io/), [Junyi Li](https://lijunyi.tech/), and [Hwee Tou Ng](https://www.comp.nus.edu.sg/~nght/)  
> The 63rd Annual Meeting of the Association for Computational Linguistics (ACL 2025), pages 33411–33424.

The codebase is built upon [TinyLlama](https://github.com/jzhang38/TinyLlama)

## Model
* No Parallel: [nusnlp/JGP-No-Parallel](https://huggingface.co/nusnlp/JGP-No-Parallel)
* Multilingual: [nusnlp/JGP-Multilingual](https://huggingface.co/nusnlp/JGP-Multilingual)
* Parallel Non-Adjacent: [nusnlp/JGP-Parallel-Non-Adjacent](https://huggingface.co/nusnlp/JGP-Parallel-Non-Adjacent)
* Parallel First: [nusnlp/JGP-Parallel-First](https://huggingface.co/nusnlp/JGP-Parallel-First)
* Parallel Distributed: [nusnlp/JGP-Parallel-Distributed](https://huggingface.co/nusnlp/JGP-Parallel-Distributed)
* Parallel Last (all): [nusnlp/JGP-Parallel-Last-all](https://huggingface.co/nusnlp/JGP-Parallel-Last-all)
* Parallel Last (uni):
  * EN→ID: [nusnlp/JGP-Parallel-Last-EN-ID](https://huggingface.co/nusnlp/JGP-Parallel-Last-EN-ID)
  * ID→EN: [nusnlp/JGP-Parallel-Last-ID-EN](https://huggingface.co/nusnlp/JGP-Parallel-Last-ID-EN)
  * EN→ZH: [nusnlp/JGP-Parallel-Last-EN-ZH](https://huggingface.co/nusnlp/JGP-Parallel-Last-EN-ZH)
  * ZH→EN: [nusnlp/JGP-Parallel-Last-ZH-EN](https://huggingface.co/nusnlp/JGP-Parallel-Last-ZH-EN)

## Training Data
| Experiment | Datasets |
| ---------- | --- |
| No-Parallel | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) |
| Multilingual | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Multilingual](https://huggingface.co/datasets/nusnlp/JGP-Multilingual) |
| Parallel Non-Adjacent | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel-Non-Adjacent](https://huggingface.co/datasets/nusnlp/JGP-Parallel-Non-Adjacent) |
| Parallel First, Parallel Distributed, Parallel Last (all) | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel](https://huggingface.co/datasets/nusnlp/JGP-Parallel) |
| Parallel Last (uni): EN→ID | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel-EN-ID](https://huggingface.co/datasets/nusnlp/JGP-Parallel-EN-ID) |
| Parallel Last (uni): ID→EN | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel-ID-EN](https://huggingface.co/datasets/nusnlp/JGP-Parallel-ID-EN) |
| Parallel Last (uni): EN→ZH | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel-EN-ZH](https://huggingface.co/datasets/nusnlp/JGP-Parallel-EN-ZH) |
| Parallel Last (uni): ZH→EN | [nusnlp/JGP-SlimPajama](https://huggingface.co/datasets/nusnlp/JGP-SlimPajama) + [nusnlp/JGP-Parallel-ZH-EN](https://huggingface.co/datasets/nusnlp/JGP-Parallel-ZH-EN) |

## Installation
We expect that you have CUDA>=11.8 installed.

### Install Pytorch.
Follow the [official guidance](https://pytorch.org/get-started/previous-versions/) to install the appropriate Pytorch version that fits the installed CUDA.

### Install XFormers
You can install the pre-built version or build from source as shown below:
```bash
pip uninstall ninja -y && pip install ninja -U
pip install -v -U git+https://github.com/facebookresearch/xformers.git@main#egg=xformers
```

### Install Flash-Attention 2 and other fused operators:
You can install the pre-built version or build from source as shown below:
```bash
git clone https://github.com/Dao-AILab/flash-attention
cd flash-attention
python setup.py install
cd csrc/rotary && pip install .
cd ../layer_norm && pip install .
cd ../xentropy && pip install .
cd ../.. && rm -rf flash-attention
```

### Install Remaining Dependencies
Install the remaining dependencies:
```
pip install -r requirements.txt tokenizers sentencepiece
```

It may take ≥ 5 minutes to build XFormers/Flash-Attention. Don’t worry if the process seems stagnant or if the terminal prints many warnings.

Then you are ready to go 🎉!

## Pretrain
Please refer to [PRETRAIN.md](PRETRAIN.md) for instructions on reproducing the pretraining of our models.

## Evaluation
Please use [ALMA](https://github.com/fe1ixxu/ALMA) to evaluate translation performance and [LM-Evaluation-Harness](https://github.com/EleutherAI/lm-evaluation-harness) to evaluate common-sense reasoning.

## License
This repository is licensed under the Apache-2.0 license.

## Citation
If you find our work useful, we kindly ask that you cite our paper.
```
@inproceedings{qorib-etal-2025-just,
    title = "Just Go Parallel: Improving the Multilingual Capabilities of Large Language Models",
    author = "Qorib, Muhammad Reza  and
      Li, Junyi  and
      Ng, Hwee Tou",
    booktitle = "Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)",
    month = jul,
    year = "2025",
    address = "Vienna, Austria",
    publisher = "Association for Computational Linguistics",
    url = "https://aclanthology.org/2025.acl-long.1602/",
    doi = "10.18653/v1/2025.acl-long.1602",
    pages = "33411--33424",
    ISBN = "979-8-89176-251-0",
}
```

## Acknowledgements
This repository builds on [TinyLlama](https://github.com/jzhang38/TinyLlama), which was developed with [lit-gpt](https://github.com/Lightning-AI/lit-gpt) and [flash-attention](https://github.com/Dao-AILab/flash-attention).
