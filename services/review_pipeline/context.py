"""PipelineContext — shared state passed between pipeline operators."""

from __future__ import annotations

from pydantic import BaseModel

from libs.models import (
    AddEdgeOp,
    CommitRequest,
    ModifyEdgeOp,
    ModifyNodeOp,
    NewNode,
)


class NewNodeInfo(BaseModel):
    """Metadata about a new node extracted from a commit operation."""

    content: str
    keywords: list[str] = []
    extra: dict = {}
    op_index: int
    position: str  # e.g. "premises[0]", "conclusions[1]"


class AbstractionTree(BaseModel):
    """A discovered relationship between a new node and an existing node."""

    source_node_index: int  # index into PipelineContext.new_nodes
    target_node_id: int
    relation: str  # "equivalent", "partial_overlap", "subsumes", "subsumed_by"
    verified: bool = False
    reasoning: str = ""
    source_content: str = ""  # content of the new node (anchor)
    target_content: str = ""  # content of the existing node (candidate)


class PipelineContext:
    """Shared mutable state flowing through the review pipeline."""

    def __init__(self) -> None:
        self.request: CommitRequest | None = None
        self.new_nodes: list[NewNodeInfo] = []
        self.affected_node_ids: list[int] = []
        self.embeddings: dict[int, list[float]] = {}  # new_node index -> vector
        self.nn_results: dict[int, list[tuple[int, float]]] = {}  # index -> [(node_id, sim)]
        self.cc_abstraction_trees: list[AbstractionTree] = []
        self.cp_abstraction_trees: list[AbstractionTree] = []
        self.verified_trees: list[AbstractionTree] = []
        self.bp_results: dict[int, float] = {}  # node_id -> belief
        self.cancelled: bool = False
        self.step_results: dict[str, dict] = {}  # step_name -> metadata

    @classmethod
    def from_commit_request(cls, request: CommitRequest) -> PipelineContext:
        ctx = cls()
        ctx.request = request
        for op_idx, op in enumerate(request.operations):
            if isinstance(op, AddEdgeOp):
                for i, item in enumerate(op.premises):
                    if isinstance(item, NewNode):
                        ctx.new_nodes.append(
                            NewNodeInfo(
                                content=item.content
                                if isinstance(item.content, str)
                                else str(item.content),
                                keywords=item.keywords,
                                extra=item.extra,
                                op_index=op_idx,
                                position=f"premises[{i}]",
                            )
                        )
                for i, item in enumerate(op.conclusions):
                    if isinstance(item, NewNode):
                        ctx.new_nodes.append(
                            NewNodeInfo(
                                content=item.content
                                if isinstance(item.content, str)
                                else str(item.content),
                                keywords=item.keywords,
                                extra=item.extra,
                                op_index=op_idx,
                                position=f"conclusions[{i}]",
                            )
                        )
            elif isinstance(op, ModifyNodeOp):
                ctx.affected_node_ids.append(op.node_id)
            elif isinstance(op, ModifyEdgeOp):
                ctx.affected_node_ids.append(op.edge_id)
        return ctx
