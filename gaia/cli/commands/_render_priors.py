"""Helpers for rendering prior metadata in legacy parameterization-shaped outputs."""

from __future__ import annotations

from typing import Any

# Beliefs and priors smaller than this threshold get scientific notation
# in user-visible Markdown / docs surfaces. Two-decimal rendering rounds
# anything below 0.005 to "0.00", which silently hides the most
# important number in some analyses (e.g. posteriors of ~4e-5).
_SMALL_BELIEF_THRESHOLD = 0.005


def format_belief(value: float) -> str:
    """Format a belief / prior probability for human-readable Markdown.

    Uses ``{value:.2f}`` for "normal" values (|value| >= 0.005). For
    smaller magnitudes — where the two-decimal form would round to
    ``0.00`` and hide the result — switches to ``{value:.1e}`` (e.g.
    ``4.0e-05``). Negative values are passed through unchanged through
    the same branches; in practice probabilities are non-negative.

    Machine-readable surfaces (``.gaia/beliefs.json``, graph.json)
    use raw floats and are not affected by this formatting.
    """
    if abs(value) >= _SMALL_BELIEF_THRESHOLD or value == 0.0:
        return f"{value:.2f}"
    return f"{value:.1e}"


def param_data_from_ir_metadata(ir: dict[str, Any]) -> dict[str, Any] | None:
    """Return parameterization-shaped prior data extracted from Knowledge metadata."""
    priors: list[dict[str, Any]] = []
    for knowledge in ir.get("knowledges", []):
        metadata = knowledge.get("metadata") or {}
        if "prior" not in metadata:
            continue
        record = {
            "knowledge_id": knowledge["id"],
            "value": float(metadata["prior"]),
        }
        justification = metadata.get("prior_justification")
        if isinstance(justification, str) and justification:
            record["justification"] = justification
        priors.append(record)
    if not priors:
        return None
    return {"priors": priors}
