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

app = typer.Typer(
    name="gaia",
    help="Gaia — proof assistant for probabilistic defeasible reasoning.",
    no_args_is_help=True,
)


@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    format: str = typer.Option("md", "--format", help="Output format: md, json, all"),
    proof_state: bool = typer.Option(False, "--proof-state", help="Output proof state report"),
) -> None:
    """Build a knowledge package."""
    pkg_path = Path(path)

    # Require Typst package
    if not (pkg_path / "typst.toml").exists():
        typer.echo(
            "Error: no typst.toml found. Only Typst packages are supported.\n"
            "Create a typst.toml in the package directory.",
            err=True,
        )
        raise typer.Exit(1)

    _build_typst(pkg_path, format, proof_state=proof_state)


def _build_typst(pkg_path: Path, format: str, proof_state: bool = False) -> None:
    """Build a Typst-based knowledge package."""
    import json as json_mod

    from libs.graph_ir import save_canonicalization_log, save_local_canonical_graph, save_raw_graph
    from libs.pipeline import pipeline_build

    build_dir = pkg_path / ".gaia" / "build"
    graph_dir = pkg_path / ".gaia" / "graph"
    build_dir.mkdir(parents=True, exist_ok=True)

    # Run unified pipeline
    result = asyncio.run(pipeline_build(pkg_path))

    # Save Graph IR artifacts
    save_raw_graph(result.raw_graph, graph_dir)
    save_local_canonical_graph(result.local_graph, graph_dir)
    save_canonicalization_log(result.canonicalization_log, graph_dir)

    # Save graph_data as JSON
    json_path = build_dir / "graph_data.json"
    json_path.write_text(json_mod.dumps(result.graph_data, ensure_ascii=False, indent=2))

    # Save markdown
    if format in ("md", "all"):
        from libs.lang.typst_renderer import render_typst_to_markdown

        md = render_typst_to_markdown(pkg_path)
        md_path = build_dir / "package.md"
        md_path.write_text(md)
        typer.echo(f"Markdown: {md_path}")

    if format in ("typst", "all"):
        from libs.lang.typst_clean_renderer import render_typst_to_clean_typst

        typ = render_typst_to_clean_typst(pkg_path)
        typ_path = build_dir / "package.typ"
        typ_path.write_text(typ)
        typer.echo(f"Typst: {typ_path}")

    if format in ("json", "all"):
        json_out = build_dir / "graph.json"
        json_out.write_text(json_mod.dumps(result.graph_data, ensure_ascii=False, indent=2))
        typer.echo(f"Graph JSON: {json_out}")

    if proof_state:
        from libs.lang.proof_state import analyze_proof_state

        state = analyze_proof_state(result.graph_data)
        report_path = build_dir / "proof_state.txt"
        report_path.write_text(state["report"])
        typer.echo(f"Proof state: {report_path}")
        typer.echo(state["report"])

    n_nodes = len(result.local_graph.knowledge_nodes)
    n_factors = len(result.local_graph.factor_nodes)
    typer.echo(f"Built {result.graph_data['package']}: {n_nodes} nodes, {n_factors} factors")
    typer.echo(f"Artifacts: {graph_dir}/")
    typer.echo("Build complete.")


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
        from libs.pipeline import pipeline_build, pipeline_infer, pipeline_publish, pipeline_review

        if not (pkg_path / "typst.toml").exists():
            typer.echo("Error: no typst.toml found. Only Typst packages are supported.", err=True)
            raise typer.Exit(1)

        resolved_db_path = db_path or os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")

        async def _run_pipeline():
            build_result = await pipeline_build(pkg_path)
            review_result = await pipeline_review(build_result, mock=True)
            infer_result = await pipeline_infer(build_result, review_result)
            return await pipeline_publish(
                build_result, review_result, infer_result, db_path=resolved_db_path
            )

        result = asyncio.run(_run_pipeline())
        typer.echo(
            f"Published {result.package_id} to v2 storage:\n"
            f"  Knowledge items: {result.stats['knowledge_items']}\n"
            f"  Chains: {result.stats['chains']}\n"
            f"  Factors: {result.stats['factors']}"
        )

    if server:
        typer.echo("Server publishing not yet implemented")
        raise typer.Exit(1)


@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Package name"),
) -> None:
    """Initialize a new Typst knowledge package."""
    pkg_dir = Path(name)
    pkg_name = pkg_dir.name
    if pkg_dir.exists():
        typer.echo(f"Error: directory '{name}' already exists", err=True)
        raise typer.Exit(1)

    pkg_dir.mkdir(parents=True)

    # Vendor the minimal Gaia Typst runtime so the package can build anywhere.
    runtime_src_dir = Path(__file__).resolve().parents[1] / "libs" / "typst" / "gaia-lang"
    runtime_dst_dir = pkg_dir / "_gaia"
    runtime_dst_dir.mkdir()
    for filename in ("v2.typ", "module.typ", "declarations.typ", "tactics.typ"):
        src = runtime_src_dir / filename
        (runtime_dst_dir / filename).write_text(src.read_text())

    # typst.toml
    toml_content = f"""[package]
name = "{pkg_name}"
version = "1.0.0"
entrypoint = "lib.typ"
authors = ["Gaia Project"]
description = "Starter Gaia knowledge package"
"""
    (pkg_dir / "typst.toml").write_text(toml_content)

    # gaia.typ
    gaia_content = """#import "_gaia/v2.typ": *
"""
    (pkg_dir / "gaia.typ").write_text(gaia_content)

    # lib.typ
    lib_content = f"""#import "gaia.typ": *
#show: gaia-style

// {pkg_name} — knowledge package
//
// Modules: motivation

#package("{pkg_name}",
  title: "{pkg_name.replace('_', ' ')}",
  version: "1.0.0",
  modules: ("motivation",),
  export: ("main_question",),
)

#include "motivation.typ"

#export-graph()
"""
    (pkg_dir / "lib.typ").write_text(lib_content)

    # motivation.typ
    motivation_content = """#import "gaia.typ": *

// motivation module

#module("motivation", title: "研究动机")

#question("main_question")[
  What is the main research question?
]
"""
    (pkg_dir / "motivation.typ").write_text(motivation_content)

    typer.echo(f"Initialized Typst package '{pkg_name}' in {pkg_dir}/")


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
