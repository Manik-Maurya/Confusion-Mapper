<h1 align="center">ConfusionMapper</h1>

![ConfusionMapper](assets/thumbnail.png)

<p align="center">
  <strong>Human vs AI Agreement for Cognitive Error Classification</strong>
</p>

<p align="center">
  A research tool for classifying cognitive error types in MCQ distractors and measuring inter-rater agreement using Cohen's Kappa (κ).
</p>

---

## Overview

Every wrong answer a student gives reveals something different about how they think—but most educational software only sees **"wrong."**

ConfusionMapper classifies MCQ distractors into four cognitive error types from the **Confusion Fingerprint Taxonomy**:

| Code | Error Type        |
| ---- | ----------------- |
| RF   | Recall Failure    |
| PK   | Partial Knowledge |
| CF   | Confabulation     |
| INT  | Interference      |

A human researcher and ChatGPT independently classify each distractor. The system then computes **Cohen's Kappa (κ)**, a widely used statistical measure of inter-rater agreement in psychology, education, and cognitive science.

The results are visualized through:

* Human vs AI Agreement Gauge
* Cohen's Kappa Reliability Score
* 4×4 Confusion Matrix
* Per-Type Agreement Statistics

---

## Example Result

```text
Human vs AI Agreement

κ = 0.74
(Substantial Agreement)
```

A study protocol may require a minimum reliability threshold before research data collection can begin.

---

## Research Context

ConfusionMapper was developed as the pre-data-collection quality gate for a pre-registered randomized controlled trial involving **108 students** at IIT Kanpur's Cognitive Science Department.

The study protocol required:

> κ ≥ 0.70

before student data collection could proceed.

The software was built to operationalize, validate, and document that requirement.

---

## Features

### Cognitive Error Classification

Classifies distractors into:

* Recall Failure (RF)
* Partial Knowledge (PK)
* Confabulation (CF)
* Interference (INT)

### Human vs AI Agreement Analysis

* Independent classification by researcher and GPT
* Automatic agreement computation
* Cohen's Kappa calculation
* Reliability interpretation

### Visualization Dashboard

* Kappa speedometer gauge
* Agreement summary
* Confusion matrix
* Category-level breakdowns

### Offline Mode

Includes a built-in NCERT question bank.

### Live Question Generation

Generate new MCQs on any topic using the OpenAI API.

### Research Record Keeping

Export complete sessions as JSON files containing:

* Questions
* Distractors
* Human labels
* AI labels
* Agreement statistics

---

## Technology Stack

* Python
* Tkinter
* OpenAI API
* JSON
* Cohen's Kappa Statistical Analysis

---

## Why This Project Matters

Most educational systems treat wrong answers as simple mistakes.

ConfusionMapper treats them as **cognitive signals**.

By identifying *why* an answer is wrong—and validating those classifications through human-AI agreement—the tool helps researchers study learning, misconceptions, and knowledge representation with greater rigor.

---

## Future Development

* Expanded confusion taxonomy
* Multi-rater reliability analysis
* Research analytics dashboard
* Classroom-scale deployment
* Integration with Cognivia
* Educational intervention recommendations

---

## Acknowledgments

Built using skills developed through Stanford Code in Place and applied to ongoing cognitive science research at IIT Kanpur.

---

## License

MIT License

---

<p align="center">
  <strong>Detect. Measure. Understand.</strong>
</p>
