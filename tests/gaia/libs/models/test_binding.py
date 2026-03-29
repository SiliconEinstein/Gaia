"""Tests for CanonicalBinding and BindingDecision models."""

from gaia.models.binding import BindingDecision, CanonicalBinding


class TestBindingDecision:
    def test_match_existing_value(self):
        assert BindingDecision.MATCH_EXISTING == "match_existing"

    def test_create_new_value(self):
        assert BindingDecision.CREATE_NEW == "create_new"

    def test_equivalent_candidate_value(self):
        assert BindingDecision.EQUIVALENT_CANDIDATE == "equivalent_candidate"

    def test_is_str(self):
        """BindingDecision is a StrEnum — behaves as plain string."""
        assert isinstance(BindingDecision.MATCH_EXISTING, str)
        assert isinstance(BindingDecision.CREATE_NEW, str)
        assert isinstance(BindingDecision.EQUIVALENT_CANDIDATE, str)


class TestCanonicalBindingMatchExisting:
    def test_match_existing_creation(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_abc123",
            global_canonical_id="gcn_xyz789",
            package_id="pkg_superconductors",
            version="1.0.0",
            decision=BindingDecision.MATCH_EXISTING,
            reason="cosine similarity 0.95",
        )
        assert cb.local_canonical_id == "lcn_abc123"
        assert cb.global_canonical_id == "gcn_xyz789"
        assert cb.package_id == "pkg_superconductors"
        assert cb.version == "1.0.0"
        assert cb.decision == BindingDecision.MATCH_EXISTING
        assert cb.reason == "cosine similarity 0.95"

    def test_match_existing_with_string_decision(self):
        """BindingDecision as plain string should be accepted."""
        cb = CanonicalBinding(
            local_canonical_id="lcn_a",
            global_canonical_id="gcn_b",
            package_id="pkg1",
            version="0.1",
            decision="match_existing",
            reason="TF-IDF fallback score 0.88",
        )
        assert cb.decision == BindingDecision.MATCH_EXISTING


class TestCanonicalBindingCreateNew:
    def test_create_new_creation(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_novel",
            global_canonical_id="gcn_novel_001",
            package_id="pkg_new_research",
            version="2.0",
            decision=BindingDecision.CREATE_NEW,
            reason="no matching global node found",
        )
        assert cb.decision == BindingDecision.CREATE_NEW
        assert cb.global_canonical_id == "gcn_novel_001"


class TestCanonicalBindingEquivalentCandidate:
    def test_equivalent_candidate_creation(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_conclusion",
            global_canonical_id="gcn_conclusion_new",
            package_id="pkg_second_paper",
            version="1.1",
            decision=BindingDecision.EQUIVALENT_CANDIDATE,
            reason="conclusion node matched existing gcn_conclusion_old; candidate equivalent factor created",
        )
        assert cb.decision == BindingDecision.EQUIVALENT_CANDIDATE


class TestCanonicalBindingSerialization:
    def test_roundtrip_model_dump(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_x",
            global_canonical_id="gcn_y",
            package_id="pkg_test",
            version="1.0",
            decision=BindingDecision.MATCH_EXISTING,
            reason="cosine similarity 0.92",
        )
        data = cb.model_dump()
        restored = CanonicalBinding.model_validate(data)
        assert restored.local_canonical_id == cb.local_canonical_id
        assert restored.global_canonical_id == cb.global_canonical_id
        assert restored.package_id == cb.package_id
        assert restored.version == cb.version
        assert restored.decision == cb.decision
        assert restored.reason == cb.reason

    def test_json_roundtrip(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_j",
            global_canonical_id="gcn_k",
            package_id="pkg_j",
            version="3.0",
            decision=BindingDecision.EQUIVALENT_CANDIDATE,
            reason="semantic match at 0.91 with existing conclusion",
        )
        json_str = cb.model_dump_json()
        restored = CanonicalBinding.model_validate_json(json_str)
        assert restored.local_canonical_id == cb.local_canonical_id
        assert restored.decision == cb.decision

    def test_decision_serializes_as_string(self):
        cb = CanonicalBinding(
            local_canonical_id="lcn_1",
            global_canonical_id="gcn_1",
            package_id="pkg_1",
            version="1.0",
            decision=BindingDecision.CREATE_NEW,
            reason="new proposition",
        )
        data = cb.model_dump()
        assert data["decision"] == "create_new"
