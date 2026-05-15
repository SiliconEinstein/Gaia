# Reasoning Claims, Warrants, and Back-References

**Status:** Design proposal for v0.5 follow-up
**Date:** 2026-05-15
**Branch:** off `v0.5`
**Related PRs:** #606
**Refines:**
`docs/specs/2026-05-15-gaia-graph-scaffold-reasoning-design.md` and
`docs/specs/2026-05-15-causal-cleanup-reasoning-shapes.md`
**Scope:** Minimal contract for `Reasoning.warrants`, verb return values,
helper claims, and `Claim.from_actions`.
**Non-goals:** No public DSL return-value migration, no BP lowering redesign,
no persistent IR schema redesign, and no new graph engine.

## 1. Why This Needs a Spec

The current runtime model mixes three different ideas:

- the reasoning record itself;
- the claim or helper claim that a verb returns;
- the warrant claims used to review whether the reasoning step is acceptable.

That overload makes some flows hard to explain. A relation helper claim can be
the output of an action, the review target for that action, and the warrant of
that same action. In Bayes helpers, the helper claim also points back to the
action through `from_actions`, creating this loop:

```text
helper Claim
  from_actions -> Reasoning
Reasoning
  warrants -> same helper Claim
```

This is not a useful semantic distinction. The helper is the thing the
reasoning record attaches to; it should not also be the warrant that justifies
the same reasoning record.

The smallest cleanup is to separate the roles:

- `Reasoning` is the formal graph record.
- verb return values are ergonomic claim handles.
- `Claim.from_actions` is only a reverse index from a claim handle to the
  reasoning records attached to it.
- `Reasoning.warrants` contains only separate reviewable claims that justify
  the reasoning record.

## 2. Current Code Facts

Current code uses the following shapes:

| Surface | Current behavior |
|---|---|
| `Action.warrants` | Every runtime action inherits `warrants: list[Claim]`. |
| `Claim.from_actions` | Every claim can store runtime actions in `from_actions`. |
| `derive`, `observe`, `compute` | Return the conclusion claim, create a separate implication warrant, and append the action to `conclusion.from_actions`. |
| `infer` | Returns the evidence claim, creates a likelihood helper, stores that helper in `action.warrants`, and appends the action to `evidence.from_actions`. |
| `equal`, `contradict`, `exclusive` | Return a relation helper claim and store the same helper in `action.warrants`, but do not append the action to `helper.from_actions`. |
| `associate` | Returns an association helper claim and stores the same helper in `action.warrants`, but does not append the action to `helper.from_actions`. |
| `bayes.model`, `bayes.likelihood` | Return helper claims, store those same helpers in `action.warrants`, and append the actions to `helper.from_actions`. |
| `depends_on` | Currently appends scaffold to `conclusion.from_actions`; the GaiaGraph scaffold spec changes this to return scaffold records instead. |

The active field name is `Claim.from_actions`, both in the current branch and
in `origin/v0.5`. This spec intentionally keeps that name for the first
migration. A separate future cleanup may rename it to something clearer, but
that is not part of this design.

Those facts show two inconsistencies:

1. relation helpers are returned but cannot be resolved back to their producing
   action through `from_actions`;
2. several helper claims are both the primary attachment claim and the warrant
   of the same action.

## 3. Target Mental Model

The target model is:

```text
Reasoning
  primary claim/helper -> Claim
  warrants -> separate Claim(s)

Claim
  from_actions -> Reasoning record(s) attached to this claim
```

The rules are:

1. A `Reasoning` record is the identity of a reasoning step.
2. A returned claim is a convenient handle, not the identity of the reasoning
   step.
3. `Claim.from_actions` is a reverse index. It does not mean the claim
   contains the reasoning action.
4. `Reasoning.warrants` contains claims that justify the reasoning step.
5. The same claim object should not be both the primary attached claim and a
   warrant of the same reasoning record.
6. Scaffold records are not reasoning and should not be placed in
   `Claim.from_actions`.

This gives `materialize(scaffold, by=returned_claim)` a clean lookup rule:
if the returned claim has exactly one attached reasoning record in
`from_actions` for which the claim is the primary attachment, Gaia can use it;
if it has none or more than one, the author must pass a label. Records where
the claim appears only as an input, `given`, relation operand, decomposition
part, background, or warrant are consumers, not producers.

## 4. Primary Attachment Rules

`from_actions` should be written only on the primary claim or helper attached
to the reasoning record.

| Reasoning shape | Verb | Returned value | Primary attachment | Warrant rule |
|---|---|---|---|---|
| `Directed` | `derive` | conclusion claim | `conclusion.from_actions += action` | generated implication warrant, separate from conclusion |
| `Directed` | `observe` | observation/conclusion claim | `conclusion.from_actions += action` | generated implication warrant, separate from conclusion |
| `Directed` | `compute` | computed conclusion claim | `conclusion.from_actions += action` | generated implication warrant, separate from conclusion |
| `Directed` | `infer` | evidence claim | `evidence.from_actions += action` | likelihood helper can remain a warrant because it is not the primary attached claim |
| `Relation` | `equal` | equivalence helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| `Relation` | `contradict` | contradiction helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| `Relation` | `exclusive` | exclusivity helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| `Relation` | `associate` | association helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| `Decompose` | `decompose` | whole claim | `whole.from_actions += action` | no generated runtime self-warrant |
| `Compose` | `compose` | function result claim | `result.from_actions += action` | explicit compose warrants only |
| Bayes record | `bayes.model` | predictive-model helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| Bayes record | `bayes.likelihood` | likelihood helper claim | `helper.from_actions += action` | no self-warrant; use only separate warrants if needed |
| Scaffold | `depends_on` | scaffold record | no claim `from_actions` write | scaffold has no warrants |
| Scaffold | `candidate_relation` | scaffold record | no claim `from_actions` write | scaffold has no warrants |

There is no core `Predict` row because the active tree does not have a core
`Predict` runtime class or public `predict(...)` verb, and this spec does not
add one.

The phrase "primary attachment" is deliberately weaker than "produced claim."
For example, `infer` attaches to the evidence claim because that is the current
strategy conclusion in lowering; Gaia is not claiming that the evidence was
created by inference.

## 5. Warrant Rules

`warrants` should mean: "claims that a reviewer may inspect to decide whether
this reasoning record is acceptable."

Allowed warrant shapes:

- generated implication warrant claims for `derive`, `observe`, and `compute`;
- the likelihood helper for `infer`, because the primary attachment is the
  evidence claim, not the helper;
- explicit compose warrants supplied by the author;
- future author-provided warrant claims that are separate from the primary
  attached claim.

Forbidden warrant shape:

```text
claim in action.warrants and claim is primary_attachment(action)
```

That rule removes the confusing self-loop without removing reviewability. A
relation helper can still be reviewed as the primary helper of a relation
reasoning record; it just should not also appear as the warrant of that same
record.

## 6. Compiler and Review Consequences

The compiler should treat action identity, primary attachment, and warrants as
separate channels.

For each lowered reasoning record:

1. assign or resolve the `action_label`;
2. lower the reasoning record to the existing strategy/operator/compose shape;
3. identify the primary attached claim/helper, if any;
4. identify separate warrant claims, excluding the primary attachment;
5. write `metadata["warrants"]` only for those separate warrant claims;
6. attach `action_label` and `pattern` metadata to the primary attached claim
   and to each separate warrant claim when those claims are reviewable.

In the current compiler, `_prepare_action_warrants(...)` both projects
`action.warrants` into IR `metadata["warrants"]` and attaches
`action_label`/`pattern` metadata to those warrant claims. That remains useful
for separate warrants. The cleanup needs a sibling path for primary helper
claims, because relation helpers and Bayes helpers should be reviewable as the
primary attachment, not by being listed as their own warrant.

The first migration can keep the existing IR target shapes:

- support-like records still lower to strategies;
- relation records still lower to operators or association strategies;
- `infer` still lowers to the existing likelihood strategy;
- Bayes records still lower through the Bayes compiler;
- compose records still lower to `IrCompose`.

Only the meaning of runtime `warrants` and `from_actions` changes.

## 7. Minimal Migration Plan

Runtime:

- Rename the public base from `Action` to `Reasoning` as described in the
  reasoning-shape spec.
- Keep `Claim.from_actions` as the reverse index field, but document it as
  `list[Reasoning]`.
- Add a small internal helper for idempotent attachment:

```python
def attach_reasoning(claim: Claim, reasoning: Reasoning) -> None:
    if all(existing is not reasoning for existing in claim.from_actions):
        claim.from_actions.append(reasoning)
```

- Add a validation helper that rejects self-warrants:

```python
def validate_no_self_warrant(reasoning: Reasoning, primary: Claim) -> None:
    if any(warrant is primary for warrant in reasoning.warrants):
        raise ValueError("reasoning primary claim/helper must not also be its warrant")
```

DSL:

- Keep `derive`, `observe`, `compute`, and `infer` return values unchanged.
- Update `equal`, `contradict`, `exclusive`, and `associate` so the returned
  helper gets `helper.from_actions.append(action)`.
- Stop appending the returned relation/association helper to
  `action.warrants`.
- Keep `decompose` return value unchanged, with `whole.from_actions` as the
  primary attachment.
- Update `compose` so the returned result claim gets the compose reasoning
  record in `result.from_actions`.
- Update scaffold verbs according to the GaiaGraph scaffold spec: return
  scaffold records and do not append scaffold to claim `from_actions`.
- Do not change compose input/output inference accidentally. In particular,
  adding `helper.from_actions` for relation helpers should not make helper
  claims appear as external compose inputs when `_action_outputs(...)` already
  treats them as outputs of relation actions.

Bayes:

- Keep `bayes.model` and `bayes.likelihood` return values unchanged.
- Keep their helper `from_actions` links, because Bayes lowering already uses
  them to recover predictive-model actions.
- Remove the returned helper from `action.warrants` unless there is a separate
  warrant claim.

Compiler and review:

- Keep existing lowering outputs.
- Ensure action labels are attached to primary helper claims as review targets.
- Ensure `metadata["warrants"]` contains only separate warrant claim IDs.
- Update review-manifest generation if it currently assumes every reviewable
  helper must appear in `metadata["warrants"]`.
- Keep Bayes lowering keyed from helper `from_actions`, because
  `bayes.likelihood(...)` already recovers `PredictiveModel` actions that way.

## 8. Tests

Minimum tests for the migration:

- `derive(...)` returns the conclusion, appends `Derive` to
  `conclusion.from_actions`, and keeps a separate implication warrant.
- `observe(...)` and `compute(...)` follow the same pattern.
- `infer(...)` returns evidence, appends `Infer` to `evidence.from_actions`,
  and keeps its likelihood helper as a separate warrant.
- `equal(...)`, `contradict(...)`, `exclusive(...)`, and `associate(...)`
  return helper claims whose `from_actions` contain the relation reasoning
  record.
- Relation and association helpers are not present in their own
  `action.warrants`.
- `bayes.model(...)` and `bayes.likelihood(...)` return helper claims whose
  `from_actions` contain the Bayes reasoning record.
- Bayes helper claims are not present in their own `action.warrants`.
- `decompose(...)` still rejects duplicate decomposition through
  `whole.from_actions`.
- `compose(...)` appends the compose reasoning record to the returned result
  claim.
- Relation helper `from_actions` links do not change inferred compose inputs or
  bloat `Compose.actions`.
- `depends_on(...)` and `candidate_relation(...)` return scaffold records and
  do not write to claim `from_actions`.
- `materialize(scaffold, by=returned_helper)` can resolve a relation helper
  with exactly one `from_actions` producer.
- `materialize(scaffold, by=returned_helper)` asks for a label when the helper
  has zero or multiple attached reasoning records.
- `gaia check` and `gaia inquiry` review-manifest counts remain stable after
  removing relation/Bayes self-warrants, except for the intentional difference
  between primary helper review targets and separate warrants.

## 9. Deferred Work

The following are compatible with this cleanup but intentionally out of scope:

- changing all verbs to return reasoning records;
- replacing `Claim.from_actions` with a persistent graph-edge table;
- changing `infer` to return a likelihood helper instead of evidence;
- redesigning the review manifest;
- adding a new produced-by relation type distinct from `from_actions`.
- renaming `Claim.from_actions` to a clearer reverse-index name such as
  `attached_reasoning`.

Those changes may become useful later, but the first cleanup only needs one
invariant: a claim can be the primary attachment of a reasoning record, or a
warrant for it, but not both at the same time.
