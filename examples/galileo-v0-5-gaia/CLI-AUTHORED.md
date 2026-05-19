# CLI-authored Galileo — strict-reproducibility walkthrough

> **Companion to** [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md) and the hand-authored package at `src/galileo_v0_5/__init__.py`. This document shows how the same Galileo falling-body thought experiment can be authored end-to-end through `gaia author <verb>` and `gaia pkg scaffold`, without hand-editing the Python source.

> **Reproduction semantics**: this walkthrough reproduces the IR (knowledge/strategy content + counts + types) of the hand-authored package, not the byte-text source. See the equivalence test under `tests/cli/galileo_demo/` for the asserted axes; a small set of source-text divergences (chiefly the single-`--label` discipline) is documented at end-of-doc and is intrinsic-by-design.

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
    --namespace example
```

The `import_name` is derived from `--name` (strip `-gaia`,
hyphen→underscore: `galileo-v0-5-gaia` → `galileo_v0_5`) to match the
engine's convention; the cli does not accept a separate
`--import-name` override.

The scaffold writes:

- `pyproject.toml` with `[tool.gaia] type = "knowledge-package"` and
  `namespace = "example"` (no `uuid` by default — `--with-uuid` opts in
  to a generated uuid; both shipping example packages omit it).
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
  --label context \
  --target ./galileo-cli-mirror-gaia

gaia author note \
  "In the tied-body thought experiment, a heavy body and a light body are bound together and considered as one composite system." \
  --label thought_experiment_setup \
  --target ./galileo-cli-mirror-gaia

gaia author note \
  "The vacuum case is a counterfactual setup in which the resisting medium is absent." \
  --label vacuum_setup \
  --target ./galileo-cli-mirror-gaia
```

The first label matches the hand-authored binding name verbatim. The
`prewrite.deprecated_ref` scan is narrowed to call positions, so
`context = note(...)` does not trip the warning — the deprecation is
about *calling* `context()` as a DSL factory, not about a binding name
that happens to match. The note's **content string** is byte-identical
to the hand-authored version, so the compiled IR node content matches.

### 3. Author the model + observation claims

Three core claims drive the rest of the package — the everyday
observation, Model A (Aristotle's weight-speed law), and Model B (medium
resistance).

```bash
gaia author claim \
  "In air, heavy bodies are often observed to fall faster than light bodies." \
  --label daily_observation \
  --target ./galileo-cli-mirror-gaia

gaia author claim \
  "Model A: weight itself causes heavier bodies to have greater natural falling speed." \
  --label aristotle_model \
  --target ./galileo-cli-mirror-gaia

gaia author claim \
  "Model B: differences in falling speed in air are caused by resistance from the medium." \
  --label medium_model \
  --target ./galileo-cli-mirror-gaia
```

### 4. Author the daily-observation derivations + matches

Each model predicts the daily falling-body observation. The walkthrough
uses `--conclusion-prose` (inline-prose mode) rather than
`--conclusion-content` (auto-mint). The inline form matches the
hand-authored shape byte-for-byte: it emits `derive('<prose>', ...)`
directly via the engine's `derive(conclusion: Claim | str, ...)`
polymorphism, with no auto-minted named Claim binding. `--conclusion-content`
remains available when the agent wants a referenceable named conclusion
Claim.

```bash
gaia author derive \
  --conclusion-prose "Under Model A, heavy bodies should fall faster than light bodies in air." \
  --given aristotle_model \
  --rationale "If weight directly increases natural falling speed, then heavier bodies falling faster in air is expected." \
  --label aristotle_daily_observation_path \
  --target ./galileo-cli-mirror-gaia

gaia author equal \
  --a aristotle_daily_observation_path --b daily_observation \
  --rationale "The daily falling-body observation matches the prediction generated by the weight-speed model." \
  --label aristotle_daily_match \
  --target ./galileo-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "Under Model B, heavy bodies can fall faster than light bodies in air." \
  --given medium_model \
  --rationale "If air resistance creates the observed speed differences, then heavier compact bodies can fall faster in air without weight itself setting the natural speed." \
  --label medium_daily_observation_path \
  --target ./galileo-cli-mirror-gaia

gaia author equal \
  --a medium_daily_observation_path --b daily_observation \
  --rationale "The daily falling-body observation matches the prediction generated by the medium-resistance model." \
  --label medium_daily_match \
  --target ./galileo-cli-mirror-gaia
```

### 5. Author the thought-experiment paradox under Model A

The two contradictory predictions from the same model are the heart of
Galileo's reductio against Aristotelian dynamics.

```bash
gaia author derive \
  --conclusion-prose "The tied composite should fall faster than the heavy body alone." \
  --given aristotle_model --background thought_experiment_setup \
  --rationale "Under the weight-speed model, greater total weight implies greater natural falling speed. In the tied-body setup, the composite contains the heavy body plus an additional light body, so it is heavier than the heavy body alone." \
  --label aristotle_composite_faster \
  --target ./galileo-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "The tied composite should fall slower than the heavy body alone." \
  --given aristotle_model --background thought_experiment_setup \
  --rationale "Under the same weight-speed model, the slower light body should retard the faster heavy body when the two are tied together." \
  --label aristotle_composite_slower \
  --target ./galileo-cli-mirror-gaia

gaia author contradict \
  --a aristotle_composite_faster --b aristotle_composite_slower \
  --rationale "For the same tied composite, the weight-speed model yields incompatible predictions." \
  --label aristotle_paradox \
  --target ./galileo-cli-mirror-gaia
```

### 6. Author the vacuum prediction under Model B

```bash
gaia author derive \
  --conclusion-prose "In vacuum, bodies of different weights fall at the same rate." \
  --given medium_model --background vacuum_setup \
  --rationale "If observed speed differences come from medium resistance, then in the vacuum setup, where the resisting medium is absent by definition, the source of those differences is absent." \
  --label medium_vacuum_equal_fall_prediction \
  --target ./galileo-cli-mirror-gaia
```

### 7. Register the empirical-background prior in `priors.py`

`register-prior --file priors.py` routes the prior into a sibling
module that mirrors the hand-authored layout. First scaffold the
sibling via `gaia pkg add-module`, then route the `register-prior` call
into it. The writer auto-inserts
`from galileo_v0_5 import daily_observation` because the referenced
claim is bound in `__init__.py` rather than `priors.py` itself.

```bash
gaia pkg add-module \
  --name priors \
  --imports register_prior \
  --target ./galileo-cli-mirror-gaia

gaia author register-prior \
  --claim daily_observation \
  --value 0.90 \
  --justification "The everyday observation is treated as familiar empirical background, not as a new vacuum experiment." \
  --file priors.py \
  --target ./galileo-cli-mirror-gaia
```

Because `--source-id` is omitted, the rendered call also omits the
`source_id=` kwarg — the engine default (`"user_priors"`) applies at
load time. This matches the hand-authored `priors.py` byte-for-byte on
that axis.

## Compile + check

```bash
cd galileo-cli-mirror-gaia
gaia build compile
# → Compiled 24 knowledge, 5 strategies, 3 operators
gaia build check
```

The counts match the hand-authored package compile (`24 / 5 / 3`).

## Documented divergences

The cli-authored mirror is **closer-to-byte-text-equivalent** with the
hand-authored package on every axis other than the cli's
single-`--label` flag discipline, which is intrinsic-by-design.

### LHS binding equals `label=` kwarg (intrinsic)

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
single `--label` flag drives both. This is intrinsic to the cli's
single-`--label` discipline; it keeps every author call's binding name
match its referenceable identifier. Subsequent
`gaia author equal --a aristotle_daily_observation_path` calls
reference the Python binding directly. The two source-text forms
compile to the same IR.

The galileo equivalence test asserts the **distinct label count** axis
on this dimension at BYTE_TEXT, rather than label identity — both sides
produce the same number of label slots.

## Equivalence guarantees

The pytest fixture at `tests/cli/galileo_demo/test_equivalence.py` runs
the full cli sequence above against a fresh temp directory and asserts:

1. **User-authored content equivalence**: every Claim or note content
   string that an author wrote in the hand-authored file appears in the
   cli-authored compiled IR, byte-identical.
2. **Auto-warrant content equivalence**: the engine's auto-generated
   implication-warrant Claim contents match byte-for-byte because the
   inline-prose mode emits no named auto-mint slug suffix.
3. **Structural-count equivalence**: strategies and operators match
   exactly (5 / 3); total knowledge node count matches (24).
4. **Knowledge type equivalence**: the multiset of (claim, note,
   formula_claim) types matches.
5. **`register_prior` source-id omission**: `register_prior` calls
   render zero `source_id=` mentions on both sides — the cli omits
   the kwarg when `--source-id` is not explicitly passed.

The only remaining source-text divergence is the cli's single-`--label`
discipline, which is non-semantic at the IR level.

## See also

- Hand-authored ground truth: [`src/galileo_v0_5/__init__.py`](src/galileo_v0_5/__init__.py)
- Equivalence test: [`tests/cli/galileo_demo/test_equivalence.py`](../../tests/cli/galileo_demo/test_equivalence.py)
- Full cli reference: [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md)
