# Gaia IR Code Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update `gaia/gaia_ir/` code to match the restructured design docs (`docs/foundations/gaia-ir/01-08`).

**Architecture:** The gaia-ir design docs underwent a significant restructure. The code models (Operator, Strategy, parameterization, validator) need to be updated to match the new contract. All changes are in the data model layer (`gaia/gaia_ir/`) and its test suite (`tests/gaia_ir/`).

**Tech Stack:** Python 3.12, Pydantic v2, pytest

---

## Delta Summary

| Area | Old (code) | New (spec) |
|------|-----------|------------|
| **Operator.variables** | Includes conclusion for directed ops | Inputs only; conclusion is separate |
| **Operator.conclusion** | None for relation ops | ALL ops have conclusion (helper claim for relation) |
| **Implication arity** | 2 variables (A + B in variables) | 1 variable (A), conclusion=B separate |
| **Conjunction arity** | N+1 variables (premises + M) | N variables (premises), conclusion=M separate |
| **Strategy type→form mapping** | abduction/induction/analogy/extrapolation → CompositeStrategy | → FormalStrategy |
| **CompositeStrategy type restriction** | Only abduction/induction/analogy/extrapolation | Any type (generic container) |
| **CompositeStrategy.sub_strategies** | `list[Strategy]` (embedded objects) | `list[str]` (strategy_id references) |
| **Strategy ID computation** | `SHA-256(scope+type+sorted(premises)+conclusion)` | adds `+structure_hash` |
| **StrategyParamRecord coverage** | All strategies need params | Only `infer`/`noisy_and`; FormalStrategy types derive behavior from FormalExpr |
| **Validator: FormalExpr** | Only validates operator refs | Also validates private node isolation + reference closure |

---

## Chunk 1: Operator Model

### Task 1: Update Operator model — conclusion separation

**Files:**
- Modify: `gaia/gaia_ir/operator.py`
- Test: `tests/gaia_ir/test_operator.py`

- [ ] **Step 1: Update test expectations for new Operator contract**

Rewrite `tests/gaia_ir/test_operator.py` to match the new design:

```python
"""Tests for Operator data model."""

import pytest
from gaia.gaia_ir import Operator, OperatorType


class TestOperatorType:
    def test_six_types(self):
        assert set(OperatorType) == {
            "implication",
            "equivalence",
            "contradiction",
            "complement",
            "disjunction",
            "conjunction",
        }


class TestOperatorCreation:
    def test_equivalence(self):
        op = Operator(
            operator="equivalence",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_eq",
        )
        assert op.conclusion == "gcn_eq"

    def test_contradiction(self):
        op = Operator(
            operator="contradiction",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_contra",
        )
        assert op.conclusion == "gcn_contra"

    def test_complement(self):
        op = Operator(
            operator="complement",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_comp",
        )
        assert op.conclusion == "gcn_comp"

    def test_implication(self):
        """Implication: variables=[A], conclusion=B (separate)."""
        op = Operator(
            operator="implication",
            variables=["gcn_a"],
            conclusion="gcn_b",
        )
        assert op.conclusion == "gcn_b"
        assert len(op.variables) == 1

    def test_conjunction(self):
        """Conjunction: variables=[A₁,...,Aₖ] (inputs only), conclusion=M (separate)."""
        op = Operator(
            operator="conjunction",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_m",
        )
        assert op.conclusion == "gcn_m"
        assert "gcn_m" not in op.variables

    def test_disjunction(self):
        op = Operator(
            operator="disjunction",
            variables=["gcn_a", "gcn_b", "gcn_c"],
            conclusion="gcn_disj",
        )
        assert op.conclusion == "gcn_disj"


class TestOperatorValidation:
    def test_all_operators_require_conclusion(self):
        """Every operator type must have a conclusion."""
        for op_type in OperatorType:
            with pytest.raises(ValueError, match="requires conclusion"):
                Operator(operator=op_type, variables=["a", "b"])

    def test_conclusion_must_not_be_in_variables(self):
        """conclusion is separate from variables — never overlaps."""
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(
                operator="conjunction",
                variables=["a", "b", "m"],
                conclusion="m",
            )

    def test_implication_conclusion_in_variables_rejected(self):
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(operator="implication", variables=["a", "b"], conclusion="b")

    def test_equivalence_requires_two_variables(self):
        with pytest.raises(ValueError, match="exactly 2"):
            Operator(
                operator="equivalence", variables=["a"], conclusion="eq"
            )

    def test_complement_requires_two_variables(self):
        with pytest.raises(ValueError, match="exactly 2"):
            Operator(
                operator="complement", variables=["a", "b", "c"], conclusion="comp"
            )

    def test_contradiction_requires_two_variables(self):
        with pytest.raises(ValueError, match="exactly 2"):
            Operator(
                operator="contradiction", variables=["a"], conclusion="contra"
            )

    def test_implication_requires_one_variable(self):
        """Implication: variables=[A] only (1 input)."""
        with pytest.raises(ValueError, match="exactly 1"):
            Operator(
                operator="implication", variables=["a", "b"], conclusion="c"
            )

    def test_conjunction_requires_at_least_two_variables(self):
        with pytest.raises(ValueError, match="at least 2"):
            Operator(
                operator="conjunction", variables=["a"], conclusion="m"
            )

    def test_disjunction_requires_at_least_two_variables(self):
        with pytest.raises(ValueError, match="at least 2"):
            Operator(
                operator="disjunction", variables=["a"], conclusion="d"
            )


class TestOperatorScope:
    def test_standalone_with_id(self):
        op = Operator(
            operator_id="gco_abc",
            scope="global",
            operator="equivalence",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_eq",
        )
        assert op.operator_id == "gco_abc"
        assert op.scope == "global"

    def test_embedded_no_scope(self):
        """Operators inside FormalExpr don't need scope or id."""
        op = Operator(operator="implication", variables=["a"], conclusion="b")
        assert op.scope is None
        assert op.operator_id is None

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be one of"):
            Operator(
                scope="detached",
                operator="equivalence",
                variables=["a", "b"],
                conclusion="eq",
            )

    def test_local_scope_requires_lco_prefix(self):
        with pytest.raises(ValueError, match="lco_ prefix"):
            Operator(
                operator_id="gco_wrong",
                scope="local",
                operator="equivalence",
                variables=["a", "b"],
                conclusion="eq",
            )

    def test_global_scope_requires_gco_prefix(self):
        with pytest.raises(ValueError, match="gco_ prefix"):
            Operator(
                operator_id="lco_wrong",
                scope="global",
                operator="equivalence",
                variables=["a", "b"],
                conclusion="eq",
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_operator.py -v`
Expected: Multiple failures (old model has opposite conclusion-in-variables semantics)

- [ ] **Step 3: Update Operator model implementation**

Replace the validation logic in `gaia/gaia_ir/operator.py`:

```python
"""Operator — deterministic logical constraints between Knowledge.

Implements docs/foundations/gaia-ir/02-gaia-ir.md §2.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator


class OperatorType(StrEnum):
    """Operator types (§2.2). All are deterministic (ψ ∈ {0,1}, no free parameters)."""

    IMPLICATION = "implication"  # A=1 → B must =1
    EQUIVALENCE = "equivalence"  # A=B
    CONTRADICTION = "contradiction"  # ¬(A=1 ∧ B=1)
    COMPLEMENT = "complement"  # A≠B (XOR)
    DISJUNCTION = "disjunction"  # ¬(all Aᵢ=0)
    CONJUNCTION = "conjunction"  # M = A₁ ∧ ... ∧ Aₖ


class Operator(BaseModel):
    """Deterministic logical constraint between Knowledge nodes.

    Operators have no probability parameters — they encode logical structure.
    They can appear standalone (top-level operators array) or embedded in FormalExpr.

    §2.4: variables contains inputs only; conclusion is a separate output.
    All operator types require a conclusion.
    """

    operator_id: str | None = None  # lco_ or gco_ prefix
    scope: str | None = None  # "local" | "global" (None when embedded in FormalExpr)

    operator: OperatorType
    variables: list[str]  # input Knowledge IDs only
    conclusion: str  # separate output claim (required for all types)

    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _validate_invariants(self) -> Operator:
        if self.scope not in (None, "local", "global"):
            raise ValueError("scope must be one of: None, 'local', 'global'")

        if (
            self.scope == "local"
            and self.operator_id is not None
            and not self.operator_id.startswith("lco_")
        ):
            raise ValueError("local operators must use an operator_id with lco_ prefix")

        if (
            self.scope == "global"
            and self.operator_id is not None
            and not self.operator_id.startswith("gco_")
        ):
            raise ValueError("global operators must use an operator_id with gco_ prefix")

        # §2.4: conclusion must NOT appear in variables
        if self.conclusion in self.variables:
            raise ValueError(
                f"conclusion '{self.conclusion}' must not appear in variables — "
                f"variables holds inputs only, conclusion is separate"
            )

        # Arity rules by operator type
        if self.operator == OperatorType.IMPLICATION:
            if len(self.variables) != 1:
                raise ValueError("operator=implication requires exactly 1 variable")

        if self.operator == OperatorType.CONJUNCTION:
            if len(self.variables) < 2:
                raise ValueError("operator=conjunction requires at least 2 variables")

        if self.operator in (
            OperatorType.EQUIVALENCE,
            OperatorType.COMPLEMENT,
            OperatorType.CONTRADICTION,
        ):
            if len(self.variables) != 2:
                raise ValueError(f"operator={self.operator} requires exactly 2 variables")

        if self.operator == OperatorType.DISJUNCTION:
            if len(self.variables) < 2:
                raise ValueError("operator=disjunction requires at least 2 variables")

        return self
```

Note: `conclusion` is now `str` (required), not `str | None`.

- [ ] **Step 4: Run operator tests to verify they pass**

Run: `pytest tests/gaia_ir/test_operator.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/operator.py tests/gaia_ir/test_operator.py
git commit -m "refactor(gaia-ir): operator conclusion separation per §2.4"
```

---

## Chunk 2: Strategy Model

### Task 2: Update Strategy type→form mapping and CompositeStrategy

**Files:**
- Modify: `gaia/gaia_ir/strategy.py`
- Test: `tests/gaia_ir/test_strategy.py`

- [ ] **Step 1: Update test expectations for new Strategy contract**

Key test changes:
1. abduction/induction/analogy/extrapolation are now FormalStrategy types
2. CompositeStrategy accepts any type and has `sub_strategies: list[str]`
3. Strategy ID includes `structure_hash`
4. toolcall/proof removed from StrategyType (deferred per spec)

Rewrite `tests/gaia_ir/test_strategy.py`:

```python
"""Tests for Strategy data model (Strategy, CompositeStrategy, FormalStrategy)."""

import pytest
from gaia.gaia_ir import (
    Strategy,
    CompositeStrategy,
    FormalStrategy,
    FormalExpr,
    StrategyType,
    Step,
    Operator,
)


class TestStrategyType:
    def test_eleven_types(self):
        """toolcall and proof are deferred per spec §3.3."""
        assert len(StrategyType) == 11
        assert "infer" in set(StrategyType)
        assert "noisy_and" in set(StrategyType)
        assert "deduction" in set(StrategyType)
        assert "abduction" in set(StrategyType)
        assert "induction" in set(StrategyType)
        assert "analogy" in set(StrategyType)
        assert "extrapolation" in set(StrategyType)

    def test_no_toolcall(self):
        """toolcall is deferred per spec."""
        with pytest.raises(ValueError):
            StrategyType("toolcall")

    def test_no_proof(self):
        """proof is deferred per spec."""
        with pytest.raises(ValueError):
            StrategyType("proof")


class TestStrategyCreation:
    def test_basic_strategy(self):
        s = Strategy(scope="local", type="noisy_and", premises=["lcn_a"], conclusion="lcn_b")
        assert s.strategy_id.startswith("lcs_")
        assert s.type == StrategyType.NOISY_AND

    def test_global_strategy(self):
        s = Strategy(scope="global", type="infer", premises=["gcn_a"], conclusion="gcn_b")
        assert s.strategy_id.startswith("gcs_")

    def test_auto_id_deterministic(self):
        s1 = Strategy(scope="local", type="infer", premises=["a", "b"], conclusion="c")
        s2 = Strategy(scope="local", type="infer", premises=["b", "a"], conclusion="c")
        assert s1.strategy_id == s2.strategy_id  # sorted premises

    def test_different_type_different_id(self):
        s1 = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        s2 = Strategy(scope="local", type="noisy_and", premises=["a"], conclusion="b")
        assert s1.strategy_id != s2.strategy_id

    def test_with_background(self):
        s = Strategy(
            scope="local",
            type="noisy_and",
            premises=["lcn_a"],
            conclusion="lcn_b",
            background=["lcn_setting"],
        )
        assert s.background == ["lcn_setting"]

    def test_with_steps(self):
        s = Strategy(
            scope="local",
            type="infer",
            premises=["lcn_a"],
            conclusion="lcn_b",
            steps=[Step(reasoning="observed correlation")],
        )
        assert len(s.steps) == 1

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be one of"):
            Strategy(scope="detached", type="infer", premises=["a"], conclusion="b")

    def test_global_steps_rejected(self):
        with pytest.raises(ValueError, match="must not carry steps"):
            Strategy(
                scope="global",
                type="infer",
                premises=["gcn_a"],
                conclusion="gcn_b",
                steps=[Step(reasoning="should stay local")],
            )

    def test_leaf_rejects_named_strategy_type(self):
        with pytest.raises(ValueError, match="Strategy form only allows types"):
            Strategy(scope="global", type="deduction", premises=["gcn_a"], conclusion="gcn_b")


class TestCompositeStrategy:
    def test_creation_with_string_refs(self):
        """sub_strategies is list[str] — strategy_id references."""
        cs = CompositeStrategy(
            scope="global",
            type="abduction",
            premises=["gcn_obs"],
            conclusion="gcn_h",
            sub_strategies=["gcs_sub1", "gcs_sub2"],
        )
        assert len(cs.sub_strategies) == 2
        assert isinstance(cs.sub_strategies[0], str)

    def test_empty_sub_strategies_rejected(self):
        with pytest.raises(ValueError, match="at least one"):
            CompositeStrategy(
                scope="global",
                type="induction",
                premises=["gcn_a"],
                conclusion="gcn_b",
                sub_strategies=[],
            )

    def test_any_type_allowed(self):
        """CompositeStrategy is a generic container — any type allowed."""
        for type_ in ["infer", "noisy_and", "deduction", "abduction", "induction"]:
            cs = CompositeStrategy(
                scope="global",
                type=type_,
                premises=["gcn_a"],
                conclusion="gcn_b",
                sub_strategies=["gcs_child"],
            )
            assert cs.type == type_

    def test_structure_hash_affects_id(self):
        """Different sub_strategies produce different strategy IDs."""
        cs1 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["gcn_a"],
            conclusion="gcn_b",
            sub_strategies=["gcs_x"],
        )
        cs2 = CompositeStrategy(
            scope="global",
            type="infer",
            premises=["gcn_a"],
            conclusion="gcn_b",
            sub_strategies=["gcs_y"],
        )
        assert cs1.strategy_id != cs2.strategy_id


class TestFormalStrategy:
    def test_deduction(self):
        """Deduction: conjunction + implication."""
        fs = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["lcn_a", "lcn_b"],
            conclusion="lcn_c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="conjunction",
                        variables=["lcn_a", "lcn_b"],
                        conclusion="lcn_m",
                    ),
                    Operator(
                        operator="implication",
                        variables=["lcn_m"],
                        conclusion="lcn_c",
                    ),
                ]
            ),
        )
        assert fs.type == StrategyType.DEDUCTION
        assert len(fs.formal_expr.operators) == 2

    def test_abduction(self):
        """Abduction is now FormalStrategy per spec §3.6."""
        fs = FormalStrategy(
            scope="local",
            type="abduction",
            premises=["lcn_obs"],
            conclusion="lcn_h",
            formal_expr=FormalExpr(
                operators=[
                    Operator(
                        operator="implication",
                        variables=["lcn_h"],
                        conclusion="lcn_o",
                    ),
                    Operator(
                        operator="equivalence",
                        variables=["lcn_o", "lcn_obs"],
                        conclusion="lcn_eq",
                    ),
                ]
            ),
        )
        assert fs.type == StrategyType.ABDUCTION

    def test_induction(self):
        """Induction is now FormalStrategy per spec §3.6."""
        fs = FormalStrategy(
            scope="local",
            type="induction",
            premises=["lcn_obs1", "lcn_obs2"],
            conclusion="lcn_law",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["lcn_law"], conclusion="lcn_i1"),
                    Operator(operator="equivalence", variables=["lcn_i1", "lcn_obs1"], conclusion="lcn_eq1"),
                    Operator(operator="implication", variables=["lcn_law"], conclusion="lcn_i2"),
                    Operator(operator="equivalence", variables=["lcn_i2", "lcn_obs2"], conclusion="lcn_eq2"),
                ]
            ),
        )
        assert fs.type == StrategyType.INDUCTION

    def test_analogy(self):
        """Analogy is now FormalStrategy per spec §3.6."""
        fs = FormalStrategy(
            scope="local",
            type="analogy",
            premises=["lcn_src", "lcn_bridge"],
            conclusion="lcn_target",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="conjunction", variables=["lcn_src", "lcn_bridge"], conclusion="lcn_m"),
                    Operator(operator="implication", variables=["lcn_m"], conclusion="lcn_target"),
                ]
            ),
        )
        assert fs.type == StrategyType.ANALOGY

    def test_extrapolation(self):
        """Extrapolation is now FormalStrategy per spec §3.6."""
        fs = FormalStrategy(
            scope="local",
            type="extrapolation",
            premises=["lcn_law", "lcn_cont"],
            conclusion="lcn_ext",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="conjunction", variables=["lcn_law", "lcn_cont"], conclusion="lcn_m"),
                    Operator(operator="implication", variables=["lcn_m"], conclusion="lcn_ext"),
                ]
            ),
        )
        assert fs.type == StrategyType.EXTRAPOLATION

    def test_reductio(self):
        """Reductio: implication + contradiction + complement."""
        fs = FormalStrategy(
            scope="local",
            type="reductio",
            premises=["lcn_r"],
            conclusion="lcn_not_p",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["lcn_p"], conclusion="lcn_q"),
                    Operator(operator="contradiction", variables=["lcn_q", "lcn_r"], conclusion="lcn_contra"),
                    Operator(operator="complement", variables=["lcn_p", "lcn_not_p"], conclusion="lcn_comp"),
                ]
            ),
        )
        assert fs.type == StrategyType.REDUCTIO
        assert len(fs.formal_expr.operators) == 3

    def test_empty_formal_expr_rejected(self):
        with pytest.raises(ValueError, match="at least one operator"):
            FormalStrategy(
                scope="local",
                type="deduction",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(operators=[]),
            )

    def test_formal_rejects_leaf_type(self):
        with pytest.raises(ValueError, match="FormalStrategy form only allows types"):
            FormalStrategy(
                scope="local",
                type="infer",
                premises=["a"],
                conclusion="b",
                formal_expr=FormalExpr(
                    operators=[
                        Operator(operator="implication", variables=["a"], conclusion="b"),
                    ]
                ),
            )

    def test_structure_hash_affects_id(self):
        """Different formal_expr produces different strategy IDs."""
        fs1 = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a", "b"],
            conclusion="c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="conjunction", variables=["a", "b"], conclusion="m"),
                    Operator(operator="implication", variables=["m"], conclusion="c"),
                ]
            ),
        )
        # Same premises/conclusion but different internal structure
        fs2 = FormalStrategy(
            scope="local",
            type="deduction",
            premises=["a", "b"],
            conclusion="c",
            formal_expr=FormalExpr(
                operators=[
                    Operator(operator="implication", variables=["a"], conclusion="c"),
                ]
            ),
        )
        assert fs1.strategy_id != fs2.strategy_id


class TestStrategyNoLifecycleStages:
    """Verify no FactorStage concept exists — form is state per §3.8."""

    def test_no_stage_field(self):
        s = Strategy(scope="local", type="infer", premises=["a"], conclusion="b")
        assert not hasattr(s, "stage")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia_ir/test_strategy.py -v`
Expected: Multiple failures

- [ ] **Step 3: Update Strategy model implementation**

Key changes in `gaia/gaia_ir/strategy.py`:
1. Remove `TOOLCALL` and `PROOF` from StrategyType (deferred)
2. Move abduction/induction/analogy/extrapolation to `_FORMAL_STRATEGY_TYPES`
3. Remove `_COMPOSITE_STRATEGY_TYPES` — CompositeStrategy accepts any type
4. Change `CompositeStrategy.sub_strategies` from `list[Strategy]` to `list[str]`
5. Add `structure_hash` to `_compute_strategy_id`

```python
"""Strategy — reasoning declarations in the Gaia reasoning hypergraph.

Implements docs/foundations/gaia-ir/02-gaia-ir.md §3.

Three forms (class hierarchy):
- Strategy: leaf reasoning (single ↝)
- CompositeStrategy: contains sub-strategy references, generic container
- FormalStrategy: contains deterministic Operator expansion (FormalExpr)
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, model_validator

from gaia.gaia_ir.operator import Operator


class StrategyType(StrEnum):
    """Strategy types (§3.3). Orthogonal to form (Strategy/Composite/Formal)."""

    INFER = "infer"  # full CPT: 2^k params
    NOISY_AND = "noisy_and"  # ∧ + single param p

    # Named strategies — all FormalStrategy when fully expanded
    DEDUCTION = "deduction"
    REDUCTIO = "reductio"
    ELIMINATION = "elimination"
    MATHEMATICAL_INDUCTION = "mathematical_induction"
    CASE_ANALYSIS = "case_analysis"
    ABDUCTION = "abduction"
    INDUCTION = "induction"
    ANALOGY = "analogy"
    EXTRAPOLATION = "extrapolation"

    # toolcall and proof are deferred per spec §3.3


class Step(BaseModel):
    """A single reasoning step (local layer only)."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class FormalExpr(BaseModel):
    """Deterministic Operator expansion embedded in FormalStrategy.

    Contains only deterministic Operators — no probability parameters.
    Intermediate Knowledge referenced by operators must exist as independent
    Knowledge nodes in the graph (created by compiler/reviewer/agent).
    """

    operators: list[Operator]


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _canonical_formal_expr(formal_expr: FormalExpr) -> str:
    """Deterministic serialization of FormalExpr for structure_hash."""
    ops = []
    for op in formal_expr.operators:
        ops.append(op.model_dump(mode="json", exclude_none=True))
    ops.sort(key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return json.dumps(ops, sort_keys=True, ensure_ascii=False)


def _compute_strategy_id(
    scope: str,
    type_: str,
    premises: list[str],
    conclusion: str | None,
    structure_hash: str = "",
) -> str:
    """Deterministic strategy ID including structure_hash per §3.2."""
    prefix = "lcs_" if scope == "local" else "gcs_"
    payload = f"{scope}|{type_}|{sorted(premises)}|{conclusion}|{structure_hash}"
    return f"{prefix}{_sha256_hex(payload)}"


_LEAF_STRATEGY_TYPES = frozenset(
    {
        StrategyType.INFER,
        StrategyType.NOISY_AND,
    }
)

_FORMAL_STRATEGY_TYPES = frozenset(
    {
        StrategyType.DEDUCTION,
        StrategyType.REDUCTIO,
        StrategyType.ELIMINATION,
        StrategyType.MATHEMATICAL_INDUCTION,
        StrategyType.CASE_ANALYSIS,
        StrategyType.ABDUCTION,
        StrategyType.INDUCTION,
        StrategyType.ANALOGY,
        StrategyType.EXTRAPOLATION,
    }
)


class Strategy(BaseModel):
    """Base strategy — leaf reasoning (single ↝).

    Can be instantiated directly for basic strategies (infer, noisy_and)
    and for named strategies not yet expanded to FormalStrategy.
    """

    strategy_id: str | None = None
    scope: str  # "local" | "global"
    type: StrategyType

    # connections
    premises: list[str]  # claim Knowledge IDs
    conclusion: str | None = None  # single output Knowledge (must be claim)
    background: list[str] | None = None  # context Knowledge IDs (any type, not in BP)

    # local layer
    steps: list[Step] | None = None  # reasoning process (local only, None at global)

    # traceability
    metadata: dict[str, Any] | None = None

    @model_validator(mode="after")
    def _compute_id_and_validate(self) -> Strategy:
        if self.scope not in {"local", "global"}:
            raise ValueError("scope must be one of: 'local', 'global'")

        if self.scope == "global" and self.steps is not None:
            raise ValueError("global Strategy must not carry steps")

        if self.strategy_id is not None:
            expected_prefix = "lcs_" if self.scope == "local" else "gcs_"
            if not self.strategy_id.startswith(expected_prefix):
                raise ValueError(
                    f"{self.scope} strategies must use a strategy_id with {expected_prefix} prefix"
                )

        if self.strategy_id is None:
            self.strategy_id = _compute_strategy_id(
                self.scope,
                self.type,
                self.premises,
                self.conclusion,
                self._structure_hash(),
            )
        return self

    def _structure_hash(self) -> str:
        """Leaf Strategy has empty structure_hash."""
        return ""

    @model_validator(mode="after")
    def _validate_leaf_form(self) -> Strategy:
        if self.__class__ is Strategy and self.type not in _LEAF_STRATEGY_TYPES:
            allowed = ", ".join(sorted(t.value for t in _LEAF_STRATEGY_TYPES))
            raise ValueError(f"Strategy form only allows types: {allowed}; got {self.type.value}")
        return self


class CompositeStrategy(Strategy):
    """Strategy with sub-strategy references — generic container.

    sub_strategies stores strategy_id strings (not embedded objects).
    Any strategy type is allowed. Used for preserving decomposition boundaries.
    """

    sub_strategies: list[str]

    @model_validator(mode="after")
    def _validate_sub_strategies(self) -> CompositeStrategy:
        if not self.sub_strategies:
            raise ValueError("CompositeStrategy requires at least one sub_strategy")
        return self

    def _structure_hash(self) -> str:
        return _sha256_hex(str(sorted(self.sub_strategies)))


class FormalStrategy(Strategy):
    """Strategy with deterministic Operator expansion.

    Used for all named strategies when fully expanded (deduction, abduction,
    induction, analogy, extrapolation, reductio, elimination, etc.).
    """

    formal_expr: FormalExpr

    @model_validator(mode="after")
    def _validate_formal_expr(self) -> FormalStrategy:
        if not self.formal_expr.operators:
            raise ValueError("FormalStrategy requires at least one operator in formal_expr")
        if self.type not in _FORMAL_STRATEGY_TYPES:
            allowed = ", ".join(sorted(t.value for t in _FORMAL_STRATEGY_TYPES))
            raise ValueError(
                f"FormalStrategy form only allows types: {allowed}; got {self.type.value}"
            )
        return self

    def _structure_hash(self) -> str:
        return _sha256_hex(_canonical_formal_expr(self.formal_expr))
```

- [ ] **Step 4: Run strategy tests to verify they pass**

Run: `pytest tests/gaia_ir/test_strategy.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/strategy.py tests/gaia_ir/test_strategy.py
git commit -m "refactor(gaia-ir): strategy type remap and CompositeStrategy as generic container"
```

---

## Chunk 3: Graphs, Parameterization, Validator

### Task 3: Update graphs.py canonical serialization

**Files:**
- Modify: `gaia/gaia_ir/graphs.py`
- Test: `tests/gaia_ir/test_graphs.py`

- [ ] **Step 1: Update graph test expectations**

Key changes:
- Operator tests: conclusion no longer in variables, all operators have conclusion
- Sub_strategies are now strings not dicts

Update operator canonicalization in tests to use new format:

```python
# In TestLocalCanonicalGraph.test_with_operators — update operator to new format
def test_with_operators(self):
    g = LocalCanonicalGraph(
        knowledges=[
            Knowledge(id="lcn_a", type="claim"),
            Knowledge(id="lcn_b", type="claim"),
            Knowledge(id="lcn_eq", type="claim"),
        ],
        operators=[
            Operator(
                operator="equivalence",
                variables=["lcn_a", "lcn_b"],
                conclusion="lcn_eq",
            ),
        ],
    )
    assert len(g.operators) == 1
```

And update `TestGlobalCanonicalGraph.test_three_entity_types` similarly.

- [ ] **Step 2: Update graphs.py operator canonicalization**

The `_canonicalize_operator_dump` function needs to be updated since `conclusion` is no longer in `variables`:

```python
def _canonicalize_operator_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    variables = list(canonical.get("variables", []))
    operator = canonical.get("operator")
    # For symmetric operators, sort variables for canonical ordering
    if operator in {"equivalence", "contradiction", "complement", "disjunction"}:
        canonical["variables"] = sorted(variables)
    elif operator == "conjunction":
        # Conjunction inputs are order-independent
        canonical["variables"] = sorted(variables)
    # implication: single variable, no sorting needed
    return canonical
```

And `_canonicalize_strategy_dump` for sub_strategies being strings:

```python
def _canonicalize_strategy_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["premises"] = sorted(canonical.get("premises", []))
    if canonical.get("background") is not None:
        canonical["background"] = sorted(canonical["background"])
    if canonical.get("sub_strategies") is not None:
        # sub_strategies are now string IDs, not dicts
        canonical["sub_strategies"] = sorted(canonical["sub_strategies"])
    if canonical.get("formal_expr") is not None:
        formal_expr = dict(canonical["formal_expr"])
        formal_expr["operators"] = sorted(
            [_canonicalize_operator_dump(op) for op in formal_expr.get("operators", [])],
            key=_json_sort_key,
        )
        canonical["formal_expr"] = formal_expr
    return canonical
```

- [ ] **Step 3: Run graph tests**

Run: `pytest tests/gaia_ir/test_graphs.py -v`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add gaia/gaia_ir/graphs.py tests/gaia_ir/test_graphs.py
git commit -m "refactor(gaia-ir): update graph canonicalization for new operator/strategy schema"
```

### Task 4: Update parameterization — only infer/noisy_and need params

**Files:**
- Modify: `gaia/gaia_ir/parameterization.py`
- Modify: `gaia/gaia_ir/validator.py`
- Test: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Update StrategyParamRecord docstring**

In `gaia/gaia_ir/parameterization.py`, update the docstring to reflect only `infer` and `noisy_and`:

```python
class StrategyParamRecord(BaseModel):
    """Conditional probability parameters for a global Strategy.

    Only parameterized strategies need StrategyParamRecord:
    - infer: 2^k values (full CPT, one per premise truth-value combination)
    - noisy_and: 1 value (P(conclusion=true | all premises=true))

    FormalStrategy types (deduction, abduction, etc.) derive behavior from
    FormalExpr + claim priors — no independent StrategyParamRecord.

    All values are Cromwell-clamped.
    """
```

- [ ] **Step 2: Update validator parameterization check**

In `gaia/gaia_ir/validator.py`, the `validate_parameterization` function should only require StrategyParamRecord for `infer` and `noisy_and` strategies:

```python
# In validate_parameterization(), replace the strategy param coverage check:

# Only parameterized strategies need StrategyParamRecord
from gaia.gaia_ir.strategy import _LEAF_STRATEGY_TYPES, StrategyType
parameterized_types = {StrategyType.INFER, StrategyType.NOISY_AND}

param_strategy_ids = {r.strategy_id for r in strategy_params}
for sid in strategy_ids:
    s = strategy_lookup.get(sid)
    if s is not None and s.type in parameterized_types:
        if sid not in param_strategy_ids:
            result.error(f"Strategy '{sid}': missing StrategyParamRecord")

# Also update arity check to only handle infer and noisy_and:
for r in strategy_params:
    s = strategy_lookup.get(r.strategy_id)
    if s is None:
        continue
    actual = len(r.conditional_probabilities)
    if s.type == StrategyType.INFER:
        expected = 2 ** len(s.premises)
        if actual != expected:
            result.error(
                f"StrategyParamRecord '{r.strategy_id}': infer strategy with "
                f"{len(s.premises)} premises requires 2^{len(s.premises)}={expected} "
                f"conditional_probabilities, got {actual}"
            )
    elif s.type == StrategyType.NOISY_AND:
        if actual != 1:
            result.error(
                f"StrategyParamRecord '{r.strategy_id}': noisy_and strategy "
                f"requires 1 conditional_probability, got {actual}"
            )
    # FormalStrategy types don't need StrategyParamRecord — warn if provided
    else:
        result.warn(
            f"StrategyParamRecord '{r.strategy_id}': strategy type '{s.type}' "
            f"does not use external parameters (behavior derived from FormalExpr)"
        )
```

- [ ] **Step 3: Update parameterization tests**

Update `tests/gaia_ir/test_validator.py` `TestParameterizationValidation`:
- FormalStrategy types should NOT require StrategyParamRecord
- Add test for FormalStrategy without params passing validation

- [ ] **Step 4: Run parameterization tests**

Run: `pytest tests/gaia_ir/test_validator.py::TestParameterizationValidation -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/gaia_ir/parameterization.py gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "refactor(gaia-ir): only infer/noisy_and need StrategyParamRecord"
```

### Task 5: Update validator for new Operator/Strategy rules

**Files:**
- Modify: `gaia/gaia_ir/validator.py`
- Test: `tests/gaia_ir/test_validator.py`

- [ ] **Step 1: Update operator validation in validator**

In `_validate_operators`, update to match new contract:
- All operators have conclusion — validate it exists in graph as claim
- conclusion must NOT be in variables

```python
def _validate_operators(
    operators: list[Operator],
    knowledge_lookup: dict[str, Knowledge],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate top-level Operators against the knowledge set."""
    for op in operators:
        if op.scope is not None and op.scope != scope:
            result.error(
                f"Operator '{op.operator_id}': scope '{op.scope}' incompatible with {scope} graph"
            )

        # variable reference completeness
        for var_id in op.variables:
            if var_id not in knowledge_lookup:
                result.error(f"Operator '{op.operator_id}': variable '{var_id}' not found in graph")
            elif knowledge_lookup[var_id].type != KnowledgeType.CLAIM:
                result.error(
                    f"Operator '{op.operator_id}': variable '{var_id}' is "
                    f"'{knowledge_lookup[var_id].type}', must be claim"
                )

        # conclusion reference (required for all operators)
        if op.conclusion not in knowledge_lookup:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' not found in graph"
            )
        elif knowledge_lookup[op.conclusion].type != KnowledgeType.CLAIM:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' is "
                f"'{knowledge_lookup[op.conclusion].type}', must be claim"
            )

        # conclusion must NOT be in variables (belt-and-suspenders)
        if op.conclusion in op.variables:
            result.error(
                f"Operator '{op.operator_id}': conclusion '{op.conclusion}' must not appear in variables"
            )
```

- [ ] **Step 2: Update CompositeStrategy validation**

Since sub_strategies are now string IDs, validation needs to check they exist in the graph:

```python
# In _validate_strategy, update CompositeStrategy handling:
if isinstance(strategy, CompositeStrategy):
    # sub_strategies are strategy_id strings — check they exist in graph
    # (This is graph-level validation; object-level just checks non-empty)
    pass  # Graph-level validation of sub_strategy refs handled separately
```

Add a new function `_validate_sub_strategy_refs` that checks all CompositeStrategy sub_strategies reference existing strategy_ids in the same graph. Call it from `_validate_strategies`.

- [ ] **Step 3: Add FormalExpr private node and reference closure validation**

Add validation per spec §5 (08-validation.md):

```python
def _validate_formal_expr(
    strategy: FormalStrategy,
    knowledge_lookup: dict[str, Knowledge],
    all_strategy_premises: set[str],
    all_strategy_conclusions: set[str],
    scope: str,
    result: ValidationResult,
) -> None:
    """Validate FormalExpr reference closure and private node isolation."""
    sid = strategy.strategy_id or "<no-id>"

    # Collect FormalExpr interface and internal nodes
    interface_inputs = set(strategy.premises)
    interface_output = {strategy.conclusion} if strategy.conclusion else set()
    internal_conclusions = {
        op.conclusion for op in strategy.formal_expr.operators
    }

    # Reference closure: every operator's variables/conclusion must be
    # interface input, interface output, or another operator's conclusion
    allowed_refs = interface_inputs | interface_output | internal_conclusions
    for op in strategy.formal_expr.operators:
        for var_id in op.variables:
            if var_id not in allowed_refs:
                result.error(
                    f"FormalStrategy '{sid}': FormalExpr operator variable "
                    f"'{var_id}' not in interface or internal conclusions"
                )
        if op.conclusion not in allowed_refs:
            result.error(
                f"FormalStrategy '{sid}': FormalExpr operator conclusion "
                f"'{op.conclusion}' not in interface or internal conclusions"
            )

    # Private node isolation: internal nodes not in any Strategy's
    # premises/conclusion are private — must not be referenced externally
    private_nodes = internal_conclusions - interface_inputs - interface_output
    for node_id in private_nodes:
        if node_id in all_strategy_premises or node_id in all_strategy_conclusions:
            result.error(
                f"FormalStrategy '{sid}': private node '{node_id}' is referenced "
                f"by another Strategy (breaks FormalStrategy collapsibility)"
            )
```

- [ ] **Step 4: Update scope consistency for operators**

In `_validate_scope_consistency`, add conclusion prefix checking for operators:

```python
for op in operators:
    for var_id in op.variables:
        if var_id and not var_id.startswith(prefix):
            result.error(...)
    # Also check operator conclusion
    if op.conclusion and not op.conclusion.startswith(prefix):
        result.error(
            f"Operator '{op.operator_id}': conclusion '{op.conclusion}' "
            f"has wrong prefix for {scope} graph"
        )
```

- [ ] **Step 5: Update all validator tests**

Update `tests/gaia_ir/test_validator.py`:
- All Operator tests need new format (conclusion separate from variables)
- CompositeStrategy tests use string sub_strategies
- FormalStrategy tests use new operator format
- Add tests for FormalExpr private node isolation
- Add tests for FormalExpr reference closure

- [ ] **Step 6: Run full validator tests**

Run: `pytest tests/gaia_ir/test_validator.py -v`
Expected: All PASS

- [ ] **Step 7: Commit**

```bash
git add gaia/gaia_ir/validator.py tests/gaia_ir/test_validator.py
git commit -m "refactor(gaia-ir): validator for new operator/strategy contract"
```

### Task 6: Full test suite pass

- [ ] **Step 1: Run the complete test suite**

Run: `pytest tests/gaia_ir/ -v`
Expected: All PASS

- [ ] **Step 2: Run ruff lint and format**

```bash
ruff check gaia/gaia_ir/ tests/gaia_ir/
ruff format --check gaia/gaia_ir/ tests/gaia_ir/
```

- [ ] **Step 3: Fix any remaining issues**

Address any test failures or lint errors.

- [ ] **Step 4: Final commit and PR**

```bash
git add -A
git commit -m "refactor(gaia-ir): align code models with restructured design docs"
```

Create PR to main.
