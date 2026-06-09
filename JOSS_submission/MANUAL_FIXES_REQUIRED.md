# JOSS Submission — Manual Fixes Required in confusion_mapper.py
# Do these BEFORE pushing the new files to GitHub.

## Fix 1 — Remove "Omega Incorporated" from line ~15 of the code header

FIND:
  Manik Maurya · IIT Kanpur Cognitive Science / Omega Incorporated

REPLACE WITH:
  Manik Maurya · Department of Cognitive Science, IIT Kanpur


## Fix 2 — Fix n=108 → n=90 in the RESEARCH CONTEXT docstring (line ~32)

FIND:
  a pre-registered three-arm RCT (n=108) at IIT Kanpur

REPLACE WITH:
  a pre-registered three-arm RCT (n=90) in government junior high schools, Kanpur Dehat, Uttar Pradesh


## Fix 3 — Rename CITATION.cff.txt → CITATION.cff
# GitHub only recognises the .cff extension (no .txt suffix).
# Delete the old file and add the new CITATION.cff provided here.


## Fix 4 — Rename requirements.txt.txt → requirements.txt
# Same issue. Delete the old file and add the new requirements.txt provided here.


## COMPLETE FILE PUSH CHECKLIST

Add these new files to repo root:
  [ ] paper.md
  [ ] paper.bib
  [ ] CITATION.cff          (replaces CITATION.cff.txt)
  [ ] requirements.txt      (replaces requirements.txt.txt)
  [ ] README.md             (replaces existing README.md)

Add this new directory + files:
  [ ] tests/__init__.py
  [ ] tests/test_kappa.py

Edit in place:
  [ ] confusion_mapper.py   (Fixes 1 and 2 above)

Delete from repo:
  [ ] CITATION.cff.txt
  [ ] requirements.txt.txt

After push:
  [ ] Run: pytest tests/ -v   (all tests should pass)
  [ ] Replace INSERT_EDRARXIV_DOI in paper.bib with your actual EdArXiv DOI
  [ ] Submit at: https://joss.theoj.org/papers/new
