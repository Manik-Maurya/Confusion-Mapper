"""
Item bank generator.

I built this because writing 90 CFI-labelled MCQ distractors by hand for
the RCT calibration set was slow and, honestly, biased. Every hand-written
distractor pool ends up shaped by whatever wrong answers the author
personally found interesting. A generator gives me a larger, more even
calibration set to run reliability on, and every distractor comes with a
CFI label I can defend from the template that produced it.

Two backends. Pick the one that matches how much you trust the labels.

  templates
      Deterministic, seedable, offline. Every distractor is produced by a
      rule I can explain out loud, so the item traces back to the
      cognitive error type it is meant to test. This is what I use for
      the actual calibration set that reliability is computed on.

  ai
      Uses OpenAI to draft items in the same shape. Faster and it can
      cover topics the templates do not cover, but the CFI labels here
      are the model's opinion, so any use of them for real research
      should be verified by a human coder before the numbers are quoted
      anywhere.

Item schema (same shape as sample_data/example_labels.csv items, so
downstream code does not need to learn a new format):

    {
        "id":            "GEN_MATH_PERCENT_DISCOUNT_0001",
        "topic":         "percentages",
        "class_level":   8,
        "question_text": "A shirt costs Rs 800. It is on sale for 15% off. What is the sale price?",
        "correct_answer":"Rs 680",
        "distractors": [
            {"option": "Rs 120",  "error_type": "PK",  "note": "computed the 15% discount amount but forgot to subtract it"},
            {"option": "Rs 785",  "error_type": "CF",  "note": "subtracted 15 rupees instead of 15 percent"},
            {"option": "Rs 920",  "error_type": "INT", "note": "added 15% (markup) instead of subtracting it (discount)"},
        ],
    }
"""

import json
import random

from .taxonomy import ERROR_TYPES
from .ai import OPENAI_AVAILABLE, OpenAI


# -----------------------------------------------------------------------------
# Small helpers
# -----------------------------------------------------------------------------

def _rupees(n):
    """Format an integer as an Indian-rupee string. Not fancy, just what
    the RCT items look like."""
    return f"Rs {int(round(n))}"


def _sample_distractor_pool(rng, pool, correct_answer, k=1):
    """
    Pick k distinct values from `pool` that are NOT equal to
    `correct_answer`. This is the fix for the second bug I hit during
    development: the RF distractor generator used to sample from a fixed
    "plausible number" pool for each item, and on some seeds the sample
    happened to equal the correct answer. That looked exactly like a
    typo in the reference labels when reliability data came back
    weirdly high, and it took me an evening to find. Now every pool is
    filtered against the correct answer before we sample from it.
    """
    filtered = [x for x in pool if x != correct_answer]
    if len(filtered) < k:
        raise ValueError(
            "distractor pool too small after removing the correct answer: "
            f"need {k}, got {len(filtered)} from pool of {len(pool)}"
        )
    return rng.sample(filtered, k)


# -----------------------------------------------------------------------------
# Deterministic templates
# -----------------------------------------------------------------------------
#
# Every template is a function `template(rng, item_index) -> item_dict`.
# `rng` is a seeded `random.Random`, so calling the same template twice
# with the same seed gives the same item, which matters for reproducible
# benchmarks and for the tests below.
#
# The templates are deliberately in-domain for the RCT (Class 7-8 NCERT
# math and simple science), not a full PISA coverage. Adding a new
# template only means writing one more function and registering it in
# TEMPLATES below.


def _template_percent_discount(rng, item_index):
    """
    A percentage-discount word problem. This template exists because
    percent-vs-flat confusion (CF) and forgot-to-subtract (PK) are two
    of the most common real errors I see in Class 8 math tests, and I
    wanted the CFI labels here to be things a real teacher would
    recognise.
    """
    original = rng.choice([200, 400, 500, 600, 800, 1000, 1200, 1500, 2000, 2500])
    pct      = rng.choice([5, 10, 15, 20, 25, 30, 40])

    discount = original * pct // 100
    sale     = original - discount

    correct  = _rupees(sale)

    pk_note  = "computed the discount amount but forgot to subtract it"
    cf_note  = f"subtracted {pct} rupees instead of {pct} percent"
    int_note = "added the discount instead of subtracting it (treated it as markup)"

    return {
        "id":             f"GEN_MATH_PERCENT_DISCOUNT_{item_index:04d}",
        "topic":          "percentages",
        "class_level":    8,
        "question_text": (
            f"A shirt costs {_rupees(original)}. It is on sale for {pct}% off. "
            f"What is the sale price?"
        ),
        "correct_answer": correct,
        "distractors": [
            {"option": _rupees(discount),          "error_type": "PK",  "note": pk_note},
            {"option": _rupees(original - pct),    "error_type": "CF",  "note": cf_note},
            {"option": _rupees(original + discount),"error_type": "INT","note": int_note},
        ],
    }


def _template_percent_tax(rng, item_index):
    """
    Percentage-increase / tax problem. Mirror image of the discount one.

    Note the base value list deliberately does not include 100. When base
    is 100, the CF distractor `base + pct` (which encodes the
    percent-vs-flat-rupees confusion) collides with the correct answer,
    since 100 + 5% of 100 is also 105. That is the third real bug I
    caught here, and the cleanest fix was to drop the collision case.
    """
    base = rng.choice([200, 250, 400, 500, 800, 1000, 1500, 2000])
    pct  = rng.choice([5, 10, 12, 15, 18, 20])

    tax     = base * pct // 100
    total   = base + tax
    correct = _rupees(total)

    return {
        "id":             f"GEN_MATH_PERCENT_TAX_{item_index:04d}",
        "topic":          "percentages",
        "class_level":    8,
        "question_text": (
            f"A meal costs {_rupees(base)}. A service tax of {pct}% is added. "
            f"What is the total to pay?"
        ),
        "correct_answer": correct,
        "distractors": [
            {"option": _rupees(tax),          "error_type": "PK",
             "note": "computed only the tax amount, forgot to add the base"},
            {"option": _rupees(base + pct),   "error_type": "CF",
             "note": f"added {pct} rupees flat instead of {pct} percent"},
            {"option": _rupees(base - tax),   "error_type": "INT",
             "note": "subtracted the tax as if it were a discount"},
        ],
    }


def _template_unit_conversion_metric(rng, item_index):
    """
    Metric conversion (km to m, or kg to g). Simple, but I use this one
    especially to test the RF (recall failure) distractor path, because
    a student who does not remember the conversion factor tends to just
    write a superficially reasonable number.
    """
    kind = rng.choice(["km_to_m", "kg_to_g", "m_to_cm"])
    value = rng.choice([2, 3, 4, 5, 6, 7, 8, 12, 15, 25])

    if kind == "km_to_m":
        q       = f"How many metres are in {value} kilometres?"
        correct = f"{value * 1000} m"
        pk_val  = f"{value * 100} m"
        cf_val  = f"{value * 10000} m"
    elif kind == "kg_to_g":
        q       = f"How many grams are in {value} kilograms?"
        correct = f"{value * 1000} g"
        pk_val  = f"{value * 100} g"
        cf_val  = f"{value * 10000} g"
    else:  # m_to_cm
        q       = f"How many centimetres are in {value} metres?"
        correct = f"{value * 100} cm"
        pk_val  = f"{value * 10} cm"
        cf_val  = f"{value * 1000} cm"

    # RF (recall failure): a plausible-shape number that has nothing to do
    # with the conversion. Filtered against the correct answer, always.
    unit = correct.split()[-1]
    rf_pool = [f"{value * m} {unit}" for m in (2, 4, 5, 50, 250, 500)]
    rf_val  = _sample_distractor_pool(rng, rf_pool, correct, k=1)[0]

    return {
        "id":             f"GEN_MATH_UNIT_CONVERT_{item_index:04d}",
        "topic":          "unit conversion",
        "class_level":    7,
        "question_text":  q,
        "correct_answer": correct,
        "distractors": [
            {"option": rf_val, "error_type": "RF",
             "note": "picked a number of the right shape but the wrong factor"},
            {"option": pk_val, "error_type": "PK",
             "note": "used a smaller step of the metric ladder"},
            {"option": cf_val, "error_type": "CF",
             "note": "used a larger step of the metric ladder (classic hundred-vs-thousand slip)"},
        ],
    }


def _template_ratio_speed(rng, item_index):
    """
    Simple unit-rate word problem. The INT distractor here is the
    interesting one: it is the correct answer to a *different but
    related* question, which is the whole point of the INT category.
    """
    distance = rng.choice([60, 90, 120, 150, 180, 240, 300])
    hours    = rng.choice([2, 3, 4, 5, 6])
    while distance % hours != 0:
        distance = rng.choice([60, 90, 120, 150, 180, 240, 300])

    speed   = distance // hours
    correct = f"{speed} km/h"

    return {
        "id":             f"GEN_MATH_SPEED_{item_index:04d}",
        "topic":          "speed and distance",
        "class_level":    8,
        "question_text": (
            f"A car travels {distance} km in {hours} hours at a constant speed. "
            f"What is the speed of the car?"
        ),
        "correct_answer": correct,
        "distractors": [
            {"option": f"{distance + hours} km/h", "error_type": "PK",
             "note": "added distance and time instead of dividing"},
            {"option": f"{distance * hours} km/h", "error_type": "CF",
             "note": "multiplied distance by time (classic mixup of the speed formula)"},
            {"option": f"{distance} km",           "error_type": "INT",
             "note": "answered the total distance, which is the answer to a different question"},
        ],
    }


def _template_science_photosynthesis(rng, item_index):
    """
    A short science-literacy item. The distractor pool here is fixed
    rather than randomly generated, because for a conceptual science
    item there is no clean formula that produces good distractors, and
    the wrong-answer patterns are the same across students anyway.
    """
    return {
        "id":             f"GEN_SCI_PHOTOSYNTHESIS_{item_index:04d}",
        "topic":          "photosynthesis",
        "class_level":    7,
        "question_text": (
            "Which of the following do plants primarily use as a source of energy "
            "to make their own food?"
        ),
        "correct_answer": "Sunlight",
        "distractors": [
            {"option": "Soil nutrients", "error_type": "CF",
             "note": "the coherent misconception that plants get their food from soil"},
            {"option": "Water only",     "error_type": "PK",
             "note": "correct that water is needed, incomplete on the actual energy source"},
            {"option": "Chloroplast",    "error_type": "INT",
             "note": "correct answer to a different question (where does photosynthesis happen)"},
        ],
    }


TEMPLATES = {
    "math.percent_discount":   _template_percent_discount,
    "math.percent_tax":        _template_percent_tax,
    "math.unit_conversion":    _template_unit_conversion_metric,
    "math.speed":              _template_ratio_speed,
    "science.photosynthesis":  _template_science_photosynthesis,
}


# -----------------------------------------------------------------------------
# Public deterministic API
# -----------------------------------------------------------------------------

def generate_item(template_name, seed=None, item_index=1):
    """
    Generate one item from a named template.

    Args:
        template_name (str): a key from TEMPLATES.
        seed (int | None):   RNG seed, for reproducibility. Same seed +
            same template always produces the same item.
        item_index (int):    used to build the item's `id` field. Handy
            when generating a batch, otherwise leave at 1.

    Returns:
        dict: an item in the schema documented in the module docstring.

    Raises:
        ValueError: if template_name is not registered.
    """
    if template_name not in TEMPLATES:
        raise ValueError(
            f"unknown template {template_name!r}. "
            f"available: {sorted(TEMPLATES.keys())}"
        )
    rng = random.Random(seed)
    item = TEMPLATES[template_name](rng, item_index)
    _validate_item_shape(item)
    return item


def generate_bank(n, templates=None, seed=None):
    """
    Generate a full bank of `n` items, spread across the given templates.

    Args:
        n (int): total number of items to generate. Must be >= 1.
        templates (list[str] | None): which template keys to use. If None,
            uses all of TEMPLATES. Items are round-robined through the
            list, so the bank is evenly balanced across templates.
        seed (int | None): master seed. Each item gets a derived per-item
            seed so the same master seed always produces the same bank,
            without every item ending up identical to the first.

    Returns:
        list[dict]: the bank. Each item has a unique `id`.
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    template_keys = list(templates) if templates else list(TEMPLATES.keys())
    for key in template_keys:
        if key not in TEMPLATES:
            raise ValueError(
                f"unknown template {key!r}. available: {sorted(TEMPLATES.keys())}"
            )

    master = random.Random(seed)
    bank = []
    for i in range(n):
        # per-item seed derived from the master, so the whole bank is
        # deterministic under one seed but every item is genuinely
        # different.
        item_seed = master.randint(0, 2**31 - 1)
        key = template_keys[i % len(template_keys)]
        bank.append(generate_item(key, seed=item_seed, item_index=i + 1))
    return bank


def save_bank(bank, path):
    """Write a bank of items to `path` as pretty-printed JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(bank, f, indent=2, ensure_ascii=False)
    return path


def load_bank(path):
    """Load a bank of items from a JSON file. Validates each item on the way in."""
    with open(path, "r", encoding="utf-8") as f:
        bank = json.load(f)
    if not isinstance(bank, list):
        raise ValueError(f"{path}: top-level JSON must be a list of item dicts")
    for i, item in enumerate(bank):
        try:
            _validate_item_shape(item)
        except ValueError as e:
            raise ValueError(f"{path}: item {i}: {e}")
    return bank


# -----------------------------------------------------------------------------
# Validation. This is what catches the two bugs I hit while building this.
# -----------------------------------------------------------------------------

REQUIRED_ITEM_KEYS      = ("id", "topic", "class_level", "question_text",
                           "correct_answer", "distractors")
REQUIRED_DISTRACTOR_KEYS = ("option", "error_type", "note")


def _validate_item_shape(item):
    """
    Sanity-check a generated (or loaded) item.

    Catches:
      1. Missing required keys.
      2. A distractor whose `option` string is equal to `correct_answer`
         (this was a real bug, see _sample_distractor_pool). If the
         RF-distractor generator's pool happened to include the correct
         answer, we would silently produce an item where two options
         were the same, which makes the whole item unscorable.
      3. A distractor with an unknown error_type.
      4. An empty option or an empty note (would look like a template
         string-slice bug, which is exactly the first bug I hit: an
         early template took the last two digits of the correct answer
         as a distractor, which for values under 100 gave an empty
         string).
    """
    for k in REQUIRED_ITEM_KEYS:
        if k not in item:
            raise ValueError(f"item is missing required key {k!r}")
    if not isinstance(item["distractors"], list) or len(item["distractors"]) < 2:
        raise ValueError("item must have at least 2 distractors")

    seen_options = {str(item["correct_answer"]).strip()}
    for d in item["distractors"]:
        for k in REQUIRED_DISTRACTOR_KEYS:
            if k not in d:
                raise ValueError(f"distractor is missing required key {k!r}")
        opt = str(d["option"]).strip()
        if not opt:
            raise ValueError(
                "distractor option is empty. this usually means a template "
                "string-slice went out of range."
            )
        if not str(d["note"]).strip():
            raise ValueError("distractor note is empty")
        if opt in seen_options:
            raise ValueError(
                f"distractor option {opt!r} duplicates the correct answer "
                f"or another distractor. this is exactly the RF-pool bug "
                f"the filter in _sample_distractor_pool exists to prevent."
            )
        seen_options.add(opt)
        if d["error_type"] not in ERROR_TYPES:
            raise ValueError(
                f"distractor error_type {d['error_type']!r} is not one of "
                f"{ERROR_TYPES}"
            )
    return True


# -----------------------------------------------------------------------------
# AI backend
# -----------------------------------------------------------------------------

def generate_bank_with_ai(n, topic, class_level, api_key,
                          model="gpt-3.5-turbo", temperature=0.7):
    """
    Ask OpenAI to draft `n` items on `topic` for `class_level`.

    The prompt asks for the same JSON schema the deterministic templates
    produce. Every returned item is put through _validate_item_shape, so a
    malformed or duplicate-option item is rejected instead of silently
    contaminating the bank.

    Returns:
        list[dict]: items that passed validation. May be shorter than `n`
        if some were rejected.

    Raises:
        RuntimeError: if openai is not installed or api_key is missing.
    """
    if not OPENAI_AVAILABLE:
        raise RuntimeError("openai library not installed. Run: pip install openai")
    if not api_key:
        raise RuntimeError("no API key given for the AI item-bank backend")

    system_prompt = (
        "You are a cognitive scientist writing MCQ items for a Class "
        f"{class_level} learning-science study. For each item, produce a "
        "question, one correct answer, and exactly three wrong-answer "
        "distractors. Each distractor must be labelled with one of "
        "RF, PK, CF, INT and carry a one-sentence note explaining the "
        "cognitive error it represents. RF is recall failure. PK is "
        "partial knowledge. CF is a confident misconception. INT is a "
        "correct answer for a different but related topic.\n\n"
        "Respond with ONLY a valid JSON array. Do not include any "
        "surrounding prose or markdown fences."
    )
    user_prompt = (
        f"Generate {n} MCQ items on: {topic}. "
        f"Return a JSON array where every element has these keys: "
        f"id (string), topic (string), class_level (integer), "
        f"question_text (string), correct_answer (string), "
        f"distractors (array of 3 objects with option, error_type, note)."
    )

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=2000,
    )
    raw = response.choices[0].message.content.strip()

    # some models still wrap JSON in fences even after being told not to
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"AI response was not valid JSON: {e}")
    if not isinstance(items, list):
        raise RuntimeError("AI response was not a JSON array")

    valid = []
    for it in items:
        try:
            _validate_item_shape(it)
            valid.append(it)
        except ValueError:
            # skip malformed items rather than fail the whole batch
            continue
    return valid
