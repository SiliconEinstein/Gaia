"""ByteHouse DDL templates for the LKM content tables.

These mirror the LanceDB schemas in ``_schemas.py`` but use ClickHouse types,
with ``Array(String)`` for premises (instead of JSON strings) so that
``has(premises, 'gcn_xxx')`` queries are supported natively.

All tables use ``HaUniqueMergeTree`` so that re-inserting a row with an
existing ``UNIQUE KEY`` performs an idempotent upsert.

The DDL strings contain a single ``{engine}`` placeholder that the caller
fills in with a fully-formed ``ENGINE = HaUniqueMergeTree(...)`` clause.
"""

from __future__ import annotations

# Each entry maps a logical name → DDL template.
# Tables are prefixed with ``lkm_`` to avoid colliding with embedding tables.

LKM_TABLES: dict[str, str] = {
    "lkm_local_variables": """
        CREATE TABLE IF NOT EXISTS {table} (
            id              String,
            type            String,
            visibility      String,
            content         String,
            content_hash    String,
            parameters      String,
            source_package  String,
            version         String,
            metadata        String,
            ingest_status   String DEFAULT 'merged',
            created_at      DateTime DEFAULT now(),
            INDEX idx_content_hash content_hash TYPE bloom_filter GRANULARITY 1,
            INDEX idx_source_package source_package TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_local_factors": """
        CREATE TABLE IF NOT EXISTS {table} (
            id              String,
            factor_type     String,
            subtype         String,
            premises        Array(String),
            conclusion      String,
            background      String,
            steps           String,
            source_package  String,
            version         String,
            metadata        String,
            ingest_status   String DEFAULT 'merged',
            created_at      DateTime DEFAULT now(),
            INDEX idx_conclusion conclusion TYPE bloom_filter GRANULARITY 1,
            INDEX idx_source_package source_package TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_global_variables": """
        CREATE TABLE IF NOT EXISTS {table} (
            id                  String,
            type                String,
            visibility          String,
            content_hash        String,
            parameters          String,
            representative_lcn  String,
            local_members       String,
            metadata            String,
            created_at          DateTime DEFAULT now(),
            INDEX idx_content_hash content_hash TYPE bloom_filter GRANULARITY 1,
            INDEX idx_visibility visibility TYPE set(8) GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_global_factors": """
        CREATE TABLE IF NOT EXISTS {table} (
            id                  String,
            factor_type         String,
            subtype             String,
            premises            Array(String),
            conclusion          String,
            representative_lfn  String,
            source_package      String,
            metadata            String,
            created_at          DateTime DEFAULT now(),
            INDEX idx_conclusion conclusion TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_canonical_bindings": """
        CREATE TABLE IF NOT EXISTS {table} (
            local_id      String,
            global_id     String,
            binding_type  String,
            package_id    String,
            version       String,
            decision      String,
            reason        String,
            created_at    String,
            INDEX idx_global_id global_id TYPE bloom_filter GRANULARITY 1,
            INDEX idx_package_id package_id TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY local_id
        UNIQUE KEY local_id
        SETTINGS index_granularity = 128
    """,
    "lkm_prior_records": """
        CREATE TABLE IF NOT EXISTS {table} (
            id           String,
            variable_id  String,
            value        Float64,
            source_id    String,
            created_at   String,
            INDEX idx_variable_id variable_id TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_factor_param_records": """
        CREATE TABLE IF NOT EXISTS {table} (
            id                         String,
            factor_id                  String,
            conditional_probabilities  String,
            source_id                  String,
            created_at                 String,
            INDEX idx_factor_id factor_id TYPE bloom_filter GRANULARITY 1
        )
        {engine}
        ORDER BY id
        UNIQUE KEY id
        SETTINGS index_granularity = 128
    """,
    "lkm_param_sources": """
        CREATE TABLE IF NOT EXISTS {table} (
            source_id     String,
            source_class  String,
            model         String,
            policy        String,
            config        String,
            created_at    String
        )
        {engine}
        ORDER BY source_id
        UNIQUE KEY source_id
        SETTINGS index_granularity = 128
    """,
    # import_status is an attempt log: one row per ingest attempt. A single
    # package_id can legitimately have many rows (retries, failures), each
    # with a distinct started_at. That is why the UNIQUE KEY is composite.
    "lkm_import_status": """
        CREATE TABLE IF NOT EXISTS {table} (
            package_id          String,
            status              String,
            variable_count      Int32,
            factor_count        Int32,
            prior_count         Int32,
            factor_param_count  Int32,
            started_at          String,
            completed_at        String,
            error               String
        )
        {engine}
        ORDER BY (package_id, started_at)
        UNIQUE KEY (package_id, started_at)
        SETTINGS index_granularity = 128
    """,
}


# Column orders for INSERT — must match the DDL field order (excluding the
# auto-populated ``created_at DEFAULT now()`` column where present).

COLUMN_ORDER: dict[str, list[str]] = {
    "lkm_local_variables": [
        "id",
        "type",
        "visibility",
        "content",
        "content_hash",
        "parameters",
        "source_package",
        "version",
        "metadata",
        "ingest_status",
    ],
    "lkm_local_factors": [
        "id",
        "factor_type",
        "subtype",
        "premises",
        "conclusion",
        "background",
        "steps",
        "source_package",
        "version",
        "metadata",
        "ingest_status",
    ],
    "lkm_global_variables": [
        "id",
        "type",
        "visibility",
        "content_hash",
        "parameters",
        "representative_lcn",
        "local_members",
        "metadata",
    ],
    "lkm_global_factors": [
        "id",
        "factor_type",
        "subtype",
        "premises",
        "conclusion",
        "representative_lfn",
        "source_package",
        "metadata",
    ],
    "lkm_canonical_bindings": [
        "local_id",
        "global_id",
        "binding_type",
        "package_id",
        "version",
        "decision",
        "reason",
        "created_at",
    ],
    "lkm_prior_records": [
        "id",
        "variable_id",
        "value",
        "source_id",
        "created_at",
    ],
    "lkm_factor_param_records": [
        "id",
        "factor_id",
        "conditional_probabilities",
        "source_id",
        "created_at",
    ],
    "lkm_param_sources": [
        "source_id",
        "source_class",
        "model",
        "policy",
        "config",
        "created_at",
    ],
    "lkm_import_status": [
        "package_id",
        "status",
        "variable_count",
        "factor_count",
        "prior_count",
        "factor_param_count",
        "started_at",
        "completed_at",
        "error",
    ],
}
