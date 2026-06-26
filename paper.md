---
title: "ConfusionMapper: A Human-AI Hybrid Inter-Rater Reliability Tool for Cognitive Error Taxonomy Classification in Multiple-Choice Questions"
author: |
  Manik Maurya \
  Independent Researcher, Kanpur, India \
  ORCID: 0009-0005-3554-693X \
  manikmaurya.in@gmail.com
date: 25 June 2026
keywords:
  - inter-rater reliability
  - Cohen's kappa
  - cognitive science
  - educational assessment
  - multiple-choice questions
  - distractor classification
  - human-AI collaboration
abstract: >
  Researchers deploying cognitive error taxonomies to classify wrong answer choices on multiple-choice questions face a validation bootstrapping problem: a coding instrument must demonstrate inter-rater reliability (IRR) before its labels can be used in statistical analysis, but the conventional two-expert-human IRR protocol is logistically prohibitive in low-resource educational settings. Large language models can perform structured annotation at high accuracy, suggesting a human-AI hybrid protocol where the AI substitutes for the second human rater. Recent empirical work, however, shows that human-LLM agreement varies substantially across categories of a single rubric, making it essential to measure agreement on the researcher's own taxonomy before treating LLM output as a usable label. We present ConfusionMapper, an open-source Python package that operationalises this protocol around the four-category Confusion Fingerprint Index (CFI) taxonomy. The tool provides nominal and weighted Cohen's kappa, bias-corrected and accelerated bootstrap confidence intervals, PABAK with bias and prevalence diagnostics for the kappa paradox, Krippendorff's alpha, Fleiss's kappa for three or more raters, an automated prompt-refinement engine that reads the confusion matrix and emits contrastive prompt instructions for the largest disagreement cells, a sample-size estimator for kappa confidence intervals, custom-taxonomy loading from JSON, a tkinter visualisation dashboard, a Unix-style command-line interface, and a fully reproducible worked example. An 88-test pytest suite (Python 3.9-3.12) cross-validates the package against published reference values. The release archive is available at https://doi.org/10.5281/zenodo.20807432.
---

# Introduction

In educational research, qualitative labels assigned by human coders enter statistical analysis only after the coding scheme has cleared an inter-rater reliability (IRR) threshold. Cohen's kappa (Cohen 1960) is the standard coefficient: it adjusts the observed proportion of agreement for chance agreement under independent marginals. Landis and Koch (1977) proposed the qualitative bands now in routine use, and a value of kappa at or above 0.70 is the de facto research threshold in education and clinical psychology.

The conventional two-expert-human IRR protocol is logistically prohibitive in many educational research contexts, particularly low-resource settings where no credentialed second rater is available and per-item annotation costs exceed small-grant budgets (Haladyna et al. 2002). Recent advances in large language models suggest a hybrid protocol in which the AI substitutes for the second human rater (OpenAI 2023). Recent empirical work on LLM raters in qualitative analysis, however, shows that human-LLM agreement varies substantially across the categories of a single rubric, from moderate (kappa ~ 0.4) to substantial (kappa > 0.6) on neighbouring themes within the same coding scheme (Borse et al. 2025). This heterogeneity makes it essential that researchers measure agreement on their own taxonomy before treating LLM output as a usable label.

ConfusionMapper is an open-source Python package designed for this purpose. It operationalises the human-AI hybrid IRR protocol around the four-category Confusion Fingerprint Index (CFI) taxonomy (Maurya 2026), which partitions incorrect answer choices on multiple-choice questions into Recall Failure (RF), Partial Knowledge (PK), Confabulation (CF), and Interference (INT). The package provides the full toolchain a researcher needs to establish reliability on the CFI taxonomy (or any user-supplied nominal scheme), diagnose disagreement at the category-boundary level, plan calibration set sizes, and iterate on the AI prompt using an automated refinement engine that reads the confusion matrix directly. The package is dependency-minimal (Python standard library plus the `openai` client) and ships with a deterministic worked example whose outputs regenerate bit-identically on any machine.

# Background and related work

General IRR computation is well supported in the scientific software ecosystem. The R `irr` package (Gamer et al. 2019) provides Cohen's kappa, weighted kappa, intraclass correlation, and Fleiss's kappa. Python's `sklearn.metrics.cohen_kappa_score` computes kappa over pre-formatted arrays but offers no session management, taxonomy-specific AI prompting, or graphical interface. Qualitative data analysis platforms (MAXQDA, NVivo, ATLAS.ti) compute kappa for coded segments but assume two human raters, use proprietary project formats, and do not export confusion matrices structured for nominal taxonomies.

None of these tools treats the AI as a first-class rater or surfaces the per-cell disagreement structure that taxonomic refinement requires. ConfusionMapper makes the full category-level confusion matrix directly visible, enabling targeted prompt revision when specific category boundaries (notably CF versus INT in CFI) prove porous under human-AI comparison (Artstein and Poesio 2008). Table 1 summarises the comparison across the dimensions that matter for AI-assisted educational annotation.

| Feature                                | sklearn | R `irr`  | MAXQDA / NVivo | ConfusionMapper |
|----------------------------------------|:-------:|:--------:|:--------------:|:---------------:|
| Cohen's kappa                          | yes     | yes      | yes            | yes             |
| Weighted kappa (linear / quadratic)    | partial | yes      | partial        | yes             |
| Krippendorff's alpha                   | no      | yes      | partial        | yes             |
| PABAK + bias / prevalence diagnostics  | no      | partial  | no             | yes             |
| Bootstrap CI (BCa, seeded)             | no      | partial  | no             | yes             |
| Sample-size estimator                  | no      | no       | no             | yes             |
| AI rater as first-class participant    | no      | no       | no             | yes             |
| Confusion-matrix export per category   | partial | partial  | partial        | yes             |
| Pre-registration go/no-go gate         | no      | no       | no             | yes             |
| Custom taxonomy via config             | partial | partial  | yes            | yes             |
| Fleiss kappa (3+ raters)               | no      | yes      | partial        | yes             |
| Auto prompt-refinement from matrix     | no      | no       | no             | yes             |
| Unix CLI with subcommands              | no      | no       | no             | yes             |

# Methods

## Statistical methods

ConfusionMapper implements the following coefficients and diagnostics. Full mathematical specifications and primary citations are documented in the file `docs/methods.md` of the release archive.

`compute_cohens_kappa(human, ai, weights=...)` computes nominal Cohen's kappa, linear weighted kappa with Cicchetti-Allison weights, or quadratic weighted kappa with Fleiss-Cohen weights, returning the Landis and Koch interpretation band as a string. The degenerate Pe = 1.0 case is guarded by returning kappa = 1.0 when Po = 1.0, the standard convention.

`bootstrap_kappa_ci(human, ai, method, seed)` computes a 95% confidence interval for kappa using either the percentile bootstrap or the bias-corrected and accelerated (BCa) bootstrap (Efron 1987). The `seed` parameter fixes the resampling order so that reported intervals regenerate bit-identically.

`compute_kappa_diagnostics(human, ai)` returns the prevalence-adjusted bias-adjusted kappa (PABAK) alongside the bias and prevalence indices of Byrt and colleagues (1993). These diagnose the well-known kappa paradox: high observed agreement combined with low kappa under skewed marginals.

`krippendorff_alpha(human, ai, level)` computes Krippendorff's alpha (Krippendorff 2018) at nominal, ordinal, or interval level. Alpha generalises kappa-style agreement to any number of raters and admits multiple measurement levels.

`fleiss_kappa(rating_matrix)` extends to panels of three or more raters (Fleiss 1971), with the same Landis and Koch interpretation bands.

`recommend_sample_size(expected_kappa, ci_half_width, n_categories)` estimates the calibration-set size required to bound the kappa CI within a target half-width under the large-sample variance approximation (Donner and Eliasziw 1992).

`suggest_prompt_refinements(human, ai, top_k)` ranks the largest off-diagonal cells of the confusion matrix and emits a Markdown report with concrete contrastive prompt instructions for each, derived from the active taxonomy's category definitions. This closes the loop between IRR measurement and rubric iteration.

## AI rater configuration

The AI rater uses the OpenAI Chat Completions API with `model="gpt-4o"` and `temperature=0.0` for determinism across sessions. The full system prompt is embedded verbatim in `classify_with_ai` in the source. Reproducibility requires pinning the model snapshot reported alongside any published results, because OpenAI model snapshots change over time.

## Software architecture

ConfusionMapper is implemented as a single Python module (`confusion_mapper.py`) with no third-party runtime dependencies beyond `openai`. A tkinter dashboard renders results visually when a display is available; otherwise the same results print to the console. A Unix-style command-line interface (`python -m confusion_mapper {kappa, alpha, diagnostics, refine, plan}`) emits JSON or Markdown on stdout for pipeline use. A custom JSON taxonomy file can replace the default CFI categories for any nominal scheme of two or more labels.

# Results: a reproducible worked example

A fully reproducible worked example lives in `case_study/run_case_study.py`. The script runs the full pipeline on 30 paired human-AI labels distributed across the four CFI categories, using a fixed random seed (20260623) and 10000 bootstrap resamples. Headline results on the bundled data set are: nominal kappa = 0.8653 ("Almost perfect" by Landis and Koch); linear weighted kappa = 0.9136; quadratic weighted kappa = 0.9538; 95% BCa bootstrap confidence interval (0.6856, 1.0000); the pre-registration gate at kappa >= 0.70 passes. All outputs (JSON summary, CSV confusion matrix, CSV per-type statistics, CSV bootstrap distribution, Markdown report) regenerate bit-identically on any machine that runs the same package version.

The 88-test pytest suite cross-validates the implementation against hand-verified textbook reference values for nominal kappa on a 3 by 3 contingency table (n = 196, agreements = 140, computed kappa = 0.5086 within 0.0001 of the value derived analytically from the table marginals) and verifies that the Landis and Koch interpretation bands are correctly assigned at the threshold boundaries.

# Discussion

ConfusionMapper provides the methodological reliability gate for a pre-registered three-arm randomised controlled trial in 90 students across government junior high schools in Kanpur Dehat, Uttar Pradesh, India (OSF preregistration: osf.io/ck6nj). The package was developed in part during a research internship at the Department of Cognitive Science, Indian Institute of Technology Kanpur. Data collection in the RCT cannot start until kappa on the CFI calibration set clears the 0.70 threshold the tool enforces. The CFI taxonomy itself is described in a companion preprint (Maurya 2026).

The contribution beyond existing IRR tooling is threefold. First, the package treats the AI as a first-class rater whose disagreements with the human are diagnostic information about the prompt, not noise to be averaged away. The automated `suggest_prompt_refinements` function operationalises this by transforming the confusion matrix into concrete prompt-rewrite suggestions. We are not aware of another open-source IRR tool that does this. Second, the package combines the IRR coefficients researchers actually need (nominal and weighted Cohen's kappa, Krippendorff's alpha, Fleiss's kappa, PABAK) with diagnostic tooling for the kappa paradox and a planning-stage sample-size estimator in a single, dependency-minimal module. Third, the package enforces pre-registration discipline: a researcher cannot pass the reliability gate by accident, because the threshold is checked programmatically and the session is exported with the seed and AI model identifier required to reproduce it, in line with current best practice for the pre-registration paradigm (Nosek et al. 2018).

A known limitation is that the AI rater is currently coupled to the OpenAI Chat Completions API. Future versions will abstract this behind a rater interface so that local or alternative-vendor models can be plugged in without code changes. A second limitation is that the prompt-refinement engine emits suggestions derived from the taxonomy's textual definitions; sophisticated rubric iteration still requires human judgement.

# Conclusion

ConfusionMapper supports the human-AI hybrid IRR protocol with the statistical depth (nominal and weighted kappa, BCa bootstrap CI, Krippendorff's alpha, Fleiss's kappa, PABAK), the diagnostic surface (confusion matrix at category-pair resolution, prompt-refinement engine), and the reproducibility guarantees (seeded bootstrap, pinned AI model, deterministic worked example) that low-resource educational researchers need to qualify a cognitive error taxonomy for downstream statistical analysis. The package is open-source under the MIT license and archived on Zenodo at https://doi.org/10.5281/zenodo.20807432.

# Acknowledgements

This software originated as a capstone project for Stanford Code in Place 2026. Early development took place during a research internship at the Department of Cognitive Science, Indian Institute of Technology Kanpur.

# References

Cohen J. (1960). A coefficient of agreement for nominal scales. *Educational and Psychological Measurement*, 20(1), 37-46. https://doi.org/10.1177/001316446002000104

Landis J.R., Koch G.G. (1977). The measurement of observer agreement for categorical data. *Biometrics*, 33(1), 159-174. https://doi.org/10.2307/2529310

Haladyna T.M., Downing S.M., Rodriguez M.C. (2002). A review of multiple-choice item-writing guidelines for classroom assessment. *Applied Measurement in Education*, 15(3), 309-334. https://doi.org/10.1207/S15324818AME1503_5

OpenAI (2023). GPT-4 Technical Report. OpenAI. https://doi.org/10.48550/arXiv.2303.08774

Borse N.S., Subramaniam R.C., Rebello N.S. (2025). Investigation of the Inter-Rater Reliability between Large Language Models and Human Raters in Qualitative Analysis. arXiv:2508.14764. https://doi.org/10.48550/arXiv.2508.14764

Maurya M. (2026). Confusion Fingerprint Index: A Taxonomy of Cognitive Error Types in Multiple-Choice Assessment. EdArXiv. https://doi.org/10.35542/osf.io/cr53e_v1

Gamer M., Lemon J., Singh I.F.P. (2019). irr: Various coefficients of interrater reliability and agreement. R package version 0.84.1. https://CRAN.R-project.org/package=irr

Artstein R., Poesio M. (2008). Inter-coder agreement for computational linguistics. *Computational Linguistics*, 34(4), 555-596. https://doi.org/10.1162/coli.07-034-R2

Efron B. (1987). Better Bootstrap Confidence Intervals. *Journal of the American Statistical Association*, 82(397), 171-185. https://doi.org/10.1080/01621459.1987.10478410

Byrt T., Bishop J., Carlin J.B. (1993). Bias, Prevalence and Kappa. *Journal of Clinical Epidemiology*, 46(5), 423-429. https://doi.org/10.1016/0895-4356(93)90018-V

Krippendorff K. (2018). Content Analysis: An Introduction to Its Methodology. (4 ed.), Thousand Oaks, CA, SAGE Publications.

Fleiss J.L. (1971). Measuring Nominal Scale Agreement Among Many Raters. *Psychological Bulletin*, 76(5), 378-382. https://doi.org/10.1037/h0031619

Donner A., Eliasziw M. (1992). A Goodness-of-Fit Approach to Inference Procedures for the Kappa Statistic: Confidence Interval Construction, Significance-Testing and Sample Size Estimation. *Statistics in Medicine*, 11(11), 1511-1519. https://doi.org/10.1002/sim.4780111109

Nosek B.A., Ebersole C.R., DeHaven A.C., Mellor D.T. (2018). The preregistration revolution. *Proceedings of the National Academy of Sciences*, 115(11), 2600-2606. https://doi.org/10.1073/pnas.1708274114
