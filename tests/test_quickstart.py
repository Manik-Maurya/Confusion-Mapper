"""
test_quickstart.py - pytest suite for confusion_mapper.cli's quickstart
command (_quickstart_demo_data, run_quickstart).

New in v2.6.0. Confirms quickstart is fully self-contained (doesn't touch
sample_data/, which isn't part of the installed wheel -- see
pyproject.toml's `packages` config) and that its demo dataset produces a
real, illustrative (not suspiciously perfect) kappa.

Run with: pytest tests/test_quickstart.py -v
"""

import sys
import os
import inspect

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.cli import _quickstart_demo_data, run_quickstart
from confusion_mapper.stats import compute_cohens_kappa
from confusion_mapper.question_bank import BUILTIN_QUESTIONS


class TestQuickstartDemoData:
    def test_returns_two_equal_length_lists(self):
        human, ai = _quickstart_demo_data()
        assert len(human) == len(ai)

    def test_matches_total_distractor_count_in_question_bank(self):
        human, ai = _quickstart_demo_data()
        n_distractors = sum(len(q["distractors"]) for q in BUILTIN_QUESTIONS)
        assert len(human) == n_distractors

    def test_human_labels_match_question_bank_ground_truth_exactly(self):
        """human_label should be the question bank's own pre-assigned
        error_type, unmodified -- ai_label is what gets perturbed."""
        human, ai = _quickstart_demo_data()
        expected = [d["error_type"] for q in BUILTIN_QUESTIONS for d in q["distractors"]]
        assert human == expected

    def test_ai_labels_mostly_but_not_entirely_agree_with_human(self):
        """Deliberately not a perfect-agreement demo -- some real
        disagreement should be present to be an honest illustration."""
        human, ai = _quickstart_demo_data()
        agreements = sum(1 for h, a in zip(human, ai) if h == a)
        assert 0 < agreements < len(human)

    def test_deterministic_across_calls(self):
        h1, a1 = _quickstart_demo_data()
        h2, a2 = _quickstart_demo_data()
        assert h1 == h2 and a1 == a2

    def test_produces_a_substantial_but_not_perfect_kappa(self):
        """Locks in the specific illustrative kappa (~0.72) the demo was
        designed around -- if the question bank ever changes, this is
        where that would surface."""
        human, ai = _quickstart_demo_data()
        result = compute_cohens_kappa(human, ai)
        assert 0.6 < result["kappa"] < 0.9


class TestRunQuickstart:
    def test_runs_without_error_and_returns_zero(self, capsys):
        result = run_quickstart()
        capsys.readouterr()
        assert result == 0

    def test_never_touches_the_filesystem(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        before = set(os.listdir(tmp_path))
        run_quickstart()
        capsys.readouterr()
        after = set(os.listdir(tmp_path))
        assert before == after

    def test_output_mentions_kappa_and_diagnostics_and_codebook(self, capsys):
        run_quickstart()
        out = capsys.readouterr().out
        assert "kappa" in out.lower()
        assert "AC1" in out
        assert "codebook" in out.lower() or "Category definitions" in out or "Definition" in out

    def test_output_points_to_every_major_subcommand(self, capsys):
        run_quickstart()
        out = capsys.readouterr().out
        for cmd in ("multirater", "export", "assist", "embed-index", "patterns", "publication"):
            assert cmd in out

    def test_source_never_opens_a_file(self):
        """quickstart must not depend on sample_data/, which is excluded
        from the installed wheel -- the precise check is that it never
        calls open() at all, not string-matching for the word
        "sample_data" (which appears harmlessly in this module's own
        docstring explaining why it avoids exactly that dependency)."""
        source = inspect.getsource(run_quickstart) + inspect.getsource(_quickstart_demo_data)
        assert "open(" not in source
