"""Reference extraction / resolution / loading errors."""

from __future__ import annotations


class ReferenceError(Exception):
    """Base error for reference handling.

    Raised from extractor, resolver, loader for any structural or semantic
    failure. Compile turns these into hard errors.
    """

    def __init__(self, message: str, *, location: str | None = None) -> None:
        self.location = location
        if location:
            super().__init__(f"{location}: {message}")
        else:
            super().__init__(message)
