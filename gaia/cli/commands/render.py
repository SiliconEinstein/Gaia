"""gaia render -- generate presentation outputs (docs and/or GitHub site) from an inferred package."""

from __future__ import annotations

import json
from enum import Enum

import typer

from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
)
from gaia.cli.commands._detailed_reasoning import generate_detailed_reasoning
from gaia.cli.commands._github import generate_github_output
from gaia.cli.commands._render_priors import param_data_from_ir_metadata
from gaia.ir.validator import validate_local_graph


class RenderTarget(str, Enum):
    docs = "docs"
    github = "github"
    obsidian = "obsidian"
    all = "all"


def render_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
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
        apply_package_priors(loaded)
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

    # ── Load inference results if available ──
    # beliefs.json lives at .gaia/beliefs.json (written by `gaia infer`).
    # If present it MUST be fresh (ir_hash matches compiled graph).
    # --target github requires beliefs; --target docs degrades gracefully.
    beliefs_data: dict | None = None
    param_data = param_data_from_ir_metadata(ir)

    beliefs_path = gaia_dir / "beliefs.json"
    if beliefs_path.exists():
        try:
            beliefs_data = json.loads(beliefs_path.read_text())
        except json.JSONDecodeError as exc:
            typer.echo(f"Error: {beliefs_path} is not valid JSON: {exc}", err=True)
            raise typer.Exit(1)
        if beliefs_data.get("ir_hash") != compiled.graph.ir_hash:
            typer.echo(
                "Error: beliefs are stale; run `gaia infer` again.",
                err=True,
            )
            raise typer.Exit(1)

    # ── Decide which targets to attempt ──
    want_docs = target in (RenderTarget.docs, RenderTarget.all)
    want_github = target in (RenderTarget.github, RenderTarget.all)

    # github strictly requires beliefs: hard error if explicit, warn+skip if 'all'.
    if want_github and beliefs_data is None:
        if target == RenderTarget.github:
            typer.echo(
                "Error: --target github requires inference results; "
                "run `gaia infer` before `gaia render`.",
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

    want_obsidian = target == RenderTarget.obsidian

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

    if want_obsidian:
        from gaia.cli.commands._obsidian import generate_obsidian_vault

        obsidian_pages = generate_obsidian_vault(
            ir, beliefs_data=beliefs_data, param_data=param_data
        )
        import shutil

        wiki_dir = loaded.pkg_path / "gaia-wiki"
        if wiki_dir.exists():
            shutil.rmtree(wiki_dir)
        wiki_dir.mkdir()
        for rel_path, page_content in obsidian_pages.items():
            out = wiki_dir / rel_path
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(page_content)
        typer.echo(f"Obsidian: {wiki_dir} ({len(obsidian_pages)} pages)")
