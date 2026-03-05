"""gaia build — validate and build knowledge package."""

import typer

from cli.commands.claim import find_package_dir
from cli.package import load_all_claims
from cli.validator import validate_package


def build_command(json_output: bool = False):
    """Validate and build the knowledge package."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)

    if not claims:
        typer.echo("No claims found.")
        raise typer.Exit(code=1)

    # Step 1: Structural validation
    typer.echo(f"Validating {len(claims)} claims...")
    errors = validate_package(claims)
    if errors:
        typer.echo("Validation errors:")
        for e in errors:
            typer.echo(f"  ✗ {e}")
        raise typer.Exit(code=1)
    typer.echo("  ✓ Structural validation passed")

    # Step 2: Run BP
    beliefs = _run_local_bp(claims)

    # Step 3: Print results
    if beliefs:
        typer.echo("\nBP Results:")
        for c in claims:
            cid = c["id"]
            prior = c.get("prior", 1.0) if c.get("type") != "axiom" else 1.0
            belief = beliefs.get(cid, prior)
            marker = ""
            if belief < prior - 0.1:
                marker = " ↓"
            elif belief > prior + 0.1:
                marker = " ↑"
            typer.echo(f"  [{cid}] {c['content'][:40]}: belief={belief:.3f}{marker}")

    # Step 4: Generate lock file
    _generate_lockfile(pkg_dir, claims)

    typer.echo("\n✓ Build complete")


def _run_local_bp(claims: list[dict]) -> dict[int, float]:
    """Convert claims to factor graph and run BP."""
    from services.inference_engine.bp import BeliefPropagation
    from services.inference_engine.factor_graph import FactorGraph

    fg = FactorGraph()

    # Add variables (claims as nodes)
    for c in claims:
        prior = 1.0 if c.get("type") in ("axiom", "observation") else 0.5
        fg.add_variable(c["id"], prior)

    # Add factors (premise relationships as edges)
    edge_id = 10000
    for c in claims:
        premises = c.get("premise", [])
        if not premises:
            continue
        edge_type = c.get("type", "deduction")
        fg.add_factor(
            edge_id=edge_id,
            tail=premises,
            head=[c["id"]],
            probability=0.9,
            edge_type=edge_type,
        )
        edge_id += 1

    if not fg.factors:
        return {}

    bp = BeliefPropagation(damping=0.5, max_iterations=50)
    return bp.run(fg)


def _generate_lockfile(pkg_dir, claims: list[dict]) -> None:
    """Generate gaia.lock from cross-package references."""
    lock_path = pkg_dir / "gaia.lock"
    # Scan for cross-package refs (format: pkg:claim_id@commit)
    deps = []
    for c in claims:
        for pid in c.get("premise", []):
            if isinstance(pid, str) and ":" in pid:
                deps.append(pid)
        for cid in c.get("context", []):
            if isinstance(cid, str) and ":" in cid:
                deps.append(cid)

    lines = ["# gaia.lock — auto-generated, do not edit\n"]
    if deps:
        for d in sorted(set(deps)):
            lines.append(f"{d}\n")
    lock_path.write_text("".join(lines))
