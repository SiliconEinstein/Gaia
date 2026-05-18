# `gaia author` and `gaia pkg scaffold`

> **Status:** Reference for the agent-first authoring CLI (v0.5).

The `gaia author` subcommand group and the `gaia pkg scaffold` verb together
form the **cli-as-client** authoring surface: an LLM agent (or human at a
shell) can scaffold a fresh `-gaia` package and append every supported DSL
statement through `gaia author <verb>` without touching the Python source by
hand. The cli owns identifier collision checks, reference resolution, pre-
write defensive validation, file appending, and (by default) a post-write
`gaia build check` to confirm the package still compiles.

Output is **JSON-by-default** through a uniform envelope (see
[Envelope shape](#envelope-shape)) so an agent consumer can
`json.loads(stdout)` once and dispatch on `verb` to interpret `payload`.
`--human` opts into a short human-readable rendering of the same payload —
the JSON form is the contract; the text form is a courtesy.

This reference is scannable, not tutorial. For a worked walkthrough using
all 5 of the DSL verbs the canonical Galileo example exercises, see
[Galileo as a worked example](#galileo-as-a-worked-example) at the end.

**R7 additions** (see also [`bayes.md`](bayes.md)):

- **`--file <relative>`** on every author verb — route the statement to
  a sibling Python module instead of `__init__.py`. Pair with
  `gaia pkg add-module --name <name>` to scaffold the sibling.
- **`--background <csv>`** on `equal` / `contradict` / `exclusive` /
  `observe` — passes through to the engine's `background=[...]` kwarg.
- **`derive --conclusion-prose`** / **`observe --observation-prose`** /
  **`infer --hypothesis-prose`** — inline-prose mode that emits the
  prose directly at the call site (no auto-mint Claim binding).
- **`claim --formula <expr>`** — canonical name for the predicate-mode
  formula expression (R7 G4); `--predicate` stays as a backwards-
  compatible alias.
- **`gaia author variable`** — declare a `Variable(...)` or `Constant(...)`
  typed term (R7 G3).
- **`gaia bayes <verb>`** group — predictive-model authoring surface
  (R7 G2). Covered in [`bayes.md`](bayes.md).

## Verb inventory — 19 author verbs + 1 pkg verb

The `gaia author` group exposes **19 verbs** partitioned by DSL layer.
**17** are *statement-emitting* (the cli appends a Python statement to
`src/<import_name>/__init__.py`); **2** are *file-based validate-and-
register* (the cli reads a file containing a decorated function and
records its metadata in `pyproject.toml`).

| Layer | Verb | DSL signature | Statement-emitting? |
|---|---|---|---|
| Knowledge | `note` | `note(content, *, title=None, **metadata)` | yes |
| Knowledge | `claim` | `claim(content, proposition=None, *, title=None, prior=None, background=None, formula=None, ...)` | yes |
| Knowledge | `question` | `question(content, *, title=None, targets=None, **metadata)` | yes |
| Structural | `equal` | `equal(a, b, *, rationale="", label=None)` | yes |
| Structural | `contradict` | `contradict(a, b, *, rationale="", label=None)` | yes |
| Structural | `exclusive` | `exclusive(a, b, *, rationale="", label=None)` | yes |
| Structural | `decompose` | `decompose(whole, parts, *, formula=None, rationale="", label=None)` | yes |
| Support | `derive` | `derive(conclusion, *, given=(), background=None, rationale="", label=None)` | yes |
| Support | `observe` | `observe(conclusion, *, value=…, error=…, given=…, rationale="", label=None)` | yes |
| Support | `compute` | `compute(result, *, fn, given=…, rationale="", label=None)` | yes |
| Probabilistic | `infer` | `infer(evidence, hypothesis, p_e_given_h, *, p_e_given_not_h=…, given=…, label=None)` | yes |
| Probabilistic | `associate` | `associate(a, b, p_a_given_b, p_b_given_a, *, pattern=…, rationale="", label=None)` | yes |
| Sugar | `parameter` | `parameter(variable, value, *, content=…, prior=…, label=None, **metadata)` | yes |
| Prior | `register-prior` | `register_prior(claim, *, value, justification, source_id=…)` | yes |
| Scaffold | `depends-on` | `depends_on(conclusion, given, *, rationale="", background=None, label=None)` | yes |
| Scaffold | `candidate-relation` | `candidate_relation(*, claims, pattern, rationale="", background=None, label=None)` | yes |
| Scaffold | `materialize` | `materialize(scaffold, *, by, rationale="", label=None)` | yes |
| Composition | `compose` | `@compose(name=…, version=…)` decorating `def fn(...) -> Claim` | **no — file-based** |
| Composition | `composition` | alias of `compose` | **no — file-based** |
| Typed terms | `variable` | `Variable(symbol=…, domain=…, value=…)` or `Constant(value, primitive)` (R7 G3) | yes |

The 20th verb in this reference, `gaia pkg scaffold`, lives in the `pkg`
group alongside `add` / `register`. It bootstraps a fresh `-gaia` package
directory layout. See [`gaia pkg scaffold`](#gaia-pkg-scaffold) below.

## Shared flag conventions

Every statement-emitting `gaia author` verb honors the same set of cross-
cutting flags. Per-verb flags layer on top of these.

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--target <path>` | string | `.` | Path to the target Gaia package root (the directory containing `pyproject.toml`). |
| `--file <relative>` | string | `__init__.py` | **R7 G1** — relative path under `src/<import_name>/` to append the statement to. Default routes to the package entrypoint. Sibling files (e.g. `priors.py`) must exist first; use `gaia pkg add-module --name <name>` to scaffold them. |
| `--label <ident>` | string | required (most verbs) | Python identifier the produced binding takes. Must not collide with module or DSL names. |
| `--rationale <text>` | string | none | Natural-language justification carried through to the DSL kwarg. |
| `--metadata <json>` | JSON object | none | Optional metadata dict; rendered as the DSL `metadata=` kwarg. |
| `--references <csv>` | csv idents | none | Comma-separated background reference identifiers (only the verbs that accept background context). |
| `--check / --no-check` | bool | `--check` on | Run post-write `gaia build check` after a successful write. Short-circuited when pre-write fails. |
| `--human` | bool flag | `False` | Render the envelope as human-readable text instead of JSON. |
| `--interactive` | bool flag | `False` | Surface pre-write warnings as a numbered prompt (human mode only — JSON mode auto-suppresses). |
| `--json / --no-json` | bool | `--json` on | Courtesy alias; redundant with the default. `--human` is the actual switch. |

`--label` is **required** for every statement-emitting verb except
`register-prior` (which writes a bare `register_prior(...)` expression with
no LHS binding) and `note` / `claim` / `question` (where the positional
content arg is also required). Verbs that emit a relation (`equal` /
`contradict` / `exclusive` / `decompose`) bind the relation's helper Claim
to `--label`.

## Per-verb flag surface (statement-emitting verbs)

The flags below are *additional* to the shared set. Each verb's DSL
signature in the inventory table above is the source of truth for what
gets rendered into the package.

### `note`

```
gaia author note <content> --label <ident> [--target <path>]
    [--title <text>] [--metadata <json>]
    [--check/--no-check] [--human] [--interactive]
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional natural-language background. |
| `--title <text>` | no | Optional short title (`title=` kwarg). |

### `claim`

```
gaia author claim <content> --label <ident> [--target <path>]
    [--title <text>] [--prior <float>] [--predicate "<expr>"]
    [--references <csv>] [--metadata <json>]
    [--check/--no-check] [--human] [--interactive]
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional claim content. |
| `--title <text>` | no | Optional short title. |
| `--prior <float>` | no | Optional inline prior in (0, 1); routed via `register_prior` with source `claim_inline`. |
| `--predicate "<expr>"` | no | Predicate-claim mode — sandbox-validated formula expression rendered as the `formula=` kwarg. See [Restricted-globals sandbox](#restricted-globals-sandbox). |
| `--references <csv>` | no | Comma-separated background claims (rendered as `background=` kwarg). |

### `question`

```
gaia author question <content> --label <ident> [--target <path>]
    [--title <text>] [--targets <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional question content. |
| `--targets <csv>` | no | Comma-separated target identifiers (`targets=` kwarg). |

### `equal` / `contradict` / `exclusive`

```
gaia author <equal|contradict|exclusive> --a <ident> --b <ident> \
    --label <ident> [--target <path>]
    [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--a <ident>` | yes | Identifier of the first Claim. |
| `--b <ident>` | yes | Identifier of the second Claim. |

All three verbs produce a binary structural relation between existing
Claim references — they do **not** mint fresh claims, by design.

### `decompose`

```
gaia author decompose --whole <ident> --parts <csv> --label <ident> \
    [--target <path>]
    [--formula-template <atom|and|or>] [--formula-expr "<expr>"]
    [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--whole <ident>` | yes | Identifier of the whole Claim. |
| `--parts <csv>` | yes | Comma-separated identifiers of the part Claims. |
| `--formula-template <atom\|and\|or>` | no | Common-shape builder — renders `formula=ClaimAtom(p)` / `formula=land(*atoms)` / `formula=lor(*atoms)` from `--parts`. Mutually exclusive with `--formula-expr`. |
| `--formula-expr "<expr>"` | no | Escape-hatch for shapes outside the three templates (`iff_and`, `iff_or`, custom). Sandbox-validated — see [Restricted-globals sandbox](#restricted-globals-sandbox). |

### `derive`

```
gaia author derive (--conclusion <ident> | --conclusion-content "<prose>" | --conclusion-prose "<prose>") \
    --given <csv> --label <ident> [--target <path>]
    [--conclusion-label <ident>] [--rationale <text>]
    [--background <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion <ident>` | one-of | Reference an already-declared conclusion Claim. |
| `--conclusion-content "<prose>"` | one-of | **Prose mode (auto-mint)** — cli prepends `slug = claim(prose)` and uses the slug as `conclusion`. Mutually exclusive with `--conclusion` / `--conclusion-prose`. See [Prose mode](#prose-mode-introducing-new-statement-verbs). |
| `--conclusion-prose "<prose>"` | one-of | **Prose mode (inline)** — emits `derive('<prose>', ...)` directly via the engine's `Claim \| str` polymorphism; no named binding minted. Mutex with the other two; no companion `--conclusion-label` (no Claim to label). The payload tag `conclusion_kind` is `"inline_prose"`. |
| `--conclusion-label <ident>` | no | Explicit label for the auto-minted Claim (only valid with `--conclusion-content`). |
| `--given <csv>` | yes | Comma-separated premise identifiers. |
| `--background <csv>` | no | Comma-separated background identifiers (rendered as `background=`). |

The envelope `payload.conclusion_kind` distinguishes the three shapes:
`"qid"` (referencing a declared identifier), `"auto_mint"` (cli minted a
named conclusion Claim), `"inline_prose"` (engine wraps the bare string
into an anonymous Claim at runtime).

### `observe`

```
gaia author observe (--conclusion <ident> | --observation-content "<prose>") \
    --label <ident> [--target <path>]
    [--observation-label <ident>] [--value <expr>] [--error <expr>]
    [--given <csv>] [--source-refs <csv>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion <ident>` | one-of | Identifier of the observed Claim or Distribution (continuous form). |
| `--observation-content "<prose>"` | one-of | **Prose mode** for discrete observations only. Mutex with `--value` / `--error` (those target a Distribution). |
| `--observation-label <ident>` | no | Explicit label for the auto-minted Claim. |
| `--value <expr>` | no | Numeric / Quantity expression for the continuous observation (`value=` kwarg). |
| `--error <expr>` | no | Observation error sigma or Distribution (`error=` kwarg); requires `--value`. |
| `--given <csv>` | no | Premise identifiers (discrete conditional form). |
| `--source-refs <csv>` | no | Source reference strings attached to the observation. |

### `compute`

```
gaia author compute --conclusion-type <ident> --label <ident> [--target <path>]
    [--fn <ident>] [--given <csv>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion-type <ident>` | yes | Identifier of the result-type Claim. |
| `--fn <ident>` | no | Identifier of the compute function (must already be declared in the package). |
| `--given <csv>` | no | Comma-separated input identifiers. |

The decorator form `@compute` stays at Python-source level (same logic as
`compose` / `composition`).

### `infer`

```
gaia author infer --evidence <ident> \
    (--hypothesis <ident> | --hypothesis-content "<prose>") \
    --p-e-given-h <float> --label <ident> [--target <path>]
    [--hypothesis-label <ident>] [--p-e-given-not-h <float>]
    [--given <csv>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--evidence <ident>` | yes | Identifier of the evidence Claim. |
| `--hypothesis <ident>` | one-of | Reference an already-declared hypothesis Claim. |
| `--hypothesis-content "<prose>"` | one-of | **Prose mode** — mint a fresh hypothesis Claim. |
| `--hypothesis-label <ident>` | no | Explicit label override for prose mode. |
| `--p-e-given-h <float>` | yes | P(evidence \| hypothesis). |
| `--p-e-given-not-h <float>` | no | P(evidence \| NOT hypothesis); DSL default 0.5. |
| `--given <csv>` | no | Conditioning Claim identifiers. |

### `associate`

```
gaia author associate --a <ident> --b <ident> \
    --p-a-given-b <float> --p-b-given-a <float> --label <ident> [--target <path>]
    [--pattern <name>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--a <ident>` | yes | First Claim. |
| `--b <ident>` | yes | Second Claim. |
| `--p-a-given-b <float>` | yes | P(a \| b). |
| `--p-b-given-a <float>` | yes | P(b \| a). |
| `--pattern <name>` | no | Optional engine-pattern hint. |

### `parameter`

```
gaia author parameter --variable <ident> --value <expr> --label <ident> \
    [--target <path>] [--content <text>] [--title <text>] [--prior <float>]
    [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--variable <ident>` | yes | Identifier of the bound Variable. |
| `--value <expr>` | yes | Value expression — numeric literal or Quantity. |
| `--content <text>` | no | Optional Claim-content prose. |
| `--prior <float>` | no | Inline prior in (0, 1). |

`--rationale` routes through `metadata['rationale']` because `parameter()`
has no top-level `rationale=` kwarg.

### `register-prior`

```
gaia author register-prior --claim <ident> --value <float> \
    --justification <text> [--target <path>]
    [--source-id <text>] [--statement-label <ident>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--claim <ident>` | yes | Claim the prior attaches to. |
| `--value <float>` | yes | Prior value in (0, 1). |
| `--justification <text>` | yes | Free-text justification. |
| `--source-id <text>` | no | Source identifier; defaults derived from claim. |
| `--statement-label <ident>` | no | Optional trailing-comment label; no semantic effect. |

The verb writes a bare expression statement (`register_prior(...)`) — no
LHS binding, since `register_prior()` returns `None`.

### `depends-on`

```
gaia author depends-on --conclusion <ident> --given <csv> --label <ident> \
    [--target <path>] [--rationale <text>] [--background <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion <ident>` | yes | Dependent Claim. |
| `--given <csv>` | yes | Comma-separated premise identifiers. |
| `--background <csv>` | no | Comma-separated background identifiers. |

### `candidate-relation`

```
gaia author candidate-relation --claims <csv> --pattern <name> --label <ident> \
    [--target <path>] [--rationale <text>] [--background <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--claims <csv>` | yes | Variadic claim identifiers. |
| `--pattern <name>` | yes | One of `equal` / `contradict` / `exclusive`. `contradict` requires exactly two claims. |

### `materialize`

```
gaia author materialize --scaffold <ident> --by <csv> --label <ident> \
    [--target <path>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--scaffold <ident>` | yes | Scaffold identifier the materialization targets. |
| `--by <csv>` | yes | Comma-separated identifiers used as the `by=` arg (single-element scalars and multi-element lists both render as `by=[...]`). |

## File-based verbs — `compose` / `composition`

The two composition verbs do **not** append a statement to
`__init__.py`. The composition primitive is a Python-decorator-level
concept (its body is an arbitrary Python function capturing nested
`Action` invocations through a ContextVar), so the cli takes the file
containing the decorated function as input and registers its metadata.

```
gaia author <compose|composition> --from-file <path> [--target <pkg-root>]
    [--check/--no-check] [--human] [--interactive] [--json/--no-json]
```

| Flag | Required | Description |
|---|---|---|
| `--from-file <path>` | yes | Path to the Python file containing the decorated function. |
| `--target <pkg-root>` | no | Target package root; defaults to cwd. |

**Validation contract** (each failure exits 2 with a structured
diagnostic):

* `--from-file` must exist and parse as valid Python.
* Exactly **one** `@compose` / `@composition`-decorated `FunctionDef` per
  file (the *one-compose-per-file rule*). Both bare names and
  `<module>.compose` Attribute-shaped references are counted.
* The decorator must carry `name=` and `version=` string kwargs.
* The decorated function's return annotation must read `Claim` (or
  `"Claim"` as a forward-ref string).

**Registration target**: `[[tool.gaia.compositions]]` as a TOML
array-of-tables in `pyproject.toml`. Each entry carries `name` /
`version` / `file` / `function` / `registered_at`. Re-running for the
same `name` rewrites in place (idempotent).

**`--check`**: when on (default), runs `postwrite_check(target_root)`
after registration succeeds. Registration is the truth-bearing action;
it stays on disk regardless of post-write outcome. On post-write
failure: envelope returns `status="error"`, `code=1`, `source="postwrite"`
diagnostic, payload still carries registration details with
`check="failed"`. On success: payload gains `check.knowledge_count` /
`check.strategy_count` / `check.operator_count`.

## `gaia pkg scaffold`

Bootstrap a fresh `-gaia` package directory layout.

```
gaia pkg scaffold --target <path> [--name <pkg-name>] [--namespace <ns>]
    [--import-name <ident>] [--description <text>]
    [--check/--no-check] [--human] [--interactive] [--json/--no-json]
```

| Flag | Required | Description |
|---|---|---|
| `--target <path>` | yes | Directory to initialise (must be empty or non-existent). |
| `--name <pkg-name>` | no | Package name; **must end with `-gaia`**. Defaults to target directory name. |
| `--namespace <ns>` | no | Package namespace; defaults to the import name. |
| `--import-name <ident>` | no | Source-root identifier; defaults to `<name without -gaia, hyphen→underscore>`. Must be a valid Python identifier. |
| `--description <text>` | no | Short description for `pyproject.toml`. |

The verb writes:

* `pyproject.toml` with `[tool.gaia] type / uuid / namespace`. UUID
  auto-generated per call.
* `src/<import_name>/__init__.py` importing the full author-surface DSL
  (so subsequent `gaia author <verb>` calls do not trip the postwrite
  `NameError`) and seeding a placeholder `hypothesis = claim(...)`.
* `.gaia/.gitkeep` so the cli postwrite check can find the IR artifact
  directory.

`--check` (default on) runs the same `postwrite_check` the statement-
emitting verbs use against the freshly created package; reports
`knowledge_count: 1` for the template's seeded hypothesis claim.

Refuses to write into a non-empty target (exit 2, `prewrite.collision`).
Validates `--name` ends with `-gaia` (exit 4,
`prewrite.target_not_gaia_package`). Validates `--import-name` is a valid
Python identifier (exit 4, `prewrite.target_invalid`).

## Envelope shape

Every `gaia author <verb>` (and `gaia pkg scaffold`) invocation writes a
single JSON object to stdout matching this schema:

```json
{
  "status": "ok" | "error" | "aborted",
  "code": 0 | 1 | 2 | 3 | 4,
  "verb": "<verb_name>",
  "payload": { /* verb-specific keys */ },
  "warnings": [ "<str>", ... ],
  "diagnostics": [
    {
      "kind": "<str>",
      "level": "error" | "warning",
      "message": "<str>",
      "source": "prewrite" | "postwrite" | "stub",
      "where": { /* optional structured locator */ }
    }
  ]
}
```

| Field | Purpose |
|---|---|
| `status` | Outcome class. `"ok"` for successful writes, `"error"` for any failure that prevented the write or compile, `"aborted"` for user-driven `--interactive` aborts. |
| `code` | Semantic exit code (0–4). Mirrors the process exit status. |
| `verb` | The verb name (`note` / `claim` / `derive` / ...). Dispatch table key. |
| `payload` | Verb-specific success payload (e.g. `label`, `written_to`, `snippet`, `auto_generated`, `check.{knowledge,strategy,operator}_count`). |
| `warnings` | Flat string list of human-readable warning messages — convenience for log scraping. |
| `diagnostics` | Structured list of error/warning entries. Each carries a `kind` an agent can dispatch on. |

### Payload — common keys

| Key | When | Description |
|---|---|---|
| `target` | always | Resolved absolute path of the target package. |
| `written_to` | statement-emitting success | Path of the file the cli appended to (`src/<import_name>/__init__.py`). |
| `label` | statement-emitting success | The `--label` value (None for `register-prior`). |
| `verb` | always | Echo of the verb name (alongside the top-level `verb`). |
| `snippet` | statement-emitting success | The exact Python source string appended to the file. |
| `auto_generated` | prose-mode success | List of `{label, snippet}` for each auto-minted Claim. |
| `check.knowledge_count` / `check.strategy_count` / `check.operator_count` | success + `--check` | Counts from the post-write compile. |
| `check` | success + `--no-check` | Literal `"skipped"`. |
| `check` | `compose` post-write failure | Literal `"failed"`. |

## Exit codes

The semantic exit-code table is fixed by `gaia/cli/commands/author/_envelope.py`:

| Code | Meaning | Typical kinds |
|---|---|---|
| `0` | Success (or `--interactive` abort, which is also a non-failure). | — |
| `1` | Pre-write structural failure or post-write check failure. | `prewrite.self_loop`, `prewrite.order_structure`, `postwrite.compile_fail`, `postwrite.check_fail` |
| `2` | Input syntax error or unimplemented stub. | `prewrite.syntax`, `prewrite.expr_unsafe`, `stub.not_implemented` |
| `3` | Identifier collision or unresolved reference. | `prewrite.collision`, `prewrite.reference_unresolved` |
| `4` | System / IO error. Target missing, target not a `-gaia` package, target pyproject invalid. | `prewrite.target_missing`, `prewrite.target_not_gaia_package`, `prewrite.target_invalid` |

Warning kinds (`prewrite.label_shadow`, `prewrite.deprecated_ref`) flow
through the envelope's `warnings` and `diagnostics` arrays at
`level: "warning"` and map to exit code `0` — they are informational,
not blocking.

## Pre-write invariants

Pre-write always runs before any file write. Fail-fast: the first
invariant to trip emits its diagnostic and aborts the run. Ordering
matters because the *first* failure determines `kind` and exit code.

1. **(a) Target validity** — `--target` exists, is a `-gaia` package
   directory, has a parseable `pyproject.toml` with `[tool.gaia]`.
   Failure kinds: `prewrite.target_missing` /
   `prewrite.target_not_gaia_package` / `prewrite.target_invalid` (all
   exit 4).
2. **(b) Syntactic well-formedness** — the proposed generated statement
   (and any prepended prose-mode auto-Claim statements) parse as valid
   Python. Failure kind: `prewrite.syntax` (exit 2). Sandbox failures
   for `--predicate` / `--formula-expr` distinguish via
   `prewrite.expr_unsafe` (also exit 2).
3. **(d) Structural self-loop check** — the proposed op's `references`
   set must not contain the proposed `--label`. Failure kind:
   `prewrite.self_loop` (exit 1).
4. **(c) Collision and reference resolution** — the proposed `--label`
   must not collide with an existing module binding or DSL surface name;
   all `references` must resolve to module bindings (or one of the
   prepended-statement labels in the same invocation). Failure kinds:
   `prewrite.collision` / `prewrite.reference_unresolved` (both exit 3).

The (d)-before-(c) ordering is deliberate: structural self-loops surface
as their own kind (exit 1) instead of being eaten by the collision /
unresolved-ref machinery (exit 3). Documented in
`gaia/cli/commands/author/_prewrite.py`.

### Warning kinds (post-(c), non-blocking)

| Kind | Fires when | Behavior |
|---|---|---|
| `prewrite.label_shadow` | The proposed `--label` collides with a Python builtin or DSL surface name (defensive — most shadow cases are intercepted by the (c) hard error). | Run proceeds; warning flows to envelope. |
| `prewrite.deprecated_ref` | One of `references` (or `required_imports`) names a DSL symbol carrying a `DeprecationWarning` in the engine (sourced via AST scan of `gaia/engine/lang/dsl/**.py` at cli import; merged with an R3 hand-curated fallback for safety). | Run proceeds; `replacement` hint in `where`. |

Both flow through `--interactive`: in human mode + `--interactive` + at
least one warning, the cli surfaces a numbered prompt with default
`N`. JSON mode auto-suppresses prompts because agents cannot drive
stdin; warnings still ship in `envelope.warnings`. An `--interactive`
abort produces `status="aborted"` / `code=0` and a `user.aborted`
diagnostic.

## Prose mode — "introducing new statement" verbs

Four verbs accept a `--<arg>-content` flag that introduces a fresh Claim
inline rather than referencing an existing identifier:

| Verb | Flag | Mutex with | Label override |
|---|---|---|---|
| `derive` | `--conclusion-content "<prose>"` | `--conclusion`, `--conclusion-prose` | `--conclusion-label` |
| `claim` | `--predicate "<formula-expr>"` | — (predicate-mode is additive, not replacement) | — |
| `infer` | `--hypothesis-content "<prose>"` | `--hypothesis` | `--hypothesis-label` |
| `observe` | `--observation-content "<prose>"` | `--conclusion`, also `--value`/`--error` | `--observation-label` |

These verbs share the rationale that the named Claim-ref arg is
*introducing* a new statement that the verb itself is bringing into
existence (the derivation's conclusion, the hypothesis under test, the
observation's proposition). Auto-generating `slug = claim(prose)` and
using the slug downstream is semantically honest. The remaining 13
author verbs are either *linking existing claims* (Structural /
Scaffold) or *quantitative* (compute / parameter / register-prior),
where prose-mode auto-mint would awkwardly bundle ops.

The cli derives a snake-case slug for the auto-Claim from the first
several word-tokens of the prose, lowercased; numeric leading tokens
get a `c_` prefix; collisions against caller-supplied identifiers get
`_2` / `_3` suffixes. Module-symbol collisions still surface as the
standard `prewrite.collision` hard error.

`--predicate` for `claim` is **not** a prose-mode flag; it is a
formula-expression flag rendered as the `formula=` kwarg. The expression
goes through the same restricted-globals sandbox as `decompose
--formula-expr`.

### Inline-prose mode — `derive --conclusion-prose` (R6)

`derive` carries a third shape, `--conclusion-prose "<prose>"`, that
**does not** mint a named binding. The prose is emitted at the call
site as a bare string literal:

```python
visibility_warrant = derive('Stars are visible tonight.', given=[hypothesis], label='visibility_warrant')
```

The engine's `derive(conclusion: Claim | str, ...)` polymorphism wraps
the string into an anonymous Claim at runtime. The shape is byte-text
closer to a hand-authored package that uses the inline-string idiom
(see the Galileo prose-mode divergence note in the walkthrough under
`examples/galileo-v0-5-gaia/`), at the cost of losing referenceability —
subsequent author calls cannot reach the conclusion Claim by name. The
envelope payload tags the shape via `conclusion_kind`:

| `conclusion_kind` | Trigger | Source effect |
|---|---|---|
| `"qid"` | `--conclusion <ident>` | Reuses a declared identifier; no extra statements written. |
| `"auto_mint"` | `--conclusion-content "<prose>"` | Prepends `slug = claim(prose)`; uses the slug. |
| `"inline_prose"` | `--conclusion-prose "<prose>"` | Emits `derive('<prose>', ...)` directly; no prepended statement. |

Pick `--conclusion-content` (auto-mint, default) when downstream author
calls might need to reference the conclusion. Pick `--conclusion-prose`
when byte-text fidelity to a target source layout matters more.

## Restricted-globals sandbox

`gaia author decompose --formula-expr` and `gaia author claim --predicate`
both accept Python expressions, evaluated by the engine at package
import time. To prevent `os.system(...)`-shaped attacks at pre-write
time, the cli sandbox-validates the expression against a whitelist:

| Category | Names |
|---|---|
| Formula primitives | `land`, `lor`, `lnot`, `implies`, `iff`, `equals`, `forall`, `exists` |
| Atomic operand | `ClaimAtom` |
| Distribution factories | `Normal`, `LogNormal`, `Beta`, `Exponential`, `Gamma`, `StudentT`, `Cauchy`, `ChiSquared`, `Binomial`, `Poisson`, `Distribution` |

Allowed AST forms: function calls, keyword arguments, arithmetic /
comparison operators, name lookups (against the whitelist), numeric /
string / boolean / `None` constants, tuples / lists.

Rejected: attribute access (`x.attr`), subscripting (`x[k]`), lambdas,
comprehensions, dunder names (`__import__`), `**kwargs` unpacking, any
identifier outside the whitelist. Failures emit
`prewrite.expr_unsafe` (exit 2), distinct from `prewrite.syntax`, so an
agent can dispatch on the kind to distinguish "your Python is wrong"
from "your Python parses but the sandbox does not allow it".

## Compose validate-and-register

The `compose` / `composition` verbs (see [File-based verbs](#file-based-
verbs-compose-composition)) extract metadata from a Python file with a
single `@compose` / `@composition`-decorated `FunctionDef` and record
that metadata in the target package's `pyproject.toml` as a
`[[tool.gaia.compositions]]` array-of-tables entry. Five string fields:
`name` / `version` / `file` / `function` / `registered_at`
(UTC ISO timestamp). Insert-or-update by composition name (case-
sensitive).

The **one-compose-per-file rule** is enforced at AST-walk time. If a
file contains zero or more than one decorated function, the verb exits
2 with a structured diagnostic identifying the count.

The minimal pattern in the file:

```python
from gaia.engine.lang import compose

@compose(name="my_strategy", version="0.1.0")
def my_strategy(...) -> Claim:
    ...
```

The cli does **not** import the file (no side effects); it only walks
the AST. The decorated function's body is left untouched; only the
metadata flows to `pyproject.toml`.

## Galileo as a worked example

The canonical Galileo falling-body thought experiment lives at
`examples/galileo-v0-5-gaia/`. The package uses **5 author verbs** —
`note`, `claim`, `derive`, `equal`, `contradict` — and exercises 15
total statements (3 notes + 3 claims + 5 derives + 2 equals + 1
contradict + 1 `register_prior` in `priors.py`).

A scripted walkthrough that re-creates the same package end-to-end via
the cli lives at `examples/galileo-v0-5-gaia/CLI-AUTHORED.md`. The
walkthrough demonstrates:

1. `gaia pkg scaffold` to bootstrap the package directory layout.
2. `gaia author note` invocations for the three contextual notes.
3. `gaia author claim` invocations for the three model / observation
   claims.
4. `gaia author derive` invocations for the five model predictions
   (using `--conclusion-content` prose mode, with the structural
   divergence from the hand-authored shape documented inline).
5. `gaia author equal` and `gaia author contradict` for the four
   structural relations.
6. `gaia author register-prior` for the empirical-background prior.

A pytest fixture at `tests/cli/galileo_demo/test_equivalence.py` drives
the same cli sequence at test time and asserts that the resulting
package is **content-equivalent** to the hand-authored ground truth —
every Claim content string in the hand-authored package appears in the
cli-authored package, every structural relation (`equal` / `contradict`
/ `derive`-given) maps to the same content pair, and both compile
through `gaia build compile` to a graph with matching knowledge /
strategy / operator counts.

Prose-mode auto-mint introduces additional named-Claim bindings (one per
`--conclusion-content` invocation) that the hand-authored file expresses
as inline string literals to `derive()`'s polymorphic `Claim | str`
conclusion argument. The two shapes compile to equivalent runtime
graphs but diverge at the source-text level; see CLI-AUTHORED.md for
the explicit delta inventory.

## Mendel as a worked example (bayes + Variable + formula + multi-file)

The Mendel single-factor cross example at `examples/mendel-v0-5-gaia/`
exercises the harder cli surface that R7 unlocked. Where Galileo uses
5 author verbs, Mendel additionally reaches for:

* **`gaia author variable`** to declare two `Variable(...)` typed terms
  (`f2_total_count`, `f2_dominant_count`).
* **`gaia author claim --formula`** to author a predicate-logic claim
  wrapping `land(equals(...), equals(...))`.
* **`gaia bayes binomial` / `gaia bayes beta-binomial` / `gaia bayes model`
  / `gaia bayes likelihood`** for the quantitative
  count-comparison sub-pipeline.
* **`gaia pkg add-module` + `gaia author register-prior --file priors.py`**
  for the multi-file authoring layout that mirrors the hand-authored
  package's `priors.py` sibling module.

A scripted walkthrough lives at `examples/mendel-v0-5-gaia/CLI-AUTHORED.md`.
The pytest fixture at `tests/cli/mendel_demo/test_equivalence.py`
re-runs the cli sequence on every PR-gate run and asserts equivalence
through the multi-level tolerance helper at
`tests/cli/_equivalence_levels.py` — BYTE_TEXT on the user-authored
content axes + structural counts, CONTENT_SET on the intrinsic
single-`--label` discipline axis. Mendel is therefore the empirical
demonstration of R7's "cli surface covers full engine" claim.

## See also

* [`gaia pkg`](pkg.md) — install / publish / scaffold packages.
* [`gaia build`](build.md) — compile / check the package the cli wrote.
* [Foundational CLI workflow](../../foundations/cli/workflow.md) — narrative tour of the cli day-to-day.
* [CLI Commands (full)](../../for-users/cli-commands.md) — every other cli verb's option surface.

## Implementation

::: gaia.cli.commands.author

::: gaia.cli.commands.pkg.scaffold
