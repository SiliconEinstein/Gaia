"""LanceDB-backed implementation of ContentStore."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

import lancedb
import pyarrow as pa

from libs.storage_v2.content_store import ContentStore
from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredKnowledge,
)

# ── PyArrow schemas ──

_PACKAGES_SCHEMA = pa.schema(
    [
        pa.field("package_id", pa.string()),
        pa.field("name", pa.string()),
        pa.field("version", pa.string()),
        pa.field("description", pa.string()),
        pa.field("modules", pa.string()),  # JSON list[str]
        pa.field("exports", pa.string()),  # JSON list[str]
        pa.field("submitter", pa.string()),
        pa.field("submitted_at", pa.string()),  # ISO datetime
        pa.field("status", pa.string()),
    ]
)

_MODULES_SCHEMA = pa.schema(
    [
        pa.field("module_id", pa.string()),
        pa.field("package_id", pa.string()),
        pa.field("package_version", pa.string()),
        pa.field("name", pa.string()),
        pa.field("role", pa.string()),
        pa.field("imports", pa.string()),  # JSON list[ImportRef]
        pa.field("chain_ids", pa.string()),  # JSON list[str]
        pa.field("export_ids", pa.string()),  # JSON list[str]
    ]
)

_KNOWLEDGE_SCHEMA = pa.schema(
    [
        pa.field("knowledge_id", pa.string()),
        pa.field("version", pa.int64()),
        pa.field("type", pa.string()),
        pa.field("content", pa.string()),
        pa.field("prior", pa.float64()),
        pa.field("keywords", pa.string()),  # JSON list[str]
        pa.field("source_package_id", pa.string()),
        pa.field("source_package_version", pa.string()),
        pa.field("source_module_id", pa.string()),
        pa.field("created_at", pa.string()),  # ISO datetime
        pa.field("embedding", pa.string()),  # JSON list[float] or ""
    ]
)

_CHAINS_SCHEMA = pa.schema(
    [
        pa.field("chain_id", pa.string()),
        pa.field("module_id", pa.string()),
        pa.field("package_id", pa.string()),
        pa.field("package_version", pa.string()),
        pa.field("type", pa.string()),
        pa.field("steps", pa.string()),  # JSON list[ChainStep]
    ]
)

_PROBABILITIES_SCHEMA = pa.schema(
    [
        pa.field("chain_id", pa.string()),
        pa.field("step_index", pa.int64()),
        pa.field("value", pa.float64()),
        pa.field("source", pa.string()),
        pa.field("source_detail", pa.string()),
        pa.field("recorded_at", pa.string()),  # ISO datetime
    ]
)

_BELIEF_HISTORY_SCHEMA = pa.schema(
    [
        pa.field("knowledge_id", pa.string()),
        pa.field("version", pa.int64()),
        pa.field("belief", pa.float64()),
        pa.field("bp_run_id", pa.string()),
        pa.field("computed_at", pa.string()),  # ISO datetime
    ]
)

_RESOURCES_SCHEMA = pa.schema(
    [
        pa.field("resource_id", pa.string()),
        pa.field("type", pa.string()),
        pa.field("format", pa.string()),
        pa.field("title", pa.string()),
        pa.field("description", pa.string()),
        pa.field("storage_backend", pa.string()),
        pa.field("storage_path", pa.string()),
        pa.field("size_bytes", pa.int64()),
        pa.field("checksum", pa.string()),
        pa.field("metadata", pa.string()),  # JSON dict
        pa.field("created_at", pa.string()),  # ISO datetime
        pa.field("source_package_id", pa.string()),
    ]
)

_RESOURCE_ATTACHMENTS_SCHEMA = pa.schema(
    [
        pa.field("resource_id", pa.string()),
        pa.field("target_type", pa.string()),
        pa.field("target_id", pa.string()),
        pa.field("role", pa.string()),
        pa.field("description", pa.string()),
    ]
)

_TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "packages": _PACKAGES_SCHEMA,
    "modules": _MODULES_SCHEMA,
    "knowledge": _KNOWLEDGE_SCHEMA,
    "chains": _CHAINS_SCHEMA,
    "probabilities": _PROBABILITIES_SCHEMA,
    "belief_history": _BELIEF_HISTORY_SCHEMA,
    "resources": _RESOURCES_SCHEMA,
    "resource_attachments": _RESOURCE_ATTACHMENTS_SCHEMA,
}

# ── Helpers ──

_MAX_SCAN = 100_000


def _q(s: str) -> str:
    """Escape single quotes for LanceDB SQL filter expressions."""
    return s.replace("'", "''")


# ── Serialization helpers ──


def _package_to_row(p: Package) -> dict[str, Any]:
    return {
        "package_id": p.package_id,
        "name": p.name,
        "version": p.version,
        "description": p.description or "",
        "modules": json.dumps(p.modules),
        "exports": json.dumps(p.exports),
        "submitter": p.submitter,
        "submitted_at": p.submitted_at.isoformat(),
        "status": p.status,
    }


def _row_to_package(row: dict[str, Any]) -> Package:
    return Package(
        package_id=row["package_id"],
        name=row["name"],
        version=row["version"],
        description=row["description"] or None,
        modules=json.loads(row["modules"]),
        exports=json.loads(row["exports"]),
        submitter=row["submitter"],
        submitted_at=datetime.fromisoformat(row["submitted_at"]),
        status=row["status"],
    )


def _module_to_row(m: Module) -> dict[str, Any]:
    return {
        "module_id": m.module_id,
        "package_id": m.package_id,
        "package_version": m.package_version,
        "name": m.name,
        "role": m.role,
        "imports": json.dumps([i.model_dump() for i in m.imports]),
        "chain_ids": json.dumps(m.chain_ids),
        "export_ids": json.dumps(m.export_ids),
    }


def _row_to_module(row: dict[str, Any]) -> Module:
    return Module(
        module_id=row["module_id"],
        package_id=row["package_id"],
        package_version=row.get("package_version", "0.1.0"),
        name=row["name"],
        role=row["role"],
        imports=json.loads(row["imports"]),
        chain_ids=json.loads(row["chain_ids"]),
        export_ids=json.loads(row["export_ids"]),
    )


def _knowledge_to_row(k: Knowledge) -> dict[str, Any]:
    return {
        "knowledge_id": k.knowledge_id,
        "version": k.version,
        "type": k.type,
        "content": k.content,
        "prior": k.prior,
        "keywords": json.dumps(k.keywords),
        "source_package_id": k.source_package_id,
        "source_package_version": k.source_package_version,
        "source_module_id": k.source_module_id,
        "created_at": k.created_at.isoformat(),
        "embedding": json.dumps(k.embedding) if k.embedding else "",
    }


def _row_to_knowledge(row: dict[str, Any]) -> Knowledge:
    emb_raw = row["embedding"]
    return Knowledge(
        knowledge_id=row["knowledge_id"],
        version=row["version"],
        type=row["type"],
        content=row["content"],
        prior=row["prior"],
        keywords=json.loads(row["keywords"]),
        source_package_id=row["source_package_id"],
        source_package_version=row.get("source_package_version", "0.1.0"),
        source_module_id=row["source_module_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        embedding=json.loads(emb_raw) if emb_raw else None,
    )


def _chain_to_row(c: Chain) -> dict[str, Any]:
    return {
        "chain_id": c.chain_id,
        "module_id": c.module_id,
        "package_id": c.package_id,
        "package_version": c.package_version,
        "type": c.type,
        "steps": json.dumps([s.model_dump() for s in c.steps]),
    }


def _row_to_chain(row: dict[str, Any]) -> Chain:
    return Chain(
        chain_id=row["chain_id"],
        module_id=row["module_id"],
        package_id=row["package_id"],
        package_version=row.get("package_version", "0.1.0"),
        type=row["type"],
        steps=json.loads(row["steps"]),
    )


def _probability_to_row(r: ProbabilityRecord) -> dict[str, Any]:
    return {
        "chain_id": r.chain_id,
        "step_index": r.step_index,
        "value": r.value,
        "source": r.source,
        "source_detail": r.source_detail or "",
        "recorded_at": r.recorded_at.isoformat(),
    }


def _row_to_probability(row: dict[str, Any]) -> ProbabilityRecord:
    return ProbabilityRecord(
        chain_id=row["chain_id"],
        step_index=row["step_index"],
        value=row["value"],
        source=row["source"],
        source_detail=row["source_detail"] or None,
        recorded_at=datetime.fromisoformat(row["recorded_at"]),
    )


def _belief_to_row(s: BeliefSnapshot) -> dict[str, Any]:
    return {
        "knowledge_id": s.knowledge_id,
        "version": s.version,
        "belief": s.belief,
        "bp_run_id": s.bp_run_id,
        "computed_at": s.computed_at.isoformat(),
    }


def _row_to_belief(row: dict[str, Any]) -> BeliefSnapshot:
    return BeliefSnapshot(
        knowledge_id=row["knowledge_id"],
        version=row["version"],
        belief=row["belief"],
        bp_run_id=row["bp_run_id"],
        computed_at=datetime.fromisoformat(row["computed_at"]),
    )


def _resource_to_row(r: Resource) -> dict[str, Any]:
    return {
        "resource_id": r.resource_id,
        "type": r.type,
        "format": r.format,
        "title": r.title or "",
        "description": r.description or "",
        "storage_backend": r.storage_backend,
        "storage_path": r.storage_path,
        "size_bytes": r.size_bytes if r.size_bytes is not None else -1,
        "checksum": r.checksum or "",
        "metadata": json.dumps(r.metadata),
        "created_at": r.created_at.isoformat(),
        "source_package_id": r.source_package_id,
    }


def _row_to_resource(row: dict[str, Any]) -> Resource:
    size_raw = row["size_bytes"]
    return Resource(
        resource_id=row["resource_id"],
        type=row["type"],
        format=row["format"],
        title=row["title"] or None,
        description=row["description"] or None,
        storage_backend=row["storage_backend"],
        storage_path=row["storage_path"],
        size_bytes=size_raw if size_raw >= 0 else None,
        checksum=row["checksum"] or None,
        metadata=json.loads(row["metadata"]),
        created_at=datetime.fromisoformat(row["created_at"]),
        source_package_id=row["source_package_id"],
    )


def _attachment_to_row(a: ResourceAttachment) -> dict[str, Any]:
    return {
        "resource_id": a.resource_id,
        "target_type": a.target_type,
        "target_id": a.target_id,
        "role": a.role,
        "description": a.description or "",
    }


def _row_to_attachment(row: dict[str, Any]) -> ResourceAttachment:
    return ResourceAttachment(
        resource_id=row["resource_id"],
        target_type=row["target_type"],
        target_id=row["target_id"],
        role=row["role"],
        description=row["description"] or None,
    )


class LanceContentStore(ContentStore):
    """LanceDB-backed content store for Gaia v2 storage layer."""

    def __init__(self, db_path: str) -> None:
        self._db = lancedb.connect(db_path)
        self._fts_dirty = True
        self._committed_pkgs: set[tuple[str, str]] | None = None  # lazy-loaded cache

    # ── Schema setup ──

    async def initialize(self) -> None:
        """Create all required tables if they don't already exist."""
        existing = set(self._db.list_tables().tables)
        for table_name, schema in _TABLE_SCHEMAS.items():
            if table_name not in existing:
                self._db.create_table(table_name, schema=schema)

    # ── Delete ──

    async def delete_package(self, package_id: str) -> None:
        """Delete all data belonging to a package (idempotent re-publish)."""
        escaped = _q(package_id)
        # Direct column matches
        direct_pairs = [
            ("packages", "package_id"),
            ("modules", "package_id"),
            ("knowledge", "source_package_id"),
            ("chains", "package_id"),
            ("resources", "source_package_id"),
        ]
        for table_name, col in direct_pairs:
            try:
                tbl = self._db.open_table(table_name)
                tbl.delete(f"{col} = '{escaped}'")
            except Exception:
                pass  # Table may not exist yet

        # Probabilities: chain_id starts with "package_id."
        try:
            tbl = self._db.open_table("probabilities")
            tbl.delete(f"chain_id LIKE '{escaped}.%'")
        except Exception:
            pass

        # Belief history: knowledge_id may use slash (CLI) or dot (fixture/legacy).
        try:
            tbl = self._db.open_table("belief_history")
            tbl.delete(f"knowledge_id LIKE '{escaped}/%'")
            tbl.delete(f"knowledge_id LIKE '{escaped}.%'")
        except Exception:
            pass

        # Resource attachments: resource_id starts with "package_id."
        try:
            tbl = self._db.open_table("resource_attachments")
            tbl.delete(f"resource_id LIKE '{escaped}.%'")
        except Exception:
            pass

        self._fts_dirty = True
        self._committed_pkgs = None

    # ── Commit / visibility ──

    async def commit_package(self, package_id: str, version: str) -> None:
        """Flip a package's status from 'preparing' to 'merged'."""
        table = self._db.open_table("packages")
        table.update(
            where=(
                f"package_id = '{_q(package_id)}' AND version = '{_q(version)}'"
                " AND status = 'preparing'"
            ),
            values={"status": "merged"},
        )
        self._committed_pkgs = None

    async def get_committed_packages(self) -> set[tuple[str, str]]:
        """Return (package_id, version) pairs with status='merged'."""
        table = self._db.open_table("packages")
        rows = table.search().where("status = 'merged'").select(["package_id", "version"]).to_list()
        return {(row["package_id"], row["version"]) for row in rows}

    async def _get_committed_packages(self) -> set[tuple[str, str]]:
        """Return cached set of committed (package_id, version) pairs."""
        if self._committed_pkgs is None:
            self._committed_pkgs = await self.get_committed_packages()
        return self._committed_pkgs

    def _is_committed(
        self, package_id: str, package_version: str, committed: set[tuple[str, str]]
    ) -> bool:
        """Check if a (package_id, version) pair is committed."""
        return (package_id, package_version) in committed

    # ── Write ──

    async def write_package(self, package: Package, modules: list[Module]) -> None:
        pkg_table = self._db.open_table("packages")
        (
            pkg_table.merge_insert(["package_id", "version"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute([_package_to_row(package)])
        )
        if modules:
            mod_table = self._db.open_table("modules")
            rows = [_module_to_row(m) for m in modules]
            (
                mod_table.merge_insert(["module_id", "package_version"])
                .when_matched_update_all()
                .when_not_matched_insert_all()
                .execute(rows)
            )

    async def write_knowledge(self, knowledge_items: list[Knowledge]) -> None:
        if not knowledge_items:
            return
        table = self._db.open_table("knowledge")
        rows = [_knowledge_to_row(k) for k in knowledge_items]
        (
            table.merge_insert(["knowledge_id", "version", "source_package_version"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )
        self._fts_dirty = True

    async def write_chains(self, chains: list[Chain]) -> None:
        if not chains:
            return
        table = self._db.open_table("chains")
        rows = [_chain_to_row(c) for c in chains]
        (
            table.merge_insert(["chain_id", "package_version"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("probabilities")
        rows = [_probability_to_row(r) for r in records]
        (
            table.merge_insert(["chain_id", "step_index", "source"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None:
        if not snapshots:
            return
        table = self._db.open_table("belief_history")
        rows = [_belief_to_row(s) for s in snapshots]
        (
            table.merge_insert(["knowledge_id", "version", "bp_run_id"])
            .when_matched_update_all()
            .when_not_matched_insert_all()
            .execute(rows)
        )

    async def write_resources(
        self, resources: list[Resource], attachments: list[ResourceAttachment]
    ) -> None:
        if resources:
            table = self._db.open_table("resources")
            table.add([_resource_to_row(r) for r in resources])
        if attachments:
            table = self._db.open_table("resource_attachments")
            table.add([_attachment_to_row(a) for a in attachments])

    # ── Read ──

    async def get_knowledge(
        self, knowledge_id: str, version: int | None = None
    ) -> Knowledge | None:
        table = self._db.open_table("knowledge")
        committed = await self._get_committed_packages()
        if version is not None:
            results = (
                table.search()
                .where(f"knowledge_id = '{_q(knowledge_id)}' AND version = {version}")
                .limit(1)
                .to_list()
            )
            results = [
                r
                for r in results
                if self._is_committed(
                    r["source_package_id"], r.get("source_package_version", "0.1.0"), committed
                )
            ]
        else:
            # Get all versions, return the latest
            results = (
                table.search()
                .where(f"knowledge_id = '{_q(knowledge_id)}'")
                .limit(_MAX_SCAN)
                .to_list()
            )
            results = [
                r
                for r in results
                if self._is_committed(
                    r["source_package_id"], r.get("source_package_version", "0.1.0"), committed
                )
            ]
            if not results:
                return None
            results = [max(results, key=lambda r: r["version"])]
        if not results:
            return None
        return _row_to_knowledge(results[0])

    async def get_knowledge_versions(self, knowledge_id: str) -> list[Knowledge]:
        table = self._db.open_table("knowledge")
        results = (
            table.search().where(f"knowledge_id = '{_q(knowledge_id)}'").limit(_MAX_SCAN).to_list()
        )
        committed = await self._get_committed_packages()
        results = [
            r
            for r in results
            if self._is_committed(
                r["source_package_id"], r.get("source_package_version", "0.1.0"), committed
            )
        ]
        knowledge_items = [_row_to_knowledge(r) for r in results]
        return sorted(knowledge_items, key=lambda k: k.version)

    async def get_package(self, package_id: str) -> Package | None:
        table = self._db.open_table("packages")
        results = (
            table.search()
            .where(f"package_id = '{_q(package_id)}' AND status = 'merged'")
            .limit(_MAX_SCAN)
            .to_list()
        )
        if not results:
            return None
        # Return the latest version
        latest = max(results, key=lambda r: r["version"])
        return _row_to_package(latest)

    async def get_module(self, module_id: str) -> Module | None:
        table = self._db.open_table("modules")
        results = table.search().where(f"module_id = '{_q(module_id)}'").limit(_MAX_SCAN).to_list()
        if not results:
            return None
        committed = await self._get_committed_packages()
        results = [
            r
            for r in results
            if self._is_committed(r["package_id"], r.get("package_version", "0.1.0"), committed)
        ]
        if not results:
            return None
        return _row_to_module(results[0])

    async def get_chains_by_module(self, module_id: str) -> list[Chain]:
        table = self._db.open_table("chains")
        results = table.search().where(f"module_id = '{_q(module_id)}'").limit(_MAX_SCAN).to_list()
        committed = await self._get_committed_packages()
        return [
            _row_to_chain(r)
            for r in results
            if self._is_committed(r["package_id"], r.get("package_version", "0.1.0"), committed)
        ]

    async def get_probability_history(
        self, chain_id: str, step_index: int | None = None
    ) -> list[ProbabilityRecord]:
        table = self._db.open_table("probabilities")
        where = f"chain_id = '{_q(chain_id)}'"
        if step_index is not None:
            where += f" AND step_index = {step_index}"
        results = table.search().where(where).limit(_MAX_SCAN).to_list()
        records = [_row_to_probability(r) for r in results]
        return sorted(records, key=lambda r: r.recorded_at)

    async def get_belief_history(self, knowledge_id: str) -> list[BeliefSnapshot]:
        table = self._db.open_table("belief_history")
        results = (
            table.search().where(f"knowledge_id = '{_q(knowledge_id)}'").limit(_MAX_SCAN).to_list()
        )
        snapshots = [_row_to_belief(r) for r in results]
        return sorted(snapshots, key=lambda s: s.computed_at)

    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]:
        att_table = self._db.open_table("resource_attachments")
        att_results = (
            att_table.search()
            .where(f"target_type = '{_q(target_type)}' AND target_id = '{_q(target_id)}'")
            .limit(_MAX_SCAN)
            .to_list()
        )
        if not att_results:
            return []
        resource_ids = [r["resource_id"] for r in att_results]
        res_table = self._db.open_table("resources")
        resources = []
        for rid in resource_ids:
            rows = res_table.search().where(f"resource_id = '{_q(rid)}'").limit(1).to_list()
            if rows:
                resources.append(_row_to_resource(rows[0]))
        return resources

    # ── Search ──

    async def search_bm25(self, text: str, top_k: int) -> list[ScoredKnowledge]:
        table = self._db.open_table("knowledge")
        if table.count_rows() == 0:
            return []
        if self._fts_dirty:
            table.create_fts_index("content", replace=True)
            self._fts_dirty = False
        committed = await self._get_committed_packages()
        results = table.search(text, query_type="fts").limit(top_k * 3).to_list()
        scored = []
        for row in results:
            if not self._is_committed(
                row["source_package_id"], row.get("source_package_version", "0.1.0"), committed
            ):
                continue
            knowledge = _row_to_knowledge(row)
            scored.append(ScoredKnowledge(knowledge=knowledge, score=row["_score"]))
        return scored[:top_k]

    # ── BP bulk load ──

    async def list_knowledge(self) -> list[Knowledge]:
        table = self._db.open_table("knowledge")
        count = table.count_rows()
        if count == 0:
            return []
        results = table.search().limit(count).to_list()
        committed = await self._get_committed_packages()
        return [
            _row_to_knowledge(r)
            for r in results
            if self._is_committed(
                r["source_package_id"], r.get("source_package_version", "0.1.0"), committed
            )
        ]

    async def list_chains(self) -> list[Chain]:
        table = self._db.open_table("chains")
        count = table.count_rows()
        if count == 0:
            return []
        results = table.search().limit(count).to_list()
        committed = await self._get_committed_packages()
        return [
            _row_to_chain(r)
            for r in results
            if self._is_committed(r["package_id"], r.get("package_version", "0.1.0"), committed)
        ]
