---
status: current-canonical
layer: cli
since: v0.5
---

# CLI Workflow

## Overview

The Gaia CLI is a knowledge package authoring toolkit. The main authoring
pipeline takes a Python DSL package from scaffolding to registry registration;
authors may either edit Python files directly or use the agent-facing
`gaia author` / `gaia bayes` commands to append DSL statements:

```
gaia build init/pkg scaffold --> gaia pkg add --> write package or gaia author/bayes --> gaia build compile --> gaia build check --> gaia run infer --> gaia run render --> git tag --> gaia pkg register
(scaffold)                  (add deps)    (DSL code / cli-as-client)       (DSL -> IR)     (validate)    (BP)            (present)              (registry PR)
```

Supporting command groups cover review, trace audit, and visualization. They
are not interchangeable: `inquiry` maintains review-state ledgers, `trace`
audits externally recorded ARM trace files and can write review snapshots, and
`inspect` writes graph visualization artifacts.

```
gaia inquiry  — local review loop (focus / obligation / hypothesis / review)
gaia trace    — inference-trace verification and audit (verify / review / show)
gaia inspect starmap  — package-graph visualization (html / dot / svg)
```

`gaia run infer` is required before `gaia run render --target github`; `--target docs` works without it (beliefs enrich the output when available but are not required).

Entry point: installed as the `gaia` CLI command via `pyproject.toml` `[project.scripts]`, backed by a Typer app at `gaia.cli.main:app`.


## Commands

### `gaia build init <NAME>`

Scaffold a new Gaia knowledge package.

```
gaia build init <NAME>
```

| Argument | Default | Description |
|----------|---------|-------------|
| `NAME`   | (required) | Package name (must end with `-gaia`) |

**What it does:**

1. Runs `uv init --lib` under the hood to create the package directory.
2. Adds `[tool.gaia]` configuration to `pyproject.toml` (with `type = "knowledge-package"` and a generated `uuid`).
3. Renames the `src/` subdirectory to match the Gaia import name convention (strips the `-gaia` suffix, replaces hyphens with underscores).
4. Writes a DSL template into the package module's `__init__.py`.

The resulting directory is a complete Gaia knowledge package ready for `gaia build compile`.

**Key output:** a new directory `<NAME>/` containing `pyproject.toml`, `src/<import_name>/__init__.py` with DSL template code.


### `gaia build compile [PATH]`

Compile a Python DSL package to Gaia IR.

```
gaia build compile [PATH]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH`   | `.`     | Path to knowledge package directory |

**What it does:**

1. Loads the package from `pyproject.toml` (requires `[tool.gaia].type = "knowledge-package"`).
2. Imports the Python module, collects `Knowledge`, `Action` (including `Compose`), `Strategy`, and `Operator` declarations registered to the active `CollectedPackage`.
3. Assigns labels from Python variable names to unlabeled objects (Knowledge labels and Action labels share a single namespace per package; collision is a compile error — see [Gaia Lang design](../gaia-lang/knowledge-and-reasoning.md)).
4. Compiles the collected package to Gaia IR via `gaia.engine.lang.compiler.compile_package`. Action lowering, formula lowering, and bayes lowering all run as part of this step.
5. Validates the resulting `LocalCanonicalGraph` (warnings printed, errors abort).
6. Generates a baseline `ReviewManifest` over every action target and attaches it in memory to `CompiledPackage.review`. The manifest is not persisted by `gaia build compile`; it is read/merged later by `gaia inquiry review` and review/gate commands when `.gaia/review_manifest.json` exists.
7. Writes `.gaia/ir.json`, `.gaia/ir_hash`, compile metadata, the
   formalization manifest, and package interface manifests to `.gaia/`.

Compilation is deterministic: same source produces the same `ir_hash`. No LLM
calls are made. The compile command does run a best-effort `uv sync --quiet`
when `uv` is available, so dependency resolution may touch the package
environment before the deterministic import/compile step starts.

**Key output:** `.gaia/ir.json` (full IR), `.gaia/ir_hash` (content hash for
staleness detection), `.gaia/compile_metadata.json`,
`.gaia/formalization_manifest.json`, and
`.gaia/manifests/{exports,premises,holes,bridges}.json`.

Reference: [Compilation](compilation.md) for internals.


### `gaia build check [PATH]`

Validate package structure and artifact consistency.

```
gaia build check [PATH]
gaia build check --brief [PATH]
gaia build check --show <module|label> [PATH]
gaia build check --hole [PATH]
gaia build check --warrants [PATH]
gaia build check --warrants --blind [PATH]
gaia build check --inquiry [PATH]
gaia build check --gate [PATH]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `PATH`   | `.`     | Path to knowledge package directory |

| Option | Description |
|--------|-------------|
| `--brief`, `-b` | Show per-module warrant structure overview |
| `--show`, `-s` | Expand a specific module or claim/strategy label |
| `--hole` | Show detailed prior contract report for independent degrees of freedom |
| `--warrants` | Show v6 `ReviewManifest` warrants and audit questions for reviewable actions |
| `--blind` | With `--warrants`, hide status values and prior diagnostics to reduce reviewer anchoring |
| `--inquiry` | Show goal-oriented reasoning progress and review status |
| `--gate` | Run quality-gate checks and exit non-zero when the package is not publishable |

**What it does:**

1. Loads and compiles the package in memory using the same loader/compiler path
   as `gaia build compile` (but without the compile command's best-effort `uv sync`).
2. Checks that `[project].name` ends with `-gaia`.
3. Validates the `LocalCanonicalGraph` (schema and structural checks).
4. If `.gaia/ir_hash` exists, verifies it matches the current compilation output.
5. If `.gaia/ir.json` exists, verifies its embedded hash matches.

Exits with code 1 on any error. Warnings (e.g., missing compiled artifacts) are
printed but do not fail the check.

**Default output:** Prints pass/fail summary with knowledge diagnostics. Each independent boundary premise is annotated with `prior=X` or `no external prior (MaxEnt)`. Shows a "MaxEnt (no external prior): N" count when any load-bearing boundary claims lack external priors. If deterministic operators constrain those MaxEnt claims, the output also reports the effective feasible state space and entropy in bits. It also reports the induced MaxEnt entropy from the current full joint distribution, which is the Jaynes-style answer to "how many independent bits are really left after the graph's existing constraints and explicit priors are applied?"

**`--hole` output:** Detailed report splitting all load-bearing boundary claims into MaxEnt degrees of freedom (no external prior, with content and QID) and covered claims (with prior value and justification). Use during prior review to identify which independent claims intentionally rely on MaxEnt, which are constrained by deterministic logic, what their induced entropy is under the current graph, and which still need `priors.py` entries.

**`--warrants` / `--blind` / `--inquiry` / `--gate`:** Per-action review and gating views, layered on top of the merged `ReviewManifest`. See [CLI Commands § `gaia build check`](../../for-users/cli-commands.md#gaia-build-check) for the full review-loop semantics, and [`review-pipeline.md`](../review/review-pipeline.md) for the manifest contract and gate criteria.

**Prior contract:** External priors belong only on independent probabilistic inputs to exported goals that are not already pinned by a zero-premise `observe(...)`. A zero-premise `observe(...)` sets its conclusion to `1 - CROMWELL_EPS`; claims concluded by `derive(...)`, `compute(...)`, or `observe(..., given=...)` get their belief from the graph and should not receive manual priors. Structural/helper claims from propositional expressions, `infer(...)`, `associate(...)`, relation verbs (`equal`, `contradict`, `exclusive`), and generated formalization internals also carry no independent prior. If an independent input is intentionally left without an external prior, Gaia uses the Jaynes maximum-entropy distribution over the remaining independent degrees of freedom subject to declared hard constraints.

Reference: [Compilation](compilation.md) for validation details.


### `gaia pkg add <PACKAGE> [OPTIONS]`

Install a registered Gaia knowledge package from the official registry.

```
gaia pkg add <PACKAGE> [--version VERSION] [--registry REPO]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PACKAGE`         | (required) | Package name (e.g., `galileo-falling-bodies-gaia`) |
| `--version VERSION` | latest | Specific version to install |
| `--registry REPO` | `SiliconEinstein/gaia-registry` | Custom registry repo slug |

**What it does:**

1. Queries registry metadata via the GitHub API to resolve the package and version.
2. Resolves the version to a specific git tag and immutable git SHA.
3. Calls `uv add` with a pinned git URL pointing to the resolved SHA. The tag
   remains registry metadata; the dependency lock uses the SHA for
   reproducibility.
4. When run inside a Gaia package, downloads the upstream release's
   `beliefs.json` into `.gaia/dep_beliefs/<import_name>.json` if the registry
   release provides one. This cache feeds the default `gaia run infer --depth 0`
   flat prior injection for foreign nodes.

The package is added as a standard Python dependency in `pyproject.toml` and
installed into the project environment.

**Key output:** updated `pyproject.toml` `[project].dependencies`, `uv.lock`
with the pinned Gaia package dependency, and optionally
`.gaia/dep_beliefs/<import_name>.json`.


### `gaia run infer [PATH] [--depth N]`

Run belief propagation using compiled IR and metadata priors.

```
gaia run infer [PATH] [--depth N]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PATH`            | `.`     | Path to knowledge package directory |
| `--depth N`       | `0`     | Inference depth. `0`: flat prior injection from `dep_beliefs/`. `N>0`: joint cross-package inference merging dependency factor graphs to the given depth. |

**What it does:**

1. Runs `uv sync` to ensure the environment is up to date.
2. Loads and compiles the package to a `LocalCanonicalGraph`.
3. Verifies `.gaia/ir_hash` and `.gaia/ir.json` are present and not stale.
4. Collects metadata priors from resolved `register_prior(...)` records,
   generated continuous-inference records, inline compatibility priors, and
   legacy DSL `reason`+`prior` fields.
5. Lowers the graph to a factor graph via `lower_local_graph`. This is a local
   numerical preview of the compiled graph and does not read
   `.gaia/review_manifest.json`; unreviewed warrants still participate in the
   preview factor graph.
6. At `--depth 0` (default): injects flat priors from `dep_beliefs/` for
   dependency claims. At `--depth N>0`: merges dependency factor graphs for
   joint cross-package inference.
7. Runs `InferenceEngine()` (from `gaia/engine/bp/engine.py`), which auto-selects the
   algorithm: Mean Field VI for graphs with more than 2000 variables, exact JT
   for graphs with treewidth <= 20, and TRW-BP for the remaining wider graphs.
   Defaults: `bp_max_iter=200, bp_threshold=1e-8`.
8. Writes results to `.gaia/beliefs.json` — per-knowledge beliefs and
   convergence diagnostics.

**Prerequisites:** `gaia build compile` must have been run first (artifacts must be
fresh).

**Key output:** `.gaia/beliefs.json`.

Reference: [Inference](inference.md) for internals.


### `gaia run render [PATH] [--target TARGET]`

Render presentation outputs (detailed-reasoning docs, a GitHub publication
bundle, and/or a local Obsidian wiki) from a compiled package.

```
gaia run render [PATH] [--target docs|github|obsidian|all]
```

| Argument / Option | Default | Description |
|-------------------|---------|-------------|
| `PATH`            | `.`     | Path to knowledge package directory |
| `--target TARGET` | `all`   | `docs` writes `docs/detailed-reasoning.md`; `github` writes `.github-output/`; `obsidian` writes `gaia-wiki/`; `all` (default) writes docs and adds GitHub when possible. |

**Strictness by target:**

- `--target docs`: renders from the compiled IR alone. When a fresh
  `beliefs.json` is available it is loaded and used to enrich the output;
  otherwise a warning is emitted and the docs are written without belief
  values. Prior display is derived from compiled IR metadata, not from a
  separate `parameterization.json` file. This is the author-facing workflow —
  useful during iteration on DSL code before inference has been run.
- `--target github`: strictly requires a matching `beliefs.json`. Missing or
  stale inference results are hard errors. This is the external-publication
  workflow for README/wiki/data artifacts; publishing without belief values
  would be misleading.
- `--target obsidian`: renders `gaia-wiki/` from the compiled IR. Beliefs are
  optional; when present and fresh they enrich the pages.
- `--target all` (default): always renders docs, and adds the GitHub target
  when inference results are available. When beliefs are missing, it degrades
  to docs-only with a warning rather than failing.

**What it does:**

1. Loads and compiles the package in memory.
2. Verifies `.gaia/ir_hash` and `.gaia/ir.json` are present and not stale.
3. If `beliefs.json` is present, verifies its `ir_hash` matches the current
   compiled graph. Any stale belief artifact is a hard error.
4. Dispatches to the selected targets, emitting warnings when `--target all`
   or `--target docs` runs without inference results.

**Prerequisites:** `gaia build compile` must have been run. `gaia run infer` must have
been run for `--target github` and for the `github` portion of `--target all`.

**Key output:**
- `docs/detailed-reasoning.md` (when target includes `docs`)
- `.github-output/` with README, wiki pages, graph data, and copied assets
  (when target includes `github` and beliefs are available)
- `gaia-wiki/` (when target is `obsidian`)


### `gaia pkg register [PATH] [OPTIONS]`

Prepare or submit a registration for a tagged, GitHub-backed Gaia package.

```
gaia pkg register [PATH] [--tag TAG] [--repo URL] [--registry-dir PATH]
              [--registry-repo SLUG] [--create-pr]
```

| Argument / Option     | Default                          | Description |
|-----------------------|----------------------------------|-------------|
| `PATH`                | `.`                              | Path to knowledge package directory |
| `--tag TAG`           | `v<version>` from pyproject.toml | Git tag to register |
| `--repo URL`          | git origin remote                | GitHub repository URL |
| `--registry-dir PATH` | `None`                           | Local checkout of the official registry repo |
| `--registry-repo SLUG`| `SiliconEinstein/gaia-registry`  | Registry GitHub repo slug for PR creation |
| `--create-pr`         | `False`                          | Push registry branch and open a GitHub PR |

**What it does:**

1. Loads, compiles, and validates the package.
2. Verifies `.gaia/ir_hash` is present and fresh.
3. Validates prerequisites:
   - `[tool.gaia].uuid` is set and is a valid UUID.
   - `[project].name` ends with `-gaia`.
   - Git worktree is clean.
   - The tag exists, points to HEAD, and is pushed to origin.
   - Remote is a GitHub URL (Phase 1 restriction).
4. Parses `[project].dependencies` for Gaia package deps (names ending in
   `-gaia`).
5. Prepares exported claims from the IR based on the package's `exported` list.
6. Builds a registration plan containing `Package.toml`, `Versions.toml`,
   `Deps.toml`, release interface manifests, and exported release beliefs.

**Three modes of operation:**

- **Dry-run** (default, no `--registry-dir`): prints the registration plan as
  JSON to stdout.
- **Local write** (`--registry-dir` without `--create-pr`): creates a branch
  `register/<name>-<version>` in the registry checkout, writes/updates TOML
  files, commits. Preserves existing versions when appending.
- **Full registration** (`--registry-dir --create-pr`): local write, then pushes
  the branch and creates a GitHub PR via `gh pr create`.

**Key output (in registry repo):**
- `packages/<name>/Package.toml` -- package identity (uuid, name, repo, description).
- `packages/<name>/Versions.toml` -- version entries (ir_hash, git_tag, git_sha, timestamp).
- `packages/<name>/Deps.toml` -- per-version Gaia package dependencies.
- `packages/<name>/releases/<version>/exports.json` -- exported claim interface.
- `packages/<name>/releases/<version>/premises.json` -- public premise interface.
- `packages/<name>/releases/<version>/holes.json` -- local-hole subset of premises.
- `packages/<name>/releases/<version>/bridges.json` -- `fills(...)` bridge records.
- `packages/<name>/releases/<version>/beliefs.json` -- exported beliefs generated
  by running local inference at registration time.

Reference: [Registration](registration.md) for details.


## Supporting Review / Trace / Visualization Commands

These commands support the authoring loop around compiled IR and beliefs.
They do not edit Python DSL source. `inquiry` persists inquiry/review state,
`trace review` can persist trace-review snapshots, and `inspect starmap`
persists visualization artifacts.

### `gaia inquiry`

Local review loop and proof-state ledger. Reads the compiled IR, the merged review manifest, the current focus claim, obligations, and working hypotheses; never modifies `.py` source, IR, priors, or beliefs.

```
gaia inquiry focus [TARGET]            # set / clear / push / pop / inspect focus
gaia inquiry obligation add|list|close
gaia inquiry hypothesis add|list|remove
gaia inquiry reject [TARGET]
gaia inquiry tactics log
gaia inquiry review                    # full review loop (compile + validate + analyze + snapshot)
```

State persists in `.gaia/inquiry/state.json` and `.gaia/inquiry/tactics.jsonl`. Review snapshots persist in `.gaia/inquiry/reviews/<review_id>.json` for diffing.

Reference: [../review/review-pipeline.md §4](../review/review-pipeline.md#4-cli-gaia-inquiry-review).

### `gaia trace`

ARM (Auditable Reasoning Manifest) trace reviewer. Inference and other agent-side workflows emit hash-chained trace files; this command verifies and audits them.

```
gaia trace verify <PATH>                                  # schema + hash-chain check
gaia trace review <PATH> [--mode trace|publish] [--package PKG] [--json|--markdown] [--strict] [--snapshot-dir DIR]
gaia trace show <PATH> [--kind KIND] [--limit N] [--json]
```

Exit codes:
- `verify`: 0 clean / 1 chain or manifest mismatch / 2 schema error.
- `review`: 0 clean / 1 error diagnostic (or `--strict` warning) / 2 invalid CLI args.

`--mode publish` weighs diagnostics more strictly for release-gate use; `--mode trace` is the authoring-time view. `--package <pkg>` cross-references `claim_ref` events against the package's `Review` records.
`gaia trace review` persists review snapshots under `.gaia/trace/reviews/` by
default; use `--snapshot-dir` to write them elsewhere.

Reference: [../review/review-pipeline.md §6](../review/review-pipeline.md#6-cli-gaia-trace-verify-review-show).

### `gaia inspect starmap`

Cross-paper / cross-package knowledge-graph visualization. Reads compiled IR (and optionally registry metadata) to render the constellation of claims, actions, and modules.

```
gaia inspect starmap [PATH] [--format html|dot|svg] [--theme light|stellaris|dark] [--out OUTPUT]
```

| Option | Default | Description |
|---|---|---|
| `--format` | `html` | `html` → interactive Sigma.js single-file bundle; `dot` → Graphviz `.dot` source (paper-ready); `svg` → rendered SVG with optional stellaris glow filters |
| `--theme` | `light` | Visual theme: `light` (flat paper-friendly), `stellaris` / `dark` (deep-space dark with glow filters for svg) |
| `--out` | `.gaia/starmap.{html,dot,svg}` | Output destination |

`gaia inspect starmap-replay` is an experimental sibling that renders an animated
playback of an LKM discovery run. It expects
`artifacts/lkm-discovery/retrieval_log.jsonl` and
`artifacts/lkm-discovery/graph_growth_log.jsonl`.


## Artifacts by Stage

| Stage    | Command          | Key Artifacts |
|----------|------------------|---------------|
| Init     | `gaia build init`      | `pyproject.toml` with `[tool.gaia]`, `src/<import_name>/__init__.py` with DSL template |
| Scaffold | `gaia pkg scaffold` | Minimal agent-facing package skeleton with `pyproject.toml`, `src/<import_name>/__init__.py`, `.gaia/.gitkeep` |
| Author   | `gaia author` / `gaia bayes` | Appended Python DSL statements in package source files |
| Module plumbing | `gaia pkg add-module` / `gaia pkg add-import` | Sibling Python modules and idempotent import lines |
| Compile  | `gaia build compile`   | `.gaia/ir.json`, `.gaia/ir_hash`, `.gaia/compile_metadata.json`, `.gaia/formalization_manifest.json`, `.gaia/manifests/{exports,premises,holes,bridges}.json` |
| Check    | `gaia build check`     | (validation only) |
| Add      | `gaia pkg add`       | Updated `pyproject.toml` dependencies, `uv.lock` |
| Inquiry  | `gaia inquiry`   | `.gaia/inquiry/state.json`, `.gaia/inquiry/tactics.jsonl`, `.gaia/inquiry/reviews/<review_id>.json`, `.gaia/review_manifest.json` (persisted by inquiry review) |
| Infer    | `gaia run infer`     | `.gaia/beliefs.json` |
| Trace    | `gaia trace`     | reads trace files; `review` also writes snapshots under `.gaia/trace/reviews/` unless `--snapshot-dir` is used |
| Render   | `gaia run render`    | `docs/detailed-reasoning.md`, `.github-output/`, or `gaia-wiki/` depending on target |
| Starmap  | `gaia inspect starmap`   | `.gaia/starmap.{html,dot,svg}` |
| Register | `gaia pkg register`  | `packages/<name>/Package.toml`, `Versions.toml`, `Deps.toml`, and `releases/<version>/{exports,premises,holes,bridges,beliefs}.json` in the registry repo |


## Package Requirements

A valid Gaia knowledge package has:

- A `pyproject.toml` with `[tool.gaia].type = "knowledge-package"`.
- `[project].name` ending with `-gaia` (enforced by `check` and `register`).
- `[project].version` set.
- `[tool.gaia].uuid` set to a valid UUID (required for `register`).
- A Python module at `src/<import_name>/` or `<import_name>/` that declares
  `Knowledge`, `Action` (including `Compose`), `Strategy`, and/or `Operator` objects.

The import name is derived from the project name: strip the `-gaia` suffix and
replace hyphens with underscores (e.g., `galileo-falling-bodies-gaia` becomes
`galileo_falling_bodies`).


## Quick Start

```bash
# 1. Scaffold a package
gaia build init galileo-falling-bodies-gaia
cd galileo-falling-bodies-gaia

# 2. Write DSL declarations in src/galileo_falling_bodies/__init__.py

# 3. Compile DSL to IR
gaia build compile .

# 4. Validate package
gaia build check .

# 5. Add dependencies from the registry (optional)
gaia pkg add some-prerequisite-gaia

# 6. Preview beliefs (optional)
gaia run infer .

# 7. Tag and push
git add -A && git commit -m "initial package"
git tag v0.1.0
git push origin main --tags

# 8. Dry-run registration (prints JSON plan)
gaia pkg register .

# 9. Write to registry and open PR
gaia pkg register . --registry-dir ../gaia-registry --create-pr
```
