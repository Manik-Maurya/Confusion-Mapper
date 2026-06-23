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
multiple-choice question (MCQ) distractors. It implements the Confusion Fingerprint
Index (CFI) taxonomy [@Maurya2026CFI], which partitions incorrect answer choices into
four theoretically grounded, mutually exclusive cognitive categories: **Recall Failure**
(RF; absent retrieval trace), **Partial Knowledge** (PK; incomplete but directionally
correct understanding), **Confabulation** (CF; coherent but incorrect mental model held
with high confidence), and **Interference** (INT; cross-domain knowledge activated in
the wrong context). A calibration set of MCQ distractors is classified independently
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

The demonstrated capability of large language models to perform structured text
annotation tasks at high accuracy [@OpenAI2023] creates the possibility of a human-AI
hybrid IRR paradigm: a human expert and an AI model independently label the same items,
and Cohen's κ is computed on the paired outputs. Recent empirical work on LLM raters in
qualitative analysis, however, finds that human-LLM agreement varies substantially
across the categories of a single rubric, from moderate (κ ~ 0.4) on some themes to
substantial (κ > 0.6) on neighbouring themes within the same coding scheme
[@Borse2025LLMIRR]. This per-category heterogeneity makes it essential that researchers
measure agreement on *their own* taxonomy before treating LLM output as a usable label,
rather than assuming model-level benchmarks transfer. Yet this paradigm is being
adopted in educational research without dedicated, transparent tooling. No existing
open-source research software package provides (1) a structured, taxonomy-specific AI
prompt integrated with a GUI annotation review workflow, (2) a 4×4 confusion matrix
that reveals the precise category boundaries where human-AI disagreement
concentrates, not just the aggregate coefficient, and (3) a pre-registration-compliant
go/no-go reliability gate with session-level CSV export for registered-report
transparency. ConfusionMapper provides all three in a single, dependency-minimal Python
module.

The tool was developed as the methodological reliability gate for a pre-registered RCT
investigating whether error-type-specific feedback improves learning outcomes compared
with correctness-only feedback in government school classrooms (OSF preregistration:
osf.io/ck6nj). This origin constrains its design toward reproducibility and
pre-registration compliance rather than general-purpose flexibility.

# State of the Field

General IRR computation is well supported. The R `irr` package [@Gamer2012] provides
Cohen's κ, weighted κ, ICC, and Fleiss's κ. Python's `sklearn.metrics.cohen_kappa_score`
computes κ over pre-formatted arrays but offers no session management, no
taxonomy-specific AI prompting, and no GUI. Qualitative data analysis
platforms (MAXQDA, NVivo, ATLAS.ti) calculate κ for coded segments but assume two
human raters, use proprietary project formats, and do not export confusion matrices
structured for four-category nominal taxonomies.

Critically, none of these tools treats AI as a first-class rater. ConfusionMapper is
designed specifically around the CFI taxonomy, where the distinction between CF
(confident wrong model) and INT (cross-domain activation) is subtle enough that the
confusion matrix cell [CF, INT] is diagnostically important in its own right. The tool
makes this cell, and all fifteen off-diagonal cells of the 4×4 matrix, directly visible,
enabling targeted prompt refinement when category boundaries prove porous under
human-AI comparison [@Artstein2008].

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
is deterministic and structured to produce a single CFI label without chain-of-thought
verbosity; temperature is set to zero for reproducibility across sessions. On gate
passage (κ >= 0.70), a confirmation dialog is shown and the complete session is exported
to CSV.

The test suite (`tests/test_kappa.py`) comprises 35+ assertions across five classes:
perfect agreement, hand-verified known-value κ calculations with worked examples,
below-chance agreement, edge cases (n = 0, n = 1), κ symmetry, interpretation threshold
mapping, confusion matrix cell counting and row/column sum integrity, per-type sum
consistency, and cross-function agreement consistency. All tests are self-contained and
require no API credentials or graphical environment.

# Acknowledgements

This software originated as a capstone project for Stanford Code in Place 2026 and was
developed as the methodological reliability validation tool for a pre-registered RCT
(OSF preregistration: osf.io/ck6nj) at the Department of Cognitive Science, IIT Kanpur.
The author thanks the Code in Place instructors and community for feedback during the initial development phase.

# References
