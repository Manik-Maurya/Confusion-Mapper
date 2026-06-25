# Cover letter — PeerJ Computer Science

Dear PeerJ Computer Science Editors,

I am pleased to submit the manuscript "ConfusionMapper: A Human-AI Hybrid Inter-Rater Reliability Tool for Cognitive Error Taxonomy Classification in Multiple-Choice Questions" for consideration in the Software Tools track.

ConfusionMapper is an open-source Python package that operationalises a human-AI hybrid inter-rater reliability (IRR) protocol for classifying cognitive error types in multiple-choice question distractors. It was developed in part during a research internship at the Department of Cognitive Science, Indian Institute of Technology Kanpur, where it now serves as the methodological reliability gate for a pre-registered three-arm randomised controlled trial in 90 government junior high school students (OSF preregistration: osf.io/ck6nj). The package is archived on Zenodo under DOI 10.5281/zenodo.20807432 and the source code is publicly available at https://github.com/Manik-Maurya/Confusion-Mapper.

The contribution beyond existing IRR tooling is threefold. First, ConfusionMapper treats the AI rater as a first-class participant whose category-level disagreements with the human are diagnostic information about the AI prompt, not noise to be averaged away. The package includes an automated `suggest_prompt_refinements` function that reads the confusion matrix and emits concrete contrastive prompt instructions for the largest disagreement cells. To my knowledge, no existing open-source IRR tool does this. Second, the package combines the coefficients researchers actually need (nominal and weighted Cohen's kappa, Krippendorff's alpha at three measurement levels, Fleiss's kappa for three or more raters, PABAK with bias and prevalence indices for diagnosing the kappa paradox) with BCa bootstrap confidence intervals and a calibration-set sample-size estimator, in a single dependency-minimal module. Third, the package enforces pre-registration discipline programmatically: a researcher cannot pass the reliability gate by accident because the threshold is checked in code and the session is exported with the random seed and AI model identifier required to reproduce it.

The repository ships with an 88-test pytest suite passing on Python 3.9-3.12 (GitHub Actions matrix), a reproducible worked-example case study whose outputs regenerate bit-identically, and a Unix-style command-line interface with five subcommands. Statistical methods are documented in `docs/methods.md` with primary citations for every formula, and tests cross-validate the implementation against published reference values (a textbook 3 by 3 contingency table is reproduced to four decimal places).

This work has not been submitted elsewhere and is not under consideration by any other journal. I have no conflicts of interest to declare. As a single-author submission, I am the sole contributor.

I am an undergraduate researcher in India submitting independently. I have separately requested a developing-country fee waiver under PeerJ's discretionary policy.

Suggested reviewers (independent of my prior collaborators):

- Researchers active in inter-rater reliability methodology in educational measurement.
- Researchers working on large-language-model-as-judge evaluation.
- Researchers in qualitative data analysis software.

I would be glad to suggest specific names if helpful. I look forward to the reviewers' feedback.

Sincerely,

Manik Maurya
Independent Researcher, Kanpur, India
ORCID: 0009-0005-3554-693X
Email: manikmaurya.in@gmail.com
