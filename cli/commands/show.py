"""gaia show — display a claim."""

import typer

from cli.commands.claim import find_package_dir
from cli.package import load_all_claims


def show_command(claim_id: int):
    """Show details of a specific claim."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)
    claims_by_id = {c["id"]: c for c in claims}

    if claim_id not in claims_by_id:
        typer.echo(f"Claim {claim_id} not found")
        raise typer.Exit(code=1)

    c = claims_by_id[claim_id]
    typer.echo(f"Claim {c['id']}")
    typer.echo(f"  Content: {c['content']}")
    typer.echo(f"  Type: {c.get('type', 'unknown')}")
    if c.get("premise"):
        typer.echo(f"  Premises: {c['premise']}")
    if c.get("context"):
        typer.echo(f"  Context: {c['context']}")
    if c.get("why"):
        typer.echo(f"  Why: {c['why']}")
