# Embedded Package Layout

> The non-invasive on-ramp for ARM bundles, ARA artifacts, plain Python
> packages, and any other host that wants Gaia semantics without
> reshuffling its own files.

## TL;DR

Mount Gaia onto any host directory by creating two — and only two —
sibling folders:

```
<host>/
  <host's own files: pyproject.toml, src/, logic/, evidence/, ...>   # untouched
  gaia/                # user-authored Gaia DSL
    gaia.toml          # package identity (name, version, namespace, host_kind)
    __init__.py        # DSL module
    <other modules>    # split your DSL across as many files as you like
  .gaia/               # generated artifacts (was already this name)
    ir.json, ir_hash, manifests/, source_map.json, formalization_queue.jsonl
```

No `pyproject.toml` edit. No `-gaia` name suffix. No `src/<import>/`
reshuffle.

```bash
gaia build init --embedded ./my-host          # (or)  gaia pkg mount ./my-host
gaia build compile ./my-host
gaia run infer    ./my-host
```

## Why

The historical "legacy" layout required hosts to opt in *invasively*:

- add `[tool.gaia].type = "knowledge-package"` to the host's
  `pyproject.toml`;
- restructure source into `src/<import_name>/`;
- name the distribution with a `-gaia` suffix.

That made it hard to express Gaia semantics on top of:

- ARM bundles (`arm_manifest.json` + structured `knowledge/`,
  `execution/`, `trace/` folders);
- ARA artifacts (`PAPER.md` + `logic/` + `evidence/`);
- plain Python packages already published on PyPI;
- paper repos that are not Python projects at all.

The embedded layout fixes that. The Gaia identity lives in
`gaia/gaia.toml`. The host's own metadata is none of Gaia's business.

## On-disk shape

### `gaia/gaia.toml`

```toml
schema_version = 1

[package]
name = "galileo_v0_5"           # user-facing name; '-gaia' suffix optional
version = "0.1.0"
namespace = "example"
description = "Galileo's falling-body thought experiment"
host_kind = "python-package"    # one of arm / ara / python-package / generic

[quality]
allow_holes = true

[projection]                    # filled by the deterministic projector
mode = "scaffold"
```

The pydantic schema lives in `gaia/engine/manifest.py`. A manifest
whose `schema_version` is higher than the installed gaia-lang knows
about is **rejected at load**, never silently downgraded.

### `gaia/` — the source folder

Author Gaia DSL the same way you would in the legacy layout. The only
difference: imports inside this folder must be **relative**:

```python
# gaia/__init__.py
from gaia.engine.lang import claim, derive
from . import priors          # ✅ relative
# from my_pkg import priors   # ❌ would not resolve under the synthetic loader name
```

#### Why the folder is called `gaia/` (and how we avoid the clash)

The folder is loaded as a *synthetic* Python package
(`_gaia_pkg_<slug>_<sha8>`) so it never shadows the installed `gaia`
library, even though the user-source folder is literally called
`gaia/`. Three rules make this safe:

1. The loader uses `importlib.util.spec_from_file_location` with a
   synthetic module name; the literal name `gaia` is never bound to
   the user's folder in `sys.modules`.
2. Submodule search is anchored at `<host>/gaia/` via the synthetic
   module's `__path__`, so `from . import priors` works.
3. Absolute imports through the literal `gaia` namespace
   (`from gaia.engine.lang import claim`) always resolve to the
   **installed** `gaia-lang` package via the standard finder chain.

This is the same trick `mypy`'s [PEP 561 stub
packages](https://peps.python.org/pep-0561/) use to ship type
information for an unrelated runtime package without colliding with
it. The regression test
`test_embedded_loader_does_not_shadow_installed_gaia` pins this
contract — break it and CI complains immediately.

#### Edit-then-reproject

The projector-managed subdirectories (`gaia/from_ara/`,
`gaia/from_arm/`, `gaia/from_host/`) are wiped and rebuilt by
`gaia pkg mount --reproject`. Everything else under `gaia/` —
`__init__.py`, `priors.py`, `formalization/`, and any other module
you hand-author — is preserved across reprojects:

```bash
gaia pkg mount ./host                          # initial mount
# edit gaia/__init__.py, add gaia/custom.py, etc.
# host source files change
gaia pkg mount ./host --reproject              # refreshes gaia/from_*/ only
```

### `.gaia/` — generated artifacts

Same layout as the legacy package (so `gaia run render`, `gaia inspect
starmap`, `gaia pkg register` all keep working):

- `ir.json`, `ir_hash`, `compile_metadata.json`
- `manifests/exports.json`, `manifests/premises.json`,
  `manifests/holes.json`, `manifests/bridges.json`
- `formalization_manifest.json`
- `source_map.json` *(new)* — spec §9 audit spine binding host paths
  to Gaia labels
- `formalization_queue.jsonl` *(new)* — spec §10 queue of scaffold
  records awaiting reviewer/agent upgrade

## CLI

### `gaia pkg mount <host>` / `gaia build init --embedded <host>`

Non-invasively create `gaia/` + `.gaia/` inside `host`. Auto-detects
the host kind:

| Detected kind   | Marker                              |
|-----------------|-------------------------------------|
| `arm`           | `arm_manifest.json`                 |
| `ara`           | `PAPER.md` AND `logic/` directory   |
| `python-package`| `pyproject.toml` (no Gaia markers)  |
| `generic`       | fallback                            |

For ARM and ARA hosts the deterministic projector (see below)
populates `gaia/from_arm/` or `gaia/from_ara/` with typed scaffolds
(claims, observations, scholarly references). For other hosts the
mount is a bare DSL template you fill in yourself, plus optional
`--from <file>` seeds.

```bash
gaia pkg mount ./resnet-ara                                  # auto-detect
gaia pkg mount ./resnet-ara --host-kind ara                  # explicit
gaia pkg mount ./scratch --from notes.md --from setup.py     # generic + seeds
```

### `gaia pkg migrate <legacy-host>`

Convert an existing legacy package to the embedded layout. Copies
`src/<import>/*.py` into `gaia/`, rewrites absolute imports of the
package's own name to relative form, writes `gaia/gaia.toml` from the
existing `[tool.gaia]` block. By default it leaves the legacy
`src/` + `[tool.gaia]` in place so you can verify IR-hash parity
before committing; `--remove-legacy` does the cleanup atomically.

```bash
gaia pkg migrate examples/galileo-v0-5-gaia
gaia build compile examples/galileo-v0-5-gaia   # warns about dual layout
gaia pkg migrate examples/galileo-v0-5-gaia --remove-legacy
```

The migration is byte-stable: the IR hash before and after migration
is identical.

### `gaia build compile <host>` flag changes

- `--sync-host` / `--no-sync-host` (default `--no-sync-host` in
  embedded mode): runs `uv sync` against the host's own
  `pyproject.toml` before importing. Off by default in the embedded
  layout — the host's Python environment is not Gaia's concern unless
  the user opts in. Always on in the legacy layout (the host's
  pyproject IS the Gaia package).

### `gaia pkg formalize <host>` — upgrade scaffold records (spec §5.2)

Walks `.gaia/formalization_queue.jsonl` and applies user-chosen
upgrades, writing the result into `gaia/formalization/<batch>.py`
plus a `materialize(scaffold, by=warrant, ...)` link that keeps the
source-map audit chain intact.

```bash
# Interactive review of each open item.
gaia pkg formalize ./my-host

# Non-interactive: pick a default upgrade for every depends_on.
gaia pkg formalize ./my-host --no-interactive --auto-accept depends_on:infer
```

The verb is **reversible**: deleting the generated batch module and
resetting the queue entry's `status` back to `"open"` restores the
pre-upgrade IR. Numeric likelihoods on `infer(...)` upgrades are
emitted as conservative `0.5/0.5` placeholders with a
`TODO(reviewer)` rationale — spec §2.3 ("形式化必须显式选择") forbids
auto-fabricated likelihoods.

### `gaia pkg lock-check <host>` — publish gate (spec §5.3)

Validates that an embedded host is ready to register. Reuses the
same pipeline `gaia build check` runs so failure diagnostics are
identical. Checks:

- every `source_map.json` record's `generated_file` is on disk;
- every record's `source_path` still resolves under the host;
- `gaia build check` passes (load + compile + IR validation + fills
  resolution, via the engine's own `load_gaia_package` /
  `apply_package_priors` / `compile_loaded_package_artifact` /
  `validate_fills_relations`);
- `.gaia/ir_hash` matches a fresh compile (via
  `gaia.engine._stale_check.check_compiled_artifacts`);
- `.gaia/manifests/exports.json` + `premises.json` exist;
- no open queue items marked `blocking_for_publish: true`;
- **no IR record still carries an unreplaced `TODO(reviewer)`
  marker** from `gaia pkg formalize` (catches the 0.5/0.5 placeholder
  trap where an upgrade looks done but is mathematically inert).

```bash
gaia pkg lock-check ./my-host                  # explicit gate run
gaia pkg register   ./my-host --locked         # gate + register in one shot
```

Used by registry CI to refuse stale or in-progress packages.

## Deterministic projector (spec §6, §7, §11)

For ARA and ARM hosts the projector emits **only safe records**
(spec §2.2 / §5.1):

- `note(...)` for narrative material
- `claim(...)` for ARA `Cxx` blocks / ARM `knowledge/claims.json`
- `observe(...)` for ARA `evidence/tables/*` / ARM
  `characterization.json` metrics
- `depends_on(...)` for `Proof: [Exx]` lines (warrant type unreviewed)
- `note(...)` with `registry_binding.state = "source_only"` for ARA
  `logic/related_work.md` entries (spec §14.1: scholarly refs are
  **not** auto-converted to `gaia pkg add` dependencies)

The projector **never** emits `derive`, `infer`, `equal`,
`contradict`, or `exclusive` on its own — those require a reviewer or
agent to upgrade through the formalization queue.

Each ambiguous record records a follow-up `QueueItem` in
`.gaia/formalization_queue.jsonl` with the legal upgrade paths:

```json
{
  "queue_id": "FQP0011",
  "source_id": "ARA:C01->E01",
  "source_refs": ["logic/claims.md#C01", "evidence/E01"],
  "current_gaia_record": "ara_c01_depends_on_e01",
  "current_action": "depends_on",
  "candidate_actions": ["infer", "derive"],
  "reason_review_needed": "ARA Proof links evidence to claim but does not classify warrant type.",
  "blocking_for_publish": false,
  "status": "open"
}
```

## Backwards compatibility

The legacy layout is unchanged. Existing example packages
(`examples/galileo-v0-5-gaia`, `examples/mendel-v0-5-gaia`) compile to
exactly the same `ir_hash` they always did, and `gaia pkg migrate`
produces byte-identical IR when run on either of them.

When a host has both an embedded `gaia/gaia.toml` and a legacy
`[tool.gaia]` block, the embedded manifest wins and `detect_layout`
emits a warning so the user knows the legacy block is no longer the
source of truth.

## Specification

This document implements the design in
[`docs/specs/2026-05-19-arm-ara-gaia-package-projection-spec.md`](https://github.com/SiliconEinstein/Gaia/blob/codex/arm-ara-gaia-projection-spec/docs/specs/2026-05-19-arm-ara-gaia-package-projection-spec.md)
(PR [#675](https://github.com/SiliconEinstein/Gaia/pull/675)). The
sections most directly mapped:

| Spec section | Implementation                                        |
|--------------|-------------------------------------------------------|
| §2 first principles    | layout / loader / mount split                |
| §3.1 native embedded layout | `gaia/` + `.gaia/`                       |
| §4 CLI semantics       | `gaia build init --embedded` + `gaia pkg mount` |
| §5.1 scaffold mode     | `gaia.engine.projector.generic` + `ara` + `arm`  |
| §5.2 formalized mode CLI | `gaia pkg formalize` (`gaia.cli.commands.pkg.formalize`) |
| §5.3 locked mode (publish gate) | `gaia pkg lock-check` + `gaia pkg register --locked` |
| §6 ARM projection rules| `gaia.engine.projector.arm`                  |
| §7 ARA projection rules| `gaia.engine.projector.ara` (PAPER frontmatter, claim body, evidence tables, trace dead_ends, related_work) |
| §9 source_map schema   | `gaia.engine.projector.api.render_source_map` |
| §10 formalization queue schema | `QueueItem.to_json`                  |
| §11 deterministic projector algorithm | `project_host(...)`           |
| §14.1 ARA scholarly vs registry refs | `ara_rw_*` notes with `source_only` state |
| §16 Phase 0/1 (embedded resolver, no Gaia loader change) | `gaia.engine.packaging._load_embedded_package_modules` |
| §16 Phase 3 (register for embedded roots) | `gaia pkg register --locked` accepts `gaia.toml`+uuid + uploads `source_map.json` |

Still future work:

- §5.2 LLM-backed agent formalization (the deterministic surface and
  the `--auto-accept rule:action` interface are in place; the
  agent itself is a separate package);
- §11 fuzzy related-work → registry binding classification beyond
  `source_only` (current state machine ships only the exact-match
  and source_only states).
