"""Gaia Lang v5 — internal declaration collector and inferred package registry."""

from __future__ import annotations

import inspect
import sys
from contextvars import Token
from pathlib import Path
from types import TracebackType
from typing import TYPE_CHECKING, Any

from gaia.engine.lang.runtime.knowledge import Knowledge, _current_package
from gaia.engine.lang.runtime.nodes import Operator, Strategy

if TYPE_CHECKING:
    from gaia.engine.lang.runtime.action import GaiaGraph, MaterializationLink
    from gaia.engine.lang.runtime.distribution import Distribution

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


class CollectedPackage:
    """Internal collector for declarations belonging to a knowledge package."""

    def __init__(self, name: str, *, namespace: str = "github", version: str = "0.1.0") -> None:
        """Create an empty declaration collector for a package."""
        self.name = name
        self.namespace = namespace
        self.version = version
        self.knowledge: list[Knowledge] = []
        self.strategies: list[Strategy] = []
        self.operators: list[Operator] = []
        self.actions: list[GaiaGraph] = []
        self.materializations: list[MaterializationLink] = []
        # Lang-only registry of Distribution objects declared while this
        # package was active. Distributions are NOT added to ``knowledge``
        # (they are not IR-bound — see gaia/engine/lang/runtime/distribution.py),
        # but the declaration list lets compile-time diagnostics detect
        # quantities that are declared but never referenced.
        self.distributions: list[Distribution] = []
        self._token: Token[CollectedPackage | None] | None = None
        self._module_counters: dict[str | None, int] = {}
        self._module_order: list[str] = []
        self._module_titles: dict[str, str] | None = None
        self._exported_labels: set[str] = set()
        self._resolution_policy: Any | None = None

    def __enter__(self) -> CollectedPackage:
        """Activate this package collector for module-scope declarations."""
        self._token = _current_package.set(self)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        """Deactivate this package collector."""
        if self._token is not None:
            _current_package.reset(self._token)
        self._token = None

    def _register_knowledge(self, k: Knowledge) -> None:
        self.knowledge.append(k)
        from gaia.engine.lang.runtime.composition import _capture_registered

        _capture_registered(k)
        module = k._source_module
        if module not in self._module_counters:
            if module is not None:
                self._module_order.append(module)
            self._module_counters[module] = 0
        k._declaration_index = self._module_counters[module]
        self._module_counters[module] += 1

    def _register_strategy(self, s: Strategy) -> None:
        self.strategies.append(s)
        from gaia.engine.lang.runtime.composition import _capture_registered

        _capture_registered(s)

    def _register_operator(self, o: Operator) -> None:
        self.operators.append(o)
        from gaia.engine.lang.runtime.composition import _capture_registered

        _capture_registered(o)

    def _register_action(self, a: GaiaGraph) -> None:
        self.actions.append(a)
        from gaia.engine.lang.runtime.composition import _capture_registered

        _capture_registered(a)

    def _register_materialization(self, link: MaterializationLink) -> None:
        self.materializations.append(link)

    @property
    def exported(self) -> list[str]:
        """Return exported knowledge labels in declaration order."""
        if self._exported_labels:
            return [k.label for k in self.knowledge if k.label in self._exported_labels]
        return [k.label for k in self.knowledge if k.label is not None]


_inferred_packages: dict[Path, CollectedPackage] = {}
_module_pyproject_cache: dict[str, Path | None] = {}

# Embedded layout manifest filename, kept here as a literal so this
# module stays import-cheap (it is hit on every DSL call). Keep in sync
# with gaia.engine.layout.EMBEDDED_GAIA_MANIFEST.
_EMBEDDED_GAIA_DIR = "gaia"
_EMBEDDED_MANIFEST = "gaia.toml"


def _project_to_import_name(project_name: str) -> str:
    return project_name.removesuffix("-gaia").replace("-", "_")


def _find_package_manifest(start: Path) -> Path | None:
    """Walk up from *start* and return the nearest Gaia package manifest.

    Two manifest kinds are recognised, in priority order:

    1. ``<dir>/gaia/gaia.toml`` — the non-invasive embedded layout. We
       check this *first* so a host that has both an embedded ``gaia/``
       and a legacy ``[tool.gaia]`` block compiles against the
       embedded manifest. This matches :func:`detect_layout` and keeps
       the in-process inference path consistent with the on-disk
       loader.
    2. ``<dir>/pyproject.toml`` with ``[tool.gaia].type ==
       "knowledge-package"`` — the historical layout.

    Plain ``pyproject.toml`` files without ``[tool.gaia]`` are skipped
    (a Gaia user package sitting next to an ARM/ARA host pyproject is
    fully supported).
    """
    for candidate in (start, *start.parents):
        embedded = candidate / _EMBEDDED_GAIA_DIR / _EMBEDDED_MANIFEST
        if embedded.exists():
            return embedded
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists():
            try:
                with open(pyproject, "rb") as f:
                    config = tomllib.load(f)
            except tomllib.TOMLDecodeError:
                continue
            gaia = config.get("tool", {}).get("gaia", {})
            if gaia.get("type") == "knowledge-package":
                return pyproject
    return None


def pyproject_for_module(module_name: str) -> Path | None:
    """Return the nearest Gaia package manifest for a loaded module.

    Despite the historical name, this returns either a
    ``pyproject.toml`` (legacy layout) or a ``gaia/gaia.toml``
    (embedded layout). Callers should treat the return value as an
    opaque "Gaia package identity anchor".
    """
    if module_name in _module_pyproject_cache:
        return _module_pyproject_cache[module_name]

    module = sys.modules.get(module_name)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        _module_pyproject_cache[module_name] = None
        return None

    manifest = _find_package_manifest(Path(module_file).resolve().parent)
    _module_pyproject_cache[module_name] = manifest
    return manifest


def _load_inferred_package(manifest: Path) -> CollectedPackage | None:
    if manifest in _inferred_packages:
        return _inferred_packages[manifest]

    with open(manifest, "rb") as f:
        config = tomllib.load(f)

    if manifest.name == _EMBEDDED_MANIFEST:
        package_block = config.get("package") or {}
        project_name = package_block.get("name") or manifest.parent.parent.name
        version = package_block.get("version") or "0.0.0"
        namespace = package_block.get("namespace", "github")
    else:
        project = config.get("project", {})
        gaia = config.get("tool", {}).get("gaia", {})
        if gaia.get("type") != "knowledge-package":
            return None
        project_name = project.get("name")
        version = project.get("version")
        namespace = gaia.get("namespace", "github")

    if not isinstance(project_name, str) or not project_name:
        return None
    if not isinstance(version, str) or not version:
        return None
    if not isinstance(namespace, str) or not namespace:
        namespace = "github"

    pkg = CollectedPackage(
        _project_to_import_name(project_name),
        namespace=namespace,
        version=version,
    )
    _inferred_packages[manifest] = pkg
    return pkg


def _caller_module_name() -> str | None:
    frame = inspect.currentframe()
    if frame is None:
        return None

    try:
        frame = frame.f_back
        while frame is not None:
            module_name = frame.f_globals.get("__name__")
            if isinstance(module_name, str) and not module_name.startswith("gaia."):
                return module_name
            frame = frame.f_back
    finally:
        del frame
    return None


def infer_package_from_callstack() -> CollectedPackage | None:
    """Infer the active knowledge package from the first non-Gaia caller."""
    pkg, _ = infer_package_and_module()
    return pkg


def infer_package_and_module() -> tuple[CollectedPackage | None, str | None]:
    """Infer package and relative module name from the call stack.

    The relative module name is what shows up on
    :attr:`Knowledge._source_module` and drives the multi-file layout
    used by ``gaia author <verb> --file``. We compute it by stripping
    the *actual* runtime module-name prefix of the caller, which works
    uniformly for:

    - legacy layout: ``my_package.s3_downfolding`` ⇒
      ``s3_downfolding`` (the runtime prefix matches ``pkg.name``);
    - embedded layout: ``_gaia_pkg_<slug>_<sha>.main`` ⇒ ``main``
      (the runtime prefix is the synthetic name, which does **not**
      match ``pkg.name`` because we deliberately project the
      user-visible name onto ``pkg.name`` rather than the synthetic
      module name).
    """
    module_name = _caller_module_name()
    if not module_name:
        return None, None

    manifest = pyproject_for_module(module_name)
    if manifest is None:
        return None, None

    pkg = _load_inferred_package(manifest)
    if pkg is None:
        return None, None

    if module_name.endswith(".__init__"):
        return pkg, None
    runtime_prefix = module_name.split(".", 1)[0]
    if module_name == runtime_prefix:
        return pkg, None
    relative = module_name.removeprefix(f"{runtime_prefix}.")
    return pkg, relative


def get_inferred_package(pyproject: Path) -> CollectedPackage | None:
    """Return the cached inferred package for a pyproject path."""
    return _inferred_packages.get(pyproject.resolve())


def reset_inferred_package(pyproject: Path, *, module_name: str | None = None) -> None:
    """Clear inferred-package and module-to-pyproject caches."""
    pyproject = pyproject.resolve()
    _inferred_packages.pop(pyproject, None)
    stale = [name for name, cached in _module_pyproject_cache.items() if cached == pyproject]
    if module_name is not None:
        stale.extend(
            name
            for name in _module_pyproject_cache
            if name == module_name or name.startswith(f"{module_name}.")
        )
    for name in stale:
        cached = _module_pyproject_cache.pop(name, None)
        if cached is not None:
            _inferred_packages.pop(cached.resolve(), None)
