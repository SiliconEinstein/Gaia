"""Tests for Knowledge data model."""

import pytest
from gaia.gaia_ir import Knowledge, KnowledgeType, Parameter, LocalCanonicalRef, PackageRef


class TestKnowledgeType:
    def test_three_types(self):
        assert set(KnowledgeType) == {"claim", "setting", "question"}

    def test_no_template(self):
        with pytest.raises(ValueError):
            KnowledgeType("template")


class TestKnowledgeCreation:
    def test_explicit_id(self):
        k = Knowledge(id="gcn_abc123", type=KnowledgeType.CLAIM)
        assert k.id == "gcn_abc123"

    def test_content_addressed_id(self):
        k = Knowledge(
            type=KnowledgeType.CLAIM,
            content="YBCO is a superconductor",
            package_id="pkg_001",
        )
        assert k.id.startswith("lcn_")
        assert len(k.id) == 4 + 16  # "lcn_" + 16 hex chars

    def test_same_content_same_package_same_id(self):
        k1 = Knowledge(type="claim", content="test", package_id="pkg")
        k2 = Knowledge(type="claim", content="test", package_id="pkg")
        assert k1.id == k2.id

    def test_different_package_different_id(self):
        k1 = Knowledge(type="claim", content="test", package_id="pkg_a")
        k2 = Knowledge(type="claim", content="test", package_id="pkg_b")
        assert k1.id != k2.id

    def test_different_package_same_content_hash(self):
        k1 = Knowledge(type="claim", content="test", package_id="pkg_a")
        k2 = Knowledge(type="claim", content="test", package_id="pkg_b")
        assert k1.content_hash == k2.content_hash

    def test_content_hash_auto_computed(self):
        k = Knowledge(type="claim", content="test", package_id="pkg")
        assert k.content_hash is not None
        assert len(k.content_hash) == 64  # full SHA-256 hex

    def test_different_content_different_content_hash(self):
        k1 = Knowledge(type="claim", content="A", package_id="pkg")
        k2 = Knowledge(type="claim", content="B", package_id="pkg")
        assert k1.content_hash != k2.content_hash

    def test_different_type_different_content_hash(self):
        k1 = Knowledge(type="claim", content="X", package_id="pkg")
        k2 = Knowledge(type="setting", content="X", package_id="pkg")
        assert k1.content_hash != k2.content_hash

    def test_different_content_different_id(self):
        k1 = Knowledge(type="claim", content="A", package_id="pkg")
        k2 = Knowledge(type="claim", content="B", package_id="pkg")
        assert k1.id != k2.id

    def test_requires_id_or_content_and_package(self):
        with pytest.raises(ValueError):
            Knowledge(type=KnowledgeType.CLAIM)

    def test_content_without_package_id_raises(self):
        with pytest.raises(ValueError):
            Knowledge(type=KnowledgeType.CLAIM, content="test")


class TestKnowledgeParameters:
    def test_closed_claim_empty_params(self):
        k = Knowledge(id="gcn_1", type="claim", parameters=[])
        assert k.parameters == []

    def test_universal_claim_with_params(self):
        k = Knowledge(
            id="gcn_2",
            type="claim",
            parameters=[Parameter(name="x", type="material")],
        )
        assert len(k.parameters) == 1
        assert k.parameters[0].name == "x"

    def test_params_affect_id(self):
        k1 = Knowledge(type="claim", content="P({x})", package_id="pkg")
        k2 = Knowledge(
            type="claim",
            content="P({x})",
            package_id="pkg",
            parameters=[Parameter(name="x", type="T")],
        )
        assert k1.id != k2.id


class TestKnowledgeLocalGlobal:
    def test_local_knowledge(self):
        k = Knowledge(
            type="claim",
            content="local content",
            package_id="pkg_001",
            provenance=[PackageRef(package_id="pkg_001", version="1.0")],
        )
        assert k.id.startswith("lcn_")
        assert k.content == "local content"
        assert k.representative_lcn is None

    def test_global_knowledge(self):
        k = Knowledge(
            id="gcn_abc123",
            type="claim",
            representative_lcn=LocalCanonicalRef(
                local_canonical_id="lcn_xyz",
                package_id="pkg_001",
                version="1.0",
            ),
            local_members=[
                LocalCanonicalRef(
                    local_canonical_id="lcn_xyz", package_id="pkg_001", version="1.0"
                ),
            ],
        )
        assert k.content is None
        assert k.content_hash is None  # no content -> no auto content_hash
        assert k.representative_lcn.local_canonical_id == "lcn_xyz"

    def test_global_with_explicit_content_hash(self):
        """Global node can have content_hash set explicitly (synced from representative)."""
        k = Knowledge(
            id="gcn_abc123",
            type="claim",
            content_hash="abcd1234" * 8,
        )
        assert k.content_hash == "abcd1234" * 8

    def test_global_with_direct_content(self):
        """LKM-created Knowledge (e.g. FormalExpr intermediate) can have content at global."""
        k = Knowledge(id="gcn_direct", type="claim", content="conjunction result")
        assert k.content == "conjunction result"


class TestKnowledgeMetadata:
    def test_metadata_refs(self):
        k = Knowledge(
            id="gcn_1",
            type="claim",
            metadata={"refs": ["gcn_2", "gcn_3"], "schema": "observation"},
        )
        assert k.metadata["refs"] == ["gcn_2", "gcn_3"]
