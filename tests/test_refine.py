"""
Tests for the prompt-refinement engine and the `refine` subcommand.

These did not exist before 2.10.0, even though the README said they did.
While linting the package I found that suggest_prompt_refinements() had
been crashing with a NameError since the 2.6.0 package split: it fell back
to TAXONOMY, which no longer lived in the same file and was never imported
into stats.py. Every call without an explicit taxonomy, including the
whole `confusion-mapper refine` command, failed. The first test below is
the regression test for that.
"""

import os

import pytest

from confusion_mapper.stats import suggest_prompt_refinements
from confusion_mapper.taxonomy import TAXONOMY
from confusion_mapper.cli import run

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "sample_data", "example_labels.csv")

HUMAN = ["CF", "CF", "CF", "CF", "RF", "RF", "PK", "PK", "INT", "INT", "CF", "PK"]
AI    = ["CF", "INT", "INT", "INT", "RF", "PK", "PK", "CF", "INT", "INT", "INT", "CF"]
# off-diagonal cells: CF->INT 4, PK->CF 2, RF->PK 1


def test_regression_works_without_an_explicit_taxonomy():
    r = suggest_prompt_refinements(HUMAN, AI)          # used to raise NameError
    assert r["suggestions"]


def test_biggest_confusions_come_first():
    r = suggest_prompt_refinements(HUMAN, AI, top_k=3)
    assert r["top_confusions"] == [("CF", "INT", 4), ("PK", "CF", 2), ("RF", "PK", 1)]


def test_top_k_limits_the_list():
    r = suggest_prompt_refinements(HUMAN, AI, top_k=1)
    assert r["top_confusions"] == [("CF", "INT", 4)]
    assert len(r["suggestions"]) == 1


def test_suggestions_quote_the_real_definitions():
    r = suggest_prompt_refinements(HUMAN, AI, top_k=1)
    text = r["suggestions"][0]
    assert TAXONOMY["CF"]["definition"] in text
    assert TAXONOMY["INT"]["definition"] in text
    assert "4 item(s)" in text


def test_perfect_agreement_has_nothing_to_suggest():
    r = suggest_prompt_refinements(HUMAN, HUMAN)
    assert r["top_confusions"] == [] and r["suggestions"] == []
    assert "No off-diagonal disagreements" in r["report_markdown"]


def test_custom_taxonomy_is_used_when_given():
    tax = {"A": {"name": "Alpha", "definition": "the A rule"},
           "B": {"name": "Beta", "definition": "the B rule"}}
    r = suggest_prompt_refinements(["A", "A", "B"], ["B", "A", "B"],
                                   taxonomy=tax, categories=["A", "B"])
    assert "the A rule" in r["suggestions"][0] and "Alpha" in r["suggestions"][0]


def test_same_input_same_report():
    a = suggest_prompt_refinements(HUMAN, AI)["report_markdown"]
    b = suggest_prompt_refinements(HUMAN, AI)["report_markdown"]
    assert a == b


def test_cli_refine_runs(capsys):
    """The whole subcommand was broken by the NameError, so test it end to end."""
    assert run(["refine", EXAMPLE, "--top", "2"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("# Prompt refinement suggestions")


@pytest.mark.parametrize("top", ["1", "5"])
def test_cli_refine_respects_top(capsys, top):
    assert run(["refine", EXAMPLE, "--top", top]) == 0
    out = capsys.readouterr().out
    assert out.count("\n## ") <= int(top)
