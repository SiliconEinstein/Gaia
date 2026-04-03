"""IR fixture smoke tests for gaia.bp.

These fixtures are legacy Typst-v4 examples, but their checked-in
``local_canonical_graph.json`` snapshots are current Gaia IR. The goal here is
to lock the minimal structural contract:

- the IR fixture validates under the current ``gaia.ir`` models
- it lowers to a BP factor graph without structural errors
- loopy BP runs to convergence on the lowered graph
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gaia.bp import BeliefPropagation, lower_local_graph
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "ir"
PACKAGES = [
    "galileo_falling_bodies_v4",
    "newton_principia_v4",
    "einstein_gravity_v4",
    "dark_energy_v4",
]
PROFILES = ["gaia_ir_coarse", "gaia_ir_fine"]


def _load_fixture(package: str, profile: str) -> LocalCanonicalGraph:
    path = FIXTURES / package / profile / "local_canonical_graph.json"
    return LocalCanonicalGraph.model_validate_json(path.read_text())


@pytest.mark.parametrize("package", PACKAGES)
@pytest.mark.parametrize("profile", PROFILES)
def test_ir_fixture_validates_and_runs_bp(package: str, profile: str) -> None:
    graph = _load_fixture(package, profile)

    validation = validate_local_graph(graph)
    assert not validation.errors, f"{package}/{profile}: {validation.errors}"

    fg = lower_local_graph(graph)
    assert not fg.validate(), f"{package}/{profile}: invalid factor graph"

    result = BeliefPropagation(damping=0.5, max_iterations=100).run(fg)

    assert result.diagnostics.converged, f"{package}/{profile}: BP did not converge"
    assert len(result.beliefs) == len(fg.variables)
    assert all(0.0 <= belief <= 1.0 for belief in result.beliefs.values())
    assert any(abs(belief - 0.5) > 1e-6 for belief in result.beliefs.values()), (
        f"{package}/{profile}: BP stayed at the uniform prior everywhere"
    )
