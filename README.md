# ConfusionMapper

A Python tool for classifying wrong answer choices in multiple-choice questions by the type of cognitive error they represent, and for computing how well a human researcher and an AI rater agree on those labels.

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20807432-1682D4?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.20807432)
[![Tests](https://github.com/Manik-Maurya/Confusion-Mapper/actions/workflows/tests.yml/badge.svg)](https://github.com/Manik-Maurya/Confusion-Mapper/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

## What it does

In educational research, you cannot use qualitative labels in a statistical analysis unless two independent raters can produce roughly the same labels on the same items. The usual way to check this is Cohen's kappa.

ConfusionMapper handles the full workflow. You go through a set of distractors one by one and pick a label for each. If you have an OpenAI API key, an AI rater labels the same distractors in parallel. At the end, the program computes Cohen's kappa, draws a 4x4 confusion matrix of where the two raters agreed and disagreed, and saves everything to JSON.

It was built as the reliability check for a preregistered RCT on cognitive error feedback in government junior high schools (OSF: https://doi.org/10.17605/OSF.IO/YU6P5). Data collection in that study could only start once kappa cleared 0.70.

## The four error types

The taxonomy is called the Confusion Fingerprint Index (CFI). It splits wrong answers into four categories:

| Code | Name | What it looks like |
|------|------|---------------------|
| RF | Recall Failure | No memory trace at all; the answer is essentially random |
| PK | Partial Knowledge | Almost right; the direction is correct but the model is incomplete |
| CF | Confabulation | A coherent misconception held with confidence |
| INT | Interference | A correct answer pulled from the wrong topic |

## Install

Once a versioned release is on PyPI:

```bash
pip install confusion-mapper
```

From source (until the first PyPI release, this is the recommended path):

```bash
git clone https://github.com/Manik-Maurya/Confusion-Mapper.git
cd Confusion-Mapper
pip install -e .
```

The only runtime dependency is `openai>=1.0.0`. `tkinter` ships with Python on most systems; on a minimal Debian or Ubuntu image install it with `sudo apt-get install python3-tk`. If `tkinter` is missing, ConfusionMapper drops to console output instead of the GUI.

Python 3.9 or higher.

For the test extras:

```bash
pip install -e ".[dev]"
```

## Run

Without an API key (you label everything by hand):

```bash
python confusion_mapper.py
```

With the AI rater on:

```bash
# macOS / Linux
export OPENAI_API_KEY="your-key-here"
python confusion_mapper.py

# Windows
set OPENAI_API_KEY=your-key-here
python confusion_mapper.py
```

For each distractor, type `1` for RF, `2` for PK, `3` for CF, or `4` for INT. When you finish, the dashboard opens and the session writes itself to JSON.

## Case study

A fully reproducible worked example lives in [`case_study/`](case_study/). It runs the entire
pipeline (nominal kappa, weighted kappa under linear and quadratic schemes, BCa
bootstrap 95% CI, confusion matrix, per-category stats) on the bundled 30-item
paired-label set with a fixed seed, then writes the results to
`case_study/results/` (JSON summary, CSV matrix, CSV per-type stats, full bootstrap
distribution, and a Markdown report). Regenerate with one command:

```bash
python case_study/run_case_study.py
```

Headline result on the bundled data: nominal kappa = 0.8653, BCa 95% CI = (0.6856, 1.0000),
pre-registration gate PASSES at the 0.70 threshold.

## Headless example

A non-interactive demo runs the three core functions on 30 pre-labelled distractors in under a second. No API key, no display:

```bash
python examples/demo.py
```

It prints kappa, the full confusion matrix, per-category agreement, and a PASS / HOLD verdict against the 0.70 gate. Swap in your own paired labels by replacing `sample_data/example_labels.csv`.

## Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

55 tests, runs in under a second. Covers the kappa formula (with hand-verified worked examples), weighted kappa (nominal / linear / quadratic), bootstrap confidence intervals (percentile + BCa, seedable), custom-taxonomy loading, the confusion matrix, and the mathematical invariants that tie everything together. Doesn't need an API key or a display.

## Advanced features

All three are stdlib-only and tested.

**Weighted kappa for ordinal taxonomies.** Pass `weights="linear"` or
`weights="quadratic"` to penalise far-apart disagreements more than adjacent ones:

```python
from confusion_mapper import compute_cohens_kappa
r = compute_cohens_kappa(human, ai, weights="linear")
print(r["kappa"], r["weights"])
```

**Bootstrap 95% confidence interval (BCa or percentile).** Cohen's kappa is a point
estimate; this gives you uncertainty around it. The `seed` makes the interval
bit-identically reproducible:

```python
from confusion_mapper import bootstrap_kappa_ci
ci = bootstrap_kappa_ci(human, ai, n_resamples=10000, method="bca", seed=42)
print(f"kappa = {ci['point_estimate']} (95% CI {ci['ci_lower']} to {ci['ci_upper']})")
```

**Custom taxonomy via JSON.** Swap the default CFI categories for any 2-or-more
category nominal scheme. A working example sits at
`sample_data/custom_taxonomy.json`:

```python
from confusion_mapper import load_taxonomy_from_json, compute_cohens_kappa
codes, tax = load_taxonomy_from_json("sample_data/custom_taxonomy.json")
r = compute_cohens_kappa(human, ai, categories=codes)
```

## Why a 4x4 confusion matrix instead of just kappa

The single kappa number tells you how much you and the AI agree overall. It does not tell you which category boundary is causing the disagreement. CF vs INT is the hardest distinction in the CFI taxonomy (a confident wrong belief looks a lot like a correct answer applied to the wrong topic), and the [CF, INT] cell of the confusion matrix is where most disagreement tends to land. Looking at the full 4x4 matrix lets you see exactly that, and rewrite the AI prompt or your own rubric until the cell stops glowing.

## A note on ethics

The AI rater is a starting point, not a substitute for a second human. For published research you should still run kappa between two trained human raters on the same calibration set. Treat the AI labels as a way to surface boundaries that need rubric work, not as a replacement for human judgment.

## How to cite

Archived release on Zenodo: https://doi.org/10.5281/zenodo.20807432

APA:

> Maurya, M. (2026). *ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research* (Version 1.0.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.20807432

BibTeX:

```bibtex
@software{maurya2026confusionmapper,
  author    = {Maurya, Manik},
  title     = {ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification
               and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research},
  year      = {2026},
  version   = {1.0.0},
  doi       = {10.5281/zenodo.20807432},
  url       = {https://doi.org/10.5281/zenodo.20807432}
}
```

## Contributing

Bug reports, feature requests, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Acknowledgements

Initial development was completed as part of Stanford Code in Place 2026. The tool is used in the Confusion Fingerprint Index research programme at the Department of Cognitive Science, IIT Kanpur.

## License

MIT License © 2026 Manik Maurya. See [LICENSE](LICENSE) for details.
