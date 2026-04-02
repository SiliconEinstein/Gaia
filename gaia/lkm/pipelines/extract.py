"""Pipeline: paper XML extraction → LKM local+global graph.

Thin adapter over core/extract + core/integrate.
"""

from __future__ import annotations

from pathlib import Path

from gaia.lkm.core.extract import extract
from gaia.lkm.core.integrate import IntegrateResult, integrate
from gaia.lkm.storage import StorageManager


async def run_extract(
    review_xml: str | None,
    reasoning_chain_xml: str,
    select_conclusion_xml: str,
    metadata_id: str,
    storage: StorageManager,
) -> IntegrateResult:
    """Extract paper XMLs → integrate into LKM global graph.

    1. core/extract.extract() — parse XML → local nodes (pure, no I/O)
    2. core/integrate.integrate() — write to storage + dedup global graph

    review_xml can be None if step3 (premises/priors) hasn't been run yet.
    """
    result = extract(review_xml, reasoning_chain_xml, select_conclusion_xml, metadata_id)

    return await integrate(
        storage,
        package_id=result.package_id,
        version=result.version,
        local_variables=result.local_variables,
        local_factors=result.local_factors,
        prior_records=result.prior_records,
        factor_param_records=result.factor_param_records,
        param_sources=result.param_sources,
    )


async def run_extract_from_dir(
    paper_dir: str | Path,
    metadata_id: str | None,
    storage: StorageManager,
) -> IntegrateResult:
    """Convenience: read XMLs from a directory and run extraction + integration.

    Expects paper_dir to contain: review.xml, reasoning_chain.xml, select_conclusion.xml
    """
    paper_dir = Path(paper_dir)
    if metadata_id is None:
        metadata_id = paper_dir.name

    review_xml = (paper_dir / "review.xml").read_text(encoding="utf-8")
    reasoning_xml = (paper_dir / "reasoning_chain.xml").read_text(encoding="utf-8")
    select_xml = (paper_dir / "select_conclusion.xml").read_text(encoding="utf-8")

    return await run_extract(review_xml, reasoning_xml, select_xml, metadata_id, storage)
