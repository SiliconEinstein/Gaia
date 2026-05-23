"""Frontier extraction — derive the exploration frontier from a package's IR.

This is build 2 of the exploration machine (SCHEMA.md §7a). It turns a package's
in-memory IR (a :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph`) into the set
of *contacts* that make up the frontier: reference *targets* a surveyed node
points at but which have no materialized ``Knowledge`` body yet.

Semantics (SCHEMA.md §7a, authoritative):

* The **materialized set** = the QIDs that have a ``Knowledge`` node in the IR.
* Every inter-node reference is an **edge by Knowledge ID**. For each edge, any
  referenced QID **not** in the materialized set is a **contact**; its ``sources``
  are the *materialized* co-referenced QIDs in that same edge (the surveyed
  territory the contact is reachable from), tagged with the edge kind.
* Multiple edges to the same contact merge into one :class:`Contact` with the
  union of ``sources``.

Edge sources and their ``edge`` kind:

============================================================  ===================
IR source                                                     edge kind
============================================================  ===================
``Operator`` (standalone + inside ``FormalStrategy``)         ``operator_target``
``Strategy`` (``premises`` + ``conclusion`` + ``background``) ``strategy_given``
``Knowledge.sub_knowledge``                                   ``sub_knowledge``
``lkm_materialize`` ``depends_on`` scaffold                   ``depends_on``
============================================================  ===================

``CompositeStrategy.sub_strategies`` are ``strategy_id`` references (not
Knowledge) and are skipped. ``lkm_related`` contacts are survey-time only
(co-retrieved LKM nodes, not IR-derived) and are out of scope for this build.

The ``depends_on`` scaffold is a special case: ``lkm_materialize`` lowers each
factor into a ``depends_on(...)`` DSL call, which the compiler records **not** in
the ``LocalCanonicalGraph`` but in a sibling *formalization manifest*
(``.gaia/formalization_manifest.json`` / ``CompiledPackage.formalization_manifest``)
as ``{"kind": "depends_on", "conclusion": <qid>, "given": [<qid>, ...],
"background": [<qid>, ...]}``. So this module accepts that manifest as an
*optional companion* to the graph and folds its ``depends_on`` records into the
frontier under the ``depends_on`` edge. When no manifest is passed, the
``depends_on`` edge simply contributes nothing.

This module is **pure**: :func:`extract_frontier` reads the IR and returns a
fresh list of :class:`Contact`; :func:`reconcile_frontier` folds that list into
an :class:`ExplorationMap` without resurrecting or deleting promoted/closed
contacts. No scoring happens here — ``score`` / ``score_features`` stay at their
schema defaults (``None`` / ``{}``) until build 3, the scorer.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from gaia.engine.exploration.state import Contact, mint_contact_id

if TYPE_CHECKING:
    from gaia.engine.exploration.state import ExplorationMap
    from gaia.engine.ir.graphs import LocalCanonicalGraph

# §7a edge kinds this build derives from the IR (``lkm_related`` is survey-time
# only and out of scope; it is intentionally absent here).
EDGE_OPERATOR_TARGET = "operator_target"
EDGE_STRATEGY_GIVEN = "strategy_given"
EDGE_SUB_KNOWLEDGE = "sub_knowledge"
EDGE_DEPENDS_ON = "depends_on"


def _materialized_qids(ir: LocalCanonicalGraph) -> set[str]:
    """Return the QIDs that have a ``Knowledge`` body in the IR (the surveyed set).

    A ``Knowledge`` node is materialized iff it carries a resolved ``id`` (a QID);
    ``LocalCanonicalGraph`` auto-assigns one to every label-only node at
    validation time, so in a compiled graph this is simply every node's ``id``.
    """
    return {k.id for k in ir.knowledges if k.id is not None}


def _iter_operators(ir: LocalCanonicalGraph) -> list[Any]:
    """Yield every Operator the IR carries: standalone + inside FormalStrategy.

    Standalone operators live on ``ir.operators``; formalized strategies embed
    further operators in ``FormalStrategy.formal_expr.operators``. Both are
    reference edges of kind ``operator_target`` (SCHEMA.md §7a).
    """
    operators: list[Any] = list(ir.operators)
    for strategy in ir.strategies:
        formal_expr = getattr(strategy, "formal_expr", None)
        if formal_expr is not None:
            operators.extend(formal_expr.operators)
    return operators


def _edges_from_ir(
    ir: LocalCanonicalGraph,
    formalization_manifest: dict[str, Any] | None,
) -> list[tuple[str, list[str]]]:
    """Collect every reference edge as ``(edge_kind, [referenced_qids])``.

    Each tuple is one edge: its referenced QIDs are the full set the edge ties
    together (both materialized and not). The caller splits them into the
    contact (unmaterialized) and its sources (materialized co-references).
    """
    edges: list[tuple[str, list[str]]] = []

    # Operators (standalone + embedded): variables[] + conclusion.
    for operator in _iter_operators(ir):
        op_refs: list[str] = [*operator.variables, operator.conclusion]
        edges.append((EDGE_OPERATOR_TARGET, op_refs))

    # Strategies: premises[] + conclusion + background[]. CompositeStrategy
    # carries its own premises/conclusion too; only its ``sub_strategies`` (which
    # are strategy_id refs, not Knowledge) are skipped — and we never read them.
    for strategy in ir.strategies:
        strat_refs: list[str] = list(strategy.premises)
        if strategy.conclusion is not None:
            strat_refs.append(strategy.conclusion)
        if strategy.background:
            strat_refs.extend(strategy.background)
        edges.append((EDGE_STRATEGY_GIVEN, strat_refs))

    # Knowledge.sub_knowledge[]: a node naming its constituent sub-knowledge.
    for knowledge in ir.knowledges:
        sub_knowledge = knowledge.sub_knowledge
        if not sub_knowledge or knowledge.id is None:
            continue
        # The owning node is itself a (materialized) co-reference, so a contact
        # reached through sub_knowledge records the parent as its source.
        edges.append((EDGE_SUB_KNOWLEDGE, [knowledge.id, *sub_knowledge]))

    # depends_on scaffolds — sourced from the formalization manifest, which is a
    # sibling artifact to the IR (lkm_materialize lowers each factor to a
    # depends_on(...) record there, not into LocalCanonicalGraph). conclusion +
    # given[] + background[] are the co-referenced QIDs of the edge.
    if formalization_manifest:
        for record in formalization_manifest.get("dependencies", []):
            if not isinstance(record, dict) or record.get("kind") != EDGE_DEPENDS_ON:
                continue
            dep_refs: list[str] = []
            conclusion = record.get("conclusion")
            if isinstance(conclusion, str):
                dep_refs.append(conclusion)
            dep_refs.extend(g for g in record.get("given", []) if isinstance(g, str))
            dep_refs.extend(b for b in record.get("background", []) if isinstance(b, str))
            edges.append((EDGE_DEPENDS_ON, dep_refs))

    return edges


def extract_frontier(
    ir: LocalCanonicalGraph,
    exploration_map: ExplorationMap | None = None,
    *,
    formalization_manifest: dict[str, Any] | None = None,
) -> list[Contact]:
    """Derive the frontier from a package's IR (SCHEMA.md §7a). Pure function.

    Walks every reference edge in the IR (operators, strategies, sub_knowledge,
    and — when supplied — ``depends_on`` scaffolds from the formalization
    manifest). Any referenced QID **not** in the materialized set is a contact;
    its ``sources`` are the materialized co-referenced QIDs in that same edge,
    each tagged with the edge kind. Multiple edges to one contact merge into a
    single :class:`Contact` with the union of ``sources``.

    Args:
        ir: The in-memory package IR — a
            :class:`~gaia.engine.ir.graphs.LocalCanonicalGraph` whose
            ``knowledges`` define the materialized set and whose
            ``operators`` / ``strategies`` carry the reference edges.
        exploration_map: Optional existing map. When given, a contact that
            already exists for a QID-ref reuses that contact's ``id`` (and its
            ``discovered_round``), so re-extraction is stable across rounds. The
            map is **not** mutated here — see :func:`reconcile_frontier`.
        formalization_manifest: Optional companion manifest
            (``{"dependencies": [...], "materializations": [...]}``) carrying the
            ``depends_on`` scaffold records that ``lkm_materialize`` produces.
            When omitted, the ``depends_on`` edge contributes no contacts.

    Returns:
        A fresh list of :class:`Contact`, one per unmaterialized referenced QID,
        with merged ``sources``. ``score`` / ``score_features`` are left at their
        schema defaults — scoring is build 3.
    """
    materialized = _materialized_qids(ir)
    edges = _edges_from_ir(ir, formalization_manifest)
    return _frontier_from_edges(materialized, edges, exploration_map=exploration_map)


def _frontier_from_edges(
    materialized: set[str],
    edges: list[tuple[str, list[str]]],
    *,
    exploration_map: ExplorationMap | None = None,
) -> list[Contact]:
    """Derive the frontier from a ``(materialized_qids, edges)`` pair.

    The shared core of frontier extraction (SCHEMA.md §7a). Both the single-graph
    :func:`extract_frontier` and the joint :func:`build_joint_view` reduce their
    inputs to a materialized-QID set + a list of ``(edge_kind, [referenced_qids])``
    edges and call this. Any referenced QID not in ``materialized`` is a contact;
    its ``sources`` are the materialized co-references in that same edge, tagged
    with the edge kind. Multiple edges to one contact merge their sources.

    Args:
        materialized: The materialized-QID set (the surveyed territory).
        edges: ``(edge_kind, [referenced_qids])`` reference edges to walk.
        exploration_map: Optional existing map; a contact already on its frontier
            for a QID-ref reuses that contact's ``id`` + ``discovered_round`` so
            re-extraction is stable. The map is not mutated.

    Returns:
        A fresh sorted list of :class:`Contact`, one per unmaterialized QID.
    """
    # Pre-index existing QID-ref contacts so re-extraction reuses their ids.
    existing_by_qid: dict[str, Contact] = {}
    if exploration_map is not None:
        for contact in exploration_map.frontier:
            if contact.ref.get("kind") == "qid":
                existing_by_qid[str(contact.ref["value"])] = contact

    # qid -> ordered, de-duplicated list of (source_qid, edge) sources.
    sources_by_qid: dict[str, list[dict[str, Any]]] = {}
    seen_source: dict[str, set[tuple[str, str]]] = {}

    for edge_kind, refs in edges:
        unmaterialized = [r for r in refs if r not in materialized]
        if not unmaterialized:
            continue
        co_referenced_sources = [r for r in refs if r in materialized]
        for target in unmaterialized:
            bucket = sources_by_qid.setdefault(target, [])
            seen = seen_source.setdefault(target, set())
            for source_qid in co_referenced_sources:
                key = (source_qid, edge_kind)
                if key in seen:
                    continue
                seen.add(key)
                bucket.append({"qid": source_qid, "edge": edge_kind})

    contacts: list[Contact] = []
    for qid in sorted(sources_by_qid):
        prior = existing_by_qid.get(qid)
        contacts.append(
            Contact(
                id=prior.id if prior is not None else mint_contact_id(),
                ref={"kind": "qid", "value": qid},
                sources=sources_by_qid[qid],
                discovered_round=prior.discovered_round if prior is not None else 0,
            )
        )
    return contacts


def reconcile_frontier(
    exploration_map: ExplorationMap,
    extracted: list[Contact],
    *,
    discovered_round: int | None = None,
) -> ExplorationMap:
    """Fold a freshly extracted frontier into an :class:`ExplorationMap` in place.

    Per SCHEMA.md §7a, reconciliation is additive and non-destructive:

    * **New** contacts (QID not already on the frontier) are appended, stamped
      with ``discovered_round`` when given.
    * **Open** existing contacts have their ``sources`` refreshed from the
      extraction (the IR is authoritative for reachability).
    * **Promoted / closed** contacts (``status`` in ``surveyed`` / ``skipped`` /
      ``deferred``) are left **completely intact** — never resurrected to
      ``open``, never deleted, and their ``sources`` are not touched. They are
      kept for round legibility.

    Only QID-ref contacts are reconciled (extraction yields only those); any
    LKM-handle contacts already on the map are untouched.

    Args:
        exploration_map: The map to update (mutated in place and returned).
        extracted: The output of :func:`extract_frontier`.
        discovered_round: Round to stamp on newly added contacts. When ``None``,
            a new contact keeps the ``discovered_round`` it was extracted with.

    Returns:
        The same ``exploration_map``, updated.
    """
    by_qid: dict[str, Contact] = {}
    for contact in exploration_map.frontier:
        if contact.ref.get("kind") == "qid":
            by_qid[str(contact.ref["value"])] = contact

    for fresh in extracted:
        qid = str(fresh.ref["value"])
        existing = by_qid.get(qid)
        if existing is None:
            if discovered_round is not None:
                fresh.discovered_round = discovered_round
            exploration_map.frontier.append(fresh)
            by_qid[qid] = fresh
            continue
        # Leave promoted/closed contacts entirely intact.
        if existing.status != "open":
            continue
        # Refresh the open contact's reachability from the authoritative IR.
        existing.sources = [dict(s) for s in fresh.sources]

    return exploration_map


# --------------------------------------------------------------------------- #
# Joint dependency view (build 4c — SCHEMA.md §7e)                            #
# --------------------------------------------------------------------------- #
#
# ``gaia pkg add --lkm-paper`` materializes a paper into a *dependency
# sub-package* (``<root>/.gaia/lkm_packages/<dist>/``, added as an editable
# ``-gaia`` dep) whose ``depends_on`` scaffolds live in the *sub-package*
# manifest, not the root's. So a frontier derived from the root graph alone can
# never regrow from a real survey. The **joint view** loads the root graph + its
# transitive ``-gaia`` deps, unions their materialized QID sets, and folds every
# package's edges (graph edges + ``depends_on`` manifest records) into one edge
# list. Contacts are then derived against the *joint* materialized set — a QID
# referenced anywhere is a contact iff it is materialized *nowhere*.


def _load_manifest_dict(root: Path) -> dict[str, Any] | None:
    """Read a package's ``.gaia/formalization_manifest.json`` if present.

    Returns ``None`` when the manifest is absent or unreadable (a package with no
    ``depends_on`` scaffolds simply contributes no ``depends_on`` edges).
    """
    p = root / ".gaia" / "formalization_manifest.json"
    if not p.exists():
        return None
    try:
        loaded = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return dict(loaded) if isinstance(loaded, dict) else None


@dataclass
class JointView:
    """The joint root+dependency exploration view (SCHEMA.md §7e).

    Aggregates the materialized-QID set and the reference edges across the root
    package and every transitive ``-gaia`` dependency, so frontier extraction and
    scorer adjacency span the whole cross-package graph rather than the root
    alone. ``warnings`` collects non-fatal degradations (e.g. a dep that is not
    compiled yet and was skipped).

    Attributes:
        materialized: Union of every package's materialized QIDs.
        edges: Union of every package's ``(edge_kind, [referenced_qids])`` edges
            (graph edges + ``depends_on`` manifest records), used by both the
            frontier core and the scorer adjacency.
        package_roots: The on-disk roots that contributed (root + deps), in load
            order, for legibility/debugging.
        warnings: Human-readable notes about anything skipped or degraded.
    """

    materialized: set[str] = field(default_factory=set)
    edges: list[tuple[str, list[str]]] = field(default_factory=list)
    package_roots: list[Path] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def extract(self, exploration_map: ExplorationMap | None = None) -> list[Contact]:
        """Derive the frontier from this joint view (shares the §7a core)."""
        return _frontier_from_edges(self.materialized, self.edges, exploration_map=exploration_map)


def build_joint_view(
    root_path: str | Path,
    root_graph: LocalCanonicalGraph,
    *,
    project_config: dict[str, Any],
    depth: int = -1,
) -> JointView:
    """Build the joint root+dependency frontier view (SCHEMA.md §7e #1, §7f A).

    Loads the root graph's transitive ``-gaia`` dependency graphs via
    :func:`gaia.engine.packaging.load_dependency_compiled_graphs` (``depth=-1`` by
    default), then for the root **and** every dep:

    * adds its materialized QIDs to the joint materialized set;
    * folds its graph edges (``_edges_from_ir``) and the ``depends_on`` records
      from its ``.gaia/formalization_manifest.json`` into the joint edge list.

    Robustness (SCHEMA.md §7e / §7f-A): the import-based loader resolves a dep
    root via ``importlib.import_module``, which raises ``ModuleNotFoundError`` /
    ``ImportError`` (NOT ``GaiaPackagingError``) for a real ``pkg add --lkm-paper``
    editable dep that is present on disk but not importable from the run
    interpreter — that crashed ``explore frontier`` in the 4c re-verify. So we
    **first** resolve deps **by path** from the root ``pyproject.toml``
    (``[tool.uv.sources]`` editable paths + ``[tool.uv.workspace]`` members),
    reading each dep's ``.gaia/ir.json`` directly without importing anything; a
    present-on-disk dep is folded in regardless of importability. The
    import-based loader is then used only to catch any additional deps the
    by-path scan missed, and **all** of ``GaiaPackagingError`` /
    ``ModuleNotFoundError`` / ``ImportError`` degrade that step to
    skipped-with-warning rather than crashing.

    Args:
        root_path: The root package directory (its manifest is read for
            ``depends_on`` edges; its ``pyproject.toml`` drives by-path dep
            resolution).
        root_graph: The already-compiled root ``LocalCanonicalGraph``.
        project_config: The root package's ``[project]`` pyproject section (the
            seam ``load_dependency_compiled_graphs`` expects).
        depth: Transitive depth passed through to the loader (``-1`` = unlimited).

    Returns:
        A :class:`JointView` spanning the root + all loadable deps.
    """
    from gaia.engine.packaging import GaiaPackagingError, load_dependency_compiled_graphs

    view = JointView()
    folded_roots: set[Path] = set()

    def _fold(graph: LocalCanonicalGraph, root: Path) -> None:
        resolved = root.resolve()
        if resolved in folded_roots:
            return
        folded_roots.add(resolved)
        view.materialized |= _materialized_qids(graph)
        view.edges.extend(_edges_from_ir(graph, _load_manifest_dict(resolved)))
        view.package_roots.append(resolved)

    root_resolved = Path(root_path).resolve()
    _fold(root_graph, root_resolved)

    # (§7f-A) Resolve present-on-disk deps BY PATH first — no import_module — so a
    # real `pkg add --lkm-paper` editable dep is folded in even when it is not
    # importable from this interpreter.
    for dep_root, dep_graph in _load_deps_by_path(root_resolved):
        _fold(dep_graph, dep_root)

    # The import-based loader catches anything the by-path scan missed; ANY of
    # GaiaPackagingError / ModuleNotFoundError / ImportError degrades to a warning
    # rather than crashing (§7f-A: ModuleNotFoundError is the 4c crash).
    try:
        deps = load_dependency_compiled_graphs(project_config, depth=depth)
    except (GaiaPackagingError, ImportError) as exc:
        view.warnings.append(
            f"skipped some dependency graphs ({type(exc).__name__}: {exc}); "
            "frontier uses the root + any disk-resolved deps this round"
        )
        return view

    for dep in deps:
        _fold(dep.graph, Path(dep.root).resolve())

    return view


def _load_deps_by_path(root: Path) -> list[tuple[Path, LocalCanonicalGraph]]:
    """Resolve ``-gaia`` dep roots on disk from the root ``pyproject.toml`` (§7f-A).

    Reads the root package's own ``pyproject.toml`` and resolves every
    ``…-gaia`` ``[project].dependency`` to a directory **by path** — preferring a
    ``[tool.uv.sources]`` editable ``{path = …}`` entry, then a
    ``[tool.uv.workspace].members`` glob match — without ever importing the dep.
    Each located dep with a compiled ``.gaia/ir.json`` is loaded and returned.

    This deliberately avoids ``importlib.import_module`` (the source of the 4c
    ``ModuleNotFoundError`` crash for a present-but-uninstalled editable dep). A
    dep that can't be located on disk, has no ``.gaia/ir.json``, or whose IR
    won't parse is simply omitted — the import-based loader (and its warning
    path) is the backstop.

    Args:
        root: The resolved root package directory.

    Returns:
        ``(dep_root, dep_graph)`` pairs for every disk-resolvable, compiled dep.
    """
    parsed = _read_root_pyproject(root)
    if parsed is None:
        return []
    dependencies, uv_sources, member_globs = parsed

    out: list[tuple[Path, LocalCanonicalGraph]] = []
    seen_roots: set[Path] = set()
    for raw in dependencies:
        if not isinstance(raw, str):
            continue
        dist_name = _dep_dist_name(raw)
        if dist_name is None or not dist_name.endswith("-gaia"):
            continue
        dep_root = _resolve_dep_root_by_path(root, dist_name, uv_sources, member_globs)
        if dep_root is None or dep_root.resolve() in seen_roots:
            continue
        dep_root = dep_root.resolve()
        seen_roots.add(dep_root)
        loaded = _load_dep_graph(dep_root)
        if loaded is not None:
            out.append((dep_root, loaded))
    return out


def _read_root_pyproject(
    root: Path,
) -> tuple[list[Any], dict[str, Any], list[Any]] | None:
    """Parse the root ``pyproject.toml`` into ``(dependencies, uv_sources, members)``.

    Returns ``None`` when the file is absent or unparseable, so the caller treats
    the package as having no by-path-resolvable deps.
    """
    import tomllib

    pyproject = root / "pyproject.toml"
    if not pyproject.exists():
        return None
    try:
        config = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError):
        return None

    project = config.get("project", {})
    dependencies = project.get("dependencies", []) if isinstance(project, dict) else []
    if not isinstance(dependencies, list):
        dependencies = []

    tool = config.get("tool")
    uv = tool.get("uv", {}) if isinstance(tool, dict) else {}
    uv_sources = uv.get("sources", {}) if isinstance(uv, dict) else {}
    if not isinstance(uv_sources, dict):
        uv_sources = {}
    workspace = uv.get("workspace", {}) if isinstance(uv, dict) else {}
    member_globs = workspace.get("members", []) if isinstance(workspace, dict) else []
    if not isinstance(member_globs, list):
        member_globs = []
    return dependencies, uv_sources, member_globs


def _load_dep_graph(dep_root: Path) -> LocalCanonicalGraph | None:
    """Load a dep's compiled ``.gaia/ir.json`` graph by path, or ``None``."""
    from gaia.engine.ir.graphs import LocalCanonicalGraph

    ir_path = dep_root / ".gaia" / "ir.json"
    if not ir_path.exists():
        return None
    try:
        ir_data = json.loads(ir_path.read_text(encoding="utf-8"))
        return LocalCanonicalGraph.model_validate(ir_data)
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _dep_dist_name(requirement: str) -> str | None:
    """Extract the distribution name from a ``[project].dependencies`` entry.

    Tolerant of the full PEP 508 grammar (extras / specifiers / markers); returns
    the bare distribution name (e.g. ``"foo-813135-gaia"``) or ``None`` when the
    requirement is unparseable.
    """
    from packaging.requirements import InvalidRequirement, Requirement

    try:
        return Requirement(requirement).name
    except InvalidRequirement:
        return None


def _resolve_dep_root_by_path(
    root: Path,
    dist_name: str,
    uv_sources: dict[str, Any],
    member_globs: list[Any],
) -> Path | None:
    """Locate a dep's package root on disk (no import) — sources, then workspace.

    Resolution order (SCHEMA.md §7f-A):

    1. ``[tool.uv.sources][<dist_name>]`` editable ``{path = …}`` (relative to the
       root package dir) — the form ``gaia pkg add --lkm-paper`` writes;
    2. a ``[tool.uv.workspace].members`` glob whose matched directory's
       ``pyproject.toml`` declares ``[project].name == dist_name``.

    Args:
        root: The resolved root package directory (paths resolve against it).
        dist_name: The dependency distribution name to locate.
        uv_sources: The root's ``[tool.uv.sources]`` table.
        member_globs: The root's ``[tool.uv.workspace].members`` globs.

    Returns:
        The dep package directory, or ``None`` if not resolvable on disk.
    """
    source = uv_sources.get(dist_name)
    if isinstance(source, dict):
        raw_path = source.get("path")
        if isinstance(raw_path, str) and raw_path:
            candidate = Path(raw_path)
            if not candidate.is_absolute():
                candidate = root / candidate
            if candidate.exists():
                return candidate

    import tomllib

    for glob in member_globs:
        if not isinstance(glob, str):
            continue
        for member_dir in sorted(root.glob(glob)):
            if not member_dir.is_dir():
                continue
            member_pyproject = member_dir / "pyproject.toml"
            if not member_pyproject.exists():
                continue
            try:
                member_cfg = tomllib.loads(member_pyproject.read_text(encoding="utf-8"))
            except (OSError, tomllib.TOMLDecodeError):
                continue
            member_project = member_cfg.get("project", {})
            if isinstance(member_project, dict) and member_project.get("name") == dist_name:
                return member_dir
    return None
