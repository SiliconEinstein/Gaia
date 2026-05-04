"""Domain — a user-declared typed sort backing Variable types and quantification.

Lang-only: subclasses Knowledge for identity/provenance, but overrides
__post_init__ to skip the IR-bound knowledge map registration. See spec §2.4.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.lang.runtime.knowledge import Knowledge, _current_package


@dataclass(init=False, eq=False)
class Domain(Knowledge):
    """A user-declared, finite, enumerable typed sort.

    Subclasses Knowledge so it carries identity, provenance, and metadata.
    Lang-only: does NOT enter the package's IR-bound knowledge map.
    """

    members: list[Any] = field(default_factory=list)

    def __init__(
        self,
        content: str,
        *,
        members: list[Any],
        format: str = "markdown",
        **kwargs,
    ):
        if not isinstance(members, list):
            raise TypeError("members must be a list")
        if len(members) == 0:
            raise ValueError("members must be a non-empty list")
        super().__init__(content=content, type="domain", format=format, **kwargs)
        self.members = list(members)

    def __post_init__(self):
        # Override Knowledge.__post_init__: associate with the package for provenance,
        # but DO NOT call pkg._register_knowledge — Domain is Lang-only (spec §2.4).
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            # No pkg._register_knowledge(self) — Lang-only.
