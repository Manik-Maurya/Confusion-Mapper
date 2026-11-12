"""
test_validation.py - pytest suite for confusion_mapper.validate_dataset()

New in v2.6.0. Separate file from test_kappa.py on purpose: validation is a
distinct concern (data quality) from reliability statistics, and giving it
its own test file is the pattern future new modules (e.g. a multi-rater
workflow) should follow rather than growing test_kappa.py indefinitely.

Run with: pytest tests/test_validation.py -v
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import validate_dataset, ERROR_TYPES


def _row(item_id="Q1_A", distractor_text="some text", human_label="CF", ai_label="CF"):
    return {
        "item_id": item_id,
        "distractor_text": distractor_text,
        "human_label": human_label,
        "ai_label": ai_label,
    }


class TestCleanData:
    def test_valid_dataset_has_no_errors_or_warnings(self):
        rows = [_row(item_id=f"Q{i}") for i in range(5)]
        report = validate_dataset(rows)
        assert report["valid"] is True
        assert report["errors"] == []
        assert report["warnings"] == []
        assert report["n_records"] == 5

    def test_empty_dataset_is_valid(self):
        report = validate_dataset([])
        assert report["valid"] is True
        assert report["n_records"] == 0


class TestMissingLabels:
    def test_empty_human_label_is_an_error(self):
        rows = [_row(human_label="")]
        report = validate_dataset(rows)
        assert report["valid"] is False
        assert any("human_label" in e["issue"] for e in report["errors"])

    def test_empty_ai_label_is_an_error(self):
        rows = [_row(ai_label="")]
        report = validate_dataset(rows)
        assert report["valid"] is False
        assert any("ai_label" in e["issue"] for e in report["errors"])

    def test_whitespace_only_label_counts_as_missing(self):
        rows = [_row(human_label="   ")]
        report = validate_dataset(rows)
        assert report["valid"] is False


class TestImpossibleValues:
    def test_label_not_in_categories_is_an_error(self):
        rows = [_row(human_label="CG")]  # typo for "CF"
        report = validate_dataset(rows)
        assert report["valid"] is False
        assert any("impossible value" in e["issue"] for e in report["errors"])

    def test_all_default_categories_are_accepted(self):
        rows = [_row(item_id=f"Q{i}", human_label=c, ai_label=c)
                for i, c in enumerate(ERROR_TYPES)]
        report = validate_dataset(rows)
        assert report["valid"] is True

    def test_custom_categories_respected(self):
        rows = [_row(human_label="Yes", ai_label="No")]
        report = validate_dataset(rows, categories=["Yes", "No"])
        assert report["valid"] is True


class TestDuplicateIDs:
    def test_duplicate_item_id_is_an_error(self):
        rows = [_row(item_id="Q1_A"), _row(item_id="Q1_A")]
        report = validate_dataset(rows)
        assert report["valid"] is False
        dup_errors = [e for e in report["errors"] if "duplicate" in e["issue"]]
        assert len(dup_errors) == 1
        assert dup_errors[0]["row"] == 2  # the second occurrence is flagged

    def test_missing_item_id_is_a_warning_not_an_error(self):
        rows = [_row(item_id="")]
        report = validate_dataset(rows)
        assert report["valid"] is True  # warning only, doesn't fail validation
        assert any("item_id is missing" in w["issue"] for w in report["warnings"])

    def test_three_way_duplicate_flags_second_and_third(self):
        rows = [_row(item_id="Q1_A"), _row(item_id="Q1_A"), _row(item_id="Q1_A")]
        report = validate_dataset(rows)
        dup_errors = [e for e in report["errors"] if "duplicate" in e["issue"]]
        assert len(dup_errors) == 2
        assert [e["row"] for e in dup_errors] == [2, 3]


class TestBrokenFormatting:
    def test_empty_distractor_text_is_a_warning(self):
        rows = [_row(distractor_text="")]
        report = validate_dataset(rows)
        assert report["valid"] is True
        assert any("distractor_text" in w["issue"] for w in report["warnings"])

    def test_missing_distractor_text_key_is_silently_skipped(self):
        """
        distractor_text is optional metadata, not a required column, a
        minimal two-column (human_label, ai_label) CSV should validate
        cleanly with no distractor_text check at all.
        """
        rows = [{"human_label": "CF", "ai_label": "CF"}]
        report = validate_dataset(rows)
        assert report["valid"] is True
        assert not any("distractor_text" in w["issue"] for w in report["warnings"])


class TestRowNumbering:
    def test_row_numbers_are_one_indexed(self):
        """Row numbers should match the line a human would open in the CSV,
        not a zero-indexed Python position."""
        rows = [_row(), _row(human_label="")]
        report = validate_dataset(rows)
        assert report["errors"][0]["row"] == 2


class TestRealisticMixedFile:
    def test_multiple_simultaneous_issues_all_reported(self):
        rows = [
            _row(item_id="Q1_A"),                      # clean
            _row(item_id="Q1_B", human_label=""),        # error: missing human_label
            _row(item_id="Q1_A"),                        # error: duplicate of row 1
            _row(item_id="", ai_label="XX"),              # warning: missing id + error: impossible ai_label
        ]
        report = validate_dataset(rows)
        assert report["valid"] is False
        assert report["n_records"] == 4
        assert len(report["errors"]) == 3
        assert len(report["warnings"]) == 1
