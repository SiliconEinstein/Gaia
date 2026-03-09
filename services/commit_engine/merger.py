"""Merger: applies commit operations to the actual storage backends.

Triple-write pattern: LanceDB (nodes) + Neo4j (hyperedges) + Vector (embeddings).
Neo4j is optional — if unavailable, graph operations are silently skipped.
"""

from __future__ import annotations

from libs.models import (
    BPResults,
    Commit,
    HyperEdge,
    MergeResult,
    Node,
    AddEdgeOp,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
    NodeRef,
)
from libs.storage.manager import StorageManager


class Merger:
    """Applies a commit's operations to storage."""

    def __init__(self, storage: StorageManager) -> None:
        self._storage = storage

    async def merge(self, commit: Commit) -> MergeResult:
        """Apply all operations in *commit* to storage.

        Returns a :class:`MergeResult` summarising what was created/modified.
        """
        new_node_ids: list[int] = []
        new_edge_ids: list[int] = []

        try:
            for op in commit.operations:
                if isinstance(op, AddEdgeOp):
                    nids, eid = await self._apply_add_edge(op)
                    new_node_ids.extend(nids)
                    new_edge_ids.append(eid)
                elif isinstance(op, ModifyNodeOp):
                    await self._apply_modify_node(op)
                elif isinstance(op, ModifyEdgeOp):
                    await self._apply_modify_edge(op)

            # Persist pipeline outputs from review
            bp_results_model: BPResults | None = None
            beliefs_persisted: dict[str, float] = {}
            abstraction_edges_created: list[str] = []

            review_data = commit.review_results
            if isinstance(review_data, dict) and "overall_verdict" in review_data:
                # It's a DetailedReviewResult
                bp_data = review_data.get("bp_results")
                if bp_data is not None:
                    bp_results_model = BPResults(**bp_data)
                    for node_id_str, belief in bp_data.get("belief_updates", {}).items():
                        node_id = int(node_id_str)
                        await self._storage.lance.update_node(node_id, belief=belief)
                        beliefs_persisted[node_id_str] = belief

            return MergeResult(
                success=True,
                new_node_ids=new_node_ids,
                new_edge_ids=new_edge_ids,
                bp_results=bp_results_model,
                abstraction_edges_created=abstraction_edges_created,
                beliefs_persisted=beliefs_persisted,
            )
        except Exception as e:
            return MergeResult(success=False, errors=[str(e)])

    # ------------------------------------------------------------------
    # Operation handlers
    # ------------------------------------------------------------------

    async def _apply_add_edge(self, op: AddEdgeOp) -> tuple[list[int], int]:
        """Create new nodes, then wire them into a new hyperedge."""
        new_node_ids: list[int] = []
        premise_ids: list[int] = []
        conclusion_ids: list[int] = []

        # Process premise members
        for item in op.premises:
            if isinstance(item, NewNode):
                nid = await self._create_node(item)
                new_node_ids.append(nid)
                premise_ids.append(nid)
            elif isinstance(item, NodeRef):
                premise_ids.append(item.node_id)

        # Process conclusion members
        for item in op.conclusions:
            if isinstance(item, NewNode):
                nid = await self._create_node(item)
                new_node_ids.append(nid)
                conclusion_ids.append(nid)
            elif isinstance(item, NodeRef):
                conclusion_ids.append(item.node_id)

        # Create the hyperedge
        eid = await self._storage.ids.alloc_hyperedge_id()
        edge = HyperEdge(
            id=eid,
            type=op.type,
            premises=premise_ids,
            conclusions=conclusion_ids,
            reasoning=op.reasoning,
        )
        if self._storage.graph:
            await self._storage.graph.create_hyperedge(edge)

        return new_node_ids, eid

    async def _create_node(self, new_node: NewNode) -> int:
        """Allocate an ID, persist a new node to LanceDB, and return its ID."""
        nid = await self._storage.ids.alloc_node_id()
        node = Node(
            id=nid,
            type="paper-extract",
            content=new_node.content,
            keywords=new_node.keywords,
            extra=new_node.extra,
        )
        await self._storage.lance.save_nodes([node])
        return nid

    async def _apply_modify_node(self, op: ModifyNodeOp) -> None:
        """Update node properties in LanceDB."""
        await self._storage.lance.update_node(op.node_id, **op.changes)

    async def _apply_modify_edge(self, op: ModifyEdgeOp) -> None:
        """Update edge properties in Neo4j (if available)."""
        if self._storage.graph:
            await self._storage.graph.update_hyperedge(op.edge_id, **op.changes)
