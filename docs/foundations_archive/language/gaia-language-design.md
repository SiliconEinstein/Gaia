# Gaia Language Design (v4)

> Related documents:
> - [gaia-language-spec.md](gaia-language-spec.md)
> - [design-rationale.md](design-rationale.md)
> - [type-system-direction.md](type-system-direction.md)
> - [../theory/scientific-ontology.md](../theory/scientific-ontology.md)
> - [../theory/inference-theory.md](../theory/inference-theory.md)

## Purpose

This document defines the language design of Gaia v4 -- a Typst-based DSL for knowledge representation and epistemic inference. Authors write knowledge packages as ordinary Typst documents; the compiler extracts a structured knowledge graph (nodes, factors, constraints) via `typst query`.

## Design Approach

**Typst as host language.** Gaia v4 follows the same architecture as Church (extending Scheme) and Pyro (extending Python): a deterministic host language with domain-specific extensions. Typst provides the parser, renderer, and label/reference system; Gaia adds five declaration functions (`#setting`, `#question`, `#claim`, `#action`, `#relation`) and a cross-package bibliography mechanism.

**Small surface, richer ontology.** Gaia keeps a compact declaration surface on purpose. Richer scientific distinctions such as observation vs hypothesis, deductive vs abductive support, and load-bearing premise vs regime assumption should primarily appear through metadata and lowering, not through a large proliferation of new top-level keywords.

**No custom parser.** Every Gaia declaration is a standard Typst function call that produces a `figure(kind: "gaia-node")`. The compiler extracts the knowledge graph by querying these figures -- `typst query lib.typ 'figure.where(kind: "gaia-node")'` -- and reading the hidden `metadata()` dict inside each one.

**Primary user.** AI agents and researchers. Typst's lightweight markup makes packages readable as rendered documents while remaining machine-extractable.

## Type System

### Knowledge types

| Type | Typst function | Purpose | `from:` | `kind:` |
|------|---------------|---------|---------|---------|
| **Setting** | `#setting` | Context, assumption, definition | No | No |
| **Question** | `#question` | Open inquiry | No | No |
| **Claim** | `#claim` | Truth-apt statement | Yes | Yes (e.g. `"observation"`) |
| **Action** | `#action` | Procedural step | Yes | Yes (e.g. `"python"`) |
| **Relation** | `#relation` | Structural constraint between nodes | No | No (uses `type:` + `between:`) |

Current v4 keeps these root declaration types intentionally coarse. Finer distinctions should come from:

- `kind:` for claim/action subkinds
- future `mode:` for deductive / inductive / abductive support
- future `under:` for regime assumptions and background conditions

### Relation subtypes

- **`contradiction`** -- two nodes are mutually exclusive.
- **`equivalence`** -- two nodes express the same proposition.

There is no `corroboration` relation type. Independent evidence for the same claim is expressed by writing multiple claims with `from:` pointing at different premises.

### Factor graph mapping

| Declaration | Graph IR role |
|-------------|--------------|
| Setting, Claim (no `from:`) | Truth-apt node that may lower to a BP variable |
| Question | Inquiry artifact; extracted structurally but not a default BP variable |
| Claim with `from:` | Truth-apt node + reasoning factor connecting premises to conclusion |
| Action with `from:` | Procedural declaration; lowering is runtime-specific rather than core scientific ontology |
| Relation | Structural constraint; exact runtime lowering is defined downstream |

### Assumptions and Observations

- `#setting` occupies the current proof-state `assumption` role: accepted locally without proof, but still challengeable by other packages.
- `#claim(kind: "observation")` remains a claim. If it is used as a premise without a local proof or imported justification, it is a `hole`, not an assumption.
- `from:` should mean load-bearing premise, not a generic bag of related refs. Background conditions such as regime or idealization should eventually move to a distinct `under:`-style slot rather than overloading `from:`.
- Gaia intentionally does not expose a node-level `axiom` category. If future inference or explanation tooling needs multiple alternative starting-point sets, those should be represented as explicit `assumption basis` / proof-view selections on top of the same graph.

## Declaration Syntax

### Setting and Question (no premises, no proof)

```typst
#setting[The universe is spatially flat.] <setting.flat_universe>

#question[What is the physical nature of dark energy?] <main_question>
```

### Claim (optional `from:`, optional `kind:`, optional proof block)

```typst
// Leaf claim -- no premises
#claim(kind: "observation")[
  Type Ia supernovae data shows the universe's expansion is accelerating.
] <sn_observation>

// Derived claim with proof block
#claim(from: (<sn_observation>, <setting.flat_universe>))[
  Dark energy accounts for ~68% of total energy density.
][
  Given SN observations @sn_observation and spatial flatness @setting.flat_universe,
  the energy budget requires a dark energy component.
] <reasoning.dark_energy_fraction>
```

### Action (same signature as Claim)

```typst
#action(kind: "python", from: (<sn_observation>,))[
  MCMC fitting of Type Ia supernovae data using emcee.
] <mcmc_fit>
```

### Relation (`type:` + `between:`)

```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[
  These two claims are mutually exclusive.
][
  Optional proof block explaining why the contradiction holds.
] <the_contradiction>
```

### Proof blocks

The second positional content argument `[...]` is the **proof block**. It contains natural language reasoning with `@ref` cross-references explaining why the premises support the conclusion. Rendered with a left-border indent. Available on `#claim`, `#action`, and `#relation`.

## Labels and References

### Label convention

Every declaration ends with a Typst label: `<filename.knowledge_name>`. The filename prefix prevents collisions across modules within a package.

```typst
#setting[...] <setting.vacuum_env>
#claim[...]   <galileo.medium_density_observation>
```

### Cross-references within a package

Use Typst's `@ref` syntax inside proof blocks to cite other nodes:

```typst
#claim(from: (<aristotle.everyday_observation>,))[
  物体下落的速度与其重量成正比。
][
  Based on everyday observation @aristotle.everyday_observation ...
] <aristotle.heavier_falls_faster>
```

### Cross-package references

External nodes are declared via `#gaia-bibliography(yaml("gaia-deps.yml"))`, which creates hidden `figure(kind: "gaia-ext")` nodes. These can be used in `from:` tuples and `@ref` like local nodes.

**`gaia-deps.yml`:**

```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights fall at the same rate."
```

**Usage in Typst:**

```typst
#gaia-bibliography(yaml("gaia-deps.yml"))

#claim(from: (<local_derivation>, <vacuum_prediction>))[
  Newton's derivation and Galileo's thought experiment independently
  reach the same conclusion.
][
  Galileo's argument @vacuum_prediction and Newton's derivation
  @local_derivation converge on mass-independent free fall.
] <convergence>
```

## Metadata Extraction

Each declaration function produces a `figure(kind: "gaia-node")` containing a hidden `metadata()` dict:

| Metadata key | Present on | Value |
|-------------|-----------|-------|
| `"gaia-type"` | All | `"setting"` \| `"question"` \| `"claim"` \| `"action"` \| `"relation"` |
| `"from"` | Claim, Action | Tuple of label references (premises); empty tuple if none |
| `"kind"` | Claim, Action | Optional subtype string (e.g. `"observation"`, `"python"`); `none` if unset |
| `"rel-type"` | Relation | `"contradiction"` \| `"equivalence"` |
| `"between"` | Relation | Tuple of label references (the two constrained nodes) |

**Extraction command:**

```bash
typst query lib.typ 'figure.where(kind: "gaia-node")'
```

Returns a JSON array. The compiler (`libs/lang/typst_loader.py :: load_typst_package_v4`) parses this into a `{nodes, factors, constraints, ...}` dict for downstream ingestion.

## Package Structure

### File layout

```
dark_energy_v4/
  typst.toml          # package metadata (name, version)
  gaia.typ            # import shim: #import "/libs/typst/gaia-lang-v4/lib.typ": *
  gaia-deps.yml       # cross-package references (optional)
  lib.typ             # entrypoint: #show: gaia-style; #include per-module files
  setting.typ         # module file
  evidence.typ        # module file
  reasoning.typ       # module file
```

### `typst.toml`

Standard Typst package metadata. The compiler reads `package.name` and `package.version` from this file.

### `gaia.typ` (import shim)

A one-line file that re-exports the Gaia library so module files can write `#import "gaia.typ": *`:

```typst
#import "/libs/typst/gaia-lang-v4/lib.typ": *
```

### `lib.typ` (entrypoint)

Includes styling and all module files:

```typst
#import "gaia.typ": *
#show: gaia-style

#include "setting.typ"
#include "evidence.typ"
#include "reasoning.typ"
```

### Module files

Each `.typ` file (other than `lib.typ` and `gaia.typ`) is a module. Modules are implicit -- there are no explicit module boundary declarations. The filename serves as the module namespace via the label convention `<filename.name>`.

## Rendering

`gaia-style` provides show rules that render each declaration type with a colored left-border block, a type badge, and styled `@ref` cross-references. External references (`gaia-ext` figures) are hidden from rendered output.

## Compiler Pipeline

The v4 compiler (`load_typst_package_v4`) performs these steps:

1. Read `typst.toml` for package name and version.
2. Run `typst query lib.typ 'figure.where(kind: "gaia-node")'` to get local nodes.
3. Run `typst query lib.typ 'figure.where(kind: "gaia-ext")'` to get external references.
4. For each local node: extract label (identity), supplement (type), visible text (content), and hidden metadata (`from:`, `kind:`, `rel-type:`, `between:`).
5. For each node with `from:`: emit a reasoning factor `{premises -> conclusion}`.
6. For each relation node: emit a constraint `{type, between}`.
7. Return `{package, version, nodes, factors, constraints, dsl_version: "v4"}`.

## What v4 Does NOT Have (Future Work)

- **`under:` / contextual dependency** -- only `from:` exists today, meaning "premise." There is no first-class way to mark a reference as regime/background rather than load-bearing support.
- **`mode:` metadata** -- no first-class deductive / inductive / abductive distinction on support edges yet.
- **Dedicated independent-evidence relation type** -- use independent `claim(from:)` instead.
- **Action execution semantics** -- `#action` declares procedural knowledge but does not execute it.
- **Schema nodes** -- no parameterized or generic knowledge declarations.
- **Explicit module boundaries** -- modules are implicit from filenames. No `export` declarations.
- **Prior/posterior annotations** -- v4 does not embed probability values in the DSL; priors are assigned downstream.
