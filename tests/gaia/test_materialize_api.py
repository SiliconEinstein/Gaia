"""Tests for public materialization APIs exposed from Gaia core."""

from __future__ import annotations

from pathlib import Path

from gaia.engine.materialize import (
    MaterializedLKMChainPackage,
    MaterializedLKMPackage,
    materialize_lkm_paper_package,
    materialize_lkm_reasoning_chain_package,
)
from tests.cli.search.test_lkm_package_e2e import (
    _claim_reasoning_payload_graph_only_dependencies,
    _paper_graph_payload,
)


def test_public_lkm_paper_materialization_api(tmp_path: Path) -> None:
    materialized = materialize_lkm_paper_package(
        _paper_graph_payload(),
        project_root=tmp_path,
        index_id="bohrium",
        paper_id="811827932371615744",
    )

    assert isinstance(materialized, MaterializedLKMPackage)
    assert materialized.source_ref == "lkm:bohrium:paper:811827932371615744"
    assert materialized.root.exists()
    assert materialize_lkm_paper_package.__module__ == "gaia.engine.materialize"


def test_public_lkm_chain_materialization_api(tmp_path: Path) -> None:
    materialized = materialize_lkm_reasoning_chain_package(
        _claim_reasoning_payload_graph_only_dependencies(),
        project_root=tmp_path,
        index_id="bohrium",
        claim_id="gcn_result",
    )

    assert isinstance(materialized, MaterializedLKMChainPackage)
    assert materialized.source_ref == "lkm:bohrium:chain:gcn_result"
    assert materialized.root.exists()
    assert materialize_lkm_reasoning_chain_package.__module__ == "gaia.engine.materialize"
