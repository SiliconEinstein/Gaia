# Unit, Stats, and Constants Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add Gaia v0.5's minimal foundation modules for unit-bearing values, distribution specifications, and physical constants.

**Architecture:** Keep the kernel boundary small: IR stores deterministic Pydantic carriers, while user-facing helpers live in top-level `gaia.unit`, `gaia.stats`, and `gaia.constants`. Pint is a core dependency for units/constants; scipy remains optional and is not imported by this slice.

**Tech Stack:** Python 3.12, Pydantic v2, Pint, uv, pytest.

---

## Source Spec

- Design: `docs/superpowers/specs/2026-04-25-unit-stats-constants-design.md`
- Foundation reference: `docs/specs/2026-04-23-gaia-foundation-spec.md` sections 4.5, 4.6, 4.7, and 17.4

All commands below run from `/Users/kunchen/project/gaia_review` unless a step says otherwise.

## File Structure

- Create `gaia/ir/schemas.py`: shared IR carriers `QuantityLiteral`, `CallableRef`, and `DistributionSpec`.
- Modify `gaia/ir/__init__.py`: export new schemas from the IR package.
- Create `gaia/unit.py`: Pint facade with shared registry, `q`, `to_literal`, and `from_literal`.
- Create `gaia/stats.py`: metadata-only distribution constructors and `from_callable`; no scipy import.
- Create `gaia/constants.py`: curated constants re-exported through `gaia.unit.ureg`.
- Modify `gaia/lang/compiler/compile.py`: normalize quantity-valued claim parameters to JSON-native `QuantityLiteral`.
- Modify `pyproject.toml`: add core Pint dependency and optional scipy `stats` extra.
- Update `uv.lock`: lock dependency metadata after `pyproject.toml` changes.
- Create `tests/ir/test_schemas.py`: schema validator tests.
- Create `tests/gaia/test_unit.py`: unit facade tests.
- Create `tests/gaia/test_stats.py`: distribution constructor tests.
- Create `tests/gaia/test_constants.py`: constants tests.
- Modify `tests/gaia/lang/test_compiler.py`: compile-boundary quantity normalization test.

## Task 1: Add IR Schema Carriers

**Files:**
- Create: `Gaia_v0.5/tests/ir/test_schemas.py`
- Create: `Gaia_v0.5/gaia/ir/schemas.py`
- Modify: `Gaia_v0.5/gaia/ir/__init__.py`

- [ ] **Step 1: Write failing schema tests**

Create `Gaia_v0.5/tests/ir/test_schemas.py` with:

```python
import pytest
from pydantic import ValidationError

from gaia.ir import CallableRef, DistributionSpec, QuantityLiteral


def test_quantity_literal_is_json_native():
    literal = QuantityLiteral(value=80, unit="K")

    assert literal.model_dump(mode="json") == {
        "schema_version": "gaia.quantity_literal.v1",
        "value": 80.0,
        "unit": "K",
    }


def test_builtin_distribution_rejects_callable_ref():
    callable_ref = CallableRef(name="pkg:normal", version="1.0")

    with pytest.raises(ValidationError, match="Built-in distributions"):
        DistributionSpec(
            kind="normal",
            params={"mu": 0.0, "sigma": 1.0},
            callable_ref=callable_ref,
        )


def test_custom_distribution_requires_callable_ref():
    with pytest.raises(ValidationError, match="custom distributions require callable_ref"):
        DistributionSpec(kind="custom", params={})


def test_custom_distribution_accepts_callable_ref():
    callable_ref = CallableRef(
        name="pkg:studentized_residual",
        version="1.0",
        signature="(x: float) -> float",
        source_hash="sha256:abc123",
        purity="pure",
    )

    spec = DistributionSpec(
        kind="custom",
        params={"scale": 2.0},
        callable_ref=callable_ref,
    )

    assert spec.kind == "custom"
    assert spec.callable_ref == callable_ref
```

- [ ] **Step 2: Run schema tests and verify they fail**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/ir/test_schemas.py -q
```

Expected: FAIL because `gaia.ir.schemas` / exported names do not exist.

- [ ] **Step 3: Implement `gaia/ir/schemas.py`**

Create `Gaia_v0.5/gaia/ir/schemas.py` with:

```python
"""Shared Gaia IR schema carriers for scientific parameters."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, model_validator


BuiltinDistributionKind = Literal[
    "normal",
    "lognormal",
    "student_t",
    "cauchy",
    "binomial",
    "poisson",
    "exponential",
    "beta",
]

DistributionKind = Literal[
    "normal",
    "lognormal",
    "student_t",
    "cauchy",
    "binomial",
    "poisson",
    "exponential",
    "beta",
    "custom",
]

BUILTIN_DISTRIBUTION_KINDS = frozenset(
    {
        "normal",
        "lognormal",
        "student_t",
        "cauchy",
        "binomial",
        "poisson",
        "exponential",
        "beta",
    }
)


class QuantityLiteral(BaseModel):
    """JSON-native IR carrier for unit-bearing scalar values."""

    schema_version: Literal["gaia.quantity_literal.v1"] = "gaia.quantity_literal.v1"
    value: float
    unit: str


class CallableRef(BaseModel):
    """Provenance pointer for a callable, not a runtime execution pointer."""

    schema_version: Literal["gaia.callable_ref.v1"] = "gaia.callable_ref.v1"
    name: str
    version: str | None = None
    signature: str | None = None
    source_hash: str | None = None
    purity: Literal["pure", "impure", "unknown"] = "unknown"


DistributionParam = QuantityLiteral | float | int


class DistributionSpec(BaseModel):
    """JSON-native distribution declaration for IR and adapter boundaries."""

    schema_version: Literal["gaia.distribution.v1"] = "gaia.distribution.v1"
    kind: DistributionKind
    params: dict[str, DistributionParam]
    callable_ref: CallableRef | None = None

    @model_validator(mode="after")
    def _validate_callable_ref(self) -> DistributionSpec:
        if self.kind == "custom":
            if self.callable_ref is None:
                raise ValueError("custom distributions require callable_ref")
            return self

        if self.callable_ref is not None:
            raise ValueError("Built-in distributions must not carry callable_ref")
        return self
```

- [ ] **Step 4: Export schemas from `gaia.ir`**

Modify `Gaia_v0.5/gaia/ir/__init__.py`:

Add after the existing `from gaia.ir.review import Review, ReviewManifest, ReviewStatus` block:

```python
from gaia.ir.schemas import (
    BUILTIN_DISTRIBUTION_KINDS,
    CallableRef,
    DistributionSpec,
    QuantityLiteral,
)
```

Add these names to `__all__` before the review names:

```python
    # Schemas
    "BUILTIN_DISTRIBUTION_KINDS",
    "CallableRef",
    "DistributionSpec",
    "QuantityLiteral",
```

- [ ] **Step 5: Run schema tests and verify they pass**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/ir/test_schemas.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git -C Gaia_v0.5 add gaia/ir/schemas.py gaia/ir/__init__.py tests/ir/test_schemas.py
git -C Gaia_v0.5 commit -m "feat: add scientific IR schema carriers"
```

## Task 2: Add Dependency Metadata and Unit Facade

**Files:**
- Modify: `Gaia_v0.5/pyproject.toml`
- Modify: `Gaia_v0.5/uv.lock`
- Create: `Gaia_v0.5/tests/gaia/test_unit.py`
- Create: `Gaia_v0.5/gaia/unit.py`

- [ ] **Step 1: Write failing unit facade tests**

Create `Gaia_v0.5/tests/gaia/test_unit.py` with:

```python
import pytest

from gaia.ir import QuantityLiteral
from gaia.unit import Quantity, from_literal, q, to_literal, ureg


def test_q_creates_shared_registry_quantity():
    qty = q(80, "K")

    assert isinstance(qty, Quantity)
    assert qty._REGISTRY is ureg
    assert qty.magnitude == 80
    assert str(qty.units) == "kelvin"


def test_to_literal_is_deterministic_json_native():
    literal = to_literal(q(80, "K"))

    assert literal == QuantityLiteral(value=80.0, unit="kelvin")
    assert literal.model_dump(mode="json") == {
        "schema_version": "gaia.quantity_literal.v1",
        "value": 80.0,
        "unit": "kelvin",
    }


def test_from_literal_roundtrips_quantity():
    literal = QuantityLiteral(value=3.0, unit="meter / second")

    qty = from_literal(literal)

    assert isinstance(qty, Quantity)
    assert qty.to("m/s").magnitude == pytest.approx(3.0)


def test_to_literal_rejects_non_quantity():
    with pytest.raises(TypeError, match="Expected a gaia.unit.Quantity"):
        to_literal(80)
```

- [ ] **Step 2: Add dependency metadata**

Modify `Gaia_v0.5/pyproject.toml`:

Add Pint to `[project].dependencies` after `sympy`:

```toml
    "pint>=0.23",
```

Add the `stats` optional extra under `[project.optional-dependencies]`, before `dev`:

```toml
stats = [
    "scipy>=1.12",
]
```

Update the lockfile:

```bash
uv lock --project Gaia_v0.5
```

Expected: `uv.lock` changes to include Pint and the scipy optional dependency metadata.

- [ ] **Step 3: Run unit tests and verify they fail on missing module**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_unit.py -q
```

Expected: FAIL because `gaia.unit` does not exist.

- [ ] **Step 4: Implement `gaia/unit.py`**

Create `Gaia_v0.5/gaia/unit.py` with:

```python
"""Gaia unit facade built on Pint."""

from __future__ import annotations

from typing import Any, TypeGuard

from pint import UnitRegistry

from gaia.ir import QuantityLiteral

ureg = UnitRegistry()
Quantity = type(ureg.Quantity(1, "dimensionless"))


def is_quantity(value: Any) -> TypeGuard[Quantity]:
    """Return True when value is a Quantity from Gaia's shared registry."""
    return isinstance(value, Quantity) and getattr(value, "_REGISTRY", None) is ureg


def q(value: float, unit: str) -> Quantity:
    """Create a Pint quantity using Gaia's shared unit registry."""
    return ureg.Quantity(value, unit)


def to_literal(quantity: Quantity) -> QuantityLiteral:
    """Convert a Gaia runtime quantity to the IR literal carrier."""
    if not is_quantity(quantity):
        raise TypeError("Expected a gaia.unit.Quantity from the shared registry")
    return QuantityLiteral(value=float(quantity.magnitude), unit=str(quantity.units))


def from_literal(literal: QuantityLiteral) -> Quantity:
    """Rehydrate an IR quantity literal into a runtime quantity."""
    return ureg.Quantity(literal.value, literal.unit)
```

- [ ] **Step 5: Run unit tests and verify they pass**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_unit.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

Run:

```bash
git -C Gaia_v0.5 add pyproject.toml uv.lock gaia/unit.py tests/gaia/test_unit.py
git -C Gaia_v0.5 commit -m "feat: add Gaia unit facade"
```

## Task 3: Add Stats Distribution Constructors

**Files:**
- Create: `Gaia_v0.5/tests/gaia/test_stats.py`
- Create: `Gaia_v0.5/gaia/stats.py`

- [ ] **Step 1: Write failing stats tests**

Create `Gaia_v0.5/tests/gaia/test_stats.py` with:

```python
from gaia.ir import CallableRef, DistributionSpec, QuantityLiteral
from gaia.stats import (
    Beta,
    Binomial,
    Cauchy,
    Exponential,
    LogNormal,
    Normal,
    Poisson,
    StudentT,
    from_callable,
)
from gaia.unit import q


def test_normal_constructor_converts_quantities_to_literals():
    spec = Normal(mu=q(80, "K"), sigma=q(3, "K"))

    assert spec == DistributionSpec(
        kind="normal",
        params={
            "mu": QuantityLiteral(value=80.0, unit="kelvin"),
            "sigma": QuantityLiteral(value=3.0, unit="kelvin"),
        },
    )


def test_all_builtin_constructors_return_specs():
    specs = [
        LogNormal(mu=0.0, sigma=1.0),
        StudentT(df=5, mu=0.0, sigma=1.0),
        Cauchy(mu=0.0, gamma=1.0),
        Binomial(n=12, p=0.4),
        Poisson(rate=q(2, "1/s")),
        Exponential(rate=q(2, "1/s")),
        Beta(alpha=2.0, beta=3.0),
    ]

    assert [spec.kind for spec in specs] == [
        "lognormal",
        "student_t",
        "cauchy",
        "binomial",
        "poisson",
        "exponential",
        "beta",
    ]


def test_from_callable_builds_custom_distribution_spec():
    def logpdf(x: float) -> float:
        return -x * x

    spec = from_callable(
        logpdf,
        name="pkg:unit_normal_logpdf",
        version="1.0",
        params={"scale": 1.0},
        purity="pure",
    )

    assert spec.kind == "custom"
    assert spec.params == {"scale": 1.0}
    assert isinstance(spec.callable_ref, CallableRef)
    assert spec.callable_ref.name == "pkg:unit_normal_logpdf"
    assert spec.callable_ref.version == "1.0"
    assert spec.callable_ref.signature == "(x: float) -> float"
    assert spec.callable_ref.source_hash.startswith("sha256:")
    assert spec.callable_ref.purity == "pure"


def test_stats_module_does_not_import_scipy():
    import sys

    assert "scipy" not in sys.modules
    assert "scipy.stats" not in sys.modules
```

- [ ] **Step 2: Run stats tests and verify they fail**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_stats.py -q
```

Expected: FAIL because `gaia.stats` does not exist.

- [ ] **Step 3: Implement `gaia/stats.py`**

Create `Gaia_v0.5/gaia/stats.py` with:

```python
"""Distribution-spec constructors for Gaia authors.

This module owns metadata-only distribution declarations. It intentionally does
not import scipy.
"""

from __future__ import annotations

import hashlib
import inspect
from collections.abc import Callable
from typing import Any, Literal

from gaia.ir import CallableRef, DistributionParam, DistributionSpec
from gaia.unit import is_quantity, to_literal


def _coerce_param(value: Any) -> DistributionParam:
    if is_quantity(value):
        return to_literal(value)
    if isinstance(value, bool):
        raise TypeError("Distribution parameters must be numeric scalars, not bool")
    if isinstance(value, int | float):
        return value
    raise TypeError(f"Unsupported distribution parameter type: {type(value).__name__}")


def _spec(kind: str, **params: Any) -> DistributionSpec:
    return DistributionSpec(
        kind=kind,
        params={name: _coerce_param(value) for name, value in params.items()},
    )


def Normal(*, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("normal", mu=mu, sigma=sigma)


def LogNormal(*, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("lognormal", mu=mu, sigma=sigma)


def StudentT(*, df: float, sigma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("student_t", df=df, mu=mu, sigma=sigma)


def Cauchy(*, gamma: Any, mu: Any = 0.0) -> DistributionSpec:
    return _spec("cauchy", mu=mu, gamma=gamma)


def Binomial(*, n: int, p: float) -> DistributionSpec:
    return _spec("binomial", n=n, p=p)


def Poisson(*, rate: Any) -> DistributionSpec:
    return _spec("poisson", rate=rate)


def Exponential(*, rate: Any) -> DistributionSpec:
    return _spec("exponential", rate=rate)


def Beta(*, alpha: float, beta: float) -> DistributionSpec:
    return _spec("beta", alpha=alpha, beta=beta)


def _callable_source_hash(fn: Callable[..., Any]) -> str:
    try:
        source = inspect.getsource(fn)
    except (OSError, TypeError):
        source = repr(fn)
    return f"sha256:{hashlib.sha256(source.encode()).hexdigest()}"


def from_callable(
    fn: Callable[..., Any],
    *,
    name: str,
    version: str | None = None,
    params: dict[str, Any] | None = None,
    purity: Literal["pure", "impure", "unknown"] = "unknown",
) -> DistributionSpec:
    callable_ref = CallableRef(
        name=name,
        version=version,
        signature=str(inspect.signature(fn)),
        source_hash=_callable_source_hash(fn),
        purity=purity,
    )
    return DistributionSpec(
        kind="custom",
        params={key: _coerce_param(value) for key, value in (params or {}).items()},
        callable_ref=callable_ref,
    )
```

- [ ] **Step 4: Export `DistributionParam` from `gaia.ir`**

Modify `Gaia_v0.5/gaia/ir/__init__.py`:

Add `DistributionParam` to the schema import block:

```python
    DistributionParam,
```

Add it to `__all__` near the other schema exports:

```python
    "DistributionParam",
```

- [ ] **Step 5: Run stats and schema tests**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_stats.py Gaia_v0.5/tests/ir/test_schemas.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 3**

Run:

```bash
git -C Gaia_v0.5 add gaia/stats.py gaia/ir/__init__.py tests/gaia/test_stats.py
git -C Gaia_v0.5 commit -m "feat: add distribution spec constructors"
```

## Task 4: Add Physical Constants Module

**Files:**
- Create: `Gaia_v0.5/tests/gaia/test_constants.py`
- Create: `Gaia_v0.5/gaia/constants.py`

- [ ] **Step 1: Write failing constants tests**

Create `Gaia_v0.5/tests/gaia/test_constants.py` with:

```python
from gaia import constants
from gaia.unit import Quantity, to_literal


def test_speed_of_light_aliases_same_quantity():
    assert constants.c is constants.speed_of_light
    assert isinstance(constants.c, Quantity)
    assert constants.c.to("m/s").magnitude == 299792458


def test_core_constants_are_quantities():
    names = [
        "h",
        "hbar",
        "k_B",
        "e",
        "G",
        "g_0",
        "N_A",
        "R",
        "sigma_SB",
        "eps_0",
        "mu_0",
        "m_e",
        "m_p",
        "m_n",
    ]

    for name in names:
        assert isinstance(getattr(constants, name), Quantity)


def test_constant_crosses_to_ir_literal():
    literal = to_literal(constants.c)

    assert literal.unit == "meter / second"
    assert literal.value == 299792458.0
```

- [ ] **Step 2: Run constants tests and verify they fail**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_constants.py -q
```

Expected: FAIL because `gaia.constants` does not exist.

- [ ] **Step 3: Implement `gaia/constants.py`**

Create `Gaia_v0.5/gaia/constants.py` with:

```python
"""Gaia-blessed physical constants as unit-bearing quantities."""

from gaia.unit import ureg

# Fundamental constants
speed_of_light = c = ureg.speed_of_light
planck = h = ureg.planck_constant
hbar = ureg.reduced_planck_constant
boltzmann = k_B = ureg.boltzmann_constant
elementary_charge = e = ureg.elementary_charge

# Gravitation
gravitational_constant = G = ureg.gravitational_constant
standard_gravity = g_0 = ureg.standard_gravity

# Thermodynamics
avogadro = N_A = ureg.avogadro_number
molar_gas_constant = R = ureg.molar_gas_constant
stefan_boltzmann = sigma_SB = ureg.stefan_boltzmann_constant

# Electromagnetism
vacuum_permittivity = eps_0 = ureg.vacuum_electric_permittivity
vacuum_permeability = mu_0 = ureg.vacuum_magnetic_permeability

# Particle masses
electron_mass = m_e = ureg.electron_mass
proton_mass = m_p = ureg.proton_mass
neutron_mass = m_n = ureg.neutron_mass

__all__ = [
    "G",
    "N_A",
    "R",
    "avogadro",
    "boltzmann",
    "c",
    "e",
    "electron_mass",
    "elementary_charge",
    "eps_0",
    "g_0",
    "gravitational_constant",
    "h",
    "hbar",
    "k_B",
    "m_e",
    "m_n",
    "m_p",
    "molar_gas_constant",
    "mu_0",
    "neutron_mass",
    "planck",
    "proton_mass",
    "sigma_SB",
    "speed_of_light",
    "standard_gravity",
    "stefan_boltzmann",
    "vacuum_permeability",
    "vacuum_permittivity",
]
```

- [ ] **Step 4: Run constants tests**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/test_constants.py -q
```

Expected: PASS. If a Pint constant attribute differs from the names above, inspect the installed Pint registry with:

```bash
uv run --project Gaia_v0.5 python -c "from gaia.unit import ureg; print([name for name in dir(ureg) if 'planck' in name or 'permittivity' in name or 'permeability' in name])"
```

Then adjust `gaia/constants.py` and the tests to use the installed Pint attribute names while preserving the public Gaia names listed in this task.

- [ ] **Step 5: Commit Task 4**

Run:

```bash
git -C Gaia_v0.5 add gaia/constants.py tests/gaia/test_constants.py
git -C Gaia_v0.5 commit -m "feat: add physical constants facade"
```

## Task 5: Normalize Quantity Parameters at Compile Boundary

**Files:**
- Modify: `Gaia_v0.5/tests/gaia/lang/test_compiler.py`
- Modify: `Gaia_v0.5/gaia/lang/compiler/compile.py`

- [ ] **Step 1: Write failing compiler test**

Modify `Gaia_v0.5/tests/gaia/lang/test_compiler.py`:

Add imports:

```python
from gaia.lang import Claim
from gaia.unit import q
```

Add this test near the existing compiler tests:

```python
class TemperatureClaim(Claim):
    """Temperature is {value}."""

    value: object


def test_quantity_parameter_compiles_to_literal_json():
    with CollectedPackage("quantity_pkg") as pkg:
        temp = TemperatureClaim(value=q(80, "K"))
        temp.label = "temperature"

    compiled = compile_package_artifact(pkg)
    knowledge = next(k for k in compiled.graph.knowledges if k.label == "temperature")

    assert [param.model_dump(mode="json") for param in knowledge.parameters] == [
        {
            "name": "value",
            "type": "object",
            "value": {
                "schema_version": "gaia.quantity_literal.v1",
                "value": 80.0,
                "unit": "kelvin",
            },
        }
    ]
    assert compiled.to_json()["knowledges"][0]["parameters"][0]["value"] == {
        "schema_version": "gaia.quantity_literal.v1",
        "value": 80.0,
        "unit": "kelvin",
    }
```

- [ ] **Step 2: Run compiler test and verify it fails**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/lang/test_compiler.py::test_quantity_parameter_compiles_to_literal_json -q
```

Expected: FAIL because the compiled parameter value is still a Pint Quantity.

- [ ] **Step 3: Implement compile-boundary normalization**

Modify `Gaia_v0.5/gaia/lang/compiler/compile.py`.

Add this import near the existing `gaia.lang.runtime.param` import:

```python
from gaia.unit import is_quantity, to_literal
```

Replace `_parameter_to_ir` with:

```python
def _parameter_to_ir(param: dict[str, Any], knowledge_map: dict[int, str]) -> IrParameter:
    payload = dict(param)
    value = payload.get("value")
    if isinstance(value, Knowledge):
        payload["value"] = knowledge_map[id(value)]
    elif value is UNBOUND:
        payload["value"] = None
    elif is_quantity(value):
        payload["value"] = to_literal(value).model_dump(mode="json")
    return IrParameter(**payload)
```

- [ ] **Step 4: Run compiler test and focused regression tests**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/lang/test_compiler.py::test_quantity_parameter_compiles_to_literal_json Gaia_v0.5/tests/gaia/lang/test_parameterized_claims.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 5**

Run:

```bash
git -C Gaia_v0.5 add gaia/lang/compiler/compile.py tests/gaia/lang/test_compiler.py
git -C Gaia_v0.5 commit -m "feat: normalize quantity parameters during compile"
```

## Task 6: Final Verification

**Files:**
- No new files.
- Verify all files touched in Tasks 1-5.

- [ ] **Step 1: Run focused foundation test suite**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/ir/test_schemas.py Gaia_v0.5/tests/gaia/test_unit.py Gaia_v0.5/tests/gaia/test_stats.py Gaia_v0.5/tests/gaia/test_constants.py Gaia_v0.5/tests/gaia/lang/test_compiler.py::test_quantity_parameter_compiles_to_literal_json -q
```

Expected: PASS.

- [ ] **Step 2: Run infer/associate/BP regression tests**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests/gaia/lang/test_infer.py Gaia_v0.5/tests/gaia/lang/test_compiler_actions.py Gaia_v0.5/tests/gaia/bp -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run --project Gaia_v0.5 python -m pytest Gaia_v0.5/tests -q
```

Expected: PASS or only pre-existing unrelated failures. If unrelated failures appear, capture exact failing test names and error messages in the final handoff.

- [ ] **Step 4: Inspect git status and recent commits**

Run:

```bash
git -C Gaia_v0.5 status --short --branch
git -C Gaia_v0.5 log --oneline -6
```

Expected: branch is ahead by the implementation commits and the working tree is clean.

## Self-Review

Spec coverage:

- `gaia.unit`: Task 2.
- `QuantityLiteral`: Task 1 and Task 2.
- `gaia.stats`: Task 3.
- `DistributionSpec`: Task 1 and Task 3.
- `CallableRef`: Task 1 and Task 3.
- `gaia.constants`: Task 4.
- Compile-boundary normalization: Task 5.
- Pint core dependency and scipy optional extra: Task 2.
- No scipy import from `gaia.stats`: Task 3 test.
- No measurement/evidence adapter in this slice: no task touches measurement or evidence modules.
- No hash migration in this slice: no task changes `Knowledge.content_hash`.

Placeholder scan:

- The plan gives exact files, code snippets, commands, and expected results.
- The only conditional branch is the Pint constant-name check in Task 4, with the exact inspection command and preserved public Gaia names.

Type consistency:

- `QuantityLiteral`, `CallableRef`, and `DistributionSpec` are defined in `gaia.ir.schemas` and exported from `gaia.ir` before use.
- `gaia.unit.is_quantity` is defined before `gaia.stats` and the compiler import it.
- `DistributionParam` is exported from `gaia.ir` before `gaia.stats` imports it.
