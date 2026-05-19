# Role-on-Action-Graph Design

**Status:** Implemented design (initial v0.5 surface)
**Branch:** `codex/v05-role-decompose-design` (v0.5 line)
**Date:** 2026-05-05

## 1. Scope

This spec designs the smallest v0.5 contract for asking:

> Given a `Claim`, what roles does it play in the authored action graph?

It intentionally does **not** add a `role` field to `Claim`. A claim can be a
hypothesis in one action, evidence in another, a conclusion in a third action,
and a warrant or background item elsewhere. Role is therefore a property of a
claim occurrence inside an action context, not a property of the claim itself.

The first consumer is prior assignment: independent probabilistic inputs should
get priors; derived, helper, and structural claims should not. This spec only
provides the role facts that a prior policy can consume. It does not prescribe
numeric priors.

## 2. First-Principles Model

The runtime already has the needed graph:

- `Action` is parallel to `Knowledge`, not a `Knowledge` subclass.
- Action subclasses expose typed fields such as `hypothesis`, `evidence`,
  `conclusion`, `given`, `helper`, `a`, `b`, `inputs`, and `actions`.
- The compiler already tracks action labels and object-to-IR mappings.

The public action hierarchy should stay shallow where an intermediate class does
not add semantics. `Support`, `Structural`, `Probabilistic`, and `Scaffold`
carry useful conceptual boundaries: directional establishment, hard structural
constraints, soft probabilistic factors, and workflow bookkeeping. `Relate` is
different: it mostly exists to share `a` / `b` / `helper` fields, so it should
not be a public semantic layer. `Equal`, `Contradict`, `Exclusive`, and
`Decompose` should live under `Structural` and share small lowering helpers
without sharing a field-only inheritance layer.

Use `Probabilistic`, not `SoftEvidence`, for the soft-factor layer. `Infer`
contains an evidence claim, but the action itself is a likelihood factor between
hypothesis, evidence, and optional conditions; `Associate` is a symmetric soft
relation and is not evidence at all. `SoftEvidence` is therefore too narrow and
risks colliding with the technical meaning of soft/virtual evidence in
probabilistic graphical models.

Recommended public shape:

```text
Action
|-- Support
|   |-- Derive
|   |-- Observe
|   `-- Compute
|-- Structural
|   |-- Equal
|   |-- Contradict
|   |-- Exclusive
|   `-- Decompose
|-- Probabilistic
|   |-- Infer
|   `-- Associate
|-- Scaffold
|   `-- DependsOn
`-- Compose
```

So the minimal design is a pure projection over runtime actions:

```python
@dataclass(frozen=True)
class RoleOccurrence:
    claim: Claim
    role: str
    action: Action
    action_type: str
    action_label: str | None = None
    path: tuple[str, ...] = ()
    source: str = "explicit_field"


def roles_for_claim(
    claim: Claim,
    graph: CollectedPackage | Sequence[Action],
    *,
    include_background: bool = True,
    include_warrants: bool = True,
) -> tuple[RoleOccurrence, ...]:
    ...
```

`roles_for_claim` returns occurrences, not just role strings, because downstream
tools need to know **where** the role came from. For example, `evidence` in an
`Infer` action and `conclusion` in an `Observe` action should usually outrank a
background citation when choosing prior targets.

A package-level index is a convenience wrapper over the same projection:

```python
def roles_for_package(
    graph: CollectedPackage | Sequence[Action],
    *,
    include_background: bool = True,
    include_warrants: bool = True,
) -> dict[Claim, tuple[RoleOccurrence, ...]]:
    ...
```

The API can use identity internally (`id(claim)`) and expose `Claim` objects in
memory. If a persisted index is later needed, entries should serialize claim IDs
and action labels, not Python object identities.

## 3. Role Projection Table

Every action contributes role occurrences from its public fields:

Implementation must match the most specific action class first. If compatibility
base classes such as `Support` remain internally, `Observe` and `Compute` still
need `observation` and `computed_result` roles, not the generic `conclusion`
role.

| Action | Field | Role |
|---|---|---|
| `Derive` | `conclusion` | `conclusion` |
| `Derive` | `given` | `premise` |
| `Observe` | `conclusion` | `observation` |
| `Observe` | `given` | `observation_context` |
| `Compute` | `conclusion` | `computed_result` |
| `Compute` | `given` | `compute_input` |
| `DependsOn` | `conclusion` | `dependency_target` |
| `DependsOn` | `given` | `unformalized_dependency` |
| `Infer` | `hypothesis` | `hypothesis` |
| `Infer` | `evidence` | `evidence` |
| `Infer` | `given` | `condition` |
| `Infer` | `helper` | `likelihood_helper` |
| `Infer` | `p_e_given_h` if `Claim` | `likelihood_parameter` |
| `Infer` | `p_e_given_not_h` if `Claim` | `likelihood_parameter` |
| `Associate` | `a`, `b` | `association_target` |
| `Associate` | `helper` | `association_helper` |
| `Equal` | `a`, `b` | `equivalent_claim` |
| `Equal` | `helper` | `equivalence_helper` |
| `Contradict` | `a`, `b` | `contradiction_target` |
| `Contradict` | `helper` | `contradiction_helper` |
| `Exclusive` | `a`, `b` | `exclusive_alternative` |
| `Exclusive` | `helper` | `exclusivity_helper` |
| `Decompose` | `whole` | `decomposition_whole` |
| `Decompose` | `parts` | `decomposition_part` |
| `Compose` | `inputs` if `Claim` | `composition_input` |
| `Compose` | `conclusion` | `composition_conclusion` |
| `Action` base | `background` if `Claim` | `background` |
| `Action` base | `warrants` | `warrant` |

Generated decomposition helpers are compile-artifact roles, not authored-action
roles. `roles_for_claim` returns only occurrences in runtime actions, so it
reports `decomposition_whole` and `decomposition_part` for `Decompose`. The
generated formula helper and generated equivalence helper do not exist as
authored `Claim` objects; compiled IR carries their roles through
`metadata.helper_kind = "decomposition_formula"` and
`metadata.helper_kind = "decomposition_equivalence"`.

`Compose.actions` should be traversed recursively when it contains action
objects. Occurrences inside a composition get a `path` containing the enclosing
composition labels or stable child positions. This lets tools distinguish a
top-level role from a role inherited through a composed reviewable DAG.

The table is deliberately descriptive. It does not imply that all roles should
be persisted or exposed as user-facing vocabulary.

## 4. Prior Policy Boundary

The role query is a fact extractor. A separate policy decides what receives a
prior. A reasonable default policy is:

| Priority | Role evidence | Default prior behavior |
|---|---|---|
| 1 | `observation`, `evidence` | Independent prior candidate |
| 2 | `likelihood_parameter`, externally asserted parameter/binding claim | Independent prior candidate |
| 3 | `hypothesis`, `association_target`, `equivalent_claim`, `contradiction_target`, `exclusive_alternative`, `decomposition_part` | Independent prior candidate when not generated or derived |
| 4 | `background`, `warrant`, `premise`, `condition` | Optional prior candidate; policy-specific |
| 5 | `*_helper`, `decomposition_whole`, generated structural operands, `composition_conclusion` | Not an independent prior by default |

Two points matter:

1. Role projection must preserve multiple roles. If a claim is both an
   observation and a conclusion, the prior policy can see both.
2. Structural claims should be classified by occurrence metadata as well as
   role. A generated formula helper from `decompose` is a helper even though it
   can appear as an `equivalent_claim` in an `Equal` action.
3. Relation operands such as the two sides of a user-authored `Equal` action may
   still be independent DOFs. The role alone is not enough to suppress priors;
   generated/residual metadata and exported-goal boundary analysis decide that.

## 5. Lowering and Persistence

No IR schema change is required for v0.5. The canonical source of role truth is
the authored action graph.

The compiler may optionally emit role metadata for audit/debugging, for example:

```python
strategy.metadata["action_roles"] = [
    {"claim_id": "...", "role": "hypothesis", "action_label": "mendel_lr"}
]
```

That metadata is derivative. It must not become the only place roles exist,
because local tools can always recompute roles from the runtime actions before
lowering.

## 6. CLI Applications

The role API should improve existing CLI diagnostics, not create a new command.
Current v0.5 CLI classification is compiled-IR based (`independent`, `derived`,
`structural`, `background`, `orphaned`). Once `roles_for_claim` exists, the CLI
can use action-level role occurrences to explain those categories more
accurately.

| CLI surface | Use of role projection |
|---|---|
| `gaia check --hole` | Select independent degrees of freedom from action roles plus exported-goal boundary analysis. Keep generated helpers out of the MaxEnt/prior list. |
| `gaia check --brief` | Show the strongest occurrence role next to each claim, with multiple roles available in detail views. |
| `gaia check --show <label>` | Explain why a claim is treated as evidence, hypothesis, observation, helper, background, or derived by listing the relevant action occurrences. |
| `gaia inquiry` / quality gate | Treat role-aware independent DOFs as structural holes when required by package policy; do not block on generated helpers. |
| `gaia infer` | No new flag. Inference still reads priors from compiled metadata, but preflight diagnostics may warn when priors are attached to structural/helper roles or missing from selected independent inputs. |
| `gaia render` / Obsidian output | Render role labels from occurrences instead of only IR-level coarse classes when available. |

`gaia compile` may emit derivative `action_roles` metadata so compiled-only
commands can inspect roles without re-executing source. That metadata is an
optimization/debug aid; it should be generated from the same role projection
logic and should not define a second semantics.

No CLI documentation should advertise these role-aware outputs as current
behavior until the runtime API and regression tests land.

## 7. Validation and Tests

Minimum tests for implementation:

1. `Infer(hypothesis=H, evidence=E)` returns `hypothesis` for `H` and
   `evidence` for `E`.
2. `Observe(conclusion=E)` returns `observation` for `E`.
3. `Equal(a=C, b=F)` returns `equivalent_claim` for both sides and a helper role
   for `helper`.
4. A claim used in two actions returns two `RoleOccurrence` entries.
5. A `Compose` action preserves nested child roles with a non-empty path.
6. The default prior policy does not select generated helper claims as
   independent prior targets.
7. `gaia check --hole` uses role-aware classification when role metadata is
   present and falls back to the existing IR classifier for older artifacts.
8. `gaia check --show <label>` can print multiple occurrences for a claim that
   appears in more than one action.

## 8. Open Questions

1. The exact public role strings may be shortened after implementation proves
   which names are useful in diagnostics.
2. Persisted role indexes can wait until a review UI or registry workflow needs
   them.
3. Numeric prior ranking remains a policy layer, not part of this projection
   API.
