"""
test_patterns.py - pytest suite for confusion_mapper.patterns (pattern
mining: co-occurrence, transitions, temporal trend, cohort comparison).

New in v2.6.0. TestChiSquarePAccuracy locks in the empirical accuracy
check against the standard chi-square critical-value table, if the
Wilson-Hilferty approximation in _chi_square_p ever regresses, this is
where it would show up. Every other worked-example value below (the 2x2
chi-square example, the lift example) was independently hand-derived in
comments and then verified against the actual function output before
being written as an assertion, not the other way around.

Run with: pytest tests/test_patterns.py -v
"""

import sys
import os
import csv
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.patterns import (
    load_longitudinal_csv,
    chi_square_test,
    _chi_square_p,
    co_occurrence_summary,
    item_pair_cooccurrence,
    transition_matrix,
    mine_transition_patterns,
    temporal_trend,
    cohort_comparison,
)


def _rec(respondent_id, item_id, label, timepoint="", cohort=""):
    return {"respondent_id": respondent_id, "item_id": item_id, "label": label,
           "timepoint": timepoint, "cohort": cohort}


class TestChiSquarePAccuracy:
    """
    Standard chi-square critical-value table (any statistics textbook):
    (df, critical_value_at_alpha, alpha). _chi_square_p(critical_value, df)
    should recover approximately alpha.
    """

    KNOWN_CRITICAL_VALUES = [
        (1, 3.841, 0.05), (2, 5.991, 0.05), (3, 7.815, 0.05),
        (4, 9.488, 0.05), (5, 11.070, 0.05), (10, 18.307, 0.05),
        (1, 6.635, 0.01), (4, 13.277, 0.01), (10, 23.209, 0.01),
    ]

    @pytest.mark.parametrize("df,crit,alpha", KNOWN_CRITICAL_VALUES)
    def test_recovers_known_critical_values_within_tolerance(self, df, crit, alpha):
        computed = _chi_square_p(crit, df)
        # df=1 is the least accurate case for Wilson-Hilferty; everything
        # df>=2 should be noticeably tighter. See module docstring.
        tol = 0.004 if df == 1 else 0.0015
        assert computed == pytest.approx(alpha, abs=tol)

    def test_zero_statistic_gives_p_of_one(self):
        assert _chi_square_p(0.0, 5) == 1.0

    def test_p_value_bounded_zero_to_one(self):
        for chi2 in [0.1, 1, 10, 100, 1000]:
            p = _chi_square_p(chi2, 3)
            assert 0.0 <= p <= 1.0

    def test_larger_statistic_gives_smaller_p(self):
        p_small = _chi_square_p(5.0, 3)
        p_large = _chi_square_p(50.0, 3)
        assert p_large < p_small


class TestChiSquareTest:
    def test_hand_derived_2x2_example(self):
        """
        observed = Group1:{A:10,B:5}, Group2:{A:5,B:10}. Row/col totals
        15/15/15/15, n=30, all expected = 7.5.
        chi2 = 4 * (2.5^2 / 7.5) = 4 * 0.8333... = 3.3333...
        df = 1, cramers_v = sqrt(3.3333/30) = 0.3333...
        """
        observed = {"Group1": {"A": 10, "B": 5}, "Group2": {"A": 5, "B": 10}}
        result = chi_square_test(observed)
        assert result["chi2"] == pytest.approx(3.3333, abs=1e-3)
        assert result["df"] == 1
        assert result["n"] == 30
        assert result["cramers_v"] == pytest.approx(0.3333, abs=1e-3)
        assert result["expected"]["Group1"]["A"] == 7.5

    def test_perfectly_independent_table_gives_chi2_near_zero(self):
        observed = {"G1": {"A": 10, "B": 10}, "G2": {"A": 10, "B": 10}}
        result = chi_square_test(observed)
        assert result["chi2"] == pytest.approx(0.0, abs=1e-9)
        assert result["p_value"] == pytest.approx(1.0, abs=1e-6)

    def test_fewer_than_two_rows_raises(self):
        with pytest.raises(ValueError, match="2 rows"):
            chi_square_test({"G1": {"A": 5, "B": 5}})

    def test_fewer_than_two_columns_raises(self):
        with pytest.raises(ValueError, match="2 columns"):
            chi_square_test({"G1": {"A": 5}, "G2": {"A": 5}})

    def test_mismatched_columns_raises(self):
        with pytest.raises(ValueError, match="different columns"):
            chi_square_test({"G1": {"A": 5, "B": 5}, "G2": {"A": 5, "C": 5}})

    def test_empty_table_raises(self):
        with pytest.raises(ValueError, match="empty"):
            chi_square_test({"G1": {"A": 0, "B": 0}, "G2": {"A": 0, "B": 0}})

    def test_3x4_table_df_calculation(self):
        observed = {
            "G1": {"A": 5, "B": 5, "C": 5, "D": 5},
            "G2": {"A": 5, "B": 5, "C": 5, "D": 5},
            "G3": {"A": 5, "B": 5, "C": 5, "D": 5},
        }
        result = chi_square_test(observed)
        assert result["df"] == (3 - 1) * (4 - 1)  # 6


class TestCoOccurrenceSummary:
    def test_hand_derived_lift_example(self):
        """
        R1,R2 have both A and B; R3 has only A; R4 has only B; R5 has only C.
        n_respondents=5, P(A)=3/5, P(B)=3/5, P(A&B)=2/5.
        lift(A,B) = 0.4 / (0.6*0.6) = 1.1111...
        """
        records = [
            _rec("R1", "I1", "A"), _rec("R1", "I2", "B"),
            _rec("R2", "I1", "A"), _rec("R2", "I2", "B"),
            _rec("R3", "I1", "A"),
            _rec("R4", "I1", "B"),
            _rec("R5", "I1", "C"),
        ]
        result = co_occurrence_summary(records, categories=["A", "B", "C"])
        ab = next(r for r in result if {r["category_a"], r["category_b"]} == {"A", "B"})
        assert ab["support"] == 2
        assert ab["lift"] == pytest.approx(1.1111, abs=1e-3)

    def test_sorted_by_lift_descending(self):
        records = [
            _rec("R1", "I1", "A"), _rec("R1", "I2", "B"),
            _rec("R2", "I1", "A"), _rec("R2", "I2", "B"),
            _rec("R3", "I1", "C"), _rec("R3", "I2", "A"),
        ]
        result = co_occurrence_summary(records, categories=["A", "B", "C"])
        lifts = [r["lift"] for r in result]
        assert lifts == sorted(lifts, reverse=True)

    def test_no_respondents_gives_empty_list(self):
        assert co_occurrence_summary([]) == []

    def test_single_item_respondents_produce_no_pairs(self):
        records = [_rec("R1", "I1", "A"), _rec("R2", "I1", "B")]
        assert co_occurrence_summary(records, categories=["A", "B"]) == []


class TestItemPairCooccurrence:
    def test_only_respondents_with_both_items_counted(self):
        records = [
            _rec("R1", "I1", "A"), _rec("R1", "I2", "A"),
            _rec("R2", "I1", "B"), _rec("R2", "I2", "B"),
            _rec("R3", "I1", "A"),  # missing I2, should be excluded
        ]
        result = item_pair_cooccurrence(records, "I1", "I2", categories=["A", "B"])
        assert result["n_respondents"] == 2

    def test_returns_chi_square_test_shape(self):
        records = [
            _rec("R1", "I1", "A"), _rec("R1", "I2", "A"),
            _rec("R2", "I1", "B"), _rec("R2", "I2", "B"),
        ]
        result = item_pair_cooccurrence(records, "I1", "I2", categories=["A", "B"])
        for key in ("chi2", "df", "p_value", "n", "cramers_v", "expected"):
            assert key in result


class TestTransitionMatrix:
    def test_counts_consecutive_transitions_only(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"),
            _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R1", "I1", "A", timepoint="t3"),
        ]
        result = transition_matrix(records, categories=["A", "B"],
                                   timepoint_order=["t1", "t2", "t3"])
        assert result["counts"]["A"]["B"] == 1
        assert result["counts"]["B"]["A"] == 1
        assert result["n_transitions"] == 2

    def test_probabilities_row_normalized(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"),
            _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R2", "I1", "A", timepoint="t1"),
            _rec("R2", "I1", "A", timepoint="t2"),
        ]
        result = transition_matrix(records, categories=["A", "B"],
                                   timepoint_order=["t1", "t2"])
        assert sum(result["probabilities"]["A"].values()) == pytest.approx(1.0)
        assert result["probabilities"]["A"]["A"] == 0.5
        assert result["probabilities"]["A"]["B"] == 0.5

    def test_never_a_starting_state_gives_none_most_likely(self):
        records = [_rec("R1", "I1", "A", timepoint="t1")]  # no second timepoint
        result = transition_matrix(records, categories=["A", "B"],
                                   timepoint_order=["t1", "t2"])
        assert result["most_likely_next"]["A"] is None
        assert result["most_likely_next"]["B"] is None

    def test_item_id_filter_excludes_other_items(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"),
            _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R1", "I2", "A", timepoint="t1"),
            _rec("R1", "I2", "A", timepoint="t2"),
        ]
        result = transition_matrix(records, item_id="I1", categories=["A", "B"],
                                   timepoint_order=["t1", "t2"])
        assert result["n_transitions"] == 1
        assert result["counts"]["A"]["B"] == 1

    def test_most_likely_next_identifies_dominant_transition(self):
        records = (
            [_rec("R1", "I1", "A", timepoint="t1"), _rec("R1", "I1", "B", timepoint="t2")] +
            [_rec("R2", "I1", "A", timepoint="t1"), _rec("R2", "I1", "B", timepoint="t2")] +
            [_rec("R3", "I1", "A", timepoint="t1"), _rec("R3", "I1", "A", timepoint="t2")]
        )
        result = transition_matrix(records, categories=["A", "B"], timepoint_order=["t1", "t2"])
        assert result["most_likely_next"]["A"] == "B"  # 2 A->B vs 1 A->A


class TestMineTransitionPatterns:
    def test_counts_bigrams_correctly(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"), _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R2", "I1", "A", timepoint="t1"), _rec("R2", "I1", "B", timepoint="t2"),
            _rec("R3", "I1", "B", timepoint="t1"), _rec("R3", "I1", "A", timepoint="t2"),
        ]
        result = mine_transition_patterns(records, categories=["A", "B"],
                                          timepoint_order=["t1", "t2"], sequence_length=2)
        top = result[0]
        assert top["pattern"] == ["A", "B"]
        assert top["count"] == 2

    def test_respects_top_k(self):
        records = []
        for i in range(20):
            records.append(_rec(f"R{i}", "I1", "A", timepoint="t1"))
            records.append(_rec(f"R{i}", "I1", "B" if i % 2 else "A", timepoint="t2"))
        result = mine_transition_patterns(records, categories=["A", "B"],
                                          timepoint_order=["t1", "t2"], top_k=1)
        assert len(result) == 1

    def test_sequence_length_below_two_raises(self):
        with pytest.raises(ValueError, match="sequence_length"):
            mine_transition_patterns([], sequence_length=1)

    def test_triples(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"),
            _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R1", "I1", "C", timepoint="t3"),
        ]
        result = mine_transition_patterns(records, categories=["A", "B", "C"],
                                          timepoint_order=["t1", "t2", "t3"], sequence_length=3)
        assert result[0]["pattern"] == ["A", "B", "C"]


class TestTemporalTrend:
    def test_returns_chi_square_shape_plus_proportions(self):
        records = [
            _rec("R1", "I1", "A", timepoint="t1"), _rec("R1", "I1", "B", timepoint="t2"),
            _rec("R2", "I1", "A", timepoint="t1"), _rec("R2", "I1", "A", timepoint="t2"),
        ]
        result = temporal_trend(records, categories=["A", "B"], timepoint_order=["t1", "t2"])
        assert "chi2" in result
        assert "proportions" in result
        assert result["proportions"]["t1"]["A"] == 1.0  # both respondents A at t1

    def test_stable_distribution_gives_low_chi2(self):
        records = []
        for tp in ["t1", "t2"]:
            for i in range(10):
                records.append(_rec(f"R{i}", "I1", "A" if i < 5 else "B", timepoint=tp))
        result = temporal_trend(records, categories=["A", "B"], timepoint_order=["t1", "t2"])
        assert result["chi2"] == pytest.approx(0.0, abs=1e-9)


class TestCohortComparison:
    def test_returns_chi_square_shape_plus_proportions_and_gap(self):
        records = [
            _rec("R1", "I1", "A", cohort="Govt"), _rec("R2", "I1", "A", cohort="Govt"),
            _rec("R3", "I1", "B", cohort="Private"), _rec("R4", "I1", "B", cohort="Private"),
        ]
        result = cohort_comparison(records, categories=["A", "B"])
        assert "chi2" in result
        assert result["proportions"]["Govt"]["A"] == 1.0
        assert result["proportions"]["Private"]["B"] == 1.0
        assert result["largest_gap"]["category"] in ("A", "B")
        assert result["largest_gap"]["gap"] == pytest.approx(1.0)

    def test_fewer_than_two_cohorts_raises(self):
        records = [_rec("R1", "I1", "A", cohort="Govt")]
        with pytest.raises(ValueError, match="2 cohorts"):
            cohort_comparison(records, categories=["A"])

    def test_explicit_cohort_list_respected(self):
        records = [
            _rec("R1", "I1", "A", cohort="Govt"),
            _rec("R2", "I1", "B", cohort="Private"),
            _rec("R3", "I1", "A", cohort="International"),
        ]
        result = cohort_comparison(records, categories=["A", "B"], cohorts=["Govt", "Private"])
        assert set(result["proportions"].keys()) == {"Govt", "Private"}


class TestLoadLongitudinalCSV:
    def test_loads_required_and_optional_columns(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["respondent_id", "item_id", "label",
                                              "timepoint", "cohort"])
            w.writeheader()
            w.writerow({"respondent_id": "R1", "item_id": "I1", "label": "A",
                       "timepoint": "t1", "cohort": "Govt"})
        try:
            records = load_longitudinal_csv(path)
            assert records[0]["respondent_id"] == "R1"
            assert records[0]["cohort"] == "Govt"
        finally:
            os.remove(path)

    def test_missing_optional_columns_default_to_empty_string(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["respondent_id", "item_id", "label"])
            w.writeheader()
            w.writerow({"respondent_id": "R1", "item_id": "I1", "label": "A"})
        try:
            records = load_longitudinal_csv(path)
            assert records[0]["timepoint"] == ""
            assert records[0]["cohort"] == ""
        finally:
            os.remove(path)
