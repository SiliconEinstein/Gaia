"""Tests for CanonicalBinding data model."""

from gaia.gaia_ir import CanonicalBinding, BindingDecision


class TestBindingDecision:
    def test_three_decisions(self):
        assert set(BindingDecision) == {"match_existing", "create_new", "equivalent_candidate"}


class TestCanonicalBinding:
    def test_match_existing(self):
        b = CanonicalBinding(
            local_canonical_id="reg:test::a",
            global_canonical_id="gcn_xyz",
            package_id="pkg_001",
            version="1.0",
            decision=BindingDecision.MATCH_EXISTING,
            reason="cosine similarity 0.95",
        )
        assert b.decision == "match_existing"

    def test_create_new(self):
        b = CanonicalBinding(
            local_canonical_id="reg:test::b",
            global_canonical_id="gcn_new",
            package_id="pkg_001",
            version="1.0",
            decision=BindingDecision.CREATE_NEW,
            reason="no matching global node found",
        )
        assert b.decision == "create_new"

    def test_equivalent_candidate(self):
        b = CanonicalBinding(
            local_canonical_id="reg:test::c",
            global_canonical_id="gcn_equiv",
            package_id="pkg_002",
            version="2.0",
            decision=BindingDecision.EQUIVALENT_CANDIDATE,
            reason="independent evidence from different premises",
        )
        assert b.decision == "equivalent_candidate"
