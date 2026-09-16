"""``gaia search lkm`` — Bohrium LKM retrieval for Gaia authoring.

Gaia-facing verbs wrap the public LKM HTTP endpoints. Search verbs write raw
JSON to stdout or, with ``--out PATH``, atomically to a file; optional
follow-up suggestions are emitted on stderr.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.search.lkm.auth import auth_app
from gaia.cli.commands.search.lkm.docs import _DOCS_EPILOG, APIFOX_BASE_URL, docs_command
from gaia.cli.commands.search.lkm.feedback import _FEEDBACK_EPILOG, feedback_command
from gaia.cli.commands.search.lkm.knowledge import (
    _KNOWLEDGE_EPILOG,
    knowledge_command,
)
from gaia.cli.commands.search.lkm.paper_graph import _PACKAGE_EPILOG, package_command
from gaia.cli.commands.search.lkm.reasoning import _REASONING_EPILOG, reasoning_command
from gaia.cli.commands.search.lkm.references import _REFERENCES_EPILOG, references_command
from gaia.cli.commands.search.lkm.variables import _NODES_EPILOG, nodes_command

# Rich reflows a single epilog paragraph: only a blank line (\n\n) starts a
# new block. Keep examples and the "what you have" rows as their own blocks.
_LKM_EPILOG = (
    "Examples:\n\n"
    '  gaia search lkm knowledge "solid state battery dendrite suppression"\n\n'
    "  gaia search lkm package --paper-id <paper_id>\n\n"
    "What you have:\n\n"
    "  claims, questions, or abstracts by topic/wording  ->  knowledge\n\n"
    "  a similar argument, derivation, or experiment     ->  reasoning <query>\n\n"
    "  a numeric paper ID from those hits ->  package, references\n\n"
    "  any global gcn_... / node id       ->  nodes\n\n"
    "  a conclusion gcn_... with has_reasoning=true      ->  reasoning --claim-id\n\n"
    "  a local PDF                        ->  gaia extract\n\n"
    "Auth: every call needs a Bohrium access key. Run "
    "`gaia search lkm auth login` to set one up (or set "
    "GAIA_LKM_ACCESS_KEY / LKM_ACCESS_KEY).\n\n"
    "LKM (Large Knowledge Model) is Bohrium's shared-knowledge layer, built "
    "on a subset of the Gaia language: it integrates, curates, retrieves, "
    "and reasons over published structured knowledge. It is not Gaia's "
    "local IR, not a Gaia knowledge package, and not a generic graph API.\n\n"
    "Search surfaces: `knowledge` retrieves paper knowledge items, including "
    "conclusion claims, weak-point / highlight claims, problems, and open "
    "questions. `reasoning` retrieves reasoning chains and workflows. `package` "
    "fetches the per-paper graph that `gaia pkg add` can materialize as a local "
    "dependency. `references` looks up bibliographic forward references and "
    "reverse cited-by lists for papers already identified by id or DOI. "
    "`feedback` reports LKM service/data issues.\n\n"
    "Configured indexes: bohrium (default). Set GAIA_LKM_INDEX_<NAME>_URL "
    "to add a named LKM index.\n\n"
    f"API docs: {APIFOX_BASE_URL}\n\n"
    "Endpoint links: gaia search lkm docs\n\n"
    "Exit codes: 0 ok / 1 business error / 2 transport / 3 no key / 4 bad args.\n\n"
    "Note: the `score` field returned by `knowledge` / `reasoning` is a "
    "retrieval ranking signal, not a probability — do not pass it to Gaia priors."
)

lkm_app = typer.Typer(
    name="lkm",
    help="Search Bohrium LKM shared knowledge.",
    epilog=_LKM_EPILOG,
    no_args_is_help=True,
)

lkm_app.add_typer(auth_app, name="auth")
lkm_app.command(name="docs", epilog=_DOCS_EPILOG)(docs_command)
lkm_app.command(name="knowledge", epilog=_KNOWLEDGE_EPILOG)(knowledge_command)
lkm_app.command(name="reasoning", epilog=_REASONING_EPILOG)(reasoning_command)
lkm_app.command(name="nodes", epilog=_NODES_EPILOG)(nodes_command)
lkm_app.command(name="package", epilog=_PACKAGE_EPILOG)(package_command)
lkm_app.command(name="references", epilog=_REFERENCES_EPILOG)(references_command)
lkm_app.command(name="feedback", epilog=_FEEDBACK_EPILOG)(feedback_command)

__all__ = ["lkm_app"]
