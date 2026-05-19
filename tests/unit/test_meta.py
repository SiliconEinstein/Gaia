"""Tests for ``gaia._meta`` — version metadata and IR schema compat."""

from __future__ import annotations

import re
import subprocess
import sys
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

from gaia import _meta
from gaia._meta import (
    ALLOWED_IR_VERSIONS,
    IR_SCHEMA,
    IR_SCHEMA_SNAPSHOT_HASH,
    IR_SCHEMA_VERSION,
    IncompatibleIRError,
    check_ir_compat,
    compute_current_ir_hash,
    get_channel,
    get_commit,
    get_library_version,
)

if TYPE_CHECKING:
    pass


# --------------------------------------------------------------------------- #
# compute_current_ir_hash                                                     #
# --------------------------------------------------------------------------- #


def test_compute_current_ir_hash_deterministic() -> None:
    """Hash is stable across calls in the same process."""
    assert compute_current_ir_hash() == compute_current_ir_hash()


def test_compute_current_ir_hash_is_12hex() -> None:
    """Hash is exactly 12 lowercase hex chars."""
    h = compute_current_ir_hash()
    assert re.fullmatch(r"[0-9a-f]{12}", h), h


# --------------------------------------------------------------------------- #
# IR_SCHEMA composition                                                       #
# --------------------------------------------------------------------------- #


def test_ir_schema_format() -> None:
    """``IR_SCHEMA`` equals ``{version}+{snapshot_hash}`` in-tree.

    Inside the worktree the current hash and the committed snapshot must agree;
    if they don't, the pre-push ``ir-schema-bump`` hook would (correctly) fail.
    """
    assert f"{IR_SCHEMA_VERSION}+{IR_SCHEMA_SNAPSHOT_HASH}" == IR_SCHEMA
    # And the IR_SCHEMA hash portion equals what compute_current_ir_hash() emits
    # right now, by construction (module-level binding).
    assert IR_SCHEMA.endswith(compute_current_ir_hash())


def test_ir_schema_version_constant() -> None:
    """``IR_SCHEMA_VERSION`` is the current pinned ir-vN slot."""
    assert IR_SCHEMA_VERSION == "ir-v1"


# --------------------------------------------------------------------------- #
# check_ir_compat                                                             #
# --------------------------------------------------------------------------- #


def test_check_ir_compat_accept_allowed() -> None:
    """Accepted version + arbitrary hash suffix passes silently."""
    check_ir_compat("ir-v1+anything")  # must not raise


def test_check_ir_compat_reject_unknown() -> None:
    """Unknown version (with hash suffix) raises ``IncompatibleIRError``."""
    with pytest.raises(IncompatibleIRError):
        check_ir_compat("ir-v2+x")


def test_check_ir_compat_reject_no_plus() -> None:
    """A bare version string with no '+' is still gated by the allowed set.

    ``split("+", 1)`` on a no-plus string returns ``["ir-v99"]``; the first
    element is the version prefix and must still match ``ALLOWED_IR_VERSIONS``.
    """
    with pytest.raises(IncompatibleIRError):
        check_ir_compat("ir-v99")


def test_allowed_ir_versions_contains_current() -> None:
    """``ALLOWED_IR_VERSIONS`` must contain the build's own ``IR_SCHEMA_VERSION``."""
    assert IR_SCHEMA_VERSION in ALLOWED_IR_VERSIONS


# --------------------------------------------------------------------------- #
# get_channel                                                                 #
# --------------------------------------------------------------------------- #


def test_get_channel_dev_default(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without ``gaia/_build_info.py`` available, channel falls back to 'dev'."""
    # Ensure no cached _build_info; block import by inserting None sentinel.
    monkeypatch.setitem(sys.modules, "gaia._build_info", None)
    assert get_channel() == "dev"


def test_get_channel_from_build_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``_build_info`` is importable, channel is read from it."""
    fake = type(sys)("gaia._build_info")
    fake.CHANNEL = "nightly"  # type: ignore[attr-defined]
    fake.COMMIT = "deadbeef1234"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gaia._build_info", fake)
    assert get_channel() == "nightly"


# --------------------------------------------------------------------------- #
# get_commit                                                                  #
# --------------------------------------------------------------------------- #


def test_get_commit_unknown_no_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """If git is unavailable and no ``_build_info``, returns 'unknown'."""
    monkeypatch.setitem(sys.modules, "gaia._build_info", None)

    def _raise(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("git")

    monkeypatch.setattr(_meta.subprocess, "run", _raise)
    assert get_commit() == "unknown"


def test_get_commit_unknown_on_nonzero_returncode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Git invocation succeeds-as-process but returns non-zero -> 'unknown'."""
    monkeypatch.setitem(sys.modules, "gaia._build_info", None)

    def _nonzero(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args=["git"], returncode=128, stdout="", stderr="")

    monkeypatch.setattr(_meta.subprocess, "run", _nonzero)
    assert get_commit() == "unknown"


def test_get_commit_from_build_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When ``_build_info`` is importable, commit comes from it (no git call)."""
    fake = type(sys)("gaia._build_info")
    fake.CHANNEL = "nightly"  # type: ignore[attr-defined]
    fake.COMMIT = "cafebabe0001"  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gaia._build_info", fake)

    def _explode(*_a: object, **_k: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError("subprocess.run should not be called when _build_info present")

    monkeypatch.setattr(_meta.subprocess, "run", _explode)
    assert get_commit() == "cafebabe0001"


def test_get_commit_local_git(monkeypatch: pytest.MonkeyPatch) -> None:
    """In the worktree, with no ``_build_info``, returns the local short sha."""
    monkeypatch.setitem(sys.modules, "gaia._build_info", None)
    sha = get_commit()
    assert sha != "unknown"
    assert re.fullmatch(r"[0-9a-f]{4,40}", sha), sha


# --------------------------------------------------------------------------- #
# get_library_version                                                         #
# --------------------------------------------------------------------------- #


def test_get_library_version_nonempty() -> None:
    """Library version is a non-empty string sourced from package metadata."""
    v = get_library_version()
    assert isinstance(v, str)
    assert v.strip() != ""


# --------------------------------------------------------------------------- #
# IncompatibleIRError                                                         #
# --------------------------------------------------------------------------- #


def test_incompatible_ir_error_is_exception() -> None:
    """``IncompatibleIRError`` is a subclass of ``Exception``."""
    assert issubclass(IncompatibleIRError, Exception)


# Silence unused-import warning for explicit re-test of patch (kept available
# for downstream extension).
_ = patch
