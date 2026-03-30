"""Graph containers — LocalCanonicalGraph and GlobalCanonicalGraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §4 (graphs) and overview.md.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import BaseModel, model_validator

from gaia.gaia_ir.knowledge import Knowledge, KnowledgeType
from gaia.gaia_ir.operator import Operator
from gaia.gaia_ir.strategy import CompositeStrategy, FormalStrategy, Strategy


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


def _validate_operator_ids(
    operator: Operator,
    knowledge_by_id: dict[str, Knowledge],
) -> None:
    for variable_id in operator.variables:
        knowledge = knowledge_by_id.get(variable_id)
        if knowledge is None:
            raise ValueError(f"Operator references unknown Knowledge id: {variable_id}")
        if knowledge.type != KnowledgeType.CLAIM:
            raise ValueError("Operator variables must all reference claim Knowledge")

    if operator.conclusion is not None and operator.conclusion not in knowledge_by_id:
        raise ValueError(f"Operator conclusion references unknown Knowledge id: {operator.conclusion}")


def _validate_strategy_connections(
    strategy: Strategy,
    knowledge_by_id: dict[str, Knowledge],
) -> None:
    for premise_id in strategy.premises:
        knowledge = knowledge_by_id.get(premise_id)
        if knowledge is None:
            raise ValueError(f"Strategy references unknown premise Knowledge id: {premise_id}")
        if knowledge.type != KnowledgeType.CLAIM:
            raise ValueError("Strategy premises must all reference claim Knowledge")

    if strategy.conclusion is not None:
        knowledge = knowledge_by_id.get(strategy.conclusion)
        if knowledge is None:
            raise ValueError(
                f"Strategy conclusion references unknown Knowledge id: {strategy.conclusion}"
            )
        if knowledge.type != KnowledgeType.CLAIM:
            raise ValueError("Strategy conclusion must reference claim Knowledge")

    if strategy.background is not None:
        for background_id in strategy.background:
            if background_id not in knowledge_by_id:
                raise ValueError(
                    f"Strategy background references unknown Knowledge id: {background_id}"
                )

    if isinstance(strategy, CompositeStrategy):
        for sub_strategy in strategy.sub_strategies:
            _validate_strategy_connections(sub_strategy, knowledge_by_id)

    if isinstance(strategy, FormalStrategy):
        for operator in strategy.formal_expr.operators:
            _validate_operator_ids(operator, knowledge_by_id)


def _validate_local_knowledge(knowledge: Knowledge) -> None:
    if knowledge.id is None or not knowledge.id.startswith("lcn_"):
        raise ValueError("LocalCanonicalGraph requires all Knowledge ids to use lcn_ prefix")
    if knowledge.content is None:
        raise ValueError("LocalCanonicalGraph requires all Knowledge to carry content")
    if knowledge.representative_lcn is not None:
        raise ValueError("LocalCanonicalGraph Knowledge must not set representative_lcn")
    if knowledge.local_members is not None:
        raise ValueError("LocalCanonicalGraph Knowledge must not set local_members")


def _validate_global_knowledge(knowledge: Knowledge) -> None:
    if knowledge.id is None or not knowledge.id.startswith("gcn_"):
        raise ValueError("GlobalCanonicalGraph requires all Knowledge ids to use gcn_ prefix")
    if knowledge.content is None and knowledge.representative_lcn is None:
        raise ValueError(
            "GlobalCanonicalGraph Knowledge must carry content or representative_lcn"
        )


def _canonical_json(
    knowledges: list[Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
) -> str:
    """Produce canonical JSON for hashing."""
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
    def _validate_contract(self) -> LocalCanonicalGraph:
        knowledge_by_id = {knowledge.id: knowledge for knowledge in self.knowledges}

        for knowledge in self.knowledges:
            _validate_local_knowledge(knowledge)

        for operator in self.operators:
            if operator.scope not in (None, "local"):
                raise ValueError("LocalCanonicalGraph operators must have scope=None or scope='local'")
            _validate_operator_ids(operator, knowledge_by_id)

        for strategy in self.strategies:
            if strategy.scope != "local":
                raise ValueError("LocalCanonicalGraph strategies must have scope='local'")
            _validate_strategy_connections(strategy, knowledge_by_id)

        return self

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

    @model_validator(mode="after")
    def _validate_contract(self) -> GlobalCanonicalGraph:
        knowledge_by_id = {knowledge.id: knowledge for knowledge in self.knowledges}

        for knowledge in self.knowledges:
            _validate_global_knowledge(knowledge)

        for operator in self.operators:
            if operator.scope not in (None, "global"):
                raise ValueError(
                    "GlobalCanonicalGraph operators must have scope=None or scope='global'"
                )
            _validate_operator_ids(operator, knowledge_by_id)

        for strategy in self.strategies:
            if strategy.scope != "global":
                raise ValueError("GlobalCanonicalGraph strategies must have scope='global'")
            _validate_strategy_connections(strategy, knowledge_by_id)

        return self
