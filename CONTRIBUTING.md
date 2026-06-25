# Contributing to ConfusionMapper

Bug reports, fixes, and ideas are all welcome. The notes below cover the basics.

## How to get set up

```bash
git clone https://github.com/Manik-Maurya/Confusion-Mapper.git
cd Confusion-Mapper
pip install -e ".[dev]"
pytest tests/ -v
python examples/demo.py
```

The test suite (55 tests) runs in under a second and needs no API key or display.

## Reporting a bug

Open an issue using the Bug Report template. The most useful bug reports include a short snippet that reproduces the problem, the output you expected, and the output you actually got.

## Suggesting a feature

Open an issue using the Feature Request template. Telling me the research use case you have in mind helps a lot more than just describing the feature.

## Sending a pull request

1. Fork the repo and start a branch off `main`.
2. Make small, focused commits with clear messages.
3. Add tests for any new code. For numerical changes, include a worked example in the test docstring.
4. Run `pytest tests/ -v` and `python examples/demo.py` locally. Both should pass.
5. If your change affects user-facing behaviour, update `README.md`, `paper.md`, or `CITATION.cff` to match.
6. Open the pull request and describe what changed and why. Link the issue it resolves.

## Style notes

- Python 3.9 or higher.
- No new third-party runtime dependencies in the core module beyond `openai` and the standard library.
- Don't silently change the output of `compute_cohens_kappa`, `build_confusion_matrix`, or `get_per_type_stats`. A version bump and a note in the changelog are required for any behaviour change.
- Public functions should have docstrings. Numerical functions should include a worked example.
- Tests should be deterministic; seed any randomness.

## Security

If you find a security issue, please email it privately rather than opening a public issue: manikmaurya.in@gmail.com.

## Code of Conduct

Participation is governed by the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

By contributing you agree that your contribution is released under the project's MIT License.
