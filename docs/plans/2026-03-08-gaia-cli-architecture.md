# Gaia CLI Architecture Design

**Date**: 2026-03-08
**Status**: Approved

## 1. Design Philosophy

Gaia is a **proof assistant for probabilistic defeasible reasoning**, extending the Lean model with probabilistic semantics. The CLI maps directly to this analogy:

| Lean Concept | Gaia Equivalent |
|---|---|
| Source file (.lean) | Package YAML (package.yaml + module YAMLs) |
| Elaboration | `gaia build`: resolve refs, instantiate parameters, expand templates |
| Kernel check | `gaia infer`: compile FG + BP computes belief distribution |
| Tactic (constructs proof) | `gaia review`: LLM reviews reasoning chains, determines dependency strengths, estimates priors |
| `lake upload` | `gaia publish`: publish to git/server |

**Key difference from Lean**: Lean's kernel is accept/reject (binary). Gaia's BP kernel produces a belief distribution. Lean's tactics are part of elaboration (deterministic once tactic is chosen), while Gaia's "tactics" (LLM review) are non-deterministic and separated into their own command.

**Two kernels**: BP checks structure (probability propagation on factor graph). LLM checks content (reasoning quality, dependency classification). Both are needed for complete verification.

**Why review must precede FG compilation**: The LLM review determines which dependencies are `direct` (strong) vs `indirect` (weak), and may introduce new Claims to localize uncertainty. These decisions change the structure of the factor graph. Therefore: `build` (elaborate) → `review` (LLM determines structure) → `infer` (compile FG + BP).

## 2. Command Set

### 2.1 Core Lifecycle (4 commands)

```
gaia build <path>                  Elaborate: parse + resolve + instantiate params
gaia review                        LLM reviews chains → sidecar report (.gaia/reviews/)
gaia infer [--review <path>]       Compile FG (from review) + BP → beliefs
                                   Default: uses latest review. Error if none exists.
gaia publish                       Publish to git or server
```

### 2.2 Auxiliary (4 commands)

```
gaia init                          Initialize a new knowledge package
gaia show <name>                   Show declaration details + connected chains
gaia search <query>                Search declarations within the package
gaia clean                         Remove build artifacts (.gaia/)
```

### 2.3 Command Details

#### `gaia build <path>`

Deterministic elaboration. Prepares the package for review and inference.

**Steps**:
1. **Parse** — YAML → Package AST (Pydantic models)
2. **Resolve** — Link Ref declarations to their targets
3. **Elaborate** — Instantiate parameters, expand templates:
   - Substitute `{prediction_a}` in InferAction with actual Claim content
   - Expand ChainExpr steps into fully-realized prompt context
   - Fold `indirect` dependency (Setting) content into context
   - Output "LLM-ready" elaborated structures

**Output**: `.gaia/build/` artifacts (elaborated package)

**Does NOT compile FactorGraph** — FG compilation requires dependency strength decisions from review.

**Properties**: Deterministic, cacheable, reproducible. Can be re-run idempotently.

#### `gaia review`

LLM reviews elaborated ChainExprs and produces a sidecar report.

**Input**: Elaborated package from `gaia build`
**Output**: Sidecar report in `.gaia/reviews/` (does NOT modify source YAML)
**Properties**: Non-deterministic (LLM-dependent). Can be re-run.

**What review does for each ChainExpr**:

1. **Estimate priors for uncertain steps**: If a StepApply or StepLambda's reasoning is not fully certain, estimate a `prior` and optionally suggest a rewrite — extract the uncertainty into a new strongly-referenced Claim so that uncertainty is localized rather than spread across the reasoning. If the LLM cannot determine how to rewrite, skip the rewrite.

2. **Classify dependencies**: For each Arg in each step, determine whether it is:
   - `direct` (strong): if this premise is wrong, the conclusion does not hold
   - `indirect` (weak): even if this premise is wrong, the conclusion may still hold

**Sidecar report format**:

```yaml
# .gaia/reviews/review_2026-03-08.yaml
package: galileo_falling_bodies
model: claude-sonnet-4-20250514
timestamp: 2026-03-08T14:30:00Z
chains:
  - chain: contradiction_chain
    steps:
      - step: 2
        assessment: valid
        suggested_prior: 0.97
        rewrite: null
        dependencies:
          - ref: tied_pair_slower_than_heavy
            suggested: direct
          - ref: tied_pair_faster_than_heavy
            suggested: direct
  - chain: synthesis_chain
    steps:
      - step: 2
        assessment: valid
        suggested_prior: 0.88
        rewrite:
          new_claim:
            name: inclined_plane_relevance
            content: "斜面实验的结果可以推广到自由落体场景"
            prior: 0.75
          rewritten_step: "..."
        dependencies:
          - ref: aristotle_contradicted
            suggested: direct
          - ref: air_resistance_is_confound
            suggested: direct
          - ref: inclined_plane_supports_equal_fall
            suggested: direct  # was indirect, review suggests upgrading
```

#### `gaia infer [--review <path>]`

Compile factor graph and run belief propagation. **Requires a review file.**

**Default**: Reads the most recent review file from `.gaia/reviews/`. If no review file exists, **exits with an error** prompting the user to run `gaia review` first.

**With `--review xxx.yaml`**: Uses the specified review file instead of the latest.

**Steps**:
1. Read elaborated package from `.gaia/build/`
2. Read review sidecar (latest or specified): merge suggested `dependency` classifications and `prior` estimates
3. **Compile** — Build FactorGraph:
   - Variables from exported Claims and Settings
   - Factors from StepApply/StepLambda in ChainExprs
   - Only `direct` dependencies become factor inputs
   - `indirect` dependencies are excluded from FG
4. **Run BP** — Belief propagation on the compiled FG
5. Output belief distribution

**Typical workflow**:
```bash
gaia build .        # elaborate
gaia review         # LLM determines deps + estimates priors
gaia infer          # compile FG (using latest review) + BP
```

#### `gaia publish`

Publish the knowledge package to a shared system.

**Modes**:
- `gaia publish --git` — git add + commit + push
- `gaia publish --server` — POST to Gaia server API (commit engine)

#### `gaia init [name]`

Initialize a new knowledge package in the current directory.

**Creates**:
```
<name>/
  package.yaml       # package metadata skeleton
  motivation.yaml    # starter module
```

#### `gaia show <name>`

Show a declaration's details and its connected ChainExprs.

**Output example**:
```
heavier_falls_faster (Claim)
  prior: 0.70 | belief: 0.30
  content: "重的物体比轻的物体下落得更快..."

  Referenced in chains:
    ← inductive_support (deduction): everyday_observation → heavier_falls_faster
    → drag_prediction_chain (deduction): heavier_falls_faster → tied_pair_slower_than_heavy
    → combined_weight_chain (deduction): heavier_falls_faster → tied_pair_faster_than_heavy
    ← retraction_chain (retraction): tied_balls_contradiction → heavier_falls_faster
```

#### `gaia search <query>`

Full-text search within the package using local BM25 index (LanceDB).

#### `gaia clean`

Remove `.gaia/` directory (build artifacts, reviews, local index).

## 3. Architecture

### 3.1 Layer Diagram

```
┌──────────────────────────────────────────────────┐
│  CLI Layer (cli/)                                │
│  Typer commands → orchestrate pipeline           │
│  init / build / infer / review / publish         │
│  show / search / clean                           │
└─────────────────────┬────────────────────────────┘
                      │ calls
                      ▼
┌──────────────────────────────────────────────────┐
│  Core Library (libs/dsl/)                        │
│  ├─ models.py      Pydantic type system          │
│  ├─ loader.py      YAML → Package AST            │
│  ├─ resolver.py    Ref resolution                │
│  ├─ elaborator.py  Parameter instantiation (NEW) │
│  ├─ compiler.py    AST → FactorGraph             │
│  └─ executor.py    ActionExecutor ABC            │
└─────────────────────┬────────────────────────────┘
                      │ calls
                      ▼
┌──────────────────────────────────────────────────┐
│  Inference Engine (services/inference_engine/)    │
│  FactorGraph + BeliefPropagation                 │
└──────────────────────────────────────────────────┘
```

**Dependencies flow downward only.** `libs/dsl/` has no CLI or service dependencies. CLI depends on both `libs/dsl/` and `services/inference_engine/`.

### 3.2 CLI Structure

```
cli/
  __init__.py
  main.py              # Typer app, subcommand registration
  commands/
    __init__.py
    build.py           # gaia build
    infer.py           # gaia infer
    review.py          # gaia review
    publish.py         # gaia publish
    init.py            # gaia init
    show.py            # gaia show
    search.py          # gaia search
    clean.py           # gaia clean
  config.py            # ~/.gaia/config.toml
  llm_client.py        # LLM integration for review
  local_store.py       # Local LanceDB index for search
  review_store.py      # Sidecar review report I/O
```

### 3.3 Core Library (`libs/dsl/`)

**Existing** (keep as-is):
- `models.py` — Pydantic type system (Claim, Setting, Question, InferAction, ToolCallAction, ChainExpr, Ref, Module, Package)
- `loader.py` — YAML → Package AST
- `resolver.py` — Ref resolution
- `compiler.py` — FactorGraph compilation (called by `gaia infer`, not `gaia build`)
- `executor.py` — ActionExecutor ABC

**New**:
- `elaborator.py` — Parameter instantiation, template expansion. Deterministic, no LLM calls.

**Refactor**:
- `runtime.py` — Pipeline orchestration moves to CLI commands. Simplify or remove.

## 4. Package Format

Uses the existing DSL YAML format (proven with Galileo fixture):

```
my_package/
  package.yaml         # name, version, manifest, modules, exports
  motivation.yaml      # motivation_module
  setting.yaml         # setting_module
  reasoning.yaml       # reasoning_module (ChainExprs, Actions)
  follow_up.yaml       # follow_up_module
  .gaia/               # generated, gitignored
    build/             # elaborated package
    reviews/           # LLM review sidecar reports
    index/             # local BM25 index for search
```

## 5. Terminology

Retain current DSL implementation terms (77 passing tests, no unnecessary churn):

| Concept | Term used | Foundation equivalent |
|---|---|---|
| Knowledge object | Declaration | Closure |
| Reasoning step | Step (Ref/Apply/Lambda) | Inference |
| Composition | ChainExpr | Chain |
| Strong dependency | `dependency: direct` | `strength: strong` |
| Weak dependency | `dependency: indirect` | `strength: weak` |
| Knowledge types | Claim, Question, Setting, InferAction, ToolCallAction | Same |
| Grouping | Module (with type field) | Module (with role) |
| Container | Package | Package |

## 6. Data Flow

```
gaia build <path>
     │
     ├── Parse YAML → Package AST
     ├── Resolve Refs
     └── Elaborate (instantiate params, expand templates)
          │
          ▼
     .gaia/build/elaborated   (LLM-ready package)
          │
          ▼
     gaia review
          │
     LLM reviews each ChainExpr:
     - classify deps (direct/indirect)
     - estimate priors
     - suggest rewrites (extract uncertainty into new Claims)
          │
          ▼
     .gaia/reviews/xxx.yaml
          │
          ▼
     gaia infer
          │
     Read latest review file
     (or --review to specify)
          │
     Compile FG using review's
     dependency + prior decisions
          │
     Run BP → beliefs
          │
          ▼
     gaia publish
```

## 7. Implementation Phases

**Phase 1**: CLI skeleton
- Wire up Typer CLI (`cli/main.py`) with all 8 commands as stubs
- `gaia init` — package scaffolding
- `gaia clean` — remove `.gaia/`
- Entry point in `pyproject.toml`

**Phase 2**: Build pipeline
- `gaia build` — loader → resolver → elaborator
- New `libs/dsl/elaborator.py` — parameter instantiation, template expansion
- Elaborated package output to `.gaia/build/`

**Phase 3**: Inference
- `gaia infer` — read review sidecar + compile FG + run BP
- Error if no review file exists; `--review` to specify file

**Phase 4**: Review
- `gaia review` — LLM reviews each ChainExpr
- LLM client (litellm-based)
- Sidecar report: dependency classification, prior estimation, rewrite suggestions

**Phase 5**: Auxiliary + Publish
- `gaia show` — declaration details + connected ChainExprs
- `gaia search` — local BM25 index via LanceDB
- `gaia publish` — git and server modes

## 8. Entry Point

Add to `pyproject.toml`:

```toml
[project.scripts]
gaia = "cli.main:app"
```

After `pip install -e .`, the `gaia` command is available system-wide.
