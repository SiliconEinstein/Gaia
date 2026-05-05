# Decompose Action Design

**Status:** Implemented design (initial v0.5 surface)
**Branch:** `codex/v05-role-decompose-design` (off `v0.5`)
**Date:** 2026-05-05

## 1. Scope

This spec designs the deferred `decompose` action from the claim formula schema
work. Its job is to connect an opaque or high-level claim to a propositional
formula over smaller atomic claims.

Example target:

```python
decompose(
    whole=C,
    parts=(A, B, D),
    formula=land(ClaimAtom(A), implies(ClaimAtom(B), ClaimAtom(D))),
)
```

Semantically this says:

```text
C == (A and (B -> D))
```

Because the existing `Equal` action relates two `Claim` objects, the compiler
does not directly emit `Equal(C, formula)`. It generates a formula-helper claim
`F` whose formula is `A and (B -> D)`, then emits `Equal(C, F)`.

## 2. First-Principles Model

There are three different things that should not be conflated:

1. The **whole claim** `C`: the author-facing claim being decomposed.
2. The **atomic parts** `A`, `B`, `D`: smaller claims that can receive priors,
   evidence, roles, and review independently.
3. The **composition formula** `F`: a generated structural claim whose truth is
   determined by propositional logic over the atomic parts.

`decompose` is therefore an action-level macro:

```text
Decompose(C, parts=[A, B, D], formula=A and (B -> D))
    generates helper claim F(formula=A and (B -> D))
    generates Equal(C, F)
```

No new BP factor type or IR operator is needed. Formula lowering already emits
the propositional operator graph for `F`, and `Equal` already expresses the
equivalence between `C` and `F`.

## 3. Runtime Shape

The minimal runtime action is:

```python
@dataclass
class Structural(Action):
    """Hard structural constraint between claims or claim formulas."""


@dataclass
class Decompose(Structural):
    """Declares a whole claim equivalent to a formula over atomic claims."""

    whole: Claim | None = None
    parts: tuple[Claim, ...] = ()
    formula: Formula | None = None
```

Generated objects should be compiler outputs, not authored fields:

- `formula_helper`: generated claim `F`
- `equal_action`: generated `Equal(C, F)`

Keeping generated objects out of the author API prevents users from having to
name or manage structural helper claims manually. Tooling may expose generated
IDs for debugging.

`Decompose` should live under `Structural` in the public hierarchy, alongside
`Equal`, `Contradict`, and `Exclusive`. `Structural` is a semantic layer for hard
constraints; it does not need to own common `a` / `b` / `helper` fields. The
implementation should not reintroduce a `Relate` base class for those
hard-constraint actions. They can share compiler helpers without sharing a
field-only inheritance layer.

## 4. Generated Structure

For the example above, lowering performs:

```python
F = claim(
    "Formula decomposition of C",
    formula=land(ClaimAtom(A), implies(ClaimAtom(B), ClaimAtom(D))),
    metadata={
        "generated": True,
        "helper_kind": "decomposition_formula",
        "generated_by": "decompose:<label-or-stable-id>",
        "review": False,
    },
)

Equal(
    a=C,
    b=F,
    helper=claim(
        "C is equivalent to its decomposition formula",
        metadata={
            "generated": True,
            "helper_kind": "decomposition_equivalence",
            "generated_by": "decompose:<label-or-stable-id>",
            "review": False,
        },
    ),
    metadata={"generated_by": "decompose:<label-or-stable-id>"},
)
```

The generated helper names are illustrative. Stable IDs should be derived from
the whole claim ID, the formula structure, and the action label, not from the
display text.

The v0.5 runtime rejects multiple `Decompose` actions for the same whole claim.
Even two formulas that look equivalent should be authored as one canonical
decomposition for now; otherwise the generated equivalences silently assert the
two formulas are interchangeable. A later compiler pass may choose to dedupe
byte-identical decompositions, but that is not part of the initial surface.

## 5. Prior and Review Semantics

The default prior contract is:

- Atomic parts (`A`, `B`, `D`) are eligible for independent priors according to
  their action roles.
- The generated formula helper `F` is structural and does not receive an
  independent prior.
- The generated equivalence helper is structural and does not receive an
  independent prior.
- The whole claim `C` should not receive a new independent prior after
  decomposition unless the author explicitly marks it as a residual/legacy
  assertion.

Review attaches to the `Decompose` action itself: reviewers should check whether
`C` is faithfully represented by `A and (B -> D)`. They should not be asked to
review generated helper claims as separate scientific assertions.

In the current review manifest shape, that does not require a new target kind.
The review target can be the generated equivalence `Operator`; its metadata
should carry the `Decompose` action label and enough decomposition metadata for
the audit question to render as "Does `C` faithfully decompose into this
formula?" rather than the generic `Equal` wording. A future runtime may expose a
first-class action review target, but v0.5 does not need one.

This is the double-counting boundary. The decomposition lets evidence and
priors land on atomic parts without also treating the whole claim and generated
formula as independent probabilistic inputs.

## 6. Role Projection

`Decompose` contributes these roles to the role-on-action-graph API:

| Field | Role |
|---|---|
| `whole` | `decomposition_whole` |
| `parts` | `decomposition_part` |

Prior policy should treat `decomposition_part` as a possible prior target and
generated helpers as structural. The generated formula helper and generated
equivalence helper are not authored `Claim` objects and are not returned by
`roles_for_claim`; compiled IR marks them with
`metadata.helper_kind = "decomposition_formula"` and
`metadata.helper_kind = "decomposition_equivalence"`.

## 7. Validation Rules

Minimum validation:

1. `whole` must be a `Claim`.
2. `parts` must be non-empty and contain unique `Claim` objects.
3. `formula` must be a propositional formula over `ClaimAtom` and connectives in
   the first version.
4. Every `ClaimAtom` in `formula` must refer to a claim in `parts`, unless the
   author explicitly opts into external references in a later version.
5. Every part should occur at least once in the formula.
6. `whole` must not occur inside its own formula.
7. Decomposition cycles are invalid: a claim cannot decompose into a formula
   that depends, directly or transitively, on itself.
8. A whole claim may have at most one authored `Decompose` action in v0.5.

Quantifiers, variables, and lifted predicates can be supported later by the
existing formula grounding machinery. The first implementation should stay
propositional so that `decompose` is useful before it becomes clever.

## 8. Lowering Contract

Lowering is a macro expansion:

1. Register/generated helper claim `F` with the authored formula.
2. Run existing formula lowering for `F`.
3. Register/generated `Equal(C, F)`.
4. Run existing action lowering for `Equal`.
5. Preserve `Decompose` metadata for audit and review diagnostics.
6. Mark the generated equivalence operator as the review target for the
   `Decompose` action label.

The generated IR should contain only existing IR concepts: `Knowledge`,
`Operator`, and the strategy/operator records already emitted for formula
lowering and equivalence. There is no `DECOMPOSE` IR factor in v0.5.

## 9. CLI Applications

`decompose` should also be visible to the existing CLI surfaces, but it should
not add a new top-level command.

| CLI surface | Expected behavior |
|---|---|
| `gaia compile` | Deterministically expands each `Decompose` action into the generated formula helper, formula operators, and `Equal(C, F)` action. Generated IDs must be stable across runs. |
| `gaia check --hole` | Does not report the whole claim `C`, the formula helper `F`, or the generated equivalence helper as independent MaxEnt/prior holes solely because of the expansion. Atomic parts remain eligible independent DOFs according to their roles. |
| `gaia check --brief` | Presents `C == <formula over parts>` as one structural decomposition rather than listing generated helper claims as ordinary scientific assertions. |
| `gaia check --show <label>` | For `C`, shows the decomposition action, formula, parts, and generated equivalence. For an atomic part, shows that it participates in the decomposition. |
| `gaia infer` | No new flag. BP consumes the generated IR exactly as if the helper formula and equivalence were authored explicitly. |
| `gaia render` / Obsidian output | May group generated helper nodes under the decomposition action to avoid clutter while preserving traceability. |

The current canonical CLI docs should not describe these outputs until
`Decompose` exists in the runtime and compiler. Before then, this table is an
implementation target for the later CLI patch.

## 10. Tests

Minimum tests for implementation:

1. `decompose(C, [A, B, D], A and (B -> D))` generates one formula helper and
   one `Equal(C, F)` action.
2. Formula lowering for `F` emits the same operators as an authored claim with
   `formula=A and (B -> D)`.
3. The role API returns `decomposition_whole` for `C` and
   `decomposition_part` for `A`, `B`, and `D`; generated helpers carry their
   structural role through compiled IR metadata.
4. The default prior policy selects atomic parts when appropriate and skips the
   generated helpers.
5. Invalid formulas fail fast: missing part, unused part, self-reference,
   duplicate part, repeated decomposition of one whole, and decomposition
   cycles.
6. `gaia check --hole` reports only role-selected atomic parts as independent
   DOFs for a decomposed claim.
7. `gaia check --show C` displays the decomposition as `C == formula` without
   asking the reader to inspect generated helper claims manually.

## 11. Open Questions

1. The Python helper may return the `Decompose` action or return `whole` for
   chaining. The runtime semantics do not depend on that choice.
2. A future review UI may present `C == formula` as one review target instead of
   exposing helper claims.
3. Residual priors for legacy whole claims need an explicit author annotation if
   they are ever needed.
