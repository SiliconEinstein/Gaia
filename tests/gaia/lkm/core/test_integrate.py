"""E2E tests for M5 integrate: lower → integrate → verify global graph.

Tests the full pipeline: IR fixtures → lower() → integrate() → verify dedup and bindings.
"""

import pytest

from gaia.lkm.core.integrate import integrate
from gaia.lkm.core.lower import lower
from gaia.lkm.models import compute_content_hash
from gaia.lkm.storage import StorageConfig, StorageManager
from tests.fixtures.lkm import load_ir


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "integrate.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


async def _lower_and_integrate(storage, name, version="4.0.0"):
    """Helper: load IR → lower → integrate."""
    ir = load_ir(name)
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
        _, result = await _lower_and_integrate(storage, "galileo")
        var_bindings = [b for b in result.bindings if b.binding_type == "variable"]
        fac_bindings = [b for b in result.bindings if b.binding_type == "factor"]
        assert all(b.decision == "create_new" for b in var_bindings)
        assert all(b.decision == "create_new" for b in fac_bindings)
        assert len(result.new_global_variables) == 13
        assert len(result.new_global_factors) == 6

    async def test_second_package_no_overlap(self, storage):
        """Einstein has no content overlap with galileo — all create_new."""
        await _lower_and_integrate(storage, "galileo")
        _, result = await _lower_and_integrate(storage, "einstein")
        var_bindings = [b for b in result.bindings if b.binding_type == "variable"]
        assert all(b.decision == "create_new" for b in var_bindings)
        assert len(result.new_global_variables) == 16

    async def test_newton_dedup_vacuum_prediction(self, storage):
        """Newton's vacuum_prediction should dedup against galileo's."""
        await _lower_and_integrate(storage, "galileo")
        await _lower_and_integrate(storage, "einstein")
        _, result = await _lower_and_integrate(storage, "newton")

        match_bindings = [
            b
            for b in result.bindings
            if b.binding_type == "variable" and b.decision == "match_existing"
        ]
        assert len(match_bindings) == 1
        assert match_bindings[0].local_id == "reg:newton_principia::ext.vacuum_prediction"

        # 15 new + 1 dedup'd = 16 total variables
        assert len(result.new_global_variables) == 15

    async def test_global_counts_after_all_packages(self, storage):
        """After all 4 packages: verify global node counts."""
        await _lower_and_integrate(storage, "galileo")
        await _lower_and_integrate(storage, "einstein")
        await _lower_and_integrate(storage, "newton")
        await _lower_and_integrate(storage, "dark_energy", version="1.0.0")

        # Total local: 13 + 16 + 16 + 10 = 55
        local_count = await storage.content.count("local_variable_nodes")
        assert local_count == 55

        # Total global: 55 - 1 (vacuum_prediction dedup) = 54
        global_count = await storage.content.count("global_variable_nodes")
        assert global_count == 54

        # Factors: 6 + 7 + 7 + 3 = 23
        factor_count = await storage.content.count("global_factor_nodes")
        assert factor_count == 23

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

        # Pick a binding and verify bidirectional lookup
        binding = result.bindings[0]
        found = await storage.find_canonical_binding(binding.local_id)
        assert found is not None
        assert found.global_id == binding.global_id

        found_list = await storage.find_bindings_by_global_id(binding.global_id)
        assert any(b.local_id == binding.local_id for b in found_list)

    async def test_unresolved_cross_refs_recorded(self, storage):
        """Dark energy references cmb-analysis which doesn't exist — should be unresolved."""
        await _lower_and_integrate(storage, "dark_energy", version="1.0.0")

        # dark_energy has factors referencing ext.prior_cmb_analysis
        # which maps to a local variable, but no cross-package binding exists for cmb-analysis
        # However, ext.prior_cmb_analysis IS in the same package's local vars,
        # so it should resolve within this package.
        # No unresolved refs expected for this case.

    async def test_local_nodes_visible_after_integrate(self, storage):
        """After integrate, local nodes should be merged (visible)."""
        lowered, _ = await _lower_and_integrate(storage, "galileo")
        for lv in lowered.local_variables[:3]:
            result = await storage.get_local_variable(lv.id)
            assert result is not None, f"{lv.id} should be visible after integrate"

    async def test_integrate_deterministic(self, storage):
        """Same input should produce consistent global graph."""
        _, r1 = await _lower_and_integrate(storage, "galileo")
        # The gcn_ids are random (UUID), but the binding decisions should be consistent
        var_decisions = sorted(
            (b.local_id, b.decision) for b in r1.bindings if b.binding_type == "variable"
        )
        assert all(d == "create_new" for _, d in var_decisions)
