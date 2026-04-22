"""Grounding metadata for root Claims."""

from __future__ import annotations

from dataclasses import dataclass, field

_VALID_KINDS = frozenset(
    {"assumption", "source_fact", "definition", "imported", "judgment", "open"}
)


@dataclass
class Grounding:
    """Explains why a root Claim can have a prior."""

    kind: str
    rationale: str = ""
    source_refs: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.kind not in _VALID_KINDS:
            raise ValueError(
                f"Invalid grounding kind {self.kind!r}. Must be one of: {sorted(_VALID_KINDS)}"
            )
