# Bayes Module — Milestone A: Distributions Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land `gaia.lang.bayes.distributions` — a typed-value distribution layer (Binomial / Normal / Beta / Poisson / Exponential / LogNormal / StudentT / Cauchy / Gamma / ChiSquared) backed by `scipy.stats`, with Variable-aware parameter slots that defer resolution to Milestone B.

**Architecture:** Each distribution is a Pydantic `BaseModel` carrying `kind: str` and `params: dict[str, DistParam]` where `DistParam = int | float | _DeferredRef`. `.logpmf / .logpdf / .support` delegate to a thin `scipy_backend` that constructs the matching `scipy.stats` frozen distribution at call time. Distributions raise `UnresolvedParameterError` when invoked with deferred params — Milestone B will resolve those before lowering. **No coupling to PR 505's Variable class** — we accept anything with a `.symbol` attribute via duck typing; the compiler in Milestone B replaces deferred slots with concrete numbers before `.logpmf` is ever called.

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


@pytest.fixture
def theta_deferred() -> _DeferredVariable:
    return _DeferredVariable(symbol="theta")


@pytest.fixture
def n_deferred() -> _DeferredVariable:
    return _DeferredVariable(symbol="n")
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
    """Deferred params are not JSON-serializable; model_dump must omit them
    or replace with a placeholder. We pick: only emit concrete params, and
    add a parallel `deferred_params: list[str]` field so the IR side can
    re-resolve them."""
    d = _Dummy(params={"a": theta_deferred, "b": 0.5})
    dumped = d.model_dump()
    assert dumped["params"] == {"b": 0.5}
    assert dumped["deferred_params"] == ["a"]
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
- model_dump emits only concrete params and a parallel deferred_params list
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

    def _resolved_params(self) -> dict[str, float]:
        """Return concrete-numeric params, or raise UnresolvedParameterError.

        Used by logpmf / logpdf / support before delegating to scipy.
        """
        deferred = self._deferred_param_names()
        if deferred:
            raise UnresolvedParameterError(self.kind, deferred)
        return {name: float(value) for name, value in self.params.items()}

    def model_dump(self, **kwargs: Any) -> dict[str, Any]:  # type: ignore[override]
        """Override Pydantic dump: emit concrete params + deferred_params list.

        Deferred references are not JSON-serializable, so we strip them and
        record their names in a parallel field. Milestone B's compiler reads
        `deferred_params` to re-bind them before lowering.
        """
        deferred = self._deferred_param_names()
        concrete = {
            name: value
            for name, value in self.params.items()
            if not _is_deferred_reference(value)
        }
        return {
            "kind": self.kind,
            "params": concrete,
            "deferred_params": deferred,
        }
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
params resolve. model_dump serializes concrete + parallel deferred_params
list so compiler (Milestone B) can re-bind."
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

