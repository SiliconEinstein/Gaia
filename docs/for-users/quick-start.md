# Quick Start

> **Status:** Current canonical

Create, build, and publish your first Gaia knowledge package in 10 minutes.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| Python | 3.12+ | [python.org](https://www.python.org/downloads/) |
| uv | latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Typst | latest | `brew install typst` or [typst.app](https://github.com/typst/typst/releases) |

Verify all three are available:

```bash
python3 --version   # 3.12+
uv --version
typst --version
```

## Install Gaia

```bash
git clone <your-gaia-repo-url>
cd Gaia
uv sync
```

That's it. All dependencies are managed by `uv`.

## Create a Package

```bash
python cli/main.py init my_first_package
```

This creates the following structure:

```
my_first_package/
  typst.toml            # package manifest (name, version, entrypoint)
  lib.typ               # entrypoint — includes all modules
  gaia.typ              # imports the Gaia runtime
  _gaia/                # vendored Gaia runtime (do not edit)
    lib.typ
    declarations.typ
    bibliography.typ
    style.typ
  motivation.typ        # starter module with a question
  reasoning.typ         # starter module with a setting and a claim
```

## Edit Your Package

Open `motivation.typ` and replace the placeholder with a real research question:

```typst
#import "gaia.typ": *

= Motivation

#setting[
  Consider two objects of different mass dropped from the same height
  in a controlled environment with minimal air resistance.
] <motivation.experimental_setup>

#question[
  Does the rate of free fall depend on an object's mass?
] <motivation.main_question>
```

Open `reasoning.typ` and add a claim with reasoning:

```typst
#import "gaia.typ": *

= Reasoning

#claim(kind: "observation", from: (<motivation.experimental_setup>,))[
  When air resistance is minimized, objects of different mass
  hit the ground at approximately the same time.
][
  Given the experimental setup @motivation.experimental_setup,
  repeated trials show no measurable difference in fall time
  across a range of masses from 1 kg to 50 kg.
] <reasoning.equal_fall_time>
```

Key syntax points:
- Each declaration ends with a label: `<filename.label_name>`
- `from:` lists premise labels as a tuple (single-element tuples need a trailing comma: `(<label>,)`)
- The second `[...]` block is the proof/justification, where you use `@label` to reference premises

## Build

```bash
python cli/main.py build my_first_package
```

Expected output:

```
Markdown: my_first_package/.gaia/build/package.md
Built my_first_package: 3 nodes, 1 factors
Artifacts: my_first_package/.gaia/graph/
Build complete.
```

Build artifacts go into `my_first_package/.gaia/`:
- `graph/raw_graph.json` — extracted knowledge graph
- `graph/local_canonical_graph.json` — canonicalized graph
- `build/graph_data.json` — full graph data
- `build/package.md` — human-readable Markdown rendering

## Infer

Run local belief propagation to compute belief values:

```bash
python cli/main.py infer my_first_package
```

Sample output:

```
Beliefs after BP:
  motivation.experimental_setup: prior=0.9 -> belief=0.9000
  reasoning.equal_fall_time: prior=0.7 -> belief=0.7842

Results: my_first_package/.gaia/infer/infer_result.json
```

Beliefs are probabilities in (0, 1). Claims supported by strong premises receive higher beliefs; unsupported or contradicted claims receive lower beliefs.

## Publish to Local Database

```bash
python cli/main.py publish my_first_package --local
```

This runs the full pipeline (build, review, infer, publish) and writes the package to your local LanceDB database:

```
Published my_first_package to v2 storage:
  Knowledge items: 3
  Chains: 1
  Factors: 1
```

By default, data is stored at `./data/lancedb/gaia`. Override with `--db-path` or the `GAIA_LANCEDB_PATH` environment variable.

## Search

Verify your package is in the database:

```bash
python cli/main.py search "free fall mass"
```

Look up a specific knowledge item by ID:

```bash
python cli/main.py search --id "reasoning.equal_fall_time"
```

## Next Steps

- [Language Reference](language-reference.md) — full cheat sheet for all declaration types, labels, cross-package references
- [CLI Commands](cli-commands.md) — complete reference for all `gaia` commands and options
- [Hole And Bridge Tutorial](hole-bridge-tutorial.md) — minimal end-to-end example for automatic `local_hole` discovery and downstream `fills`
