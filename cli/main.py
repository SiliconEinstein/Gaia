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


if __name__ == "__main__":
    app()
