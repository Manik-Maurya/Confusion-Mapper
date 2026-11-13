"""
Tests for comparing two rounds: the first test, then a follow-up set with
the same kinds of question and new numbers, after reteaching.
"""

import json

import pytest

from confusion_mapper.pisa import (
    generate_units,
    question_labels,
    score_responses,
    compare_rounds,
    format_comparison,
)
from confusion_mapper.cli import run

TEMPLATES = ["dal_price", "growth"]


def _class(units, cf_children, n=20):
    """Children 0..cf_children-1 choose the CF option or code wherever there is
    one; everyone else answers everything correctly."""
    rows = []
    for i in range(n):
        row = {"student_id": f"S{i:02d}"}
        for lab, _, q in question_labels(units):
            if q["format"] == "multiple_choice":
                cf = next((o["letter"] for o in q["options"] for d in q["distractors"]
                           if d["option"] == o["text"] and d["error_type"] == "CF"), None)
                row[lab] = cf if (cf and i < cf_children) else q["key"]
            elif q["format"] == "complex_multiple_choice":
                row[lab] = "".join("T" if s["answer"] else "F" for s in q["statements"])
            else:
                row[lab] = "CF" if i < cf_children else "full"
        rows.append(row)
    return rows


def _rounds(cf_before, cf_after):
    ub = generate_units(2, templates=TEMPLATES, seed=1)
    ua = generate_units(2, templates=TEMPLATES, seed=2)
    rb = score_responses(ub, _class(ub, cf_before))
    ra = score_responses(ua, _class(ua, cf_after))
    return compare_rounds(ub, rb, ua, ra)


def test_the_follow_up_has_new_numbers_but_the_same_kinds_of_question():
    ub = generate_units(2, templates=TEMPLATES, seed=1)
    ua = generate_units(2, templates=TEMPLATES, seed=2)
    assert [u["template"] for u in ub] == [u["template"] for u in ua]
    assert [q["prompt"] for u in ub for q in u["questions"]] != \
           [q["prompt"] for u in ua for q in u["questions"]]


def test_counts_and_rates():
    c = _rounds(cf_before=10, cf_after=3)
    assert c["n_before"] == c["n_after"] == 20
    assert c["rows"], "no rows"
    for r in c["rows"]:
        assert r["error_type"] == "CF"
        assert (r["before_count"], r["after_count"]) == (10, 3)
        assert r["before_rate"] == pytest.approx(0.5) and r["after_rate"] == pytest.approx(0.15)
    # every CF option and code counts once per child, so CF per child is the number of
    # questions that have a CF answer, times the share of children who chose it
    n_cf_questions = len(c["rows"])
    assert c["errors_per_child"]["CF"]["before"] == pytest.approx(n_cf_questions * 10 / 20)
    assert c["errors_per_child"]["CF"]["after"] == pytest.approx(n_cf_questions * 3 / 20)


def test_a_misconception_that_disappears_still_shows_up_with_zero():
    c = _rounds(cf_before=8, cf_after=0)
    assert c["rows"] and all(r["after_count"] == 0 for r in c["rows"])


def test_a_misconception_that_appears_only_in_the_follow_up_is_shown():
    c = _rounds(cf_before=0, cf_after=5)
    assert c["rows"] and all(r["before_count"] == 0 and r["after_count"] == 5 for r in c["rows"])


def test_sets_with_nothing_in_common_compare_nothing():
    ub = generate_units(1, templates=["dal_price"], seed=1)
    ua = generate_units(1, templates=["growth"], seed=1)
    c = compare_rounds(ub, score_responses(ub, _class(ub, 5)), ua, score_responses(ua, _class(ua, 5)))
    assert c["rows"] == []
    assert "nothing to compare" in format_comparison(c)


def test_rows_are_sorted_by_how_common_the_mistake_was_first():
    c = _rounds(cf_before=10, cf_after=3)
    rates = [r["before_rate"] for r in c["rows"]]
    assert rates == sorted(rates, reverse=True)


def test_report_wording():
    md = format_comparison(_rounds(cf_before=10, cf_after=3))
    assert md.startswith("# Before and after reteaching")
    assert "10 of 20 (50%)" in md and "3 of 20 (15%)" in md
    assert "not proof" in md
    assert not any(d in md for d in (chr(0x2014), chr(0x2013), " -" + "- "))


def _write(path, units, rows):
    labels = [lab for lab, _, _ in question_labels(units)]
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("student_id," + ",".join(labels) + "\n")
        for r in rows:
            f.write(r["student_id"] + "," + ",".join(r.get(l, "") for l in labels) + "\n")


def test_cli_pisa_compare(tmp_path, capsys):
    ub = generate_units(2, templates=TEMPLATES, seed=1)
    ua = generate_units(2, templates=TEMPLATES, seed=2)
    for name, units, cf in (("before", ub, 10), ("after", ua, 3)):
        (tmp_path / f"{name}.json").write_text(json.dumps(units), encoding="utf-8")
        _write(tmp_path / f"{name}.csv", units, _class(units, cf))
    report = tmp_path / "compare.md"
    code = run(["pisa-compare", str(tmp_path / "before.json"), str(tmp_path / "before.csv"),
                str(tmp_path / "after.json"), str(tmp_path / "after.csv"),
                "--report", str(report)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert all((r["before_count"], r["after_count"]) == (10, 3) for r in out["rows"])
    assert report.read_text(encoding="utf-8").startswith("# Before and after reteaching")


def test_cli_pisa_compare_reports_a_missing_file(tmp_path, capsys):
    assert run(["pisa-compare", "nope.json", "nope.csv", "nope2.json", "nope2.csv"]) == 1
    assert "[error]" in capsys.readouterr().err
