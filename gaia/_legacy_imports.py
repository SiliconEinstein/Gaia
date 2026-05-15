"""Alpha 0 legacy-import tombstones — helper + machine-readable maps.

This module exists so any stale ``from gaia.<old> import X`` (whether in
user code, examples, or external tooling) raises a clean ``ImportError``
that points at the new ``gaia.engine.<sub>`` path. The maps are also the
contract that ``tests/baseline/test_l2_tombstones.py`` asserts against.

See ``home_agent/projects/gaia/alpha-0/legacy-import-paths.md`` for the
generation rationale and the full enumeration.
"""

from __future__ import annotations

import importlib.abc
import importlib.machinery
import sys
from collections.abc import Callable, Sequence
from types import ModuleType

_TOMBSTONE_TEMPLATE = (
    "{old_path} has moved to {new_path}; this path was never public API "
    "and is removed in alpha 0. Update imports to `{new_path}`."
)


def _tombstoned_namespace_getattr(old_ns: str, new_ns: str) -> Callable[[str], object]:
    """Build a module ``__getattr__`` that redirects every attribute access."""

    def __getattr__(name: str) -> object:
        raise ImportError(
            _TOMBSTONE_TEMPLATE.format(
                old_path=f"{old_ns}.{name}",
                new_path=f"{new_ns}.{name}",
            )
        )

    return __getattr__


def _tombstoned_symbol_getattr(
    old_ns: str,
    redirects: dict[str, str],
) -> Callable[[str], object]:
    """Build a module ``__getattr__`` that redirects specific symbols.

    Symbols in ``redirects`` raise ``ImportError`` pointing to the new path.
    Other names raise ``AttributeError`` so the module can still expose
    private helpers / type aliases that did not migrate.
    """

    def __getattr__(name: str) -> object:
        if name in redirects:
            new_path = redirects[name]
            raise ImportError(
                _TOMBSTONE_TEMPLATE.format(
                    old_path=f"{old_ns}.{name}",
                    new_path=new_path,
                )
            )
        raise AttributeError(f"module {old_ns!r} has no attribute {name!r}")

    return __getattr__


class _TombstonedSubmoduleLoader(importlib.abc.Loader):
    """Loader that turns stale direct submodule imports into redirect errors."""

    def __init__(self, old_path: str, new_path: str) -> None:
        self._old_path = old_path
        self._new_path = new_path

    def create_module(self, spec: importlib.machinery.ModuleSpec) -> ModuleType | None:
        del spec
        return None

    def exec_module(self, module: ModuleType) -> None:
        del module
        raise ImportError(
            _TOMBSTONE_TEMPLATE.format(
                old_path=self._old_path,
                new_path=self._new_path,
            )
        )


class _TombstonedSubmoduleFinder(importlib.abc.MetaPathFinder):
    """Finder for direct imports like ``import gaia.bp.factor_graph``."""

    _gaia_tombstoned_submodule_finder = True

    def find_spec(
        self,
        fullname: str,
        path: Sequence[str] | None,
        target: ModuleType | None = None,
    ) -> importlib.machinery.ModuleSpec | None:
        del path, target
        for old_ns, new_ns in TOMBSTONED_NAMESPACES.items():
            prefix = f"{old_ns}."
            if fullname.startswith(prefix):
                suffix = fullname.removeprefix(prefix)
                new_path = f"{new_ns}.{suffix}"
                return importlib.machinery.ModuleSpec(
                    fullname,
                    _TombstonedSubmoduleLoader(fullname, new_path),
                )
        return None


def _install_tombstoned_submodule_finder() -> None:
    """Install the finder once per interpreter."""
    already_installed = any(
        getattr(finder, "_gaia_tombstoned_submodule_finder", False) for finder in sys.meta_path
    )
    if not already_installed:
        sys.meta_path.insert(0, _TombstonedSubmoduleFinder())


TOMBSTONED_NAMESPACES: dict[str, str] = {
    "gaia.bp": "gaia.engine.bp",
    "gaia.ir": "gaia.engine.ir",
    "gaia.lang": "gaia.engine.lang",
    "gaia.logic": "gaia.engine.logic",
    "gaia.inquiry": "gaia.engine.inquiry",
    "gaia.trace": "gaia.engine.trace",
}


TOMBSTONED_SYMBOLS: dict[str, dict[str, str]] = {
    "gaia.cli._packages": {
        "GaiaCliError": "gaia.engine.packaging.GaiaPackagingError",
        "apply_package_priors": "gaia.engine.packaging.apply_package_priors",
        "collect_foreign_node_priors": "gaia.engine.packaging.collect_foreign_node_priors",
        "compile_loaded_package_artifact": "gaia.engine.packaging.compile_loaded_package_artifact",
        "ensure_package_env": "gaia.engine.packaging.ensure_package_env",
        "load_dependency_compiled_graphs": "gaia.engine.packaging.load_dependency_compiled_graphs",
        "load_gaia_package": "gaia.engine.packaging.load_gaia_package",
    },
    "gaia.cli.commands._review_manifest": {
        "load_or_generate_review_manifest": "gaia.engine.inquiry.load_or_generate_review_manifest",
    },
    "gaia.cli.commands.check_core": {
        "KnowledgeBreakdown": "gaia.engine.inquiry.KnowledgeBreakdown",
        "analyze_knowledge_breakdown": "gaia.engine.inquiry.analyze_knowledge_breakdown",
        "find_possible_duplicate_claims": "gaia.engine.inquiry.find_possible_duplicate_claims",
        "HoleEntry": "gaia.engine.inquiry.HoleEntry",
    },
}


_install_tombstoned_submodule_finder()


__all__ = [
    "TOMBSTONED_NAMESPACES",
    "TOMBSTONED_SYMBOLS",
    "_tombstoned_namespace_getattr",
    "_tombstoned_symbol_getattr",
]
