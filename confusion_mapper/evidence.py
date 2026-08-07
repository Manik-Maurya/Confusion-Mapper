"""
Evidence panel: for every coded item, the original answer, the assigned
label, the reason behind it, free-text notes, and a full revision history
-- the Level 1.5 "evidence panel" from the roadmap this package has been
built against.

New in v2.6.0. Deliberately NOT wired into run_session() / console.py.
Prompting a human coder to type a reason for every one of 15-90 distractors
during a live session is a real change to the coding workflow's pace and
cognitive load, not a silent metadata addition like the provenance fields
in storage.py/taxonomy.py -- exactly the kind of change that shouldn't
happen without you signing off first, given the Sept 22 data collection
window. So this module works the other way around: post-hoc, on top of
already-saved session files, without ever touching them.

Session ratings already carry three of the five things an evidence panel
needs -- distractor_id, distractor_text (the original answer), human_label
(the assigned label) -- plus ai_reasoning when the AI rater ran, which
already IS a "reason" for the AI's half of the pair. What's genuinely new
here is notes and revision history, both stored in a separate,
append-only JSON log keyed by distractor_id. The original session file is
never opened for writing by this module. If you revise a label, the
original human_label in the session file stays exactly what was recorded
live; the revision log records the change, the reason, who made it, and
when, and current_label() tells you what the item's label is *now* by
checking the log first, falling back to the session's original label only
if there's no revision on file.
"""

import datetime
import json
import os


def build_evidence_panel(session):
    """
    Turn a session's `ratings` list into an evidence panel: one entry per
    distractor, using only fields already present in the session (no
    revision/note data yet -- combine with an evidence log via
    current_label() / get_revision_history() / get_notes() for that).

    Args:
        session (dict): a session dict as returned by run_session() /
            saved by save_session() -- must have a "ratings" key.

    Returns:
        dict: {distractor_id: {original_answer, assigned_label, ai_label,
        reason, question_id, topic}}
    """
    panel = {}
    for r in session.get("ratings", []):
        did = r["distractor_id"]
        panel[did] = {
            "original_answer": r.get("distractor_text", ""),
            "assigned_label":  r.get("human_label", ""),
            "ai_label":        r.get("ai_label", ""),
            "reason":          r.get("ai_reasoning", "") or None,
            "question_id":     r.get("question_id", ""),
            "topic":           r.get("topic", ""),
        }
    return panel


def _now():
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _entry(evidence_log, distractor_id):
    return evidence_log.setdefault(distractor_id, {"notes": [], "revisions": []})


def add_note(evidence_log, distractor_id, note, author=None):
    """
    Append a free-text note to an item. Does not touch any other item's
    entry and never overwrites a previous note -- notes accumulate.

    Args:
        evidence_log (dict): as returned by load_evidence_log() / an empty
            {} for a fresh log.
        distractor_id (str): e.g. "Q1_D2", matching the session's
            ratings[i]["distractor_id"].
        note (str)
        author (str | None)

    Returns:
        dict: the same evidence_log, mutated in place and returned for
        convenient chaining.
    """
    _entry(evidence_log, distractor_id)["notes"].append({
        "note":   note,
        "author": author,
        "date":   _now(),
    })
    return evidence_log


def revise_label(evidence_log, distractor_id, new_label, reason, author=None, old_label=None):
    """
    Log a label revision. This is the whole point of the module: nothing
    anywhere overwrites the original label from the session file. This
    function only appends a revision record; current_label() is what
    resolves "what is this item's label now."

    Args:
        evidence_log (dict)
        distractor_id (str)
        new_label (str): the revised label.
        reason (str): required -- a revision without a stated reason
            defeats the purpose of keeping the log. Raises ValueError if
            empty.
        author (str | None)
        old_label (str | None): the label being superseded, for the
            record. If you don't pass it, it's inferred as the previous
            revision's new_label, or left None for the very first
            revision on an item (call current_label() against the
            session first if you want it recorded accurately).

    Returns:
        dict: the same evidence_log, mutated in place and returned.
    """
    if not reason or not reason.strip():
        raise ValueError("revise_label requires a non-empty reason")

    entry = _entry(evidence_log, distractor_id)
    if old_label is None and entry["revisions"]:
        old_label = entry["revisions"][-1]["new_label"]

    entry["revisions"].append({
        "old_label": old_label,
        "new_label": new_label,
        "reason":    reason,
        "author":    author,
        "date":      _now(),
    })
    return evidence_log


def current_label(evidence_log, session, distractor_id):
    """
    The item's label *right now*: the newest revision if the evidence log
    has one, otherwise the original human_label from the session --
    session data is never mutated, so this is always computed, never
    stored redundantly.
    """
    entry = evidence_log.get(distractor_id)
    if entry and entry["revisions"]:
        return entry["revisions"][-1]["new_label"]

    for r in session.get("ratings", []):
        if r["distractor_id"] == distractor_id:
            return r.get("human_label")
    return None


def get_revision_history(evidence_log, distractor_id):
    """Ordered list of every revision recorded for one item, oldest first."""
    entry = evidence_log.get(distractor_id)
    return list(entry["revisions"]) if entry else []


def get_notes(evidence_log, distractor_id):
    """Ordered list of every note recorded for one item, oldest first."""
    entry = evidence_log.get(distractor_id)
    return list(entry["notes"]) if entry else []


def full_panel_report(session, evidence_log):
    """
    The complete evidence panel for a session: build_evidence_panel()'s
    per-item fields, plus current_label (accounting for any revisions),
    notes, and revision_history layered in from evidence_log.

    Returns:
        dict: {distractor_id: {original_answer, assigned_label (as
        recorded live), current_label (after any revisions), ai_label,
        reason, notes, revision_history, question_id, topic}}
    """
    panel = build_evidence_panel(session)
    for did, item in panel.items():
        item["current_label"]    = current_label(evidence_log, session, did)
        item["notes"]            = get_notes(evidence_log, did)
        item["revision_history"] = get_revision_history(evidence_log, did)
    return panel


def load_evidence_log(path):
    """Load an evidence log from disk, or return {} if the file doesn't exist yet."""
    if not os.path.exists(path):
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}


def save_evidence_log(evidence_log, path):
    """Write an evidence log to disk as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(evidence_log, f, indent=2)
    return path
