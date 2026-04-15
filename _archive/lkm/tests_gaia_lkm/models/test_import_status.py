from datetime import datetime


def test_import_status_record_defaults():
    from gaia.lkm.models import ImportStatusRecord

    r = ImportStatusRecord(
        package_id="paper:12345",
        status="ingested",
        variable_count=10,
        factor_count=3,
        prior_count=8,
        factor_param_count=2,
    )
    assert r.package_id == "paper:12345"
    assert r.status == "ingested"
    assert r.variable_count == 10
    assert isinstance(r.started_at, datetime)
    assert isinstance(r.completed_at, datetime)


def test_import_status_roundtrip():
    from gaia.lkm.models import ImportStatusRecord
    from gaia.lkm.storage._serialization import import_status_to_row, row_to_import_status

    r = ImportStatusRecord(
        package_id="paper:99",
        status="ingested",
        variable_count=5,
        factor_count=2,
        prior_count=4,
        factor_param_count=1,
    )
    row = import_status_to_row(r)
    assert isinstance(row["started_at"], str)
    back = row_to_import_status(row)
    assert back.package_id == r.package_id
    assert back.variable_count == r.variable_count
    assert back.prior_count == r.prior_count
