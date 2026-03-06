"""Local storage for CLI — manages LanceDB for FTS search."""

from pathlib import Path

import lancedb
import pyarrow as pa


class LocalStore:
    """Manages local LanceDB for BM25 full-text search over claims."""

    def __init__(self, pkg_dir: Path):
        self._store_dir = pkg_dir / ".gaia"
        self._store_dir.mkdir(parents=True, exist_ok=True)
        self._db = lancedb.connect(str(self._store_dir / "lancedb"))

    def index_claims(self, claims: list[dict]) -> None:
        """Index claims into LanceDB for FTS."""
        if not claims:
            return
        records = []
        for c in claims:
            records.append(
                {
                    "id": c["id"],
                    "content": c.get("content", ""),
                    "type": c.get("type", ""),
                    "why": c.get("why", ""),
                }
            )

        schema = pa.schema(
            [
                ("id", pa.int64()),
                ("content", pa.utf8()),
                ("type", pa.utf8()),
                ("why", pa.utf8()),
            ]
        )
        table_data = pa.table(
            {col: [r[col] for r in records] for col in ["id", "content", "type", "why"]},
            schema=schema,
        )

        if "claims" in self._db.list_tables():
            self._db.drop_table("claims")
        table = self._db.create_table("claims", table_data)
        try:
            table.create_fts_index("content", replace=True)
        except Exception:
            pass  # FTS index may not be available in all LanceDB versions

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search claims using FTS or fallback to substring matching."""
        if "claims" not in self._db.list_tables():
            return []

        table = self._db.open_table("claims")

        try:
            results = table.search(query).limit(limit).to_pandas()
            return results.to_dict("records")
        except Exception:
            # Fallback: load all and filter by substring
            all_data = table.to_pandas()
            matches = all_data[all_data["content"].str.contains(query, na=False)]
            return matches.head(limit).to_dict("records")
