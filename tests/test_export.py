"""
test_export.py - pytest suite for confusion_mapper.export_for_r/spss/jasp/all()

New in v2.6.0.

Note: this suite checks the *files themselves* (existence, correct value
labels/factor levels, correct structure) since there's no R or SPSS
interpreter in this test environment to execute the generated scripts
against. Both formats are plain-text, decades-stable syntaxes reviewed by
hand; if you have R or SPSS available, running the generated .R/.sps files
against sample_data/example_labels.csv once is worth doing before you rely
on them for a real analysis.

Run with: pytest tests/test_export.py -v
"""

import sys
import os
import csv
import shutil
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import export_for_r, export_for_spss, export_for_jasp, export_all


@pytest.fixture
def sample_rows():
    return [
        {"item_id": "Q1_A", "distractor_text": "text one", "human_label": "CF", "ai_label": "CF"},
        {"item_id": "Q1_B", "distractor_text": "text two", "human_label": "RF", "ai_label": "PK"},
        {"item_id": "Q1_C", "distractor_text": "text three", "human_label": "INT", "ai_label": "INT"},
    ]


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp()
    yield d
    shutil.rmtree(d, ignore_errors=True)


class TestExportForR:
    def test_writes_csv_and_r_script(self, sample_rows, tmp_dir):
        result = export_for_r(sample_rows, os.path.join(tmp_dir, "out.csv"))
        assert os.path.exists(result["csv"])
        assert os.path.exists(result["script"])
        assert result["script"].endswith(".R")

    def test_csv_content_matches_input(self, sample_rows, tmp_dir):
        result = export_for_r(sample_rows, os.path.join(tmp_dir, "out.csv"))
        with open(result["csv"], newline="", encoding="utf-8") as f:
            rows_out = list(csv.DictReader(f))
        assert len(rows_out) == 3
        assert rows_out[0]["item_id"] == "Q1_A"
        assert rows_out[0]["human_label"] == "CF"

    def test_r_script_sets_correct_factor_levels_in_taxonomy_order(self, sample_rows, tmp_dir):
        result = export_for_r(sample_rows, os.path.join(tmp_dir, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        assert 'levels = c("RF", "PK", "CF", "INT")' in script
        assert 'labels = c("Recall Failure", "Partial Knowledge", "Confabulation", "Interference")' in script
        assert "df$human_label <- factor" in script
        assert "df$ai_label <- factor" in script

    def test_r_script_references_correct_csv_filename(self, sample_rows, tmp_dir):
        result = export_for_r(sample_rows, os.path.join(tmp_dir, "coded.csv"))
        script = open(result["script"], encoding="utf-8").read()
        assert 'read.csv("coded.csv"' in script

    def test_custom_categories(self, sample_rows, tmp_dir):
        rows = [{"item_id": "Q1", "human_label": "Yes", "ai_label": "No"}]
        result = export_for_r(rows, os.path.join(tmp_dir, "out.csv"), categories=["Yes", "No"])
        script = open(result["script"], encoding="utf-8").read()
        assert 'levels = c("Yes", "No")' in script

    def test_empty_rows_raises(self, tmp_dir):
        with pytest.raises(ValueError, match="empty"):
            export_for_r([], os.path.join(tmp_dir, "out.csv"))


class TestExportForSPSS:
    def test_writes_csv_and_sps_script(self, sample_rows, tmp_dir):
        result = export_for_spss(sample_rows, os.path.join(tmp_dir, "out.csv"))
        assert os.path.exists(result["csv"])
        assert os.path.exists(result["script"])
        assert result["script"].endswith(".sps")

    def test_sps_contains_get_data_block(self, sample_rows, tmp_dir):
        result = export_for_spss(sample_rows, os.path.join(tmp_dir, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        assert "GET DATA /TYPE=TXT" in script
        assert '/FILE="out.csv"' in script
        assert "/DELIMITERS=\",\"" in script

    def test_sps_value_labels_cover_every_category(self, sample_rows, tmp_dir):
        result = export_for_spss(sample_rows, os.path.join(tmp_dir, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        for code, name in [("RF", "Recall Failure"), ("PK", "Partial Knowledge"),
                           ("CF", "Confabulation"), ("INT", "Interference")]:
            assert f"'{code}' '{name}'" in script

    def test_sps_variables_clause_lists_every_column(self, sample_rows, tmp_dir):
        result = export_for_spss(sample_rows, os.path.join(tmp_dir, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        for col in ("item_id", "distractor_text", "human_label", "ai_label"):
            assert col in script

    def test_ends_with_a_period_terminated_variables_clause(self, sample_rows, tmp_dir):
        """A missing trailing period on /VARIABLES is a classic SPSS syntax
        error -- guard against regressing it."""
        result = export_for_spss(sample_rows, os.path.join(tmp_dir, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        variables_block = script.split("/VARIABLES=")[1].split("CACHE.")[0]
        assert variables_block.strip().endswith(".")


class TestExportForJASP:
    def test_writes_csv_and_instructions(self, sample_rows, tmp_dir):
        result = export_for_jasp(sample_rows, os.path.join(tmp_dir, "out.csv"))
        assert os.path.exists(result["csv"])
        assert os.path.exists(result["instructions"])
        assert result["instructions"].endswith("_JASP_INSTRUCTIONS.txt")

    def test_instructions_mention_the_kappa_analysis(self, sample_rows, tmp_dir):
        result = export_for_jasp(sample_rows, os.path.join(tmp_dir, "out.csv"))
        text = open(result["instructions"], encoding="utf-8").read()
        assert "Cohen's & Fleiss' Kappa" in text

    def test_instructions_list_every_category_code(self, sample_rows, tmp_dir):
        result = export_for_jasp(sample_rows, os.path.join(tmp_dir, "out.csv"))
        text = open(result["instructions"], encoding="utf-8").read()
        assert "RF = Recall Failure" in text
        assert "INT = Interference" in text


class TestExportAll:
    def test_default_writes_all_three_formats(self, sample_rows, tmp_dir):
        result = export_all(sample_rows, tmp_dir)
        assert result["r"] is not None
        assert result["spss"] is not None
        assert result["jasp"] is not None
        assert os.path.exists(result["r"]["script"])
        assert os.path.exists(result["spss"]["script"])
        assert os.path.exists(result["jasp"]["instructions"])

    def test_formats_subset_only_writes_requested(self, sample_rows, tmp_dir):
        result = export_all(sample_rows, tmp_dir, formats=("r",))
        assert result["r"] is not None
        assert result["spss"] is None
        assert result["jasp"] is None

    def test_creates_out_dir_if_missing(self, sample_rows, tmp_dir):
        nested = os.path.join(tmp_dir, "does", "not", "exist", "yet")
        result = export_all(sample_rows, nested)
        assert os.path.isdir(nested)
        assert os.path.exists(result["r"]["csv"])

    def test_all_three_formats_share_the_same_csv_content(self, sample_rows, tmp_dir):
        """r/spss/jasp all point at freshly (re)written copies of the same
        rows under the same stem -- confirm they're identical, not
        silently diverging across calls."""
        result = export_all(sample_rows, tmp_dir, stem="shared")
        r_csv = open(result["r"]["csv"], encoding="utf-8").read()
        spss_csv = open(result["spss"]["csv"], encoding="utf-8").read()
        jasp_csv = open(result["jasp"]["csv"], encoding="utf-8").read()
        assert r_csv == spss_csv == jasp_csv

    def test_end_to_end_on_bundled_sample_data(self, tmp_dir):
        sample_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "sample_data", "example_labels.csv",
        )
        with open(sample_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        result = export_all(rows, tmp_dir)
        with open(result["r"]["csv"], newline="", encoding="utf-8") as f:
            assert len(list(csv.DictReader(f))) == 30
