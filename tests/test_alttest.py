"""
Tests for the alt-test module.

The statistics here decide pass or fail verdicts that people might put in
a methods section, so most of these tests check numbers against something
independent: exact closed forms, printed t-table values, hand-worked
examples, the optimal-judge theorem from the paper, and scipy whenever it
happens to be installed (it is not a dependency).
"""

import json
import math
import os
import random

import pytest

from confusion_mapper.alttest import (
    t_cdf,
    regularized_incomplete_beta,
    one_sided_t_test_less,
    benjamini_yekutieli,
    accuracy_score,
    neg_rmse_score,
    alt_test,
    compare_judges,
    human_agreement_summary,
    load_alttest_csv,
    _looks_like_ai_column,
    generate_synthetic_panel,
    simulate_alt_test_power,
    format_alttest_report,
    format_comparison_report,
    EPSILON_PRESETS,
    CITATION,
)
from confusion_mapper.cli import run

ROOT = os.path.join(os.path.dirname(__file__), "..")
EXAMPLE = os.path.join(ROOT, "sample_data", "example_alttest.csv")
HUMANS = ["coder_A", "coder_B", "coder_C"]


# -----------------------------------------------------------------------------
# Student's t distribution
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("df", [1, 2, 3, 7, 30, 200])
def test_t_cdf_is_one_half_at_zero(df):
    assert t_cdf(0.0, df) == pytest.approx(0.5, abs=1e-14)


@pytest.mark.parametrize("t", [-30.0, -3.0, -1.0, -0.2, 0.5, 1.0, 4.0, 25.0])
def test_t_cdf_with_one_df_is_the_cauchy_cdf(t):
    # exact closed form: F(t) = 1/2 + atan(t) / pi
    assert t_cdf(t, 1) == pytest.approx(0.5 + math.atan(t) / math.pi, abs=1e-12)


@pytest.mark.parametrize("t", [-10.0, -2.0, -0.7, 0.3, 1.5, 6.0])
def test_t_cdf_with_two_df_matches_closed_form(t):
    # exact closed form: F(t) = 1/2 + t / (2 sqrt(2 + t^2))
    assert t_cdf(t, 2) == pytest.approx(0.5 + t / (2 * math.sqrt(2 + t * t)), abs=1e-12)


@pytest.mark.parametrize("df, t, prob", [
    # printed t-table critical values, rounded to 3 decimals in the tables
    (5, 2.015, 0.95), (10, 1.812, 0.95), (30, 1.697, 0.95),
    (60, 1.671, 0.95), (10, 2.228, 0.975), (10, 2.764, 0.99), (1, 6.314, 0.95),
])
def test_t_cdf_matches_t_table_critical_values(df, t, prob):
    assert t_cdf(t, df) == pytest.approx(prob, abs=3e-4)


@pytest.mark.parametrize("df", [1, 4, 12, 50])
def test_t_cdf_is_symmetric(df):
    for t in (0.1, 0.9, 2.5, 7.0):
        assert t_cdf(-t, df) == pytest.approx(1 - t_cdf(t, df), abs=1e-13)


def test_t_cdf_handles_infinities_and_nan():
    assert t_cdf(float("inf"), 5) == 1.0
    assert t_cdf(float("-inf"), 5) == 0.0
    assert math.isnan(t_cdf(float("nan"), 5))


def test_t_cdf_rejects_nonpositive_df():
    with pytest.raises(ValueError):
        t_cdf(1.0, 0)


def test_incomplete_beta_edges_and_a_known_value():
    assert regularized_incomplete_beta(2, 3, 0.0) == 0.0
    assert regularized_incomplete_beta(2, 3, 1.0) == 1.0
    # I_x(1, 1) is the uniform CDF
    assert regularized_incomplete_beta(1, 1, 0.37) == pytest.approx(0.37, abs=1e-14)


def test_t_cdf_against_scipy_if_available():
    stats = pytest.importorskip("scipy.stats")
    rng = random.Random(3)
    for _ in range(500):
        df = rng.choice([1, 2, 3, 5, 9, 20, 47, 120, 400])
        t = rng.uniform(-15, 15)
        assert t_cdf(t, df) == pytest.approx(float(stats.t.cdf(t, df)), abs=1e-11)


# -----------------------------------------------------------------------------
# The one-sided t-test
# -----------------------------------------------------------------------------

def test_one_sided_t_test_hand_example():
    # mean 3, sd sqrt(2.5), t = (3 - 4) / (sqrt(2.5) / sqrt(5)) = -sqrt(2)
    r = one_sided_t_test_less([1, 2, 3, 4, 5], 4)
    assert r["mean"] == 3
    assert r["df"] == 4
    assert r["t"] == pytest.approx(-math.sqrt(2), abs=1e-12)
    # reference value from scipy.stats.ttest_1samp(..., alternative="less")
    assert r["p_value"] == pytest.approx(0.11509982054024936, abs=1e-10)


def test_one_sided_t_test_zero_variance_cases():
    below = one_sided_t_test_less([0, 0, 0], 0.2)
    assert below["p_value"] == 0.0 and below["t"] == float("-inf")
    above = one_sided_t_test_less([1, 1, 1], 0.2)
    assert above["p_value"] == 1.0 and above["t"] == float("inf")
    on = one_sided_t_test_less([0.0, 0.0], 0.0)
    assert on["p_value"] == 1.0


def test_one_sided_t_test_needs_two_values():
    with pytest.raises(ValueError):
        one_sided_t_test_less([1], 0)


# -----------------------------------------------------------------------------
# Benjamini-Yekutieli
# -----------------------------------------------------------------------------
# m = 3, q = 0.05, H_3 = 1 + 1/2 + 1/3 = 11/6
# thresholds: k=1 0.009091, k=2 0.018182, k=3 0.027273

def test_by_rejects_only_what_passes():
    assert benjamini_yekutieli([0.001, 0.02, 0.5], 0.05) == [0]


def test_by_rejects_everything_below_its_threshold():
    assert sorted(benjamini_yekutieli([0.015, 0.001, 0.02], 0.05)) == [0, 1, 2]


def test_by_is_step_up():
    # 0.012 misses the k=1 threshold but the k=3 one passes, so all three go
    assert sorted(benjamini_yekutieli([0.012, 0.012, 0.02], 0.05)) == [0, 1, 2]


def test_by_empty_and_extremes():
    assert benjamini_yekutieli([], 0.05) == []
    assert benjamini_yekutieli([0.9, 0.8], 0.05) == []
    assert sorted(benjamini_yekutieli([1e-9, 1e-8, 1e-7], 0.05)) == [0, 1, 2]


def test_by_smaller_q_never_rejects_more():
    rng = random.Random(11)
    for _ in range(300):
        p = [rng.random() ** 4 for _ in range(rng.randint(1, 8))]
        assert len(benjamini_yekutieli(p, 0.01)) <= len(benjamini_yekutieli(p, 0.05))


# -----------------------------------------------------------------------------
# Alignment scores
# -----------------------------------------------------------------------------

def test_accuracy_score():
    assert accuracy_score("CF", ["CF", "PK"]) == 0.5
    assert accuracy_score("RF", ["CF", "PK"]) == 0.0


def test_neg_rmse_score():
    # sqrt(((3-1)^2 + (3-5)^2) / 2) = 2
    assert neg_rmse_score(3, [1, 5]) == -2.0
    assert neg_rmse_score("4", ["4", "4"]) == 0.0


# -----------------------------------------------------------------------------
# The alt-test on a hand-worked example
# -----------------------------------------------------------------------------
#
#        A  B  C  AI
#   i1   X  X  X  X
#   i2   X  Y  X  X
#   i3   Y  Y  X  Y
#   i4   X  X  Y  Y
#
# Worked by hand (see comments in each test):
#   coder A: every item is a tie            rho_AI = 1, rho_A = 1
#   coder B: i2 goes to the AI, rest ties   rho_AI = 1, rho_B = 0.75
#   coder C: i3 goes to the AI, rest ties   rho_AI = 1, rho_C = 0.75

HAND_HUMANS = {
    "A": {"i1": "X", "i2": "X", "i3": "Y", "i4": "X"},
    "B": {"i1": "X", "i2": "Y", "i3": "Y", "i4": "X"},
    "C": {"i1": "X", "i2": "X", "i3": "X", "i4": "Y"},
}
HAND_AI = {"i1": "X", "i2": "X", "i3": "Y", "i4": "Y"}


def _hand():
    return alt_test(HAND_AI, HAND_HUMANS, epsilon=0.2, min_instances_per_human=2)


def test_hand_example_advantage_probabilities():
    r = {a["annotator"]: a for a in _hand()["per_annotator"]}
    assert (r["A"]["rho_llm"], r["A"]["rho_human"]) == (1.0, 1.0)
    assert (r["B"]["rho_llm"], r["B"]["rho_human"]) == (1.0, 0.75)
    assert (r["C"]["rho_llm"], r["C"]["rho_human"]) == (1.0, 0.75)
    assert _hand()["advantage_probability"] == 1.0


def test_hand_example_t_statistic_for_coder_b():
    # d = [0, -1, 0, 0], mean -0.25, sd 0.5, t = (-0.25 - 0.2) / (0.5 / 2) = -1.8
    b = next(a for a in _hand()["per_annotator"] if a["annotator"] == "B")
    assert b["mean_d"] == -0.25
    assert b["sd_d"] == pytest.approx(0.5)
    assert b["t"] == pytest.approx(-1.8)
    assert b["df"] == 3
    # reference value from scipy
    assert b["p_value"] == pytest.approx(0.08483996445062908, abs=1e-10)


def test_hand_example_coder_a_zero_variance_is_a_clean_win():
    a = next(x for x in _hand()["per_annotator"] if x["annotator"] == "A")
    assert a["p_value"] == 0.0


def test_ties_count_for_both_sides():
    # an AI identical to coder A ties with A on every item
    r = alt_test(dict(HAND_HUMANS["A"]), HAND_HUMANS, min_instances_per_human=2)
    a = next(x for x in r["per_annotator"] if x["annotator"] == "A")
    assert a["rho_llm"] == 1.0 and a["rho_human"] == 1.0 and a["mean_d"] == 0.0


# -----------------------------------------------------------------------------
# Behaviour on synthetic panels
# -----------------------------------------------------------------------------

def _majority_vote(humans, items):
    out = {}
    for x in items:
        labels = [humans[c][x] for c in humans if x in humans[c]]
        out[x] = max(sorted(set(labels)), key=labels.count)
    return out


def test_majority_vote_judge_has_advantage_probability_one():
    """Theorem 1 in the paper: under accuracy, the majority vote is the
    optimal judge and its advantage probability is exactly 1."""
    p = generate_synthetic_panel(120, n_coders=5, coder_noise=0.4, seed=5)
    ai = _majority_vote(p["humans"], p["gold"])
    r = alt_test(ai, p["humans"], epsilon=0.1)
    assert all(a["rho_llm"] == 1.0 for a in r["per_annotator"])
    assert r["advantage_probability"] == 1.0
    assert r["passed"]


def test_mean_judge_is_optimal_under_neg_rmse():
    """Theorem 1, the -RMSE half: the mean rating beats every coder."""
    rng = random.Random(9)
    humans = {c: {} for c in ("r1", "r2", "r3")}
    for i in range(60):
        base = rng.randint(1, 5)
        for c in humans:
            humans[c][f"x{i}"] = max(1, min(5, base + rng.choice([-1, 0, 0, 1])))
    ai = {x: sum(humans[c][x] for c in humans) / 3 for x in humans["r1"]}
    r = alt_test(ai, humans, scoring="neg_rmse", epsilon=0.1)
    assert r["advantage_probability"] == 1.0


def test_an_ai_nobody_agrees_with_fails():
    p = generate_synthetic_panel(80, n_coders=3, coder_noise=0.2, seed=2)
    ai = {x: "NONSENSE" for x in p["gold"]}
    r = alt_test(ai, p["humans"], epsilon=0.2)
    assert r["passed"] is False
    assert r["winning_rate"] == 0.0
    assert "FAILED" in r["verdict"]


def test_bigger_epsilon_never_lowers_the_winning_rate():
    p = generate_synthetic_panel(100, n_coders=4, coder_noise=0.3, ai_noises=(0.35,), seed=8)
    rates = [alt_test(p["ais"]["ai_1"], p["humans"], epsilon=e)["winning_rate"]
             for e in (0.0, 0.05, 0.1, 0.15, 0.2, 0.3)]
    assert rates == sorted(rates)


def test_custom_scoring_function():
    def lenient(pred, others):
        return 1.0 if pred in others else 0.0
    r = alt_test(HAND_AI, HAND_HUMANS, scoring=lenient, min_instances_per_human=2)
    assert r["scoring"] == "lenient"


# -----------------------------------------------------------------------------
# Missing data, skipping and warnings
# -----------------------------------------------------------------------------

def test_items_with_one_coder_or_no_ai_label_are_dropped():
    p = generate_synthetic_panel(40, n_coders=3, seed=4)
    humans, ai = p["humans"], dict(p["ais"]["ai_1"])
    humans["coder_1"]["solo"] = "RF"     # only one coder labelled this
    del ai["item_0001"]                  # the AI skipped this one
    r = alt_test(ai, humans)
    assert "solo" in r["dropped_instances"]
    assert "item_0001" in r["dropped_instances"]
    assert r["n_instances_used"] == 39


def test_coder_with_too_few_items_is_skipped_and_reported():
    p = generate_synthetic_panel(40, n_coders=3, seed=6)
    humans = p["humans"]
    humans["late_joiner"] = {x: "PK" for x in list(p["gold"])[:10]}
    r = alt_test(p["ais"]["ai_1"], humans)
    assert {"annotator": "late_joiner", "n_instances": 10} in r["skipped_annotators"]
    assert r["n_humans_tested"] == 3
    assert any("skipped" in w for w in r["warnings"])


def test_two_coders_triggers_the_authors_warning():
    p = generate_synthetic_panel(60, n_coders=2, seed=1)
    r = alt_test(p["ais"]["ai_1"], p["humans"])
    assert any("at least 3" in w for w in r["warnings"])


def test_nothing_testable_gives_a_clear_result():
    p = generate_synthetic_panel(10, n_coders=3, seed=1)
    r = alt_test(p["ais"]["ai_1"], p["humans"])
    assert r["winning_rate"] is None and r["passed"] is False
    assert r["verdict"].startswith("Not tested")


@pytest.mark.parametrize("kwargs", [
    {"scoring": "f1"}, {"epsilon": -0.1}, {"epsilon": 1.0}, {"q_fdr": 0.0},
    {"min_humans_per_instance": 1}, {"min_instances_per_human": 1},
])
def test_bad_settings_are_rejected(kwargs):
    with pytest.raises(ValueError):
        alt_test(HAND_AI, HAND_HUMANS, **kwargs)


def test_one_coder_is_not_enough():
    with pytest.raises(ValueError):
        alt_test(HAND_AI, {"A": HAND_HUMANS["A"]})


def test_epsilon_presets_match_the_authors_rule_of_thumb():
    assert EPSILON_PRESETS == {"expert": 0.2, "skilled": 0.15, "crowd": 0.1}


# -----------------------------------------------------------------------------
# Comparing judges, human agreement
# -----------------------------------------------------------------------------

def test_compare_judges_ranks_by_advantage_probability():
    p = generate_synthetic_panel(100, n_coders=3, coder_noise=0.3,
                                 ai_noises=(0.7, 0.05), seed=12)
    c = compare_judges({"sloppy": p["ais"]["ai_1"], "careful": p["ais"]["ai_2"]},
                       p["humans"], epsilon=0.15)
    assert [r["judge"] for r in c["ranking"]] == ["careful", "sloppy"]
    assert set(c["results"]) == {"sloppy", "careful"}


def test_compare_judges_needs_a_judge():
    with pytest.raises(ValueError):
        compare_judges({}, HAND_HUMANS)


def test_human_agreement_summary():
    same = {"a": {"1": "X", "2": "Y", "3": "X"}, "b": {"1": "X", "2": "Y", "3": "X"},
            "c": {"1": "X", "2": "Y", "3": "X"}}
    s = human_agreement_summary(same)
    assert s["mean_pairwise_kappa"] == 1.0
    assert len(s["pairs"]) == 3


# -----------------------------------------------------------------------------
# Loading CSVs, including the bug I hit on my own example file
# -----------------------------------------------------------------------------

def test_load_example_csv_with_explicit_humans():
    humans, llms = load_alttest_csv(EXAMPLE, ["ai_prompt_v1", "ai_prompt_v2"])
    assert list(humans) == HUMANS
    assert len(humans["coder_A"]) == 81
    assert len(humans["coder_C"]) == 75          # six blank cells
    assert set(llms) == {"ai_prompt_v1", "ai_prompt_v2"}


def test_regression_other_ai_column_is_not_silently_a_human():
    """
    Bug: asking for one AI column made every other column a human coder,
    including the second AI column. No crash, just a wrong panel of four
    "humans". The loader now refuses and asks which columns are human.
    """
    with pytest.raises(ValueError, match="look like AI output"):
        load_alttest_csv(EXAMPLE, "ai_prompt_v1")
    humans, _ = load_alttest_csv(EXAMPLE, "ai_prompt_v1", human_columns=HUMANS)
    assert list(humans) == HUMANS


@pytest.mark.parametrize("name, expected", [
    ("ai_label", True), ("AI", True), ("ai-v2", True), ("llm_out", True),
    ("gpt4o", True), ("model_b", True), ("judge_1", True), ("Gemini_pro", True),
    ("coder_A", False), ("Aisha", False), ("Modesto", False), ("maid", False),
])
def test_ai_column_name_detection(name, expected):
    assert _looks_like_ai_column(name) is expected


def _write(tmp_path, text):
    path = tmp_path / "panel.csv"
    path.write_text(text, encoding="utf-8")
    return str(path)


def test_loader_errors(tmp_path):
    with pytest.raises(ValueError, match="item_id"):
        load_alttest_csv(_write(tmp_path, "id,a,b,ai\n1,X,X,X\n"), "ai")
    with pytest.raises(ValueError, match="not found"):
        load_alttest_csv(_write(tmp_path, "item_id,a,b\n1,X,X\n"), "ai")
    with pytest.raises(ValueError, match="duplicate"):
        load_alttest_csv(_write(tmp_path, "item_id,a,b,ai\n1,X,X,X\n1,Y,Y,Y\n"), "ai")
    with pytest.raises(ValueError, match="at least 2"):
        load_alttest_csv(_write(tmp_path, "item_id,a,ai\n1,X,X\n"), "ai")


# -----------------------------------------------------------------------------
# Synthetic panels and the power simulator
# -----------------------------------------------------------------------------

def test_synthetic_panel_is_deterministic_and_shaped_right():
    a = generate_synthetic_panel(50, n_coders=4, ai_noises=(0.1, 0.5), seed=3)
    b = generate_synthetic_panel(50, n_coders=4, ai_noises=(0.1, 0.5), seed=3)
    assert a == b
    assert len(a["humans"]) == 4 and len(a["ais"]) == 2
    assert all(len(v) == 50 for v in a["humans"].values())
    assert sum(a["prior"].values()) == pytest.approx(1.0)


def test_zero_noise_coders_report_the_truth():
    p = generate_synthetic_panel(60, n_coders=3, coder_noise=0.0, seed=7)
    for labels in p["humans"].values():
        assert labels == p["gold"]


def test_synthetic_panel_rejects_bad_noise():
    with pytest.raises(ValueError):
        generate_synthetic_panel(10, coder_noise=1.5)


def test_power_simulation_is_reproducible():
    kw = dict(n_items_grid=(30, 60), n_simulations=10, epsilon=0.15, seed=99)
    assert simulate_alt_test_power(**kw) == simulate_alt_test_power(**kw)


def test_power_grows_with_items_for_a_good_ai():
    r = simulate_alt_test_power(n_items_grid=(30, 200), coder_noise=0.3, ai_noise=0.1,
                                epsilon=0.15, n_simulations=40, seed=21)
    small, large = r["rows"]
    assert large["pass_rate"] >= small["pass_rate"]
    assert r["recommended_n"] in (30, 200, None)


def test_noise_free_coders_imply_kappa_one():
    r = simulate_alt_test_power(n_items_grid=(30,), coder_noise=0.0, n_simulations=5, seed=1)
    assert r["implied_human_kappa"] == 1.0


def test_power_grid_below_30_is_refused():
    with pytest.raises(ValueError):
        simulate_alt_test_power(n_items_grid=(20, 50), n_simulations=2)


# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------

def _no_ai_tells(text):
    dashes = (chr(0x2014), chr(0x2013), " -" + "- ")
    return not any(d in text for d in dashes)


def test_single_report_has_verdict_checklist_and_citation():
    humans, llms = load_alttest_csv(EXAMPLE, "ai_prompt_v1", human_columns=HUMANS)
    r = alt_test(llms["ai_prompt_v1"], humans, epsilon=0.15)
    md = format_alttest_report(r, human_agreement_summary(humans),
                               judge_name="ai_prompt_v1", annotator_profile="skilled")
    assert "PASSED" in md
    assert "Reporting checklist" in md
    assert "skilled coders preset" in md
    assert "Mean pairwise Cohen's kappa" in md
    assert CITATION in md
    assert _no_ai_tells(md)


def test_comparison_report_ranks_and_includes_each_judge():
    humans, llms = load_alttest_csv(EXAMPLE, ["ai_prompt_v1", "ai_prompt_v2"])
    md = format_comparison_report(compare_judges(llms, humans, epsilon=0.15))
    assert md.index("| 1 | ai_prompt_v1") < md.index("| 2 | ai_prompt_v2")
    assert "Judge: ai_prompt_v1" in md and "Judge: ai_prompt_v2" in md
    assert md.count("DRAFT") == 1
    assert _no_ai_tells(md)


# -----------------------------------------------------------------------------
# The example file says what the README says it says
# -----------------------------------------------------------------------------

def test_example_file_outcome_matches_the_readme():
    humans, llms = load_alttest_csv(EXAMPLE, ["ai_prompt_v1", "ai_prompt_v2"])
    c = compare_judges(llms, humans, epsilon=EPSILON_PRESETS["skilled"])
    v1, v2 = c["results"]["ai_prompt_v1"], c["results"]["ai_prompt_v2"]
    assert v1["passed"] and v1["winning_rate"] == pytest.approx(2 / 3)
    assert not v2["passed"] and v2["winning_rate"] == 0.0
    # coder_B: p < 0.05 on its own, but not after the FDR correction
    b = next(a for a in v1["per_annotator"] if a["annotator"] == "coder_B")
    assert b["p_value"] < 0.05 and not b["rejected"]


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------

def test_cli_single_judge(capsys, tmp_path):
    report = tmp_path / "alt.md"
    code = run(["alt-test", EXAMPLE, "--ai-column", "ai_prompt_v1",
                "--human-columns", ",".join(HUMANS), "--annotators", "skilled",
                "--report", str(report)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["passed"] is True and out["epsilon"] == 0.15
    assert out["judge"] == "ai_prompt_v1"
    assert out["human_agreement"]["mean_pairwise_kappa"] is not None
    assert report.read_text(encoding="utf-8").startswith("# Can the AI replace")


def test_cli_compare(capsys):
    code = run(["alt-test", EXAMPLE, "--ai-column", "ai_prompt_v1",
                "--ai-column", "ai_prompt_v2", "--epsilon", "0.15"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ranking"][0]["judge"] == "ai_prompt_v1"


def test_cli_refuses_ambiguous_columns(capsys):
    code = run(["alt-test", EXAMPLE, "--ai-column", "ai_prompt_v1", "--annotators", "expert"])
    assert code == 1
    assert "look like AI output" in capsys.readouterr().err


def test_cli_requires_an_epsilon_choice():
    with pytest.raises(SystemExit):
        run(["alt-test", EXAMPLE, "--ai-column", "ai_prompt_v1"])


def test_cli_plan(capsys):
    code = run(["alt-test-plan", "--annotators", "crowd", "--sizes", "30,60",
                "--simulations", "5"])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert [row["n_items"] for row in out["rows"]] == [30, 60]
    assert out["settings"]["epsilon"] == 0.1


def test_cli_plan_rejects_tiny_sizes(capsys):
    assert run(["alt-test-plan", "--epsilon", "0.1", "--sizes", "10"]) == 1
