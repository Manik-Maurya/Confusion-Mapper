# Contributing to ConfusionMapper

Thank you for your interest in contributing. ConfusionMapper is a research-grade tool used as a methodological reliability gate for pre-registered educational RCTs, so changes must preserve numerical correctness and reproducibility.

## Ways to Contribute

- **Report a bug**, open an issue using the Bug Report template. Include a minimal reproducible example, the expected output, and the actual output.
- **Request a feature**, open an issue using the Feature Request template. Explain the research use case the feature would unlock.
- **Submit a pull request**, see the workflow below.
- **Improve documentation**, typo fixes, clearer examples, and translation of the docstrings are all welcome.

## Development Setup

```bash
git clone https://github.com/Manik-Maurya/Confusion-Mapper.git
cd Confusion-Mapper
pip install -e ".[dev]"
pytest tests/ -v
python examples/demo.py
```

The full test suite (33 tests) runs in under a second and requires no API key or display.

## Pull Request Workflow

1. Fork the repository and create a feature branch from `main` (e.g. `fix/kappa-edge-case` or `feat/weighted-kappa`).
2. Make your changes in small, focused commits with clear messages.
3. Add or update tests covering the change. New numerical code requires at least one hand-verified worked example in the test docstring.
4. Run the full suite locally: `pytest tests/ -v`, every test must pass.
5. Run the headless demo: `python examples/demo.py`, must exit 0.
6. Update `README.md`, `paper.md`, or `CITATION.cff` if the change affects user-facing behaviour or scholarly attribution.
7. Open a pull request describing what changed and why. Link the issue it resolves.

## Coding Standards

- **Python 3.9+**, no third-party dependencies in the core module beyond `openai` and the standard library.
- **No silent behaviour changes** in `compute_cohens_kappa`, `build_confusion_matrix`, or `get_per_type_stats` without an explicit version bump and migration note.
- **Docstrings** on every public function: one-line summary, parameters, returns, and at least one worked example for numerical functions.
- **Deterministic output**, no randomness in user-facing functions; tests use seeded RNG.

## Reporting Security Issues

Email security concerns privately to manikmaurya.in@gmail.com rather than opening a public issue.

## Code of Conduct

Participation in this project is governed by the [Code of Conduct](CODE_OF_CONDUCT.md). By contributing, you agree to abide by its terms.

## Attribution and Licensing

All contributions are licensed under the project's MIT License. Significant code contributions will be acknowledged in release notes; contributions that meet the [JOSS authorship criteria](https://joss.readthedocs.io/en/latest/submitting.html#authorship) (substantive design, code, or scholarly contribution) may be added to the author list of future paper versions.
