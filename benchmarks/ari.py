"""
Adjusted Rand Index (Hubert & Arabie, 1985), implemented from scratch --
no scipy/sklearn dependency, matching this whole project's stdlib-only
philosophy. Standard formula:

  index          = sum_ij C(n_ij, 2)
  expected_index = [sum_i C(a_i,2) * sum_j C(b_j,2)] / C(n,2)
  max_index      = 0.5 * [sum_i C(a_i,2) + sum_j C(b_j,2)]
  ARI            = (index - expected_index) / (max_index - expected_index)
"""
from collections import defaultdict


def _comb2(n):
    return n * (n - 1) / 2


def adjusted_rand_index(labels_true, labels_pred):
    assert len(labels_true) == len(labels_pred)
    n = len(labels_true)
    if n == 0:
        return 0.0

    contingency = defaultdict(lambda: defaultdict(int))
    row_totals = defaultdict(int)
    col_totals = defaultdict(int)
    for t, p in zip(labels_true, labels_pred):
        contingency[p][t] += 1
        row_totals[p] += 1
        col_totals[t] += 1

    index = sum(_comb2(v) for row in contingency.values() for v in row.values())
    sum_a = sum(_comb2(v) for v in row_totals.values())
    sum_b = sum(_comb2(v) for v in col_totals.values())
    total_comb = _comb2(n)

    if total_comb == 0:
        return 1.0
    expected_index = (sum_a * sum_b) / total_comb
    max_index = 0.5 * (sum_a + sum_b)
    if max_index == expected_index:
        return 1.0
    return (index - expected_index) / (max_index - expected_index)


if __name__ == "__main__":
    # Hand-derived example (see accompanying methods note):
    # true = [0,0,0,1,1,1], pred = [0,0,1,1,2,2]
    # index=2, sum_a=3, sum_b=6, C(n,2)=15
    # expected=1.2, max=4.5, ARI = 0.8/3.3 = 0.242424...
    true_labels = [0, 0, 0, 1, 1, 1]
    pred_labels = [0, 0, 1, 1, 2, 2]
    ari = adjusted_rand_index(true_labels, pred_labels)
    print(f"hand-derived example: ARI = {ari:.6f}  (expected 0.242424...)")
    assert abs(ari - 0.242424242424) < 1e-6, "MISMATCH with hand-derived value"
    print("MATCHES hand-derived value exactly")

    # Sanity checks
    identical = adjusted_rand_index([0, 0, 1, 1, 2, 2], [0, 0, 1, 1, 2, 2])
    print(f"identical partitions: ARI = {identical} (expected 1.0)")
    assert abs(identical - 1.0) < 1e-9

    single_cluster = adjusted_rand_index([0, 0, 1, 1, 2, 2], [0, 0, 0, 0, 0, 0])
    print(f"everything in one cluster: ARI = {single_cluster} (expected 0.0)")
    assert abs(single_cluster - 0.0) < 1e-9
