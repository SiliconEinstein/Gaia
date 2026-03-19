"""Curation reviewer — LLM-based with rule-based fallback.

Reviews suggestions in the 0.7-0.95 confidence tier. Uses an LLM to judge
whether a proposed merge/equivalence/contradiction is semantically correct,
given the full content of the two nodes involved.

Falls back to rule-based heuristics if no LLM is available.

Spec §6: separate from package review agent — different judgment criteria.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Literal

from libs.global_graph.models import GlobalCanonicalNode

from .models import CurationSuggestion

logger = logging.getLogger(__name__)

Decision = Literal["approve", "reject", "modify"]

_PROMPT_PATH = Path(__file__).parent / "prompts" / "curation_reviewer.md"
_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)


class CurationReviewer:
    """LLM-based curation reviewer with rule-based fallback.

    Args:
        model: litellm model name (e.g. "gpt-5-mini"). If None, uses rules only.
        nodes: Mapping of global_canonical_id → GlobalCanonicalNode for content lookup.
    """

    def __init__(
        self,
        model: str | None = "gpt-5-mini",
        nodes: dict[str, GlobalCanonicalNode] | None = None,
    ) -> None:
        self._model = model
        self._nodes = nodes or {}
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        if _PROMPT_PATH.exists():
            return _PROMPT_PATH.read_text()
        return ""

    # ── Public API ──

    def review(self, suggestion: CurationSuggestion) -> Decision:
        """Synchronous review — rule-based only."""
        return self._review_rules(suggestion)

    async def areview(self, suggestion: CurationSuggestion) -> Decision:
        """Async review — tries LLM first, falls back to rules."""
        if self._model and self._nodes:
            try:
                return await self._review_llm(suggestion)
            except Exception:
                logger.warning(
                    "LLM review failed for %s, falling back to rules",
                    suggestion.suggestion_id,
                    exc_info=True,
                )
        return self._review_rules(suggestion)

    # ── LLM path ──

    async def _review_llm(self, suggestion: CurationSuggestion) -> Decision:
        """Call LLM to review a suggestion."""
        import litellm

        user_msg = self._build_user_message(suggestion)
        if user_msg is None:
            return self._review_rules(suggestion)

        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": user_msg},
            ],
        )
        raw_output = response.choices[0].message.content
        self._last_llm_input = user_msg
        self._last_llm_output = raw_output
        return self._parse_llm_response(raw_output, suggestion)

    def _build_user_message(self, suggestion: CurationSuggestion) -> str | None:
        """Build the user message with node contents and evidence."""
        if not suggestion.target_ids:
            return None

        evidence_lines = []
        for k, v in suggestion.evidence.items():
            evidence_lines.append(f"  {k}: {v}")
        evidence_block = "\n".join(evidence_lines) if evidence_lines else "  (none)"

        if len(suggestion.target_ids) == 1:
            # Single-node operations (archive_orphan, etc.)
            node = self._nodes.get(suggestion.target_ids[0])
            if not node:
                return None
            return (
                f"## Proposed Operation: {suggestion.operation}\n\n"
                f"### Node: {suggestion.target_ids[0]}\n"
                f"Type: {node.knowledge_type}\n"
                f"Content: {node.representative_content}\n\n"
                f"### Evidence\n{evidence_block}\n\n"
                f"Confidence: {suggestion.confidence:.3f}\n"
                f"Reason: {suggestion.reason}\n"
            )

        if len(suggestion.target_ids) == 2:
            node_a = self._nodes.get(suggestion.target_ids[0])
            node_b = self._nodes.get(suggestion.target_ids[1])
            if not node_a or not node_b:
                return None
            return (
                f"## Proposed Operation: {suggestion.operation}\n\n"
                f"### Node A: {suggestion.target_ids[0]}\n"
                f"Type: {node_a.knowledge_type}\n"
                f"Content: {node_a.representative_content}\n\n"
                f"### Node B: {suggestion.target_ids[1]}\n"
                f"Type: {node_b.knowledge_type}\n"
                f"Content: {node_b.representative_content}\n\n"
                f"### Evidence\n{evidence_block}\n\n"
                f"Confidence: {suggestion.confidence:.3f}\n"
                f"Reason: {suggestion.reason}\n"
            )

        # Multi-node operations (create_abstraction)
        if len(suggestion.target_ids) >= 2:
            member_lines = []
            for tid in suggestion.target_ids:
                node = self._nodes.get(tid)
                if node:
                    member_lines.append(
                        f"### Member: {tid}\n"
                        f"Type: {node.knowledge_type}\n"
                        f"Content: {node.representative_content}\n"
                    )
            if not member_lines:
                return None
            return (
                f"## Proposed Operation: {suggestion.operation}\n\n"
                + "\n".join(member_lines)
                + f"\n### Evidence\n{evidence_block}\n\n"
                f"Confidence: {suggestion.confidence:.3f}\n"
                f"Reason: {suggestion.reason}\n"
            )

        return None

    def _parse_llm_response(self, response: str, suggestion: CurationSuggestion) -> Decision:
        """Parse LLM JSON response into a Decision."""
        text = response.strip()
        match = _JSON_RE.search(text)
        if not match:
            logger.warning("Could not parse LLM response, falling back to rules")
            return self._review_rules(suggestion)

        try:
            parsed = json.loads(match.group(0))
            decision = parsed.get("decision", "reject")
            reason = parsed.get("reason", "")

            if decision == "modify":
                modified_op = parsed.get("modified_operation")
                logger.info(
                    "LLM suggests modify %s → %s: %s",
                    suggestion.operation,
                    modified_op,
                    reason,
                )
                # For now, treat modify as approve (the caller can check the log)
                return "approve"

            if decision in ("approve", "reject"):
                logger.info("LLM %s %s: %s", decision, suggestion.suggestion_id, reason)
                return decision

        except (json.JSONDecodeError, KeyError):
            logger.warning("JSON parse error in LLM response, falling back to rules")

        return self._review_rules(suggestion)

    # ── Rule-based fallback ──

    def _review_rules(self, suggestion: CurationSuggestion) -> Decision:
        """Rule-based review heuristics."""
        op = suggestion.operation
        evidence = suggestion.evidence

        if op == "merge":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= 0.90:
                return "approve"
            return "reject"

        if op == "create_equivalence":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= 0.85:
                return "approve"
            return "reject"

        if op == "create_contradiction":
            drop = evidence.get("belief_drop", 0.0)
            if drop >= 0.15 or suggestion.confidence >= 0.80:
                return "approve"
            return "reject"

        if op in ("archive_orphan", "fix_dangling_factor"):
            return "approve"

        if op == "create_abstraction":
            if suggestion.confidence >= 0.80:
                return "approve"
            return "reject"

        logger.warning("Unknown operation for review: %s", op)
        return "reject"
