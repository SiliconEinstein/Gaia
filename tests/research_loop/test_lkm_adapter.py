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
