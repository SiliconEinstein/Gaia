"""Tests for the non-blocking PyPI update-check (``gaia.cli._update_check``).

Covers: notice fires when a newer version (incl. prerelease > prerelease)
is on PyPI; silence on equal / ahead / opt-out / CI / network-error /
malformed-JSON / unresolvable-version; throttle honored within TTL and
re-checked after; output lands on stderr (not stdout); stdin is never read.

No test touches the network — every test injects a fetcher or monkeypatches
the default fetcher. A tmp ``XDG_CACHE_HOME`` fixture isolates the throttle
stamp so no real ``~/.cache/gaia/update-check.json`` is touched.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

from gaia.cli import _update_check as uc

pytestmark = pytest.mark.pr_gate

_INSTALLED = "0.5.0a1"


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Redirect the cache to a tmp dir and clear all skip-condition env vars."""
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    monkeypatch.delenv(uc._OPT_OUT_ENV, raising=False)
    monkeypatch.delenv(uc._TTL_ENV, raising=False)
    monkeypatch.delenv("CI", raising=False)
    # Pin the installed version so ordering assertions are deterministic.
    monkeypatch.setattr(uc, "get_library_version", lambda: _INSTALLED)


def _payload(*versions: str, yanked: tuple[str, ...] = ()) -> dict[str, object]:
    """Build a minimal PyPI JSON payload with the given release versions.

    Each version gets one non-yanked file unless listed in ``yanked``, in
    which case its single file is marked yanked. ``info.version`` is set to a
    deliberately *stale* stable value to prove the scanner reads ``releases``
    (the prerelease line), not ``info.version``.
    """
    releases: dict[str, object] = {}
    for v in versions:
        releases[v] = [{"filename": f"gaia_lang-{v}.whl", "yanked": v in yanked}]
    return {"info": {"version": "0.4.0"}, "releases": releases}


def _capture(monkeypatch: pytest.MonkeyPatch) -> tuple[io.StringIO, io.StringIO]:
    """Replace stdout + stderr with capturing buffers; return ``(out, err)``."""
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr(uc.sys, "stdout", out)
    monkeypatch.setattr(uc.sys, "stderr", err)
    return out, err


# --------------------------------------------------------------------------- #
# latest_pypi_version — pure version-picking                                  #
# --------------------------------------------------------------------------- #


class TestLatestPypiVersion:
    def test_picks_max_prerelease(self) -> None:
        payload = _payload("0.5.0a1", "0.5.0a4", "0.5.0a2")
        assert uc.latest_pypi_version(payload) == "0.5.0a4"

    def test_prerelease_below_stable_ordering(self) -> None:
        # PEP 440: 0.5.0a4 < 0.5.0 < 0.5.1 — the final must win.
        payload = _payload("0.5.0a4", "0.5.0", "0.5.1")
        assert uc.latest_pypi_version(payload) == "0.5.1"

    def test_skips_fully_yanked(self) -> None:
        payload = _payload("0.5.0a4", "0.5.0a9", yanked=("0.5.0a9",))
        assert uc.latest_pypi_version(payload) == "0.5.0a4"

    def test_skips_unparseable_versions(self) -> None:
        payload = _payload("0.5.0a4", "not-a-version")
        assert uc.latest_pypi_version(payload) == "0.5.0a4"

    def test_none_when_no_releases(self) -> None:
        assert uc.latest_pypi_version({"info": {}, "releases": {}}) is None

    def test_none_when_releases_missing(self) -> None:
        assert uc.latest_pypi_version({"info": {}}) is None

    def test_ignores_info_version(self) -> None:
        # info.version is the stale 0.4.0 stub; the prerelease line must win.
        payload = _payload("0.5.0a3")
        assert uc.latest_pypi_version(payload) == "0.5.0a3"


# --------------------------------------------------------------------------- #
# maybe_notify_update — notice fires                                          #
# --------------------------------------------------------------------------- #


class TestNoticeFires:
    def test_prerelease_to_prerelease(self, monkeypatch: pytest.MonkeyPatch) -> None:
        out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0a1", "0.5.0a4"))
        assert "gaia-lang 0.5.0a4 is available" in err.getvalue()
        assert "you have 0.5.0a1" in err.getvalue()
        # stdout stays clean.
        assert out.getvalue() == ""

    def test_notice_includes_upgrade_and_silence_lines(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0a4"))
        text = err.getvalue()
        assert "Upgrade:" in text
        assert "GAIA_NO_UPDATE_CHECK=1" in text

    def test_stable_release_above_installed_prerelease(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        _out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0"))
        assert "gaia-lang 0.5.0 is available" in err.getvalue()


# --------------------------------------------------------------------------- #
# maybe_notify_update — silence                                               #
# --------------------------------------------------------------------------- #


class TestSilence:
    def test_silent_when_equal(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0a1"))
        assert err.getvalue() == ""

    def test_silent_when_installed_ahead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.4.0"))
        assert err.getvalue() == ""

    def test_silent_on_opt_out(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(uc._OPT_OUT_ENV, "1")
        _out, err = _capture(monkeypatch)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        assert err.getvalue() == ""
        assert called["n"] == 0  # skipped before any network

    def test_silent_in_ci(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CI", "true")
        _out, err = _capture(monkeypatch)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        assert err.getvalue() == ""
        assert called["n"] == 0

    def test_silent_on_network_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: None)
        assert err.getvalue() == ""

    def test_silent_on_malformed_json(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, err = _capture(monkeypatch)
        # A dict with no usable releases mimics unexpected JSON shape.
        uc.maybe_notify_update(fetcher=lambda: {"unexpected": "shape"})
        assert err.getvalue() == ""

    def test_silent_when_version_unresolved(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom() -> str:
            from importlib.metadata import PackageNotFoundError

            raise PackageNotFoundError("gaia-lang")

        monkeypatch.setattr(uc, "get_library_version", boom)
        _out, err = _capture(monkeypatch)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        assert err.getvalue() == ""
        assert called["n"] == 0  # version-unresolved skips before network

    def test_silent_when_stderr_closed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        closed = io.StringIO()
        closed.close()
        monkeypatch.setattr(uc.sys, "stderr", closed)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        assert called["n"] == 0  # non-writable stderr skips before network


# --------------------------------------------------------------------------- #
# throttle                                                                    #
# --------------------------------------------------------------------------- #


class TestThrottle:
    def test_second_call_within_ttl_skips_network(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, err = _capture(monkeypatch)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        uc.maybe_notify_update(fetcher=fetcher)
        # Only the first call hit the fetcher; the second reused the stamp.
        assert called["n"] == 1
        # Notice still surfaces both times (cached "latest" still > installed).
        assert err.getvalue().count("gaia-lang 0.5.0a4 is available") == 2

    def test_recheck_after_ttl(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv(uc._TTL_ENV, "0")  # TTL=0 → stamp is always stale
        _out, _err = _capture(monkeypatch)
        called = {"n": 0}

        def fetcher() -> dict[str, object]:
            called["n"] += 1
            return _payload("0.5.0a4")

        uc.maybe_notify_update(fetcher=fetcher)
        uc.maybe_notify_update(fetcher=fetcher)
        assert called["n"] == 2  # both calls re-checked

    def test_stamp_rewritten_on_network_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, _err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: None)
        stamp = json.loads(uc.cache_path().read_text(encoding="utf-8"))
        assert "checked_at" in stamp
        assert stamp["latest"] is None  # failure recorded → throttles retries

    def test_stamp_records_latest_on_success(self, monkeypatch: pytest.MonkeyPatch) -> None:
        _out, _err = _capture(monkeypatch)
        uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0a4"))
        stamp = json.loads(uc.cache_path().read_text(encoding="utf-8"))
        assert stamp["latest"] == "0.5.0a4"


# --------------------------------------------------------------------------- #
# stdin is never read                                                         #
# --------------------------------------------------------------------------- #


def test_stdin_never_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The notice must never touch stdin (an agent would hang on a prompt)."""

    class ExplodingStdin:
        def read(self, *_args: object, **_kwargs: object) -> str:
            raise AssertionError("update check read from stdin")

        def readline(self, *_args: object, **_kwargs: object) -> str:
            raise AssertionError("update check read from stdin")

    monkeypatch.setattr(uc.sys, "stdin", ExplodingStdin())
    _out, _err = _capture(monkeypatch)
    uc.maybe_notify_update(fetcher=lambda: _payload("0.5.0a4"))
    # No exception → stdin untouched.


# --------------------------------------------------------------------------- #
# cache path resolution                                                       #
# --------------------------------------------------------------------------- #


def test_cache_path_uses_xdg(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path))
    assert uc.cache_path() == tmp_path / "gaia" / "update-check.json"


# --------------------------------------------------------------------------- #
# _upgrade_command — install-method detection branches                        #
# --------------------------------------------------------------------------- #
#
# _upgrade_command inspects only sys.executable / sys.prefix / sys.base_prefix
# and probes for sibling pyproject.toml / uv.lock markers. Monkeypatching those
# four interpreter attributes (and laying down markers under tmp_path) pins each
# branch deterministically, independent of the real install environment.


def _allows_prerelease(cmd: str) -> bool:
    """A returned upgrade command must keep the user on the prerelease line."""
    return "--pre" in cmd or "--prerelease=allow" in cmd


class TestUpgradeCommand:
    def test_uv_tool_branch(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Executable/prefix under .../uv/tools/<name> → `uv tool upgrade`.
        tool_root = "/home/u/.local/share/uv/tools/gaia-lang"
        monkeypatch.setattr(uc.sys, "executable", f"{tool_root}/bin/python")
        monkeypatch.setattr(uc.sys, "prefix", tool_root)
        cmd = uc._upgrade_command()
        assert cmd == "uv tool upgrade --prerelease=allow gaia-lang"
        assert _allows_prerelease(cmd)

    def test_uv_project_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # A .venv with a sibling pyproject.toml → `uv add ... @latest`.
        venv = tmp_path / "myproj" / ".venv"
        venv.mkdir(parents=True)
        (tmp_path / "myproj" / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
        monkeypatch.setattr(uc.sys, "executable", str(venv / "bin" / "python"))
        monkeypatch.setattr(uc.sys, "prefix", str(venv))
        cmd = uc._upgrade_command()
        assert cmd == "uv add --prerelease=allow gaia-lang@latest"
        assert _allows_prerelease(cmd)

    def test_pip_venv_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Inside a virtualenv (prefix != base_prefix) but no uv markers → pip --pre.
        venv = tmp_path / "plainvenv"
        venv.mkdir()
        monkeypatch.setattr(uc.sys, "executable", str(venv / "bin" / "python"))
        monkeypatch.setattr(uc.sys, "prefix", str(venv))
        monkeypatch.setattr(uc.sys, "base_prefix", "/usr")
        cmd = uc._upgrade_command()
        assert cmd == "pip install -U --pre gaia-lang"
        assert _allows_prerelease(cmd)

    def test_generic_fallback_branch(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        # Not a venv (prefix == base_prefix), no uv markers → show both forms.
        sys_prefix = tmp_path / "sys"
        sys_prefix.mkdir()
        monkeypatch.setattr(uc.sys, "executable", str(sys_prefix / "bin" / "python"))
        monkeypatch.setattr(uc.sys, "prefix", str(sys_prefix))
        monkeypatch.setattr(uc.sys, "base_prefix", str(sys_prefix))
        cmd = uc._upgrade_command()
        assert "pip install -U --pre gaia-lang" in cmd
        assert "uv tool upgrade --prerelease=allow gaia-lang" in cmd
        assert _allows_prerelease(cmd)
