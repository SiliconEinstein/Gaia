# Step 5 — Emit And Hand Off

Load this file only after Step 4 is complete. This step finalizes the source
artifact and runs the Gaia quality gates.

## Authoring surface — `gaia author` (cli-as-client)

Step 5 emits the package through the **agent-first authoring CLI**
(`docs/reference/cli/author.md`), not by writing raw
Python DSL by hand. The CLI:

- pre-validates each statement (identifier collision, reference resolution,
  syntactic well-formedness, structural self-loop) before writing,
- appends the rendered Python to the target source file,
- runs `gaia build check` automatically after each successful write
  (default `--check` on),
- emits a uniform JSON envelope on stdout — `json.loads(stdout)` once and
  dispatch on `verb` / `status` / `code`.

Per Step 4's mapping outputs, the DSL primitives this skill emits map to
author verbs as follows (canonical v0.5 names; legacy aliases in
`gaia.engine.lang.compat` emit `DeprecationWarning` and must not be used in
fresh packages):

| Step 4/5 emission | DSL primitive | Author verb |
|---|---|---|
| LKM source / no-chain claim | `claim(...)` | `gaia author claim` |
| Background context | `note(...)` | `gaia author note` |
| Open inquiry | `question(...)` | `gaia author question` |
| Factor-derived deduction | `derive(...)` | `gaia author derive` |
| Frontier support warrant (`support([U], target)`) | `derive(target, given=[U])` | `gaia author derive` |
| Accepted scientific contradiction (`contradiction(A, B)`) | `contradict(a, b)` | `gaia author contradict` |
| Cross-paper equivalence (`equivalence(A, B)`) | `equal(a, b)` | `gaia author equal` |
| Mutually-exclusive hypothesis pair | `exclusive(a, b)` | `gaia author exclusive` |
| Leaf prior record | `register_prior(...)` | `gaia author register-prior` |

The legacy `support([U], target, reason=..., prior=...)` strategy is
replaced by `derive(target, given=[U], rationale=...)` per
`docs/for-users/language-reference.md`.
The engine `derive(...)` signature accepts only `{given, background,
rationale, label}` — there is no `metadata=` / `warrant_prior` kwarg on
`derive` / `equal` / `contradict` / `exclusive` / `observe`. The CLI
exposes `--metadata` on these verbs but the post-write `gaia build check`
rejects, so warrant-strength intent (legacy `prior=` on the strategy)
moves into the `--rationale` prose instead.

`--metadata` remains valid on `gaia author claim` / `note` / `question`
(those underlying engine constructors accept `**metadata`), so
LKM provenance kwargs (`provenance_source`, `lkm_id`) continue to flow
through `claim --metadata`.

Errors surface in the envelope's `diagnostics` array with a `kind`
dispatch key (`prewrite.collision`, `prewrite.reference_unresolved`,
`prewrite.syntax`, `prewrite.self_loop`, `postwrite.check_fail`, ...).
Treat non-zero `code` as a fix-and-retry obligation before moving on; the
CLI guarantees no partial writes on pre-write failure.

## Batch Output

For batch mode, emit a new standalone `<name>-gaia/` package. Bootstrap the
package and its `priors.py` sibling with the CLI (matches the upstream
Mendel/Galileo two-module layout):

```bash
gaia pkg scaffold \
    --target <name>-gaia \
    --name <name>-gaia \
    --namespace <namespace> \
    --with-uuid \
    --description "<one-line description of this LKM-rooted package>"

gaia pkg add-module \
    --name priors \
    --imports register_prior \
    --target <name>-gaia
```

`gaia pkg scaffold` writes `pyproject.toml` (with `[tool.gaia] type =
"knowledge-package"` and a freshly-minted `uuid`),
`src/<import_name>/__init__.py` seeded with a minimal DSL import, and
`.gaia/.gitkeep`. `--namespace` matches `gaia example mendel` / `gaia
example galileo` (both pass `--namespace example`); set it to whatever
namespace you have chosen for this run. `add-module --name
priors --imports register_prior` creates `src/<import_name>/priors.py`
with the `register_prior` import pre-seeded.

All DSL emissions for this package — claims, deductions, cross-paper
operators (`equal` / `contradict` / `exclusive`) — go in `__init__.py`
(the default `--file` target). Leaf-prior `register_prior(...)` records
go in `priors.py` via `gaia author register-prior --file priors.py`.

Resulting layout after Step 4 + Step 5 emissions complete:

```text
<name>-gaia/
├── pyproject.toml
├── references.json
└── src/<import>/
    ├── __init__.py
    └── priors.py
```

`references.json` is a JSON object keyed by citation key, CSL-JSON entry
shape; each entry must include `type` (drawn from the CSL allowlist). See
`docs/specs/2026-04-09-references-and-at-syntax.md` for the full schema.

For refreshes, extend `__init__.py` and `priors.py` rather than replacing
prior emitted statements. Reuse existing labels where possible.

### Example invocations

Source claim with LKM provenance (no-chain) — `--metadata` is valid on
`claim` because the engine `claim(...)` accepts `**metadata`:

```bash
gaia author claim "<self-contained claim body>" \
    --dsl-binding-name <key>_<suffix> \
    --target <name>-gaia \
    --metadata '{"provenance_source": "lkm_no_chain", "lkm_id": "<lkm_id>"}'
```

Factor-derived deduction (chain-backed). Provenance kwargs that used to
ride `--metadata` are dropped here — the engine `derive(...)` has no
`metadata=` kwarg. LKM provenance for chain-backed deductions lives on
the conclusion / premise `claim --metadata` records and in the
`--rationale` prose for the deduction itself:

```bash
gaia author derive \
    --conclusion <key>_c<id>_<suffix> \
    --given <premise_label_1>,<premise_label_2> \
    --label <key>_c<id>_chain \
    --rationale "<factor-chain rationale>. LKM provenance: factor=<chain_id>, source=lkm:factor_chain. Warrant intent: strong (directly implies via factor chain)." \
    --target <name>-gaia
```

Frontier support warrant (legacy `support([U], target, prior=p)` → canonical
`derive(target, given=[U], rationale=...)`):

```bash
gaia author derive \
    --conclusion <target_label> \
    --given <upstream_label> \
    --label <upstream>_supports_<target> \
    --rationale "<what U says and why it supports target>. Provenance: lkm:frontier_support. Warrant intent: moderate (related, partial overlap)." \
    --target <name>-gaia
```

Cross-paper equivalence:

```bash
gaia author equal --a <claim_label_from_paper_A> --b <claim_label_from_paper_B> \
    --label <key_a>_<key_b>_<short_suffix>_equiv \
    --rationale "<why these refer to the same scientific assertion>. Provenance: lkm:factor_chain.equivalence, lkm_id=<lkm_equiv_id>." \
    --target <name>-gaia
```

Accepted scientific contradiction (per `mapping-contract.md` §4):

```bash
gaia author contradict --a <side_a_label> --b <side_b_label> \
    --label <side_a>_vs_<side_b>[_<quantity_or_regime>] \
    --rationale "<why these claims are adjudicably conflicting> | open_problem: <specific discriminating question>. Provenance: lkm:contradiction_scan. Warrant intent: clear accepted contradiction." \
    --target <name>-gaia
```

Per author.md "the contradiction operator binds the helper Claim to
`--label`; do not mint fresh claims by design" — `<side_a>_vs_<side_b>` is
the contradiction's helper-Claim label, not a synthesized side claim. The
`open_problem:` convention lives inside `--rationale`.

Leaf prior record (in `priors.py`):

```bash
gaia author register-prior \
    --claim <claim_label> \
    --value <float> \
    --justification "<terse rationale ending in TODO:review>" \
    --target <name>-gaia \
    --file priors.py
```

The CLI auto-inserts `from <import_name> import <claim>` into `priors.py`
when the referenced claim is not already imported.

## Refresh Output

For an existing standalone package, extend the existing package in place.
`gaia author` writes are append-only by design (pre-write collision check
refuses to overwrite a binding):

- extend `__init__.py` with new `gaia author` invocations carrying
  `--target <existing-pkg>` (the default `--file` is `__init__.py`),
- extend `priors.py` with `gaia author register-prior --file priors.py`
  invocations,
- reuse existing labels in `--given` / `--a` / `--b` / `--claim` to weave
  new statements into the prior graph; the CLI's pre-write reference
  resolution catches typos at write time,
- preserve existing labels and priors where possible — `gaia author
  register-prior` is additive (a Claim can carry multiple prior records
  from distinct `--source-id`s; Gaia's `ResolutionPolicy` picks the
  winning value at compile time and keeps the losing records for audit).

## Local Source Checks

Pre-write CLI validation handles the syntactic / structural slice — every
`gaia author <verb>` invocation runs identifier-collision, reference-
resolution, and `ast.parse`-equivalent checks before writing, and aborts
with a `prewrite.*` diagnostic on failure (see `docs/reference/cli/author.md`
"Pre-write invariants"). So legacy items "Python source parses with
`ast.parse`", "Gaia labels are lowercase identifiers", and "no claim has a
`prior` kwarg" (the CLI renders `--prior` as a `register_prior(...)` call
attached to the claim, never as a `prior=` claim kwarg) are enforced at the
verb boundary.

The remaining checks before handoff are SOP-owned semantic content:

- Every claim preserves LKM provenance metadata where available
  (`provenance_source` and `lkm_id` flow through `claim --metadata`).
- Every `derive(...)` is factor-derived; no-chain source claims have no
  fabricated deductions (no `gaia author derive` invocation against a
  no-chain source claim's label unless a real factor chain backs it).
  Factor / chain ids and warrant-strength intent live in the
  `--rationale` prose (the engine `derive` has no `metadata=` kwarg).
- Accepted contradictions use direct `contradict(A, B)` per
  `mapping-contract.md` §4, with an `xx_vs_yy` label and `open_problem:`
  + warrant-strength intent in the `--rationale` prose.

## Caller Quality Gate

`gaia author --check` (default on) runs `gaia build check` automatically
after each statement write, so per-statement structural / IR-hash drift is
already caught at the verb boundary. The end-of-batch quality gates this
skill runs collapse to three commands:

```bash
gaia build compile .
gaia run infer .
gaia inquiry review --strict .
```

- `gaia build compile .` — full-package compile catches cross-statement
  issues the per-write check cannot (cyclic imports, IR-hash regeneration,
  manifest emission for `exports` / `premises` / `holes` / `bridges`).
- `gaia run infer .` — belief propagation; emits `.gaia/beliefs.json`.
- `gaia inquiry review --strict .` — strict warrant / obligation /
  duplicate-control review (unchanged subapp).

If inquiry review reports unreviewed warrants or duplicates, resolve them
according to Step 4 and rerun the gate.

## Hand-Off Report

Return:

- files created or changed (aggregated from each `gaia author` envelope's
  `payload.written_to`),
- high-level counts: claims (chain-backed vs no-chain), deductions, supports
  (emitted as `derive(...)` with `provenance_source="lkm:frontier_support"`),
  equivalences, accepted contradictions, hypothesis-only open problems,
  priors added,
- inquiry obligations/hypotheses opened or closed,
- the three quality-gate commands run and pass/fail status
  (`gaia build compile .`, `gaia run infer .`, `gaia inquiry review
  --strict .`),
- the final `gaia author` envelope's `check.knowledge_count` /
  `check.strategy_count` / `check.operator_count` as IR-side sanity counts,
- deviations from the mapping contract, if any.

## What This Skill Is Not

- Not graph rendering: use `gaia run render` (or `gaia-evidence-subgraph`
  for closure-chain graphs) outside this skill.
- Not scholarly prose: that is `gaia-scholarly-synthesis`.
- Not a Gaia DSL language guide: syntax details belong to the installed Gaia
  package (`docs/reference/cli/author.md` for the authoring surface;
  `docs/for-users/language-reference.md` for the DSL primitives) and must be
  verified through Gaia CLI quality gates.

## Step-Completion Gate

When handoff is complete, mark Step 5 complete. If quality gates surface new
obligations, create a new iteration checklist and return to Step 1 with the new
target or obligation.
