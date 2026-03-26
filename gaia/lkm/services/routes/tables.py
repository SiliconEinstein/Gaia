"""Table browser routes — expose LanceDB tables for frontend inspection."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from gaia.lkm.services import deps as deps_module

router = APIRouter(tags=["tables"])


@router.get("/tables")
async def list_tables():
    """List all LanceDB table names."""
    store = deps_module.deps.storage.content_store
    db = store._db
    names = await store._run_sync(db.table_names)
    return {"tables": names}


@router.get("/tables/{name}")
async def get_table_data(name: str, limit: int = 100):
    """Get rows from a LanceDB table."""
    store = deps_module.deps.storage.content_store
    db = store._db
    table_names = await store._run_sync(db.table_names)
    if name not in table_names:
        raise HTTPException(status_code=404, detail=f"Table '{name}' not found")
    table = await store._run_sync(db.open_table, name)
    df = await store._run_sync(table.to_pandas)
    rows = df.head(limit).to_dict(orient="records")
    columns = list(df.columns)
    return {"table": name, "columns": columns, "rows": rows, "total": len(df)}
