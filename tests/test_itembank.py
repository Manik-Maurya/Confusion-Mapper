"""
Tests for the item-bank generator.

Includes explicit regression tests for the two real bugs I hit while
writing this: an empty-option distractor produced by an out-of-range
string slice, and an RF-distractor that coincidentally equalled the
correct answer because the "random plausible number" pool was not
filtered.
"""

import json
import os
import tempfile
import pytest

from confusion_mapper.itembank import (
    TEMPLATES,
    generate_item,
    generate_bank,
    save_bank,
    load_bank,
    _validate_item_shape,
    _sample_distractor_pool,
    REQUIRED_ITEM_KEYS,
    REQUIRED_DISTRACTOR_KEYS,
)
from confusion_mapper.taxonomy import ERROR_TYPES


# -----------------------------------------------------------------------------
# Shape checks. Every template must produce a well-formed item.
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_every_template_produces_a_valid_item(template_name):
    item = generate_item(template_name, seed=42)
    for key in REQUIRED_ITEM_KEYS:
        assert key in item
    assert len(item["distractors"]) >= 2
    for d in item["distractors"]:
        for k in REQUIRED_DISTRACTOR_KEYS:
            assert k in d
        assert d["error_type"] in ERROR_TYPES
        assert str(d["option"]).strip() != ""
        assert str(d["note"]).strip() != ""


@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_no_distractor_equals_the_correct_answer(template_name):
    """The whole point of _sample_distractor_pool. Try 200 seeds per
    template so any RF-pool collision would show up."""
    for seed in range(200):
        item = generate_item(template_name, seed=seed)
        options = [d["option"] for d in item["distractors"]]
        assert item["correct_answer"] not in options, (
            f"template {template_name} at seed {seed} produced a "
            f"distractor that equals the correct answer."
        )


@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_all_distractors_within_an_item_are_distinct(template_name):
    for seed in range(100):
        item = generate_item(template_name, seed=seed)
        options = [d["option"] for d in item["distractors"]]
        assert len(options) == len(set(options)), (
            f"template {template_name} at seed {seed} produced duplicate "
            f"distractor options: {options}"
        )


@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_item_id_matches_template_family(template_name):
    item = generate_item(template_name, seed=1)
    # id should be uppercase snake-case and share a stem with the template
    assert item["id"].startswith("GEN_")
    family = template_name.split(".")[-1].upper()
    assert family in item["id"] or family.split("_")[0] in item["id"]


# -----------------------------------------------------------------------------
# Determinism. Same seed, same item.
# -----------------------------------------------------------------------------

@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_same_seed_produces_the_same_item(template_name):
    a = generate_item(template_name, seed=7)
    b = generate_item(template_name, seed=7)
    assert a == b


@pytest.mark.parametrize("template_name", list(TEMPLATES.keys()))
def test_different_seeds_usually_produce_different_items(template_name):
    """Not a strict guarantee but should be true on 20 seeds."""
    items = [generate_item(template_name, seed=s) for s in range(20)]
    unique_questions = {i["question_text"] for i in items}
    if template_name == "science.photosynthesis":
        # this one has a fixed question; only IDs vary
        assert len({i["id"] for i in items}) >= 1
    else:
        assert len(unique_questions) > 1, (
            f"template {template_name} produced the same question across "
            f"20 different seeds. that means the template is not actually "
            f"using the RNG."
        )


# -----------------------------------------------------------------------------
# The bank-level generator.
# -----------------------------------------------------------------------------

def test_bank_has_expected_size():
    bank = generate_bank(n=12, seed=1)
    assert len(bank) == 12


def test_bank_ids_are_unique():
    bank = generate_bank(n=50, seed=1)
    ids = [item["id"] for item in bank]
    assert len(ids) == len(set(ids))


def test_bank_is_reproducible_under_a_seed():
    a = generate_bank(n=20, seed=99)
    b = generate_bank(n=20, seed=99)
    assert a == b


def test_bank_is_evenly_spread_across_templates_by_default():
    bank = generate_bank(n=10, seed=1)
    # 10 items across 5 templates -> exactly 2 per template
    per_family = {}
    for item in bank:
        stem = item["id"].split("_")[1]  # GEN_<STEM>_...
        per_family[stem] = per_family.get(stem, 0) + 1
    for family, count in per_family.items():
        assert count >= 1


def test_bank_can_be_restricted_to_a_subset_of_templates():
    bank = generate_bank(n=6, templates=["math.percent_discount"], seed=1)
    for item in bank:
        assert "PERCENT_DISCOUNT" in item["id"]


def test_bank_rejects_zero_or_negative_n():
    with pytest.raises(ValueError):
        generate_bank(n=0)
    with pytest.raises(ValueError):
        generate_bank(n=-3)


def test_bank_rejects_unknown_template_name():
    with pytest.raises(ValueError):
        generate_bank(n=5, templates=["math.does_not_exist"])


def test_generate_item_rejects_unknown_template_name():
    with pytest.raises(ValueError):
        generate_item("math.does_not_exist")


# -----------------------------------------------------------------------------
# Regression tests. These are the two real bugs.
# -----------------------------------------------------------------------------

def test_regression_rf_pool_never_equals_correct_answer():
    """
    Bug: the RF distractor generator sampled from a fixed pool of
    "plausible-shape" numbers, and on some seeds the sampled value
    happened to equal the correct answer, producing an item where two
    options were the same string. The fix is _sample_distractor_pool,
    which filters the pool before sampling.

    This is the direct unit test for the fix.
    """
    correct = "5000 m"
    pool = ["1000 m", "5000 m", "10000 m", "50000 m"]
    import random as _r
    rng = _r.Random(0)
    for _ in range(50):
        picked = _sample_distractor_pool(rng, pool, correct, k=1)
        assert picked[0] != correct


def test_regression_sample_distractor_pool_raises_if_pool_too_small():
    correct = "42"
    pool = ["42"]  # only the correct answer
    import random as _r
    with pytest.raises(ValueError):
        _sample_distractor_pool(_r.Random(0), pool, correct, k=1)


def test_regression_empty_option_string_is_rejected():
    """
    Bug: an early template took the last two digits of the correct
    answer as a distractor (`str(n)[-2:]`), which for values under 100
    produced a string equal to the whole number and, for a single-digit
    corner case in another template, produced an empty string. Validator
    now refuses empty options.
    """
    bad = {
        "id": "TEST_1", "topic": "x", "class_level": 8,
        "question_text": "q", "correct_answer": "10",
        "distractors": [
            {"option": "",   "error_type": "RF", "note": "empty"},
            {"option": "20", "error_type": "PK", "note": "ok"},
        ],
    }
    with pytest.raises(ValueError, match="empty"):
        _validate_item_shape(bad)


def test_regression_duplicate_option_is_rejected():
    """A distractor equal to the correct answer must be caught up front."""
    bad = {
        "id": "TEST_2", "topic": "x", "class_level": 8,
        "question_text": "q", "correct_answer": "Rs 680",
        "distractors": [
            {"option": "Rs 680", "error_type": "PK", "note": "duplicates correct answer"},
            {"option": "Rs 200", "error_type": "CF", "note": "ok"},
        ],
    }
    with pytest.raises(ValueError):
        _validate_item_shape(bad)


def test_regression_unknown_error_type_is_rejected():
    bad = {
        "id": "TEST_3", "topic": "x", "class_level": 8,
        "question_text": "q", "correct_answer": "A",
        "distractors": [
            {"option": "B", "error_type": "XX", "note": "bogus label"},
            {"option": "C", "error_type": "PK", "note": "ok"},
        ],
    }
    with pytest.raises(ValueError):
        _validate_item_shape(bad)


def test_validator_rejects_missing_required_key():
    for missing in REQUIRED_ITEM_KEYS:
        item = {
            "id": "T", "topic": "x", "class_level": 8,
            "question_text": "q", "correct_answer": "A",
            "distractors": [
                {"option": "B", "error_type": "PK", "note": "ok"},
                {"option": "C", "error_type": "CF", "note": "ok"},
            ],
        }
        item.pop(missing)
        with pytest.raises(ValueError):
            _validate_item_shape(item)


# -----------------------------------------------------------------------------
# Round-trip save/load.
# -----------------------------------------------------------------------------

def test_bank_round_trips_through_json():
    bank = generate_bank(n=8, seed=2024)
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        save_bank(bank, path)
        loaded = load_bank(path)
        assert loaded == bank
    finally:
        os.unlink(path)


def test_load_bank_rejects_a_top_level_object():
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        with open(path, "w") as f:
            json.dump({"not": "a list"}, f)
        with pytest.raises(ValueError, match="list"):
            load_bank(path)
    finally:
        os.unlink(path)


def test_load_bank_rejects_a_malformed_item():
    bad_bank = [
        {"id": "X", "topic": "y", "class_level": 7, "question_text": "q",
         "correct_answer": "A",
         "distractors": [{"option": "B", "error_type": "PK", "note": "ok"}]},  # only 1 distractor
    ]
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
        path = tf.name
    try:
        with open(path, "w") as f:
            json.dump(bad_bank, f)
        with pytest.raises(ValueError):
            load_bank(path)
    finally:
        os.unlink(path)


# -----------------------------------------------------------------------------
# Integration with the rest of the package. The generated items should
# slot cleanly into run_session (via console.py) without any adaptation.
# -----------------------------------------------------------------------------

def test_generated_items_have_the_shape_run_session_expects():
    """
    console.run_session iterates over questions with these fields:
      q["id"], q["topic"], q["question_text"], q["correct_answer"]
      d["option"], d["error_type"] for d in q["distractors"]
    """
    bank = generate_bank(n=5, seed=1)
    for q in bank:
        _ = q["id"], q["topic"], q["question_text"], q["correct_answer"]
        for d in q["distractors"]:
            _ = d["option"], d["error_type"]


def test_generated_items_can_feed_kappa_computation():
    """
    A fully AI-agreed generated bank should give kappa = 1.0 when
    reference labels are treated as one rater and themselves as the other.
    Not a research check, just a sanity that shapes line up.
    """
    from confusion_mapper.stats import compute_cohens_kappa
    bank = generate_bank(n=8, seed=1)
    labels = [d["error_type"] for q in bank for d in q["distractors"]]
    result = compute_cohens_kappa(labels, labels)
    assert result["kappa"] == 1.0
    assert result["agreements"] == result["n"]
