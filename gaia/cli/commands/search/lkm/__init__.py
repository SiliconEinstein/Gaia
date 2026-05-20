"""``gaia search lkm`` — Bohrium LKM knowledge-graph search backend.

Five atomic verbs mapping 1:1 onto the public LKM HTTP endpoints, plus an
``auth`` sub-group for the access-key lifecycle. Every verb writes pretty
JSON to stdout or, with ``--out PATH``, atomically to a file.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.search.lkm.auth import auth_app
from gaia.cli.commands.search.lkm.claims import _CLAIMS_EPILOG, claims_command
from gaia.cli.commands.search.lkm.paper_graph import paper_graph_command
from gaia.cli.commands.search.lkm.reasoning import reasoning_command
from gaia.cli.commands.search.lkm.reasoning_search import reasoning_search_command
from gaia.cli.commands.search.lkm.variables import variables_command

_LKM_EPILOG = (
    "Endpoints (all under https://open.bohrium.com/openapi/v1/lkm):\n\n"
    "  claims           POST /search             — recall claim / question nodes\n"
    "  reasoning        GET  /claims/{id}/reasoning — chains backing one claim\n"
    "  reasoning-search POST /reasoning/search   — recall whole reasoning chains\n"
    "  variables        POST /variables/batch    — hydrate variable detail by id\n"
    "  paper-graph      POST /papers/graph       — a paper's knowledge graph\n\n"
    "Auth: every call needs a Bohrium access key. Run "
    "`gaia search lkm auth login` to set one up (or set "
    "GAIA_LKM_ACCESS_KEY).\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args.\n\n"
    "Note: the `score` field returned by `claims` / `reasoning-search` is a "
    "retrieval ranking signal, not a probability — do not pass it to Gaia priors."
)

lkm_app = typer.Typer(
    name="lkm",
    help="Search the Bohrium LKM knowledge graph (5 verbs + auth).",
    epilog=_LKM_EPILOG,
    no_args_is_help=True,
)

lkm_app.add_typer(auth_app, name="auth")
lkm_app.command(name="claims", epilog=_CLAIMS_EPILOG)(claims_command)
lkm_app.command(name="reasoning")(reasoning_command)
lkm_app.command(name="reasoning-search")(reasoning_search_command)
lkm_app.command(name="variables")(variables_command)
lkm_app.command(name="paper-graph")(paper_graph_command)

__all__ = ["lkm_app"]
