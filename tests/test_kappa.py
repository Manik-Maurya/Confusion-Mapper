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


# ===========================================================================
# SECTION 6 - Weighted kappa (linear / quadratic)
# ===========================================================================

class TestWeightedKappa:
    """
    Weighted kappa supports ordinal taxonomies. With nominal weights, every
    disagreement counts equally. Linear weights penalise adjacent-category
    disagreements less than far-apart ones; quadratic weights penalise far
    disagreements even more strongly.
    """

    def test_nominal_default_matches_legacy(self):
        """Default weights="nominal" reproduces the original Cohen 1960 kappa."""
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]
        r_default = compute_cohens_kappa(human, ai)
        r_nominal = compute_cohens_kappa(human, ai, weights="nominal")
        assert r_default["kappa"] == r_nominal["kappa"]
        assert abs(r_default["kappa"] - 0.7222) < 0.0001

    def test_linear_weights_geq_nominal_on_adjacent_disagreements(self):
        """
        When disagreements are between adjacent ordinal categories, linear
        weights yield kappa >= nominal kappa (adjacent disagreements count less).
        """
        # All "errors" are between adjacent categories (RF<->PK and CF<->INT)
        human = ["RF","RF","RF","PK","PK","CF","CF","INT","INT","INT"]
        ai    = ["PK","RF","RF","RF","PK","INT","CF","CF","INT","INT"]
        r_nominal = compute_cohens_kappa(human, ai, weights="nominal")
        r_linear  = compute_cohens_kappa(human, ai, weights="linear")
        assert r_linear["kappa"] >= r_nominal["kappa"]

    def test_quadratic_geq_linear_on_adjacent_disagreements(self):
        """Quadratic weights penalise adjacent disagreements even less than linear."""
        human = ["RF","RF","PK","PK","CF","CF","INT","INT"]
        ai    = ["PK","RF","RF","PK","INT","CF","CF","INT"]
        r_lin = compute_cohens_kappa(human, ai, weights="linear")
        r_qua = compute_cohens_kappa(human, ai, weights="quadratic")
        assert r_qua["kappa"] >= r_lin["kappa"]

    def test_perfect_agreement_all_weights_equal_one(self):
        """Perfect agreement returns kappa=1.0 under every weighting."""
        human = ai = ["RF","PK","CF","INT"] * 5
        for w in ("nominal", "linear", "quadratic"):
            assert compute_cohens_kappa(human, ai, weights=w)["kappa"] == 1.0

    def test_invalid_weights_raises(self):
        """Unknown weight schemes raise a ValueError."""
        with pytest.raises(ValueError):
            compute_cohens_kappa(["RF"], ["RF"], weights="cubic")

    def test_weighted_result_includes_weights_field(self):
        """Result dict surfaces which weighting scheme was used."""
        r = compute_cohens_kappa(["RF","PK"], ["RF","CF"], weights="linear")
        assert r["weights"] == "linear"


# ===========================================================================
# SECTION 7 - Bootstrap confidence intervals for kappa
# ===========================================================================

class TestBootstrapKappaCI:
    """
    Cohen's kappa is a point estimate. Research use needs uncertainty around
    that point. bootstrap_kappa_ci resamples paired labels with replacement
    and returns a percentile or BCa confidence interval.
    """

    def test_ci_contains_point_estimate(self):
        """The CI should bracket the point estimate."""
        from confusion_mapper import bootstrap_kappa_ci
        human = ["CF","CF","CF","RF","RF","PK","PK","INT","INT","CF"]
        ai    = ["CF","CF","RF","RF","PK","PK","CF","INT","INT","CF"]
        ci = bootstrap_kappa_ci(human, ai, n_resamples=500, method="percentile", seed=42)
        assert ci["ci_lower"] <= ci["point_estimate"] <= ci["ci_upper"]

    def test_bca_ci_contains_point_estimate(self):
        """BCa CI should also bracket the point estimate."""
        from confusion_mapper import bootstrap_kappa_ci
        human = ["CF","CF","CF","RF","RF","PK","PK","INT","INT","CF"]
        ai    = ["CF","CF","RF","RF","PK","PK","CF","INT","INT","CF"]
        ci = bootstrap_kappa_ci(human, ai, n_resamples=500, method="bca", seed=42)
        assert ci["ci_lower"] <= ci["point_estimate"] <= ci["ci_upper"]

    def test_seed_reproducibility(self):
        """Same seed must yield identical CI on the same input."""
        from confusion_mapper import bootstrap_kappa_ci
        h = ["CF","RF","PK","INT","CF","RF","PK","INT"]
        a = ["CF","CF","PK","INT","RF","RF","PK","CF"]
        ci1 = bootstrap_kappa_ci(h, a, n_resamples=300, seed=7)
        ci2 = bootstrap_kappa_ci(h, a, n_resamples=300, seed=7)
        assert ci1 == ci2

    def test_different_seeds_can_differ(self):
        """Different seeds usually give different CIs (sanity check)."""
        from confusion_mapper import bootstrap_kappa_ci
        h = ["CF","RF","PK","INT","CF","RF","PK","INT","CF","RF"]
        a = ["CF","CF","PK","INT","RF","RF","PK","CF","RF","CF"]
        ci_a = bootstrap_kappa_ci(h, a, n_resamples=300, seed=1)
        ci_b = bootstrap_kappa_ci(h, a, n_resamples=300, seed=2)
        # They will not be guaranteed different, but with 300 resamples the
        # endpoints almost always shift by at least one index. Allow either.
        assert isinstance(ci_a["ci_lower"], float)
        assert isinstance(ci_b["ci_lower"], float)

    def test_perfect_agreement_ci_collapses_to_one(self):
        """When kappa=1 and there is no resampling variance, CI is degenerate."""
        from confusion_mapper import bootstrap_kappa_ci
        human = ai = ["RF","PK","CF","INT","RF","PK","CF","INT"]
        ci = bootstrap_kappa_ci(human, ai, n_resamples=200, method="percentile", seed=1)
        assert ci["point_estimate"] == 1.0
        assert ci["ci_upper"] == 1.0

    def test_ci_metadata(self):
        """Result dict carries the confidence level, method, and resample count."""
        from confusion_mapper import bootstrap_kappa_ci
        h = ["CF","RF","PK","INT"] * 5
        a = ["CF","CF","PK","INT"] * 5
        ci = bootstrap_kappa_ci(h, a, n_resamples=200, confidence=0.9,
                                method="percentile", seed=1)
        assert ci["confidence"] == 0.9
        assert ci["method"] == "percentile"
        assert ci["n_resamples"] == 200

    def test_invalid_method_raises(self):
        """Unknown CI methods raise a ValueError."""
        from confusion_mapper import bootstrap_kappa_ci
        with pytest.raises(ValueError):
            bootstrap_kappa_ci(["RF","PK"], ["RF","CF"], method="unknown", seed=1)

    def test_invalid_confidence_raises(self):
        """confidence must be strictly between 0 and 1."""
        from confusion_mapper import bootstrap_kappa_ci
        with pytest.raises(ValueError):
            bootstrap_kappa_ci(["RF","PK"], ["RF","CF"], confidence=0.0, seed=1)
        with pytest.raises(ValueError):
            bootstrap_kappa_ci(["RF","PK"], ["RF","CF"], confidence=1.0, seed=1)

    def test_mismatched_lengths_raises(self):
        """Length mismatch is rejected before any sampling happens."""
        from confusion_mapper import bootstrap_kappa_ci
        with pytest.raises(ValueError):
            bootstrap_kappa_ci(["RF","PK"], ["RF"], seed=1)


# ===========================================================================
# SECTION 8 - Custom taxonomy loading
# ===========================================================================

class TestLoadTaxonomy:
    """A custom JSON taxonomy can replace the built-in CFI categories."""

    def test_loads_valid_taxonomy(self, tmp_path):
        from confusion_mapper import load_taxonomy_from_json
        import json
        p = tmp_path / "tax.json"
        p.write_text(json.dumps({"labels": [
            {"code": "A", "name": "Alpha", "definition": "first"},
            {"code": "B", "name": "Beta",  "definition": "second"},
        ]}), encoding="utf-8")
        codes, tax = load_taxonomy_from_json(str(p))
        assert codes == ["A", "B"]
        assert tax["A"]["name"] == "Alpha"
        assert tax["B"]["definition"] == "second"

    def test_rejects_duplicate_codes(self, tmp_path):
        from confusion_mapper import load_taxonomy_from_json
        import json
        p = tmp_path / "tax.json"
        p.write_text(json.dumps({"labels": [
            {"code": "A", "name": "x", "definition": "y"},
            {"code": "A", "name": "z", "definition": "w"},
        ]}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_taxonomy_from_json(str(p))

    def test_rejects_too_few_labels(self, tmp_path):
        from confusion_mapper import load_taxonomy_from_json
        import json
        p = tmp_path / "tax.json"
        p.write_text(json.dumps({"labels": [
            {"code": "A", "name": "x", "definition": "y"},
        ]}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_taxonomy_from_json(str(p))

    def test_rejects_missing_required_keys(self, tmp_path):
        from confusion_mapper import load_taxonomy_from_json
        import json
        p = tmp_path / "tax.json"
        p.write_text(json.dumps({"labels": [
            {"code": "A", "name": "x"},  # missing definition
            {"code": "B", "name": "y", "definition": "z"},
        ]}), encoding="utf-8")
        with pytest.raises(ValueError):
            load_taxonomy_from_json(str(p))

    def test_supplies_defaults_for_optional_fields(self, tmp_path):
        from confusion_mapper import load_taxonomy_from_json
        import json
        p = tmp_path / "tax.json"
        p.write_text(json.dumps({"labels": [
            {"code": "A", "name": "x", "definition": "y"},
            {"code": "B", "name": "z", "definition": "w"},
        ]}), encoding="utf-8")
        codes, tax = load_taxonomy_from_json(str(p))
        assert "color" in tax["A"] and "example" in tax["A"]

    def test_kappa_works_with_custom_categories(self):
        """Kappa and confusion matrix accept a categories list."""
        cats = ["A", "B", "C"]
        h = ["A","A","B","B","C","C"]
        a = ["A","B","B","B","C","A"]
        r = compute_cohens_kappa(h, a, categories=cats)
        assert r["n"] == 6
        m = build_confusion_matrix(h, a, categories=cats)
        assert set(m.keys()) == set(cats)
        s = get_per_type_stats(h, a, categories=cats)
        assert set(s.keys()) == set(cats)

    def test_bundled_example_loads(self):
        """The shipped sample_data/custom_taxonomy.json file is valid."""
        import os
        from confusion_mapper import load_taxonomy_from_json
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(repo_root, "sample_data", "custom_taxonomy.json")
        codes, tax = load_taxonomy_from_json(path)
        assert len(codes) >= 2
        assert all("definition" in tax[c] for c in codes)


# ===========================================================================
# SECTION 9 - compute_kappa_diagnostics (PABAK + bias + prevalence)
# ===========================================================================

class TestKappaDiagnostics:
    """PABAK, bias index, prevalence index alongside nominal kappa."""

    def test_returns_all_expected_keys(self):
        from confusion_mapper import compute_kappa_diagnostics
        d = compute_kappa_diagnostics(["RF","PK"], ["RF","CF"])
        for key in ("kappa", "pabak", "bias_index", "prevalence_index", "po"):
            assert key in d

    def test_pabak_equals_2po_minus_1(self):
        """PABAK is mathematically 2 * Po - 1."""
        from confusion_mapper import compute_kappa_diagnostics
        h = ["CF","CF","RF","RF","PK","PK","INT","INT"]
        a = ["CF","CF","RF","CF","PK","PK","INT","INT"]
        d = compute_kappa_diagnostics(h, a)
        assert abs(d["pabak"] - (2 * d["po"] - 1)) < 1e-4

    def test_zero_bias_when_marginals_match(self):
        """When both raters use categories at identical rates, bias is 0."""
        from confusion_mapper import compute_kappa_diagnostics
        h = ["RF","PK","CF","INT","RF","PK","CF","INT"]
        a = ["RF","PK","CF","INT","PK","RF","INT","CF"]
        d = compute_kappa_diagnostics(h, a)
        assert d["bias_index"] == 0.0

    def test_high_prevalence_on_skewed_marginals(self):
        """When most agreements concentrate in one cell, prevalence is high."""
        from confusion_mapper import compute_kappa_diagnostics
        h = ["RF"] * 18 + ["PK", "CF"]
        a = ["RF"] * 18 + ["PK", "CF"]
        d = compute_kappa_diagnostics(h, a)
        assert d["prevalence_index"] > 0.5

    def test_pabak_exceeds_kappa_on_kappa_paradox_input(self):
        """The classic kappa paradox: high Po but low kappa due to skew."""
        from confusion_mapper import compute_kappa_diagnostics
        # 80% agreement but extreme skew - kappa underestimates agreement
        h = ["RF"] * 16 + ["PK"] * 2 + ["CF","INT"]
        a = ["RF"] * 16 + ["RF"] * 2 + ["CF","INT"]
        d = compute_kappa_diagnostics(h, a)
        assert d["pabak"] > d["kappa"]  # PABAK is higher when paradox bites


# ===========================================================================
# SECTION 10 - Krippendorff's alpha
# ===========================================================================

class TestKrippendorffAlpha:
    """Alternative IRR coefficient, supports nominal / ordinal / interval."""

    def test_perfect_agreement(self):
        from confusion_mapper import krippendorff_alpha
        a = krippendorff_alpha(["RF","PK","CF","INT"]*4, ["RF","PK","CF","INT"]*4)
        assert a["alpha"] == 1.0

    def test_alpha_in_valid_range(self):
        from confusion_mapper import krippendorff_alpha
        h = ["CF","CF","RF","PK","INT","CF","RF","PK"]
        a = ["CF","RF","RF","PK","INT","PK","CF","PK"]
        for level in ("nominal", "ordinal", "interval"):
            r = krippendorff_alpha(h, a, level=level)
            assert -1.0 <= r["alpha"] <= 1.0

    def test_ordinal_geq_nominal_on_adjacent_disagreements(self):
        """Ordinal alpha is higher than nominal when disagreements are adjacent."""
        from confusion_mapper import krippendorff_alpha
        h = ["RF","RF","PK","PK","CF","CF","INT","INT"]
        a = ["PK","RF","RF","PK","INT","CF","CF","INT"]
        nom = krippendorff_alpha(h, a, level="nominal")["alpha"]
        ord_ = krippendorff_alpha(h, a, level="ordinal")["alpha"]
        assert ord_ >= nom

    def test_invalid_level_raises(self):
        from confusion_mapper import krippendorff_alpha
        with pytest.raises(ValueError):
            krippendorff_alpha(["RF"], ["RF"], level="bogus")

    def test_unknown_label_raises(self):
        from confusion_mapper import krippendorff_alpha
        with pytest.raises(ValueError):
            krippendorff_alpha(["X"], ["RF"])

    def test_empty_input_safe(self):
        from confusion_mapper import krippendorff_alpha
        r = krippendorff_alpha([], [])
        assert r["alpha"] == 0.0
        assert r["n"] == 0


# ===========================================================================
# SECTION 11 - Sample-size estimator (power analysis)
# ===========================================================================

class TestRecommendSampleSize:
    """Plan how many items a calibration set needs for a given CI width."""

    def test_tighter_ci_requires_more_items(self):
        from confusion_mapper import recommend_sample_size
        loose = recommend_sample_size(0.75, ci_half_width=0.10)
        tight = recommend_sample_size(0.75, ci_half_width=0.05)
        assert tight["recommended_n"] > loose["recommended_n"]

    def test_returns_integer_at_least_one(self):
        from confusion_mapper import recommend_sample_size
        r = recommend_sample_size(0.80, ci_half_width=0.10)
        assert isinstance(r["recommended_n"], int)
        assert r["recommended_n"] >= 1

    def test_metadata_round_trip(self):
        from confusion_mapper import recommend_sample_size
        r = recommend_sample_size(0.70, ci_half_width=0.08, n_categories=5, confidence=0.95)
        assert r["expected_kappa"] == 0.70
        assert r["ci_half_width"] == 0.08
        assert r["n_categories"] == 5
        assert r["confidence"] == 0.95

    def test_invalid_inputs_raise(self):
        from confusion_mapper import recommend_sample_size
        with pytest.raises(ValueError):
            recommend_sample_size(0.5, ci_half_width=0.0)
        with pytest.raises(ValueError):
            recommend_sample_size(0.5, ci_half_width=1.0)
        with pytest.raises(ValueError):
            recommend_sample_size(0.5, n_categories=1)
        with pytest.raises(ValueError):
            recommend_sample_size(2.0)
        with pytest.raises(ValueError):
            recommend_sample_size(0.5, confidence=0.0)


# ===========================================================================
# SECTION 12 - Module surface
# ===========================================================================

class TestModuleSurface:
    """Public API surface checks."""

    def test_version_string_exposed(self):
        import confusion_mapper as cm
        assert hasattr(cm, "__version__")
        assert isinstance(cm.__version__, str)
        # SemVer X.Y.Z shape
        parts = cm.__version__.split(".")
        assert len(parts) == 3 and all(p.isdigit() for p in parts)

    def test_public_functions_importable(self):
        from confusion_mapper import (
            compute_cohens_kappa,
            build_confusion_matrix,
            get_per_type_stats,
            bootstrap_kappa_ci,
            load_taxonomy_from_json,
            compute_kappa_diagnostics,
            krippendorff_alpha,
            recommend_sample_size,
            ERROR_TYPES,
            TAXONOMY,
        )
        assert callable(compute_cohens_kappa)
        assert callable(krippendorff_alpha)
