"""gaia infer -- run BP from compiled IR with metadata priors."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from gaia.bp import FactorGraph, lower_local_graph, merge_factor_graphs
from gaia.bp.engine import InferenceEngine
from gaia.cli._packages import (
    GaiaCliError,
    apply_package_priors,
    collect_foreign_node_priors,
    collect_strategy_conditional_params,
    compile_loaded_package_artifact,
    ensure_package_env,
    gaia_lang_version,
    load_dependency_compiled_graphs,
    load_gaia_package,
)
from gaia.cli.commands._review_manifest import load_or_generate_review_manifest
from gaia.ir.validator import validate_local_graph


def _write_json(path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


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
    DSL pairing during compilation). For v6 action-backed Strategy/Operator
    targets, ReviewManifest gates whether the target participates in BP;
    review status is qualitative and never supplies numeric priors.

    With ``--depth N`` (N>0), dependency packages' factor graphs are
    merged for joint cross-package inference instead of using flat
    prior injection from dep_beliefs/.
    """
    try:
        ensure_package_env(Path(path).resolve())
        loaded = load_gaia_package(path)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
        review_manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)
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

    if depth != 0:
        strategy_params = collect_strategy_conditional_params(compiled)
        # Joint cross-package inference: merge dependency factor graphs
        try:
            dep_compiled = load_dependency_compiled_graphs(loaded.project_config, depth=depth)
        except GaiaCliError as exc:
            typer.echo(str(exc), err=True)
            raise typer.Exit(1)

        if not dep_compiled:
            typer.echo("No -gaia dependencies found; running local inference only")

        dep_factor_graphs: list[tuple[str, FactorGraph, str]] = []
        for dep in dep_compiled:
            dep_review_manifest = load_or_generate_review_manifest(dep.root, dep)
            dep_fg = lower_local_graph(dep.graph, review_manifest=dep_review_manifest)
            dep_prefix = f"{dep.graph.namespace}:{dep.graph.package_name}::"
            dep_factor_graphs.append((dep.import_name, dep_fg, dep_prefix))
            typer.echo(
                f"Loaded dep '{dep.import_name}': "
                f"{len(dep.graph.knowledges)} knowledge, "
                f"{len(dep_fg.factors)} factors"
            )

        # Lower local graph WITHOUT foreign node priors — the dep graphs
        # provide the full reasoning structure instead of flat priors
        local_fg = lower_local_graph(
            compiled.graph,
            strategy_conditional_params=strategy_params,
            review_manifest=review_manifest,
        )
        local_prefix = f"{compiled.graph.namespace}:{compiled.graph.package_name}::"

        if dep_factor_graphs:
            factor_graph = merge_factor_graphs(
                local_fg, dep_factor_graphs, local_prefix=local_prefix
            )
            typer.echo(
                f"Merged graph: {len(factor_graph.variables)} variables, "
                f"{len(factor_graph.factors)} factors"
            )
        else:
            factor_graph = local_fg
    else:
        # Default: flat prior injection from dep_beliefs/
        foreign_priors = collect_foreign_node_priors(compiled.graph, loaded.pkg_path)
        if foreign_priors:
            typer.echo(f"Loaded {len(foreign_priors)} upstream belief(s) for foreign nodes")
        factor_graph = lower_local_graph(
            compiled.graph,
            node_priors=foreign_priors or None,
            strategy_conditional_params=collect_strategy_conditional_params(compiled),
            review_manifest=review_manifest,
        )
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
