"""Unit tests for the joint root+dependency frontier view (SCHEMA.md §7e #1).

A real `gaia pkg add --lkm-paper` materializes a paper into a *dependency
sub-package* whose `depends_on` scaffolds live in the sub-package manifest, not
the root's — so the root-only frontier can never regrow from a survey. These
tests use a SYNTHETIC root graph + dep graph + dep manifest to prove the joint
view:

* a `depends_on` given that is unmaterialized in BOTH packages surfaces as a
  contact against the joint materialized set;
* a `depends_on` given that IS materialized in the dep but is NOT referenced by
  any ROOT edge surfaces as a *pulled-but-unformalized* contact (build-16
  `_pulled_unformalized_contacts` worklist; contract change reconciled
  2026-05-25 — see the test below). A dep-materialized QID that a ROOT edge DOES
  reference is a joint-materialized source, not a contact
  (`test_joint_materialization_in_dep_suppresses_contact`);
* the dep's graph edges + manifest fold into the joint edge set;
* `build_joint_view` degrades gracefully (root-only) when a dep can't be loaded.
"""

from __future__ import annotations

import json
from pathlib import Path

import gaia.engine.packaging as packaging_mod
from gaia.engine.ir.graphs import LocalCanonicalGraph
from gaia.engine.ir.knowledge import Knowledge
from gaia.engine.ir.operator import Operator
from gaia.lkm_explorer.engine.frontier import build_joint_view

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


def _write_root_pyproject_with_dep(root: Path, dist_name: str, dep_rel_path: str) -> None:
    """Write a root pyproject declaring an editable `-gaia` dep BY PATH (§7f-A).

    Mirrors the `[tool.uv.sources] {path, editable}` shape `gaia pkg add` writes,
    so `build_joint_view`'s by-path resolver folds the dep without importing it.
    """
    (root / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "rootpkg-gaia"',
                'version = "0.0.0"',
                f'dependencies = ["{dist_name}"]',
                "[tool.uv.sources]",
                f'{dist_name} = {{ path = "{dep_rel_path}", editable = true }}',
            ]
        ),
        encoding="utf-8",
    )


def _no_import_loader(monkeypatch) -> None:
    """Make the import-based loader explode if reached.

    The by-path route must fold every declared dep so this fallback is never
    consulted (no spurious ModuleNotFoundError warning), matching the real
    `gaia pkg add --lkm-paper` case.
    """

    def _boom(*_a, **_k):  # pragma: no cover - asserts it is never called
        raise AssertionError("import-based loader must not be consulted when deps resolve by path")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _boom)


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
    # Write the dep's compiled ir.json on disk so the by-path resolver loads it.
    (dep_path / ".gaia" / "ir.json").write_text(dep_graph.model_dump_json(), encoding="utf-8")

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

    # Declare the dep editable BY PATH in the root pyproject; the import loader
    # must NOT be consulted (deps resolve by path, as with `pkg add --lkm-paper`).
    _write_root_pyproject_with_dep(root_path, "deppkg-gaia", "../dep")
    _no_import_loader(monkeypatch)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)

    # Joint materialized set = root + dep knowledges.
    assert view.materialized == {root_qid("root_seed"), dep_qid("dep_fact")}
    assert not view.warnings

    contacts = view.extract()
    contact_values = {c.ref["value"] for c in contacts}

    # `dep_concl` (manifest conclusion, unmaterialized) AND `dep_unmaterialized`
    # are contacts via the standard frontier core (referenced-but-unmaterialized).
    assert dep_qid("dep_unmaterialized") in contact_values
    assert dep_qid("dep_concl") in contact_values

    # CONTRACT CHANGE (build 16 + expand-consolidate, reconciled 2026-05-25).
    # Pre-build-16 this asserted `dep_fact` (materialized in the dep) is NOT a
    # contact — "a joint-materialized source is never a contact". Build 16's
    # `JointView._pulled_unformalized_contacts` (the "formalize me" worklist)
    # changed that contract on purpose: a dep claim that IS materialized but is
    # NOT referenced by any ROOT edge is *pulled-but-unformalized* (inert until
    # the agent wires it into the root graph), and the joint view now surfaces it
    # as a `qid` contact tagged `meta.pulled_unformalized` so it ranks/surveys
    # through the normal machinery and retires once formalized. `dep_fact` is
    # exactly that case here (the root references nothing in the dep), so under
    # the current contract it DOES surface — as a pulled-unformalized contact,
    # distinct from the two ordinary unmaterialized contacts above. (Verified
    # legitimate, not a regression: see project INDEX open-thread reconciliation.)
    assert dep_qid("dep_fact") in contact_values
    fact = next(c for c in contacts if c.ref["value"] == dep_qid("dep_fact"))
    assert fact.meta.get("pulled_unformalized") is True
    # The two ordinary contacts are NOT pulled-unformalized (they are
    # genuinely unmaterialized refs, surfaced by the standard frontier core).
    for label in ("dep_unmaterialized", "dep_concl"):
        ordinary = next(c for c in contacts if c.ref["value"] == dep_qid(label))
        assert not ordinary.meta.get("pulled_unformalized")

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
    # The dep materializes `shared`; write its compiled ir.json on disk.
    dep_graph = _graph(DEP_NS, DEP_PKG, [_claim(dep_qid("shared"))])
    (dep_path / ".gaia" / "ir.json").write_text(dep_graph.model_dump_json(), encoding="utf-8")

    _write_root_pyproject_with_dep(root_path, "deppkg-gaia", "../dep")
    _no_import_loader(monkeypatch)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    contact_values = {c.ref["value"] for c in view.extract()}
    assert dep_qid("shared") not in contact_values, "dep-materialized QID must not be a contact"
    assert contact_values == set()
    assert not view.warnings


def test_joint_view_warns_actionably_when_dep_present_but_uncompiled(tmp_path, monkeypatch):
    # A dep declared + located on disk BY PATH but with no compiled .gaia/ir.json
    # must NOT crash and must NOT reach the import loader; it degrades to an
    # actionable `gaia build compile` warning, root-only.
    root_path = tmp_path / "root"
    dep_path = tmp_path / "dep"
    (root_path / ".gaia").mkdir(parents=True)
    dep_path.mkdir(parents=True)  # present on disk, but NO .gaia/ir.json

    root_graph = _graph(
        ROOT_NS,
        ROOT_PKG,
        [_claim(root_qid("a"))],
        operators=[
            Operator(operator="negation", variables=[root_qid("a")], conclusion=root_qid("b"))
        ],
    )
    _write_root_pyproject_with_dep(root_path, "deppkg-gaia", "../dep")
    _no_import_loader(monkeypatch)  # import loader must not be consulted

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert view.warnings
    assert "deppkg-gaia" in view.warnings[0]
    assert "gaia build compile" in view.warnings[0]
    assert view.materialized == {root_qid("a")}
    contact_values = {c.ref["value"] for c in view.extract()}
    assert root_qid("b") in contact_values  # root operator conclusion still a contact


def test_joint_view_falls_back_to_import_loader_only_for_unresolvable_dep(tmp_path, monkeypatch):
    # (§7f-A) A `-gaia` dep declared in pyproject but NOT locatable on disk falls
    # through to the import-based loader as the backstop. When that loader raises
    # ModuleNotFoundError (the original 4c/4d crash), build_joint_view must catch
    # it and degrade gracefully with an actionable warning, not crash.
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
    # Declare a dep whose path/workspace cannot be resolved on disk -> unresolved.
    (root_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "rootpkg-gaia"',
                'version = "0.0.0"',
                'dependencies = ["free-fall-813135-gaia"]',
            ]
        ),
        encoding="utf-8",
    )

    def _raise(*_a, **_k):
        raise ModuleNotFoundError("No module named 'free_fall_813135_gaia'")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _raise)

    # Must not raise — the crash fix.
    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert view.warnings
    assert "ModuleNotFoundError" in view.warnings[0]
    assert "free-fall-813135-gaia" in view.warnings[0]
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

    # No import side-effect: the import-based loader must not be called AT ALL
    # when the dep resolves by path. Tripwire raises if it is reached.
    called = {"n": 0}

    def _tripwire(*_a, **_k):
        called["n"] += 1
        raise AssertionError("import-based loader must not be consulted")

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", _tripwire)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    # The dep was folded BY PATH; the import loader was never touched.
    assert called["n"] == 0
    assert not view.warnings
    assert dep_qid("shared") in view.materialized
    assert dep_path.resolve() in view.package_roots
    # `shared` is materialized in the dep -> NOT a contact.
    contact_values = {c.ref["value"] for c in view.extract()}
    assert dep_qid("shared") not in contact_values
    # `c` (root conclusion, unmaterialized everywhere) still surfaces.
    assert root_qid("c") in contact_values


def test_joint_view_collects_authoritative_paper_id_and_retires_contact(tmp_path, monkeypatch):
    # (theme 004) A pulled LKM paper dep records its authoritative `paper_id` in
    # its `[tool.gaia.source]` pyproject table. build_joint_view must collect it
    # into `materialized_paper_ids`, and an lkm_related contact keyed by that
    # paper_id must then be RETIRED (status surveyed), while an unrelated unpulled
    # contact stays open.
    from gaia.lkm_explorer.engine.observe import promote_materialized_lkm_contacts
    from gaia.lkm_explorer.engine.state import Contact, ExplorationMap

    root_path = tmp_path / "root"
    dep_path = tmp_path / "deps" / "deppkg"
    (root_path / ".gaia").mkdir(parents=True)
    (dep_path / ".gaia").mkdir(parents=True)

    root_graph = _graph(ROOT_NS, ROOT_PKG, [_claim(root_qid("a"))])
    dep_graph = _graph(DEP_NS, DEP_PKG, [_claim(dep_qid("dep_fact"))])
    (dep_path / ".gaia" / "ir.json").write_text(dep_graph.model_dump_json(), encoding="utf-8")

    # The dep is an LKM paper package whose paper_id is LONG (so the dist-dir-name
    # slug, truncated to 18 chars, would NOT round-trip it) — proving the
    # authoritative pyproject read is what matches.
    pulled_paper_id = "9988776655443322110099"
    (dep_path / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                'name = "deppkg-gaia"',
                'version = "0.0.0"',
                "[tool.gaia.source]",
                'provider = "lkm"',
                'kind = "paper"',
                f'paper_id = "{pulled_paper_id}"',
            ]
        ),
        encoding="utf-8",
    )

    # Root pyproject declares the dep editable BY PATH.
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
    _no_import_loader(monkeypatch)

    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert pulled_paper_id in view.materialized_paper_ids

    # A map with two lkm_related contacts: one for the pulled paper, one unpulled.
    other_paper_id = "1234567654321000"
    exploration_map = ExplorationMap(
        frontier=[
            Contact(
                id="ct_pulled",
                ref={"kind": "lkm", "value": pulled_paper_id},
                sources=[{"qid": root_qid("a"), "edge": "lkm_related"}],
                meta={"paper_id": pulled_paper_id},
            ),
            Contact(
                id="ct_open",
                ref={"kind": "lkm", "value": other_paper_id},
                sources=[{"qid": root_qid("a"), "edge": "lkm_related"}],
                meta={"paper_id": other_paper_id},
            ),
        ]
    )

    promoted = promote_materialized_lkm_contacts(
        exploration_map,
        materialized_paper_ids=set(view.materialized_paper_ids),
        survey_round=1,
    )
    assert promoted == [pulled_paper_id]

    by_id = {c.id: c for c in exploration_map.frontier}
    # The pulled paper's contact is retired (surveyed); the other stays open.
    assert by_id["ct_pulled"].status == "surveyed"
    assert by_id["ct_open"].status == "open"
    # And it is no longer in the OPEN frontier.
    open_papers = {c.ref["value"] for c in exploration_map.frontier if c.status == "open"}
    assert pulled_paper_id not in open_papers
    assert other_paper_id in open_papers


def test_joint_view_root_only_when_no_deps(tmp_path, monkeypatch):
    root_path = tmp_path / "root"
    (root_path / ".gaia").mkdir(parents=True)
    root_graph = _graph(ROOT_NS, ROOT_PKG, [_claim(root_qid("a"))])

    monkeypatch.setattr(packaging_mod, "load_dependency_compiled_graphs", lambda *_a, **_k: [])
    view = build_joint_view(root_path, root_graph, project_config={}, depth=-1)
    assert view.materialized == {root_qid("a")}
    assert view.package_roots == [root_path.resolve()]
    assert not view.warnings
