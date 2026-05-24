"""gaia add -- install a Gaia knowledge package from the official registry."""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from gaia.cli._registry import DEFAULT_REGISTRY, fetch_file_optional, resolve_package
from gaia.cli.commands.pkg.lkm_materialize import (
    MaterializedLKMPackage,
    materialize_lkm_paper_package,
)
from gaia.cli.commands.search.lkm._indexes import (
    DEFAULT_LKM_INDEX_ID,
    known_lkm_index_ids,
    lkm_index_base_url,
    normalize_lkm_index_id,
)
from gaia.cli.commands.search.lkm._shared import run_request
from gaia.engine.packaging import GaiaPackagingError


def _run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, text=True, capture_output=True, **kwargs)
    except FileNotFoundError as exc:
        raise GaiaPackagingError(
            "uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        ) from exc


def add_command(
    package: str | None = typer.Argument(
        None,
        help=(
            "Package name (e.g., galileo-falling-bodies-gaia) or LKM ref (lkm:<index>:paper:<id>)."
        ),
    ),
    version: str | None = typer.Option(None, "--version", "-v", help="Specific version"),
    registry: str = typer.Option(DEFAULT_REGISTRY, "--registry", help="Registry GitHub repo"),
    lkm_index: str = typer.Option(
        DEFAULT_LKM_INDEX_ID,
        "--lkm-index",
        "--lkm-server",
        help="Configured LKM index id for --lkm-paper / --lkm-claim.",
    ),
    lkm_paper: str | None = typer.Option(
        None,
        "--lkm-paper",
        help="Materialize this LKM paper id as a local Gaia package and add it.",
    ),
    lkm_claim: str | None = typer.Option(
        None,
        "--lkm-claim",
        help="Resolve this LKM claim id to its backing paper package.",
    ),
    target: str = typer.Option(
        ".",
        "--target",
        help=(
            "Path to the Gaia knowledge package to add the dependency to "
            "(default: cwd). Matches the --target convention used by "
            "`gaia author` verbs so the whole package lifecycle runs from "
            "one place."
        ),
    ),
) -> None:
    """Install a registered or LKM-backed Gaia knowledge package.

    Resolves ``<package>`` against the gaia registry (default:
    ``SiliconEinstein/gaia-registry`` on GitHub), runs ``uv add`` on the
    resolved ``git+<repo>@<sha>`` spec, and best-effort downloads the
    upstream ``beliefs.json`` into ``.gaia/dep_beliefs/<import_name>.json``
    so foreign-node priors flow into local inference. Must be run from
    within a Gaia knowledge package (``pyproject.toml`` carrying
    ``[tool.gaia]``).

    LKM paper refs/flags fetch the paper graph, generate a local Gaia package
    under ``.gaia/lkm_packages/``, compile it, and add it as an editable
    dependency with ``uv add --editable``.

    ``--version`` pins a specific release; omit to take the latest
    registered version.

    Example:

    .. code-block:: bash

        gaia pkg add galileo-falling-bodies-gaia
        gaia pkg add mendel-v0-5-gaia --version 0.1.0
        gaia pkg add --lkm-index bohrium --lkm-paper 811827932371615744
        gaia pkg add lkm:bohrium:paper:811827932371615744
    """
    try:
        lkm_ref = _resolve_lkm_source_ref(
            package,
            lkm_index=lkm_index,
            lkm_paper=lkm_paper,
            lkm_claim=lkm_claim,
        )
    except GaiaPackagingError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(4) from exc
    # Resolve the consumer package once, honoring --target (default cwd). The
    # same --target convention used by `gaia author` verbs / `gaia init` /
    # `gaia pkg scaffold` works here; --target . preserves the historical
    # "run from inside the package" behavior by walking up to the nearest root.
    package_root = _resolve_package_root(target)

    if lkm_ref is not None:
        _handle_lkm_source_add(lkm_ref, package_root=package_root)
        return
    if package is None:
        typer.echo("Error: pass PACKAGE or an LKM source flag.", err=True)
        raise typer.Exit(4)
    _warn_unused_lkm_index(lkm_index)

    try:
        resolved = resolve_package(package, version=version, registry=registry)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    # Normalize: ensure -gaia suffix for the dep spec
    canonical_name = package if package.endswith("-gaia") else f"{package}-gaia"
    dep_spec = f"{canonical_name} @ git+{resolved.repo}@{resolved.git_sha}"
    typer.echo(f"Resolved {package} v{resolved.version} → {resolved.git_sha[:8]}")

    # `uv add` runs in the resolved package root when one was found; otherwise
    # it falls back to the process cwd (matching the prior behavior for the
    # registry path, which uv resolves against the nearest project).
    uv_cwd = package_root if package_root is not None else None
    try:
        result = _run_uv(["uv", "add", dep_spec], cwd=uv_cwd)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        typer.echo(f"Error: uv add failed: {stderr}", err=True)
        raise typer.Exit(1)

    typer.echo(f"Added {package} v{resolved.version}")

    # Download upstream beliefs manifest for foreign-node prior injection.
    # This is best-effort: older registry entries may not have beliefs.json.
    if package_root is None:
        typer.echo("Note: not inside a Gaia package; skipping dep_beliefs download")
    else:
        _fetch_dep_beliefs(
            package_name=canonical_name.removesuffix("-gaia"),
            version=resolved.version,
            registry=registry,
            pkg_root=package_root,
        )


@dataclass(frozen=True)
class LKMSourceRef:
    """Stable source identity for an LKM-backed package candidate."""

    index_id: str
    kind: str
    provider_id: str

    @property
    def ref(self) -> str:
        """Return the canonical LKM source ref."""
        return f"lkm:{self.index_id}:{self.kind}:{self.provider_id}"


def _resolve_lkm_source_ref(
    package: str | None,
    *,
    lkm_index: str,
    lkm_paper: str | None,
    lkm_claim: str | None,
) -> LKMSourceRef | None:
    lkm_flag_count = sum(value is not None for value in (lkm_paper, lkm_claim))
    package_is_lkm_ref = bool(package and package.startswith("lkm:"))
    if package_is_lkm_ref and lkm_flag_count:
        raise GaiaPackagingError("pass either an LKM ref or LKM flags, not both.")
    if package is not None and not package_is_lkm_ref and lkm_flag_count:
        raise GaiaPackagingError("pass either PACKAGE or LKM flags, not both.")
    if lkm_flag_count > 1:
        raise GaiaPackagingError("pass at most one of --lkm-paper / --lkm-claim.")
    if package_is_lkm_ref:
        assert package is not None
        return _parse_lkm_ref(package)
    if lkm_paper is not None:
        return _make_lkm_ref(lkm_index, "paper", lkm_paper)
    if lkm_claim is not None:
        return _make_lkm_ref(lkm_index, "claim", lkm_claim)
    return None


def _parse_lkm_ref(raw: str) -> LKMSourceRef:
    parts = raw.split(":")
    if len(parts) == 3 and parts[1] in {"paper", "claim"}:
        return _make_lkm_ref(DEFAULT_LKM_INDEX_ID, parts[1], parts[2])
    if len(parts) == 4 and parts[2] in {"paper", "claim"}:
        return _make_lkm_ref(parts[1], parts[2], parts[3])
    raise GaiaPackagingError(
        "malformed LKM ref; expected lkm:<index>:paper:<id>, "
        "lkm:<index>:claim:<id>, lkm:paper:<id>, or lkm:claim:<id>."
    )


def _make_lkm_ref(index_id: str, kind: str, provider_id: str) -> LKMSourceRef:
    normalized_index = normalize_lkm_index_id(index_id)
    if not normalized_index:
        raise GaiaPackagingError("--lkm-index must be non-empty.")
    if lkm_index_base_url(normalized_index) is None:
        known = ", ".join(known_lkm_index_ids())
        raise GaiaPackagingError(f"unknown LKM index {index_id!r}. Configured indexes: {known}.")
    normalized_provider_id = provider_id.strip()
    if not normalized_provider_id:
        raise GaiaPackagingError(f"LKM {kind} id must be non-empty.")
    return LKMSourceRef(
        index_id=normalized_index,
        kind=kind,
        provider_id=normalized_provider_id,
    )


def _handle_lkm_source_add(ref: LKMSourceRef, *, package_root: Path | None) -> None:
    if ref.kind == "paper":
        _handle_lkm_paper_add(ref, package_root=package_root)
        return

    typer.echo(
        f"LKM claim source recognized: {ref.ref}\n"
        "`gaia pkg add` installs paper-level Gaia packages, not standalone "
        "claim nodes. Resolve this claim to its backing paper first:\n"
        f"  gaia search lkm reasoning --index {ref.index_id} --claim-id {ref.provider_id}\n"
        "Then add the paper package from the returned action.",
        err=True,
    )
    raise typer.Exit(1)


def _handle_lkm_paper_add(ref: LKMSourceRef, *, package_root: Path | None) -> None:
    if package_root is None:
        typer.echo(
            f"Error: LKM paper source recognized ({ref.ref}), but no current "
            "Gaia knowledge package was found. Run `gaia pkg add --lkm-paper ...` "
            "inside the package that should depend on this LKM paper, or point "
            "--target at it.",
            err=True,
        )
        raise typer.Exit(1)

    try:
        payload = run_request(
            "POST",
            "/papers/graph",
            json_body={
                "paper_id": ref.provider_id,
                "include": ["paper", "variables", "factors", "motivations"],
            },
            index_id=ref.index_id,
        )
        materialized = materialize_lkm_paper_package(
            payload,
            project_root=package_root,
            index_id=ref.index_id,
            paper_id=ref.provider_id,
        )
    except GaiaPackagingError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from exc

    try:
        result = _run_uv(["uv", "add", "--editable", str(materialized.root)], cwd=package_root)
    except GaiaPackagingError as exc:
        _echo_lkm_uv_add_failure(materialized, str(exc))
        raise typer.Exit(1) from exc
    if result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip()
        _echo_lkm_uv_add_failure(materialized, stderr or "uv exited with a non-zero status")
        raise typer.Exit(1)

    typer.echo(f"Materialized {materialized.source_ref}")
    typer.echo(f"Package: {materialized.dist_name}")
    typer.echo(f"Path: {materialized.root}")
    typer.echo(
        "Contents: "
        f"{materialized.claim_count} claims, "
        f"{materialized.question_count} questions, "
        f"{materialized.dependency_count} depends_on scaffold dependencies"
    )
    if materialized.paper_id_inferred:
        typer.echo(
            "Warning: LKM response did not include a paper id; "
            f"using requested paper id {materialized.paper_id!r} for the generated package.",
            err=True,
        )
    if materialized.regenerated_existing:
        typer.echo(
            "Warning: regenerated an existing LKM package; review downstream imports "
            "if generated symbols changed.",
            err=True,
        )
    if materialized.skipped_factor_count:
        typer.echo(
            f"Note: skipped {materialized.skipped_factor_count} LKM factor(s) whose "
            "conclusion or premises were not extractable claim nodes."
        )
    if materialized.dependency_count:
        typer.echo(
            "Note: generated `depends_on(...)` records are the unformalized "
            "counterpart of `derive(...)`; review/materialize them before "
            "treating them as formal Gaia reasoning."
        )
    typer.echo("Added editable dependency with uv.")
    if materialized.exported_symbol:
        typer.echo(
            f"Import hint: from {materialized.import_name} import {materialized.exported_symbol}"
        )


def _warn_unused_lkm_index(lkm_index: str) -> None:
    normalized_index = normalize_lkm_index_id(lkm_index)
    if normalized_index and normalized_index != DEFAULT_LKM_INDEX_ID:
        typer.echo(
            f"Warning: ignoring --lkm-index {normalized_index!r}; "
            "`gaia pkg add PACKAGE` resolves registry packages. "
            "Use --lkm-paper, --lkm-claim, or an lkm:<index>:... ref for LKM sources.",
            err=True,
        )


def _echo_lkm_uv_add_failure(materialized: MaterializedLKMPackage, details: str) -> None:
    typer.echo(
        f"Error: uv add failed after materializing {materialized.source_ref}: {details}",
        err=True,
    )
    typer.echo(
        f"Generated package left at: {materialized.root}",
        err=True,
    )
    typer.echo(
        "Fix the uv error and rerun the same `gaia pkg add` command to retry installation.",
        err=True,
    )


def _is_gaia_package_dir(directory: Path) -> bool:
    """Return True if *directory* holds a Gaia knowledge-package pyproject.toml."""
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib  # type: ignore[no-redef]

    pyproject = directory / "pyproject.toml"
    if not pyproject.exists():
        return False
    try:
        config = tomllib.loads(pyproject.read_text())
    except Exception:
        return False
    gaia_type = config.get("tool", {}).get("gaia", {}).get("type")
    return bool(gaia_type == "knowledge-package")


def _resolve_package_root(target: str) -> Path | None:
    """Resolve the Gaia package root for ``gaia pkg add`` honoring ``--target``.

    Unifies the cwd contract with the rest of the package lifecycle: the same
    ``--target <path>`` form used by ``gaia author`` verbs and ``gaia init`` /
    ``gaia pkg scaffold`` works here too. ``--target .`` (the default) keeps the
    historical "run from inside the package" behavior by walking up from the
    target directory to the nearest Gaia package root.
    """
    base = Path(target).resolve()
    if not base.exists():
        return None
    if base.is_file():
        base = base.parent
    for directory in [base, *base.parents]:
        if _is_gaia_package_dir(directory):
            return directory
    return None


def _fetch_dep_beliefs(
    *,
    package_name: str,
    version: str,
    registry: str,
    pkg_root: Path,
) -> None:
    """Download beliefs.json from the registry into ``.gaia/dep_beliefs/``."""
    registry_path = f"packages/{package_name}/releases/{version}/beliefs.json"
    content = fetch_file_optional(registry, registry_path)
    if content is None:
        typer.echo(f"Note: no beliefs manifest for {package_name} v{version} (optional)")
        return

    # Validate it's valid JSON before writing
    try:
        json.loads(content)
    except json.JSONDecodeError:
        typer.echo(f"Warning: beliefs manifest for {package_name} is not valid JSON; skipping")
        return

    dep_beliefs_dir = pkg_root / ".gaia" / "dep_beliefs"
    dep_beliefs_dir.mkdir(parents=True, exist_ok=True)

    import_name = package_name.replace("-", "_")
    dest = dep_beliefs_dir / f"{import_name}.json"
    dest.write_text(content)
    typer.echo(f"Saved upstream beliefs: {dest}")
