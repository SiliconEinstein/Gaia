# V1 Static Shared Knowledge Package Schema

## Purpose

This document defines the V1 static shared knowledge package schema used by both Gaia local/CLI and Gaia server.

It instantiates the shared vocabulary defined in [../domain-model.md](../domain-model.md).

It covers:

1. the core object layers used in shared Gaia knowledge packages
2. the static schema for `knowledge_artifact`, `chain_step`, `reasoning_chain`, and `package`
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
- `chain_step` is a local occurrence of one knowledge artifact inside one reasoning chain
- `reasoning_chain` is a local reasoning chain
- `package` is a reusable container of reasoning chains

The document intentionally does not define where any object is stored. It defines only the logical structure.

## Core Model

Gaia V1 static structure has four layers:

1. global `knowledge_artifact`
2. local `chain_step`
3. local `reasoning_chain`
4. local `package`

The main idea is:

- reusable content and reusable actions are global `knowledge_artifact`s
- a `reasoning_chain` is a single ordered chain of `chain_step` occurrences
- a `package` is a collection of related reasoning chains, similar to a paper or research bundle

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

### 2. Chain Step

A `chain_step` is one local occurrence of a `knowledge_artifact` inside a single `reasoning_chain`.

Chain steps are needed because:

- the same global knowledge artifact may appear in multiple reasoning chains
- the same knowledge artifact may be used differently in different reasoning chains
- local extra dependencies belong to the chain occurrence, not to the global knowledge artifact

### 3. Reasoning Chain

A `reasoning_chain` is the basic local reasoning unit.

It is represented as one ordered main path:

```text
step_1 -> step_2 -> ... -> step_n
```

The last step is the output of the reasoning chain.

### 4. Package

A `package` is a reusable container of reasoning chains.

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

The action itself is global; a specific use of the action inside a reasoning chain is represented by a `chain_step`.

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

Reasoning-chain-specific execution details such as concrete inputs, outputs, runtime context, and artifacts should not be placed on the global action object. They belong to the local chain-step occurrence.

## Chain Step

A `chain_step` is one local occurrence of a global knowledge artifact inside a reasoning chain.

### Chain Step Schema

```text
chain_step {
  step_id
  artifact_id
  extra_inputs[]?
  metadata?
}
```

### `step_id`

Stable local identifier inside the reasoning chain.

### `artifact_id`

Reference to a global knowledge artifact.

### `extra_inputs[]`

Optional extra dependencies beyond the ordered main path.

Suggested minimal shape:

```text
extra_inputs: [
  {
    step_id,
    strength,   # strong | weak
    note?
  }
]
```

Rules:

- `extra_inputs[]` should point only to earlier chain steps in the same reasoning chain
- the main predecessor in the ordered chain is not repeated here
- use `extra_inputs[]` only for non-main-path dependencies

### `metadata`

Optional local occurrence metadata.

This is the right place for reasoning-chain-specific details such as:

- local notes
- concrete tool invocation details
- local execution context
- chain-local artifact references

## Reasoning Chain

A `reasoning_chain` is the basic local reasoning chain.

### Reasoning Chain Schema

```text
reasoning_chain {
  chain_id
  chain_steps[]
  metadata?
}
```

### `chain_steps[]`

Ordered main path of the reasoning chain.

Rules:

- `chain_steps[]` is the canonical representation of the main chain
- the last chain step is the output of the reasoning chain
- if a reasoning thread naturally has multiple outputs, split it into multiple reasoning chains

V1 does not impose a rigid formal grammar such as:

- claim must always be followed by action
- question must always appear only at the beginning
- setting must appear only as background

Instead, a reasoning chain is valid when:

- the ordered path makes local logical sense
- each transition is understandable in context
- any materially nontrivial reasoning gap is made explicit with an `action`

This means:

- direct transitions such as `claim -> claim` are allowed when the step is trivial or locally obvious
- `action` is required when the transition would otherwise hide a meaningful reasoning jump

### `metadata`

Optional reasoning-chain-level metadata.

## Package

A `package` is a local container of related reasoning chains.

It is the closest V1 analog of a paper, research bundle, or structured project unit.

### Package Schema

```text
package {
  package_id
  reasoning_chains[]
  motivation_artifact_ids[]?
  key_claim_ids[]?
  follow_up_question_ids[]?
  shared_setting_ids[]?
  metadata?
}
```

### `package_id`

Stable identifier for the package.

### `reasoning_chains[]`

Ordered list of reasoning chains included in the package.

V1 does not constrain all reasoning chains to form a single global chain. A package may contain multiple related reasoning chains.

### `motivation_artifact_ids[]`

Optional references to knowledge artifacts that motivate the package.

These are intentionally typed as generic knowledge artifact references rather than split into claims and questions. Motivation may later expand beyond the current artifact kinds without changing package structure.

### `key_claim_ids[]`

Optional references to the package's most important claims.

### `follow_up_question_ids[]`

Optional references to the package's follow-up questions.

### `shared_setting_ids[]`

Optional references to settings shared across multiple reasoning chains in the package.

### `metadata`

Optional package-level metadata.

## Static Constraints

V1 static schema assumes:

1. a reasoning chain is a single ordered main path
2. the last chain step of a reasoning chain is its output
3. extra dependencies are explicit and local to chain-step occurrences
4. local reasoning structure belongs to reasoning chains, not to global knowledge artifacts
5. package roles such as motivation, key claims, and follow-up questions belong to the package, not to knowledge artifact identity

## Example

### Global knowledge artifacts

```text
q1 = question("Why do a feather and a stone fall at different rates in air?")
s1 = setting(definition, "Air resistance depends on drag and shape.")
a1 = action(infer, "Contrast vacuum behavior with air-mediated behavior.")
c1 = claim("The observed difference in air is better explained by drag than by mass-dependent gravity.")
q2 = question("How can drag be modeled quantitatively for different shapes?")
```

### Reasoning chain

```text
t1.chain_steps = [
  s01(artifact_id=q1),
  s02(artifact_id=s1),
  s03(artifact_id=a1),
  s04(artifact_id=c1, extra_inputs=[{step_id=s02, strength=strong}]),
  s05(artifact_id=q2)
]
```

Interpretation:

- the main path is the ordered sequence
- `q2` is the output of the reasoning chain because it is the last chain step
- `s04` additionally depends on `s02` beyond the immediate main-path predecessor

### Package

```text
package {
  package_id = p1
  reasoning_chains = [t1]
  motivation_artifact_ids = [q1]
  key_claim_ids = [c1]
  follow_up_question_ids = [q2]
  shared_setting_ids = [s1]
}
```

## Deferred Topics

The following topics are intentionally deferred:

- how raw material is canonicalized into knowledge artifacts, chain steps, reasoning chains, and packages
- how review works
- how optional revised packages are materialized
- how packages integrate into the global Gaia graph
- how support, contradiction, retraction, prior, belief, or BP should be defined

Those belong to later documents.
