"""E2E tests for M4 extraction: paper XMLs → LKM local nodes.

Uses real paper fixtures from tests/fixtures/inputs/papers/.
"""

from pathlib import Path

import pytest

from gaia.lkm.core.extract import extract
from gaia.lkm.core.integrate import integrate
from gaia.lkm.storage import StorageConfig, StorageManager

PAPERS_DIR = Path("tests/fixtures/inputs/papers")

# Papers that have all 3 XML files
PAPER_IDS = [
    "10.1038332139a0_1988_Natu",
    "363056a0",
    "10.1038s41467-021-25372-2",
    "Sak-1977",
    "2512_Superconductivity",
]


def _load_paper_xmls(paper_id: str) -> tuple[str, str, str]:
    d = PAPERS_DIR / paper_id
    return (
        (d / "review.xml").read_text(encoding="utf-8"),
        (d / "reasoning_chain.xml").read_text(encoding="utf-8"),
        (d / "select_conclusion.xml").read_text(encoding="utf-8"),
    )


class TestExtraction:
    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_extracts_premises(self, paper_id):
        """Should extract at least one premise from review.xml."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        claims = [v for v in result.local_variables if v.type == "claim"]
        assert len(claims) > 0, f"{paper_id}: no claims extracted"

    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_extracts_factors(self, paper_id):
        """Should extract at least one strategy factor."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        assert len(result.local_factors) > 0, f"{paper_id}: no factors extracted"

    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_extracts_priors(self, paper_id):
        """Should extract prior_probability from premises."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        assert len(result.prior_records) > 0, f"{paper_id}: no priors extracted"
        for pr in result.prior_records:
            assert 0.001 <= pr.value <= 0.999, f"Prior {pr.value} not Cromwell clamped"

    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_qid_format(self, paper_id):
        """QIDs should use paper:{metadata_id}::{name} format."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        for v in result.local_variables:
            assert v.id.startswith(f"paper:{paper_id}::"), f"Bad QID: {v.id}"

    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_package_id_format(self, paper_id):
        """Package ID should be paper:{metadata_id}."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        assert result.package_id == f"paper:{paper_id}"

    @pytest.mark.parametrize("paper_id", PAPER_IDS)
    def test_source_class_heuristic(self, paper_id):
        """All param sources should be heuristic."""
        review, reasoning, select = _load_paper_xmls(paper_id)
        result = extract(review, reasoning, select, paper_id)
        for ps in result.param_sources:
            assert ps.source_class == "heuristic"

    def test_deterministic(self):
        """Same input should produce same output."""
        review, reasoning, select = _load_paper_xmls("363056a0")
        r1 = extract(review, reasoning, select, "363056a0")
        r2 = extract(review, reasoning, select, "363056a0")
        assert [v.id for v in r1.local_variables] == [v.id for v in r2.local_variables]
        assert [f.id for f in r1.local_factors] == [f.id for f in r2.local_factors]

    def test_version_is_1_0_0(self):
        """Papers always version 1.0.0."""
        review, reasoning, select = _load_paper_xmls("363056a0")
        result = extract(review, reasoning, select, "363056a0")
        assert result.version == "1.0.0"
        for v in result.local_variables:
            assert v.version == "1.0.0"

    def test_factors_have_steps(self):
        """Strategy factors should have reasoning steps."""
        review, reasoning, select = _load_paper_xmls("363056a0")
        result = extract(review, reasoning, select, "363056a0")
        for f in result.local_factors:
            assert f.steps is not None and len(f.steps) > 0


class TestExtractionIntegrate:
    """Test extraction + integrate E2E."""

    @pytest.fixture
    async def storage(self, tmp_path):
        config = StorageConfig(lancedb_path=str(tmp_path / "paper.lance"))
        mgr = StorageManager(config)
        await mgr.initialize()
        return mgr

    async def test_extract_and_integrate(self, storage):
        """Extract a paper, integrate it, verify it's queryable."""
        review, reasoning, select = _load_paper_xmls("363056a0")
        result = extract(review, reasoning, select, "363056a0")

        ir = await integrate(
            storage,
            result.package_id,
            result.version,
            result.local_variables,
            result.local_factors,
            result.prior_records,
            param_sources=result.param_sources,
        )

        # Should have created global nodes
        assert len(ir.new_global_variables) > 0
        assert len(ir.new_global_factors) > 0

        # Verify data is queryable
        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        assert local_count == len(result.local_variables)
        assert global_count == len(result.local_variables)  # first paper, no dedup

    async def test_two_papers_no_dedup(self, storage):
        """Two different papers should not dedup (different content)."""
        for paper_id in ["363056a0", "Sak-1977"]:
            review, reasoning, select = _load_paper_xmls(paper_id)
            result = extract(review, reasoning, select, paper_id)
            await integrate(
                storage,
                result.package_id,
                result.version,
                result.local_variables,
                result.local_factors,
                result.prior_records,
                param_sources=result.param_sources,
            )

        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        # No dedup expected — different papers have different content
        assert local_count == global_count
