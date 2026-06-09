"""
test_kappa.py — pytest test suite for ConfusionMapper core functions

Tests cover:
  - compute_cohens_kappa()   : κ formula, edge cases, interpretation thresholds
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
# Import path setup — works whether tests/ is run from repo root or directly
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import (
    compute_cohens_kappa,
    build_confusion_matrix,
    get_per_type_stats,
    ERROR_TYPES,
)

# ===========================================================================
# SECTION 1 — compute_cohens_kappa()
# ===========================================================================

class TestCohenKappaPerfectAgreement:
    """κ = 1.0 when both raters agree on every item."""

    def test_perfect_agreement_all_same_label(self):
        """
        Worked example:
          human = ai = ["CF", "CF", "CF"]
          Po = 3/3 = 1.0
          Pe = (3/3 * 3/3) = 1.0  → guarded case → κ = 1.0
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
          κ = (1.0 − 0.25) / (1.0 − 0.25) = 0.75 / 0.75 = 1.0
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
    κ computed against manual calculation for a specific input.
    These serve as regression tests: if the formula changes, these will fail.
    """

    def test_known_kappa_substantial(self):
        """
        Worked example (verified by hand):

          n = 10 items
          human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
          ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]

          Agreements (position-by-position):
            CF==CF ✓, CF==CF ✓, CF==CF ✓, CF≠RF ✗,
            RF==RF ✓, RF==RF ✓, PK==PK ✓, PK≠CF ✗,
            INT==INT ✓, INT==INT ✓
          Agreements = 8,  Po = 8/10 = 0.8

          Marginal counts:
            human: CF=4, RF=2, PK=2, INT=2
            ai:    CF=4, RF=3, PK=1, INT=2

          Pe = (4/10)(4/10) + (2/10)(3/10) + (2/10)(1/10) + (2/10)(2/10)
             = 0.16 + 0.06 + 0.02 + 0.04
             = 0.28

          κ = (0.8 − 0.28) / (1.0 − 0.28)
            = 0.52 / 0.72
            = 0.7222...
            ≈ 0.7222 (rounded to 4 d.p.)
        """
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]

        result = compute_cohens_kappa(human, ai)

        expected_kappa = round(0.52 / 0.72, 4)   # 0.7222
        assert abs(result["kappa"] - expected_kappa) < 0.0001, (
            f"Expected κ ≈ {expected_kappa}, got {result['kappa']}"
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
            CF==CF ✓, CF≠RF ✗, RF==RF ✓, RF≠CF ✗,
            PK==PK ✓, PK≠INT ✗, INT==INT ✓, INT≠RF ✗
          Agreements = 4, Po = 4/8 = 0.5

          Marginal counts:
            human: CF=2, RF=2, PK=2, INT=2  (each 2/8 = 0.25)
            ai:    CF=2, RF=3, PK=1, INT=2

          Pe = (2/8)(2/8) + (2/8)(3/8) + (2/8)(1/8) + (2/8)(2/8)
             = 4/64 + 6/64 + 2/64 + 4/64
             = 16/64 = 0.25

          κ = (0.5 − 0.25) / (1.0 − 0.25)
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
        When agreement is systematically below chance, κ is negative.

          n = 4 (one item per category)
          human = ["RF", "PK", "CF", "INT"]
          ai    = ["PK", "CF", "INT", "RF"]   ← shifted by one, zero agreement

          Po = 0/4 = 0.0
          Pe = (1/4)(1/4) × 4 = 0.25
          κ = (0.0 − 0.25) / (1.0 − 0.25) = −0.25 / 0.75 = −0.3333...
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
        """Single item, both agree → κ = 1.0 (pe = 1, guarded case)."""
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
        κ = (0.0 − 0.0) / (1.0 − 0.0) = 0.0
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
        """κ should never exceed 1.0 for any valid input."""
        import random
        random.seed(42)
        for _ in range(50):
            n = random.randint(1, 20)
            human = [random.choice(ERROR_TYPES) for _ in range(n)]
            ai    = [random.choice(ERROR_TYPES) for _ in range(n)]
            result = compute_cohens_kappa(human, ai)
            assert result["kappa"] <= 1.0, (
                f"κ exceeded 1.0: {result['kappa']} for human={human}, ai={ai}"
            )


class TestCohenKappaInterpretation:
    """Interpretation strings map correctly to kappa zones."""

    def _get_interp(self, kappa_val):
        """Helper: build minimal label arrays that produce a target kappa."""
        # We construct labels that give the desired approximate kappa
        # For interpretation tests, exact kappa doesn't matter — we need
        # to test that the interpretation string matches the zone.
        # Use the known-kappa test case and scale the agreement level.
        n = 100
        # We'll use a parameterised approach:
        # Force kappa by choosing Po to hit the zone, then verify interpretation.
        result = compute_cohens_kappa.__wrapped__ if hasattr(compute_cohens_kappa, '__wrapped__') else compute_cohens_kappa
        return None

    def test_above_threshold_contains_check(self):
        """κ ≥ 0.70 interpretation should contain the checkmark."""
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]
        result = compute_cohens_kappa(human, ai)
        # κ ≈ 0.7222 — should be "Substantial ✓"
        assert "✓" in result["interpretation"]

    def test_below_threshold_no_checkmark(self):
        """κ < 0.70 interpretation should not contain the checkmark."""
        human = ["CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","RF","RF","CF","PK","INT","INT","RF"]
        result = compute_cohens_kappa(human, ai)
        # κ ≈ 0.3333 — should be "Fair"
        assert "✓" not in result["interpretation"]


# ===========================================================================
# SECTION 2 — build_confusion_matrix()
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
            CF         1   0   1    0   ← CF→CF (agree) and CF→RF (disagree)
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
# SECTION 3 — get_per_type_stats()
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
# SECTION 4 — Integration: kappa + matrix + stats are consistent
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
