"""``gaia search lkm docs`` -- print LKM API and CLI reference links."""

from __future__ import annotations

import typer

APIFOX_BASE_URL = "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84"
APIFOX_SEARCH_URL = f"{APIFOX_BASE_URL}/api-459806352"
APIFOX_REASONING_SEARCH_URL = f"{APIFOX_BASE_URL}/api-459807117"
APIFOX_CLAIM_REASONING_URL = f"{APIFOX_BASE_URL}/api-459807347"
APIFOX_VARIABLES_BATCH_URL = f"{APIFOX_BASE_URL}/api-459805971"
APIFOX_PAPERS_GRAPH_URL = f"{APIFOX_BASE_URL}/api-459808997"
ENDPOINT_DOCS: tuple[tuple[str, str], ...] = (
    ("knowledge search", APIFOX_SEARCH_URL),
    ("reasoning search", APIFOX_REASONING_SEARCH_URL),
    ("claim reasoning lookup", APIFOX_CLAIM_REASONING_URL),
    ("node lookup", APIFOX_VARIABLES_BATCH_URL),
    ("paper graph lookup", APIFOX_PAPERS_GRAPH_URL),
)


def docs_command() -> None:
    """Print LKM API documentation links."""
    lines = [
        f"LKM API docs: {APIFOX_BASE_URL}",
        "Endpoint docs:",
        *[f"  {label}: {url}" for label, url in ENDPOINT_DOCS],
        "CLI reference: docs/reference/cli/search.md",
        "",
        "Maintenance note: verify the relevant Apifox endpoint before changing "
        "`gaia search lkm` behavior, options, or help text.",
    ]
    typer.echo("\n".join(lines))


__all__ = ["APIFOX_BASE_URL", "ENDPOINT_DOCS", "docs_command"]
