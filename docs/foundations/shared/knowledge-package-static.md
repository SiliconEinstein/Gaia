# V1 Static Shared Knowledge Package Schema

## Purpose

This document defines the V1 static shared knowledge package schema used by both Gaia local/CLI and Gaia server.

It instantiates the shared vocabulary defined in [../domain-model.md](../domain-model.md).

It covers:

1. the core object layers used in shared Gaia knowledge packages
2. the static schema for `knowledge_artifact`, `step`, `module`, and `package`
3. the minimal subtype schemas for `claim`, `question`, `setting`, and `action`
4. the static relationships between package structure and global reusable artifacts

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

- `knowledge_artifact` is global and reusable
- `step` is a local occurrence of one knowledge artifact, with explicit logical dependencies
- `step` belongs to exactly one module; the same artifact can appear in steps across different modules
- `module` groups related steps into a coherent unit and exports selected steps
- `package` is a reusable container of modules and exports selected steps from its modules

The document intentionally does not define where any object is stored. It defines only the logical structure.

## Core Model

Gaia V1 static structure has four layers:

1. global `knowledge_artifact`
2. local `step`
3. local `module`
4. local `package`

The main idea is:

- reusable content and reusable actions are global `knowledge_artifact`s
- a `step` is one use of a knowledge artifact, with explicit `input` dependencies (strong or weak)
- a `module` groups related steps into a coherent unit and exports selected steps — analogous to a module in a codebase
- a `package` contains one or more modules and exports selected steps from its modules, analogous to a paper or research bundle
- each step belongs to exactly one module; the same artifact can appear as steps in different modules
- logical dependencies are fully captured by `input` declarations on steps, not by narrative ordering
- the logical structure of a module is a hypergraph: each step's strong inputs jointly form the premises of a reasoning link to that step's conclusion

## Object Overview

### 1. Knowledge Artifact

A `knowledge_artifact` is a globally reusable object.

Current artifact kinds are:

- `claim`
- `question`
- `setting`
- `action`

V1 keeps this artifact set intentionally minimal.

More detailed epistemic distinctions such as `observation` and `assumption` are deferred to later graph and probabilistic layers. In V1 they are represented through `claim` or `setting` plus provenance and review context.

### 2. Step

A `step` is one local occurrence of a `knowledge_artifact` inside a module. Each step belongs to exactly one module.

Steps are needed because:

- the same global knowledge artifact may appear in multiple modules and packages (as different steps)
- the same knowledge artifact may have different logical dependencies in different contexts
- logical dependencies (strong/weak) belong to the step, not to the global knowledge artifact

Each step declares its own `input` dependencies explicitly. There are no implicit dependencies from narrative ordering.

### 3. Module

A `module` groups related steps into a coherent unit and exports selected steps. This is analogous to a module in a codebase — it groups related logic and has clear outputs.

Modules serve different roles within a package:

- **reasoning** — the primary type; establishes conclusions through a chain of premises, actions, and inferences
- **setting** — establishes shared context (definitions, environment, assumptions) used by other modules
- **motivation** — establishes why the research was undertaken (typically exports questions)
- **follow_up_question** — establishes open questions for future work
- **other** — any module that does not fit the above roles

The logical structure within a module is a **hypergraph**: each step with strong inputs implicitly defines a reasoning link where the strong input artifacts are the **premises** and the step's own artifact is the **conclusion**. This hypergraph is not declared as a separate object — it is derived from the step `input` declarations.

Modules within the same package can reference each other's steps or artifacts.

### 4. Package

A `package` is a reusable container of modules.

It corresponds to a paper, research bundle, project unit, structured note, or another portable knowledge package.

## Common Knowledge Artifact Schema

All knowledge artifacts share the following minimal structure:

```text
artifact_id
artifact_kind
content
content_mode = nl (default)
summary?
metadata?
embedding?
```

### `artifact_id`

Stable global identifier.

V1 should treat `artifact_id` as globally unique even when artifacts are first created locally.

Recommended shape:

```text
ka_<uuidv7>
```

The recommended rule is:

- use an opaque globally unique id as the primary artifact identity
- generate it locally at creation time
- do not use content hash as the primary id

If later layers need semantic deduplication or merge suggestions, they should use separate fingerprints rather than rewriting `artifact_id`.

### `artifact_kind`

Exactly one of:

- `claim`
- `question`
- `setting`
- `action`

### `content`

The canonical primary payload of the knowledge artifact.

### `content_mode`

Single-valued mode describing the canonical primary representation.

Default:

- `nl`

Common explicit values:

- `python`
- `lean`
- `config`

V1 keeps exactly one canonical primary representation per knowledge artifact.

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
  artifact_id
  artifact_kind = claim
  content
  content_mode = nl (default)
  summary?
  metadata?
  embedding?
}
```

### Modeling rule

- if the content is a statement-like result, model it as a `claim`
- do not put local roles such as `premise`, `context`, or `conclusion` on the claim itself

Those roles, when needed, belong to later local reasoning or review layers, not to the global claim object.

## Question

A `question` is an inquiry object. It is not a truth-apt statement.

Examples:

- "Why do a feather and a stone fall at different rates in air?"
- "Can this implementation be proven correct in Lean?"

### Question Schema

```text
question {
  artifact_id
  artifact_kind = question
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

A `setting` is a context-setting object. It specifies the background under which later reasoning should be interpreted or executed.

Examples include:

- definitions
- logical assumptions or model setup
- execution environments
- experimental environments

### Setting Schema

```text
setting {
  artifact_id
  artifact_kind = setting
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

An `action` is a reusable atomic process object.

It represents a process such as inference, tool use, or another canonicalized local step.

The action itself is global; a specific use of the action inside a package is represented by a `step`.

### Action Schema

```text
action {
  artifact_id
  artifact_kind = action
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

Package-specific execution details such as concrete inputs, outputs, runtime context, and artifacts should not be placed on the global action object. They belong to the local step occurrence.

## Step

A `step` is one local occurrence of a global knowledge artifact inside a module. Each step belongs to exactly one module. The same artifact can appear as different steps in different modules.

### Step Schema

```text
step {
  step_id
  artifact_id
  input[]?
  metadata?
}
```

### `step_id`

Stable local identifier inside the module.

### `artifact_id`

Reference to a global knowledge artifact.

### `input[]`

Explicit logical dependencies of this step.

```text
input: [
  {
    ref,          # step_id or artifact_id
    strength,     # strong | weak
    note?
  }
]
```

**Dependency semantics:**

- **strong** — if the referenced artifact is wrong, this step is likely wrong too. This is a logical dependency that affects truth value.
- **weak** — the referenced artifact is relevant context, but this step can stand on its own even if the reference is wrong.

**Reference types:**

- `ref` may be a `step_id` (local to the same package) or an `artifact_id` (global, including cross-package references)
- a `step_id` reference can always be resolved to its underlying `artifact_id`
- cross-package references must use `artifact_id`

**Rules:**

- all logical dependencies must be declared explicitly via `input`
- the narrative ordering of steps does NOT imply any dependency
- a step with no `input` is a leaf (starting point of the reasoning)

### `metadata`

Optional local occurrence metadata.

This is the right place for package-specific details such as:

- local notes
- concrete tool invocation details
- local execution context
- local artifact references

## Module

A `module` groups related steps into a coherent unit and exports selected steps.

### Module Schema

```text
module {
  module_id
  role?             # reasoning | setting | motivation | follow_up_question | other
  summary?
  keywords[]?
  exports[]         # step_ids
  steps[]
  metadata?
}
```

### `module_id`

Stable identifier for the module within the package.

### `role`

Optional module role. Recommended values:

- `reasoning` — establishes conclusions through premises, actions, and inferences
- `setting` — establishes shared context (definitions, environment, assumptions)
- `motivation` — establishes why the research was undertaken
- `follow_up_question` — establishes open questions for future work
- `other`

When omitted, `reasoning` is assumed by convention.

### `summary`

Optional short human-readable summary of what this module establishes.

### `keywords`

Optional keywords for search and discovery.

### `exports[]`

The steps this module makes available to the outside world. Analogous to `export` in Julia modules.

Exported steps are the module's public interface — they are what other modules, packages, or the global graph should reference and build upon. Non-exported steps are internal reasoning structure.

### `steps[]`

Ordered list of steps representing the narrative flow of this module.

**Narrative ordering:**

- the list defines the recommended reading order for understanding the reasoning
- adjacent steps may be logically unrelated (the narrative can have "breaks")
- the ordering should not reverse the logical flow: conclusions should not precede their premises in the narrative
- this ordering carries no implicit logical dependency; all dependencies are declared via `input` on each step

**Starting points are derived:** steps with no `input` are leaves (premises, observations, questions that begin the reasoning).

**Reasoning gap rule:** if there is a nontrivial logical gap between two artifacts in the reasoning, it should be made explicit with an `action` step. If the reasoning is trivial or locally obvious, the `action` may be omitted.

### `metadata`

Optional module-level metadata.

### Implicit hypergraph structure

The logical structure of a module is a hypergraph, derived from step `input` declarations:

- for each step with strong inputs, the strong input artifacts are the **premises** and the step's own artifact is the **conclusion** of one reasoning link
- weak inputs are relevant context but do not form reasoning links
- steps with no inputs are leaves (no incoming reasoning link)

This hypergraph is not declared as a separate schema object. It is always derived from the step `input` declarations, avoiding redundancy and inconsistency.

## Package

A `package` is a container of modules. It exports selected steps from its modules as the package's public interface.

It is the closest V1 analog of a paper, research bundle, or structured project unit.

### Package Schema

```text
package {
  package_id
  summary?
  keywords[]?
  modules[]
  exports[]?        # step_ids from any module
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

One or more modules included in the package. The list order defines the recommended reading order for the package (narrative ordering), analogous to how a module's `steps[]` order defines its internal narrative.

Modules within the same package can reference each other's steps (via `step_id`) or artifacts (via `artifact_id`).

Different module roles serve different structural purposes: `reasoning` modules establish conclusions, `setting` modules provide shared context, `motivation` modules explain why the work was done, and `follow_up_question` modules capture open questions. This replaces the need for separate editorial fields — the structure itself carries the editorial intent.

### `exports[]`

Optional list of step_ids from any module in the package. These are the package's public interface — the steps (and their underlying artifacts) that the package offers to the outside world.

Package exports are typically a curated subset of module exports. For example, a package might export only its key conclusions and follow-up questions, not every intermediate result.

### `metadata`

Optional package-level metadata.

## Static Constraints

V1 static schema assumes:

1. logical dependencies are fully captured by explicit `input` declarations on steps, not by narrative ordering
2. dependency strength (`strong` / `weak`) determines whether a reference participates in later probabilistic evaluation
3. local reasoning structure belongs to steps, not to global knowledge artifacts
4. each step belongs to exactly one module; the same artifact can appear as steps in different modules
5. modules export selected steps as their public interface; packages export selected steps from their modules
6. the implicit logical structure within a module is a hypergraph: each step's strong inputs jointly form the premises of a reasoning link
7. knowledge artifacts are global objects referenced by steps; they are not "owned" by any package

## Example

### Knowledge artifacts

```text
q1 = question("Why do a feather and a stone fall at different rates in air?")
s1 = setting(definition, "Air resistance depends on drag and shape.")
a1 = action(infer, "Contrast vacuum behavior with air-mediated behavior.")
c1 = claim("The observed difference in air is better explained by drag than by mass-dependent gravity.")
q2 = question("How can drag be modeled quantitatively for different shapes?")
```

### Modules

```text
module {
  module_id = m_motivation
  role = motivation
  summary = "Motivating question about differential fall rates"
  exports = [s_q1]

  steps = [
    s_q1(artifact_id=q1, input=[])
  ]
}

module {
  module_id = m_env
  role = setting
  summary = "Air resistance definitions"
  exports = [s_def]

  steps = [
    s_def(artifact_id=s1, input=[])
  ]
}

module {
  module_id = m_main
  role = reasoning
  summary = "Air resistance, not mass, explains differential fall rates"
  keywords = ["air resistance", "drag", "falling bodies"]
  exports = [s_conclusion]

  steps = [                            # narrative order
    s_action(artifact_id=a1, input=[
      {ref=s_q1, strength=weak},       # question motivates the action, but action is valid without it
      {ref=s_def, strength=strong}     # setting is required for the action to make sense
    ]),
    s_conclusion(artifact_id=c1, input=[
      {ref=s_def, strength=strong},    # definition is a logical premise
      {ref=s_action, strength=strong}  # action result is a logical premise
    ])
  ]
}

module {
  module_id = m_follow
  role = follow_up_question
  summary = "Open questions on drag modeling"
  exports = [s_followup]

  steps = [
    s_followup(artifact_id=q2, input=[
      {ref=s_conclusion, strength=weak}  # conclusion motivates the follow-up, but question stands on its own
    ])
  ]
}
```

Implicit hypergraph for `m_main` (derived from strong inputs):

```text
premises: [s1]           → conclusion: a1    (setting enables the inferential action)
premises: [s1, a1]       → conclusion: c1    (definition + action result jointly establish the claim)
```

### Package

```text
package {
  package_id = p1
  summary = "Why feathers and stones fall differently in air"
  keywords = ["falling bodies", "air resistance", "drag"]

  modules = [m_motivation, m_env, m_main, m_follow]   # narrative order

  exports = [s_conclusion, s_followup]                 # package public interface
}
```

Interpretation:

- each module has its own `exports` — its public interface within the package
- the package's `exports = [s_conclusion, s_followup]` is a curated subset: only the main conclusion and follow-up question are published to the outside world
- `m_env`'s exported setting `s_def` is used by `m_main` (via cross-module reference) but not re-exported by the package — it is internal shared context
- `m_motivation`'s exported question `s_q1` motivates the work but is also not in the package exports
- module roles (`motivation`, `setting`, `reasoning`, `follow_up_question`) replace the need for separate editorial fields on the package; the structure itself carries the editorial intent

## Deferred Topics

The following topics are intentionally deferred:

- how raw material is canonicalized into knowledge artifacts, steps, modules, and packages
- how review works
- how optional revised packages are materialized
- how packages integrate into the global Gaia graph (V2)
- how prior, belief, and BP are defined on top of the dependency graph (V3)

Those belong to later documents.
