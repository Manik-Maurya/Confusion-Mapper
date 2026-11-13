"""
Tests for the item analysis of real classroom answers.

Every statistic here is checked against something independent: a
hand-worked example, a second formula that must agree (KR-20 against
Cronbach's alpha on right/wrong items), or the scoring module, which must
give every child exactly the same total as the item matrix does.
"""

import json
import math
import random

import pytest

from confusion_mapper.pisa import (
    generate_units,
    question_labels,
    score_responses,
)
from confusion_mapper.itemanalysis import (
    pearson,
    cronbach_alpha,
    upper_lower_groups,
    ebel_band,
    item_matrix,
    analyze_items,
    format_item_report,
)
from confusion_mapper.cli import run


# -----------------------------------------------------------------------------
# Plain statistics
# -----------------------------------------------------------------------------

def test_alpha_hand_example():
    # item variances .1875 + .25 + .1875 = .625, total variance 1.25
    # alpha = 3/2 * (1 - .625 / 1.25) = .75
    assert cronbach_alpha([[1, 1, 1], [1, 1, 0], [1, 0, 0], [0, 0, 0]]) == pytest.approx(0.75)


def _kr20(matrix):
    k, n = len(matrix[0]), len(matrix)
    totals = [sum(r) for r in matrix]
    mean = sum(totals) / n
    var = sum((t - mean) ** 2 for t in totals) / n
    pq = sum((sum(col) / n) * (1 - sum(col) / n) for col in zip(*matrix))
    return k / (k - 1) * (1 - pq / var)


def test_alpha_equals_kr20_on_right_wrong_items():
    rng = random.Random(4)
    for _ in range(200):
        n, k = rng.randint(3, 40), rng.randint(2, 15)
        m = [[rng.randint(0, 1) for _ in range(k)] for _ in range(n)]
        if len({sum(r) for r in m}) < 2:
            continue
        assert cronbach_alpha(m) == pytest.approx(_kr20(m), abs=1e-12)


@pytest.mark.parametrize("matrix", [[[1, 0, 1]], [[1], [0], [1]], [[1, 0], [0, 1], [1, 0]]])
def test_alpha_is_none_when_undefined(matrix):
    # one student, one item, or totals that never vary
    assert cronbach_alpha(matrix) is None


def test_pearson_matches_the_raw_sums_formula():
    rng = random.Random(9)
    for _ in range(200):
        n = rng.randint(3, 50)
        x = [rng.randint(0, 3) for _ in range(n)]
        y = [rng.uniform(-2, 5) for _ in range(n)]
        sx, sy = sum(x), sum(y)
        num = n * sum(a * b for a, b in zip(x, y)) - sx * sy
        den = math.sqrt((n * sum(a * a for a in x) - sx ** 2) * (n * sum(b * b for b in y) - sy ** 2))
        if den == 0:
            assert pearson(x, y) is None
        else:
            assert pearson(x, y) == pytest.approx(num / den, abs=1e-9)


def test_pearson_extremes():
    assert pearson([1, 2, 3], [2, 4, 6]) == pytest.approx(1.0)
    assert pearson([1, 2, 3], [3, 2, 1]) == pytest.approx(-1.0)
    assert pearson([1, 1, 1], [1, 2, 3]) is None
    with pytest.raises(ValueError):
        pearson([1], [1])


def test_upper_lower_groups_size_and_ties():
    totals = [5, 1, 9, 1, 7, 3, 9, 2, 6, 4]          # n = 10, 27% -> 3
    lower, upper = upper_lower_groups(totals)
    assert len(lower) == len(upper) == 3
    assert lower == [1, 3, 7]                         # the two 1s (in order) then the 2
    assert upper == [4, 2, 6]                         # 7, then the two 9s in order
    assert upper_lower_groups([4, 2]) == ([1], [0])   # never smaller than one


@pytest.mark.parametrize("d, band", [(0.55, "very good"), (0.40, "very good"),
                                     (0.3999, "reasonably good"), (0.30, "reasonably good"),
                                     (0.29, "marginal"), (0.20, "marginal"),
                                     (0.1999, "poor"), (-0.3, "poor"), (None, None)])
def test_ebel_bands(d, band):
    assert ebel_band(d) == band


# -----------------------------------------------------------------------------
# A small class worked by hand
# -----------------------------------------------------------------------------

def _units():
    return generate_units(2, templates=["dal_price", "growth"], seed=3)


def _letters(q):
    wrong = [o["letter"] for o in q["options"] if o["letter"] != q["key"]]
    return q["key"], wrong


def _row(sid, units, right_mask):
    """right_mask: one bool per question, in booklet order."""
    row = {"student_id": sid}
    for ok, (lab, _, q) in zip(right_mask, question_labels(units)):
        if q["format"] == "multiple_choice":
            key, wrong = _letters(q)
            row[lab] = key if ok else wrong[0]
        elif q["format"] == "complex_multiple_choice":
            truth = "".join("T" if s["answer"] else "F" for s in q["statements"])
            row[lab] = truth if ok else "".join("F" if c == "T" else "T" for c in truth)
        else:
            row[lab] = "full" if ok else "CF"
    return row


def test_totals_match_the_scoring_module():
    units = _units()
    rng = random.Random(1)
    rows = [_row(f"S{i}", units, [rng.random() < 0.6 for _ in range(6)]) for i in range(25)]
    rows.append({"student_id": "absent"})
    m = item_matrix(units, rows)
    s = score_responses(units, rows)
    assert m["students"] == [x["student_id"] for x in s["students"]]
    assert [sum(r) for r in m["scores"]] == [x["score"] for x in s["students"]]


def test_difficulty_and_d_by_hand():
    units = _units()
    # 10 children. Question 1 (Q1.1) is right for the 4 strongest only.
    masks = [[i >= 6] + [i >= k for k in (3, 4, 5, 6, 7)] for i in range(10)]
    rows = [_row(f"S{i:02d}", units, mk) for i, mk in enumerate(masks)]
    a = analyze_items(units, rows)
    q11 = a["items"][0]
    assert q11["difficulty"] == pytest.approx(0.4)          # 4 of 10
    # groups of 3: top three all right, bottom three all wrong
    assert q11["d_index"] == pytest.approx(1.0)
    assert q11["ebel"] == "very good"
    assert a["group_size"] == 3


def test_blanks_count_as_zero_and_as_omitted():
    units = _units()
    rows = [_row(f"S{i}", units, [True] * 6) for i in range(8)]
    for r in rows[:2]:
        r["Q1.1"] = ""
    item = analyze_items(units, rows)["items"][0]
    assert item["difficulty"] == pytest.approx(6 / 8)
    assert item["omitted"] == pytest.approx(2 / 8)


def test_written_answers_use_their_point_scale():
    units = generate_units(1, templates=["data_plans"], seed=2)   # Q1.3 has partial credit
    rows = [{"student_id": "a", "Q1.1": "A", "Q1.3": "full"},
            {"student_id": "b", "Q1.1": "A", "Q1.3": "partial"},
            {"student_id": "c", "Q1.1": "A", "Q1.3": "none"},
            {"student_id": "d", "Q1.1": "A", "Q1.3": "CF"}]
    q13 = analyze_items(units, rows)["items"][2]
    assert q13["max_points"] == 2
    assert q13["difficulty"] == pytest.approx((2 + 1 + 0 + 0) / (4 * 2))


# -----------------------------------------------------------------------------
# Flags
# -----------------------------------------------------------------------------

def _class_with(units, pick, n=40):
    """pick(i, q, label) -> answer for child i."""
    rows = []
    for i in range(n):
        row = {"student_id": f"S{i:02d}"}
        for lab, _, q in question_labels(units):
            row[lab] = pick(i, q, lab)
        rows.append(row)
    return rows


def _ability_answers(i, q, lab, n=40):
    """Child i is right on a question when i is above a cut that differs by
    question, so stronger children (higher i) do better everywhere. The cuts
    are spread from 6 to 33 so totals rise steadily with i."""
    unit_no, q_no = (int(x) for x in lab[1:].split("."))
    cut = 6 + (((unit_no - 1) * 3 + q_no - 1) * 7) % 28
    right = i >= cut
    if q["format"] == "multiple_choice":
        key, wrong = _letters(q)
        return key if right else wrong[i % 3]
    if q["format"] == "complex_multiple_choice":
        truth = "".join("T" if s["answer"] else "F" for s in q["statements"])
        return truth if right else "".join("F" if c == "T" else "T" for c in truth)
    return "full" if right else "none"


def test_a_miskeyed_question_on_a_short_test_still_gets_flagged():
    """
    On a short test a miskeyed question drags down the totals of the very
    children who answered it 'wrong', so the top 27% by total can end up
    being the next tier down and D can come out near zero. The item-rest
    correlation, which leaves the question out of the total, still turns
    negative, and that is enough to raise the flag.
    """
    units = _units()
    q11 = question_labels(units)[0][2]
    key, wrong = _letters(q11)

    def pick(i, q, lab):
        if lab == "Q1.1":
            return wrong[0] if i >= 25 else key
        return _ability_answers(i, q, lab)

    item = analyze_items(units, _class_with(units, pick))["items"][0]
    assert item["item_rest_r"] < 0
    assert any("Check the key" in f for f in item["flags"])


def test_a_well_behaved_set_raises_no_discrimination_flags():
    units = _long_units()
    a = analyze_items(units, _class_with(units, _ability_answers))
    for item in a["items"]:
        assert item["d_index"] > 0.3
        assert not any("did worse" in f or "poorly" in f for f in item["flags"])
    assert a["alpha"] > 0.7


def _long_units():
    return generate_units(4, templates=["dal_price", "growth", "rainfall", "water_tank"], seed=3)


def test_a_miskeyed_question_is_flagged():
    units = _long_units()
    q11 = question_labels(units)[0][2]
    key, wrong = _letters(q11)

    def pick(i, q, lab):
        if lab == "Q1.1":        # the strongest children all choose the same "wrong" option
            return wrong[0] if i >= 28 else key
        return _ability_answers(i, q, lab)

    items = analyze_items(units, _class_with(units, pick))["items"]
    item = items[0]
    assert item["d_index"] < 0
    assert any("Check the key" in f for f in item["flags"])
    assert any(f"Option {wrong[0]} attracted more of the stronger" in f for f in item["flags"])
    # and it is the only question that looks broken
    for other in items[1:]:
        assert not any("did worse" in f or "poorly" in f or "attracted more" in f
                       for f in other["flags"]), other["label"]


def test_a_distractor_almost_nobody_picks_is_non_functioning():
    units = _units()
    q11 = question_labels(units)[0][2]
    key, wrong = _letters(q11)

    def pick(i, q, lab):
        if lab == "Q1.1":        # wrong[2] chosen by 1 child in 40 (2.5%)
            return wrong[2] if i == 0 else (wrong[i % 2] if i < 20 else key)
        return _ability_answers(i, q, lab)

    item = analyze_items(units, _class_with(units, pick))["items"][0]
    assert any(f"Option {wrong[2]} was chosen by fewer than 5%" in f for f in item["flags"])
    shares = {c["choice"]: c["share"] for c in item["choices"]}
    assert shares[wrong[2]] == pytest.approx(1 / 40)


def test_small_classes_get_a_warning():
    units = _units()
    assert analyze_items(units, _class_with(units, _ability_answers, n=12))["warnings"]
    assert not analyze_items(units, _class_with(units, _ability_answers, n=30))["warnings"]


def test_choice_shares_add_up():
    units = _units()
    a = analyze_items(units, _class_with(units, _ability_answers))
    for item in a["items"]:
        if item["format"] == "multiple_choice":
            assert sum(c["share"] for c in item["choices"]) + item["omitted"] == pytest.approx(1)


def test_bad_cells_and_empty_classes():
    units = _units()
    with pytest.raises(ValueError, match="student x, Q1.1"):
        analyze_items(units, [{"student_id": "x", "Q1.1": "Z"}])
    with pytest.raises(ValueError, match="no students"):
        analyze_items(units, [{"student_id": "absent"}])


def test_report():
    units = _units()
    md = format_item_report(analyze_items(units, _class_with(units, _ability_answers)))
    assert md.startswith("# Item analysis")
    for ref in ("Cronbach, L. J. (1951)", "Ebel, R. L. (1972)", "Haladyna, T. M., and Downing",
                "Kelley, T. L. (1939)"):
        assert ref in md
    assert not any(d in md for d in (chr(0x2014), chr(0x2013), " -" + "- "))


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def _write_class(path, units, rows):
    labels = [lab for lab, _, _ in question_labels(units)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("student_id," + ",".join(labels) + "\n")
        for r in rows:
            f.write(r["student_id"] + "," + ",".join(r.get(l, "") for l in labels) + "\n")


def test_cli_pools_classes_and_keeps_children_apart(tmp_path, capsys):
    units_path = tmp_path / "units.json"
    assert run(["pisa", "2", "--seed", "8", "--out", str(units_path)]) == 0
    capsys.readouterr()
    units = json.loads(units_path.read_text(encoding="utf-8"))
    a = _class_with(units, _ability_answers, n=20)
    _write_class(tmp_path / "classA.csv", units, a)
    _write_class(tmp_path / "classB.csv", units, a)         # same student ids on purpose
    report = tmp_path / "items.md"
    assert run(["pisa-items", str(units_path), str(tmp_path / "classA.csv"),
                str(tmp_path / "classB.csv"), "--report", str(report)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["n_students"] == 40
    assert report.read_text(encoding="utf-8").startswith("# Item analysis")


def test_cli_reports_errors(tmp_path, capsys):
    units_path = tmp_path / "u.json"
    run(["pisa", "1", "--seed", "1", "--out", str(units_path)])
    bad = tmp_path / "bad.csv"
    bad.write_text("student_id,Q1.1\nS1,Z\n", encoding="utf-8")
    capsys.readouterr()
    assert run(["pisa-items", str(units_path), str(bad)]) == 1
    assert "student S1, Q1.1" in capsys.readouterr().err
