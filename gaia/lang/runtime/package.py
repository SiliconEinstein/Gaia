"""Gaia Lang v5 — internal declaration collector and inferred package registry."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

from gaia.lang.runtime.nodes import Knowledge, Operator, Strategy, _current_package

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


class CollectedPackage:
    """Internal collector for declarations belonging to a knowledge package."""

    def __init__(self, name: str, *, namespace: str = "reg", version: str = "0.1.0"):
        self.name = name
        self.namespace = namespace
        self.version = version
        self.knowledge: list[Knowledge] = []
        self.strategies: list[Strategy] = []
        self.operators: list[Operator] = []
        self._token = None

    def __enter__(self):
        self._token = _current_package.set(self)
        return self

    def __exit__(self, *exc):
        _current_package.reset(self._token)
        self._token = None

    def _register_knowledge(self, k: Knowledge):
        self.knowledge.append(k)

    def _register_strategy(self, s: Strategy):
        self.strategies.append(s)

    def _register_operator(self, o: Operator):
        self.operators.append(o)

    @property
    def exported(self) -> list[str]:
        return [k.label for k in self.knowledge if k.label is not None]


_inferred_packages: dict[Path, CollectedPackage] = {}
_module_pyproject_cache: dict[str, Path | None] = {}


def _project_to_import_name(project_name: str) -> str:
    return project_name.removesuffix("-gaia").replace("-", "_")


def _find_pyproject(start: Path) -> Path | None:
    for candidate in (start, *start.parents):
        pyproject = candidate / "pyproject.toml"
        if pyproject.exists():
            return pyproject
    return None


def _pyproject_for_module(module_name: str) -> Path | None:
    if module_name in _module_pyproject_cache:
        return _module_pyproject_cache[module_name]

    module = sys.modules.get(module_name)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        _module_pyproject_cache[module_name] = None
        return None

    pyproject = _find_pyproject(Path(module_file).resolve().parent)
    _module_pyproject_cache[module_name] = pyproject
    return pyproject


def _load_inferred_package(pyproject: Path) -> CollectedPackage | None:
    if pyproject in _inferred_packages:
        return _inferred_packages[pyproject]

    with open(pyproject, "rb") as f:
        config = tomllib.load(f)

    project = config.get("project", {})
    gaia = config.get("tool", {}).get("gaia", {})
    if gaia.get("type") != "knowledge-package":
        return None

    project_name = project.get("name")
    version = project.get("version")
    if not isinstance(project_name, str) or not project_name:
        return None
    if not isinstance(version, str) or not version:
        return None

    namespace = gaia.get("namespace", "reg")
    if not isinstance(namespace, str) or not namespace:
        namespace = "reg"

    pkg = CollectedPackage(
        _project_to_import_name(project_name),
        namespace=namespace,
        version=version,
    )
    _inferred_packages[pyproject] = pkg
    return pkg


def _caller_module_name() -> str | None:
    frame = inspect.currentframe()
    if frame is None:
        return None

    try:
        frame = frame.f_back
        while frame is not None:
            module_name = frame.f_globals.get("__name__")
            if isinstance(module_name, str) and not module_name.startswith("gaia.lang"):
                return module_name
            frame = frame.f_back
    finally:
        del frame
    return None


def infer_package_from_callstack() -> CollectedPackage | None:
    module_name = _caller_module_name()
    if not module_name:
        return None

    pyproject = _pyproject_for_module(module_name)
    if pyproject is None:
        return None

    return _load_inferred_package(pyproject)


def get_inferred_package(pyproject: Path) -> CollectedPackage | None:
    return _inferred_packages.get(pyproject.resolve())


def reset_inferred_package(pyproject: Path, *, module_name: str | None = None) -> None:
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
