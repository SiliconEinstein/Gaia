"""LanceDB content store — source of truth for all entities.

Implements :class:`ContentStore` with 8 LanceDB tables:
knowledge_nodes, factor_nodes, canonical_bindings, prior_records,
factor_param_records, param_sources, belief_states, node_embeddings.
"""

from __future__ import annotations

import asyncio
from datetime import datetime
from functools import partial
from typing import Any

import lancedb
import pyarrow as pa

from gaia.models.belief_state import BeliefState
from gaia.models.binding import CanonicalBinding
from gaia.models.graph_ir import FactorNode, KnowledgeNode
from gaia.models.parameterization import (
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
)
from gaia.libs.storage.base import ContentStore

# ---------------------------------------------------------------------------
# Table schemas (PyArrow)
# ---------------------------------------------------------------------------

_KNOWLEDGE_NODES_SCHEMA = pa.schema(
    [
        ("id", pa.string()),
        ("type", pa.string()),
        ("content", pa.string()),
        ("parameters_json", pa.string()),
        ("source_refs_json", pa.string()),
        ("metadata_json", pa.string()),
        ("provenance_json", pa.string()),
        ("representative_lcn_json", pa.string()),
        ("member_local_nodes_json", pa.string()),
    ]
)

_FACTOR_NODES_SCHEMA = pa.schema(
    [
        ("factor_id", pa.string()),
        ("scope", pa.string()),
        ("category", pa.string()),
        ("stage", pa.string()),
        ("reasoning_type", pa.string()),
        ("premises_json", pa.string()),
        ("conclusion", pa.string()),
        ("steps_json", pa.string()),
        ("weak_points_json", pa.string()),
        ("subgraph_json", pa.string()),
        ("source_ref_json", pa.string()),
        ("metadata_json", pa.string()),
    ]
)

_CANONICAL_BINDINGS_SCHEMA = pa.schema(
    [
        ("local_canonical_id", pa.string()),
        ("global_canonical_id", pa.string()),
        ("package_id", pa.string()),
        ("version", pa.string()),
        ("decision", pa.string()),
        ("reason", pa.string()),
    ]
)

_PRIOR_RECORDS_SCHEMA = pa.schema(
    [
        ("gcn_id", pa.string()),
        ("value", pa.float64()),
        ("source_id", pa.string()),
        ("created_at", pa.string()),
    ]
)

_FACTOR_PARAM_RECORDS_SCHEMA = pa.schema(
    [
        ("factor_id", pa.string()),
        ("probability", pa.float64()),
        ("source_id", pa.string()),
        ("created_at", pa.string()),
    ]
)

_PARAM_SOURCES_SCHEMA = pa.schema(
    [
        ("source_id", pa.string()),
        ("model", pa.string()),
        ("policy", pa.string()),
        ("config_json", pa.string()),
        ("created_at", pa.string()),
    ]
)

_BELIEF_STATES_SCHEMA = pa.schema(
    [
        ("bp_run_id", pa.string()),
        ("created_at", pa.string()),
        ("resolution_policy", pa.string()),
        ("prior_cutoff", pa.string()),
        ("beliefs_json", pa.string()),
        ("converged", pa.bool_()),
        ("iterations", pa.int64()),
        ("max_residual", pa.float64()),
    ]
)

# Embedding dimension is not fixed — inferred from first write.
# We define a helper to build the schema on demand.
_NODE_EMBEDDINGS_COLS = [
    ("gcn_id", pa.string()),
    ("content_preview", pa.string()),
    ("type", pa.string()),
]


def _node_embeddings_schema(dim: int) -> pa.Schema:
    return pa.schema(
        [
            ("gcn_id", pa.string()),
            ("vector", pa.list_(pa.float32(), dim)),
            ("content_preview", pa.string()),
            ("type", pa.string()),
        ]
    )


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def _json_or_none(obj: Any) -> str:
    """Serialize a Pydantic model or list of models to JSON string, or empty string."""
    if obj is None:
        return ""
    if isinstance(obj, list):
        import json

        return json.dumps([item.model_dump(mode="json") for item in obj])
    if isinstance(obj, dict):
        import json

        return json.dumps(obj)
    # Pydantic model
    return obj.model_dump_json()


def _from_json_or_none(json_str: str, model_cls: type | None = None, *, is_list: bool = False):
    """Deserialize JSON string back to model or None."""
    if not json_str:
        return [] if is_list else None
    import json

    if is_list and model_cls is not None:
        raw = json.loads(json_str)
        return [model_cls.model_validate(item) for item in raw]
    if model_cls is not None:
        return model_cls.model_validate_json(json_str)
    # dict
    return json.loads(json_str)


def _dt_to_iso(dt: datetime) -> str:
    return dt.isoformat()


def _iso_to_dt(s: str) -> datetime:
    return datetime.fromisoformat(s)


# ---------------------------------------------------------------------------
# LanceContentStore
# ---------------------------------------------------------------------------


class LanceContentStore(ContentStore):
    """LanceDB-backed content store implementing :class:`ContentStore`.

    Args:
        path: Filesystem path (local) or URI (remote) for the LanceDB database.
    """

    def __init__(self, path: str) -> None:
        self._path = path
        self._db: lancedb.DBConnection | None = None
        self._embedding_dim: int | None = None

    # ── helpers ──

    def _get_db(self) -> lancedb.DBConnection:
        if self._db is None:
            raise RuntimeError("Store not initialized. Call initialize() first.")
        return self._db

    def _table_exists(self, name: str) -> bool:
        page = self._get_db().list_tables()
        return name in page.tables

    async def _run_sync(self, fn, *args, **kwargs):
        """Run a synchronous function in the default executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, partial(fn, *args, **kwargs))

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Connect to LanceDB and create tables if they don't exist."""
        self._db = await self._run_sync(lancedb.connect, self._path)

        table_schemas = {
            "knowledge_nodes": _KNOWLEDGE_NODES_SCHEMA,
            "factor_nodes": _FACTOR_NODES_SCHEMA,
            "canonical_bindings": _CANONICAL_BINDINGS_SCHEMA,
            "prior_records": _PRIOR_RECORDS_SCHEMA,
            "factor_param_records": _FACTOR_PARAM_RECORDS_SCHEMA,
            "param_sources": _PARAM_SOURCES_SCHEMA,
            "belief_states": _BELIEF_STATES_SCHEMA,
        }

        for name, schema in table_schemas.items():
            if not self._table_exists(name):
                await self._run_sync(self._db.create_table, name, schema=schema)

        # node_embeddings created lazily on first write (needs vector dimension)

    async def clean_all(self) -> None:
        """Drop and recreate all tables."""
        db = self._get_db()
        for name in [
            "knowledge_nodes",
            "factor_nodes",
            "canonical_bindings",
            "prior_records",
            "factor_param_records",
            "param_sources",
            "belief_states",
            "node_embeddings",
        ]:
            if self._table_exists(name):
                await self._run_sync(db.drop_table, name)

        self._embedding_dim = None
        await self.initialize()

    # ── Write: Knowledge Nodes ──

    async def write_knowledge_nodes(self, nodes: list[KnowledgeNode]) -> None:
        if not nodes:
            return
        rows = [self._knowledge_node_to_row(n) for n in nodes]
        table = await self._run_sync(self._get_db().open_table, "knowledge_nodes")
        await self._run_sync(table.add, rows)

    @staticmethod
    def _knowledge_node_to_row(node: KnowledgeNode) -> dict[str, Any]:
        return {
            "id": node.id,
            "type": node.type.value,
            "content": node.content or "",
            "parameters_json": _json_or_none(node.parameters if node.parameters else None),
            "source_refs_json": _json_or_none(node.source_refs),
            "metadata_json": _json_or_none(node.metadata),
            "provenance_json": _json_or_none(node.provenance),
            "representative_lcn_json": _json_or_none(node.representative_lcn),
            "member_local_nodes_json": _json_or_none(node.member_local_nodes),
        }

    @staticmethod
    def _row_to_knowledge_node(row: dict[str, Any]) -> KnowledgeNode:
        from gaia.models.graph_ir import (
            LocalCanonicalRef,
            PackageRef,
            Parameter,
            SourceRef,
        )

        return KnowledgeNode(
            id=row["id"],
            type=row["type"],
            content=row["content"] if row["content"] else None,
            parameters=_from_json_or_none(row["parameters_json"], Parameter, is_list=True),
            source_refs=_from_json_or_none(row["source_refs_json"], SourceRef, is_list=True),
            metadata=_from_json_or_none(row["metadata_json"]) if row["metadata_json"] else None,
            provenance=_from_json_or_none(row["provenance_json"], PackageRef, is_list=True) or None,
            representative_lcn=_from_json_or_none(
                row["representative_lcn_json"], LocalCanonicalRef
            ),
            member_local_nodes=_from_json_or_none(
                row["member_local_nodes_json"], LocalCanonicalRef, is_list=True
            )
            or None,
        )

    # ── Read: Knowledge Nodes ──

    async def get_node(self, node_id: str) -> KnowledgeNode | None:
        table = await self._run_sync(self._get_db().open_table, "knowledge_nodes")
        df = await self._run_sync(
            lambda: table.search().where(f"id = '{node_id}'").limit(1).to_pandas()
        )
        if df.empty:
            return None
        return self._row_to_knowledge_node(df.iloc[0].to_dict())

    async def get_knowledge_nodes(self, prefix: str | None = None) -> list[KnowledgeNode]:
        table = await self._run_sync(self._get_db().open_table, "knowledge_nodes")
        if prefix:
            df = await self._run_sync(
                lambda: table.search().where(f"id LIKE '{prefix}%'").to_pandas()
            )
        else:
            df = await self._run_sync(table.to_pandas)
        return [self._row_to_knowledge_node(row.to_dict()) for _, row in df.iterrows()]

    # ── Write: Factor Nodes ──

    async def write_factor_nodes(self, factors: list[FactorNode]) -> None:
        if not factors:
            return
        rows = [self._factor_node_to_row(f) for f in factors]
        table = await self._run_sync(self._get_db().open_table, "factor_nodes")
        await self._run_sync(table.add, rows)

    @staticmethod
    def _factor_node_to_row(factor: FactorNode) -> dict[str, Any]:
        import json

        return {
            "factor_id": factor.factor_id,
            "scope": factor.scope,
            "category": factor.category.value,
            "stage": factor.stage.value,
            "reasoning_type": factor.reasoning_type.value if factor.reasoning_type else "",
            "premises_json": json.dumps(factor.premises),
            "conclusion": factor.conclusion or "",
            "steps_json": _json_or_none(factor.steps),
            "weak_points_json": json.dumps(factor.weak_points) if factor.weak_points else "",
            "subgraph_json": _json_or_none(factor.subgraph),
            "source_ref_json": _json_or_none(factor.source_ref),
            "metadata_json": _json_or_none(factor.metadata),
        }

    @staticmethod
    def _row_to_factor_node(row: dict[str, Any]) -> FactorNode:
        import json

        from gaia.models.graph_ir import SourceRef, Step

        steps = _from_json_or_none(row["steps_json"], Step, is_list=True) or None
        weak_points = json.loads(row["weak_points_json"]) if row["weak_points_json"] else None
        subgraph = _from_json_or_none(row["subgraph_json"], FactorNode, is_list=True) or None

        return FactorNode(
            factor_id=row["factor_id"],
            scope=row["scope"],
            category=row["category"],
            stage=row["stage"],
            reasoning_type=row["reasoning_type"] if row["reasoning_type"] else None,
            premises=json.loads(row["premises_json"]),
            conclusion=row["conclusion"] if row["conclusion"] else None,
            steps=steps,
            weak_points=weak_points,
            subgraph=subgraph,
            source_ref=_from_json_or_none(row["source_ref_json"], SourceRef),
            metadata=_from_json_or_none(row["metadata_json"]) if row["metadata_json"] else None,
        )

    # ── Read: Factor Nodes ──

    async def get_factor_nodes(self, scope: str | None = None) -> list[FactorNode]:
        table = await self._run_sync(self._get_db().open_table, "factor_nodes")
        if scope:
            df = await self._run_sync(
                lambda: table.search().where(f"scope = '{scope}'").to_pandas()
            )
        else:
            df = await self._run_sync(table.to_pandas)
        return [self._row_to_factor_node(row.to_dict()) for _, row in df.iterrows()]

    # ── Write: Bindings ──

    async def write_bindings(self, bindings: list[CanonicalBinding]) -> None:
        if not bindings:
            return
        rows = [
            {
                "local_canonical_id": b.local_canonical_id,
                "global_canonical_id": b.global_canonical_id,
                "package_id": b.package_id,
                "version": b.version,
                "decision": b.decision.value,
                "reason": b.reason,
            }
            for b in bindings
        ]
        table = await self._run_sync(self._get_db().open_table, "canonical_bindings")
        await self._run_sync(table.add, rows)

    # ── Read: Bindings ──

    async def get_bindings(self, package_id: str | None = None) -> list[CanonicalBinding]:
        table = await self._run_sync(self._get_db().open_table, "canonical_bindings")
        if package_id:
            df = await self._run_sync(
                lambda: table.search().where(f"package_id = '{package_id}'").to_pandas()
            )
        else:
            df = await self._run_sync(table.to_pandas)
        return [
            CanonicalBinding(
                local_canonical_id=row["local_canonical_id"],
                global_canonical_id=row["global_canonical_id"],
                package_id=row["package_id"],
                version=row["version"],
                decision=row["decision"],
                reason=row["reason"],
            )
            for _, row in df.iterrows()
        ]

    # ── Write: Prior Records ──

    async def write_prior_records(self, records: list[PriorRecord]) -> None:
        if not records:
            return
        rows = [
            {
                "gcn_id": r.gcn_id,
                "value": r.value,
                "source_id": r.source_id,
                "created_at": _dt_to_iso(r.created_at),
            }
            for r in records
        ]
        table = await self._run_sync(self._get_db().open_table, "prior_records")
        await self._run_sync(table.add, rows)

    # ── Read: Prior Records ──

    async def get_prior_records(self, gcn_id: str | None = None) -> list[PriorRecord]:
        table = await self._run_sync(self._get_db().open_table, "prior_records")
        if gcn_id:
            df = await self._run_sync(
                lambda: table.search().where(f"gcn_id = '{gcn_id}'").to_pandas()
            )
        else:
            df = await self._run_sync(table.to_pandas)
        return [
            PriorRecord(
                gcn_id=row["gcn_id"],
                value=row["value"],
                source_id=row["source_id"],
                created_at=_iso_to_dt(row["created_at"]),
            )
            for _, row in df.iterrows()
        ]

    # ── Write: Factor Param Records ──

    async def write_factor_param_records(self, records: list[FactorParamRecord]) -> None:
        if not records:
            return
        rows = [
            {
                "factor_id": r.factor_id,
                "probability": r.probability,
                "source_id": r.source_id,
                "created_at": _dt_to_iso(r.created_at),
            }
            for r in records
        ]
        table = await self._run_sync(self._get_db().open_table, "factor_param_records")
        await self._run_sync(table.add, rows)

    # ── Read: Factor Param Records ──

    async def get_factor_param_records(
        self, factor_id: str | None = None
    ) -> list[FactorParamRecord]:
        table = await self._run_sync(self._get_db().open_table, "factor_param_records")
        if factor_id:
            df = await self._run_sync(
                lambda: table.search().where(f"factor_id = '{factor_id}'").to_pandas()
            )
        else:
            df = await self._run_sync(table.to_pandas)
        return [
            FactorParamRecord(
                factor_id=row["factor_id"],
                probability=row["probability"],
                source_id=row["source_id"],
                created_at=_iso_to_dt(row["created_at"]),
            )
            for _, row in df.iterrows()
        ]

    # ── Write: Param Source ──

    async def write_param_source(self, source: ParameterizationSource) -> None:
        import json

        row = {
            "source_id": source.source_id,
            "model": source.model,
            "policy": source.policy or "",
            "config_json": json.dumps(source.config) if source.config else "",
            "created_at": _dt_to_iso(source.created_at),
        }
        table = await self._run_sync(self._get_db().open_table, "param_sources")
        await self._run_sync(table.add, [row])

    # ── Write: Belief State ──

    async def write_belief_state(self, state: BeliefState) -> None:
        import json

        row = {
            "bp_run_id": state.bp_run_id,
            "created_at": _dt_to_iso(state.created_at),
            "resolution_policy": state.resolution_policy,
            "prior_cutoff": _dt_to_iso(state.prior_cutoff),
            "beliefs_json": json.dumps(state.beliefs),
            "converged": state.converged,
            "iterations": state.iterations,
            "max_residual": state.max_residual,
        }
        table = await self._run_sync(self._get_db().open_table, "belief_states")
        await self._run_sync(table.add, [row])

    # ── Read: Belief States ──

    async def get_belief_states(self, limit: int = 10) -> list[BeliefState]:
        import json

        table = await self._run_sync(self._get_db().open_table, "belief_states")
        df = await self._run_sync(table.to_pandas)
        # Return most recent first, limited
        rows = df.head(limit)
        return [
            BeliefState(
                bp_run_id=row["bp_run_id"],
                created_at=_iso_to_dt(row["created_at"]),
                resolution_policy=row["resolution_policy"],
                prior_cutoff=_iso_to_dt(row["prior_cutoff"]),
                beliefs=json.loads(row["beliefs_json"]),
                converged=bool(row["converged"]),
                iterations=int(row["iterations"]),
                max_residual=float(row["max_residual"]),
            )
            for _, row in rows.iterrows()
        ]

    # ── Write: Node Embeddings ──

    async def write_node_embedding(self, gcn_id: str, vector: list[float], content: str) -> None:
        dim = len(vector)
        db = self._get_db()

        if not self._table_exists("node_embeddings"):
            self._embedding_dim = dim
            schema = _node_embeddings_schema(dim)
            await self._run_sync(db.create_table, "node_embeddings", schema=schema)

        row = {
            "gcn_id": gcn_id,
            "vector": vector,
            "content_preview": content,
            "type": "",  # type not provided at embedding write time
        }
        table = await self._run_sync(db.open_table, "node_embeddings")
        await self._run_sync(table.add, [row])

    # ── Read: Node Embeddings (vector search) ──

    async def search_similar_nodes(
        self, query_vector: list[float], top_k: int = 10, type_filter: str | None = None
    ) -> list[tuple[str, float]]:
        """Return list of (gcn_id, distance) pairs sorted by similarity."""
        db = self._get_db()
        if not self._table_exists("node_embeddings"):
            return []

        table = await self._run_sync(db.open_table, "node_embeddings")

        def _search():
            q = table.search(query_vector).limit(top_k)
            if type_filter:
                q = q.where(f"type = '{type_filter}'")
            return q.to_pandas()

        df = await self._run_sync(_search)
        return [(row["gcn_id"], float(row["_distance"])) for _, row in df.iterrows()]
