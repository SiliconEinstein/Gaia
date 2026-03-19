"""Additional coverage tests for PR #161 (dedup-replace-classification).

Targets uncovered lines in: libs/llm.py, cleanup.py, reviewer.py, scheduler.py, clustering.py.
"""

from unittest.mock import AsyncMock, MagicMock, patch

from libs.curation.audit import AuditLog
from libs.curation.cleanup import execute_cleanup, generate_cleanup_plan
from libs.curation.models import (
    ConflictCandidate,
    CurationPlan,
    CurationSuggestion,
    StructureReport,
    StructureIssue,
)
from libs.global_graph.models import GlobalCanonicalNode
from libs.storage.models import FactorNode


# ── Shared fixtures ──

_NODES = {
    "gcn_a": GlobalCanonicalNode(
        global_canonical_id="gcn_a",
        knowledge_type="claim",
        representative_content="F = ma",
    ),
    "gcn_b": GlobalCanonicalNode(
        global_canonical_id="gcn_b",
        knowledge_type="claim",
        representative_content="Force equals mass times acceleration",
    ),
    "gcn_c": GlobalCanonicalNode(
        global_canonical_id="gcn_c",
        knowledge_type="claim",
        representative_content="Energy equals mass times c squared",
    ),
}


# ═══════════════════════════════════════════════════════════════════════
# libs/llm.py — _normalize_model + llm_completion
# ═══════════════════════════════════════════════════════════════════════


class TestLLMNormalizeModel:
    def test_already_openai_prefix(self):
        from libs.llm import _normalize_model

        assert _normalize_model("openai/chenkun/gpt-5-mini") == "openai/chenkun/gpt-5-mini"

    def test_bare_model_gets_prefix(self):
        from libs.llm import _normalize_model

        assert _normalize_model("chenkun/gpt-5-mini") == "openai/chenkun/gpt-5-mini"

    def test_anthropic_provider_unchanged(self):
        from libs.llm import _normalize_model

        assert _normalize_model("anthropic/claude-3") == "anthropic/claude-3"

    def test_azure_provider_unchanged(self):
        from libs.llm import _normalize_model

        assert _normalize_model("azure/gpt-4") == "azure/gpt-4"

    def test_ollama_provider_unchanged(self):
        from libs.llm import _normalize_model

        assert _normalize_model("ollama/llama3") == "ollama/llama3"

    def test_default_model_used(self):
        from libs.llm import DEFAULT_MODEL, _normalize_model

        assert _normalize_model(DEFAULT_MODEL) == DEFAULT_MODEL

    async def test_llm_completion_default_model(self):
        from libs.llm import llm_completion

        mock_resp = MagicMock()
        with patch("libs.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp):
            result = await llm_completion(messages=[{"role": "user", "content": "hi"}])
        assert result is mock_resp

    async def test_llm_completion_custom_model(self):
        from libs.llm import llm_completion

        mock_resp = MagicMock()
        with patch(
            "libs.llm.litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp
        ) as mock_call:
            await llm_completion(model="my/model", messages=[])
        mock_call.assert_called_once()
        assert mock_call.call_args.kwargs["model"] == "openai/my/model"


# ═══════════════════════════════════════════════════════════════════════
# cleanup.py — uncovered branches
# ═══════════════════════════════════════════════════════════════════════


class TestCleanupAutoApproveFailure:
    """Line 118: auto-approve suggestion that fails _execute_suggestion."""

    async def test_auto_approve_merge_wrong_target_count_skipped(self):
        """Merge with 3 target_ids fails and gets skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="merge",
                    target_ids=["gcn_a", "gcn_b", "gcn_c"],
                    confidence=0.99,
                    reason="too many targets",
                    evidence={},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1
        assert len(result.executed) == 0

    async def test_auto_approve_merge_missing_node_skipped(self):
        """Merge where source node doesn't exist → skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="merge",
                    target_ids=["gcn_missing", "gcn_a"],
                    confidence=0.99,
                    reason="node gone",
                    evidence={},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1

    async def test_constraint_wrong_target_count(self):
        """create_equivalence with 3 targets → skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="create_equivalence",
                    target_ids=["gcn_a", "gcn_b", "gcn_c"],
                    confidence=0.99,
                    reason="too many",
                    evidence={},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1


class TestCleanupCreateAbstraction:
    """Lines 194-208: create_abstraction execution path."""

    async def test_create_abstraction_executed(self):
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="create_abstraction",
                    target_ids=["gcn_a", "gcn_b"],
                    confidence=0.99,
                    reason="shared physics law",
                    evidence={"abstraction": "Newton's second law of motion"},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.executed) == 1
        assert result.executed[0].operation == "create_abstraction"
        # Schema node should be added to nodes
        assert len(nodes) > 3
        # Instantiation factors should be created
        assert len(factors) >= 2

    async def test_create_abstraction_too_few_targets(self):
        """create_abstraction with <2 targets → skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="create_abstraction",
                    target_ids=["gcn_a"],
                    confidence=0.99,
                    reason="only one",
                    evidence={"abstraction": "Something"},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1

    async def test_create_abstraction_no_content(self):
        """create_abstraction with empty abstraction content → skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="create_abstraction",
                    target_ids=["gcn_a", "gcn_b"],
                    confidence=0.99,
                    reason="no content",
                    evidence={"abstraction": ""},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1


class TestCleanupUnknownOp:
    """Lines 249-250: unknown operation type (bypassing Literal validation)."""

    async def test_unknown_operation_skipped(self):
        from libs.curation.cleanup import _execute_suggestion

        s = CurationSuggestion(
            operation="merge",  # valid for construction
            target_ids=["gcn_a"],
            confidence=0.99,
            reason="unknown",
            evidence={},
        )
        # Bypass Literal validation to test the unknown-op fallthrough
        object.__setattr__(s, "operation", "teleport_node")
        result = _execute_suggestion(s, dict(_NODES), [])
        assert result is None


class TestCleanupArchiveOrphanAllMissing:
    """Line 240: archive_orphan where all target nodes are already gone."""

    async def test_archive_orphan_all_missing(self):
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="archive_orphan",
                    target_ids=["gcn_nonexistent_1", "gcn_nonexistent_2"],
                    confidence=0.99,
                    reason="already gone",
                    evidence={},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1


class TestCleanupNeedsReviewRejected:
    """Lines 131-132: needs_review suggestion rejected by reviewer."""

    async def test_needs_review_rejected_skipped(self):
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="merge",
                    target_ids=["gcn_a", "gcn_b"],
                    confidence=0.80,  # needs_review tier
                    reason="maybe",
                    evidence={"cosine": 0.50},  # too low → reject
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1
        assert len(result.executed) == 0

    async def test_needs_review_approved_but_execution_fails(self):
        """Reviewer approves but execution fails → still skipped."""
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="merge",
                    target_ids=["gcn_a", "gcn_missing"],
                    confidence=0.85,
                    reason="test",
                    evidence={"cosine": 0.95},  # high cosine → approve
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1


class TestCleanupDiscardTier:
    """Line 136: discard tier goes to skipped."""

    async def test_discard_tier_skipped(self):
        plan = CurationPlan(
            suggestions=[
                CurationSuggestion(
                    operation="merge",
                    target_ids=["gcn_a", "gcn_b"],
                    confidence=0.50,  # discard tier (< 0.70)
                    reason="low confidence",
                    evidence={},
                ),
            ]
        )
        nodes = dict(_NODES)
        factors: list[FactorNode] = []
        audit_log = AuditLog()
        result = await execute_cleanup(plan, nodes, factors, audit_log)
        assert len(result.skipped) == 1
        assert len(result.executed) == 0


# ═══════════════════════════════════════════════════════════════════════
# generate_cleanup_plan — conflict + structure issue conversion
# ═══════════════════════════════════════════════════════════════════════


class TestGenerateCleanupPlan:
    def test_conflict_candidates_converted(self):
        candidates = [
            ConflictCandidate(
                node_a_id="gcn_a",
                node_b_id="gcn_b",
                signal_type="oscillation",
                strength=0.85,
                detail={"source": "bp"},
            )
        ]
        plan = generate_cleanup_plan([], candidates, StructureReport())
        assert len(plan.suggestions) == 1
        assert plan.suggestions[0].operation == "create_contradiction"
        assert plan.suggestions[0].confidence == 0.85

    def test_structure_issues_converted(self):
        report = StructureReport(
            issues=[
                StructureIssue(
                    issue_type="dangling_factor",
                    severity="error",
                    detail="Factor f1 references missing node",
                    factor_ids=["f1"],
                ),
                StructureIssue(
                    issue_type="orphan_node",
                    severity="warning",
                    detail="Node gcn_orphan has no connections",
                    node_ids=["gcn_orphan"],
                ),
            ]
        )
        plan = generate_cleanup_plan([], [], report)
        assert len(plan.suggestions) == 2
        ops = {s.operation for s in plan.suggestions}
        assert ops == {"fix_dangling_factor", "archive_orphan"}


# ═══════════════════════════════════════════════════════════════════════
# reviewer.py — uncovered rule-based paths
# ═══════════════════════════════════════════════════════════════════════


class TestReviewerRulesMorePaths:
    def test_create_contradiction_approve_by_drop(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="create_contradiction",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.60,  # below 0.80
            reason="conflict",
            evidence={"belief_drop": 0.20},  # >= 0.15
        )
        assert reviewer._review_rules(s) == "approve"

    def test_create_contradiction_reject(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="create_contradiction",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.60,
            reason="weak conflict",
            evidence={"belief_drop": 0.05},  # < 0.15 and confidence < 0.80
        )
        assert reviewer._review_rules(s) == "reject"

    def test_create_equivalence_reject(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="create_equivalence",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.80,
            reason="similar",
            evidence={"cosine": 0.70},  # < 0.85
        )
        assert reviewer._review_rules(s) == "reject"

    def test_create_abstraction_approve(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="create_abstraction",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.85,
            reason="shared pattern",
            evidence={},
        )
        assert reviewer._review_rules(s) == "approve"

    def test_create_abstraction_reject(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="create_abstraction",
            target_ids=["gcn_a", "gcn_b"],
            confidence=0.60,
            reason="weak",
            evidence={},
        )
        assert reviewer._review_rules(s) == "reject"

    def test_unknown_operation_reject(self):
        from libs.curation.reviewer import CurationReviewer

        reviewer = CurationReviewer(model=None)
        s = CurationSuggestion(
            operation="merge",  # valid for construction
            target_ids=["gcn_a"],
            confidence=0.90,
            reason="",
            evidence={},
        )
        # Bypass Literal validation
        object.__setattr__(s, "operation", "warp_drive")
        assert reviewer._review_rules(s) == "reject"


# ═══════════════════════════════════════════════════════════════════════
# scheduler.py — skip_abstraction + abstraction integration + persist
# ═══════════════════════════════════════════════════════════════════════


class TestSchedulerPaths:
    async def test_empty_nodes_early_return(self):
        """No nodes → early return with empty result."""
        from libs.curation.scheduler import run_curation

        mgr = AsyncMock()
        mgr.list_global_nodes = AsyncMock(return_value=[])
        mgr.list_factors = AsyncMock(return_value=[])

        result = await run_curation(mgr)
        assert result.structure_report is not None
        assert len(result.executed) == 0

    async def test_skip_abstraction_path(self):
        """skip_abstraction=True skips the abstraction agent."""
        from libs.curation.scheduler import run_curation

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_x",
                knowledge_type="claim",
                representative_content="Unique claim X",
            ),
        ]
        mgr = AsyncMock()
        mgr.list_global_nodes = AsyncMock(return_value=nodes)
        mgr.list_factors = AsyncMock(return_value=[])
        mgr.upsert_global_nodes = AsyncMock()
        mgr.write_factors = AsyncMock()

        result = await run_curation(
            mgr,
            skip_abstraction=True,
            skip_conflict_detection=True,
        )
        assert result.structure_report is not None

    async def test_scheduler_with_dedup_persists(self):
        """Scheduler with exact duplicates → merge executed → persists to storage."""
        from libs.curation.scheduler import run_curation

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_dup1",
                knowledge_type="claim",
                representative_content="The sky is blue",
            ),
            GlobalCanonicalNode(
                global_canonical_id="gcn_dup2",
                knowledge_type="claim",
                representative_content="The sky is blue",
            ),
        ]
        mgr = AsyncMock()
        mgr.list_global_nodes = AsyncMock(return_value=nodes)
        mgr.list_factors = AsyncMock(return_value=[])
        mgr.upsert_global_nodes = AsyncMock()
        mgr.write_factors = AsyncMock()

        result = await run_curation(
            mgr,
            skip_abstraction=True,
            skip_conflict_detection=True,
        )
        # Merge + possibly orphan archive
        merge_ops = [s for s in result.executed if s.operation == "merge"]
        assert len(merge_ops) == 1
        # Verify persistence was called
        mgr.upsert_global_nodes.assert_called_once()
        mgr.write_factors.assert_called_once()

    async def test_scheduler_schema_nodes_excluded_from_clustering(self):
        """Schema nodes should be excluded from clustering."""
        from libs.curation.scheduler import run_curation

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_claim",
                knowledge_type="claim",
                representative_content="Normal claim",
            ),
            GlobalCanonicalNode(
                global_canonical_id="gcn_schema",
                knowledge_type="claim",
                kind="schema",
                representative_content="Normal claim",  # same content but schema
            ),
        ]
        mgr = AsyncMock()
        mgr.list_global_nodes = AsyncMock(return_value=nodes)
        mgr.list_factors = AsyncMock(return_value=[])
        mgr.upsert_global_nodes = AsyncMock()
        mgr.write_factors = AsyncMock()

        result = await run_curation(
            mgr,
            skip_abstraction=True,
            skip_conflict_detection=True,
        )
        # Should still find the dedup match (dedup runs on all nodes)
        merge_ops = [s for s in result.executed if s.operation == "merge"]
        assert len(merge_ops) == 1


# ═══════════════════════════════════════════════════════════════════════
# scheduler.py — _build_factor_graph_from_storage
# ═══════════════════════════════════════════════════════════════════════


class TestBuildFactorGraph:
    def test_basic_reasoning_factor(self):
        from libs.curation.scheduler import _build_factor_graph_from_storage

        nodes = {"n1": MagicMock(), "n2": MagicMock()}
        factors = [
            FactorNode(
                factor_id="f1",
                type="reasoning",
                premises=["n1"],
                conclusion="n2",
                package_id="pkg",
                metadata={"edge_type": "deduction"},
            ),
        ]
        fg, s2i, i2s = _build_factor_graph_from_storage(nodes, factors)
        assert len(fg.variables) == 2
        assert len(fg.factors) == 1

    def test_constraint_factor(self):
        from libs.curation.scheduler import _build_factor_graph_from_storage

        nodes = {"n1": MagicMock(), "n2": MagicMock()}
        factors = [
            FactorNode(
                factor_id="f1",
                type="mutex_constraint",
                premises=["n1", "n2"],
                conclusion="gate",
                package_id="pkg",
                metadata={"edge_type": "relation_contradiction"},
            ),
        ]
        fg, s2i, i2s = _build_factor_graph_from_storage(nodes, factors)
        assert len(fg.factors) == 1

    def test_factor_with_missing_premise_skipped(self):
        from libs.curation.scheduler import _build_factor_graph_from_storage

        nodes = {"n1": MagicMock()}
        factors = [
            FactorNode(
                factor_id="f1",
                type="reasoning",
                premises=["n_missing"],
                conclusion="n1",
                package_id="pkg",
                metadata={},
            ),
        ]
        fg, _, _ = _build_factor_graph_from_storage(nodes, factors)
        # Premise not in nodes → premises_int is empty → skipped
        assert len(fg.factors) == 0

    def test_factor_no_metadata(self):
        from libs.curation.scheduler import _build_factor_graph_from_storage

        nodes = {"n1": MagicMock(), "n2": MagicMock()}
        factors = [
            FactorNode(
                factor_id="f1",
                type="reasoning",
                premises=["n1"],
                conclusion="n2",
                package_id="pkg",
                metadata=None,
            ),
        ]
        fg, _, _ = _build_factor_graph_from_storage(nodes, factors)
        assert len(fg.factors) == 1


# ═══════════════════════════════════════════════════════════════════════
# clustering.py — exclude_pairs
# ═══════════════════════════════════════════════════════════════════════


class TestClusteringExcludePairs:
    async def test_exclude_pairs_prevents_clustering(self):
        from libs.curation.clustering import cluster_similar_nodes

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_a",
                knowledge_type="claim",
                representative_content="identical content",
            ),
            GlobalCanonicalNode(
                global_canonical_id="gcn_b",
                knowledge_type="claim",
                representative_content="identical content",
            ),
        ]
        # Exclude the pair → no clusters
        clusters = await cluster_similar_nodes(
            nodes,
            threshold=0.50,
            exclude_pairs={("gcn_a", "gcn_b")},
        )
        assert len(clusters) == 0

    async def test_single_node_no_clusters(self):
        from libs.curation.clustering import cluster_similar_nodes

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_a",
                knowledge_type="claim",
                representative_content="alone",
            ),
        ]
        clusters = await cluster_similar_nodes(nodes, threshold=0.50)
        assert len(clusters) == 0

    async def test_different_knowledge_types_not_clustered(self):
        from libs.curation.clustering import cluster_similar_nodes

        nodes = [
            GlobalCanonicalNode(
                global_canonical_id="gcn_a",
                knowledge_type="claim",
                representative_content="identical content",
            ),
            GlobalCanonicalNode(
                global_canonical_id="gcn_b",
                knowledge_type="question",
                representative_content="identical content",
            ),
        ]
        clusters = await cluster_similar_nodes(nodes, threshold=0.50)
        assert len(clusters) == 0
