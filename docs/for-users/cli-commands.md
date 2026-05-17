# CLI Commands

> **Status:** Current canonical (alpha 0)

Reference for the Gaia Lang v0.5 CLI. The installed entrypoint is `gaia`.

Alpha 0 organizes the historical 9 flat verbs into 6 logical groups plus
the independent `trace` sub-app. The 22 leaf verbs keep their pre-alpha-0
semantics and option flags — only the top-level argument structure changed.

```text
gaia build    init / compile / check          Create and validate a package
gaia run      infer / render                  Execute inference + render
gaia inspect  starmap / starmap-replay        Visualize the compiled graph
gaia review   (skeleton — no commands yet)    Reserved for reviewer tooling
gaia inquiry  focus / review / obligation /   Local semantic-inquiry loop
              hypothesis / tactics / reject
gaia pkg      add / register                  Install and publish packages
gaia trace    verify / review / show          ARM Trace tooling (independent)
```

> **Note**: `gaia review` is a help-visible empty skeleton in alpha 0 and
> is **different** from `gaia inquiry review` and `gaia trace review`,
> which are pre-existing inner subcommands and keep their invocation paths.

For the old-to-new verb mapping (and the related Python import-path
changes), see [Migration to alpha 0](../migration.md).

## Top-level options

### `gaia --version`

```bash
gaia --version
```

Prints version, release channel, commit, and IR schema metadata, then exits:

```text
gaia-lang 0.5.0
channel: stable
commit: 84353aa3
ir_schema: ir-v1+<12hex>
```

| Field | Source | Meaning |
|-------|--------|---------|
| version | `gaia._meta.get_library_version()` | distribution version of `gaia-lang` |
| channel | `gaia._meta.get_channel()` | `stable` / `alpha` / `beta` / `rc` / `dev` — release channel |
| commit | `gaia._meta.get_commit()` | git short-SHA the wheel was built from |
| ir_schema | `gaia._meta.IR_SCHEMA` | IR schema version this CLI consumes/emits |

Use `--version` in CI logs and bug reports so the IR schema and channel
are unambiguous when debugging registry / dependency mismatches.
`.gaia/compile_metadata.json` records the compiled `ir_hash` and
`gaia_lang_version`; use `gaia --version` for the schema string.

## `gaia build`

Create and validate a knowledge package.

### `gaia build init`

```bash
gaia build init <name>
```

The name **must** end with `-gaia` (e.g., `galileo-falling-bodies-gaia`).

Creates:
- `pyproject.toml` with `[tool.gaia]` section (auto-generated `type` and `uuid`)
- `src/<import_name>/__init__.py` with a starter template
- `.gitignore`
- Auto-runs `uv add gaia-lang` to pin the dependency

| Naming | Convention | Example |
|--------|-----------|---------|
| Git repo / PyPI | `kebab-case-gaia` | `galileo-falling-bodies-gaia` |
| Python import | `snake_case` (no `-gaia` suffix) | `galileo_falling_bodies` |

### `gaia build compile`

```bash
gaia build compile [path]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the package repository |

Compiles the package into `.gaia/ir.json`, `.gaia/ir_hash`, and
interface manifests:

- loads `pyproject.toml`
- resolves the Python import package from `<repo>/src/<import_name>/`
- executes the Gaia DSL declarations (including `priors.py` if present)
- emits a `LocalCanonicalGraph` to `.gaia/ir.json`
- writes the deterministic graph hash to `.gaia/ir_hash`
- writes `.gaia/compile_metadata.json` and `.gaia/formalization_manifest.json`
- writes `.gaia/manifests/{exports,premises,holes,bridges}.json` for
  cross-package interfaces and `fills(...)` validation

### `gaia build check`

Validate structure and artifact consistency. Optionally display warrant
structure for review.

```bash
gaia build check [path]
gaia build check --brief [path]
gaia build check --show <module|label> [path]
gaia build check --hole [path]
gaia build check --warrants [path]
gaia build check --warrants --blind [path]
gaia build check --inquiry [path]
gaia build check --gate [path]
```

| Option | Description |
|--------|-------------|
| `--brief`, `-b` | Per-module overview: claims (with roles), strategies, operators |
| `--show`, `-s` | Expand a specific module or claim/strategy label with full warrant trees |
| `--hole` | Detailed prior contract report: MaxEnt independent DOF + covered inputs |
| `--warrants` | Show v6 `ReviewManifest` warrants and audit questions for reviewable actions |
| `--blind` | With `--warrants`, hide status values and prior diagnostics to reduce anchoring |
| `--inquiry` | Show goal-oriented reasoning progress and review status |
| `--gate` | Run quality-gate checks and exit non-zero when the package is not publishable |

What it checks:

- `pyproject.toml` and `[tool.gaia]` metadata exist
- `.gaia/ir.json` matches the current source (`ir_hash` check)
- compiled IR validates against the current schema
- package name ends with `-gaia`

`gaia build check` does not prove that a package can be registered:
registration also requires a valid `[tool.gaia].uuid`, a clean git
worktree, a pushed tag that points at `HEAD`, and a clean registry
checkout.

The default output annotates each independent boundary premise with `prior=X`
or `no external prior (MaxEnt)`, and shows a "MaxEnt (no external prior): N"
summary. When the boundary includes deterministic logical constraints,
`gaia build check` reports the effective MaxEnt state space (feasible
assignments and entropy in bits). It also computes the induced MaxEnt
entropy of those boundary claims under the current full joint distribution,
so you can see how much uncertainty the existing graph actually removes
without changing the package structure.

Use the variants for different review loops:

- `gaia build check --brief .` when you want a compact map of modules, claims,
  roles, and action warrants.
- `gaia build check --show high_Tc .` when a single claim or module needs a
  full warrant tree.
- `gaia build check --hole .` before inference, to see which independent
  inputs have author priors and which remain MaxEnt.
- `gaia build check --warrants .` when you want a review sheet for strategies,
  operators, and other reviewable actions.
- `gaia build check --warrants --blind .` when a reviewer should inspect
  warrants without seeing author status or prior diagnostics first.
- `gaia build check --inquiry .` when you want a goal-oriented progress view:
  exported claims, review status, open gaps, and blocked reasoning steps.
- `gaia build check --gate .` in CI or before publication. Treat a non-zero
  exit as a package-quality failure, not as an inference failure.

`--gate` fails by default on structural holes, unformalized `depends_on(...)`
scaffold dependencies, and reachable unaccepted review warrants. Optional
`[tool.gaia.quality]` settings can relax selected checks or add a belief
floor:

```toml
[tool.gaia.quality]
allow_holes = false
allow_unformalized_dependencies = false
min_posterior = 0.7  # optional; omit for no posterior threshold
```

#### Prior assignment contract

- Assign external priors only to independent probabilistic inputs that are load-bearing for exported goals.
- A zero-premise `observe(...)` pins its conclusion to `1 - CROMWELL_EPS`; do not add a separate external prior for it.
- Do not assign priors to claims concluded by `derive(...)`, `compute(...)`, or `observe(..., given=...)`.
- Do not assign priors to structural/helper claims from `~`, `&`, `|`, `infer(...)`, `associate(...)`, `equal(...)`, `contradict(...)`, `exclusive(...)`, generated `decompose(...)` helpers, or generated formalization internals.
- Leaving an independent input unset is explicit: Gaia applies the Jaynes maximum-entropy distribution over the remaining independent degrees of freedom, subject to declared hard constraints.

#### Claim roles in output

| Role | Meaning | Needs prior? |
|------|---------|-------------|
| Independent | Load-bearing boundary premise for exported goals, excluding zero-premise `observe(...)` claims | External prior or MaxEnt |
| Derived | Concluded by a strategy — belief comes from BP | No external prior |
| Structural/helper | Boolean expression, relation helper, or generated formalization helper | No external prior |
| Background-only | Only used in `background=`, not as premise | Use `note(...)`; promote to `claim(...)` only if it is a probabilistic input |
| Orphaned | Not referenced by any strategy | Export/connect it if intentional, otherwise remove |

## `gaia run`

Execute inference and emit presentation outputs.

### `gaia run infer`

Run belief propagation inference on a compiled knowledge package.

```bash
gaia run infer [path]
gaia run infer --depth 1 [path]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--depth` | `0` | Dependency depth for joint inference. `0` = flat priors, `1` = merge direct deps, `-1` = all transitive deps |

Priors come from `register_prior(...)` calls in `priors.py`, inline
`claim(prior=...)` compatibility shortcuts, generated continuous-inference
records, and dependency beliefs. The resolver writes the winning value into
claim metadata before lowering to the factor graph.

Action-backed strategies and operators are lowered for local preview even
when their generated review targets are still `unreviewed`. `gaia run infer`
does not read `.gaia/review_manifest.json` to decide whether a reasoning
edge may participate in the factor graph. Treat the output as "what the
current compiled graph implies numerically", not as a publication-quality
approval. Use `gaia build check --warrants`, `gaia build check --gate`, and
`gaia inquiry review` to see which warrants still need review before
publishing or registering the package.

Algorithm selection is automatic:

- If the graph has more than 2000 variables, Gaia uses Mean Field VI.
- Otherwise, Gaia estimates treewidth. If treewidth is at most 20, Gaia uses
  exact Junction Tree inference.
- For remaining graphs, Gaia uses TRW-BP as a bounded approximate method.

| Condition | Algorithm | Type |
|-----------|-----------|------|
| `n > 2000` variables | Mean Field VI | Fast approximate |
| `n <= 2000` and treewidth `<= 20` | Junction Tree | Exact |
| `n <= 2000` and treewidth `> 20` | TRW-BP | Bounded approximate |

Output: `.gaia/beliefs.json`

### `gaia run render`

Generate documentation and presentation outputs from a compiled package.

```bash
gaia run render [path] --target docs
gaia run render [path] --target github
gaia run render [path] --target obsidian
gaia run render [path]                       # --target all (default)
```

| Target | Requires beliefs? | Output |
|--------|------------------|--------|
| `docs` | Optional (enriched when available) | `docs/detailed-reasoning.md` with per-module Mermaid graphs |
| `github` | Required | `.github-output/` with README skeleton, narrative outline, manifest |
| `obsidian` | Optional (enriched when available) | `gaia-wiki/` Obsidian vault with claim pages and sections |
| `all` | Optional | `docs` always + `github` when beliefs are available |

## `gaia inspect`

Visualize the compiled package graph.

### `gaia inspect starmap`

Generate a package graph visualization from the compiled IR.

```bash
gaia inspect starmap [path]
gaia inspect starmap [path] --format html
gaia inspect starmap [path] --format dot --out figures/package.dot
gaia inspect starmap [path] --format svg --theme stellaris --out figures/package.svg
```

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `html` | `html` for a self-contained interactive Sigma.js viewer, `dot` for Graphviz source, `svg` for a rendered figure |
| `--theme` | `light` | `light`, `stellaris`, or `dark`; the dark aliases use the deep-space visual style |
| `--out` | `.gaia/starmap.<format>` | Output path; absolute paths are honored |

Typical use:

- Use `html` while authoring, because it opens directly in a browser and does
  not require a local server.
- Use `dot` when you want to post-process the graph yourself with Graphviz.
- Use `svg` when you need a paper-ready or slide-ready static figure.

### `gaia inspect starmap-replay`

Render an animated HTML replay of an LKM discovery run.

```bash
gaia inspect starmap-replay [path]
gaia inspect starmap-replay [path] --out figures/replay.html
```

Input files:

- `artifacts/lkm-discovery/retrieval_log.jsonl`
- `artifacts/lkm-discovery/graph_growth_log.jsonl`

Output: `.gaia/starmap-replay.html` by default.

This command is useful after an LKM-to-Gaia run. It merges retrieval and
graph growth events, drops retry/failure events, replays each emitted Gaia
action on a pinned layout, and recomputes round-by-round beliefs from the
truncated IR.

## `gaia review`

Reserved for downstream reviewer tooling.

```text
gaia review     (alpha 0: help-visible empty skeleton)
```

Alpha 0 ships `gaia review` as a placeholder group so downstream
reviewer-tooling work has a stable home. Invoking it with no subcommand
prints help; concrete subcommands will arrive in a later release.

`gaia review` is **different** from `gaia inquiry review` and
`gaia trace review` (see below) — those are pre-existing inner subcommands,
untouched by alpha 0.

## `gaia inquiry`

Manage the semantic review loop for a package. Inquiry state is stored in
the package's `.gaia` state files; these commands do not edit Python source,
compiled IR, priors, or beliefs.

```bash
gaia inquiry review [path]
gaia inquiry review [path] --mode publish --markdown --strict
gaia inquiry review [path] --focus github:pkg::claim --depth 1
gaia inquiry focus <target> --path .
gaia inquiry focus --clear --path .
gaia inquiry focus <target> --push --path .              # push current, set new
gaia inquiry focus --pop --path .                        # pop saved focus
gaia inquiry focus --stack --path .                      # print focus stack
gaia inquiry obligation add <target-qid> --content "What must be shown" --kind other --path .
gaia inquiry obligation list --path .
gaia inquiry obligation close <obligation-qid> --path .
gaia inquiry hypothesis add "Alternative mechanism" --path .
gaia inquiry hypothesis list --path .
gaia inquiry hypothesis remove <hypothesis-qid> --path .
gaia inquiry reject <strategy-label-or-id> --content "Why this path is rejected" --path .
gaia inquiry tactics log --path .
```

`gaia inquiry focus` flags `--clear`, `--push`, `--pop`, and `--stack` are
mutually exclusive. `--push` and a positional `<target>` together push the
current frame and set a new focus; `--pop` restores the most recent frame.

`gaia inquiry review` options:

| Option | Description |
|--------|-------------|
| `--focus <target>` | Review one focus claim instead of the whole package |
| `--mode auto|formalize|explore|verify|publish` | Ranking profile for diagnostics and next edits |
| `--no-infer` | Skip the inference-backed diagnostics |
| `--depth N` | Dependency depth for inference-backed diagnostics |
| `--since <review-id>` | Diff against a previous review snapshot |
| `--json` | Emit JSON |
| `--markdown` | Emit Markdown |
| `--strict` | Exit non-zero on strict warnings/errors |

Use it when a package is structurally valid but the scientific reasoning still
needs review work: tracking a current focus claim, recording open obligations,
adding temporary working hypotheses, rejecting a path with a reason, and
printing the tactic log for the inquiry.

## `gaia pkg`

Install and publish packages.

### `gaia pkg add`

Install a registered package from the official registry.

```bash
gaia pkg add <package>
gaia pkg add <package> --version 1.0.0
```

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Pin to a specific version |
| `--registry` | Override registry repo (default: `SiliconEinstein/gaia-registry`) |

What it does:

- resolves the package and version from the registry index to a git tag and
  immutable git SHA
- adds the package dependency to the current Python project using a SHA-pinned
  git URL
- when run inside a Gaia package, downloads the upstream release's
  `beliefs.json` into `.gaia/dep_beliefs/<import_name>.json` if the registry
  has one; this cache is written at the nearest Gaia package root, not
  necessarily the shell's current subdirectory

That cached `dep_beliefs` file is used by `gaia run infer --depth 0` as a
flat prior source for foreign nodes. If the registry release has no beliefs
file, the command prints a note and still installs the dependency.

### `gaia pkg register`

Submit a package to the official registry. Requires a git tag pushed to
GitHub.

```bash
gaia pkg register [path]
gaia pkg register [path] --registry-dir ../gaia-registry
gaia pkg register [path] --registry-dir ../gaia-registry --create-pr
```

| Option | Description |
|--------|-------------|
| `--tag` | Git tag to register (default: `v<version>`) |
| `--repo` | Override the GitHub repository URL |
| `--registry-dir` | Path to a local checkout of the registry repo |
| `--create-pr` | Create the registry branch and open a PR; requires `--registry-dir` |

Prerequisites:

- `gaia build compile` and `gaia build check` pass
- `[tool.gaia].uuid` is set and is a valid UUID
- package source is pushed to GitHub
- git worktree is clean
- target tag exists, points to `HEAD`, and is pushed to origin
- registry checkout is clean when `--registry-dir` is used
- registry branch `register/<name>-<version>` does not already exist

Without `--registry-dir`, `gaia pkg register` is always a dry-run: it
prints a JSON plan and does not create a local registry branch, even if
`--create-pr` is present. Use `--registry-dir ../gaia-registry --create-pr`
for the full push/PR path.

Example:

```bash
gaia build compile .
gaia build check .
git push origin main
git tag v1.0.0
git push origin v1.0.0
gaia pkg register . --tag v1.0.0 --registry-dir ../gaia-registry --create-pr
```

Without `--create-pr`, `gaia pkg register` creates and commits the registry
branch locally, then prints the manual next step:

```bash
cd ../gaia-registry
git push origin register/<name>-<version>
gh pr create --repo SiliconEinstein/gaia-registry --base main \
  --head <your-user>:register/<name>-<version> --title "register: <name> <version>"
```

With `--create-pr`, Gaia runs the push and `gh pr create` step for you.

Registry write mode creates or updates:

- `packages/<name>/Package.toml`
- `packages/<name>/Versions.toml`
- `packages/<name>/Deps.toml`
- `packages/<name>/releases/<version>/exports.json`
- `packages/<name>/releases/<version>/premises.json`
- `packages/<name>/releases/<version>/holes.json`
- `packages/<name>/releases/<version>/bridges.json`
- `packages/<name>/releases/<version>/beliefs.json`

The release `beliefs.json` is generated by local inference at registration
time and contains exported claims only. It is distinct from local
`.gaia/beliefs.json`, which is an authoring artifact and remains gitignored.

## `gaia trace`

Verify, review, and inspect ARM execution traces. Independent of the 6
groups; sub-app internals are unchanged in alpha 0.

```bash
gaia trace verify trace.jsonl
gaia trace verify trace.jsonl --quiet
gaia trace review trace.jsonl --mode trace
gaia trace review trace.jsonl --mode publish --package .
gaia trace review trace.jsonl --markdown
gaia trace review trace.jsonl --snapshot-dir .gaia/trace/reviews
gaia trace show trace.jsonl --limit 20
gaia trace show trace.jsonl --kind tool_call --json
```

| Subcommand | Purpose | Exit codes |
|------------|---------|------------|
| `verify` | Validate schema, event hash chain, events root, and manifest hash | `0` clean, `1` tampered/hash mismatch, `2` schema or bad args |
| `review` | Run the full trace review and print text, JSON, or Markdown | `0` clean, `1` error diagnostics or strict warnings, `2` bad args |
| `show` | Print the event stream, optionally filtered by kind | `0` clean, `2` un-loadable schema |

Use `verify` as the fast fail-fast check. Use `review` when you need the
full diagnostic report; by default it also saves a review snapshot under
`.gaia/trace/reviews/`, or under `--snapshot-dir` when provided. Use `show`
when you want to inspect the raw event sequence.

## Typical Workflow

```bash
gaia build init my-package-gaia                                      # 1. Scaffold
# ... write DSL code ...                                             # 2. Author
gaia build compile .                                                 # 3. Compile
gaia build check .                                                   # 4. Validate
# ... write priors.py ...                                            # 5. Assign priors
gaia build compile .                                                 # 6. Re-compile with priors
gaia run infer .                                                     # 7. Run inference
gaia run render . --target docs                                      # 8. Generate documentation
gaia run render . --target github                                    # 9. Generate presentation
gaia pkg register . --registry-dir ../gaia-registry --create-pr      # 10. Publish
```

## Old flat verbs

The historical flat top-level verbs (`gaia compile`, `gaia infer`, `gaia check`,
`gaia init`, `gaia render`, `gaia starmap`, `gaia starmap-replay`, `gaia add`,
`gaia register`) were removed in alpha 0. The grouped forms documented above
(`gaia build compile`, `gaia run infer`, `gaia inspect starmap`, etc.) are the
current canonical replacements.

Invoking one of the removed flat verbs now fails with typer's standard
`No such command` usage error and exits with code 2 — no side effects, no
partial work. See [Migration to alpha 0](../migration.md) for the full
old-to-new mapping.
