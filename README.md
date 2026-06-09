# ConfusionMapper

**AI-Assisted Distractor Classification and Cohen's Kappa Inter-Rater Reliability Tool**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/Python-3.8%2B-blue.svg)](https://www.python.org/)

> *Every wrong answer a student gives reveals something different about how they think — but most educational software only sees "wrong."*

ConfusionMapper classifies MCQ distractors into four cognitive error types from the **Confusion Fingerprint Index (CFI)** taxonomy, then computes **Cohen's Kappa (κ)** between a human researcher and an AI rater to quantify their agreement.

---

## Overview

In educational research, inter-rater reliability (IRR) is a prerequisite for using qualitative labels in statistical analysis. ConfusionMapper provides an end-to-end workflow for establishing that reliability on a researcher-defined cognitive error taxonomy: it presents each distractor to a human rater, queries the OpenAI API as a parallel AI rater, computes Cohen's kappa, and renders results through an interactive visualisation dashboard.

The tool was developed as the pre-data-collection quality gate for a preregistered randomised controlled trial of cognitive error taxonomy as an adaptive learning signal (OSF: https://doi.org/10.17605/OSF.IO/YU6P5).

---

## The CFI Taxonomy

ConfusionMapper classifies distractors into four mutually exclusive error types:

| Code | Error Type | Cognitive Mechanism |
|------|------------|---------------------|
| RF | **Recall Failure** | No consolidated memory trace; answer is random or implausible |
| PK | **Partial Knowledge** | Almost right — correct direction, but model is incomplete |
| CF | **Confabulation** | Strong, coherent misconception; student answers confidently |
| INT | **Interference** | Correct answer for a *different* related topic; cross-topic confusion |

---

## Features

- **Human + AI classification workflow** — sequential distractor presentation, human rating via console, parallel AI classification via OpenAI GPT
- **Cohen's Kappa computation** — pairwise agreement between human and AI, with Landis–Koch interpretation and κ ≥ 0.70 threshold flagging
- **4×4 confusion matrix** — per-cell agreement/disagreement counts (human labels as rows, AI labels as columns)
- **Per-category agreement statistics** — identifies which error types drive disagreement, enabling targeted rubric revision
- **Interactive visualisation dashboard** — kappa gauge, confusion matrix, and bar chart rendered in tkinter
- **Graceful degradation** — runs fully offline in manual-only mode; headless-safe (console output when tkinter is unavailable)
- **Built-in question bank** — 5 NCERT-aligned questions with 15 pre-labelled distractors for offline use
- **AI question generation** — generate new questions on any topic via the OpenAI API
- **JSON export** — full session records including human labels, AI labels, reasoning strings, and summary statistics

---

## Installation

```bash
git clone https://github.com/Manik-Maurya/Confusion-Mapper.git
cd Confusion-Mapper
pip install openai
```

`tkinter` is part of the Python standard library. No additional installation is required for it.

**Python version:** 3.8 or higher.

---

## Quick Start

**Manual mode (no API key required):**
```bash
python confusion_mapper.py
```

**With AI rater enabled:**
```bash
# macOS / Linux
export OPENAI_API_KEY="your-key-here"
python confusion_mapper.py

# Windows
set OPENAI_API_KEY=your-key-here
python confusion_mapper.py
```

The tool will present each distractor sequentially. You enter `1` (RF), `2` (PK), `3` (CF), or `4` (INT) for your classification. If an API key is set, the AI rater classifies in parallel. After rating all distractors, results are shown in the GUI dashboard and exported as JSON.

---

## Running Tests

```bash
pip install pytest
pytest tests/ -v
```

The test suite covers Cohen's kappa computation (including worked numerical examples), confusion matrix construction, per-type statistics, and consistency across all three functions. No API key or display is required.

---

## Research Context

ConfusionMapper was built for the **Confusion Fingerprint Index (CFI)** research programme at the Department of Cognitive Science, IIT Kanpur.

The CFI characterises each learner's distribution of error types across a question bank as a diagnostic signal for adaptive learning systems. The tool served as the pre-data-collection quality gate for a preregistered three-arm randomised controlled trial (n = 90, Classes 6–8, government junior high schools, Kanpur Dehat, Uttar Pradesh, India), which required κ ≥ 0.70 before data collection could proceed.

**Ethics note:** AI classifications are a starting point, not a substitute for human–human validation. Always verify κ ≥ 0.70 between two trained human raters before using labels in published research.

---

## How to Cite

If you use ConfusionMapper in your research, please cite it as follows.

**APA:**
> Maurya, M. (2026). *ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research*. Journal of Open Source Software. https://github.com/Manik-Maurya/Confusion-Mapper

**BibTeX:**
```bibtex
@article{maurya2026confusionmapper,
  author    = {Maurya, Manik},
  title     = {ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification
               and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research},
  journal   = {Journal of Open Source Software},
  year      = {2026},
  url       = {https://github.com/Manik-Maurya/Confusion-Mapper}
}
```

---

## Acknowledgements

Built during a research internship at the Department of Cognitive Science, IIT Kanpur, under the supervision of Prof. K. M. Sharika. Initial development was completed as part of Stanford Code in Place 2026.

---

## License

MIT License © 2026 Manik Maurya. See [LICENSE.txt](LICENSE.txt) for details.

---

**Detect. Measure. Understand.**
