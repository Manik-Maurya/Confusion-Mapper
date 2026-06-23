---
name: Bug report
about: Report a defect in ConfusionMapper's numerical output, GUI, or API integration.
title: "[Bug] "
labels: bug
assignees: Manik-Maurya
---

## Summary
A clear, one-sentence description of the bug.

## Minimal reproducible example
```python
from confusion_mapper import compute_cohens_kappa
human = ["CF", "RF", "PK", "INT"]
ai    = ["CF", "RF", "PK", "INT"]
print(compute_cohens_kappa(human, ai))
```

## Expected output
What you expected to see.

## Actual output
What you actually saw (paste the full output, including any traceback).

## Environment
- OS: (e.g. Ubuntu 22.04, Windows 11, macOS 14)
- Python version: (e.g. 3.11.5)
- ConfusionMapper version / commit hash:
- `openai` library version (if AI rater is involved):

## Additional context
Anything else that would help reproduce or diagnose the bug — relevant configuration, the size of your label set, whether the bug appears with the GUI only or also in headless mode, etc.
