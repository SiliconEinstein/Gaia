"""Reference resolution: label table vs references.json.

Run order at compile time:
    1. check_collisions(label_table, references)  — fail fast on ambiguous keys
    2. For each bracket group: validate_groups([group], markers, ...)
    3. For each marker: resolve(marker.key, label_table, references)

Step 1 guarantees step 3's inputs are disjoint (no key appears in both
tables), so resolve() only needs a 3-state output (knowledge / citation /
unknown).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from gaia.lang.refs.errors import ReferenceError
from gaia.lang.refs.types import BracketGroup, RefKind, RefMarker


def resolve(
    key: str,
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> RefKind:
    """Resolve a single reference key.

    Must only be called after `check_collisions` has passed, which guarantees
    a key is in at most one table.
    """
    if key in references:
        return "citation"
    if key in label_table:
        return "knowledge"
    return "unknown"


def check_collisions(
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> None:
    """Fail fast if any key appears in both the label table and references.

    Raises:
        ReferenceError: listing all colliding keys.

    Per spec §3.5, collision is a compile error — never a warning — to
    prevent silent semantic drift when a bibliography is imported.
    """
    collisions = sorted(set(label_table) & set(references))
    if collisions:
        quoted = ", ".join(f"'{k}'" for k in collisions)
        raise ReferenceError(
            f"ambiguous reference key(s) {quoted}: "
            f"same identifier exists as both a knowledge label and a "
            f"citation key. rename one side to disambiguate."
        )


def validate_groups(
    groups: Iterable[BracketGroup],
    markers: tuple[RefMarker, ...] | list[RefMarker],
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> None:
    """Enforce the homogeneous-group rule (spec §3.2).

    A `[...]` group must contain only knowledge refs or only citations.
    Mixing them in one group is a compile error because the rendering
    pipeline cannot faithfully process mixed Pandoc groups through
    citeproc-py.

    Unknown keys are NOT flagged here — they have their own disposition
    (strict → error at marker level; opportunistic → literal). This function
    only fires on the specific knowledge+citation mix.

    Raises:
        ReferenceError: on the first mixed group encountered, listing which
            keys are knowledge and which are citations.
    """
    markers_seq = tuple(markers)
    for group in groups:
        knowledge_keys: list[str] = []
        citation_keys: list[str] = []
        for idx in group.marker_indices:
            marker = markers_seq[idx]
            kind = resolve(marker.key, label_table, references)
            if kind == "knowledge":
                knowledge_keys.append(marker.key)
            elif kind == "citation":
                citation_keys.append(marker.key)
        if knowledge_keys and citation_keys:
            raise ReferenceError(
                f"mixed-type reference group {group.raw!r}: contains both "
                f"knowledge refs ({', '.join(knowledge_keys)}) and "
                f"citations ({', '.join(citation_keys)}). "
                f"split into separate bracketed groups — one for knowledge "
                f"refs and one for citations."
            )
