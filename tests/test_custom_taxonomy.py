"""
test_custom_taxonomy.py - pytest suite for custom (non-CFI) taxonomy
support: stats.load_taxonomy_from_json() (pre-existing but previously
untested), and the `taxonomy` parameter added to codebook.generate_codebook()
and export.export_for_r/spss/jasp/all() in this release so a custom
taxonomy gets real category names/definitions instead of "no definition on
file" placeholders.

New test file for v2.6.0. The end-to-end tests at the bottom load the real
sample_data/item_bank_distractor_taxonomy.json and
sample_data/item_bank_demo.csv shipped with the package, a distractor-
functioning taxonomy modeled on published item-analysis literature (not an
official PISA framework; see that file's _comment), and run kappa,
codebook, and export against them, as the concrete proof that this
toolkit's reliability/export/documentation machinery works for a taxonomy
that has nothing to do with the CFI categories the rest of the package
defaults to.

Run with: pytest tests/test_custom_taxonomy.py -v
"""

import sys
import os
import csv
import json
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.stats import load_taxonomy_from_json, compute_cohens_kappa
from confusion_mapper.codebook import generate_codebook
from confusion_mapper.export import export_for_r, export_for_spss, export_for_jasp, export_all
from confusion_mapper.taxonomy import TAXONOMY, ERROR_TYPES

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ITEM_BANK_TAXONOMY = os.path.join(_REPO_ROOT, "sample_data", "item_bank_distractor_taxonomy.json")
_ITEM_BANK_CSV = os.path.join(_REPO_ROOT, "sample_data", "item_bank_demo.csv")
_EXISTING_CUSTOM_TAXONOMY = os.path.join(_REPO_ROOT, "sample_data", "custom_taxonomy.json")


def _write_taxonomy_json(labels):
    fd, path = tempfile.mkstemp(suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump({"labels": labels}, f)
    return path


class TestLoadTaxonomyFromJSON:
    def test_loads_codes_and_taxonomy_dict(self):
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha", "definition": "def A"},
            {"code": "B", "name": "Beta", "definition": "def B"},
        ])
        try:
            codes, tax = load_taxonomy_from_json(path)
            assert codes == ["A", "B"]
            assert tax["A"]["name"] == "Alpha"
            assert tax["A"]["definition"] == "def A"
            assert tax["B"]["name"] == "Beta"
        finally:
            os.remove(path)

    def test_optional_fields_have_sane_defaults(self):
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha", "definition": "def A"},
            {"code": "B", "name": "Beta", "definition": "def B"},
        ])
        try:
            codes, tax = load_taxonomy_from_json(path)
            assert tax["A"]["number"] == "1"       # defaults to position + 1
            assert tax["B"]["number"] == "2"
            assert tax["A"]["example"] == ""
            assert tax["A"]["color"] == "#888888"
        finally:
            os.remove(path)

    def test_explicit_number_and_color_respected(self):
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha", "definition": "d", "number": "7", "color": "#123456"},
            {"code": "B", "name": "Beta", "definition": "d"},
        ])
        try:
            codes, tax = load_taxonomy_from_json(path)
            assert tax["A"]["number"] == "7"
            assert tax["A"]["color"] == "#123456"
        finally:
            os.remove(path)

    def test_missing_labels_key_raises(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump({"not_labels": []}, f)
        try:
            with pytest.raises(ValueError, match="labels"):
                load_taxonomy_from_json(path)
        finally:
            os.remove(path)

    def test_fewer_than_two_labels_raises(self):
        path = _write_taxonomy_json([{"code": "A", "name": "Alpha", "definition": "d"}])
        try:
            with pytest.raises(ValueError, match="at least 2"):
                load_taxonomy_from_json(path)
        finally:
            os.remove(path)

    def test_missing_required_key_raises(self):
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha"},  # missing "definition"
            {"code": "B", "name": "Beta", "definition": "d"},
        ])
        try:
            with pytest.raises(ValueError, match="definition"):
                load_taxonomy_from_json(path)
        finally:
            os.remove(path)

    def test_duplicate_code_raises(self):
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha", "definition": "d1"},
            {"code": "A", "name": "Alpha2", "definition": "d2"},
        ])
        try:
            with pytest.raises(ValueError, match="duplicate"):
                load_taxonomy_from_json(path)
        finally:
            os.remove(path)

    def test_returned_taxonomy_dict_is_kappa_compatible(self):
        """The whole point: codes loaded this way must work as `categories`
        for the existing, untouched kappa machinery."""
        path = _write_taxonomy_json([
            {"code": "A", "name": "Alpha", "definition": "d"},
            {"code": "B", "name": "Beta", "definition": "d"},
        ])
        try:
            codes, tax = load_taxonomy_from_json(path)
            result = compute_cohens_kappa(["A", "B", "A"], ["A", "B", "B"], categories=codes)
            assert "kappa" in result
        finally:
            os.remove(path)

    def test_ships_with_the_repo_and_loads_cleanly(self):
        """sample_data/custom_taxonomy.json (pre-existing, referenced in
        load_taxonomy_from_json's own docstring) should actually load."""
        codes, tax = load_taxonomy_from_json(_EXISTING_CUSTOM_TAXONOMY)
        assert len(codes) >= 2
        assert all(c in tax for c in codes)


class TestCodebookWithCustomTaxonomy:
    def test_uses_custom_names_not_placeholders(self):
        custom_tax = {"A": {"name": "Alpha Category", "definition": "custom def",
                            "example": "custom ex", "number": "1"}}
        text = generate_codebook(categories=["A"], taxonomy=custom_tax)
        assert "Alpha Category" in text
        assert "custom def" in text
        assert "no definition on file" not in text

    def test_defaults_to_built_in_taxonomy_when_none_given(self):
        text = generate_codebook()  # taxonomy=None
        assert TAXONOMY["RF"]["definition"] in text

    def test_metadata_header_differs_for_custom_vs_builtin(self):
        builtin_text = generate_codebook()
        custom_text = generate_codebook(
            categories=["A", "B"],
            taxonomy={"A": {"name": "A", "definition": "d"}, "B": {"name": "B", "definition": "d"}},
        )
        assert "taxonomy fingerprint" in builtin_text
        assert "taxonomy fingerprint" not in custom_text
        assert "custom taxonomy" in custom_text


class TestExportWithCustomTaxonomy:
    _rows = [{"item_id": "Q1", "human_label": "A", "ai_label": "A"},
            {"item_id": "Q2", "human_label": "B", "ai_label": "A"}]
    _tax = {"A": {"name": "Alpha Category", "definition": "d"},
           "B": {"name": "Beta Category", "definition": "d"}}

    def test_r_export_uses_custom_names_in_factor_labels(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            result = export_for_r(self._rows, path, categories=["A", "B"], taxonomy=self._tax)
            script = open(result["script"], encoding="utf-8").read()
            assert "Alpha Category" in script
            assert "Beta Category" in script
        finally:
            os.remove(path)
            os.remove(result["script"])

    def test_spss_export_uses_custom_names_in_value_labels(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            result = export_for_spss(self._rows, path, categories=["A", "B"], taxonomy=self._tax)
            script = open(result["script"], encoding="utf-8").read()
            assert "'A' 'Alpha Category'" in script
            assert "'B' 'Beta Category'" in script
        finally:
            os.remove(path)
            os.remove(result["script"])

    def test_jasp_export_uses_custom_names_in_instructions(self):
        fd, path = tempfile.mkstemp(suffix=".csv")
        os.close(fd)
        try:
            result = export_for_jasp(self._rows, path, categories=["A", "B"], taxonomy=self._tax)
            text = open(result["instructions"], encoding="utf-8").read()
            assert "A = Alpha Category" in text
            assert "B = Beta Category" in text
        finally:
            os.remove(path)
            os.remove(result["instructions"])

    def test_export_all_threads_taxonomy_to_every_format(self):
        d = tempfile.mkdtemp()
        result = export_all(self._rows, d, categories=["A", "B"], taxonomy=self._tax)
        r_script = open(result["r"]["script"], encoding="utf-8").read()
        spss_script = open(result["spss"]["script"], encoding="utf-8").read()
        jasp_text = open(result["jasp"]["instructions"], encoding="utf-8").read()
        assert "Alpha Category" in r_script
        assert "Alpha Category" in spss_script
        assert "Alpha Category" in jasp_text

    def test_export_still_defaults_to_cfi_when_no_taxonomy_given(self):
        """Backward compatibility: omitting `taxonomy` must behave exactly
        as it did before this parameter existed."""
        rows = [{"item_id": "Q1", "human_label": "CF", "ai_label": "CF"},
               {"item_id": "Q2", "human_label": "RF", "ai_label": "RF"}]
        d = tempfile.mkdtemp()
        result = export_for_r(rows, os.path.join(d, "out.csv"))
        script = open(result["script"], encoding="utf-8").read()
        assert "Confabulation" in script   # CFI's real name for "CF"


class TestItemBankExampleEndToEnd:
    """
    The concrete proof, not just the assertion: this package's reliability
    stats, codebook generator, and export packages all work correctly on a
    taxonomy and dataset that have nothing to do with the CFI categories --
    modeled on real item-analysis literature for large-scale-assessment
    (PISA-style) item banks, not the CFI cognitive-error framework.
    """

    def test_taxonomy_file_loads(self):
        codes, tax = load_taxonomy_from_json(_ITEM_BANK_TAXONOMY)
        assert set(codes) == {"NF", "PLM", "FD", "AMB"}
        assert tax["PLM"]["name"] == "Potentially Lead to Misconception"

    def test_kappa_computes_on_the_demo_csv(self):
        codes, tax = load_taxonomy_from_json(_ITEM_BANK_TAXONOMY)
        with open(_ITEM_BANK_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        human = [r["human_label"] for r in rows]
        ai = [r["ai_label"] for r in rows]
        result = compute_cohens_kappa(human, ai, categories=codes)
        assert result["n"] == len(rows)
        assert -1.0 <= result["kappa"] <= 1.0

    def test_codebook_generates_real_content_for_item_bank_taxonomy(self):
        codes, tax = load_taxonomy_from_json(_ITEM_BANK_TAXONOMY)
        text = generate_codebook(categories=codes, taxonomy=tax,
                                 title="Item Bank Distractor-Functioning Codebook")
        assert "Non-Functional Distractor" in text
        assert "Potentially Lead to Misconception" in text
        assert "no definition on file" not in text

    def test_export_generates_real_content_for_item_bank_taxonomy(self):
        codes, tax = load_taxonomy_from_json(_ITEM_BANK_TAXONOMY)
        with open(_ITEM_BANK_CSV, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        d = tempfile.mkdtemp()
        result = export_all(rows, d, categories=codes, taxonomy=tax)
        r_script = open(result["r"]["script"], encoding="utf-8").read()
        assert "Non-Functional Distractor" in r_script


class TestCLITaxonomyFileFlag:
    """
    The `--taxonomy-file` flag itself (argparse wiring + the "use the
    file's own category order unless --categories overrides it" fallback
    logic) isn't exercised by the direct-function tests above, which is
    why these call cli() the same way run() does, rather than the
    underlying functions directly.
    """

    def test_codebook_taxonomy_file_flag(self, capsys):
        from confusion_mapper.cli import cli
        cli(["codebook", "--taxonomy-file", _ITEM_BANK_TAXONOMY])
        out = capsys.readouterr().out
        assert "Non-Functional Distractor" in out
        assert "Potentially Lead to Misconception" in out

    def test_codebook_taxonomy_file_flag_uses_default_title_when_not_overridden(self, capsys):
        from confusion_mapper.cli import cli
        cli(["codebook", "--taxonomy-file", _ITEM_BANK_TAXONOMY])
        out = capsys.readouterr().out
        assert out.startswith("# Coding Manual")   # not "# CFI Coding Manual"

    def test_codebook_taxonomy_file_flag_respects_explicit_title(self, capsys):
        from confusion_mapper.cli import cli
        cli(["codebook", "--taxonomy-file", _ITEM_BANK_TAXONOMY, "--title", "My Title"])
        out = capsys.readouterr().out
        assert out.startswith("# My Title")

    def test_export_taxonomy_file_flag(self, capsys):
        from confusion_mapper.cli import cli
        d = tempfile.mkdtemp()
        cli(["export", _ITEM_BANK_CSV, "--taxonomy-file", _ITEM_BANK_TAXONOMY,
            "--out", d, "--formats", "r"])
        capsys.readouterr()
        r_script_path = os.path.join(d, "confusion_mapper_export.R")
        assert os.path.exists(r_script_path)
        assert "Non-Functional Distractor" in open(r_script_path, encoding="utf-8").read()

    def test_explicit_categories_overrides_taxonomy_file_order(self, capsys):
        """--categories, if given, should win over the taxonomy file's own
        category list/order (e.g. to generate a codebook for a subset)."""
        from confusion_mapper.cli import cli
        cli(["codebook", "--taxonomy-file", _ITEM_BANK_TAXONOMY, "--categories", "NF,PLM"])
        out = capsys.readouterr().out
        assert "(NF)" in out
        assert "(PLM)" in out
        assert "(FD)" not in out
        assert "(AMB)" not in out
