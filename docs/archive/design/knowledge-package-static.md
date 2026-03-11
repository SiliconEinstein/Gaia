# V1 Static Shared Knowledge Package Schema

## Purpose

This document defines the V1 static shared knowledge package schema used by both Gaia local/CLI and Gaia server.

It instantiates the shared vocabulary defined in [../domain-model.md](../domain-model.md).

It covers:

1. the core object layers used in shared Gaia knowledge packages
2. the static schema for `knowledge`, `module`, and `package`
3. the knowledge kind schemas for `claim`, `question`, `setting`, and `action`
4. the chain model: `knowledge ↔ inference` alternation within modules
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

## Design Rationale

### Gaia as Curry-Howard for plausible reasoning

Gaia is **Curry-Howard for plausible reasoning**: a probabilistic functional programming language where writing a knowledge package is constructing a plausible argument, and running belief propagation is computing how much you should believe the conclusions given the premises.

This document (V1) defines the **deterministic FP core** — knowledge objects (values), inferences (lambdas), chains (composition), modules, and packages. The **probabilistic layer** — priors, dependency strength as conditioning, and belief propagation as inference — is defined in [V3: Probabilistic Semantics](probabilistic-semantics.md). Together they extend the Curry-Howard correspondence from deductive proof to plausible reasoning, following Pólya, Jaynes, and Cox's theorem.

### Why a package/module system for knowledge?

Gaia's knowledge package model borrows its structural design from programming language module systems. The core insight is that **structured knowledge and structured code face the same organizational problems**: namespacing, dependency declaration, encapsulation, and reuse across contexts.

A research paper, like a software library, needs to:

- declare what it depends on (imports)
- expose a public interface (exports)
- organize internal logic into coherent units (modules)
- be distributed as a self-contained package

### Design influences

Gaia's design draws from two layers of programming language tradition:

- **Semantic model** — from functional programming (Haskell, OCaml): immutable values, knowledge objects as the universal currency, explicit interfaces, referential transparency
- **Packaging discipline** — from systems languages (Rust/Cargo): module = file, explicit exports, manifest-driven dependency management

The table below compares the semantic model (Haskell, OCaml) and the packaging model (Rust) with Gaia. Python is included as a familiar baseline.

| Aspect | Haskell | OCaml | Rust/Cargo | Python | Gaia |
|--------|---------|-------|------------|--------|------|
| **Core unit** | value (immutable) | value (immutable by default) | item (owned) | object (mutable) | knowledge (immutable) |
| **Composition** | function composition | function composition | expressions + items | statements | chain (knowledge ↔ inference) |
| **Package** | `.cabal` package | opam package | crate | PyPI package | knowledge package |
| **Module** | `module` (1:1 with files) | `module` (1:1 with files, or inline) | `mod` (1:1 with files) | `.py` file | module (with role) |
| **Public interface** | export list in `module Foo (...)` | `.mli` signature file | `pub` items | `__all__` / convention | `exports[]` knowledge_ids |
| **Interface contract** | type classes (value-level) | module signatures (module-level) | traits (value-level) | duck typing | imports[] + exports[] (module-level) |
| **Dependencies** | `import` + `.cabal` `build-depends` | `open` + opam `depends` | `use` + `Cargo.toml` | `import` + `requirements.txt` | `imports[]` with strength |
| **Internal modules** | `other-modules` in `.cabal` | `private_modules` in dune | `pub(crate)` | `_` prefix convention | non-exported knowledge objects in chain |
| **Parameterized modules** | — (type classes instead) | functors | — (traits instead) | — | — (deferred to V2) |
| **Manifest** | `package.cabal` | `opam` + `dune` | `Cargo.toml` | `pyproject.toml` | `Gaia.toml` |
| **Lock file** | `cabal.project.freeze` | `opam.locked` | `Cargo.lock` | `requirements.lock` | `Gaia.lock` (deferred) |

### Key design choices and their origins

**From Haskell/FP: immutable values as the universal currency.** In Haskell, values are immutable and referentially transparent — a name always refers to the same thing. Gaia's `knowledge` follows the same principle: a `knowledge_id` always refers to the same content, knowledge objects are never mutated in place, and they can be freely shared across modules and packages. This is why knowledge objects (not modules, not inferences) are the unit of import/export — they are the "values" of the knowledge system.

**From Haskell: explicit export lists.** Haskell modules declare exactly what they export via `module Foo (bar, baz) where`. Items not listed are internal. Gaia follows this directly: a module's `exports[]` lists the knowledge_ids that form its public interface, while other knowledge objects in the chain remain internal. At the package level, Haskell's `.cabal` distinguishes `exposed-modules` (public API) from `other-modules` (internal); Gaia's package `exports[]` plays the same role — a curated subset of module exports.

**From OCaml: module signatures as contracts.** OCaml separates interface (`.mli`) from implementation (`.ml`). The `.mli` file declares what a module provides without revealing how. In Gaia, a module's "signature" is its `imports[]` + `exports[]` + `role` — this is the contract other modules see. The `chain[]` is the "implementation" — the internal reasoning that produces the exported knowledge objects. This separation is structural in our schema: you can read a module's interface without reading its chain.

**From Rust: module = file, packaging discipline.** Rust binds modules to files 1:1 (`mod foo` → `foo.rs`) and uses `Cargo.toml` for manifest-driven dependency management. Gaia follows this packaging spirit: each module is a self-contained unit, `Gaia.toml` declares package-level metadata and dependencies, and the structure is mechanically navigable for both humans and AI agents.

**From FP: the chain as lambda composition.** Haskell programs are built by composing pure functions: `value → function → value → function → value`. Gaia's chain follows the same pattern: `knowledge → inference → knowledge → inference → knowledge`. Knowledge objects are the **states** (immutable, self-contained, exportable) and inferences are the **actions** (local transformations, context-dependent, not exportable). A chain is therefore a sequential composition of lambdas applied to values — `v₀ |> λ₁ |> v₁ |> λ₂ |> v₂`. An inference can be anonymous (plain text, like a lambda) or it can reference a named `action` knowledge object (like a named function application). This connects the two: an `action` knowledge object is a **function definition**, an `inference` with an `action` reference is a **function call**.

**Unique to Gaia: dependency strength.** No programming language distinguishes between strong and weak imports. In code, a dependency either compiles or it doesn't. In knowledge, the distinction matters: a `strong` dependency means "if this is wrong, my conclusion is likely wrong too," while a `weak` dependency means "this is relevant context, but my conclusion can stand on its own." This feeds directly into probabilistic evaluation (V3).

**Unique to Gaia: module roles.** Programming language modules don't declare their purpose. Gaia modules carry an optional `role` (reasoning, setting, motivation, follow_up_question, other) that replaces the need for separate editorial fields on packages. A `motivation` module replaces a "motivation" text field; a `follow_up_question` module replaces a "future work" section. The structure itself carries the editorial intent.

### Logical foundations and evolution roadmap

The Gaia package model has a precise correspondence to formal logic. Each version level raises the logical expressiveness:

| Logic level | Key capability | PL analogy | Gaia version |
|------------|---------------|-----------|-------------|
| **Propositional** | Concrete propositions, fixed connectives | values + lambdas | **V1**: knowledge objects + anonymous inferences |
| **Many-sorted first-order** | Variables, quantification over typed domains, named functions | Haskell/Lean type signatures | **V1**: action knowledge + named inferences (function application) |
| **Higher-order** | Functions over functions, parameterized modules | OCaml functors | **V2**: parameterized modules |
| **Dependent types** | Output type depends on input value | Lean/Coq | **Future**: formal verification of reasoning chains |

**V1 = propositional + first-order bridge.** Most V1 content operates at the propositional level: concrete knowledge objects connected by inferences. But the `action` knowledge with named inference references introduces first-order elements — an action like `contrastive_analysis` is implicitly universally quantified ("for any setting and claim, this analysis produces a claim"). V1 does not formalize this with explicit type signatures, but the structure is already there.

**Curry-Howard correspondence.** The connection to typed lambda calculus is not accidental:

| Curry-Howard | Gaia |
|-------------|------|
| **Type** (proposition) | **Claim** knowledge (a statement to be supported) |
| **Term** (proof/program) | **Chain** (the reasoning from imports to exported claim) |
| **Function type** `A → B` | **Action** (maps input knowledge to output knowledge) |
| **Function application** | **Named inference** (`inference: { action: knowledge_id }`) |
| **Type checking** | Dependency strength + BP (V3) |

A module's chain from imported premises to exported conclusion is, in this view, a **proof term** that inhabits the **type** declared by its exports. This connection becomes actionable in V2+ when formal verification of reasoning chains becomes possible.

### Future directions

The following features are identified as valuable for later versions, organized by the logical level they introduce:

#### Already expressible in V1

**Facade modules (Haskell re-exports).** A module with an empty chain that imports knowledge objects from other modules and re-exports them. Useful for aggregation packages (e.g., a "Physics" package curating exports from "Mechanics" and "Thermodynamics" sub-packages). No schema change needed.

#### V2: first-order and higher-order extensions

**Action type signatures (Lean/Haskell function types).** Formalize action knowledge with explicit input/output signatures:

```text
action {
  knowledge_id: cl_contrastive_analysis
  knowledge_kind: action
  action_type: infer
  inputs:  [setting, claim]     # formal parameter kinds
  outputs: [claim]              # return kind
  content: "Contrast behavior under two different conditions..."
}
```

This enables **type checking** of named inferences: when an inference references `cl_contrastive_analysis`, the surrounding knowledge objects in the chain should match the declared `inputs` and `outputs`. This is the step from propositional to fully formalized many-sorted first-order logic.

**Parameterized modules (OCaml functors).** Functors are "functions from modules to modules." For Gaia, this enables **reasoning templates**: a parameterized module that takes a `setting` module as input and produces a `reasoning` module as output. The same deductive chain instantiated with different assumptions yields different conclusions. This is higher-order logic — functions that operate on modules (which are themselves compositions of functions).

**Standalone module signatures (OCaml `.mli`).** A module signature declares "I need a knowledge object of kind `claim` about topic X" without providing one. Other packages provide implementations satisfying the interface. This supports a registry of "open problems" that packages can claim to solve — analogous to dune's virtual libraries.

**Opaque knowledge (Haskell abstract types).** Knowledge objects exported with `knowledge_id` and `summary` but without full `content`. Useful for packages behind access control, or for declaring conclusions without revealing supporting evidence.

#### V3: probabilistic semantics

**Dependency strength as soft type checking.** Where V2 type checking is structural ("do the knowledge kinds match?"), V3 adds probabilistic type checking: `strong` dependencies propagate belief, `weak` dependencies contribute to priors. This is a form of **graded type theory** where the "type" of a dependency carries a continuous weight rather than a binary pass/fail.

#### Future: dependent types and formal verification

**Dependent action signatures.** Output knowledge kind or content constraints that depend on input values — e.g., "if the input setting is `logical_setup`, the output claim must be a deductive conclusion." This requires dependent type theory and connects Gaia to formal proof assistants like Lean.

**Chain verification.** Formal verification that a module's chain is a valid proof term for its declared exports, given its imports. This is the ultimate Curry-Howard realization: the chain IS the proof, the exports ARE the theorem, and verification checks that the proof is valid.

## Design Boundary

This document defines only the shared static knowledge package schema.

The key split is:

- `knowledge` is a self-contained, globally reusable knowledge object
- `module` groups knowledge objects into a coherent unit via a chain, imports knowledge objects from other modules, and exports knowledge objects
- `package` is a reusable container of modules and exports knowledge objects from its modules

The document intentionally does not define where any object is stored. It defines only the logical structure.

## Core Model

Gaia V1 static structure has three layers:

1. global `knowledge`
2. local `module`
3. local `package`

The design follows a **state-action model** inspired by functional programming:

- a `knowledge` object is a self-contained knowledge object — the **state**. Like a closure in FP, it captures everything it needs and can be passed around (exported, imported, referenced) independently of its creation context
- an `inference` is a local reasoning step that connects knowledge objects — the **action**. Unlike a knowledge object, it depends on its surrounding context in the chain and is not exportable
- a module's `chain` alternates knowledge objects and inferences: `knowledge → inference → knowledge → inference → knowledge`
- knowledge kinds are: `claim`, `question`, `setting`, `action`
- modules declare cross-module dependencies via `imports` (with strong/weak strength) and make knowledge objects available via `exports`
- a `package` contains one or more modules and exports knowledge objects from its modules

## Object Overview

### 1. Knowledge

A `knowledge` object is a self-contained, globally reusable knowledge object.

The name comes from functional programming: like an FP closure that captures its free variables and can be passed around independently, a knowledge object carries its content and metadata and can be exported, imported, and referenced without knowing the chain it was created in.

Current knowledge kinds are:

- `claim` — a truth-apt statement or result
- `question` — an inquiry
- `setting` — context or environment
- `action` — a reusable process description

V1 keeps this set intentionally minimal. More detailed epistemic distinctions such as `observation` and `assumption` are deferred to later layers.

### 2. Module

A `module` groups knowledge objects into a coherent unit. It imports knowledge objects from other modules, arranges knowledge objects and inferences into a chain (the narrative), and exports selected knowledge objects.

This is analogous to a module in Rust or Julia: it groups related logic, declares its dependencies (`imports`), and exposes a public interface (`exports`).

Modules serve different roles within a package:

- **reasoning** — establishes conclusions through a chain of premises, inferences, and results
- **setting** — establishes shared context (definitions, environment, assumptions)
- **motivation** — establishes why the research was undertaken
- **follow_up_question** — establishes open questions for future work
- **other** — any module that does not fit the above roles

### 3. Package

A `package` is a reusable container of modules. It exports selected knowledge objects from its modules as the package's public interface.

It corresponds to a paper, research bundle, project unit, structured note, or another portable knowledge package.

## Knowledge Schema

All knowledge objects share the following minimal structure:

```text
knowledge {
  knowledge_id
  knowledge_kind      # claim | question | setting | action
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### `knowledge_id`

Stable global identifier.

V1 should treat `knowledge_id` as globally unique even when knowledge objects are first created locally.

Recommended shape:

```text
kn_<uuidv7>
```

The recommended rule is:

- use an opaque globally unique id as the primary knowledge identity
- generate it locally at creation time
- do not use content hash as the primary id

If later layers need semantic deduplication or merge suggestions, they should use separate fingerprints rather than rewriting `knowledge_id`.

### `knowledge_kind`

Exactly one of:

- `claim`
- `question`
- `setting`
- `action`

### `content`

The canonical primary payload of the knowledge object.

### `content_mode`

Single-valued mode describing the canonical primary representation.

Default:

- `nl`

Common explicit values:

- `python`
- `lean`
- `config`

V1 keeps exactly one canonical primary representation per knowledge object.

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
  knowledge_id
  knowledge_kind = claim
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
  knowledge_id
  knowledge_kind = question
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

A `setting` is a context-setting knowledge object. It specifies the background under which later reasoning should be interpreted or executed.

Examples include:

- definitions
- logical assumptions or model setup
- execution environments
- experimental environments

### Setting Schema

```text
setting {
  knowledge_id
  knowledge_kind = setting
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

It represents a process such as an inference method, a tool, or another canonicalized procedure. The action knowledge object describes **what** the process is; the `inference` entries in a module's chain describe **how** it was applied in a specific context.

### Action Schema

```text
action {
  knowledge_id
  knowledge_kind = action
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

An `inference` is a local reasoning step within a module's chain. It connects knowledge objects by filling logical gaps, providing explanations, or describing how an action was applied.

Unlike knowledge objects, inferences are **not** self-contained — they depend on their surrounding context in the chain. They are never exported or referenced from outside the module.

In the FP analogy: knowledge objects are **values**, inferences are **lambdas** (anonymous functions). A chain is a sequential composition of lambdas applied to values.

### Inference forms

V1 supports two inference forms:

**Anonymous inference (lambda)** — plain text describing the reasoning step:

```text
chain:
  - knowledge: cl_premise
  - inference: "Applying the definition to contrast vacuum and air behavior"
  - knowledge: cl_result
```

**Named inference (function application)** — references a reusable `action` knowledge object:

```text
chain:
  - knowledge: cl_premise
  - inference:
      content: "Applying contrastive analysis to vacuum vs air"
      action: cl_contrastive_analysis    # references an action knowledge object
  - knowledge: cl_result
```

The two forms correspond to the FP distinction between anonymous lambdas and named function calls:

| FP concept | Gaia inference form |
|------------|-------------------|
| `λx. x + 1` (anonymous lambda) | `inference: "reasoning text"` |
| `f(x)` (named function application) | `inference: { content, action: knowledge_id }` |

The `action` field is optional. When present, it must reference a knowledge object of kind `action`. The `content` field provides a human-readable description of how the action was applied in this specific context.

### Omitting inferences

When the logical transition between two knowledge objects is trivial or locally obvious, the inference may be omitted — two adjacent knowledge objects in the chain imply a trivial transition.

## Module

A `module` groups knowledge objects into a coherent unit via a chain of knowledge objects and inferences.

### Module Schema

```text
module {
  module_id
  role?             # reasoning | setting | motivation | follow_up_question | other
  summary?
  keywords[]?
  imports[]?        # knowledge dependencies from other modules
  exports[]         # knowledge_ids
  chain[]           # alternating knowledge objects and inferences
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

Cross-module dependencies. Each import declares a knowledge object this module depends on from another module, with provenance and dependency strength.

```text
imports: [
  {
    knowledge,      # knowledge_id
    from,           # module_id (provenance)
    strength        # strong | weak
  }
]
```

**Dependency semantics:**

- **strong** — if the imported knowledge is wrong, this module's conclusions are likely wrong too. This is a logical dependency that affects truth value.
- **weak** — the imported knowledge is relevant context, but this module's conclusions can stand on their own.

**Cross-package imports** use `knowledge_id` alone (which is globally unique). The `from` field may reference a module in the same package or identify an external source.

### `exports[]`

The knowledge objects this module makes available to the outside world. Analogous to `pub` in Rust or `export` in Julia.

Exported knowledge objects are the module's public interface. Non-exported knowledge objects that appear in the chain are internal to the module.

For single-file modules (simple chains), the last knowledge object in the chain is the implicit export by convention. Explicit `exports[]` overrides this default.

### `chain[]`

The module's narrative — an ordered list of knowledge objects and inferences.

```text
chain: [
  { knowledge: knowledge_id },
  { inference: "reasoning text" },                              # anonymous lambda
  { knowledge: knowledge_id },
  { inference: { content: "text", action: knowledge_id } },    # named function application
  { knowledge: knowledge_id },
  ...
]
```

**Chain rules:**

- the chain defines the recommended reading order for understanding the module's reasoning
- knowledge objects and inferences alternate: `knowledge → inference → knowledge → ...`
- adjacent knowledge objects (no inference between them) imply a trivial or obvious transition
- the chain may include imported knowledge objects for narrative context — their dependency semantics are declared in `imports`, not inferred from chain position
- the chain should not reverse the logical flow: conclusions should not precede their premises

### `metadata`

Optional module-level metadata.

## Package

A `package` is a container of modules. It exports selected knowledge objects from its modules as the package's public interface.

### Package Schema

```text
package {
  package_id
  summary?
  keywords[]?
  modules[]
  exports[]?        # knowledge_ids from any module
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

Modules within the same package can import each other's exported knowledge objects.

Different module roles serve different structural purposes: `reasoning` modules establish conclusions, `setting` modules provide shared context, `motivation` modules explain why the work was done, and `follow_up_question` modules capture open questions. This replaces the need for separate editorial fields — the structure itself carries the editorial intent.

### `exports[]`

Optional list of knowledge_ids from any module in the package. These are the package's public interface — the knowledge objects that the package offers to the outside world.

Package exports are typically a curated subset of module exports. For example, a package might export only its key conclusions and follow-up questions, not every intermediate result.

### `metadata`

Optional package-level metadata.

## Static Constraints

V1 static schema assumes:

1. knowledge objects are self-contained, globally reusable objects; inferences are local and context-dependent
2. modules declare cross-module dependencies via `imports` with dependency strength (`strong` / `weak`)
3. dependency strength determines whether a reference participates in later probabilistic evaluation
4. modules export knowledge objects, not inferences — the public interface is always self-contained objects
5. a module's chain alternates knowledge objects and inferences; knowledge objects are the states, inferences are the transitions
6. knowledge objects are global objects; they are not "owned" by any module or package

## Example

### Knowledge Objects

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
    {knowledge: cl_q1}
  ]
}

module {
  module_id = m_env
  role = setting
  summary = "Air resistance definitions"
  exports = [cl_s1]

  chain = [
    {knowledge: cl_s1}
  ]
}

module {
  module_id = m_main
  role = reasoning
  summary = "Air resistance, not mass, explains differential fall rates"
  keywords = ["air resistance", "drag", "falling bodies"]

  imports = [
    {knowledge: cl_s1, from: m_env, strength: strong},
    {knowledge: cl_q1, from: m_motivation, strength: weak}
  ]
  exports = [cl_c1]

  chain = [
    {knowledge: cl_s1},                                                     # imported: establish context
    {inference: {                                                            # named: references action knowledge
        content: "Contrasting vacuum vs air behavior using the definition",
        action: cl_a1
    }},
    {knowledge: cl_c1}                                                      # conclusion
  ]
}

module {
  module_id = m_follow
  role = follow_up_question
  summary = "Open questions on drag modeling"

  imports = [
    {knowledge: cl_c1, from: m_main, strength: weak}
  ]
  exports = [cl_q2]

  chain = [
    {knowledge: cl_q2}
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
- `m_main` (role=reasoning) imports `cl_s1` (strong) and `cl_q1` (weak), exports the conclusion `cl_c1`. Its chain uses a named inference referencing the `cl_a1` action knowledge object (function application)
- `m_follow` (role=follow_up_question) imports `cl_c1` (weak), exports the open question `cl_q2`
- the package exports `cl_c1` and `cl_q2` — only the main conclusion and follow-up question are published
- `cl_s1` is used internally (imported by `m_main`) but not re-exported by the package
- module roles replace separate editorial fields; the structure itself carries the editorial intent

## Deferred Topics

The following topics are intentionally deferred:

- how raw material is canonicalized into knowledge objects, modules, and packages
- how review works
- how optional revised packages are materialized
- how packages integrate into the global Gaia graph (V2)
- how prior, belief, and BP are defined on top of the dependency graph (V3)

Those belong to later documents.
