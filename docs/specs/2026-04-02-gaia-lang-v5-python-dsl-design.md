# Gaia Lang v5 — Python DSL Design

> **Status:** Current canonical for Phase 1 structural authoring
>
> **Replaces:** [2026-03-20-typst-dsl-v4-design.md](2026-03-20-typst-dsl-v4-design.md), [2026-03-25-gaia-lang-alignment-design.md](2026-03-25-gaia-lang-alignment-design.md)
>
> **Depends on:** [Gaia IR v2](../foundations/gaia-ir/02-gaia-ir.md), [Parameterization](../foundations/gaia-ir/06-parameterization.md), [Ecosystem](../foundations/ecosystem/)
>
> **Future extensions:** [2026-04-03-gaia-lang-future-extensions-design.md](2026-04-03-gaia-lang-future-extensions-design.md)

## 1. Overview

Gaia Lang v5 is a **Python internal DSL** for declaratively authoring knowledge packages. It replaces the Typst-based v4 design.

### 1.1 Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Host language | Python 3.12+ internal DSL | Zero learning cost (students already know Python); full IDE support; complete programmability |
| Package management | uv/pip ecosystem | Dependency resolution, lockfiles, private registries, workspaces — all solved |
| Math notation | LaTeX strings in content | Students already know LaTeX; avoids Typst's bracket-heavy function syntax |
| Document output | Decoupled (IR → rendering) | Separation of concerns; DSL focuses on knowledge structure |
| Probability values | Independent parameterization layer | Aligns with IR v2; reviewers assign probabilities separately from structure |

### 1.2 Key Differences from v4

| | v4 (Typst) | v5 (Python DSL) |
|---|---|---|
| Host language | Typst typesetting engine | Python 3.12+ |
| Package metadata | typst.toml + gaia-deps.yml | pyproject.toml |
| Cross-package refs | Hand-written YAML labels | `from pkg import claim` (Python import) |
| Reference safety | Compile-time check | Instant NameError |
| Programmability | Very limited | Full Python |
| Document output | Same-source dual output | Decoupled (IR → renderer) |
| Math formulas | Typst syntax `frac(a,b)` | LaTeX syntax `\frac{a}{b}` |
| Probability | Inline `prior: 0.9` | Separate parameterization layer |

---

## 2. Package Model

### 2.1 Package Structure

Each Gaia knowledge package is a standard Python library package:

```
galileo-falling-bodies-gaia/
├── pyproject.toml
├── src/
│   └── galileo_falling_bodies/
│       ├── __init__.py      # Package entry: exports + DSL declarations
│       ├── premises.py      # Module: background + observations
│       └── reasoning.py     # Module: reasoning chains
└── .gaia/                   # Compiled artifacts (git tracked)
    ├── ir.json              # Pure LocalCanonicalGraph JSON
    └── ir_hash              # Integrity checksum
```

`src/` layout is recommended, but the current compiler also accepts a flat `<repo>/<import_name>/` layout.

Earlier sketches in this document showed optional `.gaia/params/` and review artifacts. Those are not part of the current Phase 1 CLI contract.

### 2.2 pyproject.toml

```toml
[project]
name = "galileo-falling-bodies-gaia"
version = "4.0.0"
description = "Galileo's falling bodies argument"
authors = [{name = "Galileo Galilei"}]
requires-python = ">=3.12"
dependencies = [
    "gaia-lang >= 2.0.0",
    "aristotle-mechanics-gaia >= 1.0.0",
]

[tool.setuptools.packages.find]
include = ["galileo_falling_bodies*"]    # Import name omits -gaia suffix

[tool.gaia]
namespace = "galileo"
type = "knowledge-package"
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
```

**Naming convention (Julia-style `.gaia` suffix):**

| Layer | Format | Example |
|-------|--------|---------|
| GitHub repo | `<CamelCase>.gaia` | `GalileoFallingBodies.gaia` |
| PyPI package | `<kebab-case>-gaia` | `galileo-falling-bodies-gaia` |
| Python import | `<snake_case>` (no suffix) | `galileo_falling_bodies` |
| Source directory | `<snake_case>/` | `galileo_falling_bodies/` |

**Conventions:**
- Package names use `<name>-gaia` suffix to identify Gaia knowledge packages (like Julia's `.jl` convention).
- `[tool.gaia].namespace` is used for QID generation: `{namespace}:{package_name}::{label}`. The compiler maps this to IR v2's allowed namespace set (`reg` for registry-bound packages, `paper` for extracted packages).
- Cross-package dependencies are standard Python dependencies in `[project].dependencies`.

### 2.3 Version Semantics

Follows semver, defined by knowledge evolution:

| Change | Version level | Example |
|--------|--------------|---------|
| Typo fix, metadata update | PATCH | 1.0.0 → 1.0.1 |
| New claims/strategies added, existing exports unchanged | MINOR | 1.0.0 → 1.1.0 |
| Exported claim semantics changed, deletions, restructuring | MAJOR | 1.0.0 → 2.0.0 |

### 2.4 Exported Conclusions

```python
# galileo_falling_bodies/__init__.py
from .reasoning import vacuum_prediction, air_resistance_hypothesis

__all__ = ["vacuum_prediction", "air_resistance_hypothesis"]
```

Three visibility levels:

| Level | Mechanism | Gaia IR mapping | Usage |
|-------|-----------|-----------------|-------|
| **exported** | `__all__` | Package public interface | Cross-package import, LKM integration |
| **public** | No underscore prefix | Internal claims | Visible to review, not recommended for cross-package dependency |
| **private** | `_` prefix | Package-private claims | Not exported; still regular claims in IR (distinct from FormalExpr internal private nodes, which are managed by the compiler) |

### 2.5 Cross-Package References

```python
from aristotle_mechanics import heavy_body_doctrine

my_claim = claim("...", given=[heavy_body_doctrine])
__all__ = ["my_claim"]
```

Dependency management:
```bash
uv add "aristotle-mechanics-gaia @ git+https://github.com/example/AristotleMechanics.gaia@v1.0.0"
```

Phase 1 assumes a GitHub-backed source registry, not an installable package index. Cross-package dependencies are therefore pinned as standard Python direct references (or handled via local workspace paths in a monorepo).

### 2.6 Workspace (Monorepo)

```toml
# Root pyproject.toml
[tool.uv.workspace]
members = ["packages/*"]
```

```
lab-knowledge/
├── pyproject.toml
├── uv.lock                          # Shared lockfile
├── packages/
│   ├── YBCOSuperconductor.gaia/
│   ├── BSCCOSuperconductor.gaia/
│   └── HighTcReview.gaia/           # References the above two
```

---

## 3. DSL API

The DSL API strictly aligns with Gaia IR v2's three entity types: Knowledge, Operator, Strategy. **All probability values are excluded from this layer** — they belong to the independent parameterization layer (§4).

### 3.1 Knowledge

Three knowledge types, corresponding to Gaia IR v2 §1.2:

```python
from gaia.lang import claim, setting, question

# setting: background assumption. No probability, no BP participation.
aristotle_doctrine = setting("""
    Aristotle's doctrine of motion: heavier objects fall faster.
""")

# question: research direction. No probability, no BP participation.
what_in_vacuum = question("""
    Do objects of different mass fall at different rates without air resistance?
""")

# claim: scientific assertion. The ONLY type that participates in BP.
heavy_falls_faster = claim(r"""
    Observations show heavier stones fall faster than feathers.
    Fall time $t = \sqrt{\frac{2h}{g}}$ is mass-independent (in vacuum).
""")
```

**API signatures:**

```python
def setting(content: str, **metadata) -> Knowledge:
    """Background assumption. No probability, no BP participation."""

def question(content: str, **metadata) -> Knowledge:
    """Research question. No probability, no BP participation."""

def claim(
    content: str,
    *,
    given: list[Knowledge] | None = None,       # Sugar: creates noisy_and Strategy
    background: list[Knowledge] | None = None,   # Context dependency (not in BP)
    parameters: list[dict] | None = None,        # Quantified variables (universal claims)
    **metadata,
) -> Knowledge:
    """Scientific assertion. The only type carrying probability (via parameterization layer)."""
```

**`given` shorthand:** The `given` parameter on `claim()` is syntactic sugar — it automatically creates a `noisy_and` Strategy with the given claims as premises and the current claim as conclusion. This covers ~80% of reasoning patterns without needing explicit Strategy declarations:

```python
# These two are equivalent:

# Shorthand (recommended for simple cases)
vacuum_prediction = claim("...", given=[tied_ball, heavy_falls_faster])

# Explicit (use when you need steps or named strategy type)
vacuum_prediction = claim("...")
noisy_and(premises=[tied_ball, heavy_falls_faster], conclusion=vacuum_prediction)
```

**Universal claims (with parameters):**

```python
universal_sc = claim(r"""
    All superconductors exhibit zero resistance below Tc.
    $\forall x: \text{superconductor}(x) \Rightarrow \text{zero\_resistance}(x)$
""", parameters=[{"name": "x", "type": "material"}])

# Instantiation via deduction
ybco_binding = setting("x = YBCO")
ybco_zero_resistance = claim("YBCO exhibits zero resistance below Tc.")
deduction(
    premises=[universal_sc],
    conclusion=ybco_zero_resistance,
    background=[ybco_binding],
)
```

### 3.2 Operator

Corresponding to Gaia IR v2 §2. Operators express **deterministic logical relationships** between claims — no probability parameters.

```python
from gaia.lang import contradiction, equivalence, complement, disjunction

# contradiction: ¬(A=1 ∧ B=1)
tied_ball = contradiction(
    composite_slower, composite_faster,
    reason="Same premise yields contradictory conclusions",
)
# Auto-creates helper claim: not_both_true(composite_slower, composite_faster)

# equivalence: A=B (truth values must match)
eq = equivalence(
    predicted_obs, actual_obs,
    reason="BCS theory prediction matches observation",
)

# complement: A≠B (truth values must differ, XOR)
comp = complement(
    classical_pred, quantum_pred,
    reason="Classical and quantum predictions oppose at this scale",
)

# disjunction: ¬(all Aᵢ=0), at least one true
disj = disjunction(
    mechanism_a, mechanism_b, mechanism_c,
    reason="At least one mechanism explains the phenomenon",
)
```

**API signatures:**

```python
def contradiction(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """¬(A ∧ B). Creates Operator and returns its helper claim: not_both_true(A, B)."""

def equivalence(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """A = B. Creates Operator and returns its helper claim: same_truth(A, B)."""

def complement(a: Knowledge, b: Knowledge, *, reason: str = "") -> Knowledge:
    """A ≠ B (XOR). Creates Operator and returns its helper claim: opposite_truth(A, B)."""

def disjunction(*claims: Knowledge, reason: str = "") -> Knowledge:
    """At least one true. Creates Operator and returns its helper claim: any_true(A₁, ..., Aₖ)."""
```

Each Operator function creates the Operator internally and **returns the helper claim** (a `Knowledge` object). This allows seamless use in `given=` and other places that accept Knowledge:

```python
contra = contradiction(a, b, reason="...")
my_claim = claim("...", given=[contra])  # contra is a Knowledge (helper claim)
```

**Note:** `implication` and `conjunction` are NOT exposed as user API. They only appear inside FormalStrategy's `formal_expr`, auto-generated by named strategies. The rationale: top-level implication expresses probabilistic support (use `noisy_and` or named strategies instead); top-level conjunction is rarely needed in authoring (it mainly serves as FormalExpr glue). If a reviewer discovers an implication relationship during review, it should be expressed as a `noisy_and` Strategy, not a deterministic Operator.

### 3.3 Strategy

Corresponding to Gaia IR v2 §3. Three morphologies by frequency of use.

#### 3.3.1 Leaf Strategy: `noisy_and` (most common)

All premises jointly necessary, supporting conclusion with conditional probability p:

```python
from gaia.lang import noisy_and

noisy_and(
    premises=[evidence_a, evidence_b, evidence_c],
    conclusion=my_hypothesis,
    steps=["Evidence A shows...",
           "Combined with B...",
           "Therefore supports hypothesis"],
)
# Note: no p= here. Conditional probability assigned in parameterization layer.
```

#### 3.3.2 Leaf Strategy: `infer` (general CPT)

```python
from gaia.lang import infer

infer(
    premises=[a, b],
    conclusion=c,
    # Full CPT (2^k parameters) assigned in parameterization layer.
)
```

**When to use which leaf strategy:**
- `claim(given=[...])` or `noisy_and()` — default choice. Use when premises are jointly necessary conditions for the conclusion (~80% of cases).
- `infer()` — use when the reasoning is unclassified or when the full CPT structure matters (e.g., different premise combinations have non-trivial conditional probabilities). Reviewers may later reclassify an `infer` to `noisy_and` or a named FormalStrategy type.
- Named strategies (`deduction`, `abduction`, etc.) — use when the reasoning fits a recognized pattern. The compiler auto-generates the canonical skeleton.

#### 3.3.3 FormalStrategy: Named Strategies

Named strategies accept semantic interface parameters and auto-expand into `FormalExpr` (Operator DAG) at compile time. Users **do not** hand-write Operator skeletons.

**deduction:**

```python
from gaia.lang import deduction

deduction(
    premises=[universal_law],
    conclusion=specific_instance,
    background=[variable_binding],
    reason="Instantiate universal claim with x=YBCO",
)
# Auto-expands to FormalExpr:
#   conjunction([universal_law], conclusion=_M)
#   implication([_M], conclusion=specific_instance)
# `background` is preserved on the Strategy object (not in FormalExpr — it provides context, not structure).
```

**abduction:**

```python
from gaia.lang import abduction

abduction(
    observation=superconductivity_obs,
    hypothesis=bcs_hypothesis,
    alternative=alternative_explanation,  # Optional; auto-created if omitted
    reason="BCS theory prediction matches observation",
)
# IR v2 interface: premises=[Obs, AlternativeExplanationForObs], conclusion=H
# Auto-expands to canonical FormalExpr:
#   disjunction([hypothesis, alternative], conclusion=_Disj_Explains_Obs)
#   equivalence([_Disj_Explains_Obs, observation], conclusion=_Eq_Explains_Obs)
# _Disj_Explains_Obs and _Eq_Explains_Obs are private helper claims.
# `alternative` is a public interface claim (carries prior, can be supported by other strategies).
```

**analogy:**

```python
from gaia.lang import analogy

analogy(
    source=bcs_in_metallic_sc,
    target=bcs_in_high_tc,
    bridge=claim("Metallic and high-Tc SC share Cooper pair mechanism."),
    reason="BCS verified in metallic SC, analogize to high-Tc",
)
# Auto-expands to:
#   conjunction([source, bridge], conclusion=_M)
#   implication([_M], conclusion=target)
```

**extrapolation:**

```python
from gaia.lang import extrapolation

extrapolation(
    source=low_pressure_behavior,
    target=high_pressure_prediction,
    continuity=claim("The quantity varies continuously with pressure."),
    reason="Extrapolate linear low-pressure trend to high-pressure regime",
)
# Same skeleton as analogy; semantically marks cross-range transfer.
```

**elimination:**

```python
from gaia.lang import elimination

elimination(
    exhaustiveness=candidates_exhaustive,  # Coverage claim: listed candidates suffice
    excluded=[(bacterial, antibiotics_neg),  # (candidate, evidence) pairs
              (viral, viral_test_neg)],
    survivor=autoimmune,                    # The remaining hypothesis
    reason="All other candidates excluded by evidence",
)
# IR v2 interface: premises=[Exhaustiveness, H₁, E₁, ..., Hₖ, Eₖ], conclusion=Hₛ
# Auto-expands to canonical FormalExpr:
#   disjunction([H₁,...,Hₖ, Hₛ], conclusion=_Disj_Candidates)
#   equivalence([_Disj_Candidates, Exhaustiveness], conclusion=_Eq_Disj_Exhaustive)
#   contradiction([H₁, E₁], conclusion=_Contra_H₁_E₁)  (per excluded candidate)
#   conjunction([Exhaustiveness, E₁, _Contra_H₁_E₁, ...], conclusion=_M)
#   implication([_M], conclusion=Hₛ)
```

**case_analysis:**

```python
from gaia.lang import case_analysis

case_analysis(
    exhaustiveness=parity_exhaustive,  # Coverage claim: cases are exhaustive
    cases=[(n_even, even_support),     # (case_condition, case_justification) pairs
           (n_odd, odd_support)],
    conclusion=n2_plus_n_even,
    reason="Both even and odd cases support the conclusion",
)
# IR v2 interface: premises=[Exhaustiveness, A₁, P₁, ..., Aₖ, Pₖ], conclusion=C
# Auto-expands to canonical FormalExpr:
#   disjunction([A₁,...,Aₖ], conclusion=_Disj)
#   equivalence([_Disj, Exhaustiveness], conclusion=_Eq_Disj_Exhaustive)
#   conjunction([A₁, P₁], conclusion=_M₁), implication([_M₁], conclusion=C)  (per case)
```

**mathematical_induction:**

```python
from gaia.lang import mathematical_induction

mathematical_induction(
    base=p_zero_holds,      # P(0) base case
    step=inductive_step,    # ∀n: P(n)→P(n+1)
    conclusion=law_for_all, # ∀n: P(n)
    reason="Base case + inductive step establish universal property",
)
# Same skeleton as deduction (conjunction + implication).
# Semantic distinction: base=P(0), step=∀n(P(n)→P(n+1)), conclusion=∀n.P(n).
```

**Deferred types (not supported in DSL v5.0):**
- `induction` — expressible as repeated abduction with shared conclusion; no independent IR primitive.
- `reductio` — IR v2 defers: hypothetical assumption/consequence interface not yet stabilized.
- `toolcall` / `proof` — not yet designed in IR v2.

#### 3.3.4 CompositeStrategy

Combines multiple Strategies into a hierarchical argument:

```python
from gaia.lang import composite

galileo_argument = composite(
    premises=[aristotle_doctrine],
    conclusion=vacuum_prediction,
    sub_strategies=[
        tied_ball_strategy,
        air_resistance_strategy,
        vacuum_inference_strategy,
    ],
    reason="Galileo's three-step argument",
)
# Note: CompositeStrategy folding behavior is an open question in IR v2.
# The DSL compiles it, but inference-time behavior (fold vs expand)
# depends on the backend's expand_set configuration.
```

### 3.4 API Summary

| Function | Type | IR v2 Mapping | Description |
|----------|------|---------------|-------------|
| `setting()` | Knowledge | `Knowledge(type=setting)` | Background assumption |
| `question()` | Knowledge | `Knowledge(type=question)` | Research question |
| `claim()` | Knowledge | `Knowledge(type=claim)` | Scientific assertion (only type with probability) |
| `claim(given=...)` | Knowledge + Strategy | claim + `noisy_and` | Sugar: declaration + reasoning in one step |
| `contradiction()` | Operator | `Operator(operator=contradiction)` | Returns helper claim |
| `equivalence()` | Operator | `Operator(operator=equivalence)` | Returns helper claim |
| `complement()` | Operator | `Operator(operator=complement)` | Returns helper claim |
| `disjunction()` | Operator | `Operator(operator=disjunction)` | Returns helper claim |
| `noisy_and()` | Strategy | `Strategy(type=noisy_and)` | Most common leaf reasoning |
| `infer()` | Strategy | `Strategy(type=infer)` | General CPT (rarely used directly) |
| `deduction()` | FormalStrategy | `FormalStrategy(type=deduction)` | Auto-expands |
| `abduction()` | FormalStrategy | `FormalStrategy(type=abduction)` | Auto-expands |
| `analogy()` | FormalStrategy | `FormalStrategy(type=analogy)` | Auto-expands |
| `extrapolation()` | FormalStrategy | `FormalStrategy(type=extrapolation)` | Auto-expands |
| `elimination()` | FormalStrategy | `FormalStrategy(type=elimination)` | Auto-expands |
| `case_analysis()` | FormalStrategy | `FormalStrategy(type=case_analysis)` | Auto-expands |
| `mathematical_induction()` | FormalStrategy | `FormalStrategy(type=mathematical_induction)` | Auto-expands |
| `composite()` | CompositeStrategy | `CompositeStrategy` | Hierarchical composition |
| — | — | `induction` (deferred) | Use repeated abduction |
| — | — | `reductio` (deferred) | IR v2 interface not stabilized |
| — | — | `toolcall` / `proof` (deferred) | Not yet designed |

---

## 4. Compilation & Tooling

### 4.1 Compilation Pipeline

```
.py files (Python DSL)
    │
    ↓  gaia compile
    │
    ├──→ ir.json           (LocalCanonicalGraph, structure only)
    └──→ ir_hash           (SHA-256 integrity checksum)
```

Three steps:

**Step 1: Collection.** Python import executes module top-level declarations. All DSL calls (`claim()`, `contradiction()`, `noisy_and()`, etc.) register into the package inferred from `pyproject.toml`. No inference runs — only declarations are collected.

**Step 2: Build IR.** Convert collected declarations to Gaia IR v2 structures:

- Knowledge declarations → Knowledge nodes (QID, content_hash, type)
- Operator calls → Operator nodes (operator_id, variables, conclusion)
- Strategy declarations → Strategy nodes (strategy_id, premises, conclusion)
  - `claim(given=[...])` → `Strategy(type=noisy_and)`
  - `noisy_and(...)` → `Strategy(type=noisy_and)`
  - `infer(...)` → `Strategy(type=infer)`
  - `deduction(...)` → `FormalStrategy(type=deduction)` + auto-expanded formal_expr
  - `abduction(...)` → `FormalStrategy(type=abduction)` + auto-expanded + helper claims
  - `analogy(...)` → `FormalStrategy(type=analogy)` + auto-expanded
  - `composite(...)` → `CompositeStrategy`

FormalStrategy expansion auto-creates helper claims and internal Operators, marked as private (`_` prefix or unbound variables).

**Step 3: Canonicalize.**

- Assign QIDs: `{namespace}:{package_name}::{label}` (label = Python variable name)
- Compute `content_hash = SHA-256(type + content + sorted(parameters))` (empty list when `parameters` is None)
- Compute `strategy_id = lcs_{SHA-256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}` (per IR v2 §3.2)
- Compute `operator_id = lco_{SHA-256(operator + sorted(variables) + conclusion)[:16]}`
- Compute `ir_hash` (SHA-256 of deterministic whole-graph serialization)

### 4.2 Variable Name as Label

Python variable names automatically become IR labels:

```python
vacuum_prediction = claim("...")
# → Knowledge(label="vacuum_prediction",
#              id="galileo:galileo_falling_bodies::vacuum_prediction")
```

Implementation: after import, the compiler inspects the loaded module and uses `__all__` when present, otherwise public module globals, to assign labels.

**Edge cases:**
- Inline claims (e.g., `analogy(bridge=claim("..."))`) without variable binding get auto-generated labels (e.g., `_anon_claim_001`), marked as private.
- Reassignment to the same variable name: the last assignment wins; previous Knowledge becomes anonymous.
- Claims created in loops or comprehensions: use explicit `label=` parameter to override auto-detection when needed.

### 4.3 CLI Commands

```bash
gaia compile [path]            # Compile → .gaia/ir.json + ir_hash

gaia check [path]              # Structural validation (references, schema legality)
gaia register [path]           # Submit a tagged GitHub-backed release to the official registry
```

Phase 1 keeps the author-side lifecycle intentionally small:

1. `gaia compile`
2. `gaia check`
3. Push source to GitHub
4. Create and push a git tag (default convention: `v<version>`)
5. `gaia register`

`gaia register` is **not** direct publication of artifacts. It creates or prepares a metadata PR against the official registry for a GitHub-tagged source release.

### 4.4 Validation (`gaia check`)

Three levels, aligning with Gaia IR v2 [08-validation.md](../foundations/gaia-ir/08-validation.md):

**Object-level:**
- Every Knowledge has valid `type` (claim/setting/question)
- `content` is non-empty
- `parameters` format is correct (universal claims)

**Graph-level:**
- All referenced Knowledge IDs exist in graph
- Strategy `premises` and `conclusion` are `claim` (not setting/question)
- Operator `variables` are all `claim`
- No cyclic dependencies (Strategy DAG is acyclic)
- ID uniqueness
- FormalExpr private nodes not referenced by external Strategies
- All names in `__all__` exist

Parameterization, inference, and rendering are intentionally excluded from the current Phase 1 CLI contract. See [2026-04-03-gaia-lang-future-extensions-design.md](2026-04-03-gaia-lang-future-extensions-design.md).

### 4.5 Test Support

Standard pytest for structural assertions:

```python
# tests/test_structure.py
from galileo_falling_bodies import vacuum_prediction, heavy_falls_faster

def test_vacuum_prediction_has_premises():
    strategy = vacuum_prediction.strategy
    assert strategy.type == "noisy_and"
    assert heavy_falls_faster in strategy.premises

def test_compiled_graph_has_no_cycles(tmp_path):
    # compile with the CLI and inspect .gaia/ir.json in an integration test
    ...
```

---

## 5. Complete Structural Example

### 5.1 Structural Layer (Author)

```python
# galileo_falling_bodies/__init__.py
from gaia.lang import claim, setting, question, contradiction
from .reasoning import vacuum_prediction, air_resistance

__all__ = ["vacuum_prediction", "air_resistance"]
```

```python
# galileo_falling_bodies/premises.py
from gaia.lang import claim, setting

aristotle_doctrine = setting("""
    Aristotle's doctrine: heavier objects fall proportionally faster.
""")

heavy_falls_faster = claim(r"""
    Observations show heavier stones fall faster than feathers.
""")

composite_slower = claim(r"""
    The tied composite should be slower (light ball drags heavy ball).
    $v_{\text{composite}} = \frac{m_1 v_1 + m_2 v_2}{m_1 + m_2}$
""")

composite_faster = claim(r"""
    The composite has greater mass, so it should be faster.
    $v_{\text{composite}} = k(m_1 + m_2) > k m_1$
""")
```

```python
# galileo_falling_bodies/reasoning.py
from gaia.lang import claim, contradiction
from .premises import (
    heavy_falls_faster, composite_slower, composite_faster,
)

tied_ball = contradiction(
    composite_slower, composite_faster,
    reason="Same premise yields contradictory conclusions",
)

air_resistance = claim("""
    Observed speed differences are caused entirely by air resistance.
""", given=[tied_ball])

vacuum_prediction = claim(r"""
    In a vacuum, objects of different mass fall at the same rate.
    $g \approx 9.8 \text{ m/s}^2$, independent of mass.
""", given=[tied_ball, heavy_falls_faster])
```

### 5.2 Workflow

```bash
uv init --lib galileo-falling-bodies-gaia
uv add gaia-lang
# ... write knowledge ...
gaia compile .
gaia check .
git add . && git commit -m "Prepare v1.0.0"
git push origin main
git tag v1.0.0
git push origin v1.0.0
gaia register
```

---

## 6. Ecosystem Integration

### 6.1 Mapping to Ecosystem Workflows

| Ecosystem concept | v4 design | v5 (Python DSL + uv) |
|---|---|---|
| Package creation | `gaia init` + typst.toml | `uv init --lib` + pyproject.toml |
| Dependency declaration | gaia-deps.yml | pyproject.toml `[project].dependencies` |
| Cross-package reference | Hand-written YAML label | Python `import` |
| Version management | typst.toml version field | `uv version --bump` |
| Local build | `gaia build` → .gaia/ir.json | `gaia compile` → .gaia/ir.json |
| Registration | git push + manual registration | `git push` + `git tag` + `gaia register` |
| Private source registry | Not designed | Git-hosted metadata repo + direct Git dependencies |
| Workspace | Not supported | `[tool.uv.workspace]` |
| Lockfile | ir_hash only | uv.lock + ir_hash |

### 6.2 What uv Handles vs What Gaia Builds

**uv handles (solved infrastructure):**
- Package creation and packaging scaffolding
- Dependency resolution and lockfiles
- Private registry authentication
- Workspace management
- Python version management

**Gaia Phase 1 currently provides (implemented author-side surface):**
- `gaia compile` — Python DSL → Gaia IR JSON compiler
- `gaia check` — IR validation and artifact consistency checks
- `gaia register` — source-release registration PR generation

Future extensions such as parameterization resolution, inference, and rendering are tracked separately in [2026-04-03-gaia-lang-future-extensions-design.md](2026-04-03-gaia-lang-future-extensions-design.md).

> **Note:** The ecosystem foundation docs (`docs/foundations/ecosystem/`) still reference Typst-based authoring. They remain higher-level protected docs and will need a coordinated update later.

---

## 7. Migration from v4

### 7.1 What Changes

| v4 artifact | v5 replacement |
|---|---|
| `.typ` files | `.py` files |
| `typst.toml` | `pyproject.toml` |
| `gaia-deps.yml` | `[project].dependencies` |
| `libs/typst/gaia-lang-v4/` | `gaia-lang` Python package |
| `libs/lang/typst_loader.py` | `gaia.lang.compiler` |
| `typst query` extraction | Python import + `pkg.compile()` |

### 7.2 What Stays

- `.gaia/` artifact directory structure
- `ir.json` output format (Gaia IR v2, unchanged)
- `ir_hash` integrity verification
- Review report format
- LKM integration protocol (consumes IR JSON)
- BP inference engine (consumes compiled factor graph)

The IR contract layer (`docs/foundations/gaia-ir/`) is untouched — v5 only changes how IR is **produced**, not what it **is**.
