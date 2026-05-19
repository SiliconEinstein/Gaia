# Bayes Model Observable Unit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace PR #657's `predict(target=Variable | Distribution)` surface with `model(observable=Variable)`, while preserving Gaia's unit safety through a new `Variable.unit` contract.

**Architecture:** Keep Bayes as an extension module with `BayesInference(Reasoning)` records, but rename the model-declaration record to `Model`. `Variable` becomes the sole observable identity for Bayes models, and Gaia's existing `gaia.unit` facade is used to canonicalize and validate unit-bearing observables and observations.

**Tech Stack:** Python 3.12, dataclasses, Gaia Lang runtime, Gaia unit facade (`gaia.unit.q`, `Quantity`, `ureg`, `QuantityLiteral`), pytest, ruff, mypy.

---

## File Structure

- Modify `gaia/unit.py`: add a tiny `canonical_unit()` helper shared by `Variable`, observe validation, and tests.
- Modify `gaia/engine/lang/runtime/variable.py`: add `unit: str | None`, canonicalization, and default content rendering.
- Modify `gaia/engine/lang/compiler/compile.py`: include `unit` when serializing `Variable` metadata.
- Modify `gaia/engine/lang/dsl/support.py`: enforce unit-bearing vs unitless `observe(variable, ...)` behavior and validate noise distribution units for variables.
- Modify `gaia/engine/bayes/runtime/actions.py`: rename `Prediction` to `Model` and `target` to `observable`.
- Move `gaia/engine/bayes/dsl/predict.py` to `gaia/engine/bayes/dsl/model.py`: expose `model(...)`, validate `observable: Variable`, and validate distribution units.
- Modify `gaia/engine/bayes/dsl/__init__.py` and `gaia/engine/bayes/__init__.py`: export `model` / `Model`, remove `predict` / `Prediction`.
- Modify `gaia/engine/bayes/dsl/compare.py`: resolve `Model` helper actions and validate shared observable.
- Modify `gaia/engine/bayes/compiler/lower.py`: lower `Model` / `ModelComparison` using model terminology and `metadata["model"]`.
- Modify `gaia/engine/bayes/compiler/__init__.py`: no behavior change expected; verify imports still use `BayesInference`.
- Modify tests under `tests/gaia/lang`, `tests/gaia/bayes`, and `tests/baseline` to use `model(observable=...)`.
- Modify docs and examples that mention `predict(target=...)`.

## Task 1: Add Canonical Unit Support to Variable

**Files:**
- Modify: `gaia/unit.py`
- Modify: `gaia/engine/lang/runtime/variable.py`
- Modify: `gaia/engine/lang/compiler/compile.py`
- Test: `tests/gaia/test_unit.py`
- Test: `tests/gaia/lang/runtime/test_variable.py`

- [ ] **Step 1: Add failing unit helper tests**

Add to `tests/gaia/test_unit.py`:

```python
from gaia.unit import canonical_unit


def test_canonical_unit_normalizes_aliases() -> None:
    assert canonical_unit("K") == "kelvin"
    assert canonical_unit("m/s") == "meter / second"
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/test_unit.py::test_canonical_unit_normalizes_aliases -v`

Expected: FAIL with an import error for `canonical_unit`.

- [ ] **Step 2: Implement `canonical_unit`**

Add to `gaia/unit.py` after `q(...)`:

```python
def canonical_unit(unit: str) -> str:
    """Return Gaia's canonical Pint unit string for an authored unit."""
    if not isinstance(unit, str) or not unit:
        raise TypeError("unit must be a non-empty string")
    return str(ureg.parse_units(unit))
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/test_unit.py::test_canonical_unit_normalizes_aliases -v`

Expected: PASS.

- [ ] **Step 3: Add failing Variable unit tests**

Add to `tests/gaia/lang/runtime/test_variable.py`:

```python
import pytest

from gaia.engine.lang import Real, Variable


def test_variable_unit_canonicalizes_through_gaia_unit() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    assert temperature.unit == "kelvin"
    assert "kelvin" in temperature.content


def test_variable_rejects_invalid_unit() -> None:
    with pytest.raises(Exception, match="not_a_unit"):
        Variable(symbol="T", domain=Real, unit="not_a_unit")
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/lang/runtime/test_variable.py::test_variable_unit_canonicalizes_through_gaia_unit tests/gaia/lang/runtime/test_variable.py::test_variable_rejects_invalid_unit -v`

Expected: FAIL because `Variable.__init__` does not accept `unit`.

- [ ] **Step 4: Implement `Variable.unit`**

Update `gaia/engine/lang/runtime/variable.py` so the class fields and constructor match this shape:

```python
    symbol: str = field(default="")
    domain: PrimitiveType | Domain = field(default=cast(PrimitiveType, None))
    value: Any | None = None
    unit: str | None = None

    def __init__(
        self,
        *,
        symbol: str,
        domain: PrimitiveType | Domain,
        value: Any | None = None,
        unit: str | None = None,
        content: str | None = None,
        format: str = "markdown",
        **kwargs: Any,
    ) -> None:
        """Create a typed authoring variable."""
        if not isinstance(symbol, str) or not symbol:
            raise TypeError("symbol must be a non-empty string")
        if not isinstance(domain, (PrimitiveType, Domain)):
            raise TypeError("domain must be a PrimitiveType or a Domain")

        if value is not None:
            _validate_value(value, domain)

        canonical_unit_value: str | None = None
        if unit is not None:
            from gaia.unit import canonical_unit

            canonical_unit_value = canonical_unit(unit)

        if content is None:
            content = _default_content(symbol, domain, value, canonical_unit_value)

        super().__init__(content=content, type="variable", format=format, **kwargs)
        self.symbol = symbol
        self.domain = domain
        self.value = value
        self.unit = canonical_unit_value
```

Replace `_default_content(...)` with:

```python
def _default_content(
    symbol: str,
    domain: PrimitiveType | Domain,
    value: Any | None,
    unit: str | None,
) -> str:
    domain_name = domain.name if isinstance(domain, PrimitiveType) else (domain.label or "Domain")
    unit_part = f" [{unit}]" if unit is not None else ""
    if value is None:
        return f"Variable {symbol}: {domain_name}{unit_part}"
    return f"Variable {symbol}: {domain_name}{unit_part} = {value!r}"
```

Run the tests from Step 3.

Expected: PASS.

- [ ] **Step 5: Serialize Variable units in metadata**

In `gaia/engine/lang/compiler/compile.py`, update the `Variable` branch of `_metadata_to_ir(...)` to include unit:

```python
    if isinstance(value, Variable):
        domain = getattr(value.domain, "name", None) or getattr(value.domain, "label", None)
        return {
            "kind": "variable",
            "symbol": value.symbol,
            "domain": domain,
            "unit": value.unit,
        }
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/lang/runtime/test_variable.py tests/gaia/test_unit.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add gaia/unit.py gaia/engine/lang/runtime/variable.py gaia/engine/lang/compiler/compile.py tests/gaia/test_unit.py tests/gaia/lang/runtime/test_variable.py
git commit -m "feat(lang): add unit-aware variables"
```

Expected: commit succeeds.

## Task 2: Enforce Unit Rules for observe(variable, ...)

**Files:**
- Modify: `gaia/engine/lang/dsl/support.py`
- Test: `tests/gaia/lang/test_distribution_units.py`

- [ ] **Step 1: Add failing observe(variable) unit tests**

Add to `tests/gaia/lang/test_distribution_units.py`:

```python
from gaia.engine.lang import Real, Variable


def test_observe_unit_typed_variable_converts_quantity_value_and_error() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    obs = observe(temperature, value=q(26.85, "celsius"), error=q(5, "K"))
    payload = obs.metadata["observation"]
    assert math.isclose(payload["value"], 300.0, abs_tol=1e-6)
    assert payload["unit"] == "kelvin"
    noise = payload["noise"]
    assert noise.kind == "normal"
    assert noise.metadata["unit"] == "kelvin"
    assert noise.params["sigma"] == 5.0


def test_observe_unit_typed_variable_rejects_bare_scalar_value() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    with pytest.raises(TypeError, match="must be a gaia.unit.Quantity in 'kelvin'"):
        observe(temperature, value=203)


def test_observe_unitless_variable_rejects_quantity_value() -> None:
    temperature = Variable(symbol="T", domain=Real)
    with pytest.raises(TypeError, match="unitless"):
        observe(temperature, value=q(203, "K"))


def test_observe_unit_typed_variable_rejects_incompatible_error_distribution() -> None:
    temperature = Variable(symbol="T", domain=Real, unit="K")
    noise = Normal("length noise", mu=q(0, "m"), sigma=q(1, "m"))
    with pytest.raises(ValueError, match="not compatible"):
        observe(temperature, value=q(203, "K"), error=noise)


def test_observe_unitless_variable_rejects_unit_typed_error_distribution() -> None:
    temperature = Variable(symbol="T", domain=Real)
    noise = Normal("temperature noise", mu=q(0, "K"), sigma=q(1, "K"))
    with pytest.raises(TypeError, match="unit-typed noise distribution"):
        observe(temperature, value=203, error=noise)
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/lang/test_distribution_units.py::test_observe_unit_typed_variable_converts_quantity_value_and_error tests/gaia/lang/test_distribution_units.py::test_observe_unit_typed_variable_rejects_bare_scalar_value tests/gaia/lang/test_distribution_units.py::test_observe_unitless_variable_rejects_quantity_value tests/gaia/lang/test_distribution_units.py::test_observe_unit_typed_variable_rejects_incompatible_error_distribution tests/gaia/lang/test_distribution_units.py::test_observe_unitless_variable_rejects_unit_typed_error_distribution -v`

Expected: FAIL because `observe(variable, ...)` still accepts observation-local units.

- [ ] **Step 2: Add variable unit helper functions**

In `gaia/engine/lang/dsl/support.py`, add these helpers near the existing observation coercion helpers:

```python
def _distribution_unit(distribution: Distribution) -> str | None:
    unit = (distribution.metadata or {}).get("unit")
    if unit is None:
        return None
    from gaia.unit import canonical_unit

    return canonical_unit(unit)


def _ensure_noise_unit_for_variable(noise: Distribution, *, target: Variable) -> None:
    from gaia.unit import ureg

    target_unit = target.unit
    noise_unit = _distribution_unit(noise)
    label = target.symbol
    if target_unit is None:
        if noise_unit is not None:
            raise TypeError(
                "observe(variable, error=<Distribution>) got a unit-typed noise "
                f"distribution {noise_unit!r} for unitless target {label!r}."
            )
        return
    if noise_unit is None:
        raise TypeError(
            "observe(variable, error=<Distribution>) noise distribution must carry "
            f"unit {target_unit!r} because target {label!r} carries that unit."
        )
    try:
        (1 * ureg.parse_units(noise_unit)).to(ureg.parse_units(target_unit))
    except Exception as err:
        raise ValueError(
            "observe(variable, error=<Distribution>) noise distribution unit "
            f"{noise_unit!r} is not compatible with target unit {target_unit!r}: {err}"
        ) from err
    if noise_unit != target_unit:
        raise ValueError(
            "observe(variable, error=<Distribution>) noise distribution unit "
            f"{noise_unit!r} must match target unit {target_unit!r}."
        )
```

- [ ] **Step 3: Replace variable scalar and error coercion**

In `gaia/engine/lang/dsl/support.py`, replace `_coerce_variable_scalar(...)` and `_coerce_variable_error(...)` with:

```python
def _coerce_variable_scalar(raw: Any, *, target: Variable, role: str) -> tuple[Any, str | None]:
    """Coerce a Variable-target observation scalar to (magnitude, unit)."""
    from gaia.unit import is_quantity, ureg

    target_unit = target.unit
    if target_unit is not None:
        if not is_quantity(raw):
            raise TypeError(
                f"observe(variable, {role}=...) must be a gaia.unit.Quantity in "
                f"{target_unit!r} because target {target.symbol!r} carries that unit; "
                f"got {type(raw).__name__}: {raw!r}."
            )
        try:
            converted = raw.to(ureg.parse_units(target_unit))
        except Exception as err:
            raise ValueError(
                f"observe(variable, {role}=...) unit {raw.units!s} is not compatible "
                f"with target unit {target_unit!r}: {err}"
            ) from err
        return float(converted.magnitude), target_unit

    if is_quantity(raw):
        raise TypeError(
            f"observe(variable, {role}=...) got a unit-typed Quantity for unitless "
            f"target {target.symbol!r}. Declare Variable(unit=...) or pass a bare scalar."
        )
    if isinstance(raw, bool) or not isinstance(raw, (int, float)):
        raise TypeError(
            f"observe(variable, {role}=...) must be a numeric scalar, got "
            f"{type(raw).__name__}: {raw!r}."
        )
    return raw, None


def _coerce_variable_error(error: Any, *, target: Variable, value_unit: str | None) -> Distribution | None:
    """Sugar error= into anonymous Normal(0, sigma) under the variable unit contract."""
    if error is None:
        return None
    if isinstance(error, Distribution):
        _ensure_noise_unit_for_variable(error, target=target)
        return error

    from gaia.unit import is_quantity, ureg

    if target.unit is not None:
        if not is_quantity(error):
            raise TypeError(
                "observe(variable, error=...) must be a gaia.unit.Quantity or "
                f"a Distribution because target {target.symbol!r} carries unit "
                f"{target.unit!r}; got {type(error).__name__}: {error!r}."
            )
        try:
            converted = error.to(ureg.parse_units(target.unit))
        except Exception as err:
            raise ValueError(
                f"observe(variable, error=...) unit {error.units!s} is not compatible "
                f"with target unit {target.unit!r}: {err}"
            ) from err
        sigma = float(converted.magnitude)
    else:
        if is_quantity(error):
            raise TypeError(
                f"observe(variable, error=...) got a unit-typed Quantity for unitless "
                f"target {target.symbol!r}. Declare Variable(unit=...) or pass a bare scalar."
            )
        if isinstance(error, bool) or not isinstance(error, (int, float)):
            raise TypeError(
                "observe(variable, error=...) must be None, a positive numeric scalar, "
                f"or a Distribution; got {type(error).__name__}: {error!r}."
            )
        sigma = float(error)

    if sigma <= 0.0:
        raise ValueError(f"observe(variable, error=sigma) requires sigma > 0, got {error!r}.")
    return _anonymous_normal_noise(sigma, value_unit=value_unit)
```

- [ ] **Step 4: Update `_observe_variable(...)` call sites**

In `_observe_variable(...)`, replace:

```python
    coerced_value, value_unit = _coerce_variable_scalar(value, role="value")
    noise = _coerce_variable_error(error, value_unit=value_unit)
```

with:

```python
    coerced_value, value_unit = _coerce_variable_scalar(value, target=target, role="value")
    noise = _coerce_variable_error(error, target=target, value_unit=value_unit)
```

Run the tests from Step 1.

Expected: PASS.

- [ ] **Step 5: Run all observe/unit tests**

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/lang/test_distribution_units.py tests/gaia/lang/test_observe_continuous.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git add gaia/engine/lang/dsl/support.py tests/gaia/lang/test_distribution_units.py
git commit -m "feat(lang): enforce variable observation units"
```

Expected: commit succeeds.

## Task 3: Rename Bayes predict/Prediction to model/Model

**Files:**
- Move: `gaia/engine/bayes/dsl/predict.py` to `gaia/engine/bayes/dsl/model.py`
- Modify: `gaia/engine/bayes/runtime/actions.py`
- Modify: `gaia/engine/bayes/runtime/__init__.py`
- Modify: `gaia/engine/bayes/dsl/__init__.py`
- Modify: `gaia/engine/bayes/__init__.py`
- Test: `tests/gaia/bayes/test_public_surface.py`
- Test: `tests/gaia/lang/test_action_hierarchy.py`

- [ ] **Step 1: Add failing public surface tests**

Update `tests/gaia/bayes/test_public_surface.py` so `test_bayes_canonical_peer_module_imports()` imports and asserts `model` / `Model`:

```python
def test_bayes_canonical_peer_module_imports() -> None:
    import gaia.engine.bayes as bayes
    from gaia.engine.bayes import (
        BayesInference,
        Model,
        ModelComparison,
        PrecomputedLikelihoods,
        compare,
        model,
    )
    from gaia.engine.bayes.dsl import compare as dsl_compare
    from gaia.engine.bayes.dsl import model as dsl_model
    from gaia.engine.lang.runtime.action import Reasoning

    assert model is dsl_model
    assert compare is dsl_compare
    assert "model" in bayes.__all__
    assert "compare" in bayes.__all__
    assert "PrecomputedLikelihoods" in bayes.__all__
    assert issubclass(BayesInference, Reasoning)
    assert issubclass(Model, BayesInference)
    assert issubclass(ModelComparison, BayesInference)
    for removed in ("predict", "data", "likelihood"):
        assert not hasattr(bayes, removed)
    for removed in ("Prediction", "PredictiveModel", "Likelihood"):
        assert not hasattr(bayes, removed)
```

Update `tests/gaia/lang/test_action_hierarchy.py` imports and Bayes assertions:

```python
from gaia.engine.bayes.runtime import BayesInference, Model, ModelComparison


def test_bayes_action_shapes_follow_reasoning_taxonomy():
    assert issubclass(BayesInference, Reasoning)
    assert not issubclass(BayesInference, Directed)
    assert issubclass(Model, BayesInference)
    assert not issubclass(Model, Directed)
    assert issubclass(ModelComparison, BayesInference)
    assert not issubclass(ModelComparison, Directed)
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/bayes/test_public_surface.py::test_bayes_canonical_peer_module_imports tests/gaia/lang/test_action_hierarchy.py::test_bayes_action_shapes_follow_reasoning_taxonomy -v`

Expected: FAIL because `model` and `Model` are not exported.

- [ ] **Step 2: Rename the runtime record**

In `gaia/engine/bayes/runtime/actions.py`, replace the file contents with:

```python
"""Bayes runtime action shapes — Model and ModelComparison."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.engine.lang.runtime.action import Reasoning
from gaia.engine.lang.runtime.distribution import Distribution
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable


@dataclass
class BayesInference(Reasoning):
    """Bayes-family reasoning record (marker base class)."""


@dataclass
class Model(BayesInference):
    """Predictive model: ties a hypothesis to a distribution over an observable."""

    hypothesis: Claim | None = None
    observable: Variable | None = None
    distribution: Distribution | None = None
    helper: Claim | None = None


@dataclass
class ModelComparison(BayesInference):
    """Equal-positioned list of competing predictive models."""

    helper: Claim | None = None
    models: tuple[Claim, ...] = ()
    data: tuple[Claim, ...] = ()
    exclusivity: str = "pairwise_contradiction"
    precomputed: Any | None = None
    log_likelihoods: dict[Claim, float] = field(default_factory=dict)
```

- [ ] **Step 3: Move and rewrite the DSL verb**

Run: `git mv gaia/engine/bayes/dsl/predict.py gaia/engine/bayes/dsl/model.py`

Replace the imports and function in `gaia/engine/bayes/dsl/model.py` with a `model(...)` verb:

```python
from gaia.engine.bayes.runtime import Model
from gaia.engine.lang.runtime import Claim, Distribution, Knowledge, Variable
from gaia.engine.lang.runtime.action import attach_reasoning, validate_no_self_warrant


def _observable_descriptor(observable: Variable) -> str:
    return observable.symbol


def _distribution_unit(distribution: Distribution) -> str | None:
    unit = (distribution.metadata or {}).get("unit")
    if unit is None:
        return None
    from gaia.unit import canonical_unit

    return canonical_unit(unit)


def _validate_model_units(observable: Variable, distribution: Distribution) -> None:
    from gaia.unit import ureg

    observable_unit = observable.unit
    distribution_unit = _distribution_unit(distribution)
    if observable_unit is None:
        if distribution_unit is not None:
            raise TypeError(
                "bayes.model() distribution carries unit "
                f"{distribution_unit!r} but observable {observable.symbol!r} is unitless. "
                "Declare Variable(unit=...) for unit-bearing observables."
            )
        return
    if distribution_unit is None:
        raise TypeError(
            f"bayes.model() observable {observable.symbol!r} carries unit "
            f"{observable_unit!r}, but distribution {distribution.label or distribution.content[:40]!r} "
            "is unitless."
        )
    try:
        (1 * ureg.parse_units(distribution_unit)).to(ureg.parse_units(observable_unit))
    except Exception as err:
        raise ValueError(
            "bayes.model() distribution unit "
            f"{distribution_unit!r} is not compatible with observable unit "
            f"{observable_unit!r}: {err}"
        ) from err
    if distribution_unit != observable_unit:
        raise ValueError(
            "bayes.model() distribution unit "
            f"{distribution_unit!r} must match observable unit {observable_unit!r}."
        )


def model(
    hypothesis: Claim,
    *,
    observable: Variable,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare a predictive model for one hypothesis and observable."""
    if not isinstance(hypothesis, Claim):
        raise TypeError("model() hypothesis must be a Claim")
    if not isinstance(observable, Variable):
        raise TypeError(
            f"model() observable must be a Variable; got {type(observable).__name__}"
        )
    if not isinstance(distribution, Distribution):
        raise TypeError(
            "model() distribution must be a Distribution Knowledge object "
            "(use factories in gaia.engine.lang: Normal, Binomial, BetaBinomial, ...); "
            f"got {type(distribution).__name__}"
        )
    _validate_model_units(observable, distribution)

    merged = dict(metadata or {})
    model_meta = {
        "kind": "model",
        "hypothesis": hypothesis,
        "observable": observable,
        "distribution": distribution,
    }
    merged["model"] = {**dict(merged.get("model", {})), **model_meta}
    merged.setdefault("generated", True)
    merged.setdefault("helper_kind", "model")
    merged.setdefault("review", True)
    if rationale:
        merged["reason"] = rationale

    content = f"{_claim_ref(hypothesis)} models {_observable_descriptor(observable)} ~ {distribution.kind}."
    helper = Claim(content, background=background or [], metadata=merged)
    helper.label = label

    action = Model(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata={"bayes": {"action": "model"}},
        hypothesis=hypothesis,
        observable=observable,
        distribution=distribution,
        helper=helper,
    )
    validate_no_self_warrant(action, helper)
    attach_reasoning(helper, action)
    return helper
```

Keep the existing `_claim_ref(...)` helper from the old file.

- [ ] **Step 4: Update exports and role handlers**

In `gaia/engine/bayes/dsl/__init__.py`:

```python
"""Bayes DSL verbs."""

from gaia.engine.bayes.dsl.compare import compare
from gaia.engine.bayes.dsl.model import model

__all__ = ["compare", "model"]
```

In `gaia/engine/bayes/runtime/__init__.py`:

```python
"""Runtime action shapes for Bayes helpers."""

from gaia.engine.bayes.runtime.actions import BayesInference, Model, ModelComparison
from gaia.engine.bayes.runtime.precomputed import PrecomputedLikelihoods

__all__ = [
    "BayesInference",
    "Model",
    "ModelComparison",
    "PrecomputedLikelihoods",
]
```

In `gaia/engine/bayes/__init__.py`, import `model` and `Model`, remove `predict` and `Prediction`, and update the role handler:

```python
from gaia.engine.bayes.dsl.model import model
from gaia.engine.bayes.runtime import (
    BayesInference,
    Model,
    ModelComparison,
    PrecomputedLikelihoods,
)


def _register_bayes_roles() -> None:
    def model_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, Model):
            return
        add(action.hypothesis, "hypothesis")
        add(action.helper, "model_helper")

    def model_comparison_roles(action: Action, add: RoleAdder) -> None:
        if not isinstance(action, ModelComparison):
            return
        for model_helper in action.models:
            add(model_helper, "compared_model")
        for data_claim in action.data:
            add(data_claim, "likelihood_data")
        add(action.helper, "model_preference_helper")

    register_role_handler(Model, model_roles)
    register_role_handler(ModelComparison, model_comparison_roles)
```

Set `__all__` to:

```python
__all__ = [
    "BayesInference",
    "Model",
    "ModelComparison",
    "PrecomputedLikelihoods",
    "compare",
    "model",
]
```

- [ ] **Step 5: Run public surface tests**

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/bayes/test_public_surface.py::test_bayes_canonical_peer_module_imports tests/gaia/lang/test_action_hierarchy.py::test_bayes_action_shapes_follow_reasoning_taxonomy -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git add gaia/engine/bayes/dsl gaia/engine/bayes/runtime gaia/engine/bayes/__init__.py tests/gaia/bayes/test_public_surface.py tests/gaia/lang/test_action_hierarchy.py
git commit -m "feat(bayes): rename predict surface to model"
```

Expected: commit succeeds.

## Task 4: Update compare/lowering to use Model and observable

**Files:**
- Modify: `gaia/engine/bayes/dsl/compare.py`
- Modify: `gaia/engine/bayes/compiler/lower.py`
- Test: `tests/gaia/bayes/test_runtime_and_lowering.py`
- Test: `tests/gaia/bayes/test_v06_external_solver_integration.py`

- [ ] **Step 1: Add failing Bayes model observable tests**

In `tests/gaia/bayes/test_runtime_and_lowering.py`, update imports to use `Model` and add:

```python
def test_model_rejects_distribution_observable() -> None:
    h = claim("H", prior=0.5, label="h")
    y = Normal("observed y", mu=0, sigma=1)
    with pytest.raises(TypeError, match="observable must be a Variable"):
        bayes.model(
            h,
            observable=y,
            distribution=Normal("y under H", mu=0, sigma=1),
            label="bad_model",
        )


def test_model_accepts_unit_typed_variable_and_distribution() -> None:
    h = claim("H", prior=0.5, label="h")
    y = Variable(symbol="y", domain=Real, unit="K")
    model = bayes.model(
        h,
        observable=y,
        distribution=Normal("y under H", mu=q(200, "K"), sigma=q(50, "K")),
        label="model_h",
    )
    action = next(a for a in model.from_actions if isinstance(a, Model))
    assert action.observable is y
    assert action.distribution is not None
    assert action.distribution.metadata["unit"] == "kelvin"


def test_model_rejects_unit_mismatch_between_observable_and_distribution() -> None:
    h = claim("H", prior=0.5, label="h")
    y = Variable(symbol="y", domain=Real, unit="K")
    with pytest.raises(ValueError, match="not compatible"):
        bayes.model(
            h,
            observable=y,
            distribution=Normal("length under H", mu=q(0, "m"), sigma=q(1, "m")),
            label="bad_model",
        )
```

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/bayes/test_runtime_and_lowering.py::test_model_rejects_distribution_observable tests/gaia/bayes/test_runtime_and_lowering.py::test_model_accepts_unit_typed_variable_and_distribution tests/gaia/bayes/test_runtime_and_lowering.py::test_model_rejects_unit_mismatch_between_observable_and_distribution -v`

Expected: FAIL until `compare.py`, imports, and tests are migrated.

- [ ] **Step 2: Rename compare helpers**

In `gaia/engine/bayes/dsl/compare.py`:

- Import `Model` instead of `Prediction`.
- Rename `_prediction_action(...)` to `_model_action(...)`.
- Rename `_comparison_hypotheses(prediction_actions)` parameter to `model_actions`.
- Rename `_validate_shared_target(...)` to `_validate_shared_observable(...)`.

Use this body for shared observable validation:

```python
def _validate_shared_observable(model_actions: tuple[Model, ...]) -> None:
    """All compared models must predict the same observable."""
    if not model_actions:
        return
    first_observable = model_actions[0].observable
    for action in model_actions[1:]:
        if action.observable is not first_observable:
            raise ValueError(
                "compare() model helpers must share one observable; got "
                f"{first_observable!r} vs {action.observable!r}"
            )
```

In `compare(...)`, replace:

```python
    prediction_actions = tuple(_prediction_action(m) for m in models_tuple)
    hypothesis_tuple = _comparison_hypotheses(prediction_actions)
    _validate_shared_target(prediction_actions)
```

with:

```python
    model_actions = tuple(_model_action(m) for m in models_tuple)
    hypothesis_tuple = _comparison_hypotheses(model_actions)
    _validate_shared_observable(model_actions)
```

- [ ] **Step 3: Rename lowering helpers and metadata**

In `gaia/engine/bayes/compiler/lower.py`:

- Import `Model` instead of `Prediction`.
- Rename `_prediction_metadata(...)` to `_model_metadata(...)`.
- Use `action.observable` instead of `action.target`.
- Store metadata under `"model"` with `"observable"`, not `"prediction"` with `"target"`.

Use this descriptor:

```python
def _observable_descriptor(observable: Variable) -> dict[str, Any]:
    domain = getattr(observable.domain, "name", None) or getattr(observable.domain, "label", None)
    return {
        "kind": "variable",
        "symbol": observable.symbol,
        "domain": domain,
        "unit": observable.unit,
    }
```

Use this model metadata payload:

```python
def _model_metadata(
    action: Model,
    knowledge_map: dict[int, str],
    *,
    action_label: str | None,
) -> dict[str, Any]:
    if action.hypothesis is None or action.observable is None or action.distribution is None:
        raise ValueError("Bayes Model action requires hypothesis, observable, distribution")
    payload = {
        "kind": "model",
        "distribution": action.distribution.model_dump(),
        "hypothesis": knowledge_map[id(action.hypothesis)],
        "hypotheses": [knowledge_map[id(action.hypothesis)]],
        "observable": _observable_descriptor(action.observable),
    }
    metadata: dict[str, Any] = {"model": payload}
    if action_label:
        metadata["review_target"] = {"action_label": action_label, "pattern": "model"}
    return metadata
```

In likelihood evaluation, replace `p_action.target` with `p_action.observable`.

- [ ] **Step 4: Restrict observation matching to Variable**

In `gaia/engine/bayes/compiler/lower.py`, replace `_observation_value(...)` signature and body with:

```python
def _observation_value(data_claim: Claim, observable: Variable) -> Any:
    """Read the observed value from metadata['observation'] for a model observable."""
    observation = (data_claim.metadata or {}).get("observation")
    if not isinstance(observation, dict):
        raise ValueError(
            f"compare() data {data_claim.label or data_claim.content!r} has no "
            "metadata['observation'] payload (use observe(observable, value=...))"
        )
    observed_target = observation.get("target")
    if observed_target is not observable:
        if isinstance(observed_target, Variable):
            if observed_target.symbol != observable.symbol:
                raise ValueError(
                    f"compare() data observable {observed_target!r} does not match "
                    f"model observable {observable!r}"
                )
        else:
            raise ValueError(
                f"compare() data {data_claim.label or data_claim.content!r} target "
                f"{observed_target!r} does not match model observable {observable!r}"
            )
    if "value" not in observation:
        raise ValueError(
            f"compare() data {data_claim.label or data_claim.content!r} "
            "metadata['observation'] is missing 'value'"
        )
    return observation["value"]
```

- [ ] **Step 5: Run focused Bayes lowering tests**

Run: `/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/gaia/bayes/test_runtime_and_lowering.py tests/gaia/bayes/test_v06_external_solver_integration.py -v`

Expected: FAIL only on remaining test call sites that still use `predict` or `target`.

- [ ] **Step 6: Commit Task 4**

After Step 5 is passing, run:

```bash
git add gaia/engine/bayes/dsl/compare.py gaia/engine/bayes/compiler/lower.py tests/gaia/bayes/test_runtime_and_lowering.py tests/gaia/bayes/test_v06_external_solver_integration.py
git commit -m "feat(bayes): compare models by variable observable"
```

Expected: commit succeeds.

## Task 5: Migrate Tests, Docs, Examples, and Snapshots

**Files:**
- Modify: `tests/gaia/bayes/check/test_gaia_check_bayes.py`
- Modify: `tests/gaia/bayes/check/test_gaia_check_precomputed_diagnostics.py`
- Modify: `tests/gaia/bayes/test_v06_numeric_equivalence.py`
- Modify: `tests/gaia/bayes/test_public_surface.py`
- Modify: `tests/gaia/lang/test_public_surface_milestone_a.py`
- Modify: `docs/for-users/language-reference.md`
- Modify: `docs/foundations/gaia-lang/bayes.md`
- Modify: `docs/foundations/gaia-lang/knowledge-and-reasoning.md`
- Modify: `docs/reference/engine/index.md`
- Modify: `docs/specs/2026-05-17-bayes-unified-design.md`
- Modify: `examples/mendel-v0-5-gaia/src/mendel_v0_5/__init__.py`
- Modify: `scripts/demo_v06_pymc_integration.py`
- Modify: snapshot files under `tests/baseline/__snapshots__/test_artifact_snapshot/`

- [ ] **Step 1: Mechanically find stale names**

Run:

```bash
rg -n "predict\\(|Prediction|target=|metadata\\[\"prediction\"\\]|\\[\"prediction\"\\]" docs examples scripts tests gaia
```

Expected: output lists all remaining stale call sites.

- [ ] **Step 2: Replace Bayes model declarations**

For each Bayes test/example call site, replace:

```python
bayes.predict(
    h,
    target=k,
    distribution=Binomial("k under h", n=n, p=theta),
    label="model_h",
)
```

with:

```python
bayes.model(
    h,
    observable=k,
    distribution=Binomial("k under h", n=n, p=theta),
    label="model_h",
)
```

For continuous Bayes tests that previously used `target=y_distribution`, replace the observable setup with:

```python
y = Variable(symbol="y", domain=Real, unit="kelvin")
data = observe(y, value=q(0.2, "K"), error=q(0.1, "K"), label="data")
model_a = bayes.model(
    h_a,
    observable=y,
    distribution=Normal("y under h_a", mu=q(0.0, "K"), sigma=q(1.0, "K")),
    label="model_a",
)
```

Use a physically neutral unit such as `"kelvin"` only in tests where the value is an arbitrary continuous scalar and the test needs unit behavior. For unitless continuous tests, use `Variable(symbol="y", domain=Real)` with unitless `Normal(...)`.

- [ ] **Step 3: Update precomputed and external solver tests**

In `tests/gaia/bayes/test_v06_numeric_equivalence.py` and `tests/gaia/bayes/test_v06_external_solver_integration.py`, update helper construction to:

```python
pred_31 = bayes.model(
    h_31,
    observable=k_var,
    distribution=LangBinomial("k under 3:1", n=n, p=theta),
    label="model_3_1",
)
```

Keep `compare(..., models=[pred_31, pred_null])` unchanged because the helper claims are still model helper claims.

- [ ] **Step 4: Update docs language**

Replace user-facing text:

- `predict` -> `model`
- `Prediction` -> `Model`
- `target` -> `observable` when describing Bayes model declarations
- `metadata["prediction"]` -> `metadata["model"]`

Keep non-Bayes uses of the English word "prediction" where the text describes a scientific prediction rather than the API.

- [ ] **Step 5: Run focused migration tests**

Run:

```bash
/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest \
  tests/gaia/bayes/test_runtime_and_lowering.py \
  tests/gaia/bayes/test_v06_numeric_equivalence.py \
  tests/gaia/bayes/test_v06_external_solver_integration.py \
  tests/gaia/bayes/check/test_gaia_check_bayes.py \
  tests/gaia/bayes/check/test_gaia_check_precomputed_diagnostics.py \
  tests/gaia/bayes/test_public_surface.py \
  tests/gaia/lang/test_public_surface_milestone_a.py \
  tests/gaia/lang/test_action_hierarchy.py \
  -v
```

Expected: PASS or snapshot-only failures.

- [ ] **Step 6: Refresh snapshots if focused failures are snapshot-only**

If pytest reports syrupy snapshot diffs and the diffs only reflect `predict` -> `model`, `target` -> `observable`, or `metadata["prediction"]` -> `metadata["model"]`, run:

```bash
/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest tests/baseline/test_artifact_snapshot.py --snapshot-update
```

Expected: snapshots update without non-snapshot test failures.

- [ ] **Step 7: Verify stale names are gone**

Run:

```bash
rg -n "bayes\\.predict|Prediction|metadata\\[\"prediction\"\\]|\\[\"prediction\"\\]" gaia tests docs examples scripts
```

Expected: no output. If docs still use the ordinary word "prediction", this command should not match because it searches API-shaped strings.

- [ ] **Step 8: Commit Task 5**

Run:

```bash
git add gaia tests docs examples scripts
git commit -m "docs(bayes): migrate unified surface to model"
```

Expected: commit succeeds.

## Task 6: Full Verification and PR Push

**Files:**
- No planned source edits unless verification exposes a concrete failure.

- [ ] **Step 1: Run formatting and lint**

Run:

```bash
/private/tmp/gaia_pr657_full/.venv/bin/ruff format --check .
/private/tmp/gaia_pr657_full/.venv/bin/ruff check .
```

Expected:

```text
337 files already formatted
All checks passed!
```

If format fails, run `/private/tmp/gaia_pr657_full/.venv/bin/ruff format .`, inspect the diff, and commit with `style: format model observable cleanup`.

- [ ] **Step 2: Run type check**

Run:

```bash
/private/tmp/gaia_pr657_full/.venv/bin/mypy
```

Expected:

```text
Success: no issues found in 328 source files
```

- [ ] **Step 3: Run full test suite**

Run:

```bash
/private/tmp/gaia_pr657_full/.venv/bin/python -m pytest
```

Expected: all tests pass with the same skipped-test count as the branch baseline.

- [ ] **Step 4: Push to PR #657**

Run:

```bash
git push origin HEAD:feat/bayes-unified-design
```

Expected: push succeeds and updates PR #657.

- [ ] **Step 5: Confirm GitHub checks**

Run:

```bash
gh pr view 657 --repo SiliconEinstein/Gaia --json headRefName,headRefOid,mergeable,mergeStateStatus,url
gh pr checks 657 --repo SiliconEinstein/Gaia
```

Expected:

- PR head branch is `feat/bayes-unified-design`.
- `mergeable` is `MERGEABLE`.
- `mergeStateStatus` is `CLEAN` after checks complete.
- `commit-lint`, `build`, and `test` pass; `deploy` may be skipped.

## Self-Review Checklist

- Spec coverage: Tasks 1-2 implement `Variable.unit` and observe unit rules; Tasks 3-4 implement `model` / `Model` and observable-only Bayes records; Task 5 implements docs/examples/tests migration; Task 6 verifies and pushes.
- Placeholder scan: no unresolved marker text or unspecified implementation steps are present.
- Type consistency: the plan consistently uses `Model`, `model`, `observable`, `Variable`, and `metadata["model"]`.
