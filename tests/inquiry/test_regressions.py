"""Regression tests for inquiry review integration bugs."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from gaia.inquiry.focus import FocusBinding
from gaia.inquiry.review import run_review
from gaia.inquiry.state import load_state


def _write_pkg(pkg_dir: Path, body: str, name: str = "regress_pkg") -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir(exist_ok=True)
    (src / "__init__.py").write_text(body, encoding="utf-8")


def test_semantic_diff_tracks_added_strategy_by_strategy_id(tmp_path: Path) -> None:
    pkg = tmp_path / "p"
    base_body = (
        "from gaia.lang import claim, support\n"
        'a = claim("A", metadata={"prior": 0.5})\n'
        'b = claim("B", metadata={"prior": 0.7})\n'
        'c = claim("C")\n'
        "s1 = support(premises=[a], conclusion=c)\n"
        '__all__ = ["a", "b", "c", "s1"]\n'
    )
    _write_pkg(pkg, base_body)
    first = run_review(pkg, no_infer=True)

    updated_body = base_body.replace(
        '__all__ = ["a", "b", "c", "s1"]\n',
        's2 = support(premises=[b], conclusion=c)\n__all__ = ["a", "b", "c", "s1", "s2"]\n',
    )
    (pkg / "regress_pkg" / "__init__.py").write_text(updated_body, encoding="utf-8")

    second = run_review(pkg, no_infer=True, since=first.review_id)

    assert len(second.semantic_diff.added_strategies) == 1
    assert second.semantic_diff.added_strategies[0].startswith("lcs_")
    assert not second.semantic_diff.changed_strategies


def test_warrant_diagnostics_keep_strategy_id(tmp_path: Path) -> None:
    pkg = tmp_path / "p"
    _write_pkg(
        pkg,
        "from gaia.lang import claim, support\n"
        'a = claim("A")\n'
        'c = claim("C")\n'
        "s = support(premises=[a], conclusion=c)\n"
        '__all__ = ["a", "c", "s"]\n',
    )

    report = run_review(pkg, no_infer=True)
    warrant_diags = [
        d for d in report.diagnostics if d.kind in {"unreviewed_warrant", "blocked_warrant_path"}
    ]

    assert warrant_diags
    assert all(d.target.startswith("lcs_") for d in warrant_diags)
    assert all(d.label.startswith("lcs_") for d in warrant_diags)
    assert all("``" not in d.suggested_edit for d in warrant_diags)


def test_snapshot_collision_updates_report_and_state_to_actual_id(
    tmp_path: Path, monkeypatch
) -> None:
    pkg = tmp_path / "p"
    _write_pkg(
        pkg,
        'from gaia.lang import claim\na = claim("A", metadata={"prior": 0.5})\n__all__ = ["a"]\n',
    )
    monkeypatch.setattr("gaia.inquiry.review.mint_review_id", lambda _hash, _mode: "fixed")

    first = run_review(pkg, no_infer=True)
    second = run_review(pkg, no_infer=True)

    assert first.review_id == "fixed"
    assert second.review_id == "fixed-2"
    assert load_state(pkg).last_review_id == "fixed-2"

    review_files = sorted(p.stem for p in (pkg / ".gaia" / "inquiry" / "reviews").glob("*.json"))
    assert review_files == ["fixed", "fixed-2"]
    stored = json.loads((pkg / ".gaia" / "inquiry" / "reviews" / "fixed-2.json").read_text())
    assert stored["review_id"] == "fixed-2"


def test_run_review_passes_depth_to_belief_report(tmp_path: Path, monkeypatch) -> None:
    pkg = tmp_path / "p"
    _write_pkg(
        pkg,
        'from gaia.lang import claim\na = claim("A", metadata={"prior": 0.5})\n__all__ = ["a"]\n',
    )
    seen: list[int] = []

    def fake_belief_report(graph, pkg_path, no_infer, errors, focus, depth=0, **_kwargs):
        seen.append(depth)
        return {
            "ran_inference": False,
            "beliefs": [],
            "focus": None,
            "largest_increases": [],
            "largest_decreases": [],
        }

    monkeypatch.setattr("gaia.inquiry.review._build_belief_report", fake_belief_report)

    run_review(pkg, no_infer=False, depth=2)

    assert seen == [2]


def test_belief_report_depth_uses_joint_dependency_graph(tmp_path: Path, monkeypatch) -> None:
    import gaia.bp as bp
    import gaia.bp.engine as engine_mod
    import gaia.inquiry.review as review_mod

    local_graph = SimpleNamespace(namespace="github", package_name="local", knowledges=[])
    dep_graph = SimpleNamespace(namespace="github", package_name="dep", knowledges=[])
    local_fg = SimpleNamespace(name="local", validate=lambda: [])
    dep_fg = SimpleNamespace(name="dep", validate=lambda: [])
    merged_fg = SimpleNamespace(name="merged", validate=lambda: [])
    seen: dict[str, object] = {}

    def fake_load_deps(project_config, depth):
        seen["project_config"] = project_config
        seen["depth"] = depth
        return [SimpleNamespace(import_name="dep_pkg", graph=dep_graph)]

    def fake_lower(graph, node_priors=None):
        seen.setdefault("lowered", []).append((graph.package_name, node_priors))
        return dep_fg if graph is dep_graph else local_fg

    def fake_merge(local, deps, local_prefix):
        seen["merge"] = (local, deps, local_prefix)
        return merged_fg

    class FakeEngine:
        def run(self, factor_graph):
            seen["engine_graph"] = factor_graph
            return SimpleNamespace(bp_result=SimpleNamespace(beliefs={}))

    def fail_foreign_priors(*_args, **_kwargs):
        raise AssertionError("depth inference must not use flat foreign priors")

    monkeypatch.setattr(
        review_mod, "load_dependency_compiled_graphs", fake_load_deps, raising=False
    )
    monkeypatch.setattr(review_mod, "collect_foreign_node_priors", fail_foreign_priors)
    monkeypatch.setattr(bp, "lower_local_graph", fake_lower)
    monkeypatch.setattr(bp, "merge_factor_graphs", fake_merge)
    monkeypatch.setattr(engine_mod, "InferenceEngine", FakeEngine)

    report = review_mod._build_belief_report(
        local_graph,
        tmp_path,
        no_infer=False,
        errors=[],
        focus=FocusBinding(raw=None, kind="none"),
        depth=1,
        project_config={"project": {"dependencies": ["dep-gaia"]}},
    )

    assert report["ran_inference"] is True
    assert seen["depth"] == 1
    assert seen["engine_graph"] is merged_fg
    assert seen["merge"] == (
        local_fg,
        [("dep_pkg", dep_fg, "github:dep::")],
        "github:local::",
    )
