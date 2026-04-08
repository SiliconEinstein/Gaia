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
from gaia.ir.strategy import Strategy

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


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


def test_factor_to_tensor_soft_entailment_missing_params_raises():
    # Construct a raw Factor (bypass FactorGraph validation)
    f = Factor(
        factor_id="fse",
        factor_type=FactorType.SOFT_ENTAILMENT,
        variables=["A"],
        conclusion="C",
        p1=None,
        p2=None,
    )
    with pytest.raises(ValueError, match="missing p1/p2"):
        factor_to_tensor(f)


def test_factor_to_tensor_conditional_missing_cpt_raises():
    f = Factor(
        factor_id="fc",
        factor_type=FactorType.CONDITIONAL,
        variables=["A", "B"],
        conclusion="C",
        cpt=None,
    )
    with pytest.raises(ValueError, match="missing cpt"):
        factor_to_tensor(f)


def test_factor_to_tensor_conditional_wrong_length_raises():
    f = Factor(
        factor_id="fc",
        factor_type=FactorType.CONDITIONAL,
        variables=["A", "B"],
        conclusion="C",
        cpt=(0.1, 0.2),  # wrong length: 2 instead of 2^2=4
    )
    with pytest.raises(ValueError, match="cpt length 2 != 2\\^k=4"):
        factor_to_tensor(f)


def test_factor_to_tensor_unknown_factor_type_raises():
    class _FakeFt:
        name = "FAKE"

    f = Factor(
        factor_id="fbogus",
        factor_type=_FakeFt(),  # type: ignore[arg-type]
        variables=["A"],
        conclusion="B",
    )
    with pytest.raises(ValueError, match="Unknown FactorType"):
        factor_to_tensor(f)


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
    fg.add_factor("f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=[0.1, 0.3, 0.7, 0.95])
    t, axes = factor_to_tensor(fg.factors[0])
    cpt = contract_to_cpt([(t, axes)], free_vars=["A", "B", "C"], unary_priors={})
    # Sum over conclusion axis for every (A,B) assignment == 1
    sums = cpt.sum(axis=-1)
    np.testing.assert_allclose(sums, np.ones((2, 2)), atol=1e-9)


def test_contract_to_cpt_empty_free_vars_raises():
    """If free_vars is empty we cannot produce a CPT — raise."""
    with pytest.raises(ValueError, match="free_vars must be non-empty"):
        contract_to_cpt([], free_vars=[], unary_priors={})


def test_contract_to_cpt_missing_prior_raises():
    """Non-free variable without a prior should raise with a descriptive message."""
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("M", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "M", p1=0.9, p2=1.0 - CROMWELL_EPS)
    fg.add_factor("f2", FactorType.SOFT_ENTAILMENT, ["M"], "C", p1=0.8, p2=1.0 - CROMWELL_EPS)
    tensors = [factor_to_tensor(f) for f in fg.factors]
    with pytest.raises(ValueError, match="unary prior missing"):
        contract_to_cpt(
            tensors,
            free_vars=["A", "C"],
            unary_priors={},  # missing M
        )


def test_contract_to_cpt_many_variables():
    """Ensure einsum list form handles more than 52 variables.

    Uses a chain of 60 variables connected by IMPLICATION factors.  We just
    need the contraction to run without alphabet exhaustion.
    """
    import numpy as _np  # local alias to avoid clashing with module-level np

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
    cpt = contract_to_cpt(factors, free_vars=[var_names[0], var_names[-1]], unary_priors=priors)
    assert cpt.shape == (2, 2)
    assert _np.all(_np.isfinite(cpt))


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
    # Cromwell-clamped values may differ from exact input by a few ε.
    assert _almost(cpt_tensor[0, 0, 1], 0.1, eps=5e-3)
    assert _almost(cpt_tensor[1, 0, 1], 0.3, eps=5e-3)
    assert _almost(cpt_tensor[0, 1, 1], 0.7, eps=5e-3)
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
    assert cpt_tensor[0, 0, 1] < 0.05
    assert cpt_tensor[1, 0, 1] < 0.05
    assert cpt_tensor[0, 1, 1] < 0.05
    assert cpt_tensor[1, 1, 1] > 0.83


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
    # Same tensor object returned from cache.
    assert t1 is t2
    assert a1 == a2


def test_strategy_cpt_composite_raises_not_implemented_yet():
    """Task 5 will fill this in; Task 4 only handles leaves."""
    from gaia.ir.strategy import CompositeStrategy

    sub = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::c",
    )
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=[sub.strategy_id],
    )
    with pytest.raises(NotImplementedError, match="Task 5"):
        strategy_cpt(
            comp,
            strat_by_id={sub.strategy_id: sub, comp.strategy_id: comp},
            strat_params={sub.strategy_id: [0.9]},
            var_priors={},
            namespace="",
            package_name="",
            cache={},
        )


def test_cpt_tensor_to_list_bit_ordering():
    """Bit ordering: bit 0 = first premise."""
    t = np.zeros((2, 2, 2))
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
    # index = (A << 0) | (B << 1)
    assert cpt_list == [0.11, 0.22, 0.33, 0.44]
