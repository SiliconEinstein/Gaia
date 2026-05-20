# Joint Query Diagnostic Probability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a joint-distribution query layer and use it to score formula logic diagnostic conditions from PR #648.

**Architecture:** Add `gaia.engine.bp.joint_query` as the BP-facing joint distribution provider, then add `gaia.engine.ir.logic.probability` as the BP-independent event scorer for `DiagnosticCondition`. Exact enumeration, junction tree, mean field, and TRW-BP all expose the same `JointDistribution` contract; unavailable method results are explicit and never replaced by marginal-only estimates.

**Tech Stack:** Python 3.12, Pydantic v2, NumPy, Gaia `FactorGraph`, exact enumeration, Junction Tree, TRW-BP, Mean Field VI, pytest, ruff, mypy.

---

## File Structure

- Create `gaia/engine/bp/joint_query.py`
  - Owns `JointDistribution`, `JointQueryUnavailable`, `joint_over`, and `compare_joint_over`.
  - Wraps exact enumeration, junction-tree calibrated clique marginals, TRW-BP factor pseudo-joints, and mean-field variational joints.
- Modify `gaia/engine/bp/junction_tree.py`
  - Exposes a reusable `calibrate_junction_tree(graph)` helper so joint queries can reuse calibrated cliques without duplicating inference code.
- Modify `gaia/engine/bp/trw_bp.py`
  - Records normalized factor-scope pseudo-joints in diagnostics after convergence.
- Modify `gaia/engine/bp/__init__.py`
  - Exports the stable joint-query API.
- Create `gaia/engine/ir/logic/probability.py`
  - Owns Boolean AST event evaluation and diagnostic condition scoring over supplied joint tables.
- Modify `gaia/engine/ir/logic/__init__.py`
  - Exports stable diagnostic-probability models and scoring helpers.
- Create `tests/gaia/bp/test_joint_query.py`
  - Tests joint provider behavior and method provenance.
- Create `tests/gaia/logic/test_diagnostic_probability.py`
  - Tests event probability, diagnostic scoring, missing-variable handling, and #648-style diagnostics.

All new test files should include:

```python
pytestmark = pytest.mark.pr_gate
```

This keeps the new coverage active under PR CI slicing.

## Task 1: Joint Query Models, Exact Provider, Mean-Field Provider

**Files:**
- Create: `gaia/engine/bp/joint_query.py`
- Create: `tests/gaia/bp/test_joint_query.py`

- [ ] **Step 1: Add failing joint-query tests**

Create `tests/gaia/bp/test_joint_query.py`:

```python
import pytest

from gaia.engine.bp.factor_graph import FactorGraph, FactorType
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointQueryUnavailable,
    compare_joint_over,
    joint_over,
)

pytestmark = pytest.mark.pr_gate


def _two_variable_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.7)
    graph.add_variable("B", 0.2)
    return graph


def _entailment_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.5)
    graph.add_factor("f:a_to_b", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
    return graph


def test_joint_distribution_validates_bit_order_and_normalization():
    joint = JointDistribution(
        variables=["A", "B"],
        probabilities=[0.24, 0.56, 0.06, 0.14],
        method="exact",
        is_exact=True,
        basis="exact_joint_distribution",
    )

    assert joint.variables == ["A", "B"]
    assert joint.probabilities[3] == pytest.approx(0.14)


def test_exact_joint_over_preserves_existing_bit_order():
    joint = joint_over(_two_variable_graph(), ["A", "B"], method="exact")

    assert joint.method == "exact"
    assert joint.is_exact is True
    assert joint.basis == "exact_joint_distribution"
    assert joint.variables == ["A", "B"]
    assert joint.probabilities == pytest.approx([0.24, 0.56, 0.06, 0.14])


def test_mean_field_joint_is_variational_product_distribution():
    joint = joint_over(_two_variable_graph(), ["A", "B"], method="mean_field")

    assert joint.method == "mean_field"
    assert joint.is_exact is False
    assert joint.basis == "variational_joint_distribution"
    assert joint.probabilities == pytest.approx([0.24, 0.56, 0.06, 0.14])
    assert joint.diagnostics["converged"] is True


def test_compare_joint_over_collects_unavailable_methods():
    results = compare_joint_over(
        _two_variable_graph(),
        ["A", "B"],
        methods=("exact", "trw_bp", "mean_field"),
    )

    estimates = [result for result in results if isinstance(result, JointDistribution)]
    unavailable = [result for result in results if isinstance(result, JointQueryUnavailable)]

    assert {estimate.method for estimate in estimates} == {"exact", "mean_field"}
    assert {item.method for item in unavailable} == {"trw_bp"}
    assert all(item.variables == ["A", "B"] for item in unavailable)


def test_unknown_variable_is_collected_as_unavailable():
    results = compare_joint_over(_two_variable_graph(), ["A", "missing"], methods=("exact",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "exact"
    assert "unknown variables" in unavailable.reason


def test_mean_field_on_entailment_graph_returns_normalized_joint():
    joint = joint_over(_entailment_graph(), ["A", "B"], method="mean_field")

    assert sum(joint.probabilities) == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in joint.probabilities)
    assert joint.diagnostics["iterations_run"] >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py -q --no-cov
```

Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.engine.bp.joint_query'`.

- [ ] **Step 3: Add joint-query models and exact/mean-field providers**

Create `gaia/engine/bp/joint_query.py`:

```python
"""Joint distribution queries for Gaia factor-graph inference."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import product as cartesian_product
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from gaia.engine.bp.exact import exact_joint_over
from gaia.engine.bp.factor_graph import CROMWELL_EPS, FactorGraph
from gaia.engine.bp.mean_field import MeanFieldVI

JointQueryMethod = Literal["exact", "junction_tree", "trw_bp", "mean_field"]
JointDistributionBasis = Literal[
    "exact_joint_distribution",
    "calibrated_clique_marginal",
    "approximate_joint_distribution",
    "variational_joint_distribution",
]

_NORMALIZATION_TOLERANCE = 1e-9


class JointQueryUnavailableError(RuntimeError):
    """Raised when a method cannot provide a requested joint distribution."""

    def __init__(
        self,
        method: JointQueryMethod,
        variables: Sequence[str],
        reason: str,
        diagnostics: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(reason)
        self.method = method
        self.variables = list(variables)
        self.reason = reason
        self.diagnostics = diagnostics or {}


class JointDistribution(BaseModel):
    """A normalized joint table over a binary variable set."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    probabilities: list[float]
    method: JointQueryMethod
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _validate_distribution(self) -> "JointDistribution":
        expected = 1 << len(self.variables)
        if len(self.probabilities) != expected:
            raise ValueError(
                f"JointDistribution over {len(self.variables)} variables requires "
                f"{expected} probabilities, got {len(self.probabilities)}."
            )
        if len(set(self.variables)) != len(self.variables):
            raise ValueError("JointDistribution variables must be unique.")
        if any(value < -_NORMALIZATION_TOLERANCE for value in self.probabilities):
            raise ValueError("JointDistribution probabilities must be non-negative.")
        total = sum(self.probabilities)
        if abs(total - 1.0) > _NORMALIZATION_TOLERANCE:
            raise ValueError(f"JointDistribution probabilities must sum to 1, got {total}.")
        self.probabilities = [
            0.0 if abs(value) < _NORMALIZATION_TOLERANCE else value
            for value in self.probabilities
        ]
        return self


class JointQueryUnavailable(BaseModel):
    """A method-specific joint query miss."""

    model_config = ConfigDict(extra="forbid")

    variables: list[str]
    method: JointQueryMethod
    reason: str
    diagnostics: dict[str, Any] = Field(default_factory=dict)


def joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    method: JointQueryMethod,
) -> JointDistribution:
    """Return a joint table over ``variables`` using one inference method."""
    requested = _normalized_variables(variables)
    _require_known_variables(graph, requested, method)

    if method == "exact":
        return _exact_joint_over(graph, requested)
    if method == "mean_field":
        return _mean_field_joint_over(graph, requested)
    if method == "junction_tree":
        raise JointQueryUnavailableError(
            method,
            requested,
            "junction_tree joint queries are added in Task 2",
        )
    if method == "trw_bp":
        raise JointQueryUnavailableError(
            method,
            requested,
            "trw_bp factor-scope joint queries are added in Task 3",
        )

    raise ValueError(f"Unknown joint query method: {method!r}")


def compare_joint_over(
    graph: FactorGraph,
    variables: Sequence[str],
    *,
    methods: Sequence[JointQueryMethod] = ("exact", "junction_tree", "trw_bp", "mean_field"),
) -> list[JointDistribution | JointQueryUnavailable]:
    """Run several joint providers and collect unavailable methods explicitly."""
    requested = _normalized_variables(variables)
    results: list[JointDistribution | JointQueryUnavailable] = []
    for method in methods:
        try:
            results.append(joint_over(graph, requested, method=method))
        except JointQueryUnavailableError as error:
            results.append(
                JointQueryUnavailable(
                    variables=error.variables,
                    method=error.method,
                    reason=error.reason,
                    diagnostics=error.diagnostics,
                )
            )
    return results


def _normalized_variables(variables: Sequence[str]) -> list[str]:
    requested = list(variables)
    if not requested:
        raise ValueError("joint_over requires at least one variable.")
    if not all(isinstance(variable, str) and variable for variable in requested):
        raise ValueError("joint_over variables must be non-empty strings.")
    if len(set(requested)) != len(requested):
        raise ValueError("joint_over variables must be unique.")
    return requested


def _require_known_variables(
    graph: FactorGraph,
    variables: Sequence[str],
    method: JointQueryMethod,
) -> None:
    missing = [variable for variable in variables if variable not in graph.variables]
    if missing:
        raise JointQueryUnavailableError(
            method,
            variables,
            f"unknown variables in factor graph: {missing!r}",
            diagnostics={"missing": missing},
        )


def _exact_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    try:
        probs = exact_joint_over(graph, variables)
    except (KeyError, ValueError, RuntimeError) as error:
        raise JointQueryUnavailableError(
            "exact",
            variables,
            str(error),
            diagnostics={"exception": type(error).__name__},
        ) from error
    return JointDistribution(
        variables=variables,
        probabilities=[float(value) for value in probs.tolist()],
        method="exact",
        is_exact=True,
        basis="exact_joint_distribution",
    )


def _mean_field_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    result = MeanFieldVI().run(graph)
    missing = [variable for variable in variables if variable not in result.beliefs]
    if missing:
        raise JointQueryUnavailableError(
            "mean_field",
            variables,
            f"mean_field result missing variables: {missing!r}",
            diagnostics={"missing": missing},
        )

    probabilities: list[float] = []
    for values in cartesian_product((0, 1), repeat=len(variables)):
        probability = 1.0
        for variable, value in zip(variables, values, strict=True):
            belief = result.beliefs[variable]
            probability *= belief if value == 1 else (1.0 - belief)
        probabilities.append(float(probability))

    return JointDistribution(
        variables=variables,
        probabilities=probabilities,
        method="mean_field",
        is_exact=False,
        basis="variational_joint_distribution",
        diagnostics={
            "converged": result.diagnostics.converged,
            "iterations_run": result.diagnostics.iterations_run,
            "max_change_at_stop": result.diagnostics.max_change_at_stop,
            "cromwell_eps": CROMWELL_EPS,
        },
    )
```

- [ ] **Step 4: Run joint-query tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py -q --no-cov
```

Expected: PASS for Task 1 tests.

- [ ] **Step 5: Commit Task 1**

```bash
git add gaia/engine/bp/joint_query.py tests/gaia/bp/test_joint_query.py
git commit -m "feat: add joint query exact and mean-field providers"
```

## Task 2: Junction-Tree Joint Provider

**Files:**
- Modify: `gaia/engine/bp/junction_tree.py`
- Modify: `gaia/engine/bp/joint_query.py`
- Modify: `tests/gaia/bp/test_joint_query.py`

- [ ] **Step 1: Add failing junction-tree tests**

Append to `tests/gaia/bp/test_joint_query.py`:

```python
def _chain_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.8)
    graph.add_variable("B", 0.5)
    graph.add_variable("C", 0.5)
    graph.add_factor("f:a_to_b", FactorType.SOFT_ENTAILMENT, ["A"], "B", p1=0.9, p2=0.9)
    graph.add_factor("f:b_to_c", FactorType.SOFT_ENTAILMENT, ["B"], "C", p1=0.85, p2=0.9)
    return graph


def test_junction_tree_joint_matches_exact_when_clique_contains_query():
    graph = _chain_graph()

    exact = joint_over(graph, ["A", "B"], method="exact")
    jt = joint_over(graph, ["A", "B"], method="junction_tree")

    assert jt.method == "junction_tree"
    assert jt.is_exact is True
    assert jt.basis == "calibrated_clique_marginal"
    assert jt.variables == ["A", "B"]
    assert jt.probabilities == pytest.approx(exact.probabilities, abs=1e-9)
    assert jt.diagnostics["treewidth"] >= 1


def test_junction_tree_returns_unavailable_without_covering_clique():
    results = compare_joint_over(_chain_graph(), ["A", "C"], methods=("junction_tree",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "junction_tree"
    assert "single calibrated clique" in unavailable.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_junction_tree_joint_matches_exact_when_clique_contains_query tests/gaia/bp/test_joint_query.py::test_junction_tree_returns_unavailable_without_covering_clique -q --no-cov
```

Expected: FAIL because `junction_tree` still reports Task 2 unavailable.

- [ ] **Step 3: Expose junction-tree calibration helper**

Modify `gaia/engine/bp/junction_tree.py`.

Add `dataclass` import:

```python
from dataclasses import dataclass
```

Update `__all__`:

```python
__all__ = [
    "JunctionTreeCalibration",
    "JunctionTreeInference",
    "calibrate_junction_tree",
    "jt_treewidth",
]
```

Add below the type aliases:

```python
@dataclass(frozen=True)
class JunctionTreeCalibration:
    """Calibrated clique tables from a junction-tree run."""

    cliques: list[frozenset[str]]
    clique_var_lists: list[list[str]]
    calibrated: list[PotentialTable]
    treewidth: int
```

Add before `class JunctionTreeInference`:

```python
def calibrate_junction_tree(graph: FactorGraph) -> JunctionTreeCalibration:
    """Return calibrated junction-tree clique tables for a factor graph."""
    if not graph.variables:
        return JunctionTreeCalibration(
            cliques=[],
            clique_var_lists=[],
            calibrated=[],
            treewidth=0,
        )
    if not graph.factors:
        clique = frozenset(graph.variables.keys())
        variables = sorted(clique)
        table: PotentialTable = {}
        for vals in cartesian_product((0, 1), repeat=len(variables)):
            probability = 1.0
            for variable, value in zip(variables, vals, strict=True):
                if variable in graph.hard_evidence:
                    belief = (
                        (1.0 - CROMWELL_EPS)
                        if graph.hard_evidence[variable] == 1
                        else CROMWELL_EPS
                    )
                else:
                    belief = graph.unary_factors.get(variable, 0.5)
                probability *= belief if value == 1 else (1.0 - belief)
            table[vals] = probability
        return JunctionTreeCalibration(
            cliques=[clique],
            clique_var_lists=[variables],
            calibrated=[table],
            treewidth=max(len(variables) - 1, 0),
        )

    moral_adj = _build_moral_graph(graph)
    _, elim_cliques = _triangulate_min_fill(moral_adj)
    cliques = _maximal_cliques(elim_cliques)
    n_cliques = len(cliques)
    clique_var_lists = [sorted(c) for c in cliques]
    treewidth = max(len(c) for c in cliques) - 1

    tree_edges = _build_junction_tree(cliques)
    tree_adj = _tree_adjacency(n_cliques, tree_edges)
    factor_assignment = _assign_factors_to_cliques(cliques, graph)

    unary_assigned: set[str] = set()
    clique_potentials: list[PotentialTable] = []
    for i, clique in enumerate(cliques):
        var_list = clique_var_lists[i]
        local_priors: dict[str, float] = {}
        for variable in var_list:
            if variable in graph.hard_evidence and variable not in unary_assigned:
                local_priors[variable] = (
                    (1.0 - CROMWELL_EPS)
                    if graph.hard_evidence[variable] == 1
                    else CROMWELL_EPS
                )
                unary_assigned.add(variable)
            elif variable in graph.unary_factors and variable not in unary_assigned:
                local_priors[variable] = graph.unary_factors[variable]
                unary_assigned.add(variable)

        clique_potentials.append(
            _compute_clique_potential(clique, factor_assignment[i], local_priors)
        )

    calibrated = _collect_distribute(
        cliques,
        clique_potentials,
        clique_var_lists,
        tree_adj,
        n_cliques,
    )
    return JunctionTreeCalibration(
        cliques=cliques,
        clique_var_lists=clique_var_lists,
        calibrated=calibrated,
        treewidth=treewidth,
    )
```

In `JunctionTreeInference.run`, replace the main graph-with-factors body from
`# Step 1: Moral graph` through the `_extract_beliefs(...)` call with:

```python
        calibration = calibrate_junction_tree(graph)
        diag.treewidth = calibration.treewidth
        diag.iterations_run = 2
        logger.debug(
            "JT: %d variables, %d cliques, treewidth=%d",
            len(graph.variables),
            len(calibration.cliques),
            calibration.treewidth,
        )
        beliefs = _extract_beliefs(
            calibration.cliques,
            calibration.calibrated,
            calibration.clique_var_lists,
            set(graph.variables.keys()),
        )
```

Keep the existing empty-graph, no-factor, diagnostic-finalization, and return
logic unchanged around this replacement.

- [ ] **Step 4: Add junction-tree provider to joint_query**

Modify imports in `gaia/engine/bp/joint_query.py`:

```python
from gaia.engine.bp.junction_tree import calibrate_junction_tree
```

In `joint_over`, replace the `junction_tree` branch with:

```python
    if method == "junction_tree":
        return _junction_tree_joint_over(graph, requested)
```

Add helper functions:

```python
def _junction_tree_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    try:
        calibration = calibrate_junction_tree(graph)
    except (ValueError, RuntimeError) as error:
        raise JointQueryUnavailableError(
            "junction_tree",
            variables,
            str(error),
            diagnostics={"exception": type(error).__name__},
        ) from error

    requested = set(variables)
    for clique, var_list, table in zip(
        calibration.cliques,
        calibration.clique_var_lists,
        calibration.calibrated,
        strict=True,
    ):
        if requested <= clique:
            probabilities = _marginalize_table_to_variables(table, var_list, variables)
            return JointDistribution(
                variables=variables,
                probabilities=probabilities,
                method="junction_tree",
                is_exact=True,
                basis="calibrated_clique_marginal",
                diagnostics={
                    "treewidth": calibration.treewidth,
                    "clique_size": len(var_list),
                    "source_clique": var_list,
                },
            )

    raise JointQueryUnavailableError(
        "junction_tree",
        variables,
        "requested variables are not contained in a single calibrated clique",
        diagnostics={
            "treewidth": calibration.treewidth,
            "available_cliques": [sorted(clique) for clique in calibration.cliques],
        },
    )


def _marginalize_table_to_variables(
    table: dict[tuple[int, ...], float],
    table_variables: list[str],
    variables: list[str],
) -> list[float]:
    indices = [table_variables.index(variable) for variable in variables]
    probabilities = [0.0 for _ in range(1 << len(variables))]
    for assignment, probability in table.items():
        out_index = 0
        for bit, table_index in enumerate(indices):
            out_index |= assignment[table_index] << bit
        probabilities[out_index] += float(probability)
    total = sum(probabilities)
    if total <= 0.0:
        raise ValueError("marginalized joint table has zero total mass")
    return [probability / total for probability in probabilities]
```

- [ ] **Step 5: Run junction-tree tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_junction_tree_joint_matches_exact_when_clique_contains_query tests/gaia/bp/test_joint_query.py::test_junction_tree_returns_unavailable_without_covering_clique -q --no-cov
```

Expected: PASS.

- [ ] **Step 6: Run full joint-query tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py -q --no-cov
```

Expected: PASS.

- [ ] **Step 7: Commit Task 2**

```bash
git add gaia/engine/bp/junction_tree.py gaia/engine/bp/joint_query.py tests/gaia/bp/test_joint_query.py
git commit -m "feat: add junction-tree joint queries"
```

## Task 3: TRW-BP Factor-Scope Pseudo-Joint Provider

**Files:**
- Modify: `gaia/engine/bp/trw_bp.py`
- Modify: `gaia/engine/bp/joint_query.py`
- Modify: `tests/gaia/bp/test_joint_query.py`

- [ ] **Step 1: Add failing TRW joint tests**

Append to `tests/gaia/bp/test_joint_query.py`:

```python
def _contradiction_graph() -> FactorGraph:
    graph = FactorGraph()
    graph.add_variable("A", 0.7)
    graph.add_variable("B", 0.3)
    graph.add_variable("H", 0.5)
    graph.add_factor("f:contradiction", FactorType.CONTRADICTION, ["A", "B"], "H")
    return graph


def test_trw_bp_returns_factor_scope_pseudo_joint():
    joint = joint_over(_contradiction_graph(), ["A", "B"], method="trw_bp")

    assert joint.method == "trw_bp"
    assert joint.is_exact is False
    assert joint.basis == "approximate_joint_distribution"
    assert joint.variables == ["A", "B"]
    assert sum(joint.probabilities) == pytest.approx(1.0)
    assert all(0.0 <= value <= 1.0 for value in joint.probabilities)
    assert joint.diagnostics["source_factor_id"] == "f:contradiction"


def test_trw_bp_returns_unavailable_without_factor_scope_joint():
    results = compare_joint_over(_chain_graph(), ["A", "C"], methods=("trw_bp",))

    assert len(results) == 1
    unavailable = results[0]
    assert isinstance(unavailable, JointQueryUnavailable)
    assert unavailable.method == "trw_bp"
    assert "factor-scope pseudo-joint" in unavailable.reason
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_trw_bp_returns_factor_scope_pseudo_joint tests/gaia/bp/test_joint_query.py::test_trw_bp_returns_unavailable_without_factor_scope_joint -q --no-cov
```

Expected: FAIL because `trw_bp` still reports Task 3 unavailable.

- [ ] **Step 3: Record TRW factor pseudo-joints**

Modify `gaia/engine/bp/trw_bp.py`.

In `TRWDiagnostics`, add:

```python
    factor_joint_tables: dict[str, dict[str, object]] = field(default_factory=dict)
```

Add helper below `_compute_beliefs_trw`:

```python
def _compute_factor_joint_tables_trw(
    graph: FactorGraph,
    v2f_msgs: dict[tuple[str, int], Msg],
    rho: dict[int, float],
) -> dict[str, dict[str, object]]:
    """Compute normalized factor-scope pseudo-joints from converged TRW messages."""
    tables: dict[str, dict[str, object]] = {}
    for factor_idx, factor in enumerate(graph.factors):
        variables = factor.all_vars
        probabilities: list[float] = []
        rho_f = rho.get(factor_idx, 1.0)
        for values in cartesian_product((0, 1), repeat=len(variables)):
            assignment = dict(zip(variables, values, strict=True))
            potential = evaluate_potential(factor, assignment)
            weight = potential**rho_f
            for variable, value in zip(variables, values, strict=True):
                message = v2f_msgs.get((variable, factor_idx))
                if message is not None:
                    weight *= float(message[value])
            probabilities.append(float(weight))
        total = sum(probabilities)
        if total <= 0.0:
            continue
        tables[factor.factor_id] = {
            "factor_index": factor_idx,
            "factor_type": factor.factor_type.name,
            "variables": variables,
            "probabilities": [probability / total for probability in probabilities],
            "rho": rho_f,
        }
    return tables
```

In `_run_synchronous`, before every `return TRWResult(...)`, populate diagnostics:

```python
                diag.factor_joint_tables = _compute_factor_joint_tables_trw(
                    graph,
                    v2f_msgs,
                    rho,
                )
```

for the converged return, and:

```python
        diag.factor_joint_tables = _compute_factor_joint_tables_trw(
            graph,
            v2f_msgs,
            rho,
        )
```

for the max-iteration return.

If `_run_residual` is still present, add the same assignment before its final
`return TRWResult(...)`. Keep the public constructor behavior unchanged.

- [ ] **Step 4: Add TRW provider to joint_query**

Modify imports in `gaia/engine/bp/joint_query.py`:

```python
from gaia.engine.bp.trw_bp import TRWBeliefPropagation
```

In `joint_over`, replace the `trw_bp` branch with:

```python
    if method == "trw_bp":
        return _trw_bp_joint_over(graph, requested)
```

Add helper:

```python
def _trw_bp_joint_over(graph: FactorGraph, variables: list[str]) -> JointDistribution:
    result = TRWBeliefPropagation().run(graph)
    requested = set(variables)
    for factor_id, payload in result.diagnostics.factor_joint_tables.items():
        factor_variables = list(payload["variables"])
        if requested <= set(factor_variables):
            probabilities = _marginalize_table_to_variables(
                _table_from_probability_list(list(payload["probabilities"]), factor_variables),
                factor_variables,
                variables,
            )
            return JointDistribution(
                variables=variables,
                probabilities=probabilities,
                method="trw_bp",
                is_exact=False,
                basis="approximate_joint_distribution",
                diagnostics={
                    "converged": result.diagnostics.converged,
                    "iterations_run": result.diagnostics.iterations_run,
                    "max_change_at_stop": result.diagnostics.max_change_at_stop,
                    "source_factor_id": factor_id,
                    "source_factor_variables": factor_variables,
                    "rho": payload.get("rho"),
                },
            )

    raise JointQueryUnavailableError(
        "trw_bp",
        variables,
        "no factor-scope pseudo-joint contains all query variables",
        diagnostics={
            "available_factor_scopes": {
                factor_id: list(payload["variables"])
                for factor_id, payload in result.diagnostics.factor_joint_tables.items()
            }
        },
    )


def _table_from_probability_list(
    probabilities: list[float],
    variables: list[str],
) -> dict[tuple[int, ...], float]:
    expected = 1 << len(variables)
    if len(probabilities) != expected:
        raise ValueError(
            f"expected {expected} probabilities for {variables}, got {len(probabilities)}"
        )
    return {
        values: float(probabilities[index])
        for index, values in enumerate(cartesian_product((0, 1), repeat=len(variables)))
    }
```

- [ ] **Step 5: Run TRW tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_trw_bp_returns_factor_scope_pseudo_joint tests/gaia/bp/test_joint_query.py::test_trw_bp_returns_unavailable_without_factor_scope_joint -q --no-cov
```

Expected: PASS.

- [ ] **Step 6: Run full joint-query tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py -q --no-cov
```

Expected: PASS.

- [ ] **Step 7: Commit Task 3**

```bash
git add gaia/engine/bp/trw_bp.py gaia/engine/bp/joint_query.py tests/gaia/bp/test_joint_query.py
git commit -m "feat: add trw factor-scope joint queries"
```

## Task 4: Diagnostic Condition Probability Scoring

**Files:**
- Create: `gaia/engine/ir/logic/probability.py`
- Create: `tests/gaia/logic/test_diagnostic_probability.py`

- [ ] **Step 1: Add failing diagnostic probability tests**

Create `tests/gaia/logic/test_diagnostic_probability.py`:

```python
import pytest

from gaia.engine.bp.factor_graph import FactorGraph
from gaia.engine.bp.joint_query import JointDistribution, JointQueryUnavailable
from gaia.engine.ir.logic.diagnostics import DiagnosticCondition, FormulaDiagnostic
from gaia.engine.ir.logic.probability import (
    DiagnosticProbability,
    event_probability,
    score_condition,
    score_diagnostic_conditions,
)

pytestmark = pytest.mark.pr_gate


def _explicit_joint() -> JointDistribution:
    return JointDistribution(
        variables=["A", "B"],
        probabilities=[0.3, 0.2, 0.1, 0.4],
        method="exact",
        is_exact=True,
        basis="exact_joint_distribution",
    )


def _and_condition() -> DiagnosticCondition:
    return DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["A", "B"],
        expression={"op": "and", "args": [{"var": "A"}, {"var": "B"}]},
        confidence_basis="hard_logic",
    )


def test_event_probability_computes_and_event_from_joint_table():
    probability = event_probability(
        {"op": "and", "args": [{"var": "A"}, {"var": "B"}]},
        _explicit_joint(),
    )

    assert probability == pytest.approx(0.4)


def test_event_probability_computes_entailment_violation_event():
    probability = event_probability(
        {"op": "and", "args": [{"var": "A"}, {"op": "not", "arg": {"var": "B"}}]},
        _explicit_joint(),
    )

    assert probability == pytest.approx(0.2)


def test_event_probability_computes_equivalence_mismatch_event():
    probability = event_probability(
        {
            "op": "or",
            "args": [
                {"op": "and", "args": [{"var": "A"}, {"op": "not", "arg": {"var": "B"}}]},
                {"op": "and", "args": [{"var": "B"}, {"op": "not", "arg": {"var": "A"}}]},
            ],
        },
        _explicit_joint(),
    )

    assert probability == pytest.approx(0.3)


def test_event_probability_rejects_missing_joint_variable():
    with pytest.raises(ValueError, match="missing from joint distribution"):
        event_probability({"var": "C"}, _explicit_joint())


def test_score_condition_preserves_estimates_unavailable_and_spread():
    exact = _explicit_joint()
    mean_field = JointDistribution(
        variables=["A", "B"],
        probabilities=[0.2, 0.3, 0.2, 0.3],
        method="mean_field",
        is_exact=False,
        basis="variational_joint_distribution",
    )
    unavailable = JointQueryUnavailable(
        variables=["A", "B"],
        method="trw_bp",
        reason="no factor-scope pseudo-joint contains all query variables",
    )

    scored = score_condition(
        _and_condition(),
        [exact, mean_field, unavailable],
        diagnostic_code="cross_claim_incompatibility",
    )

    assert isinstance(scored, DiagnosticProbability)
    assert scored.diagnostic_code == "cross_claim_incompatibility"
    assert [estimate.method for estimate in scored.estimates] == ["exact", "mean_field"]
    assert [estimate.probability for estimate in scored.estimates] == pytest.approx([0.4, 0.3])
    assert scored.spread == pytest.approx(0.1)
    assert scored.exact_spread == pytest.approx(0.0)
    assert scored.unavailable == [unavailable]


def test_score_diagnostic_conditions_scores_formula_diagnostic_condition():
    graph = FactorGraph()
    graph.add_variable("A", 0.7)
    graph.add_variable("B", 0.2)
    diagnostic = FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="A",
        related_claims=["B"],
        formula_nodes=["fg:a", "fg:b"],
        condition=_and_condition(),
        message="A and B cannot both hold.",
    )

    scored = score_diagnostic_conditions([diagnostic], graph, methods=("exact",))

    assert len(scored) == 1
    assert scored[0].diagnostic_code == "cross_claim_incompatibility"
    assert scored[0].estimates[0].probability == pytest.approx(0.14)


def test_score_diagnostic_conditions_skips_diagnostics_without_conditions():
    graph = FactorGraph()
    graph.add_variable("A", 0.7)
    diagnostic = FormulaDiagnostic(
        code="formula_projection_unsupported",
        severity="info",
        scope="claim",
        logic_strength="unknown",
        source_claim="A",
        formula_nodes=["fg:a"],
        message="Unsupported formula.",
    )

    assert score_diagnostic_conditions([diagnostic], graph, methods=("exact",)) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/gaia/logic/test_diagnostic_probability.py -q --no-cov
```

Expected: FAIL with `ModuleNotFoundError: No module named 'gaia.engine.ir.logic.probability'`.

- [ ] **Step 3: Implement diagnostic probability scoring**

Create `gaia/engine/ir/logic/probability.py`:

```python
"""Probability scoring for formula diagnostic conditions."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import product as cartesian_product
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from gaia.engine.bp.factor_graph import FactorGraph
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointDistributionBasis,
    JointQueryMethod,
    JointQueryUnavailable,
    compare_joint_over,
)
from gaia.engine.ir.logic.diagnostics import DiagnosticCondition, FormulaDiagnostic


class ConditionProbabilityEstimate(BaseModel):
    """One method-specific event probability estimate."""

    model_config = ConfigDict(extra="forbid")

    method: JointQueryMethod
    probability: float
    is_exact: bool
    basis: JointDistributionBasis
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class DiagnosticProbability(BaseModel):
    """Probability scoring result for one diagnostic condition."""

    model_config = ConfigDict(extra="forbid")

    diagnostic_code: str | None = None
    condition_kind: str
    variables: list[str]
    event_expression: dict[str, Any]
    estimates: list[ConditionProbabilityEstimate] = Field(default_factory=list)
    unavailable: list[JointQueryUnavailable] = Field(default_factory=list)
    spread: float | None = None
    exact_spread: float | None = None


def event_probability(expression: dict[str, Any], joint: JointDistribution) -> float:
    """Evaluate a Boolean event over a joint distribution table."""
    total = 0.0
    for values, probability in zip(
        cartesian_product((0, 1), repeat=len(joint.variables)),
        joint.probabilities,
        strict=True,
    ):
        assignment = {
            variable: bool(value)
            for variable, value in zip(joint.variables, values, strict=True)
        }
        if _eval_event_expression(expression, assignment):
            total += probability
    return float(total)


def score_condition(
    condition: DiagnosticCondition,
    joints: Sequence[JointDistribution | JointQueryUnavailable],
    *,
    diagnostic_code: str | None = None,
) -> DiagnosticProbability:
    """Score a diagnostic condition against supplied joint query results."""
    estimates: list[ConditionProbabilityEstimate] = []
    unavailable: list[JointQueryUnavailable] = []

    for item in joints:
        if isinstance(item, JointQueryUnavailable):
            unavailable.append(item)
            continue
        probability = event_probability(condition.expression, item)
        estimates.append(
            ConditionProbabilityEstimate(
                method=item.method,
                probability=probability,
                is_exact=item.is_exact,
                basis=item.basis,
                diagnostics=item.diagnostics,
            )
        )

    probabilities = [estimate.probability for estimate in estimates]
    exact_probabilities = [
        estimate.probability for estimate in estimates if estimate.is_exact
    ]
    spread = _spread(probabilities)
    exact_spread = _spread(exact_probabilities)

    return DiagnosticProbability(
        diagnostic_code=diagnostic_code,
        condition_kind=condition.kind,
        variables=condition.variables,
        event_expression=condition.expression,
        estimates=estimates,
        unavailable=unavailable,
        spread=spread,
        exact_spread=exact_spread,
    )


def score_diagnostic_conditions(
    diagnostics: Sequence[FormulaDiagnostic],
    graph: FactorGraph,
    *,
    methods: Sequence[JointQueryMethod] = ("exact", "junction_tree", "trw_bp", "mean_field"),
) -> list[DiagnosticProbability]:
    """Score all condition-bearing formula diagnostics against a factor graph."""
    scored: list[DiagnosticProbability] = []
    for diagnostic in diagnostics:
        if diagnostic.condition is None:
            continue
        joints = compare_joint_over(graph, diagnostic.condition.variables, methods=methods)
        scored.append(
            score_condition(
                diagnostic.condition,
                joints,
                diagnostic_code=diagnostic.code,
            )
        )
    return scored


def _eval_event_expression(expression: dict[str, Any], assignment: dict[str, bool]) -> bool:
    if "var" in expression:
        variable = expression["var"]
        if not isinstance(variable, str):
            raise ValueError("event variable must be a string")
        if variable not in assignment:
            raise ValueError(f"event variable {variable!r} is missing from joint distribution")
        return assignment[variable]

    operator = expression.get("op")
    if operator == "not":
        arg = expression.get("arg")
        if not isinstance(arg, dict):
            raise ValueError("event 'not' expression requires object arg")
        return not _eval_event_expression(arg, assignment)

    if operator == "and":
        args = expression.get("args")
        if not isinstance(args, list) or not args:
            raise ValueError("event 'and' expression requires non-empty args")
        if not all(isinstance(arg, dict) for arg in args):
            raise ValueError("event 'and' args must be objects")
        return all(_eval_event_expression(arg, assignment) for arg in args)

    if operator == "or":
        args = expression.get("args")
        if not isinstance(args, list) or not args:
            raise ValueError("event 'or' expression requires non-empty args")
        if not all(isinstance(arg, dict) for arg in args):
            raise ValueError("event 'or' args must be objects")
        return any(_eval_event_expression(arg, assignment) for arg in args)

    raise ValueError(f"unsupported event expression operator: {operator!r}")


def _spread(values: list[float]) -> float | None:
    if not values:
        return None
    return float(max(values) - min(values))
```

- [ ] **Step 4: Run diagnostic probability tests**

Run:

```bash
uv run pytest tests/gaia/logic/test_diagnostic_probability.py -q --no-cov
```

Expected: PASS.

- [ ] **Step 5: Commit Task 4**

```bash
git add gaia/engine/ir/logic/probability.py tests/gaia/logic/test_diagnostic_probability.py
git commit -m "feat: score diagnostic conditions from joint tables"
```

## Task 5: Public Exports And End-to-End Verification

**Files:**
- Modify: `gaia/engine/bp/__init__.py`
- Modify: `gaia/engine/ir/logic/__init__.py`
- Modify: `tests/gaia/bp/test_joint_query.py`
- Modify: `tests/gaia/logic/test_diagnostic_probability.py`

- [ ] **Step 1: Add export tests**

Append to `tests/gaia/bp/test_joint_query.py`:

```python
def test_bp_package_exports_joint_query_api():
    from gaia.engine.bp import JointDistribution as ExportedJointDistribution
    from gaia.engine.bp import compare_joint_over as exported_compare_joint_over
    from gaia.engine.bp import joint_over as exported_joint_over

    assert ExportedJointDistribution is JointDistribution
    assert exported_joint_over is joint_over
    assert exported_compare_joint_over is compare_joint_over
```

Append to `tests/gaia/logic/test_diagnostic_probability.py`:

```python
def test_logic_package_exports_diagnostic_probability_api():
    from gaia.engine.ir.logic import DiagnosticProbability as ExportedDiagnosticProbability
    from gaia.engine.ir.logic import event_probability as exported_event_probability
    from gaia.engine.ir.logic import score_condition as exported_score_condition

    assert ExportedDiagnosticProbability is DiagnosticProbability
    assert exported_event_probability is event_probability
    assert exported_score_condition is score_condition
```

- [ ] **Step 2: Run export tests to verify they fail**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_bp_package_exports_joint_query_api tests/gaia/logic/test_diagnostic_probability.py::test_logic_package_exports_diagnostic_probability_api -q --no-cov
```

Expected: FAIL because exports have not been added.

- [ ] **Step 3: Export BP joint-query API**

Modify `gaia/engine/bp/__init__.py`.

Add import block:

```python
from gaia.engine.bp.joint_query import (
    JointDistribution,
    JointDistributionBasis,
    JointQueryMethod,
    JointQueryUnavailable,
    JointQueryUnavailableError,
    compare_joint_over,
    joint_over,
)
```

Add these names to `__all__`:

```python
    "JointDistribution",
    "JointDistributionBasis",
    "JointQueryMethod",
    "JointQueryUnavailable",
    "JointQueryUnavailableError",
    "compare_joint_over",
    "joint_over",
```

- [ ] **Step 4: Export logic probability API**

Modify `gaia/engine/ir/logic/__init__.py`.

Add import block:

```python
from gaia.engine.ir.logic.probability import (
    ConditionProbabilityEstimate,
    DiagnosticProbability,
    event_probability,
    score_condition,
    score_diagnostic_conditions,
)
```

Add these names to `__all__`:

```python
    "ConditionProbabilityEstimate",
    "DiagnosticProbability",
    "event_probability",
    "score_condition",
    "score_diagnostic_conditions",
```

- [ ] **Step 5: Run export tests**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py::test_bp_package_exports_joint_query_api tests/gaia/logic/test_diagnostic_probability.py::test_logic_package_exports_diagnostic_probability_api -q --no-cov
```

Expected: PASS.

- [ ] **Step 6: Run focused test suite**

Run:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py tests/gaia/logic/test_formula_diagnostics.py tests/gaia/bp/test_inference.py -q --no-cov
```

Expected: PASS. Existing deprecation warnings from old formula sugar are acceptable.

- [ ] **Step 7: Run formatting and linting**

Run:

```bash
uv run ruff check gaia/engine/bp/joint_query.py gaia/engine/bp/junction_tree.py gaia/engine/bp/trw_bp.py gaia/engine/ir/logic/probability.py gaia/engine/bp/__init__.py gaia/engine/ir/logic/__init__.py tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py
uv run ruff format --check gaia/engine/bp/joint_query.py gaia/engine/bp/junction_tree.py gaia/engine/bp/trw_bp.py gaia/engine/ir/logic/probability.py gaia/engine/bp/__init__.py gaia/engine/ir/logic/__init__.py tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py
```

Expected: both commands pass.

- [ ] **Step 8: Run focused type checks**

Run:

```bash
uv run mypy gaia/engine/bp/joint_query.py gaia/engine/ir/logic/probability.py
```

Expected: PASS.

- [ ] **Step 9: Commit Task 5**

```bash
git add gaia/engine/bp/__init__.py gaia/engine/ir/logic/__init__.py tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py
git commit -m "feat: export diagnostic probability APIs"
```

## Completion Criteria

- `joint_over(..., method="exact")` returns the exact joint marginal from the factor graph.
- `joint_over(..., method="junction_tree")` returns an exact calibrated clique marginal when a clique covers the requested variables.
- `joint_over(..., method="mean_field")` returns the variational joint defined by Mean Field VI.
- `joint_over(..., method="trw_bp")` returns a method-consistent factor-scope pseudo-joint when available and explicit unavailable otherwise.
- No code path computes diagnostic condition probability from marginal-only substitutes.
- `event_probability` scores Boolean AST events by summing joint-table rows.
- `score_diagnostic_conditions` scores #648-style `FormulaDiagnostic.condition` objects and preserves per-method provenance.
- Cross-method output includes exact/approximate method estimates, unavailable provider records, `spread`, and `exact_spread`.
- New tests are marked `pr_gate`.

## Final Verification Commands

Run these before opening or updating the PR:

```bash
uv run pytest tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py tests/gaia/logic/test_formula_diagnostics.py tests/gaia/bp/test_inference.py -q --no-cov
uv run ruff check gaia/engine/bp/joint_query.py gaia/engine/bp/junction_tree.py gaia/engine/bp/trw_bp.py gaia/engine/ir/logic/probability.py gaia/engine/bp/__init__.py gaia/engine/ir/logic/__init__.py tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py
uv run ruff format --check gaia/engine/bp/joint_query.py gaia/engine/bp/junction_tree.py gaia/engine/bp/trw_bp.py gaia/engine/ir/logic/probability.py gaia/engine/bp/__init__.py gaia/engine/ir/logic/__init__.py tests/gaia/bp/test_joint_query.py tests/gaia/logic/test_diagnostic_probability.py
uv run mypy gaia/engine/bp/joint_query.py gaia/engine/ir/logic/probability.py
```
