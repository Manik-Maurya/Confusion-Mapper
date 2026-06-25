# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-23

First public release.

### Core functions

- `compute_cohens_kappa(human, ai)` returns nominal Cohen's kappa with a Landis and Koch interpretation string.
- `compute_cohens_kappa(..., weights="linear" | "quadratic")` returns weighted kappa for ordinal taxonomies, using Cicchetti-Allison and Fleiss-Cohen weights respectively.
- `build_confusion_matrix(human, ai)` returns the N by N cross-tabulation as a nested dict.
- `get_per_type_stats(human, ai)` returns per-category total, agreed, and percentage agreement.
- `bootstrap_kappa_ci(human, ai, method="bca", seed=...)` returns a percentile or BCa bootstrap 95% confidence interval. The `seed` argument makes the interval bit-identically reproducible.
- `load_taxonomy_from_json(path)` swaps the default Confusion Fingerprint Index categories for any nominal scheme of two or more labels described in a small JSON file.

### Interfaces

- Console session flow (`run_session`) for interactive distractor labelling.
- Optional tkinter results dashboard with a kappa gauge, confusion matrix, and per-type bar chart. Falls back to console output when no display is available.
- Optional OpenAI rater (`classify_with_ai`) using `gpt-4o` at temperature zero.
- Optional AI question generator (`generate_ai_questions`).
- JSON session export.
- Headless tutorial at `examples/demo.py`.
- Worked case study at `case_study/run_case_study.py` with deterministic outputs.

### Quality

- 55-test pytest suite.
- GitHub Actions matrix on Python 3.9 through 3.12.
- JOSS draft paper PDF built on every push.

### Archive

- Software archive: <https://doi.org/10.5281/zenodo.20807432>.
