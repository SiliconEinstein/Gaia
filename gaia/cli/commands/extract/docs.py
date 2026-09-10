"""``gaia extract docs`` -- print LKM extraction API and CLI reference links."""

from __future__ import annotations

import typer

APIFOX_BASE_URL = "https://s.apifox.cn/33d12311-ec59-4a5c-a849-391704fe7f84"
APIFOX_SUBMIT_URL = f"{APIFOX_BASE_URL}/api-502383795"
APIFOX_STATUS_URL = f"{APIFOX_BASE_URL}/api-502383796"
APIFOX_RESULT_URL = f"{APIFOX_BASE_URL}/api-502383797"
ENDPOINT_DOCS: tuple[tuple[str, str], ...] = (
    ("submit extraction task", APIFOX_SUBMIT_URL),
    ("task status", APIFOX_STATUS_URL),
    ("task result", APIFOX_RESULT_URL),
)


_DOCS_EPILOG = (
    "Examples:\n\n"
    "  gaia extract docs\n\n"
    "What you have:\n\n"
    "  a PDF or markdown       ->  submit\n\n"
    "  a task_id               ->  status / result\n\n"
    "  a paper already in LKM  ->  gaia search lkm"
)


def docs_command() -> None:
    """Print LKM extraction API documentation links."""
    lines = [
        f"LKM API docs: {APIFOX_BASE_URL}",
        "Endpoint docs:",
        *[f"  {label}: {url}" for label, url in ENDPOINT_DOCS],
        "CLI reference: docs/reference/cli/extract.md",
        "",
        "Maintenance note: verify the relevant Apifox endpoint before changing "
        "`gaia extract` behavior, options, or help text.",
    ]
    typer.echo("\n".join(lines))


__all__ = [
    "APIFOX_BASE_URL",
    "APIFOX_RESULT_URL",
    "APIFOX_STATUS_URL",
    "APIFOX_SUBMIT_URL",
    "ENDPOINT_DOCS",
    "_DOCS_EPILOG",
    "docs_command",
]
