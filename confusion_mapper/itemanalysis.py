"""
Item analysis, once real classes have sat the PISA-style units.

The honest weak spot of the units is written on every booklet: they have
not been field-tested, so nobody knows how hard each question really is.
The answer files teachers download from the worksheets page are exactly
the data that fixes that. This module runs a classical item analysis on
them, the kind an exam board runs before an item goes into a real test:

  difficulty        the share of available points the class earned on the
                    item (higher means easier)
  discrimination    two views. The corrected item-total correlation (the
                    item against the rest of the test, so the item is not
                    correlated with itself), and the upper-lower index D:
                    the item's success rate in the top 27% of the class
                    minus the bottom 27% (Kelley, 1939). D is read with
                    Ebel's rule of thumb: .40 and up very good, .30 to .39
                    reasonably good, .20 to .29 marginal, below .20 poor.
  distractors       for every wrong option, how many children chose it,
                    and whether stronger or weaker children chose it. A
                    distractor chosen by fewer than 5% of children is
                    "non-functioning" (Haladyna and Downing, 1993). A
                    distractor that the top group picks more often than
                    the bottom group is a warning sign: the question may
                    be ambiguous, or the key may be wrong.
  reliability       Cronbach's alpha (1951) for the whole set. It equals
                    KR-20 when every item is right/wrong, and also works
                    for the written answers worth 0, 1 or 2.

None of this replaces a proper field trial with hundreds of children. With
one class of thirty, these numbers move a lot from class to class. They
are still far better than no numbers, and they point at the questions a
person should look at first.

References:
    Cronbach, L. J. (1951). Coefficient alpha and the internal structure of
        tests. Psychometrika, 16(3), 297-334.
    Ebel, R. L. (1972). Essentials of Educational Measurement. Prentice-Hall.
    Haladyna, T. M., and Downing, S. M. (1993). How many options is enough
        for a multiple-choice test item? Educational and Psychological
        Measurement, 53(4), 999-1010.
    Kelley, T. L. (1939). The selection of upper and lower groups for the
        validation of test items. Journal of Educational Psychology, 30(1),
        17-24.
"""

import math

from .pisa import question_labels, _parse_answer, _max_points


NON_FUNCTIONING_SHARE = 0.05     # Haladyna and Downing (1993)
GROUP_FRACTION = 0.27            # Kelley (1939)
EBEL_BANDS = ((0.40, "very good"), (0.30, "reasonably good"),
              (0.20, "marginal"), (float("-inf"), "poor"))


# -----------------------------------------------------------------------------
# Plain statistics
# -----------------------------------------------------------------------------

def _mean(xs):
    return sum(xs) / len(xs)


def _pvar(xs):
    """Population variance. Alpha only needs a ratio, so the choice of
    denominator cancels as long as it is used everywhere."""
    m = _mean(xs)
    return sum((x - m) ** 2 for x in xs) / len(xs)


def pearson(x, y):
    """Pearson correlation, or None when either variable does not vary."""
    if len(x) != len(y) or len(x) < 2:
        raise ValueError("pearson needs two lists of the same length, at least 2")
    mx, my = _mean(x), _mean(y)
    sxx = sum((a - mx) ** 2 for a in x)
    syy = sum((b - my) ** 2 for b in y)
    if sxx == 0 or syy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(x, y)) / math.sqrt(sxx * syy)


def cronbach_alpha(matrix):
    """
    Cronbach's alpha for a students x items score matrix (list of rows).
        alpha = k / (k - 1) * (1 - sum(item variances) / variance of totals)
    Returns None with fewer than 2 items, fewer than 2 students, or when the
    totals do not vary.
    """
    if len(matrix) < 2 or len(matrix[0]) < 2:
        return None
    k = len(matrix[0])
    items = list(zip(*matrix))
    totals = [sum(row) for row in matrix]
    var_total = _pvar(totals)
    if var_total == 0:
        return None
    return k / (k - 1) * (1 - sum(_pvar(col) for col in items) / var_total)


def upper_lower_groups(totals, fraction=GROUP_FRACTION):
    """
    Indices of the lower and upper groups by total score. Group size is
    round(fraction * n), at least 1. Ties at the cut are broken by the
    order students were entered, so the result is always the same.
    """
    n = len(totals)
    size = max(1, int(round(fraction * n)))
    order = sorted(range(n), key=lambda i: (totals[i], i))
    return order[:size], order[n - size:]


def ebel_band(d):
    if d is None:
        return None
    return next(label for cut, label in EBEL_BANDS if d >= cut)


# -----------------------------------------------------------------------------
# From answer sheets to a score matrix
# -----------------------------------------------------------------------------

def item_matrix(units, responses):
    """
    Score every child on every question.

    Uses exactly the rules of pisa.score_responses: blank counts as no
    points, and a row with no answers at all is skipped as absent. Returns
    the score matrix and, for each question, what each child actually
    answered, which the distractor analysis needs.
    """
    labels = question_labels(units)
    students, scores, answers, seen = [], [], [], set()
    for row in responses:
        sid = str(row.get("student_id", "")).strip()
        if not sid or all(not str(row.get(lab) or "").strip() for lab, _, _ in labels):
            continue
        if sid in seen:
            raise ValueError(f"student_id {sid!r} appears twice")
        seen.add(sid)
        s_row, a_row = [], []
        for lab, _, q in labels:
            try:
                ans = _parse_answer(row.get(lab), lab, q)
            except ValueError as e:
                raise ValueError(f"student {sid}, {e}")
            a_row.append(ans)
            s_row.append(_points(q, ans))
        students.append(sid)
        scores.append(s_row)
        answers.append(a_row)
    if not students:
        raise ValueError("no students to analyse")
    return {"labels": labels, "students": students, "scores": scores, "answers": answers}


def _points(q, ans):
    if ans is None:
        return 0
    fmt = q["format"]
    if fmt == "multiple_choice":
        return 1 if ans == q["key"] else 0
    if fmt == "complex_multiple_choice":
        return 1 if all((a == "T") == s["answer"] for a, s in zip(ans, q["statements"])) else 0
    if ans == "full":
        return _max_points(q)
    return 1 if ans == "partial" else 0


# -----------------------------------------------------------------------------
# The analysis
# -----------------------------------------------------------------------------

def analyze_items(units, responses):
    """
    Classical item analysis of one set of units, from one or more classes
    that sat that same set.

    Returns:
        dict with n_students, alpha, mean_total, sd_total, max_total,
        items (one dict per question, with difficulty, discrimination,
        the option or code breakdown and a list of plain-language flags),
        and warnings.
    """
    m = item_matrix(units, responses)
    scores, answers, labels = m["scores"], m["answers"], m["labels"]
    n = len(scores)
    totals = [sum(r) for r in scores]
    lower, upper = upper_lower_groups(totals)
    max_total = sum(_max_points(q) for _, _, q in labels)

    items = []
    for j, (label, unit, q) in enumerate(labels):
        mx = _max_points(q)
        col = [r[j] for r in scores]
        rest = [t - c for t, c in zip(totals, col)]
        difficulty = _mean(col) / mx
        d_index = (_mean([col[i] for i in upper]) - _mean([col[i] for i in lower])) / mx
        r_it = pearson(col, rest) if n >= 3 else None
        given = [a[j] for a in answers]
        item = {
            "label": label, "qid": q["qid"], "template": unit["template"],
            "position": int(label.split(".")[1]), "unit_title": unit["title"],
            "format": q["format"], "max_points": mx, "n": n,
            "omitted": sum(1 for g in given if g is None) / n,
            "difficulty": difficulty, "item_rest_r": r_it,
            "d_index": d_index, "ebel": ebel_band(d_index),
            "choices": _choices(q, given, lower, upper, n),
        }
        item["flags"] = _flags(item, q)
        items.append(item)

    warnings = []
    if n < 30:
        warnings.append(f"Only {n} students. With fewer than about 30, these numbers can "
                        f"change a lot from one class to the next, so treat them as a first "
                        f"look and pool more classes that sat the same set.")
    alpha = cronbach_alpha(scores)
    return {
        "n_students": n,
        "max_total": max_total,
        "mean_total": _mean(totals),
        "sd_total": math.sqrt(_pvar(totals)),
        "alpha": alpha,
        "group_size": len(upper),
        "items": items,
        "warnings": warnings,
    }


def _choices(q, given, lower, upper, n):
    """Who chose what, overall and in the top and bottom groups."""
    def share(pred, idx):
        return sum(1 for i in idx if pred(given[i])) / len(idx)

    everyone = range(n)
    rows = []
    if q["format"] == "multiple_choice":
        by_text = {d["option"]: d for d in q["distractors"]}
        for o in q["options"]:
            d = by_text.get(o["text"])
            hit = (lambda g, L=o["letter"]: g == L)
            rows.append({"choice": o["letter"], "text": o["text"],
                         "is_key": d is None, "error_type": d["error_type"] if d else None,
                         "share": share(hit, everyone), "upper": share(hit, upper),
                         "lower": share(hit, lower)})
    elif q["format"] == "complex_multiple_choice":
        for k, s in enumerate(q["statements"]):
            wrong = (lambda g, K=k, S=s: g is not None and (g[K] == "T") != S["answer"])
            rows.append({"choice": f"row {k + 1} wrong", "text": s["text"], "is_key": False,
                         "error_type": s["if_wrong"]["error_type"],
                         "share": share(wrong, everyone), "upper": share(wrong, upper),
                         "lower": share(wrong, lower)})
    else:
        types = {w["error_type"]: w["answer"] for w in q["common_wrong_answers"]}
        for code in ("full", "partial", "none", "rf", "pk", "cf", "int"):
            if code == "partial" and not q["scoring"].get("partial_credit"):
                continue
            hit = (lambda g, C=code: g == C)
            label = code.upper() if len(code) <= 3 and code not in ("none",) else code
            rows.append({"choice": label, "text": types.get(code.upper(), ""),
                         "is_key": code == "full",
                         "error_type": code.upper() if code.upper() in types else None,
                         "share": share(hit, everyone), "upper": share(hit, upper),
                         "lower": share(hit, lower)})
    return rows


def _flags(item, q):
    flags = []
    d, r = item["d_index"], item["item_rest_r"]
    if d < 0 or (r is not None and r < 0):
        flags.append("Stronger students did worse on this question than weaker ones. "
                     "Check the key and the wording first.")
    elif item["ebel"] == "poor":
        flags.append("Separates stronger from weaker students poorly (D below .20, "
                     "Ebel's 'poor'). Worth rewording or replacing.")
    elif item["ebel"] == "marginal":
        flags.append("Separates students only marginally (D between .20 and .29).")
    if item["difficulty"] >= 0.95:
        flags.append("Nearly everyone got this right, so it tells you little about "
                     "differences between students.")
    elif item["difficulty"] <= 0.05:
        flags.append("Nearly no one got this right. Check that it is clear and taught.")
    if q["format"] == "multiple_choice":
        for c in item["choices"]:
            if c["is_key"]:
                continue
            if c["share"] < NON_FUNCTIONING_SHARE:
                flags.append(f"Option {c['choice']} was chosen by fewer than 5% of students, "
                             f"a non-functioning distractor (Haladyna and Downing, 1993). "
                             f"Its {c['error_type']} misconception may be rare in this group.")
            elif c["upper"] > c["lower"]:
                flags.append(f"Option {c['choice']} attracted more of the stronger students "
                             f"than the weaker ones. It may be defensible as an answer, so "
                             f"read it again.")
    if item["omitted"] >= 0.25:
        flags.append(f"{item['omitted'] * 100:.0f}% left it blank. It may be too long, "
                     f"too late in the booklet, or unclear.")
    return flags


# -----------------------------------------------------------------------------
# Report
# -----------------------------------------------------------------------------

def _f(x, digits=2):
    return "n/a" if x is None else f"{x:.{digits}f}"


def format_item_report(analysis, title="Item analysis"):
    a = analysis
    lines = [f"# {title}", "",
             f"{a['n_students']} students. Mean score {a['mean_total']:.1f} out of "
             f"{a['max_total']} (SD {a['sd_total']:.1f}). Cronbach's alpha "
             f"{_f(a['alpha'])}. Upper and lower groups: {a['group_size']} students each "
             f"(27%, Kelley 1939).", ""]
    for w in a["warnings"]:
        lines += [f"*{w}*", ""]

    flagged = [i for i in a["items"] if i["flags"]]
    lines += ["## Look at these first", ""]
    if not flagged:
        lines += ["No question raised a flag.", ""]
    for i in flagged:
        lines.append(f"**{i['label']} {i['unit_title']}**")
        lines += [f"- {fl}" for fl in i["flags"]] + [""]

    lines += ["## Every question", "",
              "Difficulty is the share of available points earned, so higher means easier. "
              "D is the success rate of the top 27% minus the bottom 27%, read with Ebel's "
              "bands: .40 and up very good, .30 to .39 reasonably good, .20 to .29 "
              "marginal, below .20 poor. r is the correlation of the question with the "
              "rest of the test.", "",
              "| Question | Difficulty | D | Ebel | r | Left blank |", "|---|---|---|---|---|---|"]
    for i in a["items"]:
        lines.append(f"| {i['label']} {i['unit_title']} | {_f(i['difficulty'])} | "
                     f"{_f(i['d_index'])} | {i['ebel']} | {_f(i['item_rest_r'])} | "
                     f"{i['omitted'] * 100:.0f}% |")
    lines.append("")

    lines += ["## Who chose what", "",
              "For each question: the share of all students who chose each option (or, for "
              "written answers, each code), and the share in the top and bottom groups. A "
              "working distractor is chosen more by the bottom group than the top group.", ""]
    for i in a["items"]:
        lines += [f"### {i['label']} {i['unit_title']}", "",
                  "| Choice | Type | All | Top 27% | Bottom 27% |", "|---|---|---|---|---|"]
        for c in i["choices"]:
            kind = "key" if c["is_key"] else (c["error_type"] or "")
            lines.append(f"| {c['choice']} | {kind} | {c['share'] * 100:.0f}% | "
                         f"{c['upper'] * 100:.0f}% | {c['lower'] * 100:.0f}% |")
        lines.append("")

    lines += ["## References", "",
              "Cronbach, L. J. (1951). Coefficient alpha and the internal structure of tests. "
              "Psychometrika, 16(3), 297-334.",
              "",
              "Ebel, R. L. (1972). Essentials of Educational Measurement. Prentice-Hall.",
              "",
              "Haladyna, T. M., and Downing, S. M. (1993). How many options is enough for a "
              "multiple-choice test item? Educational and Psychological Measurement, 53(4), "
              "999-1010.",
              "",
              "Kelley, T. L. (1939). The selection of upper and lower groups for the "
              "validation of test items. Journal of Educational Psychology, 30(1), 17-24."]
    return "\n".join(lines).rstrip() + "\n"
