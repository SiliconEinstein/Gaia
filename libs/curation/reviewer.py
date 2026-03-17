"""Simplified curation reviewer — rule-based heuristics for V1.

Reviews suggestions in the 0.7-0.95 confidence tier that are not
auto-approved. Spec §6: separate from package review agent.

Decision criteria:
- merge: only approve if cosine > 0.90 (just below auto-threshold)
- create_equivalence: approve if cosine > 0.85
- create_contradiction: approve if belief_drop > 0.15 or confidence > 0.80
- archive_orphan: always approve (low risk)
- fix_dangling_factor: always approve (structural fix)
"""

from __future__ import annotations

import logging
from typing import Literal

from .models import CurationSuggestion

logger = logging.getLogger(__name__)

Decision = Literal["approve", "reject"]


class CurationReviewer:
    """Rule-based reviewer for medium-confidence curation suggestions."""

    def __init__(
        self,
        merge_cosine_threshold: float = 0.90,
        equiv_cosine_threshold: float = 0.85,
        contradiction_confidence_threshold: float = 0.80,
        contradiction_drop_threshold: float = 0.15,
    ) -> None:
        self._merge_cosine = merge_cosine_threshold
        self._equiv_cosine = equiv_cosine_threshold
        self._contradiction_conf = contradiction_confidence_threshold
        self._contradiction_drop = contradiction_drop_threshold

    def review(self, suggestion: CurationSuggestion) -> Decision:
        """Review a suggestion and return approve or reject."""
        op = suggestion.operation
        evidence = suggestion.evidence

        if op == "merge":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= self._merge_cosine:
                return "approve"
            return "reject"

        if op == "create_equivalence":
            cosine = evidence.get("cosine", 0.0)
            if cosine >= self._equiv_cosine:
                return "approve"
            return "reject"

        if op == "create_contradiction":
            drop = evidence.get("belief_drop", 0.0)
            if (
                drop >= self._contradiction_drop
                or suggestion.confidence >= self._contradiction_conf
            ):
                return "approve"
            return "reject"

        if op in ("archive_orphan", "fix_dangling_factor"):
            return "approve"

        logger.warning("Unknown operation for review: %s", op)
        return "reject"
