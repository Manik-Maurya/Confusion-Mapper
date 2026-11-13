"""
Tests for the Hindi version of the PISA-style units.

The promise is simple: a Hindi unit and an English unit from the same seed
are the same unit. Same numbers, same option order, same answer letters,
same true/false answers, same CFI labels. Only the words change. If that
ever breaks, a bilingual class sharing one answer sheet would be marked
wrong, so these tests check it on every template across many seeds.

They also pin English down. Adding Hindi meant rewriting every template,
and the fingerprint below was taken from the English output before that
rewrite. It must never change by accident.
"""

import hashlib
import json
import os
import re

import pytest

from confusion_mapper import pisa
from confusion_mapper.cli import run

ROOT = os.path.join(os.path.dirname(__file__), "..")
DEVANAGARI = re.compile(r"[\u0900-\u097F]")

# sha256 of the English units of every template, seeds 0 to 59, taken from
# version 2.12.0 before the templates were made bilingual.
ENGLISH_FINGERPRINT = "8873a8b77792128394c6a947b6b235e640931a82c1436565774d27a1cc4b4097"

# Latin words allowed inside Hindi text: units, labels and names that stay
# in English on purpose.
ALLOWED_LATIN = {"GB", "PISA", "CFI", "ID", "RF", "PK", "CF", "INT", "Confusion",
                 "Fingerprint", "Index", "x"}


def _numbers(text):
    return sorted(n.rstrip(",.") for n in re.findall(r"\d[\d,.]*", str(text)))


CODE_FIELDS = {"data", "unit_id", "template", "content", "context", "lang", "qid",
               "process", "format", "error_type", "letter", "key"}


def _texts(obj):
    """Every piece of text a child or teacher reads, skipping codes and ids."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in CODE_FIELDS:
                yield from _texts(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _texts(v)
    elif isinstance(obj, str):
        yield obj


def _pairs(en, hi, path=""):
    """Yield (path, english, hindi) for every string in two parallel units."""
    if isinstance(en, dict):
        assert set(en) | {"lang"} == set(hi) | {"lang"}, path
        for k in en:
            yield from _pairs(en[k], hi[k], f"{path}.{k}")
    elif isinstance(en, list):
        assert isinstance(hi, list) and len(en) == len(hi), path
        for i, (a, b) in enumerate(zip(en, hi)):
            yield from _pairs(a, b, f"{path}[{i}]")
    else:
        yield path, en, hi


def test_english_output_is_exactly_what_it_was_before_hindi():
    h = hashlib.sha256()
    for t in sorted(pisa.TEMPLATES):
        for s in range(60):
            unit = pisa.generate_unit(t, seed=s)
            h.update(json.dumps(unit, sort_keys=True, ensure_ascii=False).encode("utf-8"))
    assert h.hexdigest() == ENGLISH_FINGERPRINT


def test_english_units_have_no_language_tag():
    assert "lang" not in pisa.generate_unit("growth", seed=1)
    assert pisa.generate_unit("growth", seed=1, lang="hi")["lang"] == "hi"


@pytest.mark.parametrize("template", list(pisa.TEMPLATES))
def test_hindi_is_the_same_unit_in_other_words(template):
    for seed in range(40):
        en = pisa.generate_unit(template, seed=seed)
        hi = pisa.generate_unit(template, seed=seed, lang="hi")
        assert en["data"] == hi["data"]
        for qe, qh in zip(en["questions"], hi["questions"]):
            assert (qe["qid"], qe["process"], qe["format"]) == \
                   (qh["qid"], qh["process"], qh["format"])
            if qe["format"] == "multiple_choice":
                assert qe["key"] == qh["key"]
                assert [d["error_type"] for d in qe["distractors"]] == \
                       [d["error_type"] for d in qh["distractors"]]
            elif qe["format"] == "complex_multiple_choice":
                assert [s["answer"] for s in qe["statements"]] == \
                       [s["answer"] for s in qh["statements"]]
            else:
                assert len(qe["scoring"]["accepted_answers"]) == \
                       len(qh["scoring"]["accepted_answers"])
                assert bool(qe["scoring"]["partial_credit"]) == \
                       bool(qh["scoring"]["partial_credit"])
        for path, a, b in _pairs(en, hi):
            if isinstance(a, str) and a != b:
                assert _numbers(a) == _numbers(b), f"{template} seed {seed} {path}: {a!r} / {b!r}"
            elif not isinstance(a, str):
                assert a == b, f"{template} seed {seed} {path}"


@pytest.mark.parametrize("template", list(pisa.TEMPLATES))
def test_hindi_text_is_hindi(template):
    for seed in range(20):
        unit = pisa.generate_unit(template, seed=seed, lang="hi")
        pisa.validate_unit(unit)
        for field in (unit["title"], unit["stimulus"]):
            assert DEVANAGARI.search(field)
        for q in unit["questions"]:
            assert DEVANAGARI.search(q["prompt"]), q["qid"]
            notes = ([d["note"] for d in q.get("distractors", [])] +
                     [s["if_wrong"]["note"] for s in q.get("statements", [])] +
                     [w["note"] for w in q.get("common_wrong_answers", [])])
            assert all(DEVANAGARI.search(n) for n in notes), q["qid"]
        text = " ".join(_texts(unit))
        stray = set(re.findall(r"[A-Za-z]{2,}", text)) - ALLOWED_LATIN
        assert not stray, f"{template} seed {seed}: English left in the Hindi: {stray}"


def test_hindi_money_and_time_are_written_the_hindi_way():
    dal = pisa.generate_unit("dal_price", seed=3, lang="hi")
    assert "₹" in dal["stimulus"] and "Rs" not in json.dumps(dal, ensure_ascii=False)
    bus = pisa.generate_unit("bus_journey", seed=3, lang="hi")
    assert re.search(r"(सुबह|दोपहर|शाम|रात) \d{1,2}:\d{2} बजे", bus["stimulus"])
    assert "am" not in bus["stimulus"] and "pm" not in bus["stimulus"]


def test_hindi_clock_names_the_part_of_the_day():
    assert pisa._clock_hi(7 * 60 + 5) == "सुबह 7:05 बजे"
    assert pisa._clock_hi(12 * 60) == "दोपहर 12:00 बजे"
    assert pisa._clock_hi(16 * 60 + 30) == "शाम 4:30 बजे"
    assert pisa._clock_hi(20 * 60) == "रात 8:00 बजे"


def test_unknown_language_is_refused():
    with pytest.raises(ValueError, match="unknown language"):
        pisa.generate_unit("growth", seed=1, lang="fr")
    with pytest.raises(ValueError, match="unknown language"):
        pisa.generate_units(2, seed=1, lang="ta")
    unit = pisa.generate_unit("growth", seed=1)
    unit["lang"] = "fr"
    with pytest.raises(ValueError, match="unknown language"):
        pisa.validate_unit(unit)


def test_a_hindi_set_matches_the_english_set_from_the_same_seed():
    en = pisa.generate_units(8, seed=99)
    hi = pisa.generate_units(8, seed=99, lang="hi")
    assert [u["unit_id"] for u in en] == [u["unit_id"] for u in hi]
    assert pisa.coverage(en) == pisa.coverage(hi)
    assert pisa.question_labels(en)[5][0] == pisa.question_labels(hi)[5][0]


# -----------------------------------------------------------------------------
# Booklet, key, report, comparison
# -----------------------------------------------------------------------------

def test_hindi_booklet_and_key():
    units = pisa.generate_units(8, seed=20261112, lang="hi")
    booklet = pisa.format_booklet(units)
    key = pisa.format_answer_key(units)
    assert booklet.startswith("# " + pisa.BOOKLET_TITLE["hi"])
    assert pisa.HINDI_DRAFT_NOTE["hi"] in booklet and pisa.HINDI_DRAFT_NOTE["hi"] in key
    assert "## इकाई 1:" in booklet and "**प्रश्न 1.1.**" in booklet
    for name in pisa.CFI_NAMES_HI.values():
        assert name in key
        assert name not in booklet, "the booklet must not give the key away"
    en_key = pisa.format_answer_key(pisa.generate_units(8, seed=20261112))
    assert re.findall(r"\*\*Answer: ([A-D])\*\*", en_key) == \
           re.findall(r"\*\*उत्तर: ([A-D])\*\*", key)
    assert pisa.HINDI_DRAFT_NOTE["en"] not in en_key


def test_english_booklet_has_no_draft_note():
    units = pisa.generate_units(2, seed=1)
    assert "draft" not in pisa.format_booklet(units).lower()


def _answers(units, rng_seed=4, n=12):
    import random
    rng = random.Random(rng_seed)
    rows = []
    for i in range(n):
        row = {"student_id": f"S{i + 1:02d}"}
        for label, _, q in pisa.question_labels(units):
            if q["format"] == "multiple_choice":
                row[label] = rng.choice("ABCD")
            elif q["format"] == "complex_multiple_choice":
                row[label] = "".join(rng.choice("TF") for _ in q["statements"])
            else:
                row[label] = rng.choice(["full", "none", "RF", "PK", "CF", "INT"])
        rows.append(row)
    return rows


def test_the_same_answers_score_the_same_in_both_languages():
    en = pisa.generate_units(6, seed=8)
    hi = pisa.generate_units(6, seed=8, lang="hi")
    rows = _answers(en)
    re_, rh = pisa.score_responses(en, rows), pisa.score_responses(hi, rows)
    assert rh["lang"] == "hi" and "lang" not in re_
    for a, b in zip(re_["students"], rh["students"]):
        assert (a["score"], a["errors"], a["cfi"], a["dominant_error"]) == \
               (b["score"], b["errors"], b["cfi"], b["dominant_error"])
    assert re_["class_errors"] == rh["class_errors"]
    assert [m["count"] for m in re_["misconceptions"]] == \
           [m["count"] for m in rh["misconceptions"]]
    assert all(DEVANAGARI.search(m["answer"]) for m in rh["misconceptions"])


def test_hindi_class_report():
    units = pisa.generate_units(6, seed=8, lang="hi")
    report = pisa.format_class_report(pisa.score_responses(units, _answers(units)))
    assert report.startswith("# " + pisa.REPORT_TITLE["hi"])
    assert "12 विद्यार्थी।" in report
    for heading in ("## पहले क्या दोबारा पढ़ाएँ", "## कक्षा की गलतियों की तस्वीर",
                    "## प्रश्न-दर-प्रश्न", "## विद्यार्थी-दर-विद्यार्थी", "## शोधकर्ताओं के लिए"):
        assert heading in report
    for hint in pisa.RETEACH_HINTS_HI.values():
        assert hint in report
    assert "students" not in report and "What to reteach" not in report


def test_hindi_comparison():
    ub = pisa.generate_units(4, seed=1, lang="hi")
    ua = pisa.generate_units(4, seed=2, lang="hi")
    cmp = pisa.compare_rounds(ub, pisa.score_responses(ub, _answers(ub, 1)),
                              ua, pisa.score_responses(ua, _answers(ua, 2)))
    assert cmp["lang"] == "hi"
    text = pisa.format_comparison(cmp)
    assert text.startswith("# " + pisa.COMPARISON_TITLE["hi"])
    assert "## हर बच्चे पर गलतियाँ, प्रकार के अनुसार" in text


def test_hindi_units_round_trip_through_json(tmp_path):
    units = pisa.generate_units(3, seed=5, lang="hi")
    path = pisa.save_units(units, tmp_path / "u.json")
    assert pisa.load_units(path) == units
    assert DEVANAGARI.search((tmp_path / "u.json").read_text(encoding="utf-8"))


def test_hindi_units_go_into_the_item_bank():
    bank = pisa.units_to_item_bank(pisa.generate_units(2, seed=3, lang="hi"))
    assert bank and all(DEVANAGARI.search(item["question_text"]) for item in bank)


# -----------------------------------------------------------------------------
# Command line
# -----------------------------------------------------------------------------

def test_cli_hindi_end_to_end(tmp_path):
    units_path, booklet, key, sheet = (tmp_path / n for n in
                                       ("u.json", "b.md", "k.md", "r.csv"))
    assert run(["pisa", "3", "--seed", "7", "--lang", "hi", "--out", str(units_path),
                "--booklet", str(booklet), "--key", str(key),
                "--response-sheet", str(sheet)]) == 0
    assert booklet.read_text(encoding="utf-8").startswith("# " + pisa.BOOKLET_TITLE["hi"])
    units = json.loads(units_path.read_text(encoding="utf-8"))
    assert all(u["lang"] == "hi" for u in units)
    import csv
    labels = [lab for lab, _, _ in pisa.question_labels(units)]
    with open(sheet, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["student_id"] + labels)
        w.writeheader()
        for row in _answers(units, n=5):
            w.writerow(row)
    report = tmp_path / "report.md"
    assert run(["pisa-score", str(units_path), str(sheet), "--report", str(report)]) == 0
    assert report.read_text(encoding="utf-8").startswith("# " + pisa.REPORT_TITLE["hi"])


def test_cli_refuses_an_unknown_language(tmp_path):
    with pytest.raises(SystemExit):
        run(["pisa", "2", "--lang", "fr"])


# -----------------------------------------------------------------------------
# What ships in the repo
# -----------------------------------------------------------------------------

def test_committed_hindi_examples_are_up_to_date():
    units = pisa.generate_units(8, seed=20261112, lang="hi")
    with open(os.path.join(ROOT, "examples", "pisa_booklet_example_hi.md"),
              encoding="utf-8") as f:
        assert f.read() == pisa.format_booklet(units)
    with open(os.path.join(ROOT, "examples", "pisa_teacher_key_example_hi.md"),
              encoding="utf-8") as f:
        assert f.read() == pisa.format_answer_key(units)


def test_translation_review_sheet_is_up_to_date():
    """If this fails: confusion-mapper pisa --translation-review docs/hindi-review.md"""
    with open(os.path.join(ROOT, "docs", "hindi-review.md"), encoding="utf-8") as f:
        assert f.read() == pisa.format_translation_review()


def test_translation_review_covers_every_template():
    sheet = pisa.format_translation_review()
    for name in pisa.TEMPLATES:
        assert f"## {name}:" in sheet
        pairs = pisa.translation_pairs(name)
        assert len(pairs) >= 15
        assert all(en and hi for en, hi in pairs)
