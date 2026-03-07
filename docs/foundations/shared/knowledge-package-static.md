# V1 Static Shared Knowledge Package Schema

## Purpose

This document defines the V1 static shared knowledge package schema used by both Gaia local/CLI and Gaia server.

It instantiates the shared vocabulary defined in [../domain-model.md](../domain-model.md).

It covers:

1. the core object layers used in shared Gaia knowledge packages
2. the static schema for `closure`, `module`, and `package`
3. the closure kind schemas for `claim`, `question`, `setting`, and `action`
4. the chain model: `closure ↔ inference` alternation within modules
5. the import/export model for cross-module dependencies

It does not cover:

- canonicalization
- review
- optional revision/materialization
- Gaia graph integration
- prior / belief / BP

Those belong to later documents:

- V1 file formats: shared package file formats and review-report contracts
- V2: global Gaia graph integration
- V3: probabilistic semantics and propagation

## Design Boundary

This document defines only the shared static knowledge package schema.

The key split is:

- `closure` is a self-contained, globally reusable knowledge object
- `module` groups closures into a coherent unit via a chain, imports closures from other modules, and exports closures
- `package` is a reusable container of modules and exports closures from its modules

The document intentionally does not define where any object is stored. It defines only the logical structure.

## Core Model

Gaia V1 static structure has three layers:

1. global `closure`
2. local `module`
3. local `package`

The design follows a **state-action model** inspired by functional programming:

- a `closure` is a self-contained knowledge object — the **state**. Like a closure in FP, it captures everything it needs and can be passed around (exported, imported, referenced) independently of its creation context
- an `inference` is a local reasoning step that connects closures — the **action**. Unlike a closure, it depends on its surrounding context in the chain and is not exportable
- a module's `chain` alternates closures and inferences: `closure → inference → closure → inference → closure`
- closure kinds are: `claim`, `question`, `setting`, `action`
- modules declare cross-module dependencies via `imports` (with strong/weak strength) and make closures available via `exports`
- a `package` contains one or more modules and exports closures from its modules

## Object Overview

### 1. Closure

A `closure` is a self-contained, globally reusable knowledge object.

The name comes from functional programming: like an FP closure that captures its free variables and can be passed around independently, a knowledge closure carries its content and metadata and can be exported, imported, and referenced without knowing the chain it was created in.

Current closure kinds are:

- `claim` — a truth-apt statement or result
- `question` — an inquiry
- `setting` — context or environment
- `action` — a reusable process description

V1 keeps this set intentionally minimal. More detailed epistemic distinctions such as `observation` and `assumption` are deferred to later layers.

### 2. Module

A `module` groups closures into a coherent unit. It imports closures from other modules, arranges closures and inferences into a chain (the narrative), and exports selected closures.

This is analogous to a module in Rust or Julia: it groups related logic, declares its dependencies (`imports`), and exposes a public interface (`exports`).

Modules serve different roles within a package:

- **reasoning** — establishes conclusions through a chain of premises, inferences, and results
- **setting** — establishes shared context (definitions, environment, assumptions)
- **motivation** — establishes why the research was undertaken
- **follow_up_question** — establishes open questions for future work
- **other** — any module that does not fit the above roles

### 3. Package

A `package` is a reusable container of modules. It exports selected closures from its modules as the package's public interface.

It corresponds to a paper, research bundle, project unit, structured note, or another portable knowledge package.

## Closure Schema

All closures share the following minimal structure:

```text
closure {
  closure_id
  closure_kind        # claim | question | setting | action
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### `closure_id`

Stable global identifier.

V1 should treat `closure_id` as globally unique even when closures are first created locally.

Recommended shape:

```text
cl_<uuidv7>
```

The recommended rule is:

- use an opaque globally unique id as the primary closure identity
- generate it locally at creation time
- do not use content hash as the primary id

If later layers need semantic deduplication or merge suggestions, they should use separate fingerprints rather than rewriting `closure_id`.

### `closure_kind`

Exactly one of:

- `claim`
- `question`
- `setting`
- `action`

### `content`

The canonical primary payload of the closure.

### `content_mode`

Single-valued mode describing the canonical primary representation.

Default:

- `nl`

Common explicit values:

- `python`
- `lean`
- `config`

V1 keeps exactly one canonical primary representation per closure.

### `summary`

Optional short human-readable summary.

### `metadata`

Optional extensible metadata container.

Suggested minimal shape:

```text
refs[]?
extra{}?
```

`refs[]` should point only to external resources such as papers, files, datasets, images, tables, or execution artifacts.

### `embedding`

Optional retrieval embedding.

## Claim

A `claim` is a truth-apt statement or result object that can be supported, challenged, or reused.

Examples:

- a natural-language scientific statement
- a gap statement written as a declarative sentence
- a Python code result
- a Lean theorem or proof artifact treated as a reusable result object

### Claim Schema

```text
claim {
  closure_id
  closure_kind = claim
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### Modeling rule

- if the content is a statement-like result, model it as a `claim`
- do not put local roles such as `premise`, `context`, or `conclusion` on the claim itself — those are determined by the module's chain and imports

## Question

A `question` is an inquiry object. It is not a truth-apt statement.

Examples:

- "Why do a feather and a stone fall at different rates in air?"
- "Can this implementation be proven correct in Lean?"

### Question Schema

```text
question {
  closure_id
  closure_kind = question
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### Modeling rule

- if the content is a genuine question, model it as a `question`
- if the content is a statement-form problem or gap, model it as a `claim`

## Setting

A `setting` is a context-setting closure. It specifies the background under which later reasoning should be interpreted or executed.

Examples include:

- definitions
- logical assumptions or model setup
- execution environments
- experimental environments

### Setting Schema

```text
setting {
  closure_id
  closure_kind = setting
  setting_type
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### `setting_type`

Recommended initial values:

- `definition`
- `logical_setup`
- `execution_environment`
- `experimental_environment`
- `other`

### Modeling rule

- if the object mainly sets the background for later reasoning, model it as a `setting`
- if the object mainly asserts that some fact is true, model it as a `claim`

Example:

- "This analysis adopts a near-vacuum model." -> `setting`
- "The experiment was in fact run in a near-vacuum chamber." -> `claim`

## Action

An `action` is a self-contained, reusable process description.

It represents a process such as an inference method, a tool, or another canonicalized procedure. The action closure describes **what** the process is; the `inference` entries in a module's chain describe **how** it was applied in a specific context.

### Action Schema

```text
action {
  closure_id
  closure_kind = action
  action_type
  content
  content_mode = nl (default)
  summary?
  tool_name?
  metadata?
  embedding?
}
```

### `action_type`

Recommended initial values:

- `infer`
- `tool_call`
- `other`

### `tool_name`

Optional stable tool identifier for `tool_call` actions.

## Inference

An `inference` is a local reasoning step within a module's chain. It connects closures by filling logical gaps, providing explanations, or describing how an action was applied.

Unlike closures, inferences are **not** self-contained — they depend on their surrounding context in the chain. They are never exported or referenced from outside the module.

In the state-action model: closures are the **states**, inferences are the **actions**.

### Inference in chain

An inference appears as an inline entry between closures in the chain:

```text
chain:
  - closure: cl_premise
  - inference: "Applying the definition to contrast vacuum and air behavior"
  - closure: cl_result
```

When the logical transition between two closures is trivial or locally obvious, the inference may be omitted — two adjacent closures in the chain imply a trivial transition.

V1 represents inferences as plain text content. Later versions may add structure (type, tool reference, etc.) if needed.

## Module

A `module` groups closures into a coherent unit via a chain of closures and inferences.

### Module Schema

```text
module {
  module_id
  role?             # reasoning | setting | motivation | follow_up_question | other
  summary?
  keywords[]?
  imports[]?        # closure dependencies from other modules
  exports[]         # closure_ids
  chain[]           # alternating closures and inferences
  metadata?
}
```

### `module_id`

Stable identifier for the module within the package.

### `role`

Optional module role. Recommended values:

- `reasoning` — establishes conclusions through premises, inferences, and results
- `setting` — establishes shared context (definitions, environment, assumptions)
- `motivation` — establishes why the research was undertaken
- `follow_up_question` — establishes open questions for future work
- `other`

When omitted, `reasoning` is assumed by convention.

### `summary`

Optional short human-readable summary of what this module establishes.

### `keywords`

Optional keywords for search and discovery.

### `imports[]`

Cross-module dependencies. Each import declares a closure this module depends on from another module, with provenance and dependency strength.

```text
imports: [
  {
    closure,        # closure_id
    from,           # module_id (provenance)
    strength        # strong | weak
  }
]
```

**Dependency semantics:**

- **strong** — if the imported closure is wrong, this module's conclusions are likely wrong too. This is a logical dependency that affects truth value.
- **weak** — the imported closure is relevant context, but this module's conclusions can stand on their own.

**Cross-package imports** use `closure_id` alone (which is globally unique). The `from` field may reference a module in the same package or identify an external source.

### `exports[]`

The closures this module makes available to the outside world. Analogous to `pub` in Rust or `export` in Julia.

Exported closures are the module's public interface. Non-exported closures that appear in the chain are internal to the module.

For single-file modules (simple chains), the last closure in the chain is the implicit export by convention. Explicit `exports[]` overrides this default.

### `chain[]`

The module's narrative — an ordered list of closures and inferences.

```text
chain: [
  { closure: closure_id },
  { inference: "reasoning text" },
  { closure: closure_id },
  ...
]
```

**Chain rules:**

- the chain defines the recommended reading order for understanding the module's reasoning
- closures and inferences alternate: `closure → inference → closure → ...`
- adjacent closures (no inference between them) imply a trivial or obvious transition
- the chain may include imported closures for narrative context — their dependency semantics are declared in `imports`, not inferred from chain position
- the chain should not reverse the logical flow: conclusions should not precede their premises

### `metadata`

Optional module-level metadata.

## Package

A `package` is a container of modules. It exports selected closures from its modules as the package's public interface.

### Package Schema

```text
package {
  package_id
  summary?
  keywords[]?
  modules[]
  exports[]?        # closure_ids from any module
  metadata?
}
```

### `package_id`

Stable identifier for the package.

### `summary`

Optional short human-readable summary of the package.

### `keywords`

Optional keywords for search and discovery.

### `modules[]`

One or more modules included in the package. The list order defines the recommended reading order for the package (narrative ordering).

Modules within the same package can import each other's exported closures.

Different module roles serve different structural purposes: `reasoning` modules establish conclusions, `setting` modules provide shared context, `motivation` modules explain why the work was done, and `follow_up_question` modules capture open questions. This replaces the need for separate editorial fields — the structure itself carries the editorial intent.

### `exports[]`

Optional list of closure_ids from any module in the package. These are the package's public interface — the closures that the package offers to the outside world.

Package exports are typically a curated subset of module exports. For example, a package might export only its key conclusions and follow-up questions, not every intermediate result.

### `metadata`

Optional package-level metadata.

## Static Constraints

V1 static schema assumes:

1. closures are self-contained, globally reusable objects; inferences are local and context-dependent
2. modules declare cross-module dependencies via `imports` with dependency strength (`strong` / `weak`)
3. dependency strength determines whether a reference participates in later probabilistic evaluation
4. modules export closures, not inferences — the public interface is always self-contained objects
5. a module's chain alternates closures and inferences; closures are the states, inferences are the transitions
6. knowledge closures are global objects; they are not "owned" by any module or package

## Example

### Closures

```text
cl_q1 = question("Why do a feather and a stone fall at different rates in air?")
cl_s1 = setting(definition, "Air resistance depends on drag and shape.")
cl_a1 = action(infer, "Contrast vacuum behavior with air-mediated behavior.")
cl_c1 = claim("The observed difference in air is better explained by drag than by mass-dependent gravity.")
cl_q2 = question("How can drag be modeled quantitatively for different shapes?")
```

### Modules

```text
module {
  module_id = m_motivation
  role = motivation
  summary = "Motivating question about differential fall rates"
  exports = [cl_q1]

  chain = [
    {closure: cl_q1}
  ]
}

module {
  module_id = m_env
  role = setting
  summary = "Air resistance definitions"
  exports = [cl_s1]

  chain = [
    {closure: cl_s1}
  ]
}

module {
  module_id = m_main
  role = reasoning
  summary = "Air resistance, not mass, explains differential fall rates"
  keywords = ["air resistance", "drag", "falling bodies"]

  imports = [
    {closure: cl_s1, from: m_env, strength: strong},
    {closure: cl_q1, from: m_motivation, strength: weak}
  ]
  exports = [cl_c1]

  chain = [
    {closure: cl_s1},                                                   # imported: establish context
    {inference: "Contrasting vacuum vs air behavior using the definition"},
    {closure: cl_a1},                                                   # reusable analysis method
    {inference: "The analysis shows drag, not mass, explains the difference"},
    {closure: cl_c1}                                                    # conclusion
  ]
}

module {
  module_id = m_follow
  role = follow_up_question
  summary = "Open questions on drag modeling"

  imports = [
    {closure: cl_c1, from: m_main, strength: weak}
  ]
  exports = [cl_q2]

  chain = [
    {closure: cl_q2}
  ]
}
```

### Package

```text
package {
  package_id = p1
  summary = "Why feathers and stones fall differently in air"
  keywords = ["falling bodies", "air resistance", "drag"]

  modules = [m_motivation, m_env, m_main, m_follow]   # narrative order

  exports = [cl_c1, cl_q2]                             # package public interface
}
```

### Interpretation

- `m_motivation` (role=motivation) exports the motivating question `cl_q1`
- `m_env` (role=setting) exports the shared definition `cl_s1`
- `m_main` (role=reasoning) imports `cl_s1` (strong) and `cl_q1` (weak), exports the conclusion `cl_c1`
- `m_follow` (role=follow_up_question) imports `cl_c1` (weak), exports the open question `cl_q2`
- the package exports `cl_c1` and `cl_q2` — only the main conclusion and follow-up question are published
- `cl_s1` is used internally (imported by `m_main`) but not re-exported by the package
- module roles replace separate editorial fields; the structure itself carries the editorial intent

## Deferred Topics

The following topics are intentionally deferred:

- how raw material is canonicalized into closures, modules, and packages
- how review works
- how optional revised packages are materialized
- how packages integrate into the global Gaia graph (V2)
- how prior, belief, and BP are defined on top of the dependency graph (V3)

Those belong to later documents.
