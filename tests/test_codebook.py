"""
test_codebook.py - pytest suite for confusion_mapper.generate_codebook() / write_codebook()

New in v2.6.0.

Run with: pytest tests/test_codebook.py -v
"""

import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper import generate_codebook, write_codebook, ERROR_TYPES, TAXONOMY


class TestGenerateCodebook:
    def test_includes_every_default_category(self):
        text = generate_codebook()
        for code in ERROR_TYPES:
            assert f"({code})" in text

    def test_includes_real_definitions_not_placeholders(self):
        text = generate_codebook()
        # spot-check one real definition string is present verbatim
        assert TAXONOMY["RF"]["definition"] in text
        assert TAXONOMY["CF"]["example"] in text

    def test_decision_rule_is_explicitly_a_placeholder_not_fabricated(self):
        """
        The whole design point of this function: it must never emit
        decision-rule text that looks authored/authoritative. Every
        category's decision rule field should be the same literal
        placeholder, not something synthesized per-category.
        """
        text = generate_codebook()
        placeholder_count = text.count(
            "*(fill in from your coding manual / Stage 1 RR methods, not auto-generated)*"
        )
        assert placeholder_count == len(ERROR_TYPES)

    def test_custom_title(self):
        text = generate_codebook(title="My Custom Codebook")
        assert text.startswith("# My Custom Codebook")

    def test_metadata_header_present_by_default(self):
        text = generate_codebook()
        assert "Generated" in text
        assert "taxonomy fingerprint" in text

    def test_metadata_header_omitted_when_requested(self):
        text = generate_codebook(include_metadata=False)
        assert "Generated" not in text
        assert "taxonomy fingerprint" not in text

    def test_metadata_fingerprint_matches_taxonomy_fingerprint(self):
        from confusion_mapper.taxonomy import taxonomy_fingerprint
        text = generate_codebook()
        assert taxonomy_fingerprint() in text

    def test_custom_category_subset(self):
        text = generate_codebook(categories=["RF", "CF"])
        assert "(RF)" in text
        assert "(CF)" in text
        assert "(PK)" not in text
        assert "(INT)" not in text

    def test_unknown_category_code_degrades_gracefully(self):
        """A custom taxonomy code with no TAXONOMY entry shouldn't crash --
        it should fall back to the code itself with an explicit
        no-definition-on-file marker."""
        text = generate_codebook(categories=["ZZ"])
        assert "(ZZ)" in text
        assert "no definition on file" in text
        assert "no example on file" in text

    def test_summary_table_present(self):
        text = generate_codebook()
        assert "| Code | Name | Definition |" in text
        for code in ERROR_TYPES:
            assert f"| {code} |" in text


class TestWriteCodebook:
    def test_writes_file_and_returns_path(self):
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            result = write_codebook(path)
            assert result == path
            content = open(path, encoding="utf-8").read()
            assert content == generate_codebook()
        finally:
            os.remove(path)

    def test_respects_all_kwargs(self):
        fd, path = tempfile.mkstemp(suffix=".md")
        os.close(fd)
        try:
            write_codebook(path, categories=["RF"], title="Just RF", include_metadata=False)
            content = open(path, encoding="utf-8").read()
            assert content.startswith("# Just RF")
            assert "(RF)" in content
            assert "(PK)" not in content
            assert "Generated" not in content
        finally:
            os.remove(path)
