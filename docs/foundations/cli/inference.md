---
status: current-canonical
layer: cli
since: v5-phase-2
---

# Inference Pipeline

## Overview

`gaia infer` runs local (or cross-package joint) inference on a compiled
knowledge package. External priors come from **claim metadata** set by
`priors.py` during compilation, plus dependency beliefs injected through
`node_priors`. Legacy `reason+prior` DSL pairing is still recognized for
compatibility, but new v0.5 packages should not use it as the primary prior
assignment path.

Command signature:

```
gaia infer [PATH] [--depth N]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PATH` | `.` | Path to the knowledge package directory |
| `--depth N` | `0` | Dependency depth for joint inference. `0` = flat prior injection, `1` = direct deps, `2+` = recursive transitive deps, `-1` = all transitive deps |

Pipeline:

```
ensure_package_env()          # uv sync --quiet
  -> load_gaia_package()      # import package module, collect declarations
  -> apply_package_priors()   # inject priors.py entries into Knowledge.metadata["prior"]
  -> compile                  # produce LocalCanonicalGraph
  -> staleness check          # verify ir_hash matches .gaia/ir_hash
  -> validate IR structure
  -> lower to factor graph    # lower_local_graph(), optionally merge deps
  -> validate factor graph
  -> InferenceEngine.run()    # auto-select JT / GBP / loopy BP
  -> write .gaia/beliefs.json
```

Source: `gaia/cli/commands/infer.py`

## Prior Sources And MaxEnt Contract

External priors are **embedded in claim metadata** at compile time and read by
the lowering layer (`lower_local_graph()`) from `metadata["prior"]`. There is no
separate parameterization or review sidecar step.

The v0.5 contract is:

- external priors belong only on independent probabilistic inputs to exported goals;
- root `observe(...)` claims count as independent inputs because grounding and review are qualitative, not numeric;
- derived claims and helper claims do not receive manual priors;
- claims without an explicit unary prior do not get a synthetic `0.5` factor. They remain unconstrained variables, and the exact-inference layer applies maximum entropy over the remaining independent degrees of freedom subject to declared hard constraints.

### Priority order

The lowering layer (`gaia/bp/lowering.py`) resolves each claim's prior with
two branches depending on whether the claim is a **relation conclusion**
(conclusion of EQUIVALENCE, CONTRADICTION, COMPLEMENT, or IMPLICATION):

**Relation conclusions:**

```
node_priors > structural default (1 - CROMWELL_EPS)
```

If `node_priors` has an explicit override, use it. Otherwise, the structural
default `1 - CROMWELL_EPS` applies unconditionally — `metadata["prior"]` is
**not consulted**. Relation conclusions are asserted true by construction; any
author-supplied prior on them is ignored unless injected via `node_priors`.

**Regular claims:**

```
node_priors > metadata["prior"] > no unary prior
```

1. **`node_priors`** — explicit overrides passed into `lower_local_graph()`,
   used for foreign node flat prior injection from `dep_beliefs/` (see below).
2. **`metadata["prior"]`** — set by `priors.py` or legacy `reason+prior` DSL pairing.
3. **No unary prior** — the variable is left free; MaxEnt is applied at the joint-distribution level, not by multiplying every unassigned claim by an independent 0.5 prior factor.

### priors.py

Each package may contain a `priors.py` module that exports a `PRIORS` dict
mapping Knowledge objects to `(prior_value, justification_string)` tuples.
`apply_package_priors()` injects these values into `Knowledge.metadata["prior"]`
and `Knowledge.metadata["prior_justification"]` **before** compilation.

```python
# my_package/priors.py
from my_package import claim_A, claim_B

PRIORS = {
    claim_A: (0.7, "Widely reproduced experimental result"),
    claim_B: (0.4, "Preliminary evidence, single study"),
}
```

Rules:

- `priors.py` must NOT declare new Knowledge objects — it may only reference
  claims already declared by the package.
- Prior values must satisfy Cromwell's rule: `[CROMWELL_EPS, 1 - CROMWELL_EPS]`
  where `CROMWELL_EPS = 1e-3`.
- Justification must be a string.
- No-op when the package has no `priors.py`.

Source: `gaia/cli/_packages.py :: apply_package_priors()`

### Legacy reason+prior DSL pairing

Older strategy and operator DSL functions accept paired `reason` + `prior`
keyword arguments. This path is retained for compatibility; new packages should
prefer `priors.py` for independent input priors and action/relation verbs for
warrants.

```python
from gaia.lang import support, equivalence

# Legacy soft support with warrant prior
support([A, B], C, reason="Evidence converges", prior=0.85)

# Legacy operator with helper claim prior
equivalence(X, Y, reason="Same underlying mechanism", prior=0.99)
```

The pairing is enforced: providing `reason` without `prior` (or vice versa) is
an error. In new v0.5 authoring, do not assign external priors to derived,
structural, relation-helper, or generated-helper claims.

## Flat Prior Injection (`--depth 0`)

With the default `--depth 0`, foreign knowledge nodes (nodes whose QID does not
start with the local `{namespace}:{package}::` prefix) receive flat upstream
beliefs from `.gaia/dep_beliefs/`:

```
.gaia/dep_beliefs/
  dep_package_1.json    # beliefs.json downloaded from upstream
  dep_package_2.json
```

`collect_foreign_node_priors()` scans these files and builds a
`{knowledge_id: belief}` dict. For each foreign node in the compiled graph,
if a matching upstream belief exists, it is passed as `node_priors` to
`lower_local_graph()`, overriding any other prior source.

This is the lightweight mode: the local package uses upstream **conclusions**
as fixed priors without loading the upstream reasoning structure.

Source: `gaia/cli/_packages.py :: collect_foreign_node_priors()`

## Joint Cross-Package Inference (`--depth > 0`)

With `--depth N` (N > 0), dependency packages' compiled factor graphs are merged
for joint inference instead of using flat prior injection.

### Dependency discovery

`load_dependency_compiled_graphs()` scans `[project].dependencies` in
`pyproject.toml` for entries ending in `-gaia`, locates each dependency's
`.gaia/ir.json`, and deserializes to `LocalCanonicalGraph`.

- `--depth 1`: direct dependencies only.
- `--depth 2+`: recursive transitive dependencies, decrementing depth at each
  level.
- `--depth -1`: unlimited — all transitive dependencies.
- Dependencies are deduplicated by `{namespace}:{package_name}` prefix.

### Graph merging

Each dependency graph is lowered to a `FactorGraph` independently, then
`merge_factor_graphs()` combines them with the local factor graph:

1. **Dep variables first** — a dependency graph is authoritative for variables
   it owns (those starting with its QID prefix). Foreign references in the dep
   graph may carry neutral placeholder priors.
2. **Local variables second** — the local graph overwrites only locally-owned
   nodes (those starting with `local_prefix`).
3. **Dep factors** are copied with prefixed IDs (`dep_{import_name}_{fid}`) to
   avoid collision.
4. **Local factors** are copied with `local_` prefix.

The merged graph is then run through the inference engine as a single factor
graph, allowing beliefs to propagate across package boundaries.

Source: `gaia/bp/lowering.py :: merge_factor_graphs()`

## Output Format

Output is written to `.gaia/beliefs.json` under the package directory.

### `beliefs.json`

```json
{
  "ir_hash": "sha256:...",
  "gaia_lang_version": "0.3.0",
  "beliefs": [
    {
      "knowledge_id": "github:my_pkg::my_claim",
      "label": "my_claim",
      "belief": 0.683
    }
  ],
  "diagnostics": {
    "converged": true,
    "iterations_run": 12,
    "max_change_at_stop": 3.2e-7,
    "treewidth": -1,
    "belief_history": {
      "github:my_pkg::my_claim": [0.7, 0.691, 0.685, "..."]
    },
    "direction_changes": {
      "github:my_pkg::my_claim": 0
    }
  }
}
```

| Field | Purpose |
|-------|---------|
| `ir_hash` | Content hash of the compiled IR. Must match `.gaia/ir_hash` when downstream commands (`gaia render`, `gaia register`) verify freshness. |
| `gaia_lang_version` | Which `gaia-lang` version produced these beliefs. Useful for detecting numerical drift across patch releases. |
| `beliefs` | Array sorted by `knowledge_id`. Includes only knowledge nodes present in the compiled graph (internal auxiliary variables are excluded). Each entry has `knowledge_id`, `label`, and posterior `belief` (P(claim=1)). |
| `diagnostics` | BP convergence information — see Inference Engine section below. |

## Staleness Detection

Before lowering, `gaia infer` performs a three-part staleness check:

1. `.gaia/ir_hash` must exist — otherwise `gaia compile` has not been run.
2. `.gaia/ir.json` must exist and be valid JSON.
3. The stored `ir_hash` must match the freshly recompiled `compiled.graph.ir_hash`,
   AND the stored IR JSON must match the fresh compiled JSON byte-for-byte.

If any check fails, the command exits with an error directing the user to run
`gaia compile` again. This ensures inference always runs against the latest
compiled artifacts.

## Inference Engine

`InferenceEngine` (in `gaia/bp/engine.py`) automatically selects the best
algorithm based on the factor graph's treewidth:

| Method | Condition (auto mode) | Exactness | Typical use |
|--------|----------------------|-----------|-------------|
| **JT** (Junction Tree) | treewidth <= 15 | Exact | Most Gaia packages (n <= 200, tw <= 10) |
| **GBP** (Generalized BP) | 15 < treewidth <= 30 | Near-exact | Graphs with identifiable short cycles |
| **BP** (Loopy BP) | treewidth > 30 | Approximate | Very large/dense graphs |
| **Exact** (brute-force) | forced only, <= 26 vars | Exact | Testing/validation |

For Gaia's typical factor graphs (n <= 200 variables, treewidth <= 10), JT is
almost always selected, giving exact results in milliseconds.

### Default parameters

| Parameter | Value | Description |
|-----------|-------|-------------|
| `bp_damping` | 0.5 | Blending coefficient alpha. 1.0 = full replacement, 0.5 = half-step. |
| `bp_max_iter` | 200 | Upper bound on sweep iterations |
| `bp_threshold` | 1e-8 | Convergence threshold |
| `jt_max_treewidth` | 15 | JT selected when treewidth <= this |
| `gbp_max_treewidth` | 30 | GBP selected when treewidth <= this |

### Convergence

BP stops early when the maximum belief change across all variables falls below
`bp_threshold`. If `bp_max_iter` is exhausted without convergence, the result
is returned with `diagnostics.converged = False`.

### Diagnostics

The `diagnostics` object in `beliefs.json` records:

- `converged` — whether inference reached the convergence threshold
- `iterations_run` — number of complete iterations (0 for JT exact)
- `max_change_at_stop` — maximum belief change in the final iteration
- `treewidth` — estimated treewidth of the factor graph (-1 if not computed)
- `belief_history` — `{var_id: [belief_at_iter_0, ...]}` per variable
- `direction_changes` — `{var_id: count}` of sign reversals in belief deltas
  (high counts indicate oscillation)

### Console output

After inference completes, `gaia infer` prints:

```
Inferred 42 beliefs
Method: JT (exact), 3ms
Output: /path/to/package/.gaia/beliefs.json
```

## Lowering to Factor Graph

`lower_local_graph()` in `gaia/bp/lowering.py` converts a
`LocalCanonicalGraph` into a `FactorGraph` suitable for inference.

### Variable nodes

Each `type=claim` Knowledge becomes a variable node. Prior resolution follows
the priority order described in the Prior Sources section above.

Helper claims (labels starting with `__`) are excluded from user-supplied
`node_priors` — their priors are determined by operator semantics (relation
operators get `1 - CROMWELL_EPS`, compositional operators get `0.5`).

### Factor types

The `FactorType` enum defines 8 factor types:

| FactorType | Parameters | Arity constraint |
|------------|-----------|-----------------|
| `IMPLICATION` | none (deterministic) | exactly 1 premise |
| `CONJUNCTION` | none (deterministic) | 2+ premises |
| `DISJUNCTION` | none (deterministic) | 2+ premises |
| `EQUIVALENCE` | none (deterministic) | exactly 2 premises |
| `CONTRADICTION` | none (deterministic) | exactly 2 premises |
| `COMPLEMENT` | none (deterministic) | exactly 2 premises |
| `SOFT_ENTAILMENT` | `p1`, `p2` (require `p1 + p2 > 1`) | exactly 1 premise |
| `CONDITIONAL` | `cpt` (length `2^k`) | 1+ premises |

Deterministic factors use Cromwell-softened potentials (`HIGH = 1 - EPS`,
`LOW = EPS`).

### Strategy lowering

Strategies are lowered by type:

- **`infer`**: `CONDITIONAL` factor with full CPT. When
  `infer_use_degraded_noisy_and=True`, falls back to
  `CONJUNCTION + SOFT_ENTAILMENT`.
- **`deduction`**: `CONJUNCTION` for multiple premises, then a hard
  `CONDITIONAL` implication with CPT `[0.5, 1 - EPS]`. Review gates whether
  the warrant enters the information set; it does not supply a numeric prior.
- **`support`**: soft implication via `SOFT_ENTAILMENT`; legacy `prior=`
  folds into its effective `p1`.
- **`noisy_and`**: `CONJUNCTION + SOFT_ENTAILMENT`. Single premise omits
  conjunction.
- **Other named formal types** (elimination, etc.): auto-formalized via
  `formalize_named_strategy()`, then expanded to deterministic factors.
- **`FormalStrategy`**: each operator maps to a deterministic factor via
  `_OPERATOR_MAP`.
- **`CompositeStrategy`**: recursively lowers each sub-strategy.

Reference: [Lowering](../gaia-ir/07-lowering.md)

## Package Environment Setup

Before loading the package, `ensure_package_env()` runs `uv sync --quiet` in
the package directory. This ensures all dependencies (including other `-gaia`
packages) are installed and importable. Skipped when `pyproject.toml` is absent
or `uv` is not on `$PATH`. Failures are non-fatal.
