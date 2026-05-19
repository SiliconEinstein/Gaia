"""Shared registry metadata client — fetches package info from GitHub API."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass

import httpx

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

from gaia.engine.packaging import GaiaPackagingError

DEFAULT_REGISTRY = "SiliconEinstein/gaia-registry"


@dataclass
class RegistryVersion:
    """Resolved version metadata from the registry."""

    version: str
    repo: str
    git_tag: str
    git_sha: str
    ir_hash: str


def _github_headers() -> dict[str, str]:
    headers = {"Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _fetch_file(registry: str, path: str) -> str:
    url = f"https://api.github.com/repos/{registry}/contents/{path}"
    try:
        resp = httpx.get(url, headers=_github_headers(), timeout=15)
    except httpx.HTTPError as exc:
        raise GaiaPackagingError(f"Failed to reach registry: {exc}") from exc
    if resp.status_code == 404:
        raise GaiaPackagingError(f"Not found in registry: {path}")
    if resp.status_code == 403:
        raise GaiaPackagingError(
            "GitHub API rate limit exceeded. Set GITHUB_TOKEN to authenticate."
        )
    if resp.status_code >= 400:
        raise GaiaPackagingError(f"Registry API error ({resp.status_code}): {resp.text[:200]}")
    content = resp.json().get("content", "")
    return base64.b64decode(content).decode()


def fetch_file_optional(registry: str, path: str) -> str | None:
    """Like ``_fetch_file`` but returns *None* on 404 or network error.

    Used by ``gaia add`` to download optional release artifacts (e.g.
    ``beliefs.json``) without failing when the artifact hasn't been
    published yet (older packages, or registry versions that predate the
    beliefs manifest).
    """
    url = f"https://api.github.com/repos/{registry}/contents/{path}"
    try:
        resp = httpx.get(url, headers=_github_headers(), timeout=15)
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    content = resp.json().get("content", "")
    return base64.b64decode(content).decode()


def resolve_package(
    package: str,
    *,
    version: str | None = None,
    registry: str = DEFAULT_REGISTRY,
) -> RegistryVersion:
    """Resolve a package name (and optional version) to registry metadata."""
    # Strip -gaia suffix for registry lookup
    name = package.removesuffix("-gaia") if package.endswith("-gaia") else package

    pkg_toml = tomllib.loads(_fetch_file(registry, f"packages/{name}/Package.toml"))
    ver_toml = tomllib.loads(_fetch_file(registry, f"packages/{name}/Versions.toml"))

    versions = ver_toml.get("versions", {})
    if not versions:
        raise GaiaPackagingError(f"No versions found for package '{name}'.")

    if version is None:
        from packaging.version import Version

        version = max(versions, key=Version)

    if version not in versions:
        available = ", ".join(versions)
        raise GaiaPackagingError(
            f"Version '{version}' not found for '{name}'. Available: {available}"
        )

    entry = versions[version]
    return RegistryVersion(
        version=version,
        repo=pkg_toml["repo"],
        git_tag=entry["git_tag"],
        git_sha=entry["git_sha"],
        ir_hash=entry["ir_hash"],
    )
