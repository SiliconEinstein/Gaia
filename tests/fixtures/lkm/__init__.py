"""LKM test fixtures — load package data from JSON files.

Usage:
    from tests.fixtures.lkm import load_package

    pkg = load_package("galileo")
    pkg.package_id      # "galileo_falling_bodies"
    pkg.local_variables  # list[LocalVariableNode]
    pkg.local_factors    # list[LocalFactorNode]
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from gaia.lkm.models import LocalFactorNode, LocalVariableNode

_FIXTURES_DIR = Path(__file__).parent


@dataclass
class PackageFixture:
    package_id: str
    version: str
    local_variables: list[LocalVariableNode] = field(default_factory=list)
    local_factors: list[LocalFactorNode] = field(default_factory=list)


def load_package(name: str) -> PackageFixture:
    """Load a package fixture from JSON by short name (e.g. 'galileo')."""
    path = _FIXTURES_DIR / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return PackageFixture(
        package_id=data["package_id"],
        version=data["version"],
        local_variables=[LocalVariableNode(**v) for v in data["local_variables"]],
        local_factors=[LocalFactorNode(**f) for f in data["local_factors"]],
    )
