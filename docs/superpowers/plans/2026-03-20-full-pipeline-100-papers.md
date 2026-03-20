# Full Pipeline: 100 Papers End-to-End Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run 100 papers through the complete pipeline: XML → Typst → Graph IR → Local BP → Global Canonicalize → Persist to DB → Curation (from DB) → Global BP (from DB), with local file backups at each stage.

**Architecture:** The pipeline has 7 stages. Stages 1-4 are file-based (Typst packages → Graph IR JSON). Stage 5 persists to LanceDB + Graph DB via StorageManager. Stages 6-7 are DB-native: read from DB, process, write back. A new `graph_ir_to_storage.py` converter replaces the old YAML-based `cli/lang_to_storage.py`. An end-to-end `run_full_pipeline.py` script wraps all stages.

**Tech Stack:** Python 3.12, Pydantic v2, LanceDB, Kuzu, typst (Python binding), asyncio

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/pipeline/build_graph_ir.py` | **Modify**: add Typst path (detect typst.toml → use typst_loader + typst_compiler) |
| `libs/graph_ir/storage_converter.py` | **Create**: Graph IR → storage models converter (replaces `cli/lang_to_storage.py` for Typst path) |
| `scripts/pipeline/persist_to_db.py` | **Create**: persist packages + global graph to LanceDB + Graph DB via StorageManager |
| `scripts/pipeline/run_curation_db.py` | **Create**: curation that reads from DB, processes, writes back |
| `scripts/pipeline/run_global_bp_db.py` | **Create**: global BP that reads from DB, runs BP, writes beliefs back |
| `scripts/pipeline/run_full_pipeline.py` | **Create**: end-to-end orchestrator for all 7 stages |
| `tests/libs/graph_ir/test_storage_converter.py` | **Create**: tests for Graph IR → storage conversion |

### Archive (move, don't delete)
| File | Action |
|------|--------|
| `cli/lang_to_storage.py` | Move to `archive/cli/lang_to_storage.py` |
| `scripts/ingest.py` | Move to `archive/scripts/ingest.py` |
| `scripts/xml_to_yaml.py` | Move to `archive/scripts/xml_to_yaml.py` |

---

## Chunk 1: Build Graph IR — Typst Path

### Task 1: Adapt `build_graph_ir.py` to support Typst packages

Currently `build_graph_ir.py` only handles YAML packages (`load_package`). Need to detect Typst packages (have `typst.toml` instead of `package.yaml`) and route through `typst_loader` → `typst_compiler`.

**Files:**
- Modify: `scripts/pipeline/build_graph_ir.py`
- Read: `libs/lang/typst_loader.py`, `libs/graph_ir/typst_compiler.py`

- [ ] **Step 1: Write a test for the Typst path**

Create `tests/scripts/test_build_graph_ir_typst.py` that runs `build_package_graph_ir` on an existing Typst fixture package and asserts graph_ir/ outputs are generated.

```python
from pathlib import Path
from scripts.pipeline.build_graph_ir import build_package_graph_ir

def test_build_graph_ir_typst(tmp_path):
    """Typst packages (typst.toml) should produce graph_ir/ outputs."""
    # Use an existing Typst fixture or create a minimal one
    # Assert graph_ir/raw_graph.json, local_canonical_graph.json, local_parameterization.json exist
    pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/scripts/test_build_graph_ir_typst.py -v`
Expected: FAIL

- [ ] **Step 3: Modify `build_graph_ir.py` to detect and handle Typst packages**

In `build_package_graph_ir()`, detect `typst.toml` vs `package.yaml`:

```python
def build_package_graph_ir(pkg_dir: Path) -> bool:
    typst_toml = pkg_dir / "typst.toml"
    package_yaml = pkg_dir / "package.yaml"

    if typst_toml.exists():
        return _build_from_typst(pkg_dir)
    elif package_yaml.exists():
        return _build_from_yaml(pkg_dir)
    else:
        print(f"  SKIP: no typst.toml or package.yaml in {pkg_dir.name}")
        return False


def _build_from_typst(pkg_dir: Path) -> bool:
    from libs.lang.typst_loader import load_typst_package
    from libs.graph_ir.typst_compiler import compile_typst_to_raw_graph
    from libs.graph_ir.build import build_singleton_local_graph, derive_local_parameterization_from_raw

    graph_data = load_typst_package(pkg_dir)
    raw_graph = compile_typst_to_raw_graph(graph_data)
    result = build_singleton_local_graph(raw_graph)
    local_graph = result.local_graph
    # derive_local_parameterization needs adaptation for non-YAML input
    # Use raw_graph + local_graph to derive priors
    params = derive_local_parameterization_from_raw(raw_graph, local_graph)

    # Write outputs (same as YAML path)
    graph_dir = pkg_dir / "graph_ir"
    graph_dir.mkdir(exist_ok=True)
    # ... write raw_graph.json, local_canonical_graph.json, etc.
    return True


def _build_from_yaml(pkg_dir: Path) -> bool:
    # Current implementation moved here
    ...
```

**Note:** `derive_local_parameterization` currently takes `libs.lang.models.Package` (YAML model). For Typst path, we need a variant that works from RawGraph + node metadata. Check if the existing function can be adapted or if a new `derive_local_parameterization_from_raw()` is needed.

- [ ] **Step 4: Check `derive_local_parameterization` compatibility**

Read `libs/graph_ir/build.py::derive_local_parameterization` to understand what it needs from the Package object. Determine if we need a new function or can adapt.

Key question: Does it only need node priors (which are in the Typst graph_data nodes), or does it need more from the Package model?

- [ ] **Step 5: Implement `derive_local_parameterization_from_raw` if needed**

If the existing function can't be reused, add a new function in `libs/graph_ir/build.py`:

```python
def derive_local_parameterization_from_raw(
    raw_graph: RawGraph,
    local_graph: LocalCanonicalGraph,
) -> LocalParameterization:
    """Derive parameterization from raw graph data (no YAML Package needed)."""
    node_priors = {}
    for node in local_graph.knowledge_nodes:
        # Find matching raw node to get prior from metadata
        for raw_node in raw_graph.knowledge_nodes:
            if raw_node.raw_node_id in node.member_raw_node_ids:
                prior = (raw_node.metadata or {}).get("prior", _default_prior(node.knowledge_type))
                node_priors[node.local_canonical_id] = prior
                break
        else:
            node_priors[node.local_canonical_id] = _default_prior(node.knowledge_type)

    factor_parameters = _derive_factor_params(local_graph, node_priors)
    return LocalParameterization(
        graph_hash=local_graph.graph_hash(),
        node_priors=node_priors,
        factor_parameters=factor_parameters,
    )
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/scripts/test_build_graph_ir_typst.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/pipeline/build_graph_ir.py libs/graph_ir/build.py tests/scripts/test_build_graph_ir_typst.py
git commit -m "feat: support Typst packages in build_graph_ir.py"
```

---

## Chunk 2: Graph IR → Storage Converter

### Task 2: Create `libs/graph_ir/storage_converter.py`

This replaces `cli/lang_to_storage.py` for the Typst path. Converts Graph IR outputs (LocalCanonicalGraph + LocalParameterization + local_beliefs) into storage models that `StorageManager.ingest_package()` accepts.

**Files:**
- Create: `libs/graph_ir/storage_converter.py`
- Create: `tests/libs/graph_ir/test_storage_converter.py`
- Read: `libs/storage/models.py` (target models)
- Read: `libs/graph_ir/models.py` (source models)

**Mapping:**

| Graph IR | Storage Model | Notes |
|----------|--------------|-------|
| `LocalCanonicalNode` | `Knowledge` | `knowledge_id = "{package}/{knowledge_name}"`, `content = representative_content`, `type = knowledge_type` |
| `graph_ir.FactorNode` | `storage.FactorNode` | Type mapping: `reasoning` → `infer`, `mutex_constraint` → `contradiction`, `equiv_constraint` → `equivalence` |
| `LocalParameterization.node_priors[id]` | `Knowledge.prior` | Direct mapping |
| `local_beliefs.json` | `BeliefSnapshot` | One per knowledge node |
| `typst.toml` metadata | `Package` | `package_id`, `name`, `version` |
| Module names from Typst graph_data | `Module` | One per module in the package |

- [ ] **Step 1: Write failing test for storage converter**

```python
# tests/libs/graph_ir/test_storage_converter.py
from libs.graph_ir.storage_converter import convert_graph_ir_to_storage
from libs.graph_ir.models import (
    LocalCanonicalGraph, LocalCanonicalNode, LocalParameterization,
    FactorNode, FactorParams, SourceRef,
)


def test_basic_conversion():
    lcg = LocalCanonicalGraph(
        package="test_pkg", version="1.0.0",
        knowledge_nodes=[
            LocalCanonicalNode(
                local_canonical_id="lcn_abc",
                package="test_pkg",
                knowledge_type="setting",
                representative_content="Test premise",
                source_refs=[SourceRef(package="test_pkg", version="1.0.0",
                                       module="setting", knowledge_name="test_premise")],
            ),
            LocalCanonicalNode(
                local_canonical_id="lcn_def",
                package="test_pkg",
                knowledge_type="claim",
                representative_content="Test conclusion",
                source_refs=[SourceRef(package="test_pkg", version="1.0.0",
                                       module="reasoning", knowledge_name="test_conclusion")],
            ),
        ],
        factor_nodes=[
            FactorNode(
                factor_id="f_001",
                type="reasoning",
                premises=["lcn_abc"],
                conclusion="lcn_def",
                source_ref=SourceRef(package="test_pkg", version="1.0.0",
                                     module="reasoning", knowledge_name="test_conclusion"),
            ),
        ],
    )
    params = LocalParameterization(
        graph_hash=lcg.graph_hash(),
        node_priors={"lcn_abc": 0.9, "lcn_def": 0.5},
        factor_parameters={"f_001": FactorParams(conditional_probability=0.8)},
    )
    beliefs = {"lcn_abc": 0.85, "lcn_def": 0.65}

    result = convert_graph_ir_to_storage(lcg, params, beliefs, bp_run_id="bp_001")

    assert result.package.package_id == "test_pkg"
    assert len(result.knowledge_items) == 2
    assert len(result.factors) >= 1
    assert len(result.belief_snapshots) == 2
    # Check knowledge priors match parameterization
    k_map = {k.knowledge_id: k for k in result.knowledge_items}
    assert k_map["test_pkg/test_premise"].prior == 0.9
    assert k_map["test_pkg/test_conclusion"].prior == 0.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/graph_ir/test_storage_converter.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement `libs/graph_ir/storage_converter.py`**

```python
"""Convert Graph IR (LocalCanonicalGraph + LocalParameterization) to storage models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

from libs.graph_ir.models import (
    LocalCanonicalGraph,
    LocalParameterization,
    FactorNode as GraphIRFactorNode,
)
from libs.storage import models as storage


# Graph IR factor type → storage factor type
_FACTOR_TYPE_MAP = {
    "reasoning": "infer",
    "infer": "infer",
    "abstraction": "abstraction",
    "instantiation": "instantiation",
    "mutex_constraint": "contradiction",
    "equiv_constraint": "equivalence",
    "contradiction": "contradiction",
    "equivalence": "equivalence",
}


@dataclass
class GraphIRIngestData:
    """Result of converting Graph IR to storage models."""
    package: storage.Package
    modules: list[storage.Module] = field(default_factory=list)
    knowledge_items: list[storage.Knowledge] = field(default_factory=list)
    chains: list[storage.Chain] = field(default_factory=list)
    factors: list[storage.FactorNode] = field(default_factory=list)
    belief_snapshots: list[storage.BeliefSnapshot] = field(default_factory=list)
    probabilities: list[storage.ProbabilityRecord] = field(default_factory=list)


def convert_graph_ir_to_storage(
    lcg: LocalCanonicalGraph,
    params: LocalParameterization,
    beliefs: dict[str, float] | None = None,
    bp_run_id: str = "local_bp",
) -> GraphIRIngestData:
    now = datetime.now(timezone.utc)
    pkg_name = lcg.package
    pkg_version = lcg.version

    # 1. Package
    storage_package = storage.Package(
        package_id=pkg_name,
        name=pkg_name,
        version=pkg_version,
        submitter="pipeline",
        submitted_at=now,
        status="merged",
    )

    # 2. Discover modules from source_refs
    module_names: set[str] = set()
    for node in lcg.knowledge_nodes:
        for sr in node.source_refs:
            module_names.add(sr.module)

    storage_modules = []
    for mod_name in sorted(module_names):
        storage_modules.append(storage.Module(
            module_id=f"{pkg_name}.{mod_name}",
            package_id=pkg_name,
            package_version=pkg_version,
            name=mod_name,
            role="reasoning",  # default; could infer from module name
        ))
    storage_package.modules = [m.module_id for m in storage_modules]

    # 3. Knowledge nodes
    # Map local_canonical_id → knowledge_id for factor conversion
    lcn_to_kid: dict[str, str] = {}
    storage_knowledge = []
    for node in lcg.knowledge_nodes:
        # knowledge_id = "{package}/{knowledge_name}" using first source_ref
        if node.source_refs:
            k_name = node.source_refs[0].knowledge_name
            module_name = node.source_refs[0].module
        else:
            k_name = node.local_canonical_id
            module_name = "unknown"

        knowledge_id = f"{pkg_name}/{k_name}"
        lcn_to_kid[node.local_canonical_id] = knowledge_id

        prior = params.node_priors.get(node.local_canonical_id, 0.5)
        prior = max(prior, 1e-6)
        prior = min(prior, 1.0)

        # Map knowledge_type to storage type
        k_type = node.knowledge_type
        if k_type not in ("claim", "question", "setting", "action", "contradiction", "equivalence"):
            k_type = "claim"

        storage_knowledge.append(storage.Knowledge(
            knowledge_id=knowledge_id,
            version=1,
            type=k_type,
            kind=node.kind,
            content=node.representative_content,
            parameters=[storage.Parameter(name=p.name, constraint=p.constraint) for p in node.parameters],
            prior=prior,
            keywords=[],
            source_package_id=pkg_name,
            source_package_version=pkg_version,
            source_module_id=f"{pkg_name}.{module_name}",
            created_at=now,
        ))

    storage_package.exports = [
        k.knowledge_id for k in storage_knowledge if k.type == "claim"
    ]

    # 4. Factors (Graph IR → storage)
    storage_factors = []
    for gf in lcg.factor_nodes:
        storage_type = _FACTOR_TYPE_MAP.get(gf.type, "infer")
        # Remap premise/conclusion IDs from local_canonical_id → knowledge_id
        premises_kid = [lcn_to_kid[p] for p in gf.premises if p in lcn_to_kid]
        conclusion_kid = lcn_to_kid.get(gf.conclusion) if gf.conclusion else None

        storage_factors.append(storage.FactorNode(
            factor_id=gf.factor_id,
            type=storage_type,
            premises=premises_kid,
            contexts=[lcn_to_kid.get(c, c) for c in gf.contexts],
            conclusion=conclusion_kid,
            package_id=pkg_name,
            source_ref=storage.SourceRef(
                package=gf.source_ref.package,
                version=gf.source_ref.version,
                module=gf.source_ref.module,
                knowledge_name=gf.source_ref.knowledge_name,
            ) if gf.source_ref else None,
            metadata=gf.metadata,
        ))

    # 5. Beliefs
    storage_beliefs = []
    if beliefs:
        for lcn_id, belief_value in beliefs.items():
            kid = lcn_to_kid.get(lcn_id)
            if kid is None:
                continue
            storage_beliefs.append(storage.BeliefSnapshot(
                knowledge_id=kid,
                version=1,
                belief=max(0.0, min(1.0, belief_value)),
                bp_run_id=bp_run_id,
                computed_at=now,
            ))

    return GraphIRIngestData(
        package=storage_package,
        modules=storage_modules,
        knowledge_items=storage_knowledge,
        factors=storage_factors,
        belief_snapshots=storage_beliefs,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/libs/graph_ir/test_storage_converter.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add libs/graph_ir/storage_converter.py tests/libs/graph_ir/test_storage_converter.py
git commit -m "feat: add Graph IR to storage model converter"
```

---

## Chunk 3: Persist to DB Script

### Task 3: Create `scripts/pipeline/persist_to_db.py`

Reads Graph IR outputs from each package + global graph, writes to LanceDB + Graph DB via StorageManager.

**Files:**
- Create: `scripts/pipeline/persist_to_db.py`
- Read: `libs/storage/manager.py`, `libs/storage/config.py`
- Read: `libs/graph_ir/storage_converter.py` (from Task 2)

**What it persists:**
1. **Per-package**: Package + Modules + Knowledge + Factors + Beliefs (from local_beliefs.json)
2. **Global**: CanonicalBindings + GlobalCanonicalNodes + GlobalInferenceState (from global_graph.json)

- [ ] **Step 1: Implement persist_to_db.py**

```python
#!/usr/bin/env python3
"""Persist Graph IR packages + global graph to LanceDB + Graph DB.

Reads each package's graph_ir/ outputs + global_graph.json,
writes to storage via StorageManager.

Usage:
    python scripts/pipeline/persist_to_db.py \
        --packages-dir output_typst \
        --global-graph-dir global_graph \
        --db-path ./data/lancedb/gaia

Saves local JSON backups alongside DB writes for debugging.
"""

import argparse, asyncio, json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from libs.graph_ir.models import LocalCanonicalGraph, LocalParameterization
from libs.graph_ir.storage_converter import convert_graph_ir_to_storage
from libs.global_graph.serialize import load_global_graph
from libs.storage.config import StorageConfig
from libs.storage.manager import StorageManager


async def persist_packages(packages_dir: Path, db_path: str, graph_backend: str) -> int:
    config = StorageConfig(lancedb_path=db_path, graph_backend=graph_backend)
    mgr = StorageManager(config)
    await mgr.initialize()

    succeeded = 0
    for pkg_dir in sorted(packages_dir.iterdir()):
        graph_ir_dir = pkg_dir / "graph_ir"
        lcg_path = graph_ir_dir / "local_canonical_graph.json"
        params_path = graph_ir_dir / "local_parameterization.json"
        beliefs_path = graph_ir_dir / "local_beliefs.json"

        if not lcg_path.exists():
            continue

        lcg = LocalCanonicalGraph.model_validate_json(lcg_path.read_text())
        params = LocalParameterization.model_validate_json(params_path.read_text())
        beliefs = {}
        if beliefs_path.exists():
            beliefs_data = json.loads(beliefs_path.read_text())
            beliefs = beliefs_data.get("node_beliefs", {})

        data = convert_graph_ir_to_storage(lcg, params, beliefs)

        # Save local JSON backup
        backup_dir = graph_ir_dir / "storage_backup"
        backup_dir.mkdir(exist_ok=True)
        (backup_dir / "package.json").write_text(
            json.dumps(data.package.model_dump(mode="json"), indent=2, ensure_ascii=False)
        )
        (backup_dir / "knowledge.json").write_text(
            json.dumps([k.model_dump(mode="json") for k in data.knowledge_items], indent=2, ensure_ascii=False)
        )
        (backup_dir / "factors.json").write_text(
            json.dumps([f.model_dump(mode="json") for f in data.factors], indent=2, ensure_ascii=False)
        )

        # Write to DB
        await mgr.ingest_package(
            package=data.package,
            modules=data.modules,
            knowledge_items=data.knowledge_items,
            chains=data.chains,
            factors=data.factors,
        )
        if data.belief_snapshots:
            await mgr.write_beliefs(data.belief_snapshots)

        print(f"  OK {pkg_dir.name}: {len(data.knowledge_items)} knowledge, {len(data.factors)} factors")
        succeeded += 1

    await mgr.close()
    return succeeded


async def persist_global_graph(global_graph_dir: Path, db_path: str, graph_backend: str) -> None:
    config = StorageConfig(lancedb_path=db_path, graph_backend=graph_backend)
    mgr = StorageManager(config)
    await mgr.initialize()

    gg = load_global_graph(global_graph_dir / "global_graph.json")

    # Write canonical bindings + global nodes
    # Convert global_graph.models → storage.models
    from libs.storage.models import CanonicalBinding, GlobalCanonicalNode as StorageGCN
    # ... conversion logic
    await mgr.write_canonical_bindings(bindings, global_nodes)

    # Write global inference state
    if gg.inference_state and gg.inference_state.node_beliefs:
        await mgr.update_inference_state(gg.inference_state)

    await mgr.close()
```

- [ ] **Step 2: Test persist_to_db.py manually on a small fixture**

Run: `python scripts/pipeline/persist_to_db.py --packages-dir tests/fixtures/gaia_language_packages --db-path ./data/test_lancedb --graph-backend kuzu`

- [ ] **Step 3: Verify data was written by querying**

Run: `python scripts/query_lance.py` or start the API server and check via browser.

- [ ] **Step 4: Commit**

```bash
git add scripts/pipeline/persist_to_db.py
git commit -m "feat: add persist_to_db.py — write Graph IR to LanceDB + Graph DB"
```

---

## Chunk 4: DB-Native Curation

### Task 4: Create `scripts/pipeline/run_curation_db.py`

Reads global graph data from DB (via StorageManager), runs the 6-step curation pipeline, writes results back to DB.

**Files:**
- Create: `scripts/pipeline/run_curation_db.py`
- Read: `scripts/smoke_curation.py` (reference implementation)
- Read: `libs/curation/` (all curation modules)
- Read: `libs/storage/manager.py` (read/write APIs)

**Key difference from `smoke_curation.py`:** reads from DB instead of fixture files, writes curated nodes/factors back.

- [ ] **Step 1: Implement run_curation_db.py**

```python
#!/usr/bin/env python3
"""Run curation pipeline reading from and writing to DB.

Usage:
    python scripts/pipeline/run_curation_db.py \
        --db-path ./data/lancedb/gaia \
        --report-path output/curation_report.json
"""
# Read: mgr.list_global_nodes(), mgr.list_factors()
# Process: clustering → dedup → abstraction → conflict → structure → cleanup
# Write: mgr.upsert_global_nodes(new_nodes), mgr.write_factors(new_factors)
# Save local report JSON for debugging
```

- [ ] **Step 2: Test on small dataset**
- [ ] **Step 3: Commit**

---

## Chunk 5: DB-Native Global BP

### Task 5: Create `scripts/pipeline/run_global_bp_db.py`

Reads factors + inference state from DB, runs BP, writes beliefs back.

**Files:**
- Create: `scripts/pipeline/run_global_bp_db.py`
- Read: `scripts/pipeline/run_global_bp.py` (reference)
- Read: `libs/storage/manager.py` (`load_global_factor_graph`, `update_inference_state`)

- [ ] **Step 1: Implement run_global_bp_db.py**

```python
#!/usr/bin/env python3
"""Run global BP reading from and writing to DB.

Usage:
    python scripts/pipeline/run_global_bp_db.py \
        --db-path ./data/lancedb/gaia \
        --damping 0.3 --max-iter 100
"""
# Read: factors, state = mgr.load_global_factor_graph()
# Read: global_nodes = mgr.list_global_nodes()
# Build FactorGraph from factors + node priors from state
# Run BP
# Write: mgr.update_inference_state(updated_state)
# Write: mgr.write_beliefs(belief_snapshots)
# Save local beliefs JSON backup
```

- [ ] **Step 2: Test on small dataset**
- [ ] **Step 3: Commit**

---

## Chunk 6: End-to-End Script

### Task 6: Create `scripts/pipeline/run_full_pipeline.py`

Orchestrates all 7 stages. Supports running individual stages or the full pipeline.

**Files:**
- Create: `scripts/pipeline/run_full_pipeline.py`

- [ ] **Step 1: Implement end-to-end orchestrator**

```python
#!/usr/bin/env python3
"""Run the full Gaia pipeline end-to-end.

Stages:
  1. xml-to-typst     — Convert paper XMLs to Typst packages
  2. build-graph-ir   — Build Graph IR from Typst packages
  3. local-bp          — Run local BP per package
  4. global-canon      — Canonicalize into global graph
  5. persist           — Write to LanceDB + Graph DB
  6. curation          — Run curation (from DB)
  7. global-bp         — Run global BP (from DB)

Usage:
    # Full pipeline
    python scripts/pipeline/run_full_pipeline.py \
        --papers-dir tests/fixtures/inputs/papers \
        --output-dir output \
        --db-path ./data/lancedb/gaia

    # Single stage
    python scripts/pipeline/run_full_pipeline.py --stage build-graph-ir ...

    # Resume from stage
    python scripts/pipeline/run_full_pipeline.py --from-stage persist ...
"""

import argparse, asyncio, subprocess, sys
from pathlib import Path


STAGES = [
    "xml-to-typst",
    "build-graph-ir",
    "local-bp",
    "global-canon",
    "persist",
    "curation",
    "global-bp",
]


def run_stage(stage: str, args) -> bool:
    """Run a single pipeline stage. Returns True on success."""
    print(f"\n{'='*60}")
    print(f"  Stage: {stage}")
    print(f"{'='*60}\n")

    if stage == "xml-to-typst":
        return _run("python scripts/paper_to_typst.py "
                     f"{args.papers_dir} --skip-llm -o {args.output_dir}/typst_packages")
    elif stage == "build-graph-ir":
        return _run(f"python scripts/pipeline/build_graph_ir.py {args.output_dir}/typst_packages/*")
    elif stage == "local-bp":
        return _run(f"python scripts/pipeline/run_local_bp.py {args.output_dir}/typst_packages/*")
    elif stage == "global-canon":
        return _run(f"python scripts/pipeline/canonicalize_global.py "
                     f"{args.output_dir}/typst_packages/* -o {args.output_dir}/global_graph "
                     f"{'--use-embedding' if args.use_embedding else ''}")
    elif stage == "persist":
        return _run(f"python scripts/pipeline/persist_to_db.py "
                     f"--packages-dir {args.output_dir}/typst_packages "
                     f"--global-graph-dir {args.output_dir}/global_graph "
                     f"--db-path {args.db_path}")
    elif stage == "curation":
        return _run(f"python scripts/pipeline/run_curation_db.py "
                     f"--db-path {args.db_path} "
                     f"--report-path {args.output_dir}/curation_report.json")
    elif stage == "global-bp":
        return _run(f"python scripts/pipeline/run_global_bp_db.py "
                     f"--db-path {args.db_path}")


def _run(cmd: str) -> bool:
    result = subprocess.run(cmd, shell=True)
    return result.returncode == 0
```

- [ ] **Step 2: Test end-to-end on 3 paper subset**
- [ ] **Step 3: Run full 100 papers**
- [ ] **Step 4: Commit**

---

## Chunk 7: Archive Old YAML Pipeline

### Task 7: Move old YAML pipeline files to archive

- [ ] **Step 1: Create archive directory and move files**

```bash
mkdir -p archive/cli archive/scripts
git mv cli/lang_to_storage.py archive/cli/lang_to_storage.py
git mv scripts/ingest.py archive/scripts/ingest.py
git mv scripts/xml_to_yaml.py archive/scripts/xml_to_yaml.py
```

- [ ] **Step 2: Update any imports/references**

Search for imports of `cli.lang_to_storage` and `scripts.ingest` — update or remove.

- [ ] **Step 3: Commit**

```bash
git commit -m "chore: archive old YAML pipeline scripts"
```

---

## Execution Order

1. **Chunk 1** (Task 1): Build Graph IR Typst path — prerequisite for everything
2. **Chunk 2** (Task 2): Storage converter — prerequisite for persist
3. **Chunk 3** (Task 3): Persist to DB — prerequisite for DB-native stages
4. **Chunk 4** (Task 4): DB-native curation — independent of Chunk 5
5. **Chunk 5** (Task 5): DB-native global BP — independent of Chunk 4
6. **Chunk 6** (Task 6): End-to-end script — after all stages work
7. **Chunk 7** (Task 7): Archive — after everything is validated

Chunks 4 and 5 can be parallelized.

---

## Local File Backup Strategy

Every stage saves intermediate files for debugging. These can be skipped later via `--skip-backup` flag:

| Stage | Backup Location | Contents |
|-------|----------------|----------|
| 1. XML→Typst | `output/typst_packages/<slug>/` | `.typ` files, `typst.toml` |
| 2. Build Graph IR | `output/typst_packages/<slug>/graph_ir/` | `raw_graph.json`, `local_canonical_graph.json`, `local_parameterization.json` |
| 3. Local BP | `output/typst_packages/<slug>/graph_ir/local_beliefs.json` | Per-node beliefs |
| 4. Global Canon | `output/global_graph/global_graph.json` | Full global graph |
| 5. Persist | `output/typst_packages/<slug>/graph_ir/storage_backup/` | `package.json`, `knowledge.json`, `factors.json` |
| 6. Curation | `output/curation_report.json` | Full curation audit trail |
| 7. Global BP | `output/global_beliefs.json` | Global node beliefs |
