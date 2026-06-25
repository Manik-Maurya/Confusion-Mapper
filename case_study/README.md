# Case study

This folder runs the full ConfusionMapper analysis pipeline end-to-end on the 30 paired human/AI labels bundled in `sample_data/example_labels.csv`. It is meant as a worked example: a copy-pasteable starting point for anyone who wants to run the same kind of inter-rater reliability check on their own data.

## How to regenerate

From the repository root:

```bash
pip install -e .
python case_study/run_case_study.py
```

The script writes deterministic outputs to `case_study/results/`. With a fixed seed (`20260623`) and 10,000 bootstrap resamples, the numbers come out identical on any machine.

## What the outputs are

| File | Contents |
|---|---|
| `summary.json` | Nominal kappa, weighted kappa under linear and quadratic schemes, 95% BCa confidence interval, and the gate decision. |
| `confusion_matrix.csv` | The 4 by 4 human-vs-AI cross-tabulation. |
| `per_type_stats.csv` | Per-category total, agreed, and percentage. |
| `bootstrap_kappas.csv` | All 10,000 bootstrap kappa values, in case you want to plot the distribution yourself. |
| `REPORT.md` | A short human-readable summary of the run above. |

## Results from the bundled data

| Quantity | Value |
|---|---|
| Items rated | 30 |
| Cohen's kappa (nominal) | 0.8653 |
| Weighted kappa, linear | 0.9136 |
| Weighted kappa, quadratic | 0.9538 |
| 95% BCa bootstrap CI on nominal kappa | (0.6856, 1.0000) |
| Pre-registration gate (kappa >= 0.70) | PASS |
| Landis and Koch interpretation | Almost Perfect, excellent agreement |

The full breakdown sits in `results/REPORT.md`.

## What the numbers tell you

The point estimate of 0.8653 clears the 0.70 gate comfortably. The lower bound of the 95% confidence interval (0.6856), however, brushes the threshold, which is what you would expect from a calibration set of only 30 items. If a research protocol requires the lower bound to clear 0.70, you would need either a larger calibration set or a tighter rubric.

Both weighted variants come out higher than the nominal kappa because most of the disagreements in this set are between adjacent categories rather than distant ones. Looking at all three numbers together gives you a clearer picture than any single one in isolation.

## Using your own data

Replace `sample_data/example_labels.csv` with a CSV that has the same two columns, `human_label` and `ai_label`, and re-run the script. Every output above will regenerate against your data.

## Data provenance

The labels in `example_labels.csv` were constructed around standard junior-high science topics (photosynthesis, Newton's laws, the circulatory system, density, acids and bases, gravity, water). They are realistic but synthetic, suitable for tutorial use and CI testing.
