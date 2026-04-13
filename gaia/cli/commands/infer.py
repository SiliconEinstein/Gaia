"""gaia infer -- run BP from compiled IR with metadata priors."""

from __future__ import annotations

import json
from dataclasses import asdict

import typer

from gaia.bp import lower_local_graph
from gaia.bp.engine import InferenceEngine
from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    compile_loaded_package_artifact,
    gaia_lang_version,
    load_gaia_package,
)
from gaia.ir.validator import validate_local_graph


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def infer_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Run BP inference on a compiled knowledge package.

    Priors come from claim metadata (set by priors.py and reason+prior
    DSL pairing during compilation). The lowering layer reads
    metadata["prior"] directly — no review sidecar needed.
    """
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

    ir_hash_path = loaded.pkg_path / ".gaia" / "ir_hash"
    ir_json_path = loaded.pkg_path / ".gaia" / "ir.json"
    compiled_json = compiled.to_json()
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
    if stored_ir.get("ir_hash") != compiled.graph.ir_hash or stored_ir != compiled_json:
        typer.echo("Error: compiled artifacts are stale; run `gaia compile` again.", err=True)
        raise typer.Exit(1)

    factor_graph = lower_local_graph(compiled.graph)
    fg_errors = factor_graph.validate()
    if fg_errors:
        for error in fg_errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)

    engine = InferenceEngine()
    inference_result = engine.run(factor_graph)
    result = inference_result.bp_result

    gaia_dir = loaded.pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)

    gaia_ver = gaia_lang_version()

    knowledge_by_id = {knowledge.id: knowledge for knowledge in compiled.graph.knowledges}
    beliefs_payload = {
        "ir_hash": compiled.graph.ir_hash,
        "gaia_lang_version": gaia_ver,
        "beliefs": [
            {
                "knowledge_id": knowledge_id,
                "label": knowledge_by_id[knowledge_id].label,
                "belief": belief,
            }
            for knowledge_id, belief in sorted(result.beliefs.items())
            if knowledge_id in knowledge_by_id
        ],
        "diagnostics": asdict(result.diagnostics),
    }
    _write_json(gaia_dir / "beliefs.json", beliefs_payload)

    typer.echo(f"Inferred {len(result.beliefs)} beliefs")
    method_label = inference_result.method_used.upper()
    exact_label = " (exact)" if inference_result.is_exact else ""
    typer.echo(f"Method: {method_label}{exact_label}, {inference_result.elapsed_ms:.0f}ms")
    if result.diagnostics.iterations_run:
        typer.echo(
            f"Converged: {result.diagnostics.converged} "
            f"after {result.diagnostics.iterations_run} iterations"
        )
    typer.echo(f"Output: {gaia_dir / 'beliefs.json'}")
