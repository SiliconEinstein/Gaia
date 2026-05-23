"""``gaia sdk`` command group — the first/primary authoring entry point.

Authoring the Gaia DSL directly via the Python SDK is the recommended
path. ``gaia sdk`` generates a self-contained Markdown reference plus a
one-page cheat sheet (``CHEATSHEET.md``) so an author — human or agent —
can read the surface and write DSL statements directly. The ``gaia
author`` CLI remains available as an optional convenience.
"""

from __future__ import annotations

from gaia.cli.commands.sdk.command import sdk_command

__all__ = ["sdk_command"]
