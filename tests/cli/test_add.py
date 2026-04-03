"""Tests for gaia add command."""

from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from gaia.cli._packages import GaiaCliError
from gaia.cli._registry import RegistryVersion, _fetch_file, resolve_package
from gaia.cli.main import app

runner = CliRunner()

MOCK_VERSION = RegistryVersion(
    version="4.0.5",
    repo="https://github.com/kunyuan/GalileoFallingBodies.gaia",
    git_tag="v4.0.5",
    git_sha="dac84fc722bf81398a7e77c830a60b2b068de18a",
    ir_hash="sha256:abc123",
)


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_installs_with_git_url(mock_uv, mock_resolve):
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    mock_resolve.assert_called_once()
    uv_args = mock_uv.call_args[0][0]
    assert "git+" in uv_args[2]
    assert "dac84fc7" in uv_args[2]


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_with_version(mock_uv, mock_resolve):
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["add", "galileo-falling-bodies-gaia", "--version", "4.0.5"])
    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(
        "galileo-falling-bodies-gaia",
        version="4.0.5",
        registry="SiliconEinstein/gaia-registry",
    )


@patch("gaia.cli.commands.add.resolve_package")
def test_add_not_found(mock_resolve):
    mock_resolve.side_effect = GaiaCliError("Not found in registry: packages/no-such/Package.toml")
    result = runner.invoke(app, ["add", "no-such-gaia"])
    assert result.exit_code != 0
    assert "Not found" in result.output


# --- Issue 2: Canonicalize package name (add -gaia suffix) ---


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_canonicalizes_name_without_gaia_suffix(mock_uv, mock_resolve):
    """Package name without -gaia suffix still gets correct dep spec."""
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["add", "galileo-falling-bodies"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    uv_args = mock_uv.call_args[0][0]
    dep_spec = uv_args[2]
    # dep_spec must start with the canonical name ending in -gaia
    assert dep_spec.startswith("galileo-falling-bodies-gaia @")


# --- Issue 1: Version sorting (semantic, not lexicographic) ---


@patch("gaia.cli._registry._fetch_file")
def test_resolve_package_picks_max_version_semantically(mock_fetch):
    """Version selection uses semantic sorting, not lexicographic (1.10.0 > 1.9.0)."""
    pkg_toml = '[repo]\nrepo = "https://github.com/example/pkg.gaia"\n'
    ver_toml = (
        '[versions."1.9.0"]\ngit_tag = "v1.9.0"\ngit_sha = "aaa"\nir_hash = "h1"\n'
        '[versions."1.10.0"]\ngit_tag = "v1.10.0"\ngit_sha = "bbb"\nir_hash = "h2"\n'
    )

    def fake_fetch(registry, path):
        if "Package.toml" in path:
            return pkg_toml
        return ver_toml

    mock_fetch.side_effect = fake_fetch
    result = resolve_package("test-pkg")
    assert result.version == "1.10.0"
    assert result.git_sha == "bbb"


# --- Issue 3: Handle GitHub API errors ---


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_handles_timeout(mock_get):
    """Timeout raises GaiaCliError, not raw httpx exception."""
    mock_get.side_effect = httpx.ConnectTimeout("timed out")
    with pytest.raises(GaiaCliError, match="Failed to reach registry"):
        _fetch_file("owner/repo", "some/path")


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_handles_403_rate_limit(mock_get):
    """403 raises rate-limit message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp
    with pytest.raises(GaiaCliError, match="rate limit"):
        _fetch_file("owner/repo", "some/path")


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_handles_500_error(mock_get):
    """Generic server error raises descriptive message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_get.return_value = mock_resp
    with pytest.raises(GaiaCliError, match="Registry API error.*500"):
        _fetch_file("owner/repo", "some/path")


# --- Issue 4: Handle missing uv binary ---


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add.subprocess.run", side_effect=FileNotFoundError("uv"))
def test_add_missing_uv_shows_install_hint(mock_run, mock_resolve):
    """Missing uv binary gives a helpful error message."""
    result = runner.invoke(app, ["add", "some-gaia"])
    assert result.exit_code != 0
    assert "uv is not installed" in result.output
