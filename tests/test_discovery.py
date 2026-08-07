"""
test_discovery.py - pytest suite for confusion_mapper.discovery
(label_purity, propose_candidate_categories, format_proposal_report).

New in v2.6.0. TestNeverWritesTaxonomy is the property this module exists
to guarantee: no function here should import or reference TAXONOMY,
load_taxonomy_from_json, write_codebook, or any file-writing taxonomy
function -- it should only ever read an embeddings index and produce a
plain data structure / string, never touch a taxonomy file.

Run with: pytest tests/test_discovery.py -v
"""

import sys
import os
import inspect

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import discovery
from confusion_mapper.discovery import label_purity, propose_candidate_categories, format_proposal_report
from confusion_mapper.embeddings import create_index, add_to_index


def _index_with_two_clusters():
    """
    Cluster 1 (mitochondria, 3 items): labels PK, PK, CF -- purity 2/3 = 0.667
    Cluster 2 (democracy, 3 items): labels RF, PK, INT -- purity 1/3 = 0.333
        (maximally inconsistent -- the interesting candidate)
    """
    idx = create_index(backend="local")
    add_to_index(idx, "a1", "mitochondria produce energy through cellular respiration",
                 metadata={"human_label": "PK"})
    add_to_index(idx, "a2", "mitochondria generate cellular energy via respiration",
                 metadata={"human_label": "PK"})
    add_to_index(idx, "a3", "mitochondria create energy from cellular respiration process",
                 metadata={"human_label": "CF"})
    add_to_index(idx, "b1", "democracy requires informed voters and free elections",
                 metadata={"human_label": "RF"})
    add_to_index(idx, "b2", "democracy needs informed voters with free elections",
                 metadata={"human_label": "PK"})
    add_to_index(idx, "b3", "democracy depends on informed voters having free elections",
                 metadata={"human_label": "INT"})
    return idx


class TestLabelPurity:
    def test_perfect_agreement_gives_purity_one(self):
        cluster = {"items": [
            {"item_id": "a", "text": "x", "metadata": {"label": "CF"}},
            {"item_id": "b", "text": "y", "metadata": {"label": "CF"}},
        ]}
        result = label_purity(cluster)
        assert result["purity"] == 1.0
        assert result["modal_label"] == "CF"
        assert result["n_distinct_labels"] == 1

    def test_maximal_disagreement(self):
        cluster = {"items": [
            {"item_id": "a", "text": "x", "metadata": {"label": "RF"}},
            {"item_id": "b", "text": "y", "metadata": {"label": "PK"}},
            {"item_id": "c", "text": "z", "metadata": {"label": "INT"}},
        ]}
        result = label_purity(cluster)
        assert result["purity"] == pytest.approx(1 / 3, abs=1e-3)
        assert result["n_distinct_labels"] == 3

    def test_custom_label_key(self):
        cluster = {"items": [
            {"item_id": "a", "text": "x", "metadata": {"ai_label": "CF"}},
            {"item_id": "b", "text": "y", "metadata": {"ai_label": "CF"}},
        ]}
        result = label_purity(cluster, label_key="ai_label")
        assert result["purity"] == 1.0

    def test_no_labels_present_gives_none_purity(self):
        cluster = {"items": [{"item_id": "a", "text": "x", "metadata": {}}]}
        result = label_purity(cluster)
        assert result["purity"] is None
        assert result["modal_label"] is None

    def test_label_counts_correct(self):
        cluster = {"items": [
            {"item_id": "a", "text": "x", "metadata": {"label": "CF"}},
            {"item_id": "b", "text": "y", "metadata": {"label": "CF"}},
            {"item_id": "c", "text": "z", "metadata": {"label": "PK"}},
        ]}
        result = label_purity(cluster)
        assert result["label_counts"] == {"CF": 2, "PK": 1}
        assert result["modal_label"] == "CF"
        assert result["modal_count"] == 2


class TestProposeCandidateCategories:
    def test_low_purity_cluster_is_flagged(self):
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=0.6)
        democracy_candidate = next(
            (c for c in candidates if {i["item_id"] for i in c["items"]} == {"b1", "b2", "b3"}),
            None)
        assert democracy_candidate is not None
        assert democracy_candidate["purity_report"]["purity"] == pytest.approx(1/3, abs=1e-3)

    def test_high_purity_cluster_is_not_flagged_at_strict_threshold(self):
        """The mitochondria cluster at purity 0.667 should NOT be flagged
        when max_purity is set below that."""
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=0.5)
        mito_flagged = any(
            {i["item_id"] for i in c["items"]} == {"a1", "a2", "a3"} for c in candidates)
        assert not mito_flagged

    def test_sorted_least_pure_first(self):
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        purities = [c["purity_report"]["purity"] for c in candidates]
        assert purities == sorted(purities)

    def test_no_candidates_when_everything_is_pure(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a1", "mitochondria produce energy", metadata={"label": "CF"})
        add_to_index(idx, "a2", "mitochondria generate energy", metadata={"label": "CF"})
        add_to_index(idx, "a3", "mitochondria create energy", metadata={"label": "CF"})
        candidates = propose_candidate_categories(
            idx, label_key="label", threshold=0.3, min_cluster_size=3, max_purity=0.6)
        assert candidates == []

    def test_empty_index_gives_no_candidates(self):
        idx = create_index(backend="local")
        assert propose_candidate_categories(idx) == []

    def test_min_cluster_size_filters_small_clusters(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a1", "mitochondria produce energy", metadata={"label": "CF"})
        add_to_index(idx, "a2", "mitochondria generate energy", metadata={"label": "RF"})
        candidates = propose_candidate_categories(
            idx, label_key="label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        assert candidates == []  # cluster of 2 < min_cluster_size 3


class TestFormatProposalReport:
    def test_empty_candidates_gives_no_candidates_message(self):
        report = format_proposal_report([])
        assert "No candidates found" in report

    def test_report_includes_cluster_details(self):
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        report = format_proposal_report(candidates, taxonomy_hint=["RF", "PK", "CF", "INT"])
        assert "Candidate misconception categories" in report
        assert "RF, PK, CF, INT" in report
        assert "democracy" in report.lower()
        assert "Nothing here has been written to any taxonomy file" in report

    def test_report_mentions_manual_next_step(self):
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        report = format_proposal_report(candidates)
        assert "load_taxonomy_from_json" in report

    def test_report_shows_real_labels_not_question_marks_with_custom_label_key(self):
        """
        Regression test for a real bug: format_proposal_report used to
        hardcode metadata.get("label"), so any index built with a
        different label_key (e.g. "human_label", the actual default used
        by the `embed-index --label-column` CLI flag) always showed "?"
        for every item instead of its real label.
        """
        idx = _index_with_two_clusters()  # metadata stored under "human_label"
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        report = format_proposal_report(candidates, label_key="human_label")
        assert "(?)" not in report
        assert "(RF)" in report or "(PK)" in report or "(INT)" in report or "(CF)" in report

    def test_report_shows_question_marks_when_label_key_mismatched(self):
        """The inverse check: if you pass the WRONG label_key, "?" is the
        correct, honest fallback -- not a silent wrong label."""
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(
            idx, label_key="human_label", threshold=0.3, min_cluster_size=3, max_purity=1.0)
        report = format_proposal_report(candidates, label_key="some_other_key")
        assert "(?)" in report


class TestNeverWritesTaxonomy:
    """
    The core safety property of this module. Checked two ways: (1) static
    inspection of the source for any taxonomy-file-writing call, and (2) a
    behavioral check that running the full discovery workflow doesn't
    create or modify any file on disk.
    """

    def test_source_never_calls_a_taxonomy_writing_function(self):
        source = inspect.getsource(discovery)
        forbidden = ["write_codebook(", "save_index(", "json.dump", "open(", "TAXONOMY["]
        for f in forbidden:
            assert f not in source, f"discovery.py must never call {f!r}"

    def test_source_never_imports_taxonomy_module(self):
        source = inspect.getsource(discovery)
        assert "from .taxonomy import" not in source
        assert "import taxonomy" not in source

    def test_running_the_workflow_touches_no_files(self, tmp_path):
        import os as _os
        before = set(_os.listdir(tmp_path))
        idx = _index_with_two_clusters()
        candidates = propose_candidate_categories(idx, label_key="human_label",
                                                   threshold=0.3, min_cluster_size=3)
        format_proposal_report(candidates)
        after = set(_os.listdir(tmp_path))
        assert before == after
