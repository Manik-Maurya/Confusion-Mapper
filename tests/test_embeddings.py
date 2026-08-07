"""
test_embeddings.py - pytest suite for confusion_mapper.embeddings.

New in v2.6.0. No tests here make real network calls to OpenAI -- the
"openai" backend is exercised only up to the point where it correctly
raises (missing API key / library), which is testable without a network
call. The "local" backend, cosine_similarity, and the full index
lifecycle (create/add/remove/search/find_similar/load/save) are tested
against real, deterministic behavior.

Run with: pytest tests/test_embeddings.py -v
"""

import sys
import os
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confusion_mapper.embeddings import (
    _tokenize,
    _embed_local,
    embed_text,
    cosine_similarity,
    create_index,
    add_to_index,
    remove_from_index,
    search,
    find_similar,
    index_stats,
    load_index,
    save_index,
    cluster_index,
)


class TestTokenize:
    def test_lowercases(self):
        assert _tokenize("Mitochondria") == ["mitochondria"]

    def test_strips_stopwords(self):
        tokens = _tokenize("the mitochondria is the powerhouse of the cell")
        assert "the" not in tokens
        assert "is" not in tokens
        assert "of" not in tokens
        assert "mitochondria" in tokens
        assert "powerhouse" in tokens

    def test_strips_punctuation(self):
        tokens = _tokenize("photosynthesis, respiration; and mitosis!")
        assert "photosynthesis" in tokens
        assert "respiration" in tokens
        assert "mitosis" in tokens
        assert not any("," in t or ";" in t or "!" in t for t in tokens)

    def test_empty_string_gives_empty_list(self):
        assert _tokenize("") == []

    def test_all_stopwords_gives_empty_list(self):
        assert _tokenize("the a an is are") == []


class TestEmbedLocal:
    def test_correct_dimension(self):
        v = _embed_local("mitochondria produce energy", dim=512)
        assert len(v) == 512

    def test_deterministic_across_calls(self):
        v1 = _embed_local("mitochondria produce energy")
        v2 = _embed_local("mitochondria produce energy")
        assert v1 == v2

    def test_l2_normalized_for_nonempty_text(self):
        import math
        v = _embed_local("mitochondria produce energy through respiration")
        norm = math.sqrt(sum(x * x for x in v))
        assert norm == pytest.approx(1.0, abs=1e-9)

    def test_zero_vector_for_empty_text(self):
        v = _embed_local("")
        assert all(x == 0.0 for x in v)

    def test_zero_vector_for_all_stopword_text(self):
        v = _embed_local("the a an is")
        assert all(x == 0.0 for x in v)

    def test_different_text_gives_different_vectors(self):
        v1 = _embed_local("mitochondria produce energy")
        v2 = _embed_local("democracy requires informed voters")
        assert v1 != v2

    def test_custom_dimension_respected(self):
        v = _embed_local("some text here", dim=128)
        assert len(v) == 128


class TestEmbedText:
    def test_local_backend_dispatches_correctly(self):
        v = embed_text("test text", backend="local")
        assert len(v) == 512

    def test_openai_backend_without_key_raises_before_any_network_call(self):
        with pytest.raises(RuntimeError, match="API key"):
            embed_text("test text", backend="openai", api_key=None)

    def test_unknown_backend_raises_value_error(self):
        with pytest.raises(ValueError, match="unknown backend"):
            embed_text("test", backend="magic")


class TestCosineSimilarity:
    def test_identical_vectors_give_one(self):
        v = [1.0, 2.0, 3.0]
        assert cosine_similarity(v, v) == pytest.approx(1.0)

    def test_orthogonal_vectors_give_zero(self):
        assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)

    def test_opposite_vectors_give_negative_one(self):
        assert cosine_similarity([1.0, 0.0], [-1.0, 0.0]) == pytest.approx(-1.0)

    def test_dimension_mismatch_raises(self):
        with pytest.raises(ValueError, match="dimension mismatch"):
            cosine_similarity([1.0, 2.0], [1.0, 2.0, 3.0])

    def test_zero_vector_gives_zero_not_a_crash(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 1.0]) == 0.0

    def test_semantically_related_local_embeddings_score_higher_than_unrelated(self):
        """The whole point of the local backend: shared-vocabulary text
        should score higher than text sharing nothing, even without true
        semantic understanding."""
        a = _embed_local("mitochondria produce energy through cellular respiration")
        b = _embed_local("mitochondria generate energy via cellular respiration process")
        c = _embed_local("democracy requires informed voters and free elections")
        assert cosine_similarity(a, b) > cosine_similarity(a, c)


class TestCreateIndex:
    def test_local_backend_defaults(self):
        idx = create_index(backend="local")
        assert idx["backend"] == "local"
        assert idx["dim"] == 512
        assert idx["items"] == {}

    def test_openai_backend_defaults(self):
        idx = create_index(backend="openai")
        assert idx["backend"] == "openai"
        assert idx["dim"] == 1536

    def test_invalid_backend_raises(self):
        with pytest.raises(ValueError, match="unknown backend"):
            create_index(backend="magic")

    def test_default_backend_is_local(self):
        idx = create_index()
        assert idx["backend"] == "local"


class TestAddRemoveFromIndex:
    def test_add_then_present_in_items(self):
        idx = create_index(backend="local")
        add_to_index(idx, "Q1_D1", "mitochondria produce energy")
        assert "Q1_D1" in idx["items"]
        assert idx["items"]["Q1_D1"]["text"] == "mitochondria produce energy"
        assert len(idx["items"]["Q1_D1"]["vector"]) == 512

    def test_add_stores_metadata(self):
        idx = create_index(backend="local")
        add_to_index(idx, "Q1_D1", "text", metadata={"question_id": "Q1", "label": "CF"})
        assert idx["items"]["Q1_D1"]["metadata"] == {"question_id": "Q1", "label": "CF"}

    def test_upsert_overwrites_existing_item_id(self):
        idx = create_index(backend="local")
        add_to_index(idx, "Q1_D1", "first version")
        add_to_index(idx, "Q1_D1", "second version")
        assert idx["items"]["Q1_D1"]["text"] == "second version"
        assert len(idx["items"]) == 1

    def test_add_to_openai_index_without_key_raises(self):
        idx = create_index(backend="openai")
        with pytest.raises(RuntimeError, match="API key"):
            add_to_index(idx, "Q1_D1", "some text", api_key=None)

    def test_remove_existing_returns_true(self):
        idx = create_index(backend="local")
        add_to_index(idx, "Q1_D1", "text")
        assert remove_from_index(idx, "Q1_D1") is True
        assert "Q1_D1" not in idx["items"]

    def test_remove_missing_returns_false_not_an_error(self):
        idx = create_index(backend="local")
        assert remove_from_index(idx, "NONEXISTENT") is False


class TestSearch:
    def test_empty_index_returns_empty_list(self):
        idx = create_index(backend="local")
        assert search(idx, "anything") == []

    def test_returns_most_similar_first(self):
        idx = create_index(backend="local")
        add_to_index(idx, "close", "mitochondria produce energy through respiration")
        add_to_index(idx, "far", "democracy requires informed voters")
        results = search(idx, "mitochondria generate cellular energy", k=5)
        assert results[0]["item_id"] == "close"

    def test_respects_k(self):
        idx = create_index(backend="local")
        for i in range(10):
            add_to_index(idx, f"item{i}", f"some text number {i}")
        results = search(idx, "some text", k=3)
        assert len(results) == 3

    def test_results_include_metadata(self):
        idx = create_index(backend="local")
        add_to_index(idx, "Q1_D1", "text", metadata={"label": "CF"})
        results = search(idx, "text")
        assert results[0]["metadata"] == {"label": "CF"}


class TestFindSimilar:
    def test_excludes_self_from_results(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a", "mitochondria produce energy")
        add_to_index(idx, "b", "mitochondria generate cellular energy")
        results = find_similar(idx, "a", k=5)
        assert all(r["item_id"] != "a" for r in results)
        assert results[0]["item_id"] == "b"

    def test_missing_item_id_raises_keyerror(self):
        idx = create_index(backend="local")
        with pytest.raises(KeyError):
            find_similar(idx, "NONEXISTENT")

    def test_needs_no_api_key_even_for_openai_index(self):
        """find_similar reuses the already-stored vector -- no re-embedding,
        so it should work without ever touching the network, even for an
        'openai'-backend index (as long as the item is already indexed)."""
        idx = create_index(backend="openai")
        idx["items"]["a"] = {"text": "x", "vector": [1.0] + [0.0] * 1535,
                             "metadata": {}, "added": "2026-01-01"}
        idx["items"]["b"] = {"text": "y", "vector": [0.9] + [0.1] * 1535,
                             "metadata": {}, "added": "2026-01-01"}
        results = find_similar(idx, "a")  # no api_key passed -- must not raise
        assert results[0]["item_id"] == "b"


class TestIndexStats:
    def test_reports_correct_counts(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a", "text one")
        add_to_index(idx, "b", "text two")
        stats = index_stats(idx)
        assert stats["n_items"] == 2
        assert stats["backend"] == "local"
        assert stats["dim"] == 512


class TestPersistence:
    def test_load_missing_file_creates_fresh_index(self):
        idx = load_index("/tmp/definitely_does_not_exist_embeddings_12345.json")
        assert idx["items"] == {}
        assert idx["backend"] == "local"

    def test_load_missing_file_respects_default_backend(self):
        idx = load_index("/tmp/definitely_does_not_exist_embeddings_67890.json",
                         default_backend="openai")
        assert idx["backend"] == "openai"

    def test_save_then_load_round_trips(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            idx = create_index(backend="local")
            add_to_index(idx, "Q1_D1", "mitochondria produce energy", metadata={"label": "CF"})
            save_index(idx, path)

            reloaded = load_index(path)
            assert reloaded["backend"] == "local"
            assert "Q1_D1" in reloaded["items"]
            assert reloaded["items"]["Q1_D1"]["text"] == "mitochondria produce energy"
            assert reloaded["items"]["Q1_D1"]["metadata"] == {"label": "CF"}

            # search still works correctly after a round trip
            results = search(reloaded, "mitochondria energy")
            assert results[0]["item_id"] == "Q1_D1"
        finally:
            os.remove(path)

    def test_incremental_updates_across_save_load_cycles(self):
        """The persistent-library use case: build, save, reload, add more,
        save again -- nothing from the first batch should be lost or
        altered."""
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            idx = create_index(backend="local")
            add_to_index(idx, "a", "first item")
            save_index(idx, path)

            idx2 = load_index(path)
            add_to_index(idx2, "b", "second item")
            save_index(idx2, path)

            idx3 = load_index(path)
            assert set(idx3["items"].keys()) == {"a", "b"}
        finally:
            os.remove(path)


class TestClusterIndex:
    def _clustered_index(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a1", "mitochondria produce energy through cellular respiration")
        add_to_index(idx, "a2", "mitochondria generate cellular energy via respiration")
        add_to_index(idx, "a3", "mitochondria create energy from cellular respiration process")
        add_to_index(idx, "b1", "democracy requires informed voters and free elections")
        add_to_index(idx, "b2", "democracy needs informed voters with free elections")
        add_to_index(idx, "c1", "a totally unrelated singleton about cooking recipes")
        return idx

    def test_finds_two_distinct_clusters(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        assert len(clusters) == 2
        sizes = sorted(c["size"] for c in clusters)
        assert sizes == [2, 3]

    def test_correct_membership(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        big = next(c for c in clusters if c["size"] == 3)
        small = next(c for c in clusters if c["size"] == 2)
        assert set(big["item_ids"]) == {"a1", "a2", "a3"}
        assert set(small["item_ids"]) == {"b1", "b2"}

    def test_singleton_excluded_by_default_min_size(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        all_item_ids = {iid for c in clusters for iid in c["item_ids"]}
        assert "c1" not in all_item_ids

    def test_min_cluster_size_one_includes_singletons(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.9, min_cluster_size=1)
        all_item_ids = {iid for c in clusters for iid in c["item_ids"]}
        assert "c1" in all_item_ids

    def test_sorted_largest_first(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        sizes = [c["size"] for c in clusters]
        assert sizes == sorted(sizes, reverse=True)

    def test_cluster_ids_are_stable_within_one_call(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        assert [c["cluster_id"] for c in clusters] == list(range(len(clusters)))

    def test_very_high_threshold_finds_nothing(self):
        idx = self._clustered_index()
        clusters = cluster_index(idx, threshold=0.999, min_cluster_size=2)
        assert clusters == []

    def test_fewer_than_two_items_returns_empty(self):
        idx = create_index(backend="local")
        assert cluster_index(idx) == []
        add_to_index(idx, "a", "solo item")
        assert cluster_index(idx) == []

    def test_items_carry_metadata_through(self):
        idx = create_index(backend="local")
        add_to_index(idx, "a1", "mitochondria produce energy", metadata={"label": "PK"})
        add_to_index(idx, "a2", "mitochondria generate energy", metadata={"label": "CF"})
        clusters = cluster_index(idx, threshold=0.3, min_cluster_size=2)
        labels = {item["metadata"]["label"] for item in clusters[0]["items"]}
        assert labels == {"PK", "CF"}
