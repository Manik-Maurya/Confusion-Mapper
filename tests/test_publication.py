"""
test_publication.py - pytest suite for confusion_mapper.publication.

New in v2.6.0. Every number appearing in generated text/tables must come
from the input dicts, and DRAFT_NOTICE must always be present so nothing
here could be mistaken for finished, human-reviewed prose.

Run with: pytest tests/test_publication.py -v
"""

import sys
import os
import xml.etree.ElementTree as ET

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.publication import (
    DRAFT_NOTICE,
    _fmt_kappa_like,
    _primary_descriptor,
    generate_methods_paragraph,
    generate_reliability_table,
    generate_frequency_table,
    generate_confusion_matrix_svg,
    generate_frequency_bar_chart_svg,
    assemble_results_appendix,
)
from confusion_mapper.stats import compute_cohens_kappa, gwet_ac1, krippendorff_alpha, \
    build_confusion_matrix, get_per_type_stats
from confusion_mapper.taxonomy import TAXONOMY


@pytest.fixture
def sample_stats():
    human = ["CF"] * 8 + ["RF"] * 2 + ["PK"] * 2
    ai    = ["CF"] * 7 + ["PK"] * 1 + ["RF"] * 2 + ["PK"] * 2
    return {
        "kappa": compute_cohens_kappa(human, ai),
        "ac1": gwet_ac1(human, ai),
        "alpha": krippendorff_alpha(human, ai),
        "matrix": build_confusion_matrix(human, ai),
        "type_stats": get_per_type_stats(human, ai),
    }


class TestFmtKappaLike:
    def test_positive_value_no_leading_zero(self):
        assert _fmt_kappa_like(0.87) == ".87"

    def test_negative_value(self):
        assert _fmt_kappa_like(-0.23) == "-.23"

    def test_none_gives_na(self):
        assert _fmt_kappa_like(None) == "N/A"

    def test_exactly_one(self):
        assert _fmt_kappa_like(1.0) == "1.00"

    def test_exactly_zero(self):
        assert _fmt_kappa_like(0.0) == ".00"


class TestPrimaryDescriptor:
    def test_extracts_first_clause(self):
        assert _primary_descriptor("Almost Perfect, excellent agreement.") == "almost perfect"

    def test_handles_no_comma(self):
        assert _primary_descriptor("Simple.") == "simple"

    def test_strips_trailing_period_and_lowercases(self):
        assert _primary_descriptor("Substantial, close to target.") == "substantial"


class TestGenerateMethodsParagraph:
    def test_includes_draft_notice(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"])
        assert DRAFT_NOTICE in text

    def test_includes_real_n_and_kappa(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"])
        assert f"N = {sample_stats['kappa']['n']}" in text
        assert _fmt_kappa_like(sample_stats["kappa"]["kappa"]) in text

    def test_sentence_reads_naturally_no_run_on_clauses(self, sample_stats):
        """Regression check for the exact bug caught during development:
        the interpretation string's full text ('Almost Perfect, excellent
        agreement.') must not appear verbatim mid-sentence -- only its
        primary descriptor should."""
        text = generate_methods_paragraph(sample_stats["kappa"])
        assert "excellent agreement, kappa" not in text

    def test_ac1_omitted_when_not_given(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"])
        assert "AC1" not in text

    def test_ac1_included_when_given(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"], ac1_result=sample_stats["ac1"])
        assert "AC1" in text
        assert _fmt_kappa_like(sample_stats["ac1"]["ac1"]) in text

    def test_alpha_included_when_given(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"], alpha_result=sample_stats["alpha"])
        assert "Krippendorff" in text

    def test_ci_included_when_given(self, sample_stats):
        text = generate_methods_paragraph(sample_stats["kappa"], ci_result={"lower": 0.5, "upper": 0.9})
        assert "95% CI" in text
        assert ".50" in text and ".90" in text

    def test_n_raters_changes_wording(self, sample_stats):
        text2 = generate_methods_paragraph(sample_stats["kappa"], n_raters=2)
        text3 = generate_methods_paragraph(sample_stats["kappa"], n_raters=3)
        assert "two raters" in text2
        assert "3 raters" in text3

    def test_different_kappa_value_produces_different_text(self):
        """Never-fabricates check: change the input, the output changes correspondingly."""
        r1 = compute_cohens_kappa(["A", "A"], ["A", "A"], categories=["A", "B"])
        r2 = compute_cohens_kappa(["A", "B"], ["B", "A"], categories=["A", "B"])
        t1 = generate_methods_paragraph(r1)
        t2 = generate_methods_paragraph(r2)
        assert t1 != t2
        assert _fmt_kappa_like(r1["kappa"]) in t1
        assert _fmt_kappa_like(r2["kappa"]) in t2


class TestGenerateReliabilityTable:
    def test_includes_draft_notice(self, sample_stats):
        assert DRAFT_NOTICE in generate_reliability_table(sample_stats["kappa"])

    def test_kappa_row_always_present(self, sample_stats):
        table = generate_reliability_table(sample_stats["kappa"])
        assert "Cohen's kappa" in table
        assert _fmt_kappa_like(sample_stats["kappa"]["kappa"]) in table

    def test_ac1_row_only_when_given(self, sample_stats):
        without = generate_reliability_table(sample_stats["kappa"])
        with_ac1 = generate_reliability_table(sample_stats["kappa"], ac1_result=sample_stats["ac1"])
        assert "Gwet's AC1" not in without
        assert "Gwet's AC1" in with_ac1

    def test_alpha_row_only_when_given(self, sample_stats):
        without = generate_reliability_table(sample_stats["kappa"])
        with_alpha = generate_reliability_table(sample_stats["kappa"], alpha_result=sample_stats["alpha"])
        assert "Krippendorff" not in without
        assert "Krippendorff" in with_alpha

    def test_valid_markdown_table_structure(self, sample_stats):
        table = generate_reliability_table(sample_stats["kappa"])
        assert "|---|---|---|---|---|" in table


class TestGenerateFrequencyTable:
    def test_every_category_gets_a_row(self, sample_stats):
        table = generate_frequency_table(sample_stats["type_stats"])
        for code in sample_stats["type_stats"]:
            assert f"| {code} |" in table

    def test_uses_real_taxonomy_names(self, sample_stats):
        table = generate_frequency_table(sample_stats["type_stats"], taxonomy=TAXONOMY)
        assert "Confabulation" in table  # CFI's real name for CF

    def test_falls_back_to_code_without_taxonomy_name(self, sample_stats):
        table = generate_frequency_table(sample_stats["type_stats"], taxonomy={})
        assert "| CF | CF |" in table

    def test_reflects_real_counts(self, sample_stats):
        table = generate_frequency_table(sample_stats["type_stats"])
        for code, stats in sample_stats["type_stats"].items():
            assert str(stats["total"]) in table

    def test_reflects_real_percentages_not_always_zero(self, sample_stats):
        """Regression test: get_per_type_stats() returns the percentage
        under the key 'pct', not 'percentage' -- a mismatched .get() key
        would silently default to 0% for every row without raising."""
        table = generate_frequency_table(sample_stats["type_stats"])
        for code, stats in sample_stats["type_stats"].items():
            if stats["total"] > 0:
                assert f"{stats['pct']}%" in table
        # CF has 7/8 agreed -> pct should not be 0
        assert sample_stats["type_stats"]["CF"]["pct"] != 0
        assert f"{sample_stats['type_stats']['CF']['pct']}%" in table


class TestSVGFigures:
    def test_confusion_matrix_svg_is_well_formed_xml(self, sample_stats):
        svg = generate_confusion_matrix_svg(sample_stats["matrix"])
        ET.fromstring(svg)  # raises if malformed

    def test_bar_chart_svg_is_well_formed_xml(self, sample_stats):
        svg = generate_frequency_bar_chart_svg(sample_stats["type_stats"])
        ET.fromstring(svg)

    def test_confusion_matrix_svg_contains_real_counts(self, sample_stats):
        svg = generate_confusion_matrix_svg(sample_stats["matrix"])
        diag_count = sample_stats["matrix"]["CF"]["CF"]
        assert f">{diag_count}<" in svg

    def test_bar_chart_svg_contains_real_counts(self, sample_stats):
        svg = generate_frequency_bar_chart_svg(sample_stats["type_stats"])
        for code, stats in sample_stats["type_stats"].items():
            assert f">{stats['total']}<" in svg

    def test_confusion_matrix_svg_respects_custom_category_order(self, sample_stats):
        svg = generate_confusion_matrix_svg(sample_stats["matrix"], categories=["RF", "PK", "CF", "INT"])
        assert svg.index(">RF<") < svg.index(">CF<")

    def test_bar_chart_empty_type_stats_does_not_crash(self):
        svg = generate_frequency_bar_chart_svg({})
        ET.fromstring(svg)


class TestAssembleResultsAppendix:
    def test_includes_every_section(self, sample_stats):
        doc = assemble_results_appendix(
            sample_stats["kappa"], sample_stats["type_stats"], sample_stats["matrix"],
            ac1_result=sample_stats["ac1"], alpha_result=sample_stats["alpha"],
        )
        assert "## Methods" in doc
        assert "## Reliability statistics" in doc
        assert "## Category frequency" in doc
        assert "## Figures" in doc
        assert "<svg" in doc

    def test_draft_notice_present(self, sample_stats):
        doc = assemble_results_appendix(sample_stats["kappa"], sample_stats["type_stats"],
                                        sample_stats["matrix"])
        assert DRAFT_NOTICE in doc

    def test_both_svgs_embedded_and_well_formed(self, sample_stats):
        doc = assemble_results_appendix(sample_stats["kappa"], sample_stats["type_stats"],
                                        sample_stats["matrix"])
        assert doc.count("<svg") == 2
        assert doc.count("</svg>") == 2
