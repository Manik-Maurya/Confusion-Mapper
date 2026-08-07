"""
Evidence panel. For each coded item, the answer text, the label given,
the AI reasoning if any, free-text notes, and every revision that was
made afterward.

The rule I enforce here: revising a label never rewrites history. The
old value stays, the new value is added on top, and the reason is
required. This is meant for the review phase, not for live coding, so
it deliberately does not touch the session file it reads from.
"""

import datetime
import json
import os


def build_evidence_panel(session):
    """
    Turn a session's `ratings` list into one entry per distractor.

    This function only reads from the session, no notes or revisions yet.
    For those, layer on load_evidence_log() and use current_label(),
    get_revision_history(), get_notes() over the same distractor_id.

    Args:
        session (dict): a session dict from run_session() or
            save_session(). Needs a "ratings" key.

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
    Add a free-text note to an item. Notes accumulate, nothing here
    ever overwrites a previous note.

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
        reason (str): required. A revision without a reason is the
            exact thing this whole module exists to prevent. Raises
            ValueError if empty.
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
    The item's label right now: newest revision if there is one, else
    the original human_label from the session. Session data is never
    mutated, this is always computed on the fly.
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
