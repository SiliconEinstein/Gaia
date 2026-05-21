# LKM-Explorer-Specific Contract

> Generic Gaia knowledge package emission rules — `claim` / `derive` /
> `contradict` / `equal` / `exclusive` body discipline and package
> layout — are the canonical Gaia spec (see
> `docs/for-users/language-reference.md` and
> `docs/for-users/quick-start.md`). This file covers ONLY rules specific
> to contradiction-driven LKM exploration: the LKM evidence-status vocabulary,
> no-chain source-claim handling, root-claim frontier supports, the
> open-question-first contradiction policy, and the timeline emission
> requirement for LKM-driven package work.

## 0. Evidence-status vocabulary

- **Chain-backed claim**: LKM returned claim content and
  `gaia search lkm reasoning --claim-id <id>` reports `total_chains > 0`. Emit
  `claim(...)` plus factor-derived `derive(...)` when factors are present.
- **LKM source claim**: LKM returned claim content and provenance, but `total_chains = 0`. After cold start, emit it as a leaf/source `claim(...)`; do not invent premises or deductions.
- **Search lead**: insufficient content or provenance for a self-contained claim outside an accepted chain-backed factor. Keep only in audit/search notes.

`total_chains > 0` is required for cold-start root selection. It is not a global admissibility rule for post-cold-start frontier expansion or conflict-channel candidates.

## 1. LKM-specific claim handling

Generic `claim(...)` body rules — label discipline, self-contained check, no
`prior` kwarg — are the canonical Gaia spec (see
`docs/for-users/language-reference.md`). The rules below are LKM-specific.

- **No-chain LKM source claims.** If `total_chains = 0`, use
  `provenance_source="lkm_no_chain"` and preserve `lkm_id` when available.
  Do not create `derive(...)` without factors.
- **Prior policy for no-chain candidates.** Do not lower a prior solely because
  `total_chains=0`. Set priors from claim content, provenance clarity,
  method/scope specificity, and scientific judgment.
- **Chain-internal empty-content premises.** When an LKM evidence chain
  references a premise whose `content` is empty, a placeholder string plus
  `todo="revisit when LKM corpus populates this premise"` in metadata may be
  used to preserve a factor-derived `derive(...)`. Do not invent content.
- **Empty or under-provenanced match/search results outside an accepted
  chain** are **search leads**, not placeholder claims. Do not emit them.

## 3. Root-claim frontier supports

During root-claim frontier expansion, the agent searches LKM for content that
can directly support each frontier claim. A single target claim may have
**multiple** accepted upstream supports. Use the canonical v0.5 deterministic
warrant primitive (the legacy named-strategy `support(...)` is replaced by
`derive(...)` — see `docs/for-users/language-reference.md`):

```python
derive(target, given=[U_1], rationale="<what U_1 says and why it supports target>",
       label="<u1_supports_target>")
derive(target, given=[U_2], rationale="<what U_2 says and why it supports target>",
       label="<u2_supports_target>")
```

When several upstream claims only support the target jointly, use one joint
derivation:

```python
derive(target, given=[U_1, U_2], rationale="<joint support rationale>",
       label="<u1_u2_supports_target>")
```

`derive(target, given=[a], rationale=...)` is directional: `a` supports
`target`. In Gaia v0.5 the engine `derive(...)` signature accepts only
`{given, background, rationale, label}` — there is no `metadata=` /
`warrant_prior` kwarg. Warrant-strength intent (legacy strong/moderate/weak
bands) lives in the `rationale=` prose so the reviewer's intent is
preserved in the source without breaking `gaia build check`.

Search effort for each frontier target:
- Run at least 2 distinct support-channel LKM queries
  (`gaia search lkm knowledge` / `gaia search lkm reasoning`).
- Use `--limit 10` for each query.
- Preserve raw match/evidence payloads.
- If no candidate satisfies the support standard, record the queries and
  rejection rationales as `support_not_found`; do not invent support.

Warrant-strength intent (encode qualitatively in `rationale=` prose; the
engine has no numerical warrant-prior surface on `derive`):
- Strong (same topic, directly implies) — say so in the rationale.
- Moderate (related, partially overlaps) — say so in the rationale.
- Weak/lateral — say so in the rationale, and explicitly note the gap.

The support relation itself may be a reviewer/agent scientific judgment rather
than an LKM `gfac_*` factor, but both endpoints must already be LKM-grounded
Gaia claims.

> Warrant rationale discipline (no smuggling; on-the-fly premise claims are
> normal): see `docs/for-users/language-reference.md` (`derive` semantics; the
> legacy `support` strategy semantics on the compat surface inform the same
> discipline).

For cross-scope supports (different geometry, material, temperature, extraction
method, approximation, or mass definition), explicitly downgrade the warrant
intent in the `rationale=` text (e.g. "lateral support: scope differs in
<axis>, treat as weak evidence") unless the LKM-grounded claim text directly
implies the target. Reflect the scope difference in the rationale so the
reviewer reading the source can see the gap; the engine `derive` surface has
no numerical knob to lower.

Support candidates may be chain-backed or no-chain LKM source claims after cold
start. Chain-backed candidates may add their own `claim(...)` nodes and
factor-derived `derive(...)` strategies. No-chain candidates may enter only
as leaf/source `claim(...)` nodes with clear content and provenance.

### 3a. Shared-factor extraction (>=2 supports converging on same target)

When >=2 upstream supports converge on the same target claim P, check whether the upstream claims share a common factor (same method, model assumption, dataset, physical approximation). If they do, BP would incorrectly treat them as independent evidence. Extract the shared factor as a new claim and route supports through it:

```
Before:  U1 --support-->  P
         U2 --support-->  P      <- double counting

After:   U1 --support-->  shared_factor  <--support-- U2
                                 |
                              support
                                 |
                                 v
                                 P
```

Judge the shared factor's prior normally (cap 0.9).

## 4. Open-question-first contradiction handling

This section is the canonical policy for contradiction handling in the local
LKM-explorer workflow.

The workflow prioritizes open questions during discovery and mapping. When two
source claims `A` and `B` appear to be in tension, first name the scientific
open problem they raise. When the problem may drive later work, register it
under `.gaia/inquiry/` as a hypothesis via `gaia inquiry hypothesis add`.

During root-claim frontier expansion, run an open-question/conflict channel for every
frontier claim. Minimum effort is 5 distinct LKM queries with `--limit 10`.
Prioritize theory-vs-experiment or experiment-vs-theory candidates first: if the
frontier claim is theoretical/computational, look first for experimental
observations or measurements that disagree with or qualify it; if the frontier
claim is experimental, look first for theoretical/computational results that
disagree with or reinterpret it. Then search same-system different-method,
boundary-condition, approximation/regime, and adjacent hypothesis candidates.
If no candidate satisfies the hypothesis or contradiction standard, record the
queries and rejection rationales as `conflict_not_found`.

At the final contradiction scan, promote a candidate to executable Gaia DSL when
it is a scientifically meaningful, adjudicable conflict: the pair concerns the
same scientific object/question closely enough that resolving the open problem
would confirm, falsify, or materially qualify at least one side of `A`/`B`.
This admission standard is intentionally broader than strict logical identity
of scope. Differences in method, finite-size treatment, extrapolation protocol,
approximation domain, or benchmark regime do not by themselves block promotion
when the field-facing question is genuinely the same.

Accepted scientific contradictions use the direct operator. Name the operator
after the two sides so graph views and review output make the conflict visible
without opening metadata:

```python
<side_a>_vs_<side_b>[_<quantity_or_regime>] = contradict(
    A,
    B,
    rationale="<why these claims are adjudicably conflicting> | open_problem: <specific discriminating question>",
    label="<side_a>_vs_<side_b>[_<quantity_or_regime>]",
)
```

The engine `contradict(...)` signature accepts only
`{background, rationale, label}` — no `metadata=` / `warrant_prior` /
`prior=` kwarg. Warrant-strength intent (legacy "clear / less crisp"
bands) lives in the `rationale=` prose alongside the `open_problem:`
clause.

Label rules:
- Prefer `<side_a>_vs_<side_b>` with short semantic side names, e.g.
  `dmc_vs_gw_mass_enhancement`.
- Add a quantity/regime suffix when needed to disambiguate, e.g.
  `low_density_dmc_vs_gw_mass_enhancement`.
- Keep the label a valid Gaia/Python identifier: lowercase letters, digits, and
  underscores only.
- Do not name the node `scientific_inconsistency_*`, `paradox_*`, or a generic
  `contradict_*`; the operator kind already supplies the relation semantics,
  while the label should identify the two conflicting sides.

Warrant-strength intent on a `contradict(...)` is the conviction that this
pair should be treated as an adjudicable scientific contradiction, not a
prior on either claim being true. Encode in the rationale: say "clear
accepted contradiction" for the strongest cases; say "accepted but scope
match / discriminating question is less crisp" when the candidate is
borderline. Do not weaken the rationale merely because the candidate came
from different methods; method/method conflicts are often the point of the
contradiction.

Avoid the word `paradox` in operator labels; it may be used only in synthesis
prose when appropriate for the field.

### Promotion signals

Promote a candidate to `contradict(A, B)` when one or more of these apply:

- The claims assert opposite values, signs, orderings, trends, or qualitative
  conclusions about the same system/material, quantity/effect, or scientific
  mechanism.
- The claims use different methods or approximations but are commonly read as
  answering the same field-facing question.
- The disagreement can be tested by a concrete calculation, measurement,
  benchmark, extrapolation, or reanalysis.
- Resolving that test would make at least one claim, interpretation, or
  unqualified conclusion untenable or materially qualified.

For example, the low-density 2D homogeneous-electron-gas effective-mass tension
where treatments can put `m*/m` on opposite sides of unity is admissible as an
accepted contradiction: the open problem is whether the sign and magnitude of
the mass renormalization survive matched treatment of correlation,
finite-size/extrapolation, and approximation regime.

### Hypothesis-only tensions

Keep a candidate as audit/hypothesis-only when the pair is interesting but not
yet promotable:

- the open problem is still vague or not discriminating,
- the scope relation is unknown because content/provenance is insufficient,
- the claims address adjacent but not adjudicably conflicting questions,
- the candidate is a model-applicability gap, coverage gap, or benchmark
  omission without a concrete test,
- the candidate is a false alarm, duplicate wording, or unsupported search lead.

For hypothesis-only rows, record why the pair is scientifically interesting,
the best current open problem, why no `contradict(...)` operator was emitted,
and what query or evidence would be needed to promote it later. In the
post-purge SOP these notes live in the agent's scratch and the
`gaia inquiry hypothesis add` text, not in a dedicated audit file.

## 9. What this contract does NOT cover

- Generic claim/derive/contradict/equal/exclusive emission rules,
  label discipline, and module placement — the canonical Gaia spec
  (`docs/for-users/language-reference.md`).
- Package layout and templates (`pyproject.toml`, `__init__.py`,
  `paper_<key>.py`, `references.json`) — the canonical Gaia spec
  (`docs/for-users/quick-start.md`).
- Generic `lkm_id` / `provenance_source` metadata semantics on Gaia
  statements — the canonical Gaia spec.
- The shape of `pyproject.toml` — follow current package examples and verify
  with `gaia build compile`.
- BP interpretation and weakness analysis — handled by caller/user review after
  `gaia run infer` (see `../_shared/bp-interpretation.md`).
- Render-time choices — use `gaia run render` or package-specific
  render commands after compilation/inference (see
  `docs/for-users/cli-commands.md`).
- The Gaia DSL grammar — governed by the installed Gaia library; see
  `docs/for-users/language-reference.md`.
