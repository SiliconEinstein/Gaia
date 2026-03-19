"""Tests for curation audit log."""

from libs.curation.audit import AuditLog
from libs.curation.models import AuditEntry


def test_audit_log_append_and_list():
    """Entries can be appended and listed."""
    log = AuditLog()
    entry = AuditEntry(
        entry_id="a1",
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        suggestion_id="sug_1",
        rollback_data={"removed_node": "gcn_b"},
    )
    log.append(entry)
    assert len(log.entries) == 1
    assert log.entries[0].entry_id == "a1"


def test_audit_log_get_by_id():
    """Can retrieve entry by ID."""
    log = AuditLog()
    entry = AuditEntry(
        entry_id="a1",
        operation="merge",
        target_ids=["gcn_a", "gcn_b"],
        suggestion_id="sug_1",
    )
    log.append(entry)
    assert log.get("a1") is not None
    assert log.get("nonexistent") is None


def test_audit_log_list_by_operation():
    """Can filter entries by operation type."""
    log = AuditLog()
    log.append(
        AuditEntry(
            entry_id="a1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            suggestion_id="sug_1",
        )
    )
    log.append(
        AuditEntry(
            entry_id="a2",
            operation="create_equivalence",
            target_ids=["gcn_c", "gcn_d"],
            suggestion_id="sug_2",
        )
    )
    merges = log.list_by_operation("merge")
    assert len(merges) == 1
    assert merges[0].entry_id == "a1"


def test_audit_log_serialization():
    """Log can be serialized and deserialized."""
    log = AuditLog()
    log.append(
        AuditEntry(
            entry_id="a1",
            operation="merge",
            target_ids=["gcn_a", "gcn_b"],
            suggestion_id="sug_1",
            rollback_data={"key": "value"},
        )
    )
    data = log.to_dicts()
    assert len(data) == 1
    assert data[0]["entry_id"] == "a1"

    restored = AuditLog.from_dicts(data)
    assert len(restored.entries) == 1
    assert restored.entries[0].rollback_data == {"key": "value"}
