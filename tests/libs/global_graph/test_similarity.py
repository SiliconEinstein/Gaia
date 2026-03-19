"""Tests for content similarity matching."""

from libs.global_graph.models import GlobalCanonicalNode
from libs.global_graph.similarity import compute_similarity_tfidf as compute_similarity
from libs.global_graph.similarity import find_best_match


def _node(gcn_id: str, content: str, ktype: str = "claim", kind: str | None = None):
    return GlobalCanonicalNode(
        global_canonical_id=gcn_id,
        knowledge_type=ktype,
        kind=kind,
        representative_content=content,
    )


class TestComputeSimilarity:
    def test_identical_content(self):
        score = compute_similarity("The sky is blue", "The sky is blue")
        assert score > 0.99

    def test_similar_content(self):
        score = compute_similarity(
            "Free fall acceleration is independent of mass",
            "All objects fall at the same rate regardless of weight",
        )
        assert 0.1 < score < 1.0

    def test_unrelated_content(self):
        score = compute_similarity(
            "Superconductivity occurs below critical temperature",
            "Photosynthesis converts CO2 to glucose",
        )
        assert score < 0.3

    def test_empty_string(self):
        assert compute_similarity("", "something") == 0.0
        assert compute_similarity("something", "") == 0.0


class TestFindBestMatch:
    async def test_exact_match_found(self):
        candidates = [
            _node("gcn_1", "The sky is blue"),
            _node("gcn_2", "Water boils at 100 degrees"),
        ]
        match = await find_best_match("The sky is blue", "claim", None, candidates, threshold=0.90)
        assert match is not None
        assert match[0] == "gcn_1"
        assert match[1] > 0.90

    async def test_no_match_below_threshold(self):
        candidates = [
            _node("gcn_1", "Unrelated topic about chemistry"),
        ]
        match = await find_best_match(
            "Free fall acceleration", "claim", None, candidates, threshold=0.90
        )
        assert match is None

    async def test_type_mismatch_rejected(self):
        candidates = [
            _node("gcn_1", "The sky is blue", ktype="setting"),
        ]
        match = await find_best_match("The sky is blue", "claim", None, candidates, threshold=0.90)
        assert match is None

    async def test_kind_mismatch_rejected_for_action(self):
        candidates = [
            _node("gcn_1", "Apply method X", ktype="action", kind="infer_action"),
        ]
        match = await find_best_match(
            "Apply method X", "action", "toolcall_action", candidates, threshold=0.90
        )
        assert match is None

    async def test_kind_match_required_for_question(self):
        candidates = [
            _node("gcn_1", "Is X true?", ktype="question", kind="research"),
        ]
        match = await find_best_match(
            "Is X true?", "question", "research", candidates, threshold=0.90
        )
        assert match is not None

    async def test_contradiction_never_matched(self):
        candidates = [
            _node("gcn_1", "A contradicts B", ktype="contradiction"),
        ]
        match = await find_best_match(
            "A contradicts B", "contradiction", None, candidates, threshold=0.50
        )
        assert match is None

    async def test_empty_candidates(self):
        match = await find_best_match("anything", "claim", None, [], threshold=0.90)
        assert match is None
