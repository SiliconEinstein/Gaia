"""Tests for ``scripts/review_trees.py`` — IR → review-tree decomposition."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "scripts" / "review_trees.py"


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("review_trees", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


script = _load_script()


# ----------------------------------------------------------- fixture helpers


def _k(
    label: str,
    *,
    type_: str = "claim",
    prior: float | None = None,
    review: bool = False,
    module: str = "m",
) -> dict[str, Any]:
    metadata: dict[str, Any] = {}
    if prior is not None:
        metadata["prior"] = prior
    if review:
        metadata["review"] = True
    return {
        "id": f"pkg::{label}",
        "label": label,
        "title": label.replace("_", " "),
        "type": type_,
        "module": module,
        "metadata": metadata,
        "content": "",
        "parameters": [],
        "declaration_index": 0,
        "exported": False,
    }


def _s(
    sid: str,
    type_: str,
    conclusion: str,
    premises: list[str],
    *,
    background: list[str] | None = None,
    prior: float | None = None,
) -> dict[str, Any]:
    md: dict[str, Any] = {}
    if prior is not None:
        md["prior"] = prior
    return {
        "strategy_id": sid,
        "type": type_,
        "conclusion": f"pkg::{conclusion}",
        "premises": [f"pkg::{p}" for p in premises],
        "background": [f"pkg::{p}" for p in (background or [])],
        "scope": "local",
        "metadata": md,
    }


def _make_ir(knowledges: list[dict[str, Any]], strategies: list[dict[str, Any]]):
    raw = {
        "package_name": "pkg",
        "ir_hash": "test",
        "knowledges": knowledges,
        "strategies": strategies,
        "module_order": [],
        "module_titles": {},
        "namespace": "github",
        "operators": [],
        "scope": "local",
    }
    return _ir_from_raw(raw)


def _ir_from_raw(raw: dict[str, Any], tmp_path: Path | None = None):
    """Persist to a temp file and load through script.IR.load."""
    import tempfile

    path = Path(tempfile.mkstemp(suffix=".json")[1]) if tmp_path is None else tmp_path / "ir.json"
    path.write_text(json.dumps(raw))
    return script.IR.load(path)


# ----------------------------------------------------------- IR loading tests


def test_ir_load_basic_shape() -> None:
    ir = _make_ir(
        [_k("a"), _k("b"), _k("c", type_="setting")],
        [_s("s1", "deduction", "a", ["b", "c"])],
    )
    assert ir.package == "pkg"
    assert set(ir.knowledges) == {"pkg::a", "pkg::b", "pkg::c"}
    assert ir.is_claim("pkg::a")
    assert ir.is_setting("pkg::c")
    assert ir.fanout["pkg::b"] == 1
    assert ir.fanout["pkg::c"] == 1
    assert len(ir.in_edges["pkg::a"]) == 1
    assert "pkg::b" not in ir.in_edges  # leaf claim has no inbound


# ----------------------------------------------------------- root selection


def test_helper_labels_excluded_from_roots() -> None:
    ir = _make_ir(
        [_k("_anon_0"), _k("real"), _k("__conjunction_x"), _k("p")],
        [
            _s("s1", "deduction", "_anon_0", ["p"]),
            _s("s2", "deduction", "real", ["p"]),
            _s("s3", "deduction", "__conjunction_x", ["p"]),
        ],
    )
    roots = script.select_roots(ir, max_sinks=10, max_shared=10, max_uncertain=10)
    assert "pkg::real" in roots
    assert "pkg::_anon_0" not in roots
    assert "pkg::__conjunction_x" not in roots


def test_leaf_with_no_inbound_not_root() -> None:
    """A claim with zero inbound reasoning is not a review root (nothing to review)."""
    ir = _make_ir(
        [_k("dangling_leaf"), _k("derived"), _k("p")],
        [_s("s1", "deduction", "derived", ["p"])],
    )
    roots = script.select_roots(ir, max_sinks=10, max_shared=10, max_uncertain=10)
    assert "pkg::dangling_leaf" not in roots
    assert "pkg::p" not in roots
    assert "pkg::derived" in roots


def test_uncertain_claim_promoted_over_certain_sink() -> None:
    """Low-prior premise claims still become roots via the 'uncertain' channel.

    Even if such a claim is not a sink (i.e. it's consumed downstream), it
    must still be picked up as a review root.
    """
    ir = _make_ir(
        [
            _k("uncertain_premise", prior=0.1),
            _k("certain_sink", prior=0.99),
            _k("downstream"),
            _k("base"),
        ],
        [
            _s("s1", "deduction", "uncertain_premise", ["base"]),
            _s("s2", "deduction", "downstream", ["uncertain_premise"]),
            _s("s3", "deduction", "certain_sink", ["base"]),
        ],
    )
    roots = script.select_roots(ir, max_sinks=10, max_shared=10, max_uncertain=10)
    # uncertain_premise is not a sink (downstream consumes it) — must still be a root
    assert "pkg::uncertain_premise" in roots
    # uncertain claim should come before certain sinks
    assert roots.index("pkg::uncertain_premise") < roots.index("pkg::certain_sink")


def test_review_flag_takes_priority() -> None:
    ir = _make_ir(
        [_k("flagged", review=True), _k("sink", prior=0.99), _k("p")],
        [
            _s("s1", "deduction", "flagged", ["p"]),
            _s("s2", "deduction", "sink", ["p"]),
        ],
    )
    roots = script.select_roots(ir, max_sinks=10, max_shared=10, max_uncertain=10)
    assert roots[0] == "pkg::flagged"


# ----------------------------------------------------------- cut policies


def test_setting_is_cut() -> None:
    ir = _make_ir(
        [_k("c"), _k("ax", type_="setting"), _k("p")],
        [_s("s1", "deduction", "c", ["ax", "p"])],
    )
    trees = script.decompose(
        ir,
        depth=3,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
    )
    # find the tree for c
    root = next(t for t in trees if t.root == "pkg::c")
    leaves = [n for j in root.root_node.justifications for n in j.premises + j.background]
    settings_cut = [n for n in leaves if n.cut_reason == "setting"]
    assert any(n.id == "pkg::ax" for n in settings_cut)


def test_owner_uniqueness_invariant() -> None:
    """Every node is internal in exactly one tree (excluding root duplicates)."""
    ir = _make_ir(
        [_k(f"c{i}") for i in range(6)],
        [
            _s("s1", "deduction", "c0", ["c1"]),
            _s("s2", "deduction", "c1", ["c2", "c3"]),  # c1 has 2 premises
            _s("s3", "deduction", "c4", ["c2"]),  # c2 is shared
            _s("s4", "deduction", "c5", ["c3"]),  # c3 is shared
        ],
    )
    trees = script.decompose(
        ir,
        depth=4,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
    )
    seen: dict[str, str] = {}
    for t in trees:
        for nid in t.internal:
            if nid in seen:
                assert seen[nid] == nid or seen[nid] == t.root, (
                    f"{nid} is internal in both {seen[nid]} and {t.root}"
                )
            seen[nid] = t.root


def test_coverage_invariant_full() -> None:
    """Every claim with inbound reasoning ends up internal in some tree."""
    ir = _make_ir(
        [_k(f"c{i}") for i in range(8)] + [_k("axiom", type_="setting")],
        [
            _s("s1", "deduction", "c0", ["c1", "c2"]),
            _s("s2", "deduction", "c1", ["c3"]),
            _s("s3", "deduction", "c2", ["c3", "axiom"]),
            _s("s4", "deduction", "c4", ["c5"]),
            _s("s5", "deduction", "c5", ["c6"]),
            _s("s6", "support", "c7", ["c0", "c4"], prior=0.6),
        ],
    )
    trees = script.decompose(
        ir,
        depth=5,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
    )
    covered: set[str] = set()
    for t in trees:
        covered |= t.internal
    derivable = {k for k in ir.knowledges if ir.in_edges.get(k)}
    assert covered >= derivable, f"missing: {derivable - covered}"


# ------------------------------------------------------------ size capping


def test_max_tree_size_overflow_creates_new_root() -> None:
    """When max_tree_size is hit, overflow children become new roots."""
    # linear chain c0 -> c1 -> c2 -> c3 -> c4 -> c5 (premises point left)
    ir = _make_ir(
        [_k(f"c{i}") for i in range(6)],
        [_s(f"s{i}", "deduction", f"c{i}", [f"c{i + 1}"]) for i in range(5)],
    )
    trees = script.decompose(
        ir,
        depth=10,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
        max_tree_size=3,
    )
    assert all(len(t.internal) <= 3 for t in trees), [len(t.internal) for t in trees]
    # The chain has 5 derivable claims (c0..c4); cap=3 forces at least 2 trees
    derivable_covered: set[str] = set()
    for t in trees:
        derivable_covered |= t.internal
    assert derivable_covered >= {f"pkg::c{i}" for i in range(5)}


# ------------------------------------------------------------ smells


def test_smell_axiomatic_critical() -> None:
    """Claim with high fanout but no inbound should be flagged."""
    ir = _make_ir(
        [_k("hub"), _k("c0"), _k("c1"), _k("c2"), _k("c3")],
        [
            _s("s1", "deduction", "c0", ["hub"]),
            _s("s2", "deduction", "c1", ["hub"]),
            _s("s3", "deduction", "c2", ["hub"]),
            _s("s4", "deduction", "c3", ["hub"]),
        ],
    )
    smells = script.detect_smells(ir)
    kinds = {s.kind: s for s in smells}
    assert "axiomatic_critical" in kinds
    assert kinds["axiomatic_critical"].target == "pkg::hub"


def test_smell_weak_warrant() -> None:
    ir = _make_ir(
        [_k("c"), _k("p")],
        [_s("s1", "support", "c", ["p"], prior=0.15)],
    )
    smells = script.detect_smells(ir)
    weak = [s for s in smells if s.kind == "weak_warrant"]
    assert weak and weak[0].severity == "high"


def test_smell_silent_dependency() -> None:
    """High-fanout claim with prior=None is a silent dependency."""
    ir = _make_ir(
        [_k("hub")] + [_k(f"c{i}") for i in range(5)],  # hub used 5 times, no prior
        [_s(f"s{i}", "deduction", f"c{i}", ["hub"]) for i in range(5)],
    )
    smells = script.detect_smells(ir)
    silent = [s for s in smells if s.kind == "silent_dependency"]
    assert silent
    assert silent[0].target == "pkg::hub"
    assert silent[0].severity == "high"


def test_smell_headline_missing_prior() -> None:
    """Terminal claim with no prior gets flagged."""
    ir = _make_ir(
        [_k("headline"), _k("p")],  # headline is a sink, no prior
        [_s("s1", "deduction", "headline", ["p"])],
    )
    smells = script.detect_smells(ir)
    assert any(s.kind == "headline_missing_prior" for s in smells)


def test_smell_no_false_positive_on_clean_ir() -> None:
    """A well-authored IR (all priors set, no orphans) emits no smells."""
    ir = _make_ir(
        [
            _k("c0", prior=0.9),
            _k("c1", prior=0.9),
            _k("c2", prior=0.9),
            _k("ax", type_="setting"),
        ],
        [
            _s("s1", "deduction", "c0", ["c1", "ax"], prior=0.95),
            _s("s2", "deduction", "c1", ["c2", "ax"], prior=0.95),
        ],
    )
    smells = script.detect_smells(ir)
    assert smells == [], [(s.kind, s.title) for s in smells]


# --------------------------------------------------------- output renderers


def test_json_output_roundtrip() -> None:
    ir = _make_ir(
        [_k("a", prior=0.5), _k("b", prior=0.9), _k("c"), _k("d", type_="setting")],
        [
            _s("s1", "deduction", "a", ["b", "d"], prior=0.9),
            _s("s2", "deduction", "b", ["c"], prior=0.9),
        ],
    )
    trees = script.decompose(
        ir,
        depth=3,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
    )
    smells = script.detect_smells(ir)
    out = script.to_json(ir, trees, smells)
    # must be valid JSON
    s = json.dumps(out)
    parsed = json.loads(s)
    assert parsed["package"] == "pkg"
    assert isinstance(parsed["trees"], list)
    assert isinstance(parsed["smells"], list)
    # at least the uncertain claim 'a' is a root
    titles = {t["root_title"] for t in parsed["trees"]}
    assert "a" in titles


def test_markdown_output_renders() -> None:
    ir = _make_ir(
        [_k("c", prior=0.5), _k("p")],
        [_s("s1", "deduction", "c", ["p"], prior=0.95)],
    )
    trees = script.decompose(
        ir,
        depth=3,
        max_sinks=10,
        max_shared=10,
        max_uncertain=10,
    )
    smells = script.detect_smells(ir)
    md = script.render_markdown(ir, trees, smells)
    assert md.startswith("# Review Trees")
    assert "Tree index" in md
    assert "via" in md  # at least one strategy line
