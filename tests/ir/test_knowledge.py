"""Tests for Knowledge data model."""

import pytest
from gaia.ir import Knowledge, KnowledgeType, Parameter, PackageRef
from gaia.ir.knowledge import make_qid, is_qid


class TestMakeQid:
    def test_basic(self):
        assert make_qid("reg", "my_pkg", "my_label") == "reg:my_pkg::my_label"

    def test_paper_namespace(self):
        assert make_qid("paper", "10_1038_abc", "cmb_spectrum") == "paper:10_1038_abc::cmb_spectrum"


class TestIsQid:
    def test_valid_qid(self):
        assert is_qid("reg:my_pkg::my_label")

    def test_valid_paper_qid(self):
        assert is_qid("paper:article_123::finding_a")

    def test_valid_doi_derived_package(self):
        assert is_qid("paper:10_1038_abc::cmb_spectrum")

    def test_valid_generated_label(self):
        assert is_qid("reg:test::__conjunction_result_a1b2c3d4")

    def test_invalid_gcn(self):
        assert not is_qid("gcn_abc123")

    def test_invalid_lcn(self):
        assert not is_qid("lcn_abc123")

    def test_invalid_no_double_colon(self):
        assert not is_qid("reg:pkg:label")

    def test_invalid_empty(self):
        assert not is_qid("")

    def test_invalid_uppercase(self):
        assert not is_qid("Reg:pkg::label")


class TestKnowledgeType:
    def test_three_types(self):
        assert set(KnowledgeType) == {"claim", "setting", "question"}

    def test_no_template(self):
        with pytest.raises(ValueError):
            KnowledgeType("template")


class TestKnowledgeCreation:
    def test_explicit_qid(self):
        k = Knowledge(id="reg:pkg::x", type=KnowledgeType.CLAIM, content="test", label="x")
        assert k.id == "reg:pkg::x"
        assert k.label == "x"

    def test_label_only_defers_id(self):
        """Knowledge with label but no id — id assigned later by graph."""
        k = Knowledge(label="x", type=KnowledgeType.CLAIM, content="test")
        assert k.id is None
        assert k.label == "x"

    def test_no_id_no_label_raises(self):
        with pytest.raises(ValueError, match="id.*label"):
            Knowledge(type=KnowledgeType.CLAIM, content="test")

    def test_content_hash_auto_computed_with_id(self):
        k = Knowledge(id="reg:pkg::x", type="claim", content="test", label="x")
        assert k.content_hash is not None
        assert len(k.content_hash) == 64

    def test_content_hash_auto_computed_with_label_only(self):
        k = Knowledge(label="x", type="claim", content="test")
        assert k.content_hash is not None
        assert len(k.content_hash) == 64

    def test_same_content_same_hash_different_packages(self):
        """Content hash does not include package info — same content = same hash."""
        k1 = Knowledge(id="reg:pkg_a::x", type="claim", content="test", label="x")
        k2 = Knowledge(id="reg:pkg_b::y", type="claim", content="test", label="y")
        assert k1.content_hash == k2.content_hash

    def test_explicit_wrong_content_hash_rejected(self):
        with pytest.raises(ValueError, match="content_hash"):
            Knowledge(
                id="reg:pkg::x",
                type="claim",
                content="test",
                label="x",
                content_hash="0" * 64,
            )

    def test_different_content_different_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="A", label="a")
        k2 = Knowledge(id="reg:pkg::b", type="claim", content="B", label="b")
        assert k1.content_hash != k2.content_hash

    def test_different_type_different_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="X", label="a")
        k2 = Knowledge(id="reg:pkg::b", type="setting", content="X", label="b")
        assert k1.content_hash != k2.content_hash


class TestKnowledgeParameters:
    def test_closed_claim_empty_params(self):
        k = Knowledge(id="reg:test::k1", type="claim", content="test", parameters=[])
        assert k.parameters == []

    def test_universal_claim_with_params(self):
        k = Knowledge(
            id="reg:test::k2",
            type="claim",
            content="P({x})",
            parameters=[Parameter(name="x", type="material")],
        )
        assert len(k.parameters) == 1

    def test_params_affect_content_hash(self):
        k1 = Knowledge(id="reg:pkg::a", type="claim", content="P({x})", label="a")
        k2 = Knowledge(
            id="reg:pkg::b",
            type="claim",
            content="P({x})",
            label="b",
            parameters=[Parameter(name="x", type="T")],
        )
        assert k1.content_hash != k2.content_hash


class TestKnowledgeLocalGlobal:
    def test_local_with_qid(self):
        k = Knowledge(
            id="reg:pkg::vacuum_prediction",
            type="claim",
            content="In vacuum all bodies fall equally fast",
            label="vacuum_prediction",
            provenance=[PackageRef(package_id="pkg", version="1.0")],
        )
        assert k.id == "reg:pkg::vacuum_prediction"
        assert k.label == "vacuum_prediction"


class TestKnowledgeMetadata:
    def test_metadata_refs(self):
        k = Knowledge(
            id="reg:test::k1",
            type="claim",
            content="test",
            metadata={"refs": ["reg:test::k2", "reg:test::k3"]},
        )
        assert k.metadata["refs"] == ["reg:test::k2", "reg:test::k3"]
