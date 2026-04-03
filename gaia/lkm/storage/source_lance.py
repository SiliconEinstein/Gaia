"""Source data access: ByteHouse (search) + TOS (XML download).

Search layer uses ByteHouse ``paper_data.paper_metadata`` via clickhouse-connect.
Download layer uses TOS SDK to fetch per-paper XMLs.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
import os
import re
from dataclasses import dataclass
from typing import Any


# ── ByteHouse search ──


@dataclass
class ByteHouseConfig:
    """ByteHouse connection config."""

    host: str
    user: str
    password: str
    database: str
    port: int = 8123
    secure: bool = False

    @classmethod
    def from_env(cls) -> ByteHouseConfig:
        return cls(
            host=(os.environ.get("BYTEHOUSE_HOST") or "").strip().rstrip("/"),
            user=os.environ.get("BYTEHOUSE_USER") or "",
            password=os.environ.get("BYTEHOUSE_PASSWORD") or "",
            database=(os.environ.get("BYTEHOUSE_DATABASE") or "").strip(),
            port=int(os.environ.get("BYTEHOUSE_PORT") or "8123"),
            secure=(os.environ.get("BYTEHOUSE_SECURE") or "").strip().lower()
            in ("1", "true", "yes"),
        )


def connect_bytehouse(config: ByteHouseConfig) -> Any:
    """Connect to ByteHouse via clickhouse-connect."""
    import clickhouse_connect

    kw: dict[str, Any] = {
        "host": config.host,
        "port": config.port,
        "username": config.user,
        "password": config.password,
        "secure": config.secure,
    }
    if config.database:
        kw["database"] = config.database
    return clickhouse_connect.get_client(**kw)


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


# ── TOS download ──


@dataclass
class TOSConfig:
    """TOS connection config for XML download."""

    access_key: str
    secret_key: str
    endpoint: str
    bucket: str
    paper_path: str  # e.g. "paper_data"

    @classmethod
    def from_env(cls) -> TOSConfig:
        # TOS SDK needs native endpoint (tos-cn-beijing.volces.com),
        # not S3-compatible (tos-s3-cn-beijing.volces.com).
        endpoint = os.environ.get("TOS_ENDPOINT", "tos-cn-beijing.volces.com")
        endpoint = endpoint.replace("tos-s3-", "tos-")
        return cls(
            access_key=os.environ["TOS_ACCESS_KEY"],
            secret_key=os.environ["TOS_SECRET_KEY"],
            endpoint=endpoint,
            bucket=os.environ["TOS_BUCKET"],
            paper_path=os.environ.get("TOS_PAPER_XML_PATH", "paper_ocr/xml").strip("/"),
        )


@dataclass
class PaperXMLs:
    """Downloaded XMLs for one paper."""

    paper_id: str
    select_conclusion_xml: str  # step1
    reasoning_chain_xmls: list[str]  # step2 per-conclusion
    review_xmls: list[str]  # step3 per-conclusion (refine)


async def download_paper_xmls(
    config: TOSConfig,
    paper_ids: list[str],
    max_workers: int = 16,
) -> dict[str, PaperXMLs | None]:
    """Batch download 3 XML types per paper from TOS in parallel.

    TOS paths per paper:
    - {paper_path}/xml/{norm_id}_select_conclusion.xml
    - {paper_path}/xml/{norm_id}_conclusion_{n}_reasoning_chain.xml
    - {paper_path}/xml/{norm_id}_conclusion_{n}_refine.xml

    Returns dict of paper_id → PaperXMLs (or None on failure).
    """
    import tos

    client = tos.TosClientV2(
        config.access_key,
        config.secret_key,
        config.endpoint,
        "cn-beijing",
    )

    def _get_object_text(key: str) -> str | None:
        try:
            obj = client.get_object(config.bucket, key)
            return obj.read().decode("utf-8")
        except Exception:
            return None

    def _download_one(paper_id: str) -> PaperXMLs | None:
        prefix = f"{config.paper_path}/{paper_id}"

        # Step 1: select_conclusion.xml (required)
        select_xml = _get_object_text(f"{prefix}_select_conclusion.xml")
        if not select_xml:
            return None

        # Step 2: reasoning_chain.xml (required)
        # Try single-file format first (one per paper), then per-conclusion
        reasoning_xmls = []
        single_rc = _get_object_text(f"{prefix}_reasoning_chain.xml")
        if single_rc:
            reasoning_xmls.append(single_rc)
        else:
            for n in range(1, 21):
                rc = _get_object_text(f"{prefix}_conclusion_{n}_reasoning_chain.xml")
                if rc is None:
                    break
                reasoning_xmls.append(rc)

        if not reasoning_xmls:
            return None

        # Step 3: review/refine XMLs (optional — may not exist)
        review_xmls = []
        single_rv = _get_object_text(f"{prefix}_review.xml")
        if single_rv:
            review_xmls.append(single_rv)
        else:
            for n in range(1, 21):
                rf = _get_object_text(f"{prefix}_conclusion_{n}_refine.xml")
                if rf is None:
                    break
                review_xmls.append(rf)

        return PaperXMLs(
            paper_id=paper_id,
            select_conclusion_xml=select_xml,
            reasoning_chain_xmls=reasoning_xmls,
            review_xmls=review_xmls,
        )

    loop = asyncio.get_running_loop()
    results: dict[str, PaperXMLs | None] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        tasks = {pid: loop.run_in_executor(pool, _download_one, pid) for pid in paper_ids}
        for pid, future in tasks.items():
            try:
                results[pid] = await future
            except Exception:
                results[pid] = None

    return results


def merge_xmls(xmls: list[str]) -> str:
    """Merge per-conclusion XMLs into a single <inference_unit>.

    Strips XML headers and wraps all content in one <inference_unit> element.
    """
    parts = []
    for xml in xmls:
        content = re.sub(r"<\?xml[^?]*\?>\s*", "", xml)
        content = re.sub(r"<!--[^>]*-->\s*", "", content)
        parts.append(content.strip())
    return f"<inference_unit>{''.join(parts)}</inference_unit>"
