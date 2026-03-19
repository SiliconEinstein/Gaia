"""Tests for the abstraction agent pipeline."""

from __future__ import annotations

import json
from hashlib import sha256
from unittest.mock import MagicMock, patch

from libs.curation.abstraction import AbstractionAgent, _build_claims_text, _parse_json
from libs.curation.models import (
    AbstractionGroup,
    ClusterGroup,
    VerificationResult,
)
from libs.curation.operations import create_abstraction

from .conftest import ID_FMA_1, ID_FMA_2, ID_GRAVITY, ID_HEAT, ID_MASS_V


# ── Helpers ──


def _mock_response(content: str) -> MagicMock:
    """Create a mock litellm response."""
    msg = MagicMock()
    msg.content = content
    choice = MagicMock()
    choice.message = msg
    resp = MagicMock()
    resp.choices = [choice]
    return resp


# ── _parse_json tests ──


def test_parse_json_valid():
    """Valid JSON wrapped in markdown code fences is extracted."""
    text = '```json\n{"groups": [{"id": 1}]}\n```'
    result = _parse_json(text)
    assert result == {"groups": [{"id": 1}]}


def test_parse_json_malformed():
    """Malformed input returns None."""
    assert _parse_json("no json here") is None
    assert _parse_json("{broken: json}") is None
    assert _parse_json("") is None


def test_parse_json_embedded():
    """JSON embedded in surrounding prose is extracted."""
    text = 'Here is the result:\n{"key": "value", "nested": {"a": 1}}\nEnd of response.'
    result = _parse_json(text)
    assert result == {"key": "value", "nested": {"a": 1}}


# ── _build_claims_text tests ──


def test_build_claims_text(physics_node_map):
    """Claims text is formatted with headers and content."""
    text = _build_claims_text([ID_FMA_1, ID_HEAT], physics_node_map)
    assert f"## Claim {ID_FMA_1}:" in text
    assert "Newton's second law" in text
    assert f"## Claim {ID_HEAT}:" in text
    assert "Heat is a form of energy" in text


# ── create_abstraction tests ──


def test_create_abstraction_deterministic_ids():
    """create_abstraction produces deterministic IDs from sorted member IDs."""
    members = [ID_FMA_2, ID_FMA_1]  # unsorted
    result = create_abstraction("Force law", members, reason="test")

    sorted_members = sorted(members)
    digest = sha256(":".join(sorted_members).encode()).hexdigest()[:16]
    expected_id = f"gcn_schema_{digest}"

    assert result.schema_node.global_canonical_id == expected_id
    assert result.schema_node.representative_content == "Force law"
    assert result.schema_node.kind == "schema"
    assert result.schema_node.metadata["abstraction_source_nodes"] == sorted_members

    # Same inputs in different order produce same ID
    result2 = create_abstraction("Force law", [ID_FMA_1, ID_FMA_2], reason="test")
    assert result2.schema_node.global_canonical_id == expected_id


def test_create_abstraction_factor_structure():
    """Each member gets an instantiation factor with correct premises/conclusion."""
    members = [ID_FMA_1, ID_HEAT]
    result = create_abstraction("Common energy", members, reason="test")

    schema_id = result.schema_node.global_canonical_id
    assert len(result.instantiation_factors) == 2

    for factor in result.instantiation_factors:
        assert factor.type == "instantiation"
        assert factor.premises == [schema_id]
        assert factor.conclusion in sorted(members)
        assert factor.package_id == "__curation__"
        assert factor.metadata["curation_created"] is True

    # Verify each member has exactly one factor
    conclusions = {f.conclusion for f in result.instantiation_factors}
    assert conclusions == set(members)


# ── AbstractionAgent._abstract_cluster tests ──


@patch("litellm.acompletion")
async def test_abstract_cluster_parses_groups(mock_acompletion, physics_node_map):
    """_abstract_cluster parses LLM JSON into AbstractionGroup objects."""
    llm_json = json.dumps(
        {
            "groups": [
                {
                    "group_id": "G1",
                    "abstraction": "Force equals mass times acceleration",
                    "member_ids": [ID_FMA_1, ID_FMA_2],
                    "reason": "Both express F=ma",
                }
            ]
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_FMA_1, ID_FMA_2])
    groups = await agent._abstract_cluster(cluster, physics_node_map)

    assert len(groups) == 1
    assert groups[0].group_id == "G1"
    assert groups[0].abstraction_content == "Force equals mass times acceleration"
    assert groups[0].member_node_ids == [ID_FMA_1, ID_FMA_2]


@patch("litellm.acompletion")
async def test_abstract_cluster_skips_invalid_members(mock_acompletion, physics_node_map):
    """Groups with invalid member IDs have those members filtered out."""
    llm_json = json.dumps(
        {
            "groups": [
                {
                    "group_id": "G1",
                    "abstraction": "Force law",
                    "member_ids": [ID_FMA_1, "gcn_nonexistent", ID_FMA_2],
                    "reason": "test",
                },
                {
                    "group_id": "G2",
                    "abstraction": "solo",
                    "member_ids": [ID_FMA_1, "gcn_nonexistent"],
                    "reason": "only one valid member",
                },
            ]
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_FMA_1, ID_FMA_2])
    groups = await agent._abstract_cluster(cluster, physics_node_map)

    # G1 keeps 2 valid members, G2 is dropped (only 1 valid)
    assert len(groups) == 1
    assert groups[0].member_node_ids == [ID_FMA_1, ID_FMA_2]


# ── AbstractionAgent._verify_abstraction tests ──


@patch("litellm.acompletion")
async def test_verify_passes(mock_acompletion, physics_node_map):
    """Verification with passed=true returns a passing VerificationResult."""
    llm_json = json.dumps(
        {
            "passed": True,
            "checks": [
                {"member_id": ID_FMA_1, "entails": True, "reason": "ok"},
                {"member_id": ID_FMA_2, "entails": True, "reason": "ok"},
            ],
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="F=ma",
        member_node_ids=[ID_FMA_1, ID_FMA_2],
        reason="test",
    )
    result = await agent._verify_abstraction(group, physics_node_map)

    assert result.passed is True
    assert result.group_id == "G1"
    assert len(result.checks) == 2
    assert all(c.entails for c in result.checks)


@patch("litellm.acompletion")
async def test_verify_catches_union_error(mock_acompletion, physics_node_map):
    """Verification with union_error=true is captured correctly."""
    llm_json = json.dumps(
        {
            "passed": False,
            "union_error": True,
            "union_error_detail": "Claims are not logically compatible",
            "checks": [
                {"member_id": ID_FMA_1, "entails": True, "reason": "ok"},
                {"member_id": ID_FMA_2, "entails": False, "reason": "contradicts"},
            ],
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="F=ma",
        member_node_ids=[ID_FMA_1, ID_FMA_2],
        reason="test",
    )
    result = await agent._verify_abstraction(group, physics_node_map)

    assert result.passed is False
    assert result.union_error is True
    assert result.union_error_detail == "Claims are not logically compatible"


# ── AbstractionAgent._refine_abstraction tests ──


@patch("litellm.acompletion")
async def test_refine_rewrites(mock_acompletion, physics_node_map):
    """Refine with action=rewrite returns an updated group."""
    llm_json = json.dumps(
        {
            "action": "rewrite",
            "revised_abstraction": "Revised F=ma statement",
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="Original",
        member_node_ids=[ID_FMA_1, ID_FMA_2],
        reason="test",
    )
    verification = VerificationResult(
        group_id="G1",
        passed=False,
        checks=[],
    )
    result = await agent._refine_abstraction(group, verification, physics_node_map)

    assert result is not None
    assert result.abstraction_content == "Revised F=ma statement"
    assert result.group_id == "G1"
    assert result.member_node_ids == [ID_FMA_1, ID_FMA_2]


@patch("litellm.acompletion")
async def test_refine_abandons(mock_acompletion, physics_node_map):
    """Refine with action=abandon returns None."""
    llm_json = json.dumps({"action": "abandon"})
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="Original",
        member_node_ids=[ID_FMA_1, ID_FMA_2],
        reason="test",
    )
    verification = VerificationResult(group_id="G1", passed=False, checks=[])
    result = await agent._refine_abstraction(group, verification, physics_node_map)

    assert result is None


@patch("litellm.acompletion")
async def test_refine_removes_members(mock_acompletion, physics_node_map):
    """Refine with action=remove_members drops failing member."""
    llm_json = json.dumps(
        {
            "action": "remove_members",
            "removed_ids": [ID_HEAT],
            "revised_abstraction": None,
            "reasoning": "Member does not fit the group",
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="Original abstraction",
        member_node_ids=[ID_FMA_1, ID_FMA_2, ID_HEAT],
        reason="test",
        contradiction_pairs=[(ID_FMA_1, ID_HEAT)],
    )
    verification = VerificationResult(group_id="G1", passed=False, checks=[])
    result = await agent._refine_abstraction(group, verification, physics_node_map)

    assert result is not None
    assert ID_HEAT not in result.member_node_ids
    assert ID_FMA_1 in result.member_node_ids
    assert ID_FMA_2 in result.member_node_ids
    assert result.abstraction_content == "Original abstraction"
    # Contradiction pairs involving removed member should be cleaned
    assert len(result.contradiction_pairs) == 0


@patch("litellm.acompletion")
async def test_refine_removes_members_too_few_remaining(mock_acompletion, physics_node_map):
    """Refine with remove_members leaving < 2 members returns None (abandon)."""
    llm_json = json.dumps(
        {
            "action": "remove_members",
            "removed_ids": [ID_FMA_2],
            "reasoning": "Member does not fit",
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="Original",
        member_node_ids=[ID_FMA_1, ID_FMA_2],
        reason="test",
    )
    verification = VerificationResult(group_id="G1", passed=False, checks=[])
    result = await agent._refine_abstraction(group, verification, physics_node_map)

    assert result is None


@patch("litellm.acompletion")
async def test_refine_removes_members_with_revised_abstraction(mock_acompletion, physics_node_map):
    """Refine with remove_members can also revise the abstraction text."""
    llm_json = json.dumps(
        {
            "action": "remove_members",
            "removed_ids": [ID_HEAT],
            "revised_abstraction": "Revised abstraction after removal",
            "reasoning": "Tightened after removing unrelated member",
        }
    )
    mock_acompletion.return_value = _mock_response(llm_json)

    agent = AbstractionAgent(model="test-model")
    group = AbstractionGroup(
        group_id="G1",
        abstraction_content="Original",
        member_node_ids=[ID_FMA_1, ID_FMA_2, ID_HEAT],
        reason="test",
    )
    verification = VerificationResult(group_id="G1", passed=False, checks=[])
    result = await agent._refine_abstraction(group, verification, physics_node_map)

    assert result is not None
    assert result.abstraction_content == "Revised abstraction after removal"
    assert len(result.member_node_ids) == 2


# ── AbstractionAgent.run tests ──


@patch("litellm.acompletion")
async def test_run_end_to_end(mock_acompletion, physics_node_map):
    """Full pipeline: abstract → verify (passed) → creates nodes/factors/suggestions."""
    abstract_json = json.dumps(
        {
            "groups": [
                {
                    "group_id": "G1",
                    "abstraction": "Force equals mass times acceleration",
                    "member_ids": [ID_FMA_1, ID_FMA_2],
                    "reason": "Both express Newton's second law",
                }
            ]
        }
    )
    verify_json = json.dumps(
        {
            "passed": True,
            "checks": [
                {"member_id": ID_FMA_1, "entails": True, "reason": "ok"},
                {"member_id": ID_FMA_2, "entails": True, "reason": "ok"},
            ],
        }
    )
    # First call = abstract, second call = verify
    mock_acompletion.side_effect = [
        _mock_response(abstract_json),
        _mock_response(verify_json),
    ]

    agent = AbstractionAgent(model="test-model")
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_FMA_1, ID_FMA_2])
    result = await agent.run([cluster], physics_node_map)

    assert len(result.new_nodes) == 1
    assert result.new_nodes[0].kind == "schema"
    assert len(result.new_factors) == 2  # one per member
    assert len(result.suggestions) == 1
    assert result.suggestions[0].operation == "create_abstraction"


async def test_run_skips_small_clusters(physics_node_map):
    """Cluster with fewer than 2 nodes produces an empty result."""
    agent = AbstractionAgent(model="test-model")
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_FMA_1])
    result = await agent.run([cluster], physics_node_map)

    assert len(result.new_nodes) == 0
    assert len(result.new_factors) == 0
    assert len(result.suggestions) == 0


async def test_run_no_model(physics_node_map):
    """Agent with model=None returns empty result without calling LLM."""
    agent = AbstractionAgent(model=None)
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_FMA_1, ID_FMA_2])
    result = await agent.run([cluster], physics_node_map)

    assert len(result.new_nodes) == 0
    assert len(result.new_factors) == 0
    assert len(result.suggestions) == 0


@patch("litellm.acompletion")
async def test_contradiction_pairs_extracted(mock_acompletion, physics_node_map):
    """Contradiction pairs from abstract step appear in result.contradiction_candidates."""
    abstract_json = json.dumps(
        {
            "groups": [
                {
                    "group_id": "G1",
                    "abstraction": "Mechanics principles",
                    "member_ids": [ID_GRAVITY, ID_MASS_V],
                    "reason": "Related to mechanics",
                    "contradiction_pairs": [[ID_GRAVITY, ID_MASS_V]],
                }
            ]
        }
    )
    verify_json = json.dumps(
        {
            "passed": True,
            "checks": [
                {"member_id": ID_GRAVITY, "entails": True, "reason": "ok"},
                {"member_id": ID_MASS_V, "entails": True, "reason": "ok"},
            ],
        }
    )
    mock_acompletion.side_effect = [
        _mock_response(abstract_json),
        _mock_response(verify_json),
    ]

    agent = AbstractionAgent(model="test-model")
    cluster = ClusterGroup(cluster_id="C1", node_ids=[ID_GRAVITY, ID_MASS_V])
    result = await agent.run([cluster], physics_node_map)

    assert len(result.contradiction_candidates) == 1
    cand = result.contradiction_candidates[0]
    assert cand.node_a_id == ID_GRAVITY
    assert cand.node_b_id == ID_MASS_V
    assert cand.signal_type == "sensitivity"
