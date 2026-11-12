"""
Tests for the bootstrap robustness check on the alt-test.

The check reruns the whole test on resampled items, so the useful things
to pin down are: it is reproducible, it gives the obvious answer in the
obvious cases (a perfect judge always passes, a useless one never does),
its numbers stay in range, and it never mixes up a repeated item with its
copies.
"""

import os

import pytest

from confusion_mapper.alttest import (
    alt_test,
    bootstrap_alt_test,
    generate_synthetic_panel,
    load_alttest_csv,
    format_alttest_report,
    format_comparison_report,
    compare_judges,
)

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "example_alttest.csv")


def _majority(humans, items):
    out = {}
    for x in items:
        labels = [humans[c][x] for c in humans if x in humans[c]]
        out[x] = max(sorted(set(labels)), key=labels.count)
    return out


@pytest.fixture(scope="module")
def example():
    return load_alttest_csv(EXAMPLE, ["ai_prompt_v1", "ai_prompt_v2"])


def test_same_seed_same_result(example):
    humans, ais = example
    a = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=40, seed=3, epsilon=0.15)
    b = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=40, seed=3, epsilon=0.15)
    assert a == b


def test_perfect_judge_always_passes():
    p = generate_synthetic_panel(100, n_coders=5, coder_noise=0.4, seed=5)
    mv = _majority(p["humans"], p["gold"])
    r = bootstrap_alt_test(mv, p["humans"], n_resamples=30, seed=1, epsilon=0.1)
    assert r["observed_passed"] is True
    assert r["pass_rate"] == 1.0 and r["verdict_held"] == 1.0
    assert r["advantage_probability_ci"] == [1.0, 1.0]


def test_useless_judge_never_passes():
    p = generate_synthetic_panel(80, n_coders=3, coder_noise=0.2, seed=2)
    junk = {x: "NONSENSE" for x in p["gold"]}
    r = bootstrap_alt_test(junk, p["humans"], n_resamples=30, seed=1, epsilon=0.2)
    assert r["observed_passed"] is False
    assert r["pass_rate"] == 0.0 and r["verdict_held"] == 1.0


def test_numbers_stay_in_range(example):
    humans, ais = example
    r = bootstrap_alt_test(ais["ai_prompt_v2"], humans, n_resamples=60, seed=8, epsilon=0.15)
    assert 0.0 <= r["pass_rate"] <= 1.0
    assert r["verdict_held"] == pytest.approx(1.0 - r["pass_rate"])   # observed verdict is FAIL
    lo, hi = r["advantage_probability_ci"]
    assert 0.0 <= lo <= hi <= 1.0
    assert sum(r["winning_rate_distribution"].values()) == pytest.approx(1.0)
    assert set(r["per_annotator_beaten_rate"]) == {"coder_A", "coder_B", "coder_C"}
    assert all(0.0 <= v <= 1.0 for v in r["per_annotator_beaten_rate"].values())


def test_interval_brackets_the_observed_value(example):
    humans, ais = example
    r = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=300, seed=20260623, epsilon=0.15)
    lo, hi = r["advantage_probability_ci"]
    assert lo <= r["observed_advantage_probability"] <= hi


def test_coder_b_is_the_weak_link_in_the_example(example):
    """coder_B was the one coder the AI did not beat on the real data, so
    it should also be the coder the AI beats least often in resamples."""
    humans, ais = example
    r = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=300, seed=20260623, epsilon=0.15)
    rates = r["per_annotator_beaten_rate"]
    assert rates["coder_B"] < rates["coder_A"] and rates["coder_B"] < rates["coder_C"]


def test_resamples_that_cannot_be_tested_count_as_not_passing():
    """Every coder labels 30 of 40 items, so a resample often leaves a coder
    below the 30-item minimum. Those resamples must not count as passes."""
    p = generate_synthetic_panel(40, n_coders=3, coder_noise=0.1, ai_noises=(0.05,), seed=4)
    items = list(p["gold"])
    humans = {c: {x: labels[x] for x in items[k * 5:k * 5 + 30]}
              for k, (c, labels) in enumerate(p["humans"].items())}
    r = bootstrap_alt_test(p["ais"]["ai_1"], humans, n_resamples=60, seed=7, epsilon=0.2)
    assert r["untested_resamples"] > 0
    assert r["pass_rate"] * 60 <= 60 - r["untested_resamples"] + 1e-9


def test_repeated_items_are_kept_apart():
    """A resample that draws the same item twice must give it two separate
    keys, otherwise the second draw would overwrite the first and every
    resample would quietly shrink."""
    p = generate_synthetic_panel(30, n_coders=3, seed=1)
    seen_sizes = []

    def spy(llm, humans, **settings):
        seen_sizes.append(len(llm))
        return alt_test(llm, humans, **settings)

    import confusion_mapper.alttest as mod
    original = mod.alt_test
    mod.alt_test = spy
    try:
        mod.bootstrap_alt_test(p["ais"]["ai_1"], p["humans"], n_resamples=10, seed=2)
    finally:
        mod.alt_test = original
    # the first call is the observed test, the next ten are resamples
    assert seen_sizes == [30] * 11


def test_numbers_quoted_in_the_readme(example):
    """The README quotes these exact figures for the example data, with the
    CLI's default seed and 1,000 resamples. If the code ever changes them,
    the README has to change too."""
    humans, ais = example
    v1 = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=1000,
                            seed=20260623, epsilon=0.15)
    v2 = bootstrap_alt_test(ais["ai_prompt_v2"], humans, n_resamples=1000,
                            seed=20260623, epsilon=0.15)
    assert v1["verdict_held"] == 0.759
    assert v1["advantage_probability_ci"] == [0.8023, 0.9369]
    assert v1["per_annotator_beaten_rate"]["coder_B"] == 0.45
    assert v2["verdict_held"] == 0.868


@pytest.mark.parametrize("kwargs", [{"n_resamples": 5}, {"confidence": 1.0}, {"confidence": 0.0}])
def test_bad_arguments(kwargs, example):
    humans, ais = example
    with pytest.raises(ValueError):
        bootstrap_alt_test(ais["ai_prompt_v1"], humans, **kwargs)


def test_no_overlap_between_ai_and_humans():
    humans = {"a": {"1": "X", "2": "Y"}, "b": {"1": "X", "2": "Y"}}
    with pytest.raises(ValueError):
        bootstrap_alt_test({"zzz": "X"}, humans, n_resamples=10, min_instances_per_human=2)


def test_report_sections(example):
    humans, ais = example
    r = alt_test(ais["ai_prompt_v1"], humans, epsilon=0.15)
    rb = bootstrap_alt_test(ais["ai_prompt_v1"], humans, n_resamples=50, seed=1, epsilon=0.15)
    md = format_alttest_report(r, robustness=rb)
    assert "## How fragile is this verdict?" in md
    assert "not part of the authors' procedure" in md
    assert "bootstrap resamples of the items the verdict held" in md


def test_comparison_report_has_a_held_column(example):
    humans, ais = example
    c = compare_judges(ais, humans, epsilon=0.15)
    rb = {n: bootstrap_alt_test(llm, humans, n_resamples=20, seed=1, epsilon=0.15)
          for n, llm in ais.items()}
    md = format_comparison_report(c, robustness_by_judge=rb)
    assert "Verdict held (bootstrap)" in md
    assert md.count("How fragile is this verdict?") == 2
