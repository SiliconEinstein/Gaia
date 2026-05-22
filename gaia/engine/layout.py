"""Layout resolver for Gaia knowledge packages.

A "host" is any directory on disk that wants to project itself into a
Gaia knowledge package: an ARM bundle, an ARA artifact, a plain Python
package managed by ``uv pip``, a paper-side scratch dir, or a freshly
created folder.

Historically Gaia required the host to opt-in by *editing* its
``pyproject.toml`` (adding ``[tool.gaia]``) and reshuffling its source
into ``src/<import_name>/``. That contract is invasive — it forces every
host to look like a Gaia project even when its real role is "ARM bundle"
or "ARA artifact" or "scientific code I just want to mount".

This module makes the contract **non-invasive**: a host opts in by
creating exactly two sibling folders inside itself,

```
<host>/
  gaia/          # user-authored Gaia DSL (.py files + gaia.toml identity)
  .gaia/         # generated artifacts (ir.json, manifests/, source_map.json)
```

Nothing else in the host is touched. The host's own ``pyproject.toml``
(if any) stays a plain Python project. The new layout is what the
ARM/ARA projection spec §3.1 calls "native embedded layout"; the legacy
layout is still supported byte-for-byte so existing example packages
keep their IR hashes.

This module is intentionally **pure**: it returns a :class:`LayoutInfo`
descriptor; it does not import user code or touch ``sys.modules``. The
loader in :mod:`gaia.engine.packaging` is what acts on the descriptor.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from gaia.engine.manifest import GaiaManifest, GaiaManifestError, load_manifest

try:
    import tomllib
except ImportError:  # pragma: no cover — Python <3.11 fallback
    import tomli as tomllib  # type: ignore[no-redef]


_log = logging.getLogger(__name__)


__all__ = [
    "EMBEDDED_GAIA_DIR",
    "EMBEDDED_GAIA_MANIFEST",
    "EMBEDDED_GAIA_OUTPUT_DIR",
    "GaiaLayoutError",
    "LayoutInfo",
    "LayoutKind",
    "detect_layout",
    "synthetic_import_name",
]


EMBEDDED_GAIA_DIR = "gaia"
"""User-source folder inside a host (`<host>/gaia/`)."""

EMBEDDED_GAIA_MANIFEST = "gaia.toml"
"""Identity manifest inside the user-source folder (`<host>/gaia/gaia.toml`)."""

EMBEDDED_GAIA_OUTPUT_DIR = ".gaia"
"""Generated-artifacts folder inside a host (`<host>/.gaia/`)."""


_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]+")


class GaiaLayoutError(ValueError):
    """Raised when a host directory is not a recognisable Gaia layout."""


class LayoutKind(StrEnum):
    """Discriminator returned by :func:`detect_layout`.

    Two values, mapped one-to-one to the projection spec:

    - ``embedded`` — non-invasive: ``gaia/gaia.toml`` carries the
      identity; the host's own ``pyproject.toml`` (if any) is not
      required to mention Gaia at all.
    - ``legacy`` — historical: ``pyproject.toml`` with
      ``[tool.gaia].type = "knowledge-package"`` and ``src/<import>/``.
    """

    EMBEDDED = "embedded"
    LEGACY = "legacy"


@dataclass(frozen=True)
class LayoutInfo:
    """Resolved layout for one host directory.

    Attributes:
        kind: ``embedded`` or ``legacy``.
        host_path: The host directory itself (the path the user passed
            to ``gaia build compile``).
        manifest_path: For ``embedded``, ``<host>/gaia/gaia.toml``. For
            ``legacy``, ``<host>/pyproject.toml``. This is the file
            that uniquely identifies the Gaia package on disk.
        package_name: The Gaia package name (no ``-gaia`` suffix
            required in either mode; the suffix is preserved verbatim
            when present for backward compatibility).
        version: The package version string from the manifest.
        namespace: The Gaia QID namespace; defaults to ``"github"`` for
            legacy and to ``"github"`` for embedded unless the manifest
            overrides it.
        source_root: Filesystem root that contains the ``.py`` files
            the loader will import. For ``embedded`` this is
            ``<host>/gaia/``; for ``legacy`` it is the parent of the
            ``<import_name>/`` package (``<host>/`` or ``<host>/src/``).
        import_name: For ``legacy``, the actual Python import name
            (``project_name`` with ``-gaia`` stripped and ``-`` → ``_``).
            For ``embedded``, the *synthetic* import name minted by
            :func:`synthetic_import_name` — the loader uses this name
            instead of the literal ``"gaia"`` to avoid shadowing the
            installed ``gaia`` library.
        output_dir: ``<host>/.gaia/`` in both modes — manifests, IR,
            and inference outputs always land in the same place.
        config: The full parsed manifest (``pyproject.toml`` or
            ``gaia.toml``). Available so the loader can read
            ``[tool.gaia.quality]`` / ``[quality]`` etc. without
            re-parsing.
        project_config: The host's ``[project]`` table for legacy mode;
            for embedded mode, a synthetic table with ``name``,
            ``version``, and ``dependencies`` so downstream code that
            reads ``loaded.project_config`` keeps working unchanged.
        gaia_config: The Gaia identity / quality / projection block.
            For legacy this is ``config["tool"]["gaia"]``; for embedded
            it is the whole ``gaia.toml`` (sans the ``[package]``
            section, which is mirrored into ``project_config``).
    """

    kind: LayoutKind
    host_path: Path
    manifest_path: Path
    package_name: str
    version: str
    namespace: str
    source_root: Path
    import_name: str
    output_dir: Path
    config: dict[str, Any]
    project_config: dict[str, Any]
    gaia_config: dict[str, Any]


def synthetic_import_name(host_path: Path, *, package_name: str) -> str:
    """Mint a deterministic synthetic Python module name for an embedded package.

    The embedded layout stores user code under ``<host>/gaia/``. If we
    imported that folder as ``gaia`` it would clash with the installed
    ``gaia`` library on the very first ``from gaia.engine.lang import
    claim`` inside it. The projection spec §3.1 names this constraint
    explicitly:

        Native loader 应该用 path-based 或 synthetic-module loading,
        避免和 installed ``gaia`` library 发生 import-name 冲突.

    The synthetic name encodes both the package name (for readability
    in tracebacks) and a short hash of the absolute host path (for
    uniqueness across mounted packages with the same name). It is
    deterministic so reloads do not multiply ``sys.modules`` entries.

    The result is always a valid Python identifier prefixed with
    ``_gaia_pkg_`` and is intentionally **not** a public surface — users
    never refer to it.
    """
    slug = _SAFE_SLUG_RE.sub("_", package_name.lower()).strip("_") or "pkg"
    digest = hashlib.sha1(str(host_path.resolve()).encode("utf-8")).hexdigest()[:8]
    name = f"_gaia_pkg_{slug}_{digest}"
    if not _IDENT_RE.match(name):  # pragma: no cover — slug+prefix guarantees this
        name = f"_gaia_pkg_{digest}"
    return name


def detect_layout(path: str | Path) -> LayoutInfo:
    """Return the resolved layout for a host directory.

    Embedded takes priority over legacy: if a host has both
    ``gaia/gaia.toml`` *and* a legacy ``[tool.gaia]`` block, the
    embedded manifest wins. This matches the migration story — a host
    that wants to move off the invasive layout drops a ``gaia/`` folder
    in place and Gaia immediately starts compiling against the new
    source of truth without the user having to edit the host's
    ``pyproject.toml``. When both layouts coexist the function emits a
    user-visible warning so the precedence is not silent.
    """
    host = Path(path).resolve()
    if not host.exists():
        raise GaiaLayoutError(f"Error: path does not exist: {host}")
    if not host.is_dir():
        raise GaiaLayoutError(f"Error: path is not a directory: {host}")

    embedded_manifest = host / EMBEDDED_GAIA_DIR / EMBEDDED_GAIA_MANIFEST
    pyproject = host / "pyproject.toml"
    has_legacy = False
    pyproject_config: dict[str, Any] | None = None
    if pyproject.exists():
        try:
            with open(pyproject, "rb") as f:
                pyproject_config = tomllib.load(f)
        except tomllib.TOMLDecodeError as exc:
            raise GaiaLayoutError(f"Error: invalid pyproject.toml: {exc}") from exc
        gaia_block = pyproject_config.get("tool", {}).get("gaia", {})
        has_legacy = gaia_block.get("type") == "knowledge-package"

    if embedded_manifest.exists():
        if has_legacy:
            # Mid-migration host: warn rather than silently ignore the legacy
            # block so a user who forgot to delete `[tool.gaia]` sees that
            # their pyproject metadata is no longer the source of truth.
            _log.warning(
                "Warning: host %s has both embedded (%s) and legacy ([tool.gaia] in "
                "pyproject.toml) manifests. The embedded manifest wins; remove "
                "[tool.gaia] from pyproject.toml once the migration is done.",
                host,
                embedded_manifest.relative_to(host),
            )
        return _embedded_layout(host, embedded_manifest)

    if has_legacy:
        assert pyproject_config is not None
        return _legacy_layout(host, pyproject, pyproject_config)

    raise GaiaLayoutError(
        "Error: directory is not a Gaia knowledge package. Expected one of:\n"
        f"  - embedded layout: {host}/{EMBEDDED_GAIA_DIR}/{EMBEDDED_GAIA_MANIFEST}\n"
        f"  - legacy layout:   {host}/pyproject.toml with [tool.gaia].type = "
        '"knowledge-package"\n\n'
        f"Run `gaia build init --embedded {host}` (or `gaia pkg mount {host}`) "
        "to create an embedded layout non-invasively."
    )


def _legacy_layout(host: Path, pyproject: Path, config: dict[str, Any]) -> LayoutInfo:
    project = config.get("project") or {}
    gaia = config.get("tool", {}).get("gaia") or {}

    project_name = project.get("name")
    version = project.get("version")
    if not isinstance(project_name, str) or not project_name:
        raise GaiaLayoutError("Error: [project].name is required.")
    if not isinstance(version, str) or not version:
        raise GaiaLayoutError("Error: [project].version is required.")

    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    if not _IDENT_RE.match(import_name):
        raise GaiaLayoutError(
            f"Error: cannot derive import name from {project_name!r}: "
            f"got {import_name!r} which is not a valid Python identifier."
        )

    candidates = [host, host / "src"]
    source_root = next((root for root in candidates if (root / import_name).exists()), None)
    if source_root is None:
        expected = ", ".join(
            f"{candidate.relative_to(host)}/"
            for candidate in (root / import_name for root in candidates)
        )
        raise GaiaLayoutError(
            f"Error: package source directory '{import_name}/' not found.\n"
            f"  Derived from [project] name {project_name!r}.\n"
            '  Derivation: strip trailing "-gaia" when present, then convert '
            "hyphens to underscores.\n"
            f"  Expected at one of: {expected}"
        )

    namespace_raw = gaia.get("namespace")
    namespace: str = namespace_raw if isinstance(namespace_raw, str) else "github"
    return LayoutInfo(
        kind=LayoutKind.LEGACY,
        host_path=host,
        manifest_path=pyproject,
        package_name=project_name,
        version=version,
        namespace=namespace,
        source_root=source_root,
        import_name=import_name,
        output_dir=host / EMBEDDED_GAIA_OUTPUT_DIR,
        config=config,
        project_config=project,
        gaia_config=gaia,
    )


def _embedded_layout(host: Path, manifest_path: Path) -> LayoutInfo:
    """Parse ``gaia.toml`` via the pydantic model and project into LayoutInfo."""
    try:
        manifest: GaiaManifest = load_manifest(manifest_path)
    except GaiaManifestError as exc:
        raise GaiaLayoutError(str(exc)) from exc

    package = manifest.package
    # Default name to the host directory name when the user omitted it
    # entirely from gaia.toml (pydantic rejects empty strings already).
    project_name = package.name or host.name

    # gaia_config retains the non-identity manifest blocks (quality,
    # projection, extras) so downstream code can read it the same way
    # it read [tool.gaia] in legacy mode.
    raw_config = manifest.to_raw_dict()
    gaia_config: dict[str, Any] = {
        key: value for key, value in raw_config.items() if key != "package"
    }
    gaia_config.setdefault("type", "knowledge-package")
    gaia_config.setdefault("namespace", package.namespace)

    project_config: dict[str, Any] = {
        "name": project_name,
        "version": package.version,
        "dependencies": list(package.dependencies),
    }
    if package.description is not None:
        project_config["description"] = package.description
    if package.host_kind is not None:
        project_config["host_kind"] = package.host_kind
    if package.uuid is not None:
        # Surface the uuid both in project_config (where
        # `_validated_gaia_uuid` looks first) and gaia_config (legacy
        # path for callers that read it from [tool.gaia]).
        project_config["uuid"] = package.uuid
        gaia_config["uuid"] = package.uuid

    import_name = synthetic_import_name(host, package_name=project_name)
    source_root = host / EMBEDDED_GAIA_DIR
    return LayoutInfo(
        kind=LayoutKind.EMBEDDED,
        host_path=host,
        manifest_path=manifest_path,
        package_name=project_name,
        version=package.version,
        namespace=package.namespace,
        source_root=source_root,
        import_name=import_name,
        output_dir=host / EMBEDDED_GAIA_OUTPUT_DIR,
        config=raw_config,
        project_config=project_config,
        gaia_config=gaia_config,
    )
