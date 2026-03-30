"""Graph containers — LocalCanonicalGraph and GlobalCanonicalGraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §4 (graphs) and overview.md.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, model_validator

from gaia.gaia_ir.knowledge import Knowledge
from gaia.gaia_ir.operator import Operator
from gaia.gaia_ir.strategy import Strategy


def _json_sort_key(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _canonicalize_knowledge_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["parameters"] = sorted(canonical.get("parameters", []), key=_json_sort_key)
    if canonical.get("provenance") is not None:
        canonical["provenance"] = sorted(canonical["provenance"], key=_json_sort_key)
    if canonical.get("local_members") is not None:
        canonical["local_members"] = sorted(canonical["local_members"], key=_json_sort_key)
    return canonical


def _canonicalize_operator_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    variables = list(canonical.get("variables", []))
    conclusion = canonical.get("conclusion")
    operator = canonical.get("operator")
    if operator in {"equivalence", "contradiction", "complement", "disjunction"}:
        canonical["variables"] = sorted(variables)
    elif operator == "conjunction" and conclusion is not None:
        premises = sorted(v for v in variables if v != conclusion)
        canonical["variables"] = premises + [conclusion]
    return canonical


def _canonicalize_strategy_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["premises"] = sorted(canonical.get("premises", []))
    if canonical.get("background") is not None:
        canonical["background"] = sorted(canonical["background"])
    if canonical.get("sub_strategies") is not None:
        canonical["sub_strategies"] = sorted(
            [_canonicalize_strategy_dump(sub) for sub in canonical["sub_strategies"]],
            key=_json_sort_key,
        )
    if canonical.get("formal_expr") is not None:
        formal_expr = dict(canonical["formal_expr"])
        formal_expr["operators"] = sorted(
            [_canonicalize_operator_dump(op) for op in formal_expr.get("operators", [])],
            key=_json_sort_key,
        )
        canonical["formal_expr"] = formal_expr
    return canonical


def _canonical_json(
    knowledges: list[Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
) -> str:
    """Produce canonical JSON for hashing — independent of insertion order."""
    data = {
        "knowledges": sorted(
            [_canonicalize_knowledge_dump(k.model_dump(mode="json")) for k in knowledges],
            key=_json_sort_key,
        ),
        "operators": sorted(
            [_canonicalize_operator_dump(o.model_dump(mode="json")) for o in operators],
            key=_json_sort_key,
        ),
        "strategies": sorted(
            [_canonicalize_strategy_dump(s.model_dump(mode="json")) for s in strategies],
            key=_json_sort_key,
        ),
    }
    return json.dumps(data, sort_keys=True, ensure_ascii=False)


class LocalCanonicalGraph(BaseModel):
    """Local canonical graph — single package, content-addressed hash.

    Stores complete content + Strategy steps (content repository).
    """

    scope: str = "local"
    ir_hash: str | None = None
    knowledges: list[Knowledge]
    operators: list[Operator] = []
    strategies: list[Strategy] = []

    @model_validator(mode="after")
    def _compute_hash(self) -> LocalCanonicalGraph:
        if self.ir_hash is None:
            canonical = _canonical_json(self.knowledges, self.operators, self.strategies)
            digest = hashlib.sha256(canonical.encode()).hexdigest()
            self.ir_hash = f"sha256:{digest}"
        return self


class GlobalCanonicalGraph(BaseModel):
    """Global canonical graph — cross-package structure index.

    Knowledge content is retrieved via representative_lcn (not stored here).
    Strategies have no steps at global layer.
    Incremental — no overall hash.
    """

    scope: str = "global"
    knowledges: list[Knowledge] = []
    operators: list[Operator] = []
    strategies: list[Strategy] = []
