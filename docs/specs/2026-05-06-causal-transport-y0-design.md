# Causal Extension C — Distribution Transport via y0

> **Status:** Target design (proposal)
> **Date:** 2026-05-06
> **Scope:** Add symbolic transport-identifiability queries to `gaia.causal` via y0's selection-diagram and transportability theorems. Given a causal DAG learned/declared in population A and a query about population B, determine whether the query is transportable and return the identifying functional if so. This is a **pure adapter** — no numeric BP computation, no new IR, no new lowering.
> **Depends on:** `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` (Mechanism as first-class Knowledge type, particularly §7.2 CausalDAG and §8 y0 adapter pattern).
> **Non-goals:** Numeric transport estimation from data (that needs observational datasets, which Gaia doesn't have); selection bias correction in a single population (that's a different y0 API surface); meta-transportability (transporting across 3+ populations).

---

## 0. Why This Is One Spec, Not a Roadmap Entry

y0 already implements Pearl & Bareinboim's transportability theorems (Bareinboim & Pearl 2014, "Transportability from Multiple Environments with Limited Experiments"). The algorithm takes:
- A causal DAG (possibly with selection nodes `S`)
- A source population Π (where experiments or mechanisms are known)
- A target population Π* (where we want to answer a query)
- A query `P(Y | do(X))` in Π*

and returns either:
- "Transportable" + an identifying functional in terms of Π's distributions
- "Not transportable" + an obstruction witness

Gaia already has:
- `CausalDAG` (Mech §7.2) — a NetworkX-backed DAG
- y0 adapter pattern (Mech §8) — lazy-import, optional extra, `MissingDependencyError` on missing dep

**This spec is just wiring.** The hard work (transportability algorithm) is in y0; Gaia's job is to:
1. Translate `CausalDAG` → y0's `NxMixedGraph` (already done for identification in Mech §8)
2. Accept author declarations of "this mechanism was observed in population A, that one in population B"
3. Call y0's `transport()` and wrap the result

No new BP. No new IR `KnowledgeType`. No new compiler pass. Pure consumer-layer adapter, ~200 LoC.

---

## 1. Architectural Position

```
Mech §7.2   CausalDAG (NetworkX DiGraph)
              ↓
            y0.graph.NxMixedGraph (already in Mech §8)
              ↓
            y0.algorithm.transport.transport(
                graph, source_data, target_query
            )
              ↓
            TransportResult (this spec)
```

This spec adds:
- `gaia/causal/adapters/transport.py` — new module under the `adapters/` namespace established by Mech §8.
- DSL sugar for declaring "mechanism M was learned in population Π" — a metadata annotation, not a new IR field.
- `TransportResult` dataclass wrapping y0's output.

It does **not** add:
- New `Mechanism` fields (population membership is metadata, not structural)
- New BP factors or variables
- New compiler lowering

---

## 2. The Problem — What Transport Solves

**Setup.** You have:
- A causal DAG over variables `{X, Y, Z, ...}`
- Some mechanisms in the DAG were learned/declared in **population A** (e.g., a clinical trial in the US)
- You want to answer a causal query in **population B** (e.g., the same intervention applied in Europe)

**Question.** Is `P_B(Y | do(X = x))` computable from:
- The DAG structure (assumed the same across populations)
- The mechanisms known in population A
- Observational data in population B (if available)

Pearl & Bareinboim's answer: **sometimes yes, sometimes no**, and there's an algorithm to decide. When yes, the algorithm returns a formula expressing `P_B(Y | do(X))` in terms of `P_A(...)` and `P_B(...)` terms.

**Gaia's use case.** Authors declare mechanisms in one context (e.g., "smoking causes cancer, learned from US data") and want to know: "Can I use this to reason about a European population where smoking rates differ?" This spec gives them a **symbolic yes/no + formula**, not a numeric answer (numeric needs data, which Gaia doesn't have).

---

## 3. Authoring Surface — Population Membership

### 3.1 Mechanism-level annotation

```python
from gaia.lang.dsl.causal import mechanism

mechanism(
    cause=Smokes, effect=Cancer,
    cpd=(0.15, 0.05),
    population="US_trial_2020",        # NEW (this spec)
    label="smoking_causes_cancer",
)

mechanism(
    cause=Genetics, effect=Cancer,
    cpd=(0.10, 0.02),
    population="US_trial_2020",
    label="genetics_causes_cancer",
)

mechanism(
    cause=AirPollution, effect=Cancer,
    cpd=(0.08, 0.03),
    population="EU_observational_2021",   # different population
    label="pollution_causes_cancer",
)
```

`population=` is an **optional string tag**. Mechanisms without a `population=` tag are assumed to be "universal" (hold across all populations). The tag is stored in `Mechanism` metadata (not a first-class field — see §4.1).

### 3.2 Query surface

```python
from gaia.causal.adapters.transport import transport_query

result = transport_query(
    pkg=compiled_package,
    source_population="US_trial_2020",
    target_population="EU_observational_2021",
    query_target=Cancer,
    query_intervention={Smokes: 1},
)

if result.transportable:
    print("Transportable!")
    print(result.identifying_functional_latex)
    # e.g., "P*(Y | do(X)) = ∑_Z P(Y | X, Z) · P*(Z)"
else:
    print("Not transportable.")
    print(result.obstruction)
```

`transport_query` is the single entry point. It:
1. Builds the `CausalDAG` from `pkg`
2. Partitions mechanisms by `population` tag
3. Translates to y0's `NxMixedGraph` + selection-diagram conventions
4. Calls y0's `transport()`
5. Wraps the result

---

## 4. IR & Metadata

### 4.1 No new IR field — metadata only

`population` is stored in `Knowledge.metadata["causal"]["population"]` (the same metadata namespace Mech §1.1 retired for CPD parameters, but population is different — it's not structural, it's provenance).

```python
# After compile, a Mechanism Knowledge node looks like:
Knowledge(
    type=KnowledgeType.MECHANISM,
    payload=Mechanism(cause=..., effect=..., cpd=...),
    metadata={
        "causal": {
            "population": "US_trial_2020",   # optional
        },
    },
)
```

Why metadata, not a `Mechanism.population` field?
- Population membership is **provenance**, not **structure**. The DAG shape and CPD parameters are the same; only the "where did we learn this" differs.
- Keeping it in metadata avoids IR schema churn when we later add "learned from dataset X" or "confidence interval [a, b]" — all provenance goes in the same metadata bucket.
- Mech §2.4 validator already allows arbitrary metadata on MECHANISM knowledge; no new validation rule needed.

### 4.2 Compiler pass — no change

`mechanism(population="...")` is lowered by the existing `lower_mechanism.py` (Mech §5.1). The compiler writes the `population` string into `metadata["causal"]["population"]` and moves on. No new CNID synthesis, no new grounding.

---

## 5. Runtime — `gaia/causal/adapters/transport.py`

### 5.1 `TransportResult`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class TransportResult:
    """Result of a transportability query via y0."""
    source_population: str
    target_population: str
    query_target: str                      # Variable symbol or QID
    query_intervention: dict[str, int]     # Variable symbol -> value
    transportable: bool
    identifying_functional_latex: str | None   # y0 Expression.to_latex()
    identifying_functional_python: str | None  # y0 Expression (repr)
    node_map: dict[str, str]               # y0 symbol -> Gaia QID/CNID
    obstruction: str | None                # human-readable reason if not transportable
    source_mechanisms: tuple[str, ...]     # QIDs of mechanisms in source population
    target_mechanisms: tuple[str, ...]     # QIDs of mechanisms in target population
```

### 5.2 `transport_query`

```python
def transport_query(
    pkg,
    source_population: str,
    target_population: str,
    query_target: Variable | str,
    query_intervention: dict[Variable | str, int],
) -> TransportResult:
    """Determine if a causal query is transportable from source to target population.

    Delegates to y0.algorithm.transport.identify_target_outcomes().
    Requires y0 >= 0.2 (current stable release).
    """
    try:
        import y0
        from y0.algorithm.transport import identify_target_outcomes
        from y0.dsl import Variable as Y0Variable
    except ImportError:
        raise MissingDependencyError(
            "Transport queries require y0. Install via: pip install 'gaia[causal-transport]'"
        )

    dag = build_dag(pkg)
    mechanisms = _load_mechanisms(pkg)

    # Partition by population
    source_mechs = [m for m in mechanisms if m.metadata.get("causal", {}).get("population") == source_population]
    target_mechs = [m for m in mechanisms if m.metadata.get("causal", {}).get("population") == target_population]
    universal_mechs = [m for m in mechanisms if "population" not in m.metadata.get("causal", {})]

    # Build y0 graph with selection nodes
    # (y0 convention: selection node S_i indicates population i has access to mechanism i)
    graph = _build_transport_graph(dag, source_mechs, target_mechs, universal_mechs)

    # Translate query to y0 format
    target_var_y0 = _gaia_to_y0_var(query_target)
    intervention_vars_y0 = {_gaia_to_y0_var(k) for k in query_intervention.keys()}
    
    # Build surrogate_outcomes and surrogate_interventions dicts
    # (y0 API: which outcomes/interventions are available in which population)
    surrogate_outcomes = {}
    surrogate_interventions = {}
    
    # Source population has experimental access to source mechanisms
    source_pop_var = Y0Variable(source_population)
    surrogate_outcomes[source_pop_var] = {_mechanism_effect_to_y0(m) for m in source_mechs}
    surrogate_interventions[source_pop_var] = {_mechanism_cause_to_y0(m) for m in source_mechs}
    
    # Universal mechanisms are available in both populations
    for m in universal_mechs:
        effect_y0 = _mechanism_effect_to_y0(m)
        cause_y0 = _mechanism_cause_to_y0(m)
        surrogate_outcomes.setdefault(source_pop_var, set()).add(effect_y0)
        surrogate_interventions.setdefault(source_pop_var, set()).add(cause_y0)

    # Call y0
    y0_result = identify_target_outcomes(
        graph=graph,
        target_outcomes={target_var_y0},
        target_interventions=intervention_vars_y0,
        surrogate_outcomes=surrogate_outcomes,
        surrogate_interventions=surrogate_interventions,
    )

    if y0_result is not None:
        # Transportable
        latex = y0_result.to_latex()
        python_repr = repr(y0_result)
        obstruction = None
        transportable = True
    else:
        # Not transportable
        latex = None
        python_repr = None
        obstruction = "Not identifiable from available surrogate data. y0's identify_target_outcomes returned None."
        transportable = False

    return TransportResult(
        source_population=source_population,
        target_population=target_population,
        query_target=_resolve_target(query_target),
        query_intervention={_resolve_target(k): v for k, v in query_intervention.items()},
        transportable=transportable,
        identifying_functional_latex=latex,
        identifying_functional_python=python_repr,
        node_map=_build_node_map(graph),
        obstruction=obstruction,
        source_mechanisms=tuple(m.qid for m in source_mechs),
        target_mechanisms=tuple(m.qid for m in target_mechs),
    )
```

### 5.3 Selection-diagram construction

y0's transportability algorithm expects a `NxMixedGraph` with **selection nodes** `S_X` for each variable `X` whose mechanism differs across populations. The convention (Bareinboim & Pearl 2014):
- `S_X = 1` means "population has experimental control or knowledge of the mechanism `pa(X) → X`"
- `S_X = 0` means "population only has observational data on `X`"

Gaia's `_build_transport_graph` helper:
1. Starts with the base `CausalDAG` (all directed edges)
2. For each mechanism `M` with `population = source_population`, adds a selection node `S_{M.effect}` with an edge `S_{M.effect} → M.effect`
3. For mechanisms in `target_population`, does the same with a different selection-node label
4. Universal mechanisms (no `population` tag) are treated as "known in both populations" — no selection node

This is a **pure graph transformation**, no BP involved.

---

## 6. Errors

```python
# gaia/causal/errors.py (additions)
class TransportMissingDependencyError(MissingDependencyError):
    """y0 >= 0.2 is required for transport queries. Install via
    pip install 'gaia[causal-transport]'."""

class TransportPopulationNotFoundError(Exception):
    """source_population or target_population string does not match any
    mechanism's population tag in the compiled package."""

class TransportAmbiguousUniversalError(Exception):
    """A mechanism has no population tag, but the query assumes it belongs
    to one population. Author should either tag it explicitly or clarify
    the query."""
```

---

## 7. `pyproject.toml` — New Optional Extra

```toml
[project.optional-dependencies]
causal-transport = [
    "y0>=0.2",   # identify_target_outcomes available in 0.2.x stable
]
```

Separate from `causal-do` (Mech §8) because:
- `causal-do` is for symbolic identification within a single population
- `causal-transport` is for cross-population queries
- Users who only need `do().query()` don't need the transport machinery

Both extras pull y0, but the version pins may diverge in the future.
```

Separate from `causal-do` (Mech §8) because:
- `causal-do` is for symbolic identification within a single population
- `causal-transport` is for cross-population queries
- Users who only need `do().query()` don't need the transport machinery

Both extras pull y0, but the version pins may diverge in the future.

---

## 8. Examples

### 8.1 Basic transportability check

```python
from gaia.lang import Bool, Variable
from gaia.lang.dsl.causal import mechanism
from gaia.causal.adapters.transport import transport_query

Smokes = Variable(symbol="Smokes", domain=Bool)
Cancer = Variable(symbol="Cancer", domain=Bool)
Age = Variable(symbol="Age", domain=Bool)  # simplified to binary for example

# Mechanisms learned in US trial
mechanism(cause=Smokes, effect=Cancer, cpd=(0.15, 0.05), population="US")
mechanism(cause=Age, effect=Cancer, cpd=(0.10, 0.02), population="US")

# Mechanism learned in EU observational study
mechanism(cause=Age, effect=Smokes, cpd=(0.30, 0.10), population="EU")

# After compile:
result = transport_query(
    pkg=compiled_package,
    source_population="US",
    target_population="EU",
    query_target=Cancer,
    query_intervention={Smokes: 1},
)

if result.transportable:
    print(result.identifying_functional_latex)
    # Might output: "P*(Cancer | do(Smokes=1)) = ∑_{Age} P(Cancer | Smokes=1, Age) · P*(Age)"
    # where P is from US, P* is from EU
else:
    print(f"Not transportable: {result.obstruction}")
```

### 8.2 Non-transportable case

```python
# If the Age → Cancer mechanism was also population-specific:
mechanism(cause=Age, effect=Cancer, cpd=(0.10, 0.02), population="US")
mechanism(cause=Age, effect=Cancer, cpd=(0.12, 0.03), population="EU")  # different!

result = transport_query(
    pkg=compiled_package,
    source_population="US",
    target_population="EU",
    query_target=Cancer,
    query_intervention={Smokes: 1},
)

assert not result.transportable
# result.obstruction might say: "Effect of Smokes on Cancer depends on Age mechanism,
# which differs between populations. No valid adjustment set."
```

### 8.3 Universal mechanism (holds across populations)

```python
# Genetics → Cancer is assumed universal (same across all populations)
mechanism(cause=Genetics, effect=Cancer, cpd=(0.08, 0.02))  # no population= tag

# This mechanism is treated as "known in both US and EU" during transport queries
```

---

## 9. Integration with `gaia check causal`

One new rule (opt-in, under `gaia check causal --transport`):

| Rule | Severity | Triggered by |
|---|---|---|
| Transport query references undefined population | Error | `transport_query(source_population="X", ...)` where no mechanism has `population="X"` |
| Ambiguous universal mechanism in transport context | Warning | A mechanism has no `population` tag, but appears on a path between intervention and target in a transport query where populations differ. Hint: tag it explicitly. |

---

## 10. Out of Scope

- **Numeric transport estimation** — computing `P*(Y | do(X))` numerically requires observational data from population Π*, which Gaia doesn't have. This spec only answers "is it transportable?" and "what's the formula?", not "what's the number?".
- **Selection bias correction within a single population** — y0 also handles this (via `recover()`), but it's a different API surface. Separate spec if needed.
- **Meta-transportability** (transporting across 3+ populations with partial overlap) — y0 supports this, but the DSL ergonomics need design. v0.7+ candidate.
- **Continuous variables** — same blocker as Mech §12.
- **Data-driven transport** (learning which mechanisms differ from data) — that's causal discovery + transport, not in Gaia's scope.

---

## 11. Implementation Milestones

Single PR. Estimated 1 week (most of the work is the selection-diagram construction and y0 API wiring; the algorithm itself is in y0).

- `gaia/ir/mechanism.py`: no change (population goes in metadata).
- `gaia/lang/dsl/causal.py`: `population=` kwarg on `mechanism()`.
- `gaia/lang/compiler/lower_mechanism.py`: write `population` into `metadata["causal"]["population"]`.
- `gaia/causal/adapters/transport.py`: `transport_query`, `TransportResult`, `_build_transport_graph`.
- `gaia/causal/errors.py`: three new exception types.
- `gaia/causal/adapters/__init__.py`: re-export `transport_query`, `TransportResult`.
- `pyproject.toml`: `causal-transport` optional extra with `y0>=0.3`.
- `gaia/cli/check_causal.py`: two new rules under `--transport` flag.
- Tests:
  - Transportable case (Bareinboim & Pearl 2014 Example 1).
  - Non-transportable case (Example 2 from same paper).
  - Universal mechanism treated correctly.
  - `TransportPopulationNotFoundError` on typo.
  - y0 missing → `TransportMissingDependencyError`.
- Docs: transport-queries chapter under `docs/foundations/causal/`.

No new BP. No new IR `KnowledgeType`. No new compiler pass beyond metadata write.

---

## 12. Prior-Art Anchors

- Bareinboim & Pearl (2014), "Transportability from Multiple Environments with Limited Experiments" — the algorithm y0 implements and this spec wraps.
- Pearl & Bareinboim (2011), "Transportability of Causal and Statistical Relations: A Formal Approach" — foundational paper.
- y0's `transport()` API — this spec is a thin Gaia-flavored wrapper.
- `docs/specs/2026-05-06-causal-mechanism-first-class-design.md` — Mech (this spec depends on §7.2 CausalDAG, §8 y0 adapter pattern, §14 y0 alignment statement).
- `docs/specs/2026-05-06-causal-population-api-design.md` — Extension A (sibling spec; transport + Population could compose in a future "cross-population ATE" helper, but that needs numeric data).
- `docs/specs/2026-05-06-causal-counterfactual-binary-noise-design.md` — Extension B (sibling spec; transport + counterfactual are orthogonal — one is cross-population, one is cross-world).

---

## 13. Why This Is Easier Than It Sounds

The hard part of transportability (the algorithm) is in y0. Gaia's contribution is:
1. A metadata convention (`population=` tag)
2. A graph transformation (adding selection nodes per y0's convention)
3. A result wrapper

Total Gaia-specific code: ~150-200 LoC. The rest is y0 doing the heavy lifting.

This is the **lightest** of the three extension specs (A/B/C) in terms of Gaia-internal complexity, even though the underlying theory (Pearl & Bareinboim's transportability calculus) is sophisticated. That's the power of a good adapter boundary.
