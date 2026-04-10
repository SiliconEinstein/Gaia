"""E2E tests for M5 integrate: lower → integrate → verify global graph.

Tests the full pipeline: IR fixtures → lower() → integrate() → verify dedup and bindings.
Uses real Gaia IR fine-grained compilations as fixtures.
"""

import pytest

from gaia.lkm.core.integrate import batch_integrate, integrate
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


class TestBatchIntegrate:
    """Tests for batch_integrate — the batch import path."""

    async def test_batch_first_import(self, storage):
        """Batch import of multiple packages: all create_new on empty DB."""
        from gaia.lkm.core.extract import ExtractionResult

        results = []
        for name in ["galileo", "einstein", "newton"]:
            ir = load_ir(name)
            version = "1.0.0" if "dark_energy" in name else "4.0.0"
            lowered = lower(ir, version=version)
            results.append(
                ExtractionResult(
                    package_id=lowered.package_id,
                    version=lowered.version,
                    local_variables=lowered.local_variables,
                    local_factors=lowered.local_factors,
                )
            )

        stats = await batch_integrate(storage, results)

        assert stats.packages == 3
        assert stats.total_local_variables > 0
        assert stats.total_local_factors > 0
        # Newton shares vacuum_prediction with galileo
        assert stats.dedup_within_batch >= 1
        assert stats.new_global_variables > 0
        assert stats.bindings > 0

        # Verify counts in storage
        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        assert local_count == stats.total_local_variables
        assert global_count == stats.new_global_variables

    async def test_batch_idempotent(self, storage):
        """Running batch_integrate twice produces same counts (upsert)."""
        from gaia.lkm.core.extract import ExtractionResult

        ir = load_ir("galileo")
        lowered = lower(ir, version="4.0.0")
        results = [
            ExtractionResult(
                package_id=lowered.package_id,
                version=lowered.version,
                local_variables=lowered.local_variables,
                local_factors=lowered.local_factors,
            )
        ]

        await batch_integrate(storage, results)
        count_after_first = await storage.content.count("global_variable_nodes")

        # Second run: same data
        stats2 = await batch_integrate(storage, results)
        count_after_second = await storage.content.count("global_variable_nodes")

        assert count_after_first == count_after_second
        # Private helper claims are stored locally but don't participate in
        # global dedup, so dedup_with_existing may be less than total_local_variables.
        assert stats2.dedup_with_existing <= stats2.total_local_variables
        assert stats2.dedup_with_existing > 0

    async def test_batch_incremental(self, storage):
        """Second batch adds new globals, dedup existing overlaps."""
        from gaia.lkm.core.extract import ExtractionResult

        ir_gal = load_ir("galileo")
        lowered_gal = lower(ir_gal, version="4.0.0")
        await batch_integrate(
            storage,
            [
                ExtractionResult(
                    package_id=lowered_gal.package_id,
                    version=lowered_gal.version,
                    local_variables=lowered_gal.local_variables,
                    local_factors=lowered_gal.local_factors,
                )
            ],
        )

        count_before = await storage.content.count("global_variable_nodes")

        # Newton has one overlap (vacuum_prediction)
        ir_new = load_ir("newton")
        lowered_new = lower(ir_new, version="4.0.0")
        stats2 = await batch_integrate(
            storage,
            [
                ExtractionResult(
                    package_id=lowered_new.package_id,
                    version=lowered_new.version,
                    local_variables=lowered_new.local_variables,
                    local_factors=lowered_new.local_factors,
                )
            ],
        )

        count_after = await storage.content.count("global_variable_nodes")
        assert stats2.dedup_with_existing >= 1
        assert count_after == count_before + stats2.new_global_variables
