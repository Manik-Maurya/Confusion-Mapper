"""
Discovery mode. Walks a folder, finds candidate paired-label CSVs
(anything with two columns that look like labels from a taxonomy),
and previews them so a user does not have to remember exact filenames.

Also lists which of the CLI subcommands would be useful given the
shape of each file. Small quality-of-life thing, not a research
feature.
"""

from collections import Counter

from .embeddings import cluster_index


def label_purity(cluster, label_key="label"):
    """
    How much the items in a cluster already agree on an existing label.

    1.0 means every item in the cluster already has the same label, the
    existing taxonomy probably already captures this pattern fine. A low
    purity (items spread across several different existing labels despite
    being semantically similar) is the signal this module looks for: a
    tight cluster of similar content that raters didn't have one clean
    bucket for.

    Args:
        cluster (dict): one entry from embeddings.cluster_index()'s return list.
        label_key (str): which metadata key holds the existing label,
            e.g. "human_label" if that's what you passed to
            embeddings.add_to_index(..., metadata={"human_label": ...}).

    Returns:
        dict: modal_label, modal_count, n_distinct_labels, purity
        (modal_count / n items with a label present; None if no item in
        the cluster has `label_key` set), label_counts (dict[str, int]).
    """
    labels = [item["metadata"].get(label_key) for item in cluster["items"]
             if item["metadata"].get(label_key)]
    if not labels:
        return {"modal_label": None, "modal_count": 0, "n_distinct_labels": 0,
                "purity": None, "label_counts": {}}
    counts = Counter(labels)
    modal_label, modal_count = counts.most_common(1)[0]
    return {
        "modal_label":       modal_label,
        "modal_count":       modal_count,
        "n_distinct_labels": len(counts),
        "purity":            round(modal_count / len(labels), 4),
        "label_counts":      dict(counts),
    }


def propose_candidate_categories(index, label_key="label", threshold=0.5,
                                 min_cluster_size=3, max_purity=0.6):
    """
    Cluster the index, compute each cluster's label purity, and flag
    clusters where purity is at or below `max_purity` as worth a human's
    attention. This deliberately does NOT flag every low-purity cluster
    that clustering finds, min_cluster_size and the similarity
    `threshold` (passed through to embeddings.cluster_index) already
    filter out chance groupings before purity is even checked, so what
    comes out the other end is: semantically tight, reasonably sized,
    AND inconsistently labeled. That combination is the actual signal;
    any one of the three alone is not.

    Args:
        index (dict): an embeddings index (embeddings.create_index /
            load_index), built with each item's existing label stored in
            metadata under `label_key`, e.g. via
            `embed-index --label-column human_label`.
        label_key (str): metadata key holding the label to check purity against.
        threshold (float): cosine-similarity clustering threshold.
        min_cluster_size (int): minimum cluster size to consider.
        max_purity (float): clusters at or below this purity are flagged.
            Default 0.6, even a cluster the existing taxonomy mostly
            agrees on but splits close to 60/40 is worth a look; much
            lower would only surface near-total disagreement.

    Returns:
        list[dict]: {cluster_id, size, purity_report, items}, sorted by
        purity ascending (least consistent, most interesting, first).
        A proposal list. Nothing is written anywhere.
    """
    clusters = cluster_index(index, threshold=threshold, min_cluster_size=min_cluster_size)
    candidates = []
    for cluster in clusters:
        purity_report = label_purity(cluster, label_key=label_key)
        if purity_report["purity"] is not None and purity_report["purity"] <= max_purity:
            candidates.append({
                "cluster_id":    cluster["cluster_id"],
                "size":          cluster["size"],
                "purity_report": purity_report,
                "items":         cluster["items"],
            })
    candidates.sort(key=lambda c: c["purity_report"]["purity"])
    return candidates


def format_proposal_report(candidates, taxonomy_hint=None, label_key="label"):
    """
    Render propose_candidate_categories()'s output as a readable Markdown
    report, the actual "propose... researcher names it" hand-off point.

    Args:
        candidates (list[dict]): as returned by propose_candidate_categories().
        taxonomy_hint (list[str] | None): existing category codes, for
            context in the report header only.
        label_key (str): must match whatever label_key was passed to
            propose_candidate_categories(), otherwise every item's
            displayed label falls back to "?", since the metadata was
            stored under a different key than this function looks for.

    Returns:
        str: Markdown.
    """
    lines = ["# Candidate misconception categories", ""]
    lines.append(
        "Every cluster below is a group of items the embeddings index found "
        "semantically similar, where the label(s) already assigned to them "
        "disagree more than the purity threshold allows. That makes each one "
        "a *candidate*, not a conclusion, read the items and decide whether "
        "it's a real pattern the taxonomy is missing a category for, or "
        "coincidence / an embedding false positive (this is especially worth "
        "double-checking if the index used the local hashed-BoW backend "
        "rather than real embeddings). **Nothing here has been written to "
        "any taxonomy file.**"
    )
    lines.append("")
    if taxonomy_hint:
        lines.append(f"Existing categories checked against: {', '.join(taxonomy_hint)}")
        lines.append("")

    if not candidates:
        lines.append("*No candidates found at the given threshold / purity settings. "
                     "Try a lower --threshold (looser clustering) or a higher "
                     "--max-purity (flag more clusters) if you expected some.*")
        return "\n".join(lines)

    for c in candidates:
        pr = c["purity_report"]
        lines += [
            f"## Cluster {c['cluster_id']} ({c['size']} items, "
            f"purity {pr['purity']:.2f}, {pr['n_distinct_labels']} distinct existing labels)",
            "",
            f"Existing label breakdown: {pr['label_counts']}",
            "",
            "Items:",
        ]
        for item in c["items"]:
            lbl = item["metadata"].get(label_key, "?")
            lines.append(f"- ({lbl}) {item['text']}")
        lines.append("")

    lines.append(
        "---\n\nIf you decide a cluster above is a real, distinct pattern: give it a "
        "code, name, definition, and example, add it to a taxonomy JSON (see "
        "`sample_data/custom_taxonomy.json` for the shape), and load it with "
        "`stats.load_taxonomy_from_json()` for your next coding round. This is a "
        "manual step by design, see this module's docstring."
    )
    return "\n".join(lines)
