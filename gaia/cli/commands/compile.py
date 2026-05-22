"""gaia build compile -- compile Python DSL package to Gaia IR v2 JSON."""

from __future__ import annotations

from pathlib import Path

import typer

from gaia.engine.ir import LocalCanonicalGraph
from gaia.engine.ir.validator import validate_local_graph
from gaia.engine.layout import GaiaLayoutError, LayoutKind, detect_layout
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    build_package_manifests,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
    write_compiled_artifacts,
)


def compile_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    sync_host: bool = typer.Option(
        False,
        "--sync-host/--no-sync-host",
        help=(
            "When the host has its own pyproject.toml, run `uv sync` against it "
            "before importing the Gaia package. Off by default in the embedded "
            "layout — the host's environment is none of Gaia's business unless "
            "the user opts in. Always on in the legacy layout (a legacy host's "
            "pyproject IS the Gaia package and its deps must be installed for "
            "the import to succeed)."
        ),
    ),
) -> None:
    """Compile a knowledge package to ``.gaia/ir.json``.

    Loads the package's Python DSL, applies any sidecar priors (``priors.py``),
    lowers it into the canonical IR v2 JSON, runs the IR validator, and
    writes ``.gaia/ir.json`` + ``.gaia/ir_hash`` + ``.gaia/compile_metadata.json``.
    Downstream verbs (``gaia run infer``, ``gaia run render``, ``gaia inspect
    starmap``, ``gaia pkg register``) all require fresh compile artifacts.

    Example:

    .. code-block:: bash

        gaia build compile .
    """
    try:
        # Embedded mounts must not silently uv-sync the host's own
        # pyproject.toml — that would re-introduce a side-effect on a
        # directory whose Gaia presence is supposed to be confined to
        # gaia/ + .gaia/. Legacy packages keep the historical behaviour
        # since their pyproject IS the Gaia package.
        host_path = Path(path).resolve()
        try:
            layout = detect_layout(host_path)
            is_legacy = layout.kind is LayoutKind.LEGACY
        except GaiaLayoutError:
            is_legacy = True  # let the loader raise with a useful message
            layout = None
        # When the host has BOTH an embedded gaia/gaia.toml AND a
        # legacy [tool.gaia] block, `detect_layout` logs a warning at
        # WARNING level but most users do not run with logging set
        # that low. Surface the same precedence note on stderr so
        # mid-migration confusion is impossible to miss.
        if layout is not None and layout.kind is LayoutKind.EMBEDDED:
            host_pyproject = host_path / "pyproject.toml"
            if host_pyproject.exists():
                try:
                    import tomllib as _tomllib

                    with open(host_pyproject, "rb") as _f:
                        _cfg = _tomllib.load(_f)
                    if _cfg.get("tool", {}).get("gaia", {}).get("type") == "knowledge-package":
                        typer.echo(
                            "Warning: host has both embedded (gaia/gaia.toml) and "
                            "legacy ([tool.gaia] in pyproject.toml) manifests. "
                            "The embedded manifest wins; remove [tool.gaia] from "
                            "pyproject.toml once the migration is done.",
                            err=True,
                        )
                except Exception:  # pragma: no cover — defensive
                    pass
        if sync_host or is_legacy:
            ensure_package_env(host_path)
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        ir = compiled.to_json()
        manifests = build_package_manifests(loaded, compiled)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    for warning in validation.warnings:
        typer.echo(f"Warning: {warning}")
    if validation.errors:
        for error in validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    gaia_dir = write_compiled_artifacts(
        loaded.pkg_path,
        ir,
        manifests=manifests,
        formalization_manifest=compiled.formalization_manifest,
    )

    typer.echo(
        f"Compiled {len(ir['knowledges'])} knowledge, "
        f"{len(ir['strategies'])} strategies, "
        f"{len(ir['operators'])} operators"
    )
    typer.echo(f"IR hash: {ir['ir_hash'][:16]}...")
    typer.echo(f"Output: {gaia_dir / 'ir.json'}")
