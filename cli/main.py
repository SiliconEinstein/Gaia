"""Gaia CLI — Knowledge Package Manager."""

import typer

app = typer.Typer(name="gaia", help="Gaia Knowledge Package Manager")


@app.callback()
def main():
    """Gaia Knowledge Package Manager."""


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


if __name__ == "__main__":
    app()
