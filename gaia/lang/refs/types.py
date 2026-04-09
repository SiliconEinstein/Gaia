"""Data types for the references subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RefKind = Literal["knowledge", "citation", "unknown"]


@dataclass(frozen=True)
class RefMarker:
    """A single @key reference marker extracted from text.

    Attributes:
        key: The identifier after `@`.
        start: Character offset in source text.
        end: Character offset (exclusive).
        strict: True if inside a `[...]` group, False if bare.
        group_index: Index into the parent `ExtractionResult.groups` list if
            inside a bracket group, otherwise None.
    """

    key: str
    start: int
    end: int
    strict: bool
    group_index: int | None = None


@dataclass(frozen=True)
class BracketGroup:
    """A complete `[...]` Pandoc citation group containing one or more refs.

    Attributes:
        raw: Full bracket group text including the brackets (for error
            messages).
        start: Character offset in source text (position of `[`).
        end: Character offset (exclusive; position after `]`).
        marker_indices: Indices into `ExtractionResult.markers` of all markers
            that belong to this group.
    """

    raw: str
    start: int
    end: int
    marker_indices: tuple[int, ...]


@dataclass(frozen=True)
class ExtractionResult:
    """Result of scanning a piece of text for reference markers.

    Attributes:
        markers: All extracted markers, in source order. Includes both
            bracketed (strict) and bare (opportunistic) markers.
        groups: All bracket groups detected, in source order.
    """

    markers: tuple[RefMarker, ...]
    groups: tuple[BracketGroup, ...]
