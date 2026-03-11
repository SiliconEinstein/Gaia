"""Gaia CLI — proof assistant for probabilistic defeasible reasoning."""

from __future__ import annotations

import asyncio
from pathlib import Path

import typer
import yaml

app = typer.Typer(
    name="gaia",
    help="Gaia — proof assistant for probabilistic defeasible reasoning.",
    no_args_is_help=True,
)


def _load_with_deps(pkg_path: Path):
    """Load a package and recursively resolve its declared dependencies."""
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs

    pkg = load_package(pkg_path)

    deps: dict[str, object] = {}
    for dep in pkg.dependencies:
        dep_path = pkg_path.parent / dep.package
        if not dep_path.exists():
            typer.echo(f"Error: dependency '{dep.package}' not found at {dep_path}", err=True)
            raise typer.Exit(1)
        deps[dep.package] = _load_with_deps(dep_path)

    return resolve_refs(pkg, deps=deps or None)


@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Elaborate: parse + resolve + instantiate params."""
    from cli.manifest import save_manifest
    from libs.lang.build_store import save_build
    from libs.lang.elaborator import elaborate_package

    pkg_path = Path(path)
    try:
        pkg = _load_with_deps(pkg_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    elaborated = elaborate_package(pkg)

    build_dir = pkg_path / ".gaia" / "build"
    save_build(elaborated, build_dir)
    save_manifest(pkg, build_dir, pkg_path=pkg_path)

    n_mods = len(pkg.loaded_modules)
    n_prompts = len(elaborated.prompts)
    typer.echo(f"Built {pkg.name}: {n_mods} modules, {n_prompts} elaborated prompts")
    typer.echo(f"Artifacts: {build_dir}/")


@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    mock: bool = typer.Option(False, "--mock", help="Use mock reviewer (no LLM calls)"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="LLM model for review"),
) -> None:
    """LLM reviews chains -> sidecar report (.gaia/reviews/)."""
    from datetime import datetime, timezone

    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.manifest import deserialize_package
    from cli.review_store import write_review

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Check build exists — require package.md
    package_md = build_dir / "package.md"
    if not package_md.exists():
        typer.echo(f"Error: no build artifacts.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    md_content = package_md.read_text()

    # 2. Load package metadata from manifest
    manifest_path = build_dir / "manifest.json"
    if manifest_path.exists():
        pkg = deserialize_package(manifest_path)
    else:
        from libs.lang.loader import load_package

        pkg = load_package(pkg_path)

    fingerprint = _compute_source_fingerprint(pkg_path)

    # 3. Create reviewer
    client = MockReviewClient() if mock else ReviewClient(model=model)

    # 4. Review entire package in one call
    typer.echo(f"Reviewing {pkg.name}...")
    if mock:
        result = client.review_package({"package": pkg.name, "markdown": md_content})
    else:
        result = asyncio.run(client.areview_package({"package": pkg.name, "markdown": md_content}))

    # 5. Write sidecar
    now = datetime.now(timezone.utc)
    review_data = {
        "package": pkg.name,
        "model": "mock" if mock else model,
        "timestamp": now.isoformat(),
        "source_fingerprint": fingerprint,
        "summary": result.get("summary", ""),
        "chains": result.get("chains", []),
    }
    review_path = write_review(review_data, reviews_dir)

    n_chains = len(review_data["chains"])
    typer.echo(f"Reviewed {n_chains} chains for {pkg.name}")
    typer.echo(f"Report: {review_path}")


def _compute_source_fingerprint(pkg_path: Path) -> str:
    """SHA-256 of all YAML source files sorted by name."""
    import hashlib

    h = hashlib.sha256()
    for yaml_file in sorted(pkg_path.glob("*.yaml")):
        h.update(yaml_file.read_bytes())
    return h.hexdigest()[:16]


@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile a factor graph (from review) and run BP to compute beliefs."""
    import uuid

    from cli.infer_store import save_infer_result
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph
    from libs.lang.compiler import compile_factor_graph

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"
    infer_dir = pkg_path / ".gaia" / "infer"

    # 1. Check build exists
    if not build_dir.exists():
        typer.echo(f"Error: no build artifacts found.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Load package from manifest.json (falls back to source YAML)
    manifest_path = build_dir / "manifest.json"
    if manifest_path.exists():
        pkg = deserialize_package(manifest_path)
    else:
        pkg = _load_with_deps(pkg_path)

    # 3. Read review file
    resolved_review_file: str | None = None
    try:
        if review_file:
            review = read_review(Path(review_file))
            resolved_review_file = review_file
        else:
            latest = find_latest_review(reviews_dir)
            review = read_review(latest)
            resolved_review_file = str(latest)
    except FileNotFoundError:
        typer.echo(
            f"Error: no review file found.\n"
            f"Run 'gaia review {path}' first, or specify --review <path>.",
            err=True,
        )
        raise typer.Exit(1)

    # 4. Merge review into package
    fp = _compute_source_fingerprint(pkg_path)
    pkg = merge_review(pkg, review, source_fingerprint=fp)

    # 5. Compile factor graph
    compiled_fg = compile_factor_graph(pkg)

    # 6. Convert to inference engine FactorGraph and run BP
    bp_fg = FactorGraph()
    name_to_id: dict[str, int] = {}
    for i, (name, prior) in enumerate(compiled_fg.variables.items()):
        node_id = i + 1
        name_to_id[name] = node_id
        bp_fg.add_variable(node_id, prior)

    for j, factor in enumerate(compiled_fg.factors):
        premise_ids = [name_to_id[n] for n in factor["premises"] if n in name_to_id]
        conclusion_ids = [name_to_id[n] for n in factor["conclusions"] if n in name_to_id]
        bp_fg.add_factor(
            edge_id=j + 1,
            premises=premise_ids,
            conclusions=conclusion_ids,
            probability=factor["probability"],
            edge_type=factor.get("edge_type", "deduction"),
        )

    bp = BeliefPropagation()
    beliefs = bp.run(bp_fg)

    # 7. Map back to names
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    # 8. Save infer_result.json
    bp_run_id = str(uuid.uuid4())
    variables_out = {
        name: {"prior": compiled_fg.variables[name], "belief": named_beliefs.get(name)}
        for name in compiled_fg.variables
    }
    save_infer_result(
        pkg_name=pkg.name,
        variables=variables_out,
        factors=compiled_fg.factors,
        bp_run_id=bp_run_id,
        review_file=resolved_review_file,
        source_fingerprint=fp,
        infer_dir=infer_dir,
    )

    # 9. Print results
    typer.echo(f"Package: {pkg.name}")
    typer.echo(f"Variables: {len(compiled_fg.variables)}")
    typer.echo(f"Factors: {len(compiled_fg.factors)}")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        prior = compiled_fg.variables.get(name, "?")
        typer.echo(f"  {name}: prior={prior} -> belief={belief:.4f}")
    typer.echo(f"\nResults: {infer_dir / 'infer_result.json'}")


@app.command()
def publish(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    git: bool = typer.Option(False, "--git", help="Publish via git add+commit+push"),
    local: bool = typer.Option(False, "--local", help="Import to local databases (LanceDB + Kuzu)"),
    server: bool = typer.Option(False, "--server", help="Publish to Gaia server API"),
    db_path: str = typer.Option(
        None,
        "--db-path",
        help="LanceDB path (default: GAIA_LANCEDB_PATH or ./data/lancedb/gaia)",
    ),
) -> None:
    """Publish to git, local databases, or server."""
    import asyncio
    import os
    import subprocess

    if not git and not local and not server:
        typer.echo("Error: specify --git, --local, or --server", err=True)
        raise typer.Exit(1)

    pkg_path = Path(path)

    if git:
        try:
            subprocess.run(["git", "add", "."], cwd=pkg_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "gaia: publish package"],
                cwd=pkg_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(["git", "push"], cwd=pkg_path, check=True, capture_output=True)
            typer.echo(f"Published {pkg_path} via git")
        except subprocess.CalledProcessError as e:
            typer.echo(f"Git error: {e}", err=True)
            raise typer.Exit(1)

    if local:
        resolved_db_path = db_path or os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")
        asyncio.run(_publish_local(pkg_path, resolved_db_path))

    if server:
        typer.echo("Server publishing not yet implemented")
        raise typer.Exit(1)


async def _publish_local(pkg_path: Path, db_path: str) -> None:
    """Convert artifacts to v2 models and write to LanceDB + Kuzu."""
    from cli.infer_store import load_infer_result
    from cli.lang_to_v2 import convert_to_v2
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, read_review
    from libs.storage_v2.kuzu_graph_store import KuzuGraphStore
    from libs.storage_v2.lance_content_store import LanceContentStore

    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"
    infer_dir = pkg_path / ".gaia" / "infer"
    publish_dir = pkg_path / ".gaia" / "publish"

    # 1. Read artifacts
    manifest_path = build_dir / "manifest.json"
    infer_path = infer_dir / "infer_result.json"

    if not manifest_path.exists():
        typer.echo("Error: no manifest.json. Run 'gaia build' first.", err=True)
        raise typer.Exit(1)
    if not infer_path.exists():
        typer.echo("Error: no infer_result.json. Run 'gaia infer' first.", err=True)
        raise typer.Exit(1)

    pkg = deserialize_package(manifest_path)
    infer_result = load_infer_result(infer_path)

    try:
        review = read_review(find_latest_review(reviews_dir))
    except FileNotFoundError:
        typer.echo("Error: no review file. Run 'gaia review' first.", err=True)
        raise typer.Exit(1)

    # 2. Extract beliefs from infer result
    beliefs = {
        name: var_data["belief"]
        for name, var_data in infer_result["variables"].items()
        if var_data.get("belief") is not None
    }

    # 3. Convert to v2 models
    data = convert_to_v2(
        pkg=pkg,
        review=review,
        beliefs=beliefs,
        bp_run_id=infer_result.get("bp_run_id", "unknown"),
    )

    # 4. Initialize v2 stores
    content = LanceContentStore(db_path)
    await content.initialize()
    graph = KuzuGraphStore(f"{db_path}/kuzu")
    await graph.initialize_schema()

    # 5. Idempotent cleanup
    await content.delete_package(data.package.package_id)
    await graph.delete_package(data.package.package_id)

    # 6. Write to LanceDB
    await content.write_closures(data.closures)
    await content.write_chains(data.chains)
    await content.write_package(data.package, data.modules)
    if data.probabilities:
        await content.write_probabilities(data.probabilities)
    if data.belief_snapshots:
        await content.write_belief_snapshots(data.belief_snapshots)

    # 7. Write to Kuzu
    await graph.write_topology(data.closures, data.chains)
    if data.belief_snapshots:
        await graph.update_beliefs(data.belief_snapshots)

    # 8. Write receipt
    import json
    from datetime import datetime, timezone

    publish_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "version": 1,
        "package_id": data.package.package_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "stats": {
            "closures": len(data.closures),
            "chains": len(data.chains),
            "probabilities": len(data.probabilities),
            "belief_snapshots": len(data.belief_snapshots),
        },
        "closure_ids": [c.closure_id for c in data.closures],
        "chain_ids": [ch.chain_id for ch in data.chains],
    }
    (publish_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))

    typer.echo(
        f"Published {pkg.name} to v2 storage:\n"
        f"  Closures: {len(data.closures)} written to LanceDB ({db_path})\n"
        f"  Chains: {len(data.chains)} written to LanceDB + Kuzu"
    )

    await graph.close()


@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Package name"),
) -> None:
    """Initialize a new knowledge package."""
    pkg_dir = Path(name)
    if pkg_dir.exists():
        typer.echo(f"Error: directory '{name}' already exists", err=True)
        raise typer.Exit(1)

    pkg_dir.mkdir(parents=True)

    # package.yaml
    pkg_data = {
        "name": name,
        "version": "0.1.0",
        "manifest": {
            "description": f"Knowledge package: {name}",
            "authors": [],
            "license": "CC-BY-4.0",
        },
        "modules": ["motivation"],
        "export": [],
    }
    (pkg_dir / "package.yaml").write_text(yaml.dump(pkg_data, allow_unicode=True, sort_keys=False))

    # motivation.yaml
    mod_data = {
        "type": "motivation_module",
        "name": "motivation",
        "knowledge": [
            {
                "type": "question",
                "name": "main_question",
                "content": "What is the main research question?",
            }
        ],
        "export": ["main_question"],
    }
    (pkg_dir / "motivation.yaml").write_text(
        yaml.dump(mod_data, allow_unicode=True, sort_keys=False)
    )

    typer.echo(f"Initialized package '{name}' in ./{name}/")


@app.command()
def show(
    name: str = typer.Argument(..., help="Knowledge object name to inspect"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Show knowledge object details + connected chains."""
    from libs.lang.loader import load_package
    from libs.lang.models import ChainExpr, Ref, StepApply, StepRef

    pkg_path = Path(path)
    try:
        pkg = load_package(pkg_path)
        from libs.lang.resolver import resolve_refs

        pkg = resolve_refs(pkg)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Find knowledge object
    target = None
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            actual = decl._resolved if isinstance(decl, Ref) and decl._resolved else decl
            if actual.name == name:
                target = actual
                break

    if target is None:
        typer.echo(f"Error: knowledge object '{name}' not found", err=True)
        raise typer.Exit(1)

    # Display knowledge object
    prior_str = f" | prior: {target.prior}" if target.prior is not None else ""
    typer.echo(f"{target.name} ({target.type}){prior_str}")
    if hasattr(target, "content") and target.content:
        content = target.content.strip()
        if len(content) > 120:
            content = content[:120] + "..."
        typer.echo(f'  content: "{content}"')
    typer.echo()

    # Find connected chains
    typer.echo("  Referenced in chains:")
    found_any = False
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if not isinstance(decl, ChainExpr):
                continue
            for step in decl.steps:
                refs_in_step = []
                if isinstance(step, StepRef) and step.ref == name:
                    refs_in_step.append(name)
                elif isinstance(step, StepApply):
                    refs_in_step = [a.ref for a in step.args if a.ref == name]
                if refs_in_step:
                    edge = decl.edge_type or "deduction"
                    typer.echo(f"    {decl.name} ({edge})")
                    found_any = True
                    break

    if not found_any:
        typer.echo("    (none)")


@app.command()
def search(
    query: str = typer.Argument(None, help="Search query text"),
    db_path: str = typer.Option(
        None,
        "--db-path",
        help="LanceDB path (default: GAIA_LANCEDB_PATH or ./data/lancedb/gaia)",
    ),
    limit: int = typer.Option(10, "--limit", "-k", help="Max results"),
    closure_id: str = typer.Option(None, "--id", help="Look up a closure by ID"),
) -> None:
    """Search published closures in local LanceDB (v2 storage)."""
    import asyncio
    import os

    if query is None and closure_id is None:
        typer.echo("Error: provide either a QUERY or --id <closure_id>", err=True)
        raise typer.Exit(1)

    if db_path is None:
        db_path = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")

    if closure_id is not None:
        asyncio.run(_lookup_closure(closure_id, db_path))
    else:
        asyncio.run(_search_closures(query, db_path, limit))


async def _lookup_closure(closure_id: str, db_path: str) -> None:
    """Look up a single closure by ID, including latest belief if available."""
    from libs.storage_v2.lance_content_store import LanceContentStore

    store = LanceContentStore(db_path)
    await store.initialize()
    closure = await store.get_closure(closure_id)
    if closure is None:
        typer.echo(f"Closure '{closure_id}' not found.")
        return

    # Try to get belief from belief_history
    belief = None
    snapshots = await store.get_belief_history(closure_id)
    if snapshots:
        belief = snapshots[-1].belief

    belief_str = f"  belief: {belief:.4f}" if belief is not None else ""
    typer.echo(f"[{closure.closure_id}] ({closure.type})")
    typer.echo(f"  prior: {closure.prior}{belief_str}")
    content = closure.content.strip()
    if content:
        typer.echo(f"  content: {content}")
    if closure.keywords:
        typer.echo(f"  keywords: {', '.join(closure.keywords)}")


async def _search_closures(query: str, db_path: str, limit: int) -> None:
    """Full-text BM25 search over published closures in LanceDB v2.

    Uses FTS index first; falls back to SQL LIKE filter for queries the
    default tokenizer cannot handle (e.g. CJK text without spaces).
    """
    from libs.storage_v2.lance_content_store import LanceContentStore

    store = LanceContentStore(db_path)
    await store.initialize()

    # Try BM25 FTS search first (works well for Latin-script text)
    scored_closures = await store.search_bm25(query, top_k=limit)

    if scored_closures:
        # Get belief snapshots for all matched closures
        belief_map: dict[str, float] = {}
        for sc in scored_closures:
            snapshots = await store.get_belief_history(sc.closure.closure_id)
            if snapshots:
                belief_map[sc.closure.closure_id] = snapshots[-1].belief

        for sc in scored_closures:
            belief = belief_map.get(sc.closure.closure_id)
            belief_str = f" belief={belief:.4f}" if belief is not None else ""
            typer.echo(
                f"  [{sc.closure.closure_id}] ({sc.closure.type}) "
                f"prior={sc.closure.prior}{belief_str}  score={sc.score:.3f}"
            )
            content = sc.closure.content.strip()
            if content:
                snippet = content[:100]
                typer.echo(f"    {snippet}...")
        return

    # Fallback: SQL LIKE filter for CJK / unsegmented text
    results = await _content_like_search_v2(store, query, limit)
    if not results:
        typer.echo("No results found.")
        return

    # Get belief snapshots for fallback results
    belief_map_fb: dict[str, float] = {}
    for closure in results:
        snapshots = await store.get_belief_history(closure.closure_id)
        if snapshots:
            belief_map_fb[closure.closure_id] = snapshots[-1].belief

    for closure in results:
        belief = belief_map_fb.get(closure.closure_id)
        belief_str = f" belief={belief:.4f}" if belief is not None else ""
        typer.echo(f"  [{closure.closure_id}] ({closure.type}) prior={closure.prior}{belief_str}")
        content = closure.content.strip()
        if content:
            snippet = content[:100]
            typer.echo(f"    {snippet}...")


async def _content_like_search_v2(
    store: "LanceContentStore",  # noqa: F821
    query: str,
    limit: int,
) -> list:
    """Fallback substring search using SQL LIKE on the closures content column."""
    from libs.storage_v2.lance_content_store import _row_to_closure

    try:
        table = store._db.open_table("closures")
    except Exception:
        return []
    if table.count_rows() == 0:
        return []
    escaped = query.replace("'", "''")
    rows = table.search().where(f"content LIKE '%{escaped}%'").limit(limit).to_list()
    return [_row_to_closure(r) for r in rows]


@app.command()
def clean(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Remove build artifacts (.gaia/)."""
    import shutil

    gaia_dir = Path(path) / ".gaia"
    if gaia_dir.exists():
        shutil.rmtree(gaia_dir)
        typer.echo(f"Removed {gaia_dir}")
    else:
        typer.echo(f"No .gaia directory in {path}, nothing to clean.")


if __name__ == "__main__":
    app()
