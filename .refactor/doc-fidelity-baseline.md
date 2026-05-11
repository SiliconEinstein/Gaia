# Doc Fidelity Baseline — gaia v0.5 quality refactor

> **Purpose.** This document is the contract surface the quality refactor must preserve. Downstream agents (ruff full-select, mypy strict, pre-commit, 90% coverage) MUST read this before touching code. The refactor adds type annotations, Google docstrings, and tests; it MUST NOT change IR / semantics / DSL surface / API signatures / algorithms.
>
> **Method.** Extracted by reading every file under `docs/foundations/{theory,ecosystem,gaia-ir,gaia-lang,bp,review,cli,contracts}/`, every file under `docs/for-users/`, plus selectively current-canonical specs under `docs/specs/`. Citations are by relative path; verify back to source on any doubt.

---

## 1. Canonical doc index

### 1.1 foundations/

| Path | Role |
|---|---|
| `docs/foundations/README.md` | Foundations layer map; reading order |
| `docs/documentation-policy.md` | Documentation lifecycle, change control, protected-layer rules |
| `docs/foundations/theory/01-plausible-reasoning.md` | Cox theorem, probability uniqueness, weak syllogism |
| `docs/foundations/theory/02-maxent-grounding.md` | MaxEnt / Min-KL grounding |
| `docs/foundations/theory/03-propositional-operators.md` | Operator minimal kit `{¬, ∧, π}`, derived operators, ↝ soft implication, completeness |
| `docs/foundations/theory/04-reasoning-strategies.md` | Knowledge types + nine reasoning strategies as ↝ micro-structures |
| `docs/foundations/theory/05-formalization-methodology.md` | Scientific text → propositional network methodology |
| `docs/foundations/theory/06-factor-graphs.md` | Propositional network → factor graph mapping, potentials |
| `docs/foundations/theory/07-belief-propagation.md` | BP approximation algorithm |
| `docs/foundations/ecosystem/01-product-scope.md` | Gaia product positioning ("CLI-first, server-enhanced LKM") |
| `docs/foundations/ecosystem/02-decentralized-architecture.md` | Decentralized package mgmt + inference architecture |
| `docs/foundations/ecosystem/03-authoring-and-publishing.md` | Author journey from creation to publish |
| `docs/foundations/ecosystem/04-registry-operations.md` | Registry, dedup, inference-chain activation |
| `docs/foundations/ecosystem/05-review-and-curation.md` | Review server + LKM curation |
| `docs/foundations/ecosystem/06-belief-flow-and-quality.md` | Three-level inference, error correction |
| `docs/foundations/ecosystem/07-related-systems.md` | Adjacent prior-art systems |
| `docs/foundations/gaia-ir/01-overview.md` | Gaia IR overview, frontends/backends, IR vs parameterization, lowering |
| `docs/foundations/gaia-ir/02-gaia-ir.md` | **Hard schema — Knowledge / Operator / Strategy / FormalExpr definitions** |
| `docs/foundations/gaia-ir/03-identity-and-hashing.md` | Object identity, content fingerprint, graph hash |
| `docs/foundations/gaia-ir/04-helper-claims.md` | public / private boundary on structural helper claims |
| `docs/foundations/gaia-ir/05-canonicalization.md` | Local→global canonicalization contract; cross-package relation handling |
| `docs/foundations/gaia-ir/06-parameterization.md` | PriorRecord / StrategyParamRecord / ResolutionPolicy atomic records |
| `docs/foundations/gaia-ir/07-lowering.md` | Backend-facing lowering contract (IR → runtime graph) |
| `docs/foundations/gaia-ir/08-validation.md` | Structural validator contract (object / graph / adjacent-layer) |
| `docs/foundations/gaia-lang/dsl.md` | **Per-name Gaia Lang DSL reference (v0.5 surface + v5 compat)** |
| `docs/foundations/gaia-lang/knowledge-and-reasoning.md` | DSL → IR mapping, Knowledge/Action parallel hierarchies, operator truth tables |
| `docs/foundations/gaia-lang/package.md` | Package model, naming, pyproject.toml, priors.py |
| `docs/foundations/gaia-lang/predicate-logic.md` | Typed predicate-logic layer (Variable, Domain, Formula AST) |
| `docs/foundations/gaia-lang/bayes.md` | `gaia.lang.bayes` lifted authoring surface |
| `docs/foundations/bp/potentials.md` | Factor potential functions per `FactorType` |
| `docs/foundations/bp/inference.md` | How BP runs on Gaia IR; FactorGraph spec |
| `docs/foundations/bp/local-vs-global.md` | Local / joint cross-package / global inference modes |
| `docs/foundations/bp/belief-state.md` | BeliefState schema, local CLI beliefs.json schema |
| `docs/foundations/bp/formal-strategy-lowering.md` | Unified ternary CONDITIONAL lowering, conclusion-prior roles |
| `docs/foundations/cli/workflow.md` | CLI command surface (full canonical list and flags) |
| `docs/foundations/cli/compilation.md` | `gaia compile` / `gaia check` internals |
| `docs/foundations/cli/inference.md` | `gaia infer` pipeline, prior resolution, factor types |
| `docs/foundations/cli/registration.md` | `gaia register` and registry TOML schema |
| `docs/foundations/review/review-pipeline.md` | Local review pipeline, ReviewManifest, inquiry/trace subcommands |
| `docs/foundations/contracts/review-report.md` | `ReviewOutput` data contract (CLI / server shared) |
| `docs/foundations/contracts/rebuttal-report.md` | `RebuttalReport` data contract |

### 1.2 for-users/

| Path | Role |
|---|---|
| `docs/for-users/quick-start.md` | 10-minute walkthrough; canonical user-facing flow |
| `docs/for-users/cli-commands.md` | CLI command reference (user-facing) |
| `docs/for-users/language-reference.md` | DSL cheat sheet (user-facing) |
| `docs/for-users/hole-bridge-tutorial.md` | Cross-package hole / `fills(...)` workflow |

### 1.3 specs/ (selectively current-canonical)

| Path | Role |
|---|---|
| `docs/specs/2026-04-02-gaia-lang-v5-python-dsl-design.md` | Status: Current canonical for Phase 1 structural authoring |
| `docs/specs/2026-04-23-gaia-foundation-spec.md` | Target design — consolidated foundation; defines kernel boundary |
| `docs/specs/2026-05-04-bayes-module-design.md` | Status: Target design (proposal) — drives `gaia.lang.bayes` |
| `docs/specs/2026-05-04-claim-formula-schema-design.md` | Status: Target design — `Claim.formula` + `ClaimKind` |
| `docs/specs/2026-05-05-bayes-actions-design.md` | Companion to bayes module; action-shape semantics |
| `docs/specs/2026-05-05-decompose-action-design.md` | **Implemented design (initial v0.5 surface)** |
| `docs/specs/2026-05-05-role-on-action-graph-design.md` | **Implemented design (initial v0.5 surface)** |
| `docs/specs/2026-04-09-references-and-at-syntax.md` | Reference syntax (`[@label]` / `@label`) |
| `docs/specs/2026-05-10-action-label-references-design.md` | Action label as first-class reference target |
| `docs/specs/2026-04-02-gaia-registry-design.md` | Registry CI / trust model |
| `docs/specs/2026-05-11-lkm-package-integration.md` | Status: Draft — LKM-side, included only for surface awareness |

> Other 2026-03 / 2026-04 specs are migration paths, historical alternatives, or feature explorations; treat as background, not contract.

---

## 2. Protected layers (hard rules from CLAUDE.md)

From `CLAUDE.md` "Protected Layers (Change Control)" (verbatim, translated where helpful):

```
`gaia-ir/` 是 CLI↔LKM 的协议契约层。

硬性规则：
- Agent 禁止直接修改 `docs/foundations/gaia-ir/` 下任何文件
- Agent 禁止直接修改 `docs/foundations/theory/` 下任何文件（纯理论层，外部定义）
- 如果实现中发现 Gaia IR 定义需要调整，必须停下来和用户沟通：
  1. 当前定义是什么
  2. 为什么需要改
  3. 提议的改动内容
- 用户批准后，改动作为独立 PR 提交，不能混在功能 PR 里
- 合并后必须验证所有下游引用（bp/、cli/、lkm/）一致
```

Implication for refactor:

- **Read-only**: `docs/foundations/gaia-ir/`, `docs/foundations/theory/`
- **Source code under `gaia/ir/`** is the implementation backing the protected IR contract. Refactor MAY annotate / docstring / format here, but MUST NOT rename public names, change function signatures, change dataclass / Pydantic field names, change validation behaviour, or change hash inputs without halting and asking the user.
- **`gaia/bp/`, `gaia/lang/`, `gaia/cli/` public API** is constrained by these protected docs even though the code modules themselves are not flagged "protected". Treat their public names as fixed.

Foundations layering rule (verbatim, from `CLAUDE.md`):

```
1. gaia-ir/ 是结构定义的唯一来源（FactorNode、knowledge 节点 schema）。bp/、cli/、lkm/ 引用，不重定义。
2. bp/ 定义计算语义。CLI 和 LKM 引用算法细节。
3. cli/ 拥有 Gaia Lang。LKM 从不引用 Gaia Lang — 它操作 Gaia IR。
4. 跨层定义只链接，不复制。
5. schema 改动先在 gaia-ir/ 改，再验证下游引用。
```

---

## 3. Core invariants

### 3.1 Knowledge identity

Sources: `docs/foundations/gaia-ir/02-gaia-ir.md §1.1`, `03-identity-and-hashing.md §2`, `gaia-lang/knowledge-and-reasoning.md §9`.

- **Object identity (QID, name-addressed):** `{namespace}:{package_name}::{label}`
  - Charset: `namespace` ∈ `[a-z][a-z0-9_]*`; `package_name` ∈ `[a-z0-9][a-z0-9_\-]*`; `label` ∈ `[a-z_][a-z0-9_]*`. Auto-generated labels start `__`.
  - Allowed namespaces in graph validation: `reg` | `paper` | `github` (default).
- **Content fingerprint:** `content_hash = SHA-256(type + content + sorted(parameters))`. **No `package_id`** in the hash.
- **Graph hash:** `LocalCanonicalGraph.ir_hash = sha256:{hex(canonical JSON)}`. Computed by `LocalCanonicalGraph` Pydantic model validator when None.

Three identifiers are **not interchangeable**: QID = "who"; `content_hash` = "what content"; `ir_hash` = "this entire local graph". Verbatim from `03-identity-and-hashing.md §6`:

> "QID 是 name-addressed（'我叫什么'），`content_hash` 是 content-addressed（'我长什么样'），两者不能混用。"

**Local vs imported nodes:** `LocalCanonicalGraph` is a *package-local ownership unit*, **not** a *package-local reference closure*. Foreign QIDs are valid first-class nodes in the graph. Validator does not enforce that all node QIDs share the owner prefix.

### 3.2 Knowledge types (enum)

Source: `gaia-ir/02-gaia-ir.md §1.2`, `08-validation.md §2`.

```
type ∈ {claim, setting, question}
```

- **claim** — only type carrying probability (prior + belief), only type that becomes a BP variable. Closed (`parameters=[]`) or universal (parameters non-empty). Helper claims are still `type=claim`.
- **setting** — background context, no probability. `Setting` / `Context` are deprecated v5 DSL aliases for `note(...)`; the IR type is `setting`.
- **question** — open inquiry, no probability.

`ClaimKind` (DSL-only shape discriminator on `Claim`, not IR `type`):

```
ClaimKind ∈ {GENERAL, PARAMETER, OBSERVATION, QUANTIFIED, CAUSAL}
```

Source: `gaia-lang/knowledge-and-reasoning.md §2.1`.

### 3.3 Operator types (enum) — IR

Source: `gaia-ir/02-gaia-ir.md §2.2`, `bp/potentials.md`, `knowledge-and-reasoning.md §8`.

```
operator ∈ {implication, negation, equivalence, contradiction,
            complement, disjunction, conjunction}
```

Truth-table summary (must not drift; quoted from `02-gaia-ir.md §2.2`):

| operator | variables | conclusion | constraint |
|---|---|---|---|
| `implication` | `[A]` | `B` | A=1 → B=1 |
| `negation` | `[A]` | helper | helper = ¬A |
| `equivalence` | `[A, B]` | helper | A = B |
| `contradiction` | `[A, B]` | helper | ¬(A=1 ∧ B=1) |
| `complement` | `[A, B]` | helper | A ≠ B (XOR) |
| `disjunction` | `[A₁,…,Aₖ]` | helper | ¬(all=0) |
| `conjunction` | `[A₁,…,Aₖ]` | M | M = ∧Aᵢ |

Invariants from `02-gaia-ir.md §2.4`:

1. `variables` IDs must exist and be `type=claim`.
2. `conclusion` must exist and be `type=claim`.
3. `conclusion ∉ variables`.
4. Relation-type conclusions are structural helper claims; not author-authored arbitrary results.
5. Recommended `metadata.canonical_name` (e.g., `not_both_true(A,B)`, `same_truth(A,B)`) — currently lint, not hard error.

### 3.4 Strategy types (enum) — IR

Source: `gaia-ir/02-gaia-ir.md §3.3`, `08-validation.md §4`.

Allowed `Strategy.type` set (`08-validation.md §4 item 5`):

```
infer | noisy_and | deduction | abduction | analogy | extrapolation
| elimination | mathematical_induction | case_analysis
| reductio (deferred)
```

Implementation-side `gaia-ir/02-gaia-ir.md §3.3` also lists `support`, `compare`, `induction`, with `toolcall` and `proof` deferred. Cross-check: the lowering layer in `cli/inference.md` accepts `infer`, `deduction`, `support`, `noisy_and`, `associate`, and the named formal types — these names must remain stable.

Three shapes (class hierarchy):

```
Strategy            — leaf ↝; no sub_strategies, no formal_expr
CompositeStrategy   — has non-empty sub_strategies: list[str]
FormalStrategy      — has formal_expr: FormalExpr (operators list)
```

Mutual exclusion (`02-gaia-ir.md §3.10`): `sub_strategies` and `formal_expr` cannot coexist; `sub_strategies` graph must be a DAG; FormalExpr operator graph must be a DAG. Strategy ID:

```
strategy_id = lcs_{SHA-256(scope + type + sorted(premises) + conclusion + structure_hash)[:16]}
```

Operator ID (when top-level): `lco_{SHA-256(operator + sorted(var_ids) + conclusion_id)[:16]}` — see `cli/compilation.md`.

`noisy_and` is **deprecated**; emits `DeprecationWarning`; lowering preserved for compatibility. Replacement is `support` (a `FormalStrategy`). Verbatim, `02-gaia-ir.md §3.3`:

> "`noisy_and` 已废弃，使用 `support` 替代。"

### 3.5 FactorType (BP runtime) — enum

Source: `bp/inference.md`, `cli/inference.md`, `bp/potentials.md`.

```
FactorType ∈ {IMPLICATION, NEGATION, CONJUNCTION, DISJUNCTION,
              EQUIVALENCE, CONTRADICTION, COMPLEMENT,
              SOFT_ENTAILMENT, CONDITIONAL, PAIRWISE_POTENTIAL}
```

Arity / parameter constraints (`cli/inference.md`):

| FactorType | Parameters | Arity |
|---|---|---|
| `IMPLICATION` | none | exactly 1 premise |
| `NEGATION` | none | exactly 1 premise |
| `CONJUNCTION` | none | ≥ 2 premises |
| `DISJUNCTION` | none | ≥ 2 premises |
| `EQUIVALENCE` | none | exactly 2 premises |
| `CONTRADICTION` | none | exactly 2 premises |
| `COMPLEMENT` | none | exactly 2 premises |
| `SOFT_ENTAILMENT` | `p1`, `p2` with `p1 + p2 > 1` | exactly 1 premise |
| `CONDITIONAL` | `cpt` length `2^k` | ≥ 1 premises |
| `PAIRWISE_POTENTIAL` | `cpt` length 4 | exactly 2 variables, **no conclusion** |

### 3.6 BP semantics constraints

Source: `bp/potentials.md`, `bp/inference.md`, `bp/formal-strategy-lowering.md`.

- **Cromwell's rule** is universal. `CROMWELL_EPS = 1e-3`. Hard logical 0/1 are softened to `eps` / `1 - eps`. Defined in `gaia/bp/factor_graph.py` and `gaia/ir/parameterization.py`. Applied to: `PriorRecord.value`, `StrategyParamRecord.conditional_probabilities`, all factor potentials, all author-supplied `p_e_given_h` / `p_e_given_not_h`.
- **`infer-with-given` gating** (v0.5): with `given=G`, when any of `G` is false the CPT collapses to 0.5 (MaxEnt baseline) — relation neutralizes when its precondition fails. (`cli/inference.md`.)
- **Deduction lowering specialisation:** in BP, accepted deduction maps to `P(C|premises)=1-ε`, `P(C|¬premises)=0.5`. Review acceptance controls only whether the warrant enters the information set `I`; it does not numerically tune the deduction. (`gaia-ir/02-gaia-ir.md §3.3`, `cli/inference.md`.)
- **Conclusion prior role split** (`bp/formal-strategy-lowering.md §2`):
  - **Relation operator** (`equivalence`, `contradiction`, `complement`, `implication`) conclusion uses `π = 1-ε` ("assertion that the relation holds").
  - **Expression operator** (`negation`, `conjunction`, `disjunction`) conclusion uses `π = 0.5` (computed output; belief derived from variables).
- **InferenceEngine auto-selection** (`bp/inference.md`, `cli/inference.md`):
  - treewidth ≤ 15 → JT (exact)
  - 15 < treewidth ≤ 30 → GBP
  - else → loopy BP (approximate)
  - default `bp_damping=0.5`, `bp_max_iter=200`, `bp_threshold=1e-8`.
- **Message format**: 2D vector `[p(x=0), p(x=1)]`, always normalised. Type `Msg = NDArray[float64]` shape `(2,)`.

### 3.7 Helper claim discipline (load-bearing)

Source: `gaia-ir/04-helper-claims.md`.

Hard rules:

- Helper claim is `Knowledge(type=claim)`; **not a new primitive**.
- **Private FormalExpr nodes are forbidden from external reference** — required for the marginalization-based fold guarantee.
- **Private FormalExpr nodes MUST NOT carry independent `PriorRecord`.** Any claim that needs a prior must be promoted to a strategy interface (`premises` or `conclusion`).
- Helper claims default to no independent prior. Distribution is fully determined by the Operator's truth table.
- Helper-kind metadata is a recommended convention (`helper_kind`, `helper_visibility`, `canonical_name`), not a hard schema field.

### 3.8 Parameterization atomic records

Source: `gaia-ir/06-parameterization.md`.

Three persistent record types:

```
PriorRecord:           knowledge_id, value, source_id, created_at
StrategyParamRecord:   strategy_id, conditional_probabilities, source_id, created_at
ParameterizationSource: source_id, model, policy, config, created_at
```

Rules:

- `PriorRecord` only for `type=claim`.
- `StrategyParamRecord` only for parameterized Strategy: currently `infer`, `noisy_and` (deprecated). Direct FormalStrategy uses **no** persistent strategy-level record; its conditional view is computed from `FormalExpr` + interface-claim priors at runtime.
- Resolution policy: `latest` or `source:<source_id>`.
- `prior_cutoff` (ISO 8601) filters records for reproducibility.

---

## 4. API surface to preserve

These names are mentioned in foundations docs. Renames are forbidden unless the user explicitly signs off. Citations point to the doc that names each surface.

### 4.1 `gaia.ir` (IR primitives) — public symbols

From `gaia-ir/01-overview.md` "源代码" section (verbatim listing):

- `gaia/gaia_ir/knowledge.py` — `Knowledge`, `KnowledgeType`, `make_qid`, `is_qid`
- `gaia/gaia_ir/graphs.py` — `LocalCanonicalGraph`
- `gaia/gaia_ir/operator.py` — `Operator`, `OperatorType`
- `gaia/gaia_ir/strategy.py` — `Strategy`, `CompositeStrategy`, `FormalStrategy`, `FormalExpr`, `StrategyType`
- `gaia/gaia_ir/formalize.py` — `formalize_named_strategy`, `FormalizationResult`
- `gaia/gaia_ir/parameterization.py` — `PriorRecord`, `StrategyParamRecord`, `ParameterizationSource`
- `gaia/gaia_ir/validator.py` — `validate_local_graph`, `validate_parameterization`

> **Caveat.** Foundations doc lists the module path as `gaia/gaia_ir/`, but `language-reference.md` "Common Anti-Patterns" tells users to `from gaia.ir import ...` rather than `from gaia.gaia_ir import ...`. The actual repo uses `gaia/ir/`. Treat `gaia.ir` (no double `gaia_ir`) as the live import path. Refactor MUST NOT rename modules or top-level public symbols within them.

Also from `gaia-ir/06-parameterization.md`: add `ResolutionPolicy` to the parameterization module's public surface.

Composition: `gaia/ir/compose.py` exposes `Compose` as a first-class IR node (`composes: list[Compose]` on `LocalCanonicalGraph`). See `gaia-lang/knowledge-and-reasoning.md §3.5`.

Review: `gaia/ir/review.py` exposes `Review`, `ReviewManifest`, `ReviewStatus` enum. See `review/review-pipeline.md §2`.

### 4.2 `gaia.bp` (BP runtime) — public symbols

From `bp/inference.md` "源代码":

- `gaia/bp/factor_graph.py` — `FactorGraph`, `FactorType`, `CROMWELL_EPS`
- `gaia/bp/lowering.py` — `lower_local_graph()`, `merge_factor_graphs()`
- `gaia/bp/bp.py` — `BeliefPropagation`, `run_with_diagnostics()`, `BPDiagnostics`
- `gaia/bp/junction_tree.py` — Junction Tree exact inference
- `gaia/bp/gbp.py` — Generalized BP
- `gaia/bp/exact.py` — brute-force exact inference for small graphs (`exact_inference`)
- `gaia/bp/engine.py` — `InferenceEngine`
- `gaia/bp/potentials.py` — per-`FactorType` potential functions
- `gaia/bp/contraction.py` — tensor contraction utilities

Signatures verbatim from docs:

- `lower_local_graph(graph, node_priors=None)` — `bp/inference.md` "从 Gaia IR 构建" section.
- `InferenceEngine()` with defaults `bp_max_iter=200, bp_threshold=1e-8, bp_damping=0.5, jt_max_treewidth=15, gbp_max_treewidth=30` — `cli/inference.md`.
- `merge_factor_graphs()` merges per-package factor graphs with prefixed IDs (`dep_{import_name}_{fid}`, `local_...`) — `cli/inference.md`, `bp/local-vs-global.md`.

### 4.3 `gaia.lang` — public DSL exports

Public re-exports listed verbatim in `gaia-lang/dsl.md` "Overview":

```python
from gaia.lang import (
    # Knowledge
    claim, note, question, Domain,
    # Formula primitives
    Variable, Nat, Real, Probability, Bool,
    ClaimAtom, Constant, FunctionSymbol, FunctionApp,
    PredicateSymbol, UserPredicate,
    Equals, NotEquals, Greater, GreaterEqual, Less, LessEqual, Causes,
    land, lor, lnot, implies, iff, forall, exists,
    # Structured-formula sugar
    parameter, causal,
    # Action verbs (recommended v0.5 surface)
    observe, derive, compute, predict, infer, associate,
    equal, contradict, exclusive, decompose,
    depends_on,
    compose,
    # Lifted Bayes (lazy)
    bayes,
    # Compatibility aliases / legacy / experimental
    setting, context,
    contradiction, equivalence, complement, disjunction,   # v5 compat
    support, compare, deduction, abduction, induction,     # legacy strategies
    analogy, extrapolation, elimination, case_analysis,
    mathematical_induction, composite, fills,
    # noisy_and,  # deprecated; lowers to legacy support
)
```

Also exported runtime dataclasses (per `dsl.md`):

`Knowledge`, `Claim`, `Note`, `Question`, `Action`, `Compose`, `Strategy`, `Step`, `Operator`, plus role-projection helpers `roles_for_claim` / `roles_for_package`.

User-facing reference (`docs/for-users/language-reference.md`) also lists `not_, and_, or_` (deprecated propositional shortcuts), `candidate_relation`, `tension` — all must continue to import.

Bayes module functions (`gaia-lang/bayes.md`): `bayes.model`, `bayes.likelihood`, `bayes.predict` (deprecated alias for `bayes.model`); distribution literals `Binomial`, `Poisson`, `Normal`, `Beta`, `Exponential`, `LogNormal`, `StudentT`, `Cauchy`, `Gamma`, `ChiSquared`.

Logic analysis (`gaia-lang/dsl.md` "Propositional Analysis Helpers", `language-reference.md`):

```python
from gaia.logic import (
    simplify_proposition, to_cnf_proposition, to_dnf_proposition,
    to_nnf_proposition, are_equivalent, is_satisfiable,
)
```

### 4.4 Function signatures stated in foundations docs

Action verbs — preserve exactly (`dsl.md`, `language-reference.md`):

```python
claim(content, *, title=None, background=None, parameters=None, provenance=None, **metadata) -> Knowledge
note(content, *, title=None, format="markdown", **metadata) -> Knowledge
question(content, *, title=None, **metadata) -> Knowledge

observe(conclusion, *, given=(), background=None, rationale="", label=None)
derive(conclusion, *, given=(), background=None, rationale="", label=None)
compute(ClaimType, *, fn=None, given=(), background=None, rationale="", label=None)
predict(conclusion, *, given=(), background=None, rationale="", label=None)
infer(evidence, *, hypothesis, given=(), p_e_given_h, p_e_given_not_h=0.5, background=None, rationale="", label=None)
associate(a, b, *, p_a_given_b, p_b_given_a, prior_a=None, prior_b=None, background=None, rationale="", label=None)
decompose(whole, *, parts, formula, background=None, rationale="", label=None, metadata=None)
depends_on(conclusion, *, given, rationale="", label=None)

@compose(name, version, background=None, warrants=None, rationale="", label=None)
```

Bayes (`bayes.md` "Verbs at a Glance"):

```python
bayes.model(hypothesis, *, observable, distribution,
            background=None, rationale="", label=None, metadata=None) -> Claim
bayes.likelihood(data, *, model, against=(), background=None, rationale="",
                 label=None, exclusivity="pairwise_contradiction",
                 precomputed=None, metadata=None) -> Claim
```

Relation verbs (`dsl.md`, `language-reference.md`) — `equal(a, b, ...)`, `contradict(a, b, ...)`, `exclusive(a, b, ...)`. Each takes `background=`, `rationale=`, `label=`.

Legacy v5 operators / strategies (`dsl.md` "v5 Compatibility Operators"; `language-reference.md`) — keep signatures but expect `DeprecationWarning`:

```python
contradiction(a, b, *, reason="", prior=None) -> Knowledge
equivalence(a, b, *, reason="", prior=None) -> Knowledge
complement(a, b, *, reason="", prior=None) -> Knowledge
disjunction(*claims, reason="", prior=None) -> Knowledge

support(premises, conclusion, *, background=None, reason="", prior=None)
deduction(premises, conclusion, *, background=None, reason="", prior=None)
compare(pred_h, pred_alt, observation, *, background=None, reason="", prior=None)
abduction(support_h, support_alt, comparison, *, background=None, reason="")
induction(support_1, support_2, law, *, background=None, reason="")
analogy(source, target, bridge, *, background=None, reason="")
extrapolation(source, target, continuity, *, background=None, reason="")
elimination(exhaustiveness, excluded, survivor, *, background=None, reason="")
case_analysis(exhaustiveness, cases, conclusion, *, background=None, reason="")
mathematical_induction(base, step, conclusion, *, background=None, reason="")
composite(premises, conclusion, *, sub_strategies, background=None, reason="", type="infer")
fills(source, target, *, mode=None, strength="exact", background=None, reason="")
noisy_and(...)  # deprecated; lowers to support
```

For these legacy verbs, the spec rule "`reason` and `prior` must be paired: both or neither" must remain enforced.

### 4.5 CLI command surface

Source: `docs/foundations/cli/workflow.md`, `docs/for-users/cli-commands.md`, `README.md`.

```
gaia init <NAME>
gaia compile [PATH]
gaia check [PATH] [--brief] [--show <module|label>] [--hole]
gaia add <PACKAGE> [--version VERSION] [--registry REPO]
gaia infer [PATH] [--depth N]                       # N ∈ {0, ≥1, -1}
gaia render [PATH] [--target docs|github|all]
gaia register [PATH] [--tag TAG] [--repo URL]
                       [--registry-dir PATH]
                       [--registry-repo SLUG] [--create-pr]
gaia inquiry focus|obligation|hypothesis|reject|tactics|review
gaia trace verify|review|show
gaia starmap [PATH] [--format html|dot|svg]
                    [--theme light|stellaris|dark] [--out OUTPUT]
gaia starmap-replay [PATH]                           # experimental
```

The `--target obsidian` flag also appears in `docs/for-users/cli-commands.md`. Treat as part of the surface even though `workflow.md` lists only `docs|github|all` — confirm before removing.

Default behaviours that are contract:

- `gaia init` package name must end with `-gaia` (`package.md`, `cli-commands.md`).
- `gaia render --target github` strictly requires fresh `beliefs.json`; `--target docs` works without inference; `--target all` degrades to docs-only on missing beliefs.
- `gaia infer --depth 0` injects flat priors from `.gaia/dep_beliefs/`; `--depth N>0` merges dependency factor graphs.
- `gaia compile` is deterministic — same source → same `ir_hash`.

Entry point: installed `gaia` command via `pyproject.toml [project.scripts]`, backed by Typer app at `gaia.cli.main:app` (`cli/workflow.md`).

### 4.6 Persisted artifacts under `.gaia/`

From `cli/workflow.md`, `package.md`, `bp/belief-state.md`, `review/review-pipeline.md`, `cli/inference.md`:

| Path | Owner |
|---|---|
| `.gaia/ir.json` | `gaia compile` — `LocalCanonicalGraph` JSON |
| `.gaia/ir_hash` | `gaia compile` — SHA-256 of canonical IR |
| `.gaia/compile_metadata.json` | `gaia compile` — `gaia_lang_version`, `compiled_at`, `ir_hash` |
| `.gaia/formalization_manifest.json` | `gaia compile` — scaffolds: `depends_on`, `candidate_relation`, `tension` |
| `.gaia/beliefs.json` | `gaia infer` — local CLI schema with `beliefs: list[record]` |
| `.gaia/dep_beliefs/<pkg>.json` | `gaia add` — upstream beliefs (gitignored) |
| `.gaia/review_manifest.json` | `gaia inquiry review` / `gaia infer` — persisted merged manifest |
| `.gaia/inquiry/state.json`, `tactics.jsonl`, `reviews/<id>.json` | `gaia inquiry *` |
| `.gaia/trace/...` | `gaia infer` — hash-chained ARM traces |
| `.gaia/starmap.{html,dot,svg}` | `gaia starmap` |
| `.gaia/starmap-replay.html` | `gaia starmap-replay` (experimental) |
| `.gaia/parameterization.json` | optional; `gaia render` cross-checks `ir_hash` if present |
| `.gaia/review/review_output.json` | `ReviewOutput` payload (`contracts/review-report.md`) |
| `.gaia/review/rebuttal.json` | `RebuttalReport` payload (`contracts/rebuttal-report.md`) |
| Registry-side: `packages/<name>/{Package,Versions,Deps}.toml` | `gaia register` (`cli/registration.md`) |

`beliefs.json` schema fields (verbatim, `cli/inference.md`): `ir_hash`, `gaia_lang_version`, `beliefs: [{knowledge_id, label, belief}]`, `diagnostics: {converged, iterations_run, max_change_at_stop, treewidth, belief_history, direction_changes}`.

LKM-side `BeliefState` schema (different — `bp/belief-state.md`): `bp_run_id`, `created_at`, `resolution_policy`, `prior_cutoff`, `beliefs: dict[gcn_id, float]`, `compilation_summary`, plus diagnostics. **Do not conflate the two schemas.**

---

## 5. Type / Pydantic conventions

Source: `CLAUDE.md` "Code Style":

> "- Ruff，line length 100，target Python 3.12
> - 类型注解用 PEP 604（`X | None`，不是 `Optional[X]`）
> - Google-style docstrings
> - Pydantic v2 API：`.model_dump()` / `.model_validate()` / `.model_validate_json()`"

Implications for the refactor:

- **PEP 604 only** for new annotations. `X | None` over `Optional[X]`. `list[X]` over `List[X]`. Future-import `annotations` may already be in use; do not drop without confirming each file.
- **Pydantic v2 API surface**: `.model_dump()`, `.model_validate()`, `.model_validate_json()`. Pydantic v1 calls (`.dict()`, `.parse_obj()`, `.json()`) are not allowed in new code.
- IR primitives that the docs describe as Pydantic models include `Knowledge` (validator generating `content_hash`), `LocalCanonicalGraph` (validator generating `ir_hash`), `Review`, `ReviewManifest`. Do not change validators' input/output shape.
- Numpy types: `Msg = NDArray[float64]` shape `(2,)` (`bp/inference.md`).

Cromwell constant naming: `CROMWELL_EPS = 1e-3`, defined in `gaia/ir/parameterization.py` and `gaia/bp/factor_graph.py` (`gaia-lang/knowledge-and-reasoning.md §10`). Both definitions must remain available under their current names.

---

## 6. Docstring conventions

Source: `CLAUDE.md`.

- **Google-style docstrings** for all new / refactored Python.
- Module-level docstrings should state purpose; class docstrings cover invariants; function docstrings document `Args:`, `Returns:`, `Raises:`, `Examples:` as needed.
- Existing executable code blocks in user docs (e.g. the `# testable` Mendel block in `bayes.md`) imply doctest-style verifiability — preserve their exact semantics if you docstring around the same functions.

No other doc-style constraints are stated in foundations docs.

---

## 7. Naming / module boundary rules

Source: `CLAUDE.md` "Foundations 分层规则" and "Documentation Policy".

Module dependency direction (downward only):

```
gaia-lang (DSL)  →  gaia-ir  →  bp
                              ↘
                                cli, lkm
theory  (external; no upward deps)
ecosystem, contracts, review (cross-cutting; reference, do not redefine)
```

Hard rules:

1. **`gaia-ir/` is the single source for structure definitions** (FactorNode, Knowledge schema). `bp/`, `cli/`, `lkm/` reference, never redefine.
2. **`cli/` owns Gaia Lang.** `lkm/` MUST NOT import `gaia.lang` — LKM operates on Gaia IR only.
3. **No content duplication across layers** — only links.
4. Schema changes start in `gaia-ir/`, then verify downstream references in `bp/`, `cli/`, `lkm/`.

CLI surface invariant (`cli/workflow.md`):

- `gaia inquiry *` and `gaia trace *` "do not produce or mutate IR, priors, or beliefs". They are read-only relative to compile / infer artifacts.

Cross-layer renaming forbidden without explicit user sign-off. In particular:

- `gaia/ir/{knowledge,operator,strategy,formalize,parameterization,graphs,validator,compose,review}.py` module names are part of the contract surface.
- The legacy `gaia.lang` re-exports (`setting`, `context`, v5 strategies, `noisy_and`, `not_`, `and_`, `or_`) MUST remain importable; they may keep `DeprecationWarning`.

Forbidden patterns:

- Import `gaia.gaia_ir` (path doesn't exist in code). Use `gaia.ir`. (`language-reference.md` "Common Anti-Patterns".)
- Define `__all__` in package submodules (only in `__init__.py`). (`language-reference.md`.)
- Manually set `.label = "name"`; always assign to a named variable. (`language-reference.md`.)
- Assign external priors to derived / helper / generated-formalization claims. (`package.md`, `language-reference.md`, `cli/inference.md`.)
- `reason` without `prior` (or vice versa) in legacy strategy/operator verbs. (`dsl.md`, `language-reference.md`.)
- `Claim.__bool__` raises — do not allow `if claim:`. (`dsl.md`.)

---

## 8. Behavior contracts (from for-users docs)

These are user-visible contracts. Breaking them silently is a regression.

### 8.1 Prior assignment contract (`docs/for-users/cli-commands.md`, `language-reference.md`, `package.md`, `cli/inference.md`)

- External priors only on independent probabilistic inputs to exported goals.
- Zero-premise `observe(...)` pins its conclusion to `1 - CROMWELL_EPS`; no separate external prior.
- Claims concluded by `derive(...)`, `compute(...)`, or `observe(..., given=...)` get their belief from the graph and MUST NOT receive manual priors.
- Structural/helper claims from `~`, `&`, `|`, `infer(...)`, `associate(...)`, `equal(...)`, `contradict(...)`, `exclusive(...)`, `decompose(...)`-generated helpers, and generated formalization internals MUST NOT receive priors.
- Independent inputs left without an external prior fall back to Jaynes MaxEnt over remaining DOF, subject to hard constraints.
- Prior values must satisfy Cromwell bounds: `[CROMWELL_EPS, 1 - CROMWELL_EPS] = [1e-3, 0.999]`.
- `priors.py` is the canonical path for inputs in v0.5. Legacy `reason+prior` DSL pairing is retained for compatibility.

### 8.2 Claim role enumeration (`docs/for-users/cli-commands.md`)

`gaia check` reports each claim under one role:

```
Independent | Derived | Structural/helper | Background-only | Orphaned
```

### 8.3 Reference syntax (`gaia-lang/dsl.md`, spec `2026-04-09-references-and-at-syntax.md`, spec `2026-05-10-action-label-references-design.md`)

- `[@label]` — strict reference; missing key is compile error.
- `@label` — opportunistic; missing key renders literal.
- `\@label` — escape.
- `label` resolves to either Knowledge label or Action label (the action's primary IR target; warrant helper claim QID for support / probabilistic / structural actions; conclusion claim QID for zero-premise `observe`; not addressable for `depends_on`).
- Invariants: (1) a key cannot exist in both label table and `references.json`; (2) Knowledge label and Action label cannot collide within the same package; (3) a single `[...]` group cannot mix knowledge refs and citations.

### 8.4 Package naming convention (`gaia-lang/package.md`)

```
GitHub repo   : CamelCase.gaia                  e.g. GalileoFallingBodies.gaia
PyPI package  : kebab-case-gaia                 e.g. galileo-falling-bodies-gaia
Python import : snake_case (no -gaia suffix)    e.g. galileo_falling_bodies
Source dir    : snake_case/
```

Derivation rule (not configurable): `import_name = pypi_name.removesuffix("-gaia").replace("-", "_")`.

### 8.5 Compile / register pre-conditions (`cli/registration.md`)

- `[tool.gaia].uuid` set and valid; `[tool.gaia].type == "knowledge-package"`.
- `gaia compile` produces fresh `.gaia/ir_hash`.
- `gaia check` passes.
- Git worktree clean; tag `v<version>` exists, points to HEAD, pushed to origin; repo is on GitHub.

### 8.6 ARM trace exit codes (`review/review-pipeline.md §6`)

```
gaia trace verify  : 0 clean / 1 chain mismatch / 2 schema error
gaia trace review  : 0 clean / 1 error diagnostic (or --strict warning) / 2 invalid CLI args
gaia trace show    : 0 / 2
```

### 8.7 Versions.toml `gaia_lang_version` field (`cli/registration.md`)

- Read from `.gaia/compile_metadata.json` at register time, **not** from the live process.
- Legacy packages missing the field emit `"unknown"` plus a warning.
- Renderer respects native TOML types; complex types (arrays, nested tables, datetimes) on unknown fields are rejected, not silently coerced.

---

## 9. Caveats / risk surface

Areas where docs are inconsistent, in flux, or call out "design under flux". Refactor work that touches these must double-check current behaviour against tests, not assume one doc is authoritative.

1. **Module path mismatch.** `gaia-ir/01-overview.md` lists source files under `gaia/gaia_ir/...`. The live import path used in user-facing docs and code is `gaia.ir`. Treat `gaia.ir` as canonical; the foundations doc's `gaia_ir/` path is stale wording.
2. **`StrategyType` enum drift.** `gaia-ir/02-gaia-ir.md §3.3` lists `support`, `compare`, `noisy_and (deprecated)`, named formal types, `reductio (deferred)`, `induction (deferred from FormalStrategy form)`, `toolcall (deferred)`, `proof (deferred)`. `08-validation.md §4` allows: `infer | noisy_and | deduction | abduction | analogy | extrapolation | elimination | mathematical_induction | case_analysis | reductio (deferred)` — **`support` is not listed by the validator** but is clearly named-canonical in the DSL. Verify which set the live validator actually enforces and preserve that exactly.
3. **`reductio` / `induction` lifecycle.** Both deferred at IR core. `induction` exists as DSL legacy verb; theory `04-reasoning-strategies.md` retains it. Don't accidentally bring either into the core IR primitive set.
4. **`CompositeStrategy` fold-time parameter source is undefined.** Verbatim from `gaia-ir/06-parameterization.md` and `07-lowering.md`:
   > "**Open question：CompositeStrategy 折叠时的参数来源。** 当前 contract 只定义了参数化 leaf Strategy（读 StrategyParamRecord）和 FormalStrategy（从 FormalExpr + claim prior 导出）的折叠路径。CompositeStrategy 折叠为单个单元时的条件概率来源尚未定义。"
5. **`relation_var` migration.** `bp/potentials.md` "与旧五类因子的迁移对照" lists migrations from old factor types. Make sure code does not still expose obsolete `relation_var`-style FactorType names.
6. **`infer` two forms.** `gaia.lang` `infer(...)` has two signatures: v0.5 (`evidence, hypothesis=..., given=..., p_e_given_h=..., p_e_given_not_h=0.5`) and legacy v5 (`premises, conclusion, ...`). The legacy form is deprecated but supported. Don't collapse them into one.
7. **`type` parameter on `composite(...)`.** The legacy `composite(..., type="infer")` carries a `type` keyword that shadows Python's builtin. Tolerate the shadowing — it's part of the documented signature.
8. **`namespace` validation set.** `08-validation.md §6` says `namespace ∈ {reg | paper}`. User docs default it to `github`. Live behaviour is "default `github`"; the validator likely accepts `github` too. Preserve current acceptance set; do not narrow.
9. **`noisy_and` deprecation behaviour.** Emits `DeprecationWarning`; lowering still works; auto-converts to `support` / `CONJUNCTION + SOFT_ENTAILMENT`. Three docs make slightly different claims about whether the conversion happens at compile or at lowering — keep current implementation, don't refactor "to clean it up".
10. **`gaia.logic` analysis backend.** Helpers convert IR operator graphs into a Boolean backend for analysis. The backend representation is non-persistent; Gaia IR remains source of truth (`dsl.md` "Propositional Analysis Helpers"). Don't accidentally make these helpers mutate IR.
11. **`Compose` IR node parameter shape.** `Compose` is the only `Action` subclass that survives as a first-class IR node (`composes: list[Compose]` on `LocalCanonicalGraph`). Structure_hash format: `lcm_{structure_hash}` over canonicalised payload (`knowledge-and-reasoning.md §9`). Don't rename to `lcc_` or similar.
12. **Bayes Cromwell clamp interaction with calibrated factors.** `bayes.md` "Worked Example" explicitly notes that calibrated Bayes factors above the clamp ceiling (~498) lose calibration but preserve ranking. Don't try to "fix" the clamp; it is intentional.
13. **`@compose` warrants vs child warrants.** `knowledge-and-reasoning.md §3.5`: child action warrants stay owned by their child actions; compose-level warrants are only the ones passed to `@compose(...)`. Easy to break in a refactor that touches warrant flow.
14. **`fills(...)` registry-side validation.** `for-users/hole-bridge-tutorial.md` describes a pre-existing compile-time validation against the dep package's `premises.json` / `holes.json` manifests. The flow uses `target_qid` + `target_interface_hash` rather than the Python `from … import name` alone. Easy to silently break by reordering compile passes.
15. **LKM-side specs included as Draft only.** `docs/specs/2026-05-11-lkm-package-integration.md` is Status: Draft. The LKM foundations layer has been migrated to a different repo (`gaia-lkm`). Don't pull LKM internals into this repo's refactor.
16. **Validator's `Strategy.type` allowed set vs deprecated set.** `08-validation.md §4 item 5` explicitly lists `noisy_and` as allowed even while `02-gaia-ir.md` marks it deprecated. Keep validator accepting both deprecated and current names — emit deprecation warnings, never raise.
17. **`gaia.gaia_ir` import path mention.** `gaia-ir/01-overview.md` references `gaia/gaia_ir/...` as the source layout. The actual repo uses `gaia/ir/`. The doc layer is stale, not the code. Don't "fix" the code path to match the doc — fix would break user imports.

---

## 10. Open questions (docs silent / probable refactor friction)

Things the refactor will likely touch where the foundations docs do not give a clean answer:

1. **`gaia/lang/runtime/*.py` public re-exports** — `dsl.md` lists names but does not enumerate which are dataclasses vs functions vs aliases. Use the existing `gaia/lang/__init__.py` `__all__` (if present) or `from gaia.lang import …` test cases as the source of truth, not an over-written re-export.
2. **Module-internal helper renames.** Foundations docs are silent on private helpers like `_action_label`, `_build_node_priors`, `_OPERATOR_MAP`. These can technically be renamed during refactor, but they are referenced by name in foundations docs (e.g., `cli/compilation.md` cites `_OPERATOR_MAP`). Keep names matching the doc text where docs name them.
3. **Coverage target for legacy / deprecated paths.** 90% coverage target — does it apply to deprecated DSL verbs (`noisy_and`, legacy `support`, v5 `contradiction(...)` etc.)? Foundations docs are silent. Default: cover them; deletion needs sign-off.
4. **mypy strict and `Any` in legacy adapters.** `bayes.md` references `metadata: dict[str, Any] | None`. mypy strict may need `# type: ignore` islands. Document any pragma usage rather than refactoring the API.
5. **Pydantic v2 model validators on `Knowledge` / `LocalCanonicalGraph`.** Knowledge's `content_hash` is computed by a model validator (`knowledge-and-reasoning.md §9 "Identity assignment"`); LocalCanonicalGraph's `ir_hash` is computed by a model validator (`gaia/ir/graphs.py:_canonical_json`). These validators MUST run with `mode="after"` to compute derived fields — confirm before annotating.
6. **`gaia.cli.commands.*` Typer command signatures.** Docstrings on these become user-visible `--help` output. Google-style docstrings are stated as policy, but Typer renders the docstring text directly. Validate that refactored docstrings don't mangle `--help` output.
7. **Dataclasses with `kw_only=True` vs Pydantic models.** `gaia.lang.runtime.{knowledge,action,composition}` are described as dataclass-style, while `gaia.ir.review` is Pydantic `BaseModel`. Don't accidentally migrate one to the other.
8. **`StrategyParamRecord.conditional_probabilities` length contract for `infer`.** `gaia-ir/06-parameterization.md` says length is `2^k` where `k = len(premises)`. Cli/inference.md says "1+ premises". For `infer` with `given=G`, the action computes a `2^(k+1)`-entry CPT where `k = len(G)`. Tests should verify both shapes before any refactor that touches `_build_factor_params` or `lower_local_graph`.
9. **`exclusivity` value validation in `bayes.likelihood`.** Three accepted values: `"none"`, `"pairwise_contradiction"`, `"exhaustive_pairwise_complement"`. Live validator behaviour on unknown strings is undocumented.
10. **Trace schema fields and hash chain algorithm.** `review/review-pipeline.md §6` references `gaia/trace/schema.py` and `gaia/trace/hashing.py` but does not give the hash function. Don't change without separate spec work.
11. **`gaia.starmap-replay` "experimental scaffold v4, frozen".** `README.md` calls it experimental and frozen. Refactor should leave its public surface untouched even if internals look stale.
12. **Anonymous label counter.** `cli/compilation.md` "Anonymous counter is sequential per compilation" — order-sensitive; tests will be sensitive to dict iteration order. Make sure mypy / ruff fixes don't inadvertently change iteration order over `pkg.knowledge`.

---

## 11. Refactor checklist (derived; non-normative)

> The following is **not** a contract; it is a working derived checklist for downstream agents.

- [ ] Treat `gaia/ir/` as touch-with-care; any change to a public symbol there must pause and ask the user.
- [ ] Preserve every name in §4 (`gaia.ir`, `gaia.bp`, `gaia.lang`, CLI commands, artifact paths).
- [ ] Preserve every function signature in §4.4.
- [ ] Use PEP 604 annotations, Google docstrings, Pydantic v2 API (§5, §6).
- [ ] Re-read foundations docs before renaming any private helper that is name-cited in the docs (§10 item 2).
- [ ] Keep `noisy_and`, legacy v5 verbs, and `not_/and_/or_` shortcuts importable with `DeprecationWarning` (§4.3, §4.4).
- [ ] Cover BP / lowering edge cases by tests rather than refactoring the lowering tables (§9 items 4, 9, 16).
- [ ] Do NOT modify `docs/foundations/gaia-ir/` or `docs/foundations/theory/` (§2).
