# Storage V2 Chunk 1: Models + ABCs + Fixtures

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Establish the data model contracts, storage ABCs, and test fixtures for the new Gaia Language-based storage layer.

**Architecture:** New storage layer lives in `libs/storage_v2/`. Pydantic v2 models define all 9 entities from `docs/foundations/server/storage-schema.md`. Three ABCs (`ContentStore`, `GraphStore`, `VectorStore`) define the backend contracts. JSON fixtures provide test data for all entities.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest, asyncio

**Reference docs:**
- `docs/foundations/server/storage-schema.md` — entity definitions, field specs
- `docs/foundations/server/architecture.md` — StorageManager interface, three-write logic
- `docs/plans/2026-03-10-storage-v2-design.md` — overall design

---

### Task 1: Create package structure

**Files:**
- Create: `libs/storage_v2/__init__.py`

**Step 1: Create the package directory and init file**

```python
# libs/storage_v2/__init__.py
"""Storage layer v2 — based on Gaia Language concepts."""
```

**Step 2: Verify import works**

Run: `cd /Users/dp/Projects/Gaia/.worktrees/storage-impl && python -c "import libs.storage_v2"`
Expected: No error

**Step 3: Commit**

```bash
git add libs/storage_v2/__init__.py
git commit -m "feat(storage_v2): create package structure"
```

---

### Task 2: Pydantic models — core entities

**Files:**
- Create: `libs/storage_v2/models.py`

**Step 1: Write the test file**

Create `tests/libs/storage_v2/__init__.py` (empty) and `tests/libs/storage_v2/test_models.py`:

```python
"""Tests for storage v2 Pydantic models."""

import json
from datetime import datetime
from pathlib import Path

import pytest

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    ChainStep,
    Closure,
    ClosureRef,
    ImportRef,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
)

FIXTURES = Path(__file__).parents[2] / "fixtures" / "storage_v2"


def load_fixture(name: str) -> list[dict]:
    return json.loads((FIXTURES / f"{name}.json").read_text())


class TestClosureRef:
    def test_basic(self):
        ref = ClosureRef(closure_id="galileo.heavier_falls_faster", version=1)
        assert ref.closure_id == "galileo.heavier_falls_faster"
        assert ref.version == 1


class TestClosure:
    def test_from_fixture(self):
        data = load_fixture("closures")
        closures = [Closure.model_validate(d) for d in data]
        assert len(closures) >= 2
        c = closures[0]
        assert isinstance(c.closure_id, str)
        assert isinstance(c.version, int)
        assert c.type in ("claim", "question", "setting", "action")
        assert 0 < c.prior <= 1.0
        assert isinstance(c.keywords, list)
        assert isinstance(c.created_at, datetime)

    def test_version_uniqueness_key(self):
        """(closure_id, version) should be the identity."""
        c1 = Closure.model_validate(load_fixture("closures")[0])
        c2 = c1.model_copy(update={"version": c1.version + 1, "content": "revised"})
        assert c1.closure_id == c2.closure_id
        assert c1.version != c2.version

    def test_setting_allows_prior_one(self):
        c = Closure(
            closure_id="test.setting",
            version=1,
            type="setting",
            content="A controlled environment.",
            prior=1.0,
            keywords=[],
            source_package_id="test",
            source_module_id="test.mod",
            created_at=datetime.now(),
        )
        assert c.prior == 1.0


class TestChainStep:
    def test_basic(self):
        step = ChainStep(
            step_index=0,
            premises=[ClosureRef(closure_id="a", version=1)],
            reasoning="Because A, therefore B.",
            conclusion=ClosureRef(closure_id="b", version=1),
        )
        assert step.step_index == 0
        assert len(step.premises) == 1
        assert step.conclusion.closure_id == "b"


class TestChain:
    def test_from_fixture(self):
        data = load_fixture("chains")
        chains = [Chain.model_validate(d) for d in data]
        assert len(chains) >= 1
        ch = chains[0]
        assert isinstance(ch.chain_id, str)
        assert ch.type in (
            "deduction", "induction", "abstraction", "contradiction", "retraction"
        )
        assert len(ch.steps) >= 1
        assert isinstance(ch.steps[0], ChainStep)
        assert isinstance(ch.steps[0].premises[0], ClosureRef)


class TestModule:
    def test_from_fixture(self):
        data = load_fixture("modules")
        modules = [Module.model_validate(d) for d in data]
        assert len(modules) >= 1
        m = modules[0]
        assert isinstance(m.module_id, str)
        assert isinstance(m.imports, list)


class TestPackage:
    def test_from_fixture(self):
        data = load_fixture("packages")
        packages = [Package.model_validate(d) for d in data]
        assert len(packages) >= 1
        p = packages[0]
        assert isinstance(p.package_id, str)
        assert p.status in ("submitted", "merged", "rejected")


class TestProbabilityRecord:
    def test_from_fixture(self):
        data = load_fixture("probabilities")
        records = [ProbabilityRecord.model_validate(d) for d in data]
        assert len(records) >= 1
        r = records[0]
        assert 0 < r.value <= 1.0
        assert r.source in ("author", "llm_review", "lean_verify", "code_verify")


class TestBeliefSnapshot:
    def test_from_fixture(self):
        data = load_fixture("beliefs")
        snapshots = [BeliefSnapshot.model_validate(d) for d in data]
        assert len(snapshots) >= 1
        s = snapshots[0]
        assert 0 <= s.belief <= 1.0
        assert isinstance(s.bp_run_id, str)


class TestResource:
    def test_from_fixture(self):
        data = load_fixture("resources")
        resources = [Resource.model_validate(d) for d in data]
        assert len(resources) >= 1
        r = resources[0]
        assert isinstance(r.resource_id, str)
        assert isinstance(r.storage_path, str)


class TestResourceAttachment:
    def test_from_fixture(self):
        data = load_fixture("attachments")
        attachments = [ResourceAttachment.model_validate(d) for d in data]
        assert len(attachments) >= 1
        a = attachments[0]
        assert a.target_type in ("closure", "chain", "chain_step", "module", "package")

    def test_chain_step_composite_key(self):
        a = ResourceAttachment(
            resource_id="res-1",
            target_type="chain_step",
            target_id="galileo.reasoning.tied_bodies:2",
            role="evidence",
        )
        assert ":" in a.target_id
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/dp/Projects/Gaia/.worktrees/storage-impl && python -m pytest tests/libs/storage_v2/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'libs.storage_v2.models'`

**Step 3: Write the models**

Create `libs/storage_v2/models.py`:

```python
"""Pydantic v2 models for storage layer v2.

Based on docs/foundations/server/storage-schema.md.
All IDs are strings. Closure identity is (closure_id, version).
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


# ── References ──


class ClosureRef(BaseModel):
    """Versioned reference to a Closure."""

    closure_id: str
    version: int


class ImportRef(BaseModel):
    """Cross-module dependency reference."""

    closure_id: str
    version: int
    strength: Literal["strong", "weak"]


# ── Core Entities ──


class Closure(BaseModel):
    """Versioned knowledge object. Identity: (closure_id, version)."""

    closure_id: str
    version: int
    type: Literal["claim", "question", "setting", "action"]
    content: str
    prior: float  # (0, 1), setting allows 1.0
    keywords: list[str] = []
    source_package_id: str
    source_module_id: str
    created_at: datetime
    embedding: list[float] | None = None


class ChainStep(BaseModel):
    """Single reasoning step within a Chain."""

    step_index: int
    premises: list[ClosureRef]
    reasoning: str
    conclusion: ClosureRef


class Chain(BaseModel):
    """Reasoning link connecting closures."""

    chain_id: str
    module_id: str
    package_id: str
    type: Literal["deduction", "induction", "abstraction", "contradiction", "retraction"]
    steps: list[ChainStep]


class Module(BaseModel):
    """Cohesive knowledge unit grouping closures and chains."""

    module_id: str
    package_id: str
    name: str
    role: Literal["reasoning", "setting", "motivation", "follow_up_question", "other"]
    imports: list[ImportRef] = []
    chain_ids: list[str] = []
    export_ids: list[str] = []


class Package(BaseModel):
    """Knowledge container, corresponds to one git repo."""

    package_id: str
    name: str
    version: str
    description: str | None = None
    modules: list[str] = []  # module_id list (ordered)
    exports: list[str] = []  # exported closure_ids
    submitter: str
    submitted_at: datetime
    status: Literal["submitted", "merged", "rejected"] = "submitted"


# ── Probability & Belief ──


class ProbabilityRecord(BaseModel):
    """Per-step probability, multi-source."""

    chain_id: str
    step_index: int
    value: float  # (0, 1], induction must be < 1.0
    source: Literal["author", "llm_review", "lean_verify", "code_verify"]
    source_detail: str | None = None
    recorded_at: datetime


class BeliefSnapshot(BaseModel):
    """BP result for a closure at a point in time."""

    closure_id: str
    version: int
    belief: float  # [0, 1]
    bp_run_id: str
    computed_at: datetime


# ── Resources ──


class Resource(BaseModel):
    """Metadata for a multimedia resource stored in TOS."""

    resource_id: str
    type: Literal[
        "image", "code", "notebook", "dataset", "checkpoint", "tool_output", "other"
    ]
    format: str  # png, py, ipynb, parquet, ...
    title: str | None = None
    description: str | None = None
    storage_backend: str = "tos"
    storage_path: str
    size_bytes: int | None = None
    checksum: str | None = None  # sha256
    metadata: dict = {}
    created_at: datetime
    source_package_id: str


class ResourceAttachment(BaseModel):
    """Many-to-many link between Resource and other entities."""

    resource_id: str
    target_type: Literal["closure", "chain", "chain_step", "module", "package"]
    target_id: str  # chain_step uses "chain_id:step_index"
    role: Literal["evidence", "visualization", "implementation", "reproduction", "supplement"]
    description: str | None = None
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/libs/storage_v2/test_models.py -v`
Expected: FAIL — fixture files don't exist yet (that's Task 3)

---

### Task 3: Create fixture JSON files

**Files:**
- Create: `tests/fixtures/storage_v2/packages.json`
- Create: `tests/fixtures/storage_v2/modules.json`
- Create: `tests/fixtures/storage_v2/closures.json`
- Create: `tests/fixtures/storage_v2/chains.json`
- Create: `tests/fixtures/storage_v2/probabilities.json`
- Create: `tests/fixtures/storage_v2/beliefs.json`
- Create: `tests/fixtures/storage_v2/resources.json`
- Create: `tests/fixtures/storage_v2/attachments.json`

All fixtures based on the Galileo falling bodies example from `tests/fixtures/gaia_language_packages/galileo_falling_bodies/`.

The fixture data should form a coherent knowledge graph:
- 1 package (galileo_falling_bodies)
- 2 modules (setting, reasoning)
- ~5 closures (heavier_falls_faster, thought_experiment_env, combined_slower, combined_faster, contradiction)
- 1-2 chains (tied_bodies_deduction)
- probability records for each chain step
- belief snapshots from 2 mock BP runs
- 1 resource (a figure) with 1 attachment

See `docs/foundations/server/storage-schema.md` §2 for exact field specs.

**Step 1: Create the fixture directory and all 8 JSON files**

(Files will contain valid JSON matching the Pydantic models from Task 2. Content based on the galileo package — closures about Aristotle's claim, thought experiment setup, contradictory conclusions, etc.)

**Step 2: Run model tests to verify fixtures load correctly**

Run: `python -m pytest tests/libs/storage_v2/test_models.py -v`
Expected: All tests PASS

**Step 3: Commit**

```bash
git add tests/fixtures/storage_v2/ tests/libs/storage_v2/ libs/storage_v2/models.py
git commit -m "feat(storage_v2): add Pydantic models and fixture data"
```

---

### Task 4: Storage config

**Files:**
- Create: `libs/storage_v2/config.py`

**Step 1: Write the config**

```python
"""Storage v2 configuration."""

import os
from typing import Literal

from pydantic import BaseModel


class StorageConfig(BaseModel):
    """Environment-driven storage configuration."""

    # LanceDB (required)
    lancedb_path: str = os.environ.get("GAIA_LANCEDB_PATH", "/data/lancedb/gaia_v2")

    # Graph backend
    graph_backend: Literal["neo4j", "kuzu", "none"] = os.environ.get(
        "GAIA_GRAPH_BACKEND", "kuzu"
    )

    # Neo4j
    neo4j_uri: str = os.environ.get("GAIA_NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.environ.get("GAIA_NEO4J_USER", "neo4j")
    neo4j_password: str = os.environ.get("GAIA_NEO4J_PASSWORD", "")
    neo4j_database: str = os.environ.get("GAIA_NEO4J_DATABASE", "neo4j")

    # Kuzu
    kuzu_path: str | None = None

    # Vector index
    vector_index_type: Literal["diskann", "ivf_pq"] = "diskann"
```

**Step 2: Verify import**

Run: `python -c "from libs.storage_v2.config import StorageConfig; print(StorageConfig())"`
Expected: Prints config with defaults

**Step 3: Commit**

```bash
git add libs/storage_v2/config.py
git commit -m "feat(storage_v2): add storage config"
```

---

### Task 5: ContentStore ABC

**Files:**
- Create: `libs/storage_v2/content_store.py`

**Step 1: Write the ABC**

```python
"""ContentStore ABC — LanceDB backend contract."""

from abc import ABC, abstractmethod

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
)


class ScoredClosure(BaseModel):
    """Search result with score."""

    closure: Closure
    score: float


class ContentStore(ABC):
    """Source-of-truth content store (LanceDB)."""

    # ── Write ──

    @abstractmethod
    async def write_package(self, package: Package, modules: list[Module]) -> None: ...

    @abstractmethod
    async def write_closures(self, closures: list[Closure]) -> None: ...

    @abstractmethod
    async def write_chains(self, chains: list[Chain]) -> None: ...

    @abstractmethod
    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None: ...

    @abstractmethod
    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None: ...

    @abstractmethod
    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None: ...

    # ── Read ──

    @abstractmethod
    async def get_closure(
        self, closure_id: str, version: int | None = None
    ) -> Closure | None: ...

    @abstractmethod
    async def get_closure_versions(self, closure_id: str) -> list[Closure]: ...

    @abstractmethod
    async def get_package(self, package_id: str) -> Package | None: ...

    @abstractmethod
    async def get_module(self, module_id: str) -> Module | None: ...

    @abstractmethod
    async def get_chains_by_module(self, module_id: str) -> list[Chain]: ...

    @abstractmethod
    async def get_probability_history(
        self, chain_id: str, step_index: int | None = None
    ) -> list[ProbabilityRecord]: ...

    @abstractmethod
    async def get_belief_history(self, closure_id: str) -> list[BeliefSnapshot]: ...

    @abstractmethod
    async def get_resources_for(
        self, target_type: str, target_id: str
    ) -> list[Resource]: ...

    # ── Search ──

    @abstractmethod
    async def search_bm25(self, text: str, top_k: int) -> list[ScoredClosure]: ...

    # ── BP Bulk Load ──

    @abstractmethod
    async def list_closures(self) -> list[Closure]: ...

    @abstractmethod
    async def list_chains(self) -> list[Chain]: ...
```

Note: `ScoredClosure` should be added to `models.py` instead of defined here. Move it there.

**Step 2: Verify import**

Run: `python -c "from libs.storage_v2.content_store import ContentStore"`
Expected: No error

**Step 3: Commit**

```bash
git add libs/storage_v2/content_store.py
git commit -m "feat(storage_v2): add ContentStore ABC"
```

---

### Task 6: GraphStore ABC

**Files:**
- Create: `libs/storage_v2/graph_store.py`

**Step 1: Write the ABC**

```python
"""GraphStore ABC — graph topology backend contract."""

from abc import ABC, abstractmethod

from libs.storage_v2.models import (
    Chain,
    Closure,
    ResourceAttachment,
    ScoredClosure,
    Subgraph,
)


class GraphStore(ABC):
    """Graph topology store (Neo4j / Kuzu)."""

    @abstractmethod
    async def initialize_schema(self) -> None: ...

    # ── Write ──

    @abstractmethod
    async def write_topology(
        self, closures: list[Closure], chains: list[Chain]
    ) -> None: ...

    @abstractmethod
    async def write_resource_links(
        self, attachments: list[ResourceAttachment]
    ) -> None: ...

    @abstractmethod
    async def update_beliefs(self, beliefs: dict[str, float]) -> None: ...

    @abstractmethod
    async def update_probability(
        self, chain_id: str, step_index: int, value: float
    ) -> None: ...

    # ── Query ──

    @abstractmethod
    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph: ...

    @abstractmethod
    async def get_subgraph(
        self, closure_id: str, max_closures: int = 500
    ) -> Subgraph: ...

    @abstractmethod
    async def search_topology(
        self, seed_ids: list[str], hops: int = 1
    ) -> list[ScoredClosure]: ...

    # ── Lifecycle ──

    @abstractmethod
    async def close(self) -> None: ...
```

Note: `Subgraph` model needs to be added to `models.py`:

```python
class Subgraph(BaseModel):
    """Subgraph query result."""
    closure_ids: set[str]
    chain_ids: set[str]
```

**Step 2: Verify import**

Run: `python -c "from libs.storage_v2.graph_store import GraphStore"`

**Step 3: Commit**

```bash
git add libs/storage_v2/graph_store.py
git commit -m "feat(storage_v2): add GraphStore ABC"
```

---

### Task 7: VectorStore ABC

**Files:**
- Create: `libs/storage_v2/vector_store.py`

**Step 1: Write the ABC**

```python
"""VectorStore ABC — embedding search backend contract."""

from abc import ABC, abstractmethod

from libs.storage_v2.models import ScoredClosure


class ClosureEmbedding(BaseModel):
    """Embedding entry for vector store."""
    closure_id: str
    version: int
    embedding: list[float]


class VectorStore(ABC):
    """Vector similarity search store."""

    @abstractmethod
    async def write_embeddings(self, items: list[ClosureEmbedding]) -> None: ...

    @abstractmethod
    async def search(
        self, embedding: list[float], top_k: int
    ) -> list[ScoredClosure]: ...
```

Note: `ClosureEmbedding` should also go in `models.py`.

**Step 2: Verify import**

Run: `python -c "from libs.storage_v2.vector_store import VectorStore"`

**Step 3: Commit**

```bash
git add libs/storage_v2/vector_store.py
git commit -m "feat(storage_v2): add VectorStore ABC"
```

---

### Task 8: Update __init__.py exports and final verification

**Files:**
- Modify: `libs/storage_v2/__init__.py`

**Step 1: Update exports**

```python
"""Storage layer v2 — based on Gaia Language concepts."""

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.vector_store import VectorStore

__all__ = ["ContentStore", "GraphStore", "StorageConfig", "VectorStore"]
```

**Step 2: Run all model tests**

Run: `python -m pytest tests/libs/storage_v2/ -v`
Expected: All PASS

**Step 3: Run ruff**

Run: `ruff check libs/storage_v2/ tests/libs/storage_v2/ && ruff format --check libs/storage_v2/ tests/libs/storage_v2/`
Expected: Clean

**Step 4: Commit**

```bash
git add libs/storage_v2/__init__.py
git commit -m "feat(storage_v2): export public API from __init__"
```

---

## Summary

After completing all 8 tasks, Chunk 1 delivers:

- 11 Pydantic models in `libs/storage_v2/models.py`
- 3 ABCs defining the storage contract
- `StorageConfig` for environment-driven configuration
- 8 fixture JSON files with coherent galileo test data
- Full model test coverage

Chunk 2 (ContentStore LanceDB implementation) can then start building on these contracts.
