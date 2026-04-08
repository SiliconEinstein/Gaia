"""Shared package loading utilities for Gaia CLI commands."""

from __future__ import annotations

import hashlib
import importlib
import json
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from gaia.lang.runtime import Knowledge, Strategy
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.package import _pyproject_for_module
from gaia.lang.runtime.package import get_inferred_package, reset_inferred_package

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


class GaiaCliError(RuntimeError):
    """User-facing CLI error."""


_MANIFEST_SCHEMA_VERSION = 1


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


def _assign_labels_for_loaded_modules() -> None:
    for module_name, module in list(sys.modules.items()):
        if module is None or not isinstance(module_name, str):
            continue
        pyproject = _pyproject_for_module(module_name)
        if pyproject is None:
            continue
        pkg = get_inferred_package(pyproject)
        if pkg is None:
            continue
        _assign_labels(module, pkg)


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

    _assign_labels_for_loaded_modules()

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


def _manifest_package_name(loaded: LoadedGaiaPackage) -> str:
    return loaded.project_name.removesuffix("-gaia")


def _manifest_base(loaded: LoadedGaiaPackage, *, ir_hash: str) -> dict[str, Any]:
    return {
        "manifest_schema_version": _MANIFEST_SCHEMA_VERSION,
        "package": _manifest_package_name(loaded),
        "version": loaded.project_config["version"],
        "ir_hash": ir_hash,
    }


def _canonical_json_hash(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"sha256:{hashlib.sha256(raw.encode()).hexdigest()}"


def _interface_hash(
    *,
    qid: str,
    content_hash: str,
    role: str,
    parameters: list[dict[str, Any]],
) -> str:
    return _canonical_json_hash(
        {
            "manifest_schema_version": _MANIFEST_SCHEMA_VERSION,
            "qid": qid,
            "content_hash": content_hash,
            "role": role,
            "parameters": parameters,
        }
    )


def _knowledge_manifest_entry(knowledge) -> dict[str, Any]:
    entry = {
        "qid": knowledge.id,
        "label": knowledge.label,
        "type": str(knowledge.type),
        "content": knowledge.content,
        "content_hash": knowledge.content_hash,
    }
    parameters = [parameter.model_dump(mode="json") for parameter in knowledge.parameters]
    if parameters:
        entry["parameters"] = parameters
    return entry


def build_package_manifests(loaded: LoadedGaiaPackage, compiled) -> dict[str, dict[str, Any]]:
    """Build package-level interface manifests from compiled IR plus runtime package state."""
    graph = compiled.graph
    knowledge_by_qid = {knowledge.id: knowledge for knowledge in graph.knowledges if knowledge.id}
    exported_qids = {
        knowledge.id for knowledge in graph.knowledges if knowledge.id is not None and knowledge.exported
    }
    exported_claim_qids = {
        knowledge.id
        for knowledge in graph.knowledges
        if knowledge.id is not None and knowledge.exported and str(knowledge.type) == "claim"
    }

    exports = [
        _knowledge_manifest_entry(knowledge)
        for knowledge in sorted(graph.knowledges, key=lambda item: item.id or "")
        if knowledge.exported and knowledge.id is not None
    ]

    local_knowledge_ids = {id(knowledge) for knowledge in loaded.package.knowledge}
    local_supports_by_conclusion: dict[int, list[Strategy]] = defaultdict(list)
    downstream_conclusions_by_premise: dict[int, list[Knowledge]] = defaultdict(list)
    downstream_seen: dict[int, set[int]] = defaultdict(set)

    for strategy in loaded.package.strategies:
        conclusion = strategy.conclusion
        if (
            conclusion is None
            or conclusion.type != "claim"
            or id(conclusion) not in local_knowledge_ids
        ):
            continue
        local_supports_by_conclusion[id(conclusion)].append(strategy)
        for premise in strategy.premises:
            if premise.type != "claim":
                continue
            premise_id = id(premise)
            conclusion_id = id(conclusion)
            if conclusion_id in downstream_seen[premise_id]:
                continue
            downstream_seen[premise_id].add(conclusion_id)
            downstream_conclusions_by_premise[premise_id].append(conclusion)

    public_premise_objects: dict[int, Knowledge] = {}
    visited_supported_claims: set[int] = set()

    def walk_supported_claim(claim_node: Knowledge) -> None:
        for strategy in local_supports_by_conclusion.get(id(claim_node), []):
            for premise in strategy.premises:
                if premise.type != "claim":
                    continue
                premise_id = id(premise)
                if premise_id in local_knowledge_ids and local_supports_by_conclusion.get(premise_id):
                    if premise_id in visited_supported_claims:
                        continue
                    visited_supported_claims.add(premise_id)
                    walk_supported_claim(premise)
                    continue
                public_premise_objects[premise_id] = premise

    exported_claim_roots = [
        knowledge
        for knowledge in loaded.package.knowledge
        if knowledge.type == "claim"
        and compiled.knowledge_ids_by_object.get(id(knowledge)) in exported_claim_qids
    ]
    for root in exported_claim_roots:
        root_id = id(root)
        if root_id in visited_supported_claims:
            continue
        visited_supported_claims.add(root_id)
        walk_supported_claim(root)

    premises: list[dict[str, Any]] = []
    for premise in sorted(
        public_premise_objects.values(),
        key=lambda item: compiled.knowledge_ids_by_object.get(id(item), ""),
    ):
        premise_qid = compiled.knowledge_ids_by_object.get(id(premise))
        if premise_qid is None:
            continue
        knowledge = knowledge_by_qid.get(premise_qid)
        if knowledge is None or knowledge.content_hash is None:
            continue
        role = "local_hole" if id(premise) in local_knowledge_ids else "foreign_dependency"
        queue: deque[Knowledge] = deque([premise])
        seen_claims = {id(premise)}
        required_by_set: set[str] = set()
        while queue:
            current = queue.popleft()
            for conclusion in downstream_conclusions_by_premise.get(id(current), []):
                conclusion_id = id(conclusion)
                if conclusion_id in seen_claims:
                    continue
                seen_claims.add(conclusion_id)
                conclusion_qid = compiled.knowledge_ids_by_object.get(conclusion_id)
                if conclusion_qid is None:
                    continue
                if conclusion_qid in exported_claim_qids:
                    required_by_set.add(conclusion_qid)
                    continue
                queue.append(conclusion)
        required_by = sorted(required_by_set)

        parameters = [parameter.model_dump(mode="json") for parameter in knowledge.parameters]
        entry = {
            "qid": premise_qid,
            "label": knowledge.label,
            "content": knowledge.content,
            "content_hash": knowledge.content_hash,
            "role": role,
            "interface_hash": _interface_hash(
                qid=premise_qid,
                content_hash=knowledge.content_hash,
                role=role,
                parameters=parameters,
            ),
            "exported": premise_qid in exported_qids,
            "required_by": required_by,
        }
        if parameters:
            entry["parameters"] = parameters
        premises.append(entry)

    manifests = {
        "exports.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "exports": exports,
        },
        "premises.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "premises": premises,
        },
    }
    return manifests


def write_compiled_artifacts(
    pkg_path: Path, ir: dict[str, Any], *, manifests: dict[str, dict[str, Any]] | None = None
) -> Path:
    """Write .gaia compilation artifacts and return the output directory."""
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    (gaia_dir / "ir.json").write_text(ir_json)
    (gaia_dir / "ir_hash").write_text(ir["ir_hash"])
    if manifests:
        manifests_dir = gaia_dir / "manifests"
        manifests_dir.mkdir(exist_ok=True)
        for filename, payload in manifests.items():
            rendered = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
            (manifests_dir / filename).write_text(rendered)
    return gaia_dir
