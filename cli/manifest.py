"""Build manifest serialization — save/restore a resolved Package as JSON.

The manifest captures the fully resolved package state after build, so downstream
stages (review, infer, publish) can work from the immutable artifact without
re-parsing YAML source files.
"""

from __future__ import annotations

import json
from pathlib import Path

from libs.lang.loader import _parse_step
from libs.lang.models import (
    KNOWLEDGE_TYPE_MAP,
    ChainExpr,
    Knowledge,
    Module,
    Package,
    Ref,
)


def _dump_knowledge(k: Knowledge) -> dict:
    """Serialize a Knowledge subclass preserving all subclass-specific fields.

    Module.model_dump() only emits base Knowledge fields because the list is typed
    as ``list[Knowledge]``.  Calling model_dump() on each item directly captures
    the full subclass schema.
    """
    data = k.model_dump(by_alias=True)
    data["__type__"] = k.type
    return data


def _dump_module(mod: Module) -> dict:
    """Serialize a Module, handling knowledge items individually."""
    return {
        "type": mod.type,
        "name": mod.name,
        "title": mod.title,
        "knowledge": [_dump_knowledge(k) for k in mod.knowledge],
        "export": mod.export,
    }


def save_manifest(
    pkg: Package,
    build_dir: Path,
    pkg_path: Path | None = None,
) -> Path:
    """Serialize a resolved Package to ``build_dir/manifest.json``.

    Args:
        pkg: A fully resolved Package (loaded_modules populated, _index built).
        build_dir: Directory to write the manifest into.
        pkg_path: Optional original package source path (stored as metadata).

    Returns:
        Path to the written manifest.json file.
    """
    build_dir = Path(build_dir)
    build_dir.mkdir(parents=True, exist_ok=True)

    # Build the resolution index from pkg._index
    resolution_index: dict[str, dict] = {}
    for qname, target in pkg._index.items():
        resolution_index[qname] = _dump_knowledge(target)

    manifest_data = {
        "name": pkg.name,
        "version": pkg.version,
        "manifest": pkg.manifest.model_dump() if pkg.manifest else None,
        "dependencies": [d.model_dump() for d in pkg.dependencies],
        "modules": pkg.modules_list,
        "export": pkg.export,
        "loaded_modules": [_dump_module(m) for m in pkg.loaded_modules],
        "resolution_index": resolution_index,
    }

    if pkg_path is not None:
        manifest_data["source_path"] = str(pkg_path)

    manifest_path = build_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest_data, ensure_ascii=False, indent=2))
    return manifest_path


def _restore_knowledge(data: dict) -> Knowledge:
    """Rebuild a typed Knowledge object from a serialized dict."""
    data = dict(data)  # shallow copy to avoid mutating input
    data.pop("__type__", None)

    type_key = data.get("type", "")
    cls = KNOWLEDGE_TYPE_MAP.get(type_key)

    if cls is None:
        return Knowledge.model_validate(data)

    if cls is ChainExpr:
        raw_steps = data.pop("steps", [])
        steps = [_parse_step(s) for s in raw_steps]
        return ChainExpr(
            name=data["name"],
            steps=steps,
            prior=data.get("prior"),
            metadata=data.get("metadata"),
            edge_type=data.get("edge_type"),
        )

    return cls.model_validate(data)


def _restore_module(data: dict) -> Module:
    """Rebuild a Module from a serialized dict."""
    knowledge = [_restore_knowledge(k) for k in data.get("knowledge", [])]
    return Module(
        type=data["type"],
        name=data["name"],
        title=data.get("title"),
        knowledge=knowledge,
        export=data.get("export", []),
    )


def deserialize_package(manifest_path: Path) -> Package:
    """Rebuild a resolved Package from a manifest.json file.

    Restores:
    - Package metadata (name, version, manifest, export, modules_list)
    - loaded_modules with fully typed knowledge objects
    - ``pkg._index`` from the resolution_index
    - ``Ref._resolved`` pointers by matching ``{module.name}.{ref.name}`` in the index
    """
    manifest_path = Path(manifest_path)
    data = json.loads(manifest_path.read_text())

    # Rebuild package (without loaded_modules, which is exclude=True)
    pkg = Package(
        name=data["name"],
        version=data.get("version"),
        manifest=data.get("manifest"),
        dependencies=data.get("dependencies", []),
        modules=data.get("modules", []),
        export=data.get("export", []),
    )

    # Rebuild loaded_modules
    pkg.loaded_modules = [_restore_module(m) for m in data.get("loaded_modules", [])]

    # Rebuild _index from resolution_index
    resolution_index_raw = data.get("resolution_index", {})
    rebuilt_index: dict[str, Knowledge] = {}
    for qname, kdata in resolution_index_raw.items():
        rebuilt_index[qname] = _restore_knowledge(kdata)
    pkg._index = rebuilt_index

    # Rebuild Ref._resolved pointers
    for mod in pkg.loaded_modules:
        for k in mod.knowledge:
            if isinstance(k, Ref):
                ref_qname = f"{mod.name}.{k.name}"
                resolved_target = pkg._index.get(ref_qname)
                if resolved_target is not None:
                    k._resolved = resolved_target

    return pkg
