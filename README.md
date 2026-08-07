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

CFI is this package's flagship taxonomy and everything defaults to it, but none of the reliability statistics, the multi-rater workflow, dataset validation, export packages, the codebook generator, or the embeddings/semantic-search tooling are actually CFI-specific -- they all take a `categories` list and, as of this release, an optional `taxonomy` dict, and work identically for any coding scheme. Swap in your own via `stats.load_taxonomy_from_json()` (a JSON file: a `code`, `name`, and `definition` per category, optionally `number`/`color`/`example`) and the whole toolkit -- kappa, AC1, Krippendorff's alpha, the multi-rater agreement matrix, `validate`, `export`, `codebook`, `embed-index` -- works the same way it does for CFI.

`sample_data/item_bank_distractor_taxonomy.json` is a worked, non-CFI example: a 4-category **distractor-functioning** taxonomy for multiple-choice item banks in large-scale assessment (PISA-style math/science/reading literacy items, or any MCQ bank where you care about how a wrong answer behaves psychometrically, not just whether it was chosen) -- Non-Functional, Potentially-Lead-to-Misconception, Functional, and Ambiguous/Flawed distractors, modeled on published item-analysis literature (the <5% non-functional-distractor threshold and the "Potentially Lead to Misconception" concept from mathematics-education item analysis; see the taxonomy file's own comment for citations). It is **not** an official OECD/PISA taxonomy -- PISA's own published coding is item-specific partial-credit rubrics, not one reusable cross-item scheme -- it's a demonstration, with `sample_data/item_bank_demo.csv`, that this package's machinery is genuinely general-purpose:

```bash
confusion-mapper kappa sample_data/item_bank_demo.csv --categories NF,PLM,FD,AMB
confusion-mapper codebook --taxonomy-file sample_data/item_bank_distractor_taxonomy.json
confusion-mapper export sample_data/item_bank_demo.csv \
  --taxonomy-file sample_data/item_bank_distractor_taxonomy.json --out results/
```

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
confusion-mapper
```

With the AI rater on:

```bash
# macOS / Linux
export OPENAI_API_KEY="your-key-here"
confusion-mapper

# Windows
set OPENAI_API_KEY=your-key-here
confusion-mapper
```

`python -m confusion_mapper` works identically if you'd rather not rely on the
installed script being on your `PATH`. Both entry points also accept the
`kappa` / `alpha` / `diagnostics` / `plan` / `refine` subcommands documented
under [Command line](#command-line) below.

For each distractor, type `1` for RF, `2` for PK, `3` for CF, or `4` for INT. When you finish, the dashboard opens and the session writes itself to JSON.

**Session provenance.** Every saved session includes, alongside the ratings and computed statistics: a `session_id` (UUID4), `software_version` (the actually-installed confusion-mapper version, read from package metadata), `taxonomy_fingerprint` (a 12-character hash of the exact CFI category definitions in effect -- lets you tell later whether two sessions were coded under the same taxonomy or it changed in between), and `python_version`. All four are purely additive: every key that was in a session file before this release is still there, computed by the exact same, untouched functions.

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

## Benchmarks

`benchmarks/` asks a question the rest of this README asserts but doesn't measure: does the local (hashed bag-of-words) embedding backend actually capture real signal, or is it noise dressed up as a feature? Full write-up in [`benchmarks/EMBEDDING_VALIDATION_FINDINGS.md`](benchmarks/EMBEDDING_VALIDATION_FINDINGS.md); the short version is not flattering and is reported anyway: Adjusted Rand Index (implemented from scratch in `ari.py`, hand-derived worked example, verified three separate ways) between the local backend's clusters and the real `human_label` column on both bundled labeled datasets comes out at or near zero at every threshold tested -- the local backend does not recover the taxonomy from content alone. The write-up traces this to a real property of the data (cognitive-error-type and topic are close to orthogonal by construction: every label spans many different questions, while distractors *within* one question carry different labels) rather than explaining it away, and argues a study that found *high* agreement here would be the more suspicious result. `benchmarks/benchmark_embeddings.py` runs the identical comparison against the `openai` backend and is ready to go -- it hasn't been run yet, since that needs an API key and network access. If you run it, the findings doc is where the second half of that comparison belongs.

```bash
python benchmarks/embedding_validation_study.py   # the local-only study, as reported
python benchmarks/benchmark_embeddings.py          # local vs. openai -- needs OPENAI_API_KEY
```

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

357 tests across fifteen files, run in under two seconds. `test_kappa.py` (40) covers the kappa formula (with hand-verified worked examples), weighted kappa, bootstrap confidence intervals, PABAK and the bias/prevalence diagnostics, Gwet's AC1, Krippendorff's alpha, the sample-size estimator, custom-taxonomy loading, the confusion matrix, the prompt-refinement engine, Fleiss's kappa, and the CLI subcommand router. `test_validation.py` (15), `test_multirater.py` (20), `test_export.py` (19), `test_provenance.py` (11), `test_evidence.py` (25), and `test_codebook.py` (12) cover their namesake modules. `test_embeddings.py` (52) covers both embedding backends, cosine similarity, the full persistent-index lifecycle, and single-linkage clustering. `test_assist.py` (20) covers the AI-assist workflow end to end via simulated stdin, including a regression test for a real bug caught during development. `test_custom_taxonomy.py` (26) covers custom (non-CFI) taxonomy support end to end, including a full run against `sample_data/item_bank_distractor_taxonomy.json`. `test_patterns.py` (41 collected, parametrized) validates the from-scratch chi-square test against the standard critical-value table and covers co-occurrence, transitions, pathway mining, temporal trend, and cohort comparison. `test_discovery.py` (19) covers candidate-category proposals, including static and behavioral checks that the module never writes to a taxonomy file. `test_publication.py` (36) covers the methods paragraph, tables, and SVG figures (validated as well-formed XML), including regression tests for two real bugs caught during development. `test_quickstart.py` (11) covers the guided walkthrough, including that it never opens a file (sample_data/ isn't in the installed wheel). `test_ari.py` (10) independently re-verifies the Adjusted Rand Index implementation behind the embedding-validation benchmark. None of it needs an API key or a display, and none of it makes a real network call to OpenAI.

## Advanced features

All of these use only the Python standard library and have their own tests.

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

**PABAK and the kappa paradox.** When marginals are highly skewed, Cohen's kappa can be paradoxically low even though raters agree on most items. `compute_kappa_diagnostics` returns PABAK (`2*Po - 1`) along with the bias and prevalence indices (Byrt et al. 1993) so you can tell whether a low kappa reflects genuine disagreement or just a skewed taxonomy:

```python
from confusion_mapper import compute_kappa_diagnostics
d = compute_kappa_diagnostics(human, ai)
print(d['kappa'], d['pabak'], d['bias_index'], d['prevalence_index'])
```

**Gwet's AC1.** A second, more principled answer to the same kappa-paradox problem PABAK diagnoses. Cohen's kappa assumes raters label independently in proportion to their own marginals -- a bad model when one category dominates, which drags kappa down even on near-perfect data. AC1 (Gwet, 2008) replaces that assumption with how uniformly items are spread across categories, so it stays close to raw agreement on the skewed-category-prevalence data most coding projects actually produce:

```python
from confusion_mapper import gwet_ac1
r = gwet_ac1(human, ai)
print(r['ac1'], r['interpretation'])
```

Report kappa *and* AC1 together, not whichever one is higher -- also available from the CLI via `diagnostics`.

**Dataset validation.** Before any statistic runs on a CSV, catch the data-entry mistakes that would otherwise silently distort it: missing labels, a label that isn't in your taxonomy (a typo), duplicate `item_id`s, empty distractor text.

```python
from confusion_mapper import validate_dataset
report = validate_dataset(rows, categories=["RF", "PK", "CF", "INT"])
print(report['valid'], report['errors'], report['warnings'])
```

**Krippendorff's alpha.** An alternative IRR coefficient that generalises to more than two raters and supports nominal, ordinal, or interval-level measurements:

```python
from confusion_mapper import krippendorff_alpha
r = krippendorff_alpha(human, ai, level='ordinal')
print(r['alpha'], r['interpretation'])
```

**Sample-size planning.** Before you collect calibration labels, estimate how many you need to bound the kappa CI within a target half-width:

```python
from confusion_mapper import recommend_sample_size
n = recommend_sample_size(expected_kappa=0.80, ci_half_width=0.10, n_categories=4)
print(f"Need at least {n['recommended_n']} items.")
```

**Custom taxonomy via JSON.** Swap the default CFI categories for any 2-or-more
category nominal scheme. A working example sits at
`sample_data/custom_taxonomy.json`:

```python
from confusion_mapper import load_taxonomy_from_json, compute_cohens_kappa
codes, tax = load_taxonomy_from_json("sample_data/custom_taxonomy.json")
r = compute_cohens_kappa(human, ai, categories=codes)
```

**Auto-generated prompt refinements.** Feed the confusion matrix back into the prompt: `suggest_prompt_refinements` ranks the largest off-diagonal cells and emits a Markdown report with concrete contrastive instructions you can paste into the AI prompt.

```python
from confusion_mapper import suggest_prompt_refinements
r = suggest_prompt_refinements(human, ai, top_k=3)
print(r['report_markdown'])
```

**Fleiss's kappa for three or more raters.** Cohen's kappa is two-rater. When you have a panel, use `fleiss_kappa`:

```python
from confusion_mapper import fleiss_kappa
ratings = [
    {'RF': 3, 'PK': 0, 'CF': 0, 'INT': 0},  # all 3 raters: RF
    {'RF': 0, 'PK': 0, 'CF': 3, 'INT': 0},  # all 3 raters: CF
    {'RF': 1, 'PK': 2, 'CF': 0, 'INT': 0},  # split 1 RF / 2 PK
]
print(fleiss_kappa(ratings)['kappa'])
```

## Command line

New to this? `pip install confusion-mapper && confusion-mapper quickstart` runs a self-contained, non-interactive walkthrough (kappa -> diagnostics -> per-category breakdown -> a codebook snippet -> pointers to everything else) on built-in demo data -- no CSV, no API key, nothing to set up first.

<p align="center"><img src="quickstart_demo.gif" alt="confusion-mapper quickstart running in a terminal" width="640"></p>

Prefer a browser? `dashboard/index.html` runs three of this package's real functions (Cohen's kappa, Gwet's AC1, the confusion-matrix heatmap) client-side via [Pyodide](https://pyodide.org) -- paste labels, get results, nothing uploaded. Open it directly or host it on GitHub Pages.

ConfusionMapper has a Unix-style CLI with sixteen subcommands. Pipe any CSV with `human_label, ai_label` columns through it:

```bash
python -m confusion_mapper quickstart   # start here -- no CSV needed
python -m confusion_mapper kappa        sample_data/example_labels.csv --bootstrap 10000
python -m confusion_mapper alpha        sample_data/example_labels.csv --level ordinal
python -m confusion_mapper diagnostics  sample_data/example_labels.csv
python -m confusion_mapper refine       sample_data/example_labels.csv --top 3
python -m confusion_mapper plan         --kappa 0.80 --ci 0.05 --categories 4
python -m confusion_mapper validate     sample_data/example_labels.csv
python -m confusion_mapper multirater   sample_data/example_multirater.csv
python -m confusion_mapper export       sample_data/example_labels.csv --out results/
python -m confusion_mapper evidence     panel confusion_mapper_sessions.json
python -m confusion_mapper codebook     --out codebook.md
python -m confusion_mapper embed-index  sample_data/example_labels.csv --index embeddings.json
python -m confusion_mapper embed-search "confusing voltage with current" --index embeddings.json
python -m confusion_mapper discover     embeddings.json
python -m confusion_mapper patterns     transitions longitudinal.csv --timepoint-order pretest,posttest
python -m confusion_mapper publication  sample_data/example_labels.csv --bootstrap 10000 --out results.md
```

`assist` (the AI-suggest/human-approves workflow) is documented separately below -- see [AI-assisted mode](#ai-assisted-mode). It's deliberately not grouped with the subcommands above: those are all one-shot, JSON/Markdown-out, non-interactive reports; `assist` is interactive and produces a session file, the same category as the plain `confusion-mapper` reliability-check session, not a stats report.

Every subcommand prints JSON (or Markdown for `refine`) on stdout, so you can redirect into a results bundle without writing any glue code.

`kappa`, `alpha`, `diagnostics`, and `refine` run `validate` on the file automatically before computing anything. By default a validation problem (a typo'd label, a duplicate `item_id`, a blank cell) prints a one-line warning to stderr and the computation still runs on the data as given, so nothing breaks your existing workflow. Add `--strict` to abort instead and print the full error report:

```bash
python -m confusion_mapper kappa data.csv --strict
```

`validate` on its own always prints the full report and exits `1` if there are any errors, `0` otherwise, so it's safe to use as a CI or pre-commit gate on a growing dataset.

**Three or more human coders.** `multirater` takes a wide-format CSV (`item_id` column + one column per rater) and returns Cohen's kappa + AC1 for every pair of raters, Fleiss' kappa across the whole panel (3+ raters), and every item the panel didn't unanimously agree on, ranked worst-disagreement-first with a majority-vote suggestion:

```bash
python -m confusion_mapper multirater sample_data/example_multirater.csv
python -m confusion_mapper multirater sample_data/example_multirater.csv --conflicts-only
```

`majority_label` is a suggestion, not an automatic consensus write -- a tied item (no majority) reports `majority_label: null` and lists the tied options in `tied_labels` for a human to resolve. Nothing in this workflow silently overwrites a rater's original label.

**Export packages.** `export` writes a clean CSV plus a ready-to-open companion for R, SPSS, and JASP -- so getting coded data into the tool your co-author already uses doesn't mean re-typing four category labels by hand and hoping you didn't transpose one:

```bash
python -m confusion_mapper export sample_data/example_labels.csv --out results/
python -m confusion_mapper export sample_data/example_labels.csv --out results/ --formats r,jasp
```

- **R**: CSV + a `.R` script that sets `human_label`/`ai_label` as ordered factors matching the taxonomy in effect and runs `irr::kappa2()`.
- **SPSS**: CSV + a `.sps` syntax file (`GET DATA` + `VALUE LABELS`) -- plain-text and stable across SPSS versions, deliberately not a binary `.sav`, so this package doesn't need a compiled dependency for it.
- **JASP**: CSV + a short instructions file, since JASP opens CSV directly -- points at JASP's built-in "Cohen's & Fleiss' Kappa" analysis.

Add `--taxonomy-file your_taxonomy.json` to get real category names (not the CFI ones) in the R factor labels / SPSS value labels / JASP instructions for a custom taxonomy -- see [above](#the-four-error-types) and `sample_data/item_bank_distractor_taxonomy.json`.

Parquet and a from-scratch SPSS `.sav` writer aren't implemented -- both would need a binary/compiled dependency (pyarrow, pyreadstat) this otherwise-pure-stdlib package doesn't have any other reason to carry. If you need Parquet: `pandas.DataFrame(rows).to_parquet(...)` covers it in one line once pandas is installed.

**Evidence panel.** For every coded item: the original answer, the assigned label, the reasoning behind it, free-text notes, and a full revision history. Deliberately *not* wired into the live interactive session -- prompting a coder to type a reason for every one of 15-90 distractors mid-session would change the pace and cognitive load of actual data collection, which isn't a change to make silently. Instead this works post-hoc, on top of an already-saved session file, through a separate append-only log that never opens the session file for writing:

```bash
python -m confusion_mapper evidence panel  confusion_mapper_sessions.json
python -m confusion_mapper evidence note   confusion_mapper_sessions.json Q1_D2 "borderline case, discuss" --author Manik
python -m confusion_mapper evidence revise confusion_mapper_sessions.json Q1_D2 CF --reason "AI reasoning was more convincing on review" --author Manik
```

`revise` requires `--reason` -- a label change without a stated reason defeats the point of keeping the log, so it's enforced, not just encouraged. Revising never touches the original session file: the item's `assigned_label` (as recorded live) stays exactly what it was, and `current_label` in the panel report reflects the latest revision, computed on the fly. Every session file this points at is opened read-only.

**Codebook generator.** Renders a taxonomy's definitions and examples as a Markdown research appendix, stamped with the same `taxonomy_fingerprint` used in session provenance (for the built-in CFI taxonomy) so a reader can tell exactly which version of the categories a given appendix documents:

```bash
python -m confusion_mapper codebook --out codebook.md
python -m confusion_mapper codebook --taxonomy-file sample_data/item_bank_distractor_taxonomy.json --out item_bank_codebook.md
```

Every category's decision-rule field is left as an explicit, literal placeholder (`*(fill in from your coding manual / Stage 1 RR methods -- not auto-generated)*`), not synthesized text. Definitions and examples are real, already-written content; a decision rule is part of a research instrument's methodology, and inventing one from the definition text and presenting it as finished would be fabricating that methodology, not generating a document from it.

## AI-assisted mode

Everything above -- the plain `confusion-mapper` session, `kappa`, `alpha`, `diagnostics` -- exists to answer one question: does a human and an AI, rating *independently*, agree? That independence is what makes the resulting kappa meaningful. `assist` answers a different question -- can an AI make bulk-coding faster? -- and it does that by showing the AI's opinion to the human *before* they decide, which is the opposite of independent on purpose. Mixing the two up is the one failure mode this feature was designed around: a label produced in assist mode is not independent evidence of anything, so `assist` never computes or reports a kappa, AC1, or alpha, full stop, and every session it writes carries an explicit `reliability_warning` string so that stays true even if the file is read out of context later, without this README nearby.

Use `assist` after you've already established kappa >= 0.70 with the blind session above and trust your rubric / AI prompt, to code a larger dataset faster than one-at-a-time blind rating allows:

```bash
export OPENAI_API_KEY="your-key-here"   # optional -- without it, every item is a plain manual entry
confusion-mapper assist my_dataset.csv --index confusion_mapper_embeddings.json
```

`my_dataset.csv` needs a `distractor_text` column at minimum; `item_id`, `question_text`, `correct_answer`, and `topic` are optional but sharpen the AI's suggestion. For each item you'll see the AI's suggested category, a confidence score, one sentence of reasoning, and (if you pass `--index`) the nearest already-coded examples from a persistent local library -- press Enter to accept the suggestion, or type `1`-`4` to override it (a reason is required for an override; there's no skipping that). The saved session reports an `acceptance_rate` -- how often you kept the AI's suggestion -- which is a real, useful efficiency metric, just not a reliability one. Sessions land in `confusion_mapper_assist_sessions.json`, never `confusion_mapper_sessions.json` (the blind-mode file), so the two kinds of data can't end up merged by accident even if you go looking for "all my sessions" later.

**The persistent semantic-search library** behind `--index` is built and updated only when you explicitly ask -- never automatically during a live session, the same reasoning that kept `run_session()` free of any new network calls when provenance was added. Build or grow one from any CSV:

```bash
confusion-mapper embed-index sample_data/example_labels.csv \
  --index confusion_mapper_embeddings.json \
  --id-column item_id --text-column distractor_text --label-column human_label

confusion-mapper embed-search "students confusing voltage with current" \
  --index confusion_mapper_embeddings.json --k 5
```

Two embedding backends, chosen once when an index is first created and locked in for that index's lifetime (so a later run without an API key can't silently produce a dimension mismatch buried in the file):

- **`openai`** (`--backend openai`): OpenAI's `text-embedding-3-small`, real semantic understanding -- catches synonyms and paraphrase, not just shared words. Needs `OPENAI_API_KEY` and a network call per item.
- **`local`** (the default): a from-scratch, pure-stdlib hashed bag-of-words vector. Zero cost, zero network, zero new dependencies -- and honestly weaker: it's a well-established technique ([feature hashing](https://en.wikipedia.org/wiki/Feature_hashing), Weinberger et al. 2009) that catches shared vocabulary and phrasing, not true synonyms. Documented as a fallback, not presented as equivalent to real embeddings.

## Misconception discovery

Clusters an embeddings index (single-linkage, by cosine-similarity threshold) and flags clusters where semantically similar items got inconsistent existing labels -- a signal the taxonomy might be missing a category, not a conclusion:

```bash
confusion-mapper discover confusion_mapper_embeddings.json --threshold 0.5 --min-cluster-size 3 --max-purity 0.6
```

This has a permanent design boundary, not a "coming later" one: **it never writes to any taxonomy file.** A study's taxonomy is part of its preregistered methods; a clustering heuristic silently redefining it would be a far bigger problem than any convenience it could offer. What you get instead is a Markdown report -- cluster contents, existing label breakdown, purity score -- for a human to read and decide. If you agree a cluster is real, the next step is manual and explicit: add a code/name/definition/example to a taxonomy JSON (`sample_data/custom_taxonomy.json` is the shape) and load it with `load_taxonomy_from_json()` for your *next* coding round, never retroactively into data already coded under the taxonomy that produced it.

## Pattern mining

Over a *different* CSV shape than the rest of this package -- longitudinal / multi-item coded data (`respondent_id, item_id, label, timepoint, cohort`), not the human_label/ai_label rater-comparison shape -- because it answers a different question: not "do two raters agree," but "what do the labels you already trust look like across items, time, and groups."

```bash
confusion-mapper patterns cooccurrence  longitudinal.csv
confusion-mapper patterns transitions   longitudinal.csv --timepoint-order pretest,week2,posttest
confusion-mapper patterns pathways      longitudinal.csv --timepoint-order pretest,week2,posttest --sequence-length 2
confusion-mapper patterns trend         longitudinal.csv --timepoint-order pretest,week2,posttest
confusion-mapper patterns cohorts       longitudinal.csv
confusion-mapper patterns item-pair     longitudinal.csv --item1 Q1 --item2 Q2
```

- **`cooccurrence`** -- which misconceptions tend to show up together in the same respondent's profile, via lift (the standard association-rule-mining metric: >1 means the pair co-occurs more than chance).
- **`transitions`** -- P(label at t+1 | label at t) across consecutive timepoints, plus each category's most likely next state.
- **`pathways`** -- the most frequent label sequences ("A confused with B, then B confused with C") via n-gram frequency mining.
- **`trend`** / **`cohorts`** -- does the category distribution change over time / differ between groups, via a chi-square test of independence implemented from scratch (Pearson's statistic, Cramer's V effect size, and a p-value via the Wilson-Hilferty approximation -- checked against the standard chi-square critical-value table, accurate to within about 0.003 at 1 degree of freedom and well under 0.001 by 3+; see `patterns.py`'s docstring for the full accuracy note).
- **`item-pair`** -- a real hypothesis test (unlike `cooccurrence`, which pools across the whole item bank) for one specific, well-defined pair of items.

## Publication assistant

Every number in the output below comes from this package's own already-computed, already-tested statistics -- nothing here re-derives a number or makes a judgment call the underlying function didn't already make:

```bash
confusion-mapper publication sample_data/example_labels.csv --bootstrap 10000 --out results.md
```

Generates an APA-style methods paragraph, a reliability-statistics table, a category-frequency table, and two SVG figures (confusion-matrix heatmap, frequency bar chart -- pure string-generated SVG, no plotting dependency). The qualitative language in the methods paragraph ("agreement was almost perfect") is lifted verbatim from the primary descriptor of an interpretation string `compute_cohens_kappa`/`gwet_ac1` already computed, not decided fresh here. Every generated document is stamped `DRAFT -- REQUIRES HUMAN REVIEW` -- this is a first draft to edit, the same spirit as the codebook generator's decision-rule placeholders, not paste-into-a-manuscript-unread output.

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

## Project layout

```
confusion_mapper/
├── taxonomy.py       constants + the CFI taxonomy dict
├── question_bank.py  the built-in NCERT-style question bank
├── stats.py          Cohen's kappa, Fleiss' kappa, Krippendorff's alpha, Gwet's AC1, etc.
├── validation.py     dataset validation (missing labels, duplicate IDs, impossible values)
├── multirater.py     3+ human coder workflow: agreement matrix, panel Fleiss' kappa, conflicts
├── export.py         R / SPSS / JASP export packages
├── evidence.py       post-hoc evidence panel: notes + append-only revision log
├── codebook.py       publication-ready research appendix from the taxonomy
├── embeddings.py     dual-backend embeddings + persistent semantic-search index + clustering
├── discovery.py      human-in-the-loop candidate-category proposals (never writes to any taxonomy)
├── patterns.py       co-occurrence, transitions, temporal trend, cohort comparison
├── publication.py    methods paragraph, tables, and SVG figures from real computed stats
├── assist.py         AI-suggest/human-approves workflow (separate from the
│                     blind reliability-check path; never produces a kappa)
├── ai.py             the ChatGPT rater (classification + question generation)
├── storage.py        session load / save (JSON)
├── gui.py            the tkinter results dashboard
├── console.py        the interactive console session flow
├── cli.py            the stats-subcommand router, main(), and run()
└── __main__.py        enables `python -m confusion_mapper`
```

Everything importable from `confusion_mapper` before this split (`compute_cohens_kappa`, `ERROR_TYPES`, and so on) still is; see the package docstring in `confusion_mapper/__init__.py` for the full list. If you're adding a new statistic, it belongs in `stats.py`; a new rater backend belongs alongside `ai.py`.

Repo root, beyond the package itself:

```
case_study/       reproducible worked example (see Case study, above)
benchmarks/       the embedding-backend validation study (see Benchmarks, above)
sample_data/      example CSVs and taxonomy JSONs used throughout this README
examples/         a minimal headless script (see Headless example, above)
dashboard/        index.html -- runs kappa/AC1/confusion-matrix in-browser via Pyodide
quickstart_demo.gif   real, captured `confusion-mapper quickstart` output, not staged
```

## Contributing

Bug reports, feature requests, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Acknowledgements

Initial development was completed as part of Stanford Code in Place 2026. The tool is used in the Confusion Fingerprint Index research programme.

## License

MIT License © 2026 Manik Maurya. See [LICENSE](LICENSE) for details.
