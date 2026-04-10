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

    def __init__(self, name: str, *, namespace: str = "github", version: str = "0.1.0"):
        self.name = name
        self.namespace = namespace
        self.version = version
        self.knowledge: list[Knowledge] = []
        self.strategies: list[Strategy] = []
        self.operators: list[Operator] = []
        self._token = None
        self._module_counters: dict[str | None, int] = {}
        self._module_order: list[str] = []
        self._exported_labels: set[str] = set()

    def __enter__(self):
        self._token = _current_package.set(self)
        return self

    def __exit__(self, *exc):
        _current_package.reset(self._token)
        self._token = None

    def _register_knowledge(self, k: Knowledge):
        self.knowledge.append(k)
        module = k._source_module
        if module not in self._module_counters:
            if module is not None:
                self._module_order.append(module)
            self._module_counters[module] = 0
        k._declaration_index = self._module_counters[module]
        self._module_counters[module] += 1

    def _register_strategy(self, s: Strategy):
        self.strategies.append(s)

    def _register_operator(self, o: Operator):
        self.operators.append(o)

    @property
    def exported(self) -> list[str]:
        if self._exported_labels:
            return [k.label for k in self.knowledge if k.label in self._exported_labels]
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


def pyproject_for_module(module_name: str) -> Path | None:
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

    namespace = gaia.get("namespace", "github")
    if not isinstance(namespace, str) or not namespace:
        namespace = "github"

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
    pkg, _ = infer_package_and_module()
    return pkg


def infer_package_and_module() -> tuple[CollectedPackage | None, str | None]:
    """Infer package and relative module name from the call stack."""
    module_name = _caller_module_name()
    if not module_name:
        return None, None

    pyproject = pyproject_for_module(module_name)
    if pyproject is None:
        return None, None

    pkg = _load_inferred_package(pyproject)
    if pkg is None:
        return None, None

    # Compute relative module name: strip package prefix
    # e.g. "my_package.s3_downfolding" → "s3_downfolding"
    # "my_package" or "my_package.__init__" → None (root module)
    if module_name == pkg.name or module_name.endswith(".__init__"):
        return pkg, None
    relative = module_name.removeprefix(f"{pkg.name}.")
    return pkg, relative


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
