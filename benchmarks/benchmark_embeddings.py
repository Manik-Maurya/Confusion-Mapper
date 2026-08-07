"""
benchmark_embeddings.py -- local vs. OpenAI embedding backend, same
methodology as the local-only study already run (see
EMBEDDING_VALIDATION_FINDINGS.md).

This script needs OPENAI_API_KEY and network access to run the "openai"
half -- neither is available in the sandbox this was written in, so this
file has been written carefully and reviewed, but the openai-backend
numbers in it have NOT been executed by anyone yet. Run it yourself:

    export OPENAI_API_KEY="your-key-here"
    pip install confusion-mapper   # or: pip install -e . from the repo root
    python benchmark_embeddings.py

What it does: builds a `local`-backend index and an `openai`-backend index
from the same labeled CSV, clusters each at the same thresholds, and
reports Adjusted Rand Index (see ari.py) against the real human_label
column for both -- so you get a direct, apples-to-apples comparison on
your own data, not just on the two small bundled sample files.

Cost note: OpenAI's text-embedding-3-small is billed per token. For the
bundled sample files (30 and 16 short distractor strings) this is a
fraction of a cent; for your actual RCT dataset, check current OpenAI
pricing before running this on a large CSV.
"""

import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ari import adjusted_rand_index

try:
    from confusion_mapper.embeddings import create_index, add_to_index, cluster_index
except ImportError:
    print("confusion_mapper not importable -- run `pip install -e .` from the repo "
         "root first, or `pip install confusion-mapper` once it's on PyPI.")
    sys.exit(1)


def cluster_labels_from_clusters(clusters, all_item_ids):
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


def run_backend(rows, backend, api_key, id_col, text_col, label_col, thresholds):
    idx = create_index(backend=backend)
    for row in rows:
        add_to_index(idx, row[id_col], row[text_col],
                     metadata={"label": row[label_col]}, api_key=api_key)

    item_ids = [row[id_col] for row in rows]
    true_labels = [row[label_col] for row in rows]

    results = []
    for t in thresholds:
        clusters = cluster_index(idx, threshold=t, min_cluster_size=2)
        n_clustered = sum(c["size"] for c in clusters)
        pred_labels = cluster_labels_from_clusters(clusters, item_ids)
        ari = adjusted_rand_index(true_labels, pred_labels)
        results.append({"backend": backend, "threshold": t, "n_clusters": len(clusters),
                        "n_clustered": n_clustered, "ari": round(ari, 4)})
    return results


def run_comparison(csv_path, dataset_name, id_col="item_id", text_col="distractor_text",
                   label_col="human_label", local_thresholds=(0.15, 0.20, 0.25, 0.30, 0.40),
                   openai_thresholds=(0.15, 0.25, 0.35, 0.45, 0.55, 0.65)):
    """
    Note the different default threshold ranges: cosine similarity means
    something different across the two vector spaces (512-dim hashed
    bag-of-words vs. 1536-dim OpenAI embeddings) -- real embeddings
    typically cluster at higher raw cosine similarity even for loosely
    related text, so sweeping the same 0.15-0.40 range used for the local
    backend would likely under-cluster the openai backend. Adjust both
    ranges based on what you observe; these are reasonable starting points,
    not tuned values.
    """
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    with open(csv_path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))

    print(f"\n=== {dataset_name} (n={len(rows)}) ===")

    print("\n-- local (hashed bag-of-words) --")
    local_results = run_backend(rows, "local", None, id_col, text_col, label_col, local_thresholds)
    print(f"{'threshold':>10} {'n_clusters':>11} {'n_clustered':>12} {'ARI':>8}")
    for r in local_results:
        print(f"{r['threshold']:>10.2f} {r['n_clusters']:>11d} {r['n_clustered']:>12d} {r['ari']:>8.4f}")

    if not api_key:
        print("\n-- openai (text-embedding-3-small) --")
        print("SKIPPED: no OPENAI_API_KEY set. Set it and re-run to fill in this half.")
        return local_results, None

    print("\n-- openai (text-embedding-3-small) --")
    openai_results = run_backend(rows, "openai", api_key, id_col, text_col, label_col, openai_thresholds)
    print(f"{'threshold':>10} {'n_clusters':>11} {'n_clustered':>12} {'ARI':>8}")
    for r in openai_results:
        print(f"{r['threshold']:>10.2f} {r['n_clusters']:>11d} {r['n_clustered']:>12d} {r['ari']:>8.4f}")

    return local_results, openai_results


if __name__ == "__main__":
    repo_root = os.environ.get("CONFUSION_MAPPER_REPO", ".")
    run_comparison(
        os.path.join(repo_root, "sample_data", "example_labels.csv"),
        "example_labels.csv (CFI taxonomy, biology items)",
    )
    run_comparison(
        os.path.join(repo_root, "sample_data", "item_bank_demo.csv"),
        "item_bank_demo.csv (distractor-functioning taxonomy)",
    )
    print("\nTo run this against your own data: run_comparison('your_file.csv', 'your dataset name')")
