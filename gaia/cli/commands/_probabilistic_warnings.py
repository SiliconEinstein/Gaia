"""Shared CLI warnings for probabilistic Gaia factors."""

from __future__ import annotations

from typing import Any


def _strategy_type(strategy: Any) -> str:
    if isinstance(strategy, dict):
        return str(strategy.get("type") or "")
    return str(getattr(strategy, "type", "") or "")


def _strategy_id(strategy: Any) -> str:
    if isinstance(strategy, dict):
        return str(strategy.get("strategy_id") or "<unknown>")
    return str(getattr(strategy, "strategy_id", None) or "<unknown>")


def _strategy_metadata(strategy: Any) -> dict[str, Any]:
    metadata = (
        strategy.get("metadata")
        if isinstance(strategy, dict)
        else getattr(strategy, "metadata", None)
    )
    return metadata if isinstance(metadata, dict) else {}


def _strategy_premises(strategy: Any) -> list[Any]:
    premises = (
        strategy.get("premises")
        if isinstance(strategy, dict)
        else getattr(strategy, "premises", None)
    )
    return premises if isinstance(premises, list) else []


def _knowledge_prior(node: dict[str, Any] | None) -> Any:
    metadata = (node or {}).get("metadata") or {}
    return metadata.get("prior") if isinstance(metadata, dict) else None


def _iter_strategies(graph_or_ir: Any) -> list[Any]:
    if isinstance(graph_or_ir, dict):
        strategies = graph_or_ir.get("strategies") or []
    else:
        strategies = getattr(graph_or_ir, "strategies", []) or []
    return strategies if isinstance(strategies, list) else []


def associate_local_maxent_warnings(ir: dict[str, Any]) -> list[str]:
    """Return warnings for associate factors closed by local MaxEnt."""
    claims: dict[str, dict[str, Any]] = {}
    for node in ir.get("knowledges", []):
        if not isinstance(node, dict):
            continue
        node_id = node.get("id")
        if isinstance(node_id, str):
            claims[node_id] = node

    warnings: list[str] = []
    for strategy in _iter_strategies(ir):
        if _strategy_type(strategy) != "associate":
            continue
        premises = _strategy_premises(strategy)
        if len(premises) != 2:
            continue
        a, b = premises
        if not isinstance(a, str) or not isinstance(b, str):
            continue
        if (
            _knowledge_prior(claims.get(a)) is not None
            or _knowledge_prior(claims.get(b)) is not None
        ):
            continue
        strategy_id = _strategy_id(strategy)
        warnings.append(
            f"associate strategy {strategy_id}: no declared marginal prior for "
            f"{a!r} or {b!r}; BP lowering will use local Jaynes MaxEnt closure. "
            "Prefer register_prior(...) on at least one endpoint for an explicit marginal."
        )
    return warnings


def infer_default_likelihood_warnings(graph_or_ir: Any) -> list[str]:
    """Return warnings for infer factors using the neutral background default."""
    warnings: list[str] = []
    for strategy in _iter_strategies(graph_or_ir):
        if _strategy_type(strategy) != "infer":
            continue
        metadata = _strategy_metadata(strategy)
        if not metadata.get("p_e_given_not_h_defaulted"):
            continue
        strategy_id = _strategy_id(strategy)
        warnings.append(
            f"infer strategy {strategy_id}: p_e_given_not_h was omitted; using "
            "neutral 0.5 background likelihood. Prefer an explicit "
            "p_e_given_not_h when the false-positive/background rate is known."
        )
    return warnings
