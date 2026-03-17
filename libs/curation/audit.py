"""Audit log for curation operations.

Append-only in-memory log. Each entry stores rollback_data sufficient to
undo the operation. Serializable to/from list[dict] for persistence.
"""

from __future__ import annotations

from .models import AuditEntry


class AuditLog:
    """Append-only audit log for curation operations."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    @property
    def entries(self) -> list[AuditEntry]:
        return list(self._entries)

    def append(self, entry: AuditEntry) -> None:
        self._entries.append(entry)

    def get(self, entry_id: str) -> AuditEntry | None:
        for e in self._entries:
            if e.entry_id == entry_id:
                return e
        return None

    def list_by_operation(self, operation: str) -> list[AuditEntry]:
        return [e for e in self._entries if e.operation == operation]

    def to_dicts(self) -> list[dict]:
        return [e.model_dump(mode="json") for e in self._entries]

    @classmethod
    def from_dicts(cls, data: list[dict]) -> AuditLog:
        log = cls()
        for d in data:
            log.append(AuditEntry.model_validate(d))
        return log
