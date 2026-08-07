"""
Empirical validation: does the local hashed-bag-of-words embedding backend
capture real semantic signal, or is it noise?

Method: cluster each bundled labeled dataset's distractor_text at several
similarity thresholds (embeddings.cluster_index), then compute the
Adjusted Rand Index (see ari.py) between the resulting cluster assignment
and the dataset's real, independently-assigned human_label. ARI is
chance-corrected by construction (E[ARI] = 0 for a random labeling, 1.0
for a perfect match), so no separate random baseline is needed -- the
metric's own zero point IS the chance baseline.

This is NOT a claim that high ARI is "success" for the discovery workflow
specifically -- discovery.py's whole premise is that LOW cluster/label
purity is often the interesting signal (a taxonomy gap). This study asks
a narrower, prior question: does the embedding capture real content
similarity at all, well enough to be worth using as clustering input in
the first place. A local backend indistinguishable from random noise
(ARI ~ 0 at every threshold) would undermine every feature built on top
of it; a local backend that clearly recovers real groupings, even
imperfectly, is a meaningful sanity check.

Every number below is computed directly from files already in this
repository (sample_data/example_labels.csv, sample_data/item_bank_demo.csv)
-- nothing here is estimated or invented.
"""
import sys
import csv
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.embeddings import create_index, add_to_index, cluster_index
from ari import adjusted_rand_index


def cluster_labels_from_clusters(clusters, all_item_ids):
    """Turn cluster_index()'s output into a flat predicted-label array
    aligned with all_item_ids (unclustered/singleton items each get their
    own unique label, so they don't spuriously inflate agreement)."""
    item_to_cluster = {}
    for c in clusters:
        for iid in c["item_ids"]:
            item_to_cluster[iid] = f"cluster_{c['cluster_id']}"
    next_singleton = 0
    pred = []
    for iid in all_item_ids:
        if iid in item_to_cluster:
            pred.append(item_to_cluster[iid])
        else:
            pred.append(f"singleton_{next_singleton}")
            next_singleton += 1
    return pred


def run_study(csv_path, dataset_name, id_col="item_id", text_col="distractor_text",
             label_col="human_label", thresholds=(0.15, 0.20, 0.25, 0.30, 0.40)):
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    idx = create_index(backend="local")
    for row in rows:
        add_to_index(idx, row[id_col], row[text_col], metadata={"label": row[label_col]})

    item_ids = [row[id_col] for row in rows]
    true_labels = [row[label_col] for row in rows]

    print(f"\n=== {dataset_name} (n={len(rows)}) ===")
    print(f"{'threshold':>10} {'n_clusters':>11} {'n_clustered_items':>18} {'ARI':>8}")
    results = []
    for t in thresholds:
        clusters = cluster_index(idx, threshold=t, min_cluster_size=2)
        n_clustered = sum(c["size"] for c in clusters)
        pred_labels = cluster_labels_from_clusters(clusters, item_ids)
        ari = adjusted_rand_index(true_labels, pred_labels)
        print(f"{t:>10.2f} {len(clusters):>11d} {n_clustered:>18d} {ari:>8.4f}")
        results.append({"threshold": t, "n_clusters": len(clusters),
                        "n_clustered": n_clustered, "ari": round(ari, 4)})
    return results


if __name__ == "__main__":
    _repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    r1 = run_study(os.path.join(_repo_root, "sample_data", "example_labels.csv"),
                   "example_labels.csv (CFI taxonomy, biology items)")
    r2 = run_study(os.path.join(_repo_root, "sample_data", "item_bank_demo.csv"),
                   "item_bank_demo.csv (distractor-functioning taxonomy)")

    print("\n=== Summary ===")
    best1 = max(r1, key=lambda r: r["ari"])
    best2 = max(r2, key=lambda r: r["ari"])
    print(f"example_labels.csv best ARI:   {best1['ari']} at threshold {best1['threshold']}")
    print(f"item_bank_demo.csv best ARI:   {best2['ari']} at threshold {best2['threshold']}")
