"""
Cross-checks confusion_mapper.alttest against the authors' own reference
code and against scipy.

The alt-test module is pure standard library, so it has its own t
distribution and its own Benjamini-Yekutieli step. This script checks all
of it against independent implementations:

  1. t_cdf against scipy.stats.t.cdf over 6,734 (t, df) points.
  2. benjamini_yekutieli against the numpy version from the authors'
     notebook (github.com/nitaytech/AltTest), on 20,000 random p-value sets.
  3. the full alt_test against the authors' alt_test logic (copied from
     their notebook, using scipy.stats.ttest_1samp), on 400 random
     synthetic panels with 2 to 6 coders, 2 to 4 categories, 30 to 150
     items, missing labels and several epsilon values.

Needs numpy and scipy, which are NOT dependencies of ConfusionMapper.
    pip install numpy scipy
    python benchmarks/alttest_crosscheck.py

Results are written up in ALTTEST_VALIDATION.md next to this file.
"""
import os
import sys
try:
    import numpy as np  # noqa: F401
    import scipy  # noqa: F401
except ImportError:
    sys.exit("this cross-check needs numpy and scipy: pip install numpy scipy")
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import random, math, warnings
import numpy as np
from scipy import stats
from scipy.stats import ttest_1samp
from confusion_mapper.alttest import (t_cdf, alt_test, benjamini_yekutieli,
                                      generate_synthetic_panel, one_sided_t_test_less)

# 1) t CDF vs scipy
worst = 0.0
for df in [1, 2, 3, 4, 5, 7, 10, 15, 29, 30, 49, 99, 199, 500]:
    for t in np.linspace(-12, 12, 481):
        worst = max(worst, abs(t_cdf(float(t), df) - stats.t.cdf(t, df)))
print(f"t_cdf max abs error vs scipy over 6,734 points: {worst:.2e}")

# 2) BY vs authors' numpy version (copied from their notebook)
def by_ref(p, q):
    p = np.array(p, dtype=float); m = len(p)
    idx = np.argsort(p); sp = p[idx]
    H = np.sum(1.0 / np.arange(1, m + 1))
    th = (np.arange(1, m + 1) / m) * (q / H)
    mi = -1
    for i in range(m):
        if sp[i] <= th[i]: mi = i
    return [] if mi == -1 else sorted(idx[:mi + 1].tolist())
rng = random.Random(1)
mism = 0
for _ in range(20000):
    m = rng.randint(1, 12)
    p = [rng.random() ** rng.choice([1, 3, 6]) for _ in range(m)]
    if sorted(benjamini_yekutieli(p, 0.05)) != by_ref(p, 0.05): mism += 1
print(f"BY mismatches vs reference over 20,000 random cases: {mism}")

# 3) full alt-test vs authors' reference alt_test (logic copied from their notebook)
def acc(pred, anns): return float(np.mean([pred == a for a in anns]))
def ref_alt_test(llm, humans, epsilon=0.2, q=0.05, min_h=2, min_i=30):
    i_set, h_set = {}, {}
    for h, anns in humans.items():
        i_set[h] = list(anns.keys())
        for i in anns: h_set.setdefault(i, []).append(h)
    keep = {i for i in h_set if len(h_set[i]) >= min_h and i in llm}
    i_set = {h: [i for i in i_set[h] if i in keep] for h in i_set}
    h_set = {i: h_set[i] for i in h_set if i in keep}
    pv, ap, hs = [], [], []
    for ex in humans:
        inst = [i for i in i_set[ex] if i in llm]
        if len(inst) < min_i: continue
        li, ei = [], []
        for i in inst:
            rem = [humans[h][i] for h in h_set[i] if h != ex]
            hs_ = acc(humans[ex][i], rem); ls = acc(llm[i], rem)
            li.append(1 if ls >= hs_ else 0); ei.append(1 if hs_ >= ls else 0)
        d = [e - l for e, l in zip(ei, li)]
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            pv.append(ttest_1samp(d, epsilon, alternative='less').pvalue)
        ap.append(float(np.mean(li))); hs.append(ex)
    rej = by_ref(pv, q)
    return len(rej) / len(hs), float(np.mean(ap)), pv

rng = random.Random(7)
n_cases = wr_mis = ap_mis = 0; worst_p = 0.0; nan_cases = 0
for case in range(400):
    n = rng.choice([30, 40, 60, 100, 150])
    m = rng.choice([2, 3, 4, 5, 6])
    panel = generate_synthetic_panel(n, m, ("A","B","C","D")[:rng.choice([2,3,4])],
                                     rng.choice([0.05, 0.2, 0.4, 0.7]),
                                     (rng.choice([0.0, 0.1, 0.3, 0.6, 0.9]),), seed=rng.randrange(10**9))
    humans, llm = panel["humans"], panel["ais"]["ai_1"]
    # knock out some labels to exercise missing data
    if rng.random() < 0.5:
        for c in humans:
            for x in list(humans[c]):
                if rng.random() < 0.1: del humans[c][x]
    eps = rng.choice([0.0, 0.1, 0.15, 0.2])
    mine = alt_test(llm, humans, epsilon=eps)
    if mine["winning_rate"] is None: continue
    import contextlib, io
    with contextlib.redirect_stdout(io.StringIO()):
        wr, ap, pv = ref_alt_test(llm, humans, epsilon=eps)
    n_cases += 1
    myp = [a["p_value"] for a in mine["per_annotator"]]
    for a, b in zip(myp, pv):
        if math.isnan(b): nan_cases += 1; continue
        worst_p = max(worst_p, abs(a - b))
    if abs(mine["advantage_probability"] - ap) > 1e-12: ap_mis += 1
    if abs(mine["winning_rate"] - wr) > 1e-12: wr_mis += 1
print(f"alt-test cases compared: {n_cases}")
print(f"  advantage probability mismatches: {ap_mis}")
print(f"  winning rate mismatches: {wr_mis}")
print(f"  max p-value difference (non-degenerate): {worst_p:.2e}")
print(f"  degenerate zero-variance p-values where scipy gives nan: {nan_cases}")
