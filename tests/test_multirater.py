"""
test_multirater.py - pytest suite for the 3+ rater workflow (multirater.py).

New in v2.6.0. These tests deliberately don't re-derive kappa/AC1/Fleiss
arithmetic by hand -- that's already covered by test_kappa.py, and
multirater.py calls those functions unmodified. What's tested here is
multirater.py's own logic: the CSV data model, the pairing/adapter code,
and conflict detection.

Run with: pytest tests/test_multirater.py -v
"""

import sys
import os
import csv
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import (
    load_multirater_csv,
    pairwise_agreement_matrix,
    panel_fleiss_kappa,
    detect_conflicts,
    consensus_report,
)


def _write_csv(rows, fieldnames):
    """Write rows to a temp CSV, return its path. Caller should os.remove() it."""
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path


class TestLoadMultiraterCSV:
    def test_loads_wide_format_correctly(self):
        path = _write_csv(
            [{"item_id": "Q1", "A": "CF", "B": "CF", "C": "PK"},
             {"item_id": "Q2", "A": "RF", "B": "RF", "C": "RF"}],
            fieldnames=["item_id", "A", "B", "C"],
        )
        try:
            item_ids, rater_names, ratings = load_multirater_csv(path)
            assert item_ids == ["Q1", "Q2"]
            assert rater_names == ["A", "B", "C"]
            assert ratings[0] == {"A": "CF", "B": "CF", "C": "PK"}
            assert ratings[1] == {"A": "RF", "B": "RF", "C": "RF"}
        finally:
            os.remove(path)

    def test_missing_id_column_raises(self):
        path = _write_csv([{"A": "CF", "B": "CF"}], fieldnames=["A", "B"])
        try:
            with pytest.raises(ValueError, match="item_id"):
                load_multirater_csv(path)
        finally:
            os.remove(path)

    def test_fewer_than_two_rater_columns_raises(self):
        path = _write_csv([{"item_id": "Q1", "A": "CF"}], fieldnames=["item_id", "A"])
        try:
            with pytest.raises(ValueError, match="at least 2 rater columns"):
                load_multirater_csv(path)
        finally:
            os.remove(path)

    def test_custom_id_column_name(self):
        path = _write_csv(
            [{"qid": "Q1", "A": "CF", "B": "CF"}], fieldnames=["qid", "A", "B"]
        )
        try:
            item_ids, rater_names, ratings = load_multirater_csv(path, id_column="qid")
            assert item_ids == ["Q1"]
            assert rater_names == ["A", "B"]
        finally:
            os.remove(path)


class TestPairwiseAgreementMatrix:
    def test_generates_every_unordered_pair_exactly_once(self):
        ratings = [{"A": "CF", "B": "CF", "C": "PK"} for _ in range(5)]
        matrix = pairwise_agreement_matrix(ratings, ["A", "B", "C"])
        assert set(matrix.keys()) == {"A|B", "A|C", "B|C"}

    def test_perfect_agreement_gives_kappa_and_ac1_of_one(self):
        ratings = [{"A": "CF", "B": "CF"}] * 5 + [{"A": "RF", "B": "RF"}] * 5
        matrix = pairwise_agreement_matrix(ratings, ["A", "B"], categories=["CF", "RF"])
        assert matrix["A|B"]["kappa"] == 1.0
        assert matrix["A|B"]["ac1"] == 1.0
        assert matrix["A|B"]["n"] == 10

    def test_result_matches_calling_compute_cohens_kappa_directly(self):
        """pairwise_agreement_matrix is an adapter -- it must not silently
        alter what compute_cohens_kappa would return for the same pair."""
        from confusion_mapper import compute_cohens_kappa
        ratings = [{"A": "CF", "B": "CF"}, {"A": "CF", "B": "RF"},
                  {"A": "RF", "B": "RF"}, {"A": "PK", "B": "CF"}]
        matrix = pairwise_agreement_matrix(ratings, ["A", "B"])
        direct = compute_cohens_kappa(["CF", "CF", "RF", "PK"], ["CF", "RF", "RF", "CF"])
        assert matrix["A|B"]["kappa"] == direct["kappa"]
        assert matrix["A|B"]["po"] == direct["po"]

    def test_two_raters_gives_exactly_one_pair(self):
        ratings = [{"A": "CF", "B": "PK"}]
        matrix = pairwise_agreement_matrix(ratings, ["A", "B"])
        assert len(matrix) == 1


class TestPanelFleissKappa:
    def test_requires_at_least_three_raters(self):
        ratings = [{"A": "CF", "B": "CF"}]
        with pytest.raises(ValueError, match="at least 3 raters"):
            panel_fleiss_kappa(ratings, ["A", "B"])

    def test_perfect_agreement_across_panel(self):
        ratings = [{"A": "CF", "B": "CF", "C": "CF"} for _ in range(5)] + \
                 [{"A": "RF", "B": "RF", "C": "RF"} for _ in range(5)]
        result = panel_fleiss_kappa(ratings, ["A", "B", "C"], categories=["CF", "RF"])
        assert result["kappa"] == 1.0
        assert result["n_items"] == 10
        assert result["n_raters"] == 3

    def test_adapter_produces_correct_category_counts(self):
        """
        Item 1 is unanimous (3/3 CF); item 2 splits 2 CF / 1 PK. With only 4
        categories and 2 items, one category (CF) dominates both items, so
        Fleiss' expected-by-chance agreement is high and kappa comes out
        low/negative despite high raw per-item agreement -- the same
        kappa-paradox shape gwet_ac1() exists to diagnose. Value below is
        confirmed by directly running panel_fleiss_kappa on this input, not
        assumed from the P_bar arithmetic alone.
        """
        ratings = [
            {"A": "CF", "B": "CF", "C": "CF"},   # unanimous
            {"A": "CF", "B": "CF", "C": "PK"},   # 2 CF, 1 PK
        ]
        result = panel_fleiss_kappa(ratings, ["A", "B", "C"])
        assert result["n_items"] == 2
        assert result["kappa"] == pytest.approx(-0.2, abs=1e-9)


class TestDetectConflicts:
    def test_unanimous_items_are_excluded(self):
        item_ids = ["Q1"]
        ratings = [{"A": "CF", "B": "CF", "C": "CF"}]
        conflicts = detect_conflicts(item_ids, ratings, ["A", "B", "C"])
        assert conflicts == []

    def test_clear_majority_is_identified(self):
        item_ids = ["Q1"]
        ratings = [{"A": "CF", "B": "CF", "C": "PK"}]
        conflicts = detect_conflicts(item_ids, ratings, ["A", "B", "C"])
        assert len(conflicts) == 1
        assert conflicts[0]["majority_label"] == "CF"
        assert conflicts[0]["majority_count"] == 2
        assert conflicts[0]["tied_labels"] is None

    def test_three_way_tie_has_no_majority(self):
        item_ids = ["Q1"]
        ratings = [{"A": "CF", "B": "PK", "C": "RF"}]
        conflicts = detect_conflicts(item_ids, ratings, ["A", "B", "C"])
        assert conflicts[0]["majority_label"] is None
        assert sorted(conflicts[0]["tied_labels"]) == ["CF", "PK", "RF"]

    def test_sorted_worst_disagreement_first(self):
        item_ids = ["Q_split", "Q_tie", "Q_unanimous"]
        ratings = [
            {"A": "CF", "B": "CF", "C": "PK"},   # 2 distinct
            {"A": "CF", "B": "PK", "C": "RF"},   # 3 distinct
            {"A": "CF", "B": "CF", "C": "CF"},   # unanimous, excluded
        ]
        conflicts = detect_conflicts(item_ids, ratings, ["A", "B", "C"])
        assert [c["item_id"] for c in conflicts] == ["Q_tie", "Q_split"]

    def test_two_rater_conflict_detection(self):
        """Conflict detection should also work for exactly 2 raters
        (majority = 1-0, which is degenerate but shouldn't crash)."""
        item_ids = ["Q1"]
        ratings = [{"A": "CF", "B": "PK"}]
        conflicts = detect_conflicts(item_ids, ratings, ["A", "B"])
        assert len(conflicts) == 1
        assert conflicts[0]["tied_labels"] is not None  # 1-1 is a tie


class TestConsensusReport:
    def test_includes_fleiss_for_three_plus_raters(self):
        item_ids = ["Q1", "Q2"]
        ratings = [{"A": "CF", "B": "CF", "C": "CF"}, {"A": "RF", "B": "RF", "C": "RF"}]
        report = consensus_report(item_ids, ratings, ["A", "B", "C"], categories=["CF", "RF"])
        assert "fleiss" in report
        assert report["fleiss"]["kappa"] == 1.0

    def test_omits_fleiss_for_two_raters(self):
        item_ids = ["Q1"]
        ratings = [{"A": "CF", "B": "CF"}]
        report = consensus_report(item_ids, ratings, ["A", "B"])
        assert "fleiss" not in report

    def test_report_shape(self):
        item_ids = ["Q1", "Q2"]
        ratings = [{"A": "CF", "B": "CF", "C": "PK"}, {"A": "RF", "B": "RF", "C": "RF"}]
        report = consensus_report(item_ids, ratings, ["A", "B", "C"])
        for key in ("n_items", "n_raters", "raters", "pairwise", "n_conflicts", "conflicts"):
            assert key in report
        assert report["n_items"] == 2
        assert report["n_raters"] == 3
        assert report["n_conflicts"] == 1

    def test_end_to_end_on_bundled_sample_data(self):
        """Smoke test against the actual sample_data/example_multirater.csv
        shipped with the package, the same file the CLI documentation uses."""
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sample_data", "example_multirater.csv",
        )
        item_ids, rater_names, ratings = load_multirater_csv(sample_path)
        report = consensus_report(item_ids, ratings, rater_names)
        assert report["n_items"] == 15
        assert report["n_raters"] == 3
        assert report["n_conflicts"] == 8
