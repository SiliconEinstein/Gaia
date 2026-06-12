"""Public materialization APIs for Gaia core.

This module provides stable engine-level entry points for downstream packages
that need Gaia materialization without importing CLI command modules.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from gaia.cli.commands.pkg.lkm_materialize import (
    MaterializedLKMChainPackage,
    MaterializedLKMPackage,
)
from gaia.cli.commands.pkg.lkm_materialize import (
    materialize_lkm_paper_package as _materialize_lkm_paper_package,
)
from gaia.cli.commands.pkg.lkm_materialize import (
    materialize_lkm_reasoning_chain_package as _materialize_lkm_reasoning_chain_package,
)


def materialize_lkm_paper_package(
    payload: dict[str, Any],
    *,
    project_root: Path,
    index_id: str,
    paper_id: str,
    storage_root: Path | None = None,
) -> MaterializedLKMPackage:
    """Write, compile, and return a local Gaia package for an LKM paper graph."""
    return _materialize_lkm_paper_package(
        payload,
        project_root=project_root,
        index_id=index_id,
        paper_id=paper_id,
        storage_root=storage_root,
    )


def materialize_lkm_reasoning_chain_package(
    payload: dict[str, Any],
    *,
    project_root: Path,
    index_id: str,
    claim_id: str,
    max_chains: int | None = None,
    storage_root: Path | None = None,
) -> MaterializedLKMChainPackage:
    """Write, compile, and return a local Gaia package for LKM reasoning chains."""
    return _materialize_lkm_reasoning_chain_package(
        payload,
        project_root=project_root,
        index_id=index_id,
        claim_id=claim_id,
        max_chains=max_chains,
        storage_root=storage_root,
    )


__all__ = [
    "MaterializedLKMChainPackage",
    "MaterializedLKMPackage",
    "materialize_lkm_paper_package",
    "materialize_lkm_reasoning_chain_package",
]
