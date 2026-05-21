# Step 3 — Screen Contradictions And Open Questions

Load this file only after Step 2 is complete. This step is mandatory for every
new claim. In root-claim frontier expansion it is also the mapping-time
open-question/conflict channel for each frontier claim being expanded.

## Canonical Policy

Read `mapping-contract.md` §4 before making any contradiction decision. If this
file and the mapping contract disagree, the mapping contract wins.

`mapping-contract.md` §4 is the sole authority for contradiction semantics. In
this step, prioritize open-question discovery, then run a final scan that either
emits direct `contradict(A, B)` for accepted scientific contradictions or
keeps the item as hypothesis/audit-only.

## Baseline Sources To Check

Check every new claim against:

- other new claims in the current batch,
- existing package claims,
- upstream/support claims found while resolving obligations,
- `.gaia/ir.json` when available for internal tensions.

Do not skip a claim because it looks obvious, narrow, or already accepted.

Focused LKM retrieval is allowed when needed to classify a current candidate
pair, verify scope/provenance for a claim already being mapped, or run the
claim-driven conflict channel. Do not use external PDFs or web
summaries as evidence unless the user explicitly changes the rule.

For root-claim frontier expansion, each frontier claim must run at least 5
distinct LKM conflict queries (`gaia search lkm knowledge "<query>" --limit 10`,
or `gaia search lkm reasoning "<query>" --limit 10` for reasoning-chain
recall) for this conflict channel.

Priority order for conflict queries:

1. Theory-vs-experiment or experiment-vs-theory. For a theoretical/computational
   frontier claim, first search for experimental observations or measurements
   that disagree with, qualify, or fail to confirm it. For an experimental
   frontier claim, first search for theoretical/computational results that
   disagree with or reinterpret it.
2. Computation-vs-experiment or measurement-vs-model comparisons not covered by
   the first category.
3. Same-system different-method conflicts.
4. Approximation, boundary-condition, regime, dimensionality, temperature,
   disorder, sample-quality, or protocol conflicts.
5. Broader adjacent tensions that may become useful hypotheses but are not yet
   promotable.

## Baseline Candidate Tracking

Track every candidate pair in the agent's scratch only — frontier-claim and
candidate identifiers, scope-tuple comparison across system/material,
quantity, method/model, conditions, and regime, the open problem or
discriminating question raised by the pair, the verdict
(`accepted_contradiction`, `hypothesis_only`, `dismissed`, or
`needs_more_evidence`), the rationale, and the next action. Verdicts that
produce a Gaia operator manifest in the emitted source; hypothesis-only
verdicts manifest as `gaia inquiry hypothesis add` calls (see below);
dismissed and needs-more-evidence verdicts produce no on-disk artifact in the
post-purge SOP.

## Open-Question-First Review

For every plausible tension, ask the model to name the best field-facing open
problem before deciding whether to emit an operator. Register useful open
problems even when the pair is not yet a Gaia contradiction:

```bash
gaia inquiry hypothesis add "<open problem>" --scope <namespace>::<label>
```

Do not wait for perfect contradiction certainty before recording the hypothesis;
the hypothesis is how later refreshes remember what to test.

## Accepted Contradiction Output

For each final-scan `accepted_contradiction`, emit direct
`contradict(A, B)` using the `xx_vs_yy` label policy in
`mapping-contract.md` §4:

```python
<side_a>_vs_<side_b>[_<quantity_or_regime>] = contradict(
    A,
    B,
    rationale="<why A and B are an adjudicable scientific conflict> | open_problem: <specific discriminating question>",
    label="<side_a>_vs_<side_b>[_<quantity_or_regime>]",
)
```

The engine `contradict(...)` signature accepts only
`{background, rationale, label}` — no `metadata=` / `warrant_prior` /
`prior=` kwarg. Warrant-strength intent lives in the `rationale=` prose
alongside the `open_problem:` clause.

The `rationale` field must include `open_problem:`. If no specific open
problem can be written, the candidate is not ready for
`accepted_contradiction`; keep it as `hypothesis_only`.

Register the same open problem:

```bash
gaia inquiry hypothesis add "<open problem>" --scope <namespace>::<op_label>
```

Warrant-strength intent for accepted contradiction operators (encode
qualitatively in `rationale=` prose; the engine has no numerical warrant
surface on `contradict`):

- Clear accepted contradiction: say "clear accepted contradiction".
- Accepted but less crisp scope/test relation: say so explicitly.
- Do not downgrade the rationale solely because the pair is method/method,
  theory/computation, or finite-size/extrapolation mediated.

## Hypothesis-Only Output

For tensions that raise useful open problems but do not yet satisfy
`mapping-contract.md` §4's final promotion standard:

- write no Gaia `contradict(...)` operator,
- add an inquiry hypothesis scoped to the most relevant claim — the
  hypothesis text is how the package remembers the open problem.

Dismiss false alarms, duplicate wording, and unsupported search leads silently
within the run.

## Step-Completion Gate

Before moving to Step 4:

- Every new claim has completed baseline screening against available package
  context.
- Root-claim frontier claims have completed the required conflict-channel
  search or surfaced a `conflict_not_found` note in the hand-off report.
- Accepted contradictions have direct `contradict(A, B)` operators whose
  labels identify both sides with the `xx_vs_yy` convention, with an
  `open_problem:` rationale and warrant-strength intent encoded in the
  rationale prose (no `metadata=` kwarg on `contradict`).
- Non-promoted but useful tensions are registered as inquiry hypotheses.
- Mark Step 3 complete, mark Step 4 in progress, then load
  `step-4-supports-priors-and-review.md`.
