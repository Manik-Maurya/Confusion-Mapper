"""
ConfusionMapper

A tool for classifying wrong answer choices in multiple-choice questions by
the type of cognitive error they represent, and for measuring how well a
human researcher and an AI agree on those labels.

Manik Maurya, Independent Researcher, Kanpur, India.

What this does
--------------
Wrong answers on a multiple-choice question reveal something about how the
student is thinking, not just that they got it wrong. This tool sorts each
distractor into one of four cognitive error types:

  RF   Recall Failure     (no memory trace; random or implausible answer)
  PK   Partial Knowledge  (almost right; correct direction, incomplete model)
  CF   Confabulation      (confident wrong belief; coherent misconception)
  INT  Interference       (correct answer for a different topic)

A human researcher and an AI independently label each distractor. Cohen's
kappa measures their agreement. The research target is kappa >= 0.70.

Usage
-----
  confusion-mapper                  interactive classification session
  confusion-mapper kappa data.csv   compute Cohen's kappa on a CSV
  python -m confusion_mapper        same as the installed command

  To turn on the AI rater:
    export OPENAI_API_KEY="your-key-here"   (Mac / Linux)
    set OPENAI_API_KEY=your-key-here        (Windows)

Research context
----------------
This tool is the pre-data-collection reliability check for a preregistered
three-arm RCT (n=90) in government junior high schools in Kanpur Dehat,
Uttar Pradesh. The study tests whether labelling the cognitive type of a
student error improves two-week delayed retention compared with
correctness-only adaptive feedback.

Confusion Fingerprint Index (CFI):
  CFI-CF  = CF errors / total errors        (primary predictor)
  CFI-INT = INT errors / (INT + RF errors)  (secondary predictor)
  CFI-RF  = RF errors / total errors        (weak / null predictor)

Cohen's kappa:  kappa = (Po - Pe) / (1 - Pe)
  Po = observed proportion of agreement
  Pe = agreement expected by chance

Requirements
------------
  Python 3.9 or higher
  tkinter (part of the standard library on most systems)
  openai  (optional; pip install openai; needed for the AI rater)

Package layout (since v2.6.0)
------------------------------
This used to be a single ~2,000-line confusion_mapper.py. As of v2.6.0 it is
a package, split by concern:

  taxonomy.py       constants + the CFI taxonomy dict
  question_bank.py  the built-in NCERT-style question bank
  stats.py          Cohen's kappa, Fleiss' kappa, Krippendorff's alpha,
                     Gwet's AC1, etc.
  validation.py     dataset validation (missing labels, duplicate IDs,
                     impossible values, empty distractor_text)
  multirater.py     3+ human coder workflow: agreement matrix, panel
                     Fleiss' kappa, conflict detection, majority vote
  export.py         R / SPSS / JASP export packages
  evidence.py       post-hoc evidence panel: notes + append-only revision
                     log, layered on top of sessions without mutating them
  codebook.py       publication-ready research appendix from the taxonomy
  embeddings.py     dual-backend embeddings + persistent semantic-search
                     index + single-linkage clustering
  discovery.py      human-in-the-loop candidate-category proposals from
                     low-purity clusters (never writes to any taxonomy)
  patterns.py       co-occurrence, transition matrices, temporal trend,
                     cohort comparison, pattern mining across
                     longitudinal / multi-item coded data
  publication.py    methods paragraph, tables, and SVG figures --
                     mechanical formatting of already-computed stats,
                     never inventing a number or a judgment call
  assist.py         AI-suggest/human-approves workflow (separate from the
                     blind reliability-check path; never produces a kappa)
  itembank.py       CFI-labelled MCQ item generator with a deterministic
                     template backend and an optional OpenAI backend
  alttest.py        the Alternative Annotator Test (Calderon, Reichart and
                     Dror, ACL 2025): can the AI replace a human coder?
                     Plus judge comparison, a power simulator, a bootstrap
                     robustness check and a preregistration lock
  ai.py             the ChatGPT rater (classification + question generation)
  storage.py        session load/save (JSON)
  gui.py            the tkinter results dashboard
  console.py        the interactive console session flow
  cli.py            the stats-subcommand router, main(), and run()

Every name below was importable directly from `confusion_mapper` before the
split (e.g. `from confusion_mapper import compute_cohens_kappa`); all of it
still is. No statistical formula, no CLI behavior a user could previously
reach, and no on-disk session format changed. See CHANGELOG.md for the one
behavior that *was* fixed: the installed `confusion-mapper` console command
now correctly reaches the `kappa/alpha/diagnostics/plan/refine` subcommands
(previously only `python confusion_mapper.py kappa ...` did).
"""

try:
    from importlib.metadata import version as _installed_version, PackageNotFoundError as _PkgNotFoundError
    __version__ = _installed_version("confusion-mapper")
except Exception:
    # Not installed via pip (e.g. running straight from a source checkout) --
    # fall back to a literal rather than raising on import.
    __version__ = "2.9.0"

from .taxonomy import APP_VERSION, DATA_FILE, ERROR_TYPES, TAXONOMY
from .question_bank import BUILTIN_QUESTIONS

from .stats import (
    compute_cohens_kappa,
    bootstrap_kappa_ci,
    load_taxonomy_from_json,
    build_confusion_matrix,
    get_per_type_stats,
    compute_kappa_diagnostics,
    gwet_ac1,
    krippendorff_alpha,
    recommend_sample_size,
    suggest_prompt_refinements,
    fleiss_kappa,
)

from .ai import OPENAI_AVAILABLE, OpenAI, classify_with_ai, generate_ai_questions

from .storage import load_sessions, save_session

from .validation import validate_dataset

from .multirater import (
    load_multirater_csv,
    pairwise_agreement_matrix,
    panel_fleiss_kappa,
    detect_conflicts,
    consensus_report,
)

from .export import export_for_r, export_for_spss, export_for_jasp, export_all

from .evidence import (
    build_evidence_panel,
    add_note,
    revise_label,
    current_label,
    get_revision_history,
    get_notes,
    full_panel_report,
    load_evidence_log,
    save_evidence_log,
)

from .codebook import generate_codebook, write_codebook

from .embeddings import (
    embed_text,
    cosine_similarity,
    create_index,
    add_to_index,
    remove_from_index,
    search as embedding_search,
    find_similar,
    index_stats,
    load_index,
    save_index,
    cluster_index,
)

from .discovery import label_purity, propose_candidate_categories, format_proposal_report

from .patterns import (
    load_longitudinal_csv,
    chi_square_test,
    co_occurrence_summary,
    item_pair_cooccurrence,
    transition_matrix,
    mine_transition_patterns,
    temporal_trend,
    cohort_comparison,
)

from .publication import (
    generate_methods_paragraph,
    generate_reliability_table,
    generate_frequency_table,
    generate_confusion_matrix_svg,
    generate_frequency_bar_chart_svg,
    assemble_results_appendix,
)

from .assist import (
    RELIABILITY_WARNING,
    load_assist_csv,
    classify_with_confidence,
    run_assist_session,
)

from .gui import (
    TKINTER_AVAILABLE,
    tk,
    show_results_window,
    _draw_kappa_gauge,
    _draw_confusion_matrix,
    _draw_bar_chart,
)

from .console import (
    print_header,
    print_taxonomy_card,
    get_choice,
    run_session,
    print_summary,
    view_past_sessions,
)

from .itembank import (
    TEMPLATES as ITEMBANK_TEMPLATES,
    generate_item,
    generate_bank,
    generate_bank_with_ai,
    save_bank,
    load_bank,
)

from .alttest import (
    alt_test,
    compare_judges,
    human_agreement_summary,
    load_alttest_csv,
    simulate_alt_test_power,
    generate_synthetic_panel,
    format_alttest_report,
    format_comparison_report,
    EPSILON_PRESETS,
    bootstrap_alt_test,
    create_prereg,
    save_prereg,
    load_prereg,
    check_against_prereg,
)

from .cli import cli, main, run

__all__ = [
    "__version__",
    "APP_VERSION", "DATA_FILE", "ERROR_TYPES", "TAXONOMY", "BUILTIN_QUESTIONS",
    "OPENAI_AVAILABLE", "OpenAI",
    "TKINTER_AVAILABLE", "tk",
    "compute_cohens_kappa", "bootstrap_kappa_ci", "load_taxonomy_from_json",
    "build_confusion_matrix", "get_per_type_stats", "compute_kappa_diagnostics",
    "gwet_ac1",
    "krippendorff_alpha", "recommend_sample_size", "suggest_prompt_refinements",
    "fleiss_kappa",
    "classify_with_ai", "generate_ai_questions",
    "load_sessions", "save_session",
    "validate_dataset",
    "load_multirater_csv", "pairwise_agreement_matrix", "panel_fleiss_kappa",
    "detect_conflicts", "consensus_report",
    "export_for_r", "export_for_spss", "export_for_jasp", "export_all",
    "build_evidence_panel", "add_note", "revise_label", "current_label",
    "get_revision_history", "get_notes", "full_panel_report",
    "load_evidence_log", "save_evidence_log",
    "generate_codebook", "write_codebook",
    "embed_text", "cosine_similarity", "create_index", "add_to_index",
    "remove_from_index", "embedding_search", "find_similar", "index_stats",
    "load_index", "save_index", "cluster_index",
    "label_purity", "propose_candidate_categories", "format_proposal_report",
    "load_longitudinal_csv", "chi_square_test", "co_occurrence_summary",
    "item_pair_cooccurrence", "transition_matrix", "mine_transition_patterns",
    "temporal_trend", "cohort_comparison",
    "generate_methods_paragraph", "generate_reliability_table",
    "generate_frequency_table", "generate_confusion_matrix_svg",
    "generate_frequency_bar_chart_svg", "assemble_results_appendix",
    "RELIABILITY_WARNING", "load_assist_csv", "classify_with_confidence",
    "run_assist_session",
    "show_results_window", "_draw_kappa_gauge", "_draw_confusion_matrix", "_draw_bar_chart",
    "print_header", "print_taxonomy_card", "get_choice", "run_session",
    "print_summary", "view_past_sessions",
    "ITEMBANK_TEMPLATES", "generate_item", "generate_bank",
    "generate_bank_with_ai", "save_bank", "load_bank",
    "alt_test", "compare_judges", "human_agreement_summary", "load_alttest_csv",
    "simulate_alt_test_power", "generate_synthetic_panel",
    "format_alttest_report", "format_comparison_report", "EPSILON_PRESETS",
    "bootstrap_alt_test", "create_prereg", "save_prereg", "load_prereg",
    "check_against_prereg",
    "cli", "main", "run",
]
