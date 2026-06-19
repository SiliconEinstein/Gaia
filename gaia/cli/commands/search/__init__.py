"""``gaia search`` — retrieval backends for knowledge-package authoring.

Today this group hosts a single backend, ``lkm`` (Bohrium's Large Knowledge
Model API for agent-ready paper search). The ``search`` parent is deliberately
a thin shell so future non-LKM retrieval backends can slot in alongside it
without reshaping the verb tree.
"""

from __future__ import annotations

import typer

from gaia.cli.commands.search.lkm import lkm_app

search_app = typer.Typer(
    name="search",
    help="Retrieval backends (lkm).",
    no_args_is_help=True,
)
search_app.add_typer(lkm_app, name="lkm")

__all__ = ["search_app"]
