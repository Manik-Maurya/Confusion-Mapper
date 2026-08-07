"""
Codebook generator: render the CFI taxonomy as a publication-ready
research appendix -- category definitions and examples, formatted for a
Methods/Appendix section. The Level 2 "codebook generator" from the
roadmap this package has been built against.

New in v2.6.0. Deliberately does NOT auto-generate "decision rules" as
finished, authoritative text. TAXONOMY has definitions and examples --
real, already-written content -- but no separately-authored decision-rule
field, and synthesizing one from the definition/example text and
presenting it as equivalent would mean fabricating part of a research
instrument's methodology and handing it back as if it were reviewed
content. Every category section instead gets an explicit, clearly-marked
placeholder ("*(fill in from your coding manual / Stage 1 RR methods)*")
so a human writes the actual decision rule, and it's obvious in the output
that this one field needs attention before the appendix is submission-ready.
"""

import datetime

from .taxonomy import ERROR_TYPES, TAXONOMY, taxonomy_fingerprint
from .storage import installed_package_version


def generate_codebook(categories=None, taxonomy=None, title="CFI Coding Manual", include_metadata=True):
    """
    Render a Markdown research appendix: a summary table followed by a
    full definition/example/decision-rule section for each category.

    Args:
        categories (list[str] | None): defaults to ERROR_TYPES. Any code
            not found in `taxonomy` falls back to just the code itself, with
            "(no definition on file)" placeholders -- so this also works,
            gracefully, for a partially-documented custom taxonomy.
        taxonomy (dict | None): a taxonomy dict in the same shape as the
            built-in TAXONOMY constant (code -> {name, number, definition,
            example, ...}). Defaults to the built-in CFI TAXONOMY. Pass the
            second element returned by stats.load_taxonomy_from_json() to
            generate a proper codebook -- with real names, definitions, and
            examples, not placeholders -- for any custom taxonomy, e.g. a
            large-scale-assessment item bank's own distractor-functioning
            categories. See sample_data/custom_taxonomy.json and
            sample_data/item_bank_distractor_taxonomy.json for two worked
            examples completely unrelated to the CFI categories.
        title (str): appendix title.
        include_metadata (bool): include the generation-date /
            software-version / taxonomy-fingerprint header block. The
            fingerprint is only computed for the built-in TAXONOMY (custom
            taxonomies don't have one -- there's nothing to compare a
            custom JSON file's fingerprint against, so this block is
            skipped automatically when `taxonomy` is given explicitly).

    Returns:
        str: Markdown source.
    """
    if taxonomy is None:
        taxonomy = TAXONOMY
    if categories is None:
        categories = ERROR_TYPES

    lines = [f"# {title}", ""]

    if include_metadata:
        if taxonomy is TAXONOMY:
            lines += [
                f"*Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"by confusion-mapper {installed_package_version()}, "
                f"taxonomy fingerprint `{taxonomy_fingerprint()}`.*",
                "",
            ]
        else:
            lines += [
                f"*Generated {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')} "
                f"by confusion-mapper {installed_package_version()}, from a custom taxonomy "
                f"(not the built-in CFI categories -- no fingerprint to compare against).*",
                "",
            ]
        lines += [
            "*This document was generated from the definitions and examples in "
            "the taxonomy in effect. Decision rules are marked as a "
            "placeholder below and need to be filled in by a human from the "
            "study's actual coding manual -- they are not auto-generated.*",
            "",
        ]

    # --- Summary table -----------------------------------------------------
    lines += ["## Summary", "", "| Code | Name | Definition |", "|---|---|---|"]
    for code in categories:
        entry = taxonomy.get(code, {})
        name = entry.get("name", code)
        definition = entry.get("definition", "(no definition on file)").replace("\n", " ").strip()
        lines.append(f"| {code} | {name} | {definition} |")
    lines.append("")

    # --- Per-category detail -------------------------------------------------
    lines += ["## Category definitions", ""]
    for i, code in enumerate(categories, start=1):
        entry = taxonomy.get(code, {})
        name = entry.get("name", code)
        number = entry.get("number", str(i))
        definition = entry.get("definition", "(no definition on file)").strip()
        example = entry.get("example", "(no example on file)").strip()

        lines += [
            f"### {number}. {name} ({code})",
            "",
            f"**Definition.** {definition}",
            "",
            f"**Example.** {example}",
            "",
            "**Decision rule.** *(fill in from your coding manual / Stage 1 RR "
            "methods -- not auto-generated)*",
            "",
        ]

    return "\n".join(lines)


def write_codebook(path, categories=None, taxonomy=None, title="CFI Coding Manual", include_metadata=True):
    """generate_codebook(), written to `path`. Returns `path`."""
    text = generate_codebook(categories=categories, taxonomy=taxonomy, title=title,
                             include_metadata=include_metadata)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
