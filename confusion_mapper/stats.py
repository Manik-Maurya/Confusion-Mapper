"""
The core statistics module. Cohen's kappa (nominal, linear, quadratic),
bootstrap CIs (percentile and BCa), and helpers for the confusion matrix
and per-category agreement.

I originally wrote all of this as one giant file. During the 2.6.0 cleanup
I broke it apart so each concept lives in its own module. The formulas here
are exactly the ones I had before, no changes, only the surrounding code
moved. Kept it that way on purpose so I could keep trusting the tests.

If you are reading this to understand how kappa works, start with
compute_cohens_kappa below. The bootstrap function is longer but it is
just the same kappa formula wrapped in a resampling loop.
"""

import json
import math

from .taxonomy import ERROR_TYPES, TAXONOMY


def compute_cohens_kappa(human_labels, ai_labels, weights="nominal", categories=None):
    """
    Compute Cohen's kappa between two raters.

    Supports three weighting schemes:
      - "nominal"   (default): every disagreement counts equally. This is the
                    standard Cohen (1960) kappa.
      - "linear"    Cicchetti-Allison weights, |i - j| / (k - 1). Use when the
                    categories form an ordinal scale and adjacent-category
                    disagreements should count less than far-apart ones.
      - "quadratic" Fleiss-Cohen weights, (i - j)**2 / (k - 1)**2. Sharper
                    penalisation of far-apart disagreements. Equivalent to the
                    intraclass correlation coefficient (ICC) under certain
                    assumptions.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels, same length as human_labels.
        weights      (str): "nominal" | "linear" | "quadratic".
        categories   (list[str] | None): explicit category order. If None,
                     uses the module-level ERROR_TYPES. Required for weighted
                     kappa because position in this list defines ordinal rank.

    Returns:
        dict with keys: kappa, interpretation, po, pe, n, agreements, weights.

    Worked nominal example:
        human = ["CF","CF","CF","CF","RF","RF","PK","PK","INT","INT"]
        ai    = ["CF","CF","CF","RF","RF","RF","PK","CF","INT","INT"]
        Po = 8/10 = 0.8
        Pe = 0.16 + 0.06 + 0.02 + 0.04 = 0.28
        kappa = (0.8 - 0.28) / (1 - 0.28) = 0.7222

    Worked linear example (same data, ordinal order [RF, PK, CF, INT]):
        Adjacent-category disagreements (e.g. PK to CF) get weight 1/3
        instead of 1, so the penalised observed agreement is higher.
    """
    if categories is None:
        categories = ERROR_TYPES
    k = len(categories)
    n = len(human_labels)

    if n == 0:
        return {
            "kappa": 0.0,
            "interpretation": "No data to compute kappa.",
            "po": 0.0, "pe": 0.0,
            "n": 0, "agreements": 0,
            "weights": weights,
        }

    agreements = sum(1 for h, a in zip(human_labels, ai_labels) if h == a)

    if weights == "nominal":
        po = agreements / n
        pe = 0.0
        for label in categories:
            p_human = human_labels.count(label) / n
            p_ai    = ai_labels.count(label) / n
            pe += p_human * p_ai
        if pe >= 1.0:
            kappa = 1.0
        else:
            kappa = (po - pe) / (1.0 - pe)
    else:
        if weights not in ("linear", "quadratic"):
            raise ValueError(
                f"weights must be 'nominal', 'linear', or 'quadratic'; got {weights!r}"
            )
        if k < 2:
            raise ValueError("weighted kappa requires at least 2 categories")
        idx = {c: i for i, c in enumerate(categories)}
        denom = (k - 1) ** (1 if weights == "linear" else 2)

        def w(i, j):
            d = abs(i - j)
            return (d if weights == "linear" else d * d) / denom

        # fill the observed matrix cell by cell, expected comes from row/col totals
        obs = [[0] * k for _ in range(k)]
        for h, a in zip(human_labels, ai_labels):
            if h in idx and a in idx:
                obs[idx[h]][idx[a]] += 1
        row_tot = [sum(row) for row in obs]
        col_tot = [sum(obs[r][c] for r in range(k)) for c in range(k)]

        weighted_disagreement_obs = 0.0
        weighted_disagreement_exp = 0.0
        for i in range(k):
            for j in range(k):
                wij = w(i, j)
                weighted_disagreement_obs += wij * obs[i][j]
                weighted_disagreement_exp += wij * (row_tot[i] * col_tot[j] / n)

        if weighted_disagreement_exp == 0:
            kappa = 1.0 if weighted_disagreement_obs == 0 else 0.0
        else:
            kappa = 1.0 - weighted_disagreement_obs / weighted_disagreement_exp

        po = agreements / n
        pe = 1.0 - weighted_disagreement_exp / n if weighted_disagreement_exp <= n else 0.0

    if kappa < 0.20:
        interp = "Slight, rubric needs substantial revision before research use."
    elif kappa < 0.40:
        interp = "Fair, significant revision needed. Review CF vs RF boundary."
    elif kappa < 0.60:
        interp = "Moderate, improvement needed. Target is kappa >= 0.70."
    elif kappa < 0.70:
        interp = "Substantial, close to target. Refine ambiguous cases."
    elif kappa < 0.80:
        interp = "Substantial, research threshold reached! Proceed with validation."
    else:
        interp = "Almost Perfect, excellent agreement."

    return {
        "kappa":          round(kappa, 4),
        "interpretation": interp,
        "po":             round(po, 4),
        "pe":             round(pe, 4),
        "n":              n,
        "agreements":     agreements,
        "weights":        weights,
    }


def bootstrap_kappa_ci(human_labels, ai_labels,
                       n_resamples=10000, confidence=0.95,
                       method="bca", weights="nominal",
                       categories=None, seed=None):
    """
    Bootstrap a confidence interval for Cohen's kappa.

    Cohen's kappa is a point estimate. Research use needs uncertainty around
    that point. This function resamples the paired (human, ai) tuples with
    replacement, computes kappa on each resample, and returns the lower and
    upper bounds of a confidence interval. Two methods are supported:

      - "percentile": the simple percentile bootstrap. Returns the
                      alpha/2 and 1 - alpha/2 quantiles of the bootstrap
                      kappa distribution.
      - "bca":        bias-corrected and accelerated (Efron, 1987).
                      Adjusts the percentile endpoints using a bias-correction
                      term from the bootstrap distribution and an acceleration
                      term from the leave-one-out jackknife. Recommended for
                      skewed sampling distributions.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels, same length.
        n_resamples  (int): number of bootstrap samples. Default 10000.
        confidence   (float): confidence level in (0, 1). Default 0.95.
        method       (str): "percentile" or "bca". Default "bca".
        weights      (str): forwarded to compute_cohens_kappa.
        categories   (list[str] | None): forwarded.
        seed         (int | None): RNG seed for reproducibility.

    Returns:
        dict with keys:
            point_estimate (float): kappa on the original sample.
            ci_lower       (float): lower bound of the CI.
            ci_upper       (float): upper bound of the CI.
            confidence     (float): confidence level used.
            method         (str): method used.
            n_resamples    (int): number of resamples used.
    """
    import random

    n = len(human_labels)
    if n != len(ai_labels):
        raise ValueError("human_labels and ai_labels must be the same length")
    if n < 2:
        # nothing to bootstrap over. return the point value and move on.
        point = compute_cohens_kappa(human_labels, ai_labels,
                                     weights=weights, categories=categories)["kappa"]
        return {"point_estimate": point, "ci_lower": point, "ci_upper": point,
                "confidence": confidence, "method": method, "n_resamples": 0}
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1 exclusive")
    if method not in ("percentile", "bca"):
        raise ValueError(f"method must be 'percentile' or 'bca'; got {method!r}")

    rng = random.Random(seed)

    pairs = list(zip(human_labels, ai_labels))
    point = compute_cohens_kappa(human_labels, ai_labels,
                                 weights=weights, categories=categories)["kappa"]

    boot_kappas = []
    for _ in range(n_resamples):
        sample = [rng.choice(pairs) for _ in range(n)]
        h = [p[0] for p in sample]
        a = [p[1] for p in sample]
        boot_kappas.append(
            compute_cohens_kappa(h, a, weights=weights, categories=categories)["kappa"]
        )
    boot_kappas.sort()
    alpha = 1 - confidence

    def qnorm(p):
        # inverse-normal CDF, Beasley-Springer-Moro. Table lifted from the paper;
        # I did not derive these constants.
        if p <= 0 or p >= 1:
            if p == 0: return float("-inf")
            if p == 1: return float("inf")
            raise ValueError("p must be in (0, 1)")
        a_c = [-3.969683028665376e+01,  2.209460984245205e+02,
               -2.759285104469687e+02,  1.383577518672690e+02,
               -3.066479806614716e+01,  2.506628277459239e+00]
        b_c = [-5.447609879822406e+01,  1.615858368580409e+02,
               -1.556989798598866e+02,  6.680131188771972e+01,
               -1.328068155288572e+01]
        c_c = [-7.784894002430293e-03, -3.223964580411365e-01,
               -2.400758277161838e+00, -2.549732539343734e+00,
                4.374664141464968e+00,  2.938163982698783e+00]
        d_c = [ 7.784695709041462e-03,  3.224671290700398e-01,
                2.445134137142996e+00,  3.754408661907416e+00]
        plow = 0.02425
        phigh = 1 - plow
        if p < plow:
            q = math.sqrt(-2 * math.log(p))
            return (((((c_c[0]*q+c_c[1])*q+c_c[2])*q+c_c[3])*q+c_c[4])*q+c_c[5]) /                    ((((d_c[0]*q+d_c[1])*q+d_c[2])*q+d_c[3])*q+1)
        if p > phigh:
            q = math.sqrt(-2 * math.log(1 - p))
            return -(((((c_c[0]*q+c_c[1])*q+c_c[2])*q+c_c[3])*q+c_c[4])*q+c_c[5]) /                     ((((d_c[0]*q+d_c[1])*q+d_c[2])*q+d_c[3])*q+1)
        q = p - 0.5
        r = q * q
        return (((((a_c[0]*r+a_c[1])*r+a_c[2])*r+a_c[3])*r+a_c[4])*r+a_c[5]) * q /                (((((b_c[0]*r+b_c[1])*r+b_c[2])*r+b_c[3])*r+b_c[4])*r+1)

    def pnorm(z):
        return 0.5 * (1 + math.erf(z / math.sqrt(2)))

    if method == "percentile":
        lo_idx = max(0, int(math.floor((alpha / 2) * n_resamples)))
        hi_idx = min(n_resamples - 1, int(math.ceil((1 - alpha / 2) * n_resamples)) - 1)
        return {"point_estimate": point,
                "ci_lower": round(boot_kappas[lo_idx], 4),
                "ci_upper": round(boot_kappas[hi_idx], 4),
                "confidence": confidence, "method": "percentile",
                "n_resamples": n_resamples}

    # BCa
    below = sum(1 for x in boot_kappas if x < point)
    prop_below = below / n_resamples if n_resamples > 0 else 0.5
    # clip so qnorm never sees exactly 0 or 1
    prop_below = min(max(prop_below, 1e-6), 1 - 1e-6)
    z0 = qnorm(prop_below)

    # jackknife the acceleration factor (BCa needs this)
    jack = []
    for i in range(n):
        h_jk = human_labels[:i] + human_labels[i+1:]
        a_jk = ai_labels[:i]    + ai_labels[i+1:]
        jack.append(compute_cohens_kappa(h_jk, a_jk,
                                         weights=weights, categories=categories)["kappa"])
    jack_mean = sum(jack) / n
    num = sum((jack_mean - x) ** 3 for x in jack)
    den = 6 * (sum((jack_mean - x) ** 2 for x in jack)) ** 1.5
    a_hat = num / den if den != 0 else 0.0

    z_lo = qnorm(alpha / 2)
    z_hi = qnorm(1 - alpha / 2)
    alpha_1 = pnorm(z0 + (z0 + z_lo) / (1 - a_hat * (z0 + z_lo)))
    alpha_2 = pnorm(z0 + (z0 + z_hi) / (1 - a_hat * (z0 + z_hi)))
    lo_idx = max(0, min(n_resamples - 1, int(math.floor(alpha_1 * n_resamples))))
    hi_idx = max(0, min(n_resamples - 1, int(math.ceil(alpha_2 * n_resamples)) - 1))

    return {"point_estimate": point,
            "ci_lower": round(boot_kappas[lo_idx], 4),
            "ci_upper": round(boot_kappas[hi_idx], 4),
            "confidence": confidence, "method": "bca",
            "n_resamples": n_resamples}


def load_taxonomy_from_json(json_path):
    """
    Load a custom error-type taxonomy from a JSON file.

    The file must contain a top-level "labels" array of objects with these
    required keys: "code" (short unique identifier), "name" (human-readable),
    "definition" (full description used in the AI prompt). Optional keys:
    "number" (display index, default position+1), "color" (hex string for
    GUI, default grey), "example" (default empty string).

    Example custom_taxonomy.json:
        {
          "labels": [
            {"code": "A", "name": "Alpha", "definition": "...", "color": "#f00"},
            {"code": "B", "name": "Beta",  "definition": "...", "color": "#0f0"}
          ]
        }

    Args:
        json_path (str): path to a JSON file.

    Returns:
        (list[str], dict): a tuple of (codes_in_order, taxonomy_dict). The
        taxonomy_dict has the same shape as the built-in TAXONOMY constant.

    Raises:
        ValueError: if the file is malformed, codes are not unique, or
                    required keys are missing.
    """
    with open(json_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    if "labels" not in data or not isinstance(data["labels"], list):
        raise ValueError("taxonomy JSON must have a top-level 'labels' array")
    if len(data["labels"]) < 2:
        raise ValueError("taxonomy must contain at least 2 labels")

    codes, tax = [], {}
    for i, entry in enumerate(data["labels"]):
        for required in ("code", "name", "definition"):
            if required not in entry:
                raise ValueError(f"label {i} is missing required key {required!r}")
        code = entry["code"]
        if code in tax:
            raise ValueError(f"duplicate label code: {code!r}")
        codes.append(code)
        tax[code] = {
            "name":       entry["name"],
            "number":     str(entry.get("number", i + 1)),
            "definition": entry["definition"],
            "example":    entry.get("example", ""),
            "color":      entry.get("color", "#888888"),
        }
    return codes, tax


def build_confusion_matrix(human_labels, ai_labels, categories=None):
    """
    Build a confusion matrix where rows are human labels and columns are AI labels.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels, same length as human_labels.
        categories   (list[str] | None): explicit category order. If None,
                     uses the module-level ERROR_TYPES.

    Returns:
        dict: matrix[human_label][ai_label] = count. Sum of diagonal cells
        equals the number of agreements; sum of all cells equals len(human_labels).
    """
    if categories is None:
        categories = ERROR_TYPES
    matrix = {row: {col: 0 for col in categories} for row in categories}
    for h, a in zip(human_labels, ai_labels):
        if h in matrix and a in matrix[h]:
            matrix[h][a] += 1
    return matrix


def get_per_type_stats(human_labels, ai_labels, categories=None):
    """
    Compute per-category agreement statistics.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels, same length as human_labels.
        categories   (list[str] | None): explicit category order. If None,
                     uses the module-level ERROR_TYPES.

    Returns:
        dict: code -> {"total": items the human labelled this code,
                       "agreed": items where AI matched the human,
                       "pct": agreement percentage (0 to 100)}.
    """
    if categories is None:
        categories = ERROR_TYPES
    stats = {}
    for label in categories:
        indices = [i for i, h in enumerate(human_labels) if h == label]
        if not indices:
            stats[label] = {"total": 0, "agreed": 0, "pct": 0}
        else:
            agreed = sum(1 for i in indices if ai_labels[i] == label)
            stats[label] = {
                "total":  len(indices),
                "agreed": agreed,
                "pct":    round((agreed / len(indices)) * 100),
            }
    return stats


def compute_kappa_diagnostics(human_labels, ai_labels, categories=None):
    """
    Compute kappa together with the prevalence and bias indices that explain
    its behaviour, and PABAK (prevalence-adjusted bias-adjusted kappa).

    Cohen's kappa has a known paradox (Feinstein and Cicchetti, 1990): on
    highly skewed marginals, two raters can agree on most items yet still get
    a low kappa. The standard diagnostic toolkit for this situation is:

      - Bias Index (BI):       difference between rater marginals
                               on each category, summarised. BI > 0 means the
                               two raters use the categories at different rates.
      - Prevalence Index (PI): how lopsided the agreement is across categories.
                               High PI inflates the chance-agreement term.
      - PABAK:                 2 * Po - 1. The kappa value that would be observed
                               if both raters' marginals were perfectly balanced
                               (Byrt et al., 1993). Useful as a sanity check when
                               kappa looks suspiciously low.

    These are reported alongside the nominal kappa so a reader can tell whether
    a low kappa reflects genuine disagreement or just a prevalence artefact.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels.
        categories   (list[str] | None): explicit category order, defaults to ERROR_TYPES.

    Returns:
        dict with kappa, pabak, prevalence_index, bias_index, n, plus the
        nominal kappa diagnostics from compute_cohens_kappa.
    """
    if categories is None:
        categories = ERROR_TYPES
    n = len(human_labels)
    base = compute_cohens_kappa(human_labels, ai_labels, categories=categories)

    if n == 0:
        return {**base, "pabak": 0.0, "prevalence_index": 0.0, "bias_index": 0.0}

    po = base["po"]
    pabak = 2.0 * po - 1.0

    # prevalence: max over categories of |2p - 1| where p is the share of
    # items both raters put in that category. bigger number = more skewed.
    # this is why the kappa paradox exists.
    prevalence = 0.0
    for c in categories:
        both = sum(1 for h, a in zip(human_labels, ai_labels) if h == c and a == c)
        p_pos = both / n
        prevalence = max(prevalence, abs(2 * p_pos - 1))

    # bias: average absolute gap between the two raters' marginals
    bias = 0.0
    for c in categories:
        p_human = human_labels.count(c) / n
        p_ai    = ai_labels.count(c) / n
        bias += abs(p_human - p_ai)
    bias = bias / 2.0  # normalised so values lie in [0, 1]

    return {
        **base,
        "pabak":            round(pabak, 4),
        "prevalence_index": round(prevalence, 4),
        "bias_index":       round(bias, 4),
    }


def gwet_ac1(human_labels, ai_labels, categories=None):
    """
    Compute Gwet's AC1 (Gwet, 2008) between two raters.

    Cohen's kappa's chance-agreement term Pe assumes raters assign labels
    independently in proportion to their own marginals, a poor model when
    one category dominates. On highly skewed marginals this makes kappa
    paradoxically low even when raters agree on almost everything (the
    "kappa paradox"; see PABAK / bias / prevalence indices in
    compute_kappa_diagnostics, which diagnose the same issue). AC1 replaces
    Pe with a term built from how *uniformly* items are spread across
    categories rather than the raters' actual marginal distributions, so it
    stays close to the raw observed agreement when one category is common
    and the rest are rare, exactly the shape of most real coding data,
    including CFI data, where PK and RF are typically far more common than
    INT.

        Pe(AC1) = (1 / (q - 1)) * sum_k [ pi_k * (1 - pi_k) ]
        pi_k    = (n_human_k + n_ai_k) / (2n)     (category k's average
                                                     share across both raters)
        AC1     = (Po - Pe(AC1)) / (1 - Pe(AC1))

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels, same length as human_labels.
        categories   (list[str] | None): category set. If None, uses the
                     module-level ERROR_TYPES.

    Returns:
        dict with keys: ac1, interpretation, po, pe_ac1, n, agreements.
        Uses the same interpretation bands as compute_cohens_kappa, for
        consistency within this package, Gwet did not publish AC1-specific
        benchmark bands, and the two statistics share a [-1, 1] scale with
        the same "no better than chance" zero point, so reusing the bands
        here is a project convention, not a claim about Gwet (2008) itself.

    Worked example (hand-derived here, not taken from a published table --
    verify by re-running the arithmetic yourself):
        human = ["CF","CF","CF","CF","CF","CF","CF","CF","CF","RF"]
        ai    = ["CF","CF","CF","CF","CF","CF","CF","CF","RF","RF"]
        categories = ["CF", "RF"]   (2-category subset, for a clean example)

        n = 10, agreements = 9, Po = 0.9

        Cohen's kappa on this data:
            Pe = P(CF)_human * P(CF)_ai + P(RF)_human * P(RF)_ai
               = (9/10)(8/10) + (1/10)(2/10) = 0.72 + 0.02 = 0.74
            kappa = (0.90 - 0.74) / (1 - 0.74) = 0.16 / 0.26 = 0.6154
            -> "Substantial, close to target."

        Gwet's AC1 on the same data:
            pi_CF = (9 + 8) / 20 = 0.85   pi_RF = (1 + 2) / 20 = 0.15
            Pe(AC1) = (1/(2-1)) * [0.85*0.15 + 0.15*0.85] = 0.255
            AC1 = (0.90 - 0.255) / (1 - 0.255) = 0.645 / 0.745 = 0.8658
            -> "Almost Perfect, excellent agreement."

        Same 9/10 raw agreement, same data, two different pictures of
        reliability, kappa is dragged down by the skewed 9:1 marginal,
        AC1 is not. Report both; a paper that only reports the flattering
        one invites exactly the objection this function exists to answer.
    """
    if categories is None:
        categories = ERROR_TYPES
    q = len(categories)
    n = len(human_labels)

    if n == 0:
        return {
            "ac1": 0.0,
            "interpretation": "No data to compute AC1.",
            "po": 0.0, "pe_ac1": 0.0,
            "n": 0, "agreements": 0,
        }
    if q < 2:
        raise ValueError("gwet_ac1 requires at least 2 categories")

    agreements = sum(1 for h, a in zip(human_labels, ai_labels) if h == a)
    po = agreements / n

    pe_ac1 = 0.0
    for label in categories:
        n_human = human_labels.count(label)
        n_ai    = ai_labels.count(label)
        pi_k = (n_human + n_ai) / (2.0 * n)
        pe_ac1 += pi_k * (1.0 - pi_k)
    pe_ac1 = pe_ac1 / (q - 1)

    if pe_ac1 >= 1.0:
        ac1 = 1.0
    else:
        ac1 = (po - pe_ac1) / (1.0 - pe_ac1)

    if ac1 < 0.20:
        interp = "Slight, rubric needs substantial revision before research use."
    elif ac1 < 0.40:
        interp = "Fair, significant revision needed. Review CF vs RF boundary."
    elif ac1 < 0.60:
        interp = "Moderate, improvement needed. Target is kappa >= 0.70."
    elif ac1 < 0.70:
        interp = "Substantial, close to target. Refine ambiguous cases."
    elif ac1 < 0.80:
        interp = "Substantial, research threshold reached! Proceed with validation."
    else:
        interp = "Almost Perfect, excellent agreement."

    return {
        "ac1":            round(ac1, 4),
        "interpretation": interp,
        "po":             round(po, 4),
        "pe_ac1":         round(pe_ac1, 4),
        "n":              n,
        "agreements":     agreements,
    }


def krippendorff_alpha(human_labels, ai_labels, level="nominal", categories=None):
    """
    Compute Krippendorff's alpha for two raters (Krippendorff, 2004).

    Alpha is an alternative inter-rater reliability coefficient. Unlike Cohen's
    kappa it generalises naturally to any number of raters, handles missing
    values, and admits multiple measurement levels:

      - "nominal":  categorical labels (default; equivalent to Scott's pi for two
                    raters with no missing data, and close to Cohen's kappa).
      - "ordinal":  categories have a meaningful order. Disagreements between
                    adjacent ranks are penalised less than between distant ranks.
      - "interval": numeric distances are used as the disagreement metric.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels of the same length.
        level        (str): "nominal" | "ordinal" | "interval".
        categories   (list[str] | None): explicit category order. Required for
                     "ordinal" and "interval" because position defines rank.

    Returns:
        dict with keys alpha, n, level, interpretation.
    """
    if categories is None:
        categories = ERROR_TYPES
    if level not in ("nominal", "ordinal", "interval"):
        raise ValueError(f"level must be 'nominal', 'ordinal', or 'interval'; got {level!r}")

    n = len(human_labels)
    if n != len(ai_labels):
        raise ValueError("label lists must be the same length")
    if n == 0:
        return {"alpha": 0.0, "n": 0, "level": level, "interpretation": "No data."}

    idx = {c: i for i, c in enumerate(categories)}
    if any(h not in idx or a not in idx for h, a in zip(human_labels, ai_labels)):
        raise ValueError("labels contain values outside the provided categories")

    k = len(categories)

    def delta(i, j):
        if level == "nominal":
            return 0 if i == j else 1
        if level == "ordinal":
            d = abs(i - j) / (k - 1) if k > 1 else 0
            return d * d
        # interval
        d = abs(i - j) / (k - 1) if k > 1 else 0
        return d * d

    # Coincidence matrix for two raters: each unit contributes 2 entries
    # (each ordered pair counted), so we double-count consistently with
    # Krippendorff's formulation for fully crossed designs.
    obs_pairs = 0.0
    obs_disagreement = 0.0
    for h, a in zip(human_labels, ai_labels):
        i, j = idx[h], idx[a]
        # 2 units in this pair, so 2 pairs of values
        obs_pairs += 2
        obs_disagreement += delta(i, j) + delta(j, i)

    # Expected disagreement: over the full pool of 2n labels, every pair.
    pool = list(idx[h] for h in human_labels) + list(idx[a] for a in ai_labels)
    N = len(pool)
    counts = [0] * k
    for v in pool:
        counts[v] += 1

    exp_disagreement = 0.0
    for i in range(k):
        for j in range(k):
            exp_disagreement += counts[i] * counts[j] * delta(i, j)
    # Divide by N(N-1) to normalise.
    if N > 1:
        exp_disagreement = exp_disagreement / (N - 1)

    obs_mean = obs_disagreement / obs_pairs if obs_pairs > 0 else 0.0
    exp_mean = exp_disagreement / N if N > 0 else 0.0

    if exp_mean == 0:
        alpha_val = 1.0 if obs_mean == 0 else 0.0
    else:
        alpha_val = 1.0 - obs_mean / exp_mean

    if alpha_val >= 0.80:
        interp = "Reliable for definitive conclusions."
    elif alpha_val >= 0.667:
        interp = "Reliable for tentative conclusions only."
    else:
        interp = "Insufficient reliability for research conclusions."

    return {
        "alpha":          round(alpha_val, 4),
        "n":              n,
        "level":          level,
        "interpretation": interp,
    }


def recommend_sample_size(expected_kappa, ci_half_width=0.10,
                          n_categories=4, confidence=0.95):
    """
    Estimate how many paired-label items a calibration set needs to bound
    Cohen's kappa within a target confidence-interval half-width.

    Uses the standard large-sample variance approximation for Cohen's kappa
    under the assumption of balanced marginals (Donner and Eliasziw, 1992;
    Cantor, 1996). The number returned is a planning aid: small calibration
    sets are always advisable to follow up with bootstrap CI on the realised
    data (see bootstrap_kappa_ci).

    Args:
        expected_kappa (float): the kappa value you expect to observe
                                (use the target threshold if conservative).
        ci_half_width  (float): desired half-width of the 95% CI. Default 0.10.
        n_categories   (int):   number of categories in the taxonomy. Default 4.
        confidence     (float): confidence level. Default 0.95.

    Returns:
        dict with recommended_n, expected_kappa, ci_half_width, confidence,
        and the assumed n_categories. recommended_n is always rounded up.
    """
    import math
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1 exclusive")
    if ci_half_width <= 0 or ci_half_width >= 1:
        raise ValueError("ci_half_width must be between 0 and 1 exclusive")
    if n_categories < 2:
        raise ValueError("n_categories must be at least 2")
    if not -1.0 <= expected_kappa <= 1.0:
        raise ValueError("expected_kappa must lie in [-1, 1]")

    # Two-sided z critical value via Beasley-Springer-Moro (same routine the
    # bootstrap CI uses). Inlined here to keep the dependency footprint nil.
    p = (1 + confidence) / 2.0
    # Use the same qnorm helper logic as bootstrap_kappa_ci for symmetry.
    # Approximate via math.erf-inverse Newton iteration (3 steps is plenty for
    # the standard 95% case).
    z = 0.0
    for _ in range(40):
        cdf = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        pdf = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
        if pdf == 0:
            break
        z = z - (cdf - p) / pdf
    z_alpha = z

    # Variance approximation under balanced marginals.
    pe = 1.0 / n_categories
    po = expected_kappa * (1 - pe) + pe
    po = min(max(po, 0.0), 1.0)
    var_per_item = po * (1 - po) / ((1 - pe) ** 2)
    if var_per_item <= 0:
        n_needed = 1
    else:
        n_needed = math.ceil((z_alpha ** 2) * var_per_item / (ci_half_width ** 2))

    return {
        "recommended_n":  int(n_needed),
        "expected_kappa": expected_kappa,
        "ci_half_width":  ci_half_width,
        "confidence":     confidence,
        "n_categories":   n_categories,
    }


def suggest_prompt_refinements(human_labels, ai_labels, taxonomy=None,
                               categories=None, top_k=3):
    """
    Generate concrete prompt-refinement suggestions from a confusion matrix.

    Inspects every off-diagonal cell of the confusion matrix, ranks them by
    disagreement count, and emits actionable rewrite suggestions for the AI
    prompt. The suggestions are produced from the category definitions in the
    taxonomy, so they include the exact wording that should be sharpened.

    This is intended as a starting point for prompt iteration, not a finished
    prompt. A human researcher should always read and adapt the suggestions
    before applying them.

    Args:
        human_labels (list[str]): rater 1 labels.
        ai_labels    (list[str]): rater 2 labels.
        taxonomy     (dict | None): taxonomy dict (`{code: {name, definition, ...}}`).
                     Defaults to the module-level TAXONOMY.
        categories   (list[str] | None): explicit category order. Defaults to ERROR_TYPES.
        top_k        (int): number of largest off-diagonal cells to address.

    Returns:
        dict with keys:
            top_confusions  - list of (human_code, ai_code, count) tuples, biggest first
            suggestions     - list of suggestion strings, one per top confusion
            report_markdown - a Markdown report ready to paste into a prompt-iteration log
    """
    if categories is None: categories = ERROR_TYPES
    if taxonomy is None:   taxonomy   = TAXONOMY

    matrix = build_confusion_matrix(human_labels, ai_labels, categories=categories)

    # Rank off-diagonal cells.
    cells = []
    for h in categories:
        for a in categories:
            if h != a and matrix[h][a] > 0:
                cells.append((h, a, matrix[h][a]))
    cells.sort(key=lambda t: t[2], reverse=True)
    top = cells[:top_k]

    suggestions = []
    lines = []
    lines.append("# Prompt refinement suggestions")
    lines.append("")
    lines.append("Generated by `suggest_prompt_refinements` from "
                 "the most frequent off-diagonal cells of the confusion matrix. "
                 "Each suggestion is a starting point: read it, adapt the wording, "
                 "and re-run a calibration pass before treating the new prompt as final.")
    lines.append("")

    if not top:
        lines.append("No off-diagonal disagreements were found. The rubric is fully "
                     "calibrated on this sample.")
        return {"top_confusions": [], "suggestions": [], "report_markdown": "\n".join(lines)}

    for h_code, a_code, count in top:
        h_name = taxonomy.get(h_code, {}).get("name", h_code)
        a_name = taxonomy.get(a_code, {}).get("name", a_code)
        h_def  = taxonomy.get(h_code, {}).get("definition", "(no definition)")
        a_def  = taxonomy.get(a_code, {}).get("definition", "(no definition)")

        suggestion = (
            f"The AI is labelling {count} item(s) as **{a_code} ({a_name})** that "
            f"the human labels as **{h_code} ({h_name})**. The two definitions are:\n"
            f"- {h_code}: {h_def}\n"
            f"- {a_code}: {a_def}\n"
            f"\nTo tighten the boundary, add an instruction to the AI prompt that names "
            f"the {h_code}-vs-{a_code} contrast explicitly. For example: "
            f"\"Prefer {h_code} over {a_code} when the wrong answer matches the {h_code} "
            f"definition above and lacks the specific feature that makes a choice {a_code}. "
            f"Only choose {a_code} when [restate the {a_code} feature].\""
        )
        suggestions.append(suggestion)
        lines.append(f"## {count} item(s): human {h_code} -> AI {a_code}")
        lines.append("")
        lines.append(suggestion)
        lines.append("")

    return {
        "top_confusions":  top,
        "suggestions":     suggestions,
        "report_markdown": "\n".join(lines),
    }


def fleiss_kappa(rating_matrix, categories=None):
    """
    Compute Fleiss's kappa for three or more raters (Fleiss, 1971).

    Cohen's kappa is defined for exactly two raters. When you have a panel
    (three or more raters), Fleiss's kappa is the standard generalisation.
    The same Landis and Koch interpretation thresholds apply.

    Input shape:
        rating_matrix is a list of rows, one row per item. Each row is itself
        a dict mapping category code -> number of raters who chose that code.
        Every row must sum to the same total number of raters.

        Example with 3 raters on 4 items and 4 categories:
            rating_matrix = [
                {"RF": 0, "PK": 0, "CF": 3, "INT": 0},  # all 3 raters: CF
                {"RF": 1, "PK": 2, "CF": 0, "INT": 0},  # split 1 RF / 2 PK
                ...
            ]

    Args:
        rating_matrix (list[dict[str, int]]): per-item rater counts.
        categories    (list[str] | None): explicit category order; defaults to ERROR_TYPES.

    Returns:
        dict with kappa, n_items, n_raters, n_categories, interpretation.
    """
    if categories is None: categories = ERROR_TYPES
    if not rating_matrix:
        return {"kappa": 0.0, "n_items": 0, "n_raters": 0,
                "n_categories": len(categories), "interpretation": "No data."}

    # Validate: every row has the same total
    totals = [sum(row.get(c, 0) for c in categories) for row in rating_matrix]
    if len(set(totals)) != 1:
        raise ValueError("every item must be rated by the same number of raters")
    n_raters = totals[0]
    if n_raters < 3:
        raise ValueError("Fleiss kappa requires at least 3 raters; for 2 raters use compute_cohens_kappa")

    n_items = len(rating_matrix)
    k = len(categories)

    # Per-item agreement P_i = (sum_j n_ij*(n_ij-1)) / (n_raters*(n_raters-1))
    p_i = []
    for row in rating_matrix:
        s = sum(row.get(c, 0) * (row.get(c, 0) - 1) for c in categories)
        p_i.append(s / (n_raters * (n_raters - 1)))
    p_bar = sum(p_i) / n_items

    # Marginal proportions over all items
    totals_per_cat = {c: sum(row.get(c, 0) for row in rating_matrix) for c in categories}
    total_assignments = n_items * n_raters
    p_j = {c: totals_per_cat[c] / total_assignments for c in categories}
    p_e = sum(p_j[c] ** 2 for c in categories)

    if p_e >= 1.0:
        kappa = 1.0 if p_bar == 1.0 else 0.0
    else:
        kappa = (p_bar - p_e) / (1.0 - p_e)

    if kappa < 0.20:
        interp = "Slight."
    elif kappa < 0.40:
        interp = "Fair."
    elif kappa < 0.60:
        interp = "Moderate."
    elif kappa < 0.80:
        interp = "Substantial."
    else:
        interp = "Almost perfect."

    return {
        "kappa":         round(kappa, 4),
        "n_items":       n_items,
        "n_raters":      n_raters,
        "n_categories":  k,
        "interpretation": interp,
    }

