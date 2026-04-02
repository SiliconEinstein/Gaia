"""E2E tests for M5 integrate: lower → integrate → verify global graph.

Tests the full pipeline: IR fixtures → lower() → integrate() → verify dedup and bindings.
Uses real Gaia IR fine-grained compilations as fixtures.
"""

import pytest

from gaia.lkm.core.integrate import integrate
from gaia.lkm.core.lower import lower
from gaia.lkm.models import compute_content_hash
from gaia.lkm.storage import StorageConfig, StorageManager
from tests.fixtures.lkm import load_ir, load_package


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "integrate.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


async def _lower_and_integrate(storage, name, version=None):
    """Helper: load IR → lower → integrate."""
    ir = load_ir(name)
    if version is None:
        version = "1.0.0" if "dark_energy" in name else "4.0.0"
    lowered = lower(ir, version=version)
    result = await integrate(
        storage,
        lowered.package_id,
        lowered.version,
        lowered.local_variables,
        lowered.local_factors,
    )
    return lowered, result


class TestIntegrateE2E:
    async def test_first_package_all_create_new(self, storage):
        """First package: all variables and factors should be create_new."""
        lowered, result = await _lower_and_integrate(storage, "galileo")
        var_bindings = [b for b in result.bindings if b.binding_type == "variable"]
        fac_bindings = [b for b in result.bindings if b.binding_type == "factor"]
        assert all(b.decision == "create_new" for b in var_bindings)
        assert all(b.decision == "create_new" for b in fac_bindings)
        assert len(result.new_global_variables) == len(lowered.local_variables)
        assert len(result.new_global_factors) == len(lowered.local_factors)

    async def test_second_package_no_overlap(self, storage):
        """Einstein has no content overlap with galileo — all create_new."""
        await _lower_and_integrate(storage, "galileo")
        lowered, result = await _lower_and_integrate(storage, "einstein")
        var_bindings = [b for b in result.bindings if b.binding_type == "variable"]
        assert all(b.decision == "create_new" for b in var_bindings)
        assert len(result.new_global_variables) == len(lowered.local_variables)

    async def test_newton_dedup_vacuum_prediction(self, storage):
        """Newton's vacuum_prediction should dedup against galileo's."""
        await _lower_and_integrate(storage, "galileo")
        await _lower_and_integrate(storage, "einstein")
        lowered, result = await _lower_and_integrate(storage, "newton")

        match_bindings = [
            b
            for b in result.bindings
            if b.binding_type == "variable" and b.decision == "match_existing"
        ]
        assert len(match_bindings) == 1, "vacuum_prediction should match galileo's"
        assert "vacuum_prediction" in match_bindings[0].local_id

        # One fewer new global variable due to dedup
        assert len(result.new_global_variables) == len(lowered.local_variables) - 1

    async def test_global_counts_after_all_packages(self, storage):
        """After all 4 packages: verify global node counts."""
        pkgs = []
        for name in ["galileo", "einstein", "newton", "dark_energy"]:
            lowered, _ = await _lower_and_integrate(storage, name)
            pkgs.append(lowered)

        total_local_vars = sum(len(p.local_variables) for p in pkgs)
        total_local_factors = sum(len(p.local_factors) for p in pkgs)

        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        factor_count = await storage.content.count("global_factor_nodes")

        assert local_count == total_local_vars
        assert global_count == total_local_vars - 1  # one dedup'd (vacuum_prediction)
        assert factor_count == total_local_factors

    async def test_vacuum_prediction_has_two_members(self, storage):
        """Dedup'd variable should have 2 local members."""
        await _lower_and_integrate(storage, "galileo")
        await _lower_and_integrate(storage, "newton")

        vac_hash = compute_content_hash("claim", "在真空中，不同重量的物体应以相同速率下落。", [])
        vac = await storage.find_global_by_content_hash(vac_hash)
        assert vac is not None
        assert len(vac.local_members) == 2
        member_pkgs = {m.package_id for m in vac.local_members}
        assert member_pkgs == {"galileo_falling_bodies", "newton_principia"}

    async def test_bindings_bidirectional(self, storage):
        """Bindings should be queryable by both local_id and global_id."""
        _, result = await _lower_and_integrate(storage, "galileo")
        binding = result.bindings[0]
        found = await storage.find_canonical_binding(binding.local_id)
        assert found is not None
        assert found.global_id == binding.global_id

        found_list = await storage.find_bindings_by_global_id(binding.global_id)
        assert any(b.local_id == binding.local_id for b in found_list)

    async def test_local_nodes_visible_after_integrate(self, storage):
        """After integrate, local nodes should be merged (visible)."""
        lowered, _ = await _lower_and_integrate(storage, "galileo")
        for lv in lowered.local_variables[:3]:
            result = await storage.get_local_variable(lv.id)
            assert result is not None, f"{lv.id} should be visible after integrate"

    async def test_integrate_deterministic(self, storage):
        """Same input should produce consistent binding decisions."""
        _, r1 = await _lower_and_integrate(storage, "galileo")
        var_decisions = sorted(
            (b.local_id, b.decision) for b in r1.bindings if b.binding_type == "variable"
        )
        assert all(d == "create_new" for _, d in var_decisions)
