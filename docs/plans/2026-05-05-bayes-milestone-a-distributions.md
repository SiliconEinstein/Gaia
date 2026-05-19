# Bayes Module — Milestone A: Distributions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `gaia.lang.bayes.distributions` — a typed-value distribution layer (Binomial / Normal / Beta / Poisson / Exponential / LogNormal / StudentT / Cauchy / Gamma / ChiSquared) backed by `scipy.stats`, with Variable-aware parameter slots that defer resolution to Milestone B.

**Architecture:** Each distribution is a Pydantic `BaseModel` carrying `kind: str` and `params: dict[str, DistParam]` where `DistParam = int | float | _DeferredRef`. `.logpmf / .logpdf / .support` delegate to a thin `scipy_backend` that constructs the matching `scipy.stats` frozen distribution at call time. Distributions raise `UnresolvedParameterError` when invoked with deferred params — Milestone B will resolve those before lowering. **No coupling to PR 505's Variable class** — we accept anything with a `.symbol` attribute via duck typing; the compiler in Milestone B replaces deferred slots with concrete numbers from the live runtime object references before `.logpmf` is ever called. `model_dump()` descriptors are audit/debug output, not binding keys.

**Tech Stack:** Python 3.12, Pydantic v2, scipy.stats, pytest, ruff.

**Spec reference:** `docs/specs/2026-05-04-bayes-module-design.md` §3.1 (Distribution Lang-side typed value), §9 Milestone A (Distribution module + protocol).

**Branch:** `feat/bayes-milestone-a-distributions` (off `feat/bayes-module-design`).

---

## File Structure

```
gaia/lang/bayes/
├── __init__.py                       # public re-exports for `from gaia.lang import bayes`
├── distributions/
│   ├── __init__.py                   # re-exports Binomial, Normal, Beta, ...
│   ├── protocol.py                   # Distribution Protocol + DistParam type alias + UnresolvedParameterError
│   ├── base.py                       # _BaseDistribution Pydantic model (Variable-aware params, common validation)
│   ├── discrete.py                   # Binomial, Poisson
│   └── continuous.py                 # Normal, Beta, Exponential, LogNormal, StudentT, Cauchy, Gamma, ChiSquared
└── adapters/
    ├── __init__.py
    └── scipy_backend.py              # _to_scipy_dist(distribution) -> scipy.stats frozen rv

tests/gaia/lang/bayes/
├── __init__.py
├── conftest.py                       # shared fixtures: scipy reference, deferred-param helper
├── test_protocol.py                  # Protocol contract — every distribution implements .logpmf/.logpdf/.support
├── test_base.py                      # Variable-aware param storage; UnresolvedParameterError on call
├── distributions/
│   ├── __init__.py
│   ├── test_binomial.py
│   ├── test_normal.py
│   ├── test_beta.py
│   ├── test_poisson.py
│   ├── test_exponential.py
│   ├── test_lognormal.py
│   ├── test_studentt.py
│   ├── test_cauchy.py
│   ├── test_gamma.py
│   └── test_chisquared.py
└── test_public_api.py                # `from gaia.lang.bayes import Binomial, ...` works
```

**Files NOT created in Milestone A** (defer to B/C):
- `gaia/lang/bayes/verbs/predict.py`, `verbs/likelihood.py` — Milestone B
- `gaia/lang/bayes/runtime/{prediction,comparison}.py` — Milestone B
- `gaia/lang/bayes/compiler/lower.py` — Milestone B
- `docs/foundations/gaia-lang/bayes.md` — Milestone C

---

## Chunk 1: Foundation

Adds the scipy dependency, lays the package skeleton, and defines the Protocol + parameter-handling base class. **No distributions yet** — those land in Chunks 2–3 once the framework is in place.

**Files this chunk creates:**
- `gaia/lang/bayes/__init__.py`
- `gaia/lang/bayes/distributions/__init__.py`
- `gaia/lang/bayes/distributions/protocol.py`
- `gaia/lang/bayes/distributions/base.py`
- `gaia/lang/bayes/adapters/__init__.py`
- `gaia/lang/bayes/adapters/scipy_backend.py`
- `tests/gaia/lang/bayes/__init__.py`
- `tests/gaia/lang/bayes/conftest.py`
- `tests/gaia/lang/bayes/test_protocol.py`
- `tests/gaia/lang/bayes/test_base.py`

**Files this chunk modifies:**
- `pyproject.toml` (add `scipy>=1.13` to `dependencies`)

### Task 1.1: Add scipy as a direct runtime dependency

**Files:**
- Modify: `pyproject.toml:18-26`

- [ ] **Step 1: Edit `pyproject.toml`** — add `scipy>=1.13` to the `dependencies` list, keeping alphabetical-ish placement next to `numpy`.

```toml
dependencies = [
    "pydantic>=2.0",
    "typer[all]>=0.12",
    "numpy>=1.26,<2.4",  # numpy 2.4 breaks pytest-cov (double-import C extension)
    "scipy>=1.13",
    "opt-einsum>=3.3",
    "httpx>=0.27",
    "faiss-cpu>=1.7",
]
```

- [ ] **Step 2: Re-lock**

Run: `uv lock`
Expected: `uv.lock` updated; scipy + transitive deps appear in the lock file.

- [ ] **Step 3: Verify scipy importable**

Run: `uv run --extra dev python -c "import scipy.stats; print(scipy.stats.binom.pmf(5, 10, 0.5))"`
Expected: `0.24609375` (Binomial(10, 0.5) PMF at k=5).

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "deps(bayes): add scipy>=1.13 as direct runtime dependency

Required by gaia.lang.bayes.distributions for logpmf/logpdf evaluation.
Spec §1.1: 'Single new hard dependency: scipy (must be added as a direct
runtime dependency; do not rely on optional transitive dependencies).'"
```

---

### Task 1.2: Create empty package skeleton

**Files:**
- Create: `gaia/lang/bayes/__init__.py` (empty for now — Chunk 4 fills it)
- Create: `gaia/lang/bayes/distributions/__init__.py` (empty)
- Create: `gaia/lang/bayes/adapters/__init__.py` (empty)
- Create: `tests/gaia/lang/bayes/__init__.py` (empty)
- Create: `tests/gaia/lang/bayes/distributions/__init__.py` (empty)

- [ ] **Step 1: Create the five empty files**

```bash
mkdir -p gaia/lang/bayes/distributions gaia/lang/bayes/adapters
mkdir -p tests/gaia/lang/bayes/distributions
touch gaia/lang/bayes/__init__.py
touch gaia/lang/bayes/distributions/__init__.py
touch gaia/lang/bayes/adapters/__init__.py
touch tests/gaia/lang/bayes/__init__.py
touch tests/gaia/lang/bayes/distributions/__init__.py
```

- [ ] **Step 2: Verify import path resolves**

Run: `uv run --extra dev python -c "import gaia.lang.bayes; import gaia.lang.bayes.distributions; import gaia.lang.bayes.adapters; print('ok')"`
Expected: `ok` printed (no `ModuleNotFoundError`).

- [ ] **Step 3: Add the new packages to setuptools include list**

Modify `pyproject.toml`'s `[tool.setuptools.packages.find]` `include` list to include the new subpackages. Find the line:

```toml
include = ["gaia", "gaia.ir*", "gaia.lang*", "gaia.bp*", "gaia.cli*", "gaia.review*"]
```

The existing `gaia.lang*` glob already covers `gaia.lang.bayes.*`, so **no change needed**. Verify by:

Run: `uv run --extra dev python -c "from importlib.resources import files; import gaia.lang.bayes; print(files(gaia.lang.bayes))"`
Expected: prints a path under the workspace.

- [ ] **Step 4: Commit**

```bash
git add gaia/lang/bayes tests/gaia/lang/bayes
git commit -m "feat(bayes): empty package skeleton for distributions module

Placeholder __init__.py files so subsequent commits can land
distributions, adapters, and tests incrementally without import errors."
```

---

### Task 1.3: Distribution Protocol + DistParam + UnresolvedParameterError

**Files:**
- Create: `gaia/lang/bayes/distributions/protocol.py`
- Test: `tests/gaia/lang/bayes/test_protocol.py`

- [ ] **Step 1: Write the failing protocol contract test**

Create `tests/gaia/lang/bayes/test_protocol.py`:

```python
"""Distribution Protocol contract tests.

The Protocol itself has no behaviour to test, but importing it
must succeed and DistParam / UnresolvedParameterError must be
exposed at the protocol module level. Concrete distribution
classes are checked individually in distributions/test_*.py.
"""

from __future__ import annotations

import pytest

from gaia.lang.bayes.distributions.protocol import (
    DistParam,
    Distribution,
    UnresolvedParameterError,
)


def test_protocol_imports_resolve():
    # Import side effects only — the protocol itself isn't instantiable.
    assert Distribution is not None
    assert DistParam is not None
    assert issubclass(UnresolvedParameterError, ValueError)


def test_dist_param_accepts_concrete_numbers():
    """DistParam is a duck-typed alias; concrete int/float must satisfy it."""
    # We don't enforce DistParam at runtime — this test documents the contract.
    x: DistParam = 0.75
    y: DistParam = 10
    assert x == 0.75
    assert y == 10


def test_unresolved_parameter_error_is_value_error():
    """ValueError subclass so existing 'except ValueError' handlers catch it."""
    err = UnresolvedParameterError("test", deferred_params=["theta"])
    assert isinstance(err, ValueError)
    assert "theta" in str(err)


def test_unresolved_parameter_error_carries_param_names():
    err = UnresolvedParameterError("Binomial", deferred_params=["n", "p"])
    assert err.distribution_kind == "Binomial"
    assert err.deferred_params == ["n", "p"]
```

- [ ] **Step 2: Run test — verify it fails on import**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_protocol.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'gaia.lang.bayes.distributions.protocol'`.

- [ ] **Step 3: Implement `protocol.py`**

Create `gaia/lang/bayes/distributions/protocol.py`:

```python
"""Distribution Protocol — structural type for bayes-module distribution literals.

A Distribution is a typed value (NOT a Knowledge node) that:
- carries `kind` (string discriminator) and `params` (dict of name → DistParam).
- implements `.logpmf(x)` / `.logpdf(x)` / `.support()` via a scipy backend.
- raises UnresolvedParameterError if any parameter is a deferred reference
  (e.g., a PR 505 Variable that hasn't been bound yet) at evaluation time.

Resolution of deferred parameters is the compiler's responsibility (Milestone B).
This module only defines the structural contract.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


# DistParam is a structural alias. We do NOT enforce it at runtime —
# Pydantic models in `base.py` perform per-distribution validation.
# A DistParam is one of:
#   - int / float (concrete numeric value)
#   - object with a `.symbol: str` attribute (deferred — e.g., PR 505 Variable)
DistParam = int | float | Any


class UnresolvedParameterError(ValueError):
    """Raised when a Distribution method is called with deferred parameters.

    Milestone B's compiler resolves deferred parameters (e.g., PR 505 Variables
    bound by PARAMETER claims) before any `.logpmf` / `.logpdf` call. If this
    error escapes user code, it indicates a bug in the lowering path.
    """

    def __init__(self, distribution_kind: str, deferred_params: list[str]) -> None:
        self.distribution_kind = distribution_kind
        self.deferred_params = list(deferred_params)
        names = ", ".join(deferred_params)
        super().__init__(
            f"{distribution_kind} has unresolved deferred parameter(s): {names}. "
            f"Distributions must be fully bound to concrete numeric values before "
            f"likelihood evaluation. This typically means a Variable was used as a "
            f"parameter without a corresponding parameter() claim binding it."
        )


@runtime_checkable
class Distribution(Protocol):
    """Structural type every concrete distribution implements.

    Implementors are Pydantic models in `discrete.py` / `continuous.py`,
    sharing common machinery via `_BaseDistribution` in `base.py`.
    """

    kind: str
    params: dict[str, DistParam]

    def logpmf(self, x: int) -> float:
        """Discrete log-probability mass. Continuous distributions raise TypeError."""
        ...

    def logpdf(self, x: float) -> float:
        """Continuous log-probability density. Discrete distributions raise TypeError."""
        ...

    def support(self) -> tuple[float, float]:
        """Closed interval (low, high) where the density / pmf is non-zero."""
        ...
```

- [ ] **Step 4: Run test — verify pass**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_protocol.py -v`
Expected: 4 passed.

- [ ] **Step 5: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes/distributions/protocol.py tests/gaia/lang/bayes/test_protocol.py && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/bayes/distributions/protocol.py tests/gaia/lang/bayes/test_protocol.py
git commit -m "feat(bayes): Distribution Protocol + DistParam + UnresolvedParameterError

Spec §3.1. Defines the structural contract every distribution literal
implements (kind, params, logpmf/logpdf, support). DistParam is duck-typed
to admit concrete numbers now and PR 505 Variables later without coupling.
UnresolvedParameterError extends ValueError so existing handlers catch it."
```

---

### Task 1.4: `_BaseDistribution` Pydantic model

**Files:**
- Create: `gaia/lang/bayes/distributions/base.py`
- Create: `tests/gaia/lang/bayes/conftest.py`
- Test: `tests/gaia/lang/bayes/test_base.py`

- [ ] **Step 1: Write `conftest.py` with a deferred-param fixture**

Create `tests/gaia/lang/bayes/conftest.py`:

```python
"""Shared fixtures for bayes distribution tests."""

from __future__ import annotations

from dataclasses import dataclass

import pytest


@dataclass(frozen=True)
class _DeferredVariable:
    """Stand-in for PR 505's Variable. Distributions accept it via duck typing
    on `.symbol`. Resolution is Milestone B's job; in Milestone A tests we
    only verify that distributions store the deferred reference and raise
    UnresolvedParameterError at call time."""

    symbol: str
    domain: str
    label: str | None = None


@pytest.fixture
def theta_deferred() -> _DeferredVariable:
    return _DeferredVariable(symbol="theta", domain="Probability", label="theta_var")


@pytest.fixture
def n_deferred() -> _DeferredVariable:
    return _DeferredVariable(symbol="n", domain="Nat", label="n_var")
```

- [ ] **Step 2: Write the failing base-class tests**

Create `tests/gaia/lang/bayes/test_base.py`:

```python
"""_BaseDistribution behavior — Variable-aware param storage,
deferred-parameter detection, and the kind/params shape contract."""

from __future__ import annotations

import pytest

from gaia.lang.bayes.distributions.base import _BaseDistribution
from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


class _Dummy(_BaseDistribution):
    """Minimal concrete subclass for testing the base. Real distributions
    live in discrete.py / continuous.py."""

    kind: str = "dummy"


def test_subclass_stores_concrete_params():
    d = _Dummy(params={"a": 1.5, "b": 2})
    assert d.kind == "dummy"
    assert d.params == {"a": 1.5, "b": 2}


def test_subclass_stores_deferred_params(theta_deferred):
    d = _Dummy(params={"a": theta_deferred, "b": 0.5})
    assert d.params["a"] is theta_deferred
    assert d.params["b"] == 0.5


def test_deferred_param_names_returns_only_deferred(theta_deferred):
    d = _Dummy(params={"a": theta_deferred, "b": 0.5})
    assert d._deferred_param_names() == ["a"]


def test_deferred_param_names_returns_empty_when_all_concrete():
    d = _Dummy(params={"a": 1.0, "b": 2})
    assert d._deferred_param_names() == []


def test_deferred_param_names_sorted_for_determinism(theta_deferred, n_deferred):
    d = _Dummy(params={"p": theta_deferred, "n": n_deferred})
    assert d._deferred_param_names() == ["n", "p"]


def test_resolved_params_returns_concrete_floats():
    d = _Dummy(params={"a": 1.5, "b": 2})
    resolved = d._resolved_params()
    assert resolved == {"a": 1.5, "b": 2}


def test_resolved_params_raises_when_deferred(theta_deferred):
    d = _Dummy(params={"a": theta_deferred, "b": 0.5})
    with pytest.raises(UnresolvedParameterError) as excinfo:
        d._resolved_params()
    assert excinfo.value.distribution_kind == "dummy"
    assert excinfo.value.deferred_params == ["a"]


def test_param_must_be_number_or_have_symbol_attr():
    """Strings, lists, etc. are rejected at construction."""
    with pytest.raises(ValueError, match="parameter 'a' must be"):
        _Dummy(params={"a": "not a number"})


def test_bool_rejected_as_param_value():
    """bool is a subclass of int in Python; reject it explicitly to avoid
    silent True->1 / False->0 confusion in distribution params."""
    with pytest.raises(ValueError, match="parameter 'a' must be"):
        _Dummy(params={"a": True})


def test_model_dump_serializes_concrete_params():
    d = _Dummy(params={"a": 0.75, "b": 10})
    dumped = d.model_dump()
    assert dumped == {"kind": "dummy", "params": {"a": 0.75, "b": 10}}


def test_model_dump_skips_deferred_params(theta_deferred):
    """Deferred params are not JSON-serializable; model_dump emits concrete
    params plus an audit descriptor for deferred slots.

    Milestone B must resolve deferred params from the live runtime object refs
    before serializing to IR; this descriptor is for trace/debugging, not the
    binding authority."""
    d = _Dummy(params={"a": theta_deferred, "b": 0.5})
    dumped = d.model_dump()
    assert dumped["params"] == {"b": 0.5}
    assert dumped["deferred_params"] == {
        "a": {"symbol": "theta", "domain": "Probability", "label": "theta_var"}
    }
```

- [ ] **Step 3: Run tests — verify failure**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_base.py -v`
Expected: collection error, `ModuleNotFoundError: No module named 'gaia.lang.bayes.distributions.base'`.

- [ ] **Step 4: Implement `base.py`**

Create `gaia/lang/bayes/distributions/base.py`:

```python
"""_BaseDistribution — common machinery for distribution Pydantic models.

Each concrete distribution (Binomial, Normal, ...) subclasses this and adds:
- `kind: Literal["binomial"]` (etc.) discriminator
- a __init__ overload that accepts named keyword params (n=, p=, ...) and
  packs them into the `params` dict
- `logpmf` / `logpdf` / `support` implementations delegating to scipy_backend

This base class enforces:
- params values must be numeric (int / float, excluding bool) OR a deferred
  reference (any object with a `.symbol` attribute, duck-typed for Variable)
- _deferred_param_names() returns sorted parameter names whose values are
  deferred references
- _resolved_params() returns {name: float} or raises UnresolvedParameterError
- model_dump emits only concrete params and a parallel deferred_params descriptor
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, model_validator

from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


def _is_concrete_number(value: Any) -> bool:
    # Reject bool explicitly — `True/False` would silently become 1/0.
    if isinstance(value, bool):
        return False
    return isinstance(value, (int, float))


def _is_deferred_reference(value: Any) -> bool:
    # Duck-typed: any object with a string `.symbol` attribute. Matches PR 505
    # Variable without importing it (Milestone A is independent of PR 505).
    symbol = getattr(value, "symbol", None)
    return isinstance(symbol, str)


def _domain_descriptor(value: Any) -> Any:
    name = getattr(value, "name", None)
    if isinstance(name, str):
        return name
    label = getattr(value, "label", None)
    if isinstance(label, str):
        return label
    content = getattr(value, "content", None)
    if isinstance(content, str):
        return content
    return repr(value)


def _deferred_reference_descriptor(value: Any) -> dict[str, Any]:
    """JSON-safe audit descriptor for a deferred reference.

    This is intentionally not the compiler's binding key. Milestone B resolves
    parameters from the live object references in `self.params` before IR
    serialization, then emits QID/scoped metadata from the compiler map.
    """
    descriptor: dict[str, Any] = {"symbol": value.symbol}
    domain = getattr(value, "domain", None)
    if domain is not None:
        descriptor["domain"] = _domain_descriptor(domain)
    label = getattr(value, "label", None)
    if label is not None:
        descriptor["label"] = label
    return descriptor


class _BaseDistribution(BaseModel):
    """Shared base for all distribution literals."""

    # Pydantic v2 config: allow arbitrary types so deferred refs (which are
    # not Pydantic models) can sit inside the params dict.
    model_config = ConfigDict(arbitrary_types_allowed=True, frozen=True)

    kind: str
    params: dict[str, Any]

    @model_validator(mode="after")
    def _validate_params(self) -> _BaseDistribution:
        for name, value in self.params.items():
            if not _is_concrete_number(value) and not _is_deferred_reference(value):
                raise ValueError(
                    f"{self.kind} parameter {name!r} must be a number "
                    f"(int/float, not bool) or a deferred reference with a "
                    f"`.symbol` attribute; got {type(value).__name__}"
                )
        return self

    def _deferred_param_names(self) -> list[str]:
        """Sorted names of params whose values are deferred references."""
        return sorted(
            name
            for name, value in self.params.items()
            if _is_deferred_reference(value)
        )

    def _deferred_param_descriptors(self) -> dict[str, dict[str, Any]]:
        """Map deferred parameter names to JSON-safe audit descriptors."""
        return {
            name: _deferred_reference_descriptor(value)
            for name, value in sorted(self.params.items())
            if _is_deferred_reference(value)
        }

    def _resolved_params(self) -> dict[str, float]:
        """Return concrete-numeric params, or raise UnresolvedParameterError.

        Used by logpmf / logpdf / support before delegating to scipy.
        """
        deferred = self._deferred_param_names()
        if deferred:
            raise UnresolvedParameterError(self.kind, deferred)
        return {name: float(value) for name, value in self.params.items()}

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Override Pydantic dump: emit concrete params + deferred_params descriptors.

        Deferred references are not JSON-serializable, so we strip them and
        record each parameter slot's available symbol/domain/label data in a
        parallel audit field. Milestone B's compiler must read the live object
        refs in `self.params` before lowering; `deferred_params` is not a
        binding key and must not be used to resolve ambiguous symbols.
        """
        deferred = self._deferred_param_descriptors()
        concrete = {
            name: value
            for name, value in self.params.items()
            if not _is_deferred_reference(value)
        }
        dumped = {
            "kind": self.kind,
            "params": concrete,
        }
        if deferred:
            dumped["deferred_params"] = deferred
        return dumped
```

- [ ] **Step 5: Run tests**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_base.py -v`
Expected: 11 passed.

- [ ] **Step 6: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes/distributions/base.py tests/gaia/lang/bayes/conftest.py tests/gaia/lang/bayes/test_base.py && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add gaia/lang/bayes/distributions/base.py tests/gaia/lang/bayes/conftest.py tests/gaia/lang/bayes/test_base.py
git commit -m "feat(bayes): _BaseDistribution Pydantic model with Variable-aware params

Concrete distributions subclass this. Accepts numeric params or deferred
references (any object with .symbol: str — duck-typed PR 505 Variable).
Raises UnresolvedParameterError when methods are called before deferred
params resolve. model_dump serializes concrete params plus JSON-safe
deferred reference descriptors for audit; compiler rebinding in Milestone B
must use the live runtime object references before IR serialization."
```

---

### Task 1.5: scipy backend skeleton

**Files:**
- Create: `gaia/lang/bayes/adapters/scipy_backend.py`

This is a thin internal helper that constructs a scipy frozen distribution from a `_BaseDistribution`. It has **no public surface** in Milestone A — concrete distributions in Chunks 2–3 call it. Tests for this module land alongside each distribution (e.g., `test_binomial.py` indirectly exercises `_to_scipy_dist` via `Binomial(...).logpmf(...)`).

- [ ] **Step 1: Implement `scipy_backend.py`**

Create `gaia/lang/bayes/adapters/scipy_backend.py`:

```python
"""scipy.stats backend for distribution evaluation.

Maps each distribution `kind` to a scipy.stats frozen rv. Concrete
distributions in `gaia/lang/bayes/distributions/` call this from their
.logpmf / .logpdf / .support methods.

This module is internal — it is not part of the public bayes API. PyMC /
Stan adapters in v2+ will sit alongside this module without changing the
DSL contract (Spec §5.2).
"""

from __future__ import annotations

from typing import Any, Callable

import scipy.stats as stats

# Each builder takes the distribution's resolved-params dict and returns a
# scipy frozen rv (anything implementing .logpmf / .logpdf / .support).
_BUILDERS: dict[str, Callable[[dict[str, float]], Any]] = {
    "binomial": lambda p: stats.binom(n=int(p["n"]), p=p["p"]),
    "normal": lambda p: stats.norm(loc=p["mu"], scale=p["sigma"]),
    "beta": lambda p: stats.beta(a=p["alpha"], b=p["beta"]),
    "poisson": lambda p: stats.poisson(mu=p["rate"]),
    "exponential": lambda p: stats.expon(scale=1.0 / p["rate"]),
    "lognormal": lambda p: stats.lognorm(s=p["sigma"], scale=__import__("math").exp(p["mu"])),
    "studentt": lambda p: stats.t(df=p["df"], loc=p["mu"], scale=p["sigma"]),
    "cauchy": lambda p: stats.cauchy(loc=p["mu"], scale=p["gamma"]),
    "gamma": lambda p: stats.gamma(a=p["alpha"], scale=1.0 / p["rate"]),
    "chisquared": lambda p: stats.chi2(df=p["df"]),
}


def _to_scipy_dist(kind: str, resolved_params: dict[str, float]) -> Any:
    """Build a scipy.stats frozen distribution from a `kind` + resolved params.

    Raises KeyError if `kind` has no registered builder — this is a developer
    error (a new distribution class was added without registering it here),
    not a user error, so we let the bare KeyError propagate.
    """
    return _BUILDERS[kind](resolved_params)
```

- [ ] **Step 2: Smoke test in REPL**

Run:
```bash
uv run --extra dev python -c "
from gaia.lang.bayes.adapters.scipy_backend import _to_scipy_dist
d = _to_scipy_dist('binomial', {'n': 10, 'p': 0.5})
print(d.logpmf(5))
"
```
Expected: `-1.4023300224853388` (≈ ln(0.246)).

- [ ] **Step 3: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes/adapters/scipy_backend.py && uv run --extra dev ruff check gaia/lang/bayes/adapters`
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add gaia/lang/bayes/adapters/scipy_backend.py
git commit -m "feat(bayes): scipy.stats backend skeleton

Internal _to_scipy_dist(kind, resolved_params) builds the matching
scipy.stats frozen rv. Concrete distributions in Chunks 2-3 call this from
their .logpmf / .logpdf / .support methods. Public PyMC/Stan adapter slots
land in v2+ without touching the DSL surface (spec §5.2)."
```

---

**Chunk 1 done.** Foundation in place: scipy dep added, package skeleton, Protocol + DistParam + UnresolvedParameterError, base class with Variable-aware param storage, scipy backend dispatch table. No distributions yet.

---

## Chunk 2: Reference distributions — Binomial (discrete) and Normal (continuous)

These two land first as the **canonical TDD templates** every other distribution in Chunk 3 copies. Binomial exercises the discrete path (`.logpmf`, integer support, bounded domain). Normal exercises the continuous path (`.logpdf`, unbounded support). Each ships with parity tests against `scipy.stats` reference values and a deferred-parameter test using the `theta_deferred` fixture.

**Files this chunk creates:**
- `gaia/lang/bayes/distributions/discrete.py` (with `Binomial` only for now; Poisson added in Chunk 3)
- `gaia/lang/bayes/distributions/continuous.py` (with `Normal` only for now; others in Chunk 3)
- `tests/gaia/lang/bayes/distributions/test_binomial.py`
- `tests/gaia/lang/bayes/distributions/test_normal.py`

### Task 2.1: Binomial — failing test

**Files:**
- Test: `tests/gaia/lang/bayes/distributions/test_binomial.py`

- [ ] **Step 1: Write the test file**

Create `tests/gaia/lang/bayes/distributions/test_binomial.py`:

```python
"""Binomial distribution — discrete reference implementation.

Parity with scipy.stats.binom at representative points; input validation
(n >= 0, 0 <= p <= 1); deferred-parameter handling via theta_deferred fixture.
"""

from __future__ import annotations

import math

import pytest
import scipy.stats as stats

from gaia.lang.bayes.distributions.discrete import Binomial
from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


# ---- Construction & basic identity ------------------------------------------


def test_binomial_stores_kind_and_params():
    d = Binomial(n=10, p=0.3)
    assert d.kind == "binomial"
    assert d.params == {"n": 10, "p": 0.3}


def test_binomial_keyword_only():
    """n and p are keyword-only — positional call must fail."""
    with pytest.raises(TypeError):
        Binomial(10, 0.3)  # type: ignore[misc]


def test_binomial_is_frozen():
    """Pydantic frozen=True — attributes can't be reassigned post-construction."""
    d = Binomial(n=10, p=0.3)
    with pytest.raises(Exception):
        d.params = {"n": 20, "p": 0.5}  # type: ignore[misc]


# ---- Parameter validation ---------------------------------------------------


@pytest.mark.parametrize("n", [0, 1, 10, 100, 10_000])
def test_binomial_valid_n(n):
    Binomial(n=n, p=0.5)  # no raise


@pytest.mark.parametrize("bad_n", [-1, -100])
def test_binomial_rejects_negative_n(bad_n):
    with pytest.raises(ValueError, match=r"Binomial.*n.*>=.*0"):
        Binomial(n=bad_n, p=0.5)


def test_binomial_rejects_non_integer_n():
    with pytest.raises(ValueError, match=r"Binomial.*n.*integer"):
        Binomial(n=10.5, p=0.5)  # type: ignore[arg-type]


@pytest.mark.parametrize("p", [0.0, 0.001, 0.5, 0.999, 1.0])
def test_binomial_valid_p(p):
    Binomial(n=10, p=p)  # no raise


@pytest.mark.parametrize("bad_p", [-0.1, 1.1, -1e-9, 1.0 + 1e-9])
def test_binomial_rejects_p_out_of_range(bad_p):
    with pytest.raises(ValueError, match=r"Binomial.*p.*\[0, 1\]"):
        Binomial(n=10, p=bad_p)


# ---- logpmf parity with scipy.stats -----------------------------------------


@pytest.mark.parametrize(
    "n,p,k",
    [
        (10, 0.5, 5),
        (10, 0.8, 8),
        (10, 0.5, 0),
        (10, 0.5, 10),
        (395, 0.75, 295),  # Mendel reference
        (1, 0.5, 1),
    ],
)
def test_binomial_logpmf_matches_scipy(n, p, k):
    d = Binomial(n=n, p=p)
    expected = stats.binom.logpmf(k, n, p)
    assert d.logpmf(k) == pytest.approx(expected, rel=1e-12, abs=1e-15)


def test_binomial_logpmf_outside_support_is_neg_inf():
    d = Binomial(n=10, p=0.5)
    assert d.logpmf(-1) == -math.inf
    assert d.logpmf(11) == -math.inf


def test_binomial_logpmf_rejects_float_k():
    """k must be an int — Binomial is discrete."""
    d = Binomial(n=10, p=0.5)
    with pytest.raises(TypeError, match=r"Binomial.*integer"):
        d.logpmf(5.5)  # type: ignore[arg-type]


def test_binomial_logpdf_raises():
    """Discrete distributions have no pdf; calling logpdf is a type error."""
    d = Binomial(n=10, p=0.5)
    with pytest.raises(TypeError, match=r"discrete"):
        d.logpdf(5.0)


# ---- Support ----------------------------------------------------------------


def test_binomial_support():
    d = Binomial(n=10, p=0.5)
    low, high = d.support()
    assert (low, high) == (0, 10)


def test_binomial_support_n_zero():
    d = Binomial(n=0, p=0.5)
    assert d.support() == (0, 0)


# ---- Deferred parameters ----------------------------------------------------


def test_binomial_accepts_deferred_p(theta_deferred):
    d = Binomial(n=10, p=theta_deferred)
    # Construction succeeds — resolution happens at .logpmf time.
    assert d.params["p"] is theta_deferred


def test_binomial_logpmf_with_deferred_p_raises(theta_deferred):
    d = Binomial(n=10, p=theta_deferred)
    with pytest.raises(UnresolvedParameterError) as excinfo:
        d.logpmf(5)
    assert excinfo.value.distribution_kind == "binomial"
    assert excinfo.value.deferred_params == ["p"]


def test_binomial_accepts_deferred_n_and_p(n_deferred, theta_deferred):
    d = Binomial(n=n_deferred, p=theta_deferred)
    assert d.params["n"] is n_deferred
    assert d.params["p"] is theta_deferred


def test_binomial_support_with_deferred_n_raises(n_deferred):
    d = Binomial(n=n_deferred, p=0.5)
    with pytest.raises(UnresolvedParameterError):
        d.support()


def test_binomial_model_dump_with_deferred_p(theta_deferred):
    d = Binomial(n=10, p=theta_deferred)
    dumped = d.model_dump()
    assert dumped["kind"] == "binomial"
    assert dumped["params"] == {"n": 10}
    assert dumped["deferred_params"] == {
        "p": {"symbol": "theta", "domain": "Probability", "label": "theta_var"}
    }
```

- [ ] **Step 2: Run — verify test fails at collection**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_binomial.py -v`
Expected: collection error, `ModuleNotFoundError: gaia.lang.bayes.distributions.discrete`.

---

### Task 2.2: Binomial — minimal implementation

**Files:**
- Create: `gaia/lang/bayes/distributions/discrete.py`
- Modify: `gaia/lang/bayes/adapters/scipy_backend.py` (already registers `binomial`; no change needed)

- [ ] **Step 1: Implement `discrete.py` with Binomial only**

Create `gaia/lang/bayes/distributions/discrete.py`:

```python
"""Discrete distributions for the bayes module.

Milestone A ships Binomial + Poisson. Milestone B's compiler resolves
deferred parameters (e.g., PR 505 Variables) before any .logpmf call;
calls with unresolved deferred params raise UnresolvedParameterError.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import model_validator

from gaia.lang.bayes.adapters.scipy_backend import _to_scipy_dist
from gaia.lang.bayes.distributions.base import _BaseDistribution, _is_concrete_number
from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


class Binomial(_BaseDistribution):
    """Binomial(n, p): number of successes in n independent Bernoulli trials.

    Parameters
    ----------
    n : int | DeferredRef
        Number of trials. Must be a non-negative integer (or deferred).
    p : float | DeferredRef
        Success probability per trial. Must lie in [0, 1] (or deferred).
    """

    kind: str = "binomial"

    def __init__(self, *, n: Any, p: Any) -> None:  # noqa: D417 — kwargs-only
        # Pydantic v2: route through the generic params dict on BaseModel.
        super().__init__(kind="binomial", params={"n": n, "p": p})

    @model_validator(mode="after")
    def _validate_binomial(self) -> "Binomial":
        n = self.params["n"]
        p = self.params["p"]
        # Only validate concrete values; deferred references are validated
        # post-resolution by the compiler.
        if _is_concrete_number(n):
            if isinstance(n, float) and not n.is_integer():
                raise ValueError(f"Binomial n must be an integer, got {n!r}")
            n_int = int(n)
            if n_int < 0:
                raise ValueError(f"Binomial n must be >= 0, got {n!r}")
        if _is_concrete_number(p):
            if not 0.0 <= float(p) <= 1.0:
                raise ValueError(f"Binomial p must be in [0, 1], got {p!r}")
        return self

    def logpmf(self, k: int) -> float:
        if not isinstance(k, int) or isinstance(k, bool):
            raise TypeError(f"Binomial.logpmf(k): k must be integer, got {type(k).__name__}")
        resolved = self._resolved_params()
        n = int(resolved["n"])
        if k < 0 or k > n:
            return -math.inf
        return float(_to_scipy_dist("binomial", resolved).logpmf(k))

    def logpdf(self, x: float) -> float:  # noqa: ARG002
        raise TypeError("Binomial is a discrete distribution; use .logpmf() not .logpdf()")

    def support(self) -> tuple[int, int]:
        resolved = self._resolved_params()
        n = int(resolved["n"])
        return (0, n)
```

- [ ] **Step 2: Run tests**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_binomial.py -v`
Expected: all Binomial tests pass (roughly 25–30 assertions).

- [ ] **Step 3: Re-run full bayes suite** — make sure nothing in Chunk 1 regressed.

Run: `uv run --extra dev pytest tests/gaia/lang/bayes -v`
Expected: all tests pass.

- [ ] **Step 4: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes tests/gaia/lang/bayes && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/bayes/distributions/discrete.py tests/gaia/lang/bayes/distributions/test_binomial.py
git commit -m "feat(bayes): Binomial distribution with scipy parity

First concrete distribution — establishes the TDD pattern Chunk 3
distributions will copy. Parity with scipy.stats.binom at representative
points (including Mendel n=395 k=295); kwargs-only constructor; validates
n >= 0 integer and p in [0, 1]; logpmf returns -inf outside support;
logpdf raises TypeError (discrete); accepts deferred n/p and raises
UnresolvedParameterError at call time."
```

---

### Task 2.3: Normal — failing test

**Files:**
- Test: `tests/gaia/lang/bayes/distributions/test_normal.py`

- [ ] **Step 1: Write the test file**

Create `tests/gaia/lang/bayes/distributions/test_normal.py`:

```python
"""Normal distribution — continuous reference implementation.

Parity with scipy.stats.norm at representative points; input validation
(sigma > 0); deferred-parameter handling.
"""

from __future__ import annotations

import math

import pytest
import scipy.stats as stats

from gaia.lang.bayes.distributions.continuous import Normal
from gaia.lang.bayes.distributions.protocol import UnresolvedParameterError


# ---- Construction & basic identity ------------------------------------------


def test_normal_stores_kind_and_params():
    d = Normal(mu=0.0, sigma=1.0)
    assert d.kind == "normal"
    assert d.params == {"mu": 0.0, "sigma": 1.0}


def test_normal_keyword_only():
    with pytest.raises(TypeError):
        Normal(0.0, 1.0)  # type: ignore[misc]


def test_normal_is_frozen():
    d = Normal(mu=0.0, sigma=1.0)
    with pytest.raises(Exception):
        d.params = {"mu": 1.0, "sigma": 2.0}  # type: ignore[misc]


# ---- Parameter validation ---------------------------------------------------


@pytest.mark.parametrize("mu", [-1e6, -1.5, 0.0, 1.5, 1e6])
def test_normal_accepts_any_real_mu(mu):
    Normal(mu=mu, sigma=1.0)  # no raise


@pytest.mark.parametrize("sigma", [1e-9, 0.5, 1.0, 100.0])
def test_normal_valid_sigma(sigma):
    Normal(mu=0.0, sigma=sigma)  # no raise


@pytest.mark.parametrize("bad_sigma", [0.0, -0.1, -1e-12])
def test_normal_rejects_non_positive_sigma(bad_sigma):
    with pytest.raises(ValueError, match=r"Normal.*sigma.*> 0"):
        Normal(mu=0.0, sigma=bad_sigma)


# ---- logpdf parity with scipy.stats -----------------------------------------


@pytest.mark.parametrize(
    "mu,sigma,x",
    [
        (0.0, 1.0, 0.0),
        (0.0, 1.0, 1.0),
        (0.0, 1.0, -3.0),
        (5.0, 2.0, 5.0),
        (5.0, 2.0, 10.0),
        (-1.0, 0.5, 0.0),
    ],
)
def test_normal_logpdf_matches_scipy(mu, sigma, x):
    d = Normal(mu=mu, sigma=sigma)
    expected = stats.norm.logpdf(x, loc=mu, scale=sigma)
    assert d.logpdf(x) == pytest.approx(expected, rel=1e-12, abs=1e-15)


def test_normal_logpdf_at_extreme_tail_is_finite_negative():
    """Float range, far from mean — logpdf should be a large negative float,
    not -inf (Normal has infinite support)."""
    d = Normal(mu=0.0, sigma=1.0)
    val = d.logpdf(10.0)
    assert math.isfinite(val)
    assert val < -40


def test_normal_logpmf_raises():
    """Continuous distributions have no pmf."""
    d = Normal(mu=0.0, sigma=1.0)
    with pytest.raises(TypeError, match=r"continuous"):
        d.logpmf(0)


def test_normal_logpdf_accepts_int():
    """Python ints are valid continuous inputs."""
    d = Normal(mu=0.0, sigma=1.0)
    expected = stats.norm.logpdf(0, loc=0.0, scale=1.0)
    assert d.logpdf(0) == pytest.approx(expected)


# ---- Support ----------------------------------------------------------------


def test_normal_support_is_unbounded():
    d = Normal(mu=0.0, sigma=1.0)
    low, high = d.support()
    assert low == -math.inf
    assert high == math.inf


def test_normal_support_independent_of_params():
    """Normal support is (-inf, inf) regardless of mu/sigma."""
    d = Normal(mu=100.0, sigma=0.001)
    assert d.support() == (-math.inf, math.inf)


# ---- Deferred parameters ----------------------------------------------------


def test_normal_accepts_deferred_mu(theta_deferred):
    d = Normal(mu=theta_deferred, sigma=1.0)
    assert d.params["mu"] is theta_deferred


def test_normal_logpdf_with_deferred_mu_raises(theta_deferred):
    d = Normal(mu=theta_deferred, sigma=1.0)
    with pytest.raises(UnresolvedParameterError) as excinfo:
        d.logpdf(0.0)
    assert excinfo.value.distribution_kind == "normal"
    assert excinfo.value.deferred_params == ["mu"]


def test_normal_support_with_deferred_params_still_unbounded(theta_deferred):
    """Normal support doesn't depend on params, so support() should work
    even with deferred mu/sigma."""
    d = Normal(mu=theta_deferred, sigma=1.0)
    assert d.support() == (-math.inf, math.inf)


def test_normal_model_dump_with_deferred_mu(theta_deferred):
    d = Normal(mu=theta_deferred, sigma=1.0)
    dumped = d.model_dump()
    assert dumped["kind"] == "normal"
    assert dumped["params"] == {"sigma": 1.0}
    assert dumped["deferred_params"] == {
        "mu": {"symbol": "theta", "domain": "Probability", "label": "theta_var"}
    }
```

- [ ] **Step 2: Run — verify test fails at collection**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_normal.py -v`
Expected: collection error, `ModuleNotFoundError: gaia.lang.bayes.distributions.continuous`.

---

### Task 2.4: Normal — minimal implementation

**Files:**
- Create: `gaia/lang/bayes/distributions/continuous.py`

- [ ] **Step 1: Implement `continuous.py` with Normal only**

Create `gaia/lang/bayes/distributions/continuous.py`:

```python
"""Continuous distributions for the bayes module.

Milestone A ships Normal, Beta, Exponential, LogNormal, StudentT, Cauchy,
Gamma, ChiSquared. Normal is the reference implementation landing first;
the rest follow the same pattern in Chunk 3.
"""

from __future__ import annotations

import math
from typing import Any

from pydantic import model_validator

from gaia.lang.bayes.adapters.scipy_backend import _to_scipy_dist
from gaia.lang.bayes.distributions.base import _BaseDistribution, _is_concrete_number


class Normal(_BaseDistribution):
    """Normal(mu, sigma): mean-mu, std-sigma Gaussian.

    Parameters
    ----------
    mu : float | DeferredRef
        Mean. Any real number (or deferred).
    sigma : float | DeferredRef
        Standard deviation. Must be > 0 (or deferred).

    Support: (-inf, inf) regardless of params.
    """

    kind: str = "normal"

    def __init__(self, *, mu: Any, sigma: Any) -> None:
        super().__init__(kind="normal", params={"mu": mu, "sigma": sigma})

    @model_validator(mode="after")
    def _validate_normal(self) -> "Normal":
        sigma = self.params["sigma"]
        if _is_concrete_number(sigma):
            if float(sigma) <= 0.0:
                raise ValueError(f"Normal sigma must be > 0, got {sigma!r}")
        # mu admits any real — no additional validation beyond _BaseDistribution.
        return self

    def logpdf(self, x: float) -> float:
        resolved = self._resolved_params()
        return float(_to_scipy_dist("normal", resolved).logpdf(float(x)))

    def logpmf(self, k: int) -> float:  # noqa: ARG002
        raise TypeError("Normal is a continuous distribution; use .logpdf() not .logpmf()")

    def support(self) -> tuple[float, float]:
        # Normal support is unbounded and independent of params; we skip
        # _resolved_params() so support() works with deferred mu/sigma.
        return (-math.inf, math.inf)
```

- [ ] **Step 2: Run tests**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_normal.py -v`
Expected: all Normal tests pass.

- [ ] **Step 3: Run full bayes suite**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes -v`
Expected: all tests pass (Protocol + base + Binomial + Normal).

- [ ] **Step 4: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes tests/gaia/lang/bayes && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/bayes/distributions/continuous.py tests/gaia/lang/bayes/distributions/test_normal.py
git commit -m "feat(bayes): Normal distribution with scipy parity

Continuous reference — mirrors Binomial's discrete template. Parity with
scipy.stats.norm; kwargs-only constructor; sigma > 0 validation;
support = (-inf, inf) computed without resolving params (so deferred
mu/sigma still give a usable support); logpmf raises TypeError (continuous)."
```

---

**Chunk 2 done.** Two reference distributions — one discrete, one continuous — establish the pattern for Chunk 3. Per-distribution file layout: (1) kwargs-only constructor, (2) `@model_validator(mode="after")` for type/range checks on concrete values, (3) one delegation method (`logpmf` or `logpdf`) that resolves params then calls `_to_scipy_dist`, (4) the inapplicable method raises `TypeError`, (5) `support()` reads from resolved params unless support is param-independent (Normal).

---

## Chunk 3: Remaining 8 distributions

Eight distributions sharing the Chunk 2 template: **Poisson** (discrete), **Beta / Exponential / LogNormal / StudentT / Cauchy / Gamma / ChiSquared** (continuous). Each task is a single TDD cycle (test → implementation → parity-with-scipy verification → commit). The file-level pattern is identical to Chunk 2's `Binomial` / `Normal`.

### Shared testing template

Every new distribution in this chunk copies these test sections from `test_binomial.py` / `test_normal.py`, adjusted for its own parameter names:

1. **Construction** — `kind` + `params` storage, kwargs-only, Pydantic frozen immutability (3 tests).
2. **Parameter validation** — valid range cases, invalid-range rejection with distribution-name in error message (4–8 tests, `@pytest.mark.parametrize`).
3. **Parity with scipy.stats** — 5–8 representative (params, x) pairs via `@pytest.mark.parametrize`, assert `pytest.approx(scipy_reference, rel=1e-12, abs=1e-15)` (one parametrized test).
4. **Outside support** — `-inf` return (discrete) or large-negative-finite (continuous bounded).
5. **Wrong-path method raises** — discrete distributions' `.logpdf` → `TypeError("discrete")`; continuous' `.logpmf` → `TypeError("continuous")`.
6. **Support** — `.support()` returns the expected closed interval.
7. **Deferred params** — `theta_deferred` in each parameter slot (one test per slot), plus `.logpmf` / `.logpdf` raises `UnresolvedParameterError`, plus `model_dump` emits `{slot: {symbol, domain?, label?}}` audit descriptors.

This keeps each test file at 30–60 assertions — same shape as Binomial/Normal.

### Shared implementation template

Each class in `discrete.py` / `continuous.py`:

```python
class <Name>(_BaseDistribution):
    """<one-line docstring>

    Parameters
    ----------
    <param1> : ...
    <param2> : ...

    Support: <interval>
    """

    kind: str = "<lowercase kind>"

    def __init__(self, *, <param1>: Any, <param2>: Any, ...) -> None:
        super().__init__(kind="<kind>", params={"<p1>": <p1>, ...})

    @model_validator(mode="after")
    def _validate_<name>(self) -> "<Name>":
        # Only validate concrete values (`_is_concrete_number(x)`).
        ...
        return self

    def logpmf(self, k: int) -> float:     # or logpdf for continuous
        resolved = self._resolved_params()
        return float(_to_scipy_dist("<kind>", resolved).logpmf(k))

    def logpdf(self, x: float) -> float:   # raises for discrete
        raise TypeError("<kind> is a discrete distribution; use .logpmf() not .logpdf()")

    def support(self) -> tuple[float, float]:
        ...
```

### Per-distribution task table

| Task | Class | Param signature | Validation | Support | scipy backend (already in `_BUILDERS`) |
|------|-------|------------------|------------|---------|--------------------------------|
| 3.1 | `Poisson` | `rate: float > 0` | rate > 0 | `(0, +inf)` — returned as `(0, math.inf)` | `stats.poisson(mu=p["rate"])` |
| 3.2 | `Beta` | `alpha: float > 0`, `beta: float > 0` | alpha > 0, beta > 0 | `(0.0, 1.0)` | `stats.beta(a=alpha, b=beta)` |
| 3.3 | `Exponential` | `rate: float > 0` | rate > 0 | `(0.0, math.inf)` | `stats.expon(scale=1/rate)` |
| 3.4 | `LogNormal` | `mu: float`, `sigma: float > 0` | sigma > 0 | `(0.0, math.inf)` | `stats.lognorm(s=sigma, scale=exp(mu))` |
| 3.5 | `StudentT` | `df: float > 0`, `mu: float = 0.0`, `sigma: float > 0` | df > 0, sigma > 0 | `(-inf, inf)` | `stats.t(df, loc=mu, scale=sigma)` |
| 3.6 | `Cauchy` | `mu: float`, `gamma: float > 0` | gamma > 0 | `(-inf, inf)` | `stats.cauchy(loc=mu, scale=gamma)` |
| 3.7 | `Gamma` | `alpha: float > 0`, `rate: float > 0` | alpha > 0, rate > 0 | `(0.0, math.inf)` | `stats.gamma(a=alpha, scale=1/rate)` |
| 3.8 | `ChiSquared` | `df: float > 0` | df > 0 | `(0.0, math.inf)` | `stats.chi2(df)` |

All 8 scipy builders are already wired up in `scipy_backend._BUILDERS` from Task 1.5. No changes to `scipy_backend.py` are needed in Chunk 3.

### Per-distribution task shape (applies to Tasks 3.1 – 3.8)

**Files for task 3.N:**
- Modify: `gaia/lang/bayes/distributions/discrete.py` **or** `gaia/lang/bayes/distributions/continuous.py`
- Test: `tests/gaia/lang/bayes/distributions/test_<name>.py`

- [ ] **Step 1: Write the failing test file**

Copy the matching reference test file (`test_binomial.py` for Poisson, `test_normal.py` for all continuous distributions), rename classes, adjust parameter names and validation-message regex, and pick 5–8 `(params, x)` pairs for the scipy-parity parametrize. Use the **Shared testing template** above as the checklist (all 7 sections present).

For continuous distributions whose support is bounded on one side (Beta, Exponential, LogNormal, Gamma, ChiSquared), replace Normal's "support unbounded" tests with:
```python
def test_<name>_support_bounded():
    d = <Name>(...)
    low, high = d.support()
    assert low == <lower>
    assert high == <upper>


def test_<name>_logpdf_outside_support_is_neg_inf():
    d = <Name>(...)
    assert d.logpdf(<below-lower>) == -math.inf   # or math.isclose
```

For Poisson (discrete, unbounded upper support), replace Binomial's `support() == (0, n)` test with:
```python
def test_poisson_support():
    d = Poisson(rate=3.0)
    low, high = d.support()
    assert low == 0
    assert high == math.inf
```

- [ ] **Step 2: Verify test fails**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_<name>.py -v`
Expected: `ImportError` or `AttributeError` for the missing class, or assertion failures if the file is already partially implemented from a prior step.

- [ ] **Step 3: Implement the class**

Append a class to `discrete.py` (Poisson) or `continuous.py` (the other 7), filling in the **Shared implementation template** fields from the per-distribution task table. Validation block only checks concrete values (`_is_concrete_number(x)` guard). Support interval is returned as shown in the table — for `math.inf` upper bounds import `math` at the top of the file if not already imported.

- [ ] **Step 4: Run the new distribution's tests**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/distributions/test_<name>.py -v`
Expected: all pass.

- [ ] **Step 5: Run the full bayes suite**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes -v`
Expected: no regressions; all distributions landed so far pass.

- [ ] **Step 6: Run ruff**

Run: `uv run --extra dev ruff format gaia/lang/bayes tests/gaia/lang/bayes && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 7: Commit**

```bash
git add gaia/lang/bayes/distributions/<file>.py tests/gaia/lang/bayes/distributions/test_<name>.py
git commit -m "feat(bayes): <Name> distribution with scipy parity

<one-sentence parameters and support summary>. Follows the Binomial /
Normal template established in Chunk 2."
```

### Concrete parametrize choices per distribution

These are the reference `(params, x, expected_from_scipy)` values every `test_<name>_logpmf_matches_scipy` or `test_<name>_logpdf_matches_scipy` parametrization must cover. Pick at minimum these six per distribution; add your own edge cases if you like.

**Poisson** — rate ∈ {0.5, 1.0, 3.0, 10.0}, k ∈ {0, 1, 3, 10, 20}. Include (rate=3.0, k=0) and (rate=3.0, k=3) as the mode check.

**Beta** — (alpha, beta) ∈ {(2, 2), (0.5, 0.5), (5, 1), (1, 5), (2, 5)}, x ∈ {0.1, 0.5, 0.9}. Note `logpdf(0.0)` / `logpdf(1.0)` with alpha/beta < 1 is `+inf` — that's a scipy behaviour parity case worth one assertion.

**Exponential** — rate ∈ {0.5, 1.0, 3.0}, x ∈ {0.0, 0.5, 1.0, 5.0}. Include `logpdf(0.0) == log(rate)`.

**LogNormal** — (mu, sigma) ∈ {(0.0, 1.0), (1.0, 0.5), (-1.0, 2.0)}, x ∈ {0.1, 1.0, 10.0}. Test that `logpdf(0.0) == -math.inf`.

**StudentT** — df ∈ {1, 2.5, 10, 100}, (mu, sigma) ∈ {(0, 1), (5, 2)}, x ∈ {-2, 0, 2}. df=1 is Cauchy-equivalent; cross-check against scipy only (not against `Cauchy` class).

**Cauchy** — (mu, gamma) ∈ {(0, 1), (5, 2), (-1, 0.5)}, x ∈ {-3, 0, 5}.

**Gamma** — (alpha, rate) ∈ {(1, 1), (2, 0.5), (5, 2), (0.5, 1)}, x ∈ {0.1, 1.0, 5.0}. alpha=1 is Exponential; cross-check parity against scipy only.

**ChiSquared** — df ∈ {1, 2, 5, 10}, x ∈ {0.1, 1.0, 5.0, 20.0}.

---

**Chunk 3 done.** 10 concrete distributions total (Chunk 2 + Chunk 3): 2 discrete (Binomial, Poisson), 8 continuous (Normal, Beta, Exponential, LogNormal, StudentT, Cauchy, Gamma, ChiSquared). Each matches scipy.stats parity at 5–8 representative points with 1e-12 relative tolerance, validates input ranges with distribution-named error messages, handles deferred parameters via `theta_deferred` fixture, serializes correctly through `model_dump`.

---

## Chunk 4: Public API + smoke + docs

Wire the distributions into the public `gaia.lang.bayes` namespace, add an end-to-end smoke test, and write the module README. Also lands a small **exact-inference fixture** so future Milestone B / C tests have a non-BP ground-truth source — closing the "reproducer-bug masquerading as engine bug" trap that hit twice during spec authoring.

**Files this chunk creates:**
- `gaia/lang/bayes/README.md`
- `tests/gaia/lang/bayes/test_public_api.py`
- `tests/gaia/lang/bayes/conftest.py` — extended with `exact_factor_marginals` fixture (modify, not create)

**Files this chunk modifies:**
- `gaia/lang/bayes/__init__.py` — public re-exports
- `gaia/lang/bayes/distributions/__init__.py` — re-exports of all 10 distribution classes
- `gaia/lang/__init__.py` — adds `bayes` namespace re-export

### Task 4.1: Distribution package re-exports

**Files:**
- Modify: `gaia/lang/bayes/distributions/__init__.py`

- [ ] **Step 1: Implement re-exports**

Replace the empty `gaia/lang/bayes/distributions/__init__.py` with:

```python
"""Distribution literals for the bayes module.

Public surface: 10 distribution classes + Distribution Protocol +
UnresolvedParameterError. Backed by scipy.stats via the internal
adapters/scipy_backend module.
"""

from __future__ import annotations

from gaia.lang.bayes.distributions.continuous import (
    Beta,
    Cauchy,
    ChiSquared,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    StudentT,
)
from gaia.lang.bayes.distributions.discrete import Binomial, Poisson
from gaia.lang.bayes.distributions.protocol import (
    DistParam,
    Distribution,
    UnresolvedParameterError,
)

__all__ = [
    # Discrete
    "Binomial",
    "Poisson",
    # Continuous
    "Beta",
    "Cauchy",
    "ChiSquared",
    "Exponential",
    "Gamma",
    "LogNormal",
    "Normal",
    "StudentT",
    # Protocol surface
    "DistParam",
    "Distribution",
    "UnresolvedParameterError",
]
```

- [ ] **Step 2: Verify re-exports**

Run: `uv run --extra dev python -c "from gaia.lang.bayes.distributions import Binomial, Normal, Beta, Poisson, Exponential, LogNormal, StudentT, Cauchy, Gamma, ChiSquared, Distribution, UnresolvedParameterError; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add gaia/lang/bayes/distributions/__init__.py
git commit -m "feat(bayes): public re-exports from gaia.lang.bayes.distributions"
```

---

### Task 4.2: bayes module top-level re-exports

**Files:**
- Modify: `gaia/lang/bayes/__init__.py`

- [ ] **Step 1: Implement top-level re-exports**

Replace the empty `gaia/lang/bayes/__init__.py` with:

```python
"""gaia.lang.bayes — hypothesis-data inference subsystem.

Milestone A surface: distribution literals only (Binomial / Normal / Beta /
Poisson / Exponential / LogNormal / StudentT / Cauchy / Gamma / ChiSquared).
Milestone B will add `predict()` and `likelihood()` verbs; Milestone C adds
the migration tooling.

Recommended import style:

    from gaia.lang import bayes
    bayes.Binomial(n=10, p=0.5)

Flat imports also work:

    from gaia.lang.bayes import Binomial, Normal
"""

from __future__ import annotations

from gaia.lang.bayes.distributions import (
    Beta,
    Binomial,
    Cauchy,
    ChiSquared,
    DistParam,
    Distribution,
    Exponential,
    Gamma,
    LogNormal,
    Normal,
    Poisson,
    StudentT,
    UnresolvedParameterError,
)

__all__ = [
    # Discrete distributions
    "Binomial",
    "Poisson",
    # Continuous distributions
    "Beta",
    "Cauchy",
    "ChiSquared",
    "Exponential",
    "Gamma",
    "LogNormal",
    "Normal",
    "StudentT",
    # Protocol surface
    "DistParam",
    "Distribution",
    "UnresolvedParameterError",
]
```

- [ ] **Step 2: Verify**

Run: `uv run --extra dev python -c "from gaia.lang.bayes import Binomial, Normal; print(Binomial(n=5, p=0.5).logpmf(3))"`
Expected: a numeric value ≈ `-2.0794` (scipy reference for `binom(5, 0.5).logpmf(3)`).

- [ ] **Step 3: Commit**

```bash
git add gaia/lang/bayes/__init__.py
git commit -m "feat(bayes): top-level public API for gaia.lang.bayes"
```

---

### Task 4.3: gaia.lang re-export

**Files:**
- Modify: `gaia/lang/__init__.py`

The spec (§2) prescribes `from gaia.lang import bayes` as the recommended import style. Since the current `gaia/lang/__init__.py` does NOT auto-import all submodules (it imports specific names via `from gaia.lang.dsl import ...`), `bayes` is **already** importable as `gaia.lang.bayes` because Python's import system resolves package members on demand. We add an explicit re-export for IDE autocompletion and `from gaia.lang import bayes` ergonomics.

- [ ] **Step 1: Add import to `gaia/lang/__init__.py`**

At the top of `gaia/lang/__init__.py`, after the existing `from gaia.lang.dsl import (` block, add:

```python
from gaia.lang import bayes  # noqa: F401 — namespace re-export
```

If `gaia/lang/__init__.py` has an `__all__` list, append `"bayes"` to it. (Inspect file before edit.)

- [ ] **Step 2: Verify the spec-recommended idiom works**

Run: `uv run --extra dev python -c "from gaia.lang import bayes; print(bayes.Binomial(n=5, p=0.5).logpmf(3))"`
Expected: same numeric value as Task 4.2 Step 2.

- [ ] **Step 3: Verify nothing else broke**

Run: `uv run --extra dev pytest tests/gaia/lang -q`
Expected: all existing lang tests pass.

- [ ] **Step 4: Commit**

```bash
git add gaia/lang/__init__.py
git commit -m "feat(bayes): re-export bayes namespace from gaia.lang

Spec §2: 'Recommended import style is namespace: from gaia.lang import bayes'."
```

---

### Task 4.4: Public API smoke test

**Files:**
- Test: `tests/gaia/lang/bayes/test_public_api.py`

- [ ] **Step 1: Write the smoke test**

Create `tests/gaia/lang/bayes/test_public_api.py`:

```python
"""Public-API smoke tests — verifies the import paths advertised in the spec
all resolve and return functioning distribution objects."""

from __future__ import annotations

import math

import pytest


def test_namespace_import_recommended_style():
    """Spec §2: `from gaia.lang import bayes; bayes.Binomial(...)`."""
    from gaia.lang import bayes

    d = bayes.Binomial(n=10, p=0.5)
    assert d.logpmf(5) == pytest.approx(math.log(252 / 1024))


def test_flat_import_alternate_style():
    """Spec §2: `from gaia.lang.bayes import Binomial`."""
    from gaia.lang.bayes import Binomial, Normal

    assert Binomial(n=10, p=0.5).logpmf(5) == pytest.approx(math.log(252 / 1024))
    assert Normal(mu=0.0, sigma=1.0).logpdf(0.0) == pytest.approx(-0.5 * math.log(2 * math.pi))


def test_all_ten_distributions_constructible():
    """Every distribution class in the spec's v1 list constructs with valid params."""
    from gaia.lang import bayes

    bayes.Binomial(n=10, p=0.5)
    bayes.Poisson(rate=3.0)
    bayes.Normal(mu=0.0, sigma=1.0)
    bayes.Beta(alpha=2.0, beta=2.0)
    bayes.Exponential(rate=1.0)
    bayes.LogNormal(mu=0.0, sigma=1.0)
    bayes.StudentT(df=10.0, mu=0.0, sigma=1.0)
    bayes.Cauchy(mu=0.0, gamma=1.0)
    bayes.Gamma(alpha=2.0, rate=1.0)
    bayes.ChiSquared(df=5.0)


def test_protocol_surface_exposed():
    """Distribution Protocol + UnresolvedParameterError reachable from public API."""
    from gaia.lang.bayes import Distribution, UnresolvedParameterError

    assert UnresolvedParameterError is not None
    assert Distribution is not None


def test_kind_field_consistent_across_distributions():
    """Each distribution self-reports its kind matching its scipy backend key."""
    from gaia.lang import bayes

    expected_kinds = [
        (bayes.Binomial(n=10, p=0.5), "binomial"),
        (bayes.Poisson(rate=1.0), "poisson"),
        (bayes.Normal(mu=0.0, sigma=1.0), "normal"),
        (bayes.Beta(alpha=2.0, beta=2.0), "beta"),
        (bayes.Exponential(rate=1.0), "exponential"),
        (bayes.LogNormal(mu=0.0, sigma=1.0), "lognormal"),
        (bayes.StudentT(df=5.0, mu=0.0, sigma=1.0), "studentt"),
        (bayes.Cauchy(mu=0.0, gamma=1.0), "cauchy"),
        (bayes.Gamma(alpha=2.0, rate=1.0), "gamma"),
        (bayes.ChiSquared(df=5.0), "chisquared"),
    ]
    for dist, kind in expected_kinds:
        assert dist.kind == kind


def test_dunder_all_completeness():
    """`from gaia.lang.bayes import *` exposes the documented surface."""
    import gaia.lang.bayes as bayes_mod

    expected = {
        "Binomial",
        "Poisson",
        "Normal",
        "Beta",
        "Exponential",
        "LogNormal",
        "StudentT",
        "Cauchy",
        "Gamma",
        "ChiSquared",
        "Distribution",
        "DistParam",
        "UnresolvedParameterError",
    }
    assert expected.issubset(set(bayes_mod.__all__))
```

- [ ] **Step 2: Run**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_public_api.py -v`
Expected: all 6 tests pass.

- [ ] **Step 3: Commit**

```bash
git add tests/gaia/lang/bayes/test_public_api.py
git commit -m "test(bayes): public API smoke — all 10 distributions importable

Verifies both spec-recommended import idioms ('from gaia.lang import bayes'
and 'from gaia.lang.bayes import Binomial') and confirms every distribution
class in v1 self-reports a kind that matches its scipy_backend dispatch key."
```

---

### Task 4.5: Exact-inference fixture for ground truth

**Files:**
- Modify: `tests/gaia/lang/bayes/conftest.py`
- Test: `tests/gaia/lang/bayes/test_exact_inference.py`

**Why this fixture exists.** During spec authoring, two numeric claims about BP behaviour turned out to be wrong because the *reproducer scripts* had bugs (forgot to add a CONTRADICTION factor). The fixture below performs **brute-force exact inference** on small Boolean factor graphs by enumerating all $2^N$ assignments — a slow but unimpeachable ground truth that future Milestone B / C tests can compare against without depending on BP convergence behaviour.

This is **fixture infrastructure for Milestone B/C**. Milestone A doesn't strictly need it, but landing it now while attention is on the bayes test layout is cheaper than retrofitting.

- [ ] **Step 1: Extend `conftest.py` with the exact-inference fixture**

Add these imports near the existing imports at the top of `tests/gaia/lang/bayes/conftest.py`:

```python
from itertools import product
from typing import Callable
```

Then append the fixture implementation below the existing deferred-variable fixtures:

```python

def _enumerate_marginals(
    n_vars: int,
    factor_weight: Callable[[tuple[int, ...]], float],
) -> tuple[float, list[float]]:
    """Brute-force exact marginals for a Boolean factor graph.

    Parameters
    ----------
    n_vars : int
        Number of Boolean variables (each ∈ {0, 1}).
    factor_weight : callable
        Function mapping an assignment tuple of length n_vars to a non-negative
        joint factor weight (product of all factor potentials at that assignment).

    Returns
    -------
    (Z, marginals) where Z is the partition function and marginals[i] is
    P(var_i = 1) under the joint distribution defined by `factor_weight`.

    Use this in tests as the ground-truth comparison for BP-based inference
    on small (n_vars <= 10) graphs.
    """
    Z = 0.0
    one_marg = [0.0] * n_vars
    for assignment in product((0, 1), repeat=n_vars):
        w = factor_weight(assignment)
        Z += w
        for i, v in enumerate(assignment):
            if v == 1:
                one_marg[i] += w
    if Z == 0:
        raise ValueError("Partition function Z = 0; factor graph has no satisfiable assignment")
    return Z, [m / Z for m in one_marg]


@pytest.fixture
def exact_factor_marginals() -> Callable[..., tuple[float, list[float]]]:
    """Return the brute-force enumerator for use in tests.

    Example
    -------
    >>> def w(assn):
    ...     a, b = assn
    ...     return (0.6 if a == 1 else 0.4) * (0.7 if b == 1 else 0.3)
    >>> Z, marg = exact_factor_marginals(2, w)
    >>> marg  # P(a=1), P(b=1)
    [0.6, 0.7]
    """
    return _enumerate_marginals
```

- [ ] **Step 2: Write a sanity test for the fixture**

Create `tests/gaia/lang/bayes/test_exact_inference.py`:

```python
"""Sanity tests for the exact-inference fixture used as ground truth in
Milestone B/C BP regression tests."""

from __future__ import annotations

import math

import pytest


def test_two_independent_variables(exact_factor_marginals):
    """Two independent vars with priors 0.6 and 0.7 — marginals must equal priors."""

    def weight(assn):
        a, b = assn
        return (0.6 if a == 1 else 0.4) * (0.7 if b == 1 else 0.3)

    Z, marg = exact_factor_marginals(2, weight)
    assert Z == pytest.approx(1.0)
    assert marg[0] == pytest.approx(0.6)
    assert marg[1] == pytest.approx(0.7)


def test_contradiction_constraint(exact_factor_marginals):
    """Two vars with priors 0.5 each, plus a CONTRADICTION (¬(A ∧ B)) factor —
    posterior odds P(A=1) / P(A=0) must equal 1/3 (one of the four assignments
    is ruled out, so 3 are equally likely; A=1 happens in 1 of those 3).
    """
    eps = 1e-12

    def weight(assn):
        a, b = assn
        prior = 0.5 * 0.5  # uniform over four assignments before constraint
        contradict = eps if (a == 1 and b == 1) else (1 - eps)
        return prior * contradict

    Z, marg = exact_factor_marginals(2, weight)
    assert marg[0] == pytest.approx(1 / 3, abs=1e-9)
    assert marg[1] == pytest.approx(1 / 3, abs=1e-9)


def test_likelihood_factor_recovers_clamped_bayes_odds(exact_factor_marginals):
    """Single H clamped via a likelihood factor with logL = -1.2 vs an alternate
    H' with logL = -5.1, plus pairwise CONTRADICTION. The raw Bayes factor is
    exp(3.9) ≈ 49.4; with Gaia's Cromwell clamp and the explicit comparison /
    contradiction helper variables in this modeled graph, exact posterior odds
    are ≈46.942.

    This is the corrected ground-truth that PR #514 verified — the same
    arithmetic that flushed out the spec §4.3 bug. Keeping it as a test
    locks the invariant before Milestone B's lowering tries to reproduce it.
    """
    eps = 1e-3
    p0 = 0.5
    p1_a = max(eps, min(1 - eps, (1 - eps) * 1.0))  # H_3:1 (best)
    p1_b = max(eps, min(1 - eps, (1 - eps) * math.exp(-3.9)))  # H_null
    cmp_clamp = 1 - eps

    def cond_factor(h_val, cmp_val, p1):
        cpt = [p0, p1]
        prob = max(eps, min(1 - eps, cpt[h_val]))
        return prob if cmp_val == 1 else 1 - prob

    def weight(assn):
        h_a, h_b, cmp_v, contradict_helper = assn
        # Priors: 0.5 each on H_a/H_b; cmp clamped to 1; contradict helper clamped to 1
        prior = 0.5 * 0.5
        cmp_prior = cmp_clamp if cmp_v == 1 else 1 - cmp_clamp
        contradict_prior = (1 - eps) if contradict_helper == 1 else eps
        # Factors
        f_a = cond_factor(h_a, cmp_v, p1_a)
        f_b = cond_factor(h_b, cmp_v, p1_b)
        # CONTRADICTION operator factor: helper = ¬(a ∧ b)
        truth = not (h_a == 1 and h_b == 1)
        f_contradict = (1 - eps) if (contradict_helper == 1) == truth else eps
        return prior * cmp_prior * contradict_prior * f_a * f_b * f_contradict

    Z, marg = exact_factor_marginals(4, weight)
    odds = marg[0] / marg[1]
    # Raw BF = exp(3.9) ≈ 49.4; this exact graph includes Cromwell-clamped
    # helper variables, yielding the modeled Gaia odds below.
    assert odds == pytest.approx(46.942015227014885, rel=1e-9)
```

- [ ] **Step 3: Run**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes/test_exact_inference.py -v`
Expected: 3 tests pass; the third reproduces the corrected `≈ 46.942` posterior odds for the modeled Gaia factor graph. The unclamped Bayes factor remains `exp(3.9) ≈ 49.4`.

- [ ] **Step 4: Commit**

```bash
git add tests/gaia/lang/bayes/conftest.py tests/gaia/lang/bayes/test_exact_inference.py
git commit -m "test(bayes): exact-inference fixture for BP ground-truth comparisons

Brute-force enumerator over Boolean factor graphs (n_vars <= 10).
Designed for Milestone B/C tests to verify BP-based inference matches
exact marginals — closes the 'reproducer-bug masquerades as engine-bug'
trap that hit the spec exclusivity caveat (PR #514).

Includes a regression test pinning the corrected Cromwell-clamped Mendel
posterior odds (~46.942 for the modeled Gaia factor graph) while separately
documenting the raw exp(3.9) Bayes factor (~49.4)."
```

---

### Task 4.6: Module README

**Files:**
- Create: `gaia/lang/bayes/README.md`

- [ ] **Step 1: Write the README**

Create `gaia/lang/bayes/README.md`:

````markdown
# `gaia.lang.bayes`

Hypothesis–data inference subsystem for Gaia. Spec: [`docs/specs/2026-05-04-bayes-module-design.md`](../../../docs/specs/2026-05-04-bayes-module-design.md).

## Status

| Milestone | Surface | Status |
|---|---|---|
| **A** | Distribution literals (10 distributions, scipy backend) | **this commit set** |
| B | `predict()` / `likelihood()` verbs + IR lowering | Milestone B (separate plan) |
| C | `evidence()` deletion, migration tools, foundation docs | Milestone C |

## Quick start

```python
from gaia.lang import bayes

# Discrete: Binomial PMF parity with scipy.stats.binom
b = bayes.Binomial(n=10, p=0.5)
print(b.logpmf(5))    # -1.402  (≈ log(0.246))
print(b.support())     # (0, 10)

# Continuous: Normal PDF parity with scipy.stats.norm
n = bayes.Normal(mu=0.0, sigma=1.0)
print(n.logpdf(0.0))   # -0.919  (≈ log(1/sqrt(2π)))

# Variable-aware (Milestone B will resolve at compile time)
class _StubVar:
    symbol = "theta"
b_deferred = bayes.Binomial(n=10, p=_StubVar())
b_deferred.logpmf(5)   # raises UnresolvedParameterError
```

## Architecture

```
gaia.lang.bayes
├── distributions/
│   ├── protocol.py      # Distribution Protocol, DistParam, UnresolvedParameterError
│   ├── base.py          # _BaseDistribution Pydantic model with Variable-aware params
│   ├── discrete.py      # Binomial, Poisson
│   └── continuous.py    # Normal, Beta, Exponential, LogNormal, StudentT, Cauchy, Gamma, ChiSquared
└── adapters/
    └── scipy_backend.py # internal: kind → scipy.stats frozen rv dispatch
```

## Available distributions

| Class | Family | Parameters | Support |
|---|---|---|---|
| `Binomial` | discrete | `n: int >= 0`, `p ∈ [0, 1]` | `[0, n]` |
| `Poisson` | discrete | `rate > 0` | `[0, +∞)` |
| `Normal` | continuous | `mu: real`, `sigma > 0` | `(-∞, +∞)` |
| `Beta` | continuous | `alpha > 0`, `beta > 0` | `(0, 1)` |
| `Exponential` | continuous | `rate > 0` | `[0, +∞)` |
| `LogNormal` | continuous | `mu: real`, `sigma > 0` | `(0, +∞)` |
| `StudentT` | continuous | `df > 0`, `mu: real`, `sigma > 0` | `(-∞, +∞)` |
| `Cauchy` | continuous | `mu: real`, `gamma > 0` | `(-∞, +∞)` |
| `Gamma` | continuous | `alpha > 0`, `rate > 0` | `(0, +∞)` |
| `ChiSquared` | continuous | `df > 0` | `[0, +∞)` |

## Variable-aware parameters

Distributions accept **deferred references** in any parameter slot — anything with a string `.symbol` attribute. PR 505's `Variable` class is the intended reference type, but Milestone A is decoupled: any duck-typed object works.

When a distribution method (`.logpmf` / `.logpdf` / `.support`) is called with unresolved deferred parameters, it raises `UnresolvedParameterError` listing the unresolved slot names. Milestone B's compiler resolves these before lowering (by reading bound values off `parameter()` claims).

`model_dump()` emits two fields:
- `params: dict[name, value]` — concrete numeric params only.
- `deferred_params: dict[slot, descriptor]` — present only if any param is deferred. The descriptor includes at least `symbol` and, when available, `domain` / `label`.

This shape is an audit/debug serialization only. Milestone B's compiler must resolve deferred parameters from the live runtime object references in `params` before emitting IR, then use `knowledge_map` / scoped compiler metadata to avoid duplicate-symbol ambiguity.

## Backend

The scipy.stats backend is internal (`adapters/scipy_backend.py`). Future PyMC / Stan / NumPyro adapters plug in by registering additional `kind → frozen rv` builders without touching the public DSL. See spec §5.2.

## Out of scope (this milestone)

- `predict()` and `likelihood()` verbs — Milestone B
- IR lowering — Milestone B
- `evidence()` deletion — Milestone C
- `gaia.stats` deprecation — none planned (no public `gaia.stats` to deprecate; spec §8.2)
````

- [ ] **Step 2: Verify rendering** (visual smoke — no assertion)

Run: `cat gaia/lang/bayes/README.md | head -80`
Expected: well-formed Markdown, the table renders with aligned pipes.

- [ ] **Step 3: Commit**

```bash
git add gaia/lang/bayes/README.md
git commit -m "docs(bayes): module README for Milestone A

Quick start, architecture map, distribution table, Variable-aware param
explanation, and clear out-of-scope list pointing at Milestones B and C."
```

---

### Task 4.7: Final integration check

**Files:** none — verification only.

- [ ] **Step 1: Full test sweep**

Run: `uv run --extra dev pytest tests/gaia/lang/bayes -v`
Expected: all bayes tests pass — Protocol + base + 10 distributions + public API + exact-inference fixture.

- [ ] **Step 2: Lang-wide test sweep — verify no regression**

Run: `uv run --extra dev pytest tests/gaia/lang -q`
Expected: every test in `tests/gaia/lang/` passes.

- [ ] **Step 3: Lint sweep**

Run: `uv run --extra dev ruff format --check gaia/lang/bayes tests/gaia/lang/bayes && uv run --extra dev ruff check gaia/lang/bayes tests/gaia/lang/bayes`
Expected: no errors.

- [ ] **Step 4: Milestone A acceptance subset check (§11)**

Run: `uv run --extra dev python -c "
import gaia.lang.bayes as b
# §11.1: from gaia.lang import bayes exposes 10 distribution classes
required = {'Binomial', 'Normal', 'Beta', 'Poisson', 'Exponential', 'LogNormal', 'StudentT', 'Cauchy', 'Gamma', 'ChiSquared'}
assert required.issubset(set(b.__all__)), f'Missing: {required - set(b.__all__)}'
print('§11.1 distribution subset satisfied (predict/likelihood deferred to Milestone B)')
# §11.6: no new FactorType
from gaia.bp.factor_graph import FactorType
expected_types = {
    'IMPLICATION', 'NEGATION', 'CONJUNCTION', 'DISJUNCTION',
    'EQUIVALENCE', 'CONTRADICTION', 'COMPLEMENT',
    'SOFT_ENTAILMENT', 'CONDITIONAL', 'PAIRWISE_POTENTIAL',
}
assert {ft.name for ft in FactorType} == expected_types, 'FactorType drift detected'
assert not any('BAYES' in ft.name or 'LIKELIHOOD' in ft.name for ft in FactorType)
print('§11.6 satisfied')
# §11.7: no new OperatorType
from gaia.ir.operator import OperatorType
expected_ops = {
    'IMPLICATION', 'NEGATION', 'EQUIVALENCE', 'CONTRADICTION',
    'COMPLEMENT', 'DISJUNCTION', 'CONJUNCTION',
}
assert {ot.name for ot in OperatorType} == expected_ops, 'OperatorType drift detected'
assert not any('BAYES' in ot.name or 'LIKELIHOOD' in ot.name for ot in OperatorType)
print('§11.7 satisfied')
print('Milestone A acceptance subset satisfied at code level')
"`
Expected: three "satisfied" lines plus the final summary.

Note: the rest of §11.1 (`predict` / `likelihood`) plus §11 acceptance criteria 2 (Mendel pipeline test), 3 (PR #506 close), 4 (gaia check rules), 5 (foundation docs) are deferred to Milestone B / C — they require verbs and lowering not in scope here.

- [ ] **Step 5: Final commit (if anything cosmetic was touched)**

If steps 1–4 surfaced any small fix, commit it with:
```bash
git commit -am "chore(bayes): final lint/cleanup pass for Milestone A"
```
Otherwise no commit needed.

---

**Chunk 4 done.** Public API surface for Milestone A is complete: `from gaia.lang import bayes` and `from gaia.lang.bayes import <Class>` both resolve, all 10 distributions exposed, README in place, exact-inference fixture available for Milestone B/C ground-truth comparisons. The §11.1 distribution subset plus §11.6 and §11.7 are verifiably satisfied; `predict` / `likelihood` and criteria 2-5 are deferred to later milestones.

---

## Plan summary

| Chunk | Scope | Files added | Files modified | Tests |
|---|---|---|---|---|
| 1 | Foundation: scipy dep, package skeleton, Protocol, base class, scipy backend | 9 | `pyproject.toml` | 15 |
| 2 | Reference distributions: Binomial, Normal | 2 | — | ~50 |
| 3 | Remaining 8 distributions | 8 | `discrete.py`, `continuous.py` | ~250 |
| 4 | Public API, smoke, exact-inference fixture, README | 5 | `gaia/lang/__init__.py`, distribution `__init__.py`, conftest | ~25 |

**Total:** 24 new files, 4 modifications, ~340 test assertions, ~16 commits across 4 chunks.

**Zero coupling to PR 505** — the duck-typed `.symbol` interface for deferred parameters means Milestone A can ship before, after, or alongside any PR 505 milestone. Milestone B picks up the binding work when PR 505's `parameter()` / `observation()` are merged.
