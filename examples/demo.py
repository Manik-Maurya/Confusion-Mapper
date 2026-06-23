"""
demo.py, headless tutorial for ConfusionMapper core functions.

Runs a full inter-rater reliability analysis on 30 pre-labelled distractors
from sample_data/example_labels.csv. Calls the same three functions the GUI
calls. Needs no API key, no display, and no extra dependencies beyond the
Python standard library, so it works on CI and headless servers.

Usage:
    python examples/demo.py

What it prints:
    - Cohen's kappa with the Landis-Koch interpretation
    - the 4x4 confusion matrix (RF / PK / CF / INT)
    - per-category agreement statistics
    - PASS or HOLD against the 0.70 pre-registration gate

To use your own data, replace sample_data/example_labels.csv with a CSV
that has the columns human_label and ai_label.
"""

import csv
import os
import sys

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
    print("ConfusionMapper, headless demo")
    print("=" * 66)
    print(f"Loaded {len(human)} paired human/AI labels from {os.path.basename(csv_path)}\n")

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

    print("2. 4x4 Confusion Matrix")
    print("-" * 66)
    matrix = build_confusion_matrix(human, ai)
    print_confusion_matrix(matrix)
    print()

    print("3. Per-Category Agreement")
    print("-" * 66)
    stats = get_per_type_stats(human, ai)
    print(f"   {'Type':<6}{'Total':>8}{'Agreed':>10}{'%':>8}")
    for label in ERROR_TYPES:
        s = stats[label]
        print(f"   {label:<6}{s['total']:>8}{s['agreed']:>10}{s['pct']:>7}%")
    print()

    print("4. Pre-Registration Reliability Gate (kappa >= 0.70)")
    print("-" * 66)
    if k["kappa"] >= 0.70:
        print(f"   PASS, kappa = {k['kappa']:.4f} meets the pre-registered threshold.")
        print("         Downstream data collection may proceed.")
    else:
        print(f"   HOLD, kappa = {k['kappa']:.4f} is below the 0.70 threshold.")
        print("         Refine the AI prompt or human rubric and re-run before proceeding.")
    print("=" * 66)

    return 0 if k["kappa"] >= 0.70 else 1


if __name__ == "__main__":
    sys.exit(main())
