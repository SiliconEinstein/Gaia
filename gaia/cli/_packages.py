"""Shared package loading utilities for Gaia CLI commands."""

from __future__ import annotations

import hashlib
import importlib
import json
import math
import subprocess
import sys
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from types import ModuleType
from typing import Any

from gaia.lang.runtime import Knowledge, Strategy
from gaia.lang.runtime.package import CollectedPackage
from gaia.lang.runtime.package import pyproject_for_module
from gaia.lang.runtime.package import get_inferred_package, reset_inferred_package
from gaia.ir.parameterization import CROMWELL_EPS
from packaging.requirements import InvalidRequirement, Requirement

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
        pyproject = pyproject_for_module(module_name)
        if pyproject is None:
            continue
        pkg = get_inferred_package(pyproject)
        if pkg is None:
            continue
        _assign_labels(module, pkg)


def ensure_package_env(pkg_path: Path) -> None:
    """Run ``uv sync`` in *pkg_path* so dependencies are importable.

    Skipped when the directory has no ``pyproject.toml`` or when ``uv``
    is not on ``$PATH``.  Failures are non-fatal (a warning is printed)
    because the user may manage dependencies another way.
    """
    if not (pkg_path / "pyproject.toml").exists():
        return
    import shutil

    if shutil.which("uv") is None:
        return
    result = subprocess.run(
        ["uv", "sync", "--quiet"],
        cwd=pkg_path,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        import logging

        logging.getLogger(__name__).debug("uv sync in %s: %s", pkg_path, result.stderr.strip())


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
    from gaia.lang.refs import ReferenceError, load_references

    try:
        references = load_references(loaded.pkg_path / "references.json")
        return compile_package_artifact(loaded.package, references=references)
    except ReferenceError as e:
        raise GaiaCliError(str(e)) from e


def _knowledge_display_name(knowledge: Knowledge) -> str:
    return knowledge.label or knowledge.content or repr(knowledge)


def _validate_prior_value(value: Any, *, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise GaiaCliError(
            f"Error: PRIORS[{label!r}] prior must be a number, got {type(value).__name__}."
        )
    prior = float(value)
    if not math.isfinite(prior):
        raise GaiaCliError(f"Error: PRIORS[{label!r}] prior must be finite, got {prior!r}.")
    if prior < CROMWELL_EPS or prior > 1 - CROMWELL_EPS:
        raise GaiaCliError(
            f"Error: PRIORS[{label!r}] prior {prior} outside Cromwell bounds "
            f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]."
        )
    return prior


def apply_package_priors(loaded: LoadedGaiaPackage) -> None:
    """Discover priors.py and inject prior+justification into Knowledge metadata.

    The priors.py module must export a ``PRIORS`` dict mapping Knowledge objects
    to ``(prior_value, justification_string)`` tuples.  Each entry is injected
    into the Knowledge object's ``.metadata`` dict as ``prior`` and
    ``prior_justification`` before compilation, so lowering can read them from
    ``metadata["prior"]``.

    No-op when the package has no ``priors.py``.
    """
    priors_module_name = f"{loaded.import_name}.priors"
    priors_path = loaded.source_root / loaded.import_name / "priors.py"
    if not priors_path.exists():
        return

    existing_knowledge_ids = {id(k) for k in loaded.package.knowledge}

    try:
        module = _import_fresh(priors_module_name)
    except Exception as exc:
        raise GaiaCliError(f"Error importing priors.py: {exc}") from exc

    new_knowledge = [k for k in loaded.package.knowledge if id(k) not in existing_knowledge_ids]
    if new_knowledge:
        names = ", ".join(_knowledge_display_name(k) for k in new_knowledge[:5])
        suffix = " ..." if len(new_knowledge) > 5 else ""
        raise GaiaCliError(
            "Error: priors.py must not declare new Knowledge objects; it may only "
            "reference claims/settings/questions already declared by the package. "
            f"New declarations: {names}{suffix}."
        )

    priors_dict = getattr(module, "PRIORS", None)
    if priors_dict is None:
        raise GaiaCliError(
            "Error: priors.py must export PRIORS = {Knowledge: (prior, justification), ...}."
        )
    if not isinstance(priors_dict, dict):
        raise GaiaCliError("Error: priors.py PRIORS must be a dict.")

    for key, value in priors_dict.items():
        if not isinstance(key, Knowledge):
            raise GaiaCliError(
                f"Error: PRIORS key {key!r} is not a Knowledge object. "
                "Keys must be claim/setting/question objects from the package."
            )
        if id(key) not in existing_knowledge_ids:
            raise GaiaCliError(
                f"Error: PRIORS key {_knowledge_display_name(key)!r} is not an "
                "already-declared Knowledge object from this package."
            )
        if not isinstance(value, tuple) or len(value) != 2:
            raise GaiaCliError(
                f"Error: PRIORS[{key.label or key.content!r}] must be a (prior, justification) tuple, "
                f"got {type(value).__name__}."
            )
        prior_val, justification = value
        prior = _validate_prior_value(prior_val, label=_knowledge_display_name(key))
        if not isinstance(justification, str):
            raise GaiaCliError(
                f"Error: PRIORS[{key.label or key.content!r}] justification must be a string, "
                f"got {type(justification).__name__}."
            )
        key.metadata["prior"] = prior
        key.metadata["prior_justification"] = justification


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


def render_manifest_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


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


def _parse_gaia_dependencies(
    project_config: dict[str, Any],
) -> tuple[dict[str, str], dict[str, str]]:
    """Parse [project].dependencies and return (specs, import_to_dist).

    Returns:
        specs: dict mapping distribution name → version specifier string
        import_to_dist: dict mapping inferred import name → distribution name
    """
    dependencies = project_config.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise GaiaCliError("Error: [project].dependencies must be a list if set.")
    specs: dict[str, str] = {}
    import_to_dist: dict[str, str] = {}
    for raw in dependencies:
        if not isinstance(raw, str):
            raise GaiaCliError("Error: [project].dependencies entries must be strings.")
        try:
            requirement = Requirement(raw)
        except InvalidRequirement as exc:
            raise GaiaCliError(f"Error: invalid dependency requirement '{raw}': {exc}") from exc
        if requirement.name.endswith("-gaia"):
            dist_name = requirement.name
            specs[dist_name] = str(requirement.specifier) or "*"
            import_name = dist_name.removesuffix("-gaia").replace("-", "_")
            import_to_dist[import_name] = dist_name
    return specs, import_to_dist


def _import_module(import_name: str) -> ModuleType:
    module = sys.modules.get(import_name)
    if module is not None:
        return module
    return importlib.import_module(import_name)


def _load_json_file(path: Path, *, description: str) -> dict[str, Any]:
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise GaiaCliError(f"Error: {description} is not valid JSON: {exc}") from exc


def _locate_dependency_manifest_root(import_name: str) -> Path | None:
    pyproject = pyproject_for_module(import_name)
    if pyproject is not None:
        return pyproject.parent

    module = _import_module(import_name)
    module_file = getattr(module, "__file__", None)
    if not module_file:
        return None
    module_path = Path(module_file).resolve()
    package_dir = module_path.parent
    candidates = [package_dir, package_dir.parent, package_dir.parent.parent]
    for candidate in candidates:
        if (candidate / ".gaia" / "manifests" / "premises.json").exists():
            return candidate
    return None


def _validate_dependency_manifest_freshness(
    import_name: str, root: Path, stored_ir_hash: str
) -> None:
    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return
    loaded = load_gaia_package(root)
    compiled = compile_loaded_package_artifact(loaded)
    current_ir_hash = compiled.graph.ir_hash or ""
    if current_ir_hash != stored_ir_hash:
        raise GaiaCliError(
            f"Error: dependency '{import_name}' has stale .gaia manifests; "
            f"run `gaia compile` in {root}."
        )


def _resolve_dependency_premises_manifest(import_name: str) -> tuple[Path, dict[str, Any]]:
    root = _locate_dependency_manifest_root(import_name)
    if root is None:
        raise GaiaCliError(
            f"Error: could not locate Gaia package root for dependency '{import_name}'."
        )
    premises_path = root / ".gaia" / "manifests" / "premises.json"
    if not premises_path.exists():
        raise GaiaCliError(
            f"Error: dependency '{import_name}' is missing .gaia/manifests/premises.json. "
            f"This file is generated by `gaia compile` (gaia-lang >= 0.2.5). "
            f"If the dependency was compiled with an older version, upgrade gaia-lang "
            f"and recompile: cd {root} && uv add 'gaia-lang>=0.3.0' && gaia compile"
        )
    premises_manifest = _load_json_file(
        premises_path,
        description=f"{import_name} dependency manifest {premises_path}",
    )
    stored_ir_hash = premises_manifest.get("ir_hash")
    if not isinstance(stored_ir_hash, str) or not stored_ir_hash:
        raise GaiaCliError(f"Error: dependency manifest {premises_path} is missing ir_hash.")
    _validate_dependency_manifest_freshness(import_name, root, stored_ir_hash)
    return root, premises_manifest


def _reason_to_text(reason: Any) -> str | None:
    if isinstance(reason, str):
        return reason or None
    if not isinstance(reason, list):
        return None
    parts: list[str] = []
    for entry in reason:
        if isinstance(entry, str):
            if entry:
                parts.append(entry)
            continue
        text = getattr(entry, "reason", None)
        if isinstance(text, str) and text:
            parts.append(text)
    return "\n\n".join(parts) or None


def _relation_id(
    *,
    declaring_package: str,
    declaring_version: str,
    source_qid: str,
    source_content_hash: str,
    target_qid: str,
    target_interface_hash: str,
    relation_type: str,
) -> str:
    raw = (
        f"{declaring_package}|{declaring_version}|{source_qid}|{source_content_hash}|"
        f"{target_qid}|{target_interface_hash}|{relation_type}"
    )
    return f"bridge_{hashlib.sha256(raw.encode()).hexdigest()[:16]}"


def _resolve_fills_relations(loaded: LoadedGaiaPackage, compiled) -> list[dict[str, Any]]:
    dependency_specs, import_to_dist = _parse_gaia_dependencies(loaded.project_config)
    local_package = loaded.package
    knowledge_by_qid = {
        knowledge.id: knowledge for knowledge in compiled.graph.knowledges if knowledge.id
    }
    dependency_manifest_cache: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []
    seen_relation_keys: set[tuple[str, str, str]] = set()

    for strategy in loaded.package.strategies:
        relation = strategy.metadata.get("gaia", {}).get("relation", {})
        if relation.get("type") != "fills":
            continue
        if len(strategy.premises) != 1 or strategy.conclusion is None:
            raise GaiaCliError(
                "Error: fills() strategies must have exactly one source and one target."
            )

        source = strategy.premises[0]
        target = strategy.conclusion
        source_owner = source._package
        target_owner = target._package

        if target_owner is None or target_owner == local_package:
            raise GaiaCliError(
                "Error: fills() target must be a foreign claim resolved from a dependency package."
            )

        if source_owner is not None and source_owner != local_package:
            source_dist = import_to_dist.get(source_owner.name)
            if source_dist is None or source_dist not in dependency_specs:
                raise GaiaCliError(
                    f"Error: fills() source dependency '{source_owner.name}' is not declared in "
                    "[project].dependencies (no matching *-gaia distribution found)."
                )

        target_dist = import_to_dist.get(target_owner.name)
        if target_dist is None or target_dist not in dependency_specs:
            raise GaiaCliError(
                f"Error: fills() target dependency '{target_owner.name}' is not declared in "
                "[project].dependencies (no matching *-gaia distribution found)."
            )

        premises_manifest = dependency_manifest_cache.get(target_owner.name)
        if premises_manifest is None:
            _, premises_manifest = _resolve_dependency_premises_manifest(target_owner.name)
            dependency_manifest_cache[target_owner.name] = premises_manifest
        premises = premises_manifest.get("premises", [])
        if not isinstance(premises, list):
            raise GaiaCliError("Error: dependency premises manifest must contain a premises list.")

        source_qid = compiled.knowledge_ids_by_object.get(id(source))
        target_qid = compiled.knowledge_ids_by_object.get(id(target))
        if source_qid is None or target_qid is None:
            raise GaiaCliError("Error: could not resolve fills() source/target QID during compile.")

        source_knowledge = knowledge_by_qid.get(source_qid)
        if source_knowledge is None or source_knowledge.content_hash is None:
            raise GaiaCliError(f"Error: could not resolve source content hash for '{source_qid}'.")

        entry = next(
            (
                premise
                for premise in premises
                if isinstance(premise, dict) and premise.get("qid") == target_qid
            ),
            None,
        )
        if entry is None:
            raise GaiaCliError(
                f"Error: fills() target '{target_qid}' is not a public premise in dependency "
                f"'{target_owner.name}'."
            )
        if entry.get("role") != "local_hole":
            raise GaiaCliError(
                f"Error: fills() target '{target_qid}' must resolve to a dependency local_hole, "
                f"found role={entry.get('role')!r}."
            )

        target_interface_hash = entry.get("interface_hash")
        if not isinstance(target_interface_hash, str) or not target_interface_hash:
            raise GaiaCliError(
                f"Error: dependency premise '{target_qid}' is missing interface_hash."
            )
        target_resolved_version = premises_manifest.get("version")
        if not isinstance(target_resolved_version, str) or not target_resolved_version:
            raise GaiaCliError(
                f"Error: dependency premises manifest for '{target_owner.name}' is missing version."
            )
        target_package = premises_manifest.get("package")
        if not isinstance(target_package, str) or not target_package:
            raise GaiaCliError(
                f"Error: dependency premises manifest for '{target_owner.name}' is missing package."
            )

        relation_key = (source_qid, target_qid, target_interface_hash)
        if relation_key in seen_relation_keys:
            raise GaiaCliError(
                f"Error: duplicate fills() relation for source '{source_qid}' and target "
                f"'{target_qid}' on interface '{target_interface_hash}'."
            )
        seen_relation_keys.add(relation_key)

        relation_type = str(relation.get("type"))
        justification = _reason_to_text(strategy.reason)
        relation_record = {
            "relation_id": _relation_id(
                declaring_package=_manifest_package_name(loaded),
                declaring_version=loaded.project_config["version"],
                source_qid=source_qid,
                source_content_hash=source_knowledge.content_hash,
                target_qid=target_qid,
                target_interface_hash=target_interface_hash,
                relation_type=relation_type,
            ),
            "relation_type": relation_type,
            "source_qid": source_qid,
            "source_content_hash": source_knowledge.content_hash,
            "target_qid": target_qid,
            "target_package": target_package,
            "target_dependency_req": dependency_specs[target_dist],
            "target_resolved_version": target_resolved_version,
            "target_role": entry["role"],
            "target_interface_hash": target_interface_hash,
            "strength": relation.get("strength"),
            "mode": relation.get("mode"),
            "declared_by_owner_of_source": source_owner == local_package,
        }
        if justification:
            relation_record["justification"] = justification
        relations.append(relation_record)

    return sorted(relations, key=lambda item: item["relation_id"])


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


def validate_fills_relations(loaded: LoadedGaiaPackage, compiled) -> None:
    """Validate fills() relations without building full manifests.

    Raises GaiaCliError if any fills() strategy has an invalid source,
    target, or dependency configuration. Use this for ``gaia check``
    where manifests are not needed — only validation matters.
    """
    _resolve_fills_relations(loaded, compiled)


def build_package_manifests(loaded: LoadedGaiaPackage, compiled) -> dict[str, dict[str, Any]]:
    """Build package-level interface manifests from compiled IR plus runtime package state.

    Emits four sibling manifest files under ``.gaia/manifests/``:

    - ``exports.json`` — every knowledge node in the package flagged ``exported``.
      These are the package's public interface claims that downstream packages
      may depend on.
    - ``premises.json`` — every **leaf** claim (a claim with no supporting
      strategy in the local package) that feeds into an exported conclusion.
      Each entry carries a ``role`` field:

        * ``local_hole`` — the leaf claim is declared in the **current** package
          but has no derivation chain. These are the package's primary evidence
          and abduction alternatives — i.e. the propositions the author accepts
          as given inputs to the reasoning graph.
        * ``foreign_dependency`` — the leaf claim originates in an upstream
          ``*-gaia`` dependency and is consumed by a local strategy via the
          dependency's ``exports.json``.

    - ``holes.json`` — the subset of ``premises.json`` entries whose role is
      ``local_hole``. Despite the name, a "hole" here does **not** mean an
      unresolved cross-package reference (foreign dependencies already have
      their own resolution path via the dep's exports). A ``local_hole`` is a
      local leaf claim that a *downstream* package could optionally "fill" with
      more specific evidence via the ``fills`` relation — but the current
      package is perfectly valid with its leaves unfilled.
    - ``bridges.json`` — ``fills`` relations declared in the local package that
      point at hole qids in an upstream dependency's manifest. Empty for
      packages with no upstream deps.

    Concrete example from the ``watson-rfdiffusion-2023-gaia`` package:

    - 7 exports (the paper's exported conclusions, e.g. ``binder_success_rate``)
    - 32 local holes: 20 primary observations (e.g. ``denoising_process``,
      ``binder_specificity``) + 12 abduction alternatives
      (``alt_nonspecific_binding_p53_mdm2``, etc.)
    - 0 foreign dependencies (watson has no upstream ``*-gaia`` deps)
    - 0 bridges (watson doesn't fill any upstream holes)

    All 32 holes are **declared claims** in the local package — they appear in
    ``ir.json`` as regular knowledge nodes with ``exported=false`` and no
    supporting strategy. They are reported as "holes" because the `holes.json`
    manifest is indexing *local leaves that downstream packages could optionally
    refine*, not *unresolved references*.

    See ``docs/specs/2026-04-08-gaia-lang-hole-fills-design.md`` §3.2 for the
    full rationale on why "hole" is a release-scoped interface role rather than
    a source primitive.
    """
    fills_relations = _resolve_fills_relations(loaded, compiled)
    graph = compiled.graph
    knowledge_by_qid = {knowledge.id: knowledge for knowledge in graph.knowledges if knowledge.id}
    exported_qids = {
        knowledge.id
        for knowledge in graph.knowledges
        if knowledge.id is not None and knowledge.exported
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
                if premise_id in local_knowledge_ids and local_supports_by_conclusion.get(
                    premise_id
                ):
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

    holes = [
        {key: value for key, value in premise.items() if key != "role" and key != "exported"}
        for premise in premises
        if premise["role"] == "local_hole"
    ]

    manifests = {
        "exports.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "exports": exports,
        },
        "premises.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "premises": premises,
        },
        "holes.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "holes": holes,
        },
        "bridges.json": {
            **_manifest_base(loaded, ir_hash=graph.ir_hash or ""),
            "bridges": fills_relations,
        },
    }
    return manifests


def collect_foreign_node_priors(
    graph,
    pkg_path: Path,
) -> dict[str, float]:
    """Collect upstream beliefs for foreign knowledge nodes.

    Scans ``.gaia/dep_beliefs/*.json`` for belief manifests downloaded by
    ``gaia add``.  For each foreign knowledge node in *graph* (i.e. a node
    whose QID does **not** start with the local ``{namespace}:{package}::``
    prefix), if the upstream manifest contains a matching ``knowledge_id``,
    the upstream belief is included in the returned dict.

    The returned dict is suitable for passing as ``node_priors`` to
    ``lower_local_graph()``, which gives these values highest explicit-
    override priority (above ``metadata["prior"]``).
    """
    dep_beliefs_dir = pkg_path / ".gaia" / "dep_beliefs"
    if not dep_beliefs_dir.is_dir():
        return {}

    # Build upstream beliefs mapping from all dep_beliefs files
    upstream_beliefs: dict[str, float] = {}
    for beliefs_file in sorted(dep_beliefs_dir.glob("*.json")):
        try:
            data = json.loads(beliefs_file.read_text())
        except (OSError, json.JSONDecodeError):
            continue
        beliefs_list = data.get("beliefs")
        if not isinstance(beliefs_list, list):
            continue
        for entry in beliefs_list:
            if not isinstance(entry, dict):
                continue
            kid = entry.get("knowledge_id")
            belief = entry.get("belief")
            if isinstance(kid, str) and isinstance(belief, (int, float)):
                upstream_beliefs[kid] = float(belief)

    if not upstream_beliefs:
        return {}

    # Determine local prefix to identify foreign nodes
    local_prefix = f"{graph.namespace}:{graph.package_name}::"

    foreign_priors: dict[str, float] = {}
    for knowledge in graph.knowledges:
        kid = knowledge.id
        if kid is None or kid.startswith(local_prefix):
            continue
        if kid in upstream_beliefs:
            foreign_priors[kid] = upstream_beliefs[kid]

    return foreign_priors


def collect_strategy_conditional_params(compiled) -> dict[str, list[float]]:
    """Collect v6 strategy CPT records keyed by strategy id for BP lowering."""
    return {
        record.strategy_id: list(record.conditional_probabilities)
        for record in compiled.strategy_param_records
        if record.strategy_id
    }


@dataclass
class DependencyGraph:
    """A dependency's compiled IR loaded from disk."""

    import_name: str
    dist_name: str
    root: Path
    graph: Any  # LocalCanonicalGraph (imported lazily to avoid circular deps)


def load_dependency_compiled_graphs(
    project_config: dict[str, Any],
    *,
    depth: int = 1,
    _seen: set[str] | None = None,
) -> list[DependencyGraph]:
    """Discover direct ``-gaia`` dependencies and load their compiled IR.

    Parameters
    ----------
    project_config:
        The ``[project]`` section of the local ``pyproject.toml``.
    depth:
        How many levels of transitive dependencies to load.
        1 = direct deps only, 2+ = recurse, -1 = unlimited.
    _seen:
        Internal dedup set (QID prefixes already loaded). Callers should
        not pass this.

    Returns
    -------
    Flat list of :class:`DependencyGraph` for all discovered dependencies
    (deduplicated by ``namespace:package_name``).
    """
    from gaia.ir.graphs import LocalCanonicalGraph

    if _seen is None:
        _seen = set()

    specs, import_to_dist = _parse_gaia_dependencies(project_config)
    result: list[DependencyGraph] = []

    for import_name, dist_name in sorted(import_to_dist.items()):
        root = _locate_dependency_manifest_root(import_name)
        if root is None:
            raise GaiaCliError(
                f"Could not locate Gaia package root for dependency '{import_name}'. "
                f"Is '{dist_name}' installed?"
            )
        ir_path = root / ".gaia" / "ir.json"
        if not ir_path.exists():
            raise GaiaCliError(
                f"Dependency '{import_name}' is missing .gaia/ir.json. "
                f"Run 'gaia compile' in {root}."
            )
        ir_data = _load_json_file(ir_path, description=f"{import_name} .gaia/ir.json")
        graph = LocalCanonicalGraph.model_validate(ir_data)

        # Dedup by namespace:package_name
        qid_prefix = f"{graph.namespace}:{graph.package_name}"
        if qid_prefix in _seen:
            continue
        _seen.add(qid_prefix)

        result.append(
            DependencyGraph(
                import_name=import_name,
                dist_name=dist_name,
                root=root,
                graph=graph,
            )
        )

        # Recurse into transitive deps if requested
        if depth > 1 or depth == -1:
            dep_pyproject = root / "pyproject.toml"
            if dep_pyproject.exists():
                try:
                    dep_config = tomllib.loads(dep_pyproject.read_text())
                except Exception:
                    continue
                dep_project = dep_config.get("project", {})
                next_depth = depth - 1 if depth > 1 else -1
                transitive = load_dependency_compiled_graphs(
                    dep_project, depth=next_depth, _seen=_seen
                )
                result.extend(transitive)

    return result


def gaia_lang_version() -> str:
    """Return the installed gaia-lang version, or 'unknown' for dev checkouts.

    Used by compile (to stamp `.gaia/compile_metadata.json`) and by tests. We
    deliberately return a string sentinel instead of raising so that running
    `gaia compile` inside an un-built editable checkout still produces a valid
    metadata file — downstream consumers can detect 'unknown' and decide.
    """
    try:
        return _pkg_version("gaia-lang")
    except PackageNotFoundError:
        return "unknown"


def _utc_now_iso() -> str:
    """UTC timestamp in ISO-8601 with Z suffix and second precision."""
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _render_compile_metadata(ir_hash: str) -> str:
    """Build the `.gaia/compile_metadata.json` payload.

    This file is the canonical provenance anchor for a compiled IR: it records
    which `gaia-lang` version produced the IR, pinned to the IR hash the
    metadata file sits next to. `gaia infer` copies the version into its
    output artifacts so beliefs can be correlated back to the compile
    environment, and `gaia register` reads this file to populate
    `Versions.toml`'s `gaia_lang_version` field without depending on the live
    process environment (which may have been upgraded between compile and
    register).
    """
    payload = {
        "gaia_lang_version": gaia_lang_version(),
        "compiled_at": _utc_now_iso(),
        "ir_hash": ir_hash,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_compiled_artifacts(
    pkg_path: Path, ir: dict[str, Any], *, manifests: dict[str, dict[str, Any]] | None = None
) -> Path:
    """Write .gaia compilation artifacts and return the output directory."""
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    (gaia_dir / "ir.json").write_text(ir_json)
    (gaia_dir / "ir_hash").write_text(ir["ir_hash"])
    (gaia_dir / "compile_metadata.json").write_text(_render_compile_metadata(ir["ir_hash"]))
    if manifests:
        manifests_dir = gaia_dir / "manifests"
        manifests_dir.mkdir(exist_ok=True)
        for filename, payload in manifests.items():
            (manifests_dir / filename).write_text(render_manifest_json(payload))
    return gaia_dir
