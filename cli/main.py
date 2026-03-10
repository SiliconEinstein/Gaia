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


@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Elaborate: parse + resolve + instantiate params."""
    from libs.lang.build_store import save_build
    from libs.lang.elaborator import elaborate_package
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs

    pkg_path = Path(path)
    try:
        pkg = load_package(pkg_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    build_dir = pkg_path / ".gaia" / "build"
    save_build(elaborated, build_dir)

    n_mods = len(pkg.loaded_modules)
    n_prompts = len(elaborated.prompts)
    typer.echo(f"Built {pkg.name}: {n_mods} modules, {n_prompts} elaborated prompts")
    typer.echo(f"Artifacts: {build_dir}/")


@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    mock: bool = typer.Option(False, "--mock", help="Use mock reviewer (no LLM calls)"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="LLM model for review"),
    concurrency: int = typer.Option(5, "--concurrency", "-j", help="Max parallel reviews"),
) -> None:
    """LLM reviews chains -> sidecar report (.gaia/reviews/)."""
    from datetime import datetime, timezone

    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.review_store import write_review
    from libs.lang.loader import load_package

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Check build exists — look for .md files
    md_files = sorted(build_dir.glob("*.md")) if build_dir.exists() else []
    if not md_files:
        typer.echo(f"Error: no build artifacts.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Parse chain sections from all .md files
    import re

    chain_header_re = re.compile(r"^## (\w+) \(\w+\)$", re.MULTILINE)
    all_chain_data = []
    for md_file in md_files:
        content = md_file.read_text()
        # Find all valid chain header positions
        matches = list(chain_header_re.finditer(content))
        for j, m in enumerate(matches):
            chain_name = m.group(1)
            start = m.start()
            end = matches[j + 1].start() if j + 1 < len(matches) else len(content)
            chain_section = content[start:end].strip()
            all_chain_data.append(
                {
                    "name": chain_name,
                    "markdown": chain_section,
                }
            )

    # 3. Load package for metadata + compute fingerprint
    pkg = load_package(pkg_path)
    fingerprint = _compute_source_fingerprint(pkg_path)

    # 4. Create reviewer
    client = MockReviewClient() if mock else ReviewClient(model=model)

    # 5. Review chains in parallel
    chain_reviews = asyncio.run(_review_chains_parallel(client, all_chain_data, concurrency))

    # 6. Write sidecar
    now = datetime.now(timezone.utc)
    review_data = {
        "package": pkg.name,
        "model": "mock" if mock else model,
        "timestamp": now.isoformat(),
        "source_fingerprint": fingerprint,
        "chains": chain_reviews,
    }
    review_path = write_review(review_data, reviews_dir)

    n_chains = len(chain_reviews)
    typer.echo(f"Reviewed {n_chains} chains for {pkg.name}")
    typer.echo(f"Report: {review_path}")


def _compute_source_fingerprint(pkg_path: Path) -> str:
    """SHA-256 of all YAML source files sorted by name."""
    import hashlib

    h = hashlib.sha256()
    for yaml_file in sorted(pkg_path.glob("*.yaml")):
        h.update(yaml_file.read_bytes())
    return h.hexdigest()[:16]


async def _review_chains_parallel(
    client: "ReviewClient | MockReviewClient",  # noqa: F821
    chain_data_list: list[dict],
    concurrency: int,
) -> list[dict]:
    """Review chains concurrently with bounded parallelism."""
    semaphore = asyncio.Semaphore(concurrency)
    total = len(chain_data_list)
    results: list[dict] = [{}] * total
    started = 0

    async def review_one(index: int, chain_data: dict) -> None:
        nonlocal started
        async with semaphore:
            started += 1
            typer.echo(f"  [{started}/{total}] Reviewing {chain_data['name']}...")
            results[index] = await client.areview_chain(chain_data)

    await asyncio.gather(*(review_one(i, cd) for i, cd in enumerate(chain_data_list)))
    return results


@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile a factor graph (from review) and run BP to compute beliefs."""
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.lang.compiler import compile_factor_graph
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Check build exists
    if not build_dir.exists():
        typer.echo(f"Error: no build artifacts found.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Read review file
    try:
        if review_file:
            review = read_review(Path(review_file))
        else:
            latest = find_latest_review(reviews_dir)
            review = read_review(latest)
    except FileNotFoundError:
        typer.echo(
            f"Error: no review file found.\n"
            f"Run 'gaia review {path}' first, or specify --review <path>.",
            err=True,
        )
        raise typer.Exit(1)

    # 3. Load package from source YAML, resolve refs, merge review
    pkg = load_package(pkg_path)
    pkg = resolve_refs(pkg)
    fp = _compute_source_fingerprint(pkg_path)
    pkg = merge_review(pkg, review, source_fingerprint=fp)

    # 4. Compile factor graph
    compiled_fg = compile_factor_graph(pkg)

    # 5. Convert to inference engine FactorGraph and run BP
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

    # 6. Map back to names and output
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    typer.echo(f"Package: {pkg.name}")
    typer.echo(f"Variables: {len(compiled_fg.variables)}")
    typer.echo(f"Factors: {len(compiled_fg.factors)}")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        prior = compiled_fg.variables.get(name, "?")
        typer.echo(f"  {name}: prior={prior} -> belief={belief:.4f}")


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
    """Run full pipeline and triple-write to LanceDB + Kuzu."""
    from cli.lang_to_storage import convert_package_to_storage
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.lang.compiler import compile_factor_graph
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Check build exists
    if not build_dir.exists():
        typer.echo(
            f"Error: no build artifacts found.\nRun 'gaia build {pkg_path}' first.",
            err=True,
        )
        raise typer.Exit(1)

    # 2. Read review file
    try:
        latest = find_latest_review(reviews_dir)
        review = read_review(latest)
    except FileNotFoundError:
        typer.echo(
            f"Error: no review file found.\nRun 'gaia review {pkg_path}' first.",
            err=True,
        )
        raise typer.Exit(1)

    # 3. Load package, resolve refs, merge review
    pkg = load_package(pkg_path)
    pkg = resolve_refs(pkg)
    fp = _compute_source_fingerprint(pkg_path)
    pkg = merge_review(pkg, review, source_fingerprint=fp)

    # 4. Compile factor graph and run BP
    compiled_fg = compile_factor_graph(pkg)

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

    # 5. Map beliefs back to names
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    # 6. Convert to storage models
    storage_result = convert_package_to_storage(pkg, compiled_fg, named_beliefs)

    # 7. Initialize StorageManager with Kuzu backend
    config = StorageConfig(
        lancedb_path=db_path,
        graph_backend="kuzu",
        deployment_mode="local",
    )
    storage = StorageManager(config)

    try:
        # 8. Delete existing data for idempotent re-publish
        node_ids = [n.id for n in storage_result.nodes]
        edge_ids = [e.id for e in storage_result.edges]
        if node_ids:
            table = storage.lance._get_or_create_table()
            id_list = ", ".join(str(i) for i in node_ids)
            try:
                table.delete(f"id IN ({id_list})")
            except Exception:
                pass  # Table may be empty or IDs don't exist yet
        if edge_ids and storage.graph:
            for eid in edge_ids:
                storage.graph._conn.execute(
                    "MATCH (h:Hyperedge {id: $eid}) DETACH DELETE h", {"eid": eid}
                )

        # 9. Triple-write: LanceDB nodes
        saved_ids = await storage.lance.save_nodes(storage_result.nodes)

        # 10. Kuzu edges
        edge_ids: list[int] = []
        if storage.graph and storage_result.edges:
            edge_ids = await storage.graph.create_hyperedges_bulk(storage_result.edges)

        # 11. Embeddings (optional — requires OPENAI_API_KEY)
        n_embeddings = 0
        try:
            import litellm

            # Build (node_id, content) pairs, skipping empty content
            pairs = []
            for n in storage_result.nodes:
                c = n.content if isinstance(n.content, str) else str(n.content)
                c = c.strip()
                if c:
                    pairs.append((n.id, c))

            if pairs:
                emb_ids, emb_texts = zip(*pairs)
                response = litellm.embedding(model="text-embedding-3-small", input=list(emb_texts))
                embeddings = [d["embedding"] for d in response.data]
                await storage.vector.insert_batch(list(emb_ids), embeddings)
                n_embeddings = len(embeddings)
        except Exception as e:
            typer.echo(f"  Skipped embeddings: {e}")

        # 12. Write beliefs back to LanceDB
        belief_map = {n.id: n.belief for n in storage_result.nodes if n.belief is not None}
        if belief_map:
            await storage.lance.update_beliefs(belief_map)

        emb_str = f"\n  Embeddings: {n_embeddings} written" if n_embeddings else ""
        typer.echo(
            f"Published {pkg.name} to local databases:\n"
            f"  Nodes: {len(saved_ids)} written to LanceDB ({db_path})\n"
            f"  Edges: {len(edge_ids)} written to Kuzu ({db_path}/kuzu)"
            f"{emb_str}"
        )
    finally:
        await storage.close()


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
        "declarations": [
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
    node_id: int = typer.Option(None, "--id", help="Look up a node by ID"),
) -> None:
    """Search published nodes in local LanceDB."""
    import asyncio
    import os

    if query is None and node_id is None:
        typer.echo("Error: provide either a QUERY or --id <id>", err=True)
        raise typer.Exit(1)

    if db_path is None:
        db_path = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")

    if node_id is not None:
        asyncio.run(_lookup_node(node_id, db_path))
    else:
        asyncio.run(_search_db(query, db_path, limit))


async def _lookup_node(node_id: int, db_path: str) -> None:
    """Look up a single node by ID."""
    from libs.storage.lance_store import LanceStore

    store = LanceStore(db_path)
    try:
        nodes = await store.load_nodes_bulk([node_id])
        if not nodes:
            typer.echo(f"Node {node_id} not found.")
            return
        n = nodes[0]
        typer.echo(f"[{n.id}] {n.title or '?'} ({n.type})")
        typer.echo(f"  prior: {n.prior}  belief: {n.belief}")
        content = n.content if isinstance(n.content, str) else str(n.content)
        if content.strip():
            typer.echo(f"  content: {content.strip()}")
        if n.keywords:
            typer.echo(f"  keywords: {', '.join(n.keywords)}")
    finally:
        await store.close()


async def _search_db(query: str, db_path: str, limit: int) -> None:
    """Full-text search over published nodes in LanceDB.

    Uses FTS index first; falls back to SQL LIKE filter for queries the
    default tokenizer cannot handle (e.g. CJK text without spaces).
    """
    from libs.storage.lance_store import LanceStore

    store = LanceStore(db_path)
    try:
        # Try FTS index first (works well for Latin-script text)
        fts_results = await store.fts_search(query, k=limit)
        if fts_results:
            node_ids = [nid for nid, _ in fts_results]
            nodes = await store.load_nodes_bulk(node_ids)
            scores = {nid: score for nid, score in fts_results}
        else:
            # Fallback: SQL LIKE filter for CJK / unsegmented text
            nodes = await _content_like_search(store, query, limit)
            scores = {}

        if not nodes:
            typer.echo("No results found.")
            return

        for node in nodes:
            score = scores.get(node.id, 0)
            belief_str = f" belief={node.belief:.4f}" if node.belief else ""
            score_str = f"  score={score:.3f}" if score else ""
            typer.echo(
                f"  [{node.id}] {node.title or '?'} ({node.type}) "
                f"prior={node.prior}{belief_str}{score_str}"
            )
            content = node.content if isinstance(node.content, str) else str(node.content)
            if content.strip():
                snippet = content.strip()[:100]
                typer.echo(f"    {snippet}...")
    finally:
        await store.close()


async def _content_like_search(
    store: "LanceStore",  # noqa: F821
    query: str,
    limit: int,
) -> list:
    """Fallback substring search using SQL LIKE on the content column."""
    from libs.storage.lance_store import _row_to_node

    table = store._get_or_create_table()
    if table.count_rows() == 0:
        return []
    escaped = query.replace("'", "''")
    rows = table.search().where(f"content LIKE '%{escaped}%'").limit(limit).to_list()
    return [_row_to_node(r) for r in rows]


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
