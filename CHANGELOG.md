# Changelog

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versions follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- CI: the Python 3.9 job had been failing since 13 November 2026, at the step that installs Python, before any code ran. Python 3.9 reached end of life in October 2025 and the hosted runner no longer installs it. It is now tested in the official `python:3.9-slim` Docker image, so the promise of Python 3.9 support is still checked on every push. No code changed.

## [2.13.0] - 2026-11-14

Hindi. Most children in the government schools of Kanpur Dehat learn maths in Hindi, so until now the worksheets could not really reach them.

### Added

- Every PISA-style unit in Hindi as well as English. `generate_unit(..., lang="hi")`, `generate_units(..., lang="hi")` and `confusion-mapper pisa --lang hi`. The Hindi unit from a seed is the English unit from that seed with only the words changed: same numbers, same option order, same answer letters, same true/false answers, same CFI labels. One answer sheet works for both languages. Amounts are written ₹240 and times सुबह 7:30 बजे; answer letters A to D and the sheet codes are the same in both.
- The booklet, the teacher's key, the class report and the before-and-after comparison follow the language of the units, with Hindi names for the content categories, processes, contexts, formats, the four CFI types and the reteaching hints. Hindi units carry `"lang": "hi"`; English units are unchanged and carry no tag.
- The worksheets page has an English | हिन्दी switch. Every button, heading, hint and error message is translated, the page remembers the choice, and answers typed in one language are still there in the other. A follow-up set keeps the language. The page now carries 200 units in each language, which makes it about 1.5 MB.
- A review sheet for the translation, `docs/hindi-review.md`, with every English text beside its Hindi and an empty column for a better version. `confusion-mapper pisa --translation-review PATH` rebuilds it, and a test fails if the file in the repo falls behind.
- Example Hindi booklet and key in `examples/`.
- `index.html` at the top of the repo: a landing page for GitHub Pages with three doors, for teachers, for researchers checking agreement, and for people who write code.
- A second CI job, "Every test, nothing skipped", that installs scipy, Node and jsdom, runs the whole suite, fails if any test is skipped, and walks the teacher page in English and Hindi.

### Changed

- `CITATION.cff` was still at version 1.0.0 and listed a JOSS article as the preferred citation, which has not been published. It is now at 2.13.0, cites the Zenodo concept DOI (10.5281/zenodo.20807431, which always opens the newest version) and has no preferred-citation block, so GitHub's "Cite this repository" cites the software itself. One reference had the type `misc`, which is not a valid CFF type and failed validation; it is now `generic`. The README's citation and DOI badge, and the archive link in `pyproject.toml`, use the concept DOI too.
- The JOSS backup manuscript, `paper-joss.md`, gave the affiliation as IIT Kanpur. It now says Independent Researcher, Kanpur, India, like `paper.md`, and its acknowledgement uses the same wording as `paper.md`.
- The teacher guide said "Five steps" and listed six. It now says six, and has a section on using the page in Hindi.

### How English was kept safe

- Making the templates bilingual meant rewriting all eight of them. Before touching anything I saved the English output of every template for seeds 0 to 299, plus the example booklet, key and web pool, 2,403 outputs in all. The rewrite had to reproduce every one of them byte for byte, and it did. The English class reports and comparisons were checked the same way. A fingerprint of the English output is now a test (`test_english_output_is_exactly_what_it_was_before_hindi`).

### Tests

- `tests/test_pisa_hindi.py` (34 tests): the English fingerprint; on every template across 40 seeds, the Hindi unit has the same numbers in every sentence, the same keys, true/false answers and labels as the English one; no English is left in the Hindi text; money and clock formats; the same answers score the same in both languages; Hindi booklet, key, report and comparison; the command line end to end; the examples and the review sheet are up to date.
- Six more tests in `tests/test_worksheets.py`: the landing page's links all resolve and it loads nothing from the internet, the Hindi pool is the English pool translated, the page swaps a set for its Hindi twin, the page's Hindi scoring and comparison match Python on random classes, and the English and Hindi halves of the page's wording have exactly the same keys. A one-letter typo planted in a Hindi word in the page's scoring, and the same in Python, were each caught. `worksheets/check_page.js` now also runs the whole journey in Hindi and switches language halfway through.

### Notes

- 739 tests total (699 previous plus 40 new), and with scipy, Node and jsdom installed none are skipped. Still no runtime dependency beyond `openai`.
- The Hindi is a first draft and has not yet been checked by a Hindi-medium maths teacher. The booklet, key, report and page say so.

## [2.12.0] - 2026-11-13

Two things the worksheets were missing: a way to tell whether the reteaching worked, and a way to tell whether each question is any good.

### Added

- Reteach, then check. The class report on the worksheets page now ends with "Make a follow-up set on these mistakes". It builds a short set from the kinds of unit behind the most common mistakes (up to four), with new numbers that are guaranteed different from every unit the class has already seen in that chain of rounds. The follow-up set's address carries the first round, and once the class's follow-up answers are entered, the report compares the two rounds by itself: for each mistake, how many children made it the first time and how many now. Answers are now saved on the device when the report is made, not only while typing, so the comparison finds them. If the first round was on another device, its downloaded CSV can be loaded instead.
- `compare_rounds()` and `format_comparison()` in `pisa.py`, and `confusion-mapper pisa-compare before_units.json before.csv after_units.json after.csv --report compare.md`. Mistakes are matched by unit template, question position and CFI type, since the numbers change on purpose between rounds.
- `itemanalysis.py` and `confusion-mapper pisa-items units.json class1.csv [class2.csv ...] --report items.md`: classical item analysis of real classroom answers, pooled over every class that sat the same set (children from different files are kept apart even when their IDs match). For each question: difficulty, the corrected item-total correlation, the upper-lower index D from the top and bottom 27% (Kelley, 1939) read with Ebel's bands, and who chose each option or code overall and in each group. Flags in plain language for questions where stronger students did worse, poor discrimination, a distractor chosen by fewer than 5% (non-functioning, Haladyna and Downing, 1993), a wrong option the strongest students prefer, and a lot of blanks. Cronbach's alpha (1951) for the set. A warning below about 30 students.
- `tests/test_itemanalysis.py` (31 tests): alpha against a hand-worked example and against KR-20 on 200 random right/wrong matrices, the correlation against the raw-sums formula, the 27% groups and tie-breaking, Ebel's band edges, a class worked by hand, item totals that must match the scoring module child by child, and the flags, including that a planted miskeyed question is the only one flagged.
- `tests/test_pisa_rounds.py` (9 tests) for the round comparison, and three more page tests in `tests/test_worksheets.py`: the page's comparison matches Python on 30 random pairs of rounds, follow-up sets never repeat a unit and use only the chosen kinds, and the page picks the same follow-up kinds as Python would. Four planted bugs in the page's new code (wrong denominator, wrong sort, exclusions ignored, one kind too few) were each caught. `worksheets/check_page.js` now walks the whole loop: first round, report, follow-up set, second round, comparison.
- `docs/pisa-teacher-guide.md` gains step 6, "Reteach, then check", and a section for coordinators on pooling classes for item analysis. `docs/methods.md` documents the item analysis and the round comparison with references.

### Learned along the way

- On a short set, a miskeyed question lowers the totals of exactly the children who answered it "wrong", so the top 27% by total can turn out to be the next tier down and D can come out near zero instead of negative. My first test assumed D would go negative and failed. The analysis was right and the test was wrong: the corrected item-total correlation, which leaves the question out of the total, still turns negative and still raises the flag. That case now has its own test.

### Notes

- 699 tests total (656 previous plus 43 new). Still no runtime dependency beyond `openai`.

## [2.11.0] - 2026-11-13

The PISA-style units were only usable by someone who could install Python. This release is about getting them to teachers.

### Added

- `worksheets/index.html`, a single self-contained page for teachers. Pick how many units and which topics or situations, and it makes the student booklet and the teacher's key, both printable. A set number makes every set reproducible and shareable: the same number gives the same worksheets and key, and the page address carries it. After the test, the teacher enters each child's answers in a grid and gets a class report that starts with "what to reteach first". It needs no installation and no account, works offline once saved, can be forwarded as a file on WhatsApp, and keeps everything typed into it on the device. Answers can be downloaded and loaded again as CSV.
- The page does not compute any answer itself. It carries a pool of 200 units (25 of each template) built by `build_web_pool()` in `pisa.py`, written into the page by `worksheets/build_pool.py`, so the Python templates and the tests that recompute every answer still cover everything a teacher sees.
- Class scoring in Python: `response_sheet_csv()`, `load_responses_csv()`, `score_responses()` and `format_class_report()`, with `pisa --response-sheet` and a new `confusion-mapper pisa-score units.json answers.csv --report report.md`. Every wrong answer is traced to its CFI label in the key. The report lists the most common misconceptions with what usually helps for each kind of mistake, then question-by-question and child-by-child tables. The JSON output has each child's Confusion Fingerprint Index (CFI-CF, CFI-INT, CFI-RF), using the definitions already in the package. Rows with no answers at all are skipped as absent.
- `docs/pisa-teacher-guide.md`, a plain-language guide: five steps from making a set to reading the class report, the four kinds of mistake with what usually helps, and honest limits.
- `tests/test_worksheets.py`, 23 tests. The central one runs the page's own JavaScript scoring in Node and compares every number with the Python scoring on 60 random classes, and another checks both versions reject exactly the same answers. I confirmed these can fail by breaking the page's code four ways (partial credit worth 2 points, the wrong denominator for CFI-INT, a reversed tie-break, lowercase answers refused). All four were caught. Other tests check the page's pool matches the generator, the page loads nothing from the internet, sets are reproducible and respect the filters, and a CSV downloaded from the page reads back correctly in Python. These tests are skipped where Node is not installed.
- `.nojekyll` at the repository root, so GitHub Pages serves the page as-is.

### Notes

- 656 tests total (633 previous plus 23 new). Still no runtime dependency beyond `openai`.
- `worksheets/check_page.js` drives the whole page in jsdom (a browser document running in Node): opening a shared set address, printing views, entering answers, scoring, bad input, and a filter that matches nothing, failing on any script error. `tests/test_worksheets.py` runs it whenever jsdom is installed (`npm install jsdom`).

## [2.10.0] - 2026-11-12

### Added

- `pisa.py` and `confusion-mapper pisa`: PISA-style maths units set in Indian contexts. Each unit is a short real-world situation, sometimes with a table, followed by three questions. Eight original templates (mobile data plans, a monsoon rain gauge, a school garden, a bus to the district headquarters, the price of dal, a class travel survey, a rooftop water tank, two kinds of bacterial growth) follow the published PISA 2022 mathematics framework: four content categories, four contexts, the formulate / employ / interpret processes plus mathematical reasoning, and three formats (multiple choice, true/false rows, written answers with a scoring guide). A set of eight units has exactly 6 questions in each content category and each context.
- Every wrong option, wrong true/false judgement and common wrong written answer carries a CFI label and a note on the thinking behind it. `--key` writes a teacher's key built around those diagnoses, `--booklet` writes the student booklet with no answers or labels, `--out` saves the units as JSON, and `--item-bank` exports the multiple-choice questions in the plain item format so they can go straight into a CFI coding session.
- `examples/pisa_booklet_example.md` and `examples/pisa_teacher_key_example.md`, a full eight-unit set anyone can read on GitHub without installing anything.
- `tests/test_pisa.py`, 69 tests. For every template and 300 seeds they recompute every answer from the raw numbers with separate code, and check clean options, full CFI diagnosis, an even spread of answer letters, a booklet that gives nothing away, and that the committed examples match the generator. I checked the tests can fail by planting four bugs in the generator. Three were caught at once. The fourth, a `>=` where `>` belonged in the growth unit, made a tie case (both samples at 160 thousand cells at hour 5) silently disappear instead of producing a wrong answer, so a dedicated test now pins that case.
- `tests/test_refine.py`, 10 tests for the prompt-refinement engine, which had none.

### Fixed

- `confusion-mapper refine` and `suggest_prompt_refinements()` without an explicit taxonomy crashed with `NameError: name 'TAXONOMY' is not defined`. This was broken from the 2.6.0 package split, when the taxonomy moved to its own module and `stats.py` never imported it. No test caught it because there were no tests for the engine, even though the README said `test_kappa.py` covered it. Found by running pyflakes over the package. The README claim is corrected and the new tests include a regression test that fails if the import is removed again.
- The rest of the pyflakes report, now clean across the package, tests, examples and benchmarks: unused imports in `cli.py`, `stats.py`, `__init__.py` and three test files, two f-strings with nothing to format, a dead helper in `test_kappa.py` that returned None and was never called, and a duplicated numpy import in the alt-test cross-check.

### Notes

- 633 tests total (554 previous plus 79 new). Still no runtime dependency beyond `openai`.

## [2.9.0] - 2026-11-12

Two follow-ups a careful reviewer will ask about any alt-test verdict: did you choose epsilon before you saw the data, and would the verdict survive a slightly different sample?

### Added

- Preregistration lock. `confusion-mapper alt-test-prereg` writes a plan file holding every decision that sets the verdict (epsilon and where it came from, FDR level, scoring function, minimums, pass threshold, AI and human column names, planned item count) together with a SHA-256 hash of those decisions, for your OSF preregistration. `alt-test --prereg PLAN` then takes its settings and columns from the plan. If the command line contradicts the plan, the run stops and lists every difference. `--allow-deviation` lets it run anyway, and then every deviation is printed at the top of the report and counted in the draft methods paragraph. A plan whose locked settings were edited after it was made no longer matches its hash and is refused. The hash deliberately leaves out the creation date and the notes, since a date inside a file proves nothing, the registry's timestamp is what counts.
- Bootstrap robustness check, `alt-test --bootstrap N` and `bootstrap_alt_test()`. Reruns the whole test, FDR correction included, on N resamples of the items and reports how often the verdict held, a percentile interval for the advantage probability, and how often each coder was beaten. This is ConfusionMapper's addition, not part of the authors' procedure, and the report says so. On the example data the pass for `ai_prompt_v1` holds in 75.9% of 1,000 resamples, and coder_B is beaten in only 45% of them.
- `--pass-threshold` on `alt-test`, for studies that want a stricter rule than the authors' 0.5.
- `sample_data/example_alttest_prereg.json`, an example plan for the example data.
- `tests/test_alttest_bootstrap.py` (15 tests) and `tests/test_alttest_prereg.py` (33 tests). I checked that they can fail by breaking the code on purpose three times: making repeated bootstrap items share one key, leaving epsilon out of the hash, and letting deviations through without `--allow-deviation`. Each break was caught.

### Changed

- `alt-test` no longer requires `--ai-column` or an epsilon flag at the parser level, because both can come from `--prereg`. Without a plan, leaving either out still stops with a clear message.
- `--scoring`, `--q` and `--min-items` on `alt-test` now default to "not given" internally so that a plan's values are not silently overridden by a default. The effective defaults without a plan are unchanged: accuracy, 0.05 and 30.

### Notes

- 554 tests total (506 previous plus 48 new). Still no runtime dependency beyond `openai`.

## [2.8.0] - 2026-11-12

### Added

- `alttest.py` and two new subcommands, `confusion-mapper alt-test` and `confusion-mapper alt-test-plan`. They answer the question kappa cannot: is the AI good enough to replace one of my human coders? This is a pure standard-library implementation of the Alternative Annotator Test by Calderon, Reichart and Dror (ACL 2025). The method is theirs. Their reference code is a notebook that needs numpy and scipy, so this version brings its own Student's t distribution (regularized incomplete beta, continued fraction) and its own Benjamini-Yekutieli correction, and plugs into the same wide-CSV format and Markdown reports as the rest of the package.
- `alt-test` takes a wide CSV (one column per human coder, one or more AI columns, blank cells allowed) and reports, per coder, how often the AI matched the remaining coders at least as well as that coder did, the one-sided t-test against epsilon, and whether it survives the FDR correction. It then gives the winning rate, the advantage probability and a plain-language verdict. Pass several `--ai-column` flags to compare models or prompts head to head, ranked by advantage probability as the authors recommend.
- The `--report` option writes a Markdown report with the verdict, a coder-by-coder table, the mean pairwise kappa among the human coders, the authors' six-item reporting checklist with what is already filled in, a draft methods paragraph and the citation.
- `alt-test-plan` reimplements the authors' simulation model from their appendix C in plain Python and estimates how many items you need to label before the test has a fair chance of passing. It also reports the human kappa your noise settings imply, so you can check them against your own pilot data.
- `sample_data/example_alttest.csv`, a synthetic panel of 81 CFI-coded items, three human coders and two AI prompts, plus `examples/make_alttest_example.py`, which rebuilds it byte for byte.
- `benchmarks/alttest_crosscheck.py` and `benchmarks/ALTTEST_VALIDATION.md`. The t CDF matches scipy to 1.1e-13 over 6,734 points, Benjamini-Yekutieli matches the authors' numpy version on 20,000 random cases, and the full test gives identical winning rates and advantage probabilities to the authors' own logic on 369 random synthetic panels, with p-values within 5.4e-14.
- `tests/test_alttest.py`: 100 tests. Exact closed forms of the t distribution for 1 and 2 degrees of freedom, printed t-table values, hand-worked Benjamini-Yekutieli cases including the step-up behaviour, a fully hand-worked 3-coder example down to the t statistic, the paper's optimal-judge theorem (majority vote under accuracy and the mean rating under RMSE both reach an advantage probability of exactly 1), missing data, the simulator, the reports and the CLI. One test cross-checks against scipy and only runs when scipy is installed.

### Design decisions

- Epsilon has no default. `alt-test` requires either `--epsilon` or `--annotators expert|skilled|crowd` (the authors' rule of thumb: 0.2, 0.15, 0.1). Choosing epsilon after seeing the result, and nudging it until the AI passes, is the exact flexibility the test is meant to remove, so the tool will not choose for you.
- When every per-item difference is identical the t-test's standard error is zero. The p-value is then taken as its limit, 0 if the mean is below epsilon and 1 otherwise. This matches scipy except when the mean sits exactly on epsilon, where scipy returns nan; neither counts as a rejection, so verdicts are unaffected.

### Fixed

- Found while trying the new subcommand on my own example file: asking for one AI column silently turned the second AI column into a fourth "human coder". Nothing crashed, the numbers were just wrong. `load_alttest_csv` now refuses when a column that would be counted as human looks like model output (`ai_...`, `llm...`, `gpt...`, `model_...`, `judge_...`) and asks for the human columns explicitly. Regression test included.

### Notes

- 506 tests total (406 previous plus 100 new). Still no runtime dependency beyond `openai`.

## [2.7.0] - 2026-08-14

### Added

- `itembank.py` and `confusion-mapper generate-bank`: a CFI-labelled MCQ item generator with two backends. The `templates` backend is deterministic, seedable, and offline, and produces items across five templates (percent discount, percent tax, metric unit conversion, speed / distance / time, and a fixed science-literacy item). Every distractor carries a CFI label (RF / PK / CF / INT) that traces back to a rule I can defend from the template that generated it. The `ai` backend calls OpenAI to draft items in the same schema for topics outside the template set; every AI-generated item is put through the same validator before it is returned, so a malformed or duplicate-option item is rejected instead of silently landing in the bank.
- Every generated item is validated at generation time. The validator catches missing keys, unknown `error_type` values, empty options or notes (a real bug: an early template took the last two digits of the correct answer as a distractor, which for values under 100 produced an empty string), and, most importantly, a distractor whose option equals the correct answer (another real bug: the "random plausible number" pool for RF distractors could coincidentally sample the correct answer, which made two options identical). Both bugs have regression tests in `tests/test_itembank.py`.
- `tests/test_itembank.py`: 49 tests, including a 200-seed sweep per template that would catch any distractor-vs-correct-answer collision, a bank-level determinism test (same seed always produces the same bank), full round-trip through `save_bank` / `load_bank`, and integration checks that generated items feed straight into `run_session()` and `compute_cohens_kappa()` without adaptation.
- The generator is a natural feeder for the reliability workflow: `confusion-mapper generate-bank 30 --seed 1 --out my_bank.json` produces a fully labelled 30-item calibration set that the existing `run_session()`, `kappa`, and `validate` subcommands accept directly.

### Fixed

- `[warning]` and `[error]` prefixes now replace the Unicode warning-sign and cross-mark characters used previously in CLI stderr output. Same information, plain text, easier to grep, no font-rendering surprises on Windows terminals.

### Notes

- 406 tests total (357 previous plus 49 new), running in under 5 seconds. No new runtime dependencies.

## [2.6.0] - 2026-07-30

### Added

- `gwet_ac1()`: Gwet's AC1, the prevalence-robust companion to Cohen's kappa (Gwet, 2008). Unlike kappa, AC1 doesn't get paradoxically dragged down when one category dominates a skewed taxonomy, exactly the shape of most real CFI coding data. Available from Python (`from confusion_mapper import gwet_ac1`) and folded into the `diagnostics` CLI subcommand's output alongside PABAK/bias/prevalence. 7 new tests, including a hand-derived (not externally-cited) worked example verified independently in the test suite.
- `validate_dataset()` (new `validation.py` module) + `confusion-mapper validate data.csv` CLI subcommand: catches missing labels, labels outside the taxonomy (typos), duplicate `item_id`s, and empty `distractor_text` before they silently distort a kappa/alpha/AC1 computation. `kappa`, `alpha`, `diagnostics`, and `refine` now run this automatically and print a one-line stderr warning if issues are found (computation still proceeds on the data as given, default behavior and stdout output are unchanged); add `--strict` to any of them to abort with the full report instead. 15 new tests in `tests/test_validation.py`.
- 3+ human coder workflow (new `multirater.py` module) + `confusion-mapper multirater data.csv` CLI subcommand: pairwise Cohen's kappa + AC1 for every rater pair, panel-wide Fleiss' kappa, and a ranked conflict list (unanimous items omitted, worst disagreement first) with majority-vote suggestions, `majority_label` is `null` with `tied_labels` populated when there's no clear majority, and nothing in the workflow silently overwrites a rater's original label. Introduces no new statistical formula; it's an adapter/reporting layer over the already-tested `compute_cohens_kappa`, `gwet_ac1`, and `fleiss_kappa`. New `sample_data/example_multirater.csv` (3 raters, 15 items, a deliberate mix of unanimous / 2-1 / 3-way-tied items). 20 new tests in `tests/test_multirater.py`.
- Export packages (new `export.py` module) + `confusion-mapper export data.csv --out DIR` CLI subcommand: writes a clean CSV plus a ready-to-open companion for **R** (`.R` script, sets ordered factors from the CFI taxonomy, runs `irr::kappa2()`), **SPSS** (`.sps` syntax, plain text, not a binary `.sav`, so no compiled dependency is needed), and **JASP** (CSV + instructions, since JASP reads CSV directly and has a built-in "Cohen's & Fleiss' Kappa" analysis). Parquet and a from-scratch `.sav` writer are deliberately not implemented, to avoid pulling in a binary dependency (pyarrow / pyreadstat) for a niche feature, documented in the module docstring and README with the one-line pandas alternative. 19 new tests in `tests/test_export.py`.
- Session provenance: `run_session()` now writes four additional keys into every saved session, `session_id` (UUID4), `software_version` (read from installed package metadata, not a hand-maintained string), `taxonomy_fingerprint` (a 12-char hash of the exact CFI category definitions in effect, via the new `taxonomy_fingerprint()` in `taxonomy.py`), and `python_version`. Strictly additive: every previously-existing session key keeps its exact name and is computed by the same, untouched `compute_cohens_kappa` / `build_confusion_matrix` / `get_per_type_stats` calls, verified end-to-end in `tests/test_provenance.py` by running a full simulated session and asserting the recorded kappa/matrix/type_stats are `==` to calling those functions directly on the same inputs.
- Evidence panel (new `evidence.py` module) + `confusion-mapper evidence {panel,note,revise} SESSION.json` CLI subcommand: for every coded item, the original answer, assigned label, AI reasoning (already captured, now surfaced), free-text notes, and a full append-only revision history. Deliberately not wired into `run_session()`, prompting a coder for a reason on every distractor mid-session would change the pace/cognitive load of live data collection, unlike the silent provenance-metadata addition above, so this works post-hoc on an already-saved session file through a separate log that never opens the session file for writing. `revise` requires `--reason`, enforced with a `ValueError`/CLI exit 1 if empty. 25 new tests in `tests/test_evidence.py`, including an explicit guarantee test that revising a label never mutates the session object (`test_revising_never_mutates_the_session_object`) and that the original `human_label` field is untouched even after a revision.
- Codebook generator (new `codebook.py` module) + `confusion-mapper codebook --out FILE.md` CLI subcommand: renders the CFI taxonomy's existing definitions and examples as a Markdown research appendix, stamped with the same `taxonomy_fingerprint` used in session provenance. Every category's decision-rule field is an explicit, literal placeholder, not synthesized text, inventing a decision rule from the definition and presenting it as finished would be fabricating part of a research instrument's methodology. 12 new tests in `tests/test_codebook.py`, including a check that the placeholder text is identical (not per-category-generated) across every entry.
- Embeddings and a persistent local semantic-search index (new `embeddings.py` module) + `confusion-mapper embed-index` / `embed-search` CLI subcommands. Two backends, locked per index at creation so a later run without an API key can't silently produce a dimension mismatch: `openai` (`text-embedding-3-small`, real semantic understanding, needs a key + network) and `local` (a from-scratch, pure-stdlib hashed bag-of-words vector, feature hashing, Weinberger et al. 2009, zero cost, zero network, zero new dependencies, documented as a weaker fallback rather than presented as equivalent). Building or updating the index is always an explicit, separate action (`embed-index`), never triggered automatically by any live session, for the same reason provenance never added a network call to `run_session()`. 43 new tests in `tests/test_embeddings.py`, including full round-trip and incremental-update coverage across save/load cycles.
- AI-assisted mode (new `assist.py` module) + `confusion-mapper assist data.csv`, a Copilot-style workflow where the AI suggests a category (with confidence and reasoning) and, if you point it at a persistent index, the nearest already-coded examples, and a human accepts (Enter) or overrides (1-4, reason required). This is a structurally distinct entry point from both the JSON stats subcommands and the blind reliability-check session, `run()`'s dispatcher routes `assist` on its own branch before either of the other two, so there is no argv path by which assist mode and the blind session could be confused for each other. Because the human sees the AI's opinion before deciding, a label from this mode is not independent evidence of anything: `assist` never computes or reports a kappa/AC1/alpha, reports an `acceptance_rate` instead (a real efficiency metric, not a reliability one), and every session carries an explicit `reliability_warning` string baked into the JSON so the distinction survives even if the file is read without this context later. Sessions are saved to `confusion_mapper_assist_sessions.json` (new `ASSIST_DATA_FILE` constant), never `DATA_FILE`, the file the blind session reads and writes, storage-separate, not just workflow-separate. Uses a new `classify_with_confidence()` rather than extending `ai.classify_with_ai()`, specifically so the prompt sent to OpenAI during a live blind-mode reliability-check session never changes. 20 new tests in `tests/test_assist.py`, including a regression test for a real bug found during development (see Fixed) and an explicit check that a session never contains a kappa/matrix/type_stats key.
- Custom (non-CFI) taxonomies are now first-class throughout the toolkit, not just accepted as bare category codes. `codebook.generate_codebook()` and every `export.export_for_*()` function gained an optional `taxonomy` parameter (a dict in the same shape as the built-in `TAXONOMY` constant, e.g. the second value `stats.load_taxonomy_from_json()` already returned), previously these always fell back to the built-in CFI names/definitions/examples for any code not in that dict, so a custom taxonomy's codebook and R/SPSS/JASP exports showed "no definition on file" placeholders instead of real content. Both CLI subcommands gained `--taxonomy-file` to load one directly. `stats.load_taxonomy_from_json()` itself is pre-existing (moved from the original single-file module) but had zero test coverage before this release. New `sample_data/item_bank_distractor_taxonomy.json`: a 4-category distractor-functioning taxonomy (Non-Functional / Potentially-Lead-to-Misconception / Functional / Ambiguous-Flawed) for large-scale-assessment item banks (PISA-style or otherwise), modeled on published item-analysis literature, explicitly documented as *not* an official OECD/PISA taxonomy, since PISA's own coding is item-specific partial-credit rubrics rather than one reusable scheme, plus `sample_data/item_bank_demo.csv` as a worked, original (non-copyrighted) example dataset. 26 new tests in `tests/test_custom_taxonomy.py`, including full end-to-end coverage (kappa, codebook, export, and the `--taxonomy-file` CLI flag) against those two files.
- Pattern mining (new `patterns.py` module) + `confusion-mapper patterns {cooccurrence,item-pair,transitions,pathways,trend,cohorts}` CLI subcommand, over a new "longitudinal coded response" data shape (respondent_id, item_id, label, timepoint, cohort). Co-occurrence via lift (the standard association-rule-mining metric); transition probabilities between timepoints with a per-category "most likely next state"; frequent transition-pathway (n-gram) mining; temporal-trend and cohort-comparison chi-square tests. The chi-square test itself (`chi_square_test()`) is implemented from scratch, Pearson's statistic plus Cramer's V, with the p-value via the Wilson-Hilferty normal approximation (reusing the same math.erf-based normal CDF already used elsewhere in this package for bootstrap CIs), checked against the standard chi-square critical-value table: absolute error ~0.003 at df=1, dropping below 0.001 by df=3. 33 new tests in `tests/test_patterns.py` (41 collected, with parametrized cases), including every worked example hand-derived in a comment and independently verified against the real function output before being written as an assertion.
- Single-linkage clustering (new `cluster_index()` in `embeddings.py`), the standard, efficient sorted-edges-plus-union-find algorithm for threshold-based agglomerative clustering, not a novel or ad hoc method. Deterministic regardless of index insertion order.
- Human-in-the-loop misconception discovery (new `discovery.py` module) + `confusion-mapper discover INDEX.json` CLI subcommand: clusters an embeddings index and flags clusters where semantically similar items were labeled inconsistently by the existing taxonomy (low "label purity") as candidates worth a human's attention. This module has a permanent, tested design boundary, not a "not yet implemented" one: it never writes to `TAXONOMY` or any taxonomy file, ever, only produces a Markdown proposal report for a human to read and, if they agree, manually turn into a real taxonomy entry for their *next* coding round. 19 new tests in `tests/test_discovery.py`, including static-source-inspection and behavioral checks that the module never calls a file-writing function.
- Publication assistant (new `publication.py` module) + `confusion-mapper publication data.csv` CLI subcommand: an APA-style inter-rater-reliability methods paragraph, a reliability-statistics table, a category-frequency table, and two SVG figures (confusion-matrix heatmap, frequency bar chart), pure string-generated SVG, no plotting dependency, validated as well-formed XML in tests. Every number in every output is read from an already-computed stats dict (`compute_cohens_kappa`, `gwet_ac1`, `krippendorff_alpha`, `build_confusion_matrix`, `get_per_type_stats`'s return values) and never re-derived or invented by this module; the one qualitative judgment embedded in the prose (e.g. "almost perfect") is lifted verbatim from the primary descriptor of an interpretation string those functions already computed. Every output is stamped "DRAFT, REQUIRES HUMAN REVIEW". 36 new tests in `tests/test_publication.py`, including two real bugs caught before shipping (see Fixed).
- `confusion-mapper quickstart`: a non-interactive, self-contained guided walkthrough (kappa -> diagnostics/AC1 -> per-category breakdown -> a codebook snippet -> pointers to the rest of the CLI) built from the built-in question bank's own pre-assigned ground truth, not `sample_data/`, `sample_data/` is only in the sdist via `MANIFEST.in`, not the installed wheel (`pyproject.toml`'s `packages` config only includes `confusion_mapper/`), so quickstart can't depend on it existing after a plain `pip install`. 11 new tests in `tests/test_quickstart.py`.
- New `benchmarks/` directory: an empirical check of whether the local (hashed bag-of-words) embedding backend captures real signal, using Adjusted Rand Index (Hubert & Arabie, 1985, implemented from scratch in `ari.py` with a hand-derived worked example, verified independently three times, in the module's own `__main__` self-check, in `tests/test_ari.py`, and in the findings write-up) between the local backend's clusters and each bundled labeled dataset's real `human_label` column. The honest result, reported in full in `benchmarks/EMBEDDING_VALIDATION_FINDINGS.md`: ARI is at or near zero on both `sample_data/example_labels.csv` and `sample_data/item_bank_demo.csv` at every threshold tested, the local backend does not recover the taxonomy labels from content alone. The write-up traces this to a real structural property of the data (every label spans many different questions/topics, while distractors within one question carry different labels, so topical similarity and cognitive-error-type are close to orthogonal by construction) rather than papering over it, and is explicit that a study finding *high* ARI here would be the more suspicious result. `benchmarks/benchmark_embeddings.py` runs the identical methodology against the `openai` backend for a direct comparison, written and reviewed, but **not yet run**, since doing so needs `OPENAI_API_KEY` and network access neither available in the environment this was built in. 10 new tests in `tests/test_ari.py`.
- Reorganized the single ~2,000-line `confusion_mapper.py` module into a package (`confusion_mapper/{taxonomy,question_bank,stats,validation,ai,storage,gui,console,cli}.py`). Every name previously importable from `confusion_mapper` (e.g. `from confusion_mapper import compute_cohens_kappa`) still is; see the package docstring for the full list. No statistical formula changed, verified by running the full test suite (33/33 passing, unmodified) and diffing the CLI's JSON output byte-for-byte against the pre-refactor module on the bundled sample data (identical, including the seeded bootstrap CI).

### Changed

- `python confusion_mapper.py ...` is no longer valid (there's no longer a single file to point at). Use the installed `confusion-mapper` command or `python -m confusion_mapper` instead, both accept the same subcommands.

### Fixed

- The installed `confusion-mapper` console command never reached the `kappa` / `alpha` / `diagnostics` / `plan` / `refine` subcommands, it called the interactive session directly regardless of `sys.argv`, so those subcommands only worked via `python confusion_mapper.py <subcommand>` or `python -m confusion_mapper <subcommand>`. A new `run()` dispatcher is now the entry point for both the console script and `python -m confusion_mapper`, so all invocation styles behave identically.
- `tests/test_kappa.py` had 35 mojibake-corrupted characters (`Îº` for `κ`, `â€"` for `-`, `âœ"` for ``, etc.) from a prior copy-paste through a misdeclared encoding. Repaired via a cp1252/latin-1 hybrid byte-recovery (cp1252 leaves 5 byte values undefined; those fall back to latin-1's 1:1 mapping) and confirmed to touch only comments/docstrings, all 33 pre-existing tests still pass byte-for-byte, and no other file in the repo had the same corruption.
- `confusion_mapper.__version__` was a hardcoded `"1.0.0"` string, already out of sync with the PyPI version before this release (2.5.1) and every release before that. It now reads from installed package metadata via `importlib.metadata.version("confusion-mapper")`, so it can no longer drift, `confusion_mapper.__version__` now correctly reports `"2.6.0"`. Falls back to a literal for an uninstalled source checkout rather than raising on import.
- Caught during development of assist mode, fixed before it ever shipped: the override-reason logic treated "the AI had no real suggestion" (no API key, or the call failed) the same as "the AI suggested something and the human disagreed", which meant it demanded a reason for overriding a suggestion that never existed, and offered a nonsensical "accept N/A" option via Enter. Fixed so `accepted` is `None` (not `False`) when no real suggestion existed, no reason is required in that case, and `acceptance_rate` is computed only over items where the AI actually suggested something. Locked in by `tests/test_assist.py::TestRunAssistSessionNoApiKey`.
- Caught during development of the publication assistant, fixed before it shipped: the methods-paragraph generator embedded a stats function's full interpretation string (e.g. "Almost Perfect, excellent agreement.") verbatim mid-sentence, producing a run-on ("Agreement was almost perfect, excellent agreement, kappa = .87"). Fixed to extract only the primary descriptor (the part before the first comma) via a new `_primary_descriptor()` helper. Also caught in the same module: the frequency-table generator read a `"percentage"` key that doesn't exist on `get_per_type_stats()`'s return dict (the real key is `"pct"`), so every row's "% Agreement" column silently showed 0% regardless of the real value; and passing `taxonomy={}` (an explicit empty custom taxonomy) was incorrectly treated the same as `taxonomy=None` due to a truthy check (`taxonomy or TAXONOMY`) rather than an identity check, silently falling back to the built-in CFI names instead of showing bare codes as the caller asked. All three locked in by regression tests in `tests/test_publication.py`.
- Caught during development of the discovery workflow, fixed before it shipped: `discovery.format_proposal_report()` hardcoded `metadata.get("label")` to display each item's existing label, so any index built with a different `label_key` (including `"human_label"`, the actual default used by the `embed-index --label-column` CLI flag) always displayed "?" instead of the real label. Fixed by threading `label_key` through to the formatter. Locked in by `tests/test_discovery.py::TestFormatProposalReport::test_report_shows_real_labels_not_question_marks_with_custom_label_key`.
- README claimed 88 tests; the suite has 357 as of this release across 15 files (up from 13; `test_quickstart.py` and `test_ari.py` are new in this batch): 40 in `test_kappa.py` (33 pre-existing + 7 new AC1 tests), 15 in `test_validation.py`, 20 in `test_multirater.py`, 19 in `test_export.py`, 11 in `test_provenance.py`, 25 in `test_evidence.py`, 12 in `test_codebook.py`, 52 in `test_embeddings.py`, 20 in `test_assist.py`, 26 in `test_custom_taxonomy.py`, 41 in `test_patterns.py` (parametrized), 19 in `test_discovery.py`, 36 in `test_publication.py`, 11 in `test_quickstart.py`, 10 in `test_ari.py`.

## [1.0.0] - 2026-06-23

First public release.

### Core functions

- `compute_cohens_kappa(human, ai)` returns nominal Cohen's kappa with a Landis and Koch interpretation string.
- `compute_cohens_kappa(..., weights="linear" | "quadratic")` returns weighted kappa for ordinal taxonomies, using Cicchetti-Allison and Fleiss-Cohen weights respectively.
- `build_confusion_matrix(human, ai)` returns the N by N cross-tabulation as a nested dict.
- `get_per_type_stats(human, ai)` returns per-category total, agreed, and percentage agreement.
- `bootstrap_kappa_ci(human, ai, method="bca", seed=...)` returns a percentile or BCa bootstrap 95% confidence interval. The `seed` argument makes the interval bit-identically reproducible.
- `load_taxonomy_from_json(path)` swaps the default Confusion Fingerprint Index categories for any nominal scheme of two or more labels described in a small JSON file.
- `compute_kappa_diagnostics(human, ai)` returns PABAK alongside the bias and prevalence indices (Byrt et al. 1993). Useful for diagnosing the kappa paradox on skewed marginals.
- `krippendorff_alpha(human, ai, level=...)` computes Krippendorff's alpha at nominal, ordinal, or interval level.
- `suggest_prompt_refinements(human, ai, top_k=3)` ranks the largest off-diagonal cells of the confusion matrix and emits a Markdown report with concrete contrastive prompt instructions for each.
- `fleiss_kappa(rating_matrix)` for 3-or-more rater panels (Fleiss, 1971), with the same Landis and Koch interpretation bands.
- Unix-style CLI: `python -m confusion_mapper {kappa, alpha, diagnostics, refine, plan} ...`. Every subcommand emits JSON or Markdown on stdout for easy piping.
- `docs/methods.md` documenting every formula with its primary citation.
- Cross-validation tests against published reference values for textbook 3 x 3 contingency tables and the Landis and Koch zone boundaries.
- `recommend_sample_size(expected_kappa, ci_half_width, n_categories)` estimates the calibration-set size required to bound the kappa CI within a target half-width (Donner and Eliasziw, 1992).

### Interfaces

- Console session flow (`run_session`) for interactive distractor labelling.
- Optional tkinter results dashboard with a kappa gauge, confusion matrix, and per-type bar chart. Falls back to console output when no display is available.
- Optional OpenAI rater (`classify_with_ai`) using `gpt-4o` at temperature zero.
- Optional AI question generator (`generate_ai_questions`).
- JSON session export.
- Headless tutorial at `examples/demo.py`.
- Worked case study at `case_study/run_case_study.py` with deterministic outputs.

### Quality

- 88-test pytest suite.
- GitHub Actions matrix on Python 3.9 through 3.12.
- JOSS draft paper PDF built on every push.

### Archive

- Software archive: <https://doi.org/10.5281/zenodo.20807432>.
