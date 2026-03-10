"""Resolve Ref knowledge objects to their target knowledge objects."""

from __future__ import annotations

from .models import Knowledge, Package, Ref


class ResolveError(Exception):
    """Raised when a Ref target cannot be resolved."""


def resolve_refs(pkg: Package, deps: dict[str, Package] | None = None) -> Package:
    """Resolve all Ref knowledge objects in the package.

    Intra-package refs use ``module.name`` and can point to any declaration in the
    same package. Cross-package refs are resolved against dependency package exports,
    exposed under the stable ``pkg.export_name`` surface. For compatibility, exported
    names are also indexed under ``pkg.module.export_name``.
    """
    local_decls: dict[str, Knowledge] = {}
    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            local_decls[f"{module.name}.{decl.name}"] = decl

    dep_index = _build_dependency_index(deps or {})
    resolved_index: dict[str, Knowledge] = dict(dep_index)
    resolving: set[str] = set()

    def resolve_target(target: str) -> Knowledge | None:
        if target in resolved_index:
            return resolved_index[target]
        if target in local_decls:
            return resolve_local(target)
        return dep_index.get(target)

    def resolve_local(path: str) -> Knowledge:
        if path in resolved_index:
            return resolved_index[path]

        decl = local_decls.get(path)
        if decl is None:
            raise ResolveError(f"Cannot resolve '{path}': declaration not found")

        if not isinstance(decl, Ref):
            resolved_index[path] = decl
            return decl

        if path in resolving:
            raise ResolveError(f"Circular ref detected while resolving '{path}'")

        resolving.add(path)
        try:
            target = resolve_target(decl.target)
            if target is None:
                raise ResolveError(
                    f"Cannot resolve ref '{path}' -> '{decl.target}': target not found"
                )
            decl._resolved = target
            resolved_index[path] = target
            return target
        finally:
            resolving.remove(path)

    for path in local_decls:
        resolve_local(path)

    pkg._index = {path: resolved_index[path] for path in local_decls}
    return pkg


def _build_dependency_index(deps: dict[str, Package]) -> dict[str, Knowledge]:
    """Build the cross-package public index from dependency package exports."""
    dep_index: dict[str, Knowledge] = {}

    for dep_name, dep_pkg in deps.items():
        exported_names = set(dep_pkg.export)
        if not exported_names:
            continue

        export_paths: dict[str, list[str]] = {name: [] for name in exported_names}
        for module in dep_pkg.loaded_modules:
            for decl in module.knowledge:
                if decl.name in exported_names:
                    export_paths[decl.name].append(f"{module.name}.{decl.name}")

        for export_name, candidates in export_paths.items():
            if not candidates:
                continue

            resolved_candidates: list[tuple[str, Knowledge]] = []
            unique_targets: dict[int, Knowledge] = {}
            for local_path in candidates:
                target = dep_pkg._index.get(local_path)
                if target is None:
                    module_name, _ = local_path.split(".", 1)
                    decl = next(
                        d
                        for m in dep_pkg.loaded_modules
                        if m.name == module_name
                        for d in m.knowledge
                        if d.name == export_name
                    )
                    target = decl._resolved if isinstance(decl, Ref) else decl

                if target is None:
                    raise ResolveError(
                        f"Dependency package '{dep_name}' export '{export_name}' is unresolved"
                    )

                resolved_candidates.append((local_path, target))
                unique_targets[id(target)] = target

            if len(unique_targets) > 1:
                raise ResolveError(
                    f"Dependency package '{dep_name}' exports ambiguous name '{export_name}'"
                )

            _, public_target = resolved_candidates[0]
            dep_index[f"{dep_name}.{export_name}"] = public_target
            for candidate_path, candidate_target in resolved_candidates:
                if candidate_target is public_target:
                    dep_index[f"{dep_name}.{candidate_path}"] = public_target

    return dep_index
