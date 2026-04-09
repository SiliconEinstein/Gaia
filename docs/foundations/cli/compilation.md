---
status: current-canonical
layer: cli
since: v5-phase-1
---

# Compilation and Validation

This document describes the internals of `gaia compile` and `gaia check` -- the deterministic pipeline that transforms Python DSL source into Gaia IR.

## gaia compile

### Pipeline Overview

```
pyproject.toml
  --> load metadata (name, version, [tool.gaia])
    --> detect source layout (flat vs src/)
      --> dynamic import with fresh module cache
        --> DSL declarations auto-register to CollectedPackage via contextvars
          --> label inference from variable names
            --> compile: knowledge closure, QID assignment, strategy formalization
              --> compute ir_hash (canonical JSON + SHA-256)
                --> validate (errors abort, warnings report)
                  --> write .gaia/ir.json + .gaia/ir_hash
```

Source: `gaia/cli/commands/compile.py`

### Step 1: Load Package Metadata

`load_gaia_package()` in `gaia/cli/_packages.py` reads `pyproject.toml` and extracts:

- `[project].name` -- required, used to derive the Python import name
- `[project].version` -- required, becomes `CollectedPackage.version`
- `[tool.gaia].type` -- must be `"knowledge-package"` or the command aborts
- `[tool.gaia].namespace` -- optional, defaults to `"github"`

The Python import name is derived from the project name:

```
import_name = project_name.removesuffix("-gaia").replace("-", "_")
```

For example, project `galileo-falling-bodies-gaia` becomes import name `galileo_falling_bodies`.

**Layout detection:** the loader checks two candidate roots in order:

1. `{pkg_path}/{import_name}/` (flat layout)
2. `{pkg_path}/src/{import_name}/` (src layout)

The first root where the directory exists wins. If neither exists, the command aborts.

### Step 2: Execute DSL Module

The loader performs a fresh dynamic import of the package module (`gaia/cli/_packages.py:_import_fresh`):

1. **Evict stale modules** -- removes any previously cached modules matching the import name from `sys.modules`
2. **Invalidate bytecode** -- calls `importlib.invalidate_caches()` and sets `sys.dont_write_bytecode = True` during import
3. **Import** -- calls `importlib.import_module(import_name)`

Before import, the loader calls `reset_inferred_package()` to prime the callstack-based package registry (`gaia/lang/runtime/package.py`). This ensures DSL objects created during module execution register to the correct `CollectedPackage`.

**Auto-registration via contextvars:** each DSL dataclass (`Knowledge`, `Strategy`, `Operator` in `gaia/lang/runtime/nodes.py`) has a `__post_init__` that looks up the current `CollectedPackage` from the `_current_package` context variable. If set, the object registers itself immediately. If not set, it falls back to `infer_package_from_callstack()`, which walks the call stack to find the nearest non-`gaia.lang` module, locates its `pyproject.toml`, and loads (or retrieves) the corresponding `CollectedPackage`.

**Label inference** (`_assign_labels` in `gaia/cli/_packages.py`): after import completes, the loader scans module attributes to assign labels to unlabeled DSL objects:

- If `__all__` is defined and is a list of strings, only those names are scanned for `Knowledge` objects
- Otherwise, all non-underscore-prefixed attributes are scanned
- For `Strategy` objects, all non-underscore-prefixed attributes are always scanned (regardless of `__all__`)
- Only objects that belong to the current package (by identity) and have `label is None` receive a label from the variable name

### Step 3: Compile to IR

`compile_package_artifact()` in `gaia/lang/compiler/compile.py` transforms the `CollectedPackage` into a `LocalCanonicalGraph`.

#### Knowledge Closure

The compiler recursively collects all `Knowledge` nodes that must appear in the IR graph. This includes:

- All locally declared knowledge (`pkg.knowledge`)
- All premises, backgrounds, and conclusions referenced by strategies
- All variables and conclusions referenced by operators
- All variables and conclusions referenced by operators inside `formal_expr` on strategies
- Recursively, all knowledge referenced by sub-strategies

De-duplication is by Python object identity (`id()`). Foreign knowledge nodes (imported from another package) are included in the closure alongside local nodes.

#### QID Assignment

Each knowledge node receives a stable Qualified Node ID. The assignment logic (`_knowledge_id` in `gaia/lang/compiler/compile.py`) considers three cases:

| Case | QID Format | Example |
|------|-----------|---------|
| **Local, labeled** | `{namespace}:{package_name}::{label}` | `github:galileo_falling_bodies::vacuum_prediction` |
| **Local, anonymous** | `{namespace}:{package_name}::_anon_{counter:03d}` | `github:galileo_falling_bodies::_anon_000` |
| **Foreign (imported)** | Preserved from source package | `github:newton_principia::third_law` |

For foreign nodes, the compiler checks in order:

1. An explicit `qid` in `metadata` -- used as-is
2. The node's `_package` reference -- constructs QID from the foreign package's namespace and name
3. Fallback -- `external:anonymous::{normalized_label_or_content_hash}`

Anonymous counter is sequential per compilation, producing deterministic IDs for unlabeled local nodes.

QID format is defined in [Identity and Hashing](../gaia-ir/03-identity-and-hashing.md).

#### Named Strategy Formalization

When a strategy's `type` is one of the compile-time formal families (`deduction`, `elimination`, `mathematical_induction`, `case_analysis`, `abduction`, `analogy`, `extrapolation`), the compiler delegates to `formalize_named_strategy()` in `gaia/ir/formalize.py`.

This function:

1. Validates premise/conclusion arity for the strategy type
2. Generates intermediate helper claims (e.g., conjunction results, disjunction results) with deterministic QIDs using `__{role}_{hash8}` labels
3. For `abduction`, may auto-generate a public interface claim (`AlternativeExplanationForObs`) when only one premise (the observation) is provided
4. Builds the canonical `FormalExpr` (a list of `Operator` objects) encoding the reasoning skeleton
5. Returns a `FormalizationResult` containing both generated `Knowledge` nodes and the `FormalStrategy`

The generated knowledge nodes are appended to the graph alongside the original knowledge closure.

#### Strategy Compilation

Each strategy is compiled exactly once (memoized by Python object identity). The compiler dispatches on form:

| Form | Condition | IR Type |
|------|-----------|---------|
| **Composite** | `sub_strategies` is non-empty | `CompositeStrategy` with sub-strategy IDs |
| **Explicit formal** | `formal_expr` is set on the DSL object | `FormalStrategy` with user-provided operators |
| **Named formal** | `type` in compile-time formal set | `FormalStrategy` via `formalize_named_strategy()` |
| **Leaf** | None of the above | Base `Strategy` |

#### Operator Compilation

Top-level operators (those not embedded inside a strategy's `formal_expr`) are compiled with `operator_id` and `scope` set. The `operator_id` is a content-addressed hash:

```
operator_id = lco_{SHA-256(operator_type + sorted(variable_ids) + conclusion_id)[:16]}
```

Operators that appear inside a strategy's `formal_expr` are compiled without `operator_id` or `scope` (they are embedded, not top-level).

### Step 4: Compute IR Hash

The `LocalCanonicalGraph` model validator (`gaia/ir/graphs.py`) automatically computes `ir_hash` when it is `None`:

1. **Canonical JSON serialization** (`_canonical_json`): produces a deterministic JSON string independent of insertion order by:
   - Sorting knowledge nodes, operators, and strategies by their JSON representation
   - Sorting `parameters`, `provenance`, `premises`, `background`, and `sub_strategies` within each object
   - Sorting `variables` within commutative operators (equivalence, contradiction, complement, disjunction, conjunction)
   - Sorting operators within `formal_expr`

2. **Hash**: `sha256:{hex_digest}` of the canonical JSON UTF-8 bytes

The hash covers knowledges, operators, and strategies -- the full graph closure including foreign references.

Reference: [Identity and Hashing](../gaia-ir/03-identity-and-hashing.md) and [Canonicalization](../gaia-ir/05-canonicalization.md).

### Step 5: Validate and Write

The compile command runs `validate_local_graph()` (`gaia/ir/validator.py`) on the constructed `LocalCanonicalGraph`. The validator checks (see [Validation](../gaia-ir/08-validation.md) for the full contract):

**Knowledge checks:**
- All IDs are valid QID format
- No duplicate IDs or labels
- Local-layer nodes have content
- Graph namespace is a non-empty string

**Operator checks:**
- Top-level operators have `operator_id` (with `lco_` prefix) and `scope`
- All variables and conclusions reference existing claim-type knowledge
- Conclusion is not in variables

**Strategy checks:**
- Strategy IDs use `lcs_` prefix
- All premises/conclusions reference existing claim-type knowledge
- No self-loops (conclusion in premises)
- Composite sub-strategy references exist and form a DAG
- FormalExpr reference closure: all operator variables/conclusions reference strategy interface or sibling operator conclusions
- FormalExpr operators form a DAG
- Private FormalExpr nodes are not referenced by other strategies or top-level operators

**Graph-level checks:**
- All references use QID format
- `ir_hash` matches recomputed value

If validation produces errors, the command aborts with exit code 1. Warnings are printed but do not block compilation.

On success, `write_compiled_artifacts()` (`gaia/cli/_packages.py`) writes:

- `.gaia/ir.json` -- the full `LocalCanonicalGraph` serialized as indented, sorted-keys JSON
- `.gaia/ir_hash` -- the bare hash string
- `.gaia/compile_metadata.json` -- provenance of the compile run:
  - `gaia_lang_version` -- which `gaia-lang` produced the IR (`"unknown"` when running from an editable/unbuilt dev checkout)
  - `compiled_at` -- ISO-8601 UTC timestamp with second precision
  - `ir_hash` -- duplicated from `.gaia/ir_hash` so the metadata file is self-contained

`compile_metadata.json` is the authoritative source of truth for "which gaia-lang compiled this IR". It is intended to be committed to git alongside `ir.json` and `ir_hash`, and is read at register time to populate `Versions.toml`'s `gaia_lang_version` field. The metadata is deliberately decoupled from `ir.json` content: adding it to `ir.json` directly would change `ir_hash` across gaia versions even when the structural IR is identical, breaking the "same source → same hash" invariant.

Source: `gaia/cli/commands/compile.py`

## gaia check

`gaia check` validates that a package is well-formed and its compiled artifacts are current. It runs the full compilation pipeline in memory and compares against stored artifacts.

Source: `gaia/cli/commands/check.py`

### Validation Items

| # | Check | Pass Criteria | Severity |
|---|-------|--------------|----------|
| 1 | Project name convention | `project.name` ends with `"-gaia"` | Error |
| 2 | Package type | `[tool.gaia].type == "knowledge-package"` (checked during load) | Error |
| 3 | IR validator | `validate_local_graph()` reports no errors | Error (warnings allowed) |
| 4 | Stored ir_hash freshness | `.gaia/ir_hash` exists and matches recompiled hash | Error if stale |
| 5 | Stored ir.json consistency | `.gaia/ir.json` exists, is valid JSON, and its embedded `ir_hash` matches recompiled hash | Error if mismatched |
| 6 | Artifact presence | `.gaia/ir_hash` exists | Warning if missing |

If `.gaia/ir_hash` does not exist, check reports a warning (artifacts missing, run `gaia compile`). If it exists but does not match the recompiled value, check reports an error (artifacts stale, run `gaia compile` again).

## Determinism Guarantee

The same source code always produces the same `ir_hash`, provided the package's DSL declarations are side-effect-free (no network calls, no randomness, no environment-dependent logic). The compiler itself introduces no non-determinism:

- **No LLM calls** -- compilation is purely mechanical
- **No network access** -- all inputs are local files
- **No randomness** -- no random number generation anywhere in the pipeline
- **Deterministic IDs** -- QIDs are derived from (namespace, package_name, label); anonymous IDs use sequential counters in stable iteration order; strategy and operator IDs are content-addressed hashes
- **Canonical serialization** -- JSON output is sorted at every level, making `ir_hash` independent of Python dict ordering or object creation order
- **Bytecode suppression** -- `sys.dont_write_bytecode = True` during import prevents stale `.pyc` interference

This determinism is what makes `gaia check` possible: recompiling from source must reproduce the exact same IR hash as a previous `gaia compile` run, as long as the source has not changed.
