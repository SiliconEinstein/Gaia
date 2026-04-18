# Language Reference

> **Status:** Needs upgrade to v5 — this reference covers the Typst v4 DSL, not the current Python DSL

Practical cheat sheet for the Gaia Language v4 Typst DSL. For the full specification, see `docs/foundations/interfaces/language-spec.md`.

## Package Structure

Every Gaia package is a Typst project with this layout:

```
my_package/
  typst.toml              # manifest: name, version, entrypoint
  lib.typ                 # entrypoint: imports runtime + includes modules
  gaia.typ                # imports the Gaia runtime library
  _gaia/                  # vendored runtime (created by `gaia init`)
    lib.typ
    declarations.typ
    bibliography.typ
    style.typ
  motivation.typ           # module: settings + questions
  reasoning.typ            # module: claims with from: premises
  follow_up.typ            # module: open questions for future work
  gaia-deps.yml            # (optional) cross-package references
```

**`typst.toml`** — package manifest:

```toml
[package]
name = "my_package"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Your Name"]
description = "What this package is about"
```

**`lib.typ`** — entrypoint that wires everything together:

```typst
#import "gaia.typ": *
#show: gaia-style

#include "motivation.typ"
#include "reasoning.typ"
#include "follow_up.typ"
```

**`gaia.typ`** — single-line import of the runtime:

```typst
#import "_gaia/lib.typ": *
```

## Declarations

### `#setting` — Background Assumption

An accepted context or condition that does not require proof within the package.

```typst
#setting[
  Consider two objects of different mass dropped from the same height.
  First examine their individual fall rates, then consider what happens
  when they are bound together into a composite body.
] <setting.thought_experiment>
```

Settings participate in belief propagation as premises. They have high default priors (the author considers them given).

### `#question` — Open Inquiry

A research question that motivates the package. Not truth-apt; does not participate in BP.

```typst
#question[
  Does the rate of free fall truly depend on an object's mass?
  If the observed difference is merely an artifact of air resistance,
  what should we expect under controlled conditions?
] <motivation.main_question>
```

### `#claim` — Scientific Assertion

A truth-apt proposition. The primary type for belief propagation.

```typst
#claim(kind: "observation")[
  In media of varying density, heavier and lighter objects show
  decreasing speed differences as the medium becomes less dense.
] <galileo.medium_density_obs>
```

With premises and proof:

```typst
#claim(from: (<galileo.tied_balls_contradiction>, <galileo.air_resistance_confound>))[
  In a vacuum, objects of different mass fall at the same rate.
][
  The tied-balls thought experiment shows the old law is self-contradictory
  @galileo.tied_balls_contradiction. Observed speed differences are artifacts
  of medium resistance @galileo.air_resistance_confound. These independent
  lines of evidence converge on equal fall rates in vacuum.
] <galileo.vacuum_prediction>
```

The optional `kind:` parameter records the scientific role without changing graph structure. Common values: `"observation"`, `"hypothesis"`, `"law"`, `"prediction"`.

### `#action` — Procedural Step

A computational or experimental procedure. Shares the `from:` and `kind:` parameters with `#claim`.

```typst
#action(kind: "python", from: (<data.raw_measurements>,))[
  Fit a linear regression to the fall-time measurements,
  extracting the acceleration coefficient for each mass value.
][
  Using the raw measurement data @data.raw_measurements,
  apply least-squares fitting to determine whether acceleration
  varies systematically with mass.
] <analysis.regression_fit>
```

Actions do not participate in BP by default.

### `#relation` — Structural Constraint

Declares a contradiction or equivalence between two existing nodes.

```typst
#relation(
  type: "contradiction",
  between: (<galileo.composite_is_slower>, <galileo.composite_is_faster>),
)[
  The predictions "the composite falls slower than the heavy ball"
  and "the composite falls faster than the heavy ball" are mutually exclusive.
][
  Both predictions derive from the same assumption that heavier objects
  fall faster. One invokes the drag effect of the lighter component
  @galileo.composite_is_slower; the other invokes the greater total mass
  @galileo.composite_is_faster. They cannot both be true.
] <galileo.tied_balls_contradiction>
```

Relation types:
- `"contradiction"` — the two nodes are mutually exclusive
- `"equivalence"` — the two nodes express the same proposition

## Connecting Claims with `from:`

The `from:` parameter declares load-bearing premises. It takes a tuple of label references.

**Single premise** (trailing comma required):

```typst
#claim(from: (<aristotle.everyday_observation>,))[
  An object's fall speed is proportional to its weight.
] <aristotle.heavier_falls_faster>
```

**Multiple premises:**

```typst
#claim(from: (<aristotle.heavier_falls_faster>, <setting.thought_experiment>))[
  Binding a heavy ball to a light ball produces a composite
  that should fall slower than the heavy ball alone.
][
  Under the assumption @aristotle.heavier_falls_faster, the lighter ball
  acts as a drag on the heavier one in the thought experiment
  @setting.thought_experiment.
] <galileo.composite_is_slower>
```

Each label in `from:` becomes a premise edge in the knowledge graph. The proof block (`[proof]`) should reference each premise using `@label` syntax to explain how it supports the conclusion.

## Labels

Labels follow the `<filename.label_name>` convention:

```typst
#setting[...]  <setting.vacuum_env>
#claim[...]    <reasoning.main_conclusion>
#question[...] <motivation.open_problem>
```

The `filename.` prefix is a naming convention that keeps labels unique across modules. Typst enforces label uniqueness within a document.

**Referencing labels in proof text** uses `@label` syntax:

```typst
#claim(from: (<setting.vacuum_env>,))[
  Objects fall at the same rate in vacuum.
][
  Given a vacuum environment @setting.vacuum_env, ...
] <reasoning.vacuum_result>
```

## Cross-Package References

To reference knowledge from another published package:

**1. Create `gaia-deps.yml`:**

```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights fall at the same rate."
```

Each entry declares one external knowledge node. The key (`vacuum_prediction`) becomes the label you reference.

**2. Register in your entrypoint (`lib.typ`):**

```typst
#import "gaia.typ": *
#show: gaia-style

#gaia-bibliography(yaml("gaia-deps.yml"))

#include "motivation.typ"
#include "reasoning.typ"
```

**3. Use the external label in claims:**

```typst
#claim(from: (<vacuum_prediction>, <local_observation>))[
  Extending Galileo's vacuum prediction to planetary-scale bodies...
][
  Building on the established result @vacuum_prediction ...
] <reasoning.extension>
```

## Common Patterns

### Motivation Module

Sets up context and poses research questions. Typically contains settings and questions only.

```typst
#import "gaia.typ": *

= Motivation

#setting[
  Background context for the investigation.
] <motivation.context>

#question[
  The central research question this package addresses.
] <motivation.main_question>
```

### Reasoning Module

Builds an argument from observations to conclusions. Claims reference earlier settings and other claims as premises.

```typst
#import "gaia.typ": *

= Reasoning

#claim(kind: "observation")[
  An empirical observation that serves as evidence.
] <reasoning.key_observation>

#claim(from: (<motivation.context>, <reasoning.key_observation>))[
  The main conclusion of the package.
][
  Given @motivation.context and the evidence from
  @reasoning.key_observation, we conclude ...
] <reasoning.main_conclusion>
```

### Follow-Up Module

Poses open questions for future investigation.

```typst
#import "gaia.typ": *

= Follow-Up

#question[
  Can the conclusion be verified under more extreme conditions?
  What additional experiments would provide stronger evidence?
] <follow_up.next_experiment>
```

### Contradiction Pattern

When two claims are mutually exclusive, declare a contradiction relation:

```typst
#claim(from: (<hypothesis_a>,))[Prediction X.] <reasoning.pred_x>
#claim(from: (<hypothesis_a>,))[Prediction Y (incompatible with X).] <reasoning.pred_y>

#relation(
  type: "contradiction",
  between: (<reasoning.pred_x>, <reasoning.pred_y>),
)[X and Y cannot both be true.] <reasoning.xy_contradiction>
```

In BP, the contradiction factor suppresses the weaker of the two claims.
