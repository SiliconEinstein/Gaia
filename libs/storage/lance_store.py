"""LanceDB-backed store for node content, metadata, and belief values."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import lancedb
import pyarrow as pa

from libs.models import Node

# PyArrow schema for the nodes table.
# Complex fields (content when dict/list, keywords, metadata, extra) are
# serialized as JSON strings.
_NODE_SCHEMA = pa.schema(
    [
        pa.field("id", pa.int64()),
        pa.field("type", pa.string()),
        pa.field("subtype", pa.string()),
        pa.field("title", pa.string()),
        pa.field("content", pa.string()),
        pa.field("keywords", pa.string()),
        pa.field("prior", pa.float64()),
        pa.field("belief", pa.float64()),
        pa.field("status", pa.string()),
        pa.field("metadata", pa.string()),
        pa.field("extra", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)


def _serialize_content(content: str | dict | list) -> str:
    """Serialize content to a string. Dicts/lists become JSON."""
    if isinstance(content, str):
        return content
    return json.dumps(content, ensure_ascii=False)


def _deserialize_content(raw: str) -> str | dict | list:
    """Deserialize content from storage.  Try JSON parse first; fall back to plain string."""
    try:
        parsed = json.loads(raw)
        if isinstance(parsed, (dict, list)):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return raw


def _node_to_row(node: Node) -> dict[str, Any]:
    """Convert a Node pydantic model to a flat dict suitable for LanceDB."""
    return {
        "id": node.id,
        "type": node.type,
        "subtype": node.subtype or "",
        "title": node.title or "",
        "content": _serialize_content(node.content),
        "keywords": json.dumps(node.keywords, ensure_ascii=False),
        "prior": node.prior,
        "belief": node.belief if node.belief is not None else 0.0,
        "status": node.status,
        "metadata": json.dumps(node.metadata, ensure_ascii=False),
        "extra": json.dumps(node.extra, ensure_ascii=False),
        "created_at": node.created_at.isoformat() if node.created_at else "",
    }


def _row_to_node(row: dict[str, Any]) -> Node:
    """Reconstruct a Node from a LanceDB row dict."""
    subtype = row.get("subtype") or None
    if subtype == "":
        subtype = None

    title = row.get("title") or None
    if title == "":
        title = None

    belief_val = row.get("belief")
    if belief_val == 0.0:
        # Distinguish between explicit 0.0 and the sentinel we use for None.
        # Since the default Node.belief is None and prior defaults to 1.0,
        # treat 0.0 as None unless belief was explicitly set.
        belief_val = None

    created_at_raw = row.get("created_at", "")
    created_at: datetime | None = None
    if created_at_raw:
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except (ValueError, TypeError):
            pass

    return Node(
        id=row["id"],
        type=row["type"],
        subtype=subtype,
        title=title,
        content=_deserialize_content(row["content"]),
        keywords=json.loads(row.get("keywords", "[]")),
        prior=row.get("prior", 1.0),
        belief=belief_val,
        status=row.get("status", "active"),
        metadata=json.loads(row.get("metadata", "{}")),
        extra=json.loads(row.get("extra", "{}")),
        created_at=created_at,
    )


class LanceStore:
    """LanceDB-backed store for Gaia nodes.

    Provides CRUD operations plus full-text search over node content.
    All public methods are async to match the project's async architecture,
    but the underlying LanceDB operations are synchronous.
    """

    TABLE_NAME = "nodes"

    def __init__(self, db_path: str) -> None:
        self._db = lancedb.connect(db_path)
        self._table: lancedb.table.LanceTable | None = None
        self._fts_dirty = True  # Track whether FTS index needs rebuild

    def _get_or_create_table(self) -> lancedb.table.LanceTable:
        """Lazily open or create the nodes table."""
        if self._table is not None:
            return self._table
        try:
            self._table = self._db.open_table(self.TABLE_NAME)
        except Exception:
            self._table = self._db.create_table(self.TABLE_NAME, schema=_NODE_SCHEMA)
        return self._table

    # ── Public API ──

    async def save_nodes(self, nodes: list[Node]) -> list[int]:
        """Persist a batch of nodes. Returns the list of saved node IDs."""
        if not nodes:
            return []
        table = self._get_or_create_table()
        rows = [_node_to_row(n) for n in nodes]
        table.add(rows)
        self._fts_dirty = True
        return [n.id for n in nodes]

    async def load_node(self, node_id: int) -> Node | None:
        """Load a single node by ID. Returns None if not found."""
        table = self._get_or_create_table()
        results = table.search().where(f"id = {node_id}").limit(1).to_list()
        if not results:
            return None
        return _row_to_node(results[0])

    async def load_nodes_bulk(self, node_ids: list[int]) -> list[Node]:
        """Load multiple nodes by ID. Missing IDs are silently skipped."""
        if not node_ids:
            return []
        table = self._get_or_create_table()
        id_list = ", ".join(str(i) for i in node_ids)
        results = table.search().where(f"id IN ({id_list})").limit(len(node_ids)).to_list()
        return [_row_to_node(r) for r in results]

    async def update_node(self, node_id: int, **fields: Any) -> None:
        """Update specific fields of a node in-place.

        Supported fields: any column in the schema (content, status, belief, etc.).
        Complex fields (content dict/list, keywords, metadata, extra) are
        re-serialized automatically.
        """
        table = self._get_or_create_table()
        values: dict[str, Any] = {}
        for key, val in fields.items():
            if key == "content":
                values["content"] = _serialize_content(val)
            elif key in ("keywords",):
                values["keywords"] = json.dumps(val, ensure_ascii=False)
            elif key in ("metadata", "extra"):
                values[key] = json.dumps(val, ensure_ascii=False)
            elif key == "created_at" and isinstance(val, datetime):
                values["created_at"] = val.isoformat()
            else:
                values[key] = val
        if values:
            table.update(where=f"id = {node_id}", values=values)
            if "content" in values:
                self._fts_dirty = True

    async def update_beliefs(self, beliefs: dict[int, float]) -> None:
        """Batch-update belief values for multiple nodes."""
        table = self._get_or_create_table()
        for node_id, belief in beliefs.items():
            table.update(where=f"id = {node_id}", values={"belief": belief})

    async def get_beliefs_bulk(self, node_ids: list[int]) -> dict[int, float]:
        """Retrieve belief values for a set of nodes."""
        if not node_ids:
            return {}
        table = self._get_or_create_table()
        id_list = ", ".join(str(i) for i in node_ids)
        results = (
            table.search()
            .where(f"id IN ({id_list})")
            .select(["id", "belief"])
            .limit(len(node_ids))
            .to_list()
        )
        return {r["id"]: r["belief"] for r in results}

    async def list_nodes(
        self,
        page: int = 1,
        size: int = 50,
        node_type: str | None = None,
    ) -> list[Node]:
        """List nodes with pagination and optional type filter."""
        table = self._get_or_create_table()
        query_builder = table.search()
        if node_type:
            query_builder = query_builder.where(f"type = '{node_type}'")
        offset = (page - 1) * size
        results = query_builder.limit(offset + size).to_list()
        return [_row_to_node(r) for r in results[offset:]]

    async def count_nodes(self, node_type: str | None = None) -> int:
        """Count total nodes, optionally filtered by type."""
        table = self._get_or_create_table()
        if node_type:
            return len(table.search().where(f"type = '{node_type}'").limit(1_000_000).to_list())
        return table.count_rows()

    async def fts_search(self, query: str, k: int = 100) -> list[tuple[int, float]]:
        """Full-text search over node content.

        Returns a list of (node_id, score) tuples sorted by relevance.
        The FTS index is (re)built automatically when content has changed.
        """
        table = self._get_or_create_table()
        if table.count_rows() == 0:
            return []
        # Rebuild FTS index if content has changed since last build
        if self._fts_dirty:
            table.create_fts_index("content", replace=True)
            self._fts_dirty = False
        results = table.search(query, query_type="fts").select(["id"]).limit(k).to_list()
        return [(r["id"], r["_score"]) for r in results]

    async def close(self) -> None:
        """Release resources. Currently a no-op as LanceDB handles cleanup."""
        self._table = None
