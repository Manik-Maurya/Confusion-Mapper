"""
Multi-rater workflow: three or more human coders on the same items, with a
pairwise agreement matrix, Fleiss' kappa across the whole panel, conflict
detection, and majority-vote consensus suggestions.

New in v2.6.0. This module introduces no new statistical formula -- it is a
data model and reporting layer built entirely on top of the existing,
already-tested stats.py functions (compute_cohens_kappa, gwet_ac1,
fleiss_kappa). The two-rater human-vs-AI workflow in console.py / cli.py is
unchanged; this is an additional, independent workflow for research teams
running 3+ human coders (Researcher A / B / C) on the same item set, which
was previously only reachable by hand-assembling calls to fleiss_kappa()
yourself.
"""

import csv
from collections import Counter

from .taxonomy import ERROR_TYPES
from .stats import compute_cohens_kappa, gwet_ac1, fleiss_kappa


def load_multirater_csv(path, id_column="item_id"):
    """
    Load a wide-format multi-rater CSV: one row per item, one column per
    rater, plus an item_id column.

        item_id,RaterA,RaterB,RaterC
        Q1_A,CF,CF,PK
        Q1_B,RF,RF,RF

    Args:
        path (str): path to the CSV.
        id_column (str): name of the item-identifier column. Default "item_id".

    Returns:
        item_ids    (list[str])
        rater_names (list[str])        every column except id_column, in file order
        ratings     (list[dict[str,str]])  one dict per item, rater_name -> label
    """
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        if id_column not in fieldnames:
            raise ValueError(f"CSV must have an {id_column!r} column; found {fieldnames}")
        rater_names = [c for c in fieldnames if c != id_column]
        if len(rater_names) < 2:
            raise ValueError(f"need at least 2 rater columns; found {rater_names}")

        item_ids = []
        ratings = []
        for row in reader:
            item_ids.append(row[id_column])
            ratings.append({r: row[r] for r in rater_names})

    return item_ids, rater_names, ratings


def pairwise_agreement_matrix(ratings, rater_names, categories=None):
    """
    Cohen's kappa and Gwet's AC1 for every pair of raters.

    Args:
        ratings     (list[dict[str,str]]): one dict per item, rater_name -> label.
        rater_names (list[str]): the raters to compare, in the order to report them.
        categories  (list[str] | None): defaults to ERROR_TYPES.

    Returns:
        dict: {"RaterA|RaterB": {kappa, kappa_interpretation, ac1, po, n}, ...}
        Keys are "rater1|rater2" following the order of rater_names, so each
        unordered pair appears exactly once.
    """
    if categories is None:
        categories = ERROR_TYPES
    result = {}
    for i in range(len(rater_names)):
        for j in range(i + 1, len(rater_names)):
            r1, r2 = rater_names[i], rater_names[j]
            h = [row[r1] for row in ratings]
            a = [row[r2] for row in ratings]
            k = compute_cohens_kappa(h, a, categories=categories)
            g = gwet_ac1(h, a, categories=categories)
            result[f"{r1}|{r2}"] = {
                "kappa":                k["kappa"],
                "kappa_interpretation": k["interpretation"],
                "ac1":                  g["ac1"],
                "po":                   k["po"],
                "n":                    k["n"],
            }
    return result


def panel_fleiss_kappa(ratings, rater_names, categories=None):
    """
    Fleiss' kappa across the whole panel (3+ raters) in one number.

    This is purely an adapter: it converts the long-format `ratings` (one
    dict per item, rater -> label) into the {category: count} rows
    fleiss_kappa() expects, then calls that unmodified, already-tested
    function. No new formula is introduced here.
    """
    if categories is None:
        categories = ERROR_TYPES
    if len(rater_names) < 3:
        raise ValueError("panel_fleiss_kappa requires at least 3 raters; "
                         "for 2 raters use pairwise_agreement_matrix instead")

    rating_matrix = []
    for row in ratings:
        counts = Counter(row[r] for r in rater_names)
        rating_matrix.append({c: counts.get(c, 0) for c in categories})

    return fleiss_kappa(rating_matrix, categories=categories)


def detect_conflicts(item_ids, ratings, rater_names):
    """
    Flag every item where the panel didn't unanimously agree, ranked by how
    split the panel was (more distinct labels given = ranked first). This
    is what "don't make researchers hunt" means in practice: unanimous
    items are omitted entirely rather than left for a researcher to filter
    out by hand.

    Returns:
        list[dict], sorted worst-disagreement-first:
            item_id, labels (dict rater->label), n_distinct,
            majority_label (str or None if tied), majority_count,
            tied_labels (list[str] or None if there's a clear majority).

        majority_label is a suggestion for a human to accept or override --
        nothing in this function writes a consensus label anywhere.
    """
    conflicts = []
    for item_id, row in zip(item_ids, ratings):
        labels = {r: row[r] for r in rater_names}
        counts = Counter(labels.values())
        if len(counts) <= 1:
            continue  # unanimous -- not a conflict

        top_label, top_count = counts.most_common(1)[0]
        tied = [lbl for lbl, c in counts.items() if c == top_count]

        conflicts.append({
            "item_id":        item_id,
            "labels":         labels,
            "n_distinct":     len(counts),
            "majority_label": top_label if len(tied) == 1 else None,
            "majority_count": top_count,
            "tied_labels":    tied if len(tied) > 1 else None,
        })

    conflicts.sort(key=lambda c: (-c["n_distinct"], c["item_id"]))
    return conflicts


def consensus_report(item_ids, ratings, rater_names, categories=None):
    """
    The full multi-rater workflow in one call: pairwise agreement matrix,
    panel Fleiss' kappa (when there are 3+ raters), and the ranked conflict
    list with majority-vote suggestions. This is what the `multirater` CLI
    subcommand prints.

    Returns:
        dict: n_items, n_raters, raters, pairwise, fleiss (omitted if only
        2 raters), n_conflicts, conflicts.
    """
    if categories is None:
        categories = ERROR_TYPES

    report = {
        "n_items":  len(item_ids),
        "n_raters": len(rater_names),
        "raters":   rater_names,
        "pairwise": pairwise_agreement_matrix(ratings, rater_names, categories),
    }
    if len(rater_names) >= 3:
        report["fleiss"] = panel_fleiss_kappa(ratings, rater_names, categories)

    conflicts = detect_conflicts(item_ids, ratings, rater_names)
    report["n_conflicts"] = len(conflicts)
    report["conflicts"]   = conflicts
    return report
