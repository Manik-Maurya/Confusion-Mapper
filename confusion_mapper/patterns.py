"""
Pattern mining. Given a coded corpus, this module looks for recurring
error patterns, for example specific keywords that keep showing up in
Confabulation items, or bigrams that predict Interference.

I built this because the biggest question after coding is not what the
kappa is, but why the students keep making the same mistake. The
functions here are simple descriptive statistics, not machine learning,
because that is what a rubric revision meeting can actually use.
"""

import csv
import math
from collections import Counter, defaultdict

from .taxonomy import ERROR_TYPES


def load_longitudinal_csv(path):
    """
    Load a longitudinal/multi-item coded-response CSV. Required columns:
    respondent_id, item_id, label. Optional: timepoint, cohort (default
    "" if absent).

    Returns:
        list[dict]: {respondent_id, item_id, label, timepoint, cohort}
    """
    records = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            records.append({
                "respondent_id": row["respondent_id"],
                "item_id":       row["item_id"],
                "label":         row["label"],
                "timepoint":     row.get("timepoint", ""),
                "cohort":        row.get("cohort", ""),
            })
    return records


# ---------------------------------------------------------------------------
# Chi-square test, from scratch
# ---------------------------------------------------------------------------

def _normal_cdf(z):
    """Standard normal CDF via math.erf, same expression used elsewhere
    in this package (stats.bootstrap_kappa_ci, stats.recommend_sample_size)."""
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


def _chi_square_p(chi2_stat, df):
    """
    P(X > chi2_stat) for X ~ chi-square(df), via the Wilson-Hilferty
    approximation: (X/df)^(1/3) is approximately normal with mean
    1 - 2/(9*df) and variance 2/(9*df). See module docstring for accuracy.
    """
    if df <= 0:
        return 1.0
    if chi2_stat <= 0:
        return 1.0
    h = 2.0 / (9.0 * df)
    z = ((chi2_stat / df) ** (1.0 / 3.0) - (1 - h)) / math.sqrt(h)
    return max(0.0, min(1.0, 1.0 - _normal_cdf(z)))


def chi_square_test(observed):
    """
    Pearson's chi-square test of independence on a contingency table.

    Args:
        observed (dict[str, dict[str, int]]): {row_key: {col_key: count}}.
            Every row must have the same set of column keys.

    Returns:
        dict: chi2 (float), df (int), p_value (float), n (int),
        cramers_v (float, 0-1 effect size: sqrt(chi2 / (n * min(r-1,c-1)))),
        expected (dict[str, dict[str, float]], the expected-under-
        independence counts, useful for spotting which cell drives the
        result).

    Raises:
        ValueError: fewer than 2 rows or 2 columns, or n == 0.
    """
    row_keys = list(observed.keys())
    if len(row_keys) < 2:
        raise ValueError("chi_square_test needs at least 2 rows")
    col_keys = list(observed[row_keys[0]].keys())
    if len(col_keys) < 2:
        raise ValueError("chi_square_test needs at least 2 columns")
    for rk in row_keys:
        if set(observed[rk].keys()) != set(col_keys):
            raise ValueError(f"row {rk!r} has different columns than row {row_keys[0]!r}")

    row_totals = {rk: sum(observed[rk].values()) for rk in row_keys}
    col_totals = {ck: sum(observed[rk][ck] for rk in row_keys) for ck in col_keys}
    n = sum(row_totals.values())
    if n == 0:
        raise ValueError("contingency table is empty (n=0)")

    expected = {}
    chi2 = 0.0
    for rk in row_keys:
        expected[rk] = {}
        for ck in col_keys:
            e = row_totals[rk] * col_totals[ck] / n
            expected[rk][ck] = e
            o = observed[rk][ck]
            if e > 0:
                chi2 += (o - e) ** 2 / e

    df = (len(row_keys) - 1) * (len(col_keys) - 1)
    p_value = _chi_square_p(chi2, df)
    min_dim = min(len(row_keys) - 1, len(col_keys) - 1)
    cramers_v = math.sqrt(chi2 / (n * min_dim)) if min_dim > 0 and n > 0 else 0.0

    return {
        "chi2":       round(chi2, 4),
        "df":         df,
        "p_value":    round(p_value, 6),
        "n":          n,
        "cramers_v":  round(cramers_v, 4),
        "expected":   {rk: {ck: round(v, 2) for ck, v in row.items()}
                      for rk, row in expected.items()},
    }


# ---------------------------------------------------------------------------
# Co-occurrence (association / "lift", not chi-square, see docstring)
# ---------------------------------------------------------------------------

def co_occurrence_summary(records, categories=None):
    """
    Which misconceptions tend to show up together in the same respondent's
    profile, across all their items, not "does item A predict item B"
    (that needs a *specific* item pair; see item_pair_cooccurrence()), but
    "does a respondent who shows CF anywhere also tend to show INT
    elsewhere."

    Uses lift, the standard association-rule-mining metric (Agrawal et
    al.): lift(A, B) = P(A and B both appear in a respondent's profile) /
    (P(A appears) * P(B appears)). lift > 1 means the pair co-occurs more
    than chance would predict; < 1 means less; == 1 means independent.
    Not a hypothesis test, report support (how many respondents show
    both) alongside lift, since lift on a tiny support is not meaningful.

    Args:
        records (list[dict]): as returned by load_longitudinal_csv().
        categories (list[str] | None): defaults to ERROR_TYPES.

    Returns:
        list[dict]: {category_a, category_b, support, lift}, one row per
        unordered category pair that co-occurred at least once, sorted by
        lift descending.
    """
    if categories is None:
        categories = ERROR_TYPES

    by_respondent = defaultdict(set)
    for r in records:
        if r["label"] in categories:
            by_respondent[r["respondent_id"]].add(r["label"])

    n_respondents = len(by_respondent)
    if n_respondents == 0:
        return []

    single_count = Counter()
    pair_count = Counter()
    for labels in by_respondent.values():
        for lbl in labels:
            single_count[lbl] += 1
        for a, b in _unordered_pairs(sorted(labels)):
            pair_count[(a, b)] += 1

    results = []
    for (a, b), support in pair_count.items():
        p_a = single_count[a] / n_respondents
        p_b = single_count[b] / n_respondents
        p_ab = support / n_respondents
        lift = p_ab / (p_a * p_b) if (p_a > 0 and p_b > 0) else 0.0
        results.append({
            "category_a": a, "category_b": b,
            "support": support, "lift": round(lift, 4),
        })
    results.sort(key=lambda r: r["lift"], reverse=True)
    return results


def _unordered_pairs(sorted_items):
    for i in range(len(sorted_items)):
        for j in range(i + 1, len(sorted_items)):
            yield sorted_items[i], sorted_items[j]


def item_pair_cooccurrence(records, item_id_1, item_id_2, categories=None):
    """
    For respondents who answered both item_id_1 and item_id_2: does the
    label on one predict the label on the other? Unlike
    co_occurrence_summary(), this is a real hypothesis test, one
    specific, well-defined pair of items, not pooled across the whole item
    bank, via chi_square_test() on the 2-item contingency table.

    Returns:
        dict: chi_square_test()'s return dict, plus n_respondents.
    """
    if categories is None:
        categories = ERROR_TYPES

    by_respondent = defaultdict(dict)
    for r in records:
        if r["item_id"] in (item_id_1, item_id_2):
            by_respondent[r["respondent_id"]][r["item_id"]] = r["label"]

    paired = [(v[item_id_1], v[item_id_2]) for v in by_respondent.values()
             if item_id_1 in v and item_id_2 in v]

    observed = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    for l1, l2 in paired:
        if l1 in categories and l2 in categories:
            observed[l1][l2] += 1

    result = chi_square_test(observed)
    result["n_respondents"] = len(paired)
    return result


# ---------------------------------------------------------------------------
# Transitions across timepoints
# ---------------------------------------------------------------------------

def _ordered_timepoints_for(respondent_records, timepoint_order):
    """Sort one respondent's records by timepoint, using timepoint_order
    if given, else natural/alphabetical sort as a documented fallback."""
    if timepoint_order:
        rank = {tp: i for i, tp in enumerate(timepoint_order)}
        return sorted((r for r in respondent_records if r["timepoint"] in rank),
                      key=lambda r: rank[r["timepoint"]])
    return sorted(respondent_records, key=lambda r: r["timepoint"])


def transition_matrix(records, item_id=None, categories=None, timepoint_order=None):
    """
    P(label at timepoint t+1 | label at timepoint t), across all
    respondents' consecutive-timepoint pairs.

    Args:
        records (list[dict])
        item_id (str | None): if given, only use records for this one item
            (recommended, mixing different items' labels into one
            transition matrix conflates "how this item's error type
            changed" with "which item the respondent happened to answer,"
            which usually isn't what you want). If None, uses every
            record for a respondent at each timepoint indiscriminately.
        categories (list[str] | None)
        timepoint_order (list[str] | None): explicit chronological order,
            e.g. ["pretest", "week2", "week5", "posttest"]. Without it,
            timepoints are sorted alphabetically, which is very unlikely
            to be the order you actually want, pass this explicitly.

    Returns:
        dict:
            counts (dict[str, dict[str, int]]): raw transition counts.
            probabilities (dict[str, dict[str, float]]): row-normalized
                (each "from" row sums to 1.0, or is all-zero if that
                category was never a starting point).
            most_likely_next (dict[str, str | None]): per starting
                category, whichever category it transitions to most often.
            n_transitions (int)
    """
    if categories is None:
        categories = ERROR_TYPES

    by_respondent = defaultdict(list)
    for r in records:
        if item_id is None or r["item_id"] == item_id:
            by_respondent[r["respondent_id"]].append(r)

    counts = {c1: {c2: 0 for c2 in categories} for c1 in categories}
    n_transitions = 0
    for resp_records in by_respondent.values():
        ordered = _ordered_timepoints_for(resp_records, timepoint_order)
        for i in range(len(ordered) - 1):
            l1, l2 = ordered[i]["label"], ordered[i + 1]["label"]
            if l1 in categories and l2 in categories:
                counts[l1][l2] += 1
                n_transitions += 1

    probabilities = {}
    most_likely_next = {}
    for c1 in categories:
        row_total = sum(counts[c1].values())
        if row_total > 0:
            probabilities[c1] = {c2: round(counts[c1][c2] / row_total, 4) for c2 in categories}
            most_likely_next[c1] = max(categories, key=lambda c2: counts[c1][c2])
        else:
            probabilities[c1] = {c2: 0.0 for c2 in categories}
            most_likely_next[c1] = None

    return {
        "counts": counts,
        "probabilities": probabilities,
        "most_likely_next": most_likely_next,
        "n_transitions": n_transitions,
    }


def mine_transition_patterns(records, item_id=None, categories=None,
                             timepoint_order=None, sequence_length=2, top_k=10):
    """
    The most frequent label sequences ("pathways") of a given length across
    respondents' ordered timepoints, n-gram frequency mining over each
    respondent's label sequence, the "common misconception pathways" idea.

    Args:
        sequence_length (int): e.g. 2 for pairs (A->B), 3 for triples
            (A->B->C). Must be >= 2.
        top_k (int): how many of the most frequent patterns to return.

    Returns:
        list[dict]: {pattern (tuple[str]), count}, sorted by count
        descending, length min(top_k, n_distinct_patterns_seen).
    """
    if categories is None:
        categories = ERROR_TYPES
    if sequence_length < 2:
        raise ValueError("sequence_length must be >= 2")

    by_respondent = defaultdict(list)
    for r in records:
        if item_id is None or r["item_id"] == item_id:
            by_respondent[r["respondent_id"]].append(r)

    pattern_counts = Counter()
    for resp_records in by_respondent.values():
        ordered = _ordered_timepoints_for(resp_records, timepoint_order)
        labels = [r["label"] for r in ordered if r["label"] in categories]
        for i in range(len(labels) - sequence_length + 1):
            pattern_counts[tuple(labels[i:i + sequence_length])] += 1

    ranked = pattern_counts.most_common(top_k)
    return [{"pattern": list(p), "count": c} for p, c in ranked]


# ---------------------------------------------------------------------------
# Temporal trend and cohort comparison (both chi-square, category x group)
# ---------------------------------------------------------------------------

def temporal_trend(records, categories=None, timepoint_order=None):
    """
    Does the distribution of categories change across timepoints?
    A chi-square test of independence between timepoint and category,
    plus the per-timepoint category proportions to see the shape of any
    change chi_square_test's p-value alone won't show you.

    Returns:
        dict: chi_square_test()'s return dict (keyed by timepoint x
        category), plus "proportions": {timepoint: {category: proportion}}.
    """
    if categories is None:
        categories = ERROR_TYPES

    timepoints = timepoint_order or sorted({r["timepoint"] for r in records})
    observed = {tp: {c: 0 for c in categories} for tp in timepoints}
    for r in records:
        if r["timepoint"] in observed and r["label"] in categories:
            observed[r["timepoint"]][r["label"]] += 1

    result = chi_square_test(observed)

    proportions = {}
    for tp in timepoints:
        total = sum(observed[tp].values())
        proportions[tp] = ({c: round(observed[tp][c] / total, 4) for c in categories}
                           if total > 0 else {c: 0.0 for c in categories})
    result["proportions"] = proportions
    return result


def cohort_comparison(records, categories=None, cohorts=None):
    """
    Does the category distribution differ between cohorts (e.g.
    government vs. private schools)? A chi-square test of independence
    between cohort and category, plus per-cohort proportions and which
    category shows the largest absolute proportion gap between the two
    most different cohorts.

    Args:
        cohorts (list[str] | None): defaults to every distinct
            record["cohort"] value seen.

    Returns:
        dict: chi_square_test()'s return dict, plus "proportions"
        (per-cohort category proportions) and "largest_gap": {category,
        cohort_a, cohort_b, gap} for the single biggest proportion
        difference found across any category/cohort-pair.
    """
    if categories is None:
        categories = ERROR_TYPES

    cohort_list = cohorts or sorted({r["cohort"] for r in records})
    if len(cohort_list) < 2:
        raise ValueError("need at least 2 cohorts to compare")

    observed = {ch: {c: 0 for c in categories} for ch in cohort_list}
    for r in records:
        if r["cohort"] in observed and r["label"] in categories:
            observed[r["cohort"]][r["label"]] += 1

    result = chi_square_test(observed)

    proportions = {}
    for ch in cohort_list:
        total = sum(observed[ch].values())
        proportions[ch] = ({c: round(observed[ch][c] / total, 4) for c in categories}
                           if total > 0 else {c: 0.0 for c in categories})
    result["proportions"] = proportions

    largest_gap = {"category": None, "cohort_a": None, "cohort_b": None, "gap": -1.0}
    for c in categories:
        for i in range(len(cohort_list)):
            for j in range(i + 1, len(cohort_list)):
                ch_a, ch_b = cohort_list[i], cohort_list[j]
                gap = abs(proportions[ch_a][c] - proportions[ch_b][c])
                if gap > largest_gap["gap"]:
                    largest_gap = {"category": c, "cohort_a": ch_a, "cohort_b": ch_b, "gap": round(gap, 4)}
    result["largest_gap"] = largest_gap
    return result
