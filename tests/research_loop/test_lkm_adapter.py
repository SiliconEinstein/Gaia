from __future__ import annotations

from pathlib import Path

from gaia.research_loop.lkm_adapter import build_landscape_from_raw_results


def test_build_landscape_from_raw_results_extracts_paper_leads(tmp_path: Path) -> None:
    fixture = Path("tests/lkm_explorer/fixtures/lkm_search_free_fall.json")

    artifact = build_landscape_from_raw_results(
        pkg=tmp_path,
        raw_results=[("free fall", fixture)],
        round_number=0,
    )

    assert artifact["schema"] == "gaia.research_loop.artifact.v1"
    assert artifact["kind"] == "landscape"
    assert artifact["round"] == 0
    assert artifact["raw_results"][0]["query"] == "free fall"
    assert isinstance(artifact["paper_leads"], list)


def test_build_landscape_from_raw_results_exposes_retrieved_content_snippets(
    tmp_path: Path,
) -> None:
    fixture = Path("tests/lkm_explorer/fixtures/lkm_search_free_fall.json")

    artifact = build_landscape_from_raw_results(
        pkg=tmp_path,
        raw_results=[("free fall", fixture)],
        round_number=0,
    )

    snippets = artifact["evidence_snippets"]
    assert snippets
    assert snippets[0]["content"].startswith("The kinematic maps mark free fall")
    assert snippets[0]["paper_id"] == "813135328909983744"
    assert snippets[0]["query"] == "free fall"
    assert any(lead.get("evidence_snippets") for lead in artifact["paper_leads"])
