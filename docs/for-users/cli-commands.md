# CLI Commands

> **Status:** Current canonical

Reference for all Gaia CLI commands. The CLI is invoked as `python cli/main.py <command>`.

---

### gaia init

Initialize a new Typst knowledge package with the v4 label-based DSL.

```
Usage: python cli/main.py init <name>
```

**Arguments:**

| Argument | Required | Description |
|----------|----------|-------------|
| `name` | Yes | Package name (also used as directory name) |

**What it creates:**

```
<name>/
  typst.toml          # package manifest
  lib.typ             # entrypoint
  gaia.typ            # runtime import
  _gaia/              # vendored Gaia runtime
    lib.typ
    declarations.typ
    bibliography.typ
    style.typ
  motivation.typ      # starter module with a question
  reasoning.typ       # starter module with a setting and claim
```

**Example:**

```bash
python cli/main.py init enzyme_kinetics
# Initialized Typst package 'enzyme_kinetics' in enzyme_kinetics/
```

The command fails if the directory already exists.

---

### gaia build

Build a knowledge package: validate structure, extract knowledge via `typst query`, compile the raw graph, and produce a local canonical graph.

```
Usage: python cli/main.py build [path] [--format FORMAT] [--proof-state]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the knowledge package directory |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--format` | `md` | Output format: `md`, `json`, `typst`, or `all` |
| `--proof-state` | off | Also generate a proof state analysis report |

**Output artifacts** (written to `<path>/.gaia/`):

| File | Description |
|------|-------------|
| `graph/raw_graph.json` | Extracted knowledge graph from Typst source |
| `graph/local_canonical_graph.json` | Canonicalized graph with resolved references |
| `graph/canonicalization_log.json` | Log of canonicalization decisions |
| `build/graph_data.json` | Full graph data as JSON |
| `build/package.md` | Human-readable Markdown rendering (when `--format md` or `all`) |
| `build/graph.json` | Graph JSON (when `--format json` or `all`) |
| `build/proof_state.txt` | Proof state report (when `--proof-state`) |

**Examples:**

```bash
# Build the current directory
python cli/main.py build

# Build a specific package with all output formats
python cli/main.py build my_package --format all

# Build with proof state analysis
python cli/main.py build my_package --proof-state
```

Requires `typst.toml` in the package directory. No LLM calls, no network access.

---

### gaia infer

Run local belief propagation on a built package. Computes posterior beliefs for all knowledge nodes.

```
Usage: python cli/main.py infer [path]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the knowledge package directory |

**Prerequisites:** The package must have been built (`gaia build`) at least once, so that `.gaia/build/` exists.

**Output:** Writes `<path>/.gaia/infer/infer_result.json` containing the BP run ID and belief values.

**Example:**

```bash
python cli/main.py build my_package
python cli/main.py infer my_package
```

```
Beliefs after BP:
  setting.vacuum_env: prior=0.9 -> belief=0.9000
  galileo.vacuum_prediction: prior=0.7 -> belief=0.8231
  aristotle.heavier_falls_faster: prior=0.6 -> belief=0.3512

Results: my_package/.gaia/infer/infer_result.json
```

The infer command runs the full pipeline internally: build, mock review (to derive priors and factor parameters), then belief propagation. It operates on the package-local graph only and does not query or modify any global database.

---

### gaia publish

Publish a package to git, a local database, or a remote server.

```
Usage: python cli/main.py publish [path] --git | --local | --server [--db-path PATH]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the knowledge package directory |

**Options (at least one required):**

| Option | Description |
|--------|-------------|
| `--git` | Publish via `git add`, `git commit`, `git push` |
| `--local` | Import to local LanceDB + Kuzu databases |
| `--server` | Publish to a Gaia server API (not yet implemented) |
| `--db-path` | LanceDB path (default: `$GAIA_LANCEDB_PATH` or `./data/lancedb/gaia`) |

**Examples:**

```bash
# Publish to local database
python cli/main.py publish my_package --local

# Publish to local database with custom path
python cli/main.py publish my_package --local --db-path ./my_data/lancedb

# Publish to git
python cli/main.py publish my_package --git
```

With `--local`, the command runs the full pipeline (build, review, infer, publish) and writes knowledge items, chains, and factors to LanceDB:

```
Published my_package to v2 storage:
  Knowledge items: 12
  Chains: 5
  Factors: 8
```

With `--git`, the command runs `git add .`, `git commit`, and `git push` in the package directory.

---

### gaia search

Search published knowledge items in the local LanceDB database.

```
Usage: python cli/main.py search [query] [--id ID] [--limit N] [--db-path PATH]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `query` | none | Search query text (BM25 full-text search) |

**Options:**

| Option | Default | Description |
|--------|---------|-------------|
| `--id` | none | Look up a specific knowledge item by ID |
| `--limit`, `-k` | `10` | Maximum number of results |
| `--db-path` | `$GAIA_LANCEDB_PATH` or `./data/lancedb/gaia` | LanceDB path |

Either `query` or `--id` must be provided.

**Examples:**

```bash
# Full-text search
python cli/main.py search "vacuum free fall"
```

```
  [galileo.vacuum_prediction] (claim) prior=0.7 belief=0.8231  score=4.521
    In a vacuum, objects of different mass fall at the same rate...
  [galileo.air_resistance_confound] (claim) prior=0.8 belief=0.7945  score=3.102
    Observed speed differences are artifacts of medium resistance...
```

```bash
# Look up by ID
python cli/main.py search --id "galileo.vacuum_prediction"
```

```
[galileo.vacuum_prediction] (claim)
  prior: 0.7  belief: 0.8231
  content: In a vacuum, objects of different mass fall at the same rate.
  keywords: vacuum, free fall, galileo, gravity
```

The search uses BM25 full-text indexing. For CJK or unsegmented text, it falls back to substring matching.

---

### gaia clean

Remove all build artifacts from a package.

```
Usage: python cli/main.py clean [path]
```

**Arguments:**

| Argument | Default | Description |
|----------|---------|-------------|
| `path` | `.` | Path to the knowledge package directory |

**Example:**

```bash
python cli/main.py clean my_package
# Removed my_package/.gaia
```

Deletes the entire `.gaia/` directory, including build, graph, and infer artifacts. Source files are not touched.
