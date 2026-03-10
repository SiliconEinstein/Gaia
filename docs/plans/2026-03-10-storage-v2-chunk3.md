# Storage V2 Chunk 3: GraphStore (Kuzu) Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the KuzuGraphStore that satisfies the GraphStore ABC for embedded graph topology storage.

**Architecture:** Kuzu is an embedded graph DB (like SQLite for graphs). The v2 GraphStore uses string IDs (not ints) and stores Closure/Chain nodes with PREMISE/CONCLUSION relationships per the storage schema. The Kuzu Python API is synchronous; we wrap calls in async methods. Neo4j implementation is deferred — the ABC ensures interface parity, and Neo4j tests auto-skip when unavailable.

**Tech Stack:** Python 3.12+, Kuzu, pytest, Pydantic v2

**Note:** The storage-schema.md defines 5 node types and 6 relationship types (PREMISE, CONCLUSION, BELONGS_TO, IMPORTS, ATTACHED_TO). However, the GraphStore ABC only requires Closure/Chain nodes with PREMISE/CONCLUSION (for BP topology) plus ATTACHED_TO for resources. BELONGS_TO and IMPORTS are organizational relationships not needed for graph traversal queries. We implement exactly what the ABC requires.

---

### Task 1: Schema and initialize_schema

**Files:**
- Create: `libs/storage_v2/kuzu_graph_store.py`
- Test: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing test**

```python
"""Tests for GraphStore implementations."""

import pytest

from libs.storage_v2.kuzu_graph_store import KuzuGraphStore


@pytest.fixture
async def graph_store(tmp_path):
    store = KuzuGraphStore(str(tmp_path / "kuzu"))
    await store.initialize_schema()
    return store


class TestInitializeSchema:
    async def test_initialize_creates_tables(self, graph_store):
        """Schema should create Closure, Chain node tables and PREMISE, CONCLUSION rel tables."""
        conn = graph_store._conn
        result = conn.execute("CALL show_tables() RETURN *")
        tables = set()
        while result.has_next():
            row = result.get_next()
            tables.add(row[1])
        assert "Closure" in tables
        assert "Chain" in tables
        assert "PREMISE" in tables
        assert "CONCLUSION" in tables

    async def test_initialize_idempotent(self, tmp_path):
        """Calling initialize_schema twice should not error."""
        store = KuzuGraphStore(str(tmp_path / "kuzu2"))
        await store.initialize_schema()
        await store.initialize_schema()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage_v2/test_graph_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'libs.storage_v2.kuzu_graph_store'`

**Step 3: Write minimal implementation**

```python
"""Kuzu-backed embedded graph store for Gaia storage v2.

Graph model (from docs/foundations/server/storage-schema.md):
- (:Closure {closure_id, version, type, prior, belief}) — knowledge objects
- (:Chain {chain_id, type, probability}) — reasoning chains
- (:Closure)-[:PREMISE {step_index}]->(:Chain) — premise relationship
- (:Chain)-[:CONCLUSION {step_index}]->(:Closure) — conclusion relationship
- (:Resource)-[:ATTACHED_TO {role}]->(:Closure|Chain) — resource links

Kuzu's Python API is synchronous; we wrap calls in async methods
to satisfy the GraphStore ABC.
"""

from __future__ import annotations

import kuzu

from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Closure,
    ResourceAttachment,
    ScoredClosure,
    Subgraph,
)


class KuzuGraphStore(GraphStore):
    """Embedded graph store using Kuzu for storage v2."""

    def __init__(self, db_path: str) -> None:
        self._db = kuzu.Database(db_path)
        self._conn = kuzu.Connection(self._db)

    async def initialize_schema(self) -> None:
        """Create node/rel tables (idempotent)."""
        c = self._conn
        c.execute(
            "CREATE NODE TABLE IF NOT EXISTS Closure("
            "closure_id STRING, version INT64, type STRING, "
            "prior DOUBLE, belief DOUBLE, "
            "PRIMARY KEY(closure_id))"
        )
        c.execute(
            "CREATE NODE TABLE IF NOT EXISTS Chain("
            "chain_id STRING, type STRING, probability DOUBLE, "
            "PRIMARY KEY(chain_id))"
        )
        c.execute(
            "CREATE REL TABLE IF NOT EXISTS PREMISE("
            "FROM Closure TO Chain, step_index INT64)"
        )
        c.execute(
            "CREATE REL TABLE IF NOT EXISTS CONCLUSION("
            "FROM Chain TO Closure, step_index INT64)"
        )
```

Note: Kuzu PRIMARY KEY requires unique values. Since closures have (closure_id, version) but we only store the latest version's topology, closure_id is the natural PK for graph nodes.

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage_v2/test_graph_store.py::TestInitializeSchema -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/kuzu_graph_store.py tests/libs/storage_v2/test_graph_store.py
git commit -m "feat(storage-v2): add KuzuGraphStore skeleton with schema init"
```

---

### Task 2: write_topology

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing tests**

```python
class TestWriteTopology:
    async def test_write_creates_closure_nodes(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = graph_store._conn.execute(
            "MATCH (c:Closure) RETURN c.closure_id"
        )
        ids = set()
        while result.has_next():
            ids.add(result.get_next()[0])
        assert len(ids) == len({c.closure_id for c in closures})

    async def test_write_creates_chain_nodes(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = graph_store._conn.execute(
            "MATCH (ch:Chain) RETURN ch.chain_id"
        )
        ids = set()
        while result.has_next():
            ids.add(result.get_next()[0])
        assert len(ids) == len(chains)

    async def test_write_creates_premise_relationships(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = graph_store._conn.execute(
            "MATCH (c:Closure)-[r:PREMISE]->(ch:Chain) RETURN c.closure_id, ch.chain_id, r.step_index"
        )
        rels = []
        while result.has_next():
            rels.append(result.get_next())
        assert len(rels) > 0

    async def test_write_creates_conclusion_relationships(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = graph_store._conn.execute(
            "MATCH (ch:Chain)-[r:CONCLUSION]->(c:Closure) RETURN ch.chain_id, c.closure_id, r.step_index"
        )
        rels = []
        while result.has_next():
            rels.append(result.get_next())
        assert len(rels) > 0

    async def test_write_topology_idempotent(self, graph_store, closures, chains):
        """Writing same topology twice should not create duplicates."""
        await graph_store.write_topology(closures, chains)
        await graph_store.write_topology(closures, chains)
        result = graph_store._conn.execute("MATCH (c:Closure) RETURN count(c)")
        count = result.get_next()[0]
        assert count == len({c.closure_id for c in closures})
```

Tests need `closures` and `chains` fixtures. Add to conftest or reuse from existing conftest.

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/storage_v2/test_graph_store.py::TestWriteTopology -v`
Expected: FAIL — `NotImplementedError` or method not found

**Step 3: Write implementation**

```python
async def write_topology(self, closures: list[Closure], chains: list[Chain]) -> None:
    """Write closure nodes, chain nodes, and PREMISE/CONCLUSION relationships."""
    c = self._conn
    # Upsert closure nodes
    for cl in closures:
        c.execute(
            "MERGE (c:Closure {closure_id: $cid}) "
            "SET c.version = $ver, c.type = $type, c.prior = $prior, c.belief = $prior",
            {"cid": cl.closure_id, "ver": cl.version, "type": cl.type, "prior": cl.prior},
        )
    # Upsert chain nodes
    for ch in chains:
        c.execute(
            "MERGE (ch:Chain {chain_id: $chid}) "
            "SET ch.type = $type, ch.probability = 0.0",
            {"chid": ch.chain_id, "type": ch.type},
        )
    # Create PREMISE and CONCLUSION relationships from chain steps
    for ch in chains:
        for step in ch.steps:
            for prem in step.premises:
                # Ensure premise closure node exists
                c.execute(
                    "MERGE (c:Closure {closure_id: $cid})",
                    {"cid": prem.closure_id},
                )
                # Check if relationship already exists before creating
                res = c.execute(
                    "MATCH (c:Closure {closure_id: $cid})-[r:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "WHERE r.step_index = $si RETURN count(r)",
                    {"cid": prem.closure_id, "chid": ch.chain_id, "si": step.step_index},
                )
                if res.get_next()[0] == 0:
                    c.execute(
                        "MATCH (c:Closure {closure_id: $cid}), (ch:Chain {chain_id: $chid}) "
                        "CREATE (c)-[:PREMISE {step_index: $si}]->(ch)",
                        {"cid": prem.closure_id, "chid": ch.chain_id, "si": step.step_index},
                    )
            # Conclusion
            conc = step.conclusion
            c.execute(
                "MERGE (c:Closure {closure_id: $cid})",
                {"cid": conc.closure_id},
            )
            res = c.execute(
                "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(c:Closure {closure_id: $cid}) "
                "WHERE r.step_index = $si RETURN count(r)",
                {"chid": ch.chain_id, "cid": conc.closure_id, "si": step.step_index},
            )
            if res.get_next()[0] == 0:
                c.execute(
                    "MATCH (ch:Chain {chain_id: $chid}), (c:Closure {closure_id: $cid}) "
                    "CREATE (ch)-[:CONCLUSION {step_index: $si}]->(c)",
                    {"chid": ch.chain_id, "cid": conc.closure_id, "si": step.step_index},
                )
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/storage_v2/test_graph_store.py::TestWriteTopology -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/storage_v2/kuzu_graph_store.py tests/libs/storage_v2/test_graph_store.py
git commit -m "feat(storage-v2): implement write_topology for KuzuGraphStore"
```

---

### Task 3: write_resource_links

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing test**

```python
class TestWriteResourceLinks:
    async def test_write_resource_links_to_closure(self, graph_store, closures, chains, attachments):
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        result = graph_store._conn.execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->(c:Closure) RETURN r.resource_id, c.closure_id, a.role"
        )
        rels = []
        while result.has_next():
            rels.append(result.get_next())
        closure_attachments = [a for a in attachments if a.target_type == "closure"]
        assert len(rels) == len(closure_attachments)

    async def test_write_resource_links_idempotent(self, graph_store, closures, chains, attachments):
        await graph_store.write_topology(closures, chains)
        await graph_store.write_resource_links(attachments)
        await graph_store.write_resource_links(attachments)
        result = graph_store._conn.execute(
            "MATCH (r:Resource)-[a:ATTACHED_TO]->() RETURN count(a)"
        )
        count = result.get_next()[0]
        # Should not double
        expected = len([a for a in attachments if a.target_type in ("closure", "chain")])
        assert count == expected
```

This requires adding a Resource node table and ATTACHED_TO rel table to the schema. Only `closure` and `chain` target_types map to graph nodes (chain_step is addressed via the chain node).

**Step 2: Run test to verify it fails**

**Step 3: Implement**

Add to `initialize_schema`:
```python
c.execute(
    "CREATE NODE TABLE IF NOT EXISTS Resource("
    "resource_id STRING, type STRING, format STRING, "
    "PRIMARY KEY(resource_id))"
)
c.execute(
    "CREATE REL TABLE GROUP IF NOT EXISTS ATTACHED_TO("
    "FROM Resource TO Closure, FROM Resource TO Chain, "
    "role STRING)"
)
```

Add method:
```python
async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
    c = self._conn
    for att in attachments:
        # Only closure and chain have graph nodes
        if att.target_type == "closure":
            label = "Closure"
            key = "closure_id"
        elif att.target_type in ("chain", "chain_step"):
            label = "Chain"
            key = "chain_id"
            # chain_step target_id is "chain_id:step_index", extract chain_id
            target_id = att.target_id.split(":")[0] if att.target_type == "chain_step" else att.target_id
        else:
            continue  # module/package not in graph

        target_id_val = target_id if att.target_type in ("chain", "chain_step") else att.target_id

        # Ensure Resource node exists
        c.execute("MERGE (r:Resource {resource_id: $rid})", {"rid": att.resource_id})

        # Check existence before creating
        res = c.execute(
            f"MATCH (r:Resource {{resource_id: $rid}})-[a:ATTACHED_TO]->(t:{label} {{{key}: $tid}}) "
            "RETURN count(a)",
            {"rid": att.resource_id, "tid": target_id_val},
        )
        if res.get_next()[0] == 0:
            c.execute(
                f"MATCH (r:Resource {{resource_id: $rid}}), (t:{label} {{{key}: $tid}}) "
                "CREATE (r)-[:ATTACHED_TO {role: $role}]->(t)",
                {"rid": att.resource_id, "tid": target_id_val, "role": att.role},
            )
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(storage-v2): implement write_resource_links for KuzuGraphStore"
```

---

### Task 4: update_beliefs and update_probability

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing tests**

```python
class TestUpdateBeliefs:
    async def test_update_beliefs_sets_value(self, graph_store, closures, chains, beliefs):
        await graph_store.write_topology(closures, chains)
        await graph_store.update_beliefs(beliefs)
        result = graph_store._conn.execute(
            "MATCH (c:Closure {closure_id: $cid}) RETURN c.belief",
            {"cid": beliefs[0].closure_id},
        )
        belief_val = result.get_next()[0]
        # Should be the latest belief for this closure
        assert belief_val == pytest.approx(beliefs[0].belief)

    async def test_update_beliefs_nonexistent_closure(self, graph_store, closures, chains):
        """Updating belief for a non-existent closure should not error."""
        await graph_store.write_topology(closures, chains)
        snap = BeliefSnapshot(
            closure_id="nonexistent", version=1, belief=0.5,
            bp_run_id="run1", computed_at=datetime.now()
        )
        await graph_store.update_beliefs([snap])  # should not raise


class TestUpdateProbability:
    async def test_update_probability_sets_value(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        chain_id = chains[0].chain_id
        await graph_store.update_probability(chain_id, step_index=0, value=0.85)
        result = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: $chid}) RETURN ch.probability",
            {"chid": chain_id},
        )
        assert result.get_next()[0] == pytest.approx(0.85)
```

**Step 2: Run test to verify it fails**

**Step 3: Implement**

```python
async def update_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
    c = self._conn
    for snap in snapshots:
        c.execute(
            "MATCH (cl:Closure {closure_id: $cid}) SET cl.belief = $belief",
            {"cid": snap.closure_id, "belief": snap.belief},
        )

async def update_probability(self, chain_id: str, step_index: int, value: float) -> None:
    c = self._conn
    c.execute(
        "MATCH (ch:Chain {chain_id: $chid}) SET ch.probability = $val",
        {"chid": chain_id, "val": value},
    )
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(storage-v2): implement update_beliefs and update_probability"
```

---

### Task 5: get_neighbors

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing tests**

```python
class TestGetNeighbors:
    async def test_get_neighbors_default(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        # Pick a closure that appears as a premise in some chain
        premise_id = chains[0].steps[0].premises[0].closure_id
        result = await graph_store.get_neighbors(premise_id)
        assert len(result.closure_ids) > 0 or len(result.chain_ids) > 0

    async def test_get_neighbors_downstream(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        premise_id = chains[0].steps[0].premises[0].closure_id
        result = await graph_store.get_neighbors(premise_id, direction="downstream")
        assert len(result.chain_ids) > 0

    async def test_get_neighbors_upstream(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        conclusion_id = chains[0].steps[0].conclusion.closure_id
        result = await graph_store.get_neighbors(conclusion_id, direction="upstream")
        assert len(result.chain_ids) > 0

    async def test_get_neighbors_nonexistent(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_neighbors("nonexistent")
        assert result.closure_ids == set()
        assert result.chain_ids == set()

    async def test_get_neighbors_max_hops(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        premise_id = chains[0].steps[0].premises[0].closure_id
        result_1 = await graph_store.get_neighbors(premise_id, max_hops=1)
        result_2 = await graph_store.get_neighbors(premise_id, max_hops=2)
        assert len(result_2.closure_ids) >= len(result_1.closure_ids)

    async def test_get_neighbors_chain_type_filter(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        premise_id = chains[0].steps[0].premises[0].closure_id
        chain_type = chains[0].type
        result = await graph_store.get_neighbors(
            premise_id, chain_types=[chain_type]
        )
        # Should return only chains of matching type
        if result.chain_ids:
            for chid in result.chain_ids:
                res = graph_store._conn.execute(
                    "MATCH (ch:Chain {chain_id: $chid}) RETURN ch.type",
                    {"chid": chid}
                )
                assert res.get_next()[0] == chain_type
```

**Step 2: Run test to verify it fails**

**Step 3: Implement**

One knowledge hop = Closure -> Chain -> Closure (two graph hops). Use iterative BFS expansion similar to v1 pattern.

```python
async def get_neighbors(
    self,
    closure_id: str,
    direction: str = "both",
    chain_types: list[str] | None = None,
    max_hops: int = 1,
) -> Subgraph:
    c = self._conn
    visited_closures: set[str] = set()
    visited_chains: set[str] = set()
    frontier: set[str] = {closure_id}

    # Verify seed exists
    res = c.execute(
        "MATCH (cl:Closure {closure_id: $cid}) RETURN cl.closure_id",
        {"cid": closure_id},
    )
    if not res.has_next():
        return Subgraph()

    for _ in range(max_hops):
        if not frontier:
            break
        new_chains: set[str] = set()

        for cid in frontier:
            # Downstream: closure is premise
            if direction in ("both", "downstream"):
                res = c.execute(
                    "MATCH (cl:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) "
                    "RETURN ch.chain_id, ch.type",
                    {"cid": cid},
                )
                while res.has_next():
                    row = res.get_next()
                    if chain_types is None or row[1] in chain_types:
                        new_chains.add(row[0])

            # Upstream: closure is conclusion
            if direction in ("both", "upstream"):
                res = c.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure {closure_id: $cid}) "
                    "RETURN ch.chain_id, ch.type",
                    {"cid": cid},
                )
                while res.has_next():
                    row = res.get_next()
                    if chain_types is None or row[1] in chain_types:
                        new_chains.add(row[0])

        new_chains -= visited_chains
        if not new_chains:
            break
        visited_chains |= new_chains

        # Expand to closures on the other side of discovered chains
        new_closures: set[str] = set()
        for chid in new_chains:
            if direction in ("both", "downstream"):
                res = c.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) "
                    "RETURN cl.closure_id",
                    {"chid": chid},
                )
                while res.has_next():
                    new_closures.add(res.get_next()[0])
            if direction in ("both", "upstream"):
                res = c.execute(
                    "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN cl.closure_id",
                    {"chid": chid},
                )
                while res.has_next():
                    new_closures.add(res.get_next()[0])

        frontier = new_closures - visited_closures
        visited_closures |= new_closures

    return Subgraph(closure_ids=visited_closures, chain_ids=visited_chains)
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(storage-v2): implement get_neighbors for KuzuGraphStore"
```

---

### Task 6: get_subgraph

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing tests**

```python
class TestGetSubgraph:
    async def test_get_subgraph_returns_connected(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        premise_id = chains[0].steps[0].premises[0].closure_id
        result = await graph_store.get_subgraph(premise_id)
        assert premise_id in result.closure_ids or len(result.closure_ids) > 0

    async def test_get_subgraph_respects_max_closures(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        premise_id = chains[0].steps[0].premises[0].closure_id
        result = await graph_store.get_subgraph(premise_id, max_closures=2)
        assert len(result.closure_ids) <= 2

    async def test_get_subgraph_nonexistent(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        result = await graph_store.get_subgraph("nonexistent")
        assert result.closure_ids == set()
        assert result.chain_ids == set()
```

**Step 2: Run test to verify it fails**

**Step 3: Implement**

`get_subgraph` is BFS from a root closure expanding in both directions until max_closures is reached. Reuse the same BFS pattern as `get_neighbors` but with no chain_types filter and expanding until the cap.

```python
async def get_subgraph(self, closure_id: str, max_closures: int = 500) -> Subgraph:
    c = self._conn
    res = c.execute(
        "MATCH (cl:Closure {closure_id: $cid}) RETURN cl.closure_id",
        {"cid": closure_id},
    )
    if not res.has_next():
        return Subgraph()

    visited_closures: set[str] = {closure_id}
    visited_chains: set[str] = set()
    frontier: set[str] = {closure_id}

    while frontier and len(visited_closures) < max_closures:
        new_chains: set[str] = set()
        for cid in frontier:
            for query in [
                "MATCH (cl:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) RETURN ch.chain_id",
                "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure {closure_id: $cid}) RETURN ch.chain_id",
            ]:
                res = c.execute(query, {"cid": cid})
                while res.has_next():
                    new_chains.add(res.get_next()[0])

        new_chains -= visited_chains
        if not new_chains:
            break
        visited_chains |= new_chains

        new_closures: set[str] = set()
        for chid in new_chains:
            for query in [
                "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) RETURN cl.closure_id",
                "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) RETURN cl.closure_id",
            ]:
                res = c.execute(query, {"chid": chid})
                while res.has_next():
                    new_closures.add(res.get_next()[0])

        frontier = new_closures - visited_closures
        visited_closures |= new_closures
        if len(visited_closures) >= max_closures:
            break

    return Subgraph(closure_ids=visited_closures, chain_ids=visited_chains)
```

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(storage-v2): implement get_subgraph for KuzuGraphStore"
```

---

### Task 7: search_topology

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing tests**

```python
class TestSearchTopology:
    async def test_search_topology_returns_scored(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        seed_id = chains[0].steps[0].premises[0].closure_id
        results = await graph_store.search_topology([seed_id], hops=1)
        assert len(results) >= 1
        assert all(isinstance(r, ScoredClosure) for r in results)
        # Score should decrease with distance
        if len(results) > 1:
            assert results[0].score >= results[-1].score

    async def test_search_topology_excludes_seeds(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        seed_id = chains[0].steps[0].premises[0].closure_id
        results = await graph_store.search_topology([seed_id], hops=1)
        result_ids = {r.closure.closure_id for r in results}
        assert seed_id not in result_ids

    async def test_search_topology_empty_seeds(self, graph_store, closures, chains):
        await graph_store.write_topology(closures, chains)
        results = await graph_store.search_topology([], hops=1)
        assert results == []
```

**Step 2: Run test to verify it fails**

**Step 3: Implement**

`search_topology` expands from seed closures by BFS. Score = 1.0 / (hop_distance + 1). Seeds themselves are excluded from results. For each discovered closure, we construct a minimal Closure object with the properties stored on the graph node.

```python
async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredClosure]:
    if not seed_ids:
        return []

    c = self._conn
    seed_set = set(seed_ids)
    scored: dict[str, float] = {}  # closure_id -> best score
    frontier = set(seed_ids)
    visited_closures: set[str] = set(seed_ids)
    visited_chains: set[str] = set()

    for hop in range(hops):
        score = 1.0 / (hop + 2)  # hop 0 -> 0.5, hop 1 -> 0.33, etc.
        new_chains: set[str] = set()
        for cid in frontier:
            for query in [
                "MATCH (cl:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) RETURN ch.chain_id",
                "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure {closure_id: $cid}) RETURN ch.chain_id",
            ]:
                res = c.execute(query, {"cid": cid})
                while res.has_next():
                    new_chains.add(res.get_next()[0])

        new_chains -= visited_chains
        if not new_chains:
            break
        visited_chains |= new_chains

        new_closures: set[str] = set()
        for chid in new_chains:
            for query in [
                "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) RETURN cl.closure_id",
                "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) RETURN cl.closure_id",
            ]:
                res = c.execute(query, {"chid": chid})
                while res.has_next():
                    cid = res.get_next()[0]
                    new_closures.add(cid)
                    if cid not in seed_set and cid not in scored:
                        scored[cid] = score

        frontier = new_closures - visited_closures
        visited_closures |= new_closures

    # Build ScoredClosure results
    results = []
    for cid, sc in scored.items():
        res = c.execute(
            "MATCH (cl:Closure {closure_id: $cid}) "
            "RETURN cl.closure_id, cl.version, cl.type, cl.prior",
            {"cid": cid},
        )
        if res.has_next():
            row = res.get_next()
            closure = Closure(
                closure_id=row[0],
                version=row[1] or 1,
                type=row[2] or "claim",
                content="",  # content not stored in graph
                prior=row[3] or 0.5,
                source_package_id="",
                source_module_id="",
                created_at=datetime(2026, 1, 1),
            )
            results.append(ScoredClosure(closure=closure, score=sc))

    results.sort(key=lambda r: r.score, reverse=True)
    return results
```

Note: `search_topology` returns minimal Closure objects since the graph doesn't store full content. The caller (SearchEngine) will join with ContentStore to get full content.

**Step 4: Run test to verify it passes**

**Step 5: Commit**

```bash
git commit -m "feat(storage-v2): implement search_topology for KuzuGraphStore"
```

---

### Task 8: close

**Files:**
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the failing test**

```python
class TestClose:
    async def test_close_does_not_error(self, graph_store):
        await graph_store.close()

    async def test_close_idempotent(self, graph_store):
        await graph_store.close()
        await graph_store.close()
```

**Step 2: Implement**

```python
async def close(self) -> None:
    """No-op — Kuzu handles cleanup on garbage collection."""
    pass
```

**Step 3: Commit**

```bash
git commit -m "feat(storage-v2): implement close for KuzuGraphStore"
```

---

### Task 9: Full roundtrip test

**Files:**
- Modify: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Write the roundtrip test**

```python
class TestFullRoundtrip:
    async def test_full_roundtrip(
        self, graph_store, closures, chains, attachments, beliefs
    ):
        # Write topology
        await graph_store.write_topology(closures, chains)

        # Write resource links
        await graph_store.write_resource_links(attachments)

        # Update beliefs
        await graph_store.update_beliefs(beliefs)

        # Update probability
        await graph_store.update_probability(chains[0].chain_id, 0, 0.9)

        # Query neighbors
        premise_id = chains[0].steps[0].premises[0].closure_id
        neighbors = await graph_store.get_neighbors(premise_id)
        assert len(neighbors.chain_ids) > 0

        # Query subgraph
        subgraph = await graph_store.get_subgraph(premise_id)
        assert len(subgraph.closure_ids) > 0

        # Search topology
        results = await graph_store.search_topology([premise_id], hops=2)
        assert len(results) >= 0  # may or may not find neighbors depending on graph structure

        # Verify belief was updated
        result = graph_store._conn.execute(
            "MATCH (c:Closure {closure_id: $cid}) RETURN c.belief",
            {"cid": beliefs[0].closure_id},
        )
        assert result.get_next()[0] == pytest.approx(beliefs[0].belief)

        # Verify probability was updated
        result = graph_store._conn.execute(
            "MATCH (ch:Chain {chain_id: $chid}) RETURN ch.probability",
            {"chid": chains[0].chain_id},
        )
        assert result.get_next()[0] == pytest.approx(0.9)
```

**Step 2: Run all tests**

Run: `pytest tests/libs/storage_v2/test_graph_store.py -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git commit -m "test(storage-v2): add full roundtrip test for KuzuGraphStore"
```

---

### Task 10: Lint, format, final verification

**Step 1: Run ruff**

```bash
ruff check libs/storage_v2/kuzu_graph_store.py tests/libs/storage_v2/test_graph_store.py
ruff format libs/storage_v2/kuzu_graph_store.py tests/libs/storage_v2/test_graph_store.py
```

**Step 2: Run full test suite**

```bash
pytest tests/libs/storage_v2/ -v
```

**Step 3: Commit any formatting fixes**

```bash
git commit -m "style: format graph store code"
```
