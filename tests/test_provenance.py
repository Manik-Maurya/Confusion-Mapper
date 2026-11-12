"""
test_provenance.py - pytest suite for the v2.6.0 session-provenance additions:
taxonomy_fingerprint(), installed_package_version(), and the four new keys
run_session() now writes into every session dict.

This suite exists specifically to guard the promise made in console.py's
module docstring: the provenance addition is strictly additive. Every test
class below either checks a new function in isolation, or checks that
run_session()'s pre-existing keys (kappa, matrix, type_stats, rater_id,
date, n_questions, n_distractors, ratings, ai_mode) are byte-identical to
calling compute_cohens_kappa / build_confusion_matrix / get_per_type_stats
directly on the same inputs, if a future edit to console.py ever changes
that, this suite should fail.

Run with: pytest tests/test_provenance.py -v
"""

import sys
import os
import io
import re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.taxonomy import TAXONOMY, taxonomy_fingerprint
from confusion_mapper.storage import installed_package_version
from confusion_mapper.question_bank import BUILTIN_QUESTIONS
from confusion_mapper.console import run_session
from confusion_mapper.stats import compute_cohens_kappa, build_confusion_matrix, get_per_type_stats

_HEX12 = re.compile(r"^[0-9a-f]{12}$")


class TestTaxonomyFingerprint:
    def test_returns_a_12_char_hex_string(self):
        fp = taxonomy_fingerprint()
        assert _HEX12.match(fp), f"expected 12 hex chars, got {fp!r}"

    def test_deterministic_across_calls(self):
        assert taxonomy_fingerprint() == taxonomy_fingerprint()

    def test_changes_if_taxonomy_content_changes(self):
        """Not a cryptographic guarantee, just: touching TAXONOMY changes
        the fingerprint, so two sessions coded under different definitions
        are distinguishable later."""
        original = dict(TAXONOMY)
        before = taxonomy_fingerprint()
        try:
            TAXONOMY["RF"] = dict(TAXONOMY["RF"])
            TAXONOMY["RF"]["definition"] = "a deliberately different definition for this test"
            after = taxonomy_fingerprint()
            assert before != after
        finally:
            TAXONOMY.clear()
            TAXONOMY.update(original)
            assert taxonomy_fingerprint() == before  # restored correctly


class TestInstalledPackageVersion:
    def test_returns_a_string(self):
        assert isinstance(installed_package_version(), str)

    def test_matches_importlib_metadata_directly(self):
        import importlib.metadata
        try:
            expected = importlib.metadata.version("confusion-mapper")
        except importlib.metadata.PackageNotFoundError:
            expected = "unknown (not installed via pip)"
        assert installed_package_version() == expected


class TestRunSessionProvenance:
    """
    End-to-end: drive a full interactive session via simulated stdin (every
    distractor classified "1"=RF) and check both the new provenance keys
    and that every pre-existing key is untouched.
    """

    def _run(self, monkeypatch):
        n_distractors = sum(len(q["distractors"]) for q in BUILTIN_QUESTIONS)
        fake_stdin = "\n".join(["1"] * n_distractors) + "\n"
        monkeypatch.setattr(sys, "stdin", io.StringIO(fake_stdin))
        return run_session(BUILTIN_QUESTIONS, api_key="", rater_id="TestRater")

    def test_all_four_provenance_keys_present(self, monkeypatch, capsys):
        session, kappa, matrix, type_stats = self._run(monkeypatch)
        capsys.readouterr()  # discard printed session transcript
        for key in ("session_id", "software_version", "taxonomy_fingerprint", "python_version"):
            assert key in session

    def test_session_id_is_a_valid_uuid4(self, monkeypatch, capsys):
        import uuid
        session, *_ = self._run(monkeypatch)
        capsys.readouterr()
        parsed = uuid.UUID(session["session_id"], version=4)
        assert str(parsed) == session["session_id"]

    def test_two_sessions_get_different_session_ids(self, monkeypatch, capsys):
        session1, *_ = self._run(monkeypatch)
        session2, *_ = self._run(monkeypatch)
        capsys.readouterr()
        assert session1["session_id"] != session2["session_id"]

    def test_taxonomy_fingerprint_matches_module_level_function(self, monkeypatch, capsys):
        session, *_ = self._run(monkeypatch)
        capsys.readouterr()
        assert session["taxonomy_fingerprint"] == taxonomy_fingerprint()

    def test_preexisting_keys_still_present_and_correctly_typed(self, monkeypatch, capsys):
        session, kappa, matrix, type_stats = self._run(monkeypatch)
        capsys.readouterr()
        for key in ("rater_id", "date", "n_questions", "n_distractors",
                   "ratings", "kappa", "matrix", "type_stats", "ai_mode"):
            assert key in session
        assert session["rater_id"] == "TestRater"
        assert session["n_questions"] == len(BUILTIN_QUESTIONS)
        assert session["n_distractors"] == sum(len(q["distractors"]) for q in BUILTIN_QUESTIONS)

    def test_kappa_matrix_type_stats_are_byte_identical_to_direct_calls(self, monkeypatch, capsys):
        """
        The whole point of this test: prove the provenance addition didn't
        quietly change what gets computed, only what gets recorded
        alongside it. Rebuilds human/reference label lists the same way
        run_session() does internally (manual mode, no AI key) and calls
        the stats functions directly for comparison.
        """
        session, kappa, matrix, type_stats = self._run(monkeypatch)
        capsys.readouterr()

        hl = [r["human_label"] for r in session["ratings"] if r["reference_label"]]
        al = [r["reference_label"] for r in session["ratings"] if r["reference_label"]]

        direct_kappa      = compute_cohens_kappa(hl, al)
        direct_matrix     = build_confusion_matrix(hl, al)
        direct_type_stats = get_per_type_stats(hl, al)

        assert session["kappa"] == kappa == direct_kappa
        assert session["matrix"] == matrix == direct_matrix
        assert session["type_stats"] == type_stats == direct_type_stats
