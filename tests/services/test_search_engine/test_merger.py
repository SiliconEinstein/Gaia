from services.search_engine.merger import ResultMerger


async def test_merge_single_path():
    merger = ResultMerger()
    results = {"vector": [(1, 0.1), (2, 0.5), (3, 0.9)]}
    merged = await merger.merge(results, k=10)
    ids = [m[0] for m in merged]
    assert 1 in ids
    assert 2 in ids
    assert 3 in ids


async def test_merge_dedup():
    merger = ResultMerger()
    results = {
        "vector": [(1, 0.1), (2, 0.5)],
        "bm25": [(1, 5.0), (3, 3.0)],
    }
    merged = await merger.merge(results, k=10)
    ids = [m[0] for m in merged]
    # Node 1 appears in both paths -- should appear only once
    assert ids.count(1) == 1
    # Node 1 should have sources from both
    node1 = next(m for m in merged if m[0] == 1)
    assert "vector" in node1[2]
    assert "bm25" in node1[2]


async def test_merge_respects_k():
    merger = ResultMerger()
    results = {"vector": [(i, float(i)) for i in range(100)]}
    merged = await merger.merge(results, k=5)
    assert len(merged) == 5


async def test_merge_empty():
    merger = ResultMerger()
    merged = await merger.merge({}, k=10)
    assert merged == []


async def test_merge_multi_source_higher_score():
    """Node appearing in multiple paths should score higher than single-path nodes."""
    merger = ResultMerger()
    results = {
        "vector": [(1, 0.1), (2, 0.9)],  # node 1 is close (low distance = good)
        "bm25": [(1, 5.0)],  # node 1 also matches BM25
    }
    merged = await merger.merge(results, k=10)
    scores = {m[0]: m[1] for m in merged}
    # Node 1 appears in both paths, should have higher merged score than node 2
    assert scores[1] > scores[2]


async def test_merge_vector_inversion():
    """Vector scores (distances) should be inverted: lower distance = higher score."""
    merger = ResultMerger(weights={"vector": 1.0})
    results = {"vector": [(1, 0.1), (2, 0.9)]}
    merged = await merger.merge(results, k=10)
    scores = {m[0]: m[1] for m in merged}
    # Node 1 has lower distance (0.1) so should get higher score
    assert scores[1] > scores[2]


async def test_merge_custom_weights():
    merger = ResultMerger(weights={"vector": 0.0, "bm25": 1.0})
    results = {
        "vector": [(1, 0.0)],  # would get max vector score, but weight is 0
        "bm25": [(2, 5.0)],
    }
    merged = await merger.merge(results, k=10)
    scores = {m[0]: m[1] for m in merged}
    # Node 2 should have higher score since bm25 has all weight
    assert scores[2] > scores[1]


async def test_merge_all_same_scores():
    """When all scores in a path are equal, they should all normalize to 1.0."""
    merger = ResultMerger(weights={"bm25": 1.0})
    results = {"bm25": [(1, 3.0), (2, 3.0), (3, 3.0)]}
    merged = await merger.merge(results, k=10)
    scores = {m[0]: m[1] for m in merged}
    # All should have equal score
    assert scores[1] == scores[2] == scores[3]


async def test_merge_sorted_by_score_descending():
    merger = ResultMerger()
    results = {
        "vector": [(1, 0.9), (2, 0.1), (3, 0.5)],
    }
    merged = await merger.merge(results, k=10)
    scores = [m[1] for m in merged]
    assert scores == sorted(scores, reverse=True)
