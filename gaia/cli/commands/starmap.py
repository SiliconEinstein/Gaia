"""gaia starmap — emit a starmap of a compiled package (HTML or DOT)."""

from __future__ import annotations

import json
from pathlib import Path

import typer

from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
)
from gaia.cli.commands._dot import to_dot
from gaia.cli.commands._graph_json import generate_graph_json
from gaia.cli.commands._render_priors import param_data_from_ir_metadata
from gaia.ir.validator import validate_local_graph

GRAPH_DATA_PLACEHOLDER = "<!--__GRAPH_DATA__-->"

# Default output paths per format. Resolved after the format is parsed so we
# can keep `--out` default as `None` in the signature.
_DEFAULT_OUT = {
    "html": ".gaia/starmap.html",
    "dot": ".gaia/starmap.dot",
}

# Allowed theme names. ``dark`` is an alias of ``stellaris``.
_VALID_THEMES = ("light", "stellaris", "dark")


def _load_template() -> str:
    """Read the placeholder HTML template that ships with the CLI package."""
    import gaia.cli.starmap_assets as assets_pkg

    template_path = Path(assets_pkg.__file__).parent / "template.html"
    return template_path.read_text(encoding="utf-8")


def _render_html(template: str, graph_json: str) -> str:
    """Inject the graph JSON payload into *template* at the placeholder."""
    if GRAPH_DATA_PLACEHOLDER not in template:
        raise GaiaCliError(
            f"Error: starmap template is missing the {GRAPH_DATA_PLACEHOLDER!r} placeholder."
        )
    injection = f"<script>window.GRAPH_DATA = {graph_json};</script>"
    return template.replace(GRAPH_DATA_PLACEHOLDER, injection, 1)


def starmap_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    out: str = typer.Option(
        None,
        "--out",
        help=(
            "Output file. Defaults to '.gaia/starmap.html' (html) or "
            "'.gaia/starmap.dot' (dot), relative to the package directory; "
            "absolute paths are honored as-is."
        ),
    ),
    fmt: str = typer.Option(
        "html",
        "--format",
        help="Output format: 'html' (interactive Sigma.js) or 'dot' (paper-ready Graphviz).",
    ),
    theme: str = typer.Option(
        "light",
        "--theme",
        help=(
            "Visual theme for 'dot' output. 'light' (default) is the flat "
            "paper-friendly palette. 'stellaris' (alias: 'dark') is a "
            "deep-space dark variant — use 'sfdp' to render: "
            "`sfdp -Tsvg starmap.dot -o starmap.svg`."
        ),
    ),
) -> None:
    """Emit a starmap of the compiled package.

    Two formats are supported:

    * ``html`` (default) — single-file interactive Sigma.js visualization.
      Double-click to open in a browser; no server required.
    * ``dot`` — a Graphviz ``digraph`` source. Pipe through ``dot`` (Graphviz)
      to get a paper-ready figure. ``graphviz`` must be installed separately
      (``brew install graphviz`` / ``apt install graphviz``).

    Compile freshness, beliefs freshness, and graph validation gates apply to
    both formats.

    Examples:

      # Interactive HTML (default):
      gaia starmap path/to/pkg

      # DOT source + render to SVG (paper figure, vector, scales infinitely):
      gaia starmap path/to/pkg --format dot --out figures/starmap.dot
      dot -Tsvg figures/starmap.dot -o figures/starmap.svg

      # PNG preview at higher DPI for slides / dense graphs:
      dot -Tpng -Gdpi=200 figures/starmap.dot -o figures/starmap.png

      # PDF for direct LaTeX \\includegraphics inclusion:
      dot -Tpdf figures/starmap.dot -o figures/starmap.pdf
    """
    if fmt not in _DEFAULT_OUT:
        typer.echo(
            f"Error: --format must be one of {sorted(_DEFAULT_OUT)}; got {fmt!r}.",
            err=True,
        )
        raise typer.Exit(2)

    if theme not in _VALID_THEMES:
        typer.echo(
            f"Error: --theme must be one of {sorted(_VALID_THEMES)}; got {theme!r}.",
            err=True,
        )
        raise typer.Exit(2)

    try:
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
    except GaiaCliError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1)

    graph_validation = validate_local_graph(compiled.graph)
    for warning in graph_validation.warnings:
        typer.echo(f"Warning: {warning}")
    if graph_validation.errors:
        for error in graph_validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    ir = compiled.to_json()

    # Same compile-artifact freshness gate as `render`.
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

    # Beliefs are optional — degrade gracefully when absent. When present they
    # MUST be fresh, mirroring `render`.
    beliefs_data: dict | None = None
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

    param_data = param_data_from_ir_metadata(ir)
    exported_ids = {k["id"] for k in ir.get("knowledges", []) if k.get("exported")}

    graph_json = generate_graph_json(
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported_ids,
    )
    graph_payload = json.loads(graph_json)

    if fmt == "html":
        try:
            template = _load_template()
            content = _render_html(template, graph_json)
        except GaiaCliError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)
    else:  # dot
        content = to_dot(graph_json, theme=theme)

    out_path = Path(out) if out is not None else Path(_DEFAULT_OUT[fmt])
    if not out_path.is_absolute():
        out_path = loaded.pkg_path / out_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(content, encoding="utf-8")

    node_count = len(graph_payload.get("nodes", []))
    edge_count = len(graph_payload.get("edges", []))
    typer.echo(f"Wrote starmap to {out_path} ({node_count} nodes, {edge_count} edges)")
