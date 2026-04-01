"""Seed LKM database with fixture data from 4 Typst v4 packages.

Usage:
    python -m gaia.lkm.api.seed [--db-path ./data/lancedb/lkm]
"""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from gaia.lkm.models import (
    CanonicalBinding,
    GlobalFactorNode,
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalFactorNode,
    LocalVariableNode,
    new_gcn_id,
    new_gfac_id,
)
from gaia.lkm.storage import StorageConfig, StorageManager


def _find_fixtures_dir() -> Path:
    """Find the LKM fixtures directory."""
    # Try relative to repo root
    candidates = [
        Path("tests/fixtures/lkm"),
        Path(__file__).parent.parent.parent.parent / "tests" / "fixtures" / "lkm",
    ]
    for p in candidates:
        if p.exists():
            return p
    raise FileNotFoundError("Cannot find tests/fixtures/lkm/")


def _load_fixture(fixtures_dir: Path, name: str) -> dict:
    """Load a JSON fixture by name."""
    import json

    path = fixtures_dir / f"{name}.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


async def _ingest_package(
    storage: StorageManager,
    package_id: str,
    version: str,
    local_vars: list[LocalVariableNode],
    local_factors: list[LocalFactorNode],
) -> tuple[list[GlobalVariableNode], list[GlobalFactorNode], list[CanonicalBinding]]:
    """Ingest → commit → integrate one package."""
    # 1. Write local nodes (preparing)
    await storage.ingest_local_graph(package_id, version, local_vars, local_factors)

    # 2. Commit (merged)
    await storage.commit_package(package_id, version)

    # 3. Integrate variables — dedup by content_hash
    new_globals = []
    all_bindings = []
    qid_to_gcn: dict[str, str] = {}

    for lv in local_vars:
        existing = await storage.find_global_by_content_hash(lv.content_hash)
        ref = LocalCanonicalRef(local_id=lv.id, package_id=package_id, version=version)

        if existing is not None:
            updated = GlobalVariableNode(
                id=existing.id,
                type=existing.type,
                visibility=existing.visibility,
                content_hash=existing.content_hash,
                parameters=existing.parameters,
                representative_lcn=existing.representative_lcn,
                local_members=existing.local_members + [ref],
            )
            await storage.update_global_variable_members(existing.id, updated)
            qid_to_gcn[lv.id] = existing.id
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
            qid_to_gcn[lv.id] = gcn_id
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

    # 4. Integrate factors — map QIDs to gcn_ids
    new_global_factors = []
    for lf in local_factors:
        mapped_premises = [qid_to_gcn.get(p, p) for p in lf.premises]
        mapped_conclusion = qid_to_gcn.get(lf.conclusion, lf.conclusion)

        # Check if all references resolved
        if any(p.startswith("reg:") for p in mapped_premises) or mapped_conclusion.startswith(
            "reg:"
        ):
            # Unresolved cross-package ref — skip
            continue

        # Check for existing exact match
        existing_factor = await storage.find_global_factor_exact(
            mapped_premises, mapped_conclusion, lf.factor_type, lf.subtype
        )
        if existing_factor:
            all_bindings.append(
                CanonicalBinding(
                    local_id=lf.id,
                    global_id=existing_factor.id,
                    binding_type="factor",
                    package_id=package_id,
                    version=version,
                    decision="match_existing",
                    reason="structure exact match",
                )
            )
        else:
            gfac_id = new_gfac_id()
            gf = GlobalFactorNode(
                id=gfac_id,
                factor_type=lf.factor_type,
                subtype=lf.subtype,
                premises=mapped_premises,
                conclusion=mapped_conclusion,
                representative_lfn=lf.id,
                source_package=package_id,
            )
            new_global_factors.append(gf)
            all_bindings.append(
                CanonicalBinding(
                    local_id=lf.id,
                    global_id=gfac_id,
                    binding_type="factor",
                    package_id=package_id,
                    version=version,
                    decision="create_new",
                    reason="no matching global factor",
                )
            )

    await storage.integrate_global_graph(new_globals, new_global_factors, all_bindings)
    return new_globals, new_global_factors, all_bindings


async def seed(db_path: str):
    """Seed the database with all 4 fixture packages."""
    config = StorageConfig(lancedb_path=db_path)
    storage = StorageManager(config)
    await storage.initialize()

    fixtures_dir = _find_fixtures_dir()
    packages = ["galileo", "einstein", "newton", "dark_energy"]

    for name in packages:
        data = _load_fixture(fixtures_dir, name)
        version = data["version"]
        local_vars = [
            LocalVariableNode(**{**v, "version": version}) for v in data["local_variables"]
        ]
        local_factors = [
            LocalFactorNode(**{**f, "version": version}) for f in data["local_factors"]
        ]

        new_vars, new_facs, bindings = await _ingest_package(
            storage, data["package_id"], data["version"], local_vars, local_factors
        )

        match_count = sum(1 for b in bindings if b.decision == "match_existing")
        create_count = sum(1 for b in bindings if b.decision == "create_new")
        print(
            f"  {name}: {len(local_vars)} vars, {len(local_factors)} factors "
            f"→ {create_count} new, {match_count} dedup"
        )

    # Print final stats
    for t in [
        "local_variable_nodes",
        "global_variable_nodes",
        "local_factor_nodes",
        "global_factor_nodes",
        "canonical_bindings",
    ]:
        count = await storage.content.count(t)
        print(f"  {t}: {count}")


def main():
    parser = argparse.ArgumentParser(description="Seed LKM database with fixture data")
    parser.add_argument("--db-path", default="./data/lancedb/lkm", help="LanceDB path")
    args = parser.parse_args()

    print(f"Seeding LKM database at {args.db_path}...")
    asyncio.run(seed(args.db_path))
    print("Done.")


if __name__ == "__main__":
    main()
