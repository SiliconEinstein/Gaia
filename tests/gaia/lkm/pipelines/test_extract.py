"""Tests for pipelines/extract.py — run_extract end-to-end."""

from pathlib import Path

import pytest

from gaia.lkm.pipelines.extract import run_extract, run_extract_from_dir
from gaia.lkm.storage import StorageConfig, StorageManager

PAPERS_DIR = Path("tests/fixtures/inputs/papers")


def _load_xmls(paper_id: str) -> tuple[str, str, str]:
    d = PAPERS_DIR / paper_id
    return (
        (d / "review.xml").read_text(encoding="utf-8"),
        (d / "reasoning_chain.xml").read_text(encoding="utf-8"),
        (d / "select_conclusion.xml").read_text(encoding="utf-8"),
    )


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "test.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


class TestRunExtract:
    async def test_single_paper(self, storage):
        """run_extract should extract + integrate a single paper."""
        review, reasoning, select = _load_xmls("363056a0")
        result = await run_extract(review, reasoning, select, "363056a0", storage)

        assert len(result.new_global_variables) > 0
        assert len(result.new_global_factors) > 0
        assert len(result.bindings) > 0

    async def test_two_papers_sequential(self, storage):
        """Two sequential run_extract calls should both succeed."""
        for paper_id in ["363056a0", "Sak-1977"]:
            review, reasoning, select = _load_xmls(paper_id)
            result = await run_extract(review, reasoning, select, paper_id, storage)
            assert len(result.new_global_variables) > 0

        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        assert local_count > 0
        assert global_count > 0

    async def test_from_dir(self, storage):
        """run_extract_from_dir should work with fixture directories."""
        result = await run_extract_from_dir(
            PAPERS_DIR / "363056a0", "363056a0", storage
        )
        assert len(result.new_global_variables) > 0
