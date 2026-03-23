# Knowledge Types

> **Status:** Current canonical

Gaia has four **declaration types** for knowledge objects and two **relation types** for structural constraints. Each maps to a Typst surface function.

## Declaration Types

### Claim (`#claim`)

A truth-apt scientific assertion. The primary reasoning type.

- **Meaning**: a proposition that can be true or false, with quantifiable uncertainty.
- **Default prior**: author-assigned, in (epsilon, 1 - epsilon). No fixed default; must be parameterized before inference.
- **Subtypes via `kind:`**: `"observation"`, `"hypothesis"`, `"law"`, `"prediction"`, etc. The `kind` records evidence type and scientific role but does not change structural topology.
- **Surface**: `#claim(kind: "observation", from: (<premise>,))[content][proof]`

### Setting (`#setting`)

A contextual assumption, background condition, or regime restriction that requires no proof within the package.

- **Meaning**: accepted locally without justification. Can be challenged by contradiction from another package.
- **Default prior**: typically high (author considers it given), but still in (epsilon, 1 - epsilon).
- **Surface**: `#setting[content] <label>`

### Question (`#question`)

An open scientific inquiry. Not a truth-apt assertion.

- **Meaning**: motivates the package but makes no claim about the world.
- **Default prior**: N/A. Questions are not parameterized.
- **Surface**: `#question[content] <label>`

### Action (`#action`)

A procedural step or computational task. Shares the parameter signature of `#claim`.

- **Meaning**: declares a procedure to be performed. Not a default truth-apt proposition in the scientific sense.
- **Default prior**: N/A for default inference. Runtime-specific lowering may assign one.
- **Surface**: `#action(kind: "python", from: (<dep>,))[content][proof]`

## Relation Types

Relations are declared with `#relation(type:, between:)` and serve as structural constraints between existing nodes.

### Contradiction (`#relation(type: "contradiction")`)

- **Meaning**: the two referenced nodes are mutually exclusive -- they should not both be true.
- **V1 scope**: defined for claims, settings, and other relation nodes. Not defined for questions or bare actions.

### Equivalence (`#relation(type: "equivalence")`)

- **Meaning**: the two referenced nodes express the same proposition.
- **V1 scope**: type-preserving. For questions and actions, equivalence is valid only between nodes with the same root type and same `kind`.

## Summary Table

| Type | Typst function | Truth-apt? | `from:` | `between:` |
|---|---|---|---|---|
| Claim | `#claim` | Yes | Optional | No |
| Setting | `#setting` | Yes | No | No |
| Question | `#question` | No | No | No |
| Action | `#action` | No (default) | Optional | No |
| Contradiction | `#relation(type: "contradiction")` | Yes | No | Required |
| Equivalence | `#relation(type: "equivalence")` | Yes | No | Required |

## Proof State Classification

Each knowledge node in a package can be classified by its proof state — how well-supported it is within the package's reasoning structure:

| Proof state | Meaning |
|---|---|
| **Theorem** | Has at least one reasoning chain with all premises resolved within the package |
| **Assumption** | Accepted without proof within the package (settings, or claims with no `from:`) |
| **Hole** | Referenced as a premise but never declared — a gap in the reasoning |
| **Conjecture** | Has reasoning chains, but at least one premise is unresolved (depends on a hole) |

Run `gaia build --proof-state` to generate a proof state report. See `libs/lang/proof_state.py` for the analysis implementation.

## Cross-Layer References

- **BP behavior**: see [../../bp/potentials.md](../../bp/potentials.md)
- **Graph IR mapping** (how declarations become variable and factor nodes): see [../../graph-ir/factor-nodes.md](../../graph-ir/factor-nodes.md) and [../../graph-ir/knowledge-nodes.md](../../graph-ir/knowledge-nodes.md)

## Source

- `libs/storage/models.py` -- `Knowledge.type` enum: `claim | question | setting | action | contradiction | equivalence`
- `docs/foundations/theory/scientific-ontology.md` -- ontology classification
