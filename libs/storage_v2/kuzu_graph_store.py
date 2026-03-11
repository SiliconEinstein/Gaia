"""KuzuGraphStore — embedded graph backend using Kuzu.

Graph model (from docs/foundations/server/storage-schema.md §3.2):

Nodes:
    (:Knowledge {knowledge_vid, knowledge_id, version, type, prior, belief})
    (:Chain   {chain_id, type})

Relationships:
    (:Knowledge)-[:PREMISE   {step_index}]->(:Chain)
    (:Chain)  -[:CONCLUSION{step_index, probability}]->(:Knowledge)
    (:Resource)-[:ATTACHED_TO {role, step_index}]->(:Knowledge|:Chain)

Knowledge nodes are keyed by ``knowledge_vid`` = ``knowledge_id@version``, giving
each (knowledge_id, version) pair its own graph node.  BFS queries that accept
only ``knowledge_id`` match all versions via the ``knowledge_id`` property.

Probability is stored per (chain_id, step_index) on CONCLUSION relationships,
not as a single scalar on the Chain node, preserving step-level granularity.

Kuzu's Python API is synchronous; we wrap calls in async methods.
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
    Knowledge,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)

_SCHEMA_STATEMENTS = [
    # knowledge_vid = "knowledge_id@version" — composite string PK
    (
        "CREATE NODE TABLE IF NOT EXISTS Knowledge("
        "knowledge_vid STRING, knowledge_id STRING, version INT64, "
        "type STRING, prior DOUBLE, belief DOUBLE, "
        "PRIMARY KEY(knowledge_vid))"
    ),
    ("CREATE NODE TABLE IF NOT EXISTS Chain(chain_id STRING, type STRING, PRIMARY KEY(chain_id))"),
    "CREATE REL TABLE IF NOT EXISTS PREMISE(FROM Knowledge TO Chain, step_index INT64)",
    (
        "CREATE REL TABLE IF NOT EXISTS CONCLUSION("
        "FROM Chain TO Knowledge, step_index INT64, probability DOUBLE)"
    ),
    (
        "CREATE NODE TABLE IF NOT EXISTS Resource("
        "resource_id STRING, type STRING, format STRING, "
        "PRIMARY KEY(resource_id))"
    ),
    (
        "CREATE REL TABLE GROUP IF NOT EXISTS ATTACHED_TO("
        "FROM Resource TO Knowledge, FROM Resource TO Chain, "
        "role STRING, step_index INT64)"
    ),
]


def _knowledge_vid(knowledge_id: str, version: int) -> str:
    """Build the composite primary key for a Knowledge node."""
    return f"{knowledge_id}@{version}"


class KuzuGraphStore(GraphStore):
    """Graph topology backend backed by an embedded Kuzu database.

    Kuzu's Python API is synchronous, so all public methods offload work to
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

    # ── Delete ──

    async def delete_package(self, package_id: str) -> None:
        """Delete all Knowledge, Chain, and Resource nodes (and their rels) for a package."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._delete_package_sync, package_id))

    def _delete_package_sync(self, package_id: str) -> None:
        c = self._conn
        dot_prefix = f"{package_id}."
        slash_prefix = f"{package_id}/"
        # Delete chains (chain_id starts with "package_id.")
        c.execute(
            "MATCH (ch:Chain) WHERE starts_with(ch.chain_id, $prefix) DETACH DELETE ch",
            {"prefix": dot_prefix},
        )
        # Delete knowledge nodes — knowledge_id may use slash (CLI-published: "pkg/decl")
        # or dot (fixture/legacy: "pkg.module.decl") convention.
        c.execute(
            "MATCH (kn:Knowledge) WHERE starts_with(kn.knowledge_vid, $p1) "
            "OR starts_with(kn.knowledge_vid, $p2) DETACH DELETE kn",
            {"p1": slash_prefix, "p2": dot_prefix},
        )
        # Delete resources (resource_id starts with "package_id.")
        c.execute(
            "MATCH (r:Resource) WHERE starts_with(r.resource_id, $prefix) DETACH DELETE r",
            {"prefix": dot_prefix},
        )

    # ── Write ──

    async def write_topology(self, knowledge_items: list[Knowledge], chains: list[Chain]) -> None:
        """Upsert knowledge items and chains, then wire PREMISE/CONCLUSION rels."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None, partial(self._write_topology_sync, knowledge_items, chains)
        )

    def _write_topology_sync(self, knowledge_items: list[Knowledge], chains: list[Chain]) -> None:
        c = self._conn
        # 1. MERGE knowledge nodes (keyed by knowledge_vid)
        for kn in knowledge_items:
            vid = _knowledge_vid(kn.knowledge_id, kn.version)
            c.execute(
                "MERGE (n:Knowledge {knowledge_vid: $vid}) "
                "SET n.knowledge_id = $kid, n.version = $ver, "
                "n.type = $type, n.prior = $prior, n.belief = $prior",
                {
                    "vid": vid,
                    "kid": kn.knowledge_id,
                    "ver": kn.version,
                    "type": kn.type,
                    "prior": kn.prior,
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
                    self._merge_knowledge_stub(prem.knowledge_id, prem.version)
                    self._ensure_rel(
                        "PREMISE",
                        "Knowledge",
                        "knowledge_vid",
                        _knowledge_vid(prem.knowledge_id, prem.version),
                        "Chain",
                        "chain_id",
                        ch.chain_id,
                        step.step_index,
                    )

                conc = step.conclusion
                self._merge_knowledge_stub(conc.knowledge_id, conc.version)
                self._ensure_rel(
                    "CONCLUSION",
                    "Chain",
                    "chain_id",
                    ch.chain_id,
                    "Knowledge",
                    "knowledge_vid",
                    _knowledge_vid(conc.knowledge_id, conc.version),
                    step.step_index,
                )

    def _merge_knowledge_stub(self, knowledge_id: str, version: int) -> None:
        """MERGE a Knowledge node with minimal defaults (no-op if already exists)."""
        vid = _knowledge_vid(knowledge_id, version)
        self._conn.execute(
            "MERGE (n:Knowledge {knowledge_vid: $vid}) "
            "ON CREATE SET n.knowledge_id = $kid, n.version = $ver, "
            "n.type = 'claim', n.prior = 0.5, n.belief = 0.5",
            {"vid": vid, "kid": knowledge_id, "ver": version},
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

        Only ``knowledge``, ``chain``, and ``chain_step`` target types map to
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

            if att.target_type == "knowledge":
                # Resolve to latest version of this knowledge item in the graph
                res = c.execute(
                    "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid "
                    "RETURN kn.knowledge_vid ORDER BY kn.version DESC LIMIT 1",
                    {"kid": att.target_id},
                )
                if not res.has_next():
                    continue  # knowledge item not in graph; skip
                dest_label = "Knowledge"
                dest_key = "knowledge_vid"
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
        """Set belief values on Knowledge nodes, keyed by (knowledge_id, version)."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._update_beliefs_sync, snapshots))

    def _update_beliefs_sync(self, snapshots: list[BeliefSnapshot]) -> None:
        for snap in snapshots:
            vid = _knowledge_vid(snap.knowledge_id, snap.version)
            self._conn.execute(
                "MATCH (kn:Knowledge {knowledge_vid: $vid}) SET kn.belief = $belief",
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
            "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(:Knowledge) "
            "WHERE r.step_index = $si SET r.probability = $val",
            {"chid": chain_id, "si": step_index, "val": value},
        )

    # ── Query ──

    async def get_neighbors(
        self,
        knowledge_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        """BFS expansion from a knowledge item through chains, returning discovered IDs.

        Matches all versions of the given ``knowledge_id``.  One "knowledge hop"
        = Knowledge -> Chain -> Knowledge (two graph hops).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._get_neighbors_sync, knowledge_id, direction, chain_types, max_hops),
        )

    def _get_neighbors_sync(
        self,
        knowledge_id: str,
        direction: str,
        chain_types: list[str] | None,
        max_hops: int,
    ) -> Subgraph:
        c = self._conn
        # Verify seed exists (any version)
        result = c.execute(
            "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid RETURN kn.knowledge_id LIMIT 1",
            {"kid": knowledge_id},
        )
        if not result.has_next():
            return Subgraph()

        all_knowledge_ids: set[str] = set()
        all_chain_ids: set[str] = set()
        frontier: set[str] = {knowledge_id}
        visited_knowledge: set[str] = {knowledge_id}

        for _ in range(max_hops):
            if not frontier:
                break

            new_chains: set[str] = set()

            for kid in frontier:
                if direction in ("downstream", "both"):
                    res = c.execute(
                        "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                        "WHERE kn.knowledge_id = $kid "
                        "RETURN ch.chain_id, ch.type",
                        {"kid": kid},
                    )
                    while res.has_next():
                        row = res.get_next()
                        if chain_types is None or row[1] in chain_types:
                            new_chains.add(row[0])

                if direction in ("upstream", "both"):
                    res = c.execute(
                        "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                        "WHERE kn.knowledge_id = $kid "
                        "RETURN ch.chain_id, ch.type",
                        {"kid": kid},
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
                        "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                        "RETURN DISTINCT kn.knowledge_id",
                        {"chid": ch_id},
                    )
                    while res.has_next():
                        found = res.get_next()[0]
                        if found not in visited_knowledge:
                            next_frontier.add(found)

                if direction in ("upstream", "both"):
                    res = c.execute(
                        "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                        "RETURN DISTINCT kn.knowledge_id",
                        {"chid": ch_id},
                    )
                    while res.has_next():
                        found = res.get_next()[0]
                        if found not in visited_knowledge:
                            next_frontier.add(found)

            all_knowledge_ids.update(next_frontier)
            visited_knowledge.update(next_frontier)
            frontier = next_frontier

        return Subgraph(knowledge_ids=all_knowledge_ids, chain_ids=all_chain_ids)

    async def get_subgraph(self, knowledge_id: str, max_knowledge: int = 500) -> Subgraph:
        """BFS from root knowledge item in both directions, up to max_knowledge."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._get_subgraph_sync, knowledge_id, max_knowledge),
        )

    def _get_subgraph_sync(self, knowledge_id: str, max_knowledge: int) -> Subgraph:
        c = self._conn
        result = c.execute(
            "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid RETURN kn.knowledge_id LIMIT 1",
            {"kid": knowledge_id},
        )
        if not result.has_next():
            return Subgraph()

        all_knowledge_ids: set[str] = {knowledge_id}
        all_chain_ids: set[str] = set()
        frontier: set[str] = {knowledge_id}

        while frontier and len(all_knowledge_ids) < max_knowledge:
            new_chains: set[str] = set()
            for kid in frontier:
                res = c.execute(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    {"kid": kid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                res = c.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    {"kid": kid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                res = c.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                    "RETURN DISTINCT kn.knowledge_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_knowledge_ids:
                        next_frontier.add(found)

                res = c.execute(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT kn.knowledge_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_knowledge_ids:
                        next_frontier.add(found)

            remaining = max_knowledge - len(all_knowledge_ids)
            if len(next_frontier) > remaining:
                next_frontier = set(list(next_frontier)[:remaining])

            all_knowledge_ids.update(next_frontier)
            frontier = next_frontier

        return Subgraph(knowledge_ids=all_knowledge_ids, chain_ids=all_chain_ids)

    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredKnowledge]:
        """BFS from seed knowledge items, scoring by distance.

        Score = 1.0 / (hop + 2). Seed knowledge items are excluded from results.
        Returns minimal Knowledge objects (content not stored in graph).
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._search_topology_sync, seed_ids, hops),
        )

    def _search_topology_sync(self, seed_ids: list[str], hops: int) -> list[ScoredKnowledge]:
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
            for kid in frontier:
                res = c.execute(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    {"kid": kid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                res = c.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    {"kid": kid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                res = c.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                    "RETURN DISTINCT kn.knowledge_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

                res = c.execute(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT kn.knowledge_id",
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
        results: list[ScoredKnowledge] = []
        for kid, hop_dist in discovered.items():
            if kid in seed_set:
                continue

            # Fetch the latest-version node properties
            res = c.execute(
                "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid "
                "RETURN kn.version, kn.type, kn.prior "
                "ORDER BY kn.version DESC LIMIT 1",
                {"kid": kid},
            )
            if not res.has_next():
                continue
            row = res.get_next()

            knowledge = Knowledge(
                knowledge_id=kid,
                version=row[0],
                type=row[1],
                content="",
                prior=row[2],
                source_package_id="",
                source_module_id="",
                created_at=datetime(2026, 1, 1),
            )
            results.append(ScoredKnowledge(knowledge=knowledge, score=1.0 / (hop_dist + 2)))

        results.sort(key=lambda sk: sk.score, reverse=True)
        return results

    # ── Lifecycle ──

    async def close(self) -> None:
        """Release the Kuzu connection (idempotent)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
