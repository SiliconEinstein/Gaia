"""Shared package loading utilities for Gaia CLI commands."""

from __future__ import annotations

import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from gaia.lang.runtime import Knowledge, Strategy
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.package import get_inferred_package, reset_inferred_package

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


class GaiaCliError(RuntimeError):
    """User-facing CLI error."""


@dataclass
class LoadedGaiaPackage:
    pkg_path: Path
    config: dict[str, Any]
    project_config: dict[str, Any]
    gaia_config: dict[str, Any]
    project_name: str
    import_name: str
    source_root: Path
    module: ModuleType
    package: CollectedPackage


def _import_fresh(import_name: str) -> ModuleType:
    stale_modules = [
        name for name in sys.modules if name == import_name or name.startswith(f"{import_name}.")
    ]
    for name in stale_modules:
        sys.modules.pop(name, None)
    importlib.invalidate_caches()
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        return importlib.import_module(import_name)
    finally:
        sys.dont_write_bytecode = previous


def _assign_labels(module: ModuleType, pkg: CollectedPackage) -> None:
    local_knowledge_ids = {id(k) for k in pkg.knowledge}
    local_strategy_ids = {id(s) for s in pkg.strategies}
    all_names = [name for name in dir(module) if not name.startswith("_")]
    for attr in all_names:
        obj = getattr(module, attr, None)
        if isinstance(obj, Knowledge) and id(obj) in local_knowledge_ids and obj.label is None:
            obj.label = attr
        if isinstance(obj, Strategy) and id(obj) in local_strategy_ids and obj.label is None:
            obj.label = attr


def load_gaia_package(path: str | Path = ".") -> LoadedGaiaPackage:
    """Load a Gaia knowledge package from a local directory."""
    pkg_path = Path(path).resolve()
    pyproject = pkg_path / "pyproject.toml"
    if not pyproject.exists():
        raise GaiaCliError("Error: no pyproject.toml found.")

    with open(pyproject, "rb") as f:
        config = tomllib.load(f)

    project_config = config.get("project", {})
    gaia_config = config.get("tool", {}).get("gaia", {})

    if gaia_config.get("type") != "knowledge-package":
        raise GaiaCliError(
            "Error: not a Gaia knowledge package ([tool.gaia].type != 'knowledge-package')."
        )

    project_name = project_config.get("name")
    version = project_config.get("version")
    if not isinstance(project_name, str) or not project_name:
        raise GaiaCliError("Error: [project].name is required.")
    if not isinstance(version, str) or not version:
        raise GaiaCliError("Error: [project].version is required.")

    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    reset_inferred_package(pyproject, module_name=import_name)
    package_roots = [pkg_path, pkg_path / "src"]
    source_root = next((root for root in package_roots if (root / import_name).exists()), None)
    if source_root is None:
        raise GaiaCliError(f"Error: package source directory '{import_name}/' not found.")

    source_root_str = str(source_root)
    if source_root_str not in sys.path:
        sys.path.insert(0, source_root_str)

    try:
        module = _import_fresh(import_name)
    except Exception as exc:
        raise GaiaCliError(f"Error importing package: {exc}") from exc

    pkg = get_inferred_package(pyproject)
    if pkg is None:
        raise GaiaCliError(
            "Error: no Gaia declarations found. Declare Knowledge/Strategy/Operator objects "
            "directly in the module and export the public surface via __all__ when needed."
        )

    _assign_labels(module, pkg)

    # Record exported labels from __all__ for the compiler
    export_names = getattr(module, "__all__", None)
    if isinstance(export_names, list) and all(isinstance(n, str) for n in export_names):
        pkg._exported_labels = set(export_names)

    # Extract module docstrings as titles
    module_titles: dict[str, str] = {}
    for mod_name in pkg._module_order:
        full_name = f"{import_name}.{mod_name}"
        sub = sys.modules.get(full_name)
        if sub is not None:
            doc = getattr(sub, "__doc__", None)
            if isinstance(doc, str) and doc.strip():
                # Use first line of docstring as title
                module_titles[mod_name] = doc.strip().split("\n")[0].strip()
    if module_titles:
        pkg._module_titles = module_titles

    pkg.name = import_name
    pkg.version = version
    if "namespace" in gaia_config:
        pkg.namespace = gaia_config["namespace"]

    return LoadedGaiaPackage(
        pkg_path=pkg_path,
        config=config,
        project_config=project_config,
        gaia_config=gaia_config,
        project_name=project_name,
        import_name=import_name,
        source_root=source_root,
        module=module,
        package=pkg,
    )


def compile_loaded_package(loaded: LoadedGaiaPackage) -> dict[str, Any]:
    """Compile an already loaded Gaia package to IR JSON."""
    from gaia.lang.compiler import compile_package

    return compile_package(loaded.package)


def compile_loaded_package_artifact(loaded: LoadedGaiaPackage):
    """Compile an already loaded Gaia package to IR plus runtime mappings."""
    from gaia.lang.compiler import compile_package_artifact

    return compile_package_artifact(loaded.package)


def write_compiled_artifacts(pkg_path: Path, ir: dict[str, Any]) -> Path:
    """Write .gaia compilation artifacts and return the output directory."""
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    (gaia_dir / "ir.json").write_text(ir_json)
    (gaia_dir / "ir_hash").write_text(ir["ir_hash"])
    return gaia_dir
