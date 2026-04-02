"""Pipeline B adapter: thin wrapper around core extraction."""

from __future__ import annotations

from pathlib import Path

from gaia.lkm.core.extract import ExtractionResult, extract


def run_pipeline_b(
    paper_dir: str | Path,
    metadata_id: str | None = None,
) -> ExtractionResult:
    """Run Pipeline B: extract a paper's XMLs to LKM local nodes.

    Args:
        paper_dir: Directory containing review.xml, reasoning_chain.xml, select_conclusion.xml
        metadata_id: Paper identifier. Defaults to directory name.
    """
    paper_dir = Path(paper_dir)
    if metadata_id is None:
        metadata_id = paper_dir.name

    review_xml = (paper_dir / "review.xml").read_text(encoding="utf-8")
    reasoning_xml = (paper_dir / "reasoning_chain.xml").read_text(encoding="utf-8")
    select_xml = (paper_dir / "select_conclusion.xml").read_text(encoding="utf-8")

    return extract(review_xml, reasoning_xml, select_xml, metadata_id)
