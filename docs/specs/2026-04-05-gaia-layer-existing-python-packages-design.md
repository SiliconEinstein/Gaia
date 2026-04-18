# Gaia Layer For Existing Python Packages

> **Status:** Draft
>
> **Depends on:** [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md), [2026-04-05-dsl-v6-support-witness-api-design.md](2026-04-05-dsl-v6-support-witness-api-design.md)
>
> **Note (2026-04-18):** References to "review sidecar" in this spec are outdated. Since gaia-lang 0.4.2, priors are assigned via `priors.py`. See `docs/foundations/gaia-lang/package.md`.
>
> **Scope:** How to add a Gaia authoring layer to an existing Python package without rewriting the package itself

---

## 1. Goal

Gaia v6 should make it natural to take an existing Python package and add a thin `gaia/` layer that:

- exposes selected package concepts as `Claim`s
- exposes selected package procedures as Gaia support constructors
- records enough support / witness structure for review and inference

This document defines that integration pattern.

The target outcome is:

```text
existing_python_package
    + explicit gaia layer
    -> claim graph
    -> support graph
    -> witness-bearing declarations
```

without requiring the original package internals to be rewritten in Gaia-native style.

---

## 2. Core Principle

The key v6 move is:

> Any Python function may be used as a **Gaia support constructor** if it explicitly opts into Gaia semantics and returns a `Claim`.

The important qualifier is **explicitly**.

This design does **not** say:

> every Python function that returns a `Claim` is automatically a support

That rule would be too implicit and too hard to audit.

Instead, the rule is:

> existing Python code may be wrapped, decorated, or adapted into Gaia support constructors

so that the package gains a Gaia layer with explicit semantics.

---

## 3. Three Integration Patterns

## 3.1 In-Package `gaia/` Layer

This is the recommended pattern when you control the package.

```text
mypkg/
  __init__.py
  solver.py
  model.py
  tests/
  gaia/
    __init__.py
    claims.py
    supports.py
    bridges.py
    review.py
```

Interpretation:

- `solver.py`, `model.py`, `tests/` remain ordinary Python code
- `gaia/claims.py` exposes Claim adapters
- `gaia/supports.py` exposes Gaia support constructors around existing functions
- `gaia/bridges.py` exposes interpretation / bridge claims linking execution results to scientific conclusions
- `gaia/review.py` holds review sidecars or package-local review helpers

## 3.2 Sidecar Gaia Package

Use this when the original package should remain untouched.

```text
original_pkg/
  ...

original_pkg_gaia/
  pyproject.toml
  src/original_pkg_gaia/
    __init__.py
    claims.py
    supports.py
    review.py
```

This is useful when:

- the source package is third-party
- the Gaia layer is maintained by a different team
- you want multiple competing Gaia interpretations over the same package

## 3.3 Workspace Bridge Package

Use this when the Gaia layer needs to combine multiple Python packages.

```text
workspace/
  pkg_a/
  pkg_b/
  pkg_ab_gaia/
```

This pattern is especially natural for:

- pipelines
- simulations plus post-processing
- model package + dataset package + evaluation package

---

## 4. What Lives In The Gaia Layer

The Gaia layer should contain three kinds of adapters.

## 4.1 Claim Adapters

These turn existing package objects into `Claim`s.

Examples:

- model specification
- dataset identity
- mesh geometry
- numerical scheme assumptions
- experiment setup

Example:

```python
# mypkg/gaia/claims.py
from gaia.lang import claim
from mypkg.model import DEFAULT_MODEL

model_spec = claim(
    "The package uses the default incompressible Navier-Stokes model with the documented assumptions.",
    source_object=DEFAULT_MODEL,
)
```

Claim adapters are appropriate when the object is concept-like rather than execution-like.

## 4.2 Support Constructors

These wrap package functions and expose them as Gaia constructors.

Examples:

- run solver
- run checker
- compute benchmark
- validate invariant

Example:

```python
# mypkg/gaia/supports.py
from gaia.lang import execute
from mypkg.solver import run_cfd


def pressure_field(*, geometry, boundary_condition):
    return execute(
        run_cfd,
        given=[geometry, boundary_condition],
        returns="The CFD run produced pressure field P for the stated geometry and boundary condition.",
    )
```

These functions are the main place where existing package capabilities become Gaia support.

## 4.3 Bridge Constructors

These connect package-level result claims to higher-level scientific claims.

Example:

```python
# mypkg/gaia/bridges.py
from gaia.lang import claim, deduction

pressure_profile_matches_hypothesis = claim(
    "The simulated pressure profile matching criterion is valid for assessing the target hypothesis."
)


def supports_target_hypothesis(*, pressure_field):
    return deduction(
        "The target hypothesis is supported by the simulated pressure profile.",
        given=[pressure_field, pressure_profile_matches_hypothesis],
    )
```

The bridge layer is essential. It prevents `execute()`, `check()`, or `formal_proof()` from being mistaken for direct scientific proof.

---

## 5. API Style Rules

## 5.1 Constructors Return Claims

Gaia-facing wrapper functions should generally return `Claim`, not `Support`.

Good:

```python
def pressure_field(...)-> Claim: ...
def solver_ok(...)-> Claim: ...
def supports_target_hypothesis(...)-> Claim: ...
```

Less preferred for author-facing API:

```python
def pressure_field_support(...)-> Support: ...
```

The reason is ergonomic: claim-returning constructors compose naturally.

## 5.2 Support Must Still Be Explicit Under The Hood

Even though the constructor returns a claim, the system must still create:

- a `Support`
- optional `Witness` entries
- explicit premise / conclusion structure

This preserves reviewability and IR lowering.

## 5.3 No Implicit Function Lifting

The system should not auto-scan a package and conclude:

> this function returns `Claim`, therefore it is Gaia support

Instead, a function becomes part of the Gaia layer only if it is:

- placed in the package's `gaia/` layer
- or wrapped by a dedicated Gaia constructor
- or decorated with an explicit Gaia opt-in decorator

---

## 6. Opt-In Mechanisms

There are three acceptable ways to make an existing Python function part of the Gaia layer.

## 6.1 Wrapper Function

Recommended default.

```python
def pressure_field(...):
    return execute(...)
```

Pros:

- explicit
- readable
- stable
- no decorator magic

## 6.2 Decorator

Acceptable when the author wants tight co-location with implementation.

Sketch:

```python
@gaia_support(family="execute", returns="The solver run produced pressure field P.")
def pressure_field(...):
    ...
```

This is more compact, but also more magical. It should be treated as sugar over the wrapper model, not as the foundational mechanism.

## 6.3 Adapter Registry

Useful for third-party packages or dynamic integration.

Sketch:

```python
register_gaia_support(
    function=run_cfd,
    family="execute",
    returns="The CFD run produced pressure field P.",
)
```

This is primarily for frameworks, not for the default authoring path.

---

## 7. Canonical Adapter Categories

To keep Gaia layers consistent across packages, v6 should document a small set of standard adapter categories.

## 7.1 `claim_from_object`

Purpose:

- expose a package object as a declarative claim

Sketch:

```python
claim_from_object(
    obj,
    *,
    content: str | None = None,
    title: str | None = None,
    **metadata,
) -> Claim
```

Typical uses:

- model definitions
- dataset descriptors
- configuration objects
- test suite identities

## 7.2 `execute`

Purpose:

- expose an execution result as a result claim backed by an execution witness

Typical uses:

- simulations
- parsers
- numerical solvers
- CLI tools
- remote services

`execute` is intentionally backend-agnostic at the Gaia layer. Whether the wrapped procedure eventually calls in-process Python, a CLI tool, or a remote service is execution metadata, not a separate ontology-level category.

## 7.3 `check`

Purpose:

- expose a checker / test / verifier result as an implementation-validity claim

Typical uses:

- property tests
- spec conformance checks
- regression suites
- invariant validators

## 7.4 `formal_proof`

Purpose:

- expose a theorem-checker-accepted proof artifact as a proof-backed claim

Typical uses:

- Lean theorems
- Coq proof artifacts
- Isabelle developments

`formal_proof` stays inside the same execution-backed support model. It is stronger than ordinary execution or validation witnesses, but it is still not a separate top-level ontology.

## 7.5 Bridge Support

Purpose:

- connect low-level package claims to domain-level scientific claims

Typical uses:

- “this benchmark result is relevant”
- “this simulation criterion matches the scientific notion of success”
- “this validated implementation result is sufficient under assumptions H”

---

## 8. Minimal Example

## 8.1 Original Package

```text
fluidlab/
  solver.py
  spec.py
  tests/
```

## 8.2 Gaia Layer

```text
fluidlab/
  solver.py
  spec.py
  tests/
  gaia/
    __init__.py
    claims.py
    supports.py
    bridges.py
```

`claims.py`

```python
from gaia.lang import claim
from fluidlab.spec import DEFAULT_SCHEME

scheme_spec = claim(
    "The package's default numerical scheme is the documented finite-volume discretization.",
    source_object=DEFAULT_SCHEME,
)

regression_suite = claim(
    "The package's regression suite covers the documented benchmark regime.",
)
```

`supports.py`

```python
from gaia.lang import check, execute
from fluidlab.solver import run_solver
from fluidlab.tests import check_solver_against_spec


def pressure_field(*, geometry, boundary_condition):
    return execute(
        run_solver,
        given=[geometry, boundary_condition],
        returns="The solver run produced pressure field P for the stated geometry and boundary condition.",
    )


def solver_ok():
    return check(
        check_solver_against_spec,
        given=[scheme_spec, regression_suite],
        returns="The solver implementation satisfies the stated numerical specification on the tested regime.",
    )
```

`bridges.py`

```python
from gaia.lang import claim, deduction

matching_criterion = claim(
    "Agreement between the simulated pressure profile and the target profile is a valid indicator for the stated hypothesis."
)


def target_hypothesis_supported(*, pressure_field_claim, solver_ok_claim):
    return deduction(
        "The target hypothesis is supported under the stated simulation assumptions.",
        given=[pressure_field_claim, solver_ok_claim, matching_criterion],
    )
```

This is the intended v6 layering:

- original package remains ordinary Python
- Gaia layer adds claims
- Gaia layer adds support constructors
- bridge logic stays explicit

---

## 9. Review Model For Package-Local Gaia Layers

The Gaia layer should make review possible at three levels.

## 9.1 Claim Review

Examples:

- the test suite is representative
- the scheme assumptions are valid
- the benchmark setup is relevant

## 9.2 Support Review

Examples:

- the bridge from simulation result to scientific claim is reasonable
- the `noisy_and` support strength is appropriate

## 9.3 Witness Review

Examples:

- the execution backend is trustworthy in this regime
- the checker is aligned with the stated specification
- the run artifact is valid and complete

This is why support-returning wrappers alone are not enough. The Gaia layer must preserve the witness path.

---

## 10. Packaging Guidance

## 10.1 Recommended Export Surface

The package's Gaia entrypoint should usually export:

- public claim adapters
- public support constructors
- top-level scientific conclusions

It should not necessarily export every low-level wrapper.

## 10.2 Naming Guidance

Recommended naming:

- claim adapters: noun phrases
  - `scheme_spec`
  - `regression_suite`
- execution-backed constructors: claim-like nouns
  - `pressure_field()`
  - `solver_ok()`
- bridge constructors: conclusion phrases
  - `target_hypothesis_supported()`

This keeps the call graph readable.

## 10.3 Versioning Guidance

Adding a Gaia layer to an existing package should usually be treated as:

- minor change if it only adds new Gaia exports
- major change if it changes the meaning of existing exported Gaia claims

---

## 11. Non-Goals

This document does not define:

- automatic introspection of arbitrary package functions
- execution cache protocols
- witness persistence schema
- `gaia run` runtime artifact contract
- protected IR representation for execution-backed support

Those belong to later layers.

---

## 12. Summary

Gaia v6 should make it natural to say:

> “I do not need to rewrite my Python package. I add a thin `gaia/` layer that wraps selected objects as claims and selected functions as explicit support constructors.”

That is the right level of Curry-Howard influence:

- author-facing constructors return claims
- support remains explicit underneath
- witness remains reviewable
- execution remains an external producer of witness, not the logical core itself
