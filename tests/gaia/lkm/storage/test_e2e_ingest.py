"""E2E test: ingest galileo → einstein → newton, verify dedup on shared content.

Uses real knowledge content from Typst v4 test packages.
Newton's package references Galileo's vacuum_prediction claim — after both
are ingested, content_hash dedup should merge them into one global variable.
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


@pytest.fixture
async def storage(tmp_path):
    config = StorageConfig(lancedb_path=str(tmp_path / "e2e.lance"))
    mgr = StorageManager(config)
    await mgr.initialize()
    return mgr


# ── Fixture data from Typst v4 packages ──

GALILEO_CLAIMS = [
    ("heavier_falls_faster", "物体下落的速度与其重量成正比——重者下落更快。"),
    (
        "composite_is_slower",
        '假设"重者下落更快"，将重球与轻球绑成复合体，则复合体的下落速度慢于重球单独下落。',
    ),
    (
        "composite_is_faster",
        '假设"重者下落更快"，将重球与轻球绑成复合体，则复合体的下落速度快于重球单独下落。',
    ),
    ("vacuum_prediction", "在真空中，不同重量的物体应以相同速率下落。"),
]

EINSTEIN_CLAIMS = [
    (
        "equivalence_principle",
        "在足够小的时空区域内，均匀引力场的效应与匀加速参考系的效应不可区分。",
    ),
    ("light_bends_in_gravity", "光线在引力场中会发生弯曲。"),
    ("gr_light_deflection", "广义相对论预测：光线掠过太阳表面时偏折1.75角秒。"),
]

# Newton's vacuum_prediction has SAME content as Galileo's
NEWTON_CLAIMS = [
    (
        "second_law",
        "牛顿第二定律：物体所受合外力等于其惯性质量与加速度的乘积。F = m_i a",
    ),
    (
        "law_of_gravity",
        "万有引力定律：两个物体之间的引力与两者质量之积成正比，与距离的平方成反比。",
    ),
    (
        "freefall_acceleration",
        "在地球表面附近，任何物体的自由落体加速度都等于g≈9.8m/s²，与物体质量无关。",
    ),
    ("vacuum_prediction", "在真空中，不同重量的物体应以相同速率下落。"),
]


def _build_local_vars(claims: list[tuple[str, str]], package: str) -> list[LocalVariableNode]:
    """Build LocalVariableNode list from (label, content) pairs."""
    nodes = []
    for label, content in claims:
        qid = f"reg:{package}::{label}"
        ch = compute_content_hash("claim", content, [])
        nodes.append(
            LocalVariableNode(
                id=qid,
                type="claim",
                visibility="public",
                content=content,
                content_hash=ch,
                parameters=[],
                source_package=package,
            )
        )
    return nodes


def _build_simple_factor(
    package: str, premise_label: str, conclusion_label: str
) -> LocalFactorNode:
    """Build a simple infer factor between two claims in the same package."""
    return LocalFactorNode(
        id=f"lfac_{package}_{premise_label}_{conclusion_label}",
        factor_type="strategy",
        subtype="infer",
        premises=[f"reg:{package}::{premise_label}"],
        conclusion=f"reg:{package}::{conclusion_label}",
        source_package=package,
    )


async def _ingest_and_integrate(
    storage: StorageManager,
    package: str,
    version: str,
    local_vars: list[LocalVariableNode],
    local_factors: list[LocalFactorNode],
) -> tuple[list[GlobalVariableNode], list[CanonicalBinding]]:
    """Full ingest→commit→integrate flow. Returns new globals and bindings."""
    # Step 1: write local nodes (preparing)
    await storage.ingest_local_graph(package, version, local_vars, local_factors)

    # Step 2: commit (preparing → merged)
    await storage.commit_package(package)

    # Step 3: integrate — check dedup for each local variable
    new_globals = []
    all_bindings = []

    for lv in local_vars:
        existing = await storage.find_global_by_content_hash(lv.content_hash)
        ref = LocalCanonicalRef(local_id=lv.id, package_id=package, version=version)

        if existing is not None:
            # match_existing: append to local_members
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
                    package_id=package,
                    version=version,
                    decision="match_existing",
                    reason="content_hash exact match",
                )
            )
        else:
            # create_new
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
                    package_id=package,
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
        Newton's vacuum_prediction should dedup against Galileo's.
        """
        galileo_vars = _build_local_vars(GALILEO_CLAIMS, "galileo_falling_bodies")
        galileo_factors = [
            _build_simple_factor(
                "galileo_falling_bodies",
                "heavier_falls_faster",
                "composite_is_slower",
            ),
        ]
        einstein_vars = _build_local_vars(EINSTEIN_CLAIMS, "einstein_gravity")
        newton_vars = _build_local_vars(NEWTON_CLAIMS, "newton_principia")

        # ── Ingest galileo ──
        g_globals, g_bindings = await _ingest_and_integrate(
            storage,
            "galileo_falling_bodies",
            "4.0.0",
            galileo_vars,
            galileo_factors,
        )
        assert len(g_globals) == 4, "All galileo claims should be new globals"
        assert all(b.decision == "create_new" for b in g_bindings)

        # ── Ingest einstein ──
        e_globals, e_bindings = await _ingest_and_integrate(
            storage, "einstein_gravity", "4.0.0", einstein_vars, []
        )
        assert len(e_globals) == 3, "All einstein claims should be new (no overlap)"
        assert all(b.decision == "create_new" for b in e_bindings)

        # ── Ingest newton ──
        n_globals, n_bindings = await _ingest_and_integrate(
            storage, "newton_principia", "4.0.0", newton_vars, []
        )
        # 3 new + 1 existing (vacuum_prediction matches galileo's)
        assert len(n_globals) == 3, "3 unique newton claims create new globals"

        match_bindings = [b for b in n_bindings if b.decision == "match_existing"]
        assert len(match_bindings) == 1, "vacuum_prediction should match galileo's"
        assert match_bindings[0].local_id == "reg:newton_principia::vacuum_prediction"

        # ── Verify final state ──
        # Total globals: 4 (galileo) + 3 (einstein) + 3 (newton unique) = 10
        global_count = await storage.content.count("global_variable_nodes")
        assert global_count == 10

        # Total local vars: 4 + 3 + 4 = 11
        local_count = await storage.content.count("local_variable_nodes")
        assert local_count == 11

        # vacuum_prediction global node should have 2 local members
        vac_hash = compute_content_hash("claim", "在真空中，不同重量的物体应以相同速率下落。", [])
        vac_global = await storage.find_global_by_content_hash(vac_hash)
        assert vac_global is not None
        assert len(vac_global.local_members) == 2
        member_ids = {m.local_id for m in vac_global.local_members}
        assert "reg:galileo_falling_bodies::vacuum_prediction" in member_ids
        assert "reg:newton_principia::vacuum_prediction" in member_ids

        # ── Verify all local nodes are merged ──
        for pkg in [
            "galileo_falling_bodies",
            "einstein_gravity",
            "newton_principia",
        ]:
            vars_ = await storage.content.get_local_variables_by_package(pkg, merged_only=True)
            assert len(vars_) > 0, f"{pkg} should have merged local vars"

    async def test_preparing_invisible_during_ingest(self, storage):
        """During ingest (before commit), local nodes should not appear in reads."""
        galileo_vars = _build_local_vars(GALILEO_CLAIMS[:1], "galileo_test")
        await storage.ingest_local_graph("galileo_test", "1.0.0", galileo_vars, [])

        # Before commit — invisible
        result = await storage.get_local_variable("reg:galileo_test::heavier_falls_faster")
        assert result is None

        # After commit — visible
        await storage.commit_package("galileo_test")
        result = await storage.get_local_variable("reg:galileo_test::heavier_falls_faster")
        assert result is not None
