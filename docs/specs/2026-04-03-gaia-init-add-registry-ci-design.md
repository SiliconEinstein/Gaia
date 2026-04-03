# gaia init, gaia add, and Registry CI Update — Design

**Status:** Target design
**Date:** 2026-04-03

## Summary

Add two new CLI commands (`gaia init`, `gaia add`) and update the official registry CI
to use PyPI-installed `gaia-lang` and validate namespace.

## 1. `gaia init <name>`

Scaffold a new Gaia knowledge package using `uv init --lib` as the base.

**Usage:**

```bash
gaia init galileo-falling-bodies-gaia
```

**Steps:**

1. Validate `name` ends with `-gaia`, abort otherwise
2. Run `uv init --lib <name>` to generate standard Python package structure
3. Modify `pyproject.toml`:
   - Add `[tool.gaia]` section with `type = "knowledge-package"` and auto-generated `uuid`
4. Rename `src/<name_with_underscores>/` → `src/<import_name>/` (strip `-gaia` suffix)
5. Overwrite `src/<import_name>/__init__.py` with a DSL example:
   ```python
   from gaia.lang import claim, setting

   context = setting("Background context for this package.")
   hypothesis = claim("A scientific hypothesis.")
   evidence = claim("Supporting evidence.", given=[hypothesis])

   __all__ = ["context", "hypothesis", "evidence"]
   ```
6. Append `.gaia/` to `.gitignore`
7. Run `uv add gaia-lang` to add the dependency

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Package name, must end with `-gaia` |

**Error cases:**

- Name doesn't end with `-gaia` → error with suggestion
- `uv` not installed → error with install instructions
- Directory already exists → let `uv init` handle the error

## 2. `gaia add <package>`

Install a registered Gaia knowledge package by querying the official registry metadata
via GitHub API, then delegating to `uv add` with a pinned git URL.

**Usage:**

```bash
gaia add galileo-falling-bodies-gaia
gaia add galileo-falling-bodies-gaia --version 4.0.5
```

**Steps:**

1. Strip `-gaia` suffix to get registry package name (e.g., `galileo-falling-bodies`)
2. Fetch `packages/<name>/Package.toml` from GitHub API (`SiliconEinstein/gaia-registry`)
3. Fetch `packages/<name>/Versions.toml` from GitHub API
4. Parse TOML, select version:
   - Default: latest (last entry in `[versions]`)
   - `--version X.Y.Z`: specific version
5. Extract `repo` (from Package.toml), `git_sha` (from Versions.toml)
6. Run `uv add "<name>-gaia @ git+<repo>@<git_sha>"`

**Arguments / Options:**

| Argument | Required | Description |
|----------|----------|-------------|
| `package` | Yes | Package name (with or without `-gaia` suffix) |
| `--version` | No | Specific version, default latest |
| `--registry` | No | Registry GitHub repo, default `SiliconEinstein/gaia-registry` |

**Error cases:**

- Package not found in registry → clear error with available packages hint
- Version not found → error listing available versions
- GitHub API failure / rate limit → error with suggestion to set `GITHUB_TOKEN`
- `uv` not installed → error

**GitHub API access:**

- Uses `GITHUB_TOKEN` env var if set (for rate limits), otherwise anonymous
- Fetches file content via `GET /repos/{owner}/{repo}/contents/{path}`
- Decodes base64 content, parses TOML with `tomllib`

## 3. Registry CI Update

**File:** `gaia-registry/.github/workflows/register.yml`

**Changes:**

### 3a. Replace GAIA_REPO/GAIA_REF with PyPI install

Before:
```yaml
env:
  GAIA_REPO: https://github.com/SiliconEinstein/Gaia.git
  GAIA_REF: e9fcb1ae...

- name: Clone Gaia CLI source
  run: |
    git clone "$GAIA_REPO" /tmp/gaia
    cd /tmp/gaia && git checkout "$GAIA_REF" && uv sync
```

After:
```yaml
- name: Install Gaia CLI
  run: uv pip install gaia-lang
```

And simplify the validation step to call `gaia` directly instead of going through
`/tmp/gaia/.venv/bin/python -c "..."`.

### 3b. Add namespace validation

After `gaia compile` and `gaia check`, add:

```yaml
- name: Validate namespace
  run: |
    python3 -c "
    import json
    graph = json.load(open('.gaia/ir.json'))
    ns = graph.get('namespace', '')
    assert ns == 'github', f'Namespace must be \"github\" for this registry, got \"{ns}\"'
    print(f'Namespace OK: {ns}')
    "
```

## File Changes

| Repo | File | Action |
|------|------|--------|
| Gaia | `gaia/cli/main.py` | Register `init` and `add` commands |
| Gaia | `gaia/cli/commands/init.py` | New — scaffold command |
| Gaia | `gaia/cli/commands/add.py` | New — registry install command |
| Gaia | `tests/cli/test_init.py` | New — init tests |
| Gaia | `tests/cli/test_add.py` | New — add tests |
| gaia-registry | `.github/workflows/register.yml` | Modify — PyPI install + namespace check |

## Non-Goals

- Local registry cache (`~/.gaia/registry/`) — future optimization
- `gaia remove` / `gaia update` — not needed yet
- Configurable registry URL in `pyproject.toml` — hardcoded for now
- Publishing author packages to PyPI from registry CI — separate future work
