"""
run_case_study.py - reproducible worked example for ConfusionMapper.

This script runs the full ConfusionMapper analysis pipeline on the
30 paired human/AI labels in sample_data/example_labels.csv. It calls
no network APIs, uses only the Python standard library plus ConfusionMapper,
and writes deterministic outputs under case_study/results/.

Run:
    python case_study/run_case_study.py

Outputs (overwritten each run, reproducible byte-for-byte under the same seed):
    case_study/results/summary.json       - all kappa variants + 95% CI
    case_study/results/confusion_matrix.csv
    case_study/results/per_type_stats.csv
    case_study/results/bootstrap_kappas.csv   - the full BCa resample distribution
    case_study/results/REPORT.md          - human-readable narrative
"""

import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(HERE, "results")
sys.path.insert(0, REPO_ROOT)

from confusion_mapper import (
    compute_cohens_kappa,
    build_confusion_matrix,
    get_per_type_stats,
    bootstrap_kappa_ci,
    ERROR_TYPES,
)


SEED = 20260623        # fixed for byte-identical reproducibility
N_RESAMPLES = 10000


def load_labels():
    path = os.path.join(REPO_ROOT, "sample_data", "example_labels.csv")
    human, ai = [], []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            human.append(row["human_label"])
            ai.append(row["ai_label"])
    return human, ai


def write_csv(path, rows, header):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    os.makedirs(RESULTS, exist_ok=True)
    human, ai = load_labels()
    n = len(human)

    nominal   = compute_cohens_kappa(human, ai, weights="nominal")
    linear    = compute_cohens_kappa(human, ai, weights="linear")
    quadratic = compute_cohens_kappa(human, ai, weights="quadratic")

    # Reproducible BCa bootstrap (uses ConfusionMapper's own RNG via the seed arg).
    ci = bootstrap_kappa_ci(
        human, ai,
        n_resamples=N_RESAMPLES,
        method="bca",
        weights="nominal",
        seed=SEED,
    )

    matrix = build_confusion_matrix(human, ai)
    per_type = get_per_type_stats(human, ai)

    # Re-run the resample loop with the same seed to capture the full distribution
    # for diagnostic plotting downstream.
    import random
    rng = random.Random(SEED)
    pairs = list(zip(human, ai))
    boot_kappas = []
    for _ in range(N_RESAMPLES):
        sample = [rng.choice(pairs) for _ in range(n)]
        h = [p[0] for p in sample]
        a = [p[1] for p in sample]
        boot_kappas.append(
            compute_cohens_kappa(h, a, weights="nominal")["kappa"]
        )

    # --- write outputs --------------------------------------------------------

    summary = {
        "n_items": n,
        "seed": SEED,
        "n_resamples": N_RESAMPLES,
        "nominal_kappa":       nominal["kappa"],
        "linear_weighted_kappa":    linear["kappa"],
        "quadratic_weighted_kappa": quadratic["kappa"],
        "po": nominal["po"],
        "pe": nominal["pe"],
        "agreements": nominal["agreements"],
        "interpretation_nominal": nominal["interpretation"],
        "ci_95_bca": {
            "lower": ci["ci_lower"],
            "upper": ci["ci_upper"],
            "method": ci["method"],
            "confidence": ci["confidence"],
        },
        "pre_registration_gate_kappa_ge_0_70": nominal["kappa"] >= 0.70,
    }
    with open(os.path.join(RESULTS, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, sort_keys=False)
        f.write("\n")

    write_csv(
        os.path.join(RESULTS, "confusion_matrix.csv"),
        [[row] + [matrix[row][col] for col in ERROR_TYPES] for row in ERROR_TYPES],
        header=["human_label"] + ["ai_" + c for c in ERROR_TYPES],
    )

    write_csv(
        os.path.join(RESULTS, "per_type_stats.csv"),
        [[c, per_type[c]["total"], per_type[c]["agreed"], per_type[c]["pct"]]
         for c in ERROR_TYPES],
        header=["category", "total", "agreed", "pct_agreement"],
    )

    write_csv(
        os.path.join(RESULTS, "bootstrap_kappas.csv"),
        [[i, k] for i, k in enumerate(boot_kappas)],
        header=["resample_index", "bootstrap_kappa"],
    )

    # Narrative report.
    pass_str = "PASS" if summary["pre_registration_gate_kappa_ge_0_70"] else "HOLD"
    report = (
        f"# Case study: reproducible IRR analysis on a 30-item distractor calibration set\n\n"
        f"This report is regenerated automatically by `run_case_study.py`. The exact numbers\n"
        f"below are reproducible bit-for-bit under seed `{SEED}` and "
        f"`{N_RESAMPLES}` bootstrap resamples on the bundled `sample_data/example_labels.csv`\n"
        f"file. All computations use only the Python standard library plus ConfusionMapper.\n\n"
        f"## Headline\n\n"
        f"| Quantity | Value |\n"
        f"|---|---|\n"
        f"| Items rated | {n} |\n"
        f"| Observed agreement Po | {nominal['po']} |\n"
        f"| Chance agreement Pe   | {nominal['pe']} |\n"
        f"| Cohen's kappa (nominal)        | **{nominal['kappa']}** |\n"
        f"| Weighted kappa (linear)        | {linear['kappa']} |\n"
        f"| Weighted kappa (quadratic)     | {quadratic['kappa']} |\n"
        f"| 95% BCa bootstrap CI on nominal kappa | ({ci['ci_lower']}, {ci['ci_upper']}) |\n"
        f"| Pre-registration gate (kappa >= 0.70)  | **{pass_str}** |\n\n"
        f"Interpretation (Landis & Koch 1977): {nominal['interpretation']}\n\n"
        f"## Confusion matrix (rows = human, columns = AI)\n\n"
    )
    # Render matrix as markdown
    report += "| human \\ ai | " + " | ".join(ERROR_TYPES) + " |\n"
    report += "|---" * (len(ERROR_TYPES) + 1) + "|\n"
    for row in ERROR_TYPES:
        report += f"| {row} | " + " | ".join(str(matrix[row][col]) for col in ERROR_TYPES) + " |\n"

    report += (
        f"\n## Per-category agreement\n\n"
        f"| Category | Items | Agreed | % |\n"
        f"|---|---|---|---|\n"
    )
    for c in ERROR_TYPES:
        s = per_type[c]
        report += f"| {c} | {s['total']} | {s['agreed']} | {s['pct']}% |\n"

    report += (
        f"\n## Reproducibility\n\n"
        f"- Seed: `{SEED}`\n"
        f"- Bootstrap resamples: `{N_RESAMPLES}`\n"
        f"- Bootstrap method: BCa (Efron 1987)\n"
        f"- AI rater: not invoked in this script; the labels in the CSV were generated\n"
        f"  with the OpenAI Chat Completions API (`gpt-4o`, temperature 0.0) using the\n"
        f"  prompt embedded in `classify_with_ai`. Pin the exact model snapshot in any\n"
        f"  replication run.\n"
        f"- Dependencies: ConfusionMapper plus the Python standard library only.\n"
        f"- Regenerate with: `python case_study/run_case_study.py`\n"
    )
    with open(os.path.join(RESULTS, "REPORT.md"), "w", encoding="utf-8") as f:
        f.write(report)

    print("=" * 66)
    print("Case study regenerated.")
    print(f"  nominal kappa  = {nominal['kappa']}")
    print(f"  linear weighted = {linear['kappa']}")
    print(f"  quadratic      = {quadratic['kappa']}")
    print(f"  95% BCa CI     = ({ci['ci_lower']}, {ci['ci_upper']})")
    print(f"  gate           = {pass_str}")
    print(f"  outputs in     -> {os.path.relpath(RESULTS, REPO_ROOT)}")
    print("=" * 66)


if __name__ == "__main__":
    main()
