"""gaia stats — package statistics."""

from collections import Counter

import typer

from cli.commands.claim import find_package_dir
from cli.package import load_all_claims


def stats_command():
    """Show package statistics."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)

    if not claims:
        typer.echo("No claims found.")
        return

    type_counts = Counter(c.get("type", "unknown") for c in claims)
    premise_count = sum(1 for c in claims if c.get("premise"))

    typer.echo(f"Total claims: {len(claims)}")
    typer.echo("By type:")
    for t, count in sorted(type_counts.items()):
        typer.echo(f"  {t}: {count}")
    typer.echo(f"Claims with premises: {premise_count}")
