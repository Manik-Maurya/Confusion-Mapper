"""
Tkinter GUI. Optional, headless environments never touch this. It
shows the current item, the four category buttons, and the running
tally. It exists because I found the plain terminal loop tiring after
a couple of hours of coding, and a friend I asked to help me code data
outright refused to use the terminal version.
"""

import math

# Graceful fallback if tkinter is not installed OR no display is available
try:
    import tkinter as tk
    _test = tk.Tk()
    _test.destroy()
    TKINTER_AVAILABLE = True
except Exception:
    tk = None
    TKINTER_AVAILABLE = False

from .taxonomy import ERROR_TYPES



# Colour palette, dark academic aesthetic
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
      Panel 1, Kappa Gauge (semicircular speedometer)
      Panel 2, Confusion Matrix (4x4 grid, human vs AI)
      Panel 3, Per-type Agreement (horizontal bar chart)
    """
    if not TKINTER_AVAILABLE:
        print("  (tkinter display unavailable, skipping visualisation)")
        return

    root = tk.Tk()
    root.title("ConfusionMapper, Session Results")
    root.configure(bg=C["bg"])
    root.geometry("1000x700")
    root.resizable(False, False)

    # ── Title ───────────────────────────────────────────────────────────────
    header = tk.Frame(root, bg=C["bg"])
    header.pack(fill="x", pady=10)

    tk.Label(header, text="ConfusionMapper | Session Results",
             bg=C["bg"], fg=C["gold"],
             font=("Courier", 15, "bold")).pack()

    tk.Label(header,
             text=(f"Rater: {session.get('rater_id','-')}  |  "
                   f"Questions: {session.get('n_questions',0)}  |  "
                   f"Distractors rated: {kappa['n']}  |  "
                   f"Date: {session.get('date','-')}"),
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
            "Always verify kappa >= 0.70 between two trained human raters before using labels in published research."
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
    """Semicircular speedometer. Needle angle encodes kappa value."""
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

    # five zone arcs across the Landis/Koch bands: 0.0, 0.20, 0.40, 0.70,
    # 0.80, 1.0. tkinter arc angles are geometric: 0 degrees is 3 o'clock
    # and angles grow counter-clockwise. I want kappa=0 at the 9 o'clock
    # side and kappa=1 at the 3 o'clock side, so start_angle = 180 - k*180.
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
        extent = -(k1 - k0) * 180   # negative -> clockwise
        cvs.create_arc(cx - r_out, cy - r_out, cx + r_out, cy + r_out,
                       start=start, extent=extent,
                       style="arc", outline=colour, width=ring_w)

    # Dark overlay ring to create "donut" appearance
    cvs.create_arc(cx - r_in, cy - r_in, cx + r_in, cy + r_in,
                   start=180, extent=-180,
                   style="arc", outline=C["panel"], width=ring_w - 4)

    # Target line at kappa = 0.70
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

    # kappa value centred inside gauge
    k_colour = (C["z4"] if k_val >= 0.80 else
                C["z3"] if k_val >= 0.70 else
                C["z2"] if k_val >= 0.40 else
                C["z1"] if k_val >= 0.20 else C["z0"])

    cvs.create_text(cx, cy - 30, text=f"kappa = {k_val:.3f}",
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
    """4x4 grid. Diagonal cells = agreement (green); off-diagonal = disagreement (red)."""
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
                    text="<- AI Classification ->",
                    fill=C["dim"], font=("Courier", 8))
    for j, col in enumerate(ERROR_TYPES):
        cvs.create_text(ox + j * cs + cs // 2, oy - 8,
                        text=col, fill=C[col],
                        font=("Courier", 10, "bold"))

    # Row header (Human), vertical text simulation
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

        pct_str = f"{pct}%" if stat["total"] > 0 else "-"
        cvs.create_text(bx + bw_max + 8, y + bh // 2, text=pct_str,
                        fill=C[label] if stat["total"] > 0 else C["dim"],
                        font=("Courier", 10), anchor="w")

        cnt_str = f"({stat['agreed']}/{stat['total']})"
        cvs.create_text(bx + bw_max // 2, y + bh + 5,
                        text=cnt_str, fill=C["dim"],
                        font=("Courier", 7))

    # Footnote
    cvs.create_text(145, start_y + 4 * (bh + gap) + 12,
                    text="Research target: >= 70% per type",
                    fill=C["dim"], font=("Courier", 8),
                    justify="center")


