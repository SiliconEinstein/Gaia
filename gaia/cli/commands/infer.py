"""gaia run infer -- run BP from compiled IR with metadata priors."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import typer

from gaia.engine._stale_check import check_compiled_artifacts
from gaia.engine.bp import FactorGraph, lower_local_graph, merge_factor_graphs
from gaia.engine.bp.engine import InferenceEngine
from gaia.engine.ir.validator import validate_local_graph
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    collect_foreign_node_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    gaia_lang_version,
    load_dependency_compiled_graphs,
    load_gaia_package,
)


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def _load_inference_inputs(path: str) -> tuple[Any, Any]:
    """Load package and compile it for inference preview."""
    try:
        ensure_package_env(Path(path).resolve())
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc
    return loaded, compiled


def _emit_graph_validation_errors(compiled: Any) -> None:
    """Validate compiled IR and raise Typer exit on errors."""
    graph_validation = validate_local_graph(compiled.graph)
    for warning in graph_validation.warnings:
        typer.echo(f"Warning: {warning}")
    if graph_validation.errors:
        for error in graph_validation.errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)


def _require_fresh_compile_artifacts(
    loaded: Any,
    compiled: Any,
    compiled_json: dict[str, Any],
) -> None:
    """Require `.gaia/ir_hash` and `.gaia/ir.json` to match the compiled graph."""
    staleness = check_compiled_artifacts(
        loaded.pkg_path,
        ir_hash=compiled.graph.ir_hash,
        compiled_payload=compiled_json,
    )
    if not staleness.ir_hash_exists or not staleness.ir_json_exists:
        typer.echo("Error: missing compiled artifacts; run `gaia build compile` first.", err=True)
        raise typer.Exit(1)
    if staleness.ir_hash_stale:
        typer.echo("Error: compiled artifacts are stale; run `gaia build compile` again.", err=True)
        raise typer.Exit(1)
    if staleness.ir_json_invalid_reason is not None:
        typer.echo(
            f"Error: .gaia/ir.json is not valid JSON: {staleness.ir_json_invalid_reason}",
            err=True,
        )
        raise typer.Exit(1)
    if staleness.ir_json_hash_mismatch or staleness.ir_json_payload_mismatch:
        typer.echo("Error: compiled artifacts are stale; run `gaia build compile` again.", err=True)
        raise typer.Exit(1)


def _dependency_factor_graphs(
    loaded: Any,
    *,
    depth: int,
) -> list[tuple[str, FactorGraph, str]]:
    """Load dependency package factor graphs for joint inference."""
    try:
        dep_compiled = load_dependency_compiled_graphs(loaded.project_config, depth=depth)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if not dep_compiled:
        typer.echo("No -gaia dependencies found; running local inference only")

    dep_factor_graphs: list[tuple[str, FactorGraph, str]] = []
    for dep in dep_compiled:
        dep_fg = lower_local_graph(dep.graph)
        dep_prefix = f"{dep.graph.namespace}:{dep.graph.package_name}::"
        dep_factor_graphs.append((dep.import_name, dep_fg, dep_prefix))
        typer.echo(
            f"Loaded dep '{dep.import_name}': "
            f"{len(dep.graph.knowledges)} knowledge, "
            f"{len(dep_fg.factors)} factors"
        )
    return dep_factor_graphs


def _lower_inference_graph(
    loaded: Any,
    compiled: Any,
    *,
    depth: int,
) -> FactorGraph:
    """Lower the compiled graph according to local or joint inference depth."""
    if depth == 0:
        foreign_priors = collect_foreign_node_priors(compiled.graph, loaded.pkg_path)
        if foreign_priors:
            typer.echo(f"Loaded {len(foreign_priors)} upstream belief(s) for foreign nodes")
        return lower_local_graph(
            compiled.graph,
            node_priors=foreign_priors or None,
        )

    dep_factor_graphs = _dependency_factor_graphs(loaded, depth=depth)
    local_fg = lower_local_graph(compiled.graph)
    local_prefix = f"{compiled.graph.namespace}:{compiled.graph.package_name}::"
    if not dep_factor_graphs:
        return local_fg
    factor_graph = merge_factor_graphs(local_fg, dep_factor_graphs, local_prefix=local_prefix)
    typer.echo(
        f"Merged graph: {len(factor_graph.variables)} variables, "
        f"{len(factor_graph.factors)} factors"
    )
    return factor_graph


def _validate_factor_graph(factor_graph: FactorGraph) -> None:
    """Validate a factor graph before inference."""
    fg_errors = factor_graph.validate()
    if fg_errors:
        for error in fg_errors:
            typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(1)


def _beliefs_payload(compiled: Any, result: Any) -> dict[str, Any]:
    """Build the persisted `.gaia/beliefs.json` payload."""
    knowledge_by_id = {knowledge.id: knowledge for knowledge in compiled.graph.knowledges}
    return {
        "ir_hash": compiled.graph.ir_hash,
        "gaia_lang_version": gaia_lang_version(),
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


def infer_command(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    depth: int = typer.Option(
        0,
        "--depth",
        help="Dependency depth for joint inference. "
        "0=flat priors (default), 1=direct deps, -1=all transitive deps.",
    ),
) -> None:
    """Run BP inference on a compiled knowledge package.

    Priors come from claim metadata (set by priors.py and reason+prior
    DSL pairing during compilation). Review status is qualitative and never
    supplies numeric priors; `gaia run infer` previews the compiled graph
    without gating unreviewed warrants. Use `gaia build check --gate` or
    `gaia inquiry review` for publish-quality review gating.

    With ``--depth N`` (N>0), dependency packages' factor graphs are
    merged for joint cross-package inference instead of using flat
    prior injection from dep_beliefs/.
    """
    loaded, compiled = _load_inference_inputs(path)
    _emit_graph_validation_errors(compiled)
    compiled_json = compiled.to_json()
    _require_fresh_compile_artifacts(loaded, compiled, compiled_json)

    factor_graph = _lower_inference_graph(loaded, compiled, depth=depth)
    _validate_factor_graph(factor_graph)

    engine = InferenceEngine()
    inference_result = engine.run(factor_graph)
    result = inference_result.result

    gaia_dir = loaded.pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)

    _write_json(gaia_dir / "beliefs.json", _beliefs_payload(compiled, result))

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
