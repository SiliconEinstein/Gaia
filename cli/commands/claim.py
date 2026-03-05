"""gaia claim — add a claim to the knowledge package."""

import re
from pathlib import Path

import typer
import yaml


def find_package_dir() -> Path:
    """Walk up from cwd to find gaia.toml."""
    p = Path.cwd()
    while p != p.parent:
        if (p / "gaia.toml").exists():
            return p
        p = p.parent
    typer.echo("Error: not inside a gaia package (no gaia.toml found)")
    raise typer.Exit(code=1)


def get_next_claim_id(pkg_dir: Path) -> int:
    """Scan claims/*.yaml and return max_id + 1."""
    claims_dir = pkg_dir / "claims"
    max_id = 0
    for f in claims_dir.glob("*.yaml"):
        data = yaml.safe_load(f.read_text())
        if data and "claims" in data:
            for c in data["claims"]:
                if c.get("id", 0) > max_id:
                    max_id = c["id"]
    return max_id + 1


def sanitize_filename(content: str) -> str:
    """Create a filesystem-safe name from claim content."""
    # Take first 30 chars, replace non-alphanumeric with underscore
    name = re.sub(r"[^\w]", "_", content[:30]).strip("_")
    return name or "claim"


def write_claim(
    pkg_dir: Path,
    claim_id: int,
    content: str,
    claim_type: str,
    premise: list[int] | None = None,
    context: list[int] | None = None,
    why: str | None = None,
) -> Path:
    """Write a claim to claims/ directory."""
    claims_dir = pkg_dir / "claims"
    claims_dir.mkdir(exist_ok=True)

    claim_data = {
        "id": claim_id,
        "content": content,
        "type": claim_type,
    }
    if premise:
        claim_data["premise"] = premise
    if context:
        claim_data["context"] = context
    if why:
        claim_data["why"] = why

    filename = f"{claim_id:04d}_{sanitize_filename(content)}.yaml"
    path = claims_dir / filename
    path.write_text(
        yaml.dump({"claims": [claim_data]}, allow_unicode=True, default_flow_style=False)
    )
    return path


def claim_command(
    content: str = typer.Argument(..., help="Claim content"),
    type_: str = typer.Option("deduction", "--type", "-t", help="Claim type"),
    premise: str = typer.Option(None, "--premise", "-p", help="Comma-separated premise claim IDs"),
    context: str = typer.Option(None, "--context", "-c", help="Comma-separated context claim IDs"),
    why: str = typer.Option(None, "--why", "-w", help="Reasoning explanation"),
):
    """Add a new claim to the knowledge package."""
    pkg_dir = find_package_dir()
    claim_id = get_next_claim_id(pkg_dir)

    premise_ids = [int(x.strip()) for x in premise.split(",")] if premise else None
    context_ids = [int(x.strip()) for x in context.split(",")] if context else None

    write_claim(pkg_dir, claim_id, content, type_, premise_ids, context_ids, why)
    typer.echo(f"Created claim {claim_id}: {content[:50]}")
