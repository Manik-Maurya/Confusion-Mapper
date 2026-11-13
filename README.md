# ConfusionMapper

A Python tool for classifying wrong answer choices in multiple-choice questions by the type of cognitive error they represent, and for computing how well a human researcher and an AI rater agree on those labels.

[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.20807432-1682D4?logo=zenodo&logoColor=white)](https://doi.org/10.5281/zenodo.20807432)
[![Tests](https://github.com/Manik-Maurya/Confusion-Mapper/actions/workflows/tests.yml/badge.svg)](https://github.com/Manik-Maurya/Confusion-Mapper/actions/workflows/tests.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.9+](https://img.shields.io/badge/Python-3.9%2B-blue.svg)](https://www.python.org/)

## What it does

If you want to make a claim about qualitative data, two people have to be able to read the same item and put roughly the same label on it. Otherwise the label is just one person's opinion. Cohen's kappa is the number that tells you whether that condition is met.

ConfusionMapper does the whole loop for you. You go through a set of distractors one at a time and pick a category for each. If you have an OpenAI key, an AI rater labels them in parallel. When you are done, the program computes Cohen's kappa, draws a 4x4 confusion matrix of where the two of you agreed and disagreed, and saves the whole session to JSON.

I built it as the reliability check for a preregistered RCT on cognitive error feedback in government junior high schools in Kanpur Dehat (OSF: https://doi.org/10.17605/OSF.IO/YU6P5). We could not collect any real data in that study until kappa cleared 0.70.

Once you have a few human coders, it also answers the question that always comes next: is the AI good enough to replace one of them? See [Can the AI replace a human coder?](#can-the-ai-replace-a-human-coder)

## The four error types

The taxonomy is called the Confusion Fingerprint Index (CFI). It splits wrong answers into four categories:

| Code | Name | What it looks like |
|------|------|---------------------|
| RF | Recall Failure | No memory trace at all; the answer is essentially random |
| PK | Partial Knowledge | Almost right; the direction is correct but the model is incomplete |
| CF | Confabulation | A coherent misconception held with confidence |
| INT | Interference | A correct answer pulled from the wrong topic |

CFI is what this package defaults to, but none of the machinery actually needs it. Every stats function, the multi-rater workflow, the validator, the exporters, the codebook generator, and the embeddings tools take a `categories` list. Load your own taxonomy from a JSON file with `load_taxonomy_from_json()` (each entry needs a `code`, `name`, and `definition`; `number`, `color`, and `example` are optional) and everything works the same way.

To show this, `sample_data/item_bank_distractor_taxonomy.json` ships a completely different scheme: a 4-category taxonomy for how distractors *behave* in a large-scale MCQ item bank. Non-Functional, Potentially-Lead-to-Misconception, Functional, and Ambiguous/Flawed. Modelled on real item-analysis literature (the under-5% non-functional threshold and the PLM concept from math-education studies; citations are in the file itself). It is not an official OECD/PISA taxonomy, PISA uses item-specific partial-credit rubrics. This is a demo to prove the pipeline is not hardcoded to CFI:

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

**Session provenance.** Every saved session includes, alongside the ratings and computed statistics: a `session_id` (UUID4), `software_version` (the actually-installed confusion-mapper version, read from package metadata), `taxonomy_fingerprint` (a 12-character hash of the exact CFI category definitions in effect, lets you tell later whether two sessions were coded under the same taxonomy or it changed in between), and `python_version`. All four are purely additive: every key that was in a session file before this release is still there, computed by the exact same, untouched functions.

## Can the AI replace a human coder?

New in 2.8.0, and the feature I think matters most.

Kappa tells you how much you and the AI agree. It does not tell you whether you are allowed to drop a human coder and use the AI's labels instead, which is the question everyone using an LLM as a coder actually has. Most papers answer it with a kappa cutoff that someone picked once and everyone else copied.

Calderon, Reichart and Dror (ACL 2025) proposed a real statistical test for it, the Alternative Annotator Test. The idea is simple. Take one human coder out, and ask whether the AI agrees with the remaining coders at least as well as the coder you took out does. Do that for every coder, run a one-sided t-test each time with a small allowance, epsilon, for the fact that the AI is cheaper and faster, correct for multiple testing, and count how many coders the AI beats. If it beats at least half of them, it passes.

`confusion-mapper alt-test` is a standard-library implementation of their method, built into the same CSV and reporting pipeline as the rest of this package. The method is theirs. Their reference code is a notebook that needs numpy and scipy, so I checked mine against both: identical verdicts on 369 random panels, p-values matching to within 5e-14. The full write-up is in [`benchmarks/ALTTEST_VALIDATION.md`](benchmarks/ALTTEST_VALIDATION.md).

```bash
# one AI against three human coders, epsilon from the authors' preset for skilled coders
confusion-mapper alt-test sample_data/example_alttest.csv \
  --ai-column ai_prompt_v1 --human-columns coder_A,coder_B,coder_C \
  --annotators skilled --report alttest_report.md

# two prompts head to head, ranked by advantage probability
confusion-mapper alt-test sample_data/example_alttest.csv \
  --ai-column ai_prompt_v1 --ai-column ai_prompt_v2 --annotators skilled

# before you pay anyone to label: how many items will you need?
confusion-mapper alt-test-plan --annotators skilled --coders 3 --categories 4 \
  --coder-noise 0.3 --ai-noise 0.3
```

On the bundled example, `ai_prompt_v1` passes: after correction it beats 2 of the 3 coders. `ai_prompt_v2` fails and beats none of them, even though its advantage probability is 0.80. That is the whole point. An AI that agrees with people most of the time can still be clearly worse than any one of them. coder_B is worth a look too. Against v1 its raw p-value is 0.043, under the usual 0.05, but it does not survive the Benjamini-Yekutieli correction, so it does not count as a win. The example file is synthetic, and `examples/make_alttest_example.py` rebuilds it byte for byte, so you can check it was not hand-tuned.

The Markdown report gives you the verdict in plain words, a coder-by-coder table, the mean pairwise kappa among your humans (the authors ask you to report it), their six-item reporting checklist with what is already filled in, a draft methods paragraph, and the citation.

Three design choices I want to be upfront about:

- **You have to choose epsilon yourself.** There is no default. One of `--epsilon`, `--annotators expert|skilled|crowd` (0.2, 0.15, 0.1, the authors' rule of thumb) or `--prereg` is required. Picking epsilon after seeing the results, and nudging it until the AI passes, is exactly the flexibility the test exists to remove, so the tool will not pick one for you. Since 2.9.0 it can also hold you to your choice, see below.
- **It refuses to guess which columns are human.** While trying it on my own example file, I asked for one AI column and the other AI column quietly became a fourth "human coder". No crash, just wrong numbers. Now, if a leftover column looks like model output (`ai_...`, `llm...`, `gpt...`), it stops and asks you to name the human columns.
- **It keeps the authors' minimums.** Items need at least 2 human labels, coders need at least 30 usable items, and it warns you below 3 coders or 50 items. Blank cells are fine, coders do not all have to label the same items.

`alt-test-plan` runs the authors' simulation model from their appendix C in plain Python: random label priors, and coders and an AI who report the true label with probability 1 minus their noise. It returns the pass rate at each sample size, the smallest n that reaches 80% power, and the human kappa your noise setting actually implies, so you can sanity-check it against your own pilot data. At noise 0.3 it implies a kappa of about 0.49. The authors report 0.48 for the same setting.

### Lock your settings before the data exists

New in 2.9.0. Telling people to choose epsilon in advance is easy. Proving you did is harder. So before anyone labels anything, write your settings to a plan file:

```bash
confusion-mapper alt-test-prereg --annotators skilled \
  --ai-column ai_prompt_v1 --ai-column ai_prompt_v2 \
  --human-columns coder_A,coder_B,coder_C --planned-items 81 \
  --out alttest_prereg.json
```

It prints a SHA-256 hash of the locked decisions: epsilon and where it came from, the FDR level, the scoring function, the minimums, the pass threshold, and the column names. Put the file, or at least the hash, into your OSF preregistration. Later, run the test against it:

```bash
confusion-mapper alt-test sample_data/example_alttest.csv \
  --prereg sample_data/example_alttest_prereg.json --report alttest_report.md
```

The settings and columns come from the plan. If anything you type on the command line contradicts the plan, say `--epsilon 0.2` when you locked 0.15, the run stops and tells you exactly what differs. You can still go ahead with `--allow-deviation`, because real studies sometimes have to, but then every deviation is listed at the top of the report and counted in the methods paragraph. If someone edits the locked settings inside the plan file afterwards, the hash no longer matches and the run refuses to start.

Two things it does not pretend to do. The hash covers the decisions, not the date written in the file, because a date inside a file proves nothing. The date that counts is the one your registry stamps when you register. And a different number of items than planned is reported as a note, not a deviation, since losing a few items is normal, but it is still written down. The bundled `example_alttest_prereg.json` was obviously made after the example data existed. It is there to show the mechanism, with real data you would make it first.

### How fragile is the verdict?

Also new in 2.9.0, and this part is my addition, not the authors'. The alt-test gives one verdict on one sample of items. Add `--bootstrap 1000` and the whole test, FDR correction included, is rerun on 1,000 resamples of the items. The report then says how often the verdict came out the same, gives a 95% interval for the advantage probability, and shows how often each coder was beaten.

On the example data, with seed 20260623 and 1,000 resamples, `ai_prompt_v1`'s pass holds in about 76% of resamples, its advantage probability interval runs from about 0.80 to 0.94, and coder_B, the one coder it did not beat, is beaten in only 45% of resamples. So it is a real pass, but not a rock-solid one, and a reviewer deserves to know that. `ai_prompt_v2`'s fail holds in about 87%.

That number is not a p-value and not statistical power. A verdict that holds in only about half the resamples sits right on the edge, which is what you would expect when a p-value lands near the cutoff. The honest fix is more items, not a different epsilon.

If you ran the AI more than once on the same items, `confusion-mapper multirater` on the run columns gives you the AI's run-to-run Fleiss' kappa, which is worth reporting next to all of this.

From Python:

```python
from confusion_mapper import load_alttest_csv, alt_test, compare_judges

humans, ais = load_alttest_csv("panel.csv", ["ai_v1", "ai_v2"])
r = alt_test(ais["ai_v1"], humans, epsilon=0.15)
print(r["verdict"], r["winning_rate"], r["advantage_probability"])

from confusion_mapper import bootstrap_alt_test
rb = bootstrap_alt_test(ais["ai_v1"], humans, n_resamples=1000, seed=1, epsilon=0.15)
print(rb["verdict_held"], rb["advantage_probability_ci"])
```

If you use it, please cite the method's authors:

> Calderon, N., Reichart, R., & Dror, R. (2025). The Alternative Annotator Test for LLM-as-a-Judge: How to Statistically Justify Replacing Human Annotators with LLMs. *Proceedings of the 63rd Annual Meeting of the Association for Computational Linguistics (Volume 1: Long Papers)*, 16051-16081. https://aclanthology.org/2025.acl-long.782/

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

`benchmarks/` answers a question the rest of this README skips: does the local hashed bag-of-words embedding backend actually capture real signal, or is it noise pretending to be a feature? Full writeup is in [`benchmarks/EMBEDDING_VALIDATION_FINDINGS.md`](benchmarks/EMBEDDING_VALIDATION_FINDINGS.md). The short version is not flattering, and I am reporting it anyway.

I compared the local backend's clusters against the real `human_label` column on both bundled labelled datasets using Adjusted Rand Index (my own implementation in `ari.py`, with a hand-derived worked example, checked three different ways). At every threshold I tried, ARI came out at or near zero. The local backend does not recover the CFI taxonomy from content alone.

The writeup traces this to a property of the data, not a bug in the code. Cognitive error type and topic are close to orthogonal by design here: every label spans many different questions, and distractors *within* one question carry different labels. Bag-of-words has nothing to hold on to. A study that found high agreement in this setup would honestly be the more suspicious result.

`benchmark_embeddings.py` runs the same comparison against the `openai` backend. I have not run it yet, that needs an API key and network access I do not want to spend right now. If you run it, the findings doc is where the second half of the comparison belongs.

```bash
python benchmarks/embedding_validation_study.py   # the local-only study, as reported
python benchmarks/benchmark_embeddings.py          # local vs. openai, needs OPENAI_API_KEY
python benchmarks/alttest_crosscheck.py            # alt-test vs. the authors' code and scipy, needs numpy + scipy
```

The alt-test cross-check is a happier story. [`benchmarks/ALTTEST_VALIDATION.md`](benchmarks/ALTTEST_VALIDATION.md) checks the from-scratch alt-test against the authors' own reference implementation and against scipy, and they agree everywhere it matters.

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

656 tests across twenty-two files. They finish in well under a minute, none of them touches the network, and none of them needs an API key or a display. One of them only runs if scipy happens to be installed, it cross-checks the alt-test's t distribution against scipy's.

The breakdown, in case you want to know what is being checked:

- `test_kappa.py` (40): the kappa formula against hand-verified worked examples, weighted kappa, bootstrap CIs, PABAK and the bias/prevalence diagnostics, Gwet's AC1, Krippendorff's alpha, the sample-size estimator, custom-taxonomy loading, the confusion matrix, Fleiss' kappa, and the CLI router.
- `test_refine.py` (10): the prompt-refinement engine and the `refine` subcommand. Until 2.10.0 this README claimed `test_kappa.py` covered the engine. It did not, and that gap hid a real bug, see the changelog.
- `test_validation.py` (15), `test_multirater.py` (20), `test_export.py` (19), `test_provenance.py` (11), `test_evidence.py` (25), `test_codebook.py` (12): one file per module they cover.
- `test_embeddings.py` (52): both embedding backends, cosine similarity, the full persistent-index lifecycle, and single-linkage clustering.
- `test_assist.py` (20): the AI-assist loop end to end via simulated stdin. Includes a regression test for a real bug I caught during development.
- `test_custom_taxonomy.py` (26): non-CFI taxonomy support end to end, including a full run on the distractor-functioning example.
- `test_patterns.py` (41): the from-scratch chi-square test against a standard critical-value table, plus co-occurrence, transitions, pathways, temporal trend, and cohort comparison.
- `test_discovery.py` (19): candidate-category proposals, including a behavioural check that the module never writes to a taxonomy file.
- `test_publication.py` (36): the methods paragraph, tables, and SVG figures (validated as well-formed XML). Two of these tests were added after real bugs.
- `test_quickstart.py` (11): the guided walkthrough, including that it never opens a file (`sample_data/` is not in the installed wheel).
- `test_ari.py` (10): an independent second implementation of Adjusted Rand Index that the embedding-validation benchmark is checked against.
- `test_itembank.py` (49): the CFI-labelled item generator, including a 200-seed sweep per template that would catch any distractor-vs-correct-answer collision, and explicit regression tests for two real bugs I caught during development.
- `test_alttest_bootstrap.py` (15) and `test_alttest_prereg.py` (33): the bootstrap robustness check and the preregistration lock. They include a test that pins the exact bootstrap figures quoted in this README, and tests that a run departing from its plan is stopped, that an edited plan is caught, and that a forced deviation always ends up in the report. Before trusting them I broke the code on purpose three times (repeated items sharing a key, a hash that ignored epsilon, deviations that never blocked) and checked that each break made these tests fail.
- `test_worksheets.py` (23): the teacher web page and class scoring. It runs the page's JavaScript in Node and compares it with the Python scoring on random classes, checks the page's unit pool against the generator, checks the page needs no internet, scores small hand-built classes whose answers are known, and, where jsdom is installed, drives the whole page the way a teacher would.
- `test_pisa.py` (69): the PISA-style unit generator. For every template and 300 seeds it takes the raw numbers stored in each unit and works out every answer again with separate code, then checks the options are clean, every wrong answer is diagnosed, the answer letters are spread evenly, the booklet gives nothing away, and the example booklet and key in `examples/` are exactly what the generator produces today.
- `test_alttest.py` (100): the alt-test. The t distribution against exact closed forms for 1 and 2 degrees of freedom and printed t-table values, Benjamini-Yekutieli on hand-worked cases including its step-up behaviour, a fully hand-worked 3-coder example down to the t statistic, the paper's optimal-judge theorem (majority vote and mean rating both get advantage probability exactly 1), missing data, the power simulator, the reports, the CLI, and a regression test for the column bug described above.

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

**Gwet's AC1.** A second, more principled answer to the same kappa-paradox problem PABAK diagnoses. Cohen's kappa assumes raters label independently in proportion to their own marginals, a bad model when one category dominates, which drags kappa down even on near-perfect data. AC1 (Gwet, 2008) replaces that assumption with how uniformly items are spread across categories, so it stays close to raw agreement on the skewed-category-prevalence data most coding projects actually produce:

```python
from confusion_mapper import gwet_ac1
r = gwet_ac1(human, ai)
print(r['ac1'], r['interpretation'])
```

Report kappa *and* AC1 together, not whichever one is higher, also available from the CLI via `diagnostics`.

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

## PISA-style maths units

> **Teachers: you do not need anything else on this page.** Open the worksheets page, https://manik-maurya.github.io/Confusion-Mapper/worksheets/, or download [`worksheets/index.html`](worksheets/index.html) and open it in any browser. It makes the booklet and the teacher's key, takes your class's answers, and tells you what to reteach first. No installation, no account, works offline once saved, and nothing you type leaves your device. The short guide is [`docs/pisa-teacher-guide.md`](docs/pisa-teacher-guide.md).

New in 2.10.0. PISA does not test maths as a list of sums. Each item is a small unit: a real-world situation, often with a table, and then a few questions about it, each one checking a different part of mathematical literacy. India took part once, in 2009, through about 16,000 students from 400 schools in Himachal Pradesh and Tamil Nadu, and finished 72nd of 74. The government of the day blamed questions that were "out of context" and stayed out of the next two rounds ([The Better India, 2018](https://thebetterindia.com/158849/india-pisa-news-students/)). Whatever you think of that argument, the fix is not to avoid this kind of question. It is to give children practice with it, in situations they actually recognise.

`confusion-mapper pisa` writes units like that, set in Indian contexts: a mobile data plan, a monsoon rain gauge, a school garden, a bus to the district headquarters, the price of dal, a class survey, a rooftop water tank, and two kinds of bacterial growth.

```bash
# see the 8 unit templates
confusion-mapper pisa --list

# a full set: student booklet + teacher's key, reproducible under the seed
confusion-mapper pisa 8 --seed 1 --booklet booklet.md --key teacher_key.md

# only space and shape, or only personal contexts
confusion-mapper pisa 4 --content space_and_shape --booklet shapes.md --key shapes_key.md
confusion-mapper pisa 4 --context personal --out units.json

# drop the multiple-choice questions into a normal CFI coding session
confusion-mapper pisa 8 --seed 1 --item-bank pisa_items.json
```

The structure follows the published PISA 2022 mathematics framework (https://pisa2022-maths.oecd.org): the four content categories (quantity, uncertainty and data, change and relationships, space and shape), the four contexts (personal, occupational, societal, scientific), and the processes (formulate, employ, interpret and evaluate, plus mathematical reasoning, the 2022 framework's new emphasis). A set of eight units has 24 questions, exactly 6 in each content category and 6 in each context, across all four processes and three formats: multiple choice, true/false rows, and written answers with a scoring guide. The growth unit targets one of the framework's four special emphases, growth phenomena, because seeing that doubling eventually beats steady adding is exactly the kind of thing linear intuition gets wrong.

The part that is ConfusionMapper's own is the teacher's key. Every wrong option, every wrong true/false judgement and every common wrong written answer has a CFI label and a line on the thinking behind it. So the key does not just mark an answer wrong. It says what a child who gave that answer probably believes: that a 20% rise and a 20% fall cancel out (CF, Confabulation), or that the question about the fence was about area (INT, Interference), or it shows they did the division but never turned it into whole kilograms (PK, Partial Knowledge). That is what tells a teacher what to reteach.

Want to see one without installing anything? [`examples/pisa_booklet_example.md`](examples/pisa_booklet_example.md) is a full eight-unit booklet and [`examples/pisa_teacher_key_example.md`](examples/pisa_teacher_key_example.md) is its key. A test regenerates both and fails if they ever drift from what the code produces.

What these are not. They are original templates, not released PISA items. They have not been field-tested, so they have no difficulty estimates. PISA is written for 15-year-olds. These use Class 7 to 9 maths, so they suit students around Class 8 to 10. The numbers in the tables are made up for practice, and the booklet says so. Every booklet and key carries that disclaimer.

How I made sure the answers are right. A generator like this fails quietly: one wrong answer key would go straight into a printed booklet. So the tests do not trust the templates. For every template and 300 seeds, they take the raw numbers stored in each unit and work out every answer again with separate code. They also check that no two options are ever the same, that the correct letter lands on A, B, C and D roughly equally, and that the student booklet contains no answers or labels. Before trusting those tests I broke the generator on purpose four times. Three breaks were caught straight away. The fourth taught me something: with sample A starting at 5 and sample B at 60 gaining 20 an hour, both have exactly 160 thousand cells at hour 5, so "first has more" means hour 6. My planted bug made that tie case silently vanish rather than fail, so there is now a test that pins it.

### Scoring a class

New in 2.11.0. A worksheet is only half the job. The other half is a teacher with thirty answer sheets deciding what to teach on Monday. So the set can come with a blank answer sheet, and `pisa-score` turns the filled-in sheet into a report that starts with the misconceptions that came up most:

```bash
confusion-mapper pisa 4 --seed 1 --out units.json --booklet booklet.md --key key.md \
  --response-sheet answers.csv --students 35
# ... the class sits the test, someone fills in answers.csv ...
confusion-mapper pisa-score units.json answers.csv --report class_report.md
```

In the answer sheet, a multiple-choice cell is the letter the child chose, a true/false cell is one letter per row (TFT), and a written answer is full, partial, none, or the code of the common wrong answer it matched (RF, PK, CF, INT). Blank means no answer, and a row with no answers at all is skipped, since that child was probably absent. Every wrong answer is traced back to its CFI label in the key, so the report can say something like "Q5.2, option B (It is Rs 120, the same as the original price.): 11 of 35 students, CF, Confabulation. Believes a rise and a fall of the same percentage cancel out, a common and confident misconception", followed by what usually helps with that kind of mistake.

The JSON output also has each child's Confusion Fingerprint Index, using the definitions already in this package: CFI-CF is CF errors over all diagnosed errors, CFI-INT is INT over INT plus RF, CFI-RF is RF over all diagnosed errors. Because the labels were fixed in the templates before any child answered, a researcher can use these directly, without a second round of coding.

The web page does the same scoring in JavaScript, because it has to work in a browser with no Python. Two copies of one piece of logic drift apart unless something stops them, so `tests/test_worksheets.py` runs the page's own scoring code in Node and compares every number with the Python version on 60 random classes, plus the same check for which answers each version rejects. I made sure that test can fail by breaking the page's code four ways (partial credit worth 2 points, the wrong denominator for CFI-INT, a reversed tie-break, lowercase answers refused). Each one was caught. The page also never computes an answer itself: it carries a pool of 200 units built by the Python generator, and a test fails if the page's pool and the generator ever disagree.

### What comes next

The units are in English for now. Translating the eight templates into Hindi, carefully, with the maths wording a Kanpur Dehat teacher would actually use, is the most useful next step, and it is one for a person who speaks both, not for a generator.

## Generate a calibration bank

New in 2.7.0. Writing 90 CFI-labelled distractors by hand for the RCT calibration set was slow and, honestly, biased: the wrong answers I could think of were shaped by the specific mistakes I had recently seen in class. `generate-bank` gives me a bigger, more even calibration pool where every distractor's CFI label traces back to the template rule that produced it.

```bash
# see what's available
confusion-mapper generate-bank --list-templates

# 30 items across all templates, reproducible under the seed
confusion-mapper generate-bank 30 --seed 1 --out my_bank.json

# only percent-word problems
confusion-mapper generate-bank 20 --templates math.percent_discount,math.percent_tax --out percents.json

# ai backend for topics outside the template set (needs OPENAI_API_KEY)
confusion-mapper generate-bank 10 --backend ai --topic "class 8 algebra" --out algebra.json
```

Two backends:

- **`templates`** (default). Deterministic, seedable, offline. Every distractor comes from a rule I can defend out loud, so the item traces back to the cognitive error type it is meant to test. Use this for the actual calibration set that reliability is computed on.
- **`ai`**. Uses OpenAI to draft items in the same shape for topics the templates do not cover. Faster and more flexible, but the CFI labels here are the model's opinion and should be verified by a human coder before those numbers are quoted anywhere.

Every item, from either backend, is validated at generation time. Two bugs I hit while building this are why the validator exists: an early template took the last two digits of the correct answer as a distractor and, for small numbers, produced an empty string; and the RF distractor pool could coincidentally sample the correct answer, which made two of the four options identical. Both have explicit regression tests in `tests/test_itembank.py`.

Generated banks slot straight into the rest of the pipeline: pipe one through `run_session()`, `kappa`, or `validate` without any adaptation.

## Command line

New here? Run `pip install confusion-mapper && confusion-mapper quickstart`. That walks you through the whole thing on built-in demo data. Kappa, then diagnostics, then a per-category breakdown, then a codebook snippet, then pointers to the rest. No CSV needed, no API key, nothing to set up.

<p align="center"><img src="quickstart_demo.gif" alt="confusion-mapper quickstart running in a terminal" width="640"></p>

Prefer the browser? `dashboard/index.html` runs three of the real functions (Cohen's kappa, Gwet's AC1, and the confusion-matrix heatmap) client-side through [Pyodide](https://pyodide.org). Paste your labels, get the numbers, nothing is uploaded. Open the file directly in a browser, or host it on GitHub Pages.

ConfusionMapper has a Unix-style CLI with twenty-two subcommands. Pipe any CSV with `human_label, ai_label` columns through it:

```bash
python -m confusion_mapper quickstart   # start here, no CSV needed
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
python -m confusion_mapper generate-bank 30 --seed 1 --out calibration_bank.json
python -m confusion_mapper alt-test     sample_data/example_alttest.csv --ai-column ai_prompt_v1 --ai-column ai_prompt_v2 --annotators skilled
python -m confusion_mapper alt-test-plan --annotators skilled --coders 3 --categories 4
```

`assist` (the AI-suggests, human-approves loop) is documented separately below, see [AI-assisted mode](#ai-assisted-mode). I keep it out of the list above on purpose. Everything above is one-shot, non-interactive, and prints JSON or Markdown. `assist` is interactive and produces a session file, more like the plain `confusion-mapper` session than a stats report.

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

`majority_label` is a suggestion, not an automatic consensus write, a tied item (no majority) reports `majority_label: null` and lists the tied options in `tied_labels` for a human to resolve. Nothing in this workflow silently overwrites a rater's original label.

**Export packages.** `export` writes a clean CSV plus a ready-to-open companion for R, SPSS, and JASP, so getting coded data into the tool your co-author already uses doesn't mean re-typing four category labels by hand and hoping you didn't transpose one:

```bash
python -m confusion_mapper export sample_data/example_labels.csv --out results/
python -m confusion_mapper export sample_data/example_labels.csv --out results/ --formats r,jasp
```

- **R**: CSV + a `.R` script that sets `human_label`/`ai_label` as ordered factors matching the taxonomy in effect and runs `irr::kappa2()`.
- **SPSS**: CSV + a `.sps` syntax file (`GET DATA` + `VALUE LABELS`), plain-text and stable across SPSS versions, deliberately not a binary `.sav`, so this package doesn't need a compiled dependency for it.
- **JASP**: CSV + a short instructions file, since JASP opens CSV directly, points at JASP's built-in "Cohen's & Fleiss' Kappa" analysis.

Add `--taxonomy-file your_taxonomy.json` to get real category names (not the CFI ones) in the R factor labels / SPSS value labels / JASP instructions for a custom taxonomy, see [above](#the-four-error-types) and `sample_data/item_bank_distractor_taxonomy.json`.

Parquet and a from-scratch SPSS `.sav` writer aren't implemented, both would need a binary/compiled dependency (pyarrow, pyreadstat) this otherwise-pure-stdlib package doesn't have any other reason to carry. If you need Parquet: `pandas.DataFrame(rows).to_parquet(...)` covers it in one line once pandas is installed.

**Evidence panel.** For every coded item: the original answer, the assigned label, the reasoning behind it, free-text notes, and a full revision history. Deliberately *not* wired into the live interactive session, prompting a coder to type a reason for every one of 15-90 distractors mid-session would change the pace and cognitive load of actual data collection, which isn't a change to make silently. Instead this works post-hoc, on top of an already-saved session file, through a separate append-only log that never opens the session file for writing:

```bash
python -m confusion_mapper evidence panel  confusion_mapper_sessions.json
python -m confusion_mapper evidence note   confusion_mapper_sessions.json Q1_D2 "borderline case, discuss" --author Manik
python -m confusion_mapper evidence revise confusion_mapper_sessions.json Q1_D2 CF --reason "AI reasoning was more convincing on review" --author Manik
```

`revise` requires `--reason`, a label change without a stated reason defeats the point of keeping the log, so it's enforced, not just encouraged. Revising never touches the original session file: the item's `assigned_label` (as recorded live) stays exactly what it was, and `current_label` in the panel report reflects the latest revision, computed on the fly. Every session file this points at is opened read-only.

**Codebook generator.** Renders a taxonomy's definitions and examples as a Markdown research appendix, stamped with the same `taxonomy_fingerprint` used in session provenance (for the built-in CFI taxonomy) so a reader can tell exactly which version of the categories a given appendix documents:

```bash
python -m confusion_mapper codebook --out codebook.md
python -m confusion_mapper codebook --taxonomy-file sample_data/item_bank_distractor_taxonomy.json --out item_bank_codebook.md
```

Every category's decision-rule field is left as an explicit, literal placeholder (`*(fill in from your coding manual / Stage 1 RR methods, not auto-generated)*`), not synthesized text. Definitions and examples are real, already-written content; a decision rule is part of a research instrument's methodology, and inventing one from the definition text and presenting it as finished would be fabricating that methodology, not generating a document from it.

## AI-assisted mode

Everything above (the plain `confusion-mapper` session, `kappa`, `alpha`, `diagnostics`) exists to answer one question: does a human and an AI, rating *independently*, agree? The independence is what makes the resulting kappa mean anything at all. `assist` answers a different question, can an AI make bulk coding faster? It shows you the AI's opinion *before* you decide, which is the exact opposite of independent, and that is deliberate.

Mixing the two up is the failure mode I designed this feature around. A label produced in assist mode is not independent evidence of anything. So `assist` never computes or reports a kappa, AC1, or alpha, and every session file it writes carries an explicit `reliability_warning` string, so the distinction survives even when the file is read out of context, without this README nearby.

Use `assist` after you've already established kappa >= 0.70 with the blind session above and trust your rubric / AI prompt, to code a larger dataset faster than one-at-a-time blind rating allows:

```bash
export OPENAI_API_KEY="your-key-here"   # optional, without it every item is a plain manual entry
confusion-mapper assist my_dataset.csv --index confusion_mapper_embeddings.json
```

`my_dataset.csv` needs a `distractor_text` column at minimum. `item_id`, `question_text`, `correct_answer`, and `topic` are optional but they sharpen the suggestion. For each item you see the AI's category, a confidence score, one sentence of reasoning, and, if you pass `--index`, the nearest already-coded examples from a persistent local library. Press Enter to accept, or type `1` through `4` to override. Overrides require a reason, there is no skipping that.

The saved session reports `acceptance_rate`, i.e. how often you kept the AI's suggestion. That is a real efficiency metric, just not a reliability one. Sessions land in `confusion_mapper_assist_sessions.json`, never in the blind-mode file, so the two kinds of data cannot get merged by accident later.

**The persistent semantic-search library** behind `--index` is built and updated only when you explicitly ask for it. It is never touched automatically during a live session, same principle that kept `run_session()` free of any new network calls when I added provenance. Build one from any CSV, and grow it later:

```bash
confusion-mapper embed-index sample_data/example_labels.csv \
  --index confusion_mapper_embeddings.json \
  --id-column item_id --text-column distractor_text --label-column human_label

confusion-mapper embed-search "students confusing voltage with current" \
  --index confusion_mapper_embeddings.json --k 5
```

Two embedding backends, chosen once when an index is first created and locked in for that index's lifetime (so a later run without an API key can't silently produce a dimension mismatch buried in the file):

- **`openai`** (`--backend openai`): OpenAI's `text-embedding-3-small`, real semantic understanding, catches synonyms and paraphrase, not just shared words. Needs `OPENAI_API_KEY` and a network call per item.
- **`local`** (the default): a from-scratch, pure-stdlib hashed bag-of-words vector. Zero cost, zero network, zero new dependencies, and honestly weaker: it's a well-established technique ([feature hashing](https://en.wikipedia.org/wiki/Feature_hashing), Weinberger et al. 2009) that catches shared vocabulary and phrasing, not true synonyms. Documented as a fallback, not presented as equivalent to real embeddings.

## Misconception discovery

Clusters an embeddings index (single-linkage, by cosine-similarity threshold) and flags clusters where semantically similar items got inconsistent existing labels, a signal the taxonomy might be missing a category, not a conclusion:

```bash
confusion-mapper discover confusion_mapper_embeddings.json --threshold 0.5 --min-cluster-size 3 --max-purity 0.6
```

This has a permanent design boundary, not a "coming later" one: **it never writes to any taxonomy file.** A study's taxonomy is part of its preregistered methods. A clustering heuristic silently redefining it would be a bigger problem than any convenience it could offer. What you get instead is a Markdown report: cluster contents, existing label breakdown, and a purity score, for a human to read and decide on. If you agree a cluster is real, the next step is manual: add a code/name/definition/example to a taxonomy JSON (`sample_data/custom_taxonomy.json` shows the shape) and load it with `load_taxonomy_from_json()` for your *next* coding round. Never retroactively, over data already coded under the taxonomy that produced it.

## Pattern mining

This one takes a different CSV shape than the rest of the package. Longitudinal / multi-item coded data (`respondent_id, item_id, label, timepoint, cohort`), not the human/AI paired-label shape. It answers a different question: not "do two raters agree" but "what do the labels I already trust look like across items, time, and groups."

```bash
confusion-mapper patterns cooccurrence  longitudinal.csv
confusion-mapper patterns transitions   longitudinal.csv --timepoint-order pretest,week2,posttest
confusion-mapper patterns pathways      longitudinal.csv --timepoint-order pretest,week2,posttest --sequence-length 2
confusion-mapper patterns trend         longitudinal.csv --timepoint-order pretest,week2,posttest
confusion-mapper patterns cohorts       longitudinal.csv
confusion-mapper patterns item-pair     longitudinal.csv --item1 Q1 --item2 Q2
```

- **`cooccurrence`**, which misconceptions tend to show up together in the same respondent's profile, via lift (the standard association-rule-mining metric: >1 means the pair co-occurs more than chance).
- **`transitions`**, P(label at t+1 | label at t) across consecutive timepoints, plus each category's most likely next state.
- **`pathways`**, the most frequent label sequences ("A confused with B, then B confused with C") via n-gram frequency mining.
- **`trend`** / **`cohorts`**, does the category distribution change over time / differ between groups, via a chi-square test of independence implemented from scratch (Pearson's statistic, Cramer's V effect size, and a p-value via the Wilson-Hilferty approximation, checked against the standard chi-square critical-value table, accurate to within about 0.003 at 1 degree of freedom and well under 0.001 by 3+; see `patterns.py`'s docstring for the full accuracy note).
- **`item-pair`**, a real hypothesis test (unlike `cooccurrence`, which pools across the whole item bank) for one specific, well-defined pair of items.

## Publication assistant

Every number below comes from this package's own tested statistics functions. Nothing here re-derives anything or makes a judgment the underlying function did not already make:

```bash
confusion-mapper publication sample_data/example_labels.csv --bootstrap 10000 --out results.md
```

Produces an APA-style methods paragraph, a reliability-statistics table, a category-frequency table, and two SVG figures (a confusion-matrix heatmap and a frequency bar chart). Both figures are generated by hand as SVG strings, no plotting dependency. The qualitative phrasing in the methods paragraph ("agreement was almost perfect") is lifted from the interpretation string `compute_cohens_kappa` and `gwet_ac1` already produce, not decided fresh here.

Every generated document is stamped `DRAFT, REQUIRES HUMAN REVIEW`. This is a first draft to edit, in the same spirit as the codebook generator's decision-rule placeholders. It is not paste-into-a-manuscript-unread output.

## Why a 4x4 confusion matrix, not just kappa

The kappa number tells you *how much* you and the AI agree. It does not tell you *where* you disagreed. In CFI, the hardest boundary in practice is CF vs INT: a confident wrong belief looks a lot like a correct answer applied to the wrong topic. When I look at the confusion matrix on real data, the [CF, INT] cell is almost always where the disagreement piles up. Seeing the full 4x4 is what lets me go back and rewrite the AI prompt or my rubric until that cell stops glowing.

## A note on ethics

The AI rater is a starting point, not a substitute for a second human, unless you can show it is. For published research you still need trained humans coding a calibration set. Since 2.8.0 the alt-test gives you a principled way to decide whether, after that, the AI can stand in for one of them. Without that evidence, treat the AI labels as a way to find boundaries that need rubric work, not as a shortcut around a human coder.

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
├── itembank.py       CFI-labelled MCQ item generator (templates + AI backends)
├── alttest.py        can the AI replace a human coder? (alt-test, judge comparison, power planning)
├── pisa.py           PISA-style maths units in Indian contexts, a CFI-diagnosed teacher's key,
│                     and class scoring with a 'what to reteach first' report
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
benchmarks/       the embedding-backend study and the alt-test cross-check (see Benchmarks, above)
sample_data/      example CSVs and taxonomy JSONs used throughout this README
examples/         a minimal headless script, the script that rebuilds example_alttest.csv,
                  and an example PISA-style booklet with its teacher's key
worksheets/       the no-install teacher web page (index.html) and the script that builds its unit pool
docs/             statistical methods, research context, and the guide for teachers
dashboard/        index.html, runs kappa/AC1/confusion-matrix in-browser via Pyodide
quickstart_demo.gif   real, captured `confusion-mapper quickstart` output, not staged
```

## Contributing

Bug reports, feature requests, and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md) and [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

## Acknowledgements

Initial development was completed as part of Stanford Code in Place 2026. The tool is used in the Confusion Fingerprint Index research programme.

## License

MIT License © 2026 Manik Maurya. See [LICENSE](LICENSE) for details.
