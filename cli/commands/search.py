"""gaia search — search claims in the package."""

import typer

from cli.commands.claim import find_package_dir
from cli.local_store import LocalStore
from cli.package import load_all_claims


def search_command(query: str, limit: int = 10):
    """Search claims in the knowledge package."""
    pkg_dir = find_package_dir()
    claims = load_all_claims(pkg_dir)

    if not claims:
        typer.echo("No claims to search.")
        return

    store = LocalStore(pkg_dir)
    store.index_claims(claims)
    results = store.search(query, limit)

    if not results:
        typer.echo(f"No results for '{query}'")
        return

    typer.echo(f"Found {len(results)} result(s):")
    for r in results:
        typer.echo(f"  [{r['id']}] ({r['type']}) {r['content']}")
