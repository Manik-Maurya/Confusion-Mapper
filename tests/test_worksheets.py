"""
Tests for the teacher web page (worksheets/index.html) and the class scoring.

The page has its own JavaScript copy of the scoring, because it has to run
offline in a browser with no Python. Two copies of the same logic will drift
apart unless something checks them, so the main tests here run the page's
actual scoring code in Node and compare every number with the Python
version on random classes. They are skipped if Node is not installed.

The questions themselves are not duplicated: the page carries a pool of
units built by confusion_mapper.pisa, and a test checks that the pool in the
page is exactly what the generator builds today.
"""

import json
import math
import os
import random
import re
import shutil
import subprocess

import pytest

from confusion_mapper.pisa import (
    TEMPLATES,
    ERROR_TYPES,
    build_web_pool,
    validate_unit,
    question_labels,
    score_responses,
    format_class_report,
    response_sheet_csv,
    load_responses_csv,
    generate_units,
    WEB_POOL_PER_TEMPLATE,
)
from confusion_mapper.cli import run

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAGE = os.path.join(ROOT, "worksheets", "index.html")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(NODE is None, reason="node is not installed")


def _page():
    with open(PAGE, encoding="utf-8") as f:
        return f.read()


def _embedded_pool():
    m = re.search(r'<script id="cm-pool" type="application/json">(.*?)</script>', _page(), re.S)
    return json.loads(m.group(1))


def _core_js():
    return re.search(r'<script id="cm-core">(.*?)</script>', _page(), re.S).group(1)


# -----------------------------------------------------------------------------
# The page and its pool
# -----------------------------------------------------------------------------

def test_pool_in_the_page_matches_the_generator():
    """If this fails, run: python worksheets/build_pool.py"""
    assert _embedded_pool() == json.loads(json.dumps(build_web_pool()))


def test_pool_has_every_template_and_valid_units():
    pool = _embedded_pool()
    assert pool["template_order"] == list(TEMPLATES)
    counts = {}
    for u in pool["units"]:
        validate_unit(u)
        counts[u["template"]] = counts.get(u["template"], 0) + 1
    assert counts == {t: WEB_POOL_PER_TEMPLATE for t in TEMPLATES}
    ids = [u["unit_id"] for u in pool["units"]]
    assert len(ids) == len(set(ids))


def test_page_needs_no_internet():
    """Teachers may open a saved copy with no connection."""
    html = _page()
    assert not re.search(r'<script[^>]+src=', html)
    assert not re.search(r'<link[^>]+rel="?stylesheet', html)
    assert "@import" not in html


def test_page_has_no_ai_tells():
    html = _page()
    assert not any(d in html for d in (chr(0x2014), chr(0x2013), " -" + "- ", chr(0xB7)))


@needs_node
def test_page_scripts_parse(tmp_path):
    for i, body in enumerate(re.findall(r'<script(?: id="[^"]+")?>(.*?)</script>', _page(), re.S)):
        path = tmp_path / f"s{i}.js"
        path.write_text(body, encoding="utf-8")
        r = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True)
        assert r.returncode == 0, r.stderr


def _have_jsdom():
    if NODE is None:
        return False
    r = subprocess.run([NODE, "-e", "require('jsdom')"], capture_output=True, cwd=ROOT)
    return r.returncode == 0


@pytest.mark.skipif(not _have_jsdom(), reason="jsdom is not installed (npm install jsdom)")
def test_the_whole_page_works_for_a_teacher():
    """Runs worksheets/check_page.js: shared address, filters, tabs, entering
    answers, scoring, a bad cell, and a filter that matches nothing."""
    r = subprocess.run([NODE, os.path.join(ROOT, "worksheets", "check_page.js"), PAGE],
                       capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert r.returncode == 0, r.stderr
    assert "page check passed" in r.stdout


# -----------------------------------------------------------------------------
# Running the page's JavaScript in Node
# -----------------------------------------------------------------------------

RUNNER = r"""
const fs = require("fs");
const core = require(process.argv[2]);
const pool = JSON.parse(fs.readFileSync(process.argv[3], "utf8"));
const jobs = JSON.parse(fs.readFileSync(process.argv[4], "utf8"));
const out = jobs.map(job => {
  try {
    if (job.op === "score") {
      const units = job.units.map(i => pool.units[i]);
      return { ok: core.scoreResponses(units, job.responses, pool.error_types) };
    }
    if (job.op === "parse") {
      const q = pool.units[job.unit].questions[job.q];
      return { ok: core.parseAnswer(job.cell, "Q", q) };
    }
    if (job.op === "makeSet") {
      return { ok: core.makeSet(pool, job.n, job.contents, job.contexts, job.setNo).map(u => u.unit_id) };
    }
    if (job.op === "csv") {
      return { ok: core.parseCSV(core.toCSV(job.rows)) };
    }
    if (job.op === "toCSV") {
      return { ok: core.toCSV(job.rows) };
    }
  } catch (e) { return { error: e.message }; }
});
process.stdout.write(JSON.stringify(out));
"""


def _run_js(tmp_path, jobs):
    core = tmp_path / "core.js"
    core.write_text(_core_js(), encoding="utf-8")
    runner = tmp_path / "runner.js"
    runner.write_text(RUNNER, encoding="utf-8")
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps(_embedded_pool()), encoding="utf-8")
    job_file = tmp_path / "jobs.json"
    job_file.write_text(json.dumps(jobs), encoding="utf-8")
    r = subprocess.run([NODE, str(runner), str(core), str(pool), str(job_file)],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def _same(a, b, path="result"):
    if isinstance(a, float) or isinstance(b, float):
        assert a is not None and b is not None and math.isclose(a, b, abs_tol=1e-9), path
    elif isinstance(a, dict):
        assert isinstance(b, dict) and set(a) == set(b), f"{path}: keys {set(a) ^ set(b)}"
        for k in a:
            _same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, (list, tuple)):
        assert isinstance(b, (list, tuple)) and len(a) == len(b), f"{path}: lengths"
        for i, (x, y) in enumerate(zip(a, b)):
            _same(x, y, f"{path}[{i}]")
    else:
        assert a == b, f"{path}: {a!r} != {b!r}"


def _random_class(rng, units, n_students):
    rows = []
    for s in range(n_students):
        row = {"student_id": f"S{s + 1:02d}"}
        absent = rng.random() < 0.08
        for label, _, q in question_labels(units):
            if absent or rng.random() < 0.07:
                row[label] = ""
                continue
            if q["format"] == "multiple_choice":
                row[label] = q["key"] if rng.random() < 0.5 else rng.choice("ABCD").lower()
            elif q["format"] == "complex_multiple_choice":
                row[label] = " ".join(rng.choice("TFtf") for _ in q["statements"])
            else:
                opts = ["full", "none", "RF", "pk", "Cf", "INT"]
                if q["scoring"]["partial_credit"]:
                    opts.append("partial")
                row[label] = rng.choice(opts)
        rows.append(row)
    return rows


@needs_node
def test_javascript_scoring_matches_python_on_random_classes(tmp_path):
    pool = _embedded_pool()
    rng = random.Random(2026)
    jobs, expected = [], []
    for _ in range(60):
        idx = rng.sample(range(len(pool["units"])), rng.randint(1, 8))
        units = [pool["units"][i] for i in idx]
        responses = _random_class(rng, units, rng.randint(1, 40))
        jobs.append({"op": "score", "units": idx, "responses": responses})
        try:
            expected.append({"ok": json.loads(json.dumps(score_responses(units, responses)))})
        except ValueError as e:
            expected.append({"error": str(e)})
    got = _run_js(tmp_path, jobs)
    for i, (want, have) in enumerate(zip(expected, got)):
        if "error" in want:
            assert "error" in have, f"class {i}: Python refused, JavaScript scored"
        else:
            assert "ok" in have, f"class {i}: JavaScript failed: {have.get('error')}"
            _same(want["ok"], have["ok"], f"class {i}")


@needs_node
def test_javascript_and_python_reject_the_same_answers(tmp_path):
    pool = _embedded_pool()
    unit_by_format = {}
    for ui, u in enumerate(pool["units"]):
        for qi, q in enumerate(u["questions"]):
            key = (q["format"], bool(q.get("scoring", {}).get("partial_credit")))
            unit_by_format.setdefault(key, (ui, qi))
    cells = ["A", "d", " b ", "E", "AB", "", "TFT", "tft", "T F T", "TT", "TFTF", "TXT",
             "full", "FULL", "partial", "none", "rf", "INT", "int", "maybe", "2"]
    jobs, expected = [], []
    from confusion_mapper.pisa import _parse_answer
    for (ui, qi) in unit_by_format.values():
        q = pool["units"][ui]["questions"][qi]
        for cell in cells:
            jobs.append({"op": "parse", "unit": ui, "q": qi, "cell": cell})
            try:
                expected.append(_parse_answer(cell, "Q", q))
            except ValueError:
                expected.append("REJECTED")
    got = _run_js(tmp_path, jobs)
    for job, want, have in zip(jobs, expected, got):
        if want == "REJECTED":
            assert "error" in have, f"{job}: Python rejects, JavaScript accepts"
        else:
            assert have.get("ok") == want, f"{job}: {want!r} vs {have}"


@needs_node
def test_sets_are_reproducible_and_respect_filters(tmp_path):
    pool = _embedded_pool()
    jobs = [
        {"op": "makeSet", "n": 8, "contents": [], "contexts": [], "setNo": 4821},
        {"op": "makeSet", "n": 8, "contents": [], "contexts": [], "setNo": 4821},
        {"op": "makeSet", "n": 8, "contents": [], "contexts": [], "setNo": 4822},
        {"op": "makeSet", "n": 6, "contents": ["space_and_shape"], "contexts": [], "setNo": 7},
        {"op": "makeSet", "n": 4, "contents": [], "contexts": ["personal"], "setNo": 9},
        {"op": "makeSet", "n": 2, "contents": ["quantity"], "contexts": ["scientific"], "setNo": 1},
        {"op": "makeSet", "n": 60, "contents": [], "contexts": ["personal"], "setNo": 1},
    ]
    got = _run_js(tmp_path, jobs)
    by_id = {u["unit_id"]: u for u in pool["units"]}
    assert got[0] == got[1]                                    # same number, same set
    assert got[0] != got[2]                                    # next number, different set
    assert sorted(by_id[i]["template"] for i in got[0]["ok"]) == sorted(TEMPLATES)
    assert {by_id[i]["content"] for i in got[3]["ok"]} == {"space_and_shape"}
    assert len(set(got[3]["ok"])) == 6                         # no unit twice
    assert {by_id[i]["context"] for i in got[4]["ok"]} == {"personal"}
    assert "No unit matches" in got[5]["error"]
    assert "Not enough different units" in got[6]["error"]


@needs_node
def test_csv_from_the_page_reads_back_in_python(tmp_path):
    units = generate_units(3, seed=4)
    labels = [lab for lab, _, _ in question_labels(units)]
    rows = [["student_id"] + labels,
            ["Riya, S.", "B", "c"] + [""] * (len(labels) - 2),
            ['Aman "A"', ""] + [""] * (len(labels) - 1)]
    got = _run_js(tmp_path, [{"op": "csv", "rows": rows}, {"op": "toCSV", "rows": rows}])
    assert got[0]["ok"] == rows                                # JS round trip
    path = tmp_path / "answers.csv"
    path.write_text(got[1]["ok"], encoding="utf-8")
    read = load_responses_csv(str(path))
    assert [r["student_id"] for r in read] == ["Riya, S.", 'Aman "A"']
    assert read[0]["Q1.1"] == "B"


# -----------------------------------------------------------------------------
# Python scoring on its own
# -----------------------------------------------------------------------------

def _tiny_class():
    units = generate_units(2, templates=["dal_price", "growth"], seed=3)
    q = {lab: q for lab, _, q in question_labels(units)}
    wrong_letter = next(o["letter"] for o in q["Q1.1"]["options"] if o["letter"] != q["Q1.1"]["key"])
    rows = [
        {"student_id": "all_right", "Q1.1": q["Q1.1"]["key"], "Q1.2": q["Q1.2"]["key"],
         "Q1.3": "full", "Q2.1": q["Q2.1"]["key"], "Q2.2": q["Q2.2"]["key"],
         "Q2.3": "".join("T" if s["answer"] else "F" for s in q["Q2.3"]["statements"])},
        {"student_id": "one_wrong", "Q1.1": wrong_letter, "Q1.3": "CF"},
        {"student_id": "absent"},
    ]
    return units, q, wrong_letter, rows


def test_full_marks_and_points():
    units, q, _, rows = _tiny_class()
    r = score_responses(units, rows)
    top = r["students"][0]
    assert top["score"] == top["max_score"] == 6       # 5 one-point questions + 1 written
    assert sum(top["errors"].values()) == 0 and top["dominant_error"] is None


def test_wrong_answers_are_diagnosed_from_the_key():
    units, q, wrong_letter, rows = _tiny_class()
    r = score_responses(units, rows)
    s = r["students"][1]
    text = next(o["text"] for o in q["Q1.1"]["options"] if o["letter"] == wrong_letter)
    expected_type = next(d["error_type"] for d in q["Q1.1"]["distractors"] if d["option"] == text)
    want = {c: 0 for c in ERROR_TYPES}
    want[expected_type] += 1
    want["CF"] += 1                                     # the written answer coded CF
    assert s["errors"] == want
    assert s["no_response"] == 4 and s["score"] == 0


def test_absent_children_are_skipped():
    units, _, _, rows = _tiny_class()
    assert score_responses(units, rows)["n_students"] == 2


def test_cfi_indices_follow_the_package_definitions():
    units, _, _, rows = _tiny_class()
    s = score_responses(units, rows)["students"][1]
    e = s["errors"]
    total = sum(e.values())
    assert s["cfi"]["CFI-CF"] == e["CF"] / total
    assert s["cfi"]["CFI-RF"] == e["RF"] / total
    assert s["cfi"]["CFI-INT"] == (e["INT"] / (e["INT"] + e["RF"]) if e["INT"] + e["RF"] else None)


@pytest.mark.parametrize("cell, label", [("E", "Q1.1"), ("TT", "Q2.3"), ("partial", "Q1.3"),
                                         ("maybe", "Q1.3")])
def test_bad_cells_name_the_student_and_question(cell, label):
    units, _, _, rows = _tiny_class()
    rows[1][label] = cell
    with pytest.raises(ValueError, match=f"student one_wrong, {re.escape(label)}"):
        score_responses(units, rows)


def test_duplicate_students_are_refused():
    units, _, _, rows = _tiny_class()
    rows.append(dict(rows[1]))
    with pytest.raises(ValueError, match="appears twice"):
        score_responses(units, rows)


def test_report_names_the_top_misconception():
    units, q, wrong_letter, rows = _tiny_class()
    md = format_class_report(score_responses(units, rows))
    assert md.startswith("# Class report: what to reteach first")
    assert "2 students" in md and "What usually helps" in md
    assert "Q1.1, option" in md or "Q1.3, written answer coded CF" in md
    assert not any(d in md for d in (chr(0x2014), chr(0x2013), " -" + "- "))


def test_response_sheet_shape():
    units = generate_units(2, seed=1)
    lines = response_sheet_csv(units, n_students=3).strip().split("\n")
    assert lines[0] == "student_id,Q1.1,Q1.2,Q1.3,Q2.1,Q2.2,Q2.3"
    assert lines[1].startswith("S01,") and len(lines) == 4


def test_cli_end_to_end(tmp_path, capsys):
    units_path, sheet = tmp_path / "units.json", tmp_path / "sheet.csv"
    assert run(["pisa", "2", "--seed", "5", "--out", str(units_path),
                "--response-sheet", str(sheet), "--students", "2"]) == 0
    capsys.readouterr()
    units = json.loads(units_path.read_text(encoding="utf-8"))
    labels = [lab for lab, _, _ in question_labels(units)]
    q11 = units[0]["questions"][0]
    sheet.write_text("student_id," + ",".join(labels) + "\n"
                     "S01," + q11["key"] + "," * (len(labels) - 1) + "\n"
                     "S02," + "," * (len(labels) - 1) + "\n", encoding="utf-8")
    report = tmp_path / "report.md"
    assert run(["pisa-score", str(units_path), str(sheet), "--report", str(report)]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["n_students"] == 1 and out["students"][0]["score"] == 1
    assert report.read_text(encoding="utf-8").startswith("# Class report")


def test_cli_score_reports_bad_cells(tmp_path, capsys):
    units_path = tmp_path / "u.json"
    run(["pisa", "1", "--seed", "1", "--out", str(units_path)])
    sheet = tmp_path / "s.csv"
    sheet.write_text("student_id,Q1.1\nS01,Z\n", encoding="utf-8")
    capsys.readouterr()
    assert run(["pisa-score", str(units_path), str(sheet)]) == 1
    assert "student S01, Q1.1" in capsys.readouterr().err
