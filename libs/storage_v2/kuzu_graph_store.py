"""KuzuGraphStore — embedded graph backend using Kùzu."""

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
    (
        "CREATE NODE TABLE IF NOT EXISTS Closure("
        "closure_id STRING, version INT64, type STRING, "
        "prior DOUBLE, belief DOUBLE, "
        "PRIMARY KEY(closure_id))"
    ),
    (
        "CREATE NODE TABLE IF NOT EXISTS Chain("
        "chain_id STRING, type STRING, probability DOUBLE, "
        "PRIMARY KEY(chain_id))"
    ),
    "CREATE REL TABLE IF NOT EXISTS PREMISE(FROM Closure TO Chain, step_index INT64)",
    "CREATE REL TABLE IF NOT EXISTS CONCLUSION(FROM Chain TO Closure, step_index INT64)",
    (
        "CREATE NODE TABLE IF NOT EXISTS Resource("
        "resource_id STRING, type STRING, format STRING, "
        "PRIMARY KEY(resource_id))"
    ),
    (
        "CREATE REL TABLE GROUP IF NOT EXISTS ATTACHED_TO("
        "FROM Resource TO Closure, FROM Resource TO Chain, role STRING)"
    ),
]


class KuzuGraphStore(GraphStore):
    """Graph topology backend backed by an embedded Kùzu database.

    Kùzu's Python API is synchronous, so all public methods offload work to
    a thread via ``asyncio.to_thread``.
    """

    def __init__(self, db_path: Path | str) -> None:
        self._db = kuzu.Database(str(db_path))
        self._conn = kuzu.Connection(self._db)

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

    # ── Write (stubs) ──

    async def write_topology(self, closures: list[Closure], chains: list[Chain]) -> None:
        """Upsert closures and chains, then wire PREMISE/CONCLUSION relationships.

        Steps:
          1. MERGE each Closure node (keyed by closure_id).
          2. MERGE each Chain node (keyed by chain_id).
          3. For every ChainStep, ensure referenced closure nodes exist (MERGE),
             then create PREMISE and CONCLUSION relationships if absent.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._write_topology_sync, closures, chains))

    def _write_topology_sync(self, closures: list[Closure], chains: list[Chain]) -> None:
        """Synchronous implementation of write_topology."""
        # 1. MERGE closure nodes
        for c in closures:
            self._conn.execute(
                "MERGE (n:Closure {closure_id: $id}) "
                "SET n.version = $ver, n.type = $type, n.prior = $prior, n.belief = $prior",
                {"id": c.closure_id, "ver": c.version, "type": c.type, "prior": c.prior},
            )

        # 2. MERGE chain nodes
        for ch in chains:
            self._conn.execute(
                "MERGE (n:Chain {chain_id: $id}) SET n.type = $type, n.probability = $prob",
                {"id": ch.chain_id, "type": ch.type, "prob": 0.0},
            )

        # 3. Create relationships from chain steps
        for ch in chains:
            for step in ch.steps:
                # Ensure premise closure nodes exist, then create PREMISE rels
                for prem in step.premises:
                    self._merge_closure_stub(prem.closure_id, prem.version)
                    self._ensure_rel(
                        "PREMISE",
                        "Closure",
                        "closure_id",
                        prem.closure_id,
                        "Chain",
                        "chain_id",
                        ch.chain_id,
                        step.step_index,
                    )

                # Ensure conclusion closure node exists, then create CONCLUSION rel
                conc = step.conclusion
                self._merge_closure_stub(conc.closure_id, conc.version)
                self._ensure_rel(
                    "CONCLUSION",
                    "Chain",
                    "chain_id",
                    ch.chain_id,
                    "Closure",
                    "closure_id",
                    conc.closure_id,
                    step.step_index,
                )

    def _merge_closure_stub(self, closure_id: str, version: int) -> None:
        """MERGE a Closure node with minimal defaults (no-op if it already exists)."""
        self._conn.execute(
            "MERGE (n:Closure {closure_id: $id}) "
            "ON CREATE SET n.version = $ver, n.type = 'claim', n.prior = 0.5, n.belief = 0.5",
            {"id": closure_id, "ver": version},
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
        """Create a relationship if it does not already exist.

        Kuzu does not support MERGE for relationships, so we check existence first.
        """
        check_q = (
            f"MATCH (a:{from_label} {{{from_key}: $fv}})"
            f"-[r:{rel_type}]->"
            f"(b:{to_label} {{{to_key}: $tv}}) "
            f"WHERE r.step_index = $si RETURN COUNT(r)"
        )
        result = self._conn.execute(check_q, {"fv": from_val, "tv": to_val, "si": step_index})
        row = result.get_next()
        if row[0] == 0:
            create_q = (
                f"MATCH (a:{from_label} {{{from_key}: $fv}}), "
                f"(b:{to_label} {{{to_key}: $tv}}) "
                f"CREATE (a)-[:{rel_type} {{step_index: $si}}]->(b)"
            )
            self._conn.execute(create_q, {"fv": from_val, "tv": to_val, "si": step_index})

    async def write_resource_links(self, attachments: list[ResourceAttachment]) -> None:
        """Write Resource nodes and ATTACHED_TO relationships.

        Only ``closure``, ``chain``, and ``chain_step`` target types map to
        graph nodes.  For ``chain_step``, the chain_id is extracted from the
        target_id (format ``chain_id:step_index``) and the link points to the
        parent Chain node.  ``module`` and ``package`` targets are skipped.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._write_resource_links_sync, attachments))

    def _write_resource_links_sync(self, attachments: list[ResourceAttachment]) -> None:
        """Synchronous implementation of write_resource_links."""
        for att in attachments:
            if att.target_type in ("module", "package"):
                continue

            # Determine destination label and id
            if att.target_type == "closure":
                dest_label = "Closure"
                dest_key = "closure_id"
                dest_id = att.target_id
            elif att.target_type == "chain":
                dest_label = "Chain"
                dest_key = "chain_id"
                dest_id = att.target_id
            elif att.target_type == "chain_step":
                # Extract chain_id from "chain_id:step_index"
                dest_label = "Chain"
                dest_key = "chain_id"
                dest_id = att.target_id.rsplit(":", 1)[0]
            else:
                continue

            # MERGE the Resource node
            self._conn.execute(
                "MERGE (r:Resource {resource_id: $rid})",
                {"rid": att.resource_id},
            )

            # Check-then-create the ATTACHED_TO relationship
            check_q = (
                f"MATCH (r:Resource {{resource_id: $rid}})"
                f"-[a:ATTACHED_TO]->"
                f"(t:{dest_label} {{{dest_key}: $tid}}) "
                f"WHERE a.role = $role RETURN COUNT(a)"
            )
            result = self._conn.execute(
                check_q,
                {"rid": att.resource_id, "tid": dest_id, "role": att.role},
            )
            if result.get_next()[0] == 0:
                create_q = (
                    f"MATCH (r:Resource {{resource_id: $rid}}), "
                    f"(t:{dest_label} {{{dest_key}: $tid}}) "
                    f"CREATE (r)-[:ATTACHED_TO {{role: $role}}]->(t)"
                )
                self._conn.execute(
                    create_q,
                    {"rid": att.resource_id, "tid": dest_id, "role": att.role},
                )

    async def update_beliefs(self, snapshots: list[BeliefSnapshot]) -> None:
        """Set belief values on Closure nodes.

        Non-existent closures are silently ignored.
        """
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, partial(self._update_beliefs_sync, snapshots))

    def _update_beliefs_sync(self, snapshots: list[BeliefSnapshot]) -> None:
        """Synchronous implementation of update_beliefs."""
        for snap in snapshots:
            self._conn.execute(
                "MATCH (cl:Closure {closure_id: $cid}) SET cl.belief = $belief",
                {"cid": snap.closure_id, "belief": snap.belief},
            )

    async def update_probability(self, chain_id: str, step_index: int, value: float) -> None:
        """Set probability on a Chain node."""
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            partial(
                self._conn.execute,
                "MATCH (ch:Chain {chain_id: $chid}) SET ch.probability = $val",
                {"chid": chain_id, "val": value},
            ),
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

        One "knowledge hop" = Closure → Chain → Closure (two graph hops).
        ``direction`` controls which relationships to follow:
          - ``"downstream"``: closure is a premise (PREMISE edge out), then
            follow CONCLUSION edges to find resulting closures.
          - ``"upstream"``: closure is a conclusion (CONCLUSION edge in), then
            follow PREMISE edges back to find premise closures.
          - ``"both"``: both directions.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self._get_neighbors_sync,
                closure_id,
                direction,
                chain_types,
                max_hops,
            ),
        )

    def _get_neighbors_sync(
        self,
        closure_id: str,
        direction: str,
        chain_types: list[str] | None,
        max_hops: int,
    ) -> Subgraph:
        """Synchronous BFS implementation for get_neighbors."""
        # Verify seed exists
        result = self._conn.execute(
            "MATCH (c:Closure {closure_id: $id}) RETURN c.closure_id",
            {"id": closure_id},
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

            # Step A: from frontier closures, find connected chains
            for cid in frontier:
                if direction in ("downstream", "both"):
                    # Closure -[:PREMISE]-> Chain
                    res = self._conn.execute(
                        "MATCH (c:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) "
                        "RETURN ch.chain_id, ch.type",
                        {"cid": cid},
                    )
                    while res.has_next():
                        row = res.get_next()
                        ch_id, ch_type = row[0], row[1]
                        if chain_types is None or ch_type in chain_types:
                            new_chains.add(ch_id)

                if direction in ("upstream", "both"):
                    # Chain -[:CONCLUSION]-> Closure  (closure is the conclusion)
                    res = self._conn.execute(
                        "MATCH (ch:Chain)-[:CONCLUSION]->(c:Closure {closure_id: $cid}) "
                        "RETURN ch.chain_id, ch.type",
                        {"cid": cid},
                    )
                    while res.has_next():
                        row = res.get_next()
                        ch_id, ch_type = row[0], row[1]
                        if chain_types is None or ch_type in chain_types:
                            new_chains.add(ch_id)

            all_chain_ids.update(new_chains)

            # Step B: from discovered chains, find closures on the other side
            next_frontier: set[str] = set()
            for ch_id in new_chains:
                if direction in ("downstream", "both"):
                    # Chain -[:CONCLUSION]-> Closure
                    res = self._conn.execute(
                        "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(c:Closure) "
                        "RETURN c.closure_id",
                        {"chid": ch_id},
                    )
                    while res.has_next():
                        found = res.get_next()[0]
                        if found not in visited_closures:
                            next_frontier.add(found)

                if direction in ("upstream", "both"):
                    # Closure -[:PREMISE]-> Chain
                    res = self._conn.execute(
                        "MATCH (c:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                        "RETURN c.closure_id",
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
        """BFS from root closure in both directions, up to max_closures.

        The seed closure is included in the result. Expands until no more
        nodes are reachable or the closure count reaches ``max_closures``.
        """
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(self._get_subgraph_sync, closure_id, max_closures),
        )

    def _get_subgraph_sync(self, closure_id: str, max_closures: int) -> Subgraph:
        """Synchronous BFS implementation for get_subgraph."""
        # Verify seed exists
        result = self._conn.execute(
            "MATCH (c:Closure {closure_id: $id}) RETURN c.closure_id",
            {"id": closure_id},
        )
        if not result.has_next():
            return Subgraph()

        all_closure_ids: set[str] = {closure_id}
        all_chain_ids: set[str] = set()
        frontier: set[str] = {closure_id}

        while frontier and len(all_closure_ids) < max_closures:
            new_chains: set[str] = set()

            for cid in frontier:
                # Downstream: Closure -[:PREMISE]-> Chain
                res = self._conn.execute(
                    "MATCH (c:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) "
                    "RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                # Upstream: Chain -[:CONCLUSION]-> Closure
                res = self._conn.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(c:Closure {closure_id: $cid}) "
                    "RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            all_chain_ids.update(new_chains)

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                # Conclusions
                res = self._conn.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(c:Closure) "
                    "RETURN c.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_closure_ids:
                        next_frontier.add(found)

                # Premises
                res = self._conn.execute(
                    "MATCH (c:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN c.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in all_closure_ids:
                        next_frontier.add(found)

            # Respect max_closures limit
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
        return await loop.run_in_executor(None, partial(self._search_topology_sync, seed_ids, hops))

    def _search_topology_sync(self, seed_ids: list[str], hops: int) -> list[ScoredClosure]:
        """Synchronous BFS implementation for search_topology."""
        if not seed_ids:
            return []

        seed_set = set(seed_ids)
        # Map closure_id -> best (lowest) hop distance
        discovered: dict[str, int] = {}
        frontier: set[str] = set(seed_ids)
        visited: set[str] = set(seed_ids)

        for hop in range(hops):
            if not frontier:
                break

            new_chains: set[str] = set()
            for cid in frontier:
                # Both directions
                res = self._conn.execute(
                    "MATCH (c:Closure {closure_id: $cid})-[:PREMISE]->(ch:Chain) "
                    "RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

                res = self._conn.execute(
                    "MATCH (ch:Chain)-[:CONCLUSION]->(c:Closure {closure_id: $cid}) "
                    "RETURN ch.chain_id",
                    {"cid": cid},
                )
                while res.has_next():
                    new_chains.add(res.get_next()[0])

            next_frontier: set[str] = set()
            for ch_id in new_chains:
                res = self._conn.execute(
                    "MATCH (ch:Chain {chain_id: $chid})-[:CONCLUSION]->(c:Closure) "
                    "RETURN c.closure_id",
                    {"chid": ch_id},
                )
                while res.has_next():
                    found = res.get_next()[0]
                    if found not in visited:
                        next_frontier.add(found)
                        if found not in discovered:
                            discovered[found] = hop

                res = self._conn.execute(
                    "MATCH (c:Closure)-[:PREMISE]->(ch:Chain {chain_id: $chid}) "
                    "RETURN c.closure_id",
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

            # Fetch node properties from graph
            res = self._conn.execute(
                "MATCH (c:Closure {closure_id: $cid}) RETURN c.version, c.type, c.prior",
                {"cid": cid},
            )
            if not res.has_next():
                continue
            row = res.get_next()
            version, ctype, prior = row[0], row[1], row[2]

            closure = Closure(
                closure_id=cid,
                version=version,
                type=ctype,
                content="",
                prior=prior,
                source_package_id="",
                source_module_id="",
                created_at=datetime(2026, 1, 1),
            )
            score = 1.0 / (hop_dist + 2)
            results.append(ScoredClosure(closure=closure, score=score))

        # Sort by score descending
        results.sort(key=lambda sc: sc.score, reverse=True)
        return results

    # ── Lifecycle ──

    async def close(self) -> None:
        """Release the Kùzu connection (idempotent)."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None
