"""E2E test: ingest galileo → einstein → newton, verify dedup on shared content.

Uses JSON fixture data from tests/fixtures/lkm/ (derived from Typst v4 packages).
Newton references Galileo's vacuum_prediction — content_hash dedup should merge them.
"""

import pytest

from gaia.lkm.models import (
    CanonicalBinding,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    compute_content_hash,
    new_gcn_id,
)
from gaia.lkm.storage import StorageConfig, StorageManager
from tests.fixtures.lkm import load_package


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "e2e.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


async def _ingest_and_integrate(
    storage: StorageManager,
    package_id: str,
    version: str,
    local_vars: list[LocalVariableNode],
    local_factors: list[LocalFactorNode],
) -> tuple[list[GlobalVariableNode], list[CanonicalBinding]]:
    """Full ingest→commit→integrate flow. Returns new globals and bindings."""
    await storage.ingest_local_graph(package_id, version, local_vars, local_factors)
    await storage.commit_package(package_id, version)

    new_globals = []
    all_bindings = []

    for lv in local_vars:
        existing = await storage.find_global_by_content_hash(lv.content_hash)
        ref = LocalCanonicalRef(local_id=lv.id, package_id=package_id, version=version)

        if existing is not None:
            updated_members = existing.local_members + [ref]
            updated = GlobalVariableNode(
                id=existing.id,
                type=existing.type,
                visibility=existing.visibility,
                content_hash=existing.content_hash,
                parameters=existing.parameters,
                representative_lcn=existing.representative_lcn,
                local_members=updated_members,
            )
            await storage.update_global_variable_members(existing.id, updated)
            all_bindings.append(
                CanonicalBinding(
                    local_id=lv.id,
                    global_id=existing.id,
                    binding_type="variable",
                    package_id=package_id,
                    version=version,
                    decision="match_existing",
                    reason="content_hash exact match",
                )
            )
        else:
            gcn_id = new_gcn_id()
            gv = GlobalVariableNode(
                id=gcn_id,
                type=lv.type,
                visibility=lv.visibility,
                content_hash=lv.content_hash,
                parameters=lv.parameters,
                representative_lcn=ref,
                local_members=[ref],
            )
            new_globals.append(gv)
            all_bindings.append(
                CanonicalBinding(
                    local_id=lv.id,
                    global_id=gcn_id,
                    binding_type="variable",
                    package_id=package_id,
                    version=version,
                    decision="create_new",
                    reason="no matching global node",
                )
            )

    await storage.integrate_global_graph(new_globals, [], all_bindings)
    return new_globals, all_bindings


class TestE2EIngest:
    async def test_three_package_ingest_with_dedup(self, storage):
        """Ingest galileo → einstein → newton.
        Newton's vacuum_prediction dedup's against Galileo's.
        """
        galileo = load_package("galileo")
        einstein = load_package("einstein")
        newton = load_package("newton")

        # ── Ingest galileo ──
        g_globals, g_bindings = await _ingest_and_integrate(
            storage,
            galileo.package_id,
            galileo.version,
            galileo.local_variables,
            galileo.local_factors,
        )
        assert len(g_globals) == len(galileo.local_variables)
        assert all(b.decision == "create_new" for b in g_bindings)

        # ── Ingest einstein ──
        e_globals, e_bindings = await _ingest_and_integrate(
            storage,
            einstein.package_id,
            einstein.version,
            einstein.local_variables,
            einstein.local_factors,
        )
        assert len(e_globals) == len(einstein.local_variables)
        assert all(b.decision == "create_new" for b in e_bindings)

        # ── Ingest newton ──
        n_globals, n_bindings = await _ingest_and_integrate(
            storage,
            newton.package_id,
            newton.version,
            newton.local_variables,
            newton.local_factors,
        )
        match_bindings = [b for b in n_bindings if b.decision == "match_existing"]
        create_bindings = [b for b in n_bindings if b.decision == "create_new"]
        assert len(match_bindings) == 1, "vacuum_prediction should match galileo's"
        assert match_bindings[0].local_id == "reg:newton_principia::ext.vacuum_prediction"
        assert len(create_bindings) == len(newton.local_variables) - 1

        # ── Verify final counts ──
        total_local = (
            len(galileo.local_variables)
            + len(einstein.local_variables)
            + len(newton.local_variables)
        )
        total_global = total_local - 1  # one dedup'd

        local_count = await storage.content.count("local_variable_nodes")
        global_count = await storage.content.count("global_variable_nodes")
        assert local_count == total_local
        assert global_count == total_global

        # ── Verify vacuum_prediction has 2 local members ──
        vac_hash = compute_content_hash("claim", "在真空中，不同重量的物体应以相同速率下落。", [])
        vac_global = await storage.find_global_by_content_hash(vac_hash)
        assert vac_global is not None
        assert len(vac_global.local_members) == 2
        member_ids = {m.local_id for m in vac_global.local_members}
        assert "reg:galileo_falling_bodies::galileo.vacuum_prediction" in member_ids
        assert "reg:newton_principia::ext.vacuum_prediction" in member_ids

        # ── Verify factors were ingested ──
        total_factors = (
            len(galileo.local_factors) + len(einstein.local_factors) + len(newton.local_factors)
        )
        factor_count = await storage.content.count("local_factor_nodes")
        assert factor_count == total_factors

    async def test_preparing_invisible_during_ingest(self, storage):
        """During ingest (before commit), local nodes should not appear in reads."""
        galileo = load_package("galileo")
        await storage.ingest_local_graph(
            galileo.package_id,
            galileo.version,
            galileo.local_variables[:1],
            [],
        )

        # Before commit — invisible
        result = await storage.get_local_variable(galileo.local_variables[0].id)
        assert result is None

        # After commit — visible
        await storage.commit_package(galileo.package_id, galileo.version)
        result = await storage.get_local_variable(galileo.local_variables[0].id)
        assert result is not None
