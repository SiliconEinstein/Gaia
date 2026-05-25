"""Engine-side package loading + compilation surface.

Public facade `gaia.engine.packaging`: loading Gaia user packages from disk,
compiling them into IR artifacts, priors application, and dependency-graph
loading.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import subprocess
import sys
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _pkg_version
from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Any, cast
from urllib.parse import unquote, urlparse

from packaging.requirements import InvalidRequirement, Requirement

from gaia.engine.ir.parameterization import (
    ResolutionPolicy,
    default_resolution_policy,
)
from gaia.engine.lang.compiler import CompiledPackage
from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata
from gaia.engine.lang.runtime import Knowledge, Strategy
from gaia.engine.lang.runtime.package import (
    CollectedPackage,
    get_inferred_package,
    pyproject_for_module,
    reset_inferred_package,
)

if TYPE_CHECKING:
    from gaia.engine.ir.graphs import LocalCanonicalGraph
    from gaia.engine.ir.knowledge import Knowledge as IrKnowledge

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


__all__ = [
    "CompiledPackage",
    "GaiaPackagingError",
    "LoadedGaiaPackage",
    "apply_package_priors",
    "collect_foreign_node_priors",
    "compile_loaded_package_artifact",
    "ensure_package_env",
    "load_dependency_compiled_graphs",
    "load_gaia_package",
    "write_text_atomic",
]


class GaiaPackagingError(RuntimeError):
    """Engine packaging error surface (raised by load / compile / priors paths)."""


_MANIFEST_SCHEMA_VERSION = 1


@dataclass
class LoadedGaiaPackage:
    """In-memory result of ``load_gaia_package``.

    Bundles pyproject metadata, the imported user module, and the
    collected runtime DSL objects (Knowledge / Strategy / Operator).
    """

    pkg_path: Path
    config: dict[str, Any]
    project_config: dict[str, Any]
    gaia_config: dict[str, Any]
    project_name: str
    import_name: str
    source_root: Path
    module: ModuleType
    package: CollectedPackage


@dataclass
class _FillsContext:
    loaded: LoadedGaiaPackage
    compiled: CompiledPackage
    dependency_specs: dict[str, str]
    import_to_dist: dict[str, str]
    knowledge_by_qid: dict[str, IrKnowledge]
    manifest_cache: dict[str, dict[str, Any]]
    seen_relation_keys: set[tuple[str, str, str]]


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


def _source_module_for_loaded_module(module_name: str, pkg: CollectedPackage) -> str | None:
    if module_name == pkg.name or module_name.endswith(".__init__"):
        return None
    return module_name.removeprefix(f"{pkg.name}.")


def _is_assignable_name(name: str) -> bool:
    return not (name.startswith("__") and name.endswith("__"))


def _assign_labels(module: ModuleType, pkg: CollectedPackage, source_module: str | None) -> None:
    local_knowledge_ids = {id(k) for k in pkg.knowledge}
    local_strategy_ids = {id(s) for s in pkg.strategies}
    for attr, obj in vars(module).items():
        if not _is_assignable_name(attr):
            continue
        if (
            isinstance(obj, Knowledge)
            and id(obj) in local_knowledge_ids
            and obj.label is None
            and getattr(obj, "_source_module", None) == source_module
        ):
            obj.label = attr
        if (
            isinstance(obj, Strategy)
            and id(obj) in local_strategy_ids
            and obj.label is None
            and getattr(obj, "_source_module", None) == source_module
        ):
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
        source_module = _source_module_for_loaded_module(module_name, pkg)
        _assign_labels(module, pkg, source_module)


def _is_auxiliary_source_module(parts: tuple[str, ...]) -> bool:
    if "reviews" in parts:
        return True
    return len(parts) == 1 and parts[0] in {"priors", "review"}


def _source_module_name(import_name: str, package_dir: Path, path: Path) -> str | None:
    relative = path.relative_to(package_dir)
    if relative.name == "__init__.py":
        if relative.parent == Path("."):
            return None
        parts = relative.parent.parts
    else:
        parts = relative.with_suffix("").parts
    if _is_auxiliary_source_module(parts):
        return None
    return f"{import_name}.{'.'.join(parts)}"


def _import_package_source_modules(import_name: str, package_dir: Path) -> None:
    module_names = [
        module_name
        for path in sorted(package_dir.rglob("*.py"))
        if (module_name := _source_module_name(import_name, package_dir, path)) is not None
    ]
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        for module_name in module_names:
            try:
                importlib.import_module(module_name)
            except Exception as exc:
                raise GaiaPackagingError(
                    f"Error importing package module {module_name}: {exc}"
                ) from exc
    finally:
        sys.dont_write_bytecode = previous


def _load_pyproject_config(pkg_path: Path) -> dict[str, Any]:
    """Load pyproject.toml for a Gaia package path."""
    pyproject = pkg_path / "pyproject.toml"
    if not pyproject.exists():
        raise GaiaPackagingError("Error: no pyproject.toml found.")
    with open(pyproject, "rb") as f:
        return tomllib.load(f)


def _package_identity(config: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], str, str]:
    """Validate and return project config, Gaia config, project name, and version."""
    project_config = config.get("project", {})
    gaia_config = config.get("tool", {}).get("gaia", {})
    if gaia_config.get("type") != "knowledge-package":
        raise GaiaPackagingError(
            "Error: not a Gaia knowledge package ([tool.gaia].type != 'knowledge-package')."
        )

    project_name = project_config.get("name")
    version = project_config.get("version")
    if not isinstance(project_name, str) or not project_name:
        raise GaiaPackagingError("Error: [project].name is required.")
    if not isinstance(version, str) or not version:
        raise GaiaPackagingError("Error: [project].version is required.")
    return project_config, gaia_config, project_name, version


def _source_root_for_package(pkg_path: Path, import_name: str, project_name: str) -> Path:
    """Return the source root containing the package import module."""
    package_roots = [pkg_path, pkg_path / "src"]
    source_root = next((root for root in package_roots if (root / import_name).exists()), None)
    if source_root is not None:
        return source_root
    expected_paths = ", ".join(
        f"{candidate.relative_to(pkg_path)}/"
        for candidate in (root / import_name for root in package_roots)
    )
    raise GaiaPackagingError(
        f"Error: package source directory '{import_name}/' not found.\n"
        f"  Derived from [project] name {project_name!r}.\n"
        '  Derivation: strip trailing "-gaia" when present, then convert '
        "hyphens to underscores.\n"
        f"  Expected at one of: {expected_paths}"
    )


def _prepend_local_dependency_source_roots(config: dict[str, Any], pkg_path: Path) -> None:
    """Expose local editable Gaia dependencies before importing the package."""
    project_config = config.get("project", {})
    if not isinstance(project_config, dict):
        return
    dependencies = project_config.get("dependencies", [])
    if not isinstance(dependencies, list):
        return
    uv_sources = config.get("tool", {}).get("uv", {}).get("sources", {})
    if not isinstance(uv_sources, dict):
        uv_sources = {}

    for raw in dependencies:
        if not isinstance(raw, str):
            continue
        try:
            requirement = Requirement(raw)
        except InvalidRequirement:
            continue
        if not requirement.name.endswith("-gaia"):
            continue
        dependency_root = _local_dependency_root(
            requirement,
            uv_sources=uv_sources,
            pkg_path=pkg_path,
        )
        if dependency_root is None:
            continue
        import_name = requirement.name.removesuffix("-gaia").replace("-", "_")
        source_root = _local_dependency_source_root(dependency_root, import_name)
        if source_root is None:
            continue
        source_root_str = str(source_root)
        if source_root_str not in sys.path:
            sys.path.insert(0, source_root_str)


def _local_dependency_root(
    requirement: Requirement,
    *,
    uv_sources: dict[str, Any],
    pkg_path: Path,
) -> Path | None:
    if requirement.url:
        parsed = urlparse(requirement.url)
        if parsed.scheme == "file":
            return Path(unquote(parsed.path)).resolve()
    source = uv_sources.get(requirement.name)
    if isinstance(source, dict):
        raw_path = source.get("path")
        if isinstance(raw_path, str) and raw_path:
            path = Path(raw_path)
            if not path.is_absolute():
                path = pkg_path / path
            return path.resolve()
    return None


def _local_dependency_source_root(root: Path, import_name: str) -> Path | None:
    for candidate in (root, root / "src"):
        if (candidate / import_name).exists():
            return candidate
    return None


def _prepend_pulled_package_source_roots(pkg_path: Path) -> None:
    """Expose pulled LKM packages on ``sys.path`` for this operation.

    ``gaia pkg add --lkm-paper <id>`` materializes a paper as an editable
    sub-package under ``<pkg>/.gaia/lkm_packages/<dist>-gaia/src/`` and registers
    it with ``uv add --editable``. That install lands in the *package's own* uv
    environment, which has no ``gaia-lang``, while ``gaia`` itself runs from a
    different environment that lacks the pulled package — so compiling, rendering,
    or post-write-checking a package that pulled a paper fails to import the
    generated module unless the caller hand-builds a ``PYTHONPATH``.

    Pulled packages are pure gaia-DSL claim modules depending only on the
    already-present ``gaia-lang``, so adding each pulled package's ``src/`` dir to
    module resolution is sufficient to import them in-process. This mutates only
    ``sys.path`` for the current process (no environment install), which keeps the
    augmentation scoped to the compile/render/check operation that needs it.
    """
    lkm_root = pkg_path / ".gaia" / "lkm_packages"
    if not lkm_root.is_dir():
        return
    for dist_dir in sorted(lkm_root.iterdir()):
        if not dist_dir.is_dir():
            continue
        src_root = dist_dir / "src"
        if not src_root.is_dir():
            continue
        src_root_str = str(src_root)
        if src_root_str not in sys.path:
            sys.path.insert(0, src_root_str)


def _import_package_module(import_name: str) -> ModuleType:
    """Import a Gaia package module with CLI error wrapping."""
    try:
        return _import_fresh(import_name)
    except Exception as exc:
        raise GaiaPackagingError(f"Error importing package: {exc}") from exc


def _module_titles(import_name: str, pkg: CollectedPackage) -> dict[str, str]:
    """Extract first-line docstrings for loaded package submodules."""
    module_titles: dict[str, str] = {}
    for mod_name in pkg._module_order:
        sub = sys.modules.get(f"{import_name}.{mod_name}")
        if sub is None:
            continue
        doc = getattr(sub, "__doc__", None)
        if isinstance(doc, str) and doc.strip():
            module_titles[mod_name] = doc.strip().split("\n")[0].strip()
    return module_titles


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
    config = _load_pyproject_config(pkg_path)
    project_config, gaia_config, project_name, version = _package_identity(config)

    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    reset_inferred_package(pyproject, module_name=import_name)
    _prepend_local_dependency_source_roots(config, pkg_path)
    _prepend_pulled_package_source_roots(pkg_path)
    source_root = _source_root_for_package(pkg_path, import_name, project_name)

    source_root_str = str(source_root)
    if source_root_str not in sys.path:
        sys.path.insert(0, source_root_str)

    module = _import_package_module(import_name)
    _import_package_source_modules(import_name, source_root / import_name)

    pkg = get_inferred_package(pyproject)
    if pkg is None:
        raise GaiaPackagingError(
            "Error: no Gaia declarations found. Declare Knowledge/Strategy/Operator objects "
            "directly in the module and export the public surface via __all__ when needed."
        )

    _assign_labels_for_loaded_modules()

    # Record exported labels from __all__ for the compiler
    export_names = getattr(module, "__all__", None)
    if isinstance(export_names, list) and all(isinstance(n, str) for n in export_names):
        pkg._exported_labels = set(export_names)

    module_titles = _module_titles(import_name, pkg)
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
    from gaia.engine.lang.compiler import compile_package

    return compile_package(loaded.package)


def compile_loaded_package_artifact(loaded: LoadedGaiaPackage) -> CompiledPackage:
    """Compile an already loaded Gaia package to IR plus runtime mappings."""
    from gaia.engine.lang.compiler import compile_package_artifact
    from gaia.engine.lang.refs import ReferenceError, load_references

    try:
        references = load_references(loaded.pkg_path / "references.json")
        return compile_package_artifact(loaded.package, references=references)
    except ReferenceError as e:
        raise GaiaPackagingError(str(e)) from e


def _knowledge_display_name(knowledge: Knowledge) -> str:
    return knowledge.label or knowledge.content or repr(knowledge)


def _load_resolution_policy(loaded: LoadedGaiaPackage) -> ResolutionPolicy:
    """Auto-import ``priors.py`` (if present) and read the package's ResolutionPolicy.

    Importing the module triggers any ``register_prior()`` calls inside it,
    populating ``claim.metadata['prior_records']`` as a side effect. If the
    module additionally exports ``RESOLUTION_POLICY``, that policy is used in
    place of :func:`default_resolution_policy`.

    Rejects the legacy ``PRIORS = {...}`` dict with a migration error pointing
    to ``register_prior``.
    """
    priors_module_name = f"{loaded.import_name}.priors"
    priors_path = loaded.source_root / loaded.import_name / "priors.py"
    if not priors_path.exists():
        return default_resolution_policy()

    existing_knowledge_ids = {id(k) for k in loaded.package.knowledge}

    try:
        module = _import_fresh(priors_module_name)
    except Exception as exc:
        raise GaiaPackagingError(f"Error importing priors.py: {exc}") from exc

    new_knowledge = [k for k in loaded.package.knowledge if id(k) not in existing_knowledge_ids]
    if new_knowledge:
        names = ", ".join(_knowledge_display_name(k) for k in new_knowledge[:5])
        suffix = " ..." if len(new_knowledge) > 5 else ""
        raise GaiaPackagingError(
            "Error: priors.py must not declare new Knowledge objects; it may only "
            "reference claims already declared by the package. "
            f"New declarations: {names}{suffix}."
        )

    if hasattr(module, "PRIORS"):
        raise GaiaPackagingError(
            "Error: priors.py exports a `PRIORS = {...}` dict, which is no longer "
            "supported (removed in v0.5+). Set priors with register_prior() instead:\n\n"
            "    from gaia.engine.lang import register_prior\n"
            "    from . import my_claim\n\n"
            '    register_prior(my_claim, value=0.7, justification="literature consensus")\n\n'
            "register_prior() supports multiple sources per claim (user, reviewer, "
            "engine, agent, calibration) with explicit provenance and Cromwell-checked "
            "values. See docs/foundations/gaia-ir/06-parameterization.md for the "
            "migration guide and the multi-source prior model."
        )

    if hasattr(module, "RESOLUTION_POLICY"):
        policy = module.RESOLUTION_POLICY
        if not isinstance(policy, ResolutionPolicy):
            raise GaiaPackagingError(
                "Error: priors.py exports RESOLUTION_POLICY but it is not a "
                f"ResolutionPolicy instance ({type(policy).__name__}). "
                "Use:\n\n"
                "    from gaia.engine.ir import ResolutionPolicy\n"
                '    RESOLUTION_POLICY = ResolutionPolicy(strategy="explicit_priority", ...)'
            )
        return policy

    return default_resolution_policy()


def apply_package_priors(loaded: LoadedGaiaPackage) -> None:
    """Resolve multi-source priors and inject the winning value into metadata.

    Pipeline:

    1. Auto-import ``priors.py`` if present. This runs any
       ``register_prior(...)`` calls inside the module, populating
       ``claim.metadata['prior_records']`` as a side effect. The legacy
       ``PRIORS = {...}`` dict is rejected with a migration error.
    2. Read the package's optional ``RESOLUTION_POLICY`` from ``priors.py``,
       falling back to :func:`default_resolution_policy` when absent.
    3. Walk every ``Claim`` in the package. For each claim with one or more
       records under ``metadata['prior_records']``, run the policy and write
       the winning value/justification to ``metadata['prior']`` /
       ``metadata['prior_justification']``.

    All records (winner and losers) are preserved in ``prior_records`` for
    audit purposes and for the ``prior_dissent`` / ``prior_overridden``
    diagnostics.

    Authors may also call ``register_prior`` directly from ``__init__.py`` or
    any other module imported during package load — those calls populate
    ``prior_records`` before this function runs, and are resolved identically
    to those declared in ``priors.py``.
    """
    policy = _load_resolution_policy(loaded)
    loaded.package._resolution_policy = policy
    try:
        resolve_priors_to_metadata(loaded.package.knowledge, policy)
    except (TypeError, ValueError) as exc:
        raise GaiaPackagingError(f"Error resolving priors: {exc}") from exc


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
        raise GaiaPackagingError("Error: [project].dependencies must be a list if set.")
    specs: dict[str, str] = {}
    import_to_dist: dict[str, str] = {}
    for raw in dependencies:
        if not isinstance(raw, str):
            raise GaiaPackagingError("Error: [project].dependencies entries must be strings.")
        try:
            requirement = Requirement(raw)
        except InvalidRequirement as exc:
            raise GaiaPackagingError(
                f"Error: invalid dependency requirement '{raw}': {exc}"
            ) from exc
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
        return cast(dict[str, Any], json.loads(path.read_text()))
    except json.JSONDecodeError as exc:
        raise GaiaPackagingError(f"Error: {description} is not valid JSON: {exc}") from exc


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
        raise GaiaPackagingError(
            f"Error: dependency '{import_name}' has stale .gaia manifests; "
            f"run `gaia build compile` in {root}."
        )


def _resolve_dependency_premises_manifest(import_name: str) -> tuple[Path, dict[str, Any]]:
    root = _locate_dependency_manifest_root(import_name)
    if root is None:
        raise GaiaPackagingError(
            f"Error: could not locate Gaia package root for dependency '{import_name}'."
        )
    premises_path = root / ".gaia" / "manifests" / "premises.json"
    if not premises_path.exists():
        raise GaiaPackagingError(
            f"Error: dependency '{import_name}' is missing .gaia/manifests/premises.json. "
            f"This file is generated by `gaia build compile` (gaia-lang >= 0.2.5). "
            f"If the dependency was compiled with an older version, upgrade gaia-lang "
            f"and recompile: cd {root} && uv add 'gaia-lang>=0.3.0' && gaia build compile"
        )
    premises_manifest = _load_json_file(
        premises_path,
        description=f"{import_name} dependency manifest {premises_path}",
    )
    stored_ir_hash = premises_manifest.get("ir_hash")
    if not isinstance(stored_ir_hash, str) or not stored_ir_hash:
        raise GaiaPackagingError(f"Error: dependency manifest {premises_path} is missing ir_hash.")
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


def _fills_relation_metadata(strategy: Strategy) -> dict[str, Any] | None:
    """Return fills() relation metadata for a strategy, if present."""
    relation = strategy.metadata.get("gaia", {}).get("relation", {})
    if not isinstance(relation, dict):
        return None
    if relation.get("type") != "fills":
        return None
    if len(strategy.premises) != 1 or strategy.conclusion is None:
        raise GaiaPackagingError(
            "Error: fills() strategies must have exactly one source and one target."
        )
    return cast(dict[str, Any], relation)


def _validate_fills_owners(
    *,
    source: Knowledge,
    target: Knowledge,
    local_package: CollectedPackage,
    import_to_dist: dict[str, str],
    dependency_specs: dict[str, str],
) -> None:
    """Validate fills() source and target package ownership."""
    source_owner = source._package
    target_owner = target._package
    if target_owner is None or target_owner == local_package:
        raise GaiaPackagingError(
            "Error: fills() target must be a foreign claim resolved from a dependency package."
        )
    if source_owner is not None and source_owner != local_package:
        source_dist = import_to_dist.get(source_owner.name)
        if source_dist is None or source_dist not in dependency_specs:
            raise GaiaPackagingError(
                f"Error: fills() source dependency '{source_owner.name}' is not declared in "
                "[project].dependencies (no matching *-gaia distribution found)."
            )
    target_dist = import_to_dist.get(target_owner.name)
    if target_dist is None or target_dist not in dependency_specs:
        raise GaiaPackagingError(
            f"Error: fills() target dependency '{target_owner.name}' is not declared in "
            "[project].dependencies (no matching *-gaia distribution found)."
        )


def _dependency_premises_for_owner(
    owner: CollectedPackage,
    cache: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Load and cache the dependency premises manifest for a target owner."""
    premises_manifest = cache.get(owner.name)
    if premises_manifest is None:
        _, premises_manifest = _resolve_dependency_premises_manifest(owner.name)
        cache[owner.name] = premises_manifest
    premises = premises_manifest.get("premises", [])
    if not isinstance(premises, list):
        raise GaiaPackagingError(
            "Error: dependency premises manifest must contain a premises list."
        )
    return premises_manifest


def _fills_qids_and_source_hash(
    *,
    source: Knowledge,
    target: Knowledge,
    compiled: CompiledPackage,
    knowledge_by_qid: dict[str, IrKnowledge],
) -> tuple[str, str, str]:
    """Resolve source/target QIDs and source content hash for a fills() relation."""
    source_qid = compiled.knowledge_ids_by_object.get(id(source))
    target_qid = compiled.knowledge_ids_by_object.get(id(target))
    if source_qid is None or target_qid is None:
        raise GaiaPackagingError(
            "Error: could not resolve fills() source/target QID during compile."
        )
    source_knowledge = knowledge_by_qid.get(source_qid)
    if source_knowledge is None or source_knowledge.content_hash is None:
        raise GaiaPackagingError(
            f"Error: could not resolve source content hash for '{source_qid}'."
        )
    return source_qid, target_qid, source_knowledge.content_hash


def _target_premise_entry(
    *,
    premises_manifest: dict[str, Any],
    target_owner: CollectedPackage,
    target_qid: str,
) -> dict[str, Any]:
    """Return the dependency local_hole entry for a fills() target QID."""
    premises = premises_manifest.get("premises", [])
    entry = next(
        (
            premise
            for premise in premises
            if isinstance(premise, dict) and premise.get("qid") == target_qid
        ),
        None,
    )
    if entry is None:
        raise GaiaPackagingError(
            f"Error: fills() target '{target_qid}' is not a public premise in dependency "
            f"'{target_owner.name}'."
        )
    if entry.get("role") != "local_hole":
        raise GaiaPackagingError(
            f"Error: fills() target '{target_qid}' must resolve to a dependency local_hole, "
            f"found role={entry.get('role')!r}."
        )
    return entry


def _required_manifest_string(manifest: dict[str, Any], key: str, owner_name: str) -> str:
    """Return a required string field from a dependency premises manifest."""
    value = manifest.get(key)
    if not isinstance(value, str) or not value:
        raise GaiaPackagingError(
            f"Error: dependency premises manifest for '{owner_name}' is missing {key}."
        )
    return value


def _target_interface_hash(entry: dict[str, Any], target_qid: str) -> str:
    """Return a target premise entry's required interface hash."""
    interface_hash = entry.get("interface_hash")
    if not isinstance(interface_hash, str) or not interface_hash:
        raise GaiaPackagingError(
            f"Error: dependency premise '{target_qid}' is missing interface_hash."
        )
    return interface_hash


def _mark_unique_fills_relation(
    seen_relation_keys: set[tuple[str, str, str]],
    *,
    source_qid: str,
    target_qid: str,
    target_interface_hash: str,
) -> None:
    """Record a fills() relation key and reject duplicates."""
    relation_key = (source_qid, target_qid, target_interface_hash)
    if relation_key in seen_relation_keys:
        raise GaiaPackagingError(
            f"Error: duplicate fills() relation for source '{source_qid}' and target "
            f"'{target_qid}' on interface '{target_interface_hash}'."
        )
    seen_relation_keys.add(relation_key)


def _build_fills_relation_record(
    *,
    ctx: _FillsContext,
    strategy: Strategy,
    relation: dict[str, Any],
    source: Knowledge,
    target: Knowledge,
) -> dict[str, Any]:
    """Build one serialized fills() bridge relation."""
    target_owner = cast(CollectedPackage, target._package)
    target_dist = ctx.import_to_dist[target_owner.name]
    premises_manifest = _dependency_premises_for_owner(target_owner, ctx.manifest_cache)
    source_qid, target_qid, source_content_hash = _fills_qids_and_source_hash(
        source=source,
        target=target,
        compiled=ctx.compiled,
        knowledge_by_qid=ctx.knowledge_by_qid,
    )
    entry = _target_premise_entry(
        premises_manifest=premises_manifest,
        target_owner=target_owner,
        target_qid=target_qid,
    )
    target_interface_hash = _target_interface_hash(entry, target_qid)
    _mark_unique_fills_relation(
        ctx.seen_relation_keys,
        source_qid=source_qid,
        target_qid=target_qid,
        target_interface_hash=target_interface_hash,
    )
    relation_type = str(relation.get("type"))
    relation_record = {
        "relation_id": _relation_id(
            declaring_package=_manifest_package_name(ctx.loaded),
            declaring_version=ctx.loaded.project_config["version"],
            source_qid=source_qid,
            source_content_hash=source_content_hash,
            target_qid=target_qid,
            target_interface_hash=target_interface_hash,
            relation_type=relation_type,
        ),
        "relation_type": relation_type,
        "source_qid": source_qid,
        "source_content_hash": source_content_hash,
        "target_qid": target_qid,
        "target_package": _required_manifest_string(
            premises_manifest, "package", target_owner.name
        ),
        "target_dependency_req": ctx.dependency_specs[target_dist],
        "target_resolved_version": _required_manifest_string(
            premises_manifest, "version", target_owner.name
        ),
        "target_role": entry["role"],
        "target_interface_hash": target_interface_hash,
        "strength": relation.get("strength"),
        "mode": relation.get("mode"),
        "declared_by_owner_of_source": source._package == ctx.loaded.package,
    }
    justification = _reason_to_text(strategy.reason)
    if justification:
        relation_record["justification"] = justification
    return relation_record


def _resolve_one_fills_relation(ctx: _FillsContext, strategy: Strategy) -> dict[str, Any] | None:
    """Resolve one Strategy into a fills() bridge record when applicable."""
    relation = _fills_relation_metadata(strategy)
    if relation is None:
        return None
    source = strategy.premises[0]
    target = cast(Knowledge, strategy.conclusion)
    _validate_fills_owners(
        source=source,
        target=target,
        local_package=ctx.loaded.package,
        import_to_dist=ctx.import_to_dist,
        dependency_specs=ctx.dependency_specs,
    )
    return _build_fills_relation_record(
        ctx=ctx,
        strategy=strategy,
        relation=relation,
        source=source,
        target=target,
    )


def _resolve_fills_relations(
    loaded: LoadedGaiaPackage, compiled: CompiledPackage
) -> list[dict[str, Any]]:
    dependency_specs, import_to_dist = _parse_gaia_dependencies(loaded.project_config)
    knowledge_by_qid = {
        knowledge.id: knowledge for knowledge in compiled.graph.knowledges if knowledge.id
    }
    ctx = _FillsContext(
        loaded=loaded,
        compiled=compiled,
        dependency_specs=dependency_specs,
        import_to_dist=import_to_dist,
        knowledge_by_qid=knowledge_by_qid,
        manifest_cache={},
        seen_relation_keys=set(),
    )
    relations: list[dict[str, Any]] = []

    for strategy in loaded.package.strategies:
        relation_record = _resolve_one_fills_relation(ctx, strategy)
        if relation_record is not None:
            relations.append(relation_record)

    return sorted(relations, key=lambda item: item["relation_id"])


def _knowledge_manifest_entry(knowledge: IrKnowledge) -> dict[str, Any]:
    entry: dict[str, Any] = {
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


def validate_fills_relations(loaded: LoadedGaiaPackage, compiled: CompiledPackage) -> None:
    """Validate fills() relations without building full manifests.

    Raises GaiaPackagingError if any fills() strategy has an invalid source,
    target, or dependency configuration. Use this for ``gaia build check``
    where manifests are not needed — only validation matters.
    """
    _resolve_fills_relations(loaded, compiled)


def _manifest_graph_sets(
    graph: LocalCanonicalGraph,
) -> tuple[dict[str, IrKnowledge], set[str], set[str]]:
    """Return graph knowledge map, exported ids, and exported claim ids."""
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
    return knowledge_by_qid, exported_qids, exported_claim_qids


def _manifest_exports(graph: LocalCanonicalGraph) -> list[dict[str, Any]]:
    """Return sorted exported-knowledge manifest entries."""
    return [
        _knowledge_manifest_entry(knowledge)
        for knowledge in sorted(graph.knowledges, key=lambda item: item.id or "")
        if knowledge.exported and knowledge.id is not None
    ]


def _local_support_indexes(
    loaded: LoadedGaiaPackage,
) -> tuple[set[int], dict[int, list[Strategy]], dict[int, list[Knowledge]]]:
    """Index local strategy support edges by object id."""
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
    return local_knowledge_ids, local_supports_by_conclusion, downstream_conclusions_by_premise


def _public_premise_objects(
    *,
    loaded: LoadedGaiaPackage,
    compiled: CompiledPackage,
    exported_claim_qids: set[str],
    local_knowledge_ids: set[int],
    local_supports_by_conclusion: dict[int, list[Strategy]],
) -> dict[int, Knowledge]:
    """Collect leaf claims feeding exported local conclusions."""
    public_premises: dict[int, Knowledge] = {}
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
                public_premises[premise_id] = premise

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
    return public_premises


def _required_by_exports(
    *,
    premise: Knowledge,
    compiled: CompiledPackage,
    downstream_conclusions_by_premise: dict[int, list[Knowledge]],
    exported_claim_qids: set[str],
) -> list[str]:
    """Return exported conclusions downstream of a public premise."""
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
    return sorted(required_by_set)


def _premise_manifest_entry(
    *,
    premise: Knowledge,
    compiled: CompiledPackage,
    knowledge_by_qid: dict[str, IrKnowledge],
    local_knowledge_ids: set[int],
    exported_qids: set[str],
    exported_claim_qids: set[str],
    downstream_conclusions_by_premise: dict[int, list[Knowledge]],
) -> dict[str, Any] | None:
    """Build one premises.json entry for a public premise object."""
    premise_qid = compiled.knowledge_ids_by_object.get(id(premise))
    if premise_qid is None:
        return None
    knowledge = knowledge_by_qid.get(premise_qid)
    if knowledge is None or knowledge.content_hash is None:
        return None
    role = "local_hole" if id(premise) in local_knowledge_ids else "foreign_dependency"
    parameters = [parameter.model_dump(mode="json") for parameter in knowledge.parameters]
    entry: dict[str, Any] = {
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
        "required_by": _required_by_exports(
            premise=premise,
            compiled=compiled,
            downstream_conclusions_by_premise=downstream_conclusions_by_premise,
            exported_claim_qids=exported_claim_qids,
        ),
    }
    if parameters:
        entry["parameters"] = parameters
    return entry


def _manifest_premises(
    *,
    loaded: LoadedGaiaPackage,
    compiled: CompiledPackage,
    knowledge_by_qid: dict[str, IrKnowledge],
    exported_qids: set[str],
    exported_claim_qids: set[str],
) -> list[dict[str, Any]]:
    """Build the premises.json entries for exported local conclusions."""
    local_ids, supports_by_conclusion, downstream_by_premise = _local_support_indexes(loaded)
    public_premises = _public_premise_objects(
        loaded=loaded,
        compiled=compiled,
        exported_claim_qids=exported_claim_qids,
        local_knowledge_ids=local_ids,
        local_supports_by_conclusion=supports_by_conclusion,
    )
    entries: list[dict[str, Any]] = []
    for premise in sorted(
        public_premises.values(),
        key=lambda item: compiled.knowledge_ids_by_object.get(id(item), ""),
    ):
        entry = _premise_manifest_entry(
            premise=premise,
            compiled=compiled,
            knowledge_by_qid=knowledge_by_qid,
            local_knowledge_ids=local_ids,
            exported_qids=exported_qids,
            exported_claim_qids=exported_claim_qids,
            downstream_conclusions_by_premise=downstream_by_premise,
        )
        if entry is not None:
            entries.append(entry)
    return entries


def build_package_manifests(
    loaded: LoadedGaiaPackage, compiled: CompiledPackage
) -> dict[str, dict[str, Any]]:
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
    knowledge_by_qid, exported_qids, exported_claim_qids = _manifest_graph_sets(graph)
    exports = _manifest_exports(graph)
    premises = _manifest_premises(
        loaded=loaded,
        compiled=compiled,
        knowledge_by_qid=knowledge_by_qid,
        exported_qids=exported_qids,
        exported_claim_qids=exported_claim_qids,
    )

    holes = [
        {key: value for key, value in premise.items() if key != "role" and key != "exported"}
        for premise in premises
        if premise["role"] == "local_hole"
    ]

    return {
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


def collect_foreign_node_priors(
    graph: LocalCanonicalGraph,
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

    Returns:
    -------
    Flat list of :class:`DependencyGraph` for all discovered dependencies
    (deduplicated by ``namespace:package_name``).
    """
    from gaia.engine.ir.graphs import LocalCanonicalGraph

    if _seen is None:
        _seen = set()

    _specs, import_to_dist = _parse_gaia_dependencies(project_config)
    result: list[DependencyGraph] = []

    for import_name, dist_name in sorted(import_to_dist.items()):
        root = _locate_dependency_manifest_root(import_name)
        if root is None:
            raise GaiaPackagingError(
                f"Could not locate Gaia package root for dependency '{import_name}'. "
                f"Is '{dist_name}' installed?"
            )
        ir_path = root / ".gaia" / "ir.json"
        if not ir_path.exists():
            raise GaiaPackagingError(
                f"Dependency '{import_name}' is missing .gaia/ir.json. "
                f"Run 'gaia build compile' in {root}."
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
    `gaia build compile` inside an un-built editable checkout still produces a valid
    metadata file — downstream consumers can detect 'unknown' and decide.
    """
    try:
        return _pkg_version("gaia-lang")
    except PackageNotFoundError:
        return "unknown"


def _utc_now_iso() -> str:
    """UTC timestamp in ISO-8601 with Z suffix and second precision."""
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _render_compile_metadata(ir_hash: str) -> str:
    """Build the `.gaia/compile_metadata.json` payload.

    This file is the canonical provenance anchor for a compiled IR: it records
    which `gaia-lang` version produced the IR, pinned to the IR hash the
    metadata file sits next to. `gaia run infer` copies the version into its
    output artifacts so beliefs can be correlated back to the compile
    environment, and `gaia pkg register` reads this file to populate
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


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text via a unique temp file and atomic replace."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp.write_text(text, encoding=encoding)
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink()


def write_compiled_artifacts(
    pkg_path: Path,
    ir: dict[str, Any],
    *,
    manifests: dict[str, dict[str, Any]] | None = None,
    formalization_manifest: dict[str, Any] | None = None,
) -> Path:
    """Write .gaia compilation artifacts and return the output directory."""
    gaia_dir = pkg_path / ".gaia"
    gaia_dir.mkdir(exist_ok=True)
    ir_json = json.dumps(ir, ensure_ascii=False, indent=2, sort_keys=True)
    write_text_atomic(gaia_dir / "ir.json", ir_json)
    write_text_atomic(gaia_dir / "ir_hash", ir["ir_hash"])
    write_text_atomic(gaia_dir / "compile_metadata.json", _render_compile_metadata(ir["ir_hash"]))
    if formalization_manifest is not None:
        write_text_atomic(
            gaia_dir / "formalization_manifest.json",
            render_manifest_json(formalization_manifest),
        )
    if manifests:
        manifests_dir = gaia_dir / "manifests"
        manifests_dir.mkdir(exist_ok=True)
        for filename, payload in manifests.items():
            write_text_atomic(manifests_dir / filename, render_manifest_json(payload))
    return gaia_dir
