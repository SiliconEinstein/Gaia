"""LKM test fixtures — load package data from JSON files.

Two formats:
- LKM format (M3 output): load_package("galileo") → PackageFixture
- Gaia IR format (M3 input): load_ir("galileo") → LocalCanonicalGraph

Usage:
    from tests.fixtures.lkm import load_package, load_ir

    pkg = load_package("galileo")       # LKM models
    ir = load_ir("galileo")             # Gaia IR LocalCanonicalGraph
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gaia.gaia_ir.graphs import LocalCanonicalGraph
from gaia.lkm.models import LocalFactorNode, LocalVariableNode

_FIXTURES_DIR = Path(__file__).parent


@dataclass
class PackageFixture:
    package_id: str
    version: str
    local_variables: list[LocalVariableNode] = field(default_factory=list)
    local_factors: list[LocalFactorNode] = field(default_factory=list)


def load_package(name: str) -> PackageFixture:
    """Load an LKM-format fixture (M3 output) by short name."""
    path = _FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    version = data["version"]
    return PackageFixture(
        package_id=data["package_id"],
        version=version,
        local_variables=[
            LocalVariableNode(**{**v, "version": version}) for v in data["local_variables"]
        ],
        local_factors=[LocalFactorNode(**{**f, "version": version}) for f in data["local_factors"]],
    )


def load_ir(name: str) -> LocalCanonicalGraph:
    """Load a Gaia IR fixture (M3 input) by short name."""
    path = _FIXTURES_DIR / f"{name}_ir.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return LocalCanonicalGraph.model_validate(data)
