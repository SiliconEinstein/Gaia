"""PyArrow schemas for LKM LanceDB tables."""

from __future__ import annotations

import pyarrow as pa

# ── Local layer ──

LOCAL_VARIABLE_NODES = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("type", pa.string()),
        pa.field("visibility", pa.string()),
        pa.field("content", pa.string()),
        pa.field("content_hash", pa.string()),
        pa.field("parameters", pa.string()),  # JSON list[Parameter]
        pa.field("source_package", pa.string()),
        pa.field("version", pa.string()),  # package version
        pa.field("metadata", pa.string()),  # JSON dict | ""
        pa.field("ingest_status", pa.string()),  # "preparing" | "merged"
    ]
)

LOCAL_FACTOR_NODES = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("factor_type", pa.string()),
        pa.field("subtype", pa.string()),
        pa.field("premises", pa.string()),  # JSON list[str]
        pa.field("conclusion", pa.string()),
        pa.field("background", pa.string()),  # JSON list[str] | ""
        pa.field("steps", pa.string()),  # JSON list[Step] | ""
        pa.field("source_package", pa.string()),
        pa.field("version", pa.string()),  # package version
        pa.field("metadata", pa.string()),
        pa.field("ingest_status", pa.string()),
    ]
)

# ── Global layer ──

GLOBAL_VARIABLE_NODES = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("type", pa.string()),
        pa.field("visibility", pa.string()),
        pa.field("content_hash", pa.string()),
        pa.field("parameters", pa.string()),
        pa.field("representative_lcn", pa.string()),
        pa.field("local_members", pa.string()),
        pa.field("metadata", pa.string()),
    ]
)

GLOBAL_FACTOR_NODES = pa.schema(
    [
        pa.field("id", pa.string()),
        pa.field("factor_type", pa.string()),
        pa.field("subtype", pa.string()),
        pa.field("premises", pa.string()),
        pa.field("conclusion", pa.string()),
        pa.field("representative_lfn", pa.string()),
        pa.field("source_package", pa.string()),
        pa.field("metadata", pa.string()),
    ]
)

# ── Binding ──

CANONICAL_BINDINGS = pa.schema(
    [
        pa.field("local_id", pa.string()),
        pa.field("global_id", pa.string()),
        pa.field("binding_type", pa.string()),
        pa.field("package_id", pa.string()),
        pa.field("version", pa.string()),
        pa.field("decision", pa.string()),
        pa.field("reason", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)

# ── Parameterization ──

PRIOR_RECORDS = pa.schema(
    [
        pa.field("variable_id", pa.string()),
        pa.field("value", pa.float64()),
        pa.field("source_id", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)

FACTOR_PARAM_RECORDS = pa.schema(
    [
        pa.field("factor_id", pa.string()),
        pa.field("conditional_probabilities", pa.string()),  # JSON list[float]
        pa.field("source_id", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)

PARAM_SOURCES = pa.schema(
    [
        pa.field("source_id", pa.string()),
        pa.field("source_class", pa.string()),
        pa.field("model", pa.string()),
        pa.field("policy", pa.string()),
        pa.field("config", pa.string()),
        pa.field("created_at", pa.string()),
    ]
)

# ── Registry ──

TABLE_SCHEMAS: dict[str, pa.Schema] = {
    "local_variable_nodes": LOCAL_VARIABLE_NODES,
    "local_factor_nodes": LOCAL_FACTOR_NODES,
    "global_variable_nodes": GLOBAL_VARIABLE_NODES,
    "global_factor_nodes": GLOBAL_FACTOR_NODES,
    "canonical_bindings": CANONICAL_BINDINGS,
    "prior_records": PRIOR_RECORDS,
    "factor_param_records": FACTOR_PARAM_RECORDS,
    "param_sources": PARAM_SOURCES,
}
