"""
Can the AI replace one of my human coders?

That is the question I kept running into. Cohen's kappa tells me how much
the AI and I agree. It does not tell me whether I am allowed to drop a
human coder and use the AI's labels instead. Every paper I read either
skipped the question or picked a kappa cutoff out of the air.

Calderon, Reichart and Dror (ACL 2025) proposed a proper statistical
answer, the Alternative Annotator Test, or alt-test. The method is
theirs, not mine. Their reference code is a notebook that needs numpy
and scipy. This module is a pure standard-library version of it, wired
into the rest of ConfusionMapper so the CSVs, the kappa numbers and the
reports all line up.

How the test works, in plain words:

  1. Take one human coder out of the panel.
  2. For every item, ask: does the AI agree with the remaining coders
     at least as well as the coder I took out does?
  3. Turn that into a win probability for the AI (rho_f) and for the
     coder (rho_h).
  4. Run a one-sided paired t-test of "the coder is better than the AI
     by more than epsilon". Epsilon is a cost-benefit allowance, since
     the AI is cheaper and faster than a person.
  5. Repeat for every coder, correct the p-values for multiple testing
     with Benjamini-Yekutieli, and count how many coders the AI beat.
     That fraction is the winning rate. If it is at least 0.5, the AI
     passes.

The average of rho_f over all coders is the advantage probability: the
chance that the AI's label is as good as or better than a randomly
chosen human coder's. The authors suggest using it to compare AI judges
or prompts against each other.

Everything here follows the authors' paper and reference notebook
(github.com/nitaytech/AltTest), including their tie rule, their default
of at least 2 coders per item and 30 items per coder, and their epsilon
rule of thumb: 0.2 for experts, 0.15 for skilled coders, 0.1 for crowd
workers. I cross-checked the p-values against scipy while building this
and the test suite does the same whenever scipy happens to be installed.

Reference:
    Calderon, N., Reichart, R., and Dror, R. (2025). The Alternative
    Annotator Test for LLM-as-a-Judge: How to Statistically Justify
    Replacing Human Annotators with LLMs. Proceedings of the 63rd
    Annual Meeting of the Association for Computational Linguistics
    (Volume 1: Long Papers), pages 16051-16081.
    https://aclanthology.org/2025.acl-long.782/
"""

import csv
import math
import random

from .stats import compute_cohens_kappa


CITATION = (
    "Calderon, N., Reichart, R., and Dror, R. (2025). The Alternative "
    "Annotator Test for LLM-as-a-Judge: How to Statistically Justify "
    "Replacing Human Annotators with LLMs. In Proceedings of the 63rd "
    "Annual Meeting of the Association for Computational Linguistics "
    "(Volume 1: Long Papers), pages 16051-16081. "
    "https://aclanthology.org/2025.acl-long.782/"
)

# the authors' rule of thumb for epsilon (paper FAQ and README)
EPSILON_PRESETS = {
    "expert":  0.20,
    "skilled": 0.15,
    "crowd":   0.10,
}


# -----------------------------------------------------------------------------
# Student's t distribution, no scipy
# -----------------------------------------------------------------------------
#
# The p-value of a t-test needs the t CDF. scipy has it, but I did not want
# a 40 MB dependency for one function. The t CDF can be written in terms of
# the regularized incomplete beta function, and that has a classic
# continued-fraction form (the modified Lentz method, as in Numerical
# Recipes). The tests check it against exact closed forms for 1 and 2
# degrees of freedom, against printed t-table critical values, and against
# scipy itself when it is available.

def _betacf(a, b, x, max_iter=300, eps=3e-14):
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < tiny:
        d = tiny
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < tiny:
            d = tiny
        c = 1.0 + aa / c
        if abs(c) < tiny:
            c = tiny
        d = 1.0 / d
        step = d * c
        h *= step
        if abs(step - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a, b, x):
    """I_x(a, b) for a, b > 0 and 0 <= x <= 1."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
                 + a * math.log(x) + b * math.log1p(-x))
    front = math.exp(log_front)
    # the continued fraction converges fast on this side of the mean,
    # use the symmetry I_x(a, b) = 1 - I_(1-x)(b, a) on the other side
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_cdf(t, df):
    """
    P(T <= t) for Student's t with `df` degrees of freedom.

    Handles +/- infinity. Returns nan for a nan input.
    """
    if df <= 0:
        raise ValueError("degrees of freedom must be positive")
    if math.isnan(t):
        return float("nan")
    if math.isinf(t):
        return 1.0 if t > 0 else 0.0
    x = df / (df + t * t)
    tail = 0.5 * regularized_incomplete_beta(df / 2.0, 0.5, x)
    return 1.0 - tail if t >= 0 else tail


def one_sided_t_test_less(values, popmean):
    """
    One-sample t-test of H0: mean >= popmean against H1: mean < popmean.

    Same thing as scipy.stats.ttest_1samp(values, popmean,
    alternative="less"), apart from one edge case. When every value is
    identical the standard error is zero. Like scipy, a mean below popmean
    then gives t = -inf and p = 0, and a mean above gives t = inf and p = 1.
    When the mean sits exactly on popmean scipy returns nan, and I return
    p = 1 instead: there is no evidence against the null, and a nan would
    only confuse the multiple-testing step afterwards.

    Returns:
        dict with mean, sd, t, df, p_value.
    """
    n = len(values)
    if n < 2:
        raise ValueError("a t-test needs at least 2 values")
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    sd = math.sqrt(var)
    df = n - 1
    if sd == 0.0:
        if mean < popmean:
            t, p = float("-inf"), 0.0
        else:
            t = float("inf") if mean > popmean else float("nan")
            p = 1.0
    else:
        t = (mean - popmean) / (sd / math.sqrt(n))
        p = t_cdf(t, df)
    return {"mean": mean, "sd": sd, "t": t, "df": df, "p_value": p}


# -----------------------------------------------------------------------------
# Multiple-testing correction
# -----------------------------------------------------------------------------

def benjamini_yekutieli(p_values, q=0.05):
    """
    Benjamini-Yekutieli (2001) step-up procedure. Controls the false
    discovery rate at level q even when the tests are dependent, which they
    are here: every coder's score is computed against the other coders.

    Sort the p-values, find the largest k with
        p_(k) <= (k / m) * q / H_m,   H_m = 1 + 1/2 + ... + 1/m
    and reject the k smallest. Step-up means a p-value that misses its own
    threshold can still be rejected if a larger one further down passes.

    Returns:
        list[int]: indices (into the original list) of rejected hypotheses,
        in ascending p-value order.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    harmonic = sum(1.0 / k for k in range(1, m + 1))
    last = -1
    for rank, idx in enumerate(order, start=1):
        if p_values[idx] <= (rank / m) * (q / harmonic):
            last = rank
    return order[:last] if last > 0 else []


# -----------------------------------------------------------------------------
# Alignment scores
# -----------------------------------------------------------------------------

def accuracy_score(prediction, annotations):
    """Share of the other coders who gave exactly this label."""
    return sum(1 for a in annotations if a == prediction) / len(annotations)


def neg_rmse_score(prediction, annotations):
    """Negative root mean squared distance to the other coders. For ratings."""
    p = float(prediction)
    return -math.sqrt(sum((p - float(a)) ** 2 for a in annotations) / len(annotations))


SCORING_FUNCTIONS = {
    "accuracy": accuracy_score,
    "neg_rmse": neg_rmse_score,
}


# -----------------------------------------------------------------------------
# The test itself
# -----------------------------------------------------------------------------

def alt_test(llm_annotations, human_annotations, scoring="accuracy",
             epsilon=0.2, q_fdr=0.05, min_humans_per_instance=2,
             min_instances_per_human=30, pass_threshold=0.5):
    """
    Run the Alternative Annotator Test for one AI annotator.

    Args:
        llm_annotations (dict): item_id -> the AI's label.
        human_annotations (dict): coder_id -> {item_id -> label}. Coders do
            not have to label the same items.
        scoring (str | callable): "accuracy" for categories (CFI codes,
            yes/no), "neg_rmse" for numeric ratings, or your own function
            f(prediction, list_of_other_labels) -> float, higher is better.
        epsilon (float): the cost-benefit allowance. See EPSILON_PRESETS.
            Decide this before you look at the result.
        q_fdr (float): target false discovery rate for Benjamini-Yekutieli.
        min_humans_per_instance (int): items with fewer human labels are
            dropped. The leave-one-out step needs at least 2.
        min_instances_per_human (int): coders with fewer usable items are
            skipped. 30 is the authors' default, below that the t-test's
            normality assumption gets shaky.
        pass_threshold (float): winning rate needed to pass. The authors
            use 0.5, a stricter value is reasonable in high-stakes work.

    Returns:
        dict with per_annotator results, winning_rate, advantage_probability,
        passed, verdict, plus what was dropped or skipped and any warnings.
    """
    if isinstance(scoring, str):
        if scoring not in SCORING_FUNCTIONS:
            raise ValueError(f"unknown scoring {scoring!r}, "
                             f"expected one of {sorted(SCORING_FUNCTIONS)}")
        score_fn, scoring_name = SCORING_FUNCTIONS[scoring], scoring
    elif callable(scoring):
        score_fn, scoring_name = scoring, getattr(scoring, "__name__", "custom")
    else:
        raise ValueError("scoring must be a name or a function")
    if not 0.0 <= epsilon < 1.0:
        raise ValueError("epsilon must be in [0, 1)")
    if not 0.0 < q_fdr < 1.0:
        raise ValueError("q_fdr must be between 0 and 1")
    if min_humans_per_instance < 2:
        raise ValueError("min_humans_per_instance must be at least 2, "
                         "the leave-one-out step needs someone left over")
    if min_instances_per_human < 2:
        raise ValueError("min_instances_per_human must be at least 2")
    if len(human_annotations) < 2:
        raise ValueError("the alt-test needs at least 2 human coders "
                         "(the authors recommend 3 or more)")

    # which coders labelled each item
    coders_per_item = {}
    for coder, labels in human_annotations.items():
        for item in labels:
            coders_per_item.setdefault(item, []).append(coder)

    usable = {item for item, coders in coders_per_item.items()
              if len(coders) >= min_humans_per_instance and item in llm_annotations}
    dropped = sorted(set(coders_per_item) - usable, key=str)

    per_annotator, skipped = [], []
    for coder, labels in human_annotations.items():
        items = [i for i in labels if i in usable]
        if len(items) < min_instances_per_human:
            skipped.append({"annotator": coder, "n_instances": len(items)})
            continue

        w_llm, w_human = [], []
        for item in items:
            others = [human_annotations[c][item] for c in coders_per_item[item] if c != coder]
            s_llm = score_fn(llm_annotations[item], others)
            s_human = score_fn(labels[item], others)
            # the authors' tie rule: a tie counts for both sides
            w_llm.append(1 if s_llm >= s_human else 0)
            w_human.append(1 if s_human >= s_llm else 0)

        d = [h - f for h, f in zip(w_human, w_llm)]
        test = one_sided_t_test_less(d, epsilon)
        per_annotator.append({
            "annotator":   coder,
            "n_instances": len(items),
            "rho_llm":     sum(w_llm) / len(items),
            "rho_human":   sum(w_human) / len(items),
            "mean_d":      test["mean"],
            "sd_d":        test["sd"],
            "t":           test["t"],
            "df":          test["df"],
            "p_value":     test["p_value"],
            "rejected":    False,
        })

    rejected = benjamini_yekutieli([r["p_value"] for r in per_annotator], q_fdr)
    for idx in rejected:
        per_annotator[idx]["rejected"] = True

    warnings = []
    if len(human_annotations) < 3:
        warnings.append("Only 2 human coders. The authors recommend at least 3, "
                        "with 2 the test just asks which single coder the AI "
                        "sides with, there is no consensus to compare against.")
    if min_instances_per_human < 30:
        warnings.append(f"min_instances_per_human is {min_instances_per_human}. "
                        "Below 30 items the t-test's normality assumption is "
                        "shaky and the authors suggest a non-parametric test.")
    thin = [r["annotator"] for r in per_annotator if r["n_instances"] < 50]
    if thin:
        warnings.append("Fewer than 50 items for: " + ", ".join(map(str, thin)) +
                        ". The authors found 50 to 100 items per coder is "
                        "usually enough, fewer items means less power.")
    if skipped:
        warnings.append(f"{len(skipped)} coder(s) skipped for having fewer than "
                        f"{min_instances_per_human} usable items.")
    if dropped:
        warnings.append(f"{len(dropped)} item(s) dropped: fewer than "
                        f"{min_humans_per_instance} human labels or no AI label.")

    n_tested = len(per_annotator)
    if n_tested == 0:
        winning_rate = advantage = None
        passed = False
        warnings.append("No coder had enough usable items, so nothing was tested.")
    else:
        winning_rate = len(rejected) / n_tested
        advantage = sum(r["rho_llm"] for r in per_annotator) / n_tested
        passed = winning_rate >= pass_threshold

    result = {
        "method":                  "alt-test (Calderon, Reichart and Dror, ACL 2025)",
        "scoring":                 scoring_name,
        "epsilon":                 epsilon,
        "q_fdr":                   q_fdr,
        "pass_threshold":          pass_threshold,
        "n_humans_total":          len(human_annotations),
        "n_humans_tested":         n_tested,
        "n_instances_used":        len(usable),
        "per_annotator":           per_annotator,
        "winning_rate":            winning_rate,
        "advantage_probability":   advantage,
        "passed":                  passed,
        "dropped_instances":       dropped,
        "skipped_annotators":      skipped,
        "warnings":                warnings,
    }
    result["verdict"] = _verdict(result)
    return result


def _verdict(r):
    if r["winning_rate"] is None:
        return "Not tested: no coder had enough usable items."
    beaten = sum(1 for a in r["per_annotator"] if a["rejected"])
    total = r["n_humans_tested"]
    if r["passed"]:
        return (f"PASSED. After FDR correction the AI beat {beaten} of {total} "
                f"human coders (winning rate {r['winning_rate']:.2f}) with "
                f"epsilon = {r['epsilon']}. Under the alt-test's rule this "
                f"justifies using the AI's labels in place of a human coder, "
                f"for this task, this coder pool and this epsilon.")
    return (f"FAILED. After FDR correction the AI beat {beaten} of {total} "
            f"human coders (winning rate {r['winning_rate']:.2f}, needs "
            f"{r['pass_threshold']}) with epsilon = {r['epsilon']}. Keep the "
            f"human coders for this task.")


def compare_judges(llm_annotations_by_name, human_annotations, **kwargs):
    """
    Run the alt-test for several AI judges (different models, or the same
    model with different prompts) against the same human panel, and rank
    them by advantage probability, which is what the authors recommend for
    choosing between judges. The winning rate is still reported for each,
    since that is what decides pass or fail.

    Returns:
        dict: ranking (list, best first) and results (name -> alt_test dict).
    """
    if not llm_annotations_by_name:
        raise ValueError("need at least one AI judge to compare")
    results = {name: alt_test(llm, human_annotations, **kwargs)
               for name, llm in llm_annotations_by_name.items()}

    def key(name):
        ap = results[name]["advantage_probability"]
        return (ap is None, -(ap or 0.0), str(name))

    ranking = [{
        "judge":                 name,
        "advantage_probability": results[name]["advantage_probability"],
        "winning_rate":          results[name]["winning_rate"],
        "passed":                results[name]["passed"],
    } for name in sorted(results, key=key)]
    return {"ranking": ranking, "results": results}


# -----------------------------------------------------------------------------
# Human reliability, which the authors say you must report alongside
# -----------------------------------------------------------------------------

def human_agreement_summary(human_annotations, categories=None):
    """
    Mean pairwise Cohen's kappa among the human coders, each pair computed
    on the items both of them labelled. The authors' reporting checklist
    asks for this, because epsilon only makes sense relative to how reliable
    the humans are in the first place.
    """
    coders = list(human_annotations)
    if categories is None:
        categories = sorted({str(v) for labels in human_annotations.values()
                             for v in labels.values()})
    pairs = []
    for i in range(len(coders)):
        for j in range(i + 1, len(coders)):
            a, b = human_annotations[coders[i]], human_annotations[coders[j]]
            shared = [item for item in a if item in b]
            if len(shared) < 2:
                continue
            k = compute_cohens_kappa([str(a[x]) for x in shared],
                                     [str(b[x]) for x in shared],
                                     categories=categories)
            pairs.append({"pair": f"{coders[i]}|{coders[j]}",
                          "n_shared": len(shared), "kappa": k["kappa"]})
    mean_k = round(sum(p["kappa"] for p in pairs) / len(pairs), 4) if pairs else None
    return {"mean_pairwise_kappa": mean_k, "pairs": pairs}


# -----------------------------------------------------------------------------
# Loading data
# -----------------------------------------------------------------------------

# "ai", "model" and "judge" only count as a whole word or a prefix like
# ai_ / model- so a coder called Aisha or Modesto is left alone
_AI_NAME_STRICT = ("ai", "model", "judge")
_AI_NAME_LOOSE = ("llm", "gpt", "gemini", "llama", "mistral")


def _looks_like_ai_column(name):
    """True for names like ai_label, ai-v2, llm_out, gpt4o, model_b, judge_1."""
    low = name.strip().lower()
    for hint in _AI_NAME_STRICT:
        if low == hint or low.startswith(hint + "_") or low.startswith(hint + "-"):
            return True
    return any(low.startswith(hint) for hint in _AI_NAME_LOOSE)


def load_alttest_csv(path, ai_columns, id_column="item_id", human_columns=None):
    """
    Read a wide CSV: one row per item, one column per human coder, and one
    or more AI columns. A blank cell means that coder did not label that
    item, which the test handles fine.

        item_id,coder_A,coder_B,coder_C,ai_prompt_v1
        Q1_D1,CF,CF,PK,CF
        Q1_D2,RF,,RF,RF

    Returns:
        (human_annotations, llm_annotations_by_name), both as dicts of dicts.
    """
    if isinstance(ai_columns, str):
        ai_columns = [ai_columns]
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if id_column not in fields:
            raise ValueError(f"no {id_column!r} column in {path}, found {fields}")
        missing = [c for c in ai_columns if c not in fields]
        if missing:
            raise ValueError(f"AI column(s) {missing} not found in {path}")
        if human_columns is None:
            human_columns = [c for c in fields if c != id_column and c not in ai_columns]
            # I hit this on my own example file: asking for one AI column
            # quietly turned the *other* AI column into a fourth human coder.
            # Nothing crashed, the numbers just became wrong. So if a leftover
            # column looks like machine output, stop and make the user say
            # which columns are human.
            suspicious = [c for c in human_columns if _looks_like_ai_column(c)]
            if suspicious:
                raise ValueError(
                    f"column(s) {suspicious} look like AI output but would be "
                    f"counted as human coders. Pass them as AI columns, or list "
                    f"the human coders explicitly (human_columns / --human-columns)."
                )
        else:
            absent = [c for c in human_columns if c not in fields]
            if absent:
                raise ValueError(f"human column(s) {absent} not found in {path}")
        if len(human_columns) < 2:
            raise ValueError(f"need at least 2 human coder columns, found {human_columns}")

        humans = {c: {} for c in human_columns}
        llms = {c: {} for c in ai_columns}
        seen = set()
        for row in reader:
            item = (row.get(id_column) or "").strip()
            if not item:
                continue
            if item in seen:
                raise ValueError(f"duplicate {id_column} {item!r} in {path}")
            seen.add(item)
            for c in human_columns:
                v = (row.get(c) or "").strip()
                if v:
                    humans[c][item] = v
            for c in ai_columns:
                v = (row.get(c) or "").strip()
                if v:
                    llms[c][item] = v
    return humans, llms


# -----------------------------------------------------------------------------
# Synthetic panels and power planning
# -----------------------------------------------------------------------------
#
# The authors' appendix C answers "how many items do I need?" by simulation:
# draw a true label for each item, let each coder (and the AI) report the
# true label with probability 1 - noise and otherwise draw from the label
# prior. I use the same generative model, written with the random module so
# there is still no numpy.

def generate_synthetic_panel(n_items, n_coders=3, categories=("RF", "PK", "CF", "INT"),
                             coder_noise=0.3, ai_noises=(0.3,), seed=None):
    """
    Simulate a coded panel.

    Each item gets a true label drawn from a random prior (a flat Dirichlet
    over the categories). Each coder reports a label from
        noise * prior + (1 - noise) * [true label]
    and so does each AI, with its own noise. noise = 0 is a perfect coder,
    noise = 1 is pure guessing from the base rates.

    Returns:
        dict with gold (item -> label), humans (coder -> {item -> label}),
        ais (name -> {item -> label}) and the prior used.
    """
    if n_items < 1 or n_coders < 1:
        raise ValueError("n_items and n_coders must be positive")
    cats = list(categories)
    if len(cats) < 2:
        raise ValueError("need at least 2 categories")
    for nz in [coder_noise, *ai_noises]:
        if not 0.0 <= nz <= 1.0:
            raise ValueError("noise values must be in [0, 1]")
    rng = random.Random(seed)
    draws = [rng.gammavariate(1.0, 1.0) for _ in cats]
    total = sum(draws)
    prior = [g / total for g in draws]

    def noisy(true_idx, noise):
        weights = [noise * p for p in prior]
        weights[true_idx] += 1.0 - noise
        return cats[rng.choices(range(len(cats)), weights=weights)[0]]

    gold, humans = {}, {f"coder_{k + 1}": {} for k in range(n_coders)}
    ais = {f"ai_{k + 1}": {} for k in range(len(ai_noises))}
    for i in range(n_items):
        item = f"item_{i + 1:04d}"
        t = rng.choices(range(len(cats)), weights=prior)[0]
        gold[item] = cats[t]
        for coder in humans:
            humans[coder][item] = noisy(t, coder_noise)
        for (name, nz) in zip(ais, ai_noises):
            ais[name][item] = noisy(t, nz)
    return {"gold": gold, "humans": humans, "ais": ais,
            "prior": dict(zip(cats, prior))}


def simulate_alt_test_power(n_items_grid=(30, 50, 75, 100, 150, 200), n_coders=3,
                            n_categories=4, coder_noise=0.3, ai_noise=0.3,
                            epsilon=0.15, q_fdr=0.05, n_simulations=200,
                            target_power=0.8, seed=None):
    """
    Before you pay coders to label a calibration set, estimate how often an
    AI of a given quality would pass the alt-test at each sample size.

    Every simulation draws a fresh prior and a fresh panel, then runs the
    alt-test on the first n items for each n in the grid. Alongside the pass
    rates it reports the human kappa and AI-human kappa that your noise
    settings actually imply, so you can check them against the reliability
    you expect from your own coders instead of trusting a lookup table.

    Returns:
        dict with one row per n (pass_rate, mean winning rate, mean
        advantage probability), the implied kappas, and recommended_n, the
        smallest n whose pass rate reaches target_power (None if none do).
    """
    grid = sorted(set(int(n) for n in n_items_grid))
    if not grid or grid[0] < 30:
        raise ValueError("every n in the grid must be at least 30, below that "
                         "the t-test behind the alt-test is not appropriate")
    if n_simulations < 1:
        raise ValueError("n_simulations must be at least 1")
    if n_coders < 2:
        raise ValueError("need at least 2 coders")
    cats = [f"C{k + 1}" for k in range(n_categories)]
    rng = random.Random(seed)

    tallies = {n: {"passed": 0, "wr": [], "ap": []} for n in grid}
    human_kappas, ai_kappas = [], []
    for _ in range(n_simulations):
        panel = generate_synthetic_panel(grid[-1], n_coders, cats, coder_noise,
                                         (ai_noise,), seed=rng.randrange(2 ** 31))
        humans, ai = panel["humans"], panel["ais"]["ai_1"]

        coders = list(humans)
        items = list(panel["gold"])
        for i in range(len(coders)):
            for j in range(i + 1, len(coders)):
                human_kappas.append(compute_cohens_kappa(
                    [humans[coders[i]][x] for x in items],
                    [humans[coders[j]][x] for x in items], categories=cats)["kappa"])
            ai_kappas.append(compute_cohens_kappa(
                [humans[coders[i]][x] for x in items],
                [ai[x] for x in items], categories=cats)["kappa"])

        for n in grid:
            subset = items[:n]
            h_sub = {c: {x: humans[c][x] for x in subset} for c in coders}
            a_sub = {x: ai[x] for x in subset}
            r = alt_test(a_sub, h_sub, epsilon=epsilon, q_fdr=q_fdr,
                         min_instances_per_human=30)
            tallies[n]["passed"] += 1 if r["passed"] else 0
            tallies[n]["wr"].append(r["winning_rate"])
            tallies[n]["ap"].append(r["advantage_probability"])

    rows = [{
        "n_items":                    n,
        "pass_rate":                  round(tallies[n]["passed"] / n_simulations, 4),
        "mean_winning_rate":          round(sum(tallies[n]["wr"]) / n_simulations, 4),
        "mean_advantage_probability": round(sum(tallies[n]["ap"]) / n_simulations, 4),
    } for n in grid]
    recommended = next((row["n_items"] for row in rows
                        if row["pass_rate"] >= target_power), None)
    return {
        "settings": {
            "n_coders": n_coders, "n_categories": n_categories,
            "coder_noise": coder_noise, "ai_noise": ai_noise,
            "epsilon": epsilon, "q_fdr": q_fdr,
            "n_simulations": n_simulations, "target_power": target_power,
            "seed": seed,
        },
        "implied_human_kappa":    round(sum(human_kappas) / len(human_kappas), 4),
        "implied_ai_human_kappa": round(sum(ai_kappas) / len(ai_kappas), 4),
        "rows":                   rows,
        "recommended_n":          recommended,
        "note": ("Simulated with the generative model from the authors' "
                 "appendix C. It tells you about an AI of the noise level you "
                 "typed in, not about your actual AI. Treat it as a planning "
                 "estimate, not a promise."),
    }


# -----------------------------------------------------------------------------
# Reports
# -----------------------------------------------------------------------------

DRAFT_NOTICE = ("DRAFT, requires human review. The numbers come from "
                "ConfusionMapper's tested functions. The wording around them "
                "is a starting point, rewrite it in your own words.")


def _fmt(x, digits=3):
    if x is None:
        return "n/a"
    if isinstance(x, float):
        if math.isinf(x):
            return "-inf" if x < 0 else "inf"
        if math.isnan(x):
            return "n/a"
        if 0 < abs(x) < 10 ** -digits:
            return f"{x:.1e}"
        return f"{x:.{digits}f}"
    return str(x)


def format_alttest_report(result, human_agreement=None, judge_name="AI",
                          annotator_profile=None, title=None, include_notice=True):
    """
    Markdown report for one alt-test result: the verdict, the settings,
    a per-coder table, the authors' reporting checklist with what is
    already filled in, a draft methods paragraph, and the citation.
    """
    r = result
    lines = [f"# {title or 'Can the AI replace a human coder? Alt-test report'}", ""]
    if include_notice:
        lines += [f"*{DRAFT_NOTICE}*", ""]
    lines += ["## Verdict", "", f"**{judge_name}:** {r['verdict']}", ""]

    lines += ["## Settings", "",
              "| Setting | Value |", "|---|---|",
              f"| Scoring function | {r['scoring']} |",
              f"| Epsilon (cost-benefit allowance) | {r['epsilon']}"
              + (f" ({annotator_profile} coders preset)" if annotator_profile else "") + " |",
              f"| FDR level q (Benjamini-Yekutieli) | {r['q_fdr']} |",
              f"| Winning rate needed to pass | {r['pass_threshold']} |",
              f"| Items used | {r['n_instances_used']} |",
              f"| Human coders tested | {r['n_humans_tested']} of {r['n_humans_total']} |",
              ""]

    lines += ["## Coder by coder", "",
              "rho (AI) is how often the AI agreed with the remaining coders at "
              "least as well as this coder did. rho (coder) is the reverse.", "",
              "| Coder | Items | rho (AI) | rho (coder) | t | p | Beaten after FDR? |",
              "|---|---|---|---|---|---|---|"]
    for a in r["per_annotator"]:
        lines.append(f"| {a['annotator']} | {a['n_instances']} | {_fmt(a['rho_llm'])} | "
                     f"{_fmt(a['rho_human'])} | {_fmt(a['t'], 2)} | {_fmt(a['p_value'], 4)} | "
                     f"{'yes' if a['rejected'] else 'no'} |")
    for s in r["skipped_annotators"]:
        lines.append(f"| {s['annotator']} | {s['n_instances']} | | | | | skipped |")
    lines += ["",
              f"**Winning rate:** {_fmt(r['winning_rate'], 2)}. "
              f"**Advantage probability:** {_fmt(r['advantage_probability'], 3)}, "
              "the chance the AI's label is as good as or better than a randomly "
              "chosen human coder's. Use it to compare AI judges or prompts.", ""]

    if human_agreement is not None:
        lines += ["## Human reliability", ""]
        mk = human_agreement.get("mean_pairwise_kappa")
        lines.append(f"Mean pairwise Cohen's kappa among the human coders: {_fmt(mk, 3)}.")
        for p in human_agreement.get("pairs", []):
            lines.append(f"- {p['pair']}: kappa = {_fmt(p['kappa'], 3)} on {p['n_shared']} shared items")
        lines.append("")

    if r["warnings"]:
        lines += ["## Things to look at", ""] + [f"- {w}" for w in r["warnings"]] + [""]

    lines += ["## Reporting checklist", "",
              "The authors ask for six things when you report an alt-test. "
              "Here is where each one stands.", "",
              "1. Who the human coders are, their expertise, guidelines and "
              "training. *You need to write this.*",
              f"2. Why you chose epsilon = {r['epsilon']}. *You need to write this, "
              "and ideally it was fixed in your preregistration before you saw "
              "these numbers.*",
              f"3. How many items: {r['n_instances_used']} were used. *Say how they "
              "were sampled.*",
              "4. Reliability of the human coders: "
              + ("filled in above." if human_agreement is not None else
                 "*not computed here, add a kappa or correlation.*"),
              f"5. Advantage probability of each AI judge you compared: "
              f"{judge_name} = {_fmt(r['advantage_probability'], 3)}.",
              f"6. Winning rate of the judge you picked: {_fmt(r['winning_rate'], 2)}.",
              ""]

    lines += ["## A note on epsilon", "",
              "Pick epsilon before you run this. Re-running with a bigger epsilon "
              "until the AI passes is exactly the kind of flexibility the test "
              "exists to remove. The authors' rule of thumb is 0.2 for experts, "
              "0.15 for skilled coders and 0.1 for crowd workers, and smaller "
              "when the humans do not agree with each other much.", ""]

    beaten = sum(1 for a in r["per_annotator"] if a["rejected"])
    lines += ["## Draft methods paragraph", "",
              f"To decide whether the AI annotator could replace a human coder we "
              f"ran the Alternative Annotator Test (Calderon et al., 2025) on "
              f"{r['n_instances_used']} items coded by {r['n_humans_total']} human "
              f"coders, using {r['scoring']} as the alignment score, epsilon = "
              f"{r['epsilon']}, and Benjamini-Yekutieli correction at q = {r['q_fdr']}. "
              f"The AI outperformed {beaten} of {r['n_humans_tested']} coders "
              f"(winning rate = {_fmt(r['winning_rate'], 2)}; advantage probability = "
              f"{_fmt(r['advantage_probability'], 2)}) and therefore "
              f"{'passed' if r['passed'] else 'did not pass'} the test.", "",
              "## Reference", "", CITATION, "",
              "Computed with ConfusionMapper's `alttest` module, a standard-library "
              "implementation of the procedure above."]
    return "\n".join(lines)


def format_comparison_report(comparison, human_agreement=None, annotator_profile=None):
    """Markdown report for compare_judges(): a ranking, then one section per judge."""
    lines = ["# Which AI judge should replace a human coder?", "",
             f"*{DRAFT_NOTICE}*", "",
             "Ranked by advantage probability, as the authors recommend for "
             "comparing judges. Pass or fail still comes from the winning rate.", "",
             "| Rank | Judge | Advantage probability | Winning rate | Passed |",
             "|---|---|---|---|---|"]
    for k, row in enumerate(comparison["ranking"], start=1):
        lines.append(f"| {k} | {row['judge']} | {_fmt(row['advantage_probability'], 3)} | "
                     f"{_fmt(row['winning_rate'], 2)} | {'yes' if row['passed'] else 'no'} |")
    lines.append("")
    for row in comparison["ranking"]:
        body = format_alttest_report(comparison["results"][row["judge"]],
                                     human_agreement=human_agreement,
                                     judge_name=row["judge"],
                                     annotator_profile=annotator_profile,
                                     title=f"Judge: {row['judge']}",
                                     include_notice=False)
        lines += ["---", ""] + ["#" + l if l.startswith("#") else l
                                 for l in body.splitlines()] + [""]
    return "\n".join(lines)
