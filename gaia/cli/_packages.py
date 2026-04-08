"""Shared package loading utilities for Gaia CLI commands."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from packaging.requirements import InvalidRequirement, Requirement

from gaia.lang.runtime import Knowledge, Strategy
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.package import get_inferred_package, reset_inferred_package
from gaia.lang.runtime.package import _pyproject_for_module

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


MANIFEST_FILENAMES = ("exports.json", "holes.json", "bridges.json")


def _project_to_registry_name(project_name: str) -> str:
    return project_name.removesuffix("-gaia")


def _project_to_import_name(project_name: str) -> str:
    return _project_to_registry_name(project_name).replace("-", "_")


def _parse_gaia_dependencies(dependencies: list[str]) -> dict[str, str]:
    deps: dict[str, str] = {}
    for dep in dependencies:
        try:
            requirement = Requirement(dep)
        except InvalidRequirement as exc:
            raise GaiaCliError(f"Error: invalid dependency requirement '{dep}': {exc}") from exc
        if requirement.name.endswith("-gaia"):
            deps[requirement.name] = str(requirement.specifier) or "*"
    return deps


def _parse_qid(qid: str) -> tuple[str, str, str] | None:
    parts = qid.split("::", 1)
    if len(parts) != 2:
        return None
    prefix_parts = parts[0].split(":", 1)
    if len(prefix_parts) != 2:
        return None
    return prefix_parts[0], prefix_parts[1], parts[1]


def _gaia_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    gaia = (metadata or {}).get("gaia")
    return gaia if isinstance(gaia, dict) else {}


def _is_hole_knowledge(node: dict[str, Any]) -> bool:
    return _gaia_metadata(node.get("metadata")).get("role") == "hole"


def _relation_id(
    declaring_package: str,
    declaring_version: str,
    source_qid: str,
    target_hole_qid: str,
    relation_type: str,
) -> str:
    payload = (
        f"{declaring_package}|{declaring_version}|"
        f"{source_qid}|{target_hole_qid}|{relation_type}"
    )
    return f"bridge_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def _strategy_justification(strategy: dict[str, Any]) -> str | None:
    metadata = strategy.get("metadata") or {}
    reason = metadata.get("reason")
    if isinstance(reason, str) and reason:
        return reason
    steps = strategy.get("steps") or []
    reasoning = [
        step.get("reasoning", "").strip()
        for step in steps
        if isinstance(step, dict) and isinstance(step.get("reasoning"), str) and step.get("reasoning")
    ]
    if reasoning:
        return " ".join(reasoning)
    return None


def build_compiled_manifests(loaded: LoadedGaiaPackage, ir: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Build deterministic local manifests for exports, holes, and bridges."""
    package_name = _project_to_registry_name(loaded.project_name)
    import_name = loaded.import_name
    version = str(loaded.project_config["version"])
    ir_hash = ir["ir_hash"]

    dependency_spec = loaded.project_config.get("dependencies", [])
    if not isinstance(dependency_spec, list):
        raise GaiaCliError("Error: [project].dependencies must be a list if set.")
    gaia_deps = _parse_gaia_dependencies(dependency_spec)
    deps_by_import_name = {
        _project_to_import_name(name): spec for name, spec in gaia_deps.items()
    }

    knowledges = list(ir.get("knowledges", []))
    exported_knowledges = [node for node in knowledges if node.get("exported")]
    knowledge_by_id = {node["id"]: node for node in knowledges if "id" in node}
    exported_claim_ids = {
        node["id"]
        for node in exported_knowledges
        if node.get("type") == "claim" and isinstance(node.get("id"), str)
    }

    exports_manifest = {
        "package": package_name,
        "version": version,
        "ir_hash": ir_hash,
        "exports": [
            {
                "qid": node["id"],
                "label": node.get("label"),
                "type": node["type"],
                "content": node.get("content"),
                "content_hash": node.get("content_hash"),
            }
            for node in exported_knowledges
        ],
    }

    holes: list[dict[str, Any]] = []
    strategies = list(ir.get("strategies", []))
    for node in exported_knowledges:
        if node.get("type") != "claim" or not _is_hole_knowledge(node):
            continue
        required_by: list[str] = []
        for strategy in strategies:
            if node["id"] not in strategy.get("premises", []):
                continue
            conclusion = strategy.get("conclusion")
            if isinstance(conclusion, str) and conclusion in exported_claim_ids and conclusion not in required_by:
                required_by.append(conclusion)
        holes.append(
            {
                "qid": node["id"],
                "label": node.get("label"),
                "content": node.get("content"),
                "content_hash": node.get("content_hash"),
                "required_by": required_by,
            }
        )

    holes_manifest = {
        "package": package_name,
        "version": version,
        "ir_hash": ir_hash,
        "holes": holes,
    }

    bridges: list[dict[str, Any]] = []
    for strategy in strategies:
        relation = _gaia_metadata(strategy.get("metadata")).get("relation")
        if not isinstance(relation, dict) or relation.get("type") != "fills":
            continue
        premises = strategy.get("premises") or []
        if len(premises) != 1:
            raise GaiaCliError("Error: fills relations must have exactly one source premise.")
        source_qid = premises[0]
        target_hole_qid = strategy.get("conclusion")
        if not isinstance(source_qid, str) or not isinstance(target_hole_qid, str):
            raise GaiaCliError("Error: fills relations must resolve to source and target QIDs.")

        target_node = knowledge_by_id.get(target_hole_qid)
        if target_node is None or not _is_hole_knowledge(target_node):
            raise GaiaCliError(
                f"Error: fills target '{target_hole_qid}' must resolve to a hole claim."
            )

        target_qid = _parse_qid(target_hole_qid)
        source_qid_parts = _parse_qid(source_qid)
        if target_qid is None or source_qid_parts is None:
            raise GaiaCliError("Error: fills manifests require valid QID references.")

        _, target_import_name, _ = target_qid
        target_package = target_import_name.replace("_", "-")
        if target_import_name == import_name:
            if target_hole_qid not in exported_claim_ids:
                continue
            target_version_req = f"=={version}"
        else:
            target_version_req = deps_by_import_name.get(target_import_name)
            if target_version_req is None:
                raise GaiaCliError(
                    "Error: fills target "
                    f"'{target_hole_qid}' requires a Gaia dependency constraint for "
                    f"'{target_package}-gaia'."
                )

        source_import_name = source_qid_parts[1]
        bridge: dict[str, Any] = {
            "relation_id": _relation_id(
                package_name,
                version,
                source_qid,
                target_hole_qid,
                "fills",
            ),
            "relation_type": "fills",
            "source_qid": source_qid,
            "target_hole_qid": target_hole_qid,
            "target_package": target_package,
            "target_version_req": target_version_req,
            "strength": relation.get("strength", "exact"),
            "mode": relation.get("mode") or strategy.get("type"),
            "declared_by_owner_of_source": source_import_name == import_name,
        }
        justification = _strategy_justification(strategy)
        if justification:
            bridge["justification"] = justification
        bridges.append(bridge)

    bridges_manifest = {
        "package": package_name,
        "version": version,
        "ir_hash": ir_hash,
        "bridges": bridges,
    }

    return {
        "exports.json": exports_manifest,
        "holes.json": holes_manifest,
        "bridges.json": bridges_manifest,
    }


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


def _assign_labels_for_loaded_packages() -> None:
    """Assign labels for every loaded Gaia package module, including dependencies."""
    for module_name, module in list(sys.modules.items()):
        if module is None:
            continue
        pyproject = _pyproject_for_module(module_name)
        if pyproject is None:
            continue
        pkg = get_inferred_package(pyproject)
        if pkg is None:
            continue
        _assign_labels(module, pkg)


def manifest_dir_for_package(pkg_path: Path) -> Path:
    return pkg_path / ".gaia" / "manifests"


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

    _assign_labels_for_loaded_packages()

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
    from gaia.lang.compiler import CompileValidationError, compile_package

    try:
        return compile_package(loaded.package)
    except CompileValidationError as exc:
        raise GaiaCliError(f"Error: {exc}") from exc


def compile_loaded_package_artifact(loaded: LoadedGaiaPackage):
    """Compile an already loaded Gaia package to IR plus runtime mappings."""
    from gaia.lang.compiler import CompileValidationError, compile_package_artifact

    try:
        return compile_package_artifact(loaded.package)
    except CompileValidationError as exc:
        raise GaiaCliError(f"Error: {exc}") from exc


def write_compiled_artifacts(
    pkg_path: Path,
    ir: dict[str, Any],
    *,
    manifests: dict[str, dict[str, Any]] | None = None,
) -> Path:
    """Write .gaia compilation artifacts and return the output directory."""
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    (gaia_dir / "ir.json").write_text(ir_json)
    (gaia_dir / "ir_hash").write_text(ir["ir_hash"])
    if manifests is not None:
        manifest_dir = gaia_dir / "manifests"
        manifest_dir.mkdir(parents=True, exist_ok=True)
        for filename, payload in manifests.items():
            (manifest_dir / filename).write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            )
    return gaia_dir
