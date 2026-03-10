"""Resolve Ref declarations to their target knowledge objects."""

from __future__ import annotations

from .models import Declaration, Package, Ref


class ResolveError(Exception):
    """Raised when a Ref target cannot be resolved."""


def resolve_refs(pkg: Package) -> Package:
    """Resolve all Ref declarations in the package.

    Builds a declaration index (module.name -> Declaration),
    then links each Ref._resolved to its target Declaration.
    """
    # Build index: "module_name.decl_name" -> Declaration
    index: dict[str, Declaration] = {}
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if decl.type != "ref":
                key = f"{module.name}.{decl.name}"
                index[key] = decl

    # Resolve each Ref
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Ref):
                target = index.get(decl.target)
                if target is None:
                    raise ResolveError(
                        f"Cannot resolve ref '{module.name}.{decl.name}' "
                        f"-> '{decl.target}': target not found"
                    )
                decl._resolved = target

    pkg._index = index
    return pkg
