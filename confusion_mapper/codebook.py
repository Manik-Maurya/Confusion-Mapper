"""
Codebook generator. Turns the CFI taxonomy in taxonomy.py into a
Markdown research appendix that reviewers can print or attach as
supplementary material.

The decision-rule field for each category is left as a literal
placeholder. I could have asked the model to invent a rule from the
definition, but that would be presenting fabricated methodology as if
a human wrote it, and I would rather leave a blank the researcher
fills in themselves.
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
            not found in `taxonomy` falls back to just the code with a
            "(no definition on file)" placeholder, so partially documented
            taxonomies still render cleanly.
        taxonomy (dict | None): a taxonomy dict in the same shape as the
            built-in TAXONOMY (code -> {name, number, definition, example,
            ...}). Defaults to the built-in CFI TAXONOMY. Pass the second
            element of stats.load_taxonomy_from_json() to render any custom
            taxonomy properly. See sample_data/custom_taxonomy.json and
            sample_data/item_bank_distractor_taxonomy.json for two
            unrelated worked examples.
        title (str): appendix title.
        include_metadata (bool): include the generation-date, software
            version, and taxonomy fingerprint header. The fingerprint
            only makes sense for the built-in TAXONOMY, so it is skipped
            automatically when a custom `taxonomy` is passed.

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
                f"(not the built-in CFI categories, no fingerprint to compare against).*",
                "",
            ]
        lines += [
            "*Generated from the definitions and examples in the taxonomy "
            "in effect. Decision rules are left as placeholders and need to "
            "be filled in by a human from the study's coding manual, they "
            "are not auto-generated.*",
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
