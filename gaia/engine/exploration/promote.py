"""Explorer-only promotion of pulled-paper ``depends_on`` scaffolds to ``derive``.

When the explorer expands a node it pulls a whole paper via
``gaia pkg add --lkm-paper <id>`` (``cli/commands/pkg/lkm_materialize.py``). That
materialization emits every paper factor as an INERT ``depends_on(...)`` scaffold
(recorded in the dependency sub-package's formalization manifest, never lowered
into the factor graph). ``depends_on`` is "the authoring-scaffold counterpart of
``derive(...)``" — it preserves premise→conclusion structure but does **not**
enter belief propagation (BP).

For *graph exploration* (the explorer's purpose), a pulled paper's internal
reasoning should be live: each ``depends_on(conclusion, given=[...])`` should
behave like ``derive(conclusion, given=[...])`` so the paper's factors enter BP
and show up on the map. This module performs that promotion **at the explorer
checkpoint only** — ``gaia pkg add`` / ``lkm_materialize`` stay neutral (they keep
emitting the scaffold for general use).

Mechanism (the cleanest seam, per the action graph):

* Each pulled paper lands as an editable ``-gaia`` **dependency sub-package**
  under ``<root>/.gaia/lkm_packages/<dist>/``. Its ``depends_on`` scaffolds live in
  that sub-package's source ``__init__.py`` (and, after compile, its manifest) —
  NOT in the root.
* :func:`promote_dependency_graphs` resolves every such dependency **by path**
  (reusing the frontier's path-based resolver — no ``import_module``), loads each
  from source, and rewrites its in-memory action list: every :class:`DependsOn`
  action is replaced with an equivalent :class:`Derive` (same conclusion / given /
  rationale / label, with the scaffold's provenance ``metadata`` folded into the
  derive ``rationale`` since ``derive`` has no ``metadata=`` kwarg). The promoted
  package is then compiled — the derives lower into the dependency's IR as
  strategies that enter BP.
* The orchestrator's checkpoint lowers each promoted dependency graph + the root
  and merges them (``merge_factor_graphs``, exactly like ``gaia run infer
  --depth -1``) so BP runs over the **joint** graph and the promoted derives move
  belief.

A factor that cannot form a valid ``derive`` (no conclusion, or no given Claims —
the same conditions ``lkm_materialize`` already skips) is skipped and counted,
never crashed on. A dependency that cannot be loaded/compiled degrades to a
warning, never breaks the checkpoint.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from gaia.engine.ir.graphs import LocalCanonicalGraph


@dataclass
class PromotedDependency:
    """One promoted dependency sub-package, ready for joint inference.

    Attributes:
        import_name: The dependency's import name (used as the merge prefix's
            disambiguator and in ``merge_factor_graphs`` factor-id prefixing).
        root: The dependency package directory on disk.
        graph: The recompiled :class:`LocalCanonicalGraph` with the paper's
            ``depends_on`` scaffolds promoted to live ``derive`` strategies.
        promoted: Number of ``depends_on`` scaffolds promoted to ``derive``.
        skipped: Number of scaffolds skipped (no conclusion / no given Claims).
    """

    import_name: str
    root: Path
    graph: LocalCanonicalGraph
    promoted: int
    skipped: int


@dataclass
class PromotionResult:
    """The outcome of promoting every pulled-paper dependency (checkpoint use).

    Attributes:
        dependencies: One :class:`PromotedDependency` per loadable ``-gaia`` dep.
        warnings: Human-readable notes about anything skipped or degraded (a dep
            that could not be loaded/compiled, etc.) — never fatal.
    """

    dependencies: list[PromotedDependency] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def total_promoted(self) -> int:
        """Total ``depends_on`` scaffolds promoted to ``derive`` across all deps."""
        return sum(d.promoted for d in self.dependencies)

    @property
    def total_skipped(self) -> int:
        """Total scaffolds skipped (unpromotable) across all deps."""
        return sum(d.skipped for d in self.dependencies)


def _fold_provenance_into_rationale(rationale: str, metadata: dict[str, Any]) -> str:
    """Preserve the scaffold's provenance ``metadata`` on the promoted derive.

    ``derive(...)`` has no ``metadata=`` kwarg (unlike ``depends_on``), so the
    scaffold's provider/index/paper/doi/factor provenance cannot move onto the
    derive as ``metadata=``. We fold the non-empty provenance keys into the
    derive's ``rationale`` (appended as a compact ``provenance: {...}`` tail) so
    the audit trail is not dropped. The conclusion/given Claims keep their own
    ``metadata`` (which ``lkm_materialize`` already stamps with the same
    provenance), so this is belt-and-suspenders, not the sole carrier.
    """
    clean = {k: v for k, v in metadata.items() if v is not None}
    if not clean:
        return rationale
    tail = "provenance: " + json.dumps(clean, ensure_ascii=False, sort_keys=True)
    return f"{rationale}\n\n{tail}" if rationale else tail


def promote_actions_in_place(pkg: Any) -> tuple[int, int]:
    """Rewrite a loaded package's actions: ``DependsOn`` → ``Derive`` (in place).

    Walks ``pkg.actions`` and replaces every :class:`DependsOn` with an equivalent
    :class:`Derive` carrying the same ``conclusion`` / ``given`` / ``label``, the
    scaffold's ``rationale`` (with provenance folded in), and a freshly built
    implication warrant attached to the conclusion (the step that makes a
    conclusion enter BP). The replacement preserves action order so QID/label
    minting stays stable.

    A scaffold with no ``conclusion`` or no ``given`` Claims cannot form a valid
    derive (the same condition ``lkm_materialize`` skips at authoring time) and is
    dropped from the action list and counted as skipped.

    Args:
        pkg: A ``CollectedPackage`` (``loaded.package``) whose ``actions`` are
            rewritten in place.

    Returns:
        ``(promoted, skipped)`` counts.
    """
    # Build the warrant the same way the `derive(...)` DSL helper does, so a
    # promoted derive is byte-for-byte the derive an author would have written.
    from gaia.engine.lang.dsl.support import _implication_warrant
    from gaia.engine.lang.runtime.action import (
        DependsOn,
        Derive,
        attach_reasoning,
        validate_no_self_warrant,
    )
    from gaia.engine.lang.runtime.knowledge import Claim

    promoted = 0
    skipped = 0
    new_actions: list[Any] = []
    for action in pkg.actions:
        if not isinstance(action, DependsOn):
            new_actions.append(action)
            continue
        conclusion = action.conclusion
        given = tuple(g for g in action.given if isinstance(g, Claim))
        if not isinstance(conclusion, Claim) or not given:
            # Cannot form a valid derive — skip (do not re-emit the scaffold:
            # explorer wants live reasoning, and a lone scaffold here would just
            # re-appear as an inert manifest record).
            skipped += 1
            continue
        rationale = _fold_provenance_into_rationale(action.rationale, dict(action.metadata or {}))
        warrant = _implication_warrant(
            "derive",
            given=given,
            conclusion=conclusion,
            rationale=rationale,
        )
        derive = Derive(
            label=action.label,
            rationale=rationale,
            background=list(action.background or []),
            warrants=[warrant],
            conclusion=conclusion,
            given=given,
        )
        validate_no_self_warrant(derive, conclusion)
        attach_reasoning(conclusion, derive)
        new_actions.append(derive)
        promoted += 1

    pkg.actions = new_actions
    return promoted, skipped


def _promote_one_dependency(dep_root: Path) -> PromotedDependency | None:
    """Load a dependency from source, promote its scaffolds, recompile its IR.

    Returns ``None`` (caller warns) if the dependency cannot be loaded/compiled.
    """
    from gaia.engine.ir import LocalCanonicalGraph
    from gaia.engine.ir.validator import validate_local_graph
    from gaia.engine.packaging import (
        GaiaPackagingError,
        apply_package_priors,
        compile_loaded_package_artifact,
        load_gaia_package,
    )

    loaded = load_gaia_package(str(dep_root))
    promoted, skipped = promote_actions_in_place(loaded.package)
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    ir = compiled.to_json()
    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    if validation.errors:
        raise GaiaPackagingError(
            "promoted dependency did not compile cleanly: " + "; ".join(validation.errors)
        )
    return PromotedDependency(
        import_name=loaded.import_name,
        root=dep_root,
        graph=compiled.graph,
        promoted=promoted,
        skipped=skipped,
    )


def promote_dependency_graphs(root_path: str | Path) -> PromotionResult:
    """Promote every pulled-paper dependency's ``depends_on`` to live ``derive``.

    Resolves the root package's ``-gaia`` dependencies **by path** (reusing the
    frontier's path resolver, so no ``import_module`` is needed for an editable
    ``pkg add --lkm-paper`` dep), and for each one loads it from source, rewrites
    its ``depends_on`` scaffolds into ``derive`` actions, and recompiles it. The
    returned promoted graphs are merged with the root in joint BP by the caller.

    Robustness: a dependency that cannot be resolved on disk, loaded, or compiled
    degrades to a :attr:`PromotionResult.warnings` entry — it is simply absent
    from the joint inference rather than crashing the checkpoint.

    Args:
        root_path: The root exploration package directory.

    Returns:
        A :class:`PromotionResult` with one entry per promoted dependency.
    """
    from gaia.engine.exploration.frontier import _load_deps_by_path

    result = PromotionResult()
    root = Path(root_path).resolve()
    resolution = _load_deps_by_path(root)

    # Resolve dep roots for everything the by-path scan located with a compiled
    # IR (``loaded``) — those are the deps we recompile from source with
    # promotion. ``uncompiled`` / ``unresolved`` deps simply do not participate
    # (they would not have been in the joint frontier view either).
    seen: set[Path] = set()
    for dep_root, _dep_graph in resolution.loaded:
        dep_root = dep_root.resolve()
        if dep_root in seen:
            continue
        seen.add(dep_root)
        try:
            promoted = _promote_one_dependency(dep_root)
        except Exception as exc:  # degrade, never crash the checkpoint
            result.warnings.append(
                f"could not promote dependency at {dep_root} "
                f"({type(exc).__name__}: {exc}); its reasoning will not enter BP this turn"
            )
            continue
        if promoted is not None:
            result.dependencies.append(promoted)

    for dist_name in resolution.uncompiled:
        result.warnings.append(
            f"dependency {dist_name!r} is present but not compiled; "
            "its reasoning will not enter BP (run `gaia build compile` on it)"
        )
    return result


__all__ = [
    "PromotedDependency",
    "PromotionResult",
    "promote_actions_in_place",
    "promote_dependency_graphs",
]
