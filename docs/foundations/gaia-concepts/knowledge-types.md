# Knowledge Types

> **Status:** Current canonical

Gaia has four **declaration types** for knowledge objects and two **relation types** for structural constraints. Each maps to a Typst surface function and has defined behavior in belief propagation.

## Declaration Types

### Claim (`#claim`)

A truth-apt scientific assertion. The primary BP-bearing type.

- **Meaning**: a proposition that can be true or false, with quantifiable uncertainty.
- **Default prior**: author-assigned, in (epsilon, 1 - epsilon). No fixed default; must be parameterized before BP.
- **BP role**: full participant. Appears as premise or conclusion of reasoning factors. Belief updated by incoming factor messages.
- **Subtypes via `kind:`**: `"observation"`, `"hypothesis"`, `"law"`, `"prediction"`, etc. The `kind` records evidence type and scientific role but does not change Graph IR topology or BP behavior.
- **Surface**: `#claim(kind: "observation", from: (<premise>,))[content][proof]`

### Setting (`#setting`)

A contextual assumption, background condition, or regime restriction that requires no proof within the package.

- **Meaning**: accepted locally without justification. Can be challenged by contradiction from another package.
- **Default prior**: typically high (author considers it given), but still in (epsilon, 1 - epsilon).
- **BP role**: full participant. May appear as a premise in reasoning factors. Classified as `assumption` in proof state -- not exempt from BP, but not expected to have supporting chains within the package.
- **Surface**: `#setting[content] <label>`

### Question (`#question`)

An open scientific inquiry. Not a truth-apt assertion.

- **Meaning**: motivates the package but makes no claim about the world.
- **Default prior**: N/A. Questions are not parameterized for BP.
- **BP role**: **not a BP variable** by default. Extracted structurally into Graph IR but does not participate in message passing. Cannot appear as premise or conclusion of reasoning factors.
- **Surface**: `#question[content] <label>`

### Action (`#action`)

A procedural step or computational task. Shares the parameter signature of `#claim`.

- **Meaning**: declares a procedure to be performed. Not a default truth-apt proposition in the scientific sense.
- **Default prior**: N/A for default BP. Runtime-specific lowering may assign one.
- **BP role**: **not a default BP variable**. Lowering to BP is runtime-specific rather than part of the core ontology. May appear structurally in Graph IR.
- **Surface**: `#action(kind: "python", from: (<dep>,))[content][proof]`

## Relation Types

Relations are declared with `#relation(type:, between:)` and serve as structural constraints between existing nodes. In Graph IR, each relation declaration produces both a knowledge node (the relation itself) and a constraint factor.

### Contradiction (`#relation(type: "contradiction")`)

- **Meaning**: the two referenced nodes are mutually exclusive -- they should not both be true.
- **BP role**: the relation node participates as `premises[0]` in a `mutex_constraint` / `relation_contradiction` factor. When both constrained claims have high belief, BP sends inhibitory backward messages. The weaker claim is suppressed more. If both have overwhelming evidence, the relation node's own belief is lowered ("questioning the relationship").
- **V1 scope**: defined for claims, settings, and other relation nodes. Not defined for questions or bare actions.

### Equivalence (`#relation(type: "equivalence")`)

- **Meaning**: the two referenced nodes express the same proposition.
- **BP role**: the relation node participates as `premises[0]` in an `equiv_constraint` / `relation_equivalence` factor. Agreement between the constrained claims strengthens the relation; disagreement weakens it. N-ary equivalence decomposes into pairwise factors sharing the same relation node.
- **V1 scope**: type-preserving. For questions and actions, equivalence is valid only between nodes with the same root type and same `kind`.

## Summary Table

| Type | Typst function | Truth-apt? | BP participant? | `from:` | `between:` |
|---|---|---|---|---|---|
| Claim | `#claim` | Yes | Yes | Optional | No |
| Setting | `#setting` | Yes | Yes | No | No |
| Question | `#question` | No | No (structural only) | No | No |
| Action | `#action` | No (default) | No (default) | Optional | No |
| Contradiction | `#relation(type: "contradiction")` | Yes | Yes (as gate) | No | Required |
| Equivalence | `#relation(type: "equivalence")` | Yes | Yes (as gate) | No | Required |

## Source

- `libs/storage/models.py` -- `Knowledge.type` enum: `claim | question | setting | action | contradiction | equivalence`
- `docs/foundations/theory/belief-propagation.md` -- factor potential definitions
- `docs/foundations/theory/scientific-ontology.md` -- ontology classification
- `docs/foundations_archive/language/gaia-language-spec.md` -- declaration type definitions
