"""``gaia extract docs`` -- print LKM extraction API and CLI reference links."""

from __future__ import annotations

import typer

APIFOX_BASE_URL = "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84"
ENDPOINT_DOCS: tuple[tuple[str, str], ...] = (
    ("submit extraction task", "POST /parse/task"),
    ("task status", "GET /parse/task/{task_id}"),
    ("task result", "GET /parse/task/{task_id}/result"),
)


def docs_command() -> None:
    """Print LKM extraction API documentation links."""
    lines = [
        f"LKM API docs: {APIFOX_BASE_URL}",
        "Endpoints (relative to the configured LKM index base URL):",
        *[f"  {label}: {path}" for label, path in ENDPOINT_DOCS],
        "CLI reference: docs/reference/cli/extract.md",
        "",
        "Maintenance note: verify the relevant Apifox endpoint before changing "
        "`gaia extract` behavior, options, or help text.",
    ]
    typer.echo("\n".join(lines))


__all__ = ["APIFOX_BASE_URL", "ENDPOINT_DOCS", "docs_command"]
