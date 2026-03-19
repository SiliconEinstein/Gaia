"""Abstraction agent — three-step pipeline for extracting common conclusions.

Pipeline: abstract clusters → verify entailment → refine or abandon.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path

from libs.global_graph.models import GlobalCanonicalNode

from .models import (
    AbstractionGroup,
    AbstractionResult,
    ClusterGroup,
    ConflictCandidate,
    CurationSuggestion,
    VerificationCheck,
    VerificationResult,
)
from .operations import create_abstraction

logger = logging.getLogger(__name__)

_PROMPT_DIR = Path(__file__).parent / "prompts"
_JSON_RE = re.compile(r"\{[\s\S]*\}")


def _load_prompt(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    if path.exists():
        return path.read_text()
    return ""


def _parse_json(text: str) -> dict | None:
    """Extract the first JSON object from LLM output."""
    text = text.strip()
    match = _JSON_RE.search(text)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


def _build_claims_text(node_ids: list[str], nodes: dict[str, GlobalCanonicalNode]) -> str:
    """Format claims for LLM input."""
    lines: list[str] = []
    for nid in node_ids:
        node = nodes.get(nid)
        if node:
            lines.append(f"## Claim {nid}:")
            lines.append(node.representative_content)
            lines.append("")
    return "\n".join(lines)


class AbstractionAgent:
    """Three-step abstraction pipeline: abstract → verify → refine.

    Args:
        model: litellm model name. If None, pipeline is skipped.
        max_retries: Max refine attempts per group.
    """

    def __init__(
        self,
        model: str | None = "gpt-5-mini",
        max_retries: int = 1,
    ) -> None:
        self._model = model
        self._max_retries = max_retries
        self._abstract_prompt = _load_prompt("abstraction_agent")
        self._verify_prompt = _load_prompt("verify_abstraction")
        self._refine_prompt = _load_prompt("refine_abstraction")

    # ── Step 1: Abstract ──

    async def _abstract_cluster(
        self,
        cluster: ClusterGroup,
        nodes: dict[str, GlobalCanonicalNode],
    ) -> list[AbstractionGroup]:
        """Call LLM to find abstraction groups in a cluster."""
        import litellm

        claims_text = _build_claims_text(cluster.node_ids, nodes)
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._abstract_prompt},
                {"role": "user", "content": claims_text},
            ],
        )
        raw = response.choices[0].message.content
        parsed = _parse_json(raw)
        if not parsed:
            logger.warning("Failed to parse abstraction JSON for cluster %s", cluster.cluster_id)
            return []

        groups: list[AbstractionGroup] = []
        for g in parsed.get("groups", []):
            member_ids = g.get("member_ids", [])
            # Validate member_ids are in the cluster
            valid_members = [m for m in member_ids if m in nodes]
            if len(valid_members) < 2:
                continue
            groups.append(
                AbstractionGroup(
                    group_id=g.get("group_id", f"G{len(groups) + 1}"),
                    abstraction_content=g.get("abstraction", ""),
                    member_node_ids=valid_members,
                    reason=g.get("reason", ""),
                    contradiction_pairs=[
                        tuple(p) for p in g.get("contradiction_pairs", []) if len(p) == 2
                    ],
                )
            )
        return groups

    # ── Step 2: Verify ──

    async def _verify_abstraction(
        self,
        group: AbstractionGroup,
        nodes: dict[str, GlobalCanonicalNode],
    ) -> VerificationResult:
        """Call LLM to verify entailment for an abstraction group."""
        import litellm

        claims_text = _build_claims_text(group.member_node_ids, nodes)
        user_msg = (
            f"## Abstraction to verify:\n{group.abstraction_content}\n\n"
            f"## Member claims:\n{claims_text}"
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._verify_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = response.choices[0].message.content
        parsed = _parse_json(raw)
        if not parsed:
            logger.warning("Failed to parse verification JSON for group %s", group.group_id)
            return VerificationResult(group_id=group.group_id, passed=False)

        checks = [
            VerificationCheck(
                member_id=c.get("member_id", ""),
                entails=c.get("entails", False),
                reason=c.get("reason", ""),
            )
            for c in parsed.get("checks", [])
        ]
        return VerificationResult(
            group_id=group.group_id,
            passed=parsed.get("passed", False),
            checks=checks,
            union_error=parsed.get("union_error", False),
            union_error_detail=parsed.get("union_error_detail", ""),
        )

    # ── Step 3: Refine ──

    async def _refine_abstraction(
        self,
        group: AbstractionGroup,
        verification: VerificationResult,
        nodes: dict[str, GlobalCanonicalNode],
    ) -> AbstractionGroup | None:
        """Call LLM to fix a failed abstraction. Returns refined group or None if abandoned."""
        import litellm

        claims_text = _build_claims_text(group.member_node_ids, nodes)
        feedback_lines = []
        for check in verification.checks:
            status = "PASS" if check.entails else "FAIL"
            feedback_lines.append(f"- {check.member_id}: {status} — {check.reason}")
        if verification.union_error:
            feedback_lines.append(f"- UNION ERROR: {verification.union_error_detail}")

        user_msg = (
            f"## Current abstraction:\n{group.abstraction_content}\n\n"
            f"## Member claims:\n{claims_text}\n"
            f"## Verification feedback:\n" + "\n".join(feedback_lines)
        )

        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._refine_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        raw = response.choices[0].message.content
        parsed = _parse_json(raw)
        if not parsed:
            logger.warning("Failed to parse refine JSON for group %s", group.group_id)
            return None

        action = parsed.get("action", "abandon")
        reasoning = parsed.get("reasoning", "")
        history_entry = {"action": action, "reasoning": reasoning}

        if action == "rewrite":
            revised = parsed.get("revised_abstraction", "")
            if revised:
                history = list(group.refine_history) + [history_entry]
                return group.model_copy(
                    update={"abstraction_content": revised, "refine_history": history}
                )

        elif action == "remove_members":
            removed_ids = set(parsed.get("removed_ids", []))
            if not removed_ids:
                return None
            remaining = [m for m in group.member_node_ids if m not in removed_ids]
            if len(remaining) < 2:
                logger.info(
                    "remove_members would leave < 2 members for group %s, abandoning",
                    group.group_id,
                )
                return None
            history_entry["removed_ids"] = list(removed_ids)
            updates: dict = {
                "member_node_ids": remaining,
                "refine_history": list(group.refine_history) + [history_entry],
            }
            revised = parsed.get("revised_abstraction")
            if revised:
                updates["abstraction_content"] = revised
            # Also clean contradiction_pairs involving removed members
            updates["contradiction_pairs"] = [
                p
                for p in group.contradiction_pairs
                if p[0] not in removed_ids and p[1] not in removed_ids
            ]
            return group.model_copy(update=updates)

        return None

    # ── Full pipeline ──

    async def _process_cluster(
        self,
        cluster: ClusterGroup,
        nodes: dict[str, GlobalCanonicalNode],
        semaphore: asyncio.Semaphore,
    ) -> AbstractionResult:
        """Process a single cluster through the full pipeline."""
        async with semaphore:
            result = AbstractionResult()

            if len(cluster.node_ids) < 2:
                return result

            # Step 1: Abstract
            try:
                groups = await self._abstract_cluster(cluster, nodes)
            except Exception:
                logger.warning(
                    "Abstraction failed for cluster %s",
                    cluster.cluster_id,
                    exc_info=True,
                )
                return result

            for group in groups:
                # Collect contradiction candidates
                for pair in group.contradiction_pairs:
                    if len(pair) == 2:
                        result.contradiction_candidates.append(
                            ConflictCandidate(
                                node_a_id=pair[0],
                                node_b_id=pair[1],
                                signal_type="sensitivity",
                                strength=0.7,
                                detail={"source": "abstraction_agent", "group": group.group_id},
                            )
                        )

                # Step 2: Verify
                try:
                    verification = await self._verify_abstraction(group, nodes)
                except Exception:
                    logger.warning(
                        "Verification failed for group %s", group.group_id, exc_info=True
                    )
                    continue

                current_group = group
                if not verification.passed:
                    # Step 3: Refine
                    for _ in range(self._max_retries):
                        try:
                            refined = await self._refine_abstraction(
                                current_group, verification, nodes
                            )
                        except Exception:
                            logger.warning(
                                "Refine failed for group %s",
                                current_group.group_id,
                                exc_info=True,
                            )
                            refined = None
                            break

                        if refined is None:
                            break
                        current_group = refined

                        # Re-verify after refine
                        try:
                            verification = await self._verify_abstraction(current_group, nodes)
                        except Exception:
                            logger.warning(
                                "Re-verification failed for group %s",
                                current_group.group_id,
                                exc_info=True,
                            )
                            break

                        if verification.passed:
                            break

                if not verification.passed:
                    logger.info(
                        "Abandoning group %s after failed verification", current_group.group_id
                    )
                    continue

                # Create graph objects
                abs_result = create_abstraction(
                    abstraction_content=current_group.abstraction_content,
                    member_ids=current_group.member_node_ids,
                    reason=current_group.reason,
                )
                # Attach refine history to schema node metadata
                if current_group.refine_history:
                    meta = dict(abs_result.schema_node.metadata or {})
                    meta["refine_history"] = current_group.refine_history
                    abs_result.schema_node = abs_result.schema_node.model_copy(
                        update={"metadata": meta}
                    )
                result.new_nodes.append(abs_result.schema_node)
                result.new_factors.extend(abs_result.instantiation_factors)
                result.suggestions.append(
                    CurationSuggestion(
                        operation="create_abstraction",
                        target_ids=current_group.member_node_ids,
                        confidence=current_group.confidence or 0.85,
                        reason=current_group.reason,
                        evidence={
                            "abstraction": current_group.abstraction_content,
                            "group_id": current_group.group_id,
                        },
                    )
                )

            return result

    async def run(
        self,
        clusters: list[ClusterGroup],
        nodes: dict[str, GlobalCanonicalNode],
        max_workers: int = 10,
    ) -> AbstractionResult:
        """Run the full abstraction pipeline on all clusters.

        Args:
            clusters: Clusters of similar nodes to process.
            nodes: Mapping of node_id → GlobalCanonicalNode.
            max_workers: Max concurrent LLM calls.

        Returns:
            AbstractionResult with new nodes, factors, contradictions, and suggestions.
        """
        if not self._model:
            return AbstractionResult()

        semaphore = asyncio.Semaphore(max_workers)
        tasks = [self._process_cluster(c, nodes, semaphore) for c in clusters]

        merged = AbstractionResult()
        for coro in asyncio.as_completed(tasks):
            try:
                partial = await coro
            except Exception:
                logger.warning("Cluster processing failed", exc_info=True)
                continue
            merged.new_nodes.extend(partial.new_nodes)
            merged.new_factors.extend(partial.new_factors)
            merged.contradiction_candidates.extend(partial.contradiction_candidates)
            merged.suggestions.extend(partial.suggestions)

        logger.info(
            "Abstraction pipeline: %d new nodes, %d new factors, %d contradictions",
            len(merged.new_nodes),
            len(merged.new_factors),
            len(merged.contradiction_candidates),
        )
        return merged
