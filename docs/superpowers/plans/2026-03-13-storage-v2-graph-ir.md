# Storage Layer v2.0 — Graph IR Alignment Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend the storage layer to support Graph IR entities (FactorNode, CanonicalBinding, GlobalCanonicalNode, GlobalInferenceState, PackageSubmissionArtifact), extend Knowledge with `kind`/`parameters`/new types, and wire everything through ContentStore → GraphStore → StorageManager.

**Architecture:** Bottom-up implementation: (1) Pydantic models, (2) ContentStore ABC + LanceDB impl, (3) GraphStore ABC + Kuzu/Neo4j impls, (4) StorageManager facade. Each chunk is independently testable. Existing tests must continue passing at every step.

**Tech Stack:** Python 3.12+, Pydantic v2, LanceDB, Kuzu, Neo4j (async), PyArrow, pytest (asyncio_mode=auto)

**Spec:** `docs/foundations/server/storage-schema.md` v2.0 — authoritative schema definition

---

## Chunk 1: Storage Models

Extend `libs/storage/models.py` with v2.0 entities and Knowledge field extensions. All new models are pure Pydantic — no I/O, no dependencies on storage backends.

### Task 1: Extend Knowledge model with kind, parameters, and new types

**Files:**
- Modify: `libs/storage/models.py`
- Modify: `tests/libs/storage/test_models.py`

- [ ] **Step 1: Write failing tests for Knowledge extensions**

Add to `tests/libs/storage/test_models.py`:

```python
from libs.storage.models import Knowledge, Parameter
from datetime import datetime

def test_knowledge_kind_field():
    """Knowledge should accept optional kind field."""
    k = Knowledge(
        knowledge_id="test/q1",
        version=1,
        type="question",
        kind="hypothesis",
        content="Is X true?",
        prior=0.5,
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert k.kind == "hypothesis"


def test_knowledge_kind_defaults_none():
    k = Knowledge(
        knowledge_id="test/c1",
        version=1,
        type="claim",
        content="X is true",
        prior=0.7,
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert k.kind is None


def test_knowledge_parameters_field():
    """Knowledge should accept parameters for schema nodes."""
    k = Knowledge(
        knowledge_id="test/schema1",
        version=1,
        type="claim",
        content="For all A: P(A)",
        prior=0.5,
        parameters=[Parameter(name="A", constraint="any substance")],
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert len(k.parameters) == 1
    assert k.parameters[0].name == "A"
    assert k.is_schema is True


def test_knowledge_is_schema_false_when_no_parameters():
    k = Knowledge(
        knowledge_id="test/ground1",
        version=1,
        type="claim",
        content="X is true",
        prior=0.7,
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert k.is_schema is False


def test_knowledge_contradiction_type():
    k = Knowledge(
        knowledge_id="test/contra1",
        version=1,
        type="contradiction",
        content="A contradicts B",
        prior=0.5,
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert k.type == "contradiction"


def test_knowledge_equivalence_type():
    k = Knowledge(
        knowledge_id="test/equiv1",
        version=1,
        type="equivalence",
        content="A is equivalent to B",
        prior=0.5,
        source_package_id="pkg",
        source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    assert k.type == "equivalence"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_models.py -k "kind or parameter or contradiction or equivalence or is_schema" -v`
Expected: FAIL — `Parameter` not importable, `kind` not a field, types not accepted

- [ ] **Step 3: Implement Knowledge extensions**

In `libs/storage/models.py`, add `Parameter` model (reuse structure from `libs/graph_ir/models.py` but define separately to avoid cross-dependency) and extend `Knowledge`:

```python
# Add after ImportRef class:

class Parameter(BaseModel):
    """Parameter placeholder for schema/∀-quantified knowledge nodes."""

    name: str
    constraint: str


# Modify Knowledge class:
class Knowledge(BaseModel):
    """Versioned knowledge object. Identity is (knowledge_id, version)."""

    knowledge_id: str
    version: int
    type: Literal[
        "claim", "question", "setting", "action", "contradiction", "equivalence"
    ]
    kind: str | None = None
    content: str
    parameters: list[Parameter] = []
    prior: float = Field(gt=0, le=1)
    keywords: list[str] = []
    source_package_id: str
    source_package_version: str = "0.1.0"
    source_module_id: str
    created_at: datetime
    embedding: list[float] | None = None

    @property
    def is_schema(self) -> bool:
        """True if this is a schema node (has parameters)."""
        return len(self.parameters) > 0
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/storage/test_models.py -v`
Expected: ALL PASS (including existing tests)

- [ ] **Step 5: Commit**

```bash
git add libs/storage/models.py tests/libs/storage/test_models.py
git commit -m "feat(models): extend Knowledge with kind, parameters, contradiction/equivalence types"
```

### Task 2: Add FactorNode storage model

**Files:**
- Modify: `libs/storage/models.py`
- Modify: `tests/libs/storage/test_models.py`

Note: We define a storage-layer `FactorNode` that mirrors `libs/graph_ir/models.FactorNode` but adds `package_id` for storage indexing. The graph_ir model is the authoring-side definition; this is the storage-side definition. They share the same field names for easy conversion.

- [ ] **Step 1: Write failing tests**

```python
from libs.storage.models import FactorNode, SourceRef

def test_factor_node_reasoning():
    f = FactorNode(
        factor_id="pkg.mod.chain1",
        type="reasoning",
        premises=["pkg/k1", "pkg/k2"],
        contexts=["pkg/k3"],
        conclusion="pkg/k4",
        package_id="pkg",
        source_ref=SourceRef(
            package="pkg", version="1.0.0", module="pkg.mod", knowledge_name="k4"
        ),
    )
    assert f.type == "reasoning"
    assert f.is_gate_factor is False
    assert set(f.bp_participant_ids) == {"pkg/k1", "pkg/k2", "pkg/k4"}


def test_factor_node_mutex_constraint():
    f = FactorNode(
        factor_id="pkg.mutex.1",
        type="mutex_constraint",
        premises=["pkg/k1", "pkg/k2"],
        conclusion="pkg/contra1",
        package_id="pkg",
    )
    assert f.is_gate_factor is True
    assert f.bp_participant_ids == ["pkg/k1", "pkg/k2"]


def test_factor_node_equiv_constraint():
    f = FactorNode(
        factor_id="pkg.equiv.1",
        type="equiv_constraint",
        premises=["pkg/k1", "pkg/k2"],
        conclusion="pkg/equiv1",
        package_id="pkg",
    )
    assert f.is_gate_factor is True


def test_factor_node_instantiation():
    f = FactorNode(
        factor_id="pkg.inst.1",
        type="instantiation",
        premises=["pkg/schema1"],
        conclusion="pkg/ground1",
        package_id="pkg",
    )
    assert f.is_gate_factor is False
    assert set(f.bp_participant_ids) == {"pkg/schema1", "pkg/ground1"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_models.py -k "factor_node" -v`
Expected: FAIL — `FactorNode`, `SourceRef` not importable

- [ ] **Step 3: Implement FactorNode and SourceRef**

Add to `libs/storage/models.py` after `Parameter`:

```python
class SourceRef(BaseModel):
    """Reference to the source of a factor in the authoring layer."""

    package: str
    version: str
    module: str
    knowledge_name: str


# Add after BeliefSnapshot:

class FactorNode(BaseModel):
    """Persistent factor from Graph IR. Defines a constraint between knowledge nodes."""

    factor_id: str
    type: Literal["reasoning", "instantiation", "mutex_constraint", "equiv_constraint"]
    premises: list[str] = []
    contexts: list[str] = []
    conclusion: str
    package_id: str
    source_ref: SourceRef | None = None
    metadata: dict | None = None

    @property
    def is_gate_factor(self) -> bool:
        return self.type in ("mutex_constraint", "equiv_constraint")

    @property
    def bp_participant_ids(self) -> list[str]:
        if self.is_gate_factor:
            return list(self.premises)
        return list(self.premises) + [self.conclusion]
```

- [ ] **Step 4: Run all model tests**

Run: `pytest tests/libs/storage/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage/models.py tests/libs/storage/test_models.py
git commit -m "feat(models): add FactorNode and SourceRef storage models"
```

### Task 3: Add CanonicalBinding, GlobalCanonicalNode, GlobalInferenceState, PackageSubmissionArtifact

**Files:**
- Modify: `libs/storage/models.py`
- Modify: `tests/libs/storage/test_models.py`

- [ ] **Step 1: Write failing tests**

```python
from datetime import datetime
from libs.storage.models import (
    CanonicalBinding,
    FactorParams,
    GlobalCanonicalNode,
    GlobalInferenceState,
    LocalCanonicalRef,
    PackageRef,
    PackageSubmissionArtifact,
    Parameter,
)


def test_canonical_binding():
    b = CanonicalBinding(
        package="pkg",
        version="1.0.0",
        local_graph_hash="sha256:abc123",
        local_canonical_id="pkg/lc_k1",
        decision="create_new",
        global_canonical_id="gcn_01ABC",
        decided_at=datetime.now(),
        decided_by="auto_matcher",
    )
    assert b.decision == "create_new"
    assert b.reason is None


def test_global_canonical_node():
    node = GlobalCanonicalNode(
        global_canonical_id="gcn_01ABC",
        knowledge_type="claim",
        representative_content="X is true",
        member_local_nodes=[
            LocalCanonicalRef(package="pkg", version="1.0.0", local_canonical_id="pkg/lc_k1"),
        ],
        provenance=[PackageRef(package="pkg", version="1.0.0")],
    )
    assert node.kind is None
    assert len(node.member_local_nodes) == 1
    assert node.parameters == []


def test_global_inference_state():
    state = GlobalInferenceState(
        graph_hash="sha256:xyz",
        node_priors={"gcn_01": 0.7, "gcn_02": 0.5},
        factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
        node_beliefs={"gcn_01": 0.8},
        updated_at=datetime.now(),
    )
    assert state.node_priors["gcn_01"] == 0.7
    assert state.factor_parameters["f1"].conditional_probability == 0.9


def test_package_submission_artifact():
    art = PackageSubmissionArtifact(
        package_name="pkg",
        commit_hash="abc123def",
        source_files={"main.gaia": "knowledge { ... }"},
        raw_graph={"schema_version": "1.0", "knowledge_nodes": []},
        local_canonical_graph={"schema_version": "1.0", "knowledge_nodes": []},
        canonicalization_log=[{"local_canonical_id": "lc1", "members": ["r1"], "reason": "unique"}],
        submitted_at=datetime.now(),
    )
    assert art.package_name == "pkg"
    assert len(art.source_files) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_models.py -k "canonical_binding or global_canonical or global_inference or submission_artifact" -v`
Expected: FAIL — models not importable

- [ ] **Step 3: Implement all new models**

Add to `libs/storage/models.py`:

```python
# ── Global Identity ──


class LocalCanonicalRef(BaseModel):
    """Reference to a local canonical node within a specific package version."""

    package: str
    version: str
    local_canonical_id: str


class PackageRef(BaseModel):
    """Reference to a specific package version."""

    package: str
    version: str


class CanonicalBinding(BaseModel):
    """Maps a local canonical node to a global canonical identity."""

    package: str
    version: str
    local_graph_hash: str
    local_canonical_id: str
    decision: Literal["match_existing", "create_new"]
    global_canonical_id: str
    decided_at: datetime
    decided_by: str
    reason: str | None = None


class GlobalCanonicalNode(BaseModel):
    """Registry-assigned global dedup identity for a knowledge concept."""

    global_canonical_id: str
    knowledge_type: str
    kind: str | None = None
    representative_content: str
    parameters: list[Parameter] = []
    member_local_nodes: list[LocalCanonicalRef] = []
    provenance: list[PackageRef] = []
    metadata: dict | None = None


class FactorParams(BaseModel):
    """Runtime parameters for a factor node."""

    conditional_probability: float


class GlobalInferenceState(BaseModel):
    """Registry-managed global inference state. Probabilities separated from structure."""

    graph_hash: str
    node_priors: dict[str, float] = {}
    factor_parameters: dict[str, FactorParams] = {}
    node_beliefs: dict[str, float] = {}
    updated_at: datetime


# ── Submission Artifact ──


class PackageSubmissionArtifact(BaseModel):
    """Immutable snapshot of a package submission for audit and re-verification."""

    package_name: str
    commit_hash: str
    source_files: dict[str, str]
    raw_graph: dict
    local_canonical_graph: dict
    canonicalization_log: list[dict]
    submitted_at: datetime
```

- [ ] **Step 4: Run all model tests**

Run: `pytest tests/libs/storage/test_models.py -v`
Expected: ALL PASS

- [ ] **Step 5: Update `__init__.py` exports**

Add all new models to `libs/storage/__init__.py` exports.

- [ ] **Step 6: Commit**

```bash
git add libs/storage/models.py libs/storage/__init__.py tests/libs/storage/test_models.py
git commit -m "feat(models): add CanonicalBinding, GlobalCanonicalNode, GlobalInferenceState, PackageSubmissionArtifact"
```

---

## Chunk 2: ContentStore — New Tables & Methods

Extend the ContentStore ABC and LanceContentStore with 5 new tables (factors, canonical_bindings, global_canonical_nodes, global_inference_state, submission_artifacts) and Knowledge schema extensions (+kind, +parameters).

### Task 4: Extend Knowledge LanceDB schema with kind and parameters columns

**Files:**
- Modify: `libs/storage/lance_content_store.py`
- Modify: `tests/libs/storage/test_lance_content.py`

- [ ] **Step 1: Write failing test for Knowledge kind/parameters roundtrip**

Add to `tests/libs/storage/test_lance_content.py`:

```python
from libs.storage.models import Parameter


async def test_knowledge_kind_parameters_roundtrip(content_store):
    """Knowledge with kind and parameters survives write→read."""
    k = Knowledge(
        knowledge_id="test/schema1",
        version=1,
        type="claim",
        kind="universal_law",
        content="For all A satisfying C: P(A)",
        parameters=[Parameter(name="A", constraint="any substance")],
        prior=0.5,
        source_package_id="test_pkg",
        source_package_version="1.0.0",
        source_module_id="test_pkg.mod",
        created_at=datetime.now(),
    )
    await content_store.write_knowledge([k])
    result = await content_store.get_knowledge("test/schema1", version=1)
    assert result is not None
    assert result.kind == "universal_law"
    assert len(result.parameters) == 1
    assert result.parameters[0].name == "A"
    assert result.is_schema is True


async def test_knowledge_kind_none_roundtrip(content_store):
    """Knowledge without kind/parameters defaults correctly."""
    k = Knowledge(
        knowledge_id="test/ground1",
        version=1,
        type="claim",
        content="X is true",
        prior=0.7,
        source_package_id="test_pkg",
        source_package_version="1.0.0",
        source_module_id="test_pkg.mod",
        created_at=datetime.now(),
    )
    await content_store.write_knowledge([k])
    result = await content_store.get_knowledge("test/ground1", version=1)
    assert result is not None
    assert result.kind is None
    assert result.parameters == []
    assert result.is_schema is False
```

Note: The test fixture `content_store` already exists in `tests/libs/storage/conftest.py`. These tests need the package to be committed first for visibility. Check the conftest — if it doesn't auto-commit, wrap the write in a package ingest or manually commit.

Actually, looking at the existing tests, `test_lance_content.py` writes knowledge directly and reads without visibility gating (the tests write knowledge items where `source_package_id` matches a committed package from fixtures). For simplicity, use a committed package from fixtures or add a helper.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_lance_content.py::test_knowledge_kind_parameters_roundtrip -v`
Expected: FAIL — schema doesn't have `kind`/`parameters` columns

- [ ] **Step 3: Extend Knowledge schema and serialization**

In `libs/storage/lance_content_store.py`:

1. Add `kind` and `parameters` columns to `_KNOWLEDGE_SCHEMA`:
```python
_KNOWLEDGE_SCHEMA = pa.schema(
    [
        pa.field("knowledge_id", pa.string()),
        pa.field("version", pa.int64()),
        pa.field("type", pa.string()),
        pa.field("kind", pa.string()),             # nullable, NEW
        pa.field("content", pa.string()),
        pa.field("parameters", pa.string()),        # JSON list[Parameter], NEW
        pa.field("prior", pa.float64()),
        pa.field("keywords", pa.string()),
        pa.field("source_package_id", pa.string()),
        pa.field("source_package_version", pa.string()),
        pa.field("source_module_id", pa.string()),
        pa.field("created_at", pa.string()),
        pa.field("embedding", pa.string()),
    ]
)
```

2. Update `_knowledge_to_row`:
```python
def _knowledge_to_row(k: Knowledge) -> dict[str, Any]:
    return {
        "knowledge_id": k.knowledge_id,
        "version": k.version,
        "type": k.type,
        "kind": k.kind or "",
        "content": k.content,
        "parameters": json.dumps([p.model_dump() for p in k.parameters]) if k.parameters else "[]",
        "prior": k.prior,
        "keywords": json.dumps(k.keywords),
        "source_package_id": k.source_package_id,
        "source_package_version": k.source_package_version,
        "source_module_id": k.source_module_id,
        "created_at": k.created_at.isoformat(),
        "embedding": json.dumps(k.embedding) if k.embedding else "",
    }
```

3. Update `_row_to_knowledge`:
```python
def _row_to_knowledge(row: dict[str, Any]) -> Knowledge:
    emb_raw = row["embedding"]
    params_raw = row.get("parameters", "[]")
    return Knowledge(
        knowledge_id=row["knowledge_id"],
        version=row["version"],
        type=row["type"],
        kind=row.get("kind") or None,
        content=row["content"],
        parameters=json.loads(params_raw) if params_raw else [],
        prior=row["prior"],
        keywords=json.loads(row["keywords"]),
        source_package_id=row["source_package_id"],
        source_package_version=row.get("source_package_version", "0.1.0"),
        source_module_id=row["source_module_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        embedding=json.loads(emb_raw) if emb_raw else None,
    )
```

- [ ] **Step 4: Run all content store tests**

Run: `pytest tests/libs/storage/test_lance_content.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage/lance_content_store.py tests/libs/storage/test_lance_content.py
git commit -m "feat(lance): extend Knowledge schema with kind and parameters columns"
```

### Task 5: Add factors table to ContentStore

**Files:**
- Modify: `libs/storage/content_store.py` (ABC)
- Modify: `libs/storage/lance_content_store.py` (impl)
- Modify: `tests/libs/storage/test_lance_content.py`

- [ ] **Step 1: Write failing tests for factor write/read**

```python
from libs.storage.models import FactorNode, SourceRef


async def test_write_and_list_factors(content_store):
    """Factors survive write→list roundtrip."""
    factors = [
        FactorNode(
            factor_id="pkg.mod.chain1",
            type="reasoning",
            premises=["pkg/k1", "pkg/k2"],
            contexts=["pkg/k3"],
            conclusion="pkg/k4",
            package_id="pkg",
            source_ref=SourceRef(
                package="pkg", version="1.0.0", module="pkg.mod", knowledge_name="k4"
            ),
        ),
        FactorNode(
            factor_id="pkg.mutex.1",
            type="mutex_constraint",
            premises=["pkg/k1", "pkg/k2"],
            conclusion="pkg/contra1",
            package_id="pkg",
        ),
    ]
    await content_store.write_factors(factors)
    result = await content_store.list_factors()
    assert len(result) == 2
    ids = {f.factor_id for f in result}
    assert ids == {"pkg.mod.chain1", "pkg.mutex.1"}


async def test_get_factors_by_package(content_store):
    """Can filter factors by package_id."""
    factors = [
        FactorNode(
            factor_id="a.mod.chain1", type="reasoning",
            premises=["a/k1"], conclusion="a/k2", package_id="a",
        ),
        FactorNode(
            factor_id="b.mod.chain1", type="reasoning",
            premises=["b/k1"], conclusion="b/k2", package_id="b",
        ),
    ]
    await content_store.write_factors(factors)
    result = await content_store.get_factors_by_package("a")
    assert len(result) == 1
    assert result[0].factor_id == "a.mod.chain1"


async def test_factors_upsert_idempotent(content_store):
    """Writing the same factor twice doesn't create duplicates."""
    f = FactorNode(
        factor_id="pkg.f1", type="instantiation",
        premises=["pkg/s1"], conclusion="pkg/g1", package_id="pkg",
    )
    await content_store.write_factors([f])
    await content_store.write_factors([f])
    result = await content_store.list_factors()
    assert len(result) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_lance_content.py -k "factor" -v`
Expected: FAIL — `write_factors` not defined

- [ ] **Step 3: Add factors to ContentStore ABC**

Add to `libs/storage/content_store.py` in the write section:

```python
from libs.storage.models import FactorNode  # add to imports

# In ContentStore class, after write_resources:

    @abstractmethod
    async def write_factors(self, factors: list[FactorNode]) -> None:
        """Write factor nodes from Graph IR."""

# In read section, after get_resources_for:

    @abstractmethod
    async def list_factors(self) -> list[FactorNode]:
        """Load all factors for BP factor graph construction."""

    @abstractmethod
    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]:
        """Get factors belonging to a specific package."""
```

- [ ] **Step 4: Implement in LanceContentStore**

Add schema, serialization helpers, and methods to `libs/storage/lance_content_store.py`:

```python
# Schema (add after _RESOURCE_ATTACHMENTS_SCHEMA):
_FACTORS_SCHEMA = pa.schema(
    [
        pa.field("factor_id", pa.string()),
        pa.field("type", pa.string()),
        pa.field("premises", pa.string()),    # JSON list[str]
        pa.field("contexts", pa.string()),    # JSON list[str]
        pa.field("conclusion", pa.string()),
        pa.field("source_ref", pa.string()),  # JSON SourceRef | ""
        pa.field("metadata", pa.string()),    # JSON dict | ""
        pa.field("package_id", pa.string()),
    ]
)

# Add to _TABLE_SCHEMAS:
#     "factors": _FACTORS_SCHEMA,

# Serialization helpers:
def _factor_to_row(f: FactorNode) -> dict[str, Any]:
    return {
        "factor_id": f.factor_id,
        "type": f.type,
        "premises": json.dumps(f.premises),
        "contexts": json.dumps(f.contexts),
        "conclusion": f.conclusion,
        "source_ref": json.dumps(f.source_ref.model_dump()) if f.source_ref else "",
        "metadata": json.dumps(f.metadata) if f.metadata else "",
        "package_id": f.package_id,
    }


def _row_to_factor(row: dict[str, Any]) -> FactorNode:
    sr_raw = row.get("source_ref", "")
    return FactorNode(
        factor_id=row["factor_id"],
        type=row["type"],
        premises=json.loads(row["premises"]),
        contexts=json.loads(row["contexts"]),
        conclusion=row["conclusion"],
        source_ref=json.loads(sr_raw) if sr_raw else None,
        metadata=json.loads(row["metadata"]) if row.get("metadata") else None,
        package_id=row["package_id"],
    )
```

Methods in `LanceContentStore`:

```python
    async def write_factors(self, factors: list[FactorNode]) -> None:
        if not factors:
            return
        table = self._db.open_table("factors")
        rows = [_factor_to_row(f) for f in factors]
        (
            table.merge_insert(["factor_id"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    async def list_factors(self) -> list[FactorNode]:
        table = self._db.open_table("factors")
        count = table.count_rows()
        if count == 0:
            return []
        results = table.search().limit(count).to_list()
        return [_row_to_factor(r) for r in results]

    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]:
        table = self._db.open_table("factors")
        results = (
            table.search()
            .where(f"package_id = '{_q(package_id)}'")
            .limit(_MAX_SCAN)
            .to_list()
        )
        return [_row_to_factor(r) for r in results]
```

Also add `FactorNode` and `SourceRef` to imports in lance_content_store.py.

- [ ] **Step 5: Run tests**

Run: `pytest tests/libs/storage/test_lance_content.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add libs/storage/content_store.py libs/storage/lance_content_store.py tests/libs/storage/test_lance_content.py
git commit -m "feat(lance): add factors table with write/list/get_by_package"
```

### Task 6: Add canonical_bindings and global_canonical_nodes tables

**Files:**
- Modify: `libs/storage/content_store.py`
- Modify: `libs/storage/lance_content_store.py`
- Modify: `tests/libs/storage/test_lance_content.py`

- [ ] **Step 1: Write failing tests**

```python
from libs.storage.models import (
    CanonicalBinding,
    GlobalCanonicalNode,
    LocalCanonicalRef,
    PackageRef,
    Parameter,
)


async def test_write_and_get_canonical_bindings(content_store):
    bindings = [
        CanonicalBinding(
            package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
            local_canonical_id="pkg/lc_k1", decision="create_new",
            global_canonical_id="gcn_01", decided_at=datetime.now(),
            decided_by="auto",
        ),
        CanonicalBinding(
            package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
            local_canonical_id="pkg/lc_k2", decision="match_existing",
            global_canonical_id="gcn_02", decided_at=datetime.now(),
            decided_by="auto",
        ),
    ]
    await content_store.write_canonical_bindings(bindings)
    result = await content_store.get_canonical_bindings("pkg", "1.0.0")
    assert len(result) == 2
    ids = {b.local_canonical_id for b in result}
    assert ids == {"pkg/lc_k1", "pkg/lc_k2"}


async def test_canonical_bindings_upsert(content_store):
    b = CanonicalBinding(
        package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
        local_canonical_id="pkg/lc_k1", decision="create_new",
        global_canonical_id="gcn_01", decided_at=datetime.now(),
        decided_by="auto",
    )
    await content_store.write_canonical_bindings([b])
    await content_store.write_canonical_bindings([b])
    result = await content_store.get_canonical_bindings("pkg", "1.0.0")
    assert len(result) == 1


async def test_write_and_get_global_canonical_node(content_store):
    node = GlobalCanonicalNode(
        global_canonical_id="gcn_01",
        knowledge_type="claim",
        representative_content="X is true",
        member_local_nodes=[
            LocalCanonicalRef(package="pkg", version="1.0.0", local_canonical_id="pkg/lc_k1"),
        ],
        provenance=[PackageRef(package="pkg", version="1.0.0")],
    )
    await content_store.upsert_global_nodes([node])
    result = await content_store.get_global_node("gcn_01")
    assert result is not None
    assert result.knowledge_type == "claim"
    assert len(result.member_local_nodes) == 1


async def test_global_node_upsert_updates_existing(content_store):
    node1 = GlobalCanonicalNode(
        global_canonical_id="gcn_01",
        knowledge_type="claim",
        representative_content="X is true",
        member_local_nodes=[
            LocalCanonicalRef(package="p1", version="1.0.0", local_canonical_id="p1/lc1"),
        ],
        provenance=[PackageRef(package="p1", version="1.0.0")],
    )
    await content_store.upsert_global_nodes([node1])
    # Upsert with additional member
    node2 = node1.model_copy(
        update={
            "member_local_nodes": [
                LocalCanonicalRef(package="p1", version="1.0.0", local_canonical_id="p1/lc1"),
                LocalCanonicalRef(package="p2", version="1.0.0", local_canonical_id="p2/lc2"),
            ],
            "provenance": [
                PackageRef(package="p1", version="1.0.0"),
                PackageRef(package="p2", version="1.0.0"),
            ],
        }
    )
    await content_store.upsert_global_nodes([node2])
    result = await content_store.get_global_node("gcn_01")
    assert len(result.member_local_nodes) == 2
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_lance_content.py -k "canonical_binding or global_canonical_node or global_node" -v`
Expected: FAIL

- [ ] **Step 3: Implement schemas, serializers, ABC methods, and LanceDB methods**

Add to `content_store.py` ABC:

```python
    @abstractmethod
    async def write_canonical_bindings(self, bindings: list[CanonicalBinding]) -> None: ...

    @abstractmethod
    async def get_canonical_bindings(self, package: str, version: str) -> list[CanonicalBinding]: ...

    @abstractmethod
    async def upsert_global_nodes(self, nodes: list[GlobalCanonicalNode]) -> None: ...

    @abstractmethod
    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None: ...
```

Add schemas, serializers, methods to `lance_content_store.py`:

```python
_CANONICAL_BINDINGS_SCHEMA = pa.schema([
    pa.field("package", pa.string()),
    pa.field("version", pa.string()),
    pa.field("local_graph_hash", pa.string()),
    pa.field("local_canonical_id", pa.string()),
    pa.field("decision", pa.string()),
    pa.field("global_canonical_id", pa.string()),
    pa.field("decided_at", pa.string()),
    pa.field("decided_by", pa.string()),
    pa.field("reason", pa.string()),
])

_GLOBAL_CANONICAL_NODES_SCHEMA = pa.schema([
    pa.field("global_canonical_id", pa.string()),
    pa.field("knowledge_type", pa.string()),
    pa.field("kind", pa.string()),
    pa.field("representative_content", pa.string()),
    pa.field("parameters", pa.string()),          # JSON
    pa.field("member_local_nodes", pa.string()),   # JSON
    pa.field("provenance", pa.string()),           # JSON
    pa.field("metadata", pa.string()),
])
```

Serializers and methods follow the same patterns as existing tables (merge_insert for upsert, search+where for reads). Key for canonical_bindings: merge key is `["package", "version", "local_graph_hash", "local_canonical_id"]`. Key for global_canonical_nodes: merge key is `["global_canonical_id"]`.

- [ ] **Step 4: Run tests**

Run: `pytest tests/libs/storage/test_lance_content.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage/content_store.py libs/storage/lance_content_store.py tests/libs/storage/test_lance_content.py
git commit -m "feat(lance): add canonical_bindings and global_canonical_nodes tables"
```

### Task 7: Add global_inference_state and submission_artifacts tables

**Files:**
- Modify: `libs/storage/content_store.py`
- Modify: `libs/storage/lance_content_store.py`
- Modify: `tests/libs/storage/test_lance_content.py`

- [ ] **Step 1: Write failing tests**

```python
from libs.storage.models import (
    FactorParams,
    GlobalInferenceState,
    PackageSubmissionArtifact,
)


async def test_write_and_get_inference_state(content_store):
    state = GlobalInferenceState(
        graph_hash="sha256:xyz",
        node_priors={"gcn_01": 0.7},
        factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
        node_beliefs={"gcn_01": 0.8},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state)
    result = await content_store.get_inference_state()
    assert result is not None
    assert result.graph_hash == "sha256:xyz"
    assert result.node_priors["gcn_01"] == 0.7
    assert result.factor_parameters["f1"].conditional_probability == 0.9
    assert result.node_beliefs["gcn_01"] == 0.8


async def test_inference_state_update_replaces(content_store):
    state1 = GlobalInferenceState(
        graph_hash="sha256:v1",
        node_priors={"gcn_01": 0.7},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state1)
    state2 = GlobalInferenceState(
        graph_hash="sha256:v2",
        node_priors={"gcn_01": 0.8, "gcn_02": 0.6},
        updated_at=datetime.now(),
    )
    await content_store.update_inference_state(state2)
    result = await content_store.get_inference_state()
    assert result.graph_hash == "sha256:v2"
    assert len(result.node_priors) == 2


async def test_inference_state_none_when_empty(content_store):
    result = await content_store.get_inference_state()
    assert result is None


async def test_write_and_get_submission_artifact(content_store):
    art = PackageSubmissionArtifact(
        package_name="pkg",
        commit_hash="abc123",
        source_files={"main.gaia": "knowledge { content: 'X' }"},
        raw_graph={"schema_version": "1.0", "knowledge_nodes": []},
        local_canonical_graph={"schema_version": "1.0", "knowledge_nodes": []},
        canonicalization_log=[{"local_canonical_id": "lc1", "members": ["r1"], "reason": "unique"}],
        submitted_at=datetime.now(),
    )
    await content_store.write_submission_artifact(art)
    result = await content_store.get_submission_artifact("pkg", "abc123")
    assert result is not None
    assert result.package_name == "pkg"
    assert result.source_files["main.gaia"] == "knowledge { content: 'X' }"


async def test_submission_artifact_not_found(content_store):
    result = await content_store.get_submission_artifact("nonexistent", "xxx")
    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_lance_content.py -k "inference_state or submission_artifact" -v`
Expected: FAIL

- [ ] **Step 3: Implement**

Add to ABC:

```python
    @abstractmethod
    async def update_inference_state(self, state: GlobalInferenceState) -> None: ...

    @abstractmethod
    async def get_inference_state(self) -> GlobalInferenceState | None: ...

    @abstractmethod
    async def write_submission_artifact(self, artifact: PackageSubmissionArtifact) -> None: ...

    @abstractmethod
    async def get_submission_artifact(
        self, package: str, commit_hash: str
    ) -> PackageSubmissionArtifact | None: ...
```

LanceDB implementation:

- `global_inference_state` table: single-row design with `graph_hash` as merge key. All dict fields JSON-serialized.
- `submission_artifacts` table: `(package_name, commit_hash)` as merge key. `source_files`, `raw_graph`, `local_canonical_graph`, `canonicalization_log` all JSON-serialized.

Follow the same pattern as other tables for schemas and serializers.

- [ ] **Step 4: Run all content store tests**

Run: `pytest tests/libs/storage/test_lance_content.py -v`
Expected: ALL PASS

- [ ] **Step 5: Run full test suite to check nothing broke**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add libs/storage/content_store.py libs/storage/lance_content_store.py tests/libs/storage/test_lance_content.py
git commit -m "feat(lance): add global_inference_state and submission_artifacts tables"
```

---

## Chunk 3: GraphStore — Factor & Global Topology

Extend GraphStore ABC and Kuzu/Neo4j implementations with Factor layer topology and Global layer topology. Remove deprecated `update_beliefs`/`update_probability`.

### Task 8: Add write_factor_topology to GraphStore

**Files:**
- Modify: `libs/storage/graph_store.py` (ABC)
- Modify: `libs/storage/kuzu_graph_store.py`
- Modify: `libs/storage/neo4j_graph_store.py`
- Modify: `tests/libs/storage/test_graph_store.py`

- [ ] **Step 1: Write failing tests for factor topology**

Add to `tests/libs/storage/test_graph_store.py`:

```python
from libs.storage.models import FactorNode


@pytest.fixture
def sample_factors():
    return [
        FactorNode(
            factor_id="pkg.mod.chain1",
            type="reasoning",
            premises=["pkg/k1", "pkg/k2"],
            contexts=["pkg/k3"],
            conclusion="pkg/k4",
            package_id="pkg",
        ),
        FactorNode(
            factor_id="pkg.mutex.1",
            type="mutex_constraint",
            premises=["pkg/k1", "pkg/k5"],
            conclusion="pkg/contra1",
            package_id="pkg",
        ),
    ]


async def test_write_factor_topology(graph_store, sample_knowledge, sample_chains, sample_factors):
    """Factor topology creates Factor nodes with FACTOR_PREMISE/CONTEXT/CONCLUSION rels."""
    await graph_store.write_topology(sample_knowledge, sample_chains)
    await graph_store.write_factor_topology(sample_factors)
    # Verify via subgraph — Factor nodes should be reachable
    # This test verifies no errors; deeper topology tests follow


async def test_factor_topology_idempotent(graph_store, sample_knowledge, sample_chains, sample_factors):
    """Writing factor topology twice doesn't create duplicates."""
    await graph_store.write_topology(sample_knowledge, sample_chains)
    await graph_store.write_factor_topology(sample_factors)
    await graph_store.write_factor_topology(sample_factors)
    # No error = idempotent
```

Note: Exact fixtures (`sample_knowledge`, `sample_chains`) need to include knowledge IDs matching the factor premises/conclusion. Adjust IDs in `sample_factors` to match existing fixture knowledge IDs, or create additional knowledge items.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_graph_store.py -k "factor_topology" -v`
Expected: FAIL — `write_factor_topology` not defined

- [ ] **Step 3: Add to ABC**

In `libs/storage/graph_store.py`:

```python
from libs.storage.models import FactorNode  # add to imports

    @abstractmethod
    async def write_factor_topology(self, factors: list[FactorNode]) -> None:
        """Write Factor nodes and FACTOR_PREMISE/FACTOR_CONTEXT/FACTOR_CONCLUSION relationships."""
```

- [ ] **Step 4: Implement in KuzuGraphStore**

In `libs/storage/kuzu_graph_store.py`, add Factor node table and relationship tables to schema init:

```python
# In _SCHEMA_STMTS, add:
"CREATE NODE TABLE IF NOT EXISTS Factor(factor_id STRING, type STRING, is_gate BOOLEAN, PRIMARY KEY(factor_id))",
"CREATE REL TABLE IF NOT EXISTS FACTOR_PREMISE(FROM Knowledge TO Factor)",
"CREATE REL TABLE IF NOT EXISTS FACTOR_CONTEXT(FROM Knowledge TO Factor)",
"CREATE REL TABLE IF NOT EXISTS FACTOR_CONCLUSION(FROM Factor TO Knowledge)",
```

Implement `write_factor_topology`:
- MERGE Factor nodes (keyed by `factor_id`)
- For each factor, ensure Knowledge stub nodes exist for all premises/contexts/conclusion
- Create FACTOR_PREMISE, FACTOR_CONTEXT, FACTOR_CONCLUSION relationships using `_ensure_rel`-style check-before-create pattern

- [ ] **Step 5: Implement in Neo4jGraphStore**

Same logic using async Cypher MERGE for Factor nodes and CREATE for relationships (with existence check).

- [ ] **Step 6: Run tests**

Run: `pytest tests/libs/storage/test_graph_store.py -v`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add libs/storage/graph_store.py libs/storage/kuzu_graph_store.py libs/storage/neo4j_graph_store.py tests/libs/storage/test_graph_store.py
git commit -m "feat(graph): add write_factor_topology with Factor nodes and FACTOR_PREMISE/CONTEXT/CONCLUSION rels"
```

### Task 9: Add write_global_topology to GraphStore

**Files:**
- Modify: `libs/storage/graph_store.py`
- Modify: `libs/storage/kuzu_graph_store.py`
- Modify: `libs/storage/neo4j_graph_store.py`
- Modify: `tests/libs/storage/test_graph_store.py`

- [ ] **Step 1: Write failing tests**

```python
from libs.storage.models import (
    CanonicalBinding,
    GlobalCanonicalNode,
    LocalCanonicalRef,
    PackageRef,
)


async def test_write_global_topology(graph_store, sample_knowledge, sample_chains):
    """Global topology creates GlobalCanonicalNode nodes and CANONICAL_BINDING rels."""
    await graph_store.write_topology(sample_knowledge, sample_chains)
    bindings = [
        CanonicalBinding(
            package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
            local_canonical_id="pkg/k1", decision="create_new",
            global_canonical_id="gcn_01", decided_at=datetime.now(),
            decided_by="auto",
        ),
    ]
    global_nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_01",
            knowledge_type="claim",
            representative_content="X is true",
            member_local_nodes=[
                LocalCanonicalRef(package="pkg", version="1.0.0", local_canonical_id="pkg/k1"),
            ],
            provenance=[PackageRef(package="pkg", version="1.0.0")],
        ),
    ]
    await graph_store.write_global_topology(bindings, global_nodes)
    # Verify no errors; topology is queryable via get_subgraph


async def test_global_topology_idempotent(graph_store, sample_knowledge, sample_chains):
    await graph_store.write_topology(sample_knowledge, sample_chains)
    bindings = [
        CanonicalBinding(
            package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
            local_canonical_id="pkg/k1", decision="create_new",
            global_canonical_id="gcn_01", decided_at=datetime.now(),
            decided_by="auto",
        ),
    ]
    global_nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_01", knowledge_type="claim",
            representative_content="X is true",
        ),
    ]
    await graph_store.write_global_topology(bindings, global_nodes)
    await graph_store.write_global_topology(bindings, global_nodes)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_graph_store.py -k "global_topology" -v`
Expected: FAIL

- [ ] **Step 3: Add to ABC**

```python
    @abstractmethod
    async def write_global_topology(
        self,
        bindings: list[CanonicalBinding],
        global_nodes: list[GlobalCanonicalNode],
    ) -> None:
        """Write GlobalCanonicalNode nodes and CANONICAL_BINDING relationships."""
```

- [ ] **Step 4: Implement in Kuzu and Neo4j**

Kuzu schema additions:
```python
"CREATE NODE TABLE IF NOT EXISTS GlobalCanonicalNode(global_canonical_id STRING, knowledge_type STRING, kind STRING, representative_content STRING, PRIMARY KEY(global_canonical_id))",
"CREATE REL TABLE IF NOT EXISTS CANONICAL_BINDING(FROM Knowledge TO GlobalCanonicalNode, decision STRING, package STRING, version STRING)",
```

Implementation: MERGE GlobalCanonicalNode nodes, then create CANONICAL_BINDING rels from Knowledge (using `knowledge_vid` matching `local_canonical_id + "@" + version`) to GlobalCanonicalNode.

Neo4j: same logic using `MERGE` for nodes, existence check + `CREATE` for relationships.

- [ ] **Step 5: Run tests**

Run: `pytest tests/libs/storage/test_graph_store.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add libs/storage/graph_store.py libs/storage/kuzu_graph_store.py libs/storage/neo4j_graph_store.py tests/libs/storage/test_graph_store.py
git commit -m "feat(graph): add write_global_topology with GlobalCanonicalNode and CANONICAL_BINDING rels"
```

### Task 10: Deprecate update_beliefs and update_probability from GraphStore

Per v2.0 design, probabilities move to GlobalInferenceState. Graph nodes no longer carry belief/probability values. This is a breaking change for the GraphStore ABC.

**Files:**
- Modify: `libs/storage/graph_store.py`
- Modify: `libs/storage/kuzu_graph_store.py`
- Modify: `libs/storage/neo4j_graph_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `tests/libs/storage/test_graph_store.py`
- Modify: `tests/libs/storage/test_three_write.py`

- [ ] **Step 1: Remove update_beliefs and update_probability from GraphStore ABC**

Remove both abstract methods from `graph_store.py`.

- [ ] **Step 2: Remove implementations from KuzuGraphStore and Neo4jGraphStore**

Remove `update_beliefs()` and `update_probability()` methods. Also remove `belief` and `probability` properties from graph node schemas if they exist (Kuzu Knowledge node has `belief` field, Chain CONCLUSION has `probability` — keep the fields but stop actively writing to them; OR remove if no queries depend on them).

Decision: **Keep the fields in graph schema** for now (no-op) — removing them requires migration. Just remove the write methods.

- [ ] **Step 3: Update StorageManager**

In `manager.py`, update `add_probabilities()` and `write_beliefs()` to stop calling graph store:

```python
    async def add_probabilities(self, records: list[ProbabilityRecord]) -> None:
        """Write probabilities to ContentStore."""
        await self.content_store.write_probabilities(records)

    async def write_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Write belief snapshots to ContentStore."""
        await self.content_store.write_belief_snapshots(snapshots)
```

- [ ] **Step 4: Update tests**

Remove tests for `update_beliefs`/`update_probability` from `test_graph_store.py`. Update `test_three_write.py` to remove expectations about graph store belief/probability sync.

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add libs/storage/graph_store.py libs/storage/kuzu_graph_store.py libs/storage/neo4j_graph_store.py libs/storage/manager.py tests/libs/storage/test_graph_store.py tests/libs/storage/test_three_write.py
git commit -m "refactor(graph): remove update_beliefs/update_probability, probabilities now in GlobalInferenceState"
```

---

## Chunk 4: StorageManager Orchestration

Wire all new models through StorageManager as the unified facade.

### Task 11: Update ingest_package to accept factors and submission_artifact

**Files:**
- Modify: `libs/storage/manager.py`
- Modify: `tests/libs/storage/test_three_write.py`

- [ ] **Step 1: Write failing test**

```python
async def test_ingest_package_with_factors_and_artifact(tmp_path):
    """ingest_package accepts factors and submission_artifact."""
    from libs.storage.models import FactorNode, PackageSubmissionArtifact

    config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()

    pkg = Package(
        package_id="pkg", name="pkg", version="1.0.0",
        submitter="test", submitted_at=datetime.now(), status="merged",
    )
    k1 = Knowledge(
        knowledge_id="pkg/k1", version=1, type="claim", content="X",
        prior=0.7, source_package_id="pkg", source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    mod = Module(
        module_id="pkg.mod", package_id="pkg", name="mod", role="reasoning",
        chain_ids=[], export_ids=["pkg/k1"],
    )
    factors = [
        FactorNode(
            factor_id="pkg.mod.f1", type="reasoning",
            premises=["pkg/k1"], conclusion="pkg/k1", package_id="pkg",
        ),
    ]
    artifact = PackageSubmissionArtifact(
        package_name="pkg", commit_hash="abc123",
        source_files={"main.gaia": "knowledge { content: 'X' }"},
        raw_graph={}, local_canonical_graph={},
        canonicalization_log=[], submitted_at=datetime.now(),
    )

    await mgr.ingest_package(
        package=pkg, modules=[mod], knowledge_items=[k1], chains=[],
        factors=factors, submission_artifact=artifact,
    )

    # Verify factors stored
    result_factors = await mgr.get_factors_by_package("pkg")
    assert len(result_factors) == 1

    # Verify artifact stored
    result_art = await mgr.get_submission_artifact("pkg", "abc123")
    assert result_art is not None
    assert result_art.package_name == "pkg"

    await mgr.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_three_write.py::test_ingest_package_with_factors_and_artifact -v`
Expected: FAIL — signature doesn't accept `factors`/`submission_artifact`

- [ ] **Step 3: Update ingest_package signature and implementation**

```python
    async def ingest_package(
        self,
        package: Package,
        modules: list[Module],
        knowledge_items: list[Knowledge],
        chains: list[Chain],
        factors: list[FactorNode] | None = None,
        submission_artifact: PackageSubmissionArtifact | None = None,
        embeddings: list[KnowledgeEmbedding] | None = None,
    ) -> None:
        # ... existing steps 1-4 ...

        # After Step 1 (ContentStore writes), add:
        if factors:
            await self.content_store.write_factors(factors)
        if submission_artifact:
            await self.content_store.write_submission_artifact(submission_artifact)

        # After Step 2 (GraphStore), add:
        if self.graph_store is not None and factors:
            await self.graph_store.write_factor_topology(factors)

        # Steps 3-4 unchanged
```

- [ ] **Step 4: Add new facade methods**

```python
    # Factor queries
    async def list_factors(self) -> list[FactorNode]:
        return await self.content_store.list_factors()

    async def get_factors_by_package(self, package_id: str) -> list[FactorNode]:
        return await self.content_store.get_factors_by_package(package_id)

    # Submission artifact
    async def get_submission_artifact(
        self, package: str, commit_hash: str
    ) -> PackageSubmissionArtifact | None:
        return await self.content_store.get_submission_artifact(package, commit_hash)
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/libs/storage/test_three_write.py -v`
Expected: ALL PASS

- [ ] **Step 6: Commit**

```bash
git add libs/storage/manager.py tests/libs/storage/test_three_write.py
git commit -m "feat(manager): extend ingest_package with factors and submission_artifact"
```

### Task 12: Add canonical binding, global node, and inference state facade methods

**Files:**
- Modify: `libs/storage/manager.py`
- Modify: `tests/libs/storage/test_manager.py`

- [ ] **Step 1: Write failing tests**

```python
async def test_write_and_read_canonical_bindings(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="kuzu")
    mgr = StorageManager(config)
    await mgr.initialize()

    bindings = [
        CanonicalBinding(
            package="pkg", version="1.0.0", local_graph_hash="sha256:abc",
            local_canonical_id="pkg/lc1", decision="create_new",
            global_canonical_id="gcn_01", decided_at=datetime.now(), decided_by="auto",
        ),
    ]
    global_nodes = [
        GlobalCanonicalNode(
            global_canonical_id="gcn_01", knowledge_type="claim",
            representative_content="X is true",
        ),
    ]

    await mgr.write_canonical_bindings(bindings, global_nodes)

    result_bindings = await mgr.get_bindings_for_package("pkg", "1.0.0")
    assert len(result_bindings) == 1

    result_node = await mgr.get_global_node("gcn_01")
    assert result_node is not None

    await mgr.close()


async def test_inference_state_roundtrip(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="none")
    mgr = StorageManager(config)
    await mgr.initialize()

    assert await mgr.get_inference_state() is None

    state = GlobalInferenceState(
        graph_hash="sha256:xyz",
        node_priors={"gcn_01": 0.7},
        factor_parameters={"f1": FactorParams(conditional_probability=0.9)},
        updated_at=datetime.now(),
    )
    await mgr.update_inference_state(state)

    result = await mgr.get_inference_state()
    assert result is not None
    assert result.graph_hash == "sha256:xyz"

    await mgr.close()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/libs/storage/test_manager.py -k "canonical_binding or inference_state" -v`
Expected: FAIL

- [ ] **Step 3: Implement facade methods**

```python
    # Canonical Bindings + Global Nodes (integration phase)
    async def write_canonical_bindings(
        self,
        bindings: list[CanonicalBinding],
        global_nodes: list[GlobalCanonicalNode],
    ) -> None:
        """Write canonical bindings and global nodes to ContentStore + GraphStore."""
        await self.content_store.write_canonical_bindings(bindings)
        await self.content_store.upsert_global_nodes(global_nodes)
        if self.graph_store is not None:
            await self.graph_store.write_global_topology(bindings, global_nodes)

    async def get_bindings_for_package(
        self, package: str, version: str
    ) -> list[CanonicalBinding]:
        return await self.content_store.get_canonical_bindings(package, version)

    async def get_global_node(self, global_id: str) -> GlobalCanonicalNode | None:
        return await self.content_store.get_global_node(global_id)

    # Global Inference State
    async def get_inference_state(self) -> GlobalInferenceState | None:
        return await self.content_store.get_inference_state()

    async def update_inference_state(self, state: GlobalInferenceState) -> None:
        await self.content_store.update_inference_state(state)
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/libs/storage/test_manager.py -v`
Expected: ALL PASS

- [ ] **Step 5: Commit**

```bash
git add libs/storage/manager.py tests/libs/storage/test_manager.py
git commit -m "feat(manager): add canonical binding, global node, and inference state facade"
```

### Task 13: Add load_global_factor_graph for BP

**Files:**
- Modify: `libs/storage/manager.py`
- Modify: `tests/libs/storage/test_manager.py`

- [ ] **Step 1: Write failing test**

```python
async def test_load_global_factor_graph(tmp_path):
    """load_global_factor_graph returns all factors + current inference state."""
    config = StorageConfig(lancedb_path=str(tmp_path / "lance"), graph_backend="none")
    mgr = StorageManager(config)
    await mgr.initialize()

    # Seed data
    pkg = Package(
        package_id="pkg", name="pkg", version="1.0.0",
        submitter="test", submitted_at=datetime.now(), status="merged",
    )
    k = Knowledge(
        knowledge_id="pkg/k1", version=1, type="claim", content="X",
        prior=0.7, source_package_id="pkg", source_module_id="pkg.mod",
        created_at=datetime.now(),
    )
    mod = Module(module_id="pkg.mod", package_id="pkg", name="mod", role="reasoning")
    factors = [
        FactorNode(
            factor_id="pkg.f1", type="reasoning",
            premises=["pkg/k1"], conclusion="pkg/k1", package_id="pkg",
        ),
    ]
    state = GlobalInferenceState(
        graph_hash="sha256:abc",
        node_priors={"gcn_01": 0.7},
        factor_parameters={"pkg.f1": FactorParams(conditional_probability=0.9)},
        updated_at=datetime.now(),
    )

    await mgr.ingest_package(
        package=pkg, modules=[mod], knowledge_items=[k], chains=[],
        factors=factors,
    )
    await mgr.update_inference_state(state)

    result_factors, result_state = await mgr.load_global_factor_graph()
    assert len(result_factors) == 1
    assert result_state is not None
    assert result_state.graph_hash == "sha256:abc"

    await mgr.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_manager.py::test_load_global_factor_graph -v`
Expected: FAIL

- [ ] **Step 3: Implement**

```python
    async def load_global_factor_graph(
        self,
    ) -> tuple[list[FactorNode], GlobalInferenceState | None]:
        """Load all factors and the current global inference state for BP execution."""
        factors = await self.content_store.list_factors()
        state = await self.content_store.get_inference_state()
        return factors, state
```

- [ ] **Step 4: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 5: Lint and format**

Run: `ruff check . && ruff format --check .`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add libs/storage/manager.py tests/libs/storage/test_manager.py
git commit -m "feat(manager): add load_global_factor_graph for BP execution"
```

### Task 14: Update __init__.py exports and final cleanup

**Files:**
- Modify: `libs/storage/__init__.py`

- [ ] **Step 1: Update exports**

Ensure all new models are exported from `libs/storage/__init__.py`:

```python
from libs.storage.config import StorageConfig
from libs.storage.content_store import ContentStore
from libs.storage.graph_store import GraphStore
from libs.storage.manager import StorageManager
from libs.storage.models import (
    BeliefSnapshot,
    CanonicalBinding,
    Chain,
    ChainStep,
    FactorNode,
    FactorParams,
    GlobalCanonicalNode,
    GlobalInferenceState,
    Knowledge,
    KnowledgeEmbedding,
    KnowledgeRef,
    LocalCanonicalRef,
    Module,
    Package,
    PackageRef,
    PackageSubmissionArtifact,
    Parameter,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
    SourceRef,
    Subgraph,
)
from libs.storage.vector_store import VectorStore
```

- [ ] **Step 2: Run full test suite**

Run: `pytest tests/ -v`
Expected: ALL PASS

- [ ] **Step 3: Lint and format**

Run: `ruff check . && ruff format .`

- [ ] **Step 4: Commit**

```bash
git add libs/storage/__init__.py
git commit -m "chore: export all new storage models from __init__.py"
```

---

## Execution Checklist

After all tasks complete:

1. `pytest tests/ -v` — ALL PASS
2. `ruff check .` — clean
3. `ruff format --check .` — clean
4. `git log --oneline` — verify ~14 clean commits
5. Push branch and create PR
