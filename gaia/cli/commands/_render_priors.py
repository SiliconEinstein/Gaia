"""Helpers for rendering prior metadata in legacy parameterization-shaped outputs."""

from __future__ import annotations


def param_data_from_ir_metadata(ir: dict) -> dict | None:
    """Return parameterization-shaped prior data extracted from Knowledge metadata."""
    priors: list[dict] = []
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
    return {"priors": priors, "strategy_params": []}
