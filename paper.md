---
title: 'ConfusionMapper: A Python Tool for AI-Assisted Distractor Classification and Inter-Rater Reliability Computation in Cognitive Error Taxonomy Research'
tags:
  - Python
  - inter-rater reliability
  - Cohen's kappa
  - educational research
  - cognitive error classification
  - adaptive learning
  - educational data mining
authors:
  - name: Manik Maurya
    orcid: 0009-0005-3554-693X
    affiliation: 1
affiliations:
  - name: Department of Cognitive Science, Indian Institute of Technology Kanpur, Kanpur 208016, Uttar Pradesh, India
    index: 1
date: 10 June 2026
bibliography: paper.bib
---

# Summary

ConfusionMapper is a Python desktop application for inter-rater reliability (IRR) computation in cognitive error taxonomy research. It operationalises a two-rater classification workflow in which a human researcher and an AI rater independently assign each multiple-choice question (MCQ) distractor to one of four mutually exclusive cognitive error categories: Recall Failure, Partial Knowledge, Confabulation, and Interference. Cohen's kappa (κ) is then computed between the two raters, and results are presented through an interactive visualisation dashboard that includes a kappa gauge, a 4×4 confusion matrix, and per-category agreement statistics. ConfusionMapper was developed as the pre-data-collection quality gate for a preregistered randomised controlled trial investigating whether cognitive error taxonomy can serve as an adaptive learning signal [@maurya2026].

# Statement of Need

Taxonomy-based error classification is a foundational step in the construction of cognitive tutoring systems and adaptive learning platforms that respond to the *type* of error a learner makes, rather than merely to its correctness. For such systems, the validity of any downstream statistical claim depends directly on whether the distractor labels used in the analysis were assigned with sufficient inter-rater agreement. The standard criterion in psychology and educational research is κ ≥ 0.70, corresponding to substantial agreement on the Landis and Koch scale [@landis1977].

In practice, however, researchers conducting small-to-medium-scale studies face an infrastructural gap. General-purpose IRR packages — such as the `irr` library in R or the `cohen_kappa_score` function in scikit-learn [@pedregosa2011] — provide only statistical computation: they accept pre-formatted label arrays and return a scalar. They offer no support for the full workflow that precedes statistical analysis: presenting individual distractors to raters, managing rater sessions, recording reasoning, or flagging items that fall below the reliability threshold. This forces researchers to construct bespoke spreadsheet-based pipelines, increasing the risk of bookkeeping errors and making the classification process difficult to document or reproduce.

A further methodological development motivates ConfusionMapper specifically: the growing use of large language models (LLMs) as auxiliary annotators in social-science and educational research. Several studies have demonstrated that GPT-class models can achieve human-comparable agreement rates on structured annotation tasks [@gilardi2023], which suggests a practical workflow for smaller research teams: the researcher classifies each distractor independently, the model classifies in parallel, and κ quantifies the degree of human–AI agreement. This does not substitute for human–human validation — and ConfusionMapper explicitly flags this limitation to the user — but it provides an efficient, low-cost mechanism for identifying borderline items that warrant discussion before data collection begins.

ConfusionMapper fills this gap by providing an end-to-end workflow: distractor loading, rater session management, AI classification via the OpenAI API, pairwise Cohen's kappa computation with interpretation, threshold flagging, confusion matrix construction, visualisation, and JSON export. No existing open-source tool combines these components for use with a researcher-specified cognitive error taxonomy.

# Functionality

**Classification workflow.** The tool presents each distractor sequentially in a console interface, prompting the researcher to assign one of four CFI labels. In parallel, when an OpenAI API key is available, the same distractor is submitted to GPT-3.5-turbo with a structured system prompt that defines the taxonomy and requests a JSON-formatted response containing the label and a one-sentence reasoning string. The model is called at temperature 0.2 to reduce stochasticity and improve reproducibility across sessions. If the API key is absent or the call fails, the tool falls back to manual-only mode with no disruption to the human-rating workflow.

**Cohen's kappa computation.** The kappa statistic is computed from first principles following @cohen1960:

$$\kappa = \frac{P_o - P_e}{1 - P_e}$$

where $P_o$ is the observed proportional agreement between the two raters, and $P_e$ is the agreement expected by chance, computed as the sum over all categories of the product of the marginal proportions assigned by each rater. The implementation handles the edge case where $P_e = 1$ by returning $\kappa = 1.0$. Interpretation follows the Landis and Koch benchmarks [@landis1977], with the research threshold of κ ≥ 0.70 highlighted explicitly in the output.

**Confusion matrix and per-category statistics.** Alongside the scalar kappa, the tool constructs a 4×4 confusion matrix (rows: human labels; columns: AI labels) and computes per-category agreement as the proportion of items that the human labelled as category $c$ for which the AI rater agreed. Per-category statistics are particularly useful for identifying which error types drive disagreement: in the CFI taxonomy, the Confabulation–Partial Knowledge boundary is empirically the most ambiguous, and per-category output allows researchers to target rubric revision precisely.

**Visualisation dashboard.** Results are rendered in a tkinter GUI comprising three panels: (1) a semicircular speedometer gauge encoding the κ value with colour-coded zones corresponding to the Landis–Koch benchmarks; (2) the 4×4 confusion matrix with green diagonal cells (agreement) and red off-diagonal cells (disagreement); and (3) a horizontal bar chart of per-category agreement percentages against the 70% threshold line. The tool degrades gracefully on headless systems: if tkinter is unavailable, all statistics are printed to the console and exported to JSON.

**Built-in question bank and question generation.** The tool ships with a built-in NCERT-aligned question bank covering five topics across Classes 7–8 of the Indian school curriculum, with 15 pre-labelled distractors drawn from the CFI RCT question pool. This enables offline use with no external dependencies beyond the Python standard library. For researchers working with other curricula, the tool supports AI-generated question sets via the OpenAI API and custom CSV import.

**Export.** Each session is serialised to a structured JSON file containing the question metadata, distractor text, human and AI labels, AI reasoning strings, agreement flags, and summary statistics. This export format is designed for direct ingestion by downstream analysis pipelines.

# Research Applications

ConfusionMapper was developed and validated in the context of the Confusion Fingerprint Index (CFI) research programme at the Department of Cognitive Science, IIT Kanpur [@maurya2026]. The CFI framework characterises each learner's distribution of error types across a question bank as a diagnostic signal for adaptive learning systems. Establishing reliable distractor labels is a prerequisite for computing CFI profiles, and ConfusionMapper served as the pre-data-collection quality gate for the associated preregistered RCT (n = 90, Classes 6–8, government junior high schools, Kanpur Dehat, Uttar Pradesh, India; OSF preregistration: doi.org/10.17605/OSF.IO/YU6P5), which required κ ≥ 0.70 before data collection could proceed.

The tool is taxonomy-agnostic. Researchers working with other multi-category qualitative coding schemes — such as error taxonomies in mathematics education, misconception frameworks in science education, or rubric-based coding in qualitative research — can substitute their own category set by modifying the `ERROR_TYPES` and `TAXONOMY` constants.

# Acknowledgements

The author thanks Prof. K. M. Sharika (Department of Cognitive Science, IIT Kanpur) for supervision and research guidance throughout the development of this tool and the associated research programme.

# References
