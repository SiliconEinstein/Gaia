"""Graph containers — LocalCanonicalGraph and GlobalCanonicalGraph.

Implements docs/foundations/gaia-ir/gaia-ir.md §4 (graphs) and overview.md.
"""

from __future__ import annotations

import hashlib
import json

from pydantic import BaseModel, model_validator

from gaia.gaia_ir.knowledge import Knowledge
from gaia.gaia_ir.operator import Operator
from gaia.gaia_ir.strategy import Strategy


def _canonical_json(
    knowledges: list[Knowledge],
    operators: list[Operator],
    strategies: list[Strategy],
) -> str:
    """Produce canonical JSON for hashing."""
    data = {
        "knowledges": [k.model_dump(mode="json") for k in knowledges],
        "operators": [o.model_dump(mode="json") for o in operators],
        "strategies": [s.model_dump(mode="json") for s in strategies],
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
