# Changelog

All notable changes to ConfusionMapper are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-06-23

First public release.

### Added

- `compute_cohens_kappa(human, ai)` for nominal Cohen's kappa with Landis-Koch interpretation.
- `compute_cohens_kappa(..., weights="linear")` and `weights="quadratic"` for weighted kappa over ordinal taxonomies (Cicchetti-Allison and Fleiss-Cohen schemes).
- `build_confusion_matrix(human, ai)` returning the full N x N category cross-tabulation as a nested dict.
- `get_per_type_stats(human, ai)` returning per-category agreement counts and percentages.
- `bootstrap_kappa_ci(human, ai, method="bca", seed=...)` for percentile and bias-corrected and accelerated (BCa) bootstrap confidence intervals on kappa, with a seed parameter for bit-identical reproducibility.
- `load_taxonomy_from_json(path)` for swapping the default Confusion Fingerprint Index categories for any two-or-more category nominal scheme.
- Built-in NCERT-aligned MCQ bank covering five Class 7 science questions with fifteen pre-labelled distractors.
- OpenAI-backed AI rater (`classify_with_ai`) with `model="gpt-4o"`, `temperature=0.0`, and a deterministic structured prompt.
- Optional AI question generator (`generate_ai_questions`).
- Tkinter results dashboard (`show_results_window`) with a kappa gauge, 4 x 4 confusion matrix, and per-type bar chart. Falls back to console output when no display is available.
- JSON session export for full reproducibility records.
- Headless tutorial at `examples/demo.py` reproducing a complete kappa analysis on the bundled 30-item paired-label set.
- Case study at `case_study/` with a fully reproducible IRR analysis (kappa, weighted kappa, bootstrap CI, confusion matrix, per-type stats) on the NCERT-aligned distractor set.
- 55-test pytest suite covering the kappa formula, weighted kappa, bootstrap CI determinism, custom taxonomy loading, and confusion matrix invariants.
- GitHub Actions CI building the pytest matrix on Python 3.9 through 3.12 and producing a JOSS-formatted paper PDF as a downloadable artifact on every push.

### Documentation

- README with install, usage, advanced features, and citation sections.
- JOSS-ready `paper.md` and `paper.bib` (994 body words, ten resolved citations).
- `CITATION.cff` validated and including the Zenodo software DOI.
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` (Contributor Covenant 2.1), bug-report and feature-request issue templates, pull-request template.
- `docs/` containing taxonomy, methodology, and research-context notes.

### Archive

- Version 1.0.0 archived on Zenodo: <https://doi.org/10.5281/zenodo.20807432>.
