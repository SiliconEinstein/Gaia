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
    Closure,
    Module,
    Package,
    ProbabilityRecord,
    Resource,
    ResourceAttachment,
    ScoredClosure,
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
        pa.field("name", pa.string()),
        pa.field("role", pa.string()),
        pa.field("imports", pa.string()),  # JSON list[ImportRef]
        pa.field("chain_ids", pa.string()),  # JSON list[str]
        pa.field("export_ids", pa.string()),  # JSON list[str]
    ]
)

_CLOSURES_SCHEMA = pa.schema(
    [
        pa.field("closure_id", pa.string()),
        pa.field("version", pa.int64()),
        pa.field("type", pa.string()),
        pa.field("content", pa.string()),
        pa.field("prior", pa.float64()),
        pa.field("keywords", pa.string()),  # JSON list[str]
        pa.field("source_package_id", pa.string()),
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
        pa.field("closure_id", pa.string()),
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
    "closures": _CLOSURES_SCHEMA,
    "chains": _CHAINS_SCHEMA,
    "probabilities": _PROBABILITIES_SCHEMA,
    "belief_history": _BELIEF_HISTORY_SCHEMA,
    "resources": _RESOURCES_SCHEMA,
    "resource_attachments": _RESOURCE_ATTACHMENTS_SCHEMA,
}

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
        name=row["name"],
        role=row["role"],
        imports=json.loads(row["imports"]),
        chain_ids=json.loads(row["chain_ids"]),
        export_ids=json.loads(row["export_ids"]),
    )


def _closure_to_row(c: Closure) -> dict[str, Any]:
    return {
        "closure_id": c.closure_id,
        "version": c.version,
        "type": c.type,
        "content": c.content,
        "prior": c.prior,
        "keywords": json.dumps(c.keywords),
        "source_package_id": c.source_package_id,
        "source_module_id": c.source_module_id,
        "created_at": c.created_at.isoformat(),
        "embedding": json.dumps(c.embedding) if c.embedding else "",
    }


def _row_to_closure(row: dict[str, Any]) -> Closure:
    emb_raw = row["embedding"]
    return Closure(
        closure_id=row["closure_id"],
        version=row["version"],
        type=row["type"],
        content=row["content"],
        prior=row["prior"],
        keywords=json.loads(row["keywords"]),
        source_package_id=row["source_package_id"],
        source_module_id=row["source_module_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
        embedding=json.loads(emb_raw) if emb_raw else None,
    )


def _chain_to_row(c: Chain) -> dict[str, Any]:
    return {
        "chain_id": c.chain_id,
        "module_id": c.module_id,
        "package_id": c.package_id,
        "type": c.type,
        "steps": json.dumps([s.model_dump() for s in c.steps]),
    }


def _row_to_chain(row: dict[str, Any]) -> Chain:
    return Chain(
        chain_id=row["chain_id"],
        module_id=row["module_id"],
        package_id=row["package_id"],
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
        "closure_id": s.closure_id,
        "version": s.version,
        "belief": s.belief,
        "bp_run_id": s.bp_run_id,
        "computed_at": s.computed_at.isoformat(),
    }


def _row_to_belief(row: dict[str, Any]) -> BeliefSnapshot:
    return BeliefSnapshot(
        closure_id=row["closure_id"],
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
        "size_bytes": r.size_bytes or 0,
        "checksum": r.checksum or "",
        "metadata": json.dumps(r.metadata),
        "created_at": r.created_at.isoformat(),
        "source_package_id": r.source_package_id,
    }


def _row_to_resource(row: dict[str, Any]) -> Resource:
    size = row["size_bytes"]
    return Resource(
        resource_id=row["resource_id"],
        type=row["type"],
        format=row["format"],
        title=row["title"] or None,
        description=row["description"] or None,
        storage_backend=row["storage_backend"],
        storage_path=row["storage_path"],
        size_bytes=size if size else None,
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

    # ── Schema setup ──

    async def initialize(self) -> None:
        """Create all required tables if they don't already exist."""
        existing = set(self._db.list_tables().tables)
        for table_name, schema in _TABLE_SCHEMAS.items():
            if table_name not in existing:
                self._db.create_table(table_name, schema=schema)

    # ── Write ──

    async def write_package(self, package: Package, modules: list[Module]) -> None:
        pkg_table = self._db.open_table("packages")
        pkg_table.add([_package_to_row(package)])
        if modules:
            mod_table = self._db.open_table("modules")
            mod_table.add([_module_to_row(m) for m in modules])

    async def write_closures(self, closures: list[Closure]) -> None:
        if not closures:
            return
        table = self._db.open_table("closures")
        # Filter out duplicates by (closure_id, version)
        new_rows = []
        for c in closures:
            existing = (
                table.search()
                .where(f"closure_id = '{c.closure_id}' AND version = {c.version}")
                .limit(1)
                .to_list()
            )
            if not existing:
                new_rows.append(_closure_to_row(c))
        if new_rows:
            table.add(new_rows)
            self._fts_dirty = True

    async def write_chains(self, chains: list[Chain]) -> None:
        if not chains:
            return
        table = self._db.open_table("chains")
        table.add([_chain_to_row(c) for c in chains])

    async def write_probabilities(self, records: list[ProbabilityRecord]) -> None:
        if not records:
            return
        table = self._db.open_table("probabilities")
        table.add([_probability_to_row(r) for r in records])

    async def write_belief_snapshots(self, snapshots: list[BeliefSnapshot]) -> None:
        if not snapshots:
            return
        table = self._db.open_table("belief_history")
        table.add([_belief_to_row(s) for s in snapshots])

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

    async def get_closure(self, closure_id: str, version: int | None = None) -> Closure | None:
        table = self._db.open_table("closures")
        if version is not None:
            results = (
                table.search()
                .where(f"closure_id = '{closure_id}' AND version = {version}")
                .limit(1)
                .to_list()
            )
        else:
            # Get all versions, return the latest
            results = table.search().where(f"closure_id = '{closure_id}'").limit(1000).to_list()
            if not results:
                return None
            results = [max(results, key=lambda r: r["version"])]
        if not results:
            return None
        return _row_to_closure(results[0])

    async def get_closure_versions(self, closure_id: str) -> list[Closure]:
        table = self._db.open_table("closures")
        results = table.search().where(f"closure_id = '{closure_id}'").limit(1000).to_list()
        closures = [_row_to_closure(r) for r in results]
        return sorted(closures, key=lambda c: c.version)

    async def get_package(self, package_id: str) -> Package | None:
        table = self._db.open_table("packages")
        results = table.search().where(f"package_id = '{package_id}'").limit(1).to_list()
        if not results:
            return None
        return _row_to_package(results[0])

    async def get_module(self, module_id: str) -> Module | None:
        table = self._db.open_table("modules")
        results = table.search().where(f"module_id = '{module_id}'").limit(1).to_list()
        if not results:
            return None
        return _row_to_module(results[0])

    async def get_chains_by_module(self, module_id: str) -> list[Chain]:
        table = self._db.open_table("chains")
        results = table.search().where(f"module_id = '{module_id}'").limit(10000).to_list()
        return [_row_to_chain(r) for r in results]

    async def get_probability_history(
        self, chain_id: str, step_index: int | None = None
    ) -> list[ProbabilityRecord]:
        table = self._db.open_table("probabilities")
        where = f"chain_id = '{chain_id}'"
        if step_index is not None:
            where += f" AND step_index = {step_index}"
        results = table.search().where(where).limit(10000).to_list()
        records = [_row_to_probability(r) for r in results]
        return sorted(records, key=lambda r: r.recorded_at)

    async def get_belief_history(self, closure_id: str) -> list[BeliefSnapshot]:
        table = self._db.open_table("belief_history")
        results = table.search().where(f"closure_id = '{closure_id}'").limit(10000).to_list()
        snapshots = [_row_to_belief(r) for r in results]
        return sorted(snapshots, key=lambda s: s.computed_at)

    async def get_resources_for(self, target_type: str, target_id: str) -> list[Resource]:
        att_table = self._db.open_table("resource_attachments")
        att_results = (
            att_table.search()
            .where(f"target_type = '{target_type}' AND target_id = '{target_id}'")
            .limit(10000)
            .to_list()
        )
        if not att_results:
            return []
        resource_ids = [r["resource_id"] for r in att_results]
        res_table = self._db.open_table("resources")
        resources = []
        for rid in resource_ids:
            rows = res_table.search().where(f"resource_id = '{rid}'").limit(1).to_list()
            if rows:
                resources.append(_row_to_resource(rows[0]))
        return resources

    # ── Search ──

    async def search_bm25(self, text: str, top_k: int) -> list[ScoredClosure]:
        table = self._db.open_table("closures")
        if table.count_rows() == 0:
            return []
        if self._fts_dirty:
            table.create_fts_index("content", replace=True)
            self._fts_dirty = False
        results = table.search(text, query_type="fts").limit(top_k).to_list()
        scored = []
        for row in results:
            closure = _row_to_closure(row)
            scored.append(ScoredClosure(closure=closure, score=row["_score"]))
        return scored

    # ── BP bulk load ──

    async def list_closures(self) -> list[Closure]:
        table = self._db.open_table("closures")
        if table.count_rows() == 0:
            return []
        results = table.search().limit(table.count_rows()).to_list()
        return [_row_to_closure(r) for r in results]

    async def list_chains(self) -> list[Chain]:
        table = self._db.open_table("chains")
        if table.count_rows() == 0:
            return []
        results = table.search().limit(table.count_rows()).to_list()
        return [_row_to_chain(r) for r in results]
