"""
demo.py — Headless tutorial for ConfusionMapper core functions
==============================================================

This script reproduces a complete inter-rater reliability analysis from
30 pre-labelled distractors in `sample_data/example_labels.csv`, calling
the same three functions exposed by the GUI. It requires NO API key,
NO display, and NO additional dependencies beyond the Python standard
library — making it suitable for CI, headless servers, and reviewers
who want to verify the package's core functionality in under a second.

Usage:
    python examples/demo.py

Expected output:
    - Cohen's kappa value with Landis-Koch interpretation
    - 4x4 confusion matrix (RF / PK / CF / INT)
    - Per-category agreement statistics
    - Pre-registration gate decision (PASS if kappa >= 0.70)

Educational researchers can adapt this script by replacing the CSV with
their own paired human/AI labels.
"""

import csv
import os
import sys

# Make the package importable when running from the repo root or examples/
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from confusion_mapper import (
    compute_cohens_kappa,
    build_confusion_matrix,
    get_per_type_stats,
    ERROR_TYPES,
)


def load_paired_labels(csv_path):
    """Load human and AI labels from a CSV with columns human_label, ai_label."""
    human, ai = [], []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            human.append(row["human_label"])
            ai.append(row["ai_label"])
    return human, ai


def print_confusion_matrix(matrix):
    """Pretty-print the 4x4 confusion matrix."""
    header = "human\\ai".ljust(10) + "".join(t.rjust(6) for t in ERROR_TYPES)
    print(header)
    print("-" * len(header))
    for row in ERROR_TYPES:
        line = row.ljust(10) + "".join(str(matrix[row][col]).rjust(6) for col in ERROR_TYPES)
        print(line)


def main():
    csv_path = os.path.join(os.path.dirname(HERE), "sample_data", "example_labels.csv")
    human, ai = load_paired_labels(csv_path)

    print("=" * 66)
    print("ConfusionMapper — Headless Demo")
    print("=" * 66)
    print(f"Loaded {len(human)} paired human/AI labels from {os.path.basename(csv_path)}\n")

    # 1. Cohen's kappa
    k = compute_cohens_kappa(human, ai)
    print("1. Cohen's Kappa")
    print("-" * 66)
    print(f"   kappa          = {k['kappa']:.4f}")
    print(f"   interpretation = {k['interpretation']}")
    print(f"   Po (observed)  = {k['po']:.4f}")
    print(f"   Pe (expected)  = {k['pe']:.4f}")
    print(f"   n              = {k['n']}")
    print(f"   agreements     = {k['agreements']}")
    print()

    # 2. Confusion matrix
    print("2. 4x4 Confusion Matrix")
    print("-" * 66)
    matrix = build_confusion_matrix(human, ai)
    print_confusion_matrix(matrix)
    print()

    # 3. Per-type agreement
    print("3. Per-Category Agreement")
    print("-" * 66)
    stats = get_per_type_stats(human, ai)
    print(f"   {'Type':<6}{'Total':>8}{'Agreed':>10}{'%':>8}")
    for label in ERROR_TYPES:
        s = stats[label]
        print(f"   {label:<6}{s['total']:>8}{s['agreed']:>10}{s['pct']:>7}%")
    print()

    # 4. Pre-registration gate decision
    print("4. Pre-Registration Reliability Gate (kappa >= 0.70)")
    print("-" * 66)
    if k["kappa"] >= 0.70:
        print(f"   PASS — kappa = {k['kappa']:.4f} meets the pre-registered threshold.")
        print("          Downstream data collection MAY proceed.")
    else:
        print(f"   HOLD — kappa = {k['kappa']:.4f} is below the 0.70 threshold.")
        print("          Refine the AI prompt or human rubric and re-run before proceeding.")
    print("=" * 66)

    # Exit code mirrors the gate decision so CI can assert on it.
    return 0 if k["kappa"] >= 0.70 else 1


if __name__ == "__main__":
    sys.exit(main())
