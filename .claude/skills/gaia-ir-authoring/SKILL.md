---
name: gaia-ir-authoring
description: "Use when constructing a Gaia knowledge package or LocalCanonicalGraph — teaches Python DSL authoring, compilation, validation, registration, and BP inference using the current gaia.lang + gaia.ir + gaia.bp stack."
---

# Gaia IR Authoring

Author Gaia knowledge packages using the Python DSL, compile to validated IR, and optionally run BP inference or register with the official registry.

## When to use

- Creating a new Gaia knowledge package from source material.
- Adding claims, operators, or strategies to an existing package.
- Compiling, validating, or registering a package.
- Running local BP inference on a package's IR.

Do **not** use for: modifying `gaia/ir/`, `gaia/bp/`, or `gaia/lang/` internals; review workflows; LKM server operations.

## Process

You MUST follow these steps in order. Do not skip validation or compilation.

### Step 1: Scaffold the package

Every Gaia package is a standard Python package with `[tool.gaia]` metadata.

```
my-package-gaia/
├── pyproject.toml
├── my_package/
│   └── __init__.py
└── .gaia/               # Created by `gaia compile` — git tracked
    ├── ir.json
    └── ir_hash
```

**pyproject.toml** (all fields required):

```toml
[project]
name = "my-package-gaia"          # Must end with -gaia
version = "1.0.0"
description = "..."
authors = [{name = "..."}]
requires-python = ">=3.12"
dependencies = []                  # Other *-gaia packages if needed

[tool.setuptools.packages.find]
include = ["my_package*"]

[tool.gaia]
namespace = "github"               # Source registry namespace
type = "knowledge-package"         # Required exactly
uuid = "..."                       # Unique UUID v4

[build-system]
requires = ["setuptools>=69.0"]
build-backend = "setuptools.build_meta"
```

**Naming convention:**

| Layer | Format | Example |
|-------|--------|---------|
| GitHub repo | `CamelCase.gaia` | `MendelGenetics.gaia` |
| PyPI name | `kebab-case-gaia` | `mendel-genetics-gaia` |
| Python import | `snake_case` | `mendel_genetics` |

### Step 2: Declare knowledge

Write declarations directly at module top level. Do NOT use a `Package` context manager — the runtime infers package membership automatically from `pyproject.toml`.

```python
# my_package/__init__.py
from gaia.lang import claim, setting, question, support

# Settings — background, no probability
env = setting("Experimental conditions described here.")

# Claims — propositions with truth values
obs_a = claim("Observation A holds under conditions described.")

# Derive a conclusion from premises using an explicit strategy
conclusion = claim("Derived conclusion.")
support([obs_a], conclusion, reason="Observation directly supports conclusion.", prior=0.85)
```

**Rules:**
- Labels are **automatically assigned from Python variable names** by `gaia compile`. Do NOT set `.label` manually.
- Variable names must be valid Python identifiers (`[a-z_][a-z0-9_]*`).
- Variable names must be unique within the package.
- Only `claim` carries probability; `setting` and `question` do not participate in BP.
- Use explicit strategies (`support`, `deduction`, etc.) to connect claims via reasoning.

### Step 3: Add structural operators

Operators encode deterministic logical relations. Each operator function creates the operator AND returns a helper claim. `reason` and `prior` must be paired: both or neither.

```python
from gaia.lang import contradiction, equivalence, complement, disjunction

# Contradiction: ¬(A ∧ B) — cannot both be true
helper = contradiction(claim_a, claim_b,
    reason="Why they conflict", prior=0.99)

# Equivalence: A = B — same truth value
eq = equivalence(claim_x, claim_y,
    reason="Why they are equivalent", prior=0.95)

# Complement: A ⊕ B — opposite truth values (XOR)
comp = complement(claim_p, claim_q,
    reason="Why they are opposites", prior=0.95)

# Disjunction: at least one true
disj = disjunction(hyp_a, hyp_b, hyp_c,
    reason="At least one mechanism", prior=0.9)
```

The returned helper claim can be used as a premise in subsequent strategies.

### Step 4: Add reasoning strategies

#### Leaf strategies (most common)

`support` and `deduction` are the two primary leaf strategies. Both use the directed `implication` operator (conjunction + implication). The difference is semantic: `deduction` is rigid (deterministic), `support` is soft (author-specified prior).

```python
from gaia.lang import support, deduction, compare, infer, fills

# Support: soft deduction — the most common strategy.
# reason + prior must be paired (both or neither).
support([evidence_a, evidence_b], hypothesis,
    reason="Evidence converges on hypothesis.", prior=0.85)

# Deduction: rigid — use for math proofs, logical syllogisms.
# No uncertainty beyond the premises themselves.
deduction([universal_law, binding_claim], derived_instance,
    background=[setting("x = YBCO")],
    reason="Universal instantiation.", prior=0.99)

# Compare: prediction comparison (2 equivalences + 1 implication).
# Auto-generates a comparison_claim as conclusion.
comp = compare(pred_h, pred_alt, observation,
    reason="H matches observation better.", prior=0.9)

# fills: cross-package interface bridging
fills(local_evidence, imported_interface_claim, strength="exact")

# infer: general CPT (2^k params) — rarely used directly
infer([premise], conclusion)
```

#### Named strategies (formalized at compile time)

```python
from gaia.lang import analogy, extrapolation
from gaia.lang import elimination, case_analysis, mathematical_induction

# Analogy: source + bridge → target
analogy(source_claim, target_claim, bridge_claim)

# Extrapolation: source + continuity → target
extrapolation(source_claim, target_claim, continuity_claim)

# Elimination: exhaustiveness + [(candidate, evidence), ...] → survivor
elimination(
    exhaustiveness_claim,
    [(candidate_1, evidence_1), (candidate_2, evidence_2)],
    survivor_claim,
)

# Case analysis: exhaustiveness + [(case, support), ...] → conclusion
case_analysis(
    exhaustiveness_claim,
    [(case_1, support_1), (case_2, support_2)],
    conclusion_claim,
)

# Mathematical induction: base + step → law
mathematical_induction(base_case, inductive_step, law_claim)
```

#### Composite strategies

```python
from gaia.lang import compare, support
from gaia.lang.dsl.strategies import abduction, induction

# Abduction: takes 3 Strategy objects (two supports + one compare)
s_h = support([H], obs, reason="H explains obs", prior=0.9)
s_alt = support([alt], obs, reason="Alt explains obs", prior=0.5)
comp = compare(pred_h, pred_alt, obs, reason="H matches better", prior=0.9)
abd = abduction(s_h, s_alt, comp, reason="Both explain same observation")
# abd.conclusion is comp.conclusion (the comparison claim)

# Induction: binary composite, chainable
s1 = support([law], obs1, reason="law predicts", prior=0.9)
s2 = support([law], obs2, reason="law predicts", prior=0.9)
s3 = support([law], obs3, reason="law predicts", prior=0.9)
ind_12 = induction(s1, s2, law=law, reason="independent traits")
ind_123 = induction(ind_12, s3, law=law, reason="third trait independent")
```

All named strategies (except `induction`) are automatically formalized into `FormalStrategy` with `FormalExpr` at compile time via the canonical IR formalizer. `induction` compiles to a `CompositeStrategy` wrapping its sub-strategies. Do NOT build `FormalExpr` by hand.

### Step 5: Export public interface

```python
__all__ = ["obs_a", "conclusion", "helper"]
```

Three visibility levels:
- **exported** (`__all__`): cross-package interface
- **public** (no `_` prefix): visible to review
- **private** (`_` prefix): package-internal

### Step 6: Compile and validate

```bash
gaia compile .    # Writes .gaia/ir.json + .gaia/ir_hash
gaia check .      # Validates structure + artifact consistency
```

Or programmatically:

```python
from gaia.cli._packages import load_gaia_package, compile_loaded_package, write_compiled_artifacts
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph

loaded = load_gaia_package("path/to/package")
ir = compile_loaded_package(loaded)
gaia_dir = write_compiled_artifacts(loaded.pkg_path, ir)

graph = LocalCanonicalGraph(**ir)
result = validate_local_graph(graph)
assert result.valid, result.errors
```

### Step 7: Run inference (optional, local)

```python
from gaia.bp import lower_local_graph
from gaia.bp.engine import InferenceEngine

# Assign priors to input claims (support/deduction warrant priors are in metadata)
input_ids = [k["id"] for k in ir["knowledges"]
             if k["type"] == "claim" and k.get("is_input")]
node_priors = {cid: 0.5 for cid in input_ids}

# Only `infer` strategies need external params; support/deduction/etc. are FormalStrategy
strat_params = {
    s.strategy_id: [0.85] * (2 ** len(s.premises))
    for s in graph.strategies
    if s.type.value == "infer" and s.strategy_id
}

fg = lower_local_graph(graph,
    node_priors=node_priors,
    strategy_conditional_params=strat_params)

engine = InferenceEngine()
result = engine.run(fg)  # Auto-selects JT (exact) or loopy BP
beliefs = result.beliefs
```

### Step 8: Generate reasoning docs (optional)

After inference, generate `docs/detailed-reasoning.md` with belief results and per-module Mermaid reasoning graphs:

```bash
gaia infer .                      # Run inference first (beliefs appear in the doc)
gaia render . --target docs       # Writes docs/detailed-reasoning.md
```

The generated doc includes:
- **Overview graph**: exported conclusions with belief values
- **Per-module Mermaid graphs**: focused diagrams scoped to each module
- **Knowledge nodes**: each claim with content, prior, belief, derivation, and reasoning
- **Inference Results**: summary table of all beliefs

`gaia render --target docs` works without inference results too (author iteration mode) but emits a warning and omits belief values when `gaia infer` hasn't been run. Run `gaia infer .` first for enriched output.

### Step 9: Register with official registry (optional)

Requires a GitHub repository with the package source + `.gaia/` artifacts, tagged with a version.

```bash
git tag v1.0.0
git push origin main v1.0.0
gaia register . --registry-dir /path/to/gaia-registry --create-pr
```

## Anti-patterns

<HARD-GATE>
Do NOT do any of the following. These are not style preferences — they produce invalid packages.
</HARD-GATE>

- **Using `Package(...)` context manager** — Removed in v5. The runtime infers package membership from `pyproject.toml`. Using it causes `load_gaia_package` to fail.
- **Manually setting `.label = "name"`** — Labels are auto-assigned from Python variable names by `gaia compile`. Manual assignment is redundant and risks inconsistency with the variable name.
- **Using `setting` or `question` as strategy premises** — Validator rejects non-claim premises. Use `background=` parameter instead.
- **Using `noisy_and()`** — Deprecated. Use `support()` instead. `noisy_and` emits a `DeprecationWarning` and compiles to `support` internally.
- **Using old `abduction(observation, hypothesis)` signature** — `abduction()` now takes three Strategy objects: `abduction(support_h, support_alt, comparison)`.
- **Providing `reason` without `prior` (or vice versa)** — Both `reason` and `prior` must be paired: provide both or neither. Applies to `support()`, `deduction()`, `compare()`, and all operator functions.
- **Building `FormalExpr` by hand** — The compiler calls `formalize_named_strategy` from `gaia.ir.formalize`. Do not replicate its logic.
- **Importing from `gaia.gaia_ir`** — Renamed to `gaia.ir`. Old path does not exist.
- **Setting `dependencies = ["gaia-lang >= 2.0.0"]`** — In CI, the Gaia CLI is provided externally. Set `dependencies = []` (or only list other `*-gaia` packages).
- **Omitting `[build-system]`** — Required for `uv sync` in CI. Use `requires = ["setuptools>=69.0"]`.
- **Duplicate UUIDs** — Every package must have a globally unique UUID. The registry CI checks this.

## Spec pointers

- `docs/foundations/gaia-lang/dsl.md` — DSL API reference (canonical, current)
- `docs/foundations/gaia-lang/knowledge-and-reasoning.md` — Knowledge types and strategy formalization semantics
- `docs/foundations/gaia-lang/package.md` — Package model and lifecycle
- `docs/foundations/gaia-ir/02-gaia-ir.md` — Knowledge / Operator / Strategy schemas
- `docs/foundations/gaia-ir/04-helper-claims.md` — Helper claim metadata conventions
- `docs/foundations/gaia-ir/08-validation.md` — Structural validation rules
- `docs/foundations/gaia-ir/07-lowering.md` — IR → FactorGraph lowering contract
