# P1+P2 Implementation Plan: Gaia CLI MVP + Review + Publish

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a working `gaia` CLI that can init packages, add claims, run local BP, validate/build, LLM review, and publish to remote.

**Architecture:** The CLI (`cli/`) is a new top-level package alongside `libs/` and `services/`. It uses `typer` for CLI framework, reads/writes YAML claim files and TOML config, and reuses the existing `libs/storage/` and `services/inference_engine/` for local storage and BP. A new `GraphStore` ABC abstracts graph backends so the CLI uses embedded Kuzu while the server keeps Neo4j.

**Tech Stack:** Python 3.12+, typer, PyYAML, tomli/tomli_w, Kuzu, LanceDB (existing), BP engine (existing)

**Issues covered:** #45, #50, #46, #23, #24 (P1) + #47, #48, #40, #20 (P2)

**Dependency graph:**
```
#50 GraphStore ABC + Kuzu ──┐
                            ├──→ #45 CLI Framework ──→ #46 gaia build ──→ #47 gaia review ──→ #48 gaia publish
#23 Retraction Edge ──→ #24 Type-Aware BP ───────────┘                        │
                                                                              ↓
                                                              #20 inference tests + #40 fixture integration tests
```

---

## Phase 1: Storage Abstraction (#50 + #23)

### Task 1: Extract GraphStore ABC from Neo4jGraphStore

**Files:**
- Create: `libs/storage/graph_store.py`
- Modify: `libs/storage/neo4j_store.py`
- Modify: `libs/storage/manager.py`
- Modify: `libs/storage/__init__.py`
- Test: `tests/libs/storage/test_neo4j_store.py` (existing, verify still passes)

**Step 1: Create the GraphStore ABC**

```python
# libs/storage/graph_store.py
"""Abstract base class for graph storage backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from libs.models import HyperEdge


class GraphStore(ABC):
    """Abstract graph store for the Gaia hypergraph.

    Implementations must support hyperedge CRUD and subgraph traversal.
    """

    @abstractmethod
    async def initialize_schema(self) -> None: ...

    @abstractmethod
    async def create_hyperedge(self, edge: HyperEdge) -> int: ...

    @abstractmethod
    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]: ...

    @abstractmethod
    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None: ...

    @abstractmethod
    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None: ...

    @abstractmethod
    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]: ...

    @abstractmethod
    async def close(self) -> None: ...
```

**Step 2: Make Neo4jGraphStore inherit from GraphStore**

In `libs/storage/neo4j_store.py`, change:
```python
from libs.storage.graph_store import GraphStore

class Neo4jGraphStore(GraphStore):
    ...
```

**Step 3: Update StorageManager type annotation**

In `libs/storage/manager.py`, change:
```python
from .graph_store import GraphStore
...
class StorageManager:
    graph: GraphStore | None  # was Neo4jGraphStore | None
```

**Step 4: Update `__init__.py` exports**

In `libs/storage/__init__.py`, add `GraphStore` to exports.

**Step 5: Run existing tests to verify no breakage**

Run: `pytest tests/libs/storage/ -v`
Expected: All existing tests pass unchanged.

**Step 6: Commit**

```bash
git add libs/storage/graph_store.py libs/storage/neo4j_store.py libs/storage/manager.py libs/storage/__init__.py
git commit -m "refactor: extract GraphStore ABC from Neo4jGraphStore (#50)"
```

---

### Task 2: Implement KuzuGraphStore

**Files:**
- Create: `libs/storage/kuzu_store.py`
- Create: `tests/libs/storage/test_kuzu_store.py`

**Step 1: Write the failing test**

```python
# tests/libs/storage/test_kuzu_store.py
"""Tests for KuzuGraphStore — embedded graph database for local CLI."""

import pytest
from libs.models import HyperEdge
from libs.storage.kuzu_store import KuzuGraphStore


@pytest.fixture
async def kuzu_store(tmp_path):
    store = KuzuGraphStore(db_path=str(tmp_path / "kuzu_db"))
    await store.initialize_schema()
    yield store
    await store.close()


async def test_create_and_get_hyperedge(kuzu_store):
    edge = HyperEdge(
        id=100, type="deduction", tail=[1, 2], head=[3],
        probability=0.9, reasoning=[{"content": "test"}],
    )
    eid = await kuzu_store.create_hyperedge(edge)
    assert eid == 100

    loaded = await kuzu_store.get_hyperedge(100)
    assert loaded is not None
    assert loaded.id == 100
    assert set(loaded.tail) == {1, 2}
    assert loaded.head == [3]
    assert loaded.probability == pytest.approx(0.9)


async def test_get_nonexistent_returns_none(kuzu_store):
    assert await kuzu_store.get_hyperedge(999) is None


async def test_create_bulk(kuzu_store):
    edges = [
        HyperEdge(id=1, type="deduction", tail=[10], head=[20], probability=0.8),
        HyperEdge(id=2, type="induction", tail=[20], head=[30], probability=0.7),
    ]
    ids = await kuzu_store.create_hyperedges_bulk(edges)
    assert ids == [1, 2]
    assert await kuzu_store.get_hyperedge(1) is not None
    assert await kuzu_store.get_hyperedge(2) is not None


async def test_update_hyperedge(kuzu_store):
    edge = HyperEdge(id=100, type="deduction", tail=[1], head=[2], probability=0.5)
    await kuzu_store.create_hyperedge(edge)
    await kuzu_store.update_hyperedge(100, probability=0.9)
    loaded = await kuzu_store.get_hyperedge(100)
    assert loaded.probability == pytest.approx(0.9)


async def test_subgraph_one_hop(kuzu_store):
    """A -> B -> C, subgraph from A with 1 hop should find edge 1 and nodes A, B."""
    await kuzu_store.create_hyperedge(
        HyperEdge(id=1, type="deduction", tail=[1], head=[2], probability=0.9)
    )
    await kuzu_store.create_hyperedge(
        HyperEdge(id=2, type="deduction", tail=[2], head=[3], probability=0.8)
    )
    node_ids, edge_ids = await kuzu_store.get_subgraph([1], hops=1)
    assert 1 in edge_ids
    assert 1 in node_ids and 2 in node_ids

    # 2 hops should reach C
    node_ids2, edge_ids2 = await kuzu_store.get_subgraph([1], hops=2)
    assert 2 in edge_ids2
    assert 3 in node_ids2
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage/test_kuzu_store.py -v`
Expected: ImportError (kuzu_store module doesn't exist yet)

**Step 3: Install kuzu and implement KuzuGraphStore**

Run: `pip install kuzu`

Then create `libs/storage/kuzu_store.py`:

```python
"""Kuzu-backed embedded graph store for local Gaia CLI."""

from __future__ import annotations

import json
from typing import Any

import kuzu

from libs.models import HyperEdge
from libs.storage.graph_store import GraphStore


class KuzuGraphStore(GraphStore):
    """Embedded graph store using Kuzu. Zero-config, pip install kuzu."""

    def __init__(self, db_path: str) -> None:
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)

    async def initialize_schema(self) -> None:
        try:
            self._conn.execute("CREATE NODE TABLE IF NOT EXISTS Proposition(id INT64, PRIMARY KEY(id))")
            self._conn.execute(
                "CREATE NODE TABLE IF NOT EXISTS Hyperedge("
                "id INT64, type STRING, subtype STRING, "
                "probability DOUBLE, verified BOOLEAN, reasoning STRING, "
                "PRIMARY KEY(id))"
            )
            self._conn.execute(
                "CREATE REL TABLE IF NOT EXISTS TAIL(FROM Proposition TO Hyperedge)"
            )
            self._conn.execute(
                "CREATE REL TABLE IF NOT EXISTS HEAD(FROM Hyperedge TO Proposition)"
            )
        except kuzu.RuntimeError:
            pass  # Tables already exist

    async def create_hyperedge(self, edge: HyperEdge) -> int:
        # Ensure proposition nodes exist
        for nid in set(edge.tail + edge.head):
            self._conn.execute(
                "MERGE (p:Proposition {id: $id})", {"id": nid}
            )
        # Create hyperedge node
        self._conn.execute(
            "CREATE (h:Hyperedge {id: $id, type: $type, subtype: $subtype, "
            "probability: $prob, verified: $verified, reasoning: $reasoning})",
            {
                "id": edge.id,
                "type": edge.type,
                "subtype": edge.subtype or "",
                "prob": edge.probability if edge.probability is not None else 0.0,
                "verified": edge.verified,
                "reasoning": json.dumps(edge.reasoning),
            },
        )
        # Create TAIL relationships
        for nid in edge.tail:
            self._conn.execute(
                "MATCH (p:Proposition {id: $nid}), (h:Hyperedge {id: $eid}) "
                "CREATE (p)-[:TAIL]->(h)",
                {"nid": nid, "eid": edge.id},
            )
        # Create HEAD relationships
        for nid in edge.head:
            self._conn.execute(
                "MATCH (h:Hyperedge {id: $eid}), (p:Proposition {id: $nid}) "
                "CREATE (h)-[:HEAD]->(p)",
                {"eid": edge.id, "nid": nid},
            )
        return edge.id

    async def create_hyperedges_bulk(self, edges: list[HyperEdge]) -> list[int]:
        for edge in edges:
            await self.create_hyperedge(edge)
        return [e.id for e in edges]

    async def get_hyperedge(self, edge_id: int) -> HyperEdge | None:
        result = self._conn.execute(
            "MATCH (h:Hyperedge {id: $eid}) RETURN h.*", {"eid": edge_id}
        )
        if not result.has_next():
            return None
        row = result.get_next()
        # Get tail
        tail_result = self._conn.execute(
            "MATCH (p:Proposition)-[:TAIL]->(h:Hyperedge {id: $eid}) RETURN p.id",
            {"eid": edge_id},
        )
        tail_ids = [r[0] for r in tail_result.get_as_df().values]
        # Get head
        head_result = self._conn.execute(
            "MATCH (h:Hyperedge {id: $eid})-[:HEAD]->(p:Proposition) RETURN p.id",
            {"eid": edge_id},
        )
        head_ids = [r[0] for r in head_result.get_as_df().values]

        return HyperEdge(
            id=row[0],
            type=row[1],
            subtype=row[2] if row[2] else None,
            tail=tail_ids,
            head=head_ids,
            probability=row[3] if row[3] != 0.0 else None,
            verified=row[4],
            reasoning=json.loads(row[5]),
        )

    async def update_hyperedge(self, edge_id: int, **fields: Any) -> None:
        if not fields:
            return
        set_parts = []
        params = {"eid": edge_id}
        for key, value in fields.items():
            if key == "reasoning":
                value = json.dumps(value)
            params[f"f_{key}"] = value
            set_parts.append(f"h.{key} = $f_{key}")
        query = f"MATCH (h:Hyperedge {{id: $eid}}) SET {', '.join(set_parts)}"
        self._conn.execute(query, params)

    async def get_subgraph(
        self,
        node_ids: list[int],
        hops: int = 1,
        edge_types: list[str] | None = None,
        direction: str = "both",
        max_nodes: int = 500,
    ) -> tuple[set[int], set[int]]:
        visited_nodes: set[int] = set(node_ids)
        visited_edges: set[int] = set()
        frontier: set[int] = set(node_ids)

        for _ in range(hops):
            if not frontier or len(visited_nodes) >= max_nodes:
                break
            new_edge_ids: set[int] = set()
            frontier_list = list(frontier)

            # Downstream: frontier in tail
            if direction in ("both", "downstream"):
                for nid in frontier_list:
                    q = "MATCH (p:Proposition {id: $nid})-[:TAIL]->(h:Hyperedge) RETURN h.id"
                    res = self._conn.execute(q, {"nid": nid})
                    for row in res.get_as_df().values:
                        eid = row[0]
                        if edge_types is None or self._get_edge_type(eid) in edge_types:
                            new_edge_ids.add(eid)

            # Upstream: frontier in head
            if direction in ("both", "upstream"):
                for nid in frontier_list:
                    q = "MATCH (h:Hyperedge)-[:HEAD]->(p:Proposition {id: $nid}) RETURN h.id"
                    res = self._conn.execute(q, {"nid": nid})
                    for row in res.get_as_df().values:
                        eid = row[0]
                        if edge_types is None or self._get_edge_type(eid) in edge_types:
                            new_edge_ids.add(eid)

            new_edge_ids -= visited_edges
            if not new_edge_ids:
                break
            visited_edges |= new_edge_ids

            # Collect connected nodes
            new_nodes: set[int] = set()
            for eid in new_edge_ids:
                if direction in ("both", "downstream"):
                    res = self._conn.execute(
                        "MATCH (h:Hyperedge {id: $eid})-[:HEAD]->(p:Proposition) RETURN p.id",
                        {"eid": eid},
                    )
                    for row in res.get_as_df().values:
                        new_nodes.add(row[0])
                if direction in ("both", "upstream"):
                    res = self._conn.execute(
                        "MATCH (p:Proposition)-[:TAIL]->(h:Hyperedge {id: $eid}) RETURN p.id",
                        {"eid": eid},
                    )
                    for row in res.get_as_df().values:
                        new_nodes.add(row[0])

            frontier = new_nodes - visited_nodes
            visited_nodes |= new_nodes
            if len(visited_nodes) >= max_nodes:
                break

        return visited_nodes, visited_edges

    def _get_edge_type(self, edge_id: int) -> str | None:
        res = self._conn.execute(
            "MATCH (h:Hyperedge {id: $eid}) RETURN h.type", {"eid": edge_id}
        )
        if res.has_next():
            return res.get_next()[0]
        return None

    async def close(self) -> None:
        pass  # Kuzu handles cleanup on GC
```

> **Note:** Kuzu's Python API is synchronous. We wrap in async methods to match the GraphStore ABC. This is fine for single-process CLI usage.

**Step 4: Run tests to verify they pass**

Run: `pytest tests/libs/storage/test_kuzu_store.py -v`
Expected: All 6 tests PASS

**Step 5: Commit**

```bash
git add libs/storage/kuzu_store.py tests/libs/storage/test_kuzu_store.py
git commit -m "feat: add KuzuGraphStore — embedded graph for local CLI (#50)"
```

---

### Task 3: Wire Kuzu into StorageManager

**Files:**
- Modify: `libs/storage/config.py`
- Modify: `libs/storage/manager.py`
- Modify: `libs/storage/__init__.py`
- Test: `tests/libs/storage/test_manager.py` (verify existing + add Kuzu test)

**Step 1: Add graph_backend to StorageConfig**

In `libs/storage/config.py`, add:
```python
graph_backend: Literal["neo4j", "kuzu", "none"] = "neo4j"
kuzu_path: str | None = None  # defaults to lancedb_path + "/kuzu" if not set
```

**Step 2: Update StorageManager to support Kuzu**

In `libs/storage/manager.py`, add Kuzu initialization path:
```python
from .kuzu_store import KuzuGraphStore
...
if config.graph_backend == "kuzu":
    kuzu_path = config.kuzu_path or (config.lancedb_path + "/kuzu")
    self.graph = KuzuGraphStore(db_path=kuzu_path)
elif config.graph_backend == "neo4j":
    # existing Neo4j code
    ...
```

**Step 3: Write test for Kuzu backend in StorageManager**

```python
# Add to tests/libs/storage/test_manager.py
async def test_manager_with_kuzu(tmp_path):
    config = StorageConfig(
        deployment_mode="local",
        lancedb_path=str(tmp_path / "lance"),
        graph_backend="kuzu",
    )
    manager = StorageManager(config)
    assert manager.graph is not None
    await manager.graph.initialize_schema()
    await manager.close()
```

**Step 4: Run tests**

Run: `pytest tests/libs/storage/test_manager.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage/config.py libs/storage/manager.py libs/storage/__init__.py tests/libs/storage/test_manager.py
git commit -m "feat: wire KuzuGraphStore into StorageManager (#50)"
```

---

### Task 4: Add retraction edge support (#23)

**Files:**
- Modify: `services/inference_engine/factor_graph.py` (add edge type metadata)
- Modify: `services/inference_engine/bp.py` (handle retraction type)
- Test: `tests/services/test_inference_engine/test_bp.py`

**Step 1: Write failing test for retraction edge**

Add to `tests/services/test_inference_engine/test_bp.py`:

```python
def test_retraction_edge():
    """Retraction edge should lower the belief of its target.

    A has high prior. B retracts A. After BP, A's belief should drop.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A: high prior
    fg.add_variable(2, 0.95)  # B: evidence against A
    fg.add_factor(edge_id=100, tail=[2], head=[1], probability=0.9, edge_type="retraction")
    bp = BeliefPropagation(damping=0.5, max_iterations=50)
    beliefs = bp.run(fg)
    # Retraction should lower A's belief
    assert beliefs[1] < 0.9
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_inference_engine/test_bp.py::test_retraction_edge -v`
Expected: TypeError (add_factor doesn't accept edge_type)

**Step 3: Add edge_type to FactorGraph**

In `services/inference_engine/factor_graph.py`, update `add_factor`:
```python
def add_factor(
    self,
    edge_id: int,
    tail: list[int],
    head: list[int],
    probability: float,
    edge_type: str = "deduction",
) -> None:
    self.factors.append(
        {
            "edge_id": edge_id,
            "tail": tail,
            "head": head,
            "probability": probability,
            "edge_type": edge_type,
        }
    )
```

Update `from_subgraph` to pass edge type:
```python
graph.add_factor(edge.id, edge.tail, edge.head, prob, edge_type=edge.type)
```

**Step 4: Handle retraction in BP**

In `services/inference_engine/bp.py`, inside the factor loop in `run()`, add retraction logic:

```python
for factor in graph.factors:
    tail_ids: list[int] = factor["tail"]
    head_ids: list[int] = factor["head"]
    prob: float = factor["probability"]
    edge_type: str = factor.get("edge_type", "deduction")

    if tail_ids:
        tail_belief = float(np.prod([beliefs.get(t, 1.0) for t in tail_ids]))
    else:
        tail_belief = 1.0

    factor_msg = tail_belief * prob

    for h in head_ids:
        prior = graph.variables.get(h, 1.0)

        if edge_type == "retraction":
            # Retraction: evidence AGAINST the head node
            # Higher factor_msg → lower head belief
            new_belief = prior * (1 - factor_msg)
        else:
            # Normal: evidence FOR the head node
            new_belief = prior * factor_msg

        new_belief = min(max(new_belief, 0.0), 1.0)
        beliefs[h] = self._damping * new_belief + (1 - self._damping) * old_beliefs.get(
            h, prior
        )
```

**Step 5: Run tests**

Run: `pytest tests/services/test_inference_engine/test_bp.py -v`
Expected: All tests PASS (including new retraction test)

**Step 6: Commit**

```bash
git add services/inference_engine/factor_graph.py services/inference_engine/bp.py tests/services/test_inference_engine/test_bp.py
git commit -m "feat: add retraction edge support in BP (#23)"
```

---

### Task 5: Type-aware BP — contradiction inhibition (#24)

**Files:**
- Modify: `services/inference_engine/bp.py`
- Test: `tests/services/test_inference_engine/test_bp.py`

**Step 1: Write failing test for contradiction edge**

```python
def test_contradiction_inhibits_both_sides():
    """Contradiction edge: if one side is strong, the other should drop.

    A (prior=0.9) contradicts B (prior=0.9). After BP, the contradiction
    should cause mutual inhibition.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.9)  # A
    fg.add_variable(2, 0.9)  # B
    # Contradiction: A and B in tail, both in head (mutual exclusion)
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.9, edge_type="contradiction")
    fg.add_factor(edge_id=101, tail=[2], head=[1], probability=0.9, edge_type="contradiction")
    bp = BeliefPropagation(damping=0.5, max_iterations=50)
    beliefs = bp.run(fg)
    # At least one should drop significantly
    assert beliefs[1] < 0.9 or beliefs[2] < 0.9


def test_contradiction_asymmetric():
    """Stronger side wins in contradiction.

    A (prior=0.95) contradicts B (prior=0.3). A should stay high, B should drop.
    """
    fg = FactorGraph()
    fg.add_variable(1, 0.95)  # A: strong
    fg.add_variable(2, 0.3)   # B: weak
    fg.add_factor(edge_id=100, tail=[1], head=[2], probability=0.9, edge_type="contradiction")
    fg.add_factor(edge_id=101, tail=[2], head=[1], probability=0.9, edge_type="contradiction")
    bp = BeliefPropagation(damping=0.5, max_iterations=50)
    beliefs = bp.run(fg)
    assert beliefs[1] > beliefs[2]
    assert beliefs[2] < 0.3  # B should drop
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/services/test_inference_engine/test_bp.py::test_contradiction_inhibits_both_sides -v`
Expected: FAIL (contradiction not handled differently from retraction yet)

**Step 3: Add contradiction handling in BP**

In `services/inference_engine/bp.py`, update the edge_type handling:

```python
if edge_type == "retraction":
    new_belief = prior * (1 - factor_msg)
elif edge_type == "contradiction":
    # Contradiction: strong tail evidence AGAINST head
    new_belief = prior * (1 - factor_msg)
else:
    new_belief = prior * factor_msg
```

> Note: Contradiction and retraction currently use the same math (mutual inhibition). The difference is semantic: contradiction edges are symmetric (both sides added), retraction is one-directional. Future iterations may refine the contradiction model.

**Step 4: Run all BP tests**

Run: `pytest tests/services/test_inference_engine/test_bp.py -v`
Expected: All tests PASS

**Step 5: Commit**

```bash
git add services/inference_engine/bp.py tests/services/test_inference_engine/test_bp.py
git commit -m "feat: type-aware BP with contradiction inhibition (#24)"
```

---

### Task 6: Verify full test suite after Phase 1

**Step 1: Run all tests**

Run: `pytest tests/ -v --tb=short`
Expected: All existing tests still pass. No regressions.

**Step 2: Commit (if any fixups needed)**

---

## Phase 2: CLI Framework (#45)

### Task 7: CLI entry point + `gaia init`

**Files:**
- Create: `cli/__init__.py`
- Create: `cli/main.py`
- Create: `cli/package.py` (package read/write utilities)
- Modify: `pyproject.toml` (add `[project.scripts]` entry + typer/pyyaml/tomli deps)
- Test: `tests/cli/__init__.py`
- Test: `tests/cli/test_init.py`

**Step 1: Add dependencies to pyproject.toml**

Add to `[project.dependencies]`:
```toml
"typer>=0.12",
"pyyaml>=6.0",
```

Add `[project.scripts]`:
```toml
[project.scripts]
gaia = "cli.main:app"
```

Run: `pip install -e ".[dev]"`

**Step 2: Write failing test for `gaia init`**

```python
# tests/cli/test_init.py
"""Tests for gaia init command."""

from pathlib import Path
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_init_creates_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "galileo_tied_balls"])
    assert result.exit_code == 0
    pkg_dir = tmp_path / "galileo_tied_balls"
    assert (pkg_dir / "gaia.toml").exists()
    assert (pkg_dir / "claims").is_dir()


def test_init_in_current_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init"])
    assert result.exit_code == 0
    assert (tmp_path / "gaia.toml").exists()
    assert (tmp_path / "claims").is_dir()
```

**Step 3: Implement CLI entry point and init command**

```python
# cli/__init__.py
# (empty)

# cli/main.py
"""Gaia CLI — Knowledge Package Manager."""

import typer

app = typer.Typer(name="gaia", help="Gaia Knowledge Package Manager")


@app.command()
def init(name: str = typer.Argument(None, help="Package name (default: current dir name)")):
    """Initialize a new knowledge package."""
    from cli.package import init_package
    init_package(name)


if __name__ == "__main__":
    app()
```

```python
# cli/package.py
"""Knowledge package read/write utilities."""

from pathlib import Path

import typer

_DEFAULT_TOML = """\
[package]
name = "{name}"
version = "0.1.0"
description = ""
authors = []

[remote]
mode = "server"
# server_url = "https://gaia.example.com"
# registry = "github.com/gaia-registry/packages"
"""


def init_package(name: str | None = None) -> Path:
    """Create a new knowledge package directory structure."""
    if name:
        pkg_dir = Path.cwd() / name
        pkg_dir.mkdir(exist_ok=True)
    else:
        pkg_dir = Path.cwd()
        name = pkg_dir.name

    toml_path = pkg_dir / "gaia.toml"
    if toml_path.exists():
        typer.echo(f"Package already exists: {toml_path}")
        raise typer.Exit(code=1)

    toml_path.write_text(_DEFAULT_TOML.format(name=name))
    (pkg_dir / "claims").mkdir(exist_ok=True)
    typer.echo(f"Initialized package '{name}' at {pkg_dir}")
    return pkg_dir
```

**Step 4: Run tests**

Run: `pytest tests/cli/test_init.py -v`
Expected: PASS

**Step 5: Verify CLI works end-to-end**

Run: `python -m cli.main init /tmp/test_gaia_pkg`
Expected: Creates directory with gaia.toml + claims/

**Step 6: Commit**

```bash
git add cli/ tests/cli/ pyproject.toml
git commit -m "feat: gaia CLI framework + init command (#45)"
```

---

### Task 8: `gaia claim` command

**Files:**
- Create: `cli/commands/claim.py`
- Modify: `cli/main.py` (register command)
- Modify: `cli/package.py` (add claim YAML read/write)
- Test: `tests/cli/test_claim.py`

**Step 1: Write failing test**

```python
# tests/cli/test_claim.py
"""Tests for gaia claim command."""

import yaml
from pathlib import Path
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_claim_basic(tmp_path, monkeypatch):
    """Add a simple claim with no premises."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    result = runner.invoke(app, [
        "claim", "石头比树叶落得快",
        "--type", "observation",
    ])
    assert result.exit_code == 0
    assert "Created claim" in result.output

    # Verify YAML file was created
    claim_files = list((tmp_path / "claims").glob("*.yaml"))
    assert len(claim_files) == 1
    with open(claim_files[0]) as f:
        data = yaml.safe_load(f)
    assert data["claims"][0]["content"] == "石头比树叶落得快"
    assert data["claims"][0]["type"] == "observation"


def test_claim_with_premise(tmp_path, monkeypatch):
    """Add a claim with premise references."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    # First claim
    runner.invoke(app, ["claim", "前提A", "--type", "axiom"])
    # Second claim referencing first
    result = runner.invoke(app, [
        "claim", "结论B",
        "--premise", "1",
        "--why", "从A推导出B",
        "--type", "deduction",
    ])
    assert result.exit_code == 0
    assert "Created claim" in result.output
```

**Step 2: Implement claim command**

Add to `cli/package.py`:
- `get_next_claim_id(pkg_dir)` — scan claims/*.yaml, find max ID, return max+1
- `write_claim(pkg_dir, claim_data)` — append to or create YAML file

Add `cli/commands/claim.py` with the command that:
- Reads the package dir (find gaia.toml upward)
- Assigns next available ID
- Writes claim to `claims/NNN_<sanitized_content>.yaml`
- Prints "Created claim {id}"

**Step 3: Run tests**

Run: `pytest tests/cli/test_claim.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/commands/ cli/package.py cli/main.py tests/cli/test_claim.py
git commit -m "feat: gaia claim command (#45)"
```

---

### Task 9: `gaia show` + `gaia stats` + `gaia contradictions`

**Files:**
- Create: `cli/commands/show.py`
- Create: `cli/commands/stats.py`
- Create: `cli/commands/contradictions.py`
- Modify: `cli/main.py`
- Modify: `cli/package.py` (add `load_all_claims(pkg_dir)`)
- Test: `tests/cli/test_show.py`
- Test: `tests/cli/test_stats.py`

These commands are read-only and work by parsing the local `claims/*.yaml` files.

**Step 1: Implement `load_all_claims(pkg_dir)` in package.py**

Returns a list of all claims across all YAML files, sorted by ID.

**Step 2: Implement show command**

`gaia show <id>` — prints claim content, type, premises, why, belief.

**Step 3: Implement stats command**

`gaia stats` — prints total claims, claims by type, premises count.

**Step 4: Implement contradictions command**

`gaia contradictions` — finds all claims with `type: contradiction` and prints their premises.

**Step 5: Write tests for each, run, commit**

```bash
git commit -m "feat: gaia show, stats, contradictions commands (#45)"
```

---

### Task 10: `gaia search` (local semantic search)

**Files:**
- Create: `cli/commands/search.py`
- Create: `cli/local_store.py` (manages local LanceDB + Kuzu for the package)
- Modify: `cli/main.py`
- Test: `tests/cli/test_search.py`

**Step 1: Implement local_store.py**

`LocalStore` class that:
- Takes a package dir path
- Creates/opens LanceDB at `{pkg_dir}/.gaia/lancedb`
- Creates/opens Kuzu at `{pkg_dir}/.gaia/kuzu`
- Provides `index_claims(claims)` — loads claims into LanceDB for FTS
- Provides `search(query, limit)` — BM25 full-text search over claims

**Step 2: Implement search command**

`gaia search "query"` — loads claims into local LanceDB, runs FTS, prints results.

**Step 3: Write test, run, commit**

```bash
git commit -m "feat: gaia search with local BM25 (#45)"
```

---

## Phase 3: gaia build (#46)

### Task 11: Structural validation in `gaia build`

**Files:**
- Create: `cli/commands/build.py`
- Create: `cli/validator.py`
- Modify: `cli/main.py`
- Test: `tests/cli/test_build.py`

**Step 1: Write failing test**

```python
# tests/cli/test_build.py
"""Tests for gaia build command."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_build_valid_package(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "前提A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
    assert "✓" in result.output


def test_build_invalid_premise_ref(tmp_path, monkeypatch):
    """Build should fail if premise references nonexistent claim."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "结论B", "--premise", "999", "--why", "推导", "--type", "deduction"])
    result = runner.invoke(app, ["build"])
    assert result.exit_code != 0 or "error" in result.output.lower()
```

**Step 2: Implement validator**

`cli/validator.py`:
- `validate_package(claims) -> list[str]` — returns list of error messages
- Checks: YAML format, all premise/context IDs exist, no duplicate IDs, no cycles

**Step 3: Implement build command (validation only first)**

`gaia build`:
1. Load all claims
2. Run validation
3. Print results

**Step 4: Run tests, commit**

```bash
git commit -m "feat: gaia build structural validation (#46)"
```

---

### Task 12: Local BP in `gaia build`

**Files:**
- Modify: `cli/commands/build.py`
- Modify: `cli/local_store.py`
- Test: `tests/cli/test_build.py`

**Step 1: Write failing test**

```python
def test_build_runs_bp(tmp_path, monkeypatch):
    """Build should run BP and show belief changes."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "公理B", "--type", "axiom"])
    runner.invoke(app, ["claim", "推论C", "--premise", "1,2", "--why", "A+B推C", "--type", "deduction"])
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
    assert "BP" in result.output or "belief" in result.output.lower()
```

**Step 2: Implement BP integration**

In `cli/commands/build.py`, after validation passes:
1. Convert claims to `Node` + `HyperEdge` objects
2. Build `FactorGraph.from_subgraph(nodes, edges)`
3. Run `BeliefPropagation().run(graph)`
4. Print belief change summary (before/after)

**Step 3: Run tests, commit**

```bash
git commit -m "feat: gaia build with local BP (#46)"
```

---

### Task 13: Lock file generation in `gaia build`

**Files:**
- Create: `cli/lockfile.py`
- Modify: `cli/commands/build.py`
- Test: `tests/cli/test_build.py`

**Step 1: Write failing test**

```python
def test_build_generates_lockfile(tmp_path, monkeypatch):
    """Build should generate gaia.lock from cross-package references."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    # No cross-package refs → empty lock file
    runner.invoke(app, ["claim", "本地命题", "--type", "axiom"])
    runner.invoke(app, ["build"])
    lock_path = tmp_path / "gaia.lock"
    assert lock_path.exists()
```

**Step 2: Implement lockfile generation**

`cli/lockfile.py`:
- `generate_lockfile(claims, pkg_dir)` — scan all premise/context fields for cross-package refs (`pkg:claim_id@commit`), write `gaia.lock`

**Step 3: Run tests, commit**

```bash
git commit -m "feat: gaia build lock file generation (#46)"
```

---

### Task 14: End-to-end integration test

**Files:**
- Create: `tests/cli/test_e2e_galileo.py`

**Step 1: Write Galileo thought experiment as CLI test**

```python
"""End-to-end test: recreate Galileo tied balls via CLI."""

from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_galileo_full_workflow(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "galileo_tied_balls"])
    monkeypatch.chdir(tmp_path / "galileo_tied_balls")

    # Aristotle's observations
    runner.invoke(app, ["claim", "石头比树叶落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "铁比木头落得快", "--type", "observation"])
    runner.invoke(app, ["claim", "v ∝ W 定律", "--premise", "1,2", "--why", "归纳观察", "--type", "theory"])

    # Tied balls thought experiment
    runner.invoke(app, ["claim", "绑球设定", "--type", "axiom"])
    runner.invoke(app, ["claim", "推导A: HL更慢", "--premise", "3,4", "--why", "轻球拖拽重球", "--type", "deduction"])
    runner.invoke(app, ["claim", "推导B: HL更快", "--premise", "3,4", "--why", "总重量更大", "--type", "deduction"])
    runner.invoke(app, ["claim", "矛盾: 不可能既快又慢", "--premise", "5,6", "--type", "contradiction"])

    # Build and verify
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0

    # Contradictions should be found
    result = runner.invoke(app, ["contradictions"])
    assert "矛盾" in result.output or "contradiction" in result.output.lower()

    # Stats
    result = runner.invoke(app, ["stats"])
    assert "7" in result.output  # 7 claims
```

**Step 2: Run tests, commit**

```bash
git commit -m "test: Galileo thought experiment E2E via CLI (#45, #46)"
```

---

### Task 15: Final cleanup + `--json` flag

**Files:**
- Modify: `cli/main.py` (add `--json` global option)
- Modify: all commands (respect json flag)

**Step 1: Add global `--json` callback**

```python
@app.callback()
def main(json_output: bool = typer.Option(False, "--json", help="Output as JSON")):
    ...
```

**Step 2: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 3: Commit**

```bash
git commit -m "feat: add --json output flag to all CLI commands (#45)"
```

---

## Phase 4: gaia review (#47)

### Task 16: Review skill prompt + YAML parser

**Files:**
- Create: `cli/review_skill.py`
- Create: `review-skills/claim-review-v1.0.md`
- Test: `tests/cli/test_review_skill.py`

**Step 1: Create the v1.0 skill prompt file**

Save the prompt from `docs/plans/2026-03-06-review-system-design.md` Section 3.6 as `review-skills/claim-review-v1.0.md`.

**Step 2: Write failing test for review input/output formatting**

```python
# tests/cli/test_review_skill.py
"""Tests for review skill input/output formatting."""

from cli.review_skill import format_review_input, parse_review_output


def test_format_review_input():
    claim = {
        "id": 5007,
        "content": "矛盾",
        "type": "deduction",
        "why": "两个推导矛盾",
        "premise": [5005, 5006],
        "context": [],
    }
    all_claims = {
        5005: {"id": 5005, "content": "推导A"},
        5006: {"id": 5006, "content": "推导B"},
        5007: claim,
    }
    result = format_review_input(claim, all_claims)
    assert "5007" in result
    assert "推导A" in result  # premises expanded
    assert "推导B" in result


def test_parse_review_output():
    raw = """
score: 0.95
justification: "纯逻辑演绎"
confirmed_premises: [5005, 5006]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []
"""
    result = parse_review_output(raw)
    assert result["score"] == 0.95
    assert result["confirmed_premises"] == [5005, 5006]


def test_parse_review_output_with_yaml_fence():
    """LLM may wrap output in ```yaml``` fences."""
    raw = "```yaml\nscore: 0.80\njustification: \"test\"\nconfirmed_premises: []\ndowngraded_premises: []\nupgraded_context: []\nirrelevant: []\nsuggested_premise: []\nsuggested_context: []\n```"
    result = parse_review_output(raw)
    assert result["score"] == 0.80
```

**Step 3: Implement review_skill.py**

```python
# cli/review_skill.py
"""Review skill input/output formatting and parsing."""

import re
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).parent.parent / "review-skills"


def load_skill_prompt(version: str = "v1.0") -> str:
    """Load the review skill prompt by version."""
    path = SKILL_DIR / f"claim-review-{version}.md"
    return path.read_text()


def format_review_input(claim: dict, all_claims: dict[int, dict]) -> str:
    """Format a claim into the standardized review input YAML."""
    premise_expanded = []
    for pid in claim.get("premise", []):
        p = all_claims.get(pid, {})
        premise_expanded.append({"id": pid, "content": p.get("content", "")})

    context_expanded = []
    for cid in claim.get("context", []):
        c = all_claims.get(cid, {})
        context_expanded.append({"id": cid, "content": c.get("content", "")})

    input_data = {
        "claim": {
            "id": claim["id"],
            "content": claim["content"],
            "type": claim.get("type", "deduction"),
            "why": claim.get("why", ""),
            "premise": premise_expanded,
            "context": context_expanded,
        }
    }
    return yaml.dump(input_data, allow_unicode=True, default_flow_style=False)


def parse_review_output(raw: str) -> dict:
    """Parse LLM review output YAML, stripping code fences if present."""
    # Strip ```yaml ... ``` fences
    cleaned = re.sub(r"^```(?:yaml)?\n?", "", raw.strip())
    cleaned = re.sub(r"\n?```$", "", cleaned.strip())
    return yaml.safe_load(cleaned)
```

**Step 4: Run tests**

Run: `pytest tests/cli/test_review_skill.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/review_skill.py review-skills/ tests/cli/test_review_skill.py
git commit -m "feat: review skill prompt v1.0 + input/output formatting (#47)"
```

---

### Task 17: LLM client for review

**Files:**
- Create: `cli/llm_client.py`
- Create: `cli/config.py` (user config `~/.gaia/config.toml`)
- Test: `tests/cli/test_llm_client.py`

**Step 1: Write failing test (mocked LLM)**

```python
# tests/cli/test_llm_client.py
"""Tests for review LLM client."""

from unittest.mock import AsyncMock, patch
import pytest
from cli.llm_client import review_claim


@pytest.mark.asyncio
async def test_review_claim_returns_parsed_result():
    mock_response = """score: 0.92
justification: "test"
confirmed_premises: [1, 2]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []"""

    with patch("cli.llm_client._call_llm", new_callable=AsyncMock, return_value=mock_response):
        result = await review_claim(
            claim={"id": 3, "content": "C", "type": "deduction", "why": "because", "premise": [1, 2]},
            all_claims={1: {"id": 1, "content": "A"}, 2: {"id": 2, "content": "B"}},
            model="test-model",
        )
    assert result["score"] == pytest.approx(0.92)
    assert result["confirmed_premises"] == [1, 2]
```

**Step 2: Implement LLM client**

```python
# cli/llm_client.py
"""LLM client for claim review. Uses litellm for model-agnostic API calls."""

import asyncio
import litellm
from cli.review_skill import format_review_input, load_skill_prompt, parse_review_output


async def _call_llm(system_prompt: str, user_prompt: str, model: str) -> str:
    """Call LLM via litellm (supports OpenAI, Anthropic, etc.)."""
    response = await litellm.acompletion(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.1,
    )
    return response.choices[0].message.content


async def review_claim(
    claim: dict,
    all_claims: dict[int, dict],
    model: str = "claude-sonnet-4-20250514",
    skill_version: str = "v1.0",
) -> dict:
    """Review a single claim using the review skill prompt."""
    system_prompt = load_skill_prompt(skill_version)
    user_prompt = format_review_input(claim, all_claims)
    raw_output = await _call_llm(system_prompt, user_prompt, model)
    return parse_review_output(raw_output)


async def review_claims_concurrent(
    claims: list[dict],
    all_claims: dict[int, dict],
    model: str = "claude-sonnet-4-20250514",
    concurrency: int = 5,
) -> list[dict]:
    """Review multiple claims concurrently with semaphore-based throttling."""
    sem = asyncio.Semaphore(concurrency)

    async def _review_one(claim):
        async with sem:
            return await review_claim(claim, all_claims, model)

    tasks = [_review_one(c) for c in claims]
    return await asyncio.gather(*tasks)
```

**Step 3: Implement user config**

```python
# cli/config.py
"""User configuration from ~/.gaia/config.toml."""

from pathlib import Path

try:
    import tomllib
except ImportError:
    import tomli as tomllib


DEFAULT_CONFIG = {
    "review": {
        "model": "claude-sonnet-4-20250514",
        "concurrency": 5,
        "skill_version": "v1.0",
    },
}


def load_user_config() -> dict:
    """Load user config from ~/.gaia/config.toml, with defaults."""
    config_path = Path.home() / ".gaia" / "config.toml"
    if config_path.exists():
        with open(config_path, "rb") as f:
            user = tomllib.load(f)
        # Merge with defaults
        merged = {**DEFAULT_CONFIG}
        for key, val in user.items():
            if isinstance(val, dict) and key in merged:
                merged[key] = {**merged[key], **val}
            else:
                merged[key] = val
        return merged
    return DEFAULT_CONFIG
```

**Step 4: Run tests**

Run: `pytest tests/cli/test_llm_client.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/llm_client.py cli/config.py tests/cli/test_llm_client.py
git commit -m "feat: LLM client for claim review with concurrency (#47)"
```

---

### Task 18: `gaia review` command

**Files:**
- Create: `cli/commands/review.py`
- Modify: `cli/main.py`
- Test: `tests/cli/test_review.py`

**Step 1: Write failing test (mocked LLM)**

```python
# tests/cli/test_review.py
"""Tests for gaia review command."""

from unittest.mock import patch, AsyncMock
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()

MOCK_REVIEW = """score: 0.92
justification: "valid"
confirmed_premises: [1]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []"""


def test_review_single_claim(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        result = runner.invoke(app, ["review", "2"])
    assert result.exit_code == 0
    assert "0.92" in result.output


def test_review_all_claims(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        result = runner.invoke(app, ["review"])
    assert result.exit_code == 0
    # Should review claims that have premises (skip leaf axioms)
    assert "Score" in result.output or "score" in result.output
```

**Step 2: Implement review command**

`cli/commands/review.py`:
- `gaia review` — review all claims with premises
- `gaia review 5 6 7` — review specific claim IDs
- Loads `~/.gaia/config.toml` for model/concurrency settings
- Calls `review_claims_concurrent()` with semaphore
- Prints table: `| Claim | Score | Issue |`
- Optionally re-runs BP with updated scores

**Step 3: Run tests**

Run: `pytest tests/cli/test_review.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/commands/review.py cli/main.py tests/cli/test_review.py
git commit -m "feat: gaia review command with concurrent LLM evaluation (#47)"
```

---

### Task 19: Review results storage + BP integration

**Files:**
- Create: `cli/review_store.py`
- Modify: `cli/commands/review.py`
- Modify: `cli/commands/build.py` (read review scores as edge probabilities)
- Test: `tests/cli/test_review.py`

**Step 1: Write failing test**

```python
def test_review_saves_results(tmp_path, monkeypatch):
    """Review results should be persisted locally."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["claim", "结论B", "--premise", "1", "--why", "推导", "--type", "deduction"])

    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=MOCK_REVIEW):
        runner.invoke(app, ["review", "2"])

    # Verify results file exists
    review_dir = tmp_path / ".gaia" / "reviews"
    assert review_dir.exists()
    review_files = list(review_dir.glob("*.yaml"))
    assert len(review_files) >= 1
```

**Step 2: Implement review_store.py**

```python
# cli/review_store.py
"""Local storage for review results."""

from pathlib import Path
from datetime import datetime
import yaml


def save_review(pkg_dir: Path, claim_id: int, result: dict, model: str, skill: str) -> None:
    """Save a review result to .gaia/reviews/{claim_id}.yaml."""
    review_dir = pkg_dir / ".gaia" / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)

    record = {
        "target": {"claim_id": claim_id},
        "result": result,
        "provenance": {
            "method": "local",
            "model": model,
            "skill": f"claim-review-{skill}",
            "timestamp": datetime.utcnow().isoformat() + "Z",
        },
    }
    path = review_dir / f"{claim_id}.yaml"
    path.write_text(yaml.dump(record, allow_unicode=True, default_flow_style=False))


def load_review_scores(pkg_dir: Path) -> dict[int, float]:
    """Load all review scores. Returns {claim_id: score}."""
    review_dir = pkg_dir / ".gaia" / "reviews"
    if not review_dir.exists():
        return {}
    scores = {}
    for f in review_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        cid = data["target"]["claim_id"]
        scores[cid] = data["result"]["score"]
    return scores
```

**Step 3: Integrate review scores into `gaia build`**

In `cli/commands/build.py`, after building the FactorGraph, load review scores and use them as edge probabilities (overriding defaults).

**Step 4: Run tests, commit**

```bash
git add cli/review_store.py cli/commands/review.py cli/commands/build.py tests/cli/test_review.py
git commit -m "feat: persist review results + integrate scores into BP (#47)"
```

---

## Phase 5: gaia publish (#48)

### Task 20: `gaia publish --server` (Server direct)

**Files:**
- Create: `cli/commands/publish.py`
- Create: `cli/server_client.py`
- Modify: `cli/main.py`
- Test: `tests/cli/test_publish.py`

**Step 1: Write failing test (mocked HTTP)**

```python
# tests/cli/test_publish.py
"""Tests for gaia publish command."""

from unittest.mock import patch, MagicMock
from typer.testing import CliRunner
from cli.main import app

runner = CliRunner()


def test_publish_server_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["build"])

    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_response.json.return_value = {"commit_id": "abc123", "status": "pending_review"}

    with patch("cli.server_client.httpx.post", return_value=mock_response):
        result = runner.invoke(app, ["publish", "--server"])
    assert result.exit_code == 0
    assert "Published" in result.output or "abc123" in result.output
```

**Step 2: Implement server_client.py**

```python
# cli/server_client.py
"""Client for Gaia Server API."""

import httpx
from cli.package import load_all_claims, load_package_config


def publish_to_server(pkg_dir, server_url: str) -> dict:
    """Publish package to Gaia Server via POST /commits."""
    config = load_package_config(pkg_dir)
    claims = load_all_claims(pkg_dir)

    # Convert claims to CommitRequest format
    operations = []
    for claim in claims:
        # Build AddEdgeOp from claim
        operations.append({
            "op": "add_edge",
            "tail": [{"node_id": pid} for pid in claim.get("premise", [])],
            "head": [{"content": claim["content"], "keywords": []}],
            "type": claim.get("type", "deduction"),
            "reasoning": [{"content": claim.get("why", "")}],
        })

    payload = {
        "message": f"Publish {config.get('package', {}).get('name', 'unknown')} {config.get('package', {}).get('version', '0.1.0')}",
        "operations": operations,
    }

    response = httpx.post(f"{server_url}/commits", json=payload)
    response.raise_for_status()
    return response.json()
```

**Step 3: Implement publish command**

```python
# cli/commands/publish.py
"""gaia publish — publish package to remote."""

import typer
from cli.package import find_package_dir, load_package_config


def publish(
    server: bool = typer.Option(False, "--server", help="Publish to Server directly"),
    git: bool = typer.Option(False, "--git", help="Publish via git + PR to registry"),
    all_remotes: bool = typer.Option(False, "--all", help="Publish to both server and git"),
):
    """Publish knowledge package to remote."""
    pkg_dir = find_package_dir()
    config = load_package_config(pkg_dir)

    # Determine mode
    if not server and not git and not all_remotes:
        mode = config.get("remote", {}).get("mode", "server")
    elif all_remotes:
        mode = "both"
    elif git:
        mode = "github"
    else:
        mode = "server"

    if mode in ("server", "both"):
        from cli.server_client import publish_to_server
        server_url = config.get("remote", {}).get("server_url", "http://localhost:8000")
        result = publish_to_server(pkg_dir, server_url)
        typer.echo(f"Published to server. Commit: {result.get('commit_id')}")

    if mode in ("github", "both"):
        typer.echo("Git publish: run `git push` and create PR to registry repo")
        # Future: automate git push + PR creation
```

**Step 4: Run tests**

Run: `pytest tests/cli/test_publish.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/commands/publish.py cli/server_client.py cli/main.py tests/cli/test_publish.py
git commit -m "feat: gaia publish --server command (#48)"
```

---

### Task 21: `gaia publish --git` (GitHub mode)

**Files:**
- Modify: `cli/commands/publish.py`
- Test: `tests/cli/test_publish.py`

**Step 1: Write failing test**

```python
def test_publish_git_mode(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    runner.invoke(app, ["claim", "公理A", "--type", "axiom"])
    runner.invoke(app, ["build"])

    with patch("cli.commands.publish.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        result = runner.invoke(app, ["publish", "--git"])
    assert result.exit_code == 0
    # Should have called git push
    assert any("push" in str(call) for call in mock_run.call_args_list)
```

**Step 2: Implement git publish**

In `cli/commands/publish.py`, add git mode:
- `git push origin <current_branch>`
- If `registry` configured in `gaia.toml`, create PR via `gh pr create`
- Print instructions if `gh` CLI not available

**Step 3: Run tests, commit**

```bash
git commit -m "feat: gaia publish --git with auto-push (#48)"
```

---

## Phase 6: Test Hardening (#20, #40)

### Task 22: Rewrite inference engine tests with real storage (#20)

**Files:**
- Modify: `tests/services/test_inference_engine/test_engine.py`
- Uses: `tests/conftest.py` (existing `storage` fixture)

**Step 1: Read current test file**

Read `tests/services/test_inference_engine/test_engine.py` to understand what's mocked.

**Step 2: Rewrite tests to use real StorageManager**

Replace mock-based tests with tests using the `storage` fixture from `conftest.py`:
- Seed nodes and edges from fixtures
- Call `compute_local_bp()` with real storage
- Assert beliefs are reasonable

**Step 3: Run tests**

Run: `pytest tests/services/test_inference_engine/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git commit -m "test: rewrite inference engine tests with real storage (#20)"
```

---

### Task 23: Integration tests — thought experiments with BP (#40)

**Files:**
- Create: `tests/integration/test_thought_experiments.py`
- Uses: `tests/fixtures/examples/galileo_tied_balls/` (existing fixtures)
- Uses: `tests/fixtures/examples/einstein_elevator/` (existing fixtures)

**Step 1: Write integration test for Galileo**

```python
# tests/integration/test_thought_experiments.py
"""Integration tests: thought experiment fixtures with full BP pipeline."""

import json
from pathlib import Path

import pytest

from libs.models import HyperEdge, Node
from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph

FIXTURES = Path(__file__).parent.parent / "fixtures" / "examples"


def load_example(name: str) -> tuple[list[Node], list[HyperEdge], dict]:
    """Load nodes, edges, and manifest for a thought experiment."""
    base = FIXTURES / name
    with open(base / "nodes.json") as f:
        nodes = [Node.model_validate(n) for n in json.load(f)]
    with open(base / "edges.json") as f:
        edges = [HyperEdge.model_validate(e) for e in json.load(f)]
    with open(base / "manifest.json") as f:
        manifest = json.load(f)
    return nodes, edges, manifest


def test_galileo_bp_contradiction_drops_aristotle():
    """After BP, Aristotle's v∝W law (5003) should have low belief due to contradictions."""
    nodes, edges, manifest = load_example("galileo_tied_balls")
    fg = FactorGraph.from_subgraph(nodes, edges)
    bp = BeliefPropagation(damping=0.5, max_iterations=100)
    beliefs = bp.run(fg)

    # Node 5003 (Aristotle's law) should drop due to contradiction edges
    final = manifest.get("expected_beliefs", {}).get("final", {})
    if "5003" in final:
        low, high = final["5003"]
        assert low <= beliefs.get(5003, 1.0) <= high, (
            f"5003 belief {beliefs.get(5003)} not in [{low}, {high}]"
        )


def test_einstein_bp_soldner_drops():
    """After BP, Soldner's 0.87″ prediction (6004) should drop vs GR's 1.75″."""
    nodes, edges, manifest = load_example("einstein_elevator")
    fg = FactorGraph.from_subgraph(nodes, edges)
    bp = BeliefPropagation(damping=0.5, max_iterations=100)
    beliefs = bp.run(fg)

    final = manifest.get("expected_beliefs", {}).get("final", {})
    if "6004" in final:
        low, high = final["6004"]
        assert low <= beliefs.get(6004, 1.0) <= high, (
            f"6004 belief {beliefs.get(6004)} not in [{low}, {high}]"
        )
```

**Step 2: Run tests**

Run: `pytest tests/integration/test_thought_experiments.py -v`
Expected: PASS (may need BP tuning for expected ranges)

**Step 3: Commit**

```bash
git commit -m "test: thought experiment integration tests with BP (#40)"
```

---

### Task 24: Full CLI E2E with review (mocked)

**Files:**
- Modify: `tests/cli/test_e2e_galileo.py`

**Step 1: Extend Galileo E2E test with review step**

```python
def test_galileo_with_review(tmp_path, monkeypatch):
    """Full workflow: init → claim → build → review → build (with scores)."""
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init", "galileo"])
    monkeypatch.chdir(tmp_path / "galileo")

    runner.invoke(app, ["claim", "v∝W", "--type", "theory"])
    runner.invoke(app, ["claim", "绑球设定", "--type", "axiom"])
    runner.invoke(app, ["claim", "HL更慢", "--premise", "1,2", "--why", "轻球拖拽", "--type", "deduction"])
    runner.invoke(app, ["claim", "HL更快", "--premise", "1,2", "--why", "总重更大", "--type", "deduction"])
    runner.invoke(app, ["claim", "矛盾", "--premise", "3,4", "--type", "contradiction"])

    # Build without review
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0

    # Mock review
    mock_review = "score: 0.95\njustification: \"valid\"\nconfirmed_premises: [1, 2]\ndowngraded_premises: []\nupgraded_context: []\nirrelevant: []\nsuggested_premise: []\nsuggested_context: []"
    with patch("cli.commands.review._call_llm", new_callable=AsyncMock, return_value=mock_review):
        result = runner.invoke(app, ["review"])
    assert result.exit_code == 0

    # Build again with review scores
    result = runner.invoke(app, ["build"])
    assert result.exit_code == 0
```

**Step 2: Run tests, commit**

```bash
git commit -m "test: full CLI E2E with review integration (#47, #40)"
```

---

### Task 25: Final test suite verification

**Step 1: Run full test suite**

Run: `pytest tests/ -v --tb=short`
Expected: All tests pass

**Step 2: Run linting**

Run: `ruff check . && ruff format --check .`
Expected: Clean

**Step 3: Commit any fixups**

---

## Summary

| Phase | Tasks | Issues | Estimated commits |
|-------|-------|--------|-------------------|
| 1: Storage + BP | Tasks 1-6 | #50, #23, #24 | 5 |
| 2: CLI Framework | Tasks 7-10 | #45 | 4 |
| 3: gaia build | Tasks 11-14 | #46 | 4 |
| 4: gaia review | Tasks 16-19 | #47 | 4 |
| 5: gaia publish | Tasks 20-21 | #48 | 2 |
| 6: Test Hardening | Tasks 22-25 | #20, #40 | 4 |
| Cleanup | Task 15 | #45 | 1 |
| **Total** | **25 tasks** | **9 issues** | **~24 commits** |

**Critical path:** Task 1 → 2 → 3 → 7 → 8 → 11 → 12 → 16 → 18 → 20

**Parallelizable:**
- Tasks 4-5 (BP changes) ∥ Tasks 1-3 (Kuzu) — converge at Task 12
- Task 15 (--json flag) can run anytime after Task 9
- Tasks 22-24 (test hardening) can run after their dependencies are met
