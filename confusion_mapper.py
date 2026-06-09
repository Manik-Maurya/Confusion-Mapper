"""
==============================================================================
ConfusionMapper v1.0
==============================================================================
AI-Assisted Distractor Classification & Inter-Rater Reliability Tool
for Educational Research

Built for Stanford Code in Place 2026 — Final Project
Manik Maurya · IIT Kanpur Cognitive Science (Research Intern)

WHAT THIS DOES
--------------
In educational research, MCQ distractors (wrong answer options) reveal HOW
a student is thinking — not just THAT they got it wrong. This tool classifies
each distractor into one of four cognitive error types:

  RF  — Recall Failure     (no memory trace; random or implausible answer)
  PK  — Partial Knowledge  (almost right; correct direction, incomplete model)
  CF  — Confabulation      (confident wrong belief; coherent misconception)
  INT — Interference       (correct answer for a DIFFERENT topic)

A human researcher and an AI independently classify each distractor.
Cohen's Kappa (κ) measures their agreement. Research target: κ ≥ 0.70.

USAGE
-----
  python confusion_mapper.py

  Optional — enable AI rater mode:
    export OPENAI_API_KEY="your-key-here"   (Mac/Linux)
    set OPENAI_API_KEY=your-key-here        (Windows)

RESEARCH CONTEXT
----------------
This tool is the pre-data-collection quality gate for "The Confusion
Fingerprint Study" — a pre-registered three-arm RCT (n=108) at IIT Kanpur
testing whether classifying the cognitive TYPE of a student error produces
better 2-week delayed retention than correctness-only adaptive learning.

The Confusion Fingerprint Index (CFI):
  CFI-CF  = CF errors / total errors        [primary predictor]
  CFI-INT = INT errors / (INT + RF errors)  [secondary predictor]
  CFI-RF  = RF errors / total errors        [weak/null predictor]

Cohen's Kappa formula:  κ = (Po - Pe) / (1 - Pe)
  Po = observed proportional agreement
  Pe = agreement expected by chance

REQUIREMENTS
------------
  Python 3.8+
  tkinter (built into Python — no install needed)
  openai  (optional: pip install openai — for AI rater mode)

==============================================================================
"""

import os
import json
import math
import datetime
import tkinter as tk

# Graceful fallback if openai not installed
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Graceful fallback if tkinter display not available
try:
    _test = tk.Tk()
    _test.destroy()
    TKINTER_AVAILABLE = True
except Exception:
    TKINTER_AVAILABLE = False


# ==============================================================================
# SECTION 1 — CONSTANTS & TAXONOMY DEFINITIONS
# ==============================================================================

APP_VERSION  = "1.0"
DATA_FILE    = "confusion_mapper_sessions.json"
ERROR_TYPES  = ["RF", "PK", "CF", "INT"]

# Full taxonomy — used for on-screen reference and ChatGPT prompting
TAXONOMY = {
    "RF": {
        "name":      "Recall Failure",
        "number":    "1",
        "definition": (
            "No consolidated memory trace. The answer is random, implausible, "
            "or reflects explicit uncertainty. The student simply has no encoding."
        ),
        "example":   "Answering 'mitochondria' to a photosynthesis question — no logical link.",
        "color":     "#4a90d9",
    },
    "PK": {
        "name":      "Partial Knowledge",
        "number":    "2",
        "definition": (
            "Correct direction but incomplete model. Student is 'almost right' — "
            "the concept is partially encoded. Scaffolding resolves this quickly."
        ),
        "example":   "Knowing photosynthesis needs sunlight, but not that it produces oxygen.",
        "color":     "#f5a623",
    },
    "CF": {
        "name":      "Confabulation",
        "number":    "3",
        "definition": (
            "Strong incorrect belief — a documented misconception. The student selects "
            "with moderate-to-high confidence. The wrong answer is coherent and plausible."
        ),
        "example":   "Believing plants get food from soil because 'roots absorb nutrients'.",
        "color":     "#e74c3c",
    },
    "INT": {
        "name":      "Interference",
        "number":    "4",
        "definition": (
            "Correct answer for a DIFFERENT topic. Well-encoded knowledge from Topic A "
            "fires incorrectly in response to a Topic B question."
        ),
        "example":   "Answering 'chloroplast' (correct for photosynthesis) to a cellular-respiration question.",
        "color":     "#9b59b6",
    },
}

# ==============================================================================
# SECTION 2 — BUILT-IN QUESTION BANK (NCERT-style, 5 questions, 15 distractors)
# Works completely offline — no CSV, no internet required.
# ==============================================================================

BUILTIN_QUESTIONS = [
    {
        "id":            "Q001",
        "topic":         "Photosynthesis",
        "class_level":   7,
        "question_text": "Where does photosynthesis primarily take place in a plant cell?",
        "correct_answer":"Chloroplast",
        "distractors": [
            {
                "option":     "Mitochondria",
                "error_type": "CF",
                "note":       "Student confuses the 'powerhouse' organelle — coherent but wrong",
            },
            {
                "option":     "Cell wall",
                "error_type": "PK",
                "note":       "Knows chlorophyll is in the cell somewhere but misses the organelle",
            },
            {
                "option":     "Vacuole",
                "error_type": "RF",
                "note":       "Random implausible guess — no logical connection",
            },
        ],
    },
    {
        "id":            "Q002",
        "topic":         "Nutrition in Plants",
        "class_level":   7,
        "question_text": "What gas do plants absorb from the atmosphere during photosynthesis?",
        "correct_answer":"Carbon dioxide (CO2)",
        "distractors": [
            {
                "option":     "Oxygen (O2)",
                "error_type": "CF",
                "note":       "Classic misconception — students confuse what plants absorb vs release",
            },
            {
                "option":     "Nitrogen (N2)",
                "error_type": "RF",
                "note":       "Random guess — no logical connection to photosynthesis",
            },
            {
                "option":     "Carbon monoxide (CO)",
                "error_type": "PK",
                "note":       "Student knows 'carbon' is involved but lacks the complete formula",
            },
        ],
    },
    {
        "id":            "Q003",
        "topic":         "Nutrition in Animals",
        "class_level":   7,
        "question_text": "Which organ in humans primarily digests proteins?",
        "correct_answer":"Stomach",
        "distractors": [
            {
                "option":     "Small intestine",
                "error_type": "INT",
                "note":       "Interference — small intestine digests fats, studied in the same session",
            },
            {
                "option":     "Liver",
                "error_type": "CF",
                "note":       "Confabulation — liver is prominent so students assign it all digestion",
            },
            {
                "option":     "Kidney",
                "error_type": "RF",
                "note":       "Recall Failure — just a body organ, no logical connection",
            },
        ],
    },
    {
        "id":            "Q004",
        "topic":         "Light and Optics",
        "class_level":   8,
        "question_text": "What happens to light when it moves from air into glass?",
        "correct_answer":"It slows down and bends toward the normal (refracts)",
        "distractors": [
            {
                "option":     "It speeds up and bends away from the normal",
                "error_type": "CF",
                "note":       "Common misconception — students reverse both the speed and direction",
            },
            {
                "option":     "It travels in the same direction but slower",
                "error_type": "PK",
                "note":       "Partial — knows it slows down but misses the bending/refraction part",
            },
            {
                "option":     "It reflects back into air",
                "error_type": "INT",
                "note":       "Interference — reflection was studied in the same optics unit",
            },
        ],
    },
    {
        "id":            "Q005",
        "topic":         "Motion and Time",
        "class_level":   7,
        "question_text": "A car travels 60 km in 2 hours. What is its average speed?",
        "correct_answer":"30 km/h",
        "distractors": [
            {
                "option":     "120 km/h",
                "error_type": "CF",
                "note":       "Confabulation — student multiplies instead of divides (inverted formula)",
            },
            {
                "option":     "60 km/h",
                "error_type": "PK",
                "note":       "Partial — knows speed involves distance but ignores the time divisor",
            },
            {
                "option":     "62 km/h",
                "error_type": "RF",
                "note":       "Recall Failure — random number, no formula applied at all",
            },
        ],
    },
]


# ==============================================================================
# SECTION 3 — COHEN'S KAPPA & STATISTICS
# ==============================================================================

def compute_cohens_kappa(human_labels, ai_labels):
    """
    Compute Cohen's Kappa between two raters.

    Formula:   κ = (Po - Pe) / (1 - Pe)

    Po = observed proportional agreement (how often both raters agreed)
    Pe = expected agreement by chance (product of marginal proportions)

    Interpretation guide:
      κ < 0.20       Slight
      0.20 – 0.40    Fair
      0.40 – 0.60    Moderate
      0.60 – 0.80    Substantial  ← research target is κ ≥ 0.70
      0.80 – 1.00    Almost Perfect

    Args:
        human_labels (list): e.g. ["CF", "RF", "INT", "PK", ...]
        ai_labels    (list): same length as human_labels

    Returns:
        dict with kappa, interpretation, po, pe, n, agreements
    """
    n = len(human_labels)
    if n == 0:
        return {
            "kappa": 0.0,
            "interpretation": "No data to compute kappa.",
            "po": 0.0, "pe": 0.0,
            "n": 0, "agreements": 0,
        }

    # Po — observed agreement
    agreements = sum(1 for h, a in zip(human_labels, ai_labels) if h == a)
    po = agreements / n

    # Pe — expected agreement by chance
    # For each error type: (proportion human chose it) * (proportion AI chose it)
    pe = 0.0
    for label in ERROR_TYPES:
        p_human = human_labels.count(label) / n
        p_ai    = ai_labels.count(label)    / n
        pe     += p_human * p_ai

    # Kappa — guarded against division by zero
    if pe >= 1.0:
        kappa = 1.0
    else:
        kappa = (po - pe) / (1.0 - pe)

    # Interpretation
    if kappa < 0.20:
        interp = "Slight — rubric needs substantial revision before research use."
    elif kappa < 0.40:
        interp = "Fair — significant revision needed. Review CF vs RF boundary."
    elif kappa < 0.60:
        interp = "Moderate — improvement needed. Target is κ ≥ 0.70."
    elif kappa < 0.70:
        interp = "Substantial — close to target. Refine ambiguous cases."
    elif kappa < 0.80:
        interp = "Substantial ✓ — research threshold reached! Proceed with validation."
    else:
        interp = "Almost Perfect ✓ — excellent agreement."

    return {
        "kappa":          round(kappa, 4),
        "interpretation": interp,
        "po":             round(po, 4),
        "pe":             round(pe, 4),
        "n":              n,
        "agreements":     agreements,
    }


def build_confusion_matrix(human_labels, ai_labels):
    """
    Build a 4×4 confusion matrix.
    Rows = human labels, Columns = AI labels.
    Returns a nested dict: matrix[human_label][ai_label] = count.
    """
    matrix = {row: {col: 0 for col in ERROR_TYPES} for row in ERROR_TYPES}
    for h, a in zip(human_labels, ai_labels):
        if h in matrix and a in matrix[h]:
            matrix[h][a] += 1
    return matrix


def get_per_type_stats(human_labels, ai_labels):
    """
    Compute agreement percentage per error type.
    Returns dict: type_code → {total, agreed, pct}
    """
    stats = {}
    for label in ERROR_TYPES:
        indices = [i for i, h in enumerate(human_labels) if h == label]
        if not indices:
            stats[label] = {"total": 0, "agreed": 0, "pct": 0}
        else:
            agreed = sum(1 for i in indices if ai_labels[i] == label)
            stats[label] = {
                "total":  len(indices),
                "agreed": agreed,
                "pct":    round((agreed / len(indices)) * 100),
            }
    return stats


# ==============================================================================
# SECTION 4 — CHATGPT / AI RATER
# ==============================================================================

def classify_with_ai(question_text, correct_answer, distractor_text, topic, api_key):
    """
    Ask ChatGPT to classify a single distractor as RF / PK / CF / INT.

    The model is prompted as a cognitive scientist. Temperature is kept low
    (0.2) for consistent, reproducible classifications.

    Returns:
        dict with keys: label (str), reasoning (str), available (bool)
    """
    # Graceful degradation
    if not OPENAI_AVAILABLE:
        return {
            "label": "N/A",
            "reasoning": "OpenAI library not installed. Run: pip install openai",
            "available": False,
        }
    if not api_key:
        return {
            "label": "N/A",
            "reasoning": "No API key. Set OPENAI_API_KEY environment variable.",
            "available": False,
        }

    system_prompt = """You are a cognitive scientist specializing in educational psychology.
You classify MCQ distractor options into one of four cognitive error types.

Definitions:
- RF (Recall Failure): Answer is random, implausible, or reflects no memory of the topic.
- PK (Partial Knowledge): Almost right — correct direction, but model is incomplete.
- CF (Confabulation): Strong, coherent misconception. Student would select this confidently.
- INT (Interference): Correct answer for a DIFFERENT related topic — cross-topic confusion.

Respond ONLY with valid JSON, no extra text:
{
  "label": "CF",
  "reasoning": "One concise sentence grounded in cognitive science."
}"""

    user_prompt = (
        f"Topic: {topic}\n"
        f"Question: {question_text}\n"
        f"Correct answer: {correct_answer}\n"
        f"Distractor to classify: {distractor_text}"
    )

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model       = "gpt-3.5-turbo",
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens  = 120,
            temperature = 0.2,
        )
        raw = response.choices[0].message.content.strip()

        # Strip markdown fences if present
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        result = json.loads(raw)
        if result.get("label") not in ERROR_TYPES:
            result["label"] = "RF"  # safe default
        result["available"] = True
        return result

    except json.JSONDecodeError:
        return {
            "label": "RF",
            "reasoning": f"Could not parse AI response.",
            "available": True,
        }
    except Exception as e:
        return {
            "label": "N/A",
            "reasoning": f"API error: {str(e)[:80]}",
            "available": False,
        }


def generate_ai_questions(topic, n, api_key):
    """
    Use ChatGPT to generate n MCQ questions with labeled distractors on topic.
    Returns list of question dicts matching BUILTIN_QUESTIONS format, or [] on failure.
    """
    if not OPENAI_AVAILABLE or not api_key:
        return []

    system_prompt = """You are an educational psychologist creating MCQ questions.
For each question, provide exactly 3 distractors, each with a cognitive error type label.

Types: RF (random/implausible), PK (almost right), CF (confident misconception), INT (topic interference).

Return ONLY a valid JSON array:
[
  {
    "id": "GQ001",
    "topic": "topic name",
    "class_level": 8,
    "question_text": "...",
    "correct_answer": "...",
    "distractors": [
      {"option": "...", "error_type": "CF", "note": "brief explanation"},
      {"option": "...", "error_type": "RF", "note": "brief explanation"},
      {"option": "...", "error_type": "PK", "note": "brief explanation"}
    ]
  }
]"""

    user_prompt = (
        f"Generate {n} MCQ question(s) on: {topic}. "
        f"Target Class 7-8 Indian students. Make distractors realistic and pedagogically interesting."
    )

    try:
        client   = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model       = "gpt-3.5-turbo",
            messages    = [
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            max_tokens  = 2000,
            temperature = 0.7,
        )
        raw = response.choices[0].message.content.strip()
        if "```" in raw:
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        return json.loads(raw)
    except Exception as e:
        print(f"  [Question generation error: {str(e)[:80]}]")
        return []


# ==============================================================================
# SECTION 5 — DATA PERSISTENCE (file I/O)
# ==============================================================================

def load_sessions():
    """Load all saved sessions from the JSON data file."""
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_session(session):
    """Append a completed session dict to the JSON data file."""
    sessions = load_sessions()
    sessions.append(session)
    with open(DATA_FILE, "w") as f:
        json.dump(sessions, f, indent=2)


# ==============================================================================
# SECTION 6 — TKINTER VISUALISATION (3 panels)
# ==============================================================================

# Colour palette — dark academic aesthetic
C = {
    "bg":      "#0a0a14",
    "panel":   "#10101e",
    "border":  "#2a2a40",
    "gold":    "#c9a84c",
    "cream":   "#e8e0cc",
    "dim":     "#666688",
    "agree":   "#27ae60",
    "disagree":"#c0392b",
    "RF":      "#4a90d9",
    "PK":      "#f5a623",
    "CF":      "#e74c3c",
    "INT":     "#9b59b6",
    "z0":      "#c0392b",  # kappa zone: Slight
    "z1":      "#e67e22",  # kappa zone: Fair
    "z2":      "#f1c40f",  # kappa zone: Moderate
    "z3":      "#2ecc71",  # kappa zone: Substantial
    "z4":      "#c9a84c",  # kappa zone: Almost Perfect
}


def show_results_window(kappa, matrix, type_stats, session):
    """
    Open the results window with three side-by-side panels:
      Panel 1 — Kappa Gauge (semicircular speedometer)
      Panel 2 — Confusion Matrix (4×4 grid, human vs AI)
      Panel 3 — Per-type Agreement (horizontal bar chart)
    """
    if not TKINTER_AVAILABLE:
        print("  (tkinter display unavailable — skipping visualisation)")
        return

    root = tk.Tk()
    root.title("ConfusionMapper — Session Results")
    root.configure(bg=C["bg"])
    root.geometry("1000x700")
    root.resizable(False, False)

    # ── Title ───────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg=C["bg"])
    header.pack(fill="x", pady=10)

    tk.Label(header, text="ConfusionMapper · Session Results",
             bg=C["bg"], fg=C["gold"],
             font=("Courier", 15, "bold")).pack()

    tk.Label(header,
             text=(f"Rater: {session.get('rater_id','—')}  ·  "
                   f"Questions: {session.get('n_questions',0)}  ·  "
                   f"Distractors rated: {kappa['n']}  ·  "
                   f"Date: {session.get('date','—')}"),
             bg=C["bg"], fg=C["dim"],
             font=("Courier", 10)).pack()

    # ── Three columns ───────────────────────────────────────────────────────
    body = tk.Frame(root, bg=C["bg"])
    body.pack(fill="both", expand=True, padx=14, pady=4)

    def make_panel(parent):
        frame = tk.Frame(parent, bg=C["panel"],
                         highlightbackground=C["border"],
                         highlightthickness=1)
        frame.pack(side="left", fill="both", expand=True, padx=8, pady=4)
        return frame

    p1 = make_panel(body)
    p2 = make_panel(body)
    p3 = make_panel(body)

    _draw_kappa_gauge(p1, kappa)
    _draw_confusion_matrix(p2, matrix)
    _draw_bar_chart(p3, type_stats)

    # ── Ethics note ─────────────────────────────────────────────────────────
    tk.Label(
        root,
        text=(
            "Ethics note: AI classifications are a starting point, not a substitute for human-human validation.\n"
            "Always verify κ ≥ 0.70 between two trained human raters before using labels in published research."
        ),
        bg=C["bg"], fg=C["dim"],
        font=("Courier", 9), justify="center",
    ).pack(pady=4)

    tk.Button(root, text="Close", command=root.destroy,
              bg=C["gold"], fg=C["bg"],
              font=("Courier", 11, "bold"),
              relief="flat", padx=20, pady=6,
              cursor="hand2").pack(pady=8)

    root.mainloop()


def _draw_kappa_gauge(parent, kappa):
    """Semicircular speedometer. Needle angle encodes κ value."""
    tk.Label(parent, text="COHEN'S KAPPA",
             bg=C["panel"], fg=C["gold"],
             font=("Courier", 11, "bold")).pack(pady=(14, 2))
    tk.Label(parent, text="Human vs. AI Agreement",
             bg=C["panel"], fg=C["dim"],
             font=("Courier", 9)).pack()

    cvs = tk.Canvas(parent, width=290, height=210,
                    bg=C["panel"], highlightthickness=0)
    cvs.pack(padx=10, pady=8)

    cx, cy = 145, 168  # Arc centre (bottom-centre of canvas)
    r_out  = 115       # Outer radius
    r_in   = 72        # Inner radius (creates ring look via overlay)
    ring_w = 22        # Arc stroke width

    # Five coloured zone arcs — κ zones: 0.0, 0.20, 0.40, 0.70, 0.80, 1.0
    # In tkinter: angle 0° = 3 o'clock, increases counter-clockwise.
    # We want κ=0 at 180° (9 o'clock) and κ=1 at 0° (3 o'clock).
    # A value κ maps to start_angle = 180 − κ×180.
    zones = [
        (0.00, 0.20, C["z0"]),
        (0.20, 0.40, C["z1"]),
        (0.40, 0.70, C["z2"]),
        (0.70, 0.80, C["z3"]),
        (0.80, 1.00, C["z4"]),
    ]

    for k0, k1, colour in zones:
        # start = leftmost angle of this zone
        start  =  180 - k0 * 180
        extent = -(k1 - k0) * 180   # negative → clockwise
        cvs.create_arc(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                       start=start, extent=extent,
                       style="arc", outline=colour, width=ring_w)

    # Dark overlay ring to create "donut" appearance
    cvs.create_arc(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                   start=180, extent=-180,
                   style="arc", outline=C["panel"], width=ring_w - 4)

    # Target line at κ = 0.70
    t_angle_deg = 180 - 0.70 * 180   # = 54°
    t_rad        = math.radians(t_angle_deg)
    t_x_out = cx + (r_out + 4) * math.cos(t_rad)
    t_y_out = cy - (r_out + 4) * math.sin(t_rad)
    t_x_in  = cx + (r_in  - 4) * math.cos(t_rad)
    t_y_in  = cy - (r_in  - 4) * math.sin(t_rad)
    cvs.create_line(t_x_in, t_y_in, t_x_out, t_y_out,
                    fill="white", width=2, dash=(4, 3))
    cvs.create_text(t_x_out - 2, t_y_out - 14,
                    text="0.70\ntarget", fill="white",
                    font=("Courier", 7), justify="center")

    # Needle
    k_val  = max(0.0, min(1.0, kappa["kappa"]))
    n_deg  = 180 - k_val * 180
    n_rad  = math.radians(n_deg)
    n_len  = r_in - 8
    nx = cx + n_len * math.cos(n_rad)
    ny = cy - n_len * math.sin(n_rad)
    cvs.create_line(cx, cy, nx, ny, fill="white", width=3, capstyle="round")
    cvs.create_oval(cx - 6, cy - 6, cx + 6, cy + 6,
                    fill=C["gold"], outline="")

    # κ value centred inside gauge
    k_colour = (C["z4"] if k_val >= 0.80 else
                C["z3"] if k_val >= 0.70 else
                C["z2"] if k_val >= 0.40 else
                C["z1"] if k_val >= 0.20 else C["z0"])

    cvs.create_text(cx, cy - 30, text=f"κ = {k_val:.3f}",
                    fill=k_colour, font=("Courier", 18, "bold"))

    # End labels
    cvs.create_text(cx - r_out + 6,  cy + 14, text="0.0",
                    fill=C["dim"], font=("Courier", 8))
    cvs.create_text(cx + r_out - 6, cy + 14, text="1.0",
                    fill=C["dim"], font=("Courier", 8))

    # Interpretation text
    tk.Label(parent, text=kappa["interpretation"],
             bg=C["panel"], fg=k_colour,
             font=("Courier", 9, "bold"),
             wraplength=250, justify="center").pack()

    tk.Label(parent,
             text=(f"Po (observed) = {kappa['po']:.1%}   "
                   f"Pe (chance) = {kappa['pe']:.1%}\n"
                   f"Agreements: {kappa['agreements']} / {kappa['n']}"),
             bg=C["panel"], fg=C["dim"],
             font=("Courier", 8), justify="center").pack(pady=4)


def _draw_confusion_matrix(parent, matrix):
    """4×4 grid. Diagonal cells = agreement (green); off-diagonal = disagreement (red)."""
    tk.Label(parent, text="CONFUSION MATRIX",
             bg=C["panel"], fg=C["gold"],
             font=("Courier", 11, "bold")).pack(pady=(14, 2))
    tk.Label(parent, text="Rows: Human   Columns: AI",
             bg=C["panel"], fg=C["dim"],
             font=("Courier", 9)).pack(pady=(0, 8))

    cvs = tk.Canvas(parent, width=290, height=250,
                    bg=C["panel"], highlightthickness=0)
    cvs.pack(padx=10)

    cs    = 50     # cell size in pixels
    ox    = 55     # x origin (left margin for row labels)
    oy    = 40     # y origin (top margin for col headers)

    # Column headers (AI)
    cvs.create_text(ox + 2 * cs, oy - 22,
                    text="← AI Classification →",
                    fill=C["dim"], font=("Courier", 8))
    for j, col in enumerate(ERROR_TYPES):
        cvs.create_text(ox + j * cs + cs // 2, oy - 8,
                        text=col, fill=C[col],
                        font=("Courier", 10, "bold"))

    # Row header (Human) — vertical text simulation
    for char_i, ch in enumerate("Human↓"):
        cvs.create_text(18, oy + 40 + char_i * 11,
                        text=ch, fill=C["dim"],
                        font=("Courier", 8))

    # Cells
    for i, row in enumerate(ERROR_TYPES):
        y = oy + i * cs

        # Row label
        cvs.create_text(ox - 12, y + cs // 2,
                        text=row, fill=C[row],
                        font=("Courier", 10, "bold"))

        for j, col in enumerate(ERROR_TYPES):
            x     = ox + j * cs
            count = matrix[row][col]
            diag  = (i == j)

            bg_col = ("#182d1e" if diag and count > 0 else
                      "#2d1818" if (not diag) and count > 0 else
                      "#0e0e1c")
            fg_col = (C["agree"]   if diag else
                      C["disagree"] if count > 0 else C["dim"])

            cvs.create_rectangle(x + 2, y + 2,
                                  x + cs - 2, y + cs - 2,
                                  fill=bg_col, outline=C["border"])
            cvs.create_text(x + cs // 2, y + cs // 2,
                            text=str(count),
                            fill=fg_col,
                            font=("Courier", 15, "bold") if count > 0
                                 else ("Courier", 11))

    # Legend
    leg_y = oy + 4 * cs + 16
    cvs.create_rectangle(ox + 10, leg_y - 6, ox + 22, leg_y + 6,
                          fill="#182d1e", outline="")
    cvs.create_text(ox + 36, leg_y, text="= Agree",
                    fill=C["agree"], font=("Courier", 8), anchor="w")
    cvs.create_rectangle(ox + 110, leg_y - 6, ox + 122, leg_y + 6,
                          fill="#2d1818", outline="")
    cvs.create_text(ox + 136, leg_y, text="= Disagree",
                    fill=C["disagree"], font=("Courier", 8), anchor="w")


def _draw_bar_chart(parent, type_stats):
    """Horizontal bar chart: % of human labels that AI matched, per type."""
    tk.Label(parent, text="AGREEMENT BY TYPE",
             bg=C["panel"], fg=C["gold"],
             font=("Courier", 11, "bold")).pack(pady=(14, 2))
    tk.Label(parent, text="% of human labels AI confirmed",
             bg=C["panel"], fg=C["dim"],
             font=("Courier", 9)).pack(pady=(0, 8))

    cvs = tk.Canvas(parent, width=290, height=250,
                    bg=C["panel"], highlightthickness=0)
    cvs.pack(padx=10)

    bx      = 62    # bar left edge
    bw_max  = 175   # bar width at 100%
    bh      = 30    # bar height
    gap     = 20    # vertical gap between bars
    start_y = 24    # y of first bar

    # 70% target dashed line
    tx = bx + int(bw_max * 0.70)
    cvs.create_line(tx, start_y - 10, tx,
                    start_y + 4 * (bh + gap) - 4,
                    fill="white", width=1, dash=(4, 3))
    cvs.create_text(tx, start_y - 17, text="70%",
                    fill="white", font=("Courier", 8))

    for i, label in enumerate(ERROR_TYPES):
        y    = start_y + i * (bh + gap)
        stat = type_stats[label]
        pct  = stat["pct"]
        bw   = int(bw_max * pct / 100)

        # Background track
        cvs.create_rectangle(bx, y, bx + bw_max, y + bh,
                              fill="#14141e", outline=C["border"])

        # Filled bar
        if bw > 0:
            cvs.create_rectangle(bx, y, bx + bw, y + bh,
                                  fill=C[label], outline="")

        # Labels
        cvs.create_text(bx - 8, y + bh // 2, text=label,
                        fill=C[label], font=("Courier", 10, "bold"),
                        anchor="e")

        pct_str = f"{pct}%" if stat["total"] > 0 else "—"
        cvs.create_text(bx + bw_max + 8, y + bh // 2, text=pct_str,
                        fill=C[label] if stat["total"] > 0 else C["dim"],
                        font=("Courier", 10), anchor="w")

        cnt_str = f"({stat['agreed']}/{stat['total']})"
        cvs.create_text(bx + bw_max // 2, y + bh + 5,
                        text=cnt_str, fill=C["dim"],
                        font=("Courier", 7))

    # Footnote
    cvs.create_text(145, start_y + 4 * (bh + gap) + 12,
                    text="Research target: ≥ 70% per type",
                    fill=C["dim"], font=("Courier", 8),
                    justify="center")


# ==============================================================================
# SECTION 7 — CONSOLE INTERFACE (interactive session flow)
# ==============================================================================

def print_header():
    print()
    print("=" * 66)
    print("  ConfusionMapper  v1.0")
    print("  Distractor Classification & Inter-Rater Reliability Tool")
    print("  Manik Maurya · IIT Kanpur Cognitive Science · Code in Place 2026")
    print("=" * 66)
    print()


def print_taxonomy_card():
    """Print the taxonomy reference card to console."""
    print()
    print("─" * 66)
    print("  TAXONOMY REFERENCE — Four Cognitive Error Types")
    print("─" * 66)
    for code in ERROR_TYPES:
        t = TAXONOMY[code]
        print(f"  [{t['number']}] {code} — {t['name']}")
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

            # ── Human classification ────────────────────────────────────────
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

            # ── AI classification ───────────────────────────────────────────
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

            # ── Show result ─────────────────────────────────────────────────
            if ai_res["available"] and a_label != "N/A":
                symbol = "✓ AGREE   " if h_label == a_label else "✗ DISAGREE"
                print(f" AI → {a_label}")
                print(f"  {symbol}  You: {h_label}  AI: {a_label}")
                if ai_res.get("reasoning"):
                    print(f"  AI reasoning: {ai_res['reasoning']}")
            else:
                print()
                print(f"  Your label: {h_label}  (AI unavailable — manual mode)")

            # Ground-truth check (built-in questions have reference labels)
            ref = d.get("error_type", "")
            if ref:
                mark = "✓" if h_label == ref else "✗"
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

    # ── Compute statistics ──────────────────────────────────────────────────
    # Use AI labels if available; otherwise use reference labels (built-in bank)
    valid_pairs = [(h, a) for h, a in zip(human_labels, ai_labels) if a != "N/A"]

    if valid_pairs:
        hl = [p[0] for p in valid_pairs]
        al = [p[1] for p in valid_pairs]
    else:
        # Manual mode — compare against reference labels from built-in bank
        hl = [r["human_label"]   for r in ratings if r["reference_label"]]
        al = [r["reference_label"] for r in ratings if r["reference_label"]]

    kappa       = compute_cohens_kappa(hl, al)
    matrix      = build_confusion_matrix(hl, al)
    type_stats  = get_per_type_stats(hl, al)

    session = {
        "rater_id":    rater_id,
        "date":        datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
        "n_questions": len(questions),
        "n_distractors": n_distractors,
        "ratings":     ratings,
        "kappa":       kappa,
        "matrix":      matrix,
        "type_stats":  type_stats,
        "ai_mode":     bool(api_key and any(r["ai_available"] for r in ratings)),
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
    print(f"  COHEN'S KAPPA:  κ = {kappa['kappa']:.4f}")
    print(f"  {kappa['interpretation']}")
    print(f"  Observed agreement:  {kappa['po']:.1%}")
    print(f"  Expected by chance:  {kappa['pe']:.1%}")
    print(f"  Agreements:  {kappa['agreements']} / {kappa['n']}")
    print()
    print("  Agreement by error type:")
    for label in ERROR_TYPES:
        s   = type_stats[label]
        bar = "█" * (s["pct"] // 5) + "░" * (20 - s["pct"] // 5)
        tag = " ← ✓" if s["pct"] >= 70 else ""
        print(f"  {label}  {bar}  {s['pct']:3d}%  "
              f"({s['agreed']}/{s['total']}){tag}")
    print()

    k = kappa["kappa"]
    if k >= 0.70:
        print("  ✓ RESEARCH READY: Proceed with human-human validation.")
    elif k >= 0.60:
        print("  ⚠ CLOSE: Review CF/RF boundary cases and re-pilot.")
    else:
        print("  ✗ REVISE RUBRIC before using this taxonomy in research.")
        print("    Common issues: CF vs RF (is the answer plausible?)")
        print("                  PK vs CF (is the wrong direction obvious?)")
    print()
    print("─" * 66)
    print("  ETHICS NOTE")
    print("  ChatGPT may appear artificially reliable because its training")
    print("  data includes cognitive science literature. This tool gives a")
    print("  preliminary signal — it does not replace two trained human")
    print("  raters classifying independently. Always run human-human")
    print("  inter-rater validation (κ ≥ 0.70) before data collection.")
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
        print(f"  [{i}]  {s.get('date','—')}  |  "
              f"Rater: {s.get('rater_id','?')}  |  "
              f"κ = {k.get('kappa', 0):.3f}  |  "
              f"{s.get('n_distractors', 0)} distractors")
        print(f"       {k.get('interpretation','')}")
    print()


# ==============================================================================
# SECTION 8 — MAIN
# ==============================================================================

def main():
    print_header()

    # Check for OpenAI key
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        print("  ✓ OPENAI_API_KEY detected — AI rater mode enabled.")
    else:
        print("  ℹ No OPENAI_API_KEY — running in Manual Mode.")
        print("    Set the environment variable to enable AI classification.")
    print()

    rater_id = input("  Enter your rater ID (e.g. your initials): ").strip()
    if not rater_id:
        rater_id = "Rater1"

    while True:
        print()
        print("─" * 66)
        print("  MAIN MENU")
        print("─" * 66)
        print("  [1] Classify — built-in NCERT question bank (15 distractors)")
        if api_key:
            print("  [2] Classify — AI-generated questions on any topic")
        print("  [3] View past sessions")
        print("  [4] Taxonomy reference card")
        print("  [Q] Quit")
        print()

        valid = ["1", "3", "4", "Q"]
        if api_key:
            valid.append("2")

        choice = get_choice("  Your choice: ", valid)

        # ── Option 1: built-in bank ──────────────────────────────────────────
        if choice == "1":
            print(f"\n  Loaded {len(BUILTIN_QUESTIONS)} questions "
                  f"({sum(len(q['distractors']) for q in BUILTIN_QUESTIONS)} distractors).")
            print("  Reference labels will be shown after each classification.")
            input("  Press Enter to begin...")

            session, kappa, matrix, type_stats = run_session(
                BUILTIN_QUESTIONS, api_key, rater_id
            )
            print_summary(kappa, type_stats, session)
            save_session(session)
            print(f"\n  Session saved → {DATA_FILE}")
            input("  Press Enter to open the visualisation window...")
            show_results_window(kappa, matrix, type_stats, session)

        # ── Option 2: AI-generated questions ────────────────────────────────
        elif choice == "2" and api_key:
            topic = input("\n  Topic for question generation: ").strip()
            if not topic:
                topic = "Photosynthesis"

            n_str = input("  Number of questions to generate (1–5): ").strip()
            try:
                n_q = max(1, min(5, int(n_str)))
            except ValueError:
                n_q = 3

            print(f"\n  Generating {n_q} question(s) on '{topic}'...")
            questions = generate_ai_questions(topic, n_q, api_key)

            if not questions:
                print("  Generation failed — using built-in bank instead.")
                questions = BUILTIN_QUESTIONS
            else:
                total_d = sum(len(q["distractors"]) for q in questions)
                print(f"  ✓ {len(questions)} question(s) generated "
                      f"({total_d} distractors).")

            input("  Press Enter to begin classification...")

            session, kappa, matrix, type_stats = run_session(
                questions, api_key, rater_id
            )
            print_summary(kappa, type_stats, session)
            save_session(session)
            print(f"\n  Session saved → {DATA_FILE}")
            input("  Press Enter to open the visualisation window...")
            show_results_window(kappa, matrix, type_stats, session)

        # ── Option 3: past sessions ──────────────────────────────────────────
        elif choice == "3":
            view_past_sessions()

        # ── Option 4: taxonomy card ──────────────────────────────────────────
        elif choice == "4":
            print_taxonomy_card()

        # ── Quit ──────────────────────────────────────────────────────────────
        elif choice == "Q":
            print(f"\n  All session data saved to: {DATA_FILE}")
            print("  Goodbye.\n")
            break


if __name__ == "__main__":
    main()
