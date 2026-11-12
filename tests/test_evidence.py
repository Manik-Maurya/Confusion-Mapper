"""
test_evidence.py - pytest suite for confusion_mapper's evidence panel
(build_evidence_panel, add_note, revise_label, current_label,
get_revision_history, get_notes, full_panel_report, load/save_evidence_log).

New in v2.6.0. The property this suite cares about most: revise_label()
must NEVER cause the original session's recorded human_label to change --
that guarantee is what makes it safe to use on live RCT session files. See
test_revising_never_mutates_the_session_object specifically.

Run with: pytest tests/test_evidence.py -v
"""

import sys
import os
import copy
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import (
    build_evidence_panel,
    add_note,
    revise_label,
    current_label,
    get_revision_history,
    get_notes,
    full_panel_report,
    load_evidence_log,
    save_evidence_log,
)


@pytest.fixture
def sample_session():
    return {
        "rater_id": "TestRater",
        "ratings": [
            {"distractor_id": "Q1_D1", "question_id": "Q1", "topic": "Photosynthesis",
             "distractor_text": "Mitochondria", "human_label": "RF", "ai_label": "CF",
             "ai_reasoning": "Coherent misconception about organelles.",
             "ai_available": True, "reference_label": "CF", "agreement": False},
            {"distractor_id": "Q1_D2", "question_id": "Q1", "topic": "Photosynthesis",
             "distractor_text": "Cell wall", "human_label": "PK", "ai_label": "PK",
             "ai_reasoning": "", "ai_available": True, "reference_label": "PK", "agreement": True},
        ],
    }


class TestBuildEvidencePanel:
    def test_one_entry_per_rating(self, sample_session):
        panel = build_evidence_panel(sample_session)
        assert set(panel.keys()) == {"Q1_D1", "Q1_D2"}

    def test_fields_pulled_from_session_correctly(self, sample_session):
        panel = build_evidence_panel(sample_session)
        assert panel["Q1_D1"]["original_answer"] == "Mitochondria"
        assert panel["Q1_D1"]["assigned_label"] == "RF"
        assert panel["Q1_D1"]["ai_label"] == "CF"
        assert panel["Q1_D1"]["reason"] == "Coherent misconception about organelles."

    def test_empty_ai_reasoning_becomes_none_not_empty_string(self, sample_session):
        panel = build_evidence_panel(sample_session)
        assert panel["Q1_D2"]["reason"] is None

    def test_empty_session_gives_empty_panel(self):
        assert build_evidence_panel({"ratings": []}) == {}


class TestAddNote:
    def test_note_recorded_with_author_and_date(self):
        log = {}
        add_note(log, "Q1_D1", "borderline case", author="Manik")
        notes = get_notes(log, "Q1_D1")
        assert len(notes) == 1
        assert notes[0]["note"] == "borderline case"
        assert notes[0]["author"] == "Manik"
        assert "date" in notes[0]

    def test_notes_accumulate_dont_overwrite(self):
        log = {}
        add_note(log, "Q1_D1", "first note")
        add_note(log, "Q1_D1", "second note")
        notes = get_notes(log, "Q1_D1")
        assert len(notes) == 2
        assert [n["note"] for n in notes] == ["first note", "second note"]

    def test_notes_on_different_items_dont_interfere(self):
        log = {}
        add_note(log, "Q1_D1", "note on D1")
        add_note(log, "Q1_D2", "note on D2")
        assert len(get_notes(log, "Q1_D1")) == 1
        assert len(get_notes(log, "Q1_D2")) == 1

    def test_returns_the_log_for_chaining(self):
        log = {}
        result = add_note(log, "Q1_D1", "note")
        assert result is log


class TestReviseLabel:
    def test_empty_reason_raises(self):
        log = {}
        with pytest.raises(ValueError, match="reason"):
            revise_label(log, "Q1_D1", "CF", "")

    def test_whitespace_only_reason_raises(self):
        log = {}
        with pytest.raises(ValueError, match="reason"):
            revise_label(log, "Q1_D1", "CF", "   ")

    def test_revision_recorded_with_all_fields(self):
        log = {}
        revise_label(log, "Q1_D1", "CF", "reconsidered on review", author="Manik", old_label="RF")
        history = get_revision_history(log, "Q1_D1")
        assert len(history) == 1
        assert history[0]["old_label"] == "RF"
        assert history[0]["new_label"] == "CF"
        assert history[0]["reason"] == "reconsidered on review"
        assert history[0]["author"] == "Manik"

    def test_second_revision_infers_old_label_from_first(self):
        log = {}
        revise_label(log, "Q1_D1", "CF", "first pass", old_label="RF")
        revise_label(log, "Q1_D1", "PK", "second pass")  # old_label not given
        history = get_revision_history(log, "Q1_D1")
        assert len(history) == 2
        assert history[1]["old_label"] == "CF"  # inferred from history[0]'s new_label
        assert history[1]["new_label"] == "PK"

    def test_revisions_accumulate_dont_overwrite(self):
        log = {}
        revise_label(log, "Q1_D1", "CF", "r1", old_label="RF")
        revise_label(log, "Q1_D1", "PK", "r2")
        revise_label(log, "Q1_D1", "INT", "r3")
        assert len(get_revision_history(log, "Q1_D1")) == 3


class TestCurrentLabel:
    def test_falls_back_to_session_original_when_no_revisions(self, sample_session):
        log = {}
        assert current_label(log, sample_session, "Q1_D1") == "RF"

    def test_reflects_latest_revision(self, sample_session):
        log = {}
        revise_label(log, "Q1_D1", "CF", "reason", old_label="RF")
        assert current_label(log, sample_session, "Q1_D1") == "CF"

    def test_reflects_most_recent_of_multiple_revisions(self, sample_session):
        log = {}
        revise_label(log, "Q1_D1", "CF", "r1", old_label="RF")
        revise_label(log, "Q1_D1", "INT", "r2")
        assert current_label(log, sample_session, "Q1_D1") == "INT"

    def test_unaffected_item_still_returns_original(self, sample_session):
        log = {}
        revise_label(log, "Q1_D1", "CF", "reason", old_label="RF")
        assert current_label(log, sample_session, "Q1_D2") == "PK"

    def test_unknown_distractor_id_returns_none(self, sample_session):
        log = {}
        assert current_label(log, sample_session, "NONEXISTENT") is None


class TestSessionNeverMutated:
    """The core safety property: revising a label in the evidence log must
    never alter the session object/file it's layered on top of."""

    def test_revising_never_mutates_the_session_object(self, sample_session):
        original = copy.deepcopy(sample_session)
        log = {}
        revise_label(log, "Q1_D1", "CF", "reconsidered", old_label="RF")
        revise_label(log, "Q1_D1", "INT", "reconsidered again")
        add_note(log, "Q1_D1", "some note")
        assert sample_session == original, "session object was mutated, this must never happen"

    def test_original_human_label_field_unchanged_even_after_revision(self, sample_session):
        log = {}
        revise_label(log, "Q1_D1", "CF", "reason", old_label="RF")
        rating = next(r for r in sample_session["ratings"] if r["distractor_id"] == "Q1_D1")
        assert rating["human_label"] == "RF"  # still the original, never overwritten


class TestFullPanelReport:
    def test_combines_session_and_log_correctly(self, sample_session):
        log = {}
        add_note(log, "Q1_D1", "a note")
        revise_label(log, "Q1_D1", "CF", "reason", old_label="RF")

        report = full_panel_report(sample_session, log)

        assert report["Q1_D1"]["assigned_label"] == "RF"    # original, unchanged
        assert report["Q1_D1"]["current_label"] == "CF"     # post-revision
        assert len(report["Q1_D1"]["notes"]) == 1
        assert len(report["Q1_D1"]["revision_history"]) == 1

        assert report["Q1_D2"]["assigned_label"] == "PK"
        assert report["Q1_D2"]["current_label"] == "PK"     # untouched
        assert report["Q1_D2"]["notes"] == []
        assert report["Q1_D2"]["revision_history"] == []

    def test_empty_log_gives_current_equal_assigned_for_everything(self, sample_session):
        report = full_panel_report(sample_session, {})
        for item in report.values():
            assert item["current_label"] == item["assigned_label"]
            assert item["notes"] == []
            assert item["revision_history"] == []


class TestPersistence:
    def test_load_nonexistent_file_returns_empty_dict(self):
        assert load_evidence_log("/tmp/definitely_does_not_exist_12345.json") == {}

    def test_save_then_load_round_trips(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            log = {}
            add_note(log, "Q1_D1", "a note", author="Manik")
            revise_label(log, "Q1_D1", "CF", "reason", author="Manik", old_label="RF")
            save_evidence_log(log, path)

            reloaded = load_evidence_log(path)
            assert reloaded == log
            assert get_notes(reloaded, "Q1_D1")[0]["note"] == "a note"
            assert get_revision_history(reloaded, "Q1_D1")[0]["new_label"] == "CF"
        finally:
            os.remove(path)

    def test_corrupted_file_returns_empty_dict_not_a_crash(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w") as f:
            f.write("{not valid json")
        try:
            assert load_evidence_log(path) == {}
        finally:
            os.remove(path)
