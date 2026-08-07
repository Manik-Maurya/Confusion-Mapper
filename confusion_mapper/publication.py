"""
Publication assistant: methods-paragraph drafting, reliability/frequency
tables, and SVG figures (confusion-matrix heatmap, category-frequency bar
chart) -- all mechanically assembled from statistics this package already
computed, never invented here. New in v2.6.0.

Every function in this module takes an already-computed result dict
(compute_cohens_kappa's, gwet_ac1's, krippendorff_alpha's,
build_confusion_matrix's, get_per_type_stats's -- whatever this package's
own, already-tested stats functions returned) and formats it. Nothing
here re-derives a statistic or makes a judgment call the underlying
function didn't already make (e.g. the qualitative "almost perfect" /
"substantial" language in the methods paragraph is lifted verbatim from
the interpretation string compute_cohens_kappa/gwet_ac1 already computed,
not re-decided here). The one thing this module could plausibly be
accused of inventing -- prose connective tissue like "was assessed using"
-- carries no numeric or scientific content.

Every generated document is stamped "DRAFT -- REQUIRES HUMAN REVIEW"
in the same spirit as codebook.py's decision-rule placeholders: this
produces a first draft to edit, not a paragraph to paste into a
manuscript unread.
"""

import datetime

from .taxonomy import TAXONOMY


DRAFT_NOTICE = (
    "DRAFT -- REQUIRES HUMAN REVIEW. Every number below was computed by this "
    "package's own tested statistics functions; the prose connecting them was "
    "not written or reviewed by a person. Check it reads correctly, matches "
    "your actual study design, and cite this package version/DOI if you use it."
)


def _category_name(code, taxonomy=None):
    if taxonomy is None:
        taxonomy = TAXONOMY
    return taxonomy.get(code, {}).get("name", code)


def _fmt_kappa_like(value):
    """APA-ish: no leading zero, 2 decimal places. -0.5 stays -0.50; None passes through."""
    if value is None:
        return "N/A"
    s = f"{value:.2f}"
    return s.replace("0.", ".", 1) if s.startswith("0.") else s.replace("-0.", "-.", 1)


def _primary_descriptor(interpretation):
    """
    Every interpretation string in this package's stats functions is
    structured as "{Primary descriptor}, {extra detail/advice}." (e.g.
    "Almost Perfect, excellent agreement." or "Substantial, close to
    target."). For a methods sentence, only the primary descriptor reads
    naturally embedded mid-sentence -- the full string was written for a
    CLI/dashboard status line, not a sentence fragment. Falls back to the
    whole (stripped) string if there's no comma to split on.
    """
    first_clause = interpretation.split(",")[0].strip().rstrip(".")
    return first_clause.lower() if first_clause else interpretation.rstrip(".").lower()


def generate_methods_paragraph(kappa_result, n_raters=2, ac1_result=None,
                               alpha_result=None, ci_result=None):
    """
    Draft an APA-style inter-rater-reliability methods paragraph from
    already-computed stats. Uses ASCII kappa/alpha (not italic Unicode
    Greek) since this is meant to be pasted into a word processor and
    reformatted there, not treated as camera-ready typesetting.

    Args:
        kappa_result (dict): compute_cohens_kappa()'s return dict.
        n_raters (int): 2 for a human-vs-AI pair (the default workflow),
            or more if this describes a multi-rater panel result instead
            (pass a fleiss_kappa() result as kappa_result in that case --
            it has a compatible "kappa"/"interpretation" shape).
        ac1_result (dict | None): gwet_ac1()'s return dict, if you ran it.
        alpha_result (dict | None): krippendorff_alpha()'s return dict.
        ci_result (dict | None): a "ci_95_bca" block as attached by the
            `kappa` CLI subcommand's --bootstrap flag, i.e.
            {"lower":, "upper":}.

    Returns:
        str: a draft paragraph, prefixed with DRAFT_NOTICE.
    """
    n = kappa_result.get("n")
    kappa = kappa_result.get("kappa")
    interp = _primary_descriptor(kappa_result.get("interpretation", ""))

    rater_desc = "two raters" if n_raters == 2 else f"{n_raters} raters"
    sentence = (
        f"Inter-rater reliability between {rater_desc} was assessed using "
        f"Cohen's kappa (Cohen, 1960) across N = {n} coded items. "
        f"Agreement was {interp}, kappa = {_fmt_kappa_like(kappa)}"
    )
    if ci_result:
        sentence += (f", 95% CI [{_fmt_kappa_like(ci_result['lower'])}, "
                     f"{_fmt_kappa_like(ci_result['upper'])}]")
    sentence += "."

    extra = []
    if ac1_result:
        ac1_interp = _primary_descriptor(ac1_result.get("interpretation", ""))
        extra.append(
            f"Gwet's AC1, which is less sensitive to category-prevalence skew than "
            f"kappa (Gwet, 2008), corroborated this result: AC1 = "
            f"{_fmt_kappa_like(ac1_result.get('ac1'))} ({ac1_interp})."
        )
    if alpha_result:
        alpha_interp = _primary_descriptor(alpha_result.get("interpretation", ""))
        extra.append(
            f"Krippendorff's alpha, computed as a cross-check that generalizes "
            f"beyond two raters, was alpha = {_fmt_kappa_like(alpha_result.get('alpha'))} "
            f"({alpha_interp})."
        )

    paragraph = " ".join([sentence] + extra)
    return f"*{DRAFT_NOTICE}*\n\n{paragraph}"


def generate_reliability_table(kappa_result, ac1_result=None, alpha_result=None, ci_result=None):
    """
    A Table-1-style Markdown table of every reliability statistic computed,
    side by side, for a methods/results section.

    Returns:
        str: Markdown.
    """
    lines = [
        f"*{DRAFT_NOTICE}*", "",
        "**Table: Inter-rater reliability statistics**", "",
        "| Statistic | Value | 95% CI | n | Interpretation |",
        "|---|---|---|---|---|",
    ]
    ci_str = (f"[{_fmt_kappa_like(ci_result['lower'])}, {_fmt_kappa_like(ci_result['upper'])}]"
             if ci_result else "--")
    lines.append(f"| Cohen's kappa | {_fmt_kappa_like(kappa_result.get('kappa'))} | {ci_str} | "
                f"{kappa_result.get('n', '--')} | {kappa_result.get('interpretation', '--')} |")
    if ac1_result:
        lines.append(f"| Gwet's AC1 | {_fmt_kappa_like(ac1_result.get('ac1'))} | -- | "
                    f"{ac1_result.get('n', '--')} | {ac1_result.get('interpretation', '--')} |")
    if alpha_result:
        lines.append(f"| Krippendorff's alpha | {_fmt_kappa_like(alpha_result.get('alpha'))} | -- | "
                    f"{alpha_result.get('n', '--')} | {alpha_result.get('interpretation', '--')} |")
    return "\n".join(lines)


def generate_frequency_table(type_stats, taxonomy=None):
    """
    A Markdown table of per-category frequency/agreement from
    stats.get_per_type_stats()'s return shape.

    Args:
        type_stats (dict[str, dict]): {category: {"total":, "agreed":,
            "pct":}}, i.e. get_per_type_stats()'s return value.
        taxonomy (dict | None): for real category names in the table
            instead of bare codes.

    Returns:
        str: Markdown.
    """
    lines = [
        f"*{DRAFT_NOTICE}*", "",
        "**Table: Category frequency and agreement**", "",
        "| Code | Category | n | Agreed | % Agreement |",
        "|---|---|---|---|---|",
    ]
    for code, stats in type_stats.items():
        name = _category_name(code, taxonomy)
        lines.append(f"| {code} | {name} | {stats.get('total', 0)} | "
                    f"{stats.get('agreed', 0)} | {stats.get('pct', 0)}% |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# SVG figures -- pure string generation, no plotting dependency
# ---------------------------------------------------------------------------

_SVG_COLORS = {"bg": "#ffffff", "text": "#1a1a1a", "grid": "#cccccc",
              "diag_lo": "#e8f4ea", "diag_hi": "#2e7d32",
              "off_lo": "#ffffff", "off_hi": "#c0392b"}


def _lerp_color(hex_lo, hex_hi, t):
    """Linear-interpolate between two #rrggbb colors, t in [0,1]."""
    lo = tuple(int(hex_lo[i:i + 2], 16) for i in (1, 3, 5))
    hi = tuple(int(hex_hi[i:i + 2], 16) for i in (1, 3, 5))
    mixed = tuple(round(lo[c] + (hi[c] - lo[c]) * t) for c in range(3))
    return f"#{mixed[0]:02x}{mixed[1]:02x}{mixed[2]:02x}"


def generate_confusion_matrix_svg(matrix, categories=None, taxonomy=None,
                                  rater1_name="Rater 1", rater2_name="Rater 2"):
    """
    An SVG heatmap of a confusion matrix (build_confusion_matrix()'s
    return shape) -- diagonal cells shaded green by agreement intensity,
    off-diagonal cells shaded red by disagreement intensity, the same
    visual convention as the tkinter GUI's confusion-matrix panel
    (gui._draw_confusion_matrix), reimplemented for SVG since a
    tkinter Canvas can't be exported as a file for a manuscript.

    Args:
        matrix (dict[str, dict[str, int]]): rows = rater1, cols = rater2.
        categories (list[str] | None): defaults to matrix's own row order.
        taxonomy (dict | None): for real category names in axis labels.
        rater1_name, rater2_name (str): axis labels.

    Returns:
        str: standalone SVG document (starts with <svg ...>).
    """
    categories = categories or list(matrix.keys())
    n = len(categories)
    cell = 70
    margin_left, margin_top = 140, 90
    width = margin_left + cell * n + 20
    height = margin_top + cell * n + 40

    row_max = max((sum(matrix[c].values()) for c in categories), default=1) or 1

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'font-family="Helvetica,Arial,sans-serif">']
    parts.append(f'<rect width="{width}" height="{height}" fill="{_SVG_COLORS["bg"]}"/>')
    parts.append(f'<text x="{width/2}" y="24" text-anchor="middle" font-size="14" '
                f'font-weight="bold" fill="{_SVG_COLORS["text"]}">Confusion Matrix</text>')
    parts.append(f'<text x="{margin_left + cell*n/2}" y="46" text-anchor="middle" '
                f'font-size="11" fill="{_SVG_COLORS["text"]}">{rater2_name} &#8594;</text>')
    parts.append(f'<text x="20" y="{margin_top + cell*n/2}" text-anchor="middle" font-size="11" '
                f'fill="{_SVG_COLORS["text"]}" transform="rotate(-90 20 {margin_top + cell*n/2})">'
                f'{rater1_name} &#8594;</text>')

    for j, col_code in enumerate(categories):
        x = margin_left + j * cell + cell / 2
        parts.append(f'<text x="{x}" y="{margin_top - 8}" text-anchor="middle" font-size="10" '
                    f'fill="{_SVG_COLORS["text"]}">{col_code}</text>')

    for i, row_code in enumerate(categories):
        y = margin_top + i * cell
        parts.append(f'<text x="{margin_left - 8}" y="{y + cell/2 + 4}" text-anchor="end" '
                    f'font-size="10" fill="{_SVG_COLORS["text"]}">{row_code}</text>')
        for j, col_code in enumerate(categories):
            x = margin_left + j * cell
            count = matrix.get(row_code, {}).get(col_code, 0)
            t = min(1.0, count / row_max) if row_max else 0.0
            is_diag = (row_code == col_code)
            color = (_lerp_color(_SVG_COLORS["diag_lo"], _SVG_COLORS["diag_hi"], t) if is_diag
                    else _lerp_color(_SVG_COLORS["off_lo"], _SVG_COLORS["off_hi"], t * 0.6))
            text_color = "#ffffff" if t > 0.55 else _SVG_COLORS["text"]
            parts.append(f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" '
                        f'fill="{color}" stroke="{_SVG_COLORS["grid"]}"/>')
            parts.append(f'<text x="{x + cell/2}" y="{y + cell/2 + 5}" text-anchor="middle" '
                        f'font-size="13" fill="{text_color}">{count}</text>')

    row_names = ", ".join(f"{c}={_category_name(c, taxonomy)}" for c in categories)
    parts.append(f'<text x="{margin_left}" y="{height - 8}" font-size="9" '
                f'fill="{_SVG_COLORS["grid"]}">{row_names}</text>')
    parts.append('</svg>')
    return "\n".join(parts)


def generate_frequency_bar_chart_svg(type_stats, taxonomy=None, title="Category Frequency"):
    """
    An SVG bar chart of per-category item counts, from
    stats.get_per_type_stats()'s return shape.

    Returns:
        str: standalone SVG document.
    """
    categories = list(type_stats.keys())
    counts = [type_stats[c].get("total", 0) for c in categories]
    max_count = max(counts) if counts else 1
    max_count = max_count or 1

    bar_w, gap, chart_h = 60, 20, 220
    margin_left, margin_top = 50, 40
    width = margin_left + len(categories) * (bar_w + gap) + 20
    height = margin_top + chart_h + 60

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
            f'font-family="Helvetica,Arial,sans-serif">']
    parts.append(f'<rect width="{width}" height="{height}" fill="{_SVG_COLORS["bg"]}"/>')
    parts.append(f'<text x="{width/2}" y="20" text-anchor="middle" font-size="14" '
                f'font-weight="bold" fill="{_SVG_COLORS["text"]}">{title}</text>')
    parts.append(f'<line x1="{margin_left}" y1="{margin_top + chart_h}" '
                f'x2="{width - 10}" y2="{margin_top + chart_h}" stroke="{_SVG_COLORS["text"]}"/>')

    for i, code in enumerate(categories):
        count = counts[i]
        bar_h = (count / max_count) * chart_h if max_count else 0
        x = margin_left + i * (bar_w + gap)
        y = margin_top + chart_h - bar_h
        parts.append(f'<rect x="{x}" y="{y}" width="{bar_w}" height="{bar_h}" '
                    f'fill="{_SVG_COLORS["diag_hi"]}"/>')
        parts.append(f'<text x="{x + bar_w/2}" y="{y - 6}" text-anchor="middle" font-size="11" '
                    f'fill="{_SVG_COLORS["text"]}">{count}</text>')
        parts.append(f'<text x="{x + bar_w/2}" y="{margin_top + chart_h + 16}" text-anchor="middle" '
                    f'font-size="10" fill="{_SVG_COLORS["text"]}">{code}</text>')
        name = _category_name(code, taxonomy)
        parts.append(f'<text x="{x + bar_w/2}" y="{margin_top + chart_h + 30}" text-anchor="middle" '
                    f'font-size="8" fill="{_SVG_COLORS["grid"]}">{name[:12]}</text>')

    parts.append('</svg>')
    return "\n".join(parts)


def assemble_results_appendix(kappa_result, type_stats, matrix, categories=None, taxonomy=None,
                              ac1_result=None, alpha_result=None, ci_result=None,
                              rater1_name="Human", rater2_name="AI"):
    """
    One combined Markdown "Results" appendix: methods paragraph, the
    reliability table, the frequency table, and both SVG figures embedded
    inline (SVG is valid inline in Markdown rendered by GitHub, most
    static-site generators, and Pandoc -- for a Word/LaTeX target, save
    the SVGs from generate_confusion_matrix_svg()/
    generate_frequency_bar_chart_svg() separately and insert them as
    normal figures).

    Returns:
        str: Markdown.
    """
    parts = [
        "# Results appendix",
        "",
        f"*Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}. {DRAFT_NOTICE}*",
        "",
        "## Methods",
        "",
        generate_methods_paragraph(kappa_result, ac1_result=ac1_result,
                                   alpha_result=alpha_result, ci_result=ci_result),
        "",
        "## Reliability statistics",
        "",
        generate_reliability_table(kappa_result, ac1_result=ac1_result,
                                   alpha_result=alpha_result, ci_result=ci_result),
        "",
        "## Category frequency",
        "",
        generate_frequency_table(type_stats, taxonomy=taxonomy),
        "",
        "## Figures",
        "",
        "**Figure 1.** Confusion matrix.",
        "",
        generate_confusion_matrix_svg(matrix, categories=categories, taxonomy=taxonomy,
                                      rater1_name=rater1_name, rater2_name=rater2_name),
        "",
        "**Figure 2.** Category frequency.",
        "",
        generate_frequency_bar_chart_svg(type_stats, taxonomy=taxonomy),
        "",
    ]
    return "\n".join(parts)
