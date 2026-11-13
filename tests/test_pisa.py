"""
Tests for the PISA-style unit generator.

A generator like this fails quietly. A wrong correct answer, or a
distractor that happens to equal the answer, would go straight into a
printed booklet and confuse a whole class. So the main tests here do not
trust the templates: for every template and hundreds of seeds they take
the raw numbers stored in the unit and work out every answer again with
separate code.
"""

import json
import math
import os
import re
from fractions import Fraction

import pytest

from confusion_mapper.pisa import (
    TEMPLATES,
    CONTENT_CATEGORIES,
    CONTEXTS,
    PROCESSES,
    FORMATS,
    DISCLAIMER,
    generate_unit,
    generate_units,
    validate_unit,
    list_templates,
    coverage,
    units_to_item_bank,
    save_units,
    load_units,
    format_booklet,
    format_answer_key,
)
from confusion_mapper.itembank import _validate_item_shape
from confusion_mapper.taxonomy import ERROR_TYPES
from confusion_mapper.cli import run

ROOT = os.path.join(os.path.dirname(__file__), "..")
SEEDS = range(300)


def _q(unit, n):
    return unit["questions"][n - 1]


def _rupees(n):
    return f"Rs {n:,}"


def _clock(minutes):
    """A second, separate 12-hour clock formatter, so the test does not
    reuse the code it is checking."""
    h, m = int(minutes) // 60, int(minutes) % 60
    return f"{12 if h % 12 == 0 else h % 12}:{m:02d} {'am' if h < 12 else 'pm'}"


def _eval_expression(text):
    """Evaluate '1.5 × 1.2 × 1 × 1000' style answers."""
    return eval(text.replace("×", "*"), {"__builtins__": {}})


# -----------------------------------------------------------------------------
# Every answer, recomputed from the raw numbers
# -----------------------------------------------------------------------------

def check_data_plans(u):
    d = u["data"]
    assert _q(u, 1)["correct_answer"] == _rupees(d["fee"] + d["rate_a"] * d["u1"])
    assert _q(u, 2)["correct_answer"] == f"{d['fee']} + {d['rate_a']}x"
    cost_a, cost_b = d["fee"] + d["rate_a"] * d["u2"], d["rate_b"] * d["u2"]
    assert cost_a != cost_b, "a tie would make the question unanswerable"
    expected = "Plan A" if cost_a < cost_b else "Plan B"
    assert _q(u, 3)["scoring"]["accepted_answers"] == [expected]


def check_rainfall(u):
    d = u["data"]
    months = {"June": d["june"], "July": d["july"], "August": d["august"],
              "September": d["september"]}
    total = sum(months.values())
    assert _q(u, 1)["correct_answer"] == max(months, key=months.get)
    assert total % 4 == 0
    assert _q(u, 2)["correct_answer"] == f"{total // 4} mm"
    truths = [s["answer"] for s in _q(u, 3)["statements"]]
    v = list(months.values())
    assert truths == [d["july"] > 2 * d["june"],
                      v[0] < v[1] < v[2] < v[3],
                      total > d["threshold"]]
    assert [r[1] for r in u["table"]["rows"]] == v


def check_school_garden(u):
    d = u["data"]
    fence = 2 * (d["length"] + d["width"]) - d["gate"]
    assert _q(u, 1)["correct_answer"] == f"{fence} m"
    assert (2 * d["length"]) * (2 * d["width"]) == 4 * d["length"] * d["width"]
    assert _q(u, 2)["correct_answer"] == "It is 4 times as large."
    cost = d["rate"] * fence
    assert cost != d["budget"]
    assert _q(u, 3)["scoring"]["accepted_answers"] == ["Yes" if d["budget"] > cost else "No"]


def check_bus_journey(u):
    d = u["data"]
    drive_minutes = Fraction(d["distance"], d["speed"]) * 60
    assert drive_minutes.denominator == 1
    assert _q(u, 1)["correct_answer"] == f"{d['distance']} ÷ {d['speed']}"
    assert _q(u, 2)["correct_answer"] == _clock(d["depart"] + int(drive_minutes) + d["stop"])
    overall = d["distance"] / ((int(drive_minutes) + d["stop"]) / 60)
    assert overall < d["speed"]
    assert _q(u, 3)["scoring"]["accepted_answers"] == ["No"]


def check_dal_price(u):
    d = u["data"]
    rise = Fraction(d["price"]) * (1 + Fraction(d["percent"], 100))
    after = rise * (1 - Fraction(d["percent"], 100))
    assert rise.denominator == 1 and after.denominator == 1
    assert _q(u, 1)["correct_answer"] == _rupees(int(rise))
    assert _q(u, 2)["correct_answer"].startswith(f"It is {_rupees(int(after))}, less")
    assert after < d["price"]
    assert _q(u, 3)["scoring"]["accepted_answers"] == [str(d["money"] // int(rise))]
    assert d["money"] % int(rise) != 0


def check_travel_survey(u):
    d = u["data"]
    assert d["walk"] + d["cycle"] + d["bus"] + d["other"] == d["total"]
    assert d["walk"] > max(d["cycle"], d["bus"], d["other"])      # biggest group...
    assert d["walk"] * 2 < d["total"]                              # ...but not a majority
    assert (d["cycle"] * 100) % d["total"] == 0
    assert _q(u, 1)["correct_answer"] == f"{d['cycle'] * 100 // d['total']}%"
    p = Fraction(d["bus"], d["total"])
    assert _q(u, 2)["correct_answer"] == f"{p.numerator}/{p.denominator}"


def check_water_tank(u):
    d = u["data"]
    litres = d["length_cm"] * d["width_cm"] * d["height_cm"] / 1000
    q1 = _q(u, 1)
    assert _eval_expression(q1["correct_answer"]) == pytest.approx(litres)
    wrong = {x["error_type"]: _eval_expression(x["option"]) for x in q1["distractors"]}
    assert wrong["PK"] == pytest.approx(litres / 1000)
    assert wrong["CF"] == pytest.approx(litres / 10)
    assert litres % d["pump_rate"] == 0
    assert _q(u, 2)["correct_answer"] == f"{int(litres // d['pump_rate'])} minutes"
    assert _q(u, 3)["scoring"]["accepted_answers"] == [str(math.floor(litres / 2 / d["daily_use"]))]


def check_growth(u):
    d = u["data"]

    def a(h):
        return d["a0"] * 2 ** h

    def b(h):
        return d["b0"] + d["k"] * h

    overtake = min(h for h in range(1, 60) if a(h) > b(h))
    assert _q(u, 1)["correct_answer"] == f"{a(d['h1']):,} thousand"
    assert _q(u, 2)["correct_answer"] == f"After {overtake} hours"
    assert a(overtake - 1) <= b(overtake - 1)
    truths = [s["answer"] for s in _q(u, 3)["statements"]]
    assert truths == [False, True, a(d["h3"]) > 2 * b(d["h3"])]


CHECKS = {
    "data_plans": check_data_plans, "rainfall": check_rainfall,
    "school_garden": check_school_garden, "bus_journey": check_bus_journey,
    "dal_price": check_dal_price, "travel_survey": check_travel_survey,
    "water_tank": check_water_tank, "growth": check_growth,
}


def test_every_template_has_an_independent_check():
    assert set(CHECKS) == set(TEMPLATES)


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_every_answer_is_right(template):
    for seed in SEEDS:
        CHECKS[template](generate_unit(template, seed=seed))


# -----------------------------------------------------------------------------
# Structure of every question
# -----------------------------------------------------------------------------

def test_growth_tie_is_not_counted_as_overtaking():
    """
    With A starting at 5 and B at 60 gaining 20 an hour, both samples have
    exactly 160 thousand cells after 5 hours. "More cells" means hour 6, not
    hour 5. I found this case by planting a >= instead of > in the template:
    the tie units silently disappeared instead of failing, so this test now
    makes sure they exist and are answered correctly.
    """
    tie_units = [u for u in (generate_unit("growth", seed=s) for s in range(3000))
                 if (u["data"]["a0"], u["data"]["b0"], u["data"]["k"]) == (5, 60, 20)]
    assert tie_units, "the tie case should come up in 3000 seeds"
    for u in tie_units:
        assert _q(u, 2)["correct_answer"] == "After 6 hours"


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_multiple_choice_options_are_clean(template):
    for seed in SEEDS:
        for q in generate_unit(template, seed=seed)["questions"]:
            if q["format"] != "multiple_choice":
                continue
            texts = [o["text"] for o in q["options"]]
            assert len(texts) == 4 and len(set(texts)) == 4
            assert q["correct_answer"] in texts
            assert q["correct_answer"] not in [d["option"] for d in q["distractors"]]
            key_text = next(o["text"] for o in q["options"] if o["letter"] == q["key"])
            assert key_text == q["correct_answer"]
            for t in texts:
                assert not re.search(r"nan|inf|\d\.\d{4,}", t), f"messy option {t!r}"


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_every_wrong_answer_is_diagnosed(template):
    u = generate_unit(template, seed=1)
    for q in u["questions"]:
        entries = (q.get("distractors") or [s["if_wrong"] for s in q.get("statements", [])]
                   or q.get("common_wrong_answers"))
        assert entries
        for e in entries:
            assert e["error_type"] in ERROR_TYPES and e["note"].strip()


@pytest.mark.parametrize("template", sorted(TEMPLATES))
def test_metadata_uses_the_framework_categories(template):
    u = generate_unit(template, seed=2)
    assert u["content"] in CONTENT_CATEGORIES and u["context"] in CONTEXTS
    assert all(q["process"] in PROCESSES and q["format"] in FORMATS for q in u["questions"])
    assert len(u["questions"]) == 3


def test_full_set_covers_every_dimension_of_the_framework():
    cov = coverage(generate_units(len(TEMPLATES), seed=4))
    assert set(cov["content"]) == set(CONTENT_CATEGORIES)
    assert set(cov["context"]) == set(CONTEXTS)
    assert set(cov["process"]) == set(PROCESSES)
    assert set(cov["format"]) == set(FORMATS)
    assert len(set(cov["content"].values())) == 1      # perfectly balanced
    assert len(set(cov["context"].values())) == 1


def test_answer_letters_are_spread_out():
    keys = [q["key"] for seed in range(150) for u in generate_units(8, seed=seed)
            for q in u["questions"] if q["format"] == "multiple_choice"]
    for letter in "ABCD":
        assert 0.18 < keys.count(letter) / len(keys) < 0.32


# -----------------------------------------------------------------------------
# Determinism and filters
# -----------------------------------------------------------------------------

def test_same_seed_same_units():
    assert generate_units(8, seed=7) == generate_units(8, seed=7)


def test_different_seeds_change_the_numbers():
    datas = {json.dumps(generate_unit("dal_price", seed=s)["data"], sort_keys=True)
             for s in range(30)}
    assert len(datas) > 5


def test_unit_ids_are_unique_in_a_set():
    ids = [u["unit_id"] for u in generate_units(20, seed=1)]
    assert len(ids) == len(set(ids))


def test_filters():
    for u in generate_units(6, content=["space_and_shape"], seed=1):
        assert u["content"] == "space_and_shape"
    for u in generate_units(4, context=["personal"], seed=1):
        assert u["context"] == "personal"
    assert {u["template"] for u in generate_units(3, templates=["growth"], seed=1)} == {"growth"}


@pytest.mark.parametrize("kwargs", [
    {"n": 0}, {"n": 2, "content": ["algebra"]}, {"n": 2, "context": ["moon"]},
    {"n": 2, "templates": ["nope"]},
    {"n": 2, "content": ["quantity"], "context": ["scientific"]},   # nothing matches
])
def test_bad_requests(kwargs):
    with pytest.raises(ValueError):
        generate_units(**kwargs)


def test_unknown_single_template():
    with pytest.raises(ValueError):
        generate_unit("cricket")


def test_list_templates_matches_the_units_they_build():
    for name, content, context in list_templates():
        u = generate_unit(name, seed=0)
        assert (u["content"], u["context"]) == (content, context)


# -----------------------------------------------------------------------------
# Validation catches broken units
# -----------------------------------------------------------------------------

def _broken(mutate):
    u = json.loads(json.dumps(generate_unit("data_plans", seed=1)))
    mutate(u)
    return u


@pytest.mark.parametrize("mutate", [
    lambda u: u.update(content="algebra"),
    lambda u: u.update(context="moon"),
    lambda u: u["questions"][0].update(process="guess"),
    lambda u: u["questions"][0]["options"][1].update(text=u["questions"][0]["options"][0]["text"]),
    lambda u: u["questions"][0].update(key="Z" if False else
                                       next(o["letter"] for o in u["questions"][0]["options"]
                                            if o["text"] != u["questions"][0]["correct_answer"])),
    lambda u: u["questions"][0]["distractors"][0].update(error_type="XX"),
    lambda u: u["questions"][0]["distractors"][0].update(note=" "),
    lambda u: u["questions"][2]["scoring"].update(accepted_answers=[]),
    lambda u: u["questions"][1].update(format="essay"),
])
def test_validator_catches(mutate):
    with pytest.raises(ValueError):
        validate_unit(_broken(mutate))


def test_complex_statement_answers_must_be_booleans():
    u = json.loads(json.dumps(generate_unit("growth", seed=1)))
    u["questions"][2]["statements"][0]["answer"] = "false"
    with pytest.raises(ValueError):
        validate_unit(u)


def test_save_and_load_round_trip(tmp_path):
    units = generate_units(5, seed=2)
    path = save_units(units, str(tmp_path / "units.json"))
    assert load_units(path) == units


# -----------------------------------------------------------------------------
# Booklet and key
# -----------------------------------------------------------------------------

def _no_ai_tells(text):
    return not any(d in text for d in (chr(0x2014), chr(0x2013), " -" + "- "))


def test_booklet_has_every_question_and_no_answers():
    units = generate_units(8, seed=5)
    booklet = format_booklet(units)
    for u in units:
        assert u["title"] in booklet
        for q in u["questions"]:
            assert q["prompt"] in booklet
    for giveaway in ("Answer:", "Confabulation", "Interference", "Full credit", "PISA_"):
        if giveaway == "Answer:":
            # only the blank answer lines for written answers are allowed
            assert all("____" in line for line in booklet.splitlines() if "Answer:" in line)
        else:
            assert giveaway not in booklet
    assert DISCLAIMER in booklet
    assert _no_ai_tells(booklet)


def test_key_diagnoses_every_wrong_option():
    units = generate_units(8, seed=5)
    key = format_answer_key(units)
    for u in units:
        assert u["unit_id"] in key
        for q in u["questions"]:
            if q["format"] == "multiple_choice":
                assert f"**Answer: {q['key']}** ({q['correct_answer']})" in key
                for d in q["distractors"]:
                    assert d["note"] in key
            elif q["format"] == "constructed_response":
                assert q["scoring"]["full_credit"] in key
    for name in ("Recall Failure", "Partial Knowledge", "Confabulation", "Interference"):
        assert name in key
    assert _no_ai_tells(key)


def test_key_reports_coverage():
    key = format_answer_key(generate_units(8, seed=5))
    assert "| Content | Change and relationships 6, Quantity 6, Space and shape 6, " \
           "Uncertainty and data 6 |" in key


# -----------------------------------------------------------------------------
# Plugging into the rest of ConfusionMapper
# -----------------------------------------------------------------------------

def test_item_bank_export_passes_the_generate_bank_validator():
    bank = units_to_item_bank(generate_units(8, seed=9))
    assert len(bank) == 16                  # two multiple-choice questions per unit
    for item in bank:
        _validate_item_shape(item)


def test_item_bank_export_keeps_the_stimulus():
    units = generate_units(8, seed=9)
    bank = {i["id"]: i for i in units_to_item_bank(units)}
    rain = next(u for u in units if u["template"] == "rainfall")
    text = bank[rain["questions"][0]["qid"]]["question_text"]
    assert rain["stimulus"] in text and "Rainfall (mm)" in text


def test_item_bank_has_the_shape_run_session_reads():
    for q in units_to_item_bank(generate_units(3, seed=1)):
        _ = q["id"], q["topic"], q["question_text"], q["correct_answer"]
        for d in q["distractors"]:
            _ = d["option"], d["error_type"]


# -----------------------------------------------------------------------------
# The examples shipped in the repo are what the generator really produces
# -----------------------------------------------------------------------------

def test_committed_examples_are_up_to_date():
    units = generate_units(8, seed=20261112)
    with open(os.path.join(ROOT, "examples", "pisa_booklet_example.md"), encoding="utf-8") as f:
        assert f.read() == format_booklet(units)
    with open(os.path.join(ROOT, "examples", "pisa_teacher_key_example.md"),
              encoding="utf-8") as f:
        assert f.read() == format_answer_key(units)


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def test_cli_list(capsys):
    assert run(["pisa", "--list"]) == 0
    out = capsys.readouterr().out
    assert all(name in out for name in TEMPLATES)


def test_cli_writes_everything(tmp_path, capsys):
    paths = {k: tmp_path / f"{k}.x" for k in ("out", "booklet", "key", "bank")}
    code = run(["pisa", "4", "--seed", "1", "--out", str(paths["out"]),
                "--booklet", str(paths["booklet"]), "--key", str(paths["key"]),
                "--item-bank", str(paths["bank"])])
    assert code == 0
    assert len(load_units(str(paths["out"]))) == 4
    assert paths["booklet"].read_text(encoding="utf-8").startswith("# Maths in real life")
    assert "teacher's key" in paths["key"].read_text(encoding="utf-8")
    assert len(json.loads(paths["bank"].read_text(encoding="utf-8"))) == 8
    assert "content" in json.loads(capsys.readouterr().out)


def test_cli_prints_units_when_no_file_is_given(capsys):
    assert run(["pisa", "2", "--seed", "3", "--templates", "growth,rainfall"]) == 0
    units = json.loads(capsys.readouterr().out)
    assert [u["template"] for u in units] == ["growth", "rainfall"]


def test_cli_errors(capsys):
    assert run(["pisa"]) == 1
    assert run(["pisa", "3", "--content", "algebra"]) == 1
    assert "unknown content category" in capsys.readouterr().err
