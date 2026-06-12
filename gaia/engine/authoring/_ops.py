"""Authoring operation models shared by CLI and engine callers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

OpKind = Literal["reasoning", "scaffold"]


@dataclass
class ProposedAuthorOp:
    """A pending author operation, ready to be validated and written."""

    verb: str
    kind: OpKind
    label: str | None
    references: list[str] = field(default_factory=list)
    generated_code: str = ""
    required_imports: tuple[str, ...] = ()
    export: bool = False
    prepended_statements: tuple[tuple[str, str], ...] = ()
    extra_payload: dict[str, Any] = field(default_factory=dict)
    target_file: str | None = None
    sibling_imports: tuple[tuple[str, str], ...] = ()
    foreign_imports: tuple[tuple[str, str, str], ...] = ()


__all__ = ["OpKind", "ProposedAuthorOp"]
