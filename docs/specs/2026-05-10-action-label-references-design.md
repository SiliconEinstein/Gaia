# Action Label References Design

**Status:** Design proposal (v0.5)
**Branch:** off `v0.5`
**Date:** 2026-05-10

## 1. Scope

Today the v0.5 reference resolver `[@label]` / `@label` only sees Knowledge
labels. Action labels (e.g. the `label=` argument on `derive`, `infer`,
`compute`, `causes`, `decompose`, ...) are tracked in a parallel
`action_label_map`, but they are not part of the `label_to_id` table consulted
by `gaia.lang.refs.resolver.resolve`. As a result, an author who writes

```python
key_step = derive(conclusion=c, given=[p1, p2], rationale="...")
note(f"See [@key_step] for the warrant.")
```

gets a strict-form `unknown reference key '@key_step'` error at compile time,
even though `key_step` is a perfectly well-defined object in the package.

This spec proposes the minimum change needed to make action labels first-class
reference targets, without changing IR schema, BP semantics, or class
hierarchies.

## 2. First-Principles Model

Three identifier spaces already exist in the compiler:

1. **Knowledge labels** → `label_to_id: dict[str, str]` mapping author label to
   QID of an IR `Knowledge` node. Used by the reference resolver.
2. **Action labels** → `action_label_map: dict[str, str]` mapping author label
   (action QID) to the QID of the action's *target* (its conclusion claim, its
   warrant helper claim, or its strategy ID), populated during action
   lowering. Used by review tooling and metadata back-references.
3. **Citation keys** → `references.json`, owned by the package.

The reference resolver only joins (1) and (3). The proposal is to make it also
recognise (2), with the action's *target QID* as the resolved address. That is:
when an author writes `[@key_step]`, the rendered output should resolve to the
same QID that the reviewer UI already navigates to when they click on the
action.

This keeps Action firmly in the *authoring* layer (it is still not a Knowledge
subclass, still not a first-class IR node) while giving authors a single
unified `@label` syntax across claims and actions.

## 3. Resolved Target Rule

When an action label is referenced, what does it point to? The compiler
already chose a canonical answer per action shape, captured in
`action_label_map` during lowering:

| Action family | Target the label resolves to |
|---|---|
| `Derive / Observe / Compute / Predict` (`Support`) | the `conclusion` Claim QID |
| `Infer` / `Associate` / `bayes.likelihood` (`Probabilistic`) | the warrant `helper` Claim QID |
| `Equal / Contradict / Exclusive / Decompose` (`Structural`) | the warrant `helper` Claim QID |
| `Compose` | the IR `Compose` node QID |
| `DependsOn` (`Scaffold`) | not addressable — does not enter IR |

`DependsOn` is the only authoring-only action; its label is intentionally left
out of the unified table. Referencing it from text remains a strict-form error.

## 4. Compiler Change

In `gaia/lang/compiler/compile.py`, the `label_to_id` table is built from
`knowledge_nodes` only (around line 1142). Extend it with an additional pass
over registered actions, after the action lowering passes have populated
`action_label_map`:

```python
label_to_id: dict[str, str] = {}
for k in knowledge_nodes:
    if k.label:
        label_to_id[k.label] = knowledge_map[id(k)]

# v0.5 extension: action labels resolve to their lowered target QID.
for label, target_id in action_label_map.items():
    short_label = label.rsplit("::", 1)[-1] if "::" in label else label
    if short_label in label_to_id:
        # Existing knowledge label wins; record collision later.
        continue
    label_to_id[short_label] = target_id

check_collisions(label_to_id, references)
```

Notes:

- The action label stored in `action_label_map` is already a QID
  (`{namespace}:{package}::{label}`). The reference resolver compares against
  the short author-side key, so we must strip the QID prefix before inserting.
- `check_collisions` continues to fire if an action label collides with a
  citation key.
- Knowledge-vs-action collisions inside the package are surfaced as a new
  compile error (see §5).

## 5. Collision Handling

Two new collision cases are possible once action labels join the table:

1. **Knowledge label == action label** within the same package. This is
   ambiguous on the author side (`@foo` could mean either) and must fail with a
   clear error: *"label 'foo' is used for both a Claim and an Action; rename
   one side."* Implementation: detect during the merge step in §4 before
   inserting.
2. **Action label == citation key**. Falls through to the existing
   `check_collisions` call and produces the same `ambiguous reference key`
   error as today's claim-vs-citation collisions.

Both errors are compile-time. No silent disambiguation, no precedence rule.

## 6. Rendering Pipeline

Downstream consumers of the resolver output:

- **Markdown / Pandoc** rendering: `[@key_step]` becomes a hyperlink to the
  resolved target QID. The link text remains `key_step`. No change required
  in the rendering layer because it already takes whatever QID the resolver
  returns.
- **Review pipeline**: review prompts that surface `[@key_step]` should
  display the action label (not the target QID) so that reviewers see the
  same identifier the author wrote. The reverse lookup is already provided by
  `target_action_labels_by_id`; review tooling can use it to relabel.
- **Trace / inquiry CLI**: no change. They navigate by QID.

## 7. Documentation Update

Update `docs/foundations/gaia-lang/dsl.md` *Reference Syntax* section to add:

> **Action labels.** The `label=` argument on action verbs (`derive`,
> `observe`, `compute`, `predict`, `infer`, `associate`, `equal`, `contradict`,
> `exclusive`, `decompose`, `@compose`) registers the action in the same
> reference table as Claim labels. `[@my_action]` and `@my_action` resolve to
> the action's target — its conclusion claim for support actions, its warrant
> helper claim for probabilistic and structural actions, and the Compose node
> for composed workflows. `DependsOn` (`@compose` is fine; bare `depends_on`
> is not) is authoring-only and is not addressable. A label may not be used
> for both a Claim and an action in the same package.

## 8. Testing

Minimum coverage:

1. `[@derive_label]` resolves to the conclusion Claim QID.
2. `[@infer_label]` resolves to the warrant helper Claim QID.
3. `[@compose_label]` resolves to the IR `Compose` node QID.
4. Knowledge-label vs action-label collision raises a compile error.
5. Action-label vs citation-key collision raises the existing
   `check_collisions` error.
6. `DependsOn` label remains unaddressable (strict-form `[@...]` errors).

Tests live alongside the existing reference resolver tests
(`tests/lang/refs/`).

## 9. Non-Goals

- Promoting Action to a first-class IR node. Out of scope; `LocalCanonicalGraph`
  retains its current `knowledges / operators / strategies / composes` quad.
- Renaming `Action` to `Reasoning` or making it a Knowledge subclass. Out of
  scope; orthogonal to the reference problem and would muddy BP semantics.
- Cross-package action references. The current scope is local resolution only;
  cross-package action addressing follows the same rules as cross-package
  claim addressing once it is supported.
