"""Gaia CLI — proof assistant for probabilistic defeasible reasoning."""

from __future__ import annotations

import asyncio
from pathlib import Path
import sys

if __package__ in {None, ""}:
    repo_root = Path(__file__).resolve().parents[1]
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

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
    from libs.graph_ir import (
        save_canonicalization_log,
        save_local_canonical_graph,
        save_raw_graph,
    )
    from libs.lang.build_store import save_build
    from libs.pipeline import pipeline_build

    pkg_path = Path(path)
    try:
        result = asyncio.run(pipeline_build(pkg_path))
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    build_dir = pkg_path / ".gaia" / "build"
    graph_dir = pkg_path / ".gaia" / "graph"
    save_build(result.elaborated, build_dir)
    save_manifest(result.package, build_dir, pkg_path=pkg_path)
    save_raw_graph(result.raw_graph, graph_dir)
    save_local_canonical_graph(result.local_graph, graph_dir)
    save_canonicalization_log(result.canonicalization_log, graph_dir)

    n_mods = len(result.package.loaded_modules)
    n_prompts = len(result.elaborated.prompts)
    typer.echo(f"Built {result.package.name}: {n_mods} modules, {n_prompts} elaborated prompts")
    typer.echo(f"Artifacts: {build_dir}/")


@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    mock: bool = typer.Option(False, "--mock", help="Use mock reviewer (no LLM calls)"),
    model: str = typer.Option("gpt-5-mini", "--model", help="LLM model for review"),
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
    """Build local Graph IR parameterization (from review) and run BP."""
    import uuid

    from cli.infer_store import save_infer_result
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.graph_ir import (
        adapt_local_graph_to_factor_graph,
        derive_local_parameterization,
        load_local_canonical_graph,
        save_local_parameterization,
    )
    from libs.inference.bp import BeliefPropagation

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    graph_dir = pkg_path / ".gaia" / "graph"
    reviews_dir = pkg_path / ".gaia" / "reviews"
    infer_dir = pkg_path / ".gaia" / "infer"
    inference_dir = pkg_path / ".gaia" / "inference"

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

    # 5. Load local canonical graph and derive local parameterization
    local_graph_path = graph_dir / "local_canonical_graph.json"
    if not local_graph_path.exists():
        typer.echo(
            f"Error: no local canonical graph found.\nRun 'gaia build {path}' first.",
            err=True,
        )
        raise typer.Exit(1)
    local_graph = load_local_canonical_graph(local_graph_path)
    local_parameterization = derive_local_parameterization(pkg, local_graph)
    save_local_parameterization(local_parameterization, inference_dir)

    adapted = adapt_local_graph_to_factor_graph(local_graph, local_parameterization)

    # 6. Run BP
    bp = BeliefPropagation()
    beliefs = bp.run(adapted.factor_graph)

    # 7. Map back to names
    var_id_to_local = {var_id: local_id for local_id, var_id in adapted.local_id_to_var_id.items()}
    named_beliefs = {
        adapted.local_id_to_label[var_id_to_local[var_id]]: belief
        for var_id, belief in beliefs.items()
    }

    # 8. Save infer_result.json
    bp_run_id = str(uuid.uuid4())
    variables_out = {
        adapted.local_id_to_label[local_id]: {
            "prior": local_parameterization.node_priors[local_id],
            "belief": named_beliefs.get(adapted.local_id_to_label[local_id]),
        }
        for local_id in adapted.local_id_to_var_id
    }
    save_infer_result(
        pkg_name=pkg.name,
        variables=variables_out,
        factors=adapted.factor_graph.factors,
        bp_run_id=bp_run_id,
        review_file=resolved_review_file,
        source_fingerprint=fp,
        infer_dir=infer_dir,
    )

    # 9. Print results
    typer.echo(f"Package: {pkg.name}")
    typer.echo(f"Variables: {len(adapted.factor_graph.variables)}")
    typer.echo(f"Factors: {len(adapted.factor_graph.factors)}")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        local_id = next(
            local_id for local_id, label in adapted.local_id_to_label.items() if label == name
        )
        prior = local_parameterization.node_priors.get(local_id, "?")
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
        if db_path:
            resolved_db_path = db_path
        else:
            base = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")
            resolved_db_path = base
        asyncio.run(_publish_local(pkg_path, resolved_db_path))

    if server:
        typer.echo("Server publishing not yet implemented")
        raise typer.Exit(1)


def _load_graph_ir_factors(graph_dir: Path, package_name: str) -> list:
    """Load factors from local_canonical_graph.json, mapping lcn IDs to knowledge IDs."""
    from libs.graph_ir.serialize import load_local_canonical_graph
    from libs.pipeline import _map_graph_ir_factors

    lcg_path = graph_dir / "local_canonical_graph.json"
    if not lcg_path.exists():
        return []

    local_graph = load_local_canonical_graph(lcg_path)
    return _map_graph_ir_factors(local_graph, package_name)


def _build_submission_artifact(graph_dir: Path, pkg_path: Path, package_name: str) -> object | None:
    """Assemble a PackageSubmissionArtifact from build artifacts."""
    import json
    import subprocess
    from datetime import datetime, timezone

    from libs.storage import models as storage_models

    raw_graph_path = graph_dir / "raw_graph.json"
    lcg_path = graph_dir / "local_canonical_graph.json"
    log_path = graph_dir / "canonicalization_log.json"

    if not raw_graph_path.exists() or not lcg_path.exists():
        return None

    raw_graph = json.loads(raw_graph_path.read_text())
    local_canonical_graph = json.loads(lcg_path.read_text())
    canon_log = (
        json.loads(log_path.read_text()).get("canonicalization_log", [])
        if log_path.exists()
        else []
    )

    source_files = {p.name: p.read_text() for p in pkg_path.glob("*.yaml") if p.is_file()}

    commit_hash = "unknown"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=pkg_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            commit_hash = result.stdout.strip()
    except FileNotFoundError:
        pass

    return storage_models.PackageSubmissionArtifact(
        package_name=package_name,
        commit_hash=commit_hash,
        source_files=source_files,
        raw_graph=raw_graph,
        local_canonical_graph=local_canonical_graph,
        canonicalization_log=canon_log,
        submitted_at=datetime.now(timezone.utc),
    )


async def _publish_local(pkg_path: Path, db_path: str) -> None:
    """Convert artifacts to v2 models and write to LanceDB + Kuzu."""
    from cli.infer_store import load_infer_result
    from cli.lang_to_storage import convert_to_storage
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, read_review
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    build_dir = pkg_path / ".gaia" / "build"
    graph_dir = pkg_path / ".gaia" / "graph"
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
    data = convert_to_storage(
        pkg=pkg,
        review=review,
        beliefs=beliefs,
        bp_run_id=infer_result.get("bp_run_id", "unknown"),
    )

    # 4. Load Graph IR factors (lcn IDs → knowledge IDs)
    factors = _load_graph_ir_factors(graph_dir, pkg.name)

    # 5. Build submission artifact
    submission_artifact = _build_submission_artifact(graph_dir, pkg_path, pkg.name)

    # 6. Generate embeddings for knowledge items
    from libs.embedding import StubEmbeddingModel
    from libs.storage.models import KnowledgeEmbedding

    embed_model = StubEmbeddingModel(dim=512)
    texts = [k.content for k in data.knowledge_items]
    vectors = await embed_model.embed(texts) if texts else []
    embeddings = [
        KnowledgeEmbedding(
            knowledge_id=k.knowledge_id,
            version=k.version,
            embedding=vec,
        )
        for k, vec in zip(data.knowledge_items, vectors)
    ]

    # 7. Initialize v2 stores via StorageManager
    config = StorageConfig(
        lancedb_path=db_path,
        graph_backend="kuzu",
        kuzu_path=f"{db_path}/kuzu",
    )
    mgr = StorageManager(config)
    await mgr.initialize()

    try:
        # 8. Ingest (state machine handles preparing → committed)
        await mgr.ingest_package(
            package=data.package,
            modules=data.modules,
            knowledge_items=data.knowledge_items,
            chains=data.chains,
            factors=factors or None,
            submission_artifact=submission_artifact,
            embeddings=embeddings,
        )

        # 9. Write supplementary data
        if data.probabilities:
            await mgr.add_probabilities(data.probabilities)
        if data.belief_snapshots:
            await mgr.write_beliefs(data.belief_snapshots)
    finally:
        await mgr.close()

    # 10. Write receipt
    import json
    from datetime import datetime, timezone

    publish_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "version": 1,
        "package_id": data.package.package_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "stats": {
            "knowledge_items": len(data.knowledge_items),
            "chains": len(data.chains),
            "factors": len(factors),
            "probabilities": len(data.probabilities),
            "belief_snapshots": len(data.belief_snapshots),
        },
        "knowledge_ids": [k.knowledge_id for k in data.knowledge_items],
        "chain_ids": [ch.chain_id for ch in data.chains],
    }
    (publish_dir / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2))

    typer.echo(
        f"Published {pkg.name} to v2 storage:\n"
        f"  Knowledge items: {len(data.knowledge_items)} written to LanceDB ({db_path})\n"
        f"  Chains: {len(data.chains)} written to LanceDB + Kuzu\n"
        f"  Factors: {len(factors)} written to LanceDB + Kuzu"
    )


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
    knowledge_id: str = typer.Option(None, "--id", help="Look up a knowledge item by ID"),
) -> None:
    """Search published knowledge items in local LanceDB (v2 storage)."""
    import asyncio
    import os

    if query is None and knowledge_id is None:
        typer.echo("Error: provide either a QUERY or --id <knowledge_id>", err=True)
        raise typer.Exit(1)

    if db_path is None:
        base = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")
        db_path = base

    if knowledge_id is not None:
        asyncio.run(_lookup_knowledge(knowledge_id, db_path))
    else:
        asyncio.run(_search_knowledge(query, db_path, limit))


async def _lookup_knowledge(knowledge_id: str, db_path: str) -> None:
    """Look up a single knowledge item by ID, including latest belief if available."""
    from libs.storage.lance_content_store import LanceContentStore

    store = LanceContentStore(db_path)
    await store.initialize()
    knowledge_item = await store.get_knowledge(knowledge_id)
    if knowledge_item is None:
        typer.echo(f"Knowledge item '{knowledge_id}' not found.")
        return

    # Try to get belief from belief_history
    belief = None
    snapshots = await store.get_belief_history(knowledge_id)
    if snapshots:
        belief = snapshots[-1].belief

    belief_str = f"  belief: {belief:.4f}" if belief is not None else ""
    typer.echo(f"[{knowledge_item.knowledge_id}] ({knowledge_item.type})")
    typer.echo(f"  prior: {knowledge_item.prior}{belief_str}")
    content = knowledge_item.content.strip()
    if content:
        typer.echo(f"  content: {content}")
    if knowledge_item.keywords:
        typer.echo(f"  keywords: {', '.join(knowledge_item.keywords)}")


async def _search_knowledge(query: str, db_path: str, limit: int) -> None:
    """Full-text BM25 search over published knowledge items in LanceDB v2.

    Uses FTS index first; falls back to SQL LIKE filter for queries the
    default tokenizer cannot handle (e.g. CJK text without spaces).
    """
    from libs.storage.lance_content_store import LanceContentStore

    store = LanceContentStore(db_path)
    await store.initialize()

    # Try BM25 FTS search first (works well for Latin-script text)
    scored_items = await store.search_bm25(query, top_k=limit)

    if scored_items:
        # Get belief snapshots for all matched knowledge items
        belief_map: dict[str, float] = {}
        for sc in scored_items:
            snapshots = await store.get_belief_history(sc.knowledge.knowledge_id)
            if snapshots:
                belief_map[sc.knowledge.knowledge_id] = snapshots[-1].belief

        for sc in scored_items:
            belief = belief_map.get(sc.knowledge.knowledge_id)
            belief_str = f" belief={belief:.4f}" if belief is not None else ""
            typer.echo(
                f"  [{sc.knowledge.knowledge_id}] ({sc.knowledge.type}) "
                f"prior={sc.knowledge.prior}{belief_str}  score={sc.score:.3f}"
            )
            content = sc.knowledge.content.strip()
            if content:
                snippet = content[:100]
                typer.echo(f"    {snippet}...")
        return

    # Fallback: SQL LIKE filter for CJK / unsegmented text
    results = await _content_like_search(store, query, limit)
    if not results:
        typer.echo("No results found.")
        return

    # Get belief snapshots for fallback results
    belief_map_fb: dict[str, float] = {}
    for knowledge_item in results:
        snapshots = await store.get_belief_history(knowledge_item.knowledge_id)
        if snapshots:
            belief_map_fb[knowledge_item.knowledge_id] = snapshots[-1].belief

    for knowledge_item in results:
        belief = belief_map_fb.get(knowledge_item.knowledge_id)
        belief_str = f" belief={belief:.4f}" if belief is not None else ""
        typer.echo(
            f"  [{knowledge_item.knowledge_id}] ({knowledge_item.type}) "
            f"prior={knowledge_item.prior}{belief_str}"
        )
        content = knowledge_item.content.strip()
        if content:
            snippet = content[:100]
            typer.echo(f"    {snippet}...")


async def _content_like_search(
    store: "LanceContentStore",  # noqa: F821
    query: str,
    limit: int,
) -> list:
    """Fallback substring search using SQL LIKE on the knowledge content column."""
    from libs.storage.lance_content_store import _row_to_knowledge

    try:
        table = store._db.open_table("knowledge")
    except Exception:
        return []
    if table.count_rows() == 0:
        return []
    escaped = query.replace("'", "''")
    rows = table.search().where(f"content LIKE '%{escaped}%'").limit(limit).to_list()
    return [_row_to_knowledge(r) for r in rows]


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
