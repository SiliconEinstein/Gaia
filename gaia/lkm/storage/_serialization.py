"""Model ↔ LanceDB row serialization.

Convention:
- Complex fields (list, dict, nested model) → JSON string
- datetime → ISO 8601 string
- Optional string/dict → "" when None
"""

from __future__ import annotations

import json
from datetime import datetime

from gaia.lkm.models import (
    CanonicalBinding,
    FactorParamRecord,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    Parameter,
    ParameterizationSource,
    PriorRecord,
    Step,
)


def _q(s: str) -> str:
    """Escape single quotes for LanceDB SQL filter expressions."""
    return s.replace("'", "''")


# ── LocalVariableNode ──


def local_variable_to_row(node: LocalVariableNode, ingest_status: str = "preparing") -> dict:
    return {
        "id": node.id,
        "type": node.type,
        "visibility": node.visibility,
        "content": node.content,
        "content_hash": node.content_hash,
        "parameters": json.dumps([p.model_dump() for p in node.parameters]),
        "source_package": node.source_package,
        "version": node.version,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
        "ingest_status": ingest_status,
    }


def row_to_local_variable(row: dict) -> LocalVariableNode:
    params_raw = row.get("parameters", "[]")
    meta_raw = row.get("metadata", "")
    return LocalVariableNode(
        id=row["id"],
        type=row["type"],
        visibility=row["visibility"],
        content=row["content"],
        content_hash=row["content_hash"],
        parameters=[Parameter(**p) for p in json.loads(params_raw)] if params_raw else [],
        source_package=row["source_package"],
        version=row.get("version", ""),
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── LocalFactorNode ──


def local_factor_to_row(node: LocalFactorNode, ingest_status: str = "preparing") -> dict:
    return {
        "id": node.id,
        "factor_type": node.factor_type,
        "subtype": node.subtype,
        "premises": json.dumps(node.premises),
        "conclusion": node.conclusion,
        "background": json.dumps(node.background) if node.background else "",
        "steps": json.dumps([s.model_dump() for s in node.steps]) if node.steps else "",
        "source_package": node.source_package,
        "version": node.version,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
        "ingest_status": ingest_status,
    }


def row_to_local_factor(row: dict) -> LocalFactorNode:
    bg_raw = row.get("background", "")
    steps_raw = row.get("steps", "")
    meta_raw = row.get("metadata", "")
    return LocalFactorNode(
        id=row["id"],
        factor_type=row["factor_type"],
        subtype=row["subtype"],
        premises=json.loads(row["premises"]),
        conclusion=row["conclusion"],
        background=json.loads(bg_raw) if bg_raw else None,
        steps=[Step(**s) for s in json.loads(steps_raw)] if steps_raw else None,
        source_package=row["source_package"],
        version=row.get("version", ""),
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── GlobalVariableNode ──


def global_variable_to_row(node: GlobalVariableNode) -> dict:
    return {
        "id": node.id,
        "type": node.type,
        "visibility": node.visibility,
        "content_hash": node.content_hash,
        "parameters": json.dumps([p.model_dump() for p in node.parameters]),
        "representative_lcn": json.dumps(node.representative_lcn.model_dump()),
        "local_members": json.dumps([m.model_dump() for m in node.local_members]),
        "metadata": json.dumps(node.metadata) if node.metadata else "",
    }


def row_to_global_variable(row: dict) -> GlobalVariableNode:
    meta_raw = row.get("metadata", "")
    return GlobalVariableNode(
        id=row["id"],
        type=row["type"],
        visibility=row["visibility"],
        content_hash=row["content_hash"],
        parameters=[Parameter(**p) for p in json.loads(row["parameters"])],
        representative_lcn=LocalCanonicalRef(**json.loads(row["representative_lcn"])),
        local_members=[LocalCanonicalRef(**m) for m in json.loads(row["local_members"])],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── GlobalFactorNode ──


def global_factor_to_row(node: GlobalFactorNode) -> dict:
    return {
        "id": node.id,
        "factor_type": node.factor_type,
        "subtype": node.subtype,
        "premises": json.dumps(node.premises),
        "conclusion": node.conclusion,
        "representative_lfn": node.representative_lfn,
        "source_package": node.source_package,
        "metadata": json.dumps(node.metadata) if node.metadata else "",
    }


def row_to_global_factor(row: dict) -> GlobalFactorNode:
    meta_raw = row.get("metadata", "")
    return GlobalFactorNode(
        id=row["id"],
        factor_type=row["factor_type"],
        subtype=row["subtype"],
        premises=json.loads(row["premises"]),
        conclusion=row["conclusion"],
        representative_lfn=row["representative_lfn"],
        source_package=row["source_package"],
        metadata=json.loads(meta_raw) if meta_raw else None,
    )


# ── CanonicalBinding ──


def binding_to_row(b: CanonicalBinding) -> dict:
    return {
        "local_id": b.local_id,
        "global_id": b.global_id,
        "binding_type": b.binding_type,
        "package_id": b.package_id,
        "version": b.version,
        "decision": b.decision,
        "reason": b.reason,
        "created_at": datetime.now().isoformat(),
    }


def row_to_binding(row: dict) -> CanonicalBinding:
    return CanonicalBinding(
        local_id=row["local_id"],
        global_id=row["global_id"],
        binding_type=row["binding_type"],
        package_id=row["package_id"],
        version=row["version"],
        decision=row["decision"],
        reason=row["reason"],
    )


# ── PriorRecord ──


def prior_to_row(r: PriorRecord) -> dict:
    return {
        "variable_id": r.variable_id,
        "value": r.value,
        "source_id": r.source_id,
        "created_at": r.created_at.isoformat(),
    }


def row_to_prior(row: dict) -> PriorRecord:
    return PriorRecord(
        variable_id=row["variable_id"],
        value=row["value"],
        source_id=row["source_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# ── FactorParamRecord ──


def factor_param_to_row(r: FactorParamRecord) -> dict:
    return {
        "factor_id": r.factor_id,
        "conditional_probabilities": json.dumps(r.conditional_probabilities),
        "source_id": r.source_id,
        "created_at": r.created_at.isoformat(),
    }


def row_to_factor_param(row: dict) -> FactorParamRecord:
    return FactorParamRecord(
        factor_id=row["factor_id"],
        conditional_probabilities=json.loads(row["conditional_probabilities"]),
        source_id=row["source_id"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


# ── ParameterizationSource ──


def param_source_to_row(s: ParameterizationSource) -> dict:
    return {
        "source_id": s.source_id,
        "source_class": s.source_class,
        "model": s.model,
        "policy": s.policy or "",
        "config": json.dumps(s.config) if s.config else "",
        "created_at": s.created_at.isoformat(),
    }


def row_to_param_source(row: dict) -> ParameterizationSource:
    config_raw = row.get("config", "")
    return ParameterizationSource(
        source_id=row["source_id"],
        source_class=row["source_class"],
        model=row["model"],
        policy=row["policy"] or None,
        config=json.loads(config_raw) if config_raw else None,
        created_at=datetime.fromisoformat(row["created_at"]),
    )
