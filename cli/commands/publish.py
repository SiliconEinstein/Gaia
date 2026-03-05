"""gaia publish — publish package to remote."""

import subprocess

import typer

from cli.commands.claim import find_package_dir
from cli.package import load_package_config


def publish_command(
    server: bool = False,
    git: bool = False,
):
    """Publish knowledge package to remote."""
    pkg_dir = find_package_dir()
    config = load_package_config(pkg_dir)

    # Determine mode
    if not server and not git:
        mode = config.get("remote", {}).get("mode", "server")
    elif git:
        mode = "github"
    else:
        mode = "server"

    if mode == "server":
        from cli.server_client import publish_to_server

        server_url = config.get("remote", {}).get("server_url", "http://localhost:8000")
        typer.echo(f"Publishing to {server_url}...")
        try:
            result = publish_to_server(pkg_dir, server_url)
            typer.echo(
                f"Published to server. Commit: {result.get('commit_id', result.get('id', 'unknown'))}"
            )
        except Exception as e:
            typer.echo(f"Error publishing to server: {e}")
            raise typer.Exit(code=1)

    elif mode == "github":
        typer.echo("Publishing via git...")
        try:
            subprocess.run(["git", "add", "."], cwd=str(pkg_dir), check=True)
            subprocess.run(
                ["git", "commit", "-m", "gaia publish"],
                cwd=str(pkg_dir),
                check=True,
                capture_output=True,
            )
        except subprocess.CalledProcessError:
            pass  # May already be committed

        result = subprocess.run(
            ["git", "push", "origin", "HEAD"],
            cwd=str(pkg_dir),
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            typer.echo("Pushed to remote.")
        else:
            typer.echo(f"Push failed: {result.stderr}")
            raise typer.Exit(code=1)
