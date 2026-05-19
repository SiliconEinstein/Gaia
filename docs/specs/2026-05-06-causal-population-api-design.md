# Causal Extension A — Population API

> **Status:** Target design (proposal)
> **Date:** 2026-05-06
> **Scope:** Add `gaia.causal.Population` — a consumer-layer wrapper that runs the per-instance interventional primitives from the Mechanism design (`do().query()`, `ate()`) over a `Domain`'s members and reduces the results to population-level summaries.
> **Depends on:** `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` (Mechanism as first-class Knowledge type).
> **Non-goals:** Population-level interventions in Pearl's super-population sense (`P(Y | do(X = x))` integrated against an unspecified individual distribution); structure transport across populations (covered by Extension C); structural CATE estimation from observed data.

---

## 0. Why this is one PR, not a roadmap entry

`docs/specs/2026-05-06-causal-mechanism-first-class-design.md` (the Mechanism spec, hereafter "Mech") §5.2 already grounds a universal mechanism `forall(p, mechanism(X(p), Y(p)))` per instance — every `v ∈ Domain.members` becomes a concrete `(@var:…:X_{digest(v)}, @var:…:Y_{digest(v)})` pair with its own `CausalFactor`. Mech §11 explicitly defers "what happens if 30% of the population is intervened on" — that is super-population semantics and stays out.

**But "for each Person, what is `P(Cancer | do(Smokes=1))`?" needs no new BP capability** — it is `len(Domain.members)` independent calls to Mech §7.4 `compute()`. Reducing those results to (a) a vector keyed by member, (b) a mean across members, (c) a histogram, or (d) a subgroup-restricted mean is a pure consumer-layer concern.

Implementing this as part of Mech (PR #533) would have made that PR larger and would have conflated "first-class causal IR" with "population reduce convenience". Implementing it as a follow-up spec lets each PR review focus.

**This spec adds zero IR, zero BP, zero compiler changes. It is a single new module `gaia/causal/population.py` plus tests.**

---

## 1. Architectural Position

```
Mech §5.2 per-instance grounding
  Domain Person = {alice, bob, carol}
  ↓ compiler emits
  per-instance Mechanism × |Person.members|
  ↓ Mech §7.4 compute(...)
  per-instance CausalQueryResult
                                    ↑
                                    │  reduce
                                    │
                                  ┌─┴─┐
                                  │ A │  Population (this spec)
                                  └───┘
                                    ↓
                            PopulationATEResult
                            PopulationHistogram
                            SubgroupATEResult
```

`Population` reads compiled artifacts via the same `pkg_or_artifact` argument Mech §7.2 `build_dag` already accepts. It does not write IR. It does not modify `FactorGraph`. It does not introduce new `KnowledgeType`s.

---

## 2. Public API

### 2.1 `Population` constructor

```python
# gaia/causal/population.py
from dataclasses import dataclass
from typing import Callable, Iterable

from gaia.causal.dag import build_dag, CausalDAG
from gaia.causal.intervene import compute, CausalQueryResult
from gaia.lang import Variable, Domain

@dataclass(frozen=True)
class Population:
    """A view over a Domain's members for batched causal queries.

    A Population is a read-only handle pairing a compiled package artifact
    with a Domain. All methods iterate the domain's members and dispatch
    per-instance queries through gaia.causal.intervene.compute().
    """
    pkg: object                # CollectedPackage or compiled artifact
    domain: Domain
    member_filter: Callable[[str], bool] | None = None
    _dag: CausalDAG | None = None    # cached on first access

    @property
    def members(self) -> tuple[str, ...]:
        """Iterate domain members, applying member_filter if present."""
        all_members = tuple(self.domain.members)
        if self.member_filter is None:
            return all_members
        return tuple(m for m in all_members if self.member_filter(m))
```

### 2.2 Subgroup restriction

```python
    def subgroup(self, predicate: Callable[[str], bool]) -> "Population":
        """Return a Population restricted to members where predicate(m) is True.

        Composable: pop.subgroup(over_60).subgroup(female) chains predicates.
        """
        if self.member_filter is None:
            new_filter = predicate
        else:
            existing = self.member_filter
            new_filter = lambda m: existing(m) and predicate(m)
        return Population(
            pkg=self.pkg,
            domain=self.domain,
            member_filter=new_filter,
            _dag=self._dag,    # DAG is package-scoped, survives subgroup
        )
```

### 2.3 Per-instance helpers

```python
    def per_instance(
        self,
        cause_var: Variable,
        effect_var: Variable,
        cause_value: int,
    ) -> dict[str, CausalQueryResult]:
        """For each member m, compute P(effect_var(m)=1 | do(cause_var(m)=cause_value)).

        Returns a dict member_id -> CausalQueryResult, keyed by raw domain
        member id (not CNID). Result CNIDs are recoverable from each result's
        target_id field if needed.
        """
        out: dict[str, CausalQueryResult] = {}
        for m in self.members:
            cnid_cause = _instance_cnid(cause_var, m, self.domain, self.pkg)
            cnid_effect = _instance_cnid(effect_var, m, self.domain, self.pkg)
            out[m] = compute(
                self.pkg,
                intervention={cnid_cause: cause_value},
                target=cnid_effect,
            )
        return out
```

`_instance_cnid` resolves an `(author Variable, domain member id)` pair to the synthesized CNID per Mech §3 / §5.5. It is shared with Mech §7.4 — exposed in `gaia.causal.intervene` if not already.

### 2.4 Population ATE

```python
@dataclass(frozen=True)
class PopulationATEResult:
    domain_name: str
    n_members: int
    n_filtered_out: int                    # |all members| − |evaluated members|
    cause_var: str                         # author symbol
    effect_var: str                        # author symbol
    per_instance_ate: dict[str, float]     # member_id -> ATE_m
    mean_ate: float                        # arithmetic mean over evaluated members
    audit_digests: tuple[str, ...]         # one per per-instance compute(),
                                           # in member iteration order


    def histogram(self, bins: int = 20) -> tuple[tuple[float, float], ...]:
        """Return ((bin_low, count), ...) of per-instance ATEs."""
        ...

class Population:
    ...

    def ate(
        self,
        cause_var: Variable,
        effect_var: Variable,
    ) -> PopulationATEResult:
        """Compute per-instance ATE = P(effect=1|do(cause=1)) − P(effect=1|do(cause=0))
        for each member; reduce to a population-level mean.

        Mathematical reading: this is the per-instance ATE *averaged over
        the materialized member set*. It is NOT Pearl's super-population
        ATE — it makes no claim about a population beyond the Domain's
        listed members. See §5.
        """
        do1 = self.per_instance(cause_var, effect_var, cause_value=1)
        do0 = self.per_instance(cause_var, effect_var, cause_value=0)
        per_instance_ate = {
            m: do1[m].belief - do0[m].belief
            for m in self.members
        }
        n = len(per_instance_ate)
        if n == 0:
            raise EmptyPopulationError(...)
        mean = sum(per_instance_ate.values()) / n
        return PopulationATEResult(
            domain_name=self.domain.name,
            n_members=n,
            n_filtered_out=len(self.domain.members) - n,
            cause_var=cause_var.symbol,
            effect_var=effect_var.symbol,
            per_instance_ate=per_instance_ate,
            mean_ate=mean,
            audit_digests=tuple(
                do1[m].factor_graph_digest for m in self.members
            ) + tuple(
                do0[m].factor_graph_digest for m in self.members
            ),
        )
```

### 2.5 Population histogram of beliefs (no ATE)

```python
    def histogram(
        self,
        target_var: Variable,
        *,
        do: dict[Variable, int] | None = None,
    ) -> PopulationHistogramResult:
        """For each member, compute P(target=1 | do=...); collect distribution.
        With do=None, this is observational P(target=1) per instance."""
        ...

@dataclass(frozen=True)
class PopulationHistogramResult:
    target_var: str
    intervention: dict[str, int]               # author-symbol-keyed
    per_instance_belief: dict[str, float]
    mean: float
    stddev: float
    audit_digests: tuple[str, ...]
```

### 2.6 Subgroup CATE-lite

`Population.subgroup(p).ate(...)` already gives subgroup ATE — that is the entire CATE-lite contract for v0.6.x. No new method.

```python
older = pop.subgroup(lambda m: members_metadata[m]["age"] >= 60)
younger = pop.subgroup(lambda m: members_metadata[m]["age"] < 60)
older_ate = older.ate(cause=Smokes, effect=Cancer)
younger_ate = younger.ate(cause=Smokes, effect=Cancer)
# Compare older_ate.mean_ate vs younger_ate.mean_ate
```

`members_metadata` is **author-side data** — Gaia does not know member ages. Subgroup predicates take a `member_id: str` and return bool; resolving them to attributes is the author's responsibility. v0.6 considered baking attribute lookup into Domain (`Domain(name="Person", members=[{"id":"alice","age":62}, ...])`) but rejected — that is a Lang-level enrichment, separate spec.

---

## 3. Errors

```python
# gaia/causal/errors.py (additions)
class EmptyPopulationError(Exception):
    """Subgroup filter or empty Domain produced zero members to evaluate."""

class PopulationVariableUngroundedError(Exception):
    """Variable passed to Population.ate / .histogram is not per-instance grounded
    in any mechanism over the given Domain. Author should declare:
        mechanism(cause=X, effect=Y, forall='p', domain=Person, ...)
    or pass a Variable that already participates in such a universal mechanism."""
```

`PopulationVariableUngroundedError` is the most important diagnostic — without it, authors who pass a top-level (non-quantified) Variable get a confusing CNID-resolution error. The check runs in `_instance_cnid`: if no instance CNID exists for `(var, member)` in the compiled artifact, raise this with a hint pointing at Mech §4.3 universal-mechanism syntax.

---

## 4. Integration with `gaia check causal`

One new rule:

| Rule | Severity | Triggered |
|---|---|---|
| Population query targets non-grounded Variable | Error | Static analysis of authored `Population(...).ate(X, Y)` calls finds an `X` or `Y` not appearing in any `mechanism(forall=, domain=)` over the Population's `Domain` |

This rule is opt-in: it only triggers when an author actually writes `Population(...)` somewhere in their package code. Pure runtime use (no authored `Population` in source) needs no static check.

---

## 5. Semantics — what mean_ate is and is not

`PopulationATEResult.mean_ate` is the **arithmetic mean of per-instance ATEs over the materialized member set**. Unpacked:

- "Per-instance" — Mech §5.3 chose Strategy A (full individual grounding); each member of `Domain.members` has its own causal sub-DAG. ATE is well-defined per instance.
- "Materialized" — only `Domain.members` listed at compile time count. Adding a member later changes the population.
- "Arithmetic mean" — equal weight per member. No weighting by some "true population frequency". v0.6 has no concept of sampling weight.

**What this is NOT.** Pearl's super-population ATE `E_U[Y_x − Y_{x'}]` integrates against an exogenous-noise distribution over a hypothetical infinite super-population. v0.6 has no exogenous noise variables (Mech §2.3 explicitly notes this), so super-population ATE has no operational meaning. `mean_ate` is the **finite-sample analog** under per-instance grounding — useful for symmetric DAGs where every instance has the same parameters (then `mean_ate` equals the per-instance ATE), and as a reduce when instance parameters do vary.

If a future v0.7 adds exogenous noise (Counterfactual extension, Spec B), `mean_ate` would still be well-defined under the same arithmetic-mean reduction, but a separate `superpopulation_ate()` method could be added at that time.

---

## 6. Implementation Notes

### 6.1 Caching

Per-instance `compute()` calls in `ate()` are independent — could parallelise across `Domain.members`. v0.6.1 skips parallelism (deterministic order, predictable audit). `concurrent.futures.ThreadPoolExecutor` could be added behind an opt-in flag in v0.6.2 if profiling shows it helps; not in this spec.

`Population._dag` caches the result of `build_dag(pkg)` because every per-instance call would otherwise rebuild it. The cache is invalidated on `subgroup()` only if the subgroup constructor explicitly resets it (currently it doesn't — DAG is package-scoped, not member-scoped).

### 6.2 Determinism & audit

`per_instance` iterates `self.members` in `Domain.members` order — deterministic across runs. `PopulationATEResult.audit_digests` records one digest per per-instance `compute()`, in iteration order, so a reviewer can re-run any single instance and verify bit-equality.

### 6.3 No new lowering

The compiler already emits per-instance `Mechanism` knowledge for universal mechanisms (Mech §5.2). `Population` walks those at runtime; no new compiler pass.

---

## 7. Examples

### 7.1 Basic per-instance + mean ATE

```python
from gaia.lang import Bool, Domain, Variable
from gaia.lang.dsl.causal import mechanism
from gaia.causal import Population

Person = Domain(name="Person", members=["alice", "bob", "carol"])
Smokes = Variable(symbol="Smokes", domain=Bool)
Cancer = Variable(symbol="Cancer", domain=Bool)

mechanism(
    cause=Smokes, effect=Cancer,
    forall="p", domain=Person,
    cpd=(0.15, 0.05),
    label="smoking_causes_cancer",
)

# After compile:
pop = Population(pkg=compiled_package, domain=Person)
result = pop.ate(cause_var=Smokes, effect_var=Cancer)

assert result.n_members == 3
assert set(result.per_instance_ate.keys()) == {"alice", "bob", "carol"}
# Each instance has identical CPD parameters, so per-instance ATE = 0.15 - 0.05 = 0.10
# mean_ate = 0.10
```

### 7.2 Subgroup CATE-lite

```python
metadata = {"alice": {"age": 62}, "bob": {"age": 35}, "carol": {"age": 70}}
older = pop.subgroup(lambda m: metadata[m]["age"] >= 60)
older_ate = older.ate(cause_var=Smokes, effect_var=Cancer)
assert older_ate.n_members == 2
assert older_ate.n_filtered_out == 1
# Same DAG, same parameters → mean_ate still 0.10. Subgroups would diverge
# only if the DAG had per-member parameter variation (e.g. age-dependent CPDs,
# which v0.6 doesn't natively support — that needs Lang-level
# domain-attribute-conditioned mechanisms, separate spec).
```

### 7.3 Belief histogram under intervention

```python
hist = pop.histogram(target_var=Cancer, do={Smokes: 1})
# hist.per_instance_belief maps member -> P(Cancer=1 | do(Smokes=1))_member
# hist.mean / hist.stddev summarize the distribution
```

### 7.4 Empty population diagnostic

```python
no_one = pop.subgroup(lambda m: False)
no_one.ate(Smokes, Cancer)
# Raises EmptyPopulationError: "Subgroup filter on Population(domain='Person',
# n=3) selected 0 members. Cannot compute ATE."
```

---

## 8. Out of Scope

- **Super-population ATE** (`E_U[Y_x − Y_{x'}]`) — needs exogenous noise variables, not in v0.6.
- **Per-member parameter variation** — `mechanism(cause=X, effect=Y, forall='p', cpd_fn=lambda m: (...))` — Lang-level work, separate spec.
- **Continuous outcomes** — Population reduce works for any scalar-valued query; v0.6 BP is binary, so `belief` is in [0, 1]. When BP supports continuous, `mean_ate` reduce trivially extends.
- **Sampling-weighted reduce** — equal weight per member only. Adding `weights: dict[str, float]` later is non-breaking.
- **Dataset-driven CATE** — that needs DoWhy/EconML, fundamentally different.
- **Cross-population transport** — covered by Extension C (y0 transport adapter).

---

## 9. Implementation milestones

Single PR. Estimated 1 week.

- `gaia/causal/population.py` — Population class, three result dataclasses.
- `gaia/causal/errors.py` — two new exception types.
- `gaia/causal/intervene.py` — expose `_instance_cnid` helper if not already public.
- `gaia/cli/check_causal.py` — one rule (population-query-target-not-grounded).
- Tests: per-instance dispatch with three-member Domain; subgroup chaining; empty-population error; histogram correctness; audit-digest-per-instance presence; mean-ATE correctness on hand-computed symmetric DAG.
- Docs: short user guide section under `docs/foundations/causal/`.

No IR migration. No BP changes. No compiler changes.

---

## 10. Prior-Art Anchors

- `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` — supplies the per-instance grounding (§5) and `compute()` primitive (§7.4) this spec consumes.
- y0's `Population` / `Distribution` abstractions — explicitly **not** imported (Mech §14 records this); y0's split distinguishes super-populations and is needed for transport theorems, not for per-instance reduce.
- DoWhy / EconML — solve a different problem (data-driven estimation).
- PR #505 — `Domain` and `Variable` definitions this spec relies on.
