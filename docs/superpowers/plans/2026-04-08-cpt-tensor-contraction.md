# CPT via Tensor Contraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace brute-force BP-based CPT computation in `fold_composite_to_cpt` and `compute_coarse_cpts` with exact layer-by-layer tensor contraction, eliminating O(2^k × BP) cost.

**Architecture:** New module `gaia/bp/contraction.py` provides three shared primitives: `factor_to_tensor` (Factor → ndarray), `contract_to_cpt` (einsum-based variable elimination with unary priors), and `strategy_cpt` (recursive per-strategy CPT with per-call cache). Both entry points become thin wrappers around these primitives. For composite strategies, recursion matches the `CompositeStrategy` tree — each layer contracts child CPT tensors along shared (bridge) variables. Each variable's unary prior is applied at exactly one layer (the layer where it gets marginalized), matching the semantics of the current BP-based implementation and `exact_inference`.

**Tech Stack:** Python 3.12, NumPy (einsum with list-of-indices form to avoid 52-char limit), existing `gaia.bp.factor_graph.FactorGraph`/`Factor`/`FactorType`, existing `gaia.bp.lowering._lower_strategy`, existing `gaia.ir.strategy.{Strategy, CompositeStrategy, FormalStrategy}`.

**GitHub issue:** SiliconEinstein/Gaia#357

**Working directory:** `.worktrees/cpt-tensor` on branch `feature/cpt-tensor-contraction`.

---

## File Structure

- **Create:** `gaia/bp/contraction.py` (~250 lines)
  - `factor_to_tensor(f: Factor) -> tuple[np.ndarray, list[str]]`
  - `contract_to_cpt(tensors, free_vars, unary_priors) -> np.ndarray`
  - `strategy_cpt(s, strat_by_id, strat_params, var_priors, namespace, package_name, cache) -> tuple[np.ndarray, list[str]]`
  - `cpt_tensor_to_list(tensor, axes, premises, conclusion) -> list[float]`
- **Create:** `tests/test_contraction.py` (new tests for primitives + integration)
- **Modify:** `gaia/bp/lowering.py` — replace `fold_composite_to_cpt` body (lines 134–190) with a thin wrapper around `strategy_cpt`
- **Modify:** `gaia/ir/coarsen.py` — replace `compute_coarse_cpts` body (lines 204–270) to precompute strategy CPTs once and contract per coarse strategy

The changes do not touch `exact_inference`, `lower_local_graph` (except as a consumer), or the `FactorGraph`/`Factor` data classes. Existing tests in `tests/test_lowering.py` must continue to pass; new equivalence tests verify numerical agreement with `exact_inference` at a tighter tolerance.

---

## Key Semantic Invariants

These must hold throughout the implementation. Every test below is checking one of them.

1. **One prior, one layer.** Every non-free variable gets its unary prior `[1-π, π]` applied exactly once, at the layer where it is marginalized. Never double-counted, never missed.
2. **Cromwell clamping constant.** All deterministic potentials use `_HIGH = 1 - CROMWELL_EPS` and `_LOW = CROMWELL_EPS` (import from `gaia.bp.factor_graph`). No new constants.
3. **Bit ordering.** The returned `list[float]` CPT is indexed by `sum((v_i << i) for i, v_i in enumerate(premises))` — bit 0 = first premise. Matches the current `fold_composite_to_cpt` convention and `FactorType.CONDITIONAL.cpt`.
4. **Conditional normalization.** For free axes (premises + conclusion), the final tensor is normalized along the conclusion axis per premise assignment: `T[..., 1] / (T[..., 0] + T[..., 1])`. Premises are never given a unary prior (we want P(C|P), not P(C,P)).
5. **Einsum list form.** All contractions must use `np.einsum(tensor, indices, ...)` list-of-indices form, not subscript-string form, so the number of variables is not bounded by 52.
6. **No silent fallback.** If `contract_to_cpt` cannot handle a case (e.g., degenerate normalization because all mass is `_LOW^n`), it raises; we do not fall back to BP. The Cromwell epsilon ensures non-zero partition functions for all well-formed graphs.

---

## Task 1: Scaffold contraction module and baseline test harness

**Files:**
- Create: `gaia/bp/contraction.py`
- Create: `tests/test_contraction.py`

- [ ] **Step 1: Create the module skeleton**

Write `gaia/bp/contraction.py`:

```python
"""Tensor-contraction-based CPT computation for Gaia IR strategies.

Replaces O(2^k × BP) brute-force folding in ``fold_composite_to_cpt`` and
``compute_coarse_cpts`` with exact variable elimination.

Design:
    - ``factor_to_tensor``: Factor → dense ndarray + axis labels
    - ``contract_to_cpt``: einsum-based variable elimination with unary priors
    - ``strategy_cpt``: recursive layer-by-layer CPT for a Strategy, cached by
      strategy_id per call

Every non-free variable's unary prior is applied exactly once, at the layer
where it is marginalized.  This matches the semantics of BP on the current
factor graph and of ``gaia.bp.exact.exact_inference``.

Spec: github.com/SiliconEinstein/Gaia/issues/357
"""

from __future__ import annotations

import numpy as np

from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

__all__ = [
    "factor_to_tensor",
    "contract_to_cpt",
    "strategy_cpt",
    "cpt_tensor_to_list",
]

_HIGH: float = 1.0 - CROMWELL_EPS
_LOW: float = CROMWELL_EPS
```

- [ ] **Step 2: Create the test file skeleton**

Write `tests/test_contraction.py`:

```python
"""Tests for gaia.bp.contraction (tensor-based CPT computation)."""

from __future__ import annotations

import numpy as np
import pytest

from gaia.bp.contraction import (
    contract_to_cpt,
    cpt_tensor_to_list,
    factor_to_tensor,
    strategy_cpt,
)
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS
```

- [ ] **Step 3: Verify the skeleton imports**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run python -c "from gaia.bp import contraction; print(contraction.__all__)"`
Expected: `['factor_to_tensor', 'contract_to_cpt', 'strategy_cpt', 'cpt_tensor_to_list']`

It will fail because the functions don't exist yet. That's fine — next task implements them. Skip this verification and proceed.

- [ ] **Step 4: Commit the scaffold**

```bash
cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor
git add gaia/bp/contraction.py tests/test_contraction.py
git commit -m "feat(bp): scaffold contraction module

Part of #357. Adds empty gaia/bp/contraction.py and tests/test_contraction.py
with imports and module docstrings. No logic yet."
```

---

## Task 2: Implement `factor_to_tensor` for all eight factor types

**Files:**
- Modify: `gaia/bp/contraction.py`
- Modify: `tests/test_contraction.py`

Every factor type becomes a `(np.ndarray, list[str])` pair. The ndarray has shape `(2,) * n` where `n = len(variables) + 1` (or `+0` for `IMPLICATION` which has 1 variable + 1 conclusion = shape `(2, 2)`). Axis order: `variables` in order, then `conclusion`. The axis label list is `[*variables, conclusion]`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contraction.py`:

```python
def _almost(a, b, eps=1e-9):
    return abs(a - b) < eps


def test_factor_to_tensor_implication():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.IMPLICATION,
        variables=["A"],
        conclusion="B",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B"]
    assert t.shape == (2, 2)
    # Forbid A=1, B=0
    assert _almost(t[1, 0], _LOW)
    assert _almost(t[0, 0], _HIGH)
    assert _almost(t[0, 1], _HIGH)
    assert _almost(t[1, 1], _HIGH)


def test_factor_to_tensor_conjunction_two_inputs():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B"],
        conclusion="M",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "M"]
    assert t.shape == (2, 2, 2)
    # M == (A AND B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 0], _HIGH)
    assert _almost(t[0, 1, 1], _LOW)
    assert _almost(t[1, 0, 0], _HIGH)
    assert _almost(t[1, 0, 1], _LOW)
    assert _almost(t[1, 1, 0], _LOW)
    assert _almost(t[1, 1, 1], _HIGH)


def test_factor_to_tensor_conjunction_three_inputs():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONJUNCTION,
        variables=["A", "B", "C"],
        conclusion="M",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "C", "M"]
    assert t.shape == (2, 2, 2, 2)
    assert _almost(t[1, 1, 1, 1], _HIGH)
    assert _almost(t[1, 1, 0, 0], _HIGH)
    assert _almost(t[1, 1, 1, 0], _LOW)
    assert _almost(t[0, 0, 0, 0], _HIGH)


def test_factor_to_tensor_disjunction():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.DISJUNCTION,
        variables=["A", "B"],
        conclusion="D",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "D"]
    # D == (A OR B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[1, 1, 1], _HIGH)
    assert _almost(t[1, 1, 0], _LOW)


def test_factor_to_tensor_equivalence():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.EQUIVALENCE,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == (A == B)
    assert _almost(t[0, 0, 1], _HIGH)
    assert _almost(t[0, 0, 0], _LOW)
    assert _almost(t[1, 1, 1], _HIGH)
    assert _almost(t[0, 1, 1], _LOW)
    assert _almost(t[0, 1, 0], _HIGH)
    assert _almost(t[1, 0, 0], _HIGH)


def test_factor_to_tensor_contradiction():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.CONTRADICTION,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == NOT(A AND B)
    assert _almost(t[1, 1, 0], _HIGH)
    assert _almost(t[1, 1, 1], _LOW)
    assert _almost(t[0, 0, 1], _HIGH)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[0, 0, 0], _LOW)


def test_factor_to_tensor_complement():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.COMPLEMENT,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    # H == (A XOR B)
    assert _almost(t[0, 0, 0], _HIGH)
    assert _almost(t[0, 0, 1], _LOW)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 0, 1], _HIGH)
    assert _almost(t[1, 1, 0], _HIGH)
    assert _almost(t[1, 1, 1], _LOW)


def test_factor_to_tensor_soft_entailment():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.8, p2=0.9)
    f = fg.factors[0]
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "C"]
    assert t.shape == (2, 2)
    assert _almost(t[1, 1], 0.8)
    assert _almost(t[1, 0], 0.2)
    assert _almost(t[0, 0], 0.9)
    assert _almost(t[0, 1], 0.1)


def test_factor_to_tensor_conditional():
    # Two premises; cpt is 2^2 = 4 entries.
    cpt = [0.1, 0.4, 0.6, 0.95]  # indexed by v0 | v1<<1
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=cpt)
    f = fg.factors[0]
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "C"]
    assert t.shape == (2, 2, 2)
    # (A=0, B=0): cpt[0]
    assert _almost(t[0, 0, 1], 0.1)
    assert _almost(t[0, 0, 0], 0.9)
    # (A=1, B=0): cpt[1]
    assert _almost(t[1, 0, 1], 0.4)
    assert _almost(t[1, 0, 0], 0.6)
    # (A=0, B=1): cpt[2]
    assert _almost(t[0, 1, 1], 0.6)
    assert _almost(t[0, 1, 0], 0.4)
    # (A=1, B=1): cpt[3]
    assert _almost(t[1, 1, 1], 0.95)
    assert _almost(t[1, 1, 0], 0.05)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -x -v`
Expected: FAIL with `ImportError: cannot import name 'factor_to_tensor'` (or similar — the function doesn't exist yet).

- [ ] **Step 3: Implement `factor_to_tensor`**

Append to `gaia/bp/contraction.py`:

```python
def factor_to_tensor(f: Factor) -> tuple[np.ndarray, list[str]]:
    """Build a dense tensor representation of a Factor.

    Shape: ``(2,) * (len(f.variables) + 1)``.
    Axis order: ``f.variables`` in order, then ``f.conclusion``.

    Deterministic factors use ``_HIGH``/``_LOW`` (Cromwell clamp) so they
    match the semantics of ``gaia.bp.potentials`` exactly.  Parametric
    factors (SOFT_ENTAILMENT, CONDITIONAL) use their stored parameters.
    """
    axes = [*f.variables, f.conclusion]
    n = len(axes)
    shape = (2,) * n
    ft = f.factor_type

    if ft == FactorType.IMPLICATION:
        t = np.full(shape, _HIGH, dtype=np.float64)
        # Forbid (antecedent=1, consequent=0)
        t[1, 0] = _LOW
        return t, axes

    if ft == FactorType.CONJUNCTION:
        t = np.full(shape, _LOW, dtype=np.float64)
        # Build index arrays: iterate all assignments, mark H where
        # conclusion == AND(inputs).
        for idx in np.ndindex(*shape):
            inputs = idx[:-1]
            concl = idx[-1]
            target = 1 if all(v == 1 for v in inputs) else 0
            if concl == target:
                t[idx] = _HIGH
        return t, axes

    if ft == FactorType.DISJUNCTION:
        t = np.full(shape, _LOW, dtype=np.float64)
        for idx in np.ndindex(*shape):
            inputs = idx[:-1]
            concl = idx[-1]
            target = 1 if any(v == 1 for v in inputs) else 0
            if concl == target:
                t[idx] = _HIGH
        return t, axes

    if ft == FactorType.EQUIVALENCE:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 1 if a == b else 0
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.CONTRADICTION:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 0 if (a == 1 and b == 1) else 1
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.COMPLEMENT:
        t = np.full(shape, _LOW, dtype=np.float64)
        for a in (0, 1):
            for b in (0, 1):
                target = 1 if a != b else 0
                t[a, b, target] = _HIGH
        return t, axes

    if ft == FactorType.SOFT_ENTAILMENT:
        if f.p1 is None or f.p2 is None:
            raise ValueError(f"SOFT_ENTAILMENT {f.factor_id!r} missing p1/p2")
        p1, p2 = f.p1, f.p2
        t = np.empty(shape, dtype=np.float64)
        # Axes: [premise, conclusion]
        t[0, 0] = p2
        t[0, 1] = 1.0 - p2
        t[1, 0] = 1.0 - p1
        t[1, 1] = p1
        return t, axes

    if ft == FactorType.CONDITIONAL:
        if f.cpt is None:
            raise ValueError(f"CONDITIONAL {f.factor_id!r} missing cpt")
        cpt = np.asarray(f.cpt, dtype=np.float64)
        k = len(f.variables)
        expected = 1 << k
        if cpt.shape != (expected,):
            raise ValueError(
                f"CONDITIONAL {f.factor_id!r}: cpt length {cpt.shape[0]} != 2^k={expected}"
            )
        t = np.empty(shape, dtype=np.float64)
        for idx in np.ndindex(*shape):
            prem_idx = 0
            for bit, v in enumerate(idx[:-1]):
                if v == 1:
                    prem_idx |= 1 << bit
            p = cpt[prem_idx]
            t[idx] = p if idx[-1] == 1 else (1.0 - p)
        return t, axes

    raise ValueError(f"Unknown FactorType: {ft!r}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -x -v`
Expected: all 9 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/contraction.py tests/test_contraction.py
git commit -m "feat(bp): implement factor_to_tensor for all factor types

Part of #357. Adds dense ndarray representation for each of the 8
FactorType values.  Axis order is variables + conclusion.  Deterministic
factors use CROMWELL_EPS-clamped H/L; SOFT_ENTAILMENT/CONDITIONAL use
their stored parameters.  Tests cover every branch."
```

---

## Task 3: Implement `contract_to_cpt` primitive

**Files:**
- Modify: `gaia/bp/contraction.py`
- Modify: `tests/test_contraction.py`

`contract_to_cpt` takes a list of `(tensor, axis_labels)` pairs, a list of free-variable names (= premises + conclusion, in that order), and a dict of unary priors for non-free variables. It:
1. Builds unary prior tensors `[1-π, π]` for each entry in `unary_priors`
2. Assigns a unique integer index to every distinct variable across all tensors + priors
3. Calls `np.einsum` in list-of-indices form, with the output indices corresponding to the free axes (in order)
4. Normalizes along the conclusion axis (last axis of the output) so the result is `P(C=1|premises)` joint with `P(C=0|premises) = 1 - P(C=1|premises)`
5. Returns the normalized tensor of shape `(2,) * len(free_vars)`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contraction.py`:

```python
def test_contract_to_cpt_single_soft_entailment():
    """Single SE factor: CPT should match the factor's raw probabilities."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.8, p2=0.9)
    t, axes = factor_to_tensor(fg.factors[0])
    # No internal vars to marginalize; free = [A, C]
    cpt = contract_to_cpt([(t, axes)], free_vars=["A", "C"], unary_priors={})
    assert cpt.shape == (2, 2)
    # P(C=1|A=0) = 1 - p2 = 0.1
    assert _almost(cpt[0, 1], 0.1)
    assert _almost(cpt[0, 0], 0.9)
    # P(C=1|A=1) = p1 = 0.8
    assert _almost(cpt[1, 1], 0.8)
    assert _almost(cpt[1, 0], 0.2)


def test_contract_to_cpt_chain_marginalizes_bridge_var():
    """A → M → C chain with uniform M prior; verify P(C|A)."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("M", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "M", p1=0.9, p2=1.0 - CROMWELL_EPS)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.8, p2=1.0 - CROMWELL_EPS)
    tensors = [factor_to_tensor(f) for f in fg.factors]
    cpt = contract_to_cpt(
        tensors,
        free_vars=["A", "C"],
        unary_priors={"M": 0.5},
    )
    assert cpt.shape == (2, 2)
    # A=1 → M≈0.9 → C≈0.9*0.8 ≈ 0.72 (within Cromwell slack)
    assert cpt[1, 1] > 0.6 and cpt[1, 1] < 0.85
    # A=0 → M≈ε → C≈ε
    assert cpt[0, 1] < 0.1


def test_contract_to_cpt_normalizes_along_conclusion_axis():
    """Every (premise assignment, conclusion=0/1) pair must sum to 1."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor(
        "f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=[0.1, 0.3, 0.7, 0.95]
    )
    t, axes = factor_to_tensor(fg.factors[0])
    cpt = contract_to_cpt([(t, axes)], free_vars=["A", "B", "C"], unary_priors={})
    # Sum over conclusion axis for every (A,B) assignment == 1
    sums = cpt.sum(axis=-1)
    np.testing.assert_allclose(sums, np.ones((2, 2)), atol=1e-9)


def test_contract_to_cpt_empty_free_vars_raises():
    """If free_vars is empty we cannot produce a CPT — raise."""
    with pytest.raises(ValueError, match="free_vars must be non-empty"):
        contract_to_cpt([], free_vars=[], unary_priors={})


def test_contract_to_cpt_many_variables():
    """Ensure einsum list form handles more than 52 variables.

    Uses a chain of 60 variables connected by IMPLICATION factors with a
    single observation at the start.  The CPT is trivially [1-ε, 1-ε]
    for the last variable regardless of the first, but we just need the
    contraction to run without alphabet exhaustion.
    """
    n = 60
    var_names = [f"v{i}" for i in range(n)]
    factors = []
    for i in range(n - 1):
        f = Factor(
            factor_id=f"f{i}",
            factor_type=FactorType.IMPLICATION,
            variables=[var_names[i]],
            conclusion=var_names[i + 1],
        )
        factors.append(factor_to_tensor(f))
    priors = {v: 0.5 for v in var_names[1:-1]}
    cpt = contract_to_cpt(
        factors, free_vars=[var_names[0], var_names[-1]], unary_priors=priors
    )
    # Should just not crash; exact values don't matter for this test.
    assert cpt.shape == (2, 2)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py::test_contract_to_cpt_single_soft_entailment -x -v`
Expected: FAIL with `ImportError` or `NameError`.

- [ ] **Step 3: Implement `contract_to_cpt`**

Append to `gaia/bp/contraction.py`:

```python
def contract_to_cpt(
    tensors: list[tuple[np.ndarray, list[str]]],
    free_vars: list[str],
    unary_priors: dict[str, float],
) -> np.ndarray:
    """Contract a list of factor tensors down to a conditional CPT tensor.

    Parameters
    ----------
    tensors:
        List of ``(ndarray, axis_var_ids)`` pairs.  The ndarray has one axis
        per name in ``axis_var_ids`` (in order); each axis has size 2.
    free_vars:
        Variables that remain as axes in the output, in output order.
        Typically ``[*premises, conclusion]``.  The last entry is the
        conclusion and is the axis along which the output is normalized.
    unary_priors:
        Variables that must be marginalized out and have a prior
        ``[1-π, π]`` applied as a unary tensor.  Usually every non-free
        variable that appears in ``all_axes`` (union of axis labels) must
        appear here.  Variables not in any tensor are ignored.

    Returns
    -------
    ndarray of shape ``(2,) * len(free_vars)`` giving ``P(conclusion | premises)``.
    The last axis is normalized so that ``T[..., 0] + T[..., 1] == 1``.

    Raises
    ------
    ValueError
        If ``free_vars`` is empty, if an unary prior is missing for a
        variable that appears in some tensor but is neither free nor
        covered by ``unary_priors``, or if the contracted joint is zero
        for some premise assignment (would produce NaN after normalizing).
    """
    if not free_vars:
        raise ValueError("free_vars must be non-empty (need at least a conclusion axis)")

    # Collect all distinct variable names across all tensors.
    all_vars: list[str] = []
    seen: set[str] = set()
    for _, axes in tensors:
        for v in axes:
            if v not in seen:
                seen.add(v)
                all_vars.append(v)
    for v in free_vars:
        if v not in seen:
            # A free variable that doesn't appear in any tensor would produce a
            # degenerate axis in the output.  Add it as a uniform factor so the
            # output has the requested shape.
            seen.add(v)
            all_vars.append(v)

    # Every non-free variable in all_vars needs a prior (unless it's already
    # determined by some factor tensor; for correctness in the Markov-network
    # semantics used by gaia.bp, we apply a prior for every variable that the
    # caller has declared, matching exact_inference).
    missing = [v for v in all_vars if v not in free_vars and v not in unary_priors]
    if missing:
        raise ValueError(
            f"contract_to_cpt: unary prior missing for marginalized variable(s): {missing}. "
            "The caller must supply fg.variables[v] for every non-free variable."
        )

    # Assign a unique integer index to each variable.
    var_to_idx: dict[str, int] = {v: i for i, v in enumerate(all_vars)}

    # Build the einsum argument list: alternating (tensor, [axis_indices]).
    args: list[object] = []
    for t, axes in tensors:
        args.append(t)
        args.append([var_to_idx[v] for v in axes])

    # Add unary prior tensors for each non-free variable.
    for v in all_vars:
        if v in free_vars:
            continue
        pi = unary_priors[v]
        args.append(np.array([1.0 - pi, pi], dtype=np.float64))
        args.append([var_to_idx[v]])

    # Output indices = free_vars in requested order.
    out_indices = [var_to_idx[v] for v in free_vars]
    args.append(out_indices)

    joint = np.einsum(*args, optimize="greedy")  # type: ignore[arg-type]

    # Normalize along the last axis (conclusion).
    totals = joint.sum(axis=-1, keepdims=True)
    if np.any(totals <= 0):
        raise ValueError(
            "contract_to_cpt: zero partition function encountered; "
            "graph may have contradictory deterministic factors."
        )
    return joint / totals
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -x -v`
Expected: all Task 2 tests still pass AND all 5 Task 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/contraction.py tests/test_contraction.py
git commit -m "feat(bp): implement contract_to_cpt primitive

Part of #357. Takes a list of factor tensors, free variables (premises +
conclusion), and unary priors for marginalized variables; contracts via
einsum (list-of-indices form, no 52-char limit) and normalizes along the
conclusion axis.  Handles >52 variables and raises on zero-partition
degeneracy.  Five tests cover single-factor, chain, normalization,
error path, and large-graph cases."
```

---

## Task 4: Add `cpt_tensor_to_list` helper and `strategy_cpt` for leaf strategies

**Files:**
- Modify: `gaia/bp/contraction.py`
- Modify: `tests/test_contraction.py`

For leaf strategies (INFER, NOISY_AND, FormalStrategy, auto-formalizable named strategies), `strategy_cpt` builds a mini `FactorGraph` by calling `_lower_strategy` (the existing dispatch already handles all leaf types correctly — we reuse it), extracts all factors + variables from that mini fg, converts factors to tensors, and calls `contract_to_cpt` with:
- `free_vars = [*s.premises, s.conclusion]`
- `unary_priors = {v: π for v, π in mini.variables.items() if v not in free_vars}`

We also add a small flatten helper `cpt_tensor_to_list(tensor, axes, premises, conclusion) -> list[float]` that converts a tensor back to the bit-indexed list format expected by callers.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contraction.py`:

```python
from gaia.ir.strategy import Strategy, StrategyType


def test_strategy_cpt_leaf_infer():
    """Leaf INFER strategy: CPT should be the raw strat_params reshape."""
    s = Strategy(
        scope="local",
        type="infer",
        premises=["github:t::a", "github:t::b"],
        conclusion="github:t::c",
    )
    strat_by_id = {s.strategy_id: s}
    cpt_tensor, axes = strategy_cpt(
        s,
        strat_by_id=strat_by_id,
        strat_params={s.strategy_id: [0.1, 0.3, 0.7, 0.95]},
        var_priors={},
        namespace="",
        package_name="",
        cache={},
    )
    assert axes == ["github:t::a", "github:t::b", "github:t::c"]
    # P(C=1|A=0,B=0) = 0.1
    assert _almost(cpt_tensor[0, 0, 1], 0.1, eps=5e-3)
    # P(C=1|A=1,B=0) = 0.3
    assert _almost(cpt_tensor[1, 0, 1], 0.3, eps=5e-3)
    # P(C=1|A=0,B=1) = 0.7
    assert _almost(cpt_tensor[0, 1, 1], 0.7, eps=5e-3)
    # P(C=1|A=1,B=1) = 0.95
    assert _almost(cpt_tensor[1, 1, 1], 0.95, eps=5e-3)


def test_strategy_cpt_leaf_noisy_and_single_premise():
    """NOISY_AND with one premise → SOFT_ENTAILMENT, no internal vars."""
    s = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::c",
    )
    cpt_tensor, axes = strategy_cpt(
        s,
        strat_by_id={s.strategy_id: s},
        strat_params={s.strategy_id: [0.85]},
        var_priors={},
        namespace="",
        package_name="",
        cache={},
    )
    assert axes == ["github:t::a", "github:t::c"]
    # P(C=1|A=1) ≈ 0.85
    assert cpt_tensor[1, 1] > 0.84 and cpt_tensor[1, 1] < 0.86
    # P(C=1|A=0) ≈ ε (Cromwell)
    assert cpt_tensor[0, 1] < 0.01


def test_strategy_cpt_leaf_noisy_and_two_premises():
    """NOISY_AND with two premises → CONJUNCTION + SOFT_ENTAILMENT via intermediate m.

    The intermediate m is registered in the mini fg with prior 0.5 and then
    marginalized.  Expected CPT matches test_fold_composite_to_cpt_directly.
    """
    s = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a", "github:t::b"],
        conclusion="github:t::c",
    )
    cpt_tensor, axes = strategy_cpt(
        s,
        strat_by_id={s.strategy_id: s},
        strat_params={s.strategy_id: [0.85]},
        var_priors={},
        namespace="",
        package_name="",
        cache={},
    )
    assert axes == ["github:t::a", "github:t::b", "github:t::c"]
    assert cpt_tensor[0, 0, 1] < 0.05  # A=0 B=0 → C≈0
    assert cpt_tensor[1, 0, 1] < 0.05  # A=1 B=0 → C≈0
    assert cpt_tensor[0, 1, 1] < 0.05  # A=0 B=1 → C≈0
    assert cpt_tensor[1, 1, 1] > 0.83  # A=1 B=1 → C≈0.85


def test_strategy_cpt_caches_by_strategy_id():
    s = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::c",
    )
    cache: dict = {}
    t1, a1 = strategy_cpt(
        s,
        strat_by_id={s.strategy_id: s},
        strat_params={s.strategy_id: [0.9]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    assert s.strategy_id in cache
    t2, a2 = strategy_cpt(
        s,
        strat_by_id={s.strategy_id: s},
        strat_params={s.strategy_id: [0.9]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    # Same object from cache
    assert t1 is t2
    assert a1 == a2


def test_cpt_tensor_to_list_bit_ordering():
    """Bit ordering: bit 0 = first premise."""
    # Construct a known tensor: axes [A, B, C], shape (2,2,2)
    t = np.zeros((2, 2, 2))
    # P(C=1|A=0,B=0)=0.11; A=1,B=0 → 0.22; A=0,B=1 → 0.33; A=1,B=1 → 0.44
    t[0, 0, 1] = 0.11
    t[0, 0, 0] = 0.89
    t[1, 0, 1] = 0.22
    t[1, 0, 0] = 0.78
    t[0, 1, 1] = 0.33
    t[0, 1, 0] = 0.67
    t[1, 1, 1] = 0.44
    t[1, 1, 0] = 0.56
    axes = ["A", "B", "C"]
    cpt_list = cpt_tensor_to_list(t, axes, premises=["A", "B"], conclusion="C")
    # index encoding: (A << 0) | (B << 1)
    assert cpt_list == [0.11, 0.22, 0.33, 0.44]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py::test_strategy_cpt_leaf_infer -x -v`
Expected: FAIL (`strategy_cpt` and `cpt_tensor_to_list` are empty).

- [ ] **Step 3: Implement `cpt_tensor_to_list` and leaf branch of `strategy_cpt`**

Append to `gaia/bp/contraction.py`:

```python
def cpt_tensor_to_list(
    tensor: np.ndarray,
    axes: list[str],
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Flatten a normalized CPT tensor to the bit-indexed list format.

    ``tensor`` must have shape ``(2,) * len(axes)`` and be normalized
    along the conclusion axis.  The output has length ``2 ** len(premises)``
    and is indexed by ``sum(v_i << i for i, v_i in enumerate(premises))``.
    """
    k = len(premises)
    # Build a permutation from the tensor's axis order to [*premises, conclusion]
    target_order = [*premises, conclusion]
    perm = [axes.index(name) for name in target_order]
    t = np.transpose(tensor, perm)
    out: list[float] = []
    for assignment in range(1 << k):
        idx = tuple(((assignment >> bit) & 1) for bit in range(k)) + (1,)
        out.append(float(t[idx]))
    return out


def strategy_cpt(
    s,  # gaia.ir.strategy.Strategy (any subclass)
    strat_by_id,
    strat_params: dict[str, list[float]],
    var_priors: dict[str, float],
    namespace: str,
    package_name: str,
    cache: dict,
) -> tuple[np.ndarray, list[str]]:
    """Compute the effective CPT tensor of a single Gaia IR strategy.

    - Caches by ``s.strategy_id`` (mutates ``cache``).
    - For leaf strategies: builds a mini FactorGraph via the existing
      ``_lower_strategy`` dispatch, converts factors to tensors, contracts
      with the mini fg's variable priors.
    - For CompositeStrategy: recursion — see Task 5.

    ``var_priors`` is consulted by ``_lower_strategy`` for claim variables
    that don't yet exist in the mini fg.  Pass ``{}`` when folding a
    CompositeStrategy in isolation (matches current ``fold_composite_to_cpt``),
    or ``fg.variables`` when computing strategy CPTs for ``compute_coarse_cpts``.
    """
    from gaia.ir.strategy import CompositeStrategy  # local import to avoid cycle

    if s.strategy_id in cache:
        return cache[s.strategy_id]

    if isinstance(s, CompositeStrategy):
        # Implemented in Task 5.
        raise NotImplementedError("CompositeStrategy handling added in Task 5")

    # Leaf: build mini fg via the existing lowering dispatch.
    from gaia.bp.lowering import _lower_strategy  # local import

    mini = FactorGraph()
    ctr = [0]
    claim_ids: set[str] = set()
    _lower_strategy(
        mini,
        s,
        strat_by_id,
        var_priors,
        strat_params,
        expand_formal=True,
        infer_degraded=False,
        ctr=ctr,
        claim_ids=claim_ids,
        namespace=namespace,
        package_name=package_name,
    )

    tensors = [factor_to_tensor(f) for f in mini.factors]
    free = [*s.premises, s.conclusion]
    # Priors for every non-free variable in the mini fg.
    non_free = {v: p for v, p in mini.variables.items() if v not in set(free)}

    cpt_tensor = contract_to_cpt(tensors, free_vars=free, unary_priors=non_free)
    result = (cpt_tensor, free)
    cache[s.strategy_id] = result
    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -x -v`
Expected: all Task 2 + Task 3 tests still pass AND Task 4 leaf tests pass (5 new tests). The composite test for Task 5 doesn't exist yet.

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/contraction.py tests/test_contraction.py
git commit -m "feat(bp): strategy_cpt for leaf strategies + flatten helper

Part of #357. Leaf strategies (INFER, NOISY_AND, FormalStrategy,
auto-formalized named strategies) build a mini FactorGraph via the
existing _lower_strategy dispatch, convert factors to tensors, and
contract with the mini fg's variable priors.  cpt_tensor_to_list
flattens a normalized CPT tensor to the bit-indexed list format.
CompositeStrategy branch deferred to Task 5."
```

---

## Task 5: Recursive `strategy_cpt` for `CompositeStrategy`

**Files:**
- Modify: `gaia/bp/contraction.py`
- Modify: `tests/test_contraction.py`

For a composite, we recurse on each `sub_strategies` entry, collect each sub's CPT tensor, and contract them. The `free_vars` are `[*composite.premises, composite.conclusion]`. Bridge variables = child axes not in `free_vars`; they get unary priors from `var_priors` (default 0.5).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_contraction.py`:

```python
from gaia.ir.strategy import CompositeStrategy


def test_strategy_cpt_composite_single_sub():
    """Composite wrapping a single NOISY_AND sub — CPT should match the sub."""
    sub = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a", "github:t::b"],
        conclusion="github:t::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a", "github:t::b"],
        conclusion="github:t::c",
        sub_strategies=[sub.strategy_id],
    )
    strat_by_id = {sub.strategy_id: sub, comp.strategy_id: comp}
    cpt_tensor, axes = strategy_cpt(
        comp,
        strat_by_id=strat_by_id,
        strat_params={sub.strategy_id: [0.85]},
        var_priors={},
        namespace="",
        package_name="",
        cache={},
    )
    assert axes == ["github:t::a", "github:t::b", "github:t::c"]
    assert cpt_tensor[0, 0, 1] < 0.05
    assert cpt_tensor[1, 0, 1] < 0.05
    assert cpt_tensor[0, 1, 1] < 0.05
    assert cpt_tensor[1, 1, 1] > 0.83


def test_strategy_cpt_composite_chain_with_bridge_var():
    """Chain A → M → C with two sub-strategies bridged by M.

    Matches test_fold_composite_to_cpt_chain but uses strategy_cpt directly.
    """
    sub1 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::m",
    )
    sub2 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::m"],
        conclusion="github:t::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=[sub1.strategy_id, sub2.strategy_id],
    )
    strat_by_id = {
        sub1.strategy_id: sub1,
        sub2.strategy_id: sub2,
        comp.strategy_id: comp,
    }
    cpt_tensor, axes = strategy_cpt(
        comp,
        strat_by_id=strat_by_id,
        strat_params={sub1.strategy_id: [0.9], sub2.strategy_id: [0.8]},
        var_priors={},
        namespace="",
        package_name="",
        cache={},
    )
    assert axes == ["github:t::a", "github:t::c"]
    assert cpt_tensor[0, 1] < 0.1  # A=0 → C≈0
    # A=1 → M≈0.9 → C ≈ 0.9*0.8 + 0.1*ε ≈ 0.72
    assert cpt_tensor[1, 1] > 0.65 and cpt_tensor[1, 1] < 0.80


def test_strategy_cpt_composite_reuses_shared_sub():
    """If two composites share a sub, the cache reuses its tensor."""
    sub = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::m",
    )
    sub2 = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::m"],
        conclusion="github:t::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=[sub.strategy_id, sub2.strategy_id],
    )
    cache: dict = {}
    strategy_cpt(
        comp,
        strat_by_id={
            sub.strategy_id: sub,
            sub2.strategy_id: sub2,
            comp.strategy_id: comp,
        },
        strat_params={sub.strategy_id: [0.9], sub2.strategy_id: [0.8]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    # All three strategy_ids should now be in cache.
    assert sub.strategy_id in cache
    assert sub2.strategy_id in cache
    assert comp.strategy_id in cache
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py::test_strategy_cpt_composite_single_sub -x -v`
Expected: FAIL with `NotImplementedError: CompositeStrategy handling added in Task 5`.

- [ ] **Step 3: Replace the `NotImplementedError` with the recursive composite branch**

In `gaia/bp/contraction.py`, replace:

```python
    if isinstance(s, CompositeStrategy):
        # Implemented in Task 5.
        raise NotImplementedError("CompositeStrategy handling added in Task 5")
```

with:

```python
    if isinstance(s, CompositeStrategy):
        child_tensors: list[tuple[np.ndarray, list[str]]] = []
        for sid in s.sub_strategies:
            sub = strat_by_id.get(sid)
            if sub is None:
                raise KeyError(
                    f"CompositeStrategy {s.strategy_id!r} references missing "
                    f"strategy_id {sid!r}"
                )
            sub_tensor, sub_axes = strategy_cpt(
                sub,
                strat_by_id,
                strat_params,
                var_priors,
                namespace,
                package_name,
                cache,
            )
            child_tensors.append((sub_tensor, sub_axes))

        free = [*s.premises, s.conclusion]
        free_set = set(free)

        # Bridge variables: any child axis that isn't free.  Each needs a
        # unary prior at this layer (default 0.5 if not in var_priors).
        bridges: dict[str, float] = {}
        for _, axes in child_tensors:
            for v in axes:
                if v not in free_set and v not in bridges:
                    bridges[v] = var_priors.get(v, 0.5)

        cpt_tensor = contract_to_cpt(child_tensors, free_vars=free, unary_priors=bridges)
        result = (cpt_tensor, free)
        cache[s.strategy_id] = result
        return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -x -v`
Expected: all tests pass (9 + 5 + 5 + 3 = 22 tests).

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/contraction.py tests/test_contraction.py
git commit -m "feat(bp): recursive strategy_cpt for CompositeStrategy

Part of #357. Recurses on sub_strategies, collects each child's CPT
tensor, contracts them with bridge-variable priors at the composite
layer.  Each variable's unary prior is applied at exactly one layer,
matching the semantics of BP on the current factor graph."
```

---

## Task 6: Rewire `fold_composite_to_cpt` to use `strategy_cpt`

**Files:**
- Modify: `gaia/bp/lowering.py:134-190`
- Existing tests in `tests/test_lowering.py` must continue to pass at their current tolerance

`fold_composite_to_cpt` becomes a thin wrapper: call `strategy_cpt(composite, ..., var_priors={}, ...)` and flatten with `cpt_tensor_to_list`.

- [ ] **Step 1: Inspect the current implementation**

Read `gaia/bp/lowering.py:134-190` to confirm the signature: `fold_composite_to_cpt(s: CompositeStrategy, strat_by_id, strat_params, expand_formal=True) -> list[float]`. The `expand_formal` flag is accepted but must not be removed — it's part of the public API.

- [ ] **Step 2: Replace the body**

In `gaia/bp/lowering.py`, replace the entire body of `fold_composite_to_cpt` (lines 134–190). Keep the signature and docstring, but rewrite the body to:

```python
def fold_composite_to_cpt(
    s: CompositeStrategy,
    strat_by_id: dict[str, Strategy],
    strat_params: dict[str, list[float]],
    expand_formal: bool = True,
) -> list[float]:
    """Compute the effective CPT of a CompositeStrategy via tensor contraction.

    Layer-by-layer variable elimination: each sub-strategy's CPT is computed
    recursively, then child CPTs are contracted along shared (bridge)
    variables.  Exact, no BP iterations.

    Returns a list of 2^k floats (k = number of premises), indexed by the
    binary encoding of the premise assignment (bit 0 = first premise).
    """
    from gaia.bp.contraction import cpt_tensor_to_list, strategy_cpt

    if not expand_formal:
        raise NotImplementedError(
            "fold_composite_to_cpt with expand_formal=False is not supported "
            "by the tensor-contraction path. See "
            "docs/foundations/gaia-ir/07-lowering.md §9."
        )

    cache: dict = {}
    cpt_tensor, axes = strategy_cpt(
        s,
        strat_by_id=strat_by_id,
        strat_params=strat_params,
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    return cpt_tensor_to_list(cpt_tensor, axes, list(s.premises), s.conclusion)
```

- [ ] **Step 3: Run existing lowering tests to verify compatibility**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_lowering.py::test_fold_composite_to_cpt_directly tests/test_lowering.py::test_fold_composite_to_cpt_chain -x -v`
Expected: both pass.

- [ ] **Step 4: Run the full lowering test module**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_lowering.py -x -v`
Expected: all tests in `tests/test_lowering.py` pass. If anything fails, inspect the failure — any actual semantic drift is a bug that needs fixing, not a test tolerance bump.

- [ ] **Step 5: Commit**

```bash
git add gaia/bp/lowering.py
git commit -m "refactor(bp): fold_composite_to_cpt uses tensor contraction

Part of #357. Replaces O(2^k × BP) brute-force loop with a single
recursive strategy_cpt call + cpt_tensor_to_list flatten.  Signature and
docstring preserved; expand_formal=False raises NotImplementedError
(same as before).  Existing tests in tests/test_lowering.py pass
unchanged."
```

---

## Task 7: Rewire `compute_coarse_cpts` to use tensor contraction

**Files:**
- Modify: `gaia/ir/coarsen.py:204-270`

For `compute_coarse_cpts`, the approach is:
1. Lower the canonical graph **once** via `lower_local_graph(canon, node_priors=priors, strategy_conditional_params=strat_params)`.
2. Precompute each IR strategy's effective CPT **once** via `strategy_cpt`, populating a shared cache. Pass `var_priors=fg.variables` so priors propagate correctly.
3. Collect the list of tensors to contract for each coarse strategy: the union of (a) cached strategy CPT tensors, and (b) operator factor tensors (from `fg.factors` — operators are not part of any strategy, they live directly in the factor graph).
4. For each coarse strategy, call `contract_to_cpt` with `free_vars = [*coarse.premises, coarse.conclusion]` and `unary_priors = {v: fg.variables[v] for v in all_relevant_vars if v not in free_vars}`, where `all_relevant_vars` = union of all axis labels across the collected tensors.

Operator factors in the lowered graph come from `canonical.operators`. We need to distinguish them from strategy-generated factors. The simplest way: iterate `canon.operators`, build a tensor for each (via `factor_to_tensor` on a freshly constructed `Factor`), and include those in the contraction alongside the precomputed strategy CPT tensors.

- [ ] **Step 1: Inspect the existing callers**

Read `gaia/cli/commands/_github.py:170-200` and `gaia/cli/commands/_github.py:280-310` to confirm the two callers:
- `compute_coarse_cpts(ir, coarse_for_outline, node_priors=node_priors, strategy_params=sp)` → result is a `dict[int, list[float]]`
- `compute_coarse_cpts(ir, coarse, node_priors=node_priors_for_cpt, strategy_params=strat_params)` → same shape

We must preserve the signature exactly.

- [ ] **Step 2: Replace the body of `compute_coarse_cpts`**

In `gaia/ir/coarsen.py`, replace the entire body of `compute_coarse_cpts` (keep signature and docstring, rewrite the implementation):

```python
def compute_coarse_cpts(
    ir: dict,
    coarse: dict,
    node_priors: dict[str, float] | None = None,
    strategy_params: dict[str, list[float]] | None = None,
    strategy_indices: set[int] | None = None,
) -> dict[int, list[float]]:
    """Compute effective CPTs for coarse infer strategies by tensor contraction.

    For each coarse strategy, contract all relevant factor tensors (precomputed
    IR-strategy CPTs + operator tensors + unary priors on non-free variables).
    Exact — no BP iterations.

    Returns a dict mapping strategy index to CPT (list of 2^k floats).
    """
    from gaia.bp.contraction import (
        contract_to_cpt,
        cpt_tensor_to_list,
        factor_to_tensor,
        strategy_cpt,
    )
    from gaia.bp.factor_graph import Factor, FactorType
    from gaia.bp.lowering import _OPERATOR_MAP, lower_local_graph
    from gaia.ir.graphs import LocalCanonicalGraph

    priors = dict(node_priors or {})
    strat_params = dict(strategy_params or {})
    indices = (
        strategy_indices if strategy_indices is not None else set(range(len(coarse["strategies"])))
    )

    # Build the canonical graph and lower it once.  The lowered fg carries
    # every variable's prior (including any set by `_lower_strategy` for
    # relation-operator conclusions or auto-formalized helper claims).
    canon = LocalCanonicalGraph(
        **{
            key: ir[key]
            for key in ("knowledges", "strategies", "operators", "namespace", "package_name")
        }
    )
    fg = lower_local_graph(
        canon,
        node_priors=priors,
        strategy_conditional_params=strat_params,
    )

    # Build operator tensors directly from canon.operators.  Each operator
    # becomes one factor tensor using the same mapping as lower_local_graph.
    operator_tensors: list[tuple] = []
    for op in canon.operators:
        op_factor = Factor(
            factor_id=f"op_{op.conclusion}",
            factor_type=_OPERATOR_MAP[op.operator],
            variables=list(op.variables),
            conclusion=op.conclusion,
        )
        operator_tensors.append(factor_to_tensor(op_factor))

    # Precompute every IR strategy's effective CPT once, shared cache.
    strat_by_id = {s.strategy_id: s for s in canon.strategies if s.strategy_id}
    cache: dict = {}
    strategy_tensors: list[tuple] = []
    for s in canon.strategies:
        sub_tensor, sub_axes = strategy_cpt(
            s,
            strat_by_id=strat_by_id,
            strat_params=strat_params,
            var_priors=fg.variables,
            namespace=canon.namespace,
            package_name=canon.package_name,
            cache=cache,
        )
        strategy_tensors.append((sub_tensor, sub_axes))

    all_tensors = strategy_tensors + operator_tensors

    # Union of all axis labels touched by any tensor.
    all_axes: set[str] = set()
    for _, axes in all_tensors:
        all_axes.update(axes)

    result: dict[int, list[float]] = {}

    for i, s in enumerate(coarse["strategies"]):
        if i not in indices:
            continue
        coarse_premises = list(s["premises"])
        coarse_conclusion = s["conclusion"]
        free = [*coarse_premises, coarse_conclusion]
        free_set = set(free)

        # Restrict priors to variables that actually appear in some tensor
        # AND are not free.  Variables absorbed inside a strategy CPT
        # (e.g. auto-formalized helper claims) do NOT appear in any tensor's
        # axes and so are correctly skipped.
        unary_priors = {
            v: fg.variables[v]
            for v in all_axes
            if v not in free_set and v in fg.variables
        }

        # If a free var isn't in any tensor (e.g., a coarse premise that
        # doesn't appear anywhere in the graph), contract_to_cpt will add it
        # as a trivial degenerate axis.  That case only happens for
        # pathological inputs and is handled by contract_to_cpt directly.
        cpt_tensor = contract_to_cpt(
            all_tensors,
            free_vars=free,
            unary_priors=unary_priors,
        )
        result[i] = cpt_tensor_to_list(
            cpt_tensor, free, coarse_premises, coarse_conclusion
        )

    return result
```

- [ ] **Step 3: Run the coarsen tests**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/ -k "coarsen or coarse" -x -v`
Expected: all coarse-related tests pass.

- [ ] **Step 4: Run the `_github.py` callers via an integration test**

Find an integration test that exercises `compute_coarse_cpts` through the CLI path:

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/ -k "narrative or outline or github" -x -v`
Expected: all pass.

If no such tests exist, run the full test suite to check for broken downstream behavior:

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/ -x`
Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add gaia/ir/coarsen.py
git commit -m "refactor(ir): compute_coarse_cpts uses tensor contraction

Part of #357. Precomputes each IR strategy's effective CPT once, then
contracts strategy CPTs + operator tensors + unary priors for each
coarse strategy.  Eliminates O(2^k × lower+BP) per coarse strategy.
Signature and return shape preserved."
```

---

## Task 8: Numerical equivalence tests vs `exact_inference`

**Files:**
- Modify: `tests/test_contraction.py`

We verify the tensor-contraction path produces the same marginals as `gaia.bp.exact.exact_inference` on a battery of hand-built factor graphs. `exact_inference` already covers every factor type — we treat it as ground truth and compare `contract_to_cpt` outputs against it.

- [ ] **Step 1: Write the equivalence tests**

Append to `tests/test_contraction.py`:

```python
from gaia.bp.exact import exact_inference


def _run_exact_with_premise_clamps(
    fg: FactorGraph,
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Build the reference CPT via exact_inference with premise clamping.

    Enumerate 2^k premise assignments; for each, clamp the premise priors
    to _HIGH/_LOW and read P(conclusion=1) from exact_inference.
    """
    k = len(premises)
    original_priors = dict(fg.variables)
    cpt: list[float] = []
    try:
        for assignment in range(1 << k):
            for bit, pid in enumerate(premises):
                fg.variables[pid] = _HIGH if (assignment >> bit) & 1 else _LOW
            beliefs, _ = exact_inference(fg)
            cpt.append(beliefs[conclusion])
    finally:
        for v, p in original_priors.items():
            fg.variables[v] = p
    return cpt


def _cpt_via_contraction(
    fg: FactorGraph,
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Build the CPT via factor_to_tensor + contract_to_cpt directly on fg."""
    tensors = [factor_to_tensor(f) for f in fg.factors]
    free = [*premises, conclusion]
    free_set = set(free)
    unary_priors = {v: p for v, p in fg.variables.items() if v not in free_set}
    cpt_tensor = contract_to_cpt(tensors, free_vars=free, unary_priors=unary_priors)
    return cpt_tensor_to_list(cpt_tensor, free, premises, conclusion)


def test_equivalence_single_implication():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A"], "B")
    ref = _run_exact_with_premise_clamps(fg, ["A"], "B")
    ours = _cpt_via_contraction(fg, ["A"], "B")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_conjunction_plus_soft_entailment():
    """NOISY_AND-like structure: CONJ(A,B) → M, SE(M → C)."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("M", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.CONJUNCTION, ["A", "B"], "M")
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.85, p2=1.0 - CROMWELL_EPS)
    ref = _run_exact_with_premise_clamps(fg, ["A", "B"], "C")
    ours = _cpt_via_contraction(fg, ["A", "B"], "C")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_conditional_factor():
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor(
        "f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=[0.1, 0.4, 0.6, 0.95]
    )
    ref = _run_exact_with_premise_clamps(fg, ["A", "B"], "C")
    ours = _cpt_via_contraction(fg, ["A", "B"], "C")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_relation_operator_equivalence():
    """EQUIVALENCE relation with 1-ε assertion prior on helper."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("H", 1.0 - CROMWELL_EPS)  # assert "A == B"
    fg.add_factor("f1", FactorType.EQUIVALENCE, ["A", "B"], "H")
    # Query: P(B | A) under the assertion H=1
    ref = _run_exact_with_premise_clamps(fg, ["A"], "B")
    ours = _cpt_via_contraction(fg, ["A"], "B")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_chain_with_nonuniform_intermediate_prior():
    """Non-default prior on intermediate must be honored."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("M", 0.3)  # non-default
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "M", p1=0.9, p2=0.95)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.8, p2=0.95)
    ref = _run_exact_with_premise_clamps(fg, ["A"], "C")
    ours = _cpt_via_contraction(fg, ["A"], "C")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_disjunction_and_contradiction():
    """Two relation operators and a disjunction in a small graph."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("B", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_variable("D_OR", 1.0 - CROMWELL_EPS)
    fg.add_variable("H_NOT", 1.0 - CROMWELL_EPS)
    fg.add_factor("fd", FactorType.DISJUNCTION, ["A", "B"], "D_OR")
    fg.add_factor("fn", FactorType.CONTRADICTION, ["A", "B"], "H_NOT")
    fg.add_factor("fse", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.7, p2=0.9)
    ref = _run_exact_with_premise_clamps(fg, ["A", "B"], "C")
    ours = _cpt_via_contraction(fg, ["A", "B"], "C")
    np.testing.assert_allclose(ours, ref, atol=1e-6)
```

- [ ] **Step 2: Run the equivalence tests**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/test_contraction.py -k equivalence -x -v`
Expected: all 6 equivalence tests pass. Any failure means the tensor path diverges from `exact_inference` — investigate (usually: missing unary prior, wrong axis order, or normalization bug).

- [ ] **Step 3: Run the complete test suite**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/ -x`
Expected: every test passes. If Neo4j tests skip, that's fine.

- [ ] **Step 4: Commit**

```bash
git add tests/test_contraction.py
git commit -m "test(bp): equivalence tests vs exact_inference

Part of #357. Six new tests verify factor_to_tensor + contract_to_cpt
produce marginals matching gaia.bp.exact.exact_inference at 1e-6
tolerance for IMPLICATION, CONJ+SE, CONDITIONAL, EQUIVALENCE assertion,
non-uniform intermediate priors, and DISJ+CONTRADICTION+SE combos."
```

---

## Task 9: Lint, format, push, open PR, verify CI

**Files:**
- All modified files

- [ ] **Step 1: Run ruff lint**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run ruff check .`
Expected: no errors. If any, fix inline.

- [ ] **Step 2: Run ruff format check**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run ruff format --check .`
Expected: no errors. If files need formatting, run `uv run ruff format .` and commit the changes.

- [ ] **Step 3: Run the full test suite one more time**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && uv run pytest tests/`
Expected: all tests pass.

- [ ] **Step 4: Push the branch**

Run: `cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor && git push -u origin feature/cpt-tensor-contraction`
Expected: branch created on origin.

- [ ] **Step 5: Open the PR**

Run:

```bash
cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor
gh pr create --title "feat(bp): compute CPTs via tensor contraction (#357)" --body "$(cat <<'EOF'
## Summary
- New `gaia/bp/contraction.py` module with `factor_to_tensor`, `contract_to_cpt`, and recursive `strategy_cpt`.
- `fold_composite_to_cpt` and `compute_coarse_cpts` rewired to use tensor contraction — O(2^k × BP) → single einsum per contraction.
- Layer-by-layer: each `CompositeStrategy` level contracts child CPT tensors along bridge variables; each variable's unary prior is applied exactly once.
- Six equivalence tests vs `gaia.bp.exact.exact_inference` at 1e-6 tolerance.

Closes #357.

## Test plan
- [ ] `pytest tests/test_contraction.py -v` — all 28 new tests pass
- [ ] `pytest tests/test_lowering.py -v` — existing fold tests still pass (numerical equivalence)
- [ ] `pytest tests/ -k "coarsen or narrative or outline or github"` — downstream callers OK
- [ ] `pytest tests/` — full suite green
- [ ] CI green on GitHub

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

Expected: PR URL printed.

- [ ] **Step 6: Check CI**

Run (wait a few seconds first — push → CI pickup):

```bash
cd /Users/kunchen/project/Gaia/.worktrees/cpt-tensor
gh run list --branch feature/cpt-tensor-contraction --limit 1
```

If CI is still running, wait and re-run. If CI fails:

```bash
gh run view <run-id> --log-failed
```

Fix the issue, commit, push, re-check.

- [ ] **Step 7: Report PR URL to the user and stop**

Do not merge the PR. The user will review and merge.

---

## Self-Review Checklist (ran before saving)

1. **Spec coverage (issue #357):**
   - ✅ Replace `fold_composite_to_cpt` with tensor contraction → Task 6
   - ✅ Replace `compute_coarse_cpts` with tensor contraction → Task 7
   - ✅ Per-factor CPT tensors (all 8 factor types) → Task 2
   - ✅ Marginalize intermediate variables via contraction → Task 3 + Task 5
   - ✅ Composable / naturally recursive → Task 5 (CompositeStrategy branch)
   - ✅ Exact (no BP approximation) → Task 8 equivalence vs exact_inference

2. **Placeholder scan:** No "TBD", "TODO", "similar to", or "add error handling" placeholders. Every code block is complete.

3. **Type consistency:**
   - `factor_to_tensor` signature: `(Factor) -> tuple[np.ndarray, list[str]]` — used consistently in Tasks 3, 4, 5, 7, 8.
   - `contract_to_cpt` signature: `(list[tuple[np.ndarray, list[str]]], list[str], dict[str, float]) -> np.ndarray` — used consistently.
   - `strategy_cpt` signature: `(s, strat_by_id, strat_params, var_priors, namespace, package_name, cache) -> tuple[np.ndarray, list[str]]` — same across Tasks 4, 5, 6, 7.
   - `cpt_tensor_to_list` signature: `(tensor, axes, premises, conclusion) -> list[float]` — consistent.
   - Cache is `dict` (untyped value) to hold tuples; acceptable for internal use.

4. **Invariants verified:**
   - Unary prior applied once per variable (at the layer where it's marginalized): Task 5's bridge-prior logic + Task 7's `all_axes`-based prior selection ensure non-double-counting.
   - Cromwell constants (_HIGH/_LOW) imported from factor_graph.py — single source of truth.
   - Bit ordering matches existing `fold_composite_to_cpt` convention (Task 4's `cpt_tensor_to_list` test `test_cpt_tensor_to_list_bit_ordering`).
   - Einsum list form — Task 3's `test_contract_to_cpt_many_variables` explicitly tests >52 variables.
