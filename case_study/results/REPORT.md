# Case study: reproducible IRR analysis on a 30-item distractor calibration set

This report is regenerated automatically by `run_case_study.py`. The exact numbers
below are reproducible bit-for-bit under seed `20260623` and `10000` bootstrap resamples on the bundled `sample_data/example_labels.csv`
file. All computations use only the Python standard library plus ConfusionMapper.

## Headline

| Quantity | Value |
|---|---|
| Items rated | 30 |
| Observed agreement Po | 0.9 |
| Chance agreement Pe   | 0.2578 |
| Cohen's kappa (nominal)        | **0.8653** |
| Weighted kappa (linear)        | 0.9136 |
| Weighted kappa (quadratic)     | 0.9538 |
| 95% BCa bootstrap CI on nominal kappa | (0.6856, 1.0) |
| Pre-registration gate (kappa >= 0.70)  | **PASS** |

Interpretation (Landis & Koch 1977): Almost Perfect, excellent agreement.

## Confusion matrix (rows = human, columns = AI)

| human \ ai | RF | PK | CF | INT |
|---|---|---|---|---|
| RF | 6 | 1 | 0 | 0 |
| PK | 0 | 9 | 0 | 0 |
| CF | 0 | 0 | 7 | 1 |
| INT | 0 | 0 | 1 | 5 |

## Per-category agreement

| Category | Items | Agreed | % |
|---|---|---|---|
| RF | 7 | 6 | 86% |
| PK | 9 | 9 | 100% |
| CF | 8 | 7 | 88% |
| INT | 6 | 5 | 83% |

## Reproducibility

- Seed: `20260623`
- Bootstrap resamples: `10000`
- Bootstrap method: BCa (Efron 1987)
- AI rater: not invoked in this script; the labels in the CSV were generated
  with the OpenAI Chat Completions API (`gpt-4o`, temperature 0.0) using the
  prompt embedded in `classify_with_ai`. Pin the exact model snapshot in any
  replication run.
- Dependencies: ConfusionMapper plus the Python standard library only.
- Regenerate with: `python case_study/run_case_study.py`
