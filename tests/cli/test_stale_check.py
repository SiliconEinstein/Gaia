"""Tests for compiled artifact freshness checks."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from gaia.engine._stale_check import check_compiled_artifacts

pytestmark = pytest.mark.pr_gate


def test_check_compiled_artifacts_retries_transient_invalid_ir_json(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    gaia_dir = tmp_path / ".gaia"
    gaia_dir.mkdir()
    (gaia_dir / "ir_hash").write_text("abc", encoding="utf-8")
    (gaia_dir / "ir.json").write_text(json.dumps({"ir_hash": "abc"}), encoding="utf-8")

    original_read_text = Path.read_text
    calls = 0

    def flaky_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        nonlocal calls
        if path.name == "ir.json" and calls == 0:
            calls += 1
            return "{"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)

    result = check_compiled_artifacts(tmp_path, ir_hash="abc", retries=1, retry_delay_s=0)

    assert not result.is_stale
    assert calls == 1


def test_check_compiled_artifacts_reports_persistent_invalid_ir_json(tmp_path: Path) -> None:
    gaia_dir = tmp_path / ".gaia"
    gaia_dir.mkdir()
    (gaia_dir / "ir_hash").write_text("abc", encoding="utf-8")
    (gaia_dir / "ir.json").write_text("{", encoding="utf-8")

    result = check_compiled_artifacts(tmp_path, ir_hash="abc", retries=1, retry_delay_s=0)

    assert result.is_stale
    assert result.ir_json_invalid_reason is not None
