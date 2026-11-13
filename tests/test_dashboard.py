"""
Tests for the agreement page, dashboard/index.html.

The page carries its own copy of the package's agreement functions and runs
them in the browser through Pyodide. The first test checks the page for the
same writing rules as the rest of the repo. The second runs the real page in
jsdom with real Pyodide, presses the button the way a researcher would, and
checks every number on screen against the Python package. It needs Node with
jsdom and pyodide installed, and is skipped without them (the CI job
"Every test, nothing skipped" installs both).
"""

import json
import os
import random
import shutil
import subprocess

import pytest

from confusion_mapper import stats

ROOT = os.path.join(os.path.dirname(__file__), "..")
PAGE = os.path.join(ROOT, "dashboard", "index.html")
NODE = shutil.which("node")
ET = ["RF", "PK", "CF", "INT"]


def _have(module):
    if NODE is None:
        return False
    r = subprocess.run([NODE, "-e", f"require('{module}')"], capture_output=True, cwd=ROOT)
    return r.returncode == 0


def test_page_has_no_dashes_or_stray_symbols():
    with open(PAGE, encoding="utf-8") as f:
        html = f.read()
    for bad in (chr(0x2014), chr(0x2013), "\\u2014", "\\u2013", "&mdash;", "&ndash;",
                " -" + "- "):
        assert bad not in html, bad
    assert "<title>ConfusionMapper - " not in html
    # a count of commands goes stale every time one is added
    assert "CLI has sixteen" not in html


def _expected(h, a):
    """What the package gives for the categories the page would use."""
    cats = sorted(set(h) | set(a), key=lambda c: ET.index(c) if c in ET else 99)
    if len(cats) < 2 and set(cats) <= set(ET):
        cats = list(ET)
    return {"kappa": stats.compute_cohens_kappa(h, a, categories=cats)["kappa"],
            "ac1": stats.gwet_ac1(h, a, categories=cats)["ac1"],
            "pabak": stats.compute_kappa_diagnostics(h, a, categories=cats)["pabak"],
            "n": len(h)}


def _csv(h, a, eol="\n"):
    rows = ["item_id,human_label,ai_label"] + [f"Q{i},{x},{y}" for i, (x, y) in enumerate(zip(h, a))]
    return eol.join(rows)


@pytest.mark.skipif(not (_have("jsdom") and _have("pyodide")),
                    reason="needs node with jsdom and pyodide (npm install jsdom pyodide@0.26.1)")
def test_page_shows_the_same_numbers_as_the_package(tmp_path):
    example_h = "PK CF INT RF CF PK RF INT CF PK RF PK CF INT RF".split()
    example_a = "PK CF PK RF CF PK RF INT CF CF RF PK CF INT RF".split()
    cases = [{"name": "the page's own example", "csv": None, "want": _expected(example_h, example_a)}]
    rng = random.Random(11)
    for t in range(8):
        n = rng.randint(2, 40)
        h = [rng.choice(ET) for _ in range(n)]
        a = [x if rng.random() < 0.7 else rng.choice(ET) for x in h]
        cases.append({"name": f"random {t}", "csv": _csv(h, a, "\r\n" if t % 2 else "\n"),
                      "want": _expected(h, a)})
    cases.append({"name": "every label CF", "csv": _csv(["CF"] * 6, ["CF"] * 6),
                  "want": _expected(["CF"] * 6, ["CF"] * 6)})
    h, a = ["yes", "no", "maybe", "yes", "no"], ["yes", "no", "no", "yes", "maybe"]
    cases.append({"name": "a scheme of your own", "csv": _csv(h, a), "want": _expected(h, a)})
    cases.append({"name": "one label only", "csv": _csv(["yes"] * 4, ["yes"] * 4), "want": None})

    case_file = tmp_path / "cases.json"
    case_file.write_text(json.dumps(cases), encoding="utf-8")
    r = subprocess.run([NODE, os.path.join(ROOT, "dashboard", "check_dashboard.js"), PAGE,
                        str(case_file)], capture_output=True, text=True, timeout=240, cwd=ROOT)
    assert r.returncode == 0, r.stderr[-2000:]
    got = json.loads(r.stdout)
    assert got["errors"] == []
    for case, shown in zip(cases, got["out"]):
        if case["want"] is None:
            assert "at least two categories" in shown["status"], case["name"]
            assert shown["kappa"] == "", case["name"]
            continue
        for key in ("kappa", "ac1", "pabak", "n"):
            assert float(shown[key]) == pytest.approx(case["want"][key], abs=1e-9), \
                f"{case['name']}: {key} shows {shown[key]}, package gives {case['want'][key]}"
        assert shown["svg"], case["name"]
        assert "nothing was uploaded" in shown["status"], case["name"]
