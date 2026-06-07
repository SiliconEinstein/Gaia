"""``gaia search lkm`` — LKM knowledge-graph search indexes.

Gaia-facing verbs wrap the public LKM HTTP endpoints. Every verb writes pretty
JSON to stdout or, with ``--out PATH``, atomically to a file.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.search.lkm.auth import auth_app
from gaia.cli.commands.search.lkm.docs import APIFOX_BASE_URL, docs_command
from gaia.cli.commands.search.lkm.knowledge import (
    _KNOWLEDGE_EPILOG,
    knowledge_command,
)
from gaia.cli.commands.search.lkm.paper_graph import _PACKAGE_EPILOG, package_command
from gaia.cli.commands.search.lkm.reasoning import _REASONING_EPILOG, reasoning_command
from gaia.cli.commands.search.lkm.variables import _NODES_EPILOG, nodes_command

_LKM_EPILOG = (
    "Configured indexes: bohrium (default). Set GAIA_LKM_INDEX_<NAME>_URL "
    "to add a named LKM index.\n\n"
    f"Full LKM API docs: {APIFOX_BASE_URL}\n"
    "Run `gaia search lkm docs` for endpoint links.\n\n"
    "Auth: every call needs a Bohrium access key. Run "
    "`gaia search lkm auth login` to set one up (or set "
    "GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY).\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args.\n\n"
    "Note: the `score` field returned by `knowledge` / `reasoning` is a "
    "retrieval ranking signal, not a probability — do not pass it to Gaia priors."
)

lkm_app = typer.Typer(
    name="lkm",
    help="Search configured LKM knowledge-graph indexes (5 verbs + auth).",
    epilog=_LKM_EPILOG,
    no_args_is_help=True,
)

lkm_app.add_typer(auth_app, name="auth")
lkm_app.command(name="docs")(docs_command)
lkm_app.command(name="knowledge", epilog=_KNOWLEDGE_EPILOG)(knowledge_command)
lkm_app.command(name="reasoning", epilog=_REASONING_EPILOG)(reasoning_command)
lkm_app.command(name="nodes", epilog=_NODES_EPILOG)(nodes_command)
lkm_app.command(name="package", epilog=_PACKAGE_EPILOG)(package_command)

__all__ = ["lkm_app"]
