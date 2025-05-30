# Just Go Parallel: Improving the Multilingual Capabilities of Large Language Models

This repository provides the code to systematically investigate the the impact of adding parallel data on LLMs' multilingual capabilities, as reported in the following publication:

> Just Go Parallel: Improving the Multilingual Capabilities of Large Language Models  
> [Muhammad Reza Qorib](https://mrqorib.github.io/), [Junyi Li](https://lijunyi.tech/), and [Hwee Tou Ng](https://www.comp.nus.edu.sg/~nght/)  
> The 63rd Annual Meeting of the Association for Computational Linguistics (to appear)

The codebase is built upon [TinyLlama](https://github.com/jzhang38/TinyLlama)

## Model
Coming soon.

## Training Data
Coming soon.

## Pretrain
Please refer to [PRETRAIN.md](PRETRAIN.md) for instructions on how to pretrain our model.

## Evaluation
Please use [ALMA](https://github.com/fe1ixxu/ALMA) to evaluate translation performance and [LM-Evaluation-Harness](https://github.com/EleutherAI/lm-evaluation-harness) to evaluate common-sense reasoning.

## License
This repository is licensed under the Apache-2.0 license.

## Acknowledgements
This repository is built upon [TinyLlama](https://github.com/jzhang38/TinyLlama), which was built upon [lit-gpt](https://github.com/Lightning-AI/lit-gpt) and [flash-attention](https://github.com/Dao-AILab/flash-attention).
```
@misc{zhang2024tinyllama,
      title={TinyLlama: An Open-Source Small Language Model}, 
      author={Peiyuan Zhang and Guangtao Zeng and Tianduo Wang and Wei Lu},
      year={2024},
      eprint={2401.02385},
      archivePrefix={arXiv},
      primaryClass={cs.CL}
}
@online{lit-gpt,
  author    = {Lightning AI},
  title     = {Lit-GPT},
  url       = {https://github.com/Lightning-AI/lit-gpt},
  year      = {2023},
}
@article{dao2023flashattention2,
  title     ={Flash{A}ttention-2: Faster Attention with Better Parallelism and Work Partitioning},
  author    ={Dao, Tri},
  year      ={2023}
}
```
