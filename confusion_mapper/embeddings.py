"""
Semantic search over already-coded items. Two backends, picked at
index creation time and then locked in so a later run without an API
key cannot silently produce a garbage dimension mismatch.

The openai backend uses text-embedding-3-small. It is the one I use.
The local backend is a from-scratch hashed bag-of-words vector, pure
stdlib, zero cost, zero network. It is honestly not as good, and the
module docstring says so, but it means the package works offline for
anyone who needs it to.
"""

import datetime
import hashlib
import json
import math
import os
import re
from collections import defaultdict

from .ai import OPENAI_AVAILABLE, OpenAI

_OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
_OPENAI_EMBEDDING_DIM   = 1536
_LOCAL_MODEL            = "hashed-bow-v1"
_LOCAL_DIM              = 512

# tiny stopword list, just the common English glue. I did not want to
# pull nltk in for this one thing. deliberately not exhaustive.
_STOPWORDS = frozenset("""
a an the is are was were be been being to of in on at for with by from
this that these those it its as and or but if then so not no do does did
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text):
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


def _embed_local(text, dim=_LOCAL_DIM):
    """
    Hashed bag-of-words. Each token hashes into a bucket in [0, dim)
    with a sign derived from the same hash, and the vector is L2
    normalized at the end. Standard feature hashing, Weinberger et al.
    2009.

    I use sha256 here on purpose. Python's built-in hash() randomizes
    strings per process, so an index built in one Python session would
    silently not match one built the next time you opened Python. That
    caught me once and I did not want it to catch anyone else.

    """
    vector = [0.0] * dim
    for token in _tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        h = int.from_bytes(digest[:8], "big")
        bucket = h % dim
        sign = 1.0 if (h // dim) % 2 == 0 else -1.0
        vector[bucket] += sign

    norm = math.sqrt(sum(x * x for x in vector))
    if norm > 0:
        vector = [x / norm for x in vector]
    return vector


def _embed_openai(text, api_key):
    if not OPENAI_AVAILABLE:
        raise RuntimeError("openai library not installed. Run: pip install openai")
    if not api_key:
        raise RuntimeError("no API key given for an 'openai' backend index")
    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(model=_OPENAI_EMBEDDING_MODEL, input=text)
    return list(response.data[0].embedding)


def embed_text(text, backend, api_key=None):
    """
    Embed one string with the given backend ("openai" or "local").
    Returns a list[float]. Raises ValueError for an unknown backend,
    RuntimeError if "openai" is requested without the library/API key
    available.
    """
    if backend == "openai":
        return _embed_openai(text, api_key)
    elif backend == "local":
        return _embed_local(text)
    else:
        raise ValueError(f"unknown backend {backend!r}; expected 'openai' or 'local'")


def cosine_similarity(v1, v2):
    """Standard cosine similarity, pure Python. Returns 0.0 for a
    zero-vector rather than raising a division-by-zero error."""
    if len(v1) != len(v2):
        raise ValueError(f"vector dimension mismatch: {len(v1)} vs {len(v2)}. "
                         f"probably mixing an openai index with a local one.")
    dot = sum(a * b for a, b in zip(v1, v2))
    n1 = math.sqrt(sum(a * a for a in v1))
    n2 = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)


def create_index(backend="local"):
    """
    A fresh, empty index. `backend` is locked in for this index's
    lifetime, every subsequent add_to_index() / search() call against
    this index uses whatever backend it was created with, regardless of
    what's passed to those functions later, so the vector space stays
    consistent no matter how many times this index is reopened.
    """
    if backend not in ("openai", "local"):
        raise ValueError(f"unknown backend {backend!r}; expected 'openai' or 'local'")
    model = _OPENAI_EMBEDDING_MODEL if backend == "openai" else _LOCAL_MODEL
    dim   = _OPENAI_EMBEDDING_DIM if backend == "openai" else _LOCAL_DIM
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return {
        "backend": backend,
        "model":   model,
        "dim":     dim,
        "created": now,
        "updated": now,
        "items":   {},
    }


def add_to_index(index, item_id, text, metadata=None, api_key=None):
    """
    Embed `text` with the index's own locked-in backend and store it
    under `item_id` (upsert, re-adding an existing item_id overwrites
    its text/vector/metadata, for re-indexing after an edit).

    Raises RuntimeError with a clear message if the index's backend is
    "openai" and no usable API key is available, it will not silently
    fall back to "local" and produce a dimension mismatch buried in the
    index for someone to find later.
    """
    vector = embed_text(text, index["backend"], api_key=api_key)
    index["items"][item_id] = {
        "text":     text,
        "vector":   vector,
        "metadata": metadata or {},
        "added":    datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    index["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return index


def remove_from_index(index, item_id):
    """Remove an item if present. Returns True if something was removed,
    False if item_id wasn't in the index (idempotent, doesn't raise)."""
    if item_id in index["items"]:
        del index["items"][item_id]
        index["updated"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return True
    return False


def search(index, query_text, k=5, api_key=None):
    """
    Embed `query_text` with the index's backend and return the top-k most
    similar items, sorted highest-similarity first.

    Returns:
        list[dict]: {item_id, text, score, metadata}, length min(k, n_items).
    """
    if not index["items"]:
        return []
    query_vector = embed_text(query_text, index["backend"], api_key=api_key)
    scored = [
        {"item_id": iid, "text": item["text"],
         "score": cosine_similarity(query_vector, item["vector"]),
         "metadata": item["metadata"]}
        for iid, item in index["items"].items()
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:k]


def find_similar(index, item_id, k=5):
    """
    Like search(), but uses an item already in the index as the query --
    no re-embedding, no API key needed even for an "openai" index, since
    the vector is already stored. The queried item itself is excluded
    from its own results.

    Raises KeyError if item_id isn't in the index.
    """
    if item_id not in index["items"]:
        raise KeyError(f"{item_id!r} is not in this index")
    query_vector = index["items"][item_id]["vector"]
    scored = [
        {"item_id": iid, "text": item["text"],
         "score": cosine_similarity(query_vector, item["vector"]),
         "metadata": item["metadata"]}
        for iid, item in index["items"].items()
        if iid != item_id
    ]
    scored.sort(key=lambda r: r["score"], reverse=True)
    return scored[:k]


def index_stats(index):
    return {
        "n_items": len(index["items"]),
        "backend": index["backend"],
        "model":   index["model"],
        "dim":     index["dim"],
        "created": index["created"],
        "updated": index["updated"],
    }


def load_index(path, default_backend="local"):
    """
    Load an index from disk, or create a fresh empty one (with
    `default_backend`) if the file doesn't exist yet, so the first
    `embed-index build` against a new path just works without a separate
    init step.
    """
    if not os.path.exists(path):
        return create_index(backend=default_backend)
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_index(index, path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2)
    return path


# ---------------------------------------------------------------------------
# Clustering
# ---------------------------------------------------------------------------

class _UnionFind:
    """Standard disjoint-set structure with path compression + union by
    rank, textbook implementation, not a novel data structure."""

    def __init__(self, items):
        self.parent = {x: x for x in items}
        self.rank = {x: 0 for x in items}

    def find(self, x):
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return
        if self.rank[ra] < self.rank[rb]:
            ra, rb = rb, ra
        self.parent[rb] = ra
        if self.rank[ra] == self.rank[rb]:
            self.rank[ra] += 1


def cluster_index(index, threshold=0.5, min_cluster_size=2):
    """
    Single-linkage agglomerative clustering by cosine-similarity threshold,
    implemented via the standard efficient approach for this exact
    problem: compute every pairwise similarity, sort descending, union
    each pair (via disjoint-set / union-find) if its similarity clears
    `threshold`, in similarity order. This is deterministic regardless of
    the order items were added to the index (unlike a greedy single-pass
    "leader" clustering, which depends on iteration order), it's the
    same algorithm as building a minimum-spanning-tree and cutting edges
    below a weight threshold, applied to clustering instead of routing.

    Args:
        index (dict): as returned by create_index()/load_index().
        threshold (float): cosine similarity above which two items are
            considered connected. Higher = tighter, more, smaller clusters.
        min_cluster_size (int): clusters smaller than this are dropped
            from the result (they're usually not "a pattern," just one or
            two similar-sounding items by chance).

    Returns:
        list[dict]: {cluster_id, item_ids, items: [{item_id, text,
        metadata}], size}, sorted largest-first. cluster_id is a stable
        integer index into this list, not persisted anywhere, recompute
        it each time you call this (clusters can shift as the index grows).

    Complexity: O(n^2) pairwise similarities + O(n^2 log n) sort --
    fine for the hundreds-to-low-thousands of items a single research
    project's item bank realistically has; for a much larger corpus,
    downsample or raise the threshold to shrink the candidate pair set
    first.
    """
    item_ids = list(index["items"].keys())
    n = len(item_ids)
    if n < 2:
        return []

    edges = []
    for i in range(n):
        for j in range(i + 1, n):
            a, b = item_ids[i], item_ids[j]
            sim = cosine_similarity(index["items"][a]["vector"], index["items"][b]["vector"])
            if sim >= threshold:
                edges.append((sim, a, b))
    edges.sort(key=lambda e: e[0], reverse=True)

    uf = _UnionFind(item_ids)
    for _, a, b in edges:
        uf.union(a, b)

    groups = defaultdict(list)
    for item_id in item_ids:
        groups[uf.find(item_id)].append(item_id)

    clusters = []
    for group_item_ids in groups.values():
        if len(group_item_ids) < min_cluster_size:
            continue
        clusters.append({
            "item_ids": group_item_ids,
            "items": [{"item_id": iid, "text": index["items"][iid]["text"],
                      "metadata": index["items"][iid]["metadata"]} for iid in group_item_ids],
            "size": len(group_item_ids),
        })

    clusters.sort(key=lambda c: c["size"], reverse=True)
    for i, c in enumerate(clusters):
        c["cluster_id"] = i
    return clusters
