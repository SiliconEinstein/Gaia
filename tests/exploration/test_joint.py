"""Unit tests for the joint root+dependency frontier view (SCHEMA.md §7e #1).

A real `gaia pkg add --lkm-paper` materializes a paper into a *dependency
sub-package* whose `depends_on` scaffolds live in the sub-package manifest, not
the root's — so the root-only frontier can never regrow from a survey. These
tests use a SYNTHETIC root graph + dep graph + dep manifest to prove the joint
view:

* a `depends_on` given that is unmaterialized in BOTH packages surfaces as a
  contact against the joint materialized set;
* a `depends_on` given that IS materialized in the dep does NOT surface (it is
  a joint-materialized source, not a contact);
* the dep's graph edges + manifest fold into the joint edge set;
* `build_joint_view` degrades gracefully (root-only) when a dep can't be loaded.
"""

from __future__ import annotations

import json
from pathlib import Path

import gaia.engine.packaging as packaging_mod
from gaia.engine.exploration.frontier import build_joint_view
from gaia.engine.ir.graphs import LocalCanonicalGraph
from gaia.engine.ir.knowledge import Knowledge
from gaia.engine.ir.operator import Operator

ROOT_NS, ROOT_PKG = "example", "rootpkg"
DEP_NS, DEP_PKG = "lkm", "deppkg"


def _qid(ns: str, pkg: str, label: str) -> str:
    return f"{ns}:{pkg}::{label}"


def root_qid(label: str) -> str:
    return _qid(ROOT_NS, ROOT_PKG, label)


def dep_qid(label: str) -> str:
    return _qid(DEP_NS, DEP_PKG, label)


def _claim(qid: str) -> Knowledge:
    return Knowledge(id=qid, type="claim", content=qid)


def _graph(ns: str, pkg: str, knowledges: list[Knowledge], operators=None) -> LocalCanonicalGraph:
    return LocalCanonicalGraph(
        namespace=ns,
        package_name=pkg,
        knowledges=knowledges,
        operators=operators or [],
        strategies=[],
    )


def _write_manifest(root: Path, dependencies: list[dict]) -> None:
    gaia_dir = root / ".gaia"
    gaia_dir.mkdir(parents=True, exist_ok=True)
    (gaia_dir / "formalization_manifest.json").write_text(
        json.dumps({"version": 1, "dependencies": dependencies, "materializations": []}),
        encoding="utf-8",
    )


class _FakeDep:
    """Stand-in for packaging.DependencyGraph (only the fields the joint reads)."""

    def __init__(self, import_name: str, dist_name: str, root: Path, graph: LocalCanonicalGraph):
        self.import_name = import_name
        self.dist_name = dist_name
        self.root = root
        self.graph = graph


def test_joint_view_surfaces_cross_package_unmaterialized_contact(tmp_path, monkeypatch):
    # Root has one claim (root_seed). Dep has one claim (dep_fact) and a manifest
    # depends_on whose given `dep_unmaterialized` is NOT a Knowledge in EITHER
    # package -> it must surface as a contact; `dep_fact` (materialized in the
    # dep) must NOT.
    root_path = tmp_path / "root"
    dep_path = tmp_path / "dep"
    (root_path / ".gaia").mkdir(parents=True)
    (dep_path / ".gaia").mkdir(parents=True)

    root_graph = _graph(ROOT_NS, ROOT_PKG, [_claim(root_qid("root_seed"))])
    dep_graph = _graph(DEP_NS, DEP_PKG, [_claim(dep_qid("dep_fact"))])

    # Dep manifest: conclusion + a materialized given (dep_fact) + an
    # unmaterialized given (dep_unmaterialized).
    _write_manifest(
        dep_path,
        [
            {
                "kind": "depends_on",
                "conclusion": dep_qid("dep_concl"),
                "given": [dep_qid("dep_fact"), dep_qid("dep_unmaterialized")],
                "background": [],
            }
        ],
    )

    monkeypatch.setattr(
        packaging_mod,
        "load_dependency_compiled_graphs",
        lambda *_a, **_k: [_FakeDep("deppkg", "deppkg-gaia", dep_path, dep_graph)],
    )

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)

    # Joint materialized set = root + dep knowledges.
    assert view.materialized == {root_qid("root_seed"), dep_qid("dep_fact")}
    assert not view.warnings

    contacts = view.extract()
    contact_values = {c.ref["value"] for c in contacts}

    # `dep_concl` (manifest conclusion, unmaterialized) AND `dep_unmaterialized`
    # are contacts; `dep_fact` is materialized in the dep -> NOT a contact.
    assert dep_qid("dep_unmaterialized") in contact_values
    assert dep_qid("dep_concl") in contact_values
    assert dep_qid("dep_fact") not in contact_values

    # The unmaterialized contact is sourced by the materialized co-reference
    # (dep_fact) under the depends_on edge.
    unmat = next(c for c in contacts if c.ref["value"] == dep_qid("dep_unmaterialized"))
    assert (dep_qid("dep_fact"), "depends_on") in {(s["qid"], s["edge"]) for s in unmat.sources}


def test_joint_materialization_in_dep_suppresses_contact(tmp_path, monkeypatch):
    # A QID referenced by a root operator but materialized in the DEP must NOT be
    # a contact in the joint view (it would be a contact in a root-only view).
    root_path = tmp_path / "root"
    dep_path = tmp_path / "dep"
    (root_path / ".gaia").mkdir(parents=True)
    (dep_path / ".gaia").mkdir(parents=True)

    # Root operator references a dep-owned QID as a variable.
    root_graph = _graph(
        ROOT_NS,
        ROOT_PKG,
        [_claim(root_qid("a")), _claim(root_qid("c"))],
        operators=[
            Operator(
                operator="implication",
                variables=[root_qid("a"), dep_qid("shared")],
                conclusion=root_qid("c"),
            )
        ],
    )
    # The dep materializes `shared`.
    dep_graph = _graph(DEP_NS, DEP_PKG, [_claim(dep_qid("shared"))])

    monkeypatch.setattr(
        packaging_mod,
        "load_dependency_compiled_graphs",
        lambda *_a, **_k: [_FakeDep("deppkg", "deppkg-gaia", dep_path, dep_graph)],
    )

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    contact_values = {c.ref["value"] for c in view.extract()}
    assert dep_qid("shared") not in contact_values, "dep-materialized QID must not be a contact"
    assert contact_values == set()


def test_joint_view_degrades_when_dep_not_compiled(tmp_path, monkeypatch):
    from gaia.engine.packaging import GaiaPackagingError

    root_path = tmp_path / "root"
    (root_path / ".gaia").mkdir(parents=True)
    root_graph = _graph(
        ROOT_NS,
        ROOT_PKG,
        [_claim(root_qid("a"))],
        operators=[
            Operator(operator="negation", variables=[root_qid("a")], conclusion=root_qid("b"))
        ],
    )

    def _raise(*_a, **_k):
        raise GaiaPackagingError("dep missing .gaia/ir.json; run gaia build compile")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _raise)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    # Degrades to root-only: warning emitted, root edges still present.
    assert view.warnings
    assert "GaiaPackagingError" in view.warnings[0]
    assert view.materialized == {root_qid("a")}
    contact_values = {c.ref["value"] for c in view.extract()}
    assert root_qid("b") in contact_values  # root operator conclusion still a contact


def test_joint_view_degrades_on_module_not_found(tmp_path, monkeypatch):
    # (§7f-A) The 4c crash: load_dependency_compiled_graphs -> import_module
    # raises ModuleNotFoundError (NOT GaiaPackagingError) for a real
    # `pkg add --lkm-paper` editable dep not importable from the run interpreter.
    # build_joint_view must catch it and degrade gracefully, not crash.
    root_path = tmp_path / "root"
    (root_path / ".gaia").mkdir(parents=True)
    root_graph = _graph(
        ROOT_NS,
        ROOT_PKG,
        [_claim(root_qid("a"))],
        operators=[
            Operator(operator="negation", variables=[root_qid("a")], conclusion=root_qid("b"))
        ],
    )

    def _raise(*_a, **_k):
        raise ModuleNotFoundError("No module named 'free_fall_813135_gaia'")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _raise)

    # Must not raise — the crash fix.
    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert view.warnings
    assert "ModuleNotFoundError" in view.warnings[0]
    assert view.materialized == {root_qid("a")}
    assert root_qid("b") in {c.ref["value"] for c in view.extract()}


def test_joint_view_resolves_dep_by_path_without_import(tmp_path, monkeypatch):
    # (§7f-A) A present-on-disk editable dep declared via [tool.uv.sources] is
    # folded in BY PATH (reading its .gaia/ir.json) even though the import-based
    # loader can't import it (raises ModuleNotFoundError). The dep's materialized
    # QID suppresses what would otherwise be a root contact.
    root_path = tmp_path / "root"
    dep_path = tmp_path / "deps" / "deppkg"
    (root_path / ".gaia").mkdir(parents=True)
    (dep_path / ".gaia").mkdir(parents=True)

    # Root operator references a dep-owned QID -> would be a contact root-only.
    root_graph = _graph(
        ROOT_NS,
        ROOT_PKG,
        [_claim(root_qid("a"))],
        operators=[
            Operator(
                operator="implication",
                variables=[root_qid("a"), dep_qid("shared")],
                conclusion=root_qid("c"),
            )
        ],
    )
    # The dep materializes `shared`; write its compiled ir.json to disk.
    dep_graph = _graph(DEP_NS, DEP_PKG, [_claim(dep_qid("shared"))])
    (dep_path / ".gaia" / "ir.json").write_text(dep_graph.model_dump_json(), encoding="utf-8")

    # Root pyproject points at the dep editable BY PATH via [tool.uv.sources].
    (root_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "rootpkg-gaia"',
                'version = "0.0.0"',
                'dependencies = ["deppkg-gaia"]',
                "[tool.uv.sources]",
                'deppkg-gaia = { path = "../deps/deppkg", editable = true }',
            ]
        ),
        encoding="utf-8",
    )

    # The import-based loader CANNOT import the dep — simulate the crash path.
    def _raise(*_a, **_k):
        raise ModuleNotFoundError("No module named 'deppkg'")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _raise)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    # The dep was folded BY PATH despite the import failure.
    assert dep_qid("shared") in view.materialized
    assert dep_path.resolve() in view.package_roots
    # `shared` is materialized in the dep -> NOT a contact.
    contact_values = {c.ref["value"] for c in view.extract()}
    assert dep_qid("shared") not in contact_values
    # `c` (root conclusion, unmaterialized everywhere) still surfaces.
    assert root_qid("c") in contact_values


def test_joint_view_root_only_when_no_deps(tmp_path, monkeypatch):
    root_path = tmp_path / "root"
    (root_path / ".gaia").mkdir(parents=True)
    root_graph = _graph(ROOT_NS, ROOT_PKG, [_claim(root_qid("a"))])

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", lambda *_a, **_k: [])
    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert view.materialized == {root_qid("a")}
    assert view.package_roots == [root_path.resolve()]
    assert not view.warnings
