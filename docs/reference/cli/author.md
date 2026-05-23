# `gaia author` and `gaia pkg scaffold`

> **Status:** Reference for the optional Tier-2 authoring CLI (v0.5). The
> **recommended** authoring path is direct SDK authoring — run `gaia sdk`,
> read the cheat sheet, write the DSL directly. See
> [Authoring workflow](../../for-users/authoring-workflow.md).

The `gaia author` subcommand group and the `gaia pkg scaffold` verb are an
**optional convenience** over direct SDK authoring: instead of editing the
Python source, you can scaffold a fresh `-gaia` package and append DSL
statements through `gaia author <verb>`. Every `gaia author` statement write is
confined to the package's re-exported `authored/` submodule
(`src/<import_name>/authored/`) — the author helper does not interleave
generated statements with hand-authored package-root source. The package root
composes CLI-authored statements back in via `from .authored import *`. The cli owns identifier
collision checks, reference resolution, pre-write defensive validation, file
appending, and (by default) a post-write `gaia build check` to confirm the
package still compiles.

Output is **JSON-by-default** through a uniform envelope (see
[Envelope shape](#envelope-shape)) so an agent consumer can
`json.loads(stdout)` once and dispatch on `verb` to interpret `payload`.
`--human` opts into a short human-readable rendering of the same payload —
the JSON form is the contract; the text form is a courtesy.

This reference is scannable, not tutorial. For a worked walkthrough using
the five DSL verbs exercised by the canonical Galileo example, see
[Galileo as a worked example](#galileo-as-a-worked-example) at the end.

**Capabilities at a glance** (see also [`bayes.md`](bayes.md)):

- **`--file <relative>`** on every author verb — route the statement to
  a sibling Python module instead of `__init__.py`. Pair with
  `gaia pkg add-module --name <name>` to scaffold the sibling.
- **`--background <csv>`** on `equal` / `contradict` / `exclusive` /
  `observe` — passes through to the engine's `background=[...]` kwarg.
- **`derive --conclusion-prose`** / **`observe --observation-prose`** /
  **`infer --hypothesis-prose`** — inline-prose mode that emits the
  prose directly at the call site (no auto-mint Claim binding).
- **`claim --formula <expr>`** — canonical name for the predicate-mode
  formula expression; `--predicate` stays as a backwards-compatible
  alias.
- **`gaia author variable`** — declare a `Variable(...)` or
  `Constant(...)` typed term.
- **`gaia bayes <verb>`** group — predictive-model authoring surface.
  Covered in [`bayes.md`](bayes.md).

## Verb inventory — 23 author commands + 1 pkg verb

The `gaia author` group exposes **23 public commands** partitioned by DSL
layer. **20** are *statement-emitting* (the cli appends a Python statement to
`src/<import_name>/authored/__init__.py` or an `authored/` sibling module);
**2** are *file-based validate-and-
register* (the cli reads a file containing a decorated function and
records its metadata in `pyproject.toml`); and **1** is read-only inspection.

| Layer | Verb | DSL signature | Statement-emitting? |
|---|---|---|---|
| Knowledge | `note` | `note(content, *, title=None, **metadata)` | yes |
| Knowledge | `claim` | `claim(content, proposition=None, *, title=None, prior=None, background=None, formula=None, ...)` | yes |
| Knowledge | `question` | `question(content, *, title=None, targets=None, **metadata)` | yes |
| Knowledge | `artifact` | `artifact(kind=..., source=None, locator=None, path=None, caption=None, description=None, ...)` | yes |
| Knowledge | `figure` | `figure(source=None, locator=None, path=None, caption=None, description=None, ...)` | yes |
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
| Typed terms | `variable` | `Variable(symbol=…, domain=…, value=…)` or `Constant(value, primitive)` | yes |
| Inspection | `list` | AST scan of source bindings and composition metadata | **no — read-only** |

The additional package bootstrap verb, `gaia pkg scaffold`, lives in the `pkg`
group alongside `add`, `add-import`, `add-module`, and `register`. It
bootstraps a fresh `-gaia` package directory layout. See
[`gaia pkg scaffold`](#gaia-pkg-scaffold) below.

## Shared flag conventions

Every statement-emitting `gaia author` verb honors the same set of cross-
cutting flags. Per-verb flags layer on top of these.

| Flag | Type | Default | Purpose |
|---|---|---|---|
| `--target <path>` | string | `.` | Path to the target Gaia package root (the directory containing `pyproject.toml`). |
| `--file <relative>` | string | `__init__.py` | Relative path under `src/<import_name>/authored/` to append the statement to. Default routes to `authored/__init__.py`. Sibling files (e.g. `priors.py`) must exist first; use `gaia pkg add-module --name <name>` to scaffold them. |
| `--dsl-binding-name <ident>` | string | none | Python identifier for the rendered left-hand side (`<name> = ...`). Use this when later verbs need to reference the produced statement. |
| `--label <ident>` | string | none | Engine `label=` kwarg on relation/support/probabilistic verbs. It is distinct from `--dsl-binding-name`. `claim` accepts `--label` only with `--dsl-binding-name` and emits a follow-up `<binding>.label = ...`; `note`, `question`, and `variable` expose no engine label. |
| `--rationale <text>` | string | none | Natural-language justification carried through to the DSL kwarg. |
| `--metadata <json>` | JSON object | none | Optional metadata dict; rendered as the DSL `metadata=` kwarg. |
| `--background <csv>` / `--references <csv>` | csv idents | none | Context/reference identifiers on verbs that expose them. `--references` is used by formula sandboxes; `--background` is rendered into the DSL call when that verb supports background context. |
| `--check / --no-check` | bool | `--check` on | Run post-write `gaia build check` after a successful write. Short-circuited when pre-write fails. |
| `--human` | bool flag | `False` | Render the envelope as human-readable text instead of JSON. |
| `--interactive` | bool flag | `False` | Surface pre-write warnings as a numbered prompt (human mode only — JSON mode auto-suppresses). |
| `--json / --no-json` | bool | `--json` on | Courtesy alias; redundant with the default. `--human` is the actual switch. |

Prefer `--dsl-binding-name` whenever the generated object will be referenced
later. Without it, the cli emits a bare expression statement for verbs that can
do so. `register-prior` always writes a bare `register_prior(...)` expression
because the engine call returns `None`.

## Per-verb flag surface (statement-emitting verbs)

The flags below are *additional* to the shared set. Each verb's DSL
signature in the inventory table above is the source of truth for what
gets rendered into the package.

### `note`

```
gaia author note <content> [--dsl-binding-name <ident>] [--target <path>]
    [--title <text>] [--metadata <json>]
    [--check/--no-check] [--human] [--interactive]
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional natural-language background. |
| `--title <text>` | no | Optional short title (`title=` kwarg). |

### `artifact`

```
gaia author artifact --dsl-binding-name <ident> --kind <kind> [--target <path>]
    [--source <citation-key>] [--locator <text>] [--path <package-relative>]
    [--caption <text>] [--description <text>] [--media-type <mime>]
```

Creates a normal `note(...)` through the `artifact(...)` helper. The resulting
note carries `metadata["gaia"]["artifact"]` and can be referenced with
`[@<dsl-binding-name>]`.

| Flag | Required | Description |
|---|---|---|
| `--dsl-binding-name <ident>` | yes | Python module-scope binding for the artifact note. |
| `--kind <kind>` | yes | One of `figure`, `table`, `dataset`, `notebook`, `attachment`. |
| `--source <citation-key>` | no | Citation key from `references.json`; validated during compile/check. |
| `--locator <text>` | no | Source-local locator such as `Fig. 3` or `Supplementary Data 1`. |
| `--path <package-relative>` | no | Package-relative artifact path. Absolute paths and `..` escapes are rejected. |

### `figure`

```
gaia author figure --dsl-binding-name <ident> [--target <path>]
    [--source <citation-key>] [--locator <text>] [--path <package-relative>]
    [--caption <text>] [--description <text>] [--media-type <mime>]
```

Sugar for `gaia author artifact --kind figure`. A source-bound figure requires
`--locator` so that the source-local figure number is unambiguous.

### `claim`

```
gaia author claim <content> [--dsl-binding-name <ident>] [--target <path>]
    [--label <ident>] [--title <text>] [--prior <float>]
    [--formula "<expr>" | --predicate "<expr>"]
    [--references <csv>] [--background <csv>] [--metadata <json>]
    [--check/--no-check] [--human] [--interactive]
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional claim content. |
| `--title <text>` | no | Optional short title. |
| `--prior <float>` | no | Optional inline prior in (0, 1); routed via `register_prior` with source `claim_inline`. |
| `--label <ident>` | no | Optional Claim label. Requires `--dsl-binding-name`; the cli emits `<binding>.label = "<ident>"` after the `claim(...)` call. |
| `--formula "<expr>"` / `--predicate "<expr>"` | no | Predicate-claim mode — sandbox-validated formula expression rendered as the `formula=` kwarg. `--predicate` is the backwards-compatible spelling. See [Restricted-globals sandbox](#restricted-globals-sandbox). |
| `--references <csv>` | no | Formula-sandbox references; these are not rendered into `background=`. |
| `--background <csv>` | no | Comma-separated Knowledge identifiers rendered as `background=[...]`. |

### `question`

```
gaia author question <content> [--dsl-binding-name <ident>] [--target <path>]
    [--title <text>] [--targets <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `<content>` | yes | Positional question content. |
| `--targets <csv>` | no | Comma-separated target identifiers (`targets=` kwarg). |

### `equal` / `contradict` / `exclusive`

```
gaia author <equal|contradict|exclusive> --a <ident> --b <ident> \
    [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
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
gaia author decompose --whole <ident> --parts <csv> \
    [--dsl-binding-name <ident>] [--label <ident>] \
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
    --given <csv> [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
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
gaia author observe (--conclusion <ident> | --observation-content "<prose>" | --observation-prose "<prose>") \
    [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
    [--observation-label <ident>] [--value <expr>] [--error <expr>]
    [--given <csv>] [--source-refs <csv>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion <ident>` | one-of | Identifier of the observed Claim, Variable, or Distribution. |
| `--observation-content "<prose>"` | one-of | **Prose mode** for discrete observations only. Mutex with `--value` / `--error` (those target a Variable or Distribution). |
| `--observation-prose "<prose>"` | one-of | Inline prose passed directly to `observe(...)`; no named observation Claim is minted. |
| `--observation-label <ident>` | no | Explicit label for the auto-minted Claim. |
| `--value <expr>` | no | Numeric / Quantity expression for the continuous observation (`value=` kwarg). |
| `--error <expr>` | no | Observation error sigma or Distribution (`error=` kwarg); requires `--value`. |
| `--given <csv>` | no | Premise identifiers (discrete conditional form). |
| `--source-refs <csv>` | no | Deprecated transition flag. Prefer `--rationale "... [@CitationKey]"` so citations resolve through `references.json`. |

### `compute`

```
gaia author compute --conclusion-type <ident> \
    [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
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
    (--hypothesis <ident> | --hypothesis-content "<prose>" | --hypothesis-prose "<prose>") \
    --p-e-given-h <float> [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
    [--hypothesis-label <ident>] [--p-e-given-not-h <float>]
    [--given <csv>] [--rationale <text>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--evidence <ident>` | yes | Identifier of the evidence Claim. |
| `--hypothesis <ident>` | one-of | Reference an already-declared hypothesis Claim. |
| `--hypothesis-content "<prose>"` | one-of | **Prose mode** — mint a fresh hypothesis Claim. |
| `--hypothesis-prose "<prose>"` | one-of | Inline prose passed directly to `infer(...)`; no named hypothesis Claim is minted. |
| `--hypothesis-label <ident>` | no | Explicit label override for prose mode. |
| `--p-e-given-h <float>` | yes | P(evidence \| hypothesis). |
| `--p-e-given-not-h <float>` | no | P(evidence \| NOT hypothesis); DSL default 0.5. |
| `--given <csv>` | no | Conditioning Claim identifiers. |

### `associate`

```
gaia author associate --a <ident> --b <ident> \
    --p-a-given-b <float> --p-b-given-a <float> \
    [--dsl-binding-name <ident>] [--label <ident>] [--target <path>]
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
gaia author parameter --variable <ident> --value <expr> \
    [--dsl-binding-name <ident>] [--label <ident>] \
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
| `--source-id <text>` | no | Source identifier. When omitted, the rendered call omits `source_id=` and the engine default applies. |
| `--statement-label <ident>` | no | Optional trailing-comment label; no semantic effect. |

The verb writes a bare expression statement (`register_prior(...)`) — no
LHS binding, since `register_prior()` returns `None`.

### `depends-on`

```
gaia author depends-on --conclusion <ident> --given <csv> \
    [--dsl-binding-name <ident>] [--label <ident>] \
    [--target <path>] [--rationale <text>] [--background <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--conclusion <ident>` | yes | Dependent Claim. |
| `--given <csv>` | yes | Comma-separated premise identifiers. |
| `--background <csv>` | no | Comma-separated background identifiers. |

### `candidate-relation`

```
gaia author candidate-relation --claims <csv> --pattern <name> \
    [--dsl-binding-name <ident>] [--label <ident>] \
    [--target <path>] [--rationale <text>] [--background <csv>] [--metadata <json>] ...
```

| Flag | Required | Description |
|---|---|---|
| `--claims <csv>` | yes | Variadic claim identifiers. |
| `--pattern <name>` | yes | One of `equal` / `contradict` / `exclusive`. `contradict` requires exactly two claims. |

### `materialize`

```
gaia author materialize --scaffold <ident> --by <csv> \
    [--dsl-binding-name <ident>] [--label <ident>] \
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

## Read-only inspection — `list`

```bash
gaia author list --target ./my-pkg-gaia --human
gaia author list --target ./my-pkg-gaia --kind claim --json
gaia author list --target ./my-pkg-gaia --file observations.py --unbound
```

`gaia author list` scans Gaia package source with Python AST. It does not import
the package, run compile/check, or write files. The JSON payload reports each
top-level author-verb statement's kind, binding, content preview, file, line,
and export state. It also reads `[[tool.gaia.compositions]]` entries from
`pyproject.toml`.

| Flag | Purpose |
|---|---|
| `--target <path>` | Package root to inspect |
| `--file <relative>` | Restrict the scan to one source file under `src/<import_name>/` |
| `--kind <kind>` | Filter to one binding kind such as `claim`, `derive`, or `variable` |
| `--unbound` | Include bare expression calls without an LHS binding |
| `--human` | Render a readable table instead of the JSON envelope |
| `--json / --no-json` | Courtesy alias; JSON is the default unless `--human` is used |

## `gaia pkg scaffold`

Bootstrap a fresh `-gaia` package directory layout.

```
gaia pkg scaffold --target <path> [--name <pkg-name>] [--namespace <ns>]
    [--description <text>] [--with-uuid] [--docstring <text>]
    [--check/--no-check] [--human] [--interactive] [--json/--no-json]
```

| Flag | Required | Description |
|---|---|---|
| `--target <path>` | yes | Directory to initialise (must be empty or non-existent). |
| `--name <pkg-name>` | no | Package name; **must end with `-gaia`**. Defaults to target directory name. |
| `--namespace <ns>` | no | Package namespace; defaults to the import name. |
| `--description <text>` | no | Short description for `pyproject.toml`. |
| `--with-uuid` | no | Opt in to writing `[tool.gaia].uuid`; default is to omit it. |
| `--docstring <text>` | no | Optional module docstring for the generated `src/<import_name>/__init__.py`. |

The `import_name` is **derived from `--name`** by stripping the
trailing `-gaia` and converting hyphens to underscores
(`foo-bar-gaia` → `foo_bar`). This matches the engine's loader
convention; the cli does not accept a separate `--import-name`
override because doing so produced packages the engine could not load.
If the derived name collides with a Python stdlib module (e.g.
`os-gaia` → `os`), the verb refuses with exit 4.

The verb writes:

* `pyproject.toml` with `[tool.gaia] type / namespace`; `uuid` is written only
  when `--with-uuid` is passed.
* `src/<import_name>/__init__.py` with the direct-authoring package root and a
  re-export block for `.authored`.
* `src/<import_name>/authored/__init__.py` importing the minimal DSL seed
  plus `__all__: list[str] = []`. It does not seed a placeholder claim;
  subsequent `gaia author <verb>` calls populate this file and update
  `authored.__all__`.
* `.gaia/.gitkeep` so the cli postwrite check can find the IR artifact
  directory.

`--check` defaults off because a fresh scaffold has no declarations yet.
When enabled, it runs the same `postwrite_check` the statement-emitting verbs
use against the freshly created package; the result is surfaced under
`payload.check`.

Refuses to write into a non-empty target (exit 2, `prewrite.collision`).
Validates `--name` ends with `-gaia` (exit 4,
`prewrite.target_not_gaia_package`). Rejects a derived import name that
is not a valid Python identifier or collides with stdlib (exit 4,
`prewrite.target_invalid`).

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
| `label` | statement-emitting success | The Python binding name when one was supplied with `--dsl-binding-name`; `None` for bare expression statements and `register-prior`. |
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
   set must not contain the proposed Python binding name or auto-minted
   prose-mode label. Failure kind:
   `prewrite.self_loop` (exit 1).
4. **(c) Collision and reference resolution** — the proposed Python binding
   name must not collide with an existing module binding or DSL surface name;
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
| `prewrite.label_shadow` | The proposed Python binding name collides with a Python builtin or DSL surface name (defensive — most shadow cases are intercepted by the (c) hard error). | Run proceeds; warning flows to envelope. |
| `prewrite.deprecated_ref` | A call site in the generated code or one of `references` names a DSL symbol carrying a `DeprecationWarning` in the engine (sourced via AST scan of `gaia/engine/lang/dsl/**.py` at cli import; merged with a small hand-curated fallback for safety). Scan is narrowed to call positions, so a binding name that happens to match a deprecated factory does not trip the warning. | Run proceeds; `replacement` hint in `where`. |

Both flow through `--interactive`: in human mode + `--interactive` + at
least one warning, the cli surfaces a numbered prompt with default
`N`. JSON mode auto-suppresses prompts because agents cannot drive
stdin; warnings still ship in `envelope.warnings`. An `--interactive`
abort produces `status="aborted"` / `code=0` and a `user.aborted`
diagnostic.

## Prose mode — "introducing new statement" verbs

Three verbs accept a `--<arg>-content` flag that introduces a fresh Claim
inline rather than referencing an existing identifier. Two of them also expose
an inline-prose variant that writes the prose directly at the call site without
minting a named Claim binding.

| Verb | Flag | Mutex with | Label override |
|---|---|---|---|
| `derive` | `--conclusion-content "<prose>"` | `--conclusion`, `--conclusion-prose` | `--conclusion-label` |
| `infer` | `--hypothesis-content "<prose>"` | `--hypothesis`, `--hypothesis-prose` | `--hypothesis-label` |
| `observe` | `--observation-content "<prose>"` | `--conclusion`, `--observation-prose`, also `--value`/`--error` | `--observation-label` |

These verbs share the rationale that the named Claim-ref arg is
*introducing* a new statement that the verb itself is bringing into
existence (the derivation's conclusion, the hypothesis under test, the
observation's proposition). Auto-generating `slug = claim(prose)` and
using the slug downstream is semantically honest. The remaining author
author verbs are either *linking existing claims* (Structural /
Scaffold) or *quantitative* (compute / parameter / register-prior),
where prose-mode auto-mint would awkwardly bundle ops.

The cli derives a snake-case slug for the auto-Claim from the first
several word-tokens of the prose, lowercased; numeric leading tokens
get a `c_` prefix; collisions against caller-supplied identifiers get
`_2` / `_3` suffixes. Module-symbol collisions still surface as the
standard `prewrite.collision` hard error.

`--formula` / `--predicate` for `claim` are **not** prose-mode flags; they
are formula-expression flags rendered as the `formula=` kwarg. `--formula` is
the canonical spelling; `--predicate` remains a compatibility alias. The
expression goes through the same restricted-globals sandbox as `decompose
--formula-expr`.

### Inline-prose mode — `derive`, `infer`, and `observe`

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

`infer --hypothesis-prose` and `observe --observation-prose` follow the same
tradeoff for their respective hypothesis/observation arguments.

## Restricted-globals sandbox

`gaia author decompose --formula-expr` and `gaia author claim --formula`
/ `--predicate` both accept Python expressions, evaluated by the engine at package
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
exercises the harder cli surface. Where Galileo uses 5 author verbs,
Mendel additionally reaches for:

* **`gaia author variable`** to declare two `Variable(...)` typed terms
  (`f2_total_count`, `f2_dominant_count`).
* **`gaia author observe --conclusion <Variable> --value <number>`** to
  record the quantitative count data used by Bayes comparison.
* **`gaia bayes model`** with an inline `Binomial(...)` /
  `BetaBinomial(...)` Distribution expression on `--distribution`,
  followed by **`gaia bayes compare`** for the quantitative
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
demonstration that the cli surface covers the v0.5 engine end-to-end.

## See also

* [`gaia pkg`](pkg.md) — install dependencies, manage module/import plumbing, publish, and scaffold packages.
* [`gaia build`](build.md) — compile / check the package the cli wrote.
* [Foundational CLI workflow](../../foundations/cli/workflow.md) — narrative tour of the cli day-to-day.
* [CLI Workflow Command Guide](../../for-users/cli-commands.md) — workflow-oriented guide for the broader cli surface.

## Implementation

::: gaia.cli.commands.author

::: gaia.cli.commands.pkg.scaffold
