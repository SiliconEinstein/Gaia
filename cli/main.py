"""Gaia CLI — Knowledge Package Manager."""

import typer

app = typer.Typer(name="gaia", help="Gaia Knowledge Package Manager")


# Module-level state for --json flag
_json_output: bool = False


@app.callback()
def main(json_output: bool = typer.Option(False, "--json", help="Output as JSON")):
    """Gaia Knowledge Package Manager."""
    global _json_output
    _json_output = json_output


@app.command()
def init(name: str = typer.Argument(None, help="Package name (default: current dir name)")):
    """Initialize a new knowledge package."""
    from cli.package import init_package

    init_package(name)


@app.command()
def claim(
    content: str = typer.Argument(..., help="Claim content"),
    type_: str = typer.Option("deduction", "--type", "-t", help="Claim type"),
    premise: str = typer.Option(None, "--premise", "-p", help="Comma-separated premise claim IDs"),
    context: str = typer.Option(None, "--context", "-c", help="Comma-separated context claim IDs"),
    why: str = typer.Option(None, "--why", "-w", help="Reasoning explanation"),
):
    """Add a new claim to the knowledge package."""
    from cli.commands.claim import claim_command

    claim_command(content, type_, premise, context, why)


@app.command()
def show(claim_id: int = typer.Argument(..., help="Claim ID to show")):
    """Show details of a specific claim."""
    from cli.commands.show import show_command

    show_command(claim_id)


@app.command()
def stats():
    """Show package statistics."""
    from cli.commands.stats import stats_command

    stats_command()


@app.command()
def contradictions():
    """List all contradiction claims."""
    from cli.commands.contradictions import contradictions_command

    contradictions_command()


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
):
    """Search claims in the knowledge package."""
    from cli.commands.search import search_command

    search_command(query, limit)


@app.command()
def build():
    """Validate and build the knowledge package."""
    from cli.commands.build import build_command

    build_command()


@app.command()
def review(
    claim_ids: list[int] = typer.Argument(
        None, help="Claim IDs to review (default: all with premises)"
    ),
):
    """Review claims using LLM evaluation."""
    from cli.commands.review import review_command

    review_command(claim_ids)


@app.command()
def publish(
    server: bool = typer.Option(False, "--server", help="Publish to Server directly"),
    git: bool = typer.Option(False, "--git", help="Publish via git push"),
):
    """Publish knowledge package to remote."""
    from cli.commands.publish import publish_command

    publish_command(server, git)


if __name__ == "__main__":
    app()
