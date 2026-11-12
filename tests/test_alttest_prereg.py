"""
Tests for the alt-test preregistration lock.

The point of the lock is that a researcher cannot quietly change epsilon
(or anything else that decides the verdict) after seeing the data. So the
tests check four things: the hash only depends on the decisions, editing a
plan is caught, a run that departs from the plan is stopped, and when the
researcher overrides that, every deviation is written down.
"""

import json
import os

import pytest

from confusion_mapper.alttest import (
    create_prereg,
    save_prereg,
    load_prereg,
    check_against_prereg,
    alt_test,
    load_alttest_csv,
    format_alttest_report,
    format_comparison_report,
    compare_judges,
)
from confusion_mapper.cli import run

ROOT = os.path.join(os.path.dirname(__file__), "..")
EXAMPLE = os.path.join(ROOT, "sample_data", "example_alttest.csv")
EXAMPLE_PLAN = os.path.join(ROOT, "sample_data", "example_alttest_prereg.json")
HUMANS = ["coder_A", "coder_B", "coder_C"]
AIS = ["ai_prompt_v1", "ai_prompt_v2"]

SETTINGS = dict(epsilon=0.15, q_fdr=0.05, scoring="accuracy", min_instances_per_human=30,
                min_humans_per_instance=2, pass_threshold=0.5)


def _plan(**kw):
    base = dict(annotators="skilled", ai_columns=AIS, human_columns=HUMANS, planned_items=81)
    base.update(kw)
    return create_prereg(**base)


# -----------------------------------------------------------------------------
# Creating a plan
# -----------------------------------------------------------------------------

def test_preset_fills_in_epsilon_and_says_where_it_came_from():
    s = _plan()["locked"]["settings"]
    assert s["epsilon"] == 0.15
    assert s["epsilon_source"] == "authors' preset for skilled coders"


def test_explicit_epsilon_is_marked_as_the_researchers_choice():
    s = create_prereg(epsilon=0.12)["locked"]["settings"]
    assert s["epsilon"] == 0.12 and s["epsilon_source"] == "chosen by the researcher"


def test_hash_is_sha256_and_depends_only_on_the_decisions():
    a, b = _plan(notes="first draft"), _plan(notes="something else entirely")
    assert len(a["sha256"]) == 64 and int(a["sha256"], 16) >= 0
    assert a["sha256"] == b["sha256"]                     # notes and date are not locked
    assert _plan(annotators="expert")["sha256"] != a["sha256"]
    assert _plan(planned_items=100)["sha256"] != a["sha256"]
    assert _plan(human_columns=["coder_A", "coder_B"])["sha256"] != a["sha256"]


@pytest.mark.parametrize("kwargs", [
    {},                                         # neither epsilon nor annotators
    {"epsilon": 0.1, "annotators": "crowd"},    # both
    {"annotators": "wizard"},
    {"epsilon": 1.2},
    {"epsilon": 0.1, "scoring": "f1"},
    {"epsilon": 0.1, "q_fdr": 0},
    {"epsilon": 0.1, "pass_threshold": 0},
    {"epsilon": 0.1, "planned_items": 0},
])
def test_bad_plans_are_refused(kwargs):
    with pytest.raises(ValueError):
        create_prereg(**kwargs)


# -----------------------------------------------------------------------------
# Saving, loading, tampering
# -----------------------------------------------------------------------------

def test_round_trip(tmp_path):
    plan = _plan()
    path = save_prereg(plan, str(tmp_path / "plan.json"))
    assert load_prereg(path) == plan


def test_editing_a_locked_setting_is_caught(tmp_path):
    plan = _plan()
    plan["locked"]["settings"]["epsilon"] = 0.3      # the hash still says 0.15
    path = save_prereg(plan, str(tmp_path / "plan.json"))
    with pytest.raises(ValueError, match="edited after it was created"):
        load_prereg(path)


def test_editing_the_notes_is_fine(tmp_path):
    plan = _plan()
    plan["notes"] = "added a sentence later"
    assert load_prereg(save_prereg(plan, str(tmp_path / "plan.json")))["notes"].startswith("added")


def test_a_random_json_file_is_not_a_plan(tmp_path):
    path = tmp_path / "other.json"
    path.write_text(json.dumps({"hello": "world"}), encoding="utf-8")
    with pytest.raises(ValueError, match="not a ConfusionMapper"):
        load_prereg(str(path))


def test_the_example_plan_is_intact():
    plan = load_prereg(EXAMPLE_PLAN)
    assert plan["locked"]["settings"]["epsilon"] == 0.15
    assert plan["locked"]["design"]["ai_columns"] == AIS


# -----------------------------------------------------------------------------
# Checking a run against the plan
# -----------------------------------------------------------------------------

def test_matching_run_has_no_deviations():
    c = check_against_prereg(_plan(), SETTINGS, AIS, HUMANS, n_items=81)
    assert c["matches"] and c["deviations"] == [] and c["notes"] == []


def test_a_bigger_epsilon_is_a_deviation():
    c = check_against_prereg(_plan(), dict(SETTINGS, epsilon=0.2), AIS, HUMANS, 81)
    assert not c["matches"]
    assert c["deviations"] == ["epsilon: preregistered 0.15, used 0.2"]


def test_dropping_a_coder_is_a_deviation():
    c = check_against_prereg(_plan(), SETTINGS, AIS, ["coder_A", "coder_B"], 81)
    assert not c["matches"] and "human_columns" in c["deviations"][0]


def test_column_order_does_not_matter():
    c = check_against_prereg(_plan(), SETTINGS, list(reversed(AIS)), list(reversed(HUMANS)), 81)
    assert c["matches"]


def test_a_different_item_count_is_a_note_not_a_deviation():
    c = check_against_prereg(_plan(), SETTINGS, AIS, HUMANS, n_items=75)
    assert c["matches"]
    assert c["notes"] == ["planned 81 items, analysed 75"]


def test_plan_without_columns_does_not_constrain_columns():
    plan = create_prereg(annotators="skilled")
    assert check_against_prereg(plan, SETTINGS, ["anything"], ["a", "b", "c"], 10)["matches"]


# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------

def _example_result():
    humans, ais = load_alttest_csv(EXAMPLE, AIS)
    return humans, ais, alt_test(ais["ai_prompt_v1"], humans, epsilon=0.15)


def test_report_states_the_match_and_the_hash():
    _, _, r = _example_result()
    plan = _plan()
    md = format_alttest_report(r, prereg_check=check_against_prereg(plan, SETTINGS, AIS, HUMANS, 81))
    assert "Every setting matches the preregistered plan" in md
    assert plan["sha256"] in md
    assert "fixed in advance in plan" in md                 # checklist item 2
    assert "preregistered analysis plan" in md              # methods paragraph


def test_report_lists_every_deviation():
    _, _, r = _example_result()
    check = check_against_prereg(_plan(), dict(SETTINGS, epsilon=0.2, q_fdr=0.1), AIS, HUMANS, 81)
    md = format_alttest_report(r, prereg_check=check)
    assert "This run departs from the preregistered plan" in md
    assert "epsilon: preregistered 0.15, used 0.2" in md
    assert "q_fdr: preregistered 0.05, used 0.1" in md
    assert "with 2 deviation(s)" in md


def test_comparison_report_shows_the_plan_once():
    humans, ais, _ = _example_result()
    check = check_against_prereg(_plan(), SETTINGS, AIS, HUMANS, 81)
    md = format_comparison_report(compare_judges(ais, humans, epsilon=0.15), prereg_check=check)
    assert md.count("## Preregistration") == 1


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def test_cli_writes_a_plan(tmp_path, capsys):
    out = tmp_path / "plan.json"
    code = run(["alt-test-prereg", "--annotators", "expert", "--ai-column", "ai_prompt_v1",
                "--human-columns", ",".join(HUMANS), "--planned-items", "60", "--out", str(out)])
    assert code == 0
    plan = load_prereg(str(out))
    assert plan["locked"]["settings"]["epsilon"] == 0.2
    assert plan["sha256"] in capsys.readouterr().err


def test_cli_prereg_needs_an_epsilon_choice(tmp_path):
    with pytest.raises(SystemExit):
        run(["alt-test-prereg", "--out", str(tmp_path / "p.json")])


def test_cli_run_takes_everything_from_the_plan(capsys):
    code = run(["alt-test", EXAMPLE, "--prereg", EXAMPLE_PLAN])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["preregistration"]["matches"] is True
    assert [r["judge"] for r in out["ranking"]] == AIS
    assert out["results"]["ai_prompt_v1"]["epsilon"] == 0.15


def test_cli_blocks_a_run_that_departs_from_the_plan(capsys):
    code = run(["alt-test", EXAMPLE, "--prereg", EXAMPLE_PLAN, "--epsilon", "0.2"])
    assert code == 1
    err = capsys.readouterr().err
    assert "departs from the preregistered plan" in err
    assert "epsilon: preregistered 0.15, used 0.2" in err


def test_cli_allow_deviation_runs_and_records_it(capsys, tmp_path):
    report = tmp_path / "r.md"
    code = run(["alt-test", EXAMPLE, "--prereg", EXAMPLE_PLAN, "--annotators", "expert",
                "--allow-deviation", "--report", str(report)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["preregistration"]["matches"] is False
    assert "This run departs" in report.read_text(encoding="utf-8")


def test_cli_refuses_a_tampered_plan(tmp_path, capsys):
    plan = json.loads(open(EXAMPLE_PLAN, encoding="utf-8").read())
    plan["locked"]["settings"]["epsilon"] = 0.3
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(plan), encoding="utf-8")
    assert run(["alt-test", EXAMPLE, "--prereg", str(bad)]) == 1
    assert "edited after it was created" in capsys.readouterr().err


def test_cli_bootstrap_flag(capsys):
    code = run(["alt-test", EXAMPLE, "--ai-column", "ai_prompt_v1",
                "--human-columns", ",".join(HUMANS), "--annotators", "skilled",
                "--bootstrap", "20", "--seed", "1"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["robustness"]["n_resamples"] == 20
    assert out["robustness"]["seed"] == 1


def test_cli_still_needs_an_ai_column_without_a_plan():
    with pytest.raises(SystemExit):
        run(["alt-test", EXAMPLE, "--annotators", "skilled"])
