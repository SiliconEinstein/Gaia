# CLI-authored Galileo — strict-reproducibility walkthrough

> **Companion to** [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md) and the hand-authored package at `src/galileo_v0_5/__init__.py`. This document shows how the same Galileo falling-body thought experiment can be authored end-to-end through `gaia author <verb>` and `gaia pkg scaffold`, without hand-editing the Python source.

## What you get

A scripted sequence of cli invocations produces a separately-scaffolded
`-gaia` package that compiles to a `LocalCanonicalGraph` with:

- 14 user-authored knowledge contents — **byte-identical** to the hand-
  authored package's user-authored claim and note contents.
- 5 derive strategies — **same count and structure** as the hand-authored
  package.
- 3 structural operators (2 `equal` + 1 `contradict`) — **same count and
  structure**.
- 24 total knowledge nodes (14 user-authored + 10 auto-generated
  warrants) — **same count**.

The two packages are content-equivalent at the level of what an author
wrote and what the graph compiler ingested. The pytest fixture at
`tests/cli/galileo_demo/test_equivalence.py` re-runs the cli sequence
fresh and asserts these invariants on every PR-gate run.

## Authoring sequence

The 16 `gaia` invocations below produce the cli-authored mirror. Each
invocation is shown with its full flag set; in practice an agent would
script this from a JSON template. Output is JSON by default; we route
through `python -c "import sys, json; ..."` only to print a status line
per call. The full envelope flows on every stdout.

### 1. Scaffold the package skeleton

```bash
gaia pkg scaffold \
    --target ./galileo-cli-mirror-gaia \
    --name galileo-v0-5-gaia \
    --import-name galileo_v0_5 \
    --namespace example \
    --no-check
```

The scaffold writes:

- `pyproject.toml` with `[tool.gaia] type = "knowledge-package"`,
  `uuid = "<auto>"`, `namespace = "example"`.
- `src/galileo_v0_5/__init__.py` importing the full author-surface DSL
  (so each `gaia author <verb>` does not trip the postwrite `NameError`
  from missing imports) and seeding a placeholder
  `hypothesis = claim("A scientific hypothesis to be evaluated.", title="Hypothesis")`.
- `.gaia/.gitkeep` so the cli postwrite check can find the IR artifact
  directory.

The placeholder `hypothesis` statement is **not part of the Galileo
example** — strip it before authoring the real statements:

```bash
python -c "
import pathlib
p = pathlib.Path('galileo-cli-mirror-gaia/src/galileo_v0_5/__init__.py')
src = p.read_text()
end = src.find('hypothesis = claim(')
if end > 0:
    p.write_text(src[:end].rstrip() + '\n')
"
```

(The test fixture does the same edit; the resulting file carries
the scaffold-default import block plus a blank line ready for the first
`gaia author note`.)

### 2. Author the three contextual notes

The hand-authored package opens with three `note(...)` statements
establishing the package framing and two thought-experiment setups.

```bash
gaia author note \
  "This package models Galileo's falling-body thought experiment as a comparison between two explanatory models. It does not treat vacuum falling as an observed fact inside the package." \
  --label preamble_context \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author note \
  "In the tied-body thought experiment, a heavy body and a light body are bound together and considered as one composite system." \
  --label thought_experiment_setup \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author note \
  "The vacuum case is a counterfactual setup in which the resisting medium is absent." \
  --label vacuum_setup \
  --target ./galileo-cli-mirror-gaia --no-check
```

Note the **first label rename**: hand-authored uses `context` for the
preamble note. The cli flags `context` as a `prewrite.deprecated_ref`
warning (the engine has a deprecated DSL helper named `context`), so we
rename the cli-authored binding to `preamble_context`. The warning is
non-blocking and the cli still writes — this rename is a hygiene choice,
not a functional requirement. The note's **content string** is
byte-identical to the hand-authored version, so the compiled IR node
content matches. See
[Documented divergences](#documented-divergences) below.

### 3. Author the model + observation claims

Three core claims drive the rest of the package — the everyday
observation, Model A (Aristotle's weight-speed law), and Model B (medium
resistance).

```bash
gaia author claim \
  "In air, heavy bodies are often observed to fall faster than light bodies." \
  --label daily_observation \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author claim \
  "Model A: weight itself causes heavier bodies to have greater natural falling speed." \
  --label aristotle_model \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author claim \
  "Model B: differences in falling speed in air are caused by resistance from the medium." \
  --label medium_model \
  --target ./galileo-cli-mirror-gaia --no-check
```

### 4. Author the daily-observation derivations + matches

Each model predicts the daily falling-body observation. The cli's prose
mode (`--conclusion-content`) auto-mints a conclusion Claim, then uses
the auto-minted slug as `conclusion` for the `derive(...)` call.

```bash
gaia author derive \
  --conclusion-content "Under Model A, heavy bodies should fall faster than light bodies in air." \
  --conclusion-label aristotle_daily_prediction_claim \
  --given aristotle_model \
  --rationale "If weight directly increases natural falling speed, then heavier bodies falling faster in air is expected." \
  --label aristotle_daily_observation_path \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author equal \
  --a aristotle_daily_observation_path --b daily_observation \
  --rationale "The daily falling-body observation matches the prediction generated by the weight-speed model." \
  --label aristotle_daily_match \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-content "Under Model B, heavy bodies can fall faster than light bodies in air." \
  --conclusion-label medium_daily_prediction_claim \
  --given medium_model \
  --rationale "If air resistance creates the observed speed differences, then heavier compact bodies can fall faster in air without weight itself setting the natural speed." \
  --label medium_daily_observation_path \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author equal \
  --a medium_daily_observation_path --b daily_observation \
  --rationale "The daily falling-body observation matches the prediction generated by the medium-resistance model." \
  --label medium_daily_match \
  --target ./galileo-cli-mirror-gaia --no-check
```

### 5. Author the thought-experiment paradox under Model A

The two contradictory predictions from the same model are the heart of
Galileo's reductio against Aristotelian dynamics.

```bash
gaia author derive \
  --conclusion-content "The tied composite should fall faster than the heavy body alone." \
  --conclusion-label aristotle_composite_faster_claim \
  --given aristotle_model --background thought_experiment_setup \
  --rationale "Under the weight-speed model, greater total weight implies greater natural falling speed. In the tied-body setup, the composite contains the heavy body plus an additional light body, so it is heavier than the heavy body alone." \
  --label aristotle_composite_faster \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-content "The tied composite should fall slower than the heavy body alone." \
  --conclusion-label aristotle_composite_slower_claim \
  --given aristotle_model --background thought_experiment_setup \
  --rationale "Under the same weight-speed model, the slower light body should retard the faster heavy body when the two are tied together." \
  --label aristotle_composite_slower \
  --target ./galileo-cli-mirror-gaia --no-check

gaia author contradict \
  --a aristotle_composite_faster --b aristotle_composite_slower \
  --rationale "For the same tied composite, the weight-speed model yields incompatible predictions." \
  --label aristotle_paradox \
  --target ./galileo-cli-mirror-gaia --no-check
```

### 6. Author the vacuum prediction under Model B

```bash
gaia author derive \
  --conclusion-content "In vacuum, bodies of different weights fall at the same rate." \
  --conclusion-label medium_vacuum_equal_fall_claim \
  --given medium_model --background vacuum_setup \
  --rationale "If observed speed differences come from medium resistance, then in the vacuum setup, where the resisting medium is absent by definition, the source of those differences is absent." \
  --label medium_vacuum_equal_fall_prediction \
  --target ./galileo-cli-mirror-gaia --no-check
```

### 7. Register the empirical-background prior

The hand-authored package keeps prior registration in a separate
`priors.py`. The cli currently writes to the package's entry
`__init__.py` (this is a documented divergence; see below). For
content-equivalence the choice does not matter — both files are
processed during compile.

```bash
gaia author register-prior \
  --claim daily_observation \
  --value 0.90 \
  --justification "The everyday observation is treated as familiar empirical background, not as a new vacuum experiment." \
  --target ./galileo-cli-mirror-gaia --no-check
```

## Compile + check

```bash
cd galileo-cli-mirror-gaia
gaia build compile
# → Compiled 24 knowledge, 5 strategies, 3 operators
gaia build check
```

The counts match the hand-authored package compile (`24 / 5 / 3`).

## Documented divergences

The cli-authored package is **content-equivalent** to the hand-authored
package but is **not byte-identical at the source-text level**. The two
deliberate divergences:

### 1. Prose-mode auto-mint introduces named Claim bindings

The hand-authored file uses the engine's `derive(conclusion: Claim | str, ...)`
polymorphism: the conclusion is passed as a bare string literal and the
engine auto-wraps it into an anonymous `Claim` at runtime.

```python
# hand-authored
aristotle_daily_prediction = derive(
    "Under Model A, heavy bodies should fall faster than light bodies in air.",
    given=[aristotle_model],
    rationale="If weight directly increases natural falling speed, ...",
    label="aristotle_daily_observation_path",
)
```

The cli's `--conclusion-content` prose mode mints a **named** Claim binding
and references it from the `derive` call:

```python
# cli-authored (rendered)
aristotle_daily_prediction_claim = claim(
    'Under Model A, heavy bodies should fall faster than light bodies in air.'
)
aristotle_daily_observation_path = derive(
    aristotle_daily_prediction_claim,
    given=[aristotle_model],
    label='aristotle_daily_observation_path',
    rationale='If weight directly increases natural falling speed, ...',
)
```

The two shapes lower to **the same compiled graph** — both add a Claim
node carrying the prose content as `Claim.content`. The cli-authored
version exposes the conclusion Claim as a referenceable module symbol
(named binding); the hand-authored version leaves it anonymous in the
module scope. Compile counts are identical (`24 / 5 / 3`).

Per the R5 design pass (and consistent with R3·❓-A / R4·❓-A
dispatch), the cli prose mode is the canonical agent-first authoring
shape: each conclusion claim is namable, inspectable, and referenceable
by subsequent author calls. The trade-off vs strict source-text
equivalence is intentional.

> **R6 update — `--conclusion-prose` closes this divergence on opt-in.**
> Authors who want byte-text equivalence with the hand-authored shape
> can use the R6 inline-prose flag instead:
>
> ```bash
> gaia author derive \
>     --conclusion-prose "Under Model A, heavy bodies should fall faster than light bodies in air." \
>     --given aristotle_model \
>     --rationale "If weight directly increases natural falling speed, ..." \
>     --label aristotle_daily_observation_path \
>     --target ./galileo-cli-mirror-gaia --no-check
> ```
>
> Renders directly as `aristotle_daily_observation_path = derive('Under Model A, ...', ...)` — no
> named Claim binding minted, the engine's `Claim | str` polymorphism
> wraps the prose into an anonymous Claim at runtime, matching the
> hand-authored shape. The walkthrough above sticks with
> `--conclusion-content` because the agent-first ergonomic argument
> (named conclusions are referenceable by subsequent author calls) is
> the default we want to encourage. `--conclusion-prose` is the escape
> hatch for cases where source-text fidelity to a pre-existing
> hand-authored package matters more than later referenceability.

### 2. LHS binding equals `label=` kwarg

The hand-authored file frequently uses different identifiers for the
Python binding (LHS of `=`) and the DSL `label=` kwarg:

```python
# hand-authored
aristotle_daily_prediction = derive(    # ← Python binding
    ...,
    label="aristotle_daily_observation_path",  # ← DSL label, different
)
```

The cli enforces `label = derive(..., label="label", ...)` — the LHS
binding and the DSL `label=` kwarg are forced equal because the cli's
single `--label` flag drives both. The cli-authored mirror uses the
DSL-label spelling (`aristotle_daily_observation_path`) for both the
binding and the kwarg.

This keeps every author call's binding name match its referenceable
identifier. Subsequent `gaia author equal --a aristotle_daily_observation_path`
calls reference the Python binding directly.

### 3. `preamble_context` rename for the first note's label

The hand-authored binding `context = note(...)` collides with a
deprecated DSL helper named `context` (replaced by `note()` in v0.5).
The cli surfaces this as a `prewrite.deprecated_ref` warning — non-
blocking, so the call still writes, but the convention in cli-authored
files is to pick a non-shadowing identifier. We rename the binding to
`preamble_context`. The **note's content string is byte-identical** to
hand-authored, so the compiled IR node carries the same content.

### 4. `register-prior` lands in `__init__.py`, not `priors.py`

The hand-authored package separates priors into `src/galileo_v0_5/priors.py`
for clarity. The cli writes every author statement (including
`register-prior`) to the package's entry `__init__.py`. Compile-time
behavior is the same — `gaia build compile` evaluates the package's
import graph and picks up `register_prior(...)` calls wherever they
land — but the source layout differs.

## Equivalence guarantees

The pytest fixture at `tests/cli/galileo_demo/test_equivalence.py` runs
the full cli sequence above against a fresh temp directory and asserts:

1. **User-authored content equivalence**: every Claim or note content
   string that an author wrote in the hand-authored file appears in the
   cli-authored compiled IR, byte-identical. (Auto-generated warrant
   strings are excluded because they embed conclusion-claim labels,
   which differ by the prose-mode auto-mint suffix.)
2. **Structural-count equivalence**: strategies and operators match
   exactly (5 / 3); total knowledge node count matches (24).
3. **Knowledge type equivalence**: the multiset of (claim, note,
   formula_claim) types matches.

These are the invariants that make the cli-authored mirror a faithful
reproduction of the canonical Galileo example, given the documented
divergences above.

## See also

- Hand-authored ground truth: [`src/galileo_v0_5/__init__.py`](src/galileo_v0_5/__init__.py)
- Equivalence test: [`tests/cli/galileo_demo/test_equivalence.py`](../../tests/cli/galileo_demo/test_equivalence.py)
- Full cli reference: [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md)
