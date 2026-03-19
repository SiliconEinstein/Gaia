"""Tests for gaia search command — searches LanceDB."""

import asyncio
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

TYPST_FIXTURE = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies_v3")


def _publish_galileo_typst(tmp_path: Path) -> str:
    """Build + review + infer + publish via Typst pipeline, return db_path."""
    from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

    db_path = str(tmp_path / "testdb")

    async def _run():
        build = await pipeline_build(TYPST_FIXTURE)
        review = await pipeline_review(build, mock=True)
        infer = await pipeline_infer(build, review)
        await pipeline_publish(build, review, infer, db_path=db_path)

    asyncio.run(_run())
    return db_path


def test_search_finds_published_nodes(tmp_path):
    """After publish, search should find nodes in LanceDB."""
    db_path = _publish_galileo_typst(tmp_path)
    # Content is in Chinese; use CJK LIKE fallback search
    result = runner.invoke(app, ["search", "重量", "--db-path", db_path])
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


def test_search_no_results(tmp_path):
    db_path = _publish_galileo_typst(tmp_path)
    result = runner.invoke(app, ["search", "quantum_entanglement_xyz", "--db-path", db_path])
    assert result.exit_code == 0
    assert "no results" in result.output.lower()


def test_search_shows_belief(tmp_path):
    """Search results should include prior or belief values."""
    db_path = _publish_galileo_typst(tmp_path)
    # Content is in Chinese; use CJK LIKE fallback search
    result = runner.invoke(app, ["search", "重量", "--db-path", db_path])
    assert result.exit_code == 0
    assert "prior" in result.output.lower() or "belief" in result.output.lower()
