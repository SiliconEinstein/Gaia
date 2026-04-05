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
namespace = "reg"                  # "reg" for registry, "paper" for papers
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
from gaia.lang import claim, setting, question, contradiction

# Settings — background, no probability
env = setting("Experimental conditions described here.")

# Claims — propositions with truth values
obs_a = claim("Observation A holds under conditions described.")

# Claims derived from premises (auto-creates noisy_and strategy)
conclusion = claim("Derived conclusion.", given=[obs_a])
```

**Rules:**
- Labels are **automatically assigned from Python variable names** by `gaia compile`. Do NOT set `.label` manually.
- Variable names must be valid Python identifiers (`[a-z_][a-z0-9_]*`).
- Variable names must be unique within the package.
- Only `claim` carries probability; `setting` and `question` do not participate in BP.
- `claim(given=[...])` is sugar for `noisy_and(premises, conclusion)`.

### Step 3: Add structural operators

Operators encode deterministic logical relations. Each operator function creates the operator AND returns a helper claim.

```python
from gaia.lang import contradiction, equivalence, complement, disjunction

# Contradiction: ¬(A ∧ B) — cannot both be true
helper = contradiction(claim_a, claim_b, reason="Why they conflict")
helper.label = "a_vs_b_contradiction"

# Equivalence: A = B — same truth value
eq = equivalence(claim_x, claim_y, reason="Why they are equivalent")
eq.label = "x_eq_y"

# Complement: A ⊕ B — opposite truth values (XOR)
comp = complement(claim_p, claim_q, reason="Why they are opposites")
comp.label = "p_xor_q"

# Disjunction: at least one true
disj = disjunction(hyp_a, hyp_b, hyp_c, reason="At least one mechanism")
disj.label = "some_mechanism"
```

The returned helper claim can be used as a premise in subsequent strategies.

### Step 4: Add explicit strategies (when `given=` is not enough)

Use explicit strategy functions when you need a specific reasoning type beyond `noisy_and`:

```python
from gaia.lang import deduction, abduction, analogy, extrapolation
from gaia.lang import elimination, case_analysis, mathematical_induction

# Deduction: strict deterministic derivation (math proofs, logical syllogisms).
# The reasoning step itself is error-free — uncertainty comes ONLY from premises.
# If the reasoning has any uncertainty (approximations, empirical judgments,
# omitted premises), use noisy_and instead.
deduction([premise_a, premise_b], derived_claim)

# Abduction: observation → hypothesis (with optional alternative)
abduction(observation, hypothesis)
abduction(observation, hypothesis, alternative_explanation)

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

All named strategies are automatically formalized into `FormalStrategy` with `FormalExpr` at compile time via the canonical IR formalizer. Do NOT build `FormalExpr` by hand.

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

# Assign MaxEnt priors to input claims
input_ids = [k["id"] for k in ir["knowledges"]
             if k["type"] == "claim" and k.get("is_input")]
node_priors = {cid: 0.5 for cid in input_ids}

# noisy_and strategies need a strength parameter
strat_params = {
    s.strategy_id: [0.85]
    for s in graph.strategies
    if s.type.value in ("noisy_and", "infer") and s.strategy_id
}

fg = lower_local_graph(graph,
    node_priors=node_priors,
    strategy_conditional_params=strat_params)

engine = InferenceEngine()
result = engine.run(fg)  # Auto-selects JT (exact) or loopy BP
beliefs = result.beliefs
```

### Step 8: Register with official registry (optional)

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
- **Single-premise `deduction()`** — Requires at least 2 premises. For single-premise derivation, use `claim(given=[premise])` (noisy_and).
- **Building `FormalExpr` by hand** — The compiler calls `formalize_named_strategy` from `gaia.ir.formalize`. Do not replicate its logic.
- **Importing from `gaia.gaia_ir`** — Renamed to `gaia.ir`. Old path does not exist.
- **Setting `dependencies = ["gaia-lang >= 2.0.0"]`** — In CI, the Gaia CLI is provided externally. Set `dependencies = []` (or only list other `*-gaia` packages).
- **Omitting `[build-system]`** — Required for `uv sync` in CI. Use `requires = ["setuptools>=69.0"]`.
- **Duplicate UUIDs** — Every package must have a globally unique UUID. The registry CI checks this.

## Spec pointers

- `docs/specs/2026-04-02-gaia-lang-v5-python-dsl-design.md` — Canonical DSL spec (package model, API, lifecycle)
- `docs/specs/2026-04-02-gaia-registry-design.md` — Registry structure and registration flow
- `docs/foundations/gaia-ir/02-gaia-ir.md` — Knowledge / Operator / Strategy schemas
- `docs/foundations/gaia-ir/04-helper-claims.md` — Helper claim metadata conventions
- `docs/foundations/gaia-ir/08-validation.md` — Structural validation rules
- `docs/foundations/gaia-ir/07-lowering.md` — IR → FactorGraph lowering contract
