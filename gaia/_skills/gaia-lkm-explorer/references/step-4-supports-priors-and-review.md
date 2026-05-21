# Step 4 — Supports, Priors, Obligations, And Duplicate Controls

Load this file only after Step 3 is complete. This step prevents unsupported
leaves, double counting, and untracked weak premises.

## Upstream Support

For root-claim frontier expansion, every frontier claim receives a
support-channel LKM search. Search for upstream LKM-grounded conclusions
relevant to the target claim. A single target may have multiple upstream
supports; each can get its own directional `derive(...)` (canonical v0.5
replacement for the legacy `support(...)` strategy — see
`docs/for-users/language-reference.md`):

```python
derive(P, given=[U_1], rationale="<what U_1 says and why it supports P>",
       label="<u1_supports_p>")
derive(P, given=[U_2], rationale="<what U_2 says and why it supports P>",
       label="<u2_supports_p>")
```

When several upstream claims only support the target jointly, use a joint
derivation:

```python
derive(P, given=[U_1, U_2], rationale="<joint support rationale>",
       label="<u1_u2_supports_p>")
```

`derive(P, given=[a], rationale=...)` means `a` supports `P`. The engine
`derive(...)` signature accepts only `{given, background, rationale, label}` —
warrant-strength intent (strong / moderate / weak / lateral) lives in the
`rationale=` prose, not in a `metadata=` / `warrant_prior` kwarg (the CLI
flag exists but the post-write `gaia build check` rejects).

Minimum support-channel effort per frontier claim:

- run at least 2 distinct LKM queries (`gaia search lkm knowledge` /
  `gaia search lkm reasoning`),
- use `--limit 10` for each query,
- if no candidate satisfies the support standard, surface `support_not_found`
  in the hand-off report with query and rejection rationales.

Warrant-strength intent (encode qualitatively in `rationale=` prose; the
engine has no numerical warrant surface on `derive`):

- Strong, same topic and directly implies — say so in the rationale.
- Moderate, related and partially overlaps — say so in the rationale.
- Weak or lateral — say so in the rationale and name the gap (scope,
  method, regime).

The `derive(...)` warrant edge may be a scientific-review judgment rather
than an LKM factor, but both endpoint claims must already be LKM-grounded.

> Warrant rationale discipline (no smuggling; on-the-fly premise claims are
> normal): see `docs/for-users/language-reference.md` (`derive` semantics; the
> legacy `support` strategy semantics on the compat surface inform the same
> discipline).

For cross-scope supports involving different geometry, material, temperature,
experimental extraction method, approximation, or mass definition, explicitly
flag the support as weak/lateral in the `rationale=` text (e.g. "lateral
support: scope differs in <axis>; treat as weak evidence") unless the
LKM-grounded source claim directly implies the target.

If no relevant upstream conclusion is found, do not invent one.

## Shared-Factor Extraction

Run shared-premise extraction before operator emission and again whenever two or
more supports converge on the same premise.

Rules:

1. Auto-merge identical normalized claim text.
2. Auto-merge same paper / different version when DOI, title, or author-year
   metadata show they are the same result.
3. When multiple upstream supports share a common method, model assumption,
   dataset, physical approximation, or other non-independent factor, extract
   that factor as a new claim and route supports through it.
4. Keep distinct supports that are genuinely independent.
5. For ambiguous cases, default to keep distinct.

## Leaf Priors

After source emission, the caller quality gate runs `gaia build check --hole .`.
Each claim reported as a leaf gets a `register_prior(...)` record in
`priors.py`, emitted in Step 5 via `gaia author register-prior --file
priors.py` (one invocation per leaf):

```python
register_prior(
    <label>,
    value=<float>,
    justification="<heuristic tag + LKM context + TODO:review>",
)
```

Do **not** write a legacy `PRIORS = {...}` dict — `gaia build compile`
rejects it with a migration error (`gaia/engine/packaging.py`) because the
dict form carries no per-source provenance. `register_prior(...)` is the
only v0.5 prior surface.

The float is a direct judgment of correctness, not LKM match score. Cap source
claim priors at 0.90. Do not lower a prior solely because the claim has
`total_chains=0`; judge content, provenance clarity, method/scope specificity,
and scientific plausibility.

Accepted `contradict(...)` operators from Step 3 carry their warrant-strength
intent in the `rationale=` prose (the engine has no `metadata=` /
`warrant_prior` kwarg on `contradict`); that intent is not a leaf-claim
prior and is not mirrored into `priors.py`.

## Inquiry Obligations

Mark unreliable reasoning chains or weak premises:

```bash
gaia inquiry obligation add <claim_or_strategy_qid> -c "<concern>"
```

Use `gaia inquiry obligation list` as the exploration TODO list. Do not
mechanically pick the lowest-belief claim; obligations carry intentional
exploration choices, while beliefs are diagnostics.

Register open-question hypotheses from Step 3 with:

```bash
gaia inquiry hypothesis add "<open question>" --scope <namespace>::<label>
```

## Duplicate Controls

For duplicate cleanup or refreshes, classify suspicious pairs:

- exact duplicate -> merge,
- same-paper helper restatement -> merge into canonical claim when safe,
- independent same proposition -> keep both and add `equal(...)`,
- different scope/material/method/condition -> keep distinct,
- ambiguous -> default to keep distinct.

Preserve merged-out labels' `lkm_id` provenance in the canonical claim via
`lkm_ids=[...]` when possible.

## Step-Completion Gate

Before moving to Step 5:

- Relevant upstream supports have been searched and mapped or explicitly not
  found.
- Root-claim frontier claims have completed the required support-channel
  search or surfaced `support_not_found` in the hand-off report.
- Shared-factor and duplicate decisions are resolved.
- Leaf-prior candidates are ready for `priors.py`.
- Inquiry obligations/hypotheses are registered.
- Mark Step 4 complete, mark Step 5 in progress, then load
  `step-5-emit-and-handoff.md`.
