# Import Pipeline Hardening: Logging + ImportStatus + Stage Filter

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the batch import pipeline production-ready: unified logging across all LKM modules, `import_status` table tracking, ByteHouse stage filtering, and completion timestamps.

**Architecture:** Add a `gaia/lkm/logging.py` central config; add `logger = logging.getLogger(__name__)` to every core/storage/pipeline module; add `import_status` schema + model + read/write to storage layer; modify `search_papers()` to JOIN `task_status` for stage filtering; batch-write import_status at the end of `batch_integrate()`.

**Tech Stack:** Python logging (stdlib), LanceDB, ByteHouse (clickhouse-connect)

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `gaia/lkm/logging.py` | Central logging config (console + file handler) |
| Create | `gaia/lkm/models/import_status.py` | `ImportStatusRecord` Pydantic model |
| Modify | `gaia/lkm/models/__init__.py` | Re-export `ImportStatusRecord` |
| Modify | `gaia/lkm/storage/_schemas.py` | Add `IMPORT_STATUS` PyArrow schema to `TABLE_SCHEMAS` |
| Modify | `gaia/lkm/storage/_serialization.py` | Add `import_status_to_row` / `row_to_import_status` |
| Modify | `gaia/lkm/storage/lance_store.py` | Add `write_import_status_batch()`, `get_import_status()` |
| Modify | `gaia/lkm/storage/manager.py` | Expose `write_import_status_batch()`, add logging |
| Modify | `gaia/lkm/core/extract.py` | Add `logger` with DEBUG-level extraction stats |
| Modify | `gaia/lkm/core/integrate.py` | Add `logger` with INFO-level dedup/create stats |
| Modify | `gaia/lkm/storage/source_lance.py` | Add `logger`; modify `search_papers()` to JOIN `task_status` |
| Modify | `gaia/lkm/pipelines/import_lance.py` | Use `configure_logging()`; batch-write `import_status`; progress log |
| Modify | `gaia/lkm/api/app.py` | Call `configure_logging()` at startup |
| Create | `tests/gaia/lkm/test_logging.py` | Test `configure_logging()` |
| Create | `tests/gaia/lkm/models/test_import_status.py` | Test `ImportStatusRecord` model |
| Modify | `tests/gaia/lkm/storage/test_lance_store.py` | Test `write_import_status_batch()` |
| Modify | `tests/gaia/lkm/pipelines/test_import_lance.py` | Test stage filter + import_status write |

---

## Task 1: Unified Logging Config

**Files:**
- Create: `gaia/lkm/logging.py`
- Create: `tests/gaia/lkm/test_logging.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/gaia/lkm/test_logging.py
import logging
from pathlib import Path


def test_configure_logging_console_only():
    from gaia.lkm.logging import configure_logging

    configure_logging(level="DEBUG")
    logger = logging.getLogger("gaia.lkm.test")
    assert logger.getEffectiveLevel() <= logging.DEBUG


def test_configure_logging_with_file(tmp_path: Path):
    from gaia.lkm.logging import configure_logging

    log_file = tmp_path / "test.log"
    configure_logging(level="INFO", log_file=log_file)
    logger = logging.getLogger("gaia.lkm.test_file")
    logger.info("hello")
    assert log_file.exists()
    assert "hello" in log_file.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia/lkm/test_logging.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'gaia.lkm.logging'`

- [ ] **Step 3: Write the implementation**

```python
# gaia/lkm/logging.py
"""Unified logging configuration for LKM."""

from __future__ import annotations

import logging
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)s %(name)s: %(message)s"


def configure_logging(
    level: str = "INFO",
    log_file: Path | None = None,
) -> None:
    """Configure logging for all gaia.lkm.* loggers.

    Call once at process startup (CLI entry point or API lifespan).
    Console handler is always added; file handler is added if log_file is set.
    """
    root_logger = logging.getLogger("gaia.lkm")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Clear existing handlers to allow reconfiguration
    root_logger.handlers.clear()

    formatter = logging.Formatter(_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(log_file)
        fh.setFormatter(formatter)
        root_logger.addHandler(fh)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/gaia/lkm/test_logging.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lkm/logging.py tests/gaia/lkm/test_logging.py
git commit -m "feat(lkm): add unified logging configuration"
```

---

## Task 2: ImportStatusRecord Model + Schema + Serialization

**Files:**
- Create: `gaia/lkm/models/import_status.py`
- Modify: `gaia/lkm/models/__init__.py`
- Modify: `gaia/lkm/storage/_schemas.py`
- Modify: `gaia/lkm/storage/_serialization.py`
- Create: `tests/gaia/lkm/models/test_import_status.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/gaia/lkm/models/test_import_status.py
from datetime import datetime, timezone


def test_import_status_record_defaults():
    from gaia.lkm.models import ImportStatusRecord

    r = ImportStatusRecord(
        package_id="paper:12345",
        status="ingested",
        variable_count=10,
        factor_count=3,
        prior_count=8,
        factor_param_count=2,
    )
    assert r.package_id == "paper:12345"
    assert r.status == "ingested"
    assert r.variable_count == 10
    assert isinstance(r.started_at, datetime)
    assert isinstance(r.completed_at, datetime)


def test_import_status_roundtrip():
    from gaia.lkm.models import ImportStatusRecord
    from gaia.lkm.storage._serialization import import_status_to_row, row_to_import_status

    r = ImportStatusRecord(
        package_id="paper:99",
        status="ingested",
        variable_count=5,
        factor_count=2,
        prior_count=4,
        factor_param_count=1,
    )
    row = import_status_to_row(r)
    assert isinstance(row["started_at"], str)
    back = row_to_import_status(row)
    assert back.package_id == r.package_id
    assert back.variable_count == r.variable_count
    assert back.prior_count == r.prior_count
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia/lkm/models/test_import_status.py -v`
Expected: FAIL — `ImportError`

- [ ] **Step 3: Write ImportStatusRecord model**

```python
# gaia/lkm/models/import_status.py
"""Import status tracking model."""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ImportStatusRecord(BaseModel):
    """Tracks the import status of a single package (paper) into LKM."""

    package_id: str
    status: str  # "ingested" | "failed:<reason>"
    variable_count: int = 0
    factor_count: int = 0
    prior_count: int = 0
    factor_param_count: int = 0
    started_at: datetime = Field(default_factory=_utcnow)
    completed_at: datetime = Field(default_factory=_utcnow)
    error: str = ""
```

- [ ] **Step 4: Add re-export in `gaia/lkm/models/__init__.py`**

Add to imports:

```python
from gaia.lkm.models.import_status import ImportStatusRecord
```

Add `"ImportStatusRecord"` to `__all__`.

- [ ] **Step 5: Add PyArrow schema in `_schemas.py`**

Add after `PARAM_SOURCES`:

```python
IMPORT_STATUS = pa.schema(
    [
        pa.field("package_id", pa.string()),
        pa.field("status", pa.string()),
        pa.field("variable_count", pa.int32()),
        pa.field("factor_count", pa.int32()),
        pa.field("prior_count", pa.int32()),
        pa.field("factor_param_count", pa.int32()),
        pa.field("started_at", pa.string()),
        pa.field("completed_at", pa.string()),
        pa.field("error", pa.string()),
    ]
)
```

Add `"import_status": IMPORT_STATUS` to `TABLE_SCHEMAS`.

- [ ] **Step 6: Add serialization functions in `_serialization.py`**

```python
from gaia.lkm.models.import_status import ImportStatusRecord

def import_status_to_row(r: ImportStatusRecord) -> dict:
    return {
        "package_id": r.package_id,
        "status": r.status,
        "variable_count": r.variable_count,
        "factor_count": r.factor_count,
        "prior_count": r.prior_count,
        "factor_param_count": r.factor_param_count,
        "started_at": r.started_at.isoformat(),
        "completed_at": r.completed_at.isoformat(),
        "error": r.error,
    }


def row_to_import_status(row: dict) -> ImportStatusRecord:
    return ImportStatusRecord(
        package_id=row["package_id"],
        status=row["status"],
        variable_count=row["variable_count"],
        factor_count=row["factor_count"],
        prior_count=row["prior_count"],
        factor_param_count=row["factor_param_count"],
        started_at=datetime.fromisoformat(row["started_at"]),
        completed_at=datetime.fromisoformat(row["completed_at"]),
        error=row.get("error", ""),
    )
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/gaia/lkm/models/test_import_status.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add gaia/lkm/models/import_status.py gaia/lkm/models/__init__.py \
    gaia/lkm/storage/_schemas.py gaia/lkm/storage/_serialization.py \
    tests/gaia/lkm/models/test_import_status.py
git commit -m "feat(lkm): add ImportStatusRecord model, schema, and serialization"
```

---

## Task 3: Storage Layer — import_status Read/Write

**Files:**
- Modify: `gaia/lkm/storage/lance_store.py`
- Modify: `gaia/lkm/storage/manager.py`
- Modify: `tests/gaia/lkm/storage/test_lance_store.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/gaia/lkm/storage/test_lance_store.py`:

```python
async def test_write_and_read_import_status(storage: StorageManager):
    """Batch write import_status records and read them back."""
    from gaia.lkm.models import ImportStatusRecord

    records = [
        ImportStatusRecord(
            package_id="paper:aaa",
            status="ingested",
            variable_count=10,
            factor_count=3,
            prior_count=8,
            factor_param_count=2,
        ),
        ImportStatusRecord(
            package_id="paper:bbb",
            status="failed:download",
            variable_count=0,
            factor_count=0,
            prior_count=0,
            factor_param_count=0,
            error="TOS timeout",
        ),
    ]
    await storage.write_import_status_batch(records)

    result = await storage.get_import_status("paper:aaa")
    assert result is not None
    assert result.status == "ingested"
    assert result.variable_count == 10

    result2 = await storage.get_import_status("paper:bbb")
    assert result2 is not None
    assert result2.status == "failed:download"

    missing = await storage.get_import_status("paper:zzz")
    assert missing is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/gaia/lkm/storage/test_lance_store.py::test_write_and_read_import_status -v`
Expected: FAIL — `AttributeError: 'StorageManager' has no attribute 'write_import_status_batch'`

- [ ] **Step 3: Add methods to `LanceContentStore`**

In `gaia/lkm/storage/lance_store.py`, add imports:

```python
from gaia.lkm.models.import_status import ImportStatusRecord
from gaia.lkm.storage._serialization import import_status_to_row, row_to_import_status
```

Add methods to `LanceContentStore`:

```python
async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None:
    """Batch write import status records."""
    if not records:
        return
    table = self._db.open_table("import_status")
    rows = [import_status_to_row(r) for r in records]
    await self._run(table.add, rows)

async def get_import_status(self, package_id: str) -> ImportStatusRecord | None:
    table = self._db.open_table("import_status")
    escaped = _q(package_id)
    results = await self._run(
        lambda: table.search().where(f"package_id = '{escaped}'").limit(1).to_list()
    )
    return row_to_import_status(results[0]) if results else None
```

- [ ] **Step 4: Expose via `StorageManager`**

In `gaia/lkm/storage/manager.py`, add import and methods:

```python
from gaia.lkm.models.import_status import ImportStatusRecord

async def write_import_status_batch(self, records: list[ImportStatusRecord]) -> None:
    await self.content.write_import_status_batch(records)

async def get_import_status(self, package_id: str) -> ImportStatusRecord | None:
    return await self.content.get_import_status(package_id)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/gaia/lkm/storage/test_lance_store.py::test_write_and_read_import_status -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/lkm/storage/lance_store.py gaia/lkm/storage/manager.py \
    tests/gaia/lkm/storage/test_lance_store.py
git commit -m "feat(lkm): add import_status batch write and read to storage layer"
```

---

## Task 4: ByteHouse Stage Filtering

**Files:**
- Modify: `gaia/lkm/storage/source_lance.py`
- Modify: `tests/gaia/lkm/pipelines/test_import_lance.py`

- [ ] **Step 1: Modify `search_papers()` to JOIN `task_status`**

In `gaia/lkm/storage/source_lance.py`, replace `search_papers()`:

```python
def search_papers(
    client: Any,
    *,
    keywords: str | None = None,
    areas: str | None = None,
    require_stages: tuple[str, ...] = (
        "is_extract_conclusion",
        "is_extract_reasoning",
        "is_review",
    ),
    limit: int = 1000,
) -> list[dict]:
    """Search papers in ByteHouse, filtered by extraction stage completion.

    Joins paper_metadata with task_status to ensure only papers with
    all required stages completed are returned.

    Args:
        client: clickhouse-connect client.
        keywords: Token search on en_title.
        areas: Filter by areas partition.
        require_stages: Stage columns that must be true in task_status.
        limit: Max results.
    """
    where_parts = []
    if keywords:
        safe_kw = keywords.replace("'", "\\'")
        where_parts.append(f"hasTokens(m.en_title, '{safe_kw}')")
    if areas:
        safe_areas = areas.replace("'", "\\'")
        where_parts.append(f"m.areas = '{safe_areas}'")
    for stage in require_stages:
        where_parts.append(f"t.{stage} = true")

    where_clause = " AND ".join(where_parts) if where_parts else "1=1"

    sql = (
        f"SELECT m.id, m.doi, m.en_title, m.areas\n"
        f"FROM paper_data.paper_metadata m\n"
        f"JOIN paper_data.task_status t ON toString(m.id) = t.pdf_id\n"
        f"WHERE {where_clause}\n"
        f"ORDER BY m.id DESC\n"
        f"LIMIT {limit}\n"
        f"SETTINGS enable_inverted_index_push_down = 1, "
        f"enable_optimizer = 0, optimize_lazy_materialization = 1"
    )

    result = client.query(sql)
    rows = result.result_rows
    columns = result.column_names
    return [dict(zip(columns, row)) for row in rows]
```

- [ ] **Step 2: Update existing test to match new signature**

Check `tests/gaia/lkm/pipelines/test_import_lance.py` — if it mocks `search_papers`, update the mock to accept the new `require_stages` kwarg. The default value means existing callers don't break.

- [ ] **Step 3: Run existing tests**

Run: `pytest tests/gaia/lkm/pipelines/test_import_lance.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/storage/source_lance.py tests/gaia/lkm/pipelines/test_import_lance.py
git commit -m "feat(lkm): filter ByteHouse papers by stage completion via task_status JOIN"
```

---

## Task 5: Add Logging to Core + Storage Modules

**Files:**
- Modify: `gaia/lkm/core/extract.py`
- Modify: `gaia/lkm/core/integrate.py`
- Modify: `gaia/lkm/storage/manager.py`
- Modify: `gaia/lkm/storage/source_lance.py`

No new tests needed — logging doesn't change behavior. Verify existing tests still pass.

- [ ] **Step 1: Add logger to `core/extract.py`**

At top of file (after imports):

```python
import logging

logger = logging.getLogger(__name__)
```

At end of `extract()` function, before `return result`:

```python
logger.debug(
    "Extracted paper %s: %d variables, %d factors, %d priors, %d factor_params",
    metadata_id,
    len(result.local_variables),
    len(result.local_factors),
    len(result.prior_records),
    len(result.factor_param_records),
)
```

- [ ] **Step 2: Add logger to `core/integrate.py`**

At top of file (after imports):

```python
import logging

logger = logging.getLogger(__name__)
```

At end of `integrate()`, before `return result`:

```python
logger.info(
    "Integrated %s: %d new globals, %d matched, %d new factors, %d unresolved",
    package_id,
    len(result.new_global_variables),
    len(result.updated_global_variables),
    len(result.new_global_factors),
    len(result.unresolved_cross_refs),
)
```

At end of `batch_integrate()`, before `return stats`:

```python
logger.info(
    "Batch integrated %d packages: %d new global vars, %d new global factors, "
    "%d dedup within batch, %d dedup with existing, %d unresolved",
    stats.packages,
    stats.new_global_variables,
    stats.new_global_factors,
    stats.dedup_within_batch,
    stats.dedup_with_existing,
    len(stats.unresolved_cross_refs),
)
```

- [ ] **Step 3: Add logger to `storage/manager.py`**

At top (after imports):

```python
import logging

logger = logging.getLogger(__name__)
```

Add timing log to `ingest_local_graph`:

```python
async def ingest_local_graph(self, ...) -> None:
    logger.info(
        "Ingesting local graph %s@%s: %d variables, %d factors",
        package_id, version, len(variable_nodes), len(factor_nodes),
    )
    ...  # existing code
```

Add timing log to `integrate_global_graph`:

```python
async def integrate_global_graph(self, ...) -> None:
    logger.info(
        "Integrating global graph: %d variables, %d factors, %d bindings",
        len(variable_nodes), len(factor_nodes), len(bindings),
    )
    ...  # existing code
```

- [ ] **Step 4: Add logger to `storage/source_lance.py`**

At top (after imports):

```python
import logging

logger = logging.getLogger(__name__)
```

In `download_paper_xmls`, log per-paper failures at WARNING and batch summary at INFO:

```python
# After the download loop, before return:
downloaded_count = sum(1 for v in results.values() if v is not None)
failed_count = sum(1 for v in results.values() if v is None)
logger.info("Downloaded XMLs: %d succeeded, %d failed (of %d)", downloaded_count, failed_count, len(paper_ids))
```

In `_download_one`, existing failures are silent — add at the per-paper level:

```python
# Where results[pid] = None:
except Exception:
    logger.warning("Download failed for paper %s", pid, exc_info=True)
    results[pid] = None
```

- [ ] **Step 5: Run all LKM tests**

Run: `pytest tests/gaia/lkm/ -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add gaia/lkm/core/extract.py gaia/lkm/core/integrate.py \
    gaia/lkm/storage/manager.py gaia/lkm/storage/source_lance.py
git commit -m "feat(lkm): add structured logging to core, storage, and source modules"
```

---

## Task 6: Wire Everything into `import_lance.py`

**Files:**
- Modify: `gaia/lkm/pipelines/import_lance.py`
- Modify: `tests/gaia/lkm/pipelines/test_import_lance.py`

- [ ] **Step 1: Update `import_lance.py`**

Replace `logging.basicConfig(...)` in `main()` with:

```python
from gaia.lkm.logging import configure_logging

configure_logging(level="INFO", log_file=args.output_dir / "import.log")
```

After `batch_integrate` succeeds (the `if extraction_results:` block), batch-write import_status:

```python
from datetime import datetime, timezone
from gaia.lkm.models import ImportStatusRecord

# After batch_result is computed, before checkpointing:
status_records = []
for pid, ext_result in zip(extracted_ids, extraction_results):
    status_records.append(
        ImportStatusRecord(
            package_id=ext_result.package_id,
            status="ingested",
            variable_count=len(ext_result.local_variables),
            factor_count=len(ext_result.local_factors),
            prior_count=len(ext_result.prior_records),
            factor_param_count=len(ext_result.factor_param_records),
            started_at=batch_started_at,  # capture datetime before the loop
            completed_at=datetime.now(timezone.utc),
        )
    )
await storage.write_import_status_batch(status_records)
logger.info("Wrote %d import_status records", len(status_records))
```

Also record `batch_started_at = datetime.now(timezone.utc)` at the top of `run_batch_import()`.

Add a progress log every 100 papers during extraction:

```python
for i, pid in enumerate(pending):
    if i > 0 and i % 100 == 0:
        logger.info("Extraction progress: %d/%d papers", i, len(pending))
    ...
```

Also write failed statuses to import_status:

```python
# Where a paper fails download or extraction:
failed_statuses.append(
    ImportStatusRecord(
        package_id=f"paper:{pid}",
        status=f"failed:{reason}",
        error=str(e) if e else "",
        started_at=batch_started_at,
        completed_at=datetime.now(timezone.utc),
    )
)
```

Then batch-write failed statuses after the main loop:

```python
if failed_statuses:
    await storage.write_import_status_batch(failed_statuses)
```

- [ ] **Step 2: Update test**

In `tests/gaia/lkm/pipelines/test_import_lance.py`, verify that after a mock run, `import_status` table has the expected records. This depends on the existing test structure — adapt the existing mocked test to assert `storage.get_import_status(...)` returns a record.

- [ ] **Step 3: Run tests**

Run: `pytest tests/gaia/lkm/pipelines/test_import_lance.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/pipelines/import_lance.py tests/gaia/lkm/pipelines/test_import_lance.py
git commit -m "feat(lkm): wire logging + import_status into batch import pipeline"
```

---

## Task 7: Wire Logging into API

**Files:**
- Modify: `gaia/lkm/api/app.py`

- [ ] **Step 1: Add `configure_logging()` call in lifespan**

```python
from gaia.lkm.logging import configure_logging

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    ...  # existing code
```

- [ ] **Step 2: Run existing API tests if any, else run full suite**

Run: `pytest tests/gaia/lkm/ -v`
Expected: All PASS

- [ ] **Step 3: Commit**

```bash
git add gaia/lkm/api/app.py
git commit -m "feat(lkm): wire unified logging into API startup"
```

---

## Task 8: Final Verification + Lint

- [ ] **Step 1: Run full test suite**

```bash
pytest tests/gaia/lkm/ -v
```

- [ ] **Step 2: Run ruff lint + format**

```bash
ruff check gaia/lkm/ tests/gaia/lkm/
ruff format --check gaia/lkm/ tests/gaia/lkm/
```

- [ ] **Step 3: Fix any lint/format errors**

- [ ] **Step 4: Final commit if needed, then push and create PR**

```bash
git push -u origin feat/lkm-import-pipeline-hardening
gh pr create --title "feat(lkm): import pipeline hardening — logging, import_status, stage filter" --body "..."
```
