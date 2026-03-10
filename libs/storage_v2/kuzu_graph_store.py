"""KuzuGraphStore — embedded graph backend using Kùzu."""

import asyncio
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
        for snap in snapshots:
            await loop.run_in_executor(
                None,
                partial(
                    self._conn.execute,
                    "MATCH (cl:Closure {closure_id: $cid}) SET cl.belief = $belief",
                    {"cid": snap.closure_id, "belief": snap.belief},
                ),
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

    # ── Query (stubs) ──

    async def get_neighbors(
        self,
        closure_id: str,
        direction: str = "both",
        chain_types: list[str] | None = None,
        max_hops: int = 1,
    ) -> Subgraph:
        raise NotImplementedError

    async def get_subgraph(self, closure_id: str, max_closures: int = 500) -> Subgraph:
        raise NotImplementedError

    async def search_topology(self, seed_ids: list[str], hops: int = 1) -> list[ScoredClosure]:
        raise NotImplementedError

    # ── Lifecycle ──

    async def close(self) -> None:
        """Release the Kùzu connection."""
        self._conn.close()
