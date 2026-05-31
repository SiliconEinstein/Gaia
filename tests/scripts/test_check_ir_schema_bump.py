"""Tests for ``scripts/check_ir_schema_bump.py`` — pre-push drift hook."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_ir_schema_bump.py"


def _load_script() -> ModuleType:
    """Import ``scripts/check_ir_schema_bump.py`` as a module for testing."""
    spec = importlib.util.spec_from_file_location("check_ir_schema_bump", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


def test_main_returns_zero_on_match(monkeypatch: pytest.MonkeyPatch) -> None:
    """When computed hash matches snapshot, ``main`` returns 0."""
    snapshot = script.IR_SCHEMA_SNAPSHOT_HASH
    monkeypatch.setattr(script, "compute_current_ir_hash", lambda: snapshot)
    assert script.main() == 0


def test_main_returns_one_on_mismatch_and_prints_fail(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Mismatched hashes return 1 with an actionable FAIL message.

    The output must contain both hashes, the current IR_SCHEMA_VERSION, and
    the two documented repair paths.
    """
    snapshot = script.IR_SCHEMA_SNAPSHOT_HASH
    drifted = "deadbeef0001"
    monkeypatch.setattr(script, "compute_current_ir_hash", lambda: drifted)
    rc = script.main()
    assert rc == 1
    err = capsys.readouterr().err
    assert "[FAIL]" in err
    assert "IR schema hash changed" in err
    assert snapshot in err
    assert drifted in err
    assert script.IR_SCHEMA_VERSION in err
    # Both documented repair paths are present.
    assert "Bump IR_SCHEMA_VERSION" in err
    assert "ALLOWED_IR_VERSIONS" in err
    assert "audit the diff" in err
