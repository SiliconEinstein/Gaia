"""gaia contradictions — find contradiction claims."""

import typer

from cli.commands.claim import find_package_dir
from cli.package import load_all_claims


def contradictions_command():
    """List all contradiction claims."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)

    contradictions = [c for c in claims if c.get("type") == "contradiction"]

    if not contradictions:
        typer.echo("No contradictions found.")
        return

    claims_by_id = {c["id"]: c for c in claims}
    typer.echo(f"Found {len(contradictions)} contradiction(s):")
    for c in contradictions:
        typer.echo(f"\n  Claim {c['id']}: {c['content']}")
        if c.get("premise"):
            for pid in c["premise"]:
                p = claims_by_id.get(pid)
                if p:
                    typer.echo(f"    <- Premise {pid}: {p['content']}")
