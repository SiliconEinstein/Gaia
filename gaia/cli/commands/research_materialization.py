"""Materialization helpers for the package-native research CLI."""

from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import Any

import typer

from gaia.cli.commands.add import (
    LKMDependencyAddError,
    add_lkm_chain_dependency,
    add_lkm_claim_dependency,
    add_lkm_paper_dependency,
    add_local_package_dependency,
    make_lkm_claim_ref,
    make_lkm_paper_ref,
)
from gaia.engine.packaging import GaiaPackagingError
from gaia.engine.research import (
    ResearchPackage,
    attach_source_package_refs,
    materialize_landscape_source_package,
)


def _research_cli_override(name: str, default: Any) -> Any:
    module = sys.modules.get("gaia.cli.commands.research")
    if module is None:
        return default
    return getattr(module, name, default)


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(0, value)


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return value if value >= 0 else default


def _lkm_materialization_with_transport_retries[T](
    label: str,
    operation: Callable[[], T],
) -> T:
    retries = _env_int("GAIA_RESEARCH_LKM_MATERIALIZE_RETRIES", 2)
    base_wait = _env_float("GAIA_RESEARCH_LKM_MATERIALIZE_RETRY_BASE_SECONDS", 2.0)
    for attempt in range(retries + 1):
        try:
            return operation()
        except typer.Exit as exc:
            exit_code = getattr(exc, "exit_code", None)
            if exit_code != 2 or attempt >= retries:
                raise
            wait_seconds = base_wait * (2**attempt)
            typer.echo(
                (
                    f"Warning: transient LKM transport failure while materializing {label}; "
                    f"retrying in {wait_seconds:.1f}s ({attempt + 1}/{retries})."
                ),
                err=True,
            )
            sleep(wait_seconds)
    raise AssertionError("unreachable LKM materialization retry state")


def _materialize_landscape_sources_or_exit(
    research_pkg: ResearchPackage,
    landscape: dict[str, Any],
    *,
    landscape_artifact: Path,
    dry_run: bool,
) -> dict[str, object]:
    if dry_run:
        return {
            "materialize_sources_enabled": True,
            "source_package_materialization": False,
            "source_packages_written": [],
            "source_packages_added": [],
        }

    materialized = materialize_landscape_source_package(
        research_pkg,
        landscape,
        landscape_artifact=landscape_artifact,
    )
    if materialized is None:
        return {
            "materialize_sources_enabled": True,
            "source_package_materialization": False,
            "source_packages_written": [],
            "source_packages_added": [],
        }

    payload = materialized.to_payload()
    try:
        add_local_dependency = _research_cli_override(
            "add_local_package_dependency",
            add_local_package_dependency,
        )
        local_root = add_local_dependency(materialized.root, package_root=research_pkg.path)
    except GaiaPackagingError as exc:
        typer.echo(f"Error: failed to add generated source package: {exc}", err=True)
        typer.echo(f"Generated source package: {materialized.root}", err=True)
        raise typer.Exit(1) from exc

    added_payload = dict(payload)
    added_payload["path"] = str(local_root)
    attach_source_package_refs(landscape, [materialized])
    landscape_artifact.write_text(
        json.dumps(landscape, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return {
        "materialize_sources_enabled": True,
        "source_package_materialization": True,
        "source_packages_written": [payload],
        "source_packages_added": [added_payload],
    }


def _lkm_materialized_payload(
    materialized: Any,
    *,
    requested_ref: str | None = None,
) -> dict[str, object]:
    payload = {
        "requested_source_ref": requested_ref or str(materialized.source_ref),
        "source_ref": str(materialized.source_ref),
        "path": str(materialized.root),
        "package": str(materialized.dist_name),
        "import_name": str(materialized.import_name),
        "claim_count": int(materialized.claim_count),
        "question_count": int(materialized.question_count),
        "dependency_count": int(materialized.dependency_count),
    }
    chain_count = getattr(materialized, "chain_count", None)
    if isinstance(chain_count, int):
        payload["chain_count"] = chain_count
    total_chains = getattr(materialized, "total_chains", None)
    if isinstance(total_chains, int):
        payload["total_chains"] = total_chains
    return payload


def _materialize_lkm_papers_or_exit(
    research_pkg: ResearchPackage,
    *,
    paper_ids: list[str],
    claim_ids: list[str],
    chain_claim_ids: list[str],
    lkm_index: str,
    dry_run: bool,
) -> dict[str, object]:
    requests = [*paper_ids, *claim_ids, *chain_claim_ids]
    if not requests or dry_run:
        return {
            "lkm_materialize_requests": requests,
            "lkm_packages_materialized": [],
            "lkm_chains_materialized": [],
        }

    materialized_packages = [
        *_materialize_lkm_paper_refs(
            research_pkg,
            paper_ids=paper_ids,
            lkm_index=lkm_index,
        ),
        *_materialize_lkm_claim_refs(
            research_pkg,
            claim_ids=claim_ids,
            lkm_index=lkm_index,
        ),
    ]
    materialized_chains = _materialize_lkm_chain_refs(
        research_pkg,
        claim_ids=chain_claim_ids,
        lkm_index=lkm_index,
    )
    return {
        "lkm_materialize_requests": requests,
        "lkm_packages_materialized": materialized_packages,
        "lkm_chains_materialized": materialized_chains,
    }


def _materialize_lkm_paper_refs(
    research_pkg: ResearchPackage,
    *,
    paper_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_packages: list[dict[str, object]] = []
    for paper_id in paper_ids:
        try:
            ref = make_lkm_paper_ref(lkm_index, paper_id)
            add_paper_dependency = _research_cli_override(
                "add_lkm_paper_dependency",
                add_lkm_paper_dependency,
            )

            def materialize_current_paper(
                ref: Any = ref,
                add_paper_dependency: Any = add_paper_dependency,
            ) -> Any:
                return add_paper_dependency(ref, package_root=research_pkg.path)

            materialized = _lkm_materialization_with_transport_retries(
                ref.ref,
                materialize_current_paper,
            )
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM paper package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM paper {paper_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_packages.append(_lkm_materialized_payload(materialized, requested_ref=ref.ref))
    return materialized_packages


def _materialize_lkm_claim_refs(
    research_pkg: ResearchPackage,
    *,
    claim_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_packages: list[dict[str, object]] = []
    for claim_id in claim_ids:
        try:
            ref = make_lkm_claim_ref(lkm_index, claim_id)
            add_claim_dependency = _research_cli_override(
                "add_lkm_claim_dependency",
                add_lkm_claim_dependency,
            )

            def materialize_current_claim(
                ref: Any = ref,
                add_claim_dependency: Any = add_claim_dependency,
            ) -> Any:
                return add_claim_dependency(ref, package_root=research_pkg.path)

            materialized = _lkm_materialization_with_transport_retries(
                ref.ref,
                materialize_current_claim,
            )
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM claim backing package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM claim {claim_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_packages.append(_lkm_materialized_payload(materialized, requested_ref=ref.ref))
    return materialized_packages


def _materialize_lkm_chain_refs(
    research_pkg: ResearchPackage,
    *,
    claim_ids: list[str],
    lkm_index: str,
) -> list[dict[str, object]]:
    materialized_chains: list[dict[str, object]] = []
    for claim_id in claim_ids:
        try:
            ref = make_lkm_claim_ref(lkm_index, claim_id)
            add_chain_dependency = _research_cli_override(
                "add_lkm_chain_dependency",
                add_lkm_chain_dependency,
            )

            def materialize_current_chain(
                ref: Any = ref,
                add_chain_dependency: Any = add_chain_dependency,
            ) -> Any:
                return add_chain_dependency(ref, package_root=research_pkg.path)

            chain_materialized = _lkm_materialization_with_transport_retries(
                f"{ref.ref} reasoning chain",
                materialize_current_chain,
            )
        except LKMDependencyAddError as exc:
            typer.echo(f"Error: failed to add LKM reasoning chain package: {exc}", err=True)
            if exc.materialized is not None:
                typer.echo(f"Generated LKM package: {exc.materialized.root}", err=True)
            raise typer.Exit(1) from exc
        except GaiaPackagingError as exc:
            typer.echo(f"Error: failed to materialize LKM chain {claim_id!r}: {exc}", err=True)
            raise typer.Exit(1) from exc
        materialized_chains.append(
            _lkm_materialized_payload(chain_materialized, requested_ref=ref.ref)
        )
    return materialized_chains
