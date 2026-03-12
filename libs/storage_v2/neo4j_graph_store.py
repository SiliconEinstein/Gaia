"""Neo4jGraphStore — async graph backend using Neo4j for storage v2.

Graph model (mirrors KuzuGraphStore):

Nodes:
    (:Knowledge {knowledge_vid, knowledge_id, version, type, prior, belief})
    (:Chain     {chain_id, type})
    (:Resource  {resource_id, type, format})

Relationships:
    (:Knowledge)-[:PREMISE   {step_index}]->(:Chain)
    (:Chain)    -[:CONCLUSION{step_index, probability}]->(:Knowledge)
    (:Resource) -[:ATTACHED_TO {role, step_index}]->(:Knowledge|:Chain)

Knowledge nodes are keyed by ``knowledge_vid`` = ``knowledge_id@version``.
"""

from __future__ import annotations

from datetime import datetime

import neo4j

from libs.storage_v2.graph_store import GraphStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    ResourceAttachment,
    ScoredKnowledge,
    Subgraph,
)


def _knowledge_vid(knowledge_id: str, version: int) -> str:
    return f"{knowledge_id}@{version}"


class Neo4jGraphStore(GraphStore):
    """Graph topology backend backed by Neo4j (async driver)."""

    def __init__(self, driver: neo4j.AsyncDriver, database: str = "neo4j") -> None:
        self._driver = driver
        self._db = database

    # ── Schema setup ──

    async def initialize_schema(self) -> None:
        async with self._driver.session(database=self._db) as session:
            await session.run(
                "CREATE CONSTRAINT knowledge_vid IF NOT EXISTS "
                "FOR (k:Knowledge) REQUIRE k.knowledge_vid IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT chain_id IF NOT EXISTS "
                "FOR (c:Chain) REQUIRE c.chain_id IS UNIQUE"
            )
            await session.run(
                "CREATE CONSTRAINT resource_id IF NOT EXISTS "
                "FOR (r:Resource) REQUIRE r.resource_id IS UNIQUE"
            )

    # ── Delete ──

    async def delete_package(self, package_id: str) -> None:
        dot_prefix = f"{package_id}."
        slash_prefix = f"{package_id}/"
        async with self._driver.session(database=self._db) as session:
            await session.run(
                "MATCH (ch:Chain) WHERE ch.chain_id STARTS WITH $prefix DETACH DELETE ch",
                prefix=dot_prefix,
            )
            await session.run(
                "MATCH (kn:Knowledge) WHERE kn.knowledge_vid STARTS WITH $p1 "
                "OR kn.knowledge_vid STARTS WITH $p2 DETACH DELETE kn",
                p1=slash_prefix,
                p2=dot_prefix,
            )
            await session.run(
                "MATCH (r:Resource) WHERE r.resource_id STARTS WITH $prefix DETACH DELETE r",
                prefix=dot_prefix,
            )

    # ── Write ──

    async def write_topology(self, knowledge_items: list[Knowledge], chains: list[Chain]) -> None:
        async with self._driver.session(database=self._db) as session:
            await session.execute_write(self._tx_write_topology, knowledge_items, chains)

    @staticmethod
    async def _tx_write_topology(
        tx: neo4j.AsyncManagedTransaction,
        knowledge_items: list[Knowledge],
        chains: list[Chain],
    ) -> None:
        # 1. MERGE knowledge nodes
        for kn in knowledge_items:
            vid = _knowledge_vid(kn.knowledge_id, kn.version)
            await tx.run(
                "MERGE (n:Knowledge {knowledge_vid: $vid}) "
                "SET n.knowledge_id = $kid, n.version = $ver, "
                "n.type = $type, n.prior = $prior, n.belief = $prior",
                vid=vid,
                kid=kn.knowledge_id,
                ver=kn.version,
                type=kn.type,
                prior=kn.prior,
            )

        # 2. MERGE chain nodes
        for ch in chains:
            await tx.run(
                "MERGE (n:Chain {chain_id: $id}) SET n.type = $type",
                id=ch.chain_id,
                type=ch.type,
            )

        # 3. Create PREMISE / CONCLUSION rels from chain steps
        for ch in chains:
            for step in ch.steps:
                for prem in step.premises:
                    pvid = _knowledge_vid(prem.knowledge_id, prem.version)
                    # Ensure premise stub exists
                    await tx.run(
                        "MERGE (n:Knowledge {knowledge_vid: $vid}) "
                        "ON CREATE SET n.knowledge_id = $kid, n.version = $ver, "
                        "n.type = 'claim', n.prior = 0.5, n.belief = 0.5",
                        vid=pvid,
                        kid=prem.knowledge_id,
                        ver=prem.version,
                    )
                    # Create PREMISE rel if not exists
                    await tx.run(
                        "MATCH (kn:Knowledge {knowledge_vid: $kvid}), "
                        "(ch:Chain {chain_id: $chid}) "
                        "WHERE NOT EXISTS { "
                        "  MATCH (kn)-[r:PREMISE]->(ch) WHERE r.step_index = $si "
                        "} "
                        "CREATE (kn)-[:PREMISE {step_index: $si}]->(ch)",
                        kvid=pvid,
                        chid=ch.chain_id,
                        si=step.step_index,
                    )

                conc = step.conclusion
                cvid = _knowledge_vid(conc.knowledge_id, conc.version)
                # Ensure conclusion stub exists
                await tx.run(
                    "MERGE (n:Knowledge {knowledge_vid: $vid}) "
                    "ON CREATE SET n.knowledge_id = $kid, n.version = $ver, "
                    "n.type = 'claim', n.prior = 0.5, n.belief = 0.5",
                    vid=cvid,
                    kid=conc.knowledge_id,
                    ver=conc.version,
                )
                # Create CONCLUSION rel if not exists
                await tx.run(
                    "MATCH (ch:Chain {chain_id: $chid}), "
                    "(kn:Knowledge {knowledge_vid: $kvid}) "
                    "WHERE NOT EXISTS { "
                    "  MATCH (ch)-[r:CONCLUSION]->(kn) WHERE r.step_index = $si "
                    "} "
                    "CREATE (ch)-[:CONCLUSION {step_index: $si, probability: 0.0}]->(kn)",
                    chid=ch.chain_id,
                    kvid=cvid,
                    si=step.step_index,
                )

    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
        async with self._driver.session(database=self._db) as session:
            for att in attachments:
                if att.target_type in ("module", "package"):
                    continue

                if att.target_type == "knowledge":
                    # Link to latest version
                    result = await session.run(
                        "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid "
                        "RETURN kn.knowledge_vid ORDER BY kn.version DESC LIMIT 1",
                        kid=att.target_id,
                    )
                    record = await result.single()
                    if record is None:
                        continue
                    dest_label = "Knowledge"
                    dest_key = "knowledge_vid"
                    dest_id = record[0]
                    step_idx = -1
                elif att.target_type == "chain":
                    dest_label = "Chain"
                    dest_key = "chain_id"
                    dest_id = att.target_id
                    step_idx = -1
                elif att.target_type == "chain_step":
                    parts = att.target_id.rsplit(":", 1)
                    dest_label = "Chain"
                    dest_key = "chain_id"
                    dest_id = parts[0]
                    step_idx = int(parts[1])
                else:
                    continue

                await session.run(
                    "MERGE (r:Resource {resource_id: $rid})",
                    rid=att.resource_id,
                )
                await session.run(
                    f"MATCH (r:Resource {{resource_id: $rid}}), "
                    f"(t:{dest_label} {{{dest_key}: $tid}}) "
                    f"WHERE NOT EXISTS {{ "
                    f"  MATCH (r)-[a:ATTACHED_TO]->(t) "
                    f"  WHERE a.role = $role AND a.step_index = $si "
                    f"}} "
                    f"CREATE (r)-[:ATTACHED_TO {{role: $role, step_index: $si}}]->(t)",
                    rid=att.resource_id,
                    tid=dest_id,
                    role=att.role,
                    si=step_idx,
                )

    async def update_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        async with self._driver.session(database=self._db) as session:
            for snap in snapshots:
                vid = _knowledge_vid(snap.knowledge_id, snap.version)
                await session.run(
                    "MATCH (kn:Knowledge {knowledge_vid: $vid}) SET kn.belief = $belief",
                    vid=vid,
                    belief=snap.belief,
                )

    async def update_probability(self, chain_id: str, step_index: int, value: float) -> None:
        async with self._driver.session(database=self._db) as session:
            await session.run(
                "MATCH (ch:Chain {chain_id: $chid})-[r:CONCLUSION]->(:Knowledge) "
                "WHERE r.step_index = $si SET r.probability = $val",
                chid=chain_id,
                si=step_index,
                val=value,
            )

    # ── Query ──

    async def get_neighbors(
        self,
        knowledge_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        async with self._driver.session(database=self._db) as session:
            return await session.execute_read(
                self._tx_get_neighbors, knowledge_id, direction, chain_types, max_hops
            )

    @staticmethod
    async def _tx_get_neighbors(
        tx: neo4j.AsyncManagedTransaction,
        knowledge_id: str,
        direction: str,
        chain_types: list[str] | None,
        max_hops: int,
    ) -> Subgraph:
        # Verify seed exists
        res = await tx.run(
            "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid RETURN kn.knowledge_id LIMIT 1",
            kid=knowledge_id,
        )
        if await res.single() is None:
            return Subgraph()

        all_knowledge_ids: set[str] = set()
        all_chain_ids: set[str] = set()
        frontier: set[str] = {knowledge_id}
        visited: set[str] = {knowledge_id}

        for _ in range(max_hops):
            if not frontier:
                break
            new_chains: set[str] = set()

            for kid in frontier:
                if direction in ("downstream", "both"):
                    result = await tx.run(
                        "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                        "WHERE kn.knowledge_id = $kid RETURN ch.chain_id, ch.type",
                        kid=kid,
                    )
                    async for rec in result:
                        if chain_types is None or rec["ch.type"] in chain_types:
                            new_chains.add(rec["ch.chain_id"])

                if direction in ("upstream", "both"):
                    result = await tx.run(
                        "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                        "WHERE kn.knowledge_id = $kid RETURN ch.chain_id, ch.type",
                        kid=kid,
                    )
                    async for rec in result:
                        if chain_types is None or rec["ch.type"] in chain_types:
                            new_chains.add(rec["ch.chain_id"])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                if direction in ("downstream", "both"):
                    result = await tx.run(
                        "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                        "RETURN DISTINCT kn.knowledge_id",
                        chid=ch_id,
                    )
                    async for rec in result:
                        found = rec["kn.knowledge_id"]
                        if found not in visited:
                            next_frontier.add(found)

                if direction in ("upstream", "both"):
                    result = await tx.run(
                        "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                        "RETURN DISTINCT kn.knowledge_id",
                        chid=ch_id,
                    )
                    async for rec in result:
                        found = rec["kn.knowledge_id"]
                        if found not in visited:
                            next_frontier.add(found)

            all_knowledge_ids.update(next_frontier)
            visited.update(next_frontier)
            frontier = next_frontier

        return Subgraph(knowledge_ids=all_knowledge_ids, chain_ids=all_chain_ids)

    async def get_subgraph(self, knowledge_id: str, max_knowledge: int = 500) -> Subgraph:
        async with self._driver.session(database=self._db) as session:
            return await session.execute_read(self._tx_get_subgraph, knowledge_id, max_knowledge)

    @staticmethod
    async def _tx_get_subgraph(
        tx: neo4j.AsyncManagedTransaction,
        knowledge_id: str,
        max_knowledge: int,
    ) -> Subgraph:
        res = await tx.run(
            "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid RETURN kn.knowledge_id LIMIT 1",
            kid=knowledge_id,
        )
        if await res.single() is None:
            return Subgraph()

        all_knowledge_ids: set[str] = {knowledge_id}
        all_chain_ids: set[str] = set()
        frontier: set[str] = {knowledge_id}

        while frontier and len(all_knowledge_ids) < max_knowledge:
            new_chains: set[str] = set()
            for kid in frontier:
                result = await tx.run(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    kid=kid,
                )
                async for rec in result:
                    new_chains.add(rec["ch.chain_id"])

                result = await tx.run(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    kid=kid,
                )
                async for rec in result:
                    new_chains.add(rec["ch.chain_id"])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                result = await tx.run(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                    "RETURN DISTINCT kn.knowledge_id",
                    chid=ch_id,
                )
                async for rec in result:
                    found = rec["kn.knowledge_id"]
                    if found not in all_knowledge_ids:
                        next_frontier.add(found)

                result = await tx.run(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT kn.knowledge_id",
                    chid=ch_id,
                )
                async for rec in result:
                    found = rec["kn.knowledge_id"]
                    if found not in all_knowledge_ids:
                        next_frontier.add(found)

            remaining = max_knowledge - len(all_knowledge_ids)
            if len(next_frontier) > remaining:
                next_frontier = set(list(next_frontier)[:remaining])

            all_knowledge_ids.update(next_frontier)
            frontier = next_frontier

        return Subgraph(knowledge_ids=all_knowledge_ids, chain_ids=all_chain_ids)

    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredKnowledge]:
        if not seed_ids:
            return []
        async with self._driver.session(database=self._db) as session:
            return await session.execute_read(self._tx_search_topology, seed_ids, hops)

    @staticmethod
    async def _tx_search_topology(
        tx: neo4j.AsyncManagedTransaction,
        seed_ids: list[str],
        hops: int,
    ) -> list[ScoredKnowledge]:
        seed_set = set(seed_ids)
        discovered: dict[str, int] = {}
        frontier: set[str] = set(seed_ids)
        visited: set[str] = set(seed_ids)

        for hop in range(hops):
            if not frontier:
                break

            new_chains: set[str] = set()
            for kid in frontier:
                result = await tx.run(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    kid=kid,
                )
                async for rec in result:
                    new_chains.add(rec["ch.chain_id"])

                result = await tx.run(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(kn:Knowledge) "
                    "WHERE kn.knowledge_id = $kid RETURN ch.chain_id",
                    kid=kid,
                )
                async for rec in result:
                    new_chains.add(rec["ch.chain_id"])

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                result = await tx.run(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(kn:Knowledge) "
                    "RETURN DISTINCT kn.knowledge_id",
                    chid=ch_id,
                )
                async for rec in result:
                    found = rec["kn.knowledge_id"]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

                result = await tx.run(
                    "MATCH (kn:Knowledge)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN DISTINCT kn.knowledge_id",
                    chid=ch_id,
                )
                async for rec in result:
                    found = rec["kn.knowledge_id"]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

            visited.update(next_frontier)
            frontier = next_frontier

        # Build scored results
        results: list[ScoredKnowledge] = []
        for kid, hop_dist in discovered.items():
            if kid in seed_set:
                continue

            res = await tx.run(
                "MATCH (kn:Knowledge) WHERE kn.knowledge_id = $kid "
                "RETURN kn.version, kn.type, kn.prior "
                "ORDER BY kn.version DESC LIMIT 1",
                kid=kid,
            )
            record = await res.single()
            if record is None:
                continue

            knowledge = Knowledge(
                knowledge_id=kid,
                version=record["kn.version"],
                type=record["kn.type"],
                content="",
                prior=record["kn.prior"],
                source_package_id="",
                source_module_id="",
                created_at=datetime(2026, 1, 1),
            )
            results.append(ScoredKnowledge(knowledge=knowledge, score=1.0 / (hop_dist + 2)))

        results.sort(key=lambda sk: sk.score, reverse=True)
        return results

    # ── Lifecycle ──

    async def close(self) -> None:
        await self._driver.close()
