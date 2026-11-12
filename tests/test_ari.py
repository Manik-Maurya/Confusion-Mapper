"""
test_ari.py - pytest suite for benchmarks/ari.py's adjusted_rand_index().

New in v2.6.0. The hand-derived example here is the same one reported in
benchmarks/EMBEDDING_VALIDATION_FINDINGS.md and asserted in ari.py's own
__main__ block, checked independently a third time here so the real
empirical study's numbers rest on a triply-verified implementation, not
a single self-check.

Run with: pytest tests/test_ari.py -v
"""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "benchmarks"))

from ari import adjusted_rand_index, _comb2


class TestComb2:
    def test_known_values(self):
        assert _comb2(0) == 0
        assert _comb2(1) == 0
        assert _comb2(2) == 1
        assert _comb2(3) == 3
        assert _comb2(4) == 6
        assert _comb2(5) == 10


class TestAdjustedRandIndex:
    def test_hand_derived_example(self):
        """
        true = [0,0,0,1,1,1], pred = [0,0,1,1,2,2].
        Contingency table (rows=pred cluster, cols=true label):
            pred0: true0=2, true1=0  -> a=2
            pred1: true0=1, true1=1  -> a=2
            pred2: true0=0, true1=2  -> a=2
            col totals: b0=3, b1=3, n=6
        index = C(2,2)+C(0,2)+C(1,2)+C(1,2)+C(0,2)+C(2,2) = 1+0+0+0+0+1 = 2
        sum_a = 3*C(2,2) = 3, sum_b = 2*C(3,2) = 6, C(n,2) = 15
        expected = (3*6)/15 = 1.2, max = 0.5*(3+6) = 4.5
        ARI = (2-1.2)/(4.5-1.2) = 0.8/3.3 = 0.242424...
        """
        result = adjusted_rand_index([0, 0, 0, 1, 1, 1], [0, 0, 1, 1, 2, 2])
        assert result == pytest.approx(0.242424242424, abs=1e-9)

    def test_identical_partitions_give_one(self):
        assert adjusted_rand_index([0, 0, 1, 1, 2, 2], [0, 0, 1, 1, 2, 2]) == pytest.approx(1.0)

    def test_identical_partitions_with_different_label_names_still_give_one(self):
        """ARI compares partition structure, not label identity."""
        true = ["a", "a", "b", "b", "c", "c"]
        pred = [7, 7, 3, 3, 9, 9]
        assert adjusted_rand_index(true, pred) == pytest.approx(1.0)

    def test_single_cluster_for_everything_gives_zero(self):
        """Putting every item in one cluster provides no information --
        chance-level agreement, ARI = 0."""
        result = adjusted_rand_index([0, 0, 1, 1, 2, 2], [0, 0, 0, 0, 0, 0])
        assert result == pytest.approx(0.0, abs=1e-9)

    def test_every_item_its_own_singleton_gives_zero(self):
        true = [0, 0, 1, 1, 2, 2]
        pred = [0, 1, 2, 3, 4, 5]
        assert adjusted_rand_index(true, pred) == pytest.approx(0.0, abs=1e-9)

    def test_empty_input_gives_zero_not_a_crash(self):
        assert adjusted_rand_index([], []) == 0.0

    def test_symmetric_in_its_two_arguments(self):
        true = [0, 0, 1, 1, 2, 2]
        pred = [0, 0, 1, 2, 2, 1]
        assert adjusted_rand_index(true, pred) == pytest.approx(adjusted_rand_index(pred, true))

    def test_bounded_above_by_one(self):
        import random
        random.seed(42)
        for _ in range(20):
            n = random.randint(2, 30)
            true = [random.randint(0, 3) for _ in range(n)]
            pred = [random.randint(0, 3) for _ in range(n)]
            assert adjusted_rand_index(true, pred) <= 1.0 + 1e-9

    def test_mismatched_length_raises(self):
        with pytest.raises(AssertionError):
            adjusted_rand_index([0, 1], [0, 1, 2])
