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
from gaia.bp.exact import _factor_log_potentials
from gaia.bp.factor_graph import CROMWELL_EPS, Factor, FactorGraph, FactorType
from gaia.ir.strategy import CompositeStrategy, Strategy

_HIGH = 1.0 - CROMWELL_EPS
_LOW = CROMWELL_EPS


def _almost(a, b, eps=1e-9):
    return abs(a - b) < eps


def test_factor_to_tensor_implication():
    f = Factor(
        factor_id="f1",
        factor_type=FactorType.IMPLICATION,
        variables=["A", "B"],
        conclusion="H",
    )
    t, axes = factor_to_tensor(f)
    assert axes == ["A", "B", "H"]
    assert t.shape == (2, 2, 2)
    # H=1 (implication holds): A=1,B=0 forbidden, rest HIGH
    assert _almost(t[1, 0, 1], _LOW)
    assert _almost(t[0, 0, 1], _HIGH)
    assert _almost(t[0, 1, 1], _HIGH)
    assert _almost(t[1, 1, 1], _HIGH)
    # H=0 (implication fails): A=1,B=0 is HIGH, rest LOW
    assert _almost(t[1, 0, 0], _HIGH)
    assert _almost(t[0, 0, 0], _LOW)
    assert _almost(t[0, 1, 0], _LOW)
    assert _almost(t[1, 1, 0], _LOW)


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

    Uses a chain of 60 variables connected by IMPLICATION factors with helpers.
    We just need the contraction to run without alphabet exhaustion.
    """
    import numpy as _np  # local alias to avoid clashing with module-level np

    n = 60
    var_names = [f"v{i}" for i in range(n)]
    helper_names = [f"h{i}" for i in range(n - 1)]
    factors = []
    for i in range(n - 1):
        f = Factor(
            factor_id=f"f{i}",
            factor_type=FactorType.IMPLICATION,
            variables=[var_names[i], var_names[i + 1]],
            conclusion=helper_names[i],
        )
        factors.append(factor_to_tensor(f))
    # Priors for internal variables (not the first and last main vars) and all helpers
    priors = {v: 0.5 for v in var_names[1:-1]}
    priors.update({h: _HIGH for h in helper_names})
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

    Matches test_fold_composite_to_cpt_chain in tests/test_lowering.py but
    exercises strategy_cpt directly.
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


def test_strategy_cpt_composite_populates_cache_for_subs():
    """After folding a composite, all sub-strategies are in the cache,
    and re-calling strategy_cpt on a sub returns the cached tensor object."""
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
    cache: dict = {}
    strategy_cpt(
        comp,
        strat_by_id=strat_by_id,
        strat_params={sub1.strategy_id: [0.9], sub2.strategy_id: [0.8]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    assert sub1.strategy_id in cache
    assert sub2.strategy_id in cache
    assert comp.strategy_id in cache

    # Object identity on re-call: second invocation returns the cached tuple.
    cached_sub1 = cache[sub1.strategy_id]
    t2, a2 = strategy_cpt(
        sub1,
        strat_by_id=strat_by_id,
        strat_params={sub1.strategy_id: [0.9], sub2.strategy_id: [0.8]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    assert t2 is cached_sub1[0]
    assert a2 is cached_sub1[1]


def test_strategy_cpt_composite_missing_sub_raises():
    """If a sub_strategy_id is not in strat_by_id, raise KeyError."""
    comp = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=["lcs_does_not_exist"],
    )
    with pytest.raises(KeyError, match="references missing strategy_id"):
        strategy_cpt(
            comp,
            strat_by_id={comp.strategy_id: comp},
            strat_params={},
            var_priors={},
            namespace="",
            package_name="",
            cache={},
        )


def test_strategy_cpt_nested_composite():
    """Composite containing a composite: C_outer wraps C_inner wraps leaf.

    Verifies recursion handles at least two layers of nesting and that
    all strategy_ids are cached correctly.
    """
    leaf = Strategy(
        scope="local",
        type="noisy_and",
        premises=["github:t::a"],
        conclusion="github:t::c",
    )
    inner = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=[leaf.strategy_id],
    )
    outer = CompositeStrategy(
        scope="local",
        type="infer",
        premises=["github:t::a"],
        conclusion="github:t::c",
        sub_strategies=[inner.strategy_id],
    )
    cache: dict = {}
    cpt_tensor, axes = strategy_cpt(
        outer,
        strat_by_id={
            leaf.strategy_id: leaf,
            inner.strategy_id: inner,
            outer.strategy_id: outer,
        },
        strat_params={leaf.strategy_id: [0.85]},
        var_priors={},
        namespace="",
        package_name="",
        cache=cache,
    )
    assert axes == ["github:t::a", "github:t::c"]
    # P(C=1|A=1) ≈ 0.85 (unchanged by pass-through composites)
    assert cpt_tensor[1, 1] > 0.83
    assert cpt_tensor[0, 1] < 0.05
    # All three levels cached
    assert leaf.strategy_id in cache
    assert inner.strategy_id in cache
    assert outer.strategy_id in cache


def test_strategy_cpt_cycle_detection():
    """A composite that references itself (via a manually forged strategy_id)
    must raise ValueError instead of looping forever."""
    # Build a composite that references itself by reusing the same strategy_id
    # in its sub_strategies.  Since _compute_strategy_id is content-addressed,
    # the default auto-computed ID cannot be self-referential.  We construct
    # the composite with sub_strategies=[] first (to get a valid auto-ID),
    # then patch sub_strategies in place to include that ID — simulating a
    # malformed IR bypass.
    leaf = Strategy(
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
        sub_strategies=[leaf.strategy_id],
    )
    # Inject the cycle: comp now references itself in addition to leaf.
    comp.sub_strategies = [leaf.strategy_id, comp.strategy_id]
    with pytest.raises(ValueError, match="cycle detected"):
        strategy_cpt(
            comp,
            strat_by_id={leaf.strategy_id: leaf, comp.strategy_id: comp},
            strat_params={leaf.strategy_id: [0.9]},
            var_priors={},
            namespace="",
            package_name="",
            cache={},
        )


# ---------------------------------------------------------------------------
# Equivalence tests: tensor contraction vs exact_inference ground truth
# ---------------------------------------------------------------------------


def _run_exact_with_premise_clamps(
    fg: FactorGraph,
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Reference CPT via brute-force exact conditional marginalization.

    Enumerates all 2^n joint states once, using the un-clamped priors in
    ``fg.variables``.  For each of the 2^k premise assignments, filters the
    joint to states consistent with that assignment and reads
    P(conclusion=1 | premises=assignment) by summing the filtered joint.

    This computes the TRUE conditional — the same quantity that
    ``contract_to_cpt`` computes via variable elimination — so both methods
    are guaranteed to agree within floating-point tolerance on any factor
    graph whose potentials are finite and whose joint is not zero.
    """
    var_ids = sorted(fg.variables.keys())
    n = len(var_ids)
    var_idx = {v: i for i, v in enumerate(var_ids)}
    priors = np.array([fg.variables[v] for v in var_ids], dtype=np.float64)

    N = 1 << n
    arange = np.arange(N, dtype=np.int64)
    states = np.empty((N, n), dtype=np.int8)
    for i in range(n):
        states[:, i] = (arange >> i) & 1

    # Log-joint under the un-clamped priors + all factors
    log_p1 = np.log(np.clip(priors, 1e-300, None))
    log_p0 = np.log(np.clip(1.0 - priors, 1e-300, None))
    log_j = (states * log_p1 + (1 - states) * log_p0).sum(axis=1)

    for fac in fg.factors:
        log_j += _factor_log_potentials(fac, states, var_idx)

    joint = np.exp(log_j - log_j.max())  # numerically stable unnormalized joint

    k = len(premises)
    prem_idxs = [var_idx[p] for p in premises]
    concl_idx = var_idx[conclusion]
    cpt: list[float] = []
    for assignment in range(1 << k):
        # Build a boolean mask for all states consistent with this premise assignment
        mask = np.ones(N, dtype=bool)
        for bit, pidx in enumerate(prem_idxs):
            val = (assignment >> bit) & 1
            mask &= states[:, pidx] == val
        w = joint[mask]
        w_concl1 = joint[mask & (states[:, concl_idx] == 1)]
        cpt.append(float(w_concl1.sum() / w.sum()))
    return cpt


def _cpt_via_contraction(
    fg: FactorGraph,
    premises: list[str],
    conclusion: str,
) -> list[float]:
    """Tensor-contraction CPT: all factors in fg, premises free, others priored."""
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
    fg.add_variable("H", 1.0 - CROMWELL_EPS)
    fg.add_factor("f1", FactorType.IMPLICATION, ["A", "B"], "H")
    ref = _run_exact_with_premise_clamps(fg, ["A"], "B")
    ours = _cpt_via_contraction(fg, ["A"], "B")
    np.testing.assert_allclose(ours, ref, atol=1e-6)


def test_equivalence_conjunction_plus_soft_entailment():
    """NOISY_AND-like: CONJ(A,B) → M, SE(M → C)."""
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
    fg.add_factor("f1", FactorType.CONDITIONAL, ["A", "B"], "C", cpt=[0.1, 0.4, 0.6, 0.95])
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
    """Two relation operators and a soft entailment in a small graph."""
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


# ---------------------------------------------------------------------------
# Regression tests for Codex review fixes (#361)
# ---------------------------------------------------------------------------


def test_compute_coarse_cpts_skips_composite_strategies():
    """Regression for Codex P1: compute_coarse_cpts must NOT add a composite
    CPT as a separate factor, because the composite is just an organizational
    wrapper around its sub-strategies.  Including it double-counts every path
    through the composite.

    We build a minimal IR dict with one leaf noisy_and and one composite that
    wraps it, then call compute_coarse_cpts and compare the coarse CPT to the
    CPT we'd get from the leaf alone.
    """
    from gaia.ir.coarsen import compute_coarse_cpts, coarsen_ir

    leaf = Strategy(
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
        sub_strategies=[leaf.strategy_id],
    )

    ir = {
        "knowledges": [
            {"id": "github:t::a", "label": "a", "type": "claim", "content": "a"},
            {"id": "github:t::b", "label": "b", "type": "claim", "content": "b"},
            {"id": "github:t::c", "label": "c", "type": "claim", "content": "c"},
        ],
        "strategies": [
            leaf.model_dump(mode="json"),
            comp.model_dump(mode="json"),
        ],
        "operators": [],
        "namespace": "github",
        "package_name": "t",
    }

    exported = {"github:t::c"}
    coarse = coarsen_ir(ir, exported)

    cpts = compute_coarse_cpts(
        ir,
        coarse,
        node_priors={"github:t::a": 0.5, "github:t::b": 0.5, "github:t::c": 0.5},
        strategy_params={leaf.strategy_id: [0.85]},
    )

    # There should be at least one coarse strategy.
    assert len(cpts) >= 1
    # For any returned CPT: if composites were double-counted, the "both
    # premises on" probability would get squared-ish and drift away from
    # the expected single-noisy_and value of ~0.85.  With the fix, it
    # should stay close to 0.85.
    # Find the CPT for the coarse strategy whose premises are {a, b}.
    for idx, cpt in cpts.items():
        coarse_strat = coarse["strategies"][idx]
        if set(coarse_strat["premises"]) == {"github:t::a", "github:t::b"}:
            # cpt is 2^2 = 4 floats.  Index 3 (both=1) should be ≈ 0.85.
            assert 0.80 < cpt[3] < 0.90, (
                f"Composite double-counted: cpt[3]={cpt[3]} (expected ~0.85)"
            )
            break
    else:
        pytest.fail("No coarse strategy with premises {a, b} found")


def test_contract_to_cpt_deep_chain_no_underflow():
    """Regression for Codex P2: contract_to_cpt must handle deep chains of
    Cromwell-low factors without the intermediate joint underflowing to 0.

    Builds a 150-factor IMPLICATION chain.  Each IMPLICATION factor has one
    cell at _LOW = 1e-3, so naively multiplying 150 of them would push a
    particular slice below float64 normal range (~1e-450), triggering a
    false 'zero partition function' error.  With per-step rescaling, the
    intermediate stays bounded and the final CPT is computable.
    """
    n = 150
    var_names = [f"v{i}" for i in range(n)]
    helper_names = [f"h{i}" for i in range(n - 1)]
    factors = []
    for i in range(n - 1):
        f = Factor(
            factor_id=f"f{i}",
            factor_type=FactorType.IMPLICATION,
            variables=[var_names[i], var_names[i + 1]],
            conclusion=helper_names[i],
        )
        factors.append(factor_to_tensor(f))
    priors = {v: 0.5 for v in var_names[1:-1]}
    priors.update({h: _HIGH for h in helper_names})
    # Should NOT raise, and should produce a valid CPT.
    cpt = contract_to_cpt(factors, free_vars=[var_names[0], var_names[-1]], unary_priors=priors)
    assert cpt.shape == (2, 2)
    assert np.all(np.isfinite(cpt))
    # Each row should sum to 1 (conclusion normalization).
    np.testing.assert_allclose(cpt.sum(axis=-1), np.ones(2), atol=1e-9)


def test_contract_to_cpt_allows_degenerate_free_var():
    """Regression for Codex P2 (the third finding): a free variable that
    doesn't appear in any input tensor must be handled gracefully as a
    constant axis (uniform along that axis), not rejected with ValueError.

    This happens for CompositeStrategy with interface premises that no
    sub-strategy actually touches.
    """
    fg = FactorGraph()
    fg.add_variable("A", 0.5)
    fg.add_variable("C", 0.5)
    fg.add_factor("f1", FactorType.SOFT_ENTAILMENT, ["A"], "C", p1=0.8, p2=0.9)
    t, axes = factor_to_tensor(fg.factors[0])
    # "B" is a "free var" but does not appear in any tensor.
    cpt = contract_to_cpt(
        [(t, axes)],
        free_vars=["A", "B", "C"],  # B is the degenerate axis
        unary_priors={},
    )
    assert cpt.shape == (2, 2, 2)
    # CPT should be CONSTANT along the B axis (same value for B=0 and B=1).
    np.testing.assert_allclose(cpt[:, 0, :], cpt[:, 1, :], atol=1e-9)
    # And P(C=1|A=1, B=any) should still be ≈ 0.8
    assert _almost(cpt[1, 0, 1], 0.8, eps=5e-3)
    assert _almost(cpt[1, 1, 1], 0.8, eps=5e-3)


# ── coarsen_ir: surrogate leaf premises for induction cycles ──


def test_coarsen_ir_induction_cycle_promotes_surrogate_leaves():
    """Regression: induction creates cycles (law → obs via support, obs₁+obs₂ → law
    via induction composite), making every node 'concluded'. Exported conclusions
    reachable only through such cycles must still appear in the coarse graph via
    surrogate leaf premises."""
    from gaia.ir.coarsen import coarsen_ir

    # Minimal induction pattern:
    #   law → (support) → obs1
    #   law → (support) → obs2
    #   obs1, obs2 → (induction sub-strat) → law
    #   law is exported
    ir = {
        "knowledges": [
            {"id": "ns::law", "label": "law", "type": "claim", "content": "law"},
            {"id": "ns::obs1", "label": "obs1", "type": "claim", "content": "obs1"},
            {"id": "ns::obs2", "label": "obs2", "type": "claim", "content": "obs2"},
        ],
        "strategies": [
            {
                "type": "support",
                "premises": ["ns::law"],
                "conclusion": "ns::obs1",
                "reason": "",
            },
            {
                "type": "support",
                "premises": ["ns::law"],
                "conclusion": "ns::obs2",
                "reason": "",
            },
            {
                "type": "infer",
                "premises": ["ns::obs1", "ns::obs2"],
                "conclusion": "ns::law",
                "reason": "",
            },
        ],
        "operators": [],
        "namespace": "ns",
        "package_name": "pkg",
    }
    exported = {"ns::law"}
    coarse = coarsen_ir(ir, exported)

    # law should be in the coarse graph (exported)
    coarse_ids = {k["id"] for k in coarse["knowledges"]}
    assert "ns::law" in coarse_ids

    # At least one surrogate leaf should connect to law
    assert len(coarse["strategies"]) >= 1
    for s in coarse["strategies"]:
        if s["conclusion"] == "ns::law":
            # Premises should be the cycle-broken observations
            assert len(s["premises"]) > 0
            break
    else:
        pytest.fail("No coarse strategy concluding to ns::law found")


def test_coarsen_ir_induction_to_downstream_export():
    """Regression: an exported conclusion supported by an induction law (which is
    itself in a cycle) should also be reachable via the surrogate leaves."""
    from gaia.ir.coarsen import coarsen_ir

    # law → obs1, law → obs2 (support)
    # obs1 + obs2 → law (induction)
    # law → export (support)
    ir = {
        "knowledges": [
            {"id": "ns::law", "label": "law", "type": "claim", "content": "law"},
            {"id": "ns::obs1", "label": "obs1", "type": "claim", "content": "obs1"},
            {"id": "ns::obs2", "label": "obs2", "type": "claim", "content": "obs2"},
            {"id": "ns::export", "label": "export", "type": "claim", "content": "export"},
        ],
        "strategies": [
            {"type": "support", "premises": ["ns::law"], "conclusion": "ns::obs1", "reason": ""},
            {"type": "support", "premises": ["ns::law"], "conclusion": "ns::obs2", "reason": ""},
            {
                "type": "infer",
                "premises": ["ns::obs1", "ns::obs2"],
                "conclusion": "ns::law",
                "reason": "",
            },
            {"type": "support", "premises": ["ns::law"], "conclusion": "ns::export", "reason": ""},
        ],
        "operators": [],
        "namespace": "ns",
        "package_name": "pkg",
    }
    exported = {"ns::export"}
    coarse = coarsen_ir(ir, exported)

    coarse_ids = {k["id"] for k in coarse["knowledges"]}
    assert "ns::export" in coarse_ids
    # The export should have at least one strategy connecting to it
    export_strats = [s for s in coarse["strategies"] if s["conclusion"] == "ns::export"]
    assert len(export_strats) >= 1


def test_coarsen_ir_mixed_leaf_and_cycle():
    """A graph with both normal leaf premises and induction cycles — the normal
    leaf path should still work, and the cycle path should also produce edges."""
    from gaia.ir.coarsen import coarsen_ir

    ir = {
        "knowledges": [
            {"id": "ns::leaf", "label": "leaf", "type": "claim", "content": "leaf"},
            {"id": "ns::law", "label": "law", "type": "claim", "content": "law"},
            {"id": "ns::obs", "label": "obs", "type": "claim", "content": "obs"},
            {"id": "ns::core", "label": "core", "type": "claim", "content": "core"},
            {"id": "ns::derived", "label": "derived", "type": "claim", "content": "derived"},
        ],
        "strategies": [
            # Normal path: leaf → core
            {"type": "support", "premises": ["ns::leaf"], "conclusion": "ns::core", "reason": ""},
            # Induction cycle: law ↔ obs
            {"type": "support", "premises": ["ns::law"], "conclusion": "ns::obs", "reason": ""},
            {"type": "infer", "premises": ["ns::obs"], "conclusion": "ns::law", "reason": ""},
            # law also feeds into derived (exported)
            {"type": "support", "premises": ["ns::law"], "conclusion": "ns::derived", "reason": ""},
        ],
        "operators": [],
        "namespace": "ns",
        "package_name": "pkg",
    }
    exported = {"ns::core", "ns::derived"}
    coarse = coarsen_ir(ir, exported)

    coarse_ids = {k["id"] for k in coarse["knowledges"]}
    # Both exports should be present
    assert "ns::core" in coarse_ids
    assert "ns::derived" in coarse_ids
    # leaf should connect to core
    core_strats = [s for s in coarse["strategies"] if s["conclusion"] == "ns::core"]
    assert any("ns::leaf" in s["premises"] for s in core_strats)
    # derived should have surrogate leaf connections
    derived_strats = [s for s in coarse["strategies"] if s["conclusion"] == "ns::derived"]
    assert len(derived_strats) >= 1


def test_compute_coarse_cpts_with_helper_claims():
    """Regression: compute_coarse_cpts needs priors for ALL variables including
    helper claims (__implication_result_*, etc.). If helper priors are missing,
    tensor contraction fails. This test verifies that passing complete priors
    (with helper claims at 1-ε) produces valid CPTs."""
    from gaia.ir.coarsen import compute_coarse_cpts, coarsen_ir

    # Build a support strategy (which auto-formalizes to conjunction + implication
    # with helper claims like __implication_result_*, __conjunction_result_*)
    s = Strategy(
        scope="local",
        type="support",
        premises=["github:t::a"],
        conclusion="github:t::b",
        metadata={"prior": 0.85},
    )
    ir = {
        "knowledges": [
            {"id": "github:t::a", "label": "a", "type": "claim", "content": "a"},
            {"id": "github:t::b", "label": "b", "type": "claim", "content": "b"},
        ],
        "strategies": [s.model_dump(mode="json")],
        "operators": [],
        "namespace": "github",
        "package_name": "t",
    }

    # Compile to get the full IR with helper claims
    from gaia.ir.graphs import LocalCanonicalGraph

    canon = LocalCanonicalGraph(
        **{
            key: ir[key]
            for key in ("knowledges", "strategies", "operators", "namespace", "package_name")
        }
    )
    # After compilation, helpers are generated. Build a full IR dict from canon.
    full_ir = {
        "knowledges": [k.model_dump(mode="json") for k in canon.knowledges],
        "strategies": [s.model_dump(mode="json") for s in canon.strategies],
        "operators": [o.model_dump(mode="json") for o in canon.operators],
        "namespace": canon.namespace,
        "package_name": canon.package_name,
    }

    exported = {"github:t::b"}
    coarse = coarsen_ir(full_ir, exported)

    # Build priors covering ALL knowledges (including helpers)
    _EPS = 1e-3
    node_priors: dict[str, float] = {}
    for k in full_ir["knowledges"]:
        kid = k["id"]
        meta = k.get("metadata") or {}
        helper_kind = meta.get("helper_kind", "")
        if helper_kind in (
            "implication_result",
            "equivalence_result",
            "contradiction_result",
            "complement_result",
        ):
            node_priors[kid] = 1.0 - _EPS
        else:
            node_priors[kid] = 0.5
    node_priors["github:t::a"] = 0.8

    cpts = compute_coarse_cpts(full_ir, coarse, node_priors=node_priors)

    # Should produce at least one CPT (not fail silently)
    assert len(cpts) > 0
    # The CPT for b given a should reflect the support prior
    for idx, cpt in cpts.items():
        if coarse["strategies"][idx]["conclusion"] == "github:t::b":
            assert len(cpt) == 2  # 2^1 for single premise
            # P(b=1|a=1) should be close to the support prior (0.85)
            assert cpt[1] > 0.5, f"CPT[a=1] = {cpt[1]}, expected > 0.5"
            break
    else:
        pytest.fail("No coarse CPT for conclusion b found")
