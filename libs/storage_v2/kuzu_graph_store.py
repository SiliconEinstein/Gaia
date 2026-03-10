"""KuzuGraphStore — embedded graph backend using Kùzu.

Graph model (from docs/foundations/server/storage-schema.md §3.2):

Nodes:
    (:Closure {closure_vid, closure_id, version, type, prior, belief})
    (:Chain   {chain_id, type})

Relationships:
    (:Closure)-[:PREMISE   {step_index}]->(:Chain)
    (:Chain)  -[:CONCLUSION{step_index, probability}]->(:Closure)
    (:Resource)-[:ATTACHED_TO {role, step_index}]->(:Closure|:Chain)

Closure nodes are keyed by ``closure_vid`` = ``closure_id@version``, giving
each (closure_id, version) pair its own graph node.  BFS queries that accept
only ``closure_id`` match all versions via the ``closure_id`` property.

Probability is stored per (chain_id, step_index) on CONCLUSION relationships,
not as a single scalar on the Chain node, preserving step-level granularity.

Kùzu's Python API is synchronous; we wrap calls in async methods.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from pathlib import Path

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

_SCHEMA_STATEMENTS = [
    # closure_vid = "closure_id@version" — composite string PK
    (
        "CREATE NODE TABLE IF NOT EXISTS Closure("
        "closure_vid STRING, closure_id STRING, version INT64, "
        "type STRING, prior DOUBLE, belief DOUBLE, "
        "PRIMARY KEY(closure_vid))"
    ),
    ("CREATE NODE TABLE IF NOT EXISTS Chain(chain_id STRING, type STRING, PRIMARY KEY(chain_id))"),
    "CREATE REL TABLE IF NOT EXISTS PREMISE(FROM Closure TO Chain, step_index INT64)",
    (
        "CREATE REL TABLE IF NOT EXISTS CONCLUSION("
        "FROM Chain TO Closure, step_index INT64, probability DOUBLE)"
    ),
    (
        "CREATE NODE TABLE IF NOT EXISTS Resource("
        "resource_id STRING, type STRING, format STRING, "
        "PRIMARY KEY(resource_id))"
    ),
    (
        "CREATE REL TABLE GROUP IF NOT EXISTS ATTACHED_TO("
        "FROM Resource TO Closure, FROM Resource TO Chain, "
        "role STRING, step_index INT64)"
    ),
]


def _vid(closure_id: str, version: int) -> str:
    """Build the composite primary key for a Closure node."""
    return f"{closure_id}@{version}"


class KuzuGraphStore(GraphStore):
    """Graph topology backend backed by an embedded Kùzu database.

    Kùzu's Python API is synchronous, so all public methods offload work to
    a thread via ``asyncio.run_in_executor``.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db = kuzu.Database(str(db_path))
        self._conn: kuzu.Connection | None = kuzu.Connection(self._db)

    # ── helpers ──

    def _execute(self, query: str) -> kuzu.QueryResult:
        """Run a Cypher query synchronously on the internal connection."""
        return self._conn.execute(query)

    # ── Schema setup ──

    async def initialize_schema(self) -> None:
        """Create node/rel tables if they do not already exist."""
        loop = asyncio.get_running_loop()
        for stmt in _SCHEMA_STATEMENTS:
            await loop.run_in_executor(None, partial(self._execute, stmt))

    # ── Write ──

    async def write_topology(self, closures: list[Closure], chains: list[Chain]) -> None:
        """Upsert closures and chains, then wire PREMISE/CONCLUSION rels."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._write_topology_sync, closures, chains))

    def _write_topology_sync(self, closures: list[Closure], chains: list[Chain]) -> None:
        c = self._conn
        # 1. MERGE closure nodes (keyed by closure_vid)
        for cl in closures:
            vid = _vid(cl.closure_id, cl.version)
            c.execute(
                "MERGE (n:Closure {closure_vid: $vid}) "
                "SET n.closure_id = $cid, n.version = $ver, "
                "n.type = $type, n.prior = $prior, n.belief = $prior",
                {
                    "vid": vid,
                    "cid": cl.closure_id,
                    "ver": cl.version,
                    "type": cl.type,
                    "prior": cl.prior,
                },
            )

        # 2. MERGE chain nodes
        for ch in chains:
            c.execute(
                "MERGE (n:Chain {chain_id: $id}) SET n.type = $type",
                {"id": ch.chain_id, "type": ch.type},
            )

        # 3. Create PREMISE / CONCLUSION relationships from chain steps
        for ch in chains:
            for step in ch.steps:
                for prem in step.premises:
                    self._merge_closure_stub(prem.closure_id, prem.version)
                    self._ensure_rel(
                        "PREMISE",
                        "Closure",
                        "closure_vid",
                        _vid(prem.closure_id, prem.version),
                        "Chain",
                        "chain_id",
                        ch.chain_id,
                        step.step_index,
                    )

                conc = step.conclusion
                self._merge_closure_stub(conc.closure_id, conc.version)
                self._ensure_rel(
                    "CONCLUSION",
                    "Chain",
                    "chain_id",
                    ch.chain_id,
                    "Closure",
                    "closure_vid",
                    _vid(conc.closure_id, conc.version),
                    step.step_index,
                )

    def _merge_closure_stub(self, closure_id: str, version: int) -> None:
        """MERGE a Closure node with minimal defaults (no-op if already exists)."""
        vid = _vid(closure_id, version)
        self._conn.execute(
            "MERGE (n:Closure {closure_vid: $vid}) "
            "ON CREATE SET n.closure_id = $cid, n.version = $ver, "
            "n.type = 'claim', n.prior = 0.5, n.belief = 0.5",
            {"vid": vid, "cid": closure_id, "ver": version},
        )

    def _ensure_rel(
        self,
        rel_type: str,
        from_label: str,
        from_key: str,
        from_val: str,
        to_label: str,
        to_key: str,
        to_val: str,
        step_index: int,
    ) -> None:
        """Create a relationship if it does not already exist."""
        check_q = (
            f"MATCH (a:{from_label} {{{from_key}: $fv}})"
            f"-[r:{rel_type}]->"
            f"(b:{to_label} {{{to_key}: $tv}}) "
            f"WHERE r.step_index = $si RETURN COUNT(r)"
        )
        result = self._conn.execute(check_q, {"fv": from_val, "tv": to_val, "si": step_index})
        if result.get_next()[0] == 0:
            extra = ", probability: 0.0" if rel_type == "CONCLUSION" else ""
            create_q = (
                f"MATCH (a:{from_label} {{{from_key}: $fv}}), "
                f"(b:{to_label} {{{to_key}: $tv}}) "
                f"CREATE (a)-[:{rel_type} {{step_index: $si{extra}}}]->(b)"
            )
            self._conn.execute(create_q, {"fv": from_val, "tv": to_val, "si": step_index})

    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
        """Write Resource nodes and ATTACHED_TO relationships.

        Only ``closure``, ``chain``, and ``chain_step`` target types map to
        graph nodes.  For ``chain_step``, ``step_index`` is preserved on the
        relationship.  ``module`` and ``package`` targets are skipped.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._write_resource_links_sync, attachments))

    def _write_resource_links_sync(self, attachments: list[ResourceAttachment]) -> None:
        c = self._conn
        for att in attachments:
            if att.target_type in ("module", "package"):
                continue

            if att.target_type == "closure":
                # Resolve to latest version of this closure in the graph
                res = c.execute(
                    "MATCH (cl:Closure) WHERE cl.closure_id = $cid "
                    "RETURN cl.closure_vid ORDER BY cl.version DESC LIMIT 1",
                    {"cid": att.target_id},
                )
                if not res.has_next():
                    continue  # closure not in graph; skip
                dest_label = "Closure"
                dest_key = "closure_vid"
                dest_id = res.get_next()[0]
                step_idx = -1
            elif att.target_type == "chain":
                dest_label = "Chain"
                dest_key = "chain_id"
                dest_id = att.target_id
                step_idx = -1
            elif att.target_type == "chain_step":
                # target_id format: "chain_id:step_index"
                parts = att.target_id.rsplit(":", 1)
                dest_label = "Chain"
                dest_key = "chain_id"
                dest_id = parts[0]
                step_idx = int(parts[1])
            else:
                continue

            # MERGE the Resource node
            c.execute("MERGE (r:Resource {resource_id: $rid})", {"rid": att.resource_id})

            # Check-then-create with step_index in dedup
            check_q = (
                f"MATCH (r:Resource {{resource_id: $rid}})"
                f"-[a:ATTACHED_TO]->"
                f"(t:{dest_label} {{{dest_key}: $tid}}) "
                f"WHERE a.role = $role AND a.step_index = $si RETURN COUNT(a)"
            )
            result = c.execute(
                check_q,
                {"rid": att.resource_id, "tid": dest_id, "role": att.role, "si": step_idx},
            )
            if result.get_next()[0] == 0:
                create_q = (
                    f"MATCH (r:Resource {{resource_id: $rid}}), "
                    f"(t:{dest_label} {{{dest_key}: $tid}}) "
                    f"CREATE (r)-[:ATTACHED_TO {{role: $role, step_index: $si}}]->(t)"
                )
                c.execute(
                    create_q,
                    {"rid": att.resource_id, "tid": dest_id, "role": att.role, "si": step_idx},
                )

    async def update_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Set belief values on Closure nodes, keyed by (closure_id, version)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._update_beliefs_sync, snapshots))

    def _update_beliefs_sync(self, snapshots: list[BeliefSnapshot]) -> None:
        for snap in snapshots:
            vid = _vid(snap.closure_id, snap.version)
            self._conn.execute(
                "MATCH (cl:Closure {closure_vid: $vid}) SET cl.belief = $belief",
                {"vid": vid, "belief": snap.belief},
            )

    async def update_probability(self, chain_id: str, step_index: int, value: float) -> None:
        """Set probability on a CONCLUSION relationship for (chain_id, step_index)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(self._update_probability_sync, chain_id, step_index, value),
        )

    def _update_probability_sync(self, chain_id: str, step_index: int, value: float) -> None:
        self._conn.execute(
            "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(:Closure) "
            "WHERE r.step_index = $si SET r.probability = $val",
            {"chid": chain_id, "si": step_index, "val": value},
        )

    # ── Query ──

    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        """BFS expansion from a closure through chains, returning discovered IDs.

        Matches all versions of the given ``closure_id``.  One "knowledge hop"
        = Closure → Chain → Closure (two graph hops).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._get_neighbors_sync, closure_id, direction, chain_types, max_hops),
        )

    def _get_neighbors_sync(
        self,
        closure_id: str,
        direction: str,
        chain_types: list[str] | None,
        max_hops: int,
    ) -> Subgraph:
        c = self._conn
        # Verify seed exists (any version)
        result = c.execute(
            "MATCH (cl:Closure) WHERE cl.closure_id = $cid RETURN cl.closure_id LIMIT 1",
            {"cid": closure_id},
        )
        if not result.has_next():
            return Subgraph()

        all_closure_ids: set[str] = set()
        all_chain_ids: set[str] = set()
        frontier: set[str] = {closure_id}
        visited_closures: set[str] = {closure_id}

        for _ in range(max_hops):
            if not frontier:
                break

            new_chains: set[str] = set()

            for cid in frontier:
                if direction in ("downstream", "both"):
                    res = c.execute(
                        "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain) "
                        "WHERE cl.closure_id = $cid "
                        "RETURN ch.chain_id, ch.type",
                        {"cid": cid},
                    )
                    while res.has_next():
                        row = res.get_next()
                        if chain_types is None or row[1] in chain_types:
                            new_chains.add(row[0])

                if direction in ("upstream", "both"):
                    res = c.execute(
                        "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure) "
                        "WHERE cl.closure_id = $cid "
                        "RETURN ch.chain_id, ch.type",
                        {"cid": cid},
                    )
                    while res.has_next():
                        row = res.get_next()
                        if chain_types is None or row[1] in chain_types:
                            new_chains.add(row[0])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                if direction in ("downstream", "both"):
                    res = c.execute(
                        "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) "
                        "RETURN DISTINCT cl.closure_id",
                        {"chid": ch_id},
                    )
                    while res.has_next():
                        found = res.get_next()[0]
                        if found not in visited_closures:
                            next_frontier.add(found)

                if direction in ("upstream", "both"):
                    res = c.execute(
                        "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                        "RETURN DISTINCT cl.closure_id",
                        {"chid": ch_id},
                    )
                    while res.has_next():
                        found = res.get_next()[0]
                        if found not in visited_closures:
                            next_frontier.add(found)

            all_closure_ids.update(next_frontier)
            visited_closures.update(next_frontier)
            frontier = next_frontier

        return Subgraph(closure_ids=all_closure_ids, chain_ids=all_chain_ids)

    async def get_subgraph(self, closure_id: str, max_closures: int = 500) -> Subgraph:
        """BFS from root closure in both directions, up to max_closures."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._get_subgraph_sync, closure_id, max_closures),
        )

    def _get_subgraph_sync(self, closure_id: str, max_closures: int) -> Subgraph:
        c = self._conn
        result = c.execute(
            "MATCH (cl:Closure) WHERE cl.closure_id = $cid RETURN cl.closure_id LIMIT 1",
            {"cid": closure_id},
        )
        if not result.has_next():
            return Subgraph()

        all_closure_ids: set[str] = {closure_id}
        all_chain_ids: set[str] = set()
        frontier: set[str] = {closure_id}

        while frontier and len(all_closure_ids) < max_closures:
            new_chains: set[str] = set()
            for cid in frontier:
                res = c.execute(
                    "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain) "
                    "WHERE cl.closure_id = $cid RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                res = c.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure) "
                    "WHERE cl.closure_id = $cid RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                res = c.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) "
                    "RETURN DISTINCT cl.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_closure_ids:
                        next_frontier.add(found)

                res = c.execute(
                    "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT cl.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_closure_ids:
                        next_frontier.add(found)

            remaining = max_closures - len(all_closure_ids)
            if len(next_frontier) > remaining:
                next_frontier = set(list(next_frontier)[:remaining])

            all_closure_ids.update(next_frontier)
            frontier = next_frontier

        return Subgraph(closure_ids=all_closure_ids, chain_ids=all_chain_ids)

    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredClosure]:
        """BFS from seed closures, scoring by distance.

        Score = 1.0 / (hop + 2). Seed closures are excluded from results.
        Returns minimal Closure objects (content not stored in graph).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._search_topology_sync, seed_ids, hops),
        )

    def _search_topology_sync(self, seed_ids: list[str], hops: int) -> list[ScoredClosure]:
        if not seed_ids:
            return []

        c = self._conn
        seed_set = set(seed_ids)
        discovered: dict[str, int] = {}
        frontier: set[str] = set(seed_ids)
        visited: set[str] = set(seed_ids)

        for hop in range(hops):
            if not frontier:
                break

            new_chains: set[str] = set()
            for cid in frontier:
                res = c.execute(
                    "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain) "
                    "WHERE cl.closure_id = $cid RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                res = c.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(cl:Closure) "
                    "WHERE cl.closure_id = $cid RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                res = c.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(cl:Closure) "
                    "RETURN DISTINCT cl.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

                res = c.execute(
                    "MATCH (cl:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT cl.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

            visited.update(next_frontier)
            frontier = next_frontier

        # Build scored results, excluding seeds
        results: list[ScoredClosure] = []
        for cid, hop_dist in discovered.items():
            if cid in seed_set:
                continue

            # Fetch the latest-version node properties
            res = c.execute(
                "MATCH (cl:Closure) WHERE cl.closure_id = $cid "
                "RETURN cl.version, cl.type, cl.prior "
                "ORDER BY cl.version DESC LIMIT 1",
                {"cid": cid},
            )
            if not res.has_next():
                continue
            row = res.get_next()

            closure = Closure(
                closure_id=cid,
                version=row[0],
                type=row[1],
                content="",
                prior=row[2],
                source_package_id="",
                source_module_id="",
                created_at=datetime(2026, 1, 1),
            )
            results.append(ScoredClosure(closure=closure, score=1.0 / (hop_dist + 2)))

        results.sort(key=lambda sc: sc.score, reverse=True)
        return results

    # ── Lifecycle ──

    async def close(self) -> None:
        """Release the Kùzu connection (idempotent)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
