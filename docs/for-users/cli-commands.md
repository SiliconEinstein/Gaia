# CLI Commands

> **Status:** Current canonical

Reference for the Gaia Lang v5 CLI. The installed entrypoint is `gaia`.

## Command Set

```text
gaia init       Create a new knowledge package
gaia compile    Compile to .gaia/ir.json
gaia check      Validate structure and prior coverage
gaia infer      Run belief propagation inference
gaia render     Generate documentation and presentation outputs
gaia add        Install a registered package from the registry
gaia register   Submit a package to the official registry
```

## `gaia init`

Create a new Gaia knowledge package.

```bash
gaia init <name>
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

## `gaia compile`

Compile a Gaia Python package into `.gaia/ir.json` and `.gaia/ir_hash`.

```bash
gaia compile [path]
```

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the package repository |

What it does:

- loads `pyproject.toml`
- resolves the Python import package from `<repo>/src/<import_name>/`
- executes the Gaia DSL declarations (including `priors.py` if present)
- emits a `LocalCanonicalGraph` to `.gaia/ir.json`
- writes the deterministic graph hash to `.gaia/ir_hash`

## `gaia check`

Validate structure and artifact consistency. Optionally display warrant structure for review.

```bash
gaia check [path]
gaia check --brief [path]
gaia check --show <module|label> [path]
gaia check --hole [path]
```

| Option | Description |
|--------|-------------|
| `--brief`, `-b` | Per-module overview: claims (with roles), strategies, operators |
| `--show`, `-s` | Expand a specific module or claim/strategy label with full warrant trees |
| `--hole` | Detailed prior coverage report: holes (missing prior) + covered (with prior) |

What it checks:

- `pyproject.toml` and `[tool.gaia]` metadata exist
- `.gaia/ir.json` matches the current source (`ir_hash` check)
- compiled IR validates against the current schema
- package identity fields (`name`, `version`, `uuid`) are present and consistent

The default output annotates each independent boundary premise with `prior=X` or `no external prior (MaxEnt)`, and shows a "MaxEnt (no external prior): N" summary. When the boundary includes deterministic logical constraints, `gaia check` reports the effective MaxEnt state space (feasible assignments and entropy in bits). It also computes the induced MaxEnt entropy of those boundary claims under the current full joint distribution, so you can see how much uncertainty the existing graph actually removes without changing the package structure.

### Claim roles in output

| Role | Meaning | Needs prior? |
|------|---------|-------------|
| Independent | Load-bearing boundary premise for exported goals, with no incoming warrant chain or grounding | External prior or MaxEnt |
| Derived | Concluded by a strategy — belief comes from BP | No external prior |
| Background-only | Only used in `background=`, not as premise | External prior if used as a belief variable |
| Orphaned | Not referenced by any strategy | External prior or remove |

## `gaia infer`

Run belief propagation inference on a compiled knowledge package.

```bash
gaia infer [path]
gaia infer --depth 1 [path]
```

| Option | Default | Description |
|--------|---------|-------------|
| `--depth` | `0` | Dependency depth for joint inference. `0` = flat priors, `1` = merge direct deps, `-1` = all transitive deps |

Priors come from `priors.py` and inline `reason`+`prior` pairing in the DSL. Algorithm is auto-selected based on factor graph treewidth:

| Treewidth | Algorithm | Type |
|-----------|-----------|------|
| <= 15 | Junction tree | Exact |
| 16-30 | Generalized BP | Region decomposition |
| > 30 | Loopy BP | Approximate |

Output: `.gaia/beliefs.json`

## `gaia render`

Generate documentation and presentation outputs from a compiled package.

```bash
gaia render [path] --target docs
gaia render [path] --target github
gaia render [path] --target obsidian
gaia render [path]                       # --target all (default)
```

| Target | Requires beliefs? | Output |
|--------|------------------|--------|
| `docs` | Optional (enriched when available) | `docs/detailed-reasoning.md` with per-module Mermaid graphs |
| `github` | Required | `.github-output/` with README skeleton, narrative outline, manifest |
| `obsidian` | Required | `gaia-wiki/` Obsidian vault with claim pages and sections |
| `all` | Optional | `docs` always + `github` when beliefs are available |

## `gaia add`

Install a registered package from the official registry.

```bash
gaia add <package>
gaia add <package> --version 1.0.0
```

| Option | Description |
|--------|-------------|
| `--version`, `-v` | Pin to a specific version |
| `--registry` | Override registry repo (default: `SiliconEinstein/gaia-registry`) |

## `gaia register`

Submit a package to the official registry. Requires a git tag pushed to GitHub.

```bash
gaia register [path] --create-pr
```

| Option | Description |
|--------|-------------|
| `--tag` | Git tag to register (default: `v<version>`) |
| `--repo` | Override the GitHub repository URL |
| `--registry-dir` | Path to a local checkout of the registry repo |
| `--create-pr` | Create the registry branch and open a PR |

Prerequisites:

- `gaia compile` and `gaia check` pass
- package source is pushed to GitHub
- target tag is pushed

Example:

```bash
gaia compile .
gaia check .
git push origin main
git tag v1.0.0
git push origin v1.0.0
gaia register . --tag v1.0.0 --registry-dir ../gaia-registry --create-pr
```

**Note:** `--create-pr` creates the registry branch locally but does not automatically push to your fork. After running, manually push and create the PR:

```bash
cd ../gaia-registry
git push origin register/<name>-<version>
gh pr create --repo SiliconEinstein/gaia-registry --base main \
  --head <your-user>:register/<name>-<version> --title "register: <name> <version>"
```

## Typical Workflow

```bash
gaia init my-package-gaia          # 1. Scaffold
# ... write DSL code ...           # 2. Author
gaia compile .                     # 3. Compile
gaia check .                       # 4. Validate
# ... write priors.py ...          # 5. Assign priors
gaia compile .                     # 6. Re-compile with priors
gaia infer .                       # 7. Run inference
gaia render . --target docs        # 8. Generate documentation
gaia render . --target github      # 9. Generate presentation
gaia register . --create-pr        # 10. Publish to registry
```
