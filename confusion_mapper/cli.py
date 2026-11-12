"""
The command-line entry point. Every subcommand routes through run()
below. The subcommands are, in the order I usually reach for them:

    quickstart, kappa, diagnostics, alpha, multirater, alt-test-prereg,
    alt-test, alt-test-plan, refine, export, validate, embed-index, embed-search,
    assist, evidence, codebook, patterns, publication, discovery,
    generate-bank

Argument parsing is done by hand (argparse) not click, because I did
not want a third-party CLI framework in the dependency list.
"""

import os

from .taxonomy import DATA_FILE, TAXONOMY
from .question_bank import BUILTIN_QUESTIONS
from .stats import (
    compute_cohens_kappa,
    bootstrap_kappa_ci,
    krippendorff_alpha,
    compute_kappa_diagnostics,
    gwet_ac1,
    recommend_sample_size,
    suggest_prompt_refinements,
    load_taxonomy_from_json,
    build_confusion_matrix,
    get_per_type_stats,
)
from .ai import generate_ai_questions
from .storage import save_session
from .gui import show_results_window
from .validation import validate_dataset
from .multirater import load_multirater_csv, consensus_report
from .export import export_all
from .evidence import (full_panel_report, add_note, revise_label, current_label,
                       load_evidence_log, save_evidence_log)
from .codebook import generate_codebook
from .embeddings import (
    create_index, add_to_index, search as embedding_search,
    index_stats, load_index, save_index, cluster_index,
)
from .discovery import propose_candidate_categories, format_proposal_report
from .patterns import (
    load_longitudinal_csv, co_occurrence_summary, item_pair_cooccurrence,
    transition_matrix, mine_transition_patterns, temporal_trend, cohort_comparison,
)
from .publication import assemble_results_appendix
from .assist import load_assist_csv, run_assist_session, save_assist_session
from .console import (
    print_header,
    print_taxonomy_card,
    get_choice,
    run_session,
    print_summary,
    view_past_sessions,
)

_STATS_SUBCOMMANDS = {"kappa", "alpha", "diagnostics", "plan", "refine",
                      "validate", "multirater", "export", "evidence", "codebook",
                      "embed-index", "embed-search", "discover", "patterns", "publication",
                      "quickstart", "generate-bank", "alt-test", "alt-test-plan",
                      "alt-test-prereg"}


def cli(argv=None):
    """Minimal Unix-style subcommand router. Run as `python -m confusion_mapper ...`."""
    import argparse
    import csv
    import json as _json
    import sys

    parser = argparse.ArgumentParser(
        prog="confusion-mapper",
        description=("Compute inter-rater reliability statistics on paired labels. "
                     "Subcommands: kappa, alpha, diagnostics, plan, refine, validate, "
                     "multirater, alt-test, alt-test-plan, alt-test-prereg, export, "
                     "evidence, codebook, "
                     "embed-index, embed-search, discover, patterns, publication, "
                     "generate-bank, quickstart."))
    sub = parser.add_subparsers(dest="cmd", required=False)

    def _add_csv(sp, strict=True):
        sp.add_argument("csv_path", help="CSV with columns human_label, ai_label")
        sp.add_argument("--categories", default=None,
                        help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
        if strict:
            sp.add_argument("--strict", action="store_true",
                            help="abort with a validation report instead of computing, "
                                 "if the CSV has any validation errors")

    p_k = sub.add_parser("kappa", help="Cohen's kappa (optionally weighted)")
    _add_csv(p_k)
    p_k.add_argument("--weights", choices=["nominal", "linear", "quadratic"], default="nominal")
    p_k.add_argument("--bootstrap", type=int, default=0,
                     help="bootstrap N resamples for a 95%% CI (0 to skip)")
    p_k.add_argument("--seed", type=int, default=20260623)

    p_a = sub.add_parser("alpha", help="Krippendorff's alpha")
    _add_csv(p_a)
    p_a.add_argument("--level", choices=["nominal", "ordinal", "interval"], default="nominal")

    p_d = sub.add_parser("diagnostics", help="PABAK + bias/prevalence + Gwet's AC1")
    _add_csv(p_d)

    p_p = sub.add_parser("plan", help="Sample-size estimator for a target kappa CI half-width")
    p_p.add_argument("--kappa", type=float, required=True, help="expected kappa, e.g. 0.80")
    p_p.add_argument("--ci", type=float, default=0.10, help="target CI half-width")
    p_p.add_argument("--categories", type=int, default=4, help="number of categories")

    p_r = sub.add_parser("refine", help="Generate prompt-refinement suggestions")
    _add_csv(p_r)
    p_r.add_argument("--top", type=int, default=3, help="number of top confusions to address")

    p_v = sub.add_parser("validate", help="Check a CSV for missing labels, duplicate IDs, "
                                           "impossible values, and empty distractor_text")
    _add_csv(p_v, strict=False)

    p_m = sub.add_parser("multirater", help="3+ human coder workflow: agreement matrix, "
                                             "panel Fleiss' kappa, conflict detection")
    p_m.add_argument("csv_path", help="wide-format CSV: item_id column + one column per rater")
    p_m.add_argument("--categories", default=None,
                     help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
    p_m.add_argument("--conflicts-only", action="store_true",
                     help="print just the conflict list, not the full report")

    p_e = sub.add_parser("export", help="Write R / SPSS / JASP-ready export packages")
    p_e.add_argument("csv_path", help="CSV with columns human_label, ai_label (item_id, "
                                       "distractor_text optional)")
    p_e.add_argument("--out", default="export", help="output directory (created if missing)")
    p_e.add_argument("--stem", default="confusion_mapper_export", help="base filename, no extension")
    p_e.add_argument("--formats", default="r,spss,jasp",
                     help="comma-separated subset of: r,spss,jasp")
    p_e.add_argument("--categories", default=None,
                     help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
    p_e.add_argument("--taxonomy-file", default=None,
                     help="a custom taxonomy JSON (see stats.load_taxonomy_from_json / "
                          "sample_data/item_bank_distractor_taxonomy.json), category names "
                          "in the R/SPSS/JASP output come from this instead of the built-in "
                          "CFI taxonomy. Implies --categories from the file unless overridden.")

    p_ev = sub.add_parser("evidence", help="Post-hoc evidence panel: notes + append-only "
                                            "revision log on a saved session (never edits "
                                            "the session file itself)")
    p_ev.add_argument("action", choices=["panel", "note", "revise"])
    p_ev.add_argument("session_path", help="path to the session data file (JSON; a list of "
                                            "sessions or a single session dict, either works)")
    p_ev.add_argument("distractor_id", nargs="?", default=None,
                      help="required for 'note' and 'revise', e.g. Q1_D2")
    p_ev.add_argument("text", nargs="?", default=None,
                      help="note text (for 'note') or the new label (for 'revise')")
    p_ev.add_argument("--reason", default=None, help="required for 'revise'")
    p_ev.add_argument("--author", default=None)
    p_ev.add_argument("--evidence-log", default="confusion_mapper_evidence.json",
                      help="path to the evidence log JSON (created if missing)")
    p_ev.add_argument("--session-index", type=int, default=-1,
                      help="which session to use if session_path holds a list "
                           "(default -1 = most recent)")

    p_cb = sub.add_parser("codebook", help="Generate a Markdown research appendix "
                                           "(category definitions + examples) from the taxonomy")
    p_cb.add_argument("--out", default=None, help="write to this file instead of stdout")
    p_cb.add_argument("--categories", default=None,
                      help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
    p_cb.add_argument("--taxonomy-file", default=None,
                      help="a custom taxonomy JSON, generates a real codebook (names, "
                           "definitions, examples) for that taxonomy instead of the built-in "
                           "CFI one. Implies --categories from the file unless overridden.")
    p_cb.add_argument("--title", default="CFI Coding Manual")
    p_cb.add_argument("--no-metadata", action="store_true",
                      help="omit the generation-date/version/fingerprint header")

    p_ei = sub.add_parser("embed-index", help="Build/update a persistent local semantic-search "
                                               "index from a CSV (never called automatically, "
                                               "always an explicit action)")
    p_ei.add_argument("csv_path", help="CSV with an id column and a text column to index")
    p_ei.add_argument("--index", default="confusion_mapper_embeddings.json",
                      help="index file to build/update (created fresh if missing)")
    p_ei.add_argument("--id-column", default="item_id")
    p_ei.add_argument("--text-column", default="distractor_text")
    p_ei.add_argument("--label-column", default=None,
                      help="optional column to store as metadata (e.g. human_label), "
                           "shown alongside search/find-similar results")
    p_ei.add_argument("--backend", choices=["local", "openai"], default="local",
                      help="only used when creating a brand-new index; an existing "
                           "index keeps whatever backend it was created with")

    p_es = sub.add_parser("embed-search", help="Semantic search over a persistent index")
    p_es.add_argument("query", help="search text")
    p_es.add_argument("--index", default="confusion_mapper_embeddings.json")
    p_es.add_argument("--k", type=int, default=5)

    p_disc = sub.add_parser("discover", help="Propose candidate misconception categories "
                                              "from low-purity clusters (never writes to "
                                              "any taxonomy, proposal only)")
    p_disc.add_argument("index_path", help="a persistent embeddings index built with "
                                            "--label-column set (see embed-index)")
    p_disc.add_argument("--label-key", default="human_label",
                        help="metadata key holding each item's existing label")
    p_disc.add_argument("--threshold", type=float, default=0.5, help="clustering similarity threshold")
    p_disc.add_argument("--min-cluster-size", type=int, default=3)
    p_disc.add_argument("--max-purity", type=float, default=0.6,
                        help="flag clusters at or below this label purity")
    p_disc.add_argument("--out", default=None, help="write Markdown report to this file instead of stdout")

    p_pat = sub.add_parser("patterns", help="Pattern mining over longitudinal/multi-item coded data")
    p_pat.add_argument("action", choices=["cooccurrence", "item-pair", "transitions",
                                          "pathways", "trend", "cohorts"])
    p_pat.add_argument("csv_path", help="a longitudinal CSV: respondent_id, item_id, label, "
                                        "timepoint, cohort (see patterns.load_longitudinal_csv)")
    p_pat.add_argument("--categories", default=None,
                       help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
    p_pat.add_argument("--item-id", default=None, help="restrict to one item (transitions/pathways)")
    p_pat.add_argument("--item1", default=None, help="required for item-pair")
    p_pat.add_argument("--item2", default=None, help="required for item-pair")
    p_pat.add_argument("--timepoint-order", default=None,
                       help="comma-separated chronological order, e.g. pretest,week2,posttest "
                            "(transitions/pathways/trend, without it timepoints sort "
                            "alphabetically, rarely what you want)")
    p_pat.add_argument("--sequence-length", type=int, default=2, help="for pathways")
    p_pat.add_argument("--top-k", type=int, default=10, help="for pathways")
    p_pat.add_argument("--cohorts", default=None, help="comma-separated cohort subset (for cohorts)")

    p_pub = sub.add_parser("publication", help="Generate a Results appendix (methods paragraph, "
                                                "tables, SVG figures) from a human_label/ai_label CSV")
    p_pub.add_argument("csv_path", help="CSV with columns human_label, ai_label")
    p_pub.add_argument("--categories", default=None,
                       help="comma-separated list, e.g. RF,PK,CF,INT (defaults to built-in)")
    p_pub.add_argument("--taxonomy-file", default=None, help="a custom taxonomy JSON")
    p_pub.add_argument("--bootstrap", type=int, default=0,
                       help="bootstrap N resamples for a 95%% CI in the methods paragraph (0 to skip)")
    p_pub.add_argument("--seed", type=int, default=20260623)
    p_pub.add_argument("--out", default=None, help="write to this file instead of stdout")

    p_at = sub.add_parser("alt-test", help="Can the AI replace a human coder? The Alternative "
                                            "Annotator Test (Calderon, Reichart and Dror, ACL 2025)")
    p_at.add_argument("csv_path", help="wide CSV: item_id, one column per human coder (3+ "
                                        "recommended), plus the AI column(s). Blank cell = not labelled.")
    p_at.add_argument("--ai-column", action="append", default=None,
                      help="column holding the AI's labels. Repeat it to compare several "
                           "AI judges or prompts against the same coders. Can come from "
                           "--prereg instead.")
    p_at.add_argument("--id-column", default="item_id")
    p_at.add_argument("--human-columns", default=None,
                      help="comma-separated human coder columns (default: every other column)")
    p_at_eps = p_at.add_mutually_exclusive_group()
    p_at_eps.add_argument("--epsilon", type=float,
                          help="cost-benefit allowance, decide it before you look at results")
    p_at_eps.add_argument("--annotators", choices=["expert", "skilled", "crowd"],
                          help="use the authors' preset: expert 0.2, skilled 0.15, crowd 0.1")
    p_at.add_argument("--scoring", choices=["accuracy", "neg_rmse"], default=None,
                      help="accuracy for categories (default), neg_rmse for numeric ratings")
    p_at.add_argument("--q", type=float, default=None,
                      help="FDR level for Benjamini-Yekutieli (default 0.05)")
    p_at.add_argument("--min-items", type=int, default=None,
                      help="skip coders with fewer usable items than this (default 30)")
    p_at.add_argument("--pass-threshold", type=float, default=None,
                      help="winning rate needed to pass (default 0.5, the authors' rule)")
    p_at.add_argument("--prereg", default=None,
                      help="a plan file from alt-test-prereg. Settings come from the plan, "
                           "and any difference from it stops the run.")
    p_at.add_argument("--allow-deviation", action="store_true",
                      help="run anyway when the settings differ from --prereg. Every "
                           "deviation is listed in the output and the report.")
    p_at.add_argument("--bootstrap", type=int, default=0,
                      help="rerun the test on N bootstrap resamples of the items to see "
                           "how fragile the verdict is (0 to skip, 1000 is a good number)")
    p_at.add_argument("--seed", type=int, default=20260623, help="seed for --bootstrap")
    p_at.add_argument("--report", default=None, help="also write a Markdown report to this file")

    p_pr = sub.add_parser("alt-test-prereg", help="Lock your alt-test settings before any data "
                                                   "exists, and get a hash for your preregistration")
    p_pr_eps = p_pr.add_mutually_exclusive_group(required=True)
    p_pr_eps.add_argument("--epsilon", type=float)
    p_pr_eps.add_argument("--annotators", choices=["expert", "skilled", "crowd"])
    p_pr.add_argument("--scoring", choices=["accuracy", "neg_rmse"], default="accuracy")
    p_pr.add_argument("--q", type=float, default=0.05)
    p_pr.add_argument("--min-items", type=int, default=30)
    p_pr.add_argument("--pass-threshold", type=float, default=0.5)
    p_pr.add_argument("--ai-column", action="append", default=None,
                      help="the AI column name(s) you will use; repeat for several")
    p_pr.add_argument("--human-columns", default=None,
                      help="comma-separated human coder column names you will use")
    p_pr.add_argument("--planned-items", type=int, default=None)
    p_pr.add_argument("--notes", default="", help="free text, not covered by the hash")
    p_pr.add_argument("--out", required=True, help="where to write the plan (JSON)")

    p_atp = sub.add_parser("alt-test-plan", help="Simulate how many items you need to label "
                                                  "before running the alt-test")
    p_atp_eps = p_atp.add_mutually_exclusive_group(required=True)
    p_atp_eps.add_argument("--epsilon", type=float)
    p_atp_eps.add_argument("--annotators", choices=["expert", "skilled", "crowd"])
    p_atp.add_argument("--coders", type=int, default=3, help="number of human coders")
    p_atp.add_argument("--categories", type=int, default=4, help="number of label categories")
    p_atp.add_argument("--coder-noise", type=float, default=0.3,
                       help="0 = perfect coder, 1 = pure guessing (0.3 is roughly kappa 0.5)")
    p_atp.add_argument("--ai-noise", type=float, default=0.3, help="same scale, for the AI")
    p_atp.add_argument("--sizes", default="30,50,75,100,150,200",
                       help="comma-separated item counts to simulate, each at least 30")
    p_atp.add_argument("--simulations", type=int, default=200)
    p_atp.add_argument("--target-power", type=float, default=0.8)
    p_atp.add_argument("--seed", type=int, default=20260623)

    p_gb = sub.add_parser("generate-bank", help="Generate a bank of CFI-labelled MCQ items "
                                                  "from deterministic templates or an AI backend")
    p_gb.add_argument("n", type=int, nargs="?", default=None,
                      help="how many items to generate (not needed with --list-templates)")
    p_gb.add_argument("--out", default=None,
                      help="write to this JSON file instead of stdout")
    p_gb.add_argument("--backend", choices=["templates", "ai"], default="templates",
                      help="templates is deterministic and offline; ai calls OpenAI")
    p_gb.add_argument("--templates", default=None,
                      help="comma-separated subset of template keys "
                           "(default = all). Use --list-templates to see them.")
    p_gb.add_argument("--list-templates", action="store_true",
                      help="print the registered templates and exit")
    p_gb.add_argument("--topic", default="basic arithmetic",
                      help="topic hint for the AI backend")
    p_gb.add_argument("--class-level", type=int, default=8,
                      help="class-level hint for the AI backend")
    p_gb.add_argument("--seed", type=int, default=None,
                      help="RNG seed for the templates backend (reproducible bank)")

    sub.add_parser("quickstart", help="A guided, non-interactive walkthrough of the core "
                                       "workflow on built-in demo data, start here")

    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 0

    def _load(path, cats_csv, strict=False):
        cats = cats_csv.split(",") if cats_csv else None
        rows = []
        with open(path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        h = [row["human_label"] for row in rows]
        a = [row["ai_label"] for row in rows]

        report = validate_dataset(rows, categories=cats)
        if not report["valid"]:
            if strict:
                sys.stderr.write(
                    f"\n[error] {path}: {len(report['errors'])} validation error(s), "
                    f"aborting (--strict). Run `confusion-mapper validate {path}` "
                    f"for the full report.\n\n"
                )
                for e in report["errors"]:
                    sys.stderr.write(f"  row {e['row']} ({e['item_id']}): {e['issue']}\n")
                sys.stderr.write("\n")
                sys.exit(1)
            else:
                sys.stderr.write(
                    f"[warning] {path}: {len(report['errors'])} validation error(s) found "
                    f"and included in this computation anyway. Run "
                    f"`confusion-mapper validate {path}` for details, or add "
                    f"--strict to abort instead.\n"
                )
        return h, a, cats

    if args.cmd == "kappa":
        h, a, cats = _load(args.csv_path, args.categories, strict=args.strict)
        r = compute_cohens_kappa(h, a, weights=args.weights, categories=cats)
        if args.bootstrap > 0:
            ci = bootstrap_kappa_ci(h, a, n_resamples=args.bootstrap, method="bca",
                                    weights=args.weights, categories=cats, seed=args.seed)
            r["ci_95_bca"] = {"lower": ci["ci_lower"], "upper": ci["ci_upper"],
                              "n_resamples": ci["n_resamples"], "seed": args.seed}
        print(_json.dumps(r, indent=2, sort_keys=False))
        return 0

    if args.cmd == "alpha":
        h, a, cats = _load(args.csv_path, args.categories, strict=args.strict)
        print(_json.dumps(krippendorff_alpha(h, a, level=args.level, categories=cats), indent=2))
        return 0

    if args.cmd == "diagnostics":
        h, a, cats = _load(args.csv_path, args.categories, strict=args.strict)
        d = compute_kappa_diagnostics(h, a, categories=cats)
        g = gwet_ac1(h, a, categories=cats)
        d["ac1"] = g["ac1"]
        d["ac1_interpretation"] = g["interpretation"]
        print(_json.dumps(d, indent=2))
        return 0

    if args.cmd == "plan":
        r = recommend_sample_size(args.kappa, ci_half_width=args.ci, n_categories=args.categories)
        print(_json.dumps(r, indent=2))
        return 0

    if args.cmd == "validate":
        cats = args.categories.split(",") if args.categories else None
        with open(args.csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        report = validate_dataset(rows, categories=cats)
        print(_json.dumps(report, indent=2))
        return 0 if report["valid"] else 1

    if args.cmd == "multirater":
        cats = args.categories.split(",") if args.categories else None
        item_ids, rater_names, ratings = load_multirater_csv(args.csv_path)
        report = consensus_report(item_ids, ratings, rater_names, categories=cats)
        if args.conflicts_only:
            print(_json.dumps({"n_conflicts": report["n_conflicts"],
                               "conflicts": report["conflicts"]}, indent=2))
        else:
            print(_json.dumps(report, indent=2))
        return 0

    if args.cmd == "export":
        taxonomy = None
        cats = args.categories.split(",") if args.categories else None
        if args.taxonomy_file:
            file_cats, taxonomy = load_taxonomy_from_json(args.taxonomy_file)
            if cats is None:
                cats = file_cats
        formats = tuple(f.strip() for f in args.formats.split(",") if f.strip())
        with open(args.csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        result = export_all(rows, args.out, stem=args.stem, categories=cats,
                            taxonomy=taxonomy, formats=formats)
        written = []
        for fmt, files in result.items():
            if files:
                written.extend(files.values())
        for path in written:
            sys.stderr.write(f"wrote {path}\n")
        print(_json.dumps(result, indent=2))
        return 0

    if args.cmd == "evidence":
        with open(args.session_path, encoding="utf-8") as f:
            loaded = _json.load(f)
        if isinstance(loaded, list):
            if not loaded:
                sys.stderr.write(f"{args.session_path} contains an empty session list\n")
                return 1
            session = loaded[args.session_index]
        else:
            session = loaded

        log = load_evidence_log(args.evidence_log)

        if args.action == "panel":
            print(_json.dumps(full_panel_report(session, log), indent=2))
            return 0

        if args.distractor_id is None:
            sys.stderr.write(f"'{args.action}' requires a distractor_id, e.g. Q1_D2\n")
            return 1

        if args.action == "note":
            if not args.text:
                sys.stderr.write("'note' requires note text as the next argument\n")
                return 1
            add_note(log, args.distractor_id, args.text, author=args.author)
            save_evidence_log(log, args.evidence_log)
            sys.stderr.write(f"noted {args.distractor_id} -> {args.evidence_log}\n")
            return 0

        if args.action == "revise":
            if not args.text:
                sys.stderr.write("'revise' requires the new label as the next argument\n")
                return 1
            if not args.reason:
                sys.stderr.write("'revise' requires --reason\n")
                return 1
            prior = current_label(log, session, args.distractor_id)
            revise_label(log, args.distractor_id, args.text, args.reason,
                        author=args.author, old_label=prior)
            save_evidence_log(log, args.evidence_log)
            sys.stderr.write(f"revised {args.distractor_id}: {prior} -> {args.text} "
                             f"in {args.evidence_log}\n")
            return 0

    if args.cmd == "codebook":
        taxonomy = None
        cats = args.categories.split(",") if args.categories else None
        title = args.title
        if args.taxonomy_file:
            file_cats, taxonomy = load_taxonomy_from_json(args.taxonomy_file)
            if cats is None:
                cats = file_cats
            if title == "CFI Coding Manual":  # user didn't override the default
                title = "Coding Manual"
        text = generate_codebook(categories=cats, taxonomy=taxonomy, title=title,
                                 include_metadata=not args.no_metadata)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(text)
            sys.stderr.write(f"wrote {args.out}\n")
        else:
            print(text)
        return 0

    if args.cmd == "embed-index":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        index = load_index(args.index, default_backend=args.backend)
        with open(args.csv_path, newline="", encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        for i, row in enumerate(rows):
            item_id = (row.get(args.id_column) or "").strip() or f"row_{i}"
            text = row.get(args.text_column, "")
            metadata = {args.label_column: row[args.label_column]} if (
                args.label_column and args.label_column in row) else {}
            add_to_index(index, item_id, text, metadata=metadata, api_key=api_key)
        save_index(index, args.index)
        stats = index_stats(index)
        stats["n_rows_in_csv"] = len(rows)
        sys.stderr.write(f"wrote {args.index}\n")
        print(_json.dumps(stats, indent=2))
        return 0

    if args.cmd == "embed-search":
        api_key = os.environ.get("OPENAI_API_KEY", "").strip()
        index = load_index(args.index)
        results = embedding_search(index, args.query, k=args.k, api_key=api_key)
        print(_json.dumps(results, indent=2))
        return 0

    if args.cmd == "discover":
        index = load_index(args.index_path)
        candidates = propose_candidate_categories(
            index, label_key=args.label_key, threshold=args.threshold,
            min_cluster_size=args.min_cluster_size, max_purity=args.max_purity)
        report = format_proposal_report(candidates, label_key=args.label_key)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(report)
            sys.stderr.write(f"wrote {args.out}\n")
        else:
            print(report)
        return 0

    if args.cmd == "patterns":
        cats = args.categories.split(",") if args.categories else None
        tp_order = args.timepoint_order.split(",") if args.timepoint_order else None
        records = load_longitudinal_csv(args.csv_path)

        if args.action == "cooccurrence":
            result = co_occurrence_summary(records, categories=cats)
        elif args.action == "item-pair":
            if not args.item1 or not args.item2:
                sys.stderr.write("'item-pair' requires --item1 and --item2\n")
                return 1
            result = item_pair_cooccurrence(records, args.item1, args.item2, categories=cats)
        elif args.action == "transitions":
            result = transition_matrix(records, item_id=args.item_id, categories=cats,
                                       timepoint_order=tp_order)
        elif args.action == "pathways":
            result = mine_transition_patterns(records, item_id=args.item_id, categories=cats,
                                              timepoint_order=tp_order,
                                              sequence_length=args.sequence_length, top_k=args.top_k)
        elif args.action == "trend":
            result = temporal_trend(records, categories=cats, timepoint_order=tp_order)
        elif args.action == "cohorts":
            cohorts = args.cohorts.split(",") if args.cohorts else None
            result = cohort_comparison(records, categories=cats, cohorts=cohorts)
        print(_json.dumps(result, indent=2))
        return 0

    if args.cmd == "publication":
        taxonomy = None
        cats = args.categories.split(",") if args.categories else None
        if args.taxonomy_file:
            file_cats, taxonomy = load_taxonomy_from_json(args.taxonomy_file)
            if cats is None:
                cats = file_cats
        h, a, cats = _load(args.csv_path, ",".join(cats) if cats else None)

        kappa_r = compute_cohens_kappa(h, a, categories=cats)
        ac1_r = gwet_ac1(h, a, categories=cats)
        alpha_r = krippendorff_alpha(h, a, categories=cats)
        matrix = build_confusion_matrix(h, a, categories=cats)
        type_stats = get_per_type_stats(h, a, categories=cats)

        ci_r = None
        if args.bootstrap > 0:
            ci = bootstrap_kappa_ci(h, a, n_resamples=args.bootstrap, method="bca",
                                    categories=cats, seed=args.seed)
            ci_r = {"lower": ci["ci_lower"], "upper": ci["ci_upper"]}

        doc = assemble_results_appendix(kappa_r, type_stats, matrix, categories=cats,
                                        taxonomy=taxonomy, ac1_result=ac1_r,
                                        alpha_result=alpha_r, ci_result=ci_r)
        if args.out:
            with open(args.out, "w", encoding="utf-8") as f:
                f.write(doc)
            sys.stderr.write(f"wrote {args.out}\n")
        else:
            print(doc)
        return 0

    if args.cmd in ("alt-test", "alt-test-plan", "alt-test-prereg"):
        from .alttest import (
            EPSILON_PRESETS, load_alttest_csv, alt_test, compare_judges,
            human_agreement_summary, format_alttest_report, format_comparison_report,
            simulate_alt_test_power, bootstrap_alt_test, create_prereg, save_prereg,
            load_prereg, check_against_prereg,
        )

        if args.cmd == "alt-test-prereg":
            try:
                plan = create_prereg(
                    epsilon=args.epsilon, annotators=args.annotators, q_fdr=args.q,
                    scoring=args.scoring, min_instances_per_human=args.min_items,
                    pass_threshold=args.pass_threshold, ai_columns=args.ai_column,
                    human_columns=(args.human_columns.split(",") if args.human_columns else None),
                    planned_items=args.planned_items, notes=args.notes)
            except ValueError as e:
                sys.stderr.write(f"[error] {e}\n")
                return 1
            save_prereg(plan, args.out)
            print(_json.dumps(plan, indent=2))
            sys.stderr.write(f"wrote {args.out}\nsha256: {plan['sha256']}\n"
                             "Register this file, or at least the hash, on OSF (or your "
                             "registry of choice) before anyone starts labelling.\n")
            return 0

        if args.cmd == "alt-test-plan":
            eps = args.epsilon if args.epsilon is not None else EPSILON_PRESETS[args.annotators]
            sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
            try:
                r = simulate_alt_test_power(
                    n_items_grid=sizes, n_coders=args.coders, n_categories=args.categories,
                    coder_noise=args.coder_noise, ai_noise=args.ai_noise, epsilon=eps,
                    n_simulations=args.simulations, target_power=args.target_power,
                    seed=args.seed)
            except ValueError as e:
                sys.stderr.write(f"[error] {e}\n")
                return 1
            print(_json.dumps(r, indent=2))
            return 0

        # alt-test: settings come from the command line, then the plan, then defaults
        plan = None
        if args.prereg:
            try:
                plan = load_prereg(args.prereg)
            except (OSError, ValueError) as e:
                sys.stderr.write(f"[error] {e}\n")
                return 1
        locked = plan["locked"] if plan else None

        def pick(cli_value, key, default):
            if cli_value is not None:
                return cli_value
            return locked["settings"][key] if locked else default

        if args.epsilon is not None:
            eps = args.epsilon
        elif args.annotators:
            eps = EPSILON_PRESETS[args.annotators]
        elif locked:
            eps = locked["settings"]["epsilon"]
        else:
            parser.error("alt-test needs an epsilon you chose in advance: --epsilon, "
                         "--annotators expert|skilled|crowd, or --prereg PLAN")
        settings = dict(
            epsilon=eps,
            scoring=pick(args.scoring, "scoring", "accuracy"),
            q_fdr=pick(args.q, "q_fdr", 0.05),
            min_instances_per_human=pick(args.min_items, "min_instances_per_human", 30),
            min_humans_per_instance=locked["settings"]["min_humans_per_instance"] if locked else 2,
            pass_threshold=pick(args.pass_threshold, "pass_threshold", 0.5),
        )
        ai_cols = args.ai_column or (locked["design"]["ai_columns"] if locked else None)
        if not ai_cols:
            parser.error("name the AI column(s) with --ai-column, or list them in the --prereg plan")
        if args.human_columns:
            human_cols = args.human_columns.split(",")
        else:
            human_cols = (locked["design"]["human_columns"] or None) if locked else None

        try:
            humans, llms = load_alttest_csv(args.csv_path, ai_cols,
                                            id_column=args.id_column,
                                            human_columns=human_cols)
            sys.stderr.write("human coders: " + ", ".join(humans) + "\n"
                             "AI judge(s):  " + ", ".join(llms) + "\n")

            prereg_check = None
            if plan:
                n_items = len({i for labels in humans.values() for i in labels})
                prereg_check = check_against_prereg(plan, settings, list(llms),
                                                    list(humans), n_items)
                if not prereg_check["matches"] and not args.allow_deviation:
                    sys.stderr.write("[error] this run departs from the preregistered plan:\n")
                    for d in prereg_check["deviations"]:
                        sys.stderr.write(f"  - {d}\n")
                    sys.stderr.write("Fix the command, or rerun with --allow-deviation and "
                                     "report every deviation in your paper.\n")
                    return 1

            agreement = (human_agreement_summary(humans)
                         if settings["scoring"] == "accuracy" else None)

            def robust(llm):
                if args.bootstrap <= 0:
                    return None
                return bootstrap_alt_test(llm, humans, n_resamples=args.bootstrap,
                                          seed=args.seed, **settings)

            if len(llms) == 1:
                name = next(iter(llms))
                out = alt_test(llms[name], humans, **settings)
                out["judge"] = name
                rb = robust(llms[name])
                report = format_alttest_report(out, agreement, judge_name=name,
                                               annotator_profile=args.annotators,
                                               prereg_check=prereg_check, robustness=rb)
            else:
                out = compare_judges(llms, humans, **settings)
                rb = {n: robust(llm) for n, llm in llms.items()} if args.bootstrap > 0 else None
                report = format_comparison_report(out, agreement,
                                                  annotator_profile=args.annotators,
                                                  prereg_check=prereg_check,
                                                  robustness_by_judge=rb)
        except ValueError as e:
            sys.stderr.write(f"[error] {e}\n")
            return 1
        if agreement is not None:
            out["human_agreement"] = agreement
        if prereg_check is not None:
            out["preregistration"] = prereg_check
        if rb is not None:
            out["robustness"] = rb
        print(_json.dumps(out, indent=2, default=str))
        if args.report:
            with open(args.report, "w", encoding="utf-8") as f:
                f.write(report)
            sys.stderr.write(f"wrote {args.report}\n")
        return 0

    if args.cmd == "generate-bank":
        from .itembank import (
            TEMPLATES, generate_bank, generate_bank_with_ai, save_bank,
        )
        if args.list_templates:
            for k in sorted(TEMPLATES.keys()):
                print(k)
            return 0
        if args.n is None:
            sys.stderr.write("[error] generate-bank needs the number of items to generate. "
                             "run `generate-bank --list-templates` to see the template list.\n")
            return 1
        if args.backend == "ai":
            api_key = os.environ.get("OPENAI_API_KEY", "").strip()
            if not api_key:
                sys.stderr.write(
                    "[error] the ai backend needs OPENAI_API_KEY in your "
                    "environment. run without --backend ai to use the "
                    "deterministic templates instead.\n"
                )
                return 1
            bank = generate_bank_with_ai(args.n, args.topic, args.class_level, api_key)
        else:
            template_keys = args.templates.split(",") if args.templates else None
            bank = generate_bank(args.n, templates=template_keys, seed=args.seed)
        if args.out:
            save_bank(bank, args.out)
            sys.stderr.write(f"wrote {len(bank)} items -> {args.out}\n")
        else:
            print(_json.dumps(bank, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "quickstart":
        return run_quickstart()

    if args.cmd == "refine":
        h, a, cats = _load(args.csv_path, args.categories, strict=args.strict)
        r = suggest_prompt_refinements(h, a, categories=cats, top_k=args.top)
        sys.stdout.write(r["report_markdown"])
        sys.stdout.write("\n")
        return 0

    parser.print_help()
    return 0


def main():
    print_header()

    # Check for OpenAI key
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if api_key:
        print("  OPENAI_API_KEY detected, AI rater mode enabled.")
    else:
        print("  [info] No OPENAI_API_KEY, running in Manual Mode.")
        print("    Set the environment variable to enable AI classification.")
    print()

    rater_id = input("  Enter your rater ID (e.g. your initials): ").strip()
    if not rater_id:
        rater_id = "Rater1"

    while True:
        print()
        print("─" * 66)
        print("  MAIN MENU")
        print("─" * 66)
        print("  [1] Classify, built-in NCERT question bank (15 distractors)")
        if api_key:
            print("  [2] Classify, AI-generated questions on any topic")
        print("  [3] View past sessions")
        print("  [4] Taxonomy reference card")
        print("  [Q] Quit")
        print()

        valid = ["1", "3", "4", "Q"]
        if api_key:
            valid.append("2")

        choice = get_choice("  Your choice: ", valid)

        # ── Option 1: built-in bank ──────────────────────────────────────────
        if choice == "1":
            print(f"\n  Loaded {len(BUILTIN_QUESTIONS)} questions "
                  f"({sum(len(q['distractors']) for q in BUILTIN_QUESTIONS)} distractors).")
            print("  Reference labels will be shown after each classification.")
            input("  Press Enter to begin...")

            session, kappa, matrix, type_stats = run_session(
                BUILTIN_QUESTIONS, api_key, rater_id
            )
            print_summary(kappa, type_stats, session)
            save_session(session)
            print(f"\n  Session saved -> {DATA_FILE}")
            input("  Press Enter to open the visualisation window...")
            show_results_window(kappa, matrix, type_stats, session)

        # ── Option 2: AI-generated questions ────────────────────────────────
        elif choice == "2" and api_key:
            topic = input("\n  Topic for question generation: ").strip()
            if not topic:
                topic = "Photosynthesis"

            n_str = input("  Number of questions to generate (1-5): ").strip()
            try:
                n_q = max(1, min(5, int(n_str)))
            except ValueError:
                n_q = 3

            print(f"\n  Generating {n_q} question(s) on '{topic}'...")
            questions = generate_ai_questions(topic, n_q, api_key)

            if not questions:
                print("  Generation failed, using built-in bank instead.")
                questions = BUILTIN_QUESTIONS
            else:
                total_d = sum(len(q["distractors"]) for q in questions)
                print(f"  {len(questions)} question(s) generated "
                      f"({total_d} distractors).")

            input("  Press Enter to begin classification...")

            session, kappa, matrix, type_stats = run_session(
                questions, api_key, rater_id
            )
            print_summary(kappa, type_stats, session)
            save_session(session)
            print(f"\n  Session saved -> {DATA_FILE}")
            input("  Press Enter to open the visualisation window...")
            show_results_window(kappa, matrix, type_stats, session)

        # ── Option 3: past sessions ──────────────────────────────────────────
        elif choice == "3":
            view_past_sessions()

        # ── Option 4: taxonomy card ──────────────────────────────────────────
        elif choice == "4":
            print_taxonomy_card()

        # ── Quit ──────────────────────────────────────────────────────────────
        elif choice == "Q":
            print(f"\n  All session data saved to: {DATA_FILE}")
            print("  Goodbye.\n")
            break


def _quickstart_demo_data():
    """
    A small, deterministic, self-contained demo dataset built from the
    built-in question bank's own pre-assigned error_type (its ground
    truth), not sample_data/, sample_data/ is only in the sdist via
    MANIFEST.in, not the installed wheel (pyproject.toml's `packages =
    ["confusion_mapper"]` doesn't include it), so quickstart can't depend
    on it existing on disk after `pip install confusion-mapper`.

    3 of 15 labels are deliberately flipped for "ai_label" to produce a
    realistic, non-perfect kappa (~0.72) rather than a suspiciously
    perfect demo.
    """
    flips = {3: "PK", 9: "CF", 14: "CF"}  # 1-indexed positions
    human, ai = [], []
    i = 0
    for q in BUILTIN_QUESTIONS:
        for d in q["distractors"]:
            i += 1
            human.append(d["error_type"])
            ai.append(flips.get(i, d["error_type"]))
    return human, ai


def run_quickstart():
    """
    A non-interactive, self-contained guided walkthrough: kappa ->
    diagnostics (AC1/PABAK) -> per-category breakdown -> a codebook
    snippet -> pointers to the rest of the CLI. Entirely deterministic
    (no input() calls) so it works as a demo/recording target as well as
    a genuine first-run experience.
    """
    human, ai = _quickstart_demo_data()

    print("=" * 70)
    print("  ConfusionMapper Quickstart")
    print("=" * 70)
    print("\n  Walking through the core workflow on 15 built-in demo items.")
    print("  Your own data: replace this with any CSV that has")
    print("  human_label/ai_label columns, see `confusion-mapper --help`.\n")

    print("-" * 70)
    print("  1. Cohen's kappa (human vs. AI rater)")
    print("-" * 70)
    kappa_r = compute_cohens_kappa(human, ai)
    print(f"  kappa = {kappa_r['kappa']}   n = {kappa_r['n']}   "
         f"agreements = {kappa_r['agreements']}/{kappa_r['n']}")
    print(f"  {kappa_r['interpretation']}")

    print("\n" + "-" * 70)
    print("  2. Diagnostics: is that kappa trustworthy, or a skew artifact?")
    print("-" * 70)
    diag = compute_kappa_diagnostics(human, ai)
    ac1 = gwet_ac1(human, ai)
    print(f"  PABAK = {diag['pabak']}   prevalence index = {diag['prevalence_index']}   "
         f"bias index = {diag['bias_index']}")
    print(f"  Gwet's AC1 = {ac1['ac1']} ({ac1['interpretation']})")
    print("  kappa and AC1 close together -> not a prevalence-skew artifact.")

    print("\n" + "-" * 70)
    print("  3. Per-category breakdown")
    print("-" * 70)
    type_stats = get_per_type_stats(human, ai)
    for code, s in type_stats.items():
        name = TAXONOMY.get(code, {}).get("name", code)
        print(f"  {code:4s} {name:22s} {s['agreed']}/{s['total']} agreed ({s['pct']}%)")

    print("\n" + "-" * 70)
    print("  4. Auto-generated codebook (first category shown)")
    print("-" * 70)
    codebook_text = generate_codebook(include_metadata=False)
    first_section = codebook_text.split("## Category definitions")[1].split("###")[1]
    print("  ### " + first_section.strip()[:280] + " ...")

    print("\n" + "=" * 70)
    print("  What else is here")
    print("=" * 70)
    next_steps = [
        ("Your own data",     "confusion-mapper kappa your_data.csv --bootstrap 10000"),
        ("3+ human coders",   "confusion-mapper multirater your_data.csv"),
        ("Export to R/SPSS/JASP", "confusion-mapper export your_data.csv --out results/"),
        ("AI-assisted bulk coding", "confusion-mapper assist your_data.csv"),
        ("Semantic search",   "confusion-mapper embed-index your_data.csv --index idx.json"),
        ("Pattern mining",    "confusion-mapper patterns cooccurrence longitudinal.csv"),
        ("Publication draft", "confusion-mapper publication your_data.csv --out results.md"),
    ]
    for label, cmd in next_steps:
        print(f"  {label:26s} {cmd}")
    print(f"\n  Full reference: confusion-mapper --help\n")
    return 0


def run_assist_entry(argv):
    """
    Entry point for `confusion-mapper assist ...`. Parses assist-specific
    args, prompts for a rater_id the same way main() does, then hands off
    to assist.run_assist_session().

    This function, not cli() and not main(), is what "assist" routes
    to in run() below. It is not a stats subcommand (it's interactive, and
    produces a session file, not a JSON report to stdout) and it is not
    main() (it's Copilot-style, not blind). Keeping it a third, distinct
    branch is the whole point: there's no argv path by which assist mode
    and the blind reliability-check mode could be confused for each other.
    """
    import argparse

    parser = argparse.ArgumentParser(
        prog="confusion-mapper assist",
        description="AI-suggests / human-approves bulk coding. NOT for reliability "
                    "data, see console.run_session() / plain `confusion-mapper` "
                    "for the blind reliability-check session.")
    parser.add_argument("csv_path", help="CSV of items to code (needs a distractor_text "
                                         "column at minimum; item_id, question_text, "
                                         "correct_answer, topic are optional but improve "
                                         "the AI's suggestions)")
    parser.add_argument("--index", default=None,
                        help="path to a persistent embeddings index (see `embed-index`) "
                             "to show nearest already-coded examples alongside each "
                             "suggestion. Omit to skip that part of the panel.")
    parser.add_argument("--index-k", type=int, default=5)
    parser.add_argument("--out", default=None,
                        help="where to save this session (default: append to "
                             "confusion_mapper_assist_sessions.json)")
    args = parser.parse_args(argv[1:])

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        print("  No OPENAI_API_KEY set, assist mode will run, but every "
             "'suggestion' will be unavailable and every item a manual entry. "
             "There's no assistance without a key.\n")

    rater_id = input("  Rater name/ID: ").strip() or "Anonymous"
    items = load_assist_csv(args.csv_path)
    session = run_assist_session(items, api_key, rater_id,
                                 index_path=args.index, index_k=args.index_k)

    path = save_assist_session(session) if not args.out else save_assist_session(session, path=args.out)
    print(f"\n  {session['n_items_decided']}/{session['n_items_offered']} item(s) decided. "
         f"Acceptance rate: {session['acceptance_rate']}")
    print(f"  Saved to: {path}")
    print(f"  {session['reliability_warning']}\n")
    return 0


def run(argv=None):
    """
    Single entry point for both the installed `confusion-mapper` console
    script and `python -m confusion_mapper`.

    Three-way routing, in order:
      1. argv[0] == "assist"           -> run_assist_entry() (Copilot-style,
                                          never produces reliability data)
      2. argv[0] in _STATS_SUBCOMMANDS -> cli() (JSON-output stats reports)
      3. anything else / no args       -> main() (the blind interactive
                                          reliability-check session)
    Branch 1 exists specifically so there is no argv path by which assist
    mode and the blind reliability-check session could be confused for
    each other, they are not two flags on the same command, they are two
    different subcommands that happen to share this dispatcher.
    """
    import sys as _sys

    if argv is None:
        argv = _sys.argv[1:]

    if len(argv) > 0 and argv[0] == "assist":
        return run_assist_entry(argv)

    if len(argv) > 0 and argv[0] in _STATS_SUBCOMMANDS:
        return cli(argv)

    main()
    return 0
