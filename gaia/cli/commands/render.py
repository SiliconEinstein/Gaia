"""gaia render -- generate presentation outputs (docs and/or GitHub site) from a reviewed package."""

from __future__ import annotations

import json
from enum import Enum

import typer

from gaia.cli._packages import (
    GaiaCliError,
    compile_loaded_package_artifact,
    load_gaia_package,
)
from gaia.cli._reviews import load_gaia_review, resolve_gaia_review
from gaia.cli.commands._detailed_reasoning import generate_detailed_reasoning
from gaia.cli.commands._github import generate_github_output
from gaia.ir.validator import validate_local_graph


class RenderTarget(str, Enum):
    docs = "docs"
    github = "github"
    all = "all"


def render_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review: str | None = typer.Option(
        None,
        "--review",
        help=(
            "Review sidecar name from <package>/reviews/<name>.py. "
            "Auto-selected when only one sidecar exists."
        ),
    ),
    target: RenderTarget = typer.Option(
        RenderTarget.all,
        "--target",
        help=(
            "What to render: 'docs' (renders from compiled IR alone; enriched "
            "when beliefs are available), 'github' (requires beliefs from "
            "`gaia infer`), or 'all' (default; docs unconditionally + github "
            "when beliefs are available)."
        ),
    ),
) -> None:
    """Render presentation outputs from a compiled package.

    `--target docs` renders `docs/detailed-reasoning.md` from the compiled IR
    alone; when `gaia infer` has also been run, the output is enriched with
    belief and prior values. `--target github` strictly requires inference
    results and emits the full `.github-output/` presentation site.
    `--target all` (default) always renders docs and adds github when
    inference results are available, emitting a warning when they are not.
    """
    try:
        loaded = load_gaia_package(path)
        compiled = compile_loaded_package_artifact(loaded)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    # Validate IR structure (same gate as compile/infer)
    graph_validation = validate_local_graph(compiled.graph)
    for warning in graph_validation.warnings:
        typer.echo(f"Warning: {warning}")
    if graph_validation.errors:
        for error in graph_validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    ir = compiled.to_json()

    # ── Verify compile artifacts are fresh (same pattern as infer.py) ──
    gaia_dir = loaded.pkg_path / ".gaia"
    ir_hash_path = gaia_dir / "ir_hash"
    ir_json_path = gaia_dir / "ir.json"
    if not ir_hash_path.exists() or not ir_json_path.exists():
        typer.echo("Error: missing compiled artifacts; run `gaia compile` first.", err=True)
        raise typer.Exit(1)
    if ir_hash_path.read_text().strip() != compiled.graph.ir_hash:
        typer.echo("Error: compiled artifacts are stale; run `gaia compile` again.", err=True)
        raise typer.Exit(1)
    try:
        stored_ir = json.loads(ir_json_path.read_text())
    except json.JSONDecodeError as exc:
        typer.echo(f"Error: .gaia/ir.json is not valid JSON: {exc}", err=True)
        raise typer.Exit(1)
    if stored_ir.get("ir_hash") != compiled.graph.ir_hash or stored_ir != ir:
        typer.echo("Error: compiled artifacts are stale; run `gaia compile` again.", err=True)
        raise typer.Exit(1)

    # ── Load review sidecar (optional for --target docs; required for --target github) ──
    # Propagation rules for review-loading failures (ambiguous candidates,
    # unknown `--review NAME`, broken review module imports):
    #   - explicit `--review NAME` → always hard error (user asked specifically)
    #   - `--target github` → always hard error (site without beliefs is misleading)
    #   - otherwise (`--target docs` / `--target all` in auto-select mode) →
    #     warn and fall back to no-beliefs rendering, so accumulated alternate
    #     or broken sidecars don't block the IR-only authoring workflow
    try:
        loaded_review = load_gaia_review(loaded, review_name=review)
    except GaiaCliError as exc:
        if review is not None or target == RenderTarget.github:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
        typer.echo(f"Warning: could not load review sidecar: {exc}")
        typer.echo(
            "Warning: falling back to no-beliefs rendering. "
            "Pass `--review <name>` to select a specific sidecar."
        )
        loaded_review = None

    # ── Load inference results if available ──
    # Both beliefs.json and parameterization.json are optional at load time,
    # but if present they MUST be fresh (ir_hash matches compiled graph).
    # --target github additionally requires beliefs; --target docs degrades gracefully.
    beliefs_data: dict | None = None
    param_data: dict | None = None
    if loaded_review is not None:
        review_dir = gaia_dir / "reviews" / loaded_review.name
        beliefs_path = review_dir / "beliefs.json"
        param_path = review_dir / "parameterization.json"

        if beliefs_path.exists():
            try:
                beliefs_data = json.loads(beliefs_path.read_text())
            except json.JSONDecodeError as exc:
                typer.echo(f"Error: {beliefs_path} is not valid JSON: {exc}", err=True)
                raise typer.Exit(1)
            if beliefs_data.get("ir_hash") != compiled.graph.ir_hash:
                typer.echo(
                    f"Error: beliefs for review {loaded_review.name!r} are stale; "
                    f"run `gaia infer --review {loaded_review.name}` again.",
                    err=True,
                )
                raise typer.Exit(1)

            # Review-content freshness: resolve the CURRENT review sidecar (which
            # may have been edited after the last `gaia infer`) and compare its
            # canonical content hash with the one persisted at infer time. The
            # IR hash alone cannot catch this because review priors and strategy
            # params are not part of the compiled IR — a user can edit
            # `reviews/<name>.py` and leave `ir_hash` unchanged. Without this
            # check, render would silently publish results that contradict the
            # current review sidecar.
            stored_review_hash = beliefs_data.get("review_content_hash")
            if stored_review_hash is not None:
                try:
                    current_resolved = resolve_gaia_review(loaded_review, compiled)
                except GaiaCliError as exc:
                    typer.echo(
                        f"Error: could not resolve review {loaded_review.name!r} to "
                        f"verify freshness: {exc}",
                        err=True,
                    )
                    raise typer.Exit(1)
                current_review_hash = current_resolved.content_hash()
                if current_review_hash != stored_review_hash:
                    typer.echo(
                        f"Error: review {loaded_review.name!r} has changed since the "
                        f"last `gaia infer` (review_content_hash mismatch). "
                        f"Re-run `gaia infer --review {loaded_review.name}` to refresh "
                        f"beliefs against the current review sidecar.",
                        err=True,
                    )
                    raise typer.Exit(1)

            if param_path.exists():
                try:
                    param_data = json.loads(param_path.read_text())
                except json.JSONDecodeError as exc:
                    typer.echo(f"Error: {param_path} is not valid JSON: {exc}", err=True)
                    raise typer.Exit(1)
                if param_data.get("ir_hash") != compiled.graph.ir_hash:
                    typer.echo(
                        f"Error: parameterization for review {loaded_review.name!r} "
                        f"is stale; run `gaia infer --review {loaded_review.name}` again.",
                        err=True,
                    )
                    raise typer.Exit(1)

    # ── Decide which targets to attempt ──
    want_docs = target in (RenderTarget.docs, RenderTarget.all)
    want_github = target in (RenderTarget.github, RenderTarget.all)

    # github strictly requires beliefs: hard error if explicit, warn+skip if 'all'.
    if want_github and beliefs_data is None:
        if target == RenderTarget.github:
            if loaded_review is None:
                typer.echo(
                    "Error: --target github requires a review sidecar and inference "
                    "results. Create <package>/reviews/<name>.py, then run "
                    "`gaia infer` before `gaia render`.",
                    err=True,
                )
            else:
                typer.echo(
                    f"Error: --target github requires inference results; "
                    f"run `gaia infer --review {loaded_review.name}` first.",
                    err=True,
                )
            raise typer.Exit(1)
        # --target all: degrade to docs-only with a warning.
        typer.echo(
            "Warning: no inference results found; skipping --target github. "
            "Run `gaia infer` to include the GitHub presentation.",
        )
        want_github = False

    # docs target renders even without beliefs — warn once so the user knows why
    # the output is missing belief values.
    if want_docs and beliefs_data is None:
        typer.echo(
            "Warning: rendering docs without inference results; "
            "run `gaia infer` to include belief values.",
        )

    if want_docs:
        content = generate_detailed_reasoning(
            ir,
            loaded.project_config,
            beliefs_data=beliefs_data,
            param_data=param_data,
        )
        docs_out = loaded.pkg_path / "docs" / "detailed-reasoning.md"
        docs_out.parent.mkdir(parents=True, exist_ok=True)
        docs_out.write_text(content)
        typer.echo(f"Docs: {docs_out}")

    if want_github:
        exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}
        github_out = generate_github_output(
            ir,
            loaded.pkg_path,
            beliefs_data=beliefs_data,
            param_data=param_data,
            exported_ids=exported_ids,
            pkg_metadata=loaded.project_config,
        )
        typer.echo(f"GitHub: {github_out}")

    if loaded_review is not None:
        typer.echo(f"Review: {loaded_review.name}")
