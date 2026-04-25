# Unit, Stats, and Constants Foundation Modules

Date: 2026-04-25
Status: Draft for review
Scope: Gaia v0.5, option A from the design discussion

## Goal

Implement the smallest foundation layer needed for unit-bearing values,
distribution specifications, and physical constants in Gaia v0.5.

This change gives Gaia structured carriers for scientific numeric parameters.
It does not implement measurement evidence adapters, scipy-backed evaluation, or
automatic probabilistic model construction.

## First Principles

Gaia should own only the semantic boundary it needs:

- Scientific authors need unit-bearing quantities in normal Python authoring.
- The IR needs deterministic, JSON-serializable carriers.
- Unit algebra belongs to Pint, not Gaia.
- Distribution computation belongs to scipy adapters, not Gaia core.
- Constants are named quantities, not new IR object types.

The minimal complete contract is therefore:

1. A runtime unit facade for authors.
2. Pydantic IR carriers for serialized values.
3. Compile-boundary normalization from runtime objects to IR literals.
4. Spec constructors for distribution declarations.
5. A curated constants module built on the same unit facade.

## Non-Goals

- No `MeasurementRecord` in this first slice.
- No `gaia.evidence` or gaussian measurement template.
- No scipy import from `gaia.stats`.
- No distribution evaluation API (`logpdf`, sampling, moments).
- No automatic conversion or canonicalization of units at hash time.
- No redesign of priors, `infer`, `associate`, or BP lowering.

## Proposed API

### `gaia.unit`

Add a thin Pint facade:

```python
from gaia.unit import Quantity, from_literal, q, to_literal, ureg

distance = q(3.0, "m")
speed = distance / q(2.0, "s")
literal = to_literal(speed)
roundtripped = from_literal(literal)
```

Owned responsibilities:

- Shared `ureg` singleton.
- `Quantity` alias.
- `q(value, unit)`.
- `to_literal(quantity) -> QuantityLiteral`.
- `from_literal(literal) -> Quantity`.

The module may import Pint. Kernel modules should not import Pint directly.

### `gaia.ir.schemas`

Add the small shared schema module:

```python
class QuantityLiteral(BaseModel):
    schema_version: Literal["gaia.quantity_literal.v1"] = "gaia.quantity_literal.v1"
    value: float
    unit: str


class CallableRef(BaseModel):
    schema_version: Literal["gaia.callable_ref.v1"] = "gaia.callable_ref.v1"
    name: str
    version: str | None = None
    signature: str | None = None
    source_hash: str | None = None
    purity: Literal["pure", "impure", "unknown"] = "unknown"


class DistributionSpec(BaseModel):
    schema_version: Literal["gaia.distribution.v1"] = "gaia.distribution.v1"
    kind: Literal[
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
    params: dict[str, QuantityLiteral | float | int]
    callable_ref: CallableRef | None = None
```

Validation invariant:

- Built-in distributions must not carry `callable_ref`.
- `kind == "custom"` must carry `callable_ref`.

This module is intentionally separate from `knowledge.py` so `QuantityLiteral`
and `DistributionSpec` can later be reused by measurement, prior-shape, and
adapter schemas without creating import cycles.

### `gaia.stats`

Add metadata-only distribution constructors:

```python
from gaia.stats import Normal, Binomial, from_callable

noise = Normal(mu=q(0, "K"), sigma=q(3, "K"))
count = Binomial(n=12, p=0.4)
custom = from_callable(fn, name="pkg:my_dist", version="1.0")
```

Built-in constructors:

- `Normal(mu=0, sigma=...)`
- `LogNormal(mu=..., sigma=...)`
- `StudentT(df=..., mu=0, sigma=...)`
- `Cauchy(mu=0, gamma=...)`
- `Binomial(n=..., p=...)`
- `Poisson(rate=...)`
- `Exponential(rate=...)`
- `Beta(alpha=..., beta=...)`

Quantity-valued params are converted to `QuantityLiteral`. Scalar params stay
as `float` or `int`. The module must not import scipy.

### `gaia.constants`

Add a curated re-export of Pint constants through `gaia.unit.ureg`.

Initial surface:

- `speed_of_light` / `c`
- `planck` / `h`
- `hbar`
- `boltzmann` / `k_B`
- `elementary_charge` / `e`
- `gravitational_constant` / `G`
- `standard_gravity` / `g_0`
- `avogadro` / `N_A`
- `molar_gas_constant` / `R`
- `stefan_boltzmann` / `sigma_SB`
- `vacuum_permittivity` / `eps_0`
- `vacuum_permeability` / `mu_0`
- `electron_mass` / `m_e`
- `proton_mass` / `m_p`
- `neutron_mass` / `m_n`

If a Pint constant name differs across versions, implementation should add only
names verified against the pinned/tested Pint version, plus tests.

## Compile Boundary

Current v0.5 compilation passes runtime parameter values through almost
unchanged. That is unsafe for Pint quantities because they are not stable IR
literals.

Change `_parameter_to_ir` in `gaia/lang/compiler/compile.py`:

- `Knowledge` values still become QIDs.
- `UNBOUND` still becomes `None`.
- Pint/Gaia `Quantity` values become `QuantityLiteral`.
- Existing JSON-native scalar/list/dict values remain unchanged.

This first slice should not recursively normalize every arbitrary object in
metadata. The required boundary is parameter values, because that is where
unit-bearing claim parameters are expected to enter IR in v0.5.

## Hash and Identity

For option A, implement the literal carrier and compile-boundary normalization.

Do not broaden `Knowledge.content_hash` in this slice unless implementation
reveals that parameter values are already intended to participate in the
current v0.5 hash contract. The active foundation target says
`QuantityLiteral` bytes should participate in future claim/context identity, but
the current v0.5 code and foundation docs still mostly describe
`content_hash = type + format + content + sorted(parameter names/types)`.

That makes hash migration a separate compatibility decision, not part of this
minimal module PR.

## Dependencies

Update `pyproject.toml`:

- Add `pint>=0.23` to core dependencies.
- Add optional extra `stats = ["scipy>=1.12"]`.

No production code in this slice should require scipy to import.

## Files

Expected implementation files:

- `pyproject.toml`
- `gaia/ir/schemas.py`
- `gaia/ir/__init__.py`
- `gaia/unit.py`
- `gaia/stats.py`
- `gaia/constants.py`
- `gaia/lang/compiler/compile.py`

Expected tests:

- `tests/ir/test_schemas.py`
- `tests/gaia/test_unit.py`
- `tests/gaia/test_stats.py`
- `tests/gaia/test_constants.py`
- a compiler test proving `q(..., "...")` in a `Claim` parameter becomes
  `QuantityLiteral` JSON in compiled IR

## Acceptance Criteria

- `from gaia.unit import q, to_literal, from_literal` works.
- `to_literal(q(80, "K")).model_dump()` is deterministic JSON-native data.
- `from_literal(to_literal(q(80, "K"))).to("K").magnitude == 80`.
- `from gaia.stats import Normal` works without scipy installed.
- Built-in `DistributionSpec` rejects `callable_ref`.
- Custom `DistributionSpec` requires `callable_ref`.
- `gaia.constants.c` and `gaia.constants.speed_of_light` are the same quantity.
- A compiled parameterized claim with a quantity value emits JSON containing
  `schema_version: "gaia.quantity_literal.v1"`, `value`, and `unit`.
- Existing infer/associate/BP tests keep passing.

## Risks

- Pint constant names can differ by version; tests should lock the surfaced
  names to what this dependency version provides.
- Pydantic `Any` fields may accept runtime quantities unless the compile
  boundary normalizes them before JSON serialization.
- Hash migration is semantically important but bigger than option A; bundling it
  would make the first PR harder to review.

## Later Slices

1. `MeasurementRecord` schema using `QuantityLiteral` and `DistributionSpec`.
2. A scipy-backed stats adapter under an optional import boundary.
3. A first evidence composition/template such as gaussian measurement.
4. Audit/explain helpers for unit-equivalence warnings.
