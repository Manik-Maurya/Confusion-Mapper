"""
Assist mode: AI suggests a category (with confidence and reasoning, plus
the nearest already-coded examples from a persistent index if you point
one at it), the human accepts or overrides. New in v2.6.0.

This is a DIFFERENT workflow from run_session() / main(), on purpose, and
the two are never reachable through the same entry point (see cli.py's
run() -- "assist" is routed separately from both the JSON stats
subcommands and the blind interactive session). The reason is not
stylistic: run_session() works because the human and AI rate
independently, which is what makes their kappa a meaningful reliability
estimate. Here the AI's opinion is shown to the human before they decide,
on purpose, to make bulk-coding faster -- which means a label produced in
this mode is not independent evidence of anything, and this module never
computes or reports a kappa/AC1/alpha for that reason. What it reports
instead is an acceptance_rate (how often the human kept the AI's
suggestion unchanged) -- a real, honestly-labeled efficiency metric, not
a reliability one. Every session this module produces carries an explicit
reliability_warning string for exactly this reason, so the distinction
survives even if the file is read out of context later.

Intended use: after you've established kappa >= 0.70 with run_session()'s
blind mode and are confident your rubric/AI prompt are solid, use this to
code your actual (larger) dataset faster than one-at-a-time blind rating
would allow.
"""

import csv
import datetime
import json
import os

from .taxonomy import ERROR_TYPES, ASSIST_DATA_FILE
from .ai import OPENAI_AVAILABLE, OpenAI
from .console import get_choice
from .embeddings import load_index, search as index_search

RELIABILITY_WARNING = (
    "This is AI-assisted mode. The human rater saw the AI's suggestion "
    "before deciding, so labels here are NOT independent of the AI and "
    "must not be used to compute or report inter-rater reliability "
    "(kappa / AC1 / alpha). Use run_session() / the blind interactive "
    "session for reliability data."
)


def load_assist_csv(path):
    """
    Load a CSV of items to code in assist mode. Required column:
    distractor_text. Optional columns (used to give the AI better context,
    default to "" if absent): item_id, question_text, correct_answer, topic.

    Returns:
        list[dict]: {item_id, distractor_text, question_text,
        correct_answer, topic} -- item_id defaults to "row_{n}" if the
        column is missing or a cell is empty, so every item always has a
        usable identifier for the embedding index / evidence log.
    """
    items = []
    with open(path, newline="", encoding="utf-8") as f:
        for i, row in enumerate(csv.DictReader(f)):
            items.append({
                "item_id":         (row.get("item_id") or "").strip() or f"row_{i}",
                "distractor_text": row.get("distractor_text", ""),
                "question_text":   row.get("question_text", ""),
                "correct_answer":  row.get("correct_answer", ""),
                "topic":           row.get("topic", ""),
            })
    return items


def classify_with_confidence(question_text, correct_answer, distractor_text, topic, api_key):
    """
    Like ai.classify_with_ai(), but also asks for a confidence score. A
    separate function rather than an extension of classify_with_ai()
    itself, specifically so the prompt sent to OpenAI during a live
    blind-mode reliability-check session never changes -- ai.py stays
    exactly as it was.

    Returns:
        dict with keys: label (str), confidence (float 0-1 or None),
        reasoning (str), available (bool)
    """
    if not OPENAI_AVAILABLE:
        return {"label": "N/A", "confidence": None,
               "reasoning": "OpenAI library not installed. Run: pip install openai",
               "available": False}
    if not api_key:
        return {"label": "N/A", "confidence": None,
               "reasoning": "No API key. Set OPENAI_API_KEY environment variable.",
               "available": False}

    system_prompt = """You are a cognitive scientist specializing in educational psychology.
You classify MCQ distractor options into one of four cognitive error types, and
state how confident you are in that classification.

Definitions:
- RF (Recall Failure): Answer is random, implausible, or reflects no memory of the topic.
- PK (Partial Knowledge): Almost right, correct direction, but model is incomplete.
- CF (Confabulation): Strong, coherent misconception. Student would select this confidently.
- INT (Interference): Correct answer for a DIFFERENT related topic, cross-topic confusion.

Respond ONLY with valid JSON, no extra text:
{
  "label": "CF",
  "confidence": 0.8,
  "reasoning": "One concise sentence grounded in cognitive science."
}
confidence is your certainty in this label, from 0.0 (little better than a guess,
this item is genuinely ambiguous between two categories) to 1.0 (essentially certain)."""

    user_prompt = (
        f"Topic: {topic}\n"
        f"Question: {question_text}\n"
        f"Correct answer: {correct_answer}\n"
        f"Distractor to classify: {distractor_text}"
    )

    import json as _json
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": system_prompt},
                     {"role": "user", "content": user_prompt}],
            max_tokens=150,
            temperature=0.2,
        )
        parsed = _json.loads(response.choices[0].message.content)
        label = parsed.get("label", "N/A")
        confidence = parsed.get("confidence")
        if label not in ERROR_TYPES:
            label = "N/A"
        return {
            "label":      label,
            "confidence": float(confidence) if confidence is not None else None,
            "reasoning":  parsed.get("reasoning", ""),
            "available":  True,
        }
    except Exception as e:
        return {"label": "N/A", "confidence": None,
               "reasoning": f"AI call failed: {e}", "available": False}


def _print_suggestion(item, suggestion, similar):
    print(f"\n  {item['distractor_text']}")
    if item.get("question_text"):
        print(f"    (Q: {item['question_text']})")
    if not suggestion["available"]:
        print(f"  [AI unavailable: {suggestion['reasoning']}]")
    else:
        conf = suggestion["confidence"]
        conf_str = f"{conf:.0%}" if conf is not None else "n/a"
        print(f"  AI suggests: {suggestion['label']}  (confidence: {conf_str})")
        print(f"    Reasoning: {suggestion['reasoning']}")
    if similar:
        print("  Nearest already-coded examples:")
        for s in similar:
            lbl = s["metadata"].get("label", "?")
            print(f"    [{s['score']:.2f}] ({lbl}) {s['text'][:70]}")


def run_assist_session(items, api_key, rater_id, index_path=None, index_k=5):
    """
    The assist-mode interactive loop: for each item, show the AI's
    suggestion (+ confidence, + reasoning) and, if index_path is given,
    the k nearest already-coded examples from that persistent index. The
    human presses Enter to accept, or types 1-4 to override (a reason is
    then required).

    Args:
        items (list[dict]): as returned by load_assist_csv().
        api_key (str): OpenAI key. Assist mode without a key still runs,
            but every "suggestion" is unavailable and every item is a pure
            manual override -- there's no assistance without a key.
        rater_id (str)
        index_path (str | None): path to a persistent embeddings index
            (see embeddings.py). If given and the file doesn't exist yet,
            a fresh local-backend index is created for retrieval (empty at
            first, so "nearest examples" starts empty and fills in as you
            code -- items are NOT automatically added to this index by
            this function; use `confusion-mapper embed-index build` for
            that, so indexing stays an explicit, separate action).
        index_k (int): how many similar examples to show per item.

    Returns:
        dict: the assist-mode session (see module docstring for why there
        is no kappa/matrix/type_stats key here).
    """
    index = load_index(index_path) if index_path else None
    NUM_TO_CODE = {"1": "RF", "2": "PK", "3": "CF", "4": "INT"}

    decisions = []

    print(f"\n  Assist session: {len(items)} item(s). Enter = accept AI suggestion, "
         f"or type 1=RF 2=PK 3=CF 4=INT to override, Q to stop.\n")

    for item in items:
        suggestion = classify_with_confidence(
            item["question_text"], item["correct_answer"],
            item["distractor_text"], item["topic"], api_key,
        )
        similar = index_search(index, item["distractor_text"], k=index_k) if index else []
        _print_suggestion(item, suggestion, similar)

        if suggestion["available"]:
            raw = get_choice("  [Enter=accept / 1-4=override / Q=quit]: ",
                             {"", "1", "2", "3", "4", "Q"})
        else:
            # Nothing to accept: the AI gave no real suggestion, so this is
            # plain manual coding, not an "override" of anything -- Enter
            # isn't offered as an option here.
            raw = get_choice("  [1-4=your label, no AI suggestion available / Q=quit]: ",
                             {"1", "2", "3", "4", "Q"})

        if raw == "Q":
            break

        if raw == "":
            # Only reachable when suggestion["available"] is True.
            final_label      = suggestion["label"]
            accepted         = True
            override_reason  = None
        else:
            final_label = NUM_TO_CODE[raw]
            if suggestion["available"]:
                accepted = (final_label == suggestion["label"])
                override_reason = None
                if not accepted:
                    override_reason = input("  Reason for overriding the AI: ").strip()
                    while not override_reason:
                        override_reason = input("  A reason is required: ").strip()
            else:
                # No suggestion existed, so "accepted"/"overridden" isn't a
                # meaningful distinction here -- this is just a label, not
                # counted in acceptance_rate at all (see below).
                accepted = None
                override_reason = None

        decisions.append({
            "item_id":          item["item_id"],
            "distractor_text":  item["distractor_text"],
            "ai_label":         suggestion["label"],
            "ai_confidence":    suggestion["confidence"],
            "ai_reasoning":     suggestion["reasoning"],
            "ai_available":     suggestion["available"],
            "human_label":      final_label,
            "accepted":         accepted,
            "override_reason":  override_reason,
        })

    n_decided           = len(decisions)
    n_with_suggestion    = sum(1 for d in decisions if d["ai_available"])
    n_accepted           = sum(1 for d in decisions if d["accepted"] is True)
    session = {
        "mode":                       "ai_assisted",
        "reliability_warning":        RELIABILITY_WARNING,
        "rater_id":                   rater_id,
        "date":                       datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_items_offered":            len(items),
        "n_items_decided":            n_decided,
        "n_items_with_ai_suggestion": n_with_suggestion,
        "acceptance_rate":            round(n_accepted / n_with_suggestion, 4)
                                       if n_with_suggestion else None,
        "decisions":                  decisions,
    }
    return session


def load_assist_sessions(path=ASSIST_DATA_FILE):
    """
    Load previously saved assist-mode sessions. Deliberately a separate
    function from storage.load_sessions() against a separate file
    (ASSIST_DATA_FILE, not DATA_FILE) -- so there is no code path by which
    an assist-mode session and a blind reliability-check session ever end
    up read together as if they were the same kind of data.
    """
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_assist_session(session, path=ASSIST_DATA_FILE):
    """Append an assist-mode session to ASSIST_DATA_FILE (or `path`)."""
    sessions = load_assist_sessions(path)
    sessions.append(session)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(sessions, f, indent=2)
    return path
