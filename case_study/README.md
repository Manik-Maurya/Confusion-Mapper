# Case study: a reproducible IRR analysis on a 30-item distractor calibration set

This directory contains a fully reproducible worked example of ConfusionMapper's analysis pipeline. It serves three purposes:

1. **Show JOSS reviewers that the tool produces sensible numbers on a realistic input.** The script in `run_case_study.py` runs the full pipeline (nominal kappa, weighted kappa under linear and quadratic schemes, BCa bootstrap 95% CI, confusion matrix, per-category statistics) on the 30-item paired-label set bundled in `sample_data/example_labels.csv`.
2. **Demonstrate the reproducibility guarantee.** The bootstrap is seeded (`SEED = 20260623`, `N_RESAMPLES = 10000`). Re-running the script on any machine with the same ConfusionMapper version produces bit-identical outputs.
3. **Be a copy-paste template.** Replace the input CSV with your own paired labels and re-run; the same script produces a publication-ready results bundle for your taxonomy.

## How to regenerate

From the repository root, on Python 3.9 or newer:

```bash
pip install -e .
python case_study/run_case_study.py
```

Output files land in `case_study/results/`:

| File | Contents |
|---|---|
| `summary.json` | All kappa variants, point estimate, 95% BCa CI, gate decision |
| `confusion_matrix.csv` | Full 4 x 4 human-vs-AI cross-tabulation |
| `per_type_stats.csv` | Per-category total / agreed / percentage |
| `bootstrap_kappas.csv` | All 10,000 bootstrap kappa values for downstream plotting |
| `REPORT.md` | Auto-generated human-readable narrative |

## Headline results (regenerated 2026-06-25)

| Quantity | Value |
|---|---|
| Items rated | 30 |
| Cohen's kappa (nominal) | **0.8653** |
| Weighted kappa (linear) | 0.9136 |
| Weighted kappa (quadratic) | 0.9538 |
| 95% BCa bootstrap CI on nominal kappa | (0.6856, 1.0000) |
| Pre-registration gate (kappa >= 0.70) | **PASS** |
| Landis-Koch interpretation | Almost Perfect, excellent agreement |

The full breakdown lives in `results/REPORT.md`.

## Reading the result

The point estimate `kappa = 0.8653` would normally suffice to clear the 0.70 gate, but the wide 95% CI (lower bound `0.6856`) shows that with only 30 calibration items the lower bound brushes the threshold. The Cicchetti-Allison linear (`0.9136`) and Fleiss-Cohen quadratic (`0.9538`) weighted variants are both substantially higher than the nominal score because almost every disagreement in this set is between adjacent categories rather than distant ones. This is exactly the kind of diagnostic insight that distinguishes a research-grade IRR tool from a single-number kappa wrapper.

## Data provenance

`sample_data/example_labels.csv` contains 30 paired labels constructed around the NCERT science topics that the live RCT uses (photosynthesis, Newton's laws, the heart, density, acids and bases, gravity, water). The labels are realistic but synthetic, suitable for tutorial use. To repeat the analysis on your own data, supply a CSV with the same two columns (`human_label`, `ai_label`) and update `load_labels()` in `run_case_study.py`.

## Citing this case study

If you reproduce or build on this analysis, please cite the archived software release:

> Maurya, M. (2026). *ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research* (Version 1.0.0) [Software]. Zenodo. https://doi.org/10.5281/zenodo.20807432
