"""
test_kappa.py, pytest test suite for ConfusionMapper core functions

Tests cover:
  - compute_cohens_kappa()   : k formula, edge cases, interpretation thresholds
  - build_confusion_matrix() : correct cell counting, diagonal agreement
  - get_per_type_stats()     : per-category agreement computation

All tests are self-contained: no OpenAI API calls, no tkinter, no file I/O.
The module-level tkinter availability check in confusion_mapper.py is safe
to execute in headless CI environments (it catches all exceptions).

Run with:  pytest tests/test_kappa.py -v
"""

import sys
import os
import math
import pytest

# ---------------------------------------------------------------------------
# Import path setup, works whether tests/ is run from repo root or directly
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import (
    compute_cohens_kappa,
    build_confusion_matrix,
    get_per_type_stats,
    ERROR_TYPES,
)

# ===========================================================================
# SECTION 1, compute_cohens_kappa()
# ===========================================================================

class TestCohenKappaPerfectAgreement:
    """k = 1.0 when both raters agree on every item."""

    def test_perfect_agreement_all_same_label(self):
        """
        Worked example:
          human = ai = ["CF", "CF", "CF"]
          Po = 3/3 = 1.0
          Pe = (3/3 * 3/3) = 1.0  → guarded case → k = 1.0
        """
        human = ["CF", "CF", "CF"]
        ai    = ["CF", "CF", "CF"]
        result = compute_cohens_kappa(human, ai)
        assert result["kappa"] == 1.0

    def test_perfect_agreement_mixed_labels(self):
        """
        Worked example:
          human = ai = ["RF", "PK", "CF", "INT"]
          Po = 4/4 = 1.0
          Pe = (1/4)(1/4) × 4 categories = 4/16 = 0.25
          k = (1.0 - 0.25) / (1.0 - 0.25) = 0.75 / 0.75 = 1.0
        """
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["RF", "PK", "CF", "INT"]
        result = compute_cohens_kappa(human, ai)
        assert result["kappa"] == 1.0

    def test_perfect_agreement_large_balanced(self):
        human = ["RF", "PK", "CF", "INT"] * 10
        ai    = ["RF", "PK", "CF", "INT"] * 10
        result = compute_cohens_kappa(human, ai)
        assert result["kappa"] == 1.0


class TestCohenKappaKnownValues:
    """
    k computed against manual calculation for a specific input.
    These serve as regression tests: if the formula changes, these will fail.
    """

    def test_known_kappa_substantial(self):
        """
        Worked example (verified by hand):

          n = 10 items
          human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
          ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]

          Agreements (position-by-position):
            CF==CF, CF==CF, CF==CF, CF!=RF X,
            RF==RF, RF==RF, PK==PK, PK!=CF X,
            INT==INT, INT==INT
          Agreements = 8,  Po = 8/10 = 0.8

          Marginal counts:
            human: CF=4, RF=2, PK=2, INT=2
            ai:    CF=4, RF=3, PK=1, INT=2

          Pe = (4/10)(4/10) + (2/10)(3/10) + (2/10)(1/10) + (2/10)(2/10)
             = 0.16 + 0.06 + 0.02 + 0.04
             = 0.28

          k = (0.8 - 0.28) / (1.0 - 0.28)
            = 0.52 / 0.72
            = 0.7222...
            ~ 0.7222 (rounded to 4 d.p.)
        """
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]

        result = compute_cohens_kappa(human, ai)

        expected_kappa = round(0.52 / 0.72, 4)   # 0.7222
        assert abs(result["kappa"] - expected_kappa) < 0.0001, (
            f"Expected k ~ {expected_kappa}, got {result['kappa']}"
        )
        assert result["po"] == 0.8
        assert abs(result["pe"] - 0.28) < 0.0001
        assert result["n"] == 10
        assert result["agreements"] == 8

    def test_known_kappa_moderate(self):
        """
        Worked example:

          n = 8
          human = ["CF","CF","RF","RF","PK","PK","INT","INT"]
          ai    = ["CF","RF","RF","CF","PK","INT","INT","RF"]

          Agreements:
            CF==CF, CF!=RF X, RF==RF, RF!=CF X,
            PK==PK, PK!=INT X, INT==INT, INT!=RF X
          Agreements = 4, Po = 4/8 = 0.5

          Marginal counts:
            human: CF=2, RF=2, PK=2, INT=2  (each 2/8 = 0.25)
            ai:    CF=2, RF=3, PK=1, INT=2

          Pe = (2/8)(2/8) + (2/8)(3/8) + (2/8)(1/8) + (2/8)(2/8)
             = 4/64 + 6/64 + 2/64 + 4/64
             = 16/64 = 0.25

          k = (0.5 - 0.25) / (1.0 - 0.25)
            = 0.25 / 0.75
            = 0.3333...
        """
        human = ["CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","RF","RF","CF","PK","INT","INT","RF"]

        result = compute_cohens_kappa(human, ai)

        expected_kappa = round(0.25 / 0.75, 4)  # 0.3333
        assert abs(result["kappa"] - expected_kappa) < 0.0001
        assert result["po"] == 0.5
        assert abs(result["pe"] - 0.25) < 0.0001

    def test_known_kappa_below_chance(self):
        """
        When agreement is systematically below chance, k is negative.

          n = 4 (one item per category)
          human = ["RF", "PK", "CF", "INT"]
          ai    = ["PK", "CF", "INT", "RF"]   <- shifted by one, zero agreement

          Po = 0/4 = 0.0
          Pe = (1/4)(1/4) × 4 = 0.25
          k = (0.0 - 0.25) / (1.0 - 0.25) = -0.25 / 0.75 = -0.3333...
        """
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["PK", "CF", "INT", "RF"]

        result = compute_cohens_kappa(human, ai)

        expected_kappa = round(-0.25 / 0.75, 4)  # -0.3333
        assert abs(result["kappa"] - expected_kappa) < 0.0001
        assert result["agreements"] == 0
        assert result["po"] == 0.0


class TestCohenKappaEdgeCases:
    """Edge cases and boundary conditions."""

    def test_empty_input(self):
        """Empty lists → kappa=0.0, n=0, no crash."""
        result = compute_cohens_kappa([], [])
        assert result["kappa"] == 0.0
        assert result["n"] == 0

    def test_single_item_agreement(self):
        """Single item, both agree → k = 1.0 (pe = 1, guarded case)."""
        result = compute_cohens_kappa(["CF"], ["CF"])
        assert result["kappa"] == 1.0
        assert result["n"] == 1
        assert result["agreements"] == 1

    def test_single_item_disagreement(self):
        """
        Single item, disagree.
        human = ["CF"], ai = ["RF"]
        Po = 0.0
        Pe: human CF=1/1=1.0, RF=0; ai CF=0, RF=1/1=1.0
        Pe = (1.0)(0.0) + (0.0)(1.0) + ... = 0.0
        k = (0.0 - 0.0) / (1.0 - 0.0) = 0.0
        """
        result = compute_cohens_kappa(["CF"], ["RF"])
        assert result["kappa"] == 0.0
        assert result["agreements"] == 0

    def test_returns_all_required_keys(self):
        """Result dict must contain all required keys."""
        result = compute_cohens_kappa(["CF", "RF"], ["CF", "PK"])
        for key in ("kappa", "interpretation", "po", "pe", "n", "agreements"):
            assert key in result, f"Missing key: {key}"

    def test_kappa_bounded(self):
        """k should never exceed 1.0 for any valid input."""
        import random
        random.seed(42)
        for _ in range(50):
            n = random.randint(1, 20)
            human = [random.choice(ERROR_TYPES) for _ in range(n)]
            ai    = [random.choice(ERROR_TYPES) for _ in range(n)]
            result = compute_cohens_kappa(human, ai)
            assert result["kappa"] <= 1.0, (
                f"k exceeded 1.0: {result['kappa']} for human={human}, ai={ai}"
            )


class TestCohenKappaInterpretation:
    """Interpretation strings map correctly to kappa zones."""

    def _get_interp(self, kappa_val):
        """Helper: build minimal label arrays that produce a target kappa."""
        # We construct labels that give the desired approximate kappa
        # For interpretation tests, exact kappa doesn't matter, we need
        # to test that the interpretation string matches the zone.
        # Use the known-kappa test case and scale the agreement level.
        n = 100
        # We'll use a parameterised approach:
        # Force kappa by choosing Po to hit the zone, then verify interpretation.
        result = compute_cohens_kappa.__wrapped__ if hasattr(compute_cohens_kappa, '__wrapped__') else compute_cohens_kappa
        return None

    def test_above_threshold_contains_check(self):
        """k >= 0.70 interpretation should contain the checkmark."""
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]
        result = compute_cohens_kappa(human, ai)
        # k ~ 0.7222, should be "Substantial"
        assert "research threshold" in result["interpretation"].lower()

    def test_below_threshold_no_checkmark(self):
        """k < 0.70 interpretation should not contain the checkmark."""
        human = ["CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","RF","RF","CF","PK","INT","INT","RF"]
        result = compute_cohens_kappa(human, ai)
        # k ~ 0.3333, should be "Fair"
        assert "research threshold" not in result["interpretation"].lower()
        assert "fair" in result["interpretation"].lower()


# ===========================================================================
# SECTION 2, build_confusion_matrix()
# ===========================================================================

class TestBuildConfusionMatrix:
    """Tests for the 4×4 confusion matrix constructor."""

    def test_diagonal_on_perfect_agreement(self):
        """All agreements → only diagonal cells are non-zero."""
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["RF", "PK", "CF", "INT"]
        matrix = build_confusion_matrix(human, ai)

        for label in ERROR_TYPES:
            assert matrix[label][label] == 1, f"Diagonal cell {label}×{label} should be 1"
            for other in ERROR_TYPES:
                if other != label:
                    assert matrix[label][other] == 0

    def test_off_diagonal_on_total_disagreement(self):
        """Complete disagreement → only off-diagonal cells are non-zero."""
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["PK", "CF", "INT", "RF"]
        matrix = build_confusion_matrix(human, ai)

        for label in ERROR_TYPES:
            assert matrix[label][label] == 0, (
                f"Diagonal cell {label}×{label} should be 0 for total disagreement"
            )

    def test_specific_cell_counts(self):
        """
        Manually verify cell counts for a known input.

          human = ["CF","CF","RF"]
          ai    = ["CF","RF","RF"]

          Expected matrix:
            human\ai  RF  PK  CF  INT
            RF         1   0   0    0
            PK         0   0   0    0
            CF         1   0   1    0   <- CF→CF (agree) and CF→RF (disagree)
            INT        0   0   0    0
        """
        human  = ["CF", "CF", "RF"]
        ai     = ["CF", "RF", "RF"]
        matrix = build_confusion_matrix(human, ai)

        assert matrix["CF"]["CF"] == 1   # agreement
        assert matrix["CF"]["RF"] == 1   # CF labelled RF by AI
        assert matrix["RF"]["RF"] == 1   # agreement
        assert matrix["CF"]["PK"] == 0
        assert matrix["PK"]["PK"] == 0

    def test_matrix_covers_all_error_types(self):
        """All four error types appear as both row and column keys."""
        matrix = build_confusion_matrix(["RF"], ["RF"])
        for label in ERROR_TYPES:
            assert label in matrix, f"Row key {label} missing"
            assert label in matrix["RF"], f"Column key {label} missing"

    def test_matrix_total_count_equals_n(self):
        """Sum of all matrix cells equals number of rated items."""
        human = ["CF", "RF", "PK", "INT", "CF", "RF"]
        ai    = ["CF", "CF", "PK", "INT", "RF", "RF"]
        matrix = build_confusion_matrix(human, ai)
        total = sum(matrix[r][c] for r in ERROR_TYPES for c in ERROR_TYPES)
        assert total == len(human)


# ===========================================================================
# SECTION 3, get_per_type_stats()
# ===========================================================================

class TestGetPerTypeStats:
    """Tests for per-category agreement statistics."""

    def test_perfect_agreement_all_types(self):
        """All agreed → each type should show 100% agreement."""
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["RF", "PK", "CF", "INT"]
        stats = get_per_type_stats(human, ai)

        for label in ERROR_TYPES:
            assert stats[label]["pct"] == 100
            assert stats[label]["agreed"] == stats[label]["total"]

    def test_zero_agreement_all_types(self):
        """No agreement → 0% for all types present."""
        human = ["RF", "PK", "CF", "INT"]
        ai    = ["PK", "CF", "INT", "RF"]
        stats = get_per_type_stats(human, ai)

        for label in ERROR_TYPES:
            assert stats[label]["pct"] == 0
            assert stats[label]["agreed"] == 0

    def test_absent_type_returns_zero_total(self):
        """A type with no human labels should have total=0, pct=0."""
        human = ["RF", "RF", "RF"]   # no PK, CF, INT
        ai    = ["RF", "RF", "PK"]
        stats = get_per_type_stats(human, ai)

        assert stats["PK"]["total"] == 0
        assert stats["CF"]["total"] == 0
        assert stats["INT"]["total"] == 0

    def test_partial_agreement_specific_type(self):
        """
        Manually verified case:
          human = ["CF","CF","CF","CF"]
          ai    = ["CF","CF","RF","RF"]
          CF agreement: 2/4 = 50%
        """
        human = ["CF", "CF", "CF", "CF"]
        ai    = ["CF", "CF", "RF", "RF"]
        stats = get_per_type_stats(human, ai)

        assert stats["CF"]["total"] == 4
        assert stats["CF"]["agreed"] == 2
        assert stats["CF"]["pct"] == 50

    def test_all_types_present_in_output(self):
        """Output dict always contains all four error type keys."""
        stats = get_per_type_stats(["RF"], ["RF"])
        for label in ERROR_TYPES:
            assert label in stats


# ===========================================================================
# SECTION 4, Integration: kappa + matrix + stats are consistent
# ===========================================================================

class TestConsistencyAcrossFunctions:
    """Verify that the three core functions give mutually consistent results."""

    def test_kappa_agreements_matches_matrix_diagonal(self):
        """
        The 'agreements' count from kappa computation should equal
        the sum of diagonal cells in the confusion matrix.
        """
        human = ["CF","CF","RF","RF","PK","INT","CF","RF","INT","PK"]
        ai    = ["CF","RF","RF","CF","PK","INT","CF","RF","PK","PK"]

        kappa_result = compute_cohens_kappa(human, ai)
        matrix       = build_confusion_matrix(human, ai)

        diagonal_sum = sum(matrix[label][label] for label in ERROR_TYPES)
        assert kappa_result["agreements"] == diagonal_sum

    def test_per_type_total_sums_to_n(self):
        """Sum of per-type totals equals the number of human labels."""
        human = ["CF","CF","RF","RF","PK","INT","CF","RF","INT","PK"]
        ai    = ["CF","RF","RF","CF","PK","INT","CF","RF","PK","PK"]

        stats = get_per_type_stats(human, ai)
        total_from_stats = sum(stats[label]["total"] for label in ERROR_TYPES)
        assert total_from_stats == len(human)


# ===========================================================================
# SECTION 5, Mathematical properties and additional boundary conditions
# ===========================================================================

class TestAdditionalProperties:
    """
    Property-based and boundary tests that verify mathematical invariants
    rather than specific known outputs. Each test documents the invariant
    it encodes so failures are self-explanatory.
    """

    def test_kappa_is_symmetric(self):
        """
        Cohen's k is symmetric: k(h, ai) == k(ai, h).

        Proof sketch:
          Po = agreements/n is unchanged by swapping the two lists.
          Pe = Σ_k p_h_k × p_ai_k = Σ_k p_ai_k × p_h_k  (multiplication is commutative).
          Therefore k = (Po - Pe)/(1 - Pe) is identical in both directions.
        """
        human = ["CF", "CF", "RF", "RF", "PK", "INT", "CF", "RF", "INT", "PK"]
        ai    = ["CF", "RF", "RF", "CF", "PK", "INT", "CF", "RF", "PK",  "PK"]

        kappa_h_ai = compute_cohens_kappa(human, ai)["kappa"]
        kappa_ai_h = compute_cohens_kappa(ai, human)["kappa"]

        assert abs(kappa_h_ai - kappa_ai_h) < 1e-9, (
            f"k not symmetric: k(h,ai)={kappa_h_ai:.6f}, k(ai,h)={kappa_ai_h:.6f}"
        )

    def test_kappa_reproducibility(self):
        """
        Same input must always produce identical output.
        The implementation is deterministic (no randomness, no mutable state).
        """
        human = ["CF", "RF", "PK", "INT", "CF", "RF"]
        ai    = ["CF", "CF", "PK", "INT", "RF", "RF"]

        result_1 = compute_cohens_kappa(human, ai)
        result_2 = compute_cohens_kappa(human, ai)

        assert result_1 == result_2

    def test_pe_guard_all_same_category_both_raters(self):
        """
        When both raters unanimously choose the same single category,
        Pe = (n/n)(n/n) = 1.0.

        The Pe = 1.0 guard should return k = 1.0 because Po = 1.0 too.

        Without the guard, the formula yields 0/0 (division by zero).
        Correct convention: unanimous perfect agreement → k = 1.0.
        """
        human = ["RF"] * 8
        ai    = ["RF"] * 8
        result = compute_cohens_kappa(human, ai)

        assert result["kappa"] == 1.0, (
            f"Pe=1.0 guard failed: got k={result['kappa']}"
        )
        assert result["agreements"] == 8

    def test_large_n_does_not_crash_and_stays_bounded(self):
        """
        k computation on n = 1 000 items should complete without error
        and return a value in [-1, 1].
        """
        import random
        random.seed(99)
        n = 1000
        human = [random.choice(ERROR_TYPES) for _ in range(n)]
        ai    = [random.choice(ERROR_TYPES) for _ in range(n)]

        result = compute_cohens_kappa(human, ai)

        assert result["n"] == n
        assert -1.0 <= result["kappa"] <= 1.0

    def test_matrix_row_sums_equal_human_label_counts(self):
        """
        For every error type t, sum of matrix[t][*] == count of t in human labels.

        Invariant: each row of the confusion matrix counts how many times
        the *human* assigned that label, regardless of what the AI assigned.
        """
        from collections import Counter
        human = ["CF", "CF", "RF", "PK", "CF", "INT", "RF", "PK"]
        ai    = ["CF", "RF", "RF", "PK", "INT", "INT", "CF", "PK"]
        matrix       = build_confusion_matrix(human, ai)
        human_counts = Counter(human)

        for label in ERROR_TYPES:
            row_sum  = sum(matrix[label][col] for col in ERROR_TYPES)
            expected = human_counts.get(label, 0)
            assert row_sum == expected, (
                f"Row '{label}' sums to {row_sum}, expected {expected}"
            )

    def test_matrix_col_sums_equal_ai_label_counts(self):
        """
        For every error type t, sum of matrix[*][t] == count of t in AI labels.

        Invariant: each column of the confusion matrix counts how many times
        the *AI* assigned that label, regardless of what the human assigned.
        """
        from collections import Counter
        human = ["CF", "CF", "RF", "PK", "CF", "INT", "RF", "PK"]
        ai    = ["CF", "RF", "RF", "PK", "INT", "INT", "CF", "PK"]
        matrix    = build_confusion_matrix(human, ai)
        ai_counts = Counter(ai)

        for label in ERROR_TYPES:
            col_sum  = sum(matrix[row][label] for row in ERROR_TYPES)
            expected = ai_counts.get(label, 0)
            assert col_sum == expected, (
                f"Column '{label}' sums to {col_sum}, expected {expected}"
            )

    def test_per_type_agreed_never_exceeds_total(self):
        """
        For every error type, agreed ≤ total.

        Violated only if a rater were credited with an agreement on an item
        they did not actually label, a structural impossibility that this
        test guards against across randomised inputs.
        """
        import random
        random.seed(77)
        human = [random.choice(ERROR_TYPES) for _ in range(50)]
        ai    = [random.choice(ERROR_TYPES) for _ in range(50)]
        stats = get_per_type_stats(human, ai)

        for label in ERROR_TYPES:
            assert stats[label]["agreed"] <= stats[label]["total"], (
                f"{label}: agreed={stats[label]['agreed']} "
                f"> total={stats[label]['total']}"
            )

    def test_n_field_matches_input_length_across_sizes(self):
        """
        The 'n' field returned by compute_cohens_kappa must equal
        len(human) == len(ai) for all non-trivial input sizes.
        """
        for length in [2, 5, 20, 100]:
            human = (ERROR_TYPES * (length // 4 + 1))[:length]
            ai    = (ERROR_TYPES[::-1] * (length // 4 + 1))[:length]
            result = compute_cohens_kappa(human, ai)
            assert result["n"] == length, (
                f"n field={result['n']} but input length={length}"
            )
