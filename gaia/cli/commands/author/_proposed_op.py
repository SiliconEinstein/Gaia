"""Compatibility import for author operation models.

The canonical public definitions live in :mod:`gaia.engine.authoring`.
This module remains so existing CLI verb imports keep working while downstream
SDK/research callers use the engine-level API.
"""

from __future__ import annotations

from gaia.engine.authoring._ops import OpKind, ProposedAuthorOp

__all__ = ["OpKind", "ProposedAuthorOp"]
