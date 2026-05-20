"""``gaia search lkm`` — Bohrium LKM knowledge-graph search backend.

Gaia-facing verbs wrap the public LKM HTTP endpoints while keeping the
upstream endpoint names as hidden compatibility aliases where useful. Every
verb writes pretty JSON to stdout or, with ``--out PATH``, atomically to a file.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.search.lkm.auth import auth_app
from gaia.cli.commands.search.lkm.knowledge import (
    _KNOWLEDGE_EPILOG,
    claims_command,
    knowledge_command,
)
from gaia.cli.commands.search.lkm.paper_graph import package_command, paper_graph_command
from gaia.cli.commands.search.lkm.reasoning import reasoning_command
from gaia.cli.commands.search.lkm.reasoning_search import reasoning_search_command
from gaia.cli.commands.search.lkm.variables import nodes_command, variables_command

_LKM_EPILOG = (
    "Endpoints (all under https://open.bohrium.com/openapi/v1/lkm):\n\n"
    "  knowledge  POST /search + filters        — recall claim/question nodes\n"
    "  reasoning  POST /reasoning/search        — search reasoning chains by query\n"
    "             GET  /claims/{id}/reasoning   — fetch chains for one claim\n"
    "  nodes      POST /variables/batch         — fetch LKM graph nodes by id\n"
    "  package    POST /papers/graph            — fetch a paper package candidate\n\n"
    "Auth: every call needs a Bohrium access key. Run "
    "`gaia search lkm auth login` to set one up (or set "
    "GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY).\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args.\n\n"
    "Note: the `score` field returned by `knowledge` / `reasoning` is a "
    "retrieval ranking signal, not a probability — do not pass it to Gaia priors."
)

lkm_app = typer.Typer(
    name="lkm",
    help="Search the Bohrium LKM knowledge graph (4 verbs + auth).",
    epilog=_LKM_EPILOG,
    no_args_is_help=True,
)

lkm_app.add_typer(auth_app, name="auth")
lkm_app.command(name="knowledge", epilog=_KNOWLEDGE_EPILOG)(knowledge_command)
lkm_app.command(name="claims", epilog=_KNOWLEDGE_EPILOG, hidden=True)(claims_command)
lkm_app.command(name="reasoning")(reasoning_command)
lkm_app.command(name="reasoning-search", hidden=True)(reasoning_search_command)
lkm_app.command(name="nodes")(nodes_command)
lkm_app.command(name="variables", hidden=True)(variables_command)
lkm_app.command(name="package")(package_command)
lkm_app.command(name="paper-graph", hidden=True)(paper_graph_command)

__all__ = ["lkm_app"]
