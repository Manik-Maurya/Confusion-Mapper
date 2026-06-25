---
title: 'ConfusionMapper: A Human-AI Hybrid Inter-Rater Reliability Tool for Cognitive Error Taxonomy Classification'
tags:
  - Python
  - cognitive science
  - inter-rater reliability
  - Cohen's kappa
  - educational assessment
  - multiple-choice questions
  - distractor classification
authors:
  - name: Manik Maurya
    orcid: 0009-0005-3554-693X
    affiliation: 1
affiliations:
  - name: Department of Cognitive Science, Indian Institute of Technology Kanpur, India
    index: 1
date: 22 June 2026
bibliography: paper.bib
---

# Summary

ConfusionMapper is a Python tool that operationalizes a human-AI hybrid inter-rater
reliability (IRR) protocol for classifying the cognitive type of errors embedded in
multiple-choice question (MCQ) distractors. It implements the Confusion Fingerprint Index (CFI)
taxonomy [@Maurya2026CFI], which partitions incorrect answer choices into four
mutually exclusive cognitive categories: Recall Failure (RF), Partial Knowledge
(PK), Confabulation (CF), and Interference (INT). A calibration set of MCQ distractors is classified independently
by a human researcher and by an AI rater driven by the OpenAI API [@OpenAI2023].
Cohen's κ [@Cohen1960] is computed on the paired labels; a per-category 4×4 confusion
matrix and per-type agreement statistics are derived from the same annotation pass.
A pre-registered reliability gate (κ >= 0.70; benchmark after @Landis1977) must be
satisfied before downstream randomised controlled trial (RCT) data collection may begin,
and ConfusionMapper issues an explicit go/no-go signal tied to this threshold. Session
data (human labels, AI labels, item text, and the final κ) are exported to CSV for
transparent reporting in registered reports [@Nosek2018].

# Statement of Need

Researchers deploying theory-motivated cognitive error taxonomies in classroom
designs face a validation bootstrapping problem: the instrument must demonstrate IRR
before generating interpretable data, yet establishing reliability requires systematic
rater comparison [@Artstein2008]. The conventional two-expert-human solution is
logistically prohibitive in many educational contexts, particularly low-resource
settings where no credentialed second rater is available and per-item annotation costs
exceed small-grant budgets [@Haladyna2002].

Large language models can perform structured text annotation at high accuracy
[@OpenAI2023], enabling a human-AI hybrid IRR paradigm: a human expert and an AI
independently label the same items, and Cohen's κ is computed on the paired outputs.
Recent work on LLM raters in qualitative analysis, however, shows that human-LLM
agreement varies substantially across categories of a single rubric, from moderate
(κ ~ 0.4) to substantial (κ > 0.6) on neighbouring themes [@Borse2025LLMIRR]. This
heterogeneity makes it essential that researchers measure agreement on *their own*
taxonomy before treating LLM output as a usable label. No existing open-source
package provides (1) a taxonomy-specific AI prompt with a GUI review workflow, (2) a
category-level confusion matrix that locates where human-AI disagreement
concentrates, and (3) a pre-registration-compliant go/no-go reliability gate with
session-level CSV export. ConfusionMapper provides all three in a single,
dependency-minimal Python module.

The tool was developed as the methodological reliability gate for a pre-registered RCT
investigating whether error-type-specific feedback improves learning outcomes compared
with correctness-only feedback in government school classrooms (OSF preregistration:
osf.io/ck6nj). This origin constrains its design toward reproducibility and
pre-registration compliance rather than general-purpose flexibility.

# State of the Field

General IRR computation is well supported. R's `irr` package [@Gamer2012] provides
Cohen's κ, weighted κ, ICC, and Fleiss's κ. Python's
`sklearn.metrics.cohen_kappa_score` computes κ over pre-formatted arrays but offers
no session management, taxonomy-specific AI prompting, or GUI. QDA platforms
(MAXQDA, NVivo, ATLAS.ti) calculate κ but assume two human raters and use
proprietary formats.

None of these tools treats AI as a first-class rater or surfaces the per-cell
disagreement structure that taxonomic refinement requires. ConfusionMapper makes the
full 4×4 matrix directly visible, enabling targeted prompt revision when specific
category boundaries (notably CF versus INT in CFI) prove porous under human-AI
comparison [@Artstein2008].

# Software Description

ConfusionMapper exposes three core functions, each operating on plain Python lists of
string labels drawn from the CFI vocabulary `{RF, PK, CF, INT}`:

**`compute_cohens_kappa(human, ai)`** returns a dict with keys `kappa`, `po`, `pe`,
`n`, `agreements`, and `interpretation`. The formula follows @Cohen1960. The
implementation guards against the degenerate case Pe = 1.0 (unanimous single-category
responses by both raters) by returning κ = 1.0 when Po = 1.0, consistent with the
standard convention for that edge case.

**`build_confusion_matrix(human, ai)`** returns a nested dict indexed by
`[human_label][ai_label]`, providing the full 4×4 cross-tabulation of all label pairs.
The diagonal sum is guaranteed to equal the `agreements` count from
`compute_cohens_kappa`, providing a cross-function consistency invariant verified in the
test suite.

**`get_per_type_stats(human, ai)`** returns per-category statistics (`total`, `agreed`,
`pct`) across all four CFI types. These per-type figures answer the diagnostic question
of *where* reliability breaks down (which cognitive error boundary is most porous),
rather than collapsing agreement to a single aggregate coefficient.

The graphical interface (tkinter) presents each distractor item alongside its human and
AI label with color-coded agreement highlighting and a running κ display. The AI prompt
is deterministic and structured to produce a single CFI label;
temperature is set to zero for reproducibility across sessions. On gate
passage (κ >= 0.70), a confirmation dialog is shown and the complete session is exported
to CSV.

Three further functions extend the core. `compute_cohens_kappa` accepts a `weights` argument (`nominal`, `linear` Cicchetti-Allison, or `quadratic` Fleiss-Cohen) for ordinal taxonomies. `bootstrap_kappa_ci` returns a percentile or BCa [@Efron1987] confidence interval with a seedable RNG. `load_taxonomy_from_json` swaps the default CFI categories for any user-supplied scheme, broadening the tool beyond the CFI study.

A worked example in `case_study/` regenerates a full IRR analysis (nominal and
weighted κ, BCa 95% CI under a fixed seed, confusion matrix, per-type stats, Markdown
report) on the bundled 30-item set, bit-identical on any machine.

The test suite (`tests/test_kappa.py`) comprises 55 assertions covering the κ formula,
edge cases, weighted-κ schemes, bootstrap CI determinism, custom-taxonomy loading, and
row/column-sum invariants. All tests are self-contained and require no API credentials
or graphical environment.

# Reproducibility

All randomness in ConfusionMapper is seedable. The AI rater calls the OpenAI Chat Completions API with `model="gpt-4o"` and `temperature=0.0`; the full system prompt is embedded verbatim in `classify_with_ai`. The bootstrap CI routine accepts a `seed` parameter, so reported intervals can be regenerated bit-identically. Session CSV exports record human labels, AI labels, item text, the bootstrap seed, and the exact AI model snapshot, which together constitute a minimum reproducibility record [@Nosek2018].

# Acknowledgements

This software originated as a capstone project for Stanford Code in Place 2026 and was
developed as the methodological reliability validation tool for a pre-registered RCT
(OSF preregistration: osf.io/ck6nj) at the Department of Cognitive Science, IIT Kanpur.
The author thanks the Code in Place instructors and community for feedback during the initial development phase.

# References
