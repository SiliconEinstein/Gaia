# Typst → Graph IR Compiler Design

**Date:** 2026-03-19
**Scope:** Replace YAML compilation pipeline with Typst-native Graph IR compilation; clean up all YAML-era code.

## Motivation

The current codebase has two compilation paths:

1. **YAML path (main)**: YAML → `lang_models.Package` → `build_raw_graph()` → `RawGraph` → `LocalCanonicalGraph` → Factor Graph → BP
2. **Typst path (feat/typst-gaia-lang-poc)**: Typst → `typst.query()` → JSON `{nodes, factors, constraints}` — stops at flat JSON, doesn't produce Graph IR

The Typst language is the sole authoring surface going forward. The YAML path is legacy and should be removed entirely. This design bridges the gap: a compiler that takes Typst loader output and produces Graph IR, plus cleanup of all YAML-era code. Both the v3 (string-based) and v4 (label-based) Typst formats are supported, with v4 as the primary path.

## Design Principles

1. **Typst layer emits everything it naturally knows** — module names per node, package/version at top level. Python only does what Typst shouldn't care about (content flattening, deterministic ID hashing, Pydantic model construction).
2. **Separation of concerns** — `typst_loader` handles Typst format details, `typst_compiler` handles Graph IR semantics. The loader's dict output is also consumed by `proof_state.py` and `typst_renderer.py`.
3. **Shared IR backend** — `build_singleton_local_graph()`, ID generation utils, and everything downstream of `RawGraph` are source-agnostic and preserved as-is.

## Architecture

### Compilation Pipeline

```
.typ source files
  ↓
  ├── v4 path: typst.query("figure.where(kind: \"gaia-node\")")
  │     ↓ typst_loader.load_typst_package_v4()
  │     clean Python dict (nodes with external flag, "premises" plural, constraints)
  │     ↓ typst_compiler.compile_v4_to_raw_graph()
  │
  └── v3 fallback: typst.query("<gaia-graph>")
        ↓ typst_loader.load_typst_package()
        clean Python dict (module per node, "premise" singular)
        ↓ typst_compiler.compile_typst_to_raw_graph()
  │
RawGraph
  ↓ build_utils.build_singleton_local_graph()
LocalCanonicalGraph
  ↓ [review stage assigns π, p]
  ↓ adapter.adapt_local_graph_to_factor_graph()
FactorGraph → BP → beliefs
```

`pipeline_build()` tries v4 first; if no v4 nodes are found, it falls back to v3.

### File Structure (post-cleanup)

Note: files marked "from POC worktree" currently exist only in `.worktrees/typst-gaia-lang-poc/` and must be merged before implementation.

```
libs/
  lang/
    typst_loader.py          # Typst → clean dict (from POC worktree, minor changes)
    proof_state.py           # hole detection (from POC worktree, unchanged)
    typst_renderer.py        # dict → Markdown (from POC worktree, unchanged)
    typst_clean_renderer.py  # clean Markdown rendering (from POC worktree, unchanged)
  graph_ir/
    models.py                # RawGraph, FactorNode, SourceRef etc. (existing, unchanged)
    typst_compiler.py        # dict → RawGraph (NEW)
    build_utils.py           # ID generation, build_singleton_local_graph(), CanonicalizationResult (extracted from old build.py)
    adapter.py               # LocalCanonicalGraph → FactorGraph (existing, unchanged)
    serialize.py             # JSON save/load for Graph IR artifacts (existing, unchanged)
  inference/
    factor_graph.py          # FactorGraph model (existing, unchanged)
    bp.py                    # Belief Propagation (existing, unchanged)
  pipeline.py               # pipeline_build/review/infer/publish (existing, rewritten)
```

### Module Boundary Rules

- `lang/` knows Typst only, does not depend on `graph_ir/`
- `graph_ir/` does not know Typst, accepts dict or operates on its own Pydantic models
- `inference/` knows only `FactorGraph`, nothing upstream

## Typst Layer Changes

### `declarations.typ` — add module field to nodes

`_register_node()` includes the current module name in each node entry:

```typst
_gaia_nodes.update(nodes => {
  nodes.push((
    name: name,
    type: type,
    content: body,
    module: _gaia_module_name.get(),    // NEW
  ))
  nodes
})
```

### `module.typ` — add package-level metadata to export-graph()

`export-graph()` outputs `package` and `version` at the top level (from `typst.toml` or `#package()` call):

```typst
#let export-graph() = context {
  metadata((
    package: pkg_name,
    version: pkg_version,
    nodes: _gaia_nodes.final(),       // each node now has module field
    factors: ...,
    constraints: ...,
  )) <gaia-graph>
}
```

Python constructs `SourceRef(package, version, module, knowledge_name)` from these fields.

## typst_compiler.py — Core Compilation Logic

New file: `libs/graph_ir/typst_compiler.py`

```python
def compile_typst_to_raw_graph(graph_data: dict) -> RawGraph:
    """Compile typst_loader output dict to RawGraph."""
```

### Input format (from typst_loader)

```python
{
    "package": "galileo_falling_bodies",
    "version": "0.1.0",
    "nodes": [
        {"name": "vacuum_prediction", "type": "claim", "content": "...", "module": "galileo"},
        ...
    ],
    "factors": [
        {"type": "reasoning", "premise": ["a", "b"], "conclusion": "c"},
        ...
    ],
    "constraints": [
        {"name": "tied_balls_contradiction", "type": "contradiction", "between": ["x", "y"]},
        ...
    ],
}
```

### Compilation steps

1. **Nodes → RawKnowledgeNode**
   - `raw_node_id` = SHA256(package, version, module, name, type, kind, content, parameters) — matches existing hash convention in `_raw_node_id()`
   - `knowledge_type` = node type (claim, observation, setting, question, contradiction, equivalence)
   - `kind` = `None` for most types; reserved for future use (e.g., action subtypes)
   - `source_refs` = `[SourceRef(package, version, module, name)]`
   - `parameters` = `[]` (future extension — schema parameter mechanism not yet designed)
   - `metadata` = `{"between": [...]}` for constraint nodes
   - Build `name → raw_node_id` mapping table

2. **Factors → FactorNode(type="reasoning")**
   - `premises` / `conclusion` resolved via name→raw_node_id mapping
   - `factor_id` = SHA256("reasoning", module, conclusion_name)
   - `source_ref` = SourceRef pointing to the conclusion
   - `contexts` = `[]` (v3 has no indirect dependencies)
   - `metadata` = `{"edge_type": "deduction"}` (default; future: infer from proof prose)

3. **Constraints → FactorNode(type="mutex_constraint" | "equiv_constraint")**
   - `premises` = between node IDs
   - `conclusion` = constraint node's own ID
   - `contexts` = `[]`
   - `factor_id` = SHA256(factor_type, module, constraint_name)
   - `metadata` = `{"edge_type": "relation_contradiction"}` or `"relation_equivalence"`

### Output

`RawGraph(package, version, knowledge_nodes, factor_nodes)`

## v4 Compilation Path (`compile_v4_to_raw_graph`)

The v4 Typst language (label-based DSL with `gaia-bibliography`) introduces a second compilation function: `compile_v4_to_raw_graph()` in `libs/graph_ir/typst_compiler.py`. `pipeline_build()` tries the v4 loader first and falls back to v3 if no v4 nodes are found.

### Key differences from v3

| Aspect | v3 (`compile_typst_to_raw_graph`) | v4 (`compile_v4_to_raw_graph`) |
|--------|----------------------------------|-------------------------------|
| Premise key in factors | `"premise"` (singular) | `"premises"` (plural) |
| Constraint source | Inline constraint data on nodes | Separate `"constraints"` list; relation nodes have `type: "relation"` resolved via constraint map |
| External nodes | Not supported | `ext:` prefix IDs (`ext:{package}/{node}`); external nodes carry `external: true` flag and preserve content |
| Module assignment | Per-node `"module"` field from Typst | Hardcoded `"default"` (v4 packages are single-module) |
| Node kind | Always `None` | Preserved from loader (`node.get("kind")`) |

### v4 input format (from `load_typst_package_v4`)

```python
{
    "package": "galileo_falling_bodies",
    "version": "0.1.0",
    "nodes": [
        {"name": "vacuum_prediction", "type": "claim", "content": "...", "external": False},
        {"name": "prior_result", "type": "claim", "content": "...",
         "external": True, "ext_package": "newton_principia", "ext_node": "equal_fall"},
    ],
    "factors": [
        {"type": "reasoning", "premises": ["a", "b"], "conclusion": "c"},
    ],
    "constraints": [
        {"name": "tied_balls_contradiction", "type": "contradiction", "between": ["x", "y"]},
    ],
}
```

### v4 compilation steps

1. **Local nodes** — Same as v3 except: module is always `"default"`, `kind` is preserved, and relation nodes resolve `knowledge_type` from the constraint map (`constraint_map[name]["type"]`).

2. **External nodes** — Nodes with `external: true` are compiled with `raw_node_id = "ext:{ext_package}/{ext_node}"`. Their content is preserved in a `RawKnowledgeNode` with `source_refs` pointing to the external package. Metadata includes `ext_package`, `ext_version`, and `ext_node`. External nodes participate as premises in factors but are not materialized as local Knowledge during publish.

3. **Reasoning factors** — Uses `factor_data.get("premises", [])` (plural). Otherwise identical to v3.

4. **Constraint factors** — Same as v3, with a guard: `if len(related_ids) < 2: continue` (skip constraints that reference fewer than 2 resolved nodes).

### v4 loader fallback in `pipeline_build()`

```python
try:
    graph_data = load_typst_package_v4(pkg_path)
    if not graph_data["nodes"]:
        raise ValueError("No v4 nodes found")
except Exception:
    graph_data = load_typst_package(pkg_path)          # v3 fallback
    raw_graph = compile_typst_to_raw_graph(graph_data)
else:
    raw_graph = compile_v4_to_raw_graph(graph_data)    # v4 path
```

## Pipeline Rewrite

### pipeline_build()

```python
async def pipeline_build(pkg_path: Path) -> BuildResult:
    # Tries v4 loader first, falls back to v3 (see above)
    graph_data = load_typst_package_v4(pkg_path)  # or load_typst_package()
    raw_graph = compile_v4_to_raw_graph(graph_data)  # or compile_typst_to_raw_graph()
    canonicalization = build_singleton_local_graph(raw_graph)
    source_files = {p.name: p.read_text() for p in pkg_path.glob("*.typ")}
    return BuildResult(...)
```

### BuildResult simplification

```python
@dataclass
class BuildResult:
    graph_data: dict                    # typst_loader output (for renderer, proof_state)
    raw_graph: RawGraph
    local_graph: LocalCanonicalGraph
    canonicalization_log: list
    source_files: dict[str, str]
```

Removed: `package: lang_models.Package`, `elaborated: ElaboratedPackage`, `markdown: str`.

### derive_local_parameterization()

No longer called at build time. In v3, priors (π) and conditional probabilities (p) come from the review stage, not from source declarations. `pipeline_infer()` constructs parameterization from review results.

### Downstream pipeline functions

Removing `lang_models.Package` breaks `pipeline_review()`, `pipeline_infer()`, and `pipeline_publish()`. These must be rewritten as part of this work.

**pipeline_review()** — currently uses `build.package.name` and `build.markdown`:
- `package.name` → use `build.graph_data["package"]` instead
- `markdown` → render on demand from `graph_data` via `typst_renderer`
- `ReviewResult.merged_package` → replace with a new `ReviewOutput` that holds priors (π per node) and conditional probabilities (p per factor), without depending on `lang_models.Package`

**pipeline_infer()** — currently calls `derive_local_parameterization(review.merged_package, build.local_graph)`:
- Rewrite `derive_local_parameterization()` to accept `ReviewOutput` (π, p values) + `LocalCanonicalGraph` instead of `lang_models.Package`
- The function itself (ID mapping, default priors) is simple; it's only the input type that changes

**pipeline_publish()** — currently calls `convert_to_storage(pkg=review.merged_package, ...)`:
- `cli/lang_to_storage.py` must be rewritten to convert from `LocalCanonicalGraph` + `ReviewOutput` to storage models, instead of from `lang_models.Package`
- This is the most significant rewrite — the current converter traverses `lang_models.Knowledge`, `ChainExpr`, etc.

## YAML Cleanup

### Phasing

The cleanup is split into two phases:

**Phase 1 (this spec)**: Build the Typst → Graph IR compiler and rewrite `pipeline_build()`. This is self-contained and testable.

**Phase 2 (follow-up)**: Rewrite downstream pipeline functions (review/infer/publish), rewrite `cli/lang_to_storage.py`, then delete all YAML-era code. Phase 2 depends on Phase 1 being complete and tested.

### Delete (Phase 2)

| File | Reason |
|------|--------|
| `libs/lang/loader.py` | YAML loader |
| `libs/lang/resolver.py` | Cross-module ref resolution (Typst handles natively) |
| `libs/lang/elaborator.py` | Parameter expansion (future extension) |
| `libs/lang/compiler.py` | Old factor graph compiler |
| `libs/lang/models.py` | YAML-era data models |
| `libs/lang/build_store.py` | YAML → Markdown rendering |
| `libs/lang/runtime.py` | YAML runtime, depends on loader/resolver/compiler |
| `libs/lang/executor.py` | Action executor, depends on lang models |
| `libs/graph_ir/build.py` | Old `build_raw_graph()`, depends on `lang_models` |
| `cli/lang_to_storage.py` | Converter from lang models to storage (rewritten in Phase 2) |
| `cli/review_store.py` | Review merge logic using `lang_models.Package` |
| `cli/manifest.py` | Package serialization using lang models |
| `cli/commands/lang.py` | CLI commands using YAML runtime |
| YAML test fixtures + tests | All corresponding tests |

### Preserve (extract from build.py → build_utils.py)

- `build_singleton_local_graph()` + `CanonicalizationResult` — operates on `RawGraph`, source-agnostic
- `_raw_node_id()` / `_local_canonical_id()` / `_factor_id()` — deterministic ID generation
- `_extract_parameters()` — placeholder extraction (for future use)

### Preserve (unchanged)

- `libs/graph_ir/serialize.py` — JSON save/load for Graph IR, depends only on `graph_ir.models`

### Move to future/

- `libs/lang/plausible_core.py` — fine-grained formalization exploration, not needed now
- `tests/libs/lang/test_plausible_core.py` — corresponding tests

## Future Extensions

- **Schema parameter mechanism** — `#claim` with parameterized content `{X}`, Typst-side extraction
- **Cross-package `#use` resolution** — resolve references across packages
- **Incremental build** — use `source_ref` + content hash for change detection
