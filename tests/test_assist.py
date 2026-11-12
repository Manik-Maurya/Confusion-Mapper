"""
test_assist.py - pytest suite for confusion_mapper's assist mode
(load_assist_csv, classify_with_confidence, run_assist_session,
save_assist_session/load_assist_sessions).

New in v2.6.0. The property this suite cares about most: a session
produced by this module must NEVER contain a kappa/matrix/type_stats key
(see test_session_never_reports_a_kappa), assist-mode labels are not
independent of the AI's suggestion, so a kappa computed on them would be
scientifically meaningless, and its mere presence in a session file risks
being misread later without this context. No test here makes a real
network call to OpenAI; every scenario runs with no API key, which is
enough to exercise the full interactive loop's logic.

Run with: pytest tests/test_assist.py -v
"""

import sys
import os
import io
import csv
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.assist import (
    RELIABILITY_WARNING,
    load_assist_csv,
    classify_with_confidence,
    run_assist_session,
    save_assist_session,
    load_assist_sessions,
)
from confusion_mapper.embeddings import create_index, add_to_index, save_index
from confusion_mapper.taxonomy import DATA_FILE, ASSIST_DATA_FILE


def _write_csv(rows, fieldnames):
    fd, path = tempfile.mkstemp(suffix=".csv")
    with os.fdopen(fd, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)
    return path


class TestLoadAssistCSV:
    def test_loads_all_fields(self):
        path = _write_csv(
            [{"item_id": "D1", "distractor_text": "text one",
             "question_text": "Q1?", "correct_answer": "A", "topic": "Bio"}],
            fieldnames=["item_id", "distractor_text", "question_text", "correct_answer", "topic"],
        )
        try:
            items = load_assist_csv(path)
            assert items[0]["item_id"] == "D1"
            assert items[0]["distractor_text"] == "text one"
            assert items[0]["question_text"] == "Q1?"
        finally:
            os.remove(path)

    def test_missing_optional_columns_default_to_empty_string(self):
        path = _write_csv([{"distractor_text": "text only"}], fieldnames=["distractor_text"])
        try:
            items = load_assist_csv(path)
            assert items[0]["distractor_text"] == "text only"
            assert items[0]["question_text"] == ""
            assert items[0]["correct_answer"] == ""
            assert items[0]["topic"] == ""
        finally:
            os.remove(path)

    def test_missing_item_id_gets_row_based_default(self):
        path = _write_csv(
            [{"distractor_text": "a"}, {"distractor_text": "b"}],
            fieldnames=["distractor_text"],
        )
        try:
            items = load_assist_csv(path)
            assert items[0]["item_id"] == "row_0"
            assert items[1]["item_id"] == "row_1"
        finally:
            os.remove(path)

    def test_empty_item_id_cell_also_gets_default(self):
        path = _write_csv([{"item_id": "", "distractor_text": "a"}],
                          fieldnames=["item_id", "distractor_text"])
        try:
            items = load_assist_csv(path)
            assert items[0]["item_id"] == "row_0"
        finally:
            os.remove(path)


class TestClassifyWithConfidence:
    def test_no_api_key_gives_unavailable(self):
        result = classify_with_confidence("Q?", "A", "distractor", "Topic", api_key=None)
        assert result["available"] is False
        assert result["label"] == "N/A"
        assert result["confidence"] is None
        assert "API key" in result["reasoning"]

    def test_empty_string_api_key_also_gives_unavailable(self):
        result = classify_with_confidence("Q?", "A", "distractor", "Topic", api_key="")
        assert result["available"] is False


class TestReliabilityWarning:
    def test_mentions_kappa_and_independence(self):
        assert "kappa" in RELIABILITY_WARNING.lower()
        assert "independent" in RELIABILITY_WARNING.lower() or "not" in RELIABILITY_WARNING.lower()


class TestRunAssistSessionNoApiKey:
    """
    Every scenario here runs with api_key=None, so classify_with_confidence
    always returns available=False, this exercises the full "no real
    suggestion" branch of the loop (see the bug this was built to catch:
    it used to require an override reason and offer a nonsensical
    "accept N/A" option in this exact scenario).
    """

    def _items(self, n=2):
        return [{"item_id": f"D{i}", "distractor_text": f"distractor {i}",
                 "question_text": "Q?", "correct_answer": "A", "topic": "T"}
                for i in range(n)]

    def test_manual_labels_recorded_correctly(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert session["decisions"][0]["human_label"] == "RF"
        assert session["decisions"][1]["human_label"] == "PK"

    def test_accepted_is_none_not_false_when_no_suggestion_existed(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert all(d["accepted"] is None for d in session["decisions"])

    def test_no_reason_required_when_no_suggestion_existed(self, monkeypatch, capsys):
        """The bug this test guards: stdin here provides NO reason text at
        all, only the two label choices. If the code incorrectly demanded
        an override reason for a non-existent AI suggestion, this would
        hang/EOFError instead of completing."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert session["n_items_decided"] == 2
        assert all(d["override_reason"] is None for d in session["decisions"])

    def test_acceptance_rate_is_none_when_no_suggestions_available(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert session["n_items_with_ai_suggestion"] == 0
        assert session["acceptance_rate"] is None

    def test_quit_early_stops_the_loop(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\nQ\n"))
        session = run_assist_session(self._items(3), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert session["n_items_offered"] == 3
        assert session["n_items_decided"] == 1

    def test_session_never_reports_a_kappa(self, monkeypatch, capsys):
        """The core safety property of this whole module."""
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        for forbidden_key in ("kappa", "matrix", "type_stats", "ai_mode"):
            assert forbidden_key not in session

    def test_session_mode_and_warning_present(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n2\n"))
        session = run_assist_session(self._items(2), api_key=None, rater_id="Tester")
        capsys.readouterr()
        assert session["mode"] == "ai_assisted"
        assert session["reliability_warning"] == RELIABILITY_WARNING


class TestRunAssistSessionWithIndex:
    def test_similar_examples_retrieved_when_index_given(self, monkeypatch, capsys):
        fd, index_path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            idx = create_index(backend="local")
            add_to_index(idx, "prior1", "mitochondria produce energy",
                         metadata={"label": "PK"})
            save_index(idx, index_path)

            monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
            items = [{"item_id": "D1", "distractor_text": "mitochondria generate energy",
                     "question_text": "", "correct_answer": "", "topic": ""}]
            run_assist_session(items, api_key=None, rater_id="Tester", index_path=index_path)
            out = capsys.readouterr().out
            assert "Nearest already-coded examples" in out
            assert "mitochondria produce energy" in out
        finally:
            os.remove(index_path)

    def test_no_index_path_means_no_similar_examples_section(self, monkeypatch, capsys):
        monkeypatch.setattr(sys, "stdin", io.StringIO("1\n"))
        items = [{"item_id": "D1", "distractor_text": "text",
                 "question_text": "", "correct_answer": "", "topic": ""}]
        run_assist_session(items, api_key=None, rater_id="Tester", index_path=None)
        out = capsys.readouterr().out
        assert "Nearest already-coded examples" not in out


class TestPersistence:
    def test_uses_separate_file_from_blind_mode_data_file(self):
        assert ASSIST_DATA_FILE != DATA_FILE

    def test_save_then_load_round_trips(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            session = {"mode": "ai_assisted", "rater_id": "Tester", "decisions": []}
            save_assist_session(session, path=path)
            reloaded = load_assist_sessions(path=path)
            assert len(reloaded) == 1
            assert reloaded[0]["rater_id"] == "Tester"
        finally:
            os.remove(path)

    def test_multiple_sessions_append_not_overwrite(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            save_assist_session({"mode": "ai_assisted", "rater_id": "A", "decisions": []}, path=path)
            save_assist_session({"mode": "ai_assisted", "rater_id": "B", "decisions": []}, path=path)
            reloaded = load_assist_sessions(path=path)
            assert len(reloaded) == 2
            assert [s["rater_id"] for s in reloaded] == ["A", "B"]
        finally:
            os.remove(path)

    def test_load_nonexistent_file_returns_empty_list(self):
        assert load_assist_sessions(path="/tmp/definitely_does_not_exist_assist_12345.json") == []
