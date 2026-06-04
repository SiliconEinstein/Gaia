"""Tests for gaia add command."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest
from typer.testing import CliRunner

from gaia.cli._registry import RegistryVersion, _fetch_file, fetch_file_optional, resolve_package
from gaia.cli.main import app
from gaia.engine.packaging import GaiaPackagingError

pytestmark = pytest.mark.pr_gate

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
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    mock_resolve.assert_called_once()
    uv_args = mock_uv.call_args[0][0]
    assert "git+" in uv_args[2]
    assert "dac84fc7" in uv_args[2]


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_with_version(mock_uv, mock_resolve):
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia", "--version", "4.0.5"])
    assert result.exit_code == 0
    mock_resolve.assert_called_once_with(
        "galileo-falling-bodies-gaia",
        version="4.0.5",
        registry="SiliconEinstein/gaia-registry",
    )


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_warns_when_lkm_index_is_unused_for_registry_package(mock_uv, mock_resolve):
    del mock_resolve
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(
        app,
        ["pkg", "add", "galileo-falling-bodies-gaia", "--lkm-index", "private_index"],
    )
    assert result.exit_code == 0, result.output
    assert "ignoring --lkm-index 'private-index'" in result.output
    assert "resolves registry packages" in result.output


@patch("gaia.cli.commands.add.resolve_package")
def test_add_not_found(mock_resolve):
    mock_resolve.side_effect = GaiaPackagingError(
        "Not found in registry: packages/no-such/Package.toml"
    )
    result = runner.invoke(app, ["pkg", "add", "no-such-gaia"])
    assert result.exit_code != 0
    assert "Not found" in result.output


def test_add_accepts_lkm_paper_flags_as_source_ref():
    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-server", "bohrium", "--lkm-paper", "811827932371615744"],
    )
    assert result.exit_code == 1
    assert "lkm:bohrium:paper:811827932371615744" in result.output
    assert "inside the package that should depend on this LKM paper" in result.output


def test_add_accepts_lkm_index_paper_flags_as_source_ref():
    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )
    assert result.exit_code == 1
    assert "lkm:bohrium:paper:811827932371615744" in result.output
    assert "inside the package that should depend on this LKM paper" in result.output


def test_add_accepts_canonical_lkm_paper_ref_as_source_ref():
    result = runner.invoke(app, ["pkg", "add", "lkm:bohrium:paper:811827932371615744"])
    assert result.exit_code == 1
    assert "lkm:bohrium:paper:811827932371615744" in result.output
    assert "inside the package that should depend on this LKM paper" in result.output


def test_add_accepts_short_lkm_paper_ref_as_default_server_alias():
    result = runner.invoke(app, ["pkg", "add", "lkm:paper:811827932371615744"])
    assert result.exit_code == 1
    assert "lkm:bohrium:paper:811827932371615744" in result.output


def test_add_accepts_lkm_claim_flags_as_source_ref():
    result = runner.invoke(app, ["pkg", "add", "--lkm-claim", "gcn_abc123"])
    assert result.exit_code == 1
    assert "lkm:bohrium:claim:gcn_abc123" in result.output
    assert "inside the package that should depend on this LKM paper" in result.output


def test_add_rejects_conflicting_lkm_inputs_before_registry_lookup():
    result = runner.invoke(
        app,
        [
            "pkg",
            "add",
            "galileo-falling-bodies-gaia",
            "--lkm-paper",
            "811827932371615744",
        ],
    )
    assert result.exit_code == 4
    assert "pass either PACKAGE or LKM flags" in result.output


@patch("gaia.cli.commands.add._run_uv")
def test_add_local_gaia_package_as_editable_dependency(mock_uv, tmp_path, monkeypatch):
    """Gaia pkg add --local installs a local Gaia package into the target package."""
    consumer = tmp_path / "consumer-gaia"
    dependency = tmp_path / "source-paper-gaia"
    consumer.mkdir()
    dependency.mkdir()
    _write_gaia_package_root(consumer)
    _write_gaia_package_root(dependency)
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)

    result = runner.invoke(
        app,
        ["pkg", "add", "--target", str(consumer), "--local", str(dependency)],
    )

    assert result.exit_code == 0, result.output
    mock_uv.assert_called_once_with(
        ["uv", "add", "--editable", str(dependency.resolve())],
        cwd=consumer.resolve(),
    )
    assert f"Added local Gaia package: {dependency.resolve()}" in result.output


def test_add_local_requires_local_gaia_package(tmp_path, monkeypatch):
    """Gaia pkg add --local rejects paths that are not Gaia knowledge packages."""
    consumer = tmp_path / "consumer-gaia"
    not_package = tmp_path / "not-package"
    consumer.mkdir()
    not_package.mkdir()
    _write_gaia_package_root(consumer)
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(
        app,
        ["pkg", "add", "--target", str(consumer), "--local", str(not_package)],
    )

    assert result.exit_code == 1
    assert "not a Gaia knowledge package" in result.output


def test_add_local_rejects_package_argument():
    result = runner.invoke(
        app,
        ["pkg", "add", "galileo-falling-bodies-gaia", "--local", "./dep"],
    )

    assert result.exit_code == 4
    assert "pass --local by itself" in result.output


def test_add_rejects_malformed_lkm_ref():
    result = runner.invoke(app, ["pkg", "add", "lkm:bohrium:dataset:123"])
    assert result.exit_code == 4
    assert "expected lkm:<index>:paper:<id>" in result.output


# --- Issue 2: Canonicalize package name (add -gaia suffix) ---


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
def test_add_canonicalizes_name_without_gaia_suffix(mock_uv, mock_resolve):
    """Package name without -gaia suffix still gets correct dep spec."""
    del mock_resolve
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies"])
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
        del registry
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
    """Timeout raises GaiaPackagingError, not raw httpx exception."""
    mock_get.side_effect = httpx.ConnectTimeout("timed out")
    with pytest.raises(GaiaPackagingError, match="Failed to reach registry"):
        _fetch_file("owner/repo", "some/path")


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_handles_403_rate_limit(mock_get):
    """403 raises rate-limit message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 403
    mock_get.return_value = mock_resp
    with pytest.raises(GaiaPackagingError, match="rate limit"):
        _fetch_file("owner/repo", "some/path")


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_handles_500_error(mock_get):
    """Generic server error raises descriptive message."""
    mock_resp = MagicMock()
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_get.return_value = mock_resp
    with pytest.raises(GaiaPackagingError, match=r"Registry API error.*500"):
        _fetch_file("owner/repo", "some/path")


# --- Issue 4: Handle missing uv binary ---


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add.subprocess.run", side_effect=FileNotFoundError("uv"))
def test_add_missing_uv_shows_install_hint(mock_run, mock_resolve):
    """Missing uv binary gives a helpful error message."""
    del mock_resolve, mock_run
    result = runner.invoke(app, ["pkg", "add", "some-gaia"])
    assert result.exit_code != 0
    assert "uv is not installed" in result.output


# --- fetch_file_optional ---


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_optional_returns_content_on_200(mock_get):
    """fetch_file_optional returns decoded content on 200."""
    import base64

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"content": base64.b64encode(b'{"beliefs": []}').decode()}
    mock_get.return_value = mock_resp
    result = fetch_file_optional("owner/repo", "some/path.json")
    assert result == '{"beliefs": []}'


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_optional_returns_none_on_404(mock_get):
    """fetch_file_optional returns None on 404."""
    mock_resp = MagicMock()
    mock_resp.status_code = 404
    mock_get.return_value = mock_resp
    result = fetch_file_optional("owner/repo", "nonexistent/path.json")
    assert result is None


@patch("gaia.cli._registry.httpx.get")
def test_fetch_file_optional_returns_none_on_network_error(mock_get):
    """fetch_file_optional returns None on network error."""
    mock_get.side_effect = httpx.ConnectTimeout("timed out")
    result = fetch_file_optional("owner/repo", "some/path.json")
    assert result is None


# --- dep_beliefs download in gaia add ---


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional")
def test_add_downloads_dep_beliefs(mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch):
    """Gaia add downloads beliefs.json into .gaia/dep_beliefs/."""
    del mock_resolve
    # Create a minimal Gaia package root so _find_gaia_package_root works
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\n'
    )
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)
    mock_fetch.return_value = '{"beliefs": [{"knowledge_id": "a", "belief": 0.8}]}'
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0, f"Failed: {result.output}"
    assert "Saved upstream beliefs" in result.output
    dep_file = tmp_path / ".gaia" / "dep_beliefs" / "galileo_falling_bodies.json"
    assert dep_file.exists()
    import json

    data = json.loads(dep_file.read_text())
    assert data["beliefs"][0]["belief"] == 0.8


def _write_gaia_package_root(root: Path) -> None:
    """Write a minimal knowledge-package pyproject.toml at *root*."""
    (root / "pyproject.toml").write_text(
        '[project]\nname = "test-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\n'
    )


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional", return_value=None)
def test_add_succeeds_without_beliefs_manifest(
    mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch
):
    """Gaia add succeeds even when beliefs.json is not available."""
    del mock_fetch, mock_resolve
    _write_gaia_package_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0
    assert "no beliefs manifest" in result.output.lower()


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional", return_value="not valid json {{{")
def test_add_handles_invalid_beliefs_json(mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch):
    """Gaia add gracefully handles invalid JSON in beliefs manifest."""
    del mock_fetch, mock_resolve
    _write_gaia_package_root(tmp_path)
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0
    assert "not valid json" in result.output.lower()


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional")
def test_add_registry_skips_dep_beliefs_outside_gaia_package(
    mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch
):
    """Registry add outside a Gaia package still succeeds, skipping dep_beliefs."""
    del mock_resolve
    # tmp_path has no knowledge-package pyproject — no consumer root resolves.
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)
    mock_fetch.return_value = '{"beliefs": []}'
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0
    assert "not inside a gaia package" in result.output.lower()


@patch("gaia.cli.commands.add._run_uv")
def test_add_lkm_paper_errors_outside_gaia_package(mock_uv, tmp_path, monkeypatch):
    """LKM paper add outside a Gaia package errors (it must mutate a package)."""
    mock_uv.return_value = MagicMock(returncode=0)
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["pkg", "add", "--lkm-paper", "811827932371615744"])
    assert result.exit_code == 1
    assert "inside the package that should depend on this lkm paper" in result.output.lower()


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional")
def test_add_target_points_at_package_from_parent(
    mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch
):
    """Gaia add --target ./pkg resolves the package from the parent directory."""
    del mock_resolve
    pkg_root = tmp_path / "consumer-gaia"
    pkg_root.mkdir()
    _write_gaia_package_root(pkg_root)
    monkeypatch.chdir(tmp_path)
    mock_uv.return_value = MagicMock(returncode=0)
    mock_fetch.return_value = '{"beliefs": [{"knowledge_id": "a", "belief": 0.6}]}'
    result = runner.invoke(
        app, ["pkg", "add", "galileo-falling-bodies-gaia", "--target", "./consumer-gaia"]
    )
    assert result.exit_code == 0, result.output
    dep_file = pkg_root / ".gaia" / "dep_beliefs" / "galileo_falling_bodies.json"
    assert dep_file.exists()


@patch("gaia.cli.commands.add.resolve_package", return_value=MOCK_VERSION)
@patch("gaia.cli.commands.add._run_uv")
@patch("gaia.cli.commands.add.fetch_file_optional")
def test_add_writes_dep_beliefs_at_package_root_from_subdir(
    mock_fetch, mock_uv, mock_resolve, tmp_path, monkeypatch
):
    """Gaia add from a subdirectory writes dep_beliefs at the package root."""
    del mock_resolve
    # Create package root with pyproject.toml
    (tmp_path / "pyproject.toml").write_text(
        '[project]\nname = "test-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\ntype = "knowledge-package"\n'
    )
    subdir = tmp_path / "src" / "nested"
    subdir.mkdir(parents=True)
    monkeypatch.chdir(subdir)
    mock_uv.return_value = MagicMock(returncode=0)
    mock_fetch.return_value = '{"beliefs": [{"knowledge_id": "a", "belief": 0.7}]}'
    result = runner.invoke(app, ["pkg", "add", "galileo-falling-bodies-gaia"])
    assert result.exit_code == 0
    # dep_beliefs should be at the package root, not in the subdir
    dep_file = tmp_path / ".gaia" / "dep_beliefs" / "galileo_falling_bodies.json"
    assert dep_file.exists()
    assert not (subdir / ".gaia" / "dep_beliefs").exists()
