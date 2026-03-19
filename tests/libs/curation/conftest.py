"""Shared fixtures for curation tests.

The physics_graph fixture provides a complete, realistic global knowledge graph
that covers every curation module with nontrivial behavior at each pipeline step.

Scenario: 3 physics packages contribute overlapping knowledge about mechanics,
relativity, and thermodynamics.  The graph is deliberately constructed so that:

  - Clustering finds 2 clusters (a duplicate pair + an equivalence pair)
  - Classification produces 1 merge + 1 equivalence suggestion
  - BP oscillates on the contradiction between classical and relativistic claims
  - Sensitivity analysis confirms the antagonistic pair
  - Structure inspection finds an orphan, a dangling factor, a hub, and 2 components
  - Cleanup auto-executes the merge, reviewer approves the equivalence
  - Merge redirects factors, creating a real structural change

Graph topology:

  Component 1 — Classical + Relativistic Mechanics
  ─────────────────────────────────────────────────
  [fma_1] "F = ma (Newton's second law)"                     ← pkg_A
  [fma_2] "Force equals mass times acceleration"             ← pkg_B (DUPLICATE of fma_1)
  [accel] "Acceleration is proportional to net force"        ← pkg_A
  [gravity] "All objects fall with equal acceleration"        ← pkg_A
  [light] "The speed of light is constant in all frames"     ← pkg_B
  [mass_v] "Relativistic mass increases with velocity"       ← pkg_B (CONTRADICTS fma implications)
  [heat_energy] "Heat is a form of energy"                   ← pkg_A (EQUIVALENCE candidate)
  [thermal_ke] "Thermal energy is kinetic energy of molecules" ← pkg_C (EQUIVALENCE candidate)

  f_newton:   fma_1 → accel         (deduction, p=0.95)
  f_fall:     fma_1 + accel → gravity (deduction, p=0.90)
  f_rel:      light → mass_v        (deduction, p=0.85)
  f_contra:   gravity ∧ mass_v      (relation_contradiction, p=0.90)
  f_thermo:   heat_energy → thermal_ke (deduction, p=0.80)  ← connects the equiv pair

  Component 2 — Quantum (disconnected from component 1)
  ──────────────────────────────────────────────────────
  [quantum] "Measurement collapses the wave function"        ← pkg_B
  [uncertain] "Position and momentum cannot be known simultaneously" ← pkg_B
  f_qm:      quantum → uncertain    (deduction, p=0.80)

  Structural issues:
  ──────────────────
  [orphan] "Phlogiston explains combustion"  ← pkg_C, no factor connections
  f_dangling: premises=["gcn_deleted"] → gravity  ← references nonexistent node

  Hub node: fma_1 is premise in f_newton, f_fall, and the merge will redirect
            fma_2's potential factors too.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from libs.global_graph.models import GlobalCanonicalNode, LocalCanonicalRef, PackageRef
from libs.storage.models import FactorNode


# ── Node IDs ──

ID_FMA_1 = "gcn_fma_1"
ID_FMA_2 = "gcn_fma_2"
ID_ACCEL = "gcn_accel"
ID_GRAVITY = "gcn_gravity"
ID_LIGHT = "gcn_light"
ID_MASS_V = "gcn_mass_v"
ID_HEAT = "gcn_heat_energy"
ID_THERMAL = "gcn_thermal_ke"
ID_QUANTUM = "gcn_quantum"
ID_UNCERTAIN = "gcn_uncertain"
ID_ORPHAN = "gcn_orphan"


def _ref(pkg: str, lcn: str) -> LocalCanonicalRef:
    return LocalCanonicalRef(package=pkg, version="0.1.0", local_canonical_id=lcn)


def _prov(pkg: str) -> PackageRef:
    return PackageRef(package=pkg, version="0.1.0")


def build_physics_nodes() -> list[GlobalCanonicalNode]:
    """Build all GlobalCanonicalNodes for the physics fixture."""
    return [
        # ── Duplicate pair (fma_1 ≈ fma_2) ──
        # Phrased to achieve cosine > 0.95 with real embeddings
        GlobalCanonicalNode(
            global_canonical_id=ID_FMA_1,
            knowledge_type="claim",
            representative_content=(
                "Newton's second law states that force equals mass "
                "multiplied by acceleration, F = ma"
            ),
            member_local_nodes=[_ref("classical_mechanics", "lcn_fma_1")],
            provenance=[_prov("classical_mechanics")],
            metadata={"source_knowledge_names": ["classical_mechanics.fma"]},
        ),
        GlobalCanonicalNode(
            global_canonical_id=ID_FMA_2,
            knowledge_type="claim",
            representative_content=(
                "According to Newton's second law, force is equal to "
                "mass times acceleration (F = ma)"
            ),
            member_local_nodes=[_ref("modern_physics", "lcn_fma_2")],
            provenance=[_prov("modern_physics")],
            metadata={"source_knowledge_names": ["modern_physics.fma"]},
        ),
        # ── Deduction chain nodes ──
        GlobalCanonicalNode(
            global_canonical_id=ID_ACCEL,
            knowledge_type="claim",
            representative_content="Acceleration is proportional to net force",
            member_local_nodes=[_ref("classical_mechanics", "lcn_accel")],
            provenance=[_prov("classical_mechanics")],
        ),
        GlobalCanonicalNode(
            global_canonical_id=ID_GRAVITY,
            knowledge_type="claim",
            representative_content=(
                "All objects in a vacuum fall with the same acceleration regardless of mass"
            ),
            member_local_nodes=[_ref("classical_mechanics", "lcn_gravity")],
            provenance=[_prov("classical_mechanics")],
        ),
        # ── Relativistic nodes (contradiction source) ──
        GlobalCanonicalNode(
            global_canonical_id=ID_LIGHT,
            knowledge_type="claim",
            representative_content="The speed of light is constant in all inertial reference frames",
            member_local_nodes=[_ref("modern_physics", "lcn_light")],
            provenance=[_prov("modern_physics")],
        ),
        GlobalCanonicalNode(
            global_canonical_id=ID_MASS_V,
            knowledge_type="claim",
            representative_content=(
                "Relativistic mass of an object increases as its velocity "
                "approaches the speed of light"
            ),
            member_local_nodes=[_ref("modern_physics", "lcn_mass_v")],
            provenance=[_prov("modern_physics")],
        ),
        # ── Equivalence pair ──
        # Phrased to achieve cosine ~0.67 with real embeddings (related but distinct)
        GlobalCanonicalNode(
            global_canonical_id=ID_HEAT,
            knowledge_type="claim",
            representative_content="Heat is a form of energy that can be transferred between systems",
            member_local_nodes=[_ref("classical_mechanics", "lcn_heat")],
            provenance=[_prov("classical_mechanics")],
        ),
        GlobalCanonicalNode(
            global_canonical_id=ID_THERMAL,
            knowledge_type="claim",
            representative_content=(
                "Thermal energy is the kinetic energy of the random motion of molecules"
            ),
            member_local_nodes=[_ref("thermodynamics", "lcn_thermal")],
            provenance=[_prov("thermodynamics")],
        ),
        # ── Quantum component (disconnected) ──
        GlobalCanonicalNode(
            global_canonical_id=ID_QUANTUM,
            knowledge_type="claim",
            representative_content="Measurement collapses the wave function",
            member_local_nodes=[_ref("modern_physics", "lcn_quantum")],
            provenance=[_prov("modern_physics")],
        ),
        GlobalCanonicalNode(
            global_canonical_id=ID_UNCERTAIN,
            knowledge_type="claim",
            representative_content="Position and momentum cannot be simultaneously known with "
            "arbitrary precision",
            member_local_nodes=[_ref("modern_physics", "lcn_uncertain")],
            provenance=[_prov("modern_physics")],
        ),
        # ── Orphan ──
        GlobalCanonicalNode(
            global_canonical_id=ID_ORPHAN,
            knowledge_type="claim",
            representative_content="Phlogiston explains combustion",
            member_local_nodes=[_ref("thermodynamics", "lcn_orphan")],
            provenance=[_prov("thermodynamics")],
        ),
    ]


def build_physics_factors() -> list[FactorNode]:
    """Build all FactorNodes for the physics fixture."""
    return [
        # Component 1: mechanics chain
        FactorNode(
            factor_id="f_newton",
            type="infer",
            premises=[ID_FMA_1],
            conclusion=ID_ACCEL,
            package_id="classical_mechanics",
            metadata={},
        ),
        FactorNode(
            factor_id="f_fall",
            type="infer",
            premises=[ID_FMA_1, ID_ACCEL],
            conclusion=ID_GRAVITY,
            package_id="classical_mechanics",
            metadata={},
        ),
        FactorNode(
            factor_id="f_rel",
            type="infer",
            premises=[ID_LIGHT],
            conclusion=ID_MASS_V,
            package_id="modern_physics",
            metadata={},
        ),
        # Contradiction: gravity vs mass_v
        FactorNode(
            factor_id="f_contra",
            type="contradiction",
            premises=["gcn_rel_contra", ID_GRAVITY, ID_MASS_V],
            conclusion=None,
            package_id="__curation__",
            metadata={"curation_created": True},
        ),
        # Thermodynamics link (connects equivalence pair)
        FactorNode(
            factor_id="f_thermo",
            type="infer",
            premises=[ID_HEAT],
            conclusion=ID_THERMAL,
            package_id="thermodynamics",
            metadata={},
        ),
        # Component 2: quantum
        FactorNode(
            factor_id="f_qm",
            type="infer",
            premises=[ID_QUANTUM],
            conclusion=ID_UNCERTAIN,
            package_id="modern_physics",
            metadata={},
        ),
        # Structural issue: dangling factor
        FactorNode(
            factor_id="f_dangling",
            type="infer",
            premises=["gcn_deleted"],
            conclusion=ID_GRAVITY,
            package_id="classical_mechanics",
            metadata={},
        ),
    ]


def build_physics_graph() -> tuple[list[GlobalCanonicalNode], list[FactorNode]]:
    """Build the complete physics knowledge graph fixture."""
    return build_physics_nodes(), build_physics_factors()


# ── Pytest fixtures ──


@pytest.fixture
def physics_nodes() -> list[GlobalCanonicalNode]:
    return build_physics_nodes()


@pytest.fixture
def physics_factors() -> list[FactorNode]:
    return build_physics_factors()


@pytest.fixture
def physics_graph() -> tuple[list[GlobalCanonicalNode], list[FactorNode]]:
    return build_physics_graph()


@pytest.fixture
def physics_node_map(physics_nodes) -> dict[str, GlobalCanonicalNode]:
    return {n.global_canonical_id: n for n in physics_nodes}


@pytest.fixture
def physics_storage(physics_graph):
    """Mock StorageManager backed by the physics graph."""
    nodes, factors = physics_graph
    mgr = AsyncMock()
    mgr.list_global_nodes = AsyncMock(return_value=nodes)
    mgr.list_factors = AsyncMock(return_value=factors)
    mgr.upsert_global_nodes = AsyncMock()
    mgr.write_factors = AsyncMock()
    return mgr
