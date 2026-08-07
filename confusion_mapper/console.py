"""
Terminal-only rendering helpers. Coloured headings, a text confusion
matrix, and the summary block printed at the end of a run.

Everything here degrades gracefully if the terminal does not support
ANSI colours. That is on purpose, I test this on a friend's older
Windows laptop and did not want to force him to install anything.
"""

import datetime
import platform
import uuid

from .taxonomy import TAXONOMY, ERROR_TYPES, DATA_FILE, taxonomy_fingerprint
from .ai import classify_with_ai
from .stats import compute_cohens_kappa, build_confusion_matrix, get_per_type_stats
from .storage import load_sessions, installed_package_version



def print_header():
    print()
    print("=" * 66)
    print("  ConfusionMapper  v1.0")
    print("  Distractor Classification & Inter-Rater Reliability Tool")
    print("  Manik Maurya | Independent Researcher, Kanpur, India | 2026")
    print("=" * 66)
    print()


def print_taxonomy_card():
    """Print the taxonomy reference card to console."""
    print()
    print("─" * 66)
    print("  TAXONOMY REFERENCE, Four Cognitive Error Types")
    print("─" * 66)
    for code in ERROR_TYPES:
        t = TAXONOMY[code]
        print(f"  [{t['number']}] {code}, {t['name']}")
        print(f"      {t['definition']}")
        print(f"      Example: {t['example']}")
        print()


def get_choice(prompt, valid):
    """Keep prompting until the user gives a valid choice."""
    while True:
        raw = input(prompt).strip().upper()
        if raw in valid:
            return raw
        print(f"  Please enter one of: {', '.join(valid)}")


def run_session(questions, api_key, rater_id):
    """
    Run a full classification session: show each distractor, collect human
    and AI labels, return full session dict + computed statistics.
    """
    print_taxonomy_card()

    n_distractors = sum(len(q["distractors"]) for q in questions)
    rated          = 0
    human_labels   = []
    ai_labels      = []
    ratings        = []

    print(f"  Session: {len(questions)} question(s), {n_distractors} distractor(s)")
    print("  For each distractor enter: 1=RF  2=PK  3=CF  4=INT  ?=definitions\n")

    NUM_TO_CODE = {"1": "RF", "2": "PK", "3": "CF", "4": "INT"}

    for qi, question in enumerate(questions):
        print("─" * 66)
        print(f"  Question {qi + 1}/{len(questions)}  [{question['topic']}]")
        print(f"  Q: {question['question_text']}")
        print(f"  Correct answer: {question['correct_answer']}\n")

        for di, d in enumerate(question["distractors"]):
            rated += 1
            print(f"  Distractor {di + 1}/{len(question['distractors'])}"
                  f"  ({rated}/{n_distractors} total)")
            print(f"  Wrong option: \"{d['option']}\"\n")

            # human picks first, before we ever call the model
            while True:
                c = input("  Your classification [1/2/3/4/?]: ").strip().upper()
                if c == "?":
                    print_taxonomy_card()
                    continue
                if c in NUM_TO_CODE:
                    h_label = NUM_TO_CODE[c]
                    break
                if c in ERROR_TYPES:
                    h_label = c
                    break
                print("  Enter 1, 2, 3, or 4")

            human_labels.append(h_label)

            # only now do we ask the AI, so the human's decision was blind
            ai_res = {"label": "N/A", "reasoning": "", "available": False}
            if api_key:
                print("  [Asking AI rater...]", end="", flush=True)
                ai_res = classify_with_ai(
                    question["question_text"],
                    question["correct_answer"],
                    d["option"],
                    question["topic"],
                    api_key,
                )

            a_label = ai_res["label"]
            ai_labels.append(a_label)

            # show both labels side by side
            if ai_res["available"] and a_label != "N/A":
                symbol = "AGREE   " if h_label == a_label else "X DISAGREE"
                print(f" AI -> {a_label}")
                print(f"  {symbol}  You: {h_label}  AI: {a_label}")
                if ai_res.get("reasoning"):
                    print(f"  AI reasoning: {ai_res['reasoning']}")
            else:
                print()
                print(f"  Your label: {h_label}  (AI unavailable, manual mode)")

            # Ground-truth check (built-in questions have reference labels)
            ref = d.get("error_type", "")
            if ref:
                mark = "" if h_label == ref else "X"
                print(f"  Reference label: {ref}  (your answer {mark})")

            ratings.append({
                "distractor_id":  f"{question['id']}_D{di + 1}",
                "question_id":    question["id"],
                "topic":          question["topic"],
                "distractor_text":d["option"],
                "human_label":    h_label,
                "ai_label":       a_label,
                "ai_reasoning":   ai_res.get("reasoning", ""),
                "ai_available":   ai_res["available"],
                "reference_label":ref,
                "agreement":      (h_label == a_label) if ai_res["available"] else None,
            })
            print()

    # compute the stats. if the AI answered anything at all, use those
    # as rater 2. if not (offline mode), fall back to the reference labels
    # that ship with the built-in question bank.
    valid_pairs = [(h, a) for h, a in zip(human_labels, ai_labels) if a != "N/A"]

    if valid_pairs:
        hl = [p[0] for p in valid_pairs]
        al = [p[1] for p in valid_pairs]
    else:
        hl = [r["human_label"]     for r in ratings if r["reference_label"]]
        al = [r["reference_label"] for r in ratings if r["reference_label"]]

    kappa       = compute_cohens_kappa(hl, al)
    matrix      = build_confusion_matrix(hl, al)
    type_stats  = get_per_type_stats(hl, al)

    session = {
        "session_id":  str(uuid.uuid4()),
        "rater_id":    rater_id,
        "date":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_questions": len(questions),
        "n_distractors": n_distractors,
        "ratings":     ratings,
        "kappa":       kappa,
        "matrix":      matrix,
        "type_stats":  type_stats,
        "ai_mode":     bool(api_key and any(r["ai_available"] for r in ratings)),
        "software_version":     installed_package_version(),
        "taxonomy_fingerprint": taxonomy_fingerprint(),
        "python_version":       platform.python_version(),
    }

    return session, kappa, matrix, type_stats


def print_summary(kappa, type_stats, session):
    """Print a full text summary of the session results."""
    print()
    print("=" * 66)
    print("  SESSION COMPLETE")
    print("=" * 66)
    print()
    print(f"  Rater: {session['rater_id']}   Date: {session['date']}")
    print(f"  Distractors classified: {kappa['n']}")
    print()
    print(f"  COHEN'S KAPPA:  kappa = {kappa['kappa']:.4f}")
    print(f"  {kappa['interpretation']}")
    print(f"  Observed agreement:  {kappa['po']:.1%}")
    print(f"  Expected by chance:  {kappa['pe']:.1%}")
    print(f"  Agreements:  {kappa['agreements']} / {kappa['n']}")
    print()
    print("  Agreement by error type:")
    for label in ERROR_TYPES:
        s   = type_stats[label]
        bar = "█" * (s["pct"] // 5) + "░" * (20 - s["pct"] // 5)
        tag = " <-" if s["pct"] >= 70 else ""
        print(f"  {label}  {bar}  {s['pct']:3d}%  "
              f"({s['agreed']}/{s['total']}){tag}")
    print()

    k = kappa["kappa"]
    if k >= 0.70:
        print("  RESEARCH READY: Proceed with human-human validation.")
    elif k >= 0.60:
        print("  ⚠ CLOSE: Review CF/RF boundary cases and re-pilot.")
    else:
        print("  X REVISE RUBRIC before using this taxonomy in research.")
        print("    Common issues: CF vs RF (is the answer plausible?)")
        print("                  PK vs CF (is the wrong direction obvious?)")
    print()
    print("─" * 66)
    print("  ETHICS NOTE")
    print("  ChatGPT may appear artificially reliable because its training")
    print("  data includes cognitive science literature. This tool gives a")
    print("  preliminary signal, it does not replace two trained human")
    print("  raters classifying independently. Always run human-human")
    print("  inter-rater validation (kappa >= 0.70) before data collection.")
    print("─" * 66)


def view_past_sessions():
    """Print a summary list of all past sessions."""
    all_s = load_sessions()
    if not all_s:
        print("\n  No past sessions found.\n")
        return
    print(f"\n  {len(all_s)} past session(s) in {DATA_FILE}:\n")
    for i, s in enumerate(all_s, 1):
        k = s.get("kappa", {})
        print(f"  [{i}]  {s.get('date','-')}  |  "
              f"Rater: {s.get('rater_id','?')}  |  "
              f"kappa = {k.get('kappa', 0):.3f}  |  "
              f"{s.get('n_distractors', 0)} distractors")
        print(f"       {k.get('interpretation','')}")
    print()


