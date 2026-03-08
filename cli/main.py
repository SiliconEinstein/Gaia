"""Gaia CLI — proof assistant for probabilistic defeasible reasoning."""

from __future__ import annotations

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
    from libs.dsl.build_store import save_build
    from libs.dsl.elaborator import elaborate_package
    from libs.dsl.loader import load_package
    from libs.dsl.resolver import resolve_refs

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
) -> None:
    """LLM reviews chains -> sidecar report (.gaia/reviews/)."""
    from datetime import datetime, timezone

    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.review_store import write_review
    from libs.dsl.loader import load_package
    from libs.dsl.models import ChainExpr
    from libs.dsl.resolver import resolve_refs

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Check build exists
    elab_file = build_dir / "elaborated.yaml"
    if not elab_file.exists():
        typer.echo(f"Error: no build artifacts.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Read elaborated prompts
    import yaml as _yaml

    elab_data = _yaml.safe_load(elab_file.read_text())
    prompts = elab_data.get("prompts", [])

    # 3. Load package to get step priors
    pkg = load_package(pkg_path)
    pkg = resolve_refs(pkg)

    # Build chain->step->prior index from the package
    chain_step_priors: dict[str, dict[int, float]] = {}
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, ChainExpr):
                chain_step_priors[decl.name] = {}
                for step in decl.steps:
                    if hasattr(step, "prior") and step.prior is not None:
                        chain_step_priors[decl.name][step.step] = step.prior

    # 4. Create reviewer
    client = MockReviewClient() if mock else ReviewClient(model=model)

    # 5. Group prompts by chain and review each
    prompts_by_chain: dict[str, list[dict]] = {}
    for p in prompts:
        chain_name = p["chain"]
        if chain_name not in prompts_by_chain:
            prompts_by_chain[chain_name] = []
        prompts_by_chain[chain_name].append(p)

    chain_reviews = []
    for chain_name, chain_prompts in prompts_by_chain.items():
        chain_data = {
            "name": chain_name,
            "steps": [
                {
                    "step": p["step"],
                    "action": p["action"],
                    "rendered": p["rendered"],
                    "prior": chain_step_priors.get(chain_name, {}).get(p["step"]),
                    "args": p["args"],
                }
                for p in chain_prompts
            ],
        }
        result = client.review_chain(chain_data)
        chain_reviews.append(result)

    # 6. Write sidecar
    now = datetime.now(timezone.utc)
    review_data = {
        "package": pkg.name,
        "model": "mock" if mock else model,
        "timestamp": now.isoformat(),
        "chains": chain_reviews,
    }
    review_path = write_review(review_data, reviews_dir)

    n_chains = len(chain_reviews)
    typer.echo(f"Reviewed {n_chains} chains for {pkg.name}")
    typer.echo(f"Report: {review_path}")


@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile FG (from review) + BP -> beliefs."""
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.dsl.compiler import compile_factor_graph
    from libs.dsl.loader import load_package
    from libs.dsl.resolver import resolve_refs
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
    pkg = merge_review(pkg, review)

    # 4. Compile factor graph
    dsl_fg = compile_factor_graph(pkg)

    # 5. Convert to inference engine FactorGraph and run BP
    bp_fg = FactorGraph()
    name_to_id: dict[str, int] = {}
    for i, (name, prior) in enumerate(dsl_fg.variables.items()):
        node_id = i + 1
        name_to_id[name] = node_id
        bp_fg.add_variable(node_id, prior)

    for j, factor in enumerate(dsl_fg.factors):
        tail_ids = [name_to_id[n] for n in factor["tail"] if n in name_to_id]
        head_ids = [name_to_id[n] for n in factor["head"] if n in name_to_id]
        bp_fg.add_factor(
            edge_id=j + 1,
            tail=tail_ids,
            head=head_ids,
            probability=factor["probability"],
            edge_type=factor.get("edge_type", "deduction"),
        )

    bp = BeliefPropagation()
    beliefs = bp.run(bp_fg)

    # 6. Map back to names and output
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    typer.echo(f"Package: {pkg.name}")
    typer.echo(f"Variables: {len(dsl_fg.variables)}")
    typer.echo(f"Factors: {len(dsl_fg.factors)}")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        prior = dsl_fg.variables.get(name, "?")
        typer.echo(f"  {name}: prior={prior} -> belief={belief:.4f}")


@app.command()
def publish(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    git: bool = typer.Option(False, "--git", help="Publish via git add+commit+push"),
    server: bool = typer.Option(False, "--server", help="Publish to Gaia server API"),
) -> None:
    """Publish to git or server."""
    typer.echo(f"gaia publish {path} — not yet implemented")
    raise typer.Exit(1)


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
    (pkg_dir / "package.yaml").write_text(
        yaml.dump(pkg_data, allow_unicode=True, sort_keys=False)
    )

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
    name: str = typer.Argument(..., help="Declaration name to inspect"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Show declaration details + connected chains."""
    typer.echo(f"gaia show {name} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Search declarations within the package."""
    typer.echo(f"gaia search '{query}' — not yet implemented")
    raise typer.Exit(1)


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
