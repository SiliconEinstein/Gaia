"""``gaia extract`` — turn a local PDF or parser markdown into LKM knowledge.

``gaia search lkm`` queries papers already ingested into LKM. This group is
the other direction: hand LKM a PDF and/or parser markdown you hold and get
back the research questions, conclusions, and reasoning steps it extracts.
It is a job surface, not a retrieval surface — submission is asynchronous
and the result is a flat graph rather than search hits — which is why it
sits beside ``search`` instead of inside it.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.extract.docs import APIFOX_BASE_URL, _DOCS_EPILOG, docs_command
from gaia.cli.commands.extract.result import _RESULT_EPILOG, result_command
from gaia.cli.commands.extract.status import _STATUS_EPILOG, status_command
from gaia.cli.commands.extract.submit import _SUBMIT_EPILOG, submit_command

# Rich reflows a single epilog paragraph: only a blank line (\n\n) starts a
# new block. Keep examples and the "what you have" rows as their own blocks.
_EXTRACT_EPILOG = (
    "Examples:\n\n"
    "  gaia extract submit paper.pdf\n\n"
    "  gaia extract submit paper.pdf --content paper.md\n\n"
    "  gaia extract submit --content paper.md --md5 <32-hex> --page 12\n\n"
    "What you have:\n\n"
    "  a local PDF                   ->  submit\n\n"
    "  parser markdown               ->  submit --content\n\n"
    "  a task_id from submit         ->  status, or submit --wait\n\n"
    "  a terminal task               ->  result\n\n"
    "  a paper already in the corpus ->  gaia search lkm\n\n"
    "Auth: every call needs a Bohrium access key, the same one "
    "`gaia search lkm` uses. Run `gaia search lkm auth login` to set one up "
    "(or set GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY).\n\n"
    "Flow: `submit` sends a PDF and/or parser markdown and returns a task "
    "id; `status` reads that task once; `result` fetches what it produced. "
    "`submit --wait` does the polling for you. Extraction commonly takes "
    "several minutes to a quarter of an hour.\n\n"
    "Terminal states are succeeded, partial, and failed. `partial` is a "
    "non-retryable business failure (review, too short, collection); do not "
    "resubmit the same PDF or `--content` body. `failed` is technical and may be submitted again.\n\n"
    "This is knowledge extraction, not layout parsing: it returns claims and "
    "reasoning, not page text, tables, or formulas.\n\n"
    "Configured indexes: bohrium (default). Set GAIA_LKM_INDEX_<NAME>_URL "
    "to add a named LKM index.\n\n"
    f"API docs: {APIFOX_BASE_URL}\n\n"
    "Endpoint links: gaia extract docs\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args."
)

extract_app = typer.Typer(
    name="extract",
    help="Extract knowledge from a local PDF or parser markdown via Bohrium LKM.",
    epilog=_EXTRACT_EPILOG,
    no_args_is_help=True,
)

extract_app.command(name="docs", epilog=_DOCS_EPILOG)(docs_command)
extract_app.command(name="submit", epilog=_SUBMIT_EPILOG)(submit_command)
extract_app.command(name="status", epilog=_STATUS_EPILOG)(status_command)
extract_app.command(name="result", epilog=_RESULT_EPILOG)(result_command)

__all__ = ["extract_app"]
