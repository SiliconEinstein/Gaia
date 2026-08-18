"""``gaia extract`` — turn a local PDF into LKM-extracted knowledge.

``gaia search lkm`` queries papers already ingested into LKM. This group is
the other direction: hand LKM a PDF you hold and get back the research
questions, conclusions, and reasoning steps it extracts from that file. It is
a job surface, not a retrieval surface — submission is asynchronous and the
result is a flat graph rather than search hits — which is why it sits beside
``search`` instead of inside it.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.extract.docs import APIFOX_BASE_URL, docs_command
from gaia.cli.commands.extract.result import _RESULT_EPILOG, result_command
from gaia.cli.commands.extract.status import _STATUS_EPILOG, status_command
from gaia.cli.commands.extract.submit import _SUBMIT_EPILOG, submit_command

_EXTRACT_EPILOG = (
    "Auth: every call needs a Bohrium access key, the same one "
    "`gaia search lkm` uses. Run `gaia search lkm auth login` to set one up "
    "(or set GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY).\n\n"
    "Flow: `submit` uploads a PDF and returns a task id; `status` reads that "
    "task once; `result` fetches what it produced. `submit --wait` does the "
    "polling for you. Extraction commonly takes several minutes to a quarter "
    "of an hour.\n\n"
    "Terminal states are succeeded, partial, and failed. A partial task kept "
    "the intermediate XML it managed to produce; it is not a full graph.\n\n"
    "This is knowledge extraction, not layout parsing: it returns claims and "
    "reasoning, not page text, tables, or formulas.\n\n"
    "Configured indexes: bohrium (default). Set GAIA_LKM_INDEX_<NAME>_URL "
    "to add a named LKM index.\n\n"
    f"API docs: {APIFOX_BASE_URL}\n"
    "Endpoint links: gaia extract docs\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args."
)

extract_app = typer.Typer(
    name="extract",
    help="Extract knowledge from a local PDF via Bohrium LKM.",
    epilog=_EXTRACT_EPILOG,
    no_args_is_help=True,
)

extract_app.command(name="docs")(docs_command)
extract_app.command(name="submit", epilog=_SUBMIT_EPILOG)(submit_command)
extract_app.command(name="status", epilog=_STATUS_EPILOG)(status_command)
extract_app.command(name="result", epilog=_RESULT_EPILOG)(result_command)

__all__ = ["extract_app"]
