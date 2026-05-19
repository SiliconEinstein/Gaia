#!/usr/bin/env python3
"""Decompose a Gaia IR into review trees.

Reads a built Gaia package (`.gaia/ir.json`) and partitions the reasoning
graph into a forest of depth-N trees rooted at conclusions and shared
lemmas that need review.

Each tree is "relatively independent": when reverse-BFS hits another
review root, an already-owned node, or a `setting` axiom, the branch is
cut and recorded as an external reference.

Usage:
    python scripts/review_trees.py <package_dir_or_ir_json>
    python scripts/review_trees.py <pkg> -N 4 --json > trees.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --------------------------------------------------------------------- IR


@dataclass
class Knowledge:
    """One IR ``knowledges[*]`` entry: a claim, setting, or question."""

    id: str
    type: str  # claim | setting | question
    label: str
    title: str
    module: str
    prior: float | None
    review_flag: bool


@dataclass
class Strategy:
    """One IR ``strategies[*]`` entry: a reasoning edge {premises} → conclusion."""

    id: str
    type: str
    conclusion: str
    premises: list[str]
    background: list[str]
    prior: float | None


@dataclass
class IR:
    """In-memory view of a built Gaia package's reasoning graph."""

    package: str
    knowledges: dict[str, Knowledge]
    strategies: dict[str, Strategy]
    # conclusion_id -> list of strategies producing it
    in_edges: dict[str, list[Strategy]] = field(default_factory=dict)
    # node_id -> # strategies that consume it as premise|background
    fanout: Counter[str] = field(default_factory=Counter)

    @classmethod
    def load(cls, path: Path) -> IR:
        """Read a compiled ``.gaia/ir.json`` and build the IR view."""
        raw = json.loads(path.read_text())
        knows: dict[str, Knowledge] = {}
        for k in raw["knowledges"]:
            meta = k.get("metadata") or {}
            knows[k["id"]] = Knowledge(
                id=k["id"],
                type=k["type"],
                label=k.get("label", k["id"].rsplit("::", 1)[-1]),
                title=k.get("title") or k.get("label") or "",
                module=k.get("module", ""),
                prior=meta.get("prior"),
                review_flag=bool(meta.get("review")),
            )

        strats: dict[str, Strategy] = {}
        in_edges: dict[str, list[Strategy]] = {}
        fanout: Counter[str] = Counter()
        for s in raw["strategies"]:
            meta = s.get("metadata") or {}
            st = Strategy(
                id=s["strategy_id"],
                type=s["type"],
                conclusion=s["conclusion"],
                premises=list(s.get("premises", [])),
                background=list(s.get("background", [])),
                prior=meta.get("prior"),
            )
            strats[st.id] = st
            in_edges.setdefault(st.conclusion, []).append(st)
            for p in st.premises + st.background:
                fanout[p] += 1

        return cls(
            package=raw.get("package_name", ""),
            knowledges=knows,
            strategies=strats,
            in_edges=in_edges,
            fanout=fanout,
        )

    def short(self, kid: str) -> str:
        """Return a human-readable label for a knowledge id (title > label > id)."""
        k = self.knowledges.get(kid)
        if not k:
            return kid
        return k.title or k.label or kid

    def is_claim(self, kid: str) -> bool:
        """Whether ``kid`` is a ``claim`` knowledge."""
        k = self.knowledges.get(kid)
        return bool(k and k.type == "claim")

    def is_setting(self, kid: str) -> bool:
        """Whether ``kid`` is a ``setting`` knowledge (treated as axiomatic)."""
        k = self.knowledges.get(kid)
        return bool(k and k.type == "setting")


# ----------------------------------------------------------- root selection


_HELPER_PREFIXES = ("_anon_", "__")


def _is_helper(k: Knowledge) -> bool:
    """Compiler-generated helper claims (conjunction results, anon, etc.)."""
    return k.label.startswith(_HELPER_PREFIXES)


def _has_inbound(ir: IR, kid: str) -> bool:
    return bool(ir.in_edges.get(kid))


def select_roots(ir: IR, *, max_sinks: int, max_shared: int, max_uncertain: int) -> list[str]:
    """Pick review roots in priority order.

    Eligible: claim/question, not a compiler helper, and has at least one
    inbound reasoning step (single-node "leaf claims" are not review trees).

    Priority groups (deduped, order preserved):
      1. claims/questions explicitly flagged review=True
      2. uncertain claims (prior < 0.7) — these are the high-risk predictions
      3. terminal claims (sinks) sorted by uncertainty
      4. shared lemmas (fanout >= 2) sorted by fanout
    """

    def eligible(kid: str) -> bool:
        k = ir.knowledges.get(kid)
        return (
            k is not None
            and k.type in {"claim", "question"}
            and not _is_helper(k)
            and _has_inbound(ir, kid)
        )

    flagged = [kid for kid, k in ir.knowledges.items() if k.review_flag and eligible(kid)]

    uncertain = [
        kid
        for kid, k in ir.knowledges.items()
        if eligible(kid) and k.prior is not None and k.prior < 0.7
    ]
    sinks = [kid for kid, k in ir.knowledges.items() if eligible(kid) and ir.fanout[kid] == 0]
    shared = [kid for kid in ir.fanout if ir.fanout[kid] >= 2 and eligible(kid)]

    def uncertainty(kid: str) -> float:
        p = ir.knowledges[kid].prior
        return 1.0 - (p if p is not None else 0.5)

    uncertain.sort(key=lambda k: (-uncertainty(k) * (1 + ir.fanout[k]),))
    sinks.sort(key=lambda k: (-uncertainty(k),))
    shared.sort(key=lambda k: (-ir.fanout[k],))

    out: list[str] = []
    seen: set[str] = set()
    for kid in flagged + uncertain[:max_uncertain] + sinks[:max_sinks] + shared[:max_shared]:
        if kid not in seen:
            out.append(kid)
            seen.add(kid)
    return out


# ------------------------------------------------------------ tree building


@dataclass
class Justification:
    """One strategy that produces a node (AND-group of premises)."""

    strategy_id: str
    strategy_type: str
    prior: float | None
    premises: list[TreeNode] = field(default_factory=list)
    background: list[TreeNode] = field(default_factory=list)


@dataclass
class TreeNode:
    """One node in a review tree (a knowledge plus zero or more justifications)."""

    id: str
    kind: str  # claim | setting | question | ?
    depth: int
    cut_reason: str | None = None  # None = expanded; otherwise leaf
    # Multiple strategies for the same claim = OR alternatives
    justifications: list[Justification] = field(default_factory=list)


@dataclass
class ReviewTree:
    """A single review tree rooted at one conclusion or shared lemma."""

    root: str
    root_node: TreeNode
    internal: set[str] = field(default_factory=set)
    external_refs: dict[str, str] = field(default_factory=dict)  # id -> cut_reason


# ------------------------------------------------------------ authoring smells


@dataclass
class Smell:
    """One authoring red-flag surfaced from the IR."""

    kind: str  # short tag, e.g. "axiomatic_critical"
    severity: str  # "high" | "medium" | "low"
    target: str  # knowledge id or strategy id
    title: str  # human-readable target name
    detail: str  # context info (fanout, prior, etc.)


def detect_smells(ir: IR) -> list[Smell]:  # noqa: C901  -- intentionally one cohesive switch over smell categories
    """Author-side red flags surfaced as a by-product of consuming the IR."""
    smells: list[Smell] = []

    # 1. claim used as a critical premise but never derived → likely should
    #    have been authored as setting() or observe()
    for kid, k in ir.knowledges.items():
        if k.type != "claim" or _is_helper(k):
            continue
        if ir.fanout[kid] >= 3 and not _has_inbound(ir, kid):
            smells.append(
                Smell(
                    kind="axiomatic_critical",
                    severity="high" if ir.fanout[kid] >= 5 else "medium",
                    target=kid,
                    title=ir.short(kid),
                    detail=f"fanout={ir.fanout[kid]}, no inbound reasoning; "
                    f"prior={k.prior!r}. Reauthor as setting() / observe()?",
                )
            )

    # 2. headline claim (sink, has inbound) with no calibrated prior
    for kid, k in ir.knowledges.items():
        if k.type != "claim" or _is_helper(k):
            continue
        if ir.fanout[kid] == 0 and _has_inbound(ir, kid) and k.prior is None:
            smells.append(
                Smell(
                    kind="headline_missing_prior",
                    severity="medium",
                    target=kid,
                    title=ir.short(kid),
                    detail=f"terminal claim in module '{k.module}' has prior=None; "
                    f"reviewer can't gauge confidence.",
                )
            )

    # 3. fully orphan claim — no inbound, no outbound, not a setting
    for kid, k in ir.knowledges.items():
        if k.type != "claim" or _is_helper(k):
            continue
        if ir.fanout[kid] == 0 and not _has_inbound(ir, kid):
            smells.append(
                Smell(
                    kind="orphan_claim",
                    severity="low",
                    target=kid,
                    title=ir.short(kid),
                    detail=f"module='{k.module}' — dangling claim, not referenced. "
                    f"Delete or wire in?",
                )
            )

    # 4. weak warrant — strategy with explicit prior < 0.5
    for sid, s in ir.strategies.items():
        if s.prior is not None and s.prior < 0.5:
            smells.append(
                Smell(
                    kind="weak_warrant",
                    severity="high" if s.prior < 0.25 else "medium",
                    target=sid,
                    title=f"{s.type} → {ir.short(s.conclusion)}",
                    detail=f"warrant prior={s.prior:.2f}; conclusion will be highly "
                    f"uncertain — is this intentional?",
                )
            )

    # 5. fan-out hot spot (used everywhere, prior=None) — silent dependency
    for kid, k in ir.knowledges.items():
        if k.type != "claim" or _is_helper(k):
            continue
        if ir.fanout[kid] >= 5 and k.prior is None:
            smells.append(
                Smell(
                    kind="silent_dependency",
                    severity="high",
                    target=kid,
                    title=ir.short(kid),
                    detail=f"fanout={ir.fanout[kid]} but prior=None; "
                    f"many conclusions silently inherit uncalibrated belief.",
                )
            )

    return smells


def build_tree(  # noqa: C901  -- BFS body has tightly coupled cut-policy branches
    ir: IR,
    root: str,
    depth_limit: int,
    other_roots: set[str],
    owned: dict[str, str],
    max_size: int | None = None,
) -> ReviewTree:
    """Build one review tree using a BFS-layered reverse expansion.

    BFS (rather than DFS) gives fair truncation when `max_size` is hit: the
    closest premises get expanded first, deeper ones get cut last.
    """
    rt = ReviewTree(
        root=root,
        root_node=TreeNode(id=root, kind=ir.knowledges[root].type, depth=0),
    )
    rt.internal.add(root)

    def make_child(pid: str, depth: int, *, size_budget_full: bool) -> TreeNode:
        kind = ir.knowledges[pid].type if pid in ir.knowledges else "?"
        n = TreeNode(id=pid, kind=kind, depth=depth)

        # cut policies (order matters: more-specific reasons first)
        if pid in other_roots and pid != root:
            n.cut_reason = "other-root"
            rt.external_refs[pid] = "other-root"
        elif pid in owned and owned[pid] != root:
            owner_title = ir.short(owned[pid])
            n.cut_reason = f"owned-by:{owner_title}"
            rt.external_refs[pid] = n.cut_reason
        elif ir.is_setting(pid):
            n.cut_reason = "setting"
        elif depth >= depth_limit:
            n.cut_reason = "depth"
        elif size_budget_full and pid not in rt.internal:
            # Hard cap reached; promote this premise to a later root via residual sweep
            n.cut_reason = "overflow"
            rt.external_refs[pid] = "overflow"
        else:
            rt.internal.add(pid)
        return n

    # BFS frontier
    frontier: list[TreeNode] = [rt.root_node]
    while frontier:
        next_frontier: list[TreeNode] = []
        for node in frontier:
            if node.cut_reason is not None:
                continue
            for strat in ir.in_edges.get(node.id, []):
                j = Justification(
                    strategy_id=strat.id,
                    strategy_type=strat.type,
                    prior=strat.prior,
                )
                node.justifications.append(j)
                for pid in strat.premises:
                    size_full = max_size is not None and len(rt.internal) >= max_size
                    child = make_child(pid, node.depth + 1, size_budget_full=size_full)
                    j.premises.append(child)
                    if child.cut_reason is None:
                        next_frontier.append(child)
                for pid in strat.background:
                    size_full = max_size is not None and len(rt.internal) >= max_size
                    child = make_child(pid, node.depth + 1, size_budget_full=size_full)
                    j.background.append(child)
                    # background doesn't recurse (contextual citation only)
        frontier = next_frontier

    return rt


# ----------------------------------------------------------------- driver


def decompose(
    ir: IR,
    depth: int,
    max_sinks: int,
    max_shared: int,
    max_uncertain: int,
    max_tree_size: int | None = None,
    residual_sweep: bool = True,
) -> list[ReviewTree]:
    """Run the full decomposition pipeline: select roots, build trees, sweep residual."""
    roots = select_roots(
        ir,
        max_sinks=max_sinks,
        max_shared=max_shared,
        max_uncertain=max_uncertain,
    )
    other_roots = set(roots)
    owned: dict[str, str] = {}
    trees: list[ReviewTree] = []
    for r in roots:
        rt = build_tree(ir, r, depth, other_roots, owned, max_size=max_tree_size)
        for n in rt.internal:
            owned.setdefault(n, r)
        trees.append(rt)

    if not residual_sweep:
        return trees

    # Residual sweep: keep promoting uncovered eligible claims (including
    # overflow-cut ones) to roots until convergence.
    while True:
        residual = [
            kid
            for kid, k in ir.knowledges.items()
            if k.type == "claim"
            and not _is_helper(k)
            and _has_inbound(ir, kid)
            and kid not in owned
        ]
        if not residual:
            break

        def _key(kid: str) -> tuple[float, float]:
            p = ir.knowledges[kid].prior
            u = 1.0 - (p if p is not None else 0.5)
            return (-u, -float(ir.fanout[kid]))

        residual.sort(key=_key)
        r = residual[0]
        other_roots.add(r)
        rt = build_tree(ir, r, depth, other_roots, owned, max_size=max_tree_size)
        for n in rt.internal:
            owned.setdefault(n, r)
        trees.append(rt)

    return trees


# ----------------------------------------------------------------- output


def render_text(ir: IR, trees: list[ReviewTree]) -> None:
    """Render trees as an ASCII tree to stdout."""
    for i, rt in enumerate(trees, 1):
        head = ir.short(rt.root)
        kind = ir.knowledges[rt.root].type
        n_int = len(rt.internal)
        n_ext = len(rt.external_refs)
        prior = ir.knowledges[rt.root].prior
        prior_s = f" prior={prior:.2f}" if prior is not None else ""
        print(f"\n━━ Tree {i}: {head} ({kind}{prior_s}, internal={n_int}, ext_refs={n_ext}) ━━")
        _render_node(ir, rt.root_node, indent="", is_last=True)


def _render_node(ir: IR, node: TreeNode, *, indent: str, is_last: bool) -> None:
    bullet = "└── " if is_last else "├── "
    cont = "    " if is_last else "│   "
    tag = f"[{node.kind}]"
    title = ir.short(node.id)
    cut = f"  ⟨cut:{node.cut_reason}⟩" if node.cut_reason else ""
    if indent == "":
        print(f"▶ {tag} {title}{cut}")
        next_indent = ""
    else:
        print(f"{indent}{bullet}{tag} {title}{cut}")
        next_indent = indent + cont

    for ji, j in enumerate(node.justifications):
        j_is_last = ji == len(node.justifications) - 1
        j_bullet = "└─◇ " if j_is_last else "├─◇ "
        j_cont = "    " if j_is_last else "│   "
        prior_s = f" prior={j.prior:.2f}" if j.prior is not None else ""
        n_alt = len(node.justifications)
        alt_s = f" (alt {ji + 1}/{n_alt})" if n_alt > 1 else ""
        print(f"{next_indent}{j_bullet}via {j.strategy_type}{prior_s}{alt_s}")
        children = j.premises + [
            # Mark background nodes with a tag so render shows them
            _tag_background(c)
            for c in j.background
        ]
        for ci, child in enumerate(children):
            _render_node(
                ir,
                child,
                indent=next_indent + j_cont,
                is_last=ci == len(children) - 1,
            )


def _tag_background(n: TreeNode) -> TreeNode:
    if n.cut_reason is None:
        n.cut_reason = "background"
    return n


def render_smells(smells: list[Smell]) -> None:
    """Render the authoring-smell report to stdout."""
    if not smells:
        print("\nAuthoring smells: none detected.")
        return
    by_kind: dict[str, list[Smell]] = {}
    for s in smells:
        by_kind.setdefault(s.kind, []).append(s)
    sev_rank = {"high": 0, "medium": 1, "low": 2}
    order = [
        "silent_dependency",
        "axiomatic_critical",
        "weak_warrant",
        "headline_missing_prior",
        "orphan_claim",
    ]

    print(f"\nAuthoring smells: {len(smells)} total")
    for kind in order:
        items = by_kind.get(kind, [])
        if not items:
            continue
        items.sort(key=lambda s: sev_rank.get(s.severity, 9))
        print(f"  ◆ {kind}  ({len(items)})")
        for s in items[:6]:
            print(f"    [{s.severity:6}] {s.title}")
            print(f"             {s.detail}")
        if len(items) > 6:
            print(f"             … ({len(items) - 6} more)")


def render_summary(ir: IR, trees: list[ReviewTree]) -> None:
    """Render the coverage / axiomatic-claim summary to stdout."""
    real_claims = {
        k for k, kn in ir.knowledges.items() if kn.type == "claim" and not _is_helper(kn)
    }
    derivable = {k for k in real_claims if _has_inbound(ir, k)}
    axiomatic = real_claims - derivable

    covered: set[str] = set()
    for rt in trees:
        covered |= rt.internal
    uncovered_derivable = derivable - covered

    sizes = sorted((len(rt.internal) for rt in trees), reverse=True)
    print(
        f"\nSummary: {len(trees)} trees  "
        f"derivable_coverage={len(covered & derivable)}/{len(derivable)}  "
        f"axiomatic_claims={len(axiomatic)} (no inbound, treat like settings)"
    )
    print(f"  tree sizes (internal nodes): {sizes}")
    if uncovered_derivable:
        print(f"Uncovered derivable claims ({len(uncovered_derivable)}):")
        ranked = sorted(
            uncovered_derivable,
            key=lambda k: -(1.0 - (ir.knowledges[k].prior or 0.5)),
        )
        for kid in ranked[:10]:
            k = ir.knowledges[kid]
            p = f"prior={k.prior}" if k.prior is not None else "prior=?"
            print(
                f"  · [{p}] {ir.short(kid)}  [{k.module}]  "
                f"fanout={ir.fanout[kid]}  inbound={len(ir.in_edges.get(kid, []))}"
            )
    if axiomatic:
        print(f"Axiomatic claims (no derivation, function like settings) ({len(axiomatic)}):")
        for kid in sorted(axiomatic, key=lambda k: -ir.fanout[k])[:10]:
            k = ir.knowledges[kid]
            p = f"prior={k.prior}" if k.prior is not None else "prior=?"
            print(f"  · [{p}] {ir.short(kid)}  [{k.module}]  fanout={ir.fanout[kid]}")


def render_markdown(ir: IR, trees: list[ReviewTree], smells: list[Smell]) -> str:
    """Produce a self-contained Markdown review report."""
    lines: list[str] = []

    # --- header
    real_claims = {
        k for k, kn in ir.knowledges.items() if kn.type == "claim" and not _is_helper(kn)
    }
    derivable = {k for k in real_claims if _has_inbound(ir, k)}
    axiomatic = real_claims - derivable
    covered = set().union(*(rt.internal for rt in trees)) if trees else set()

    lines.append(f"# Review Trees — `{ir.package}`")
    lines.append("")
    lines.append(
        f"- Knowledges: **{len(ir.knowledges)}** "
        f"(claims={sum(1 for k in ir.knowledges.values() if k.type == 'claim')}, "
        f"settings={sum(1 for k in ir.knowledges.values() if k.type == 'setting')}, "
        f"questions={sum(1 for k in ir.knowledges.values() if k.type == 'question')})"
    )
    lines.append(f"- Strategies (reasoning edges): **{len(ir.strategies)}**")
    lines.append(
        f"- Review trees: **{len(trees)}**  "
        f"(derivable coverage = {len(covered & derivable)}/{len(derivable)})"
    )
    lines.append(f"- Axiomatic claims (no derivation, behave like settings): **{len(axiomatic)}**")
    lines.append(f"- Authoring smells detected: **{len(smells)}**")
    lines.append("")

    # --- TOC
    lines.append("## Tree index")
    lines.append("")
    lines.append("| # | Root | kind | prior | internal | ext refs |")
    lines.append("|---|------|------|-------|----------|----------|")
    for i, rt in enumerate(trees, 1):
        k = ir.knowledges[rt.root]
        prior = f"{k.prior:.2f}" if k.prior is not None else "—"
        title = ir.short(rt.root).replace("|", "\\|")
        lines.append(
            f"| {i} | [{title}](#tree-{i}-{_anchor(title)}) "
            f"| {k.type} | {prior} | {len(rt.internal)} | {len(rt.external_refs)} |"
        )
    lines.append("")

    # --- trees
    lines.append("## Trees")
    lines.append("")
    for i, rt in enumerate(trees, 1):
        k = ir.knowledges[rt.root]
        prior = f", prior=`{k.prior:.2f}`" if k.prior is not None else ""
        anchor = _anchor(ir.short(rt.root))
        lines.append(f'### Tree {i}: {ir.short(rt.root)} <a id="tree-{i}-{anchor}"></a>')
        lines.append("")
        lines.append(
            f"*{k.type}{prior}, internal={len(rt.internal)}, "
            f"external_refs={len(rt.external_refs)}, module=`{k.module}`*"
        )
        lines.append("")
        _md_node(ir, rt.root_node, lines, indent=0, is_root=True)
        lines.append("")

    # --- smells
    if smells:
        lines.append("## Authoring smells")
        lines.append("")
        by_kind: dict[str, list[Smell]] = {}
        for s in smells:
            by_kind.setdefault(s.kind, []).append(s)
        order = [
            "silent_dependency",
            "axiomatic_critical",
            "weak_warrant",
            "headline_missing_prior",
            "orphan_claim",
        ]
        sev_rank = {"high": 0, "medium": 1, "low": 2}
        for kind in order:
            items = by_kind.get(kind, [])
            if not items:
                continue
            items.sort(key=lambda s: sev_rank.get(s.severity, 9))
            lines.append(f"### `{kind}` ({len(items)})")
            lines.append("")
            for s in items:
                lines.append(f"- **[{s.severity}]** {s.title}")
                lines.append(f"    - {s.detail}")
            lines.append("")

    return "\n".join(lines) + "\n"


_BULLET_TYPE_LABEL = {
    "claim": "claim",
    "setting": "setting",
    "question": "question",
    "?": "?",
}


def _md_node(ir: IR, node: TreeNode, lines: list[str], *, indent: int, is_root: bool) -> None:
    pad = "    " * indent
    tag = _BULLET_TYPE_LABEL.get(node.kind, node.kind)
    title = ir.short(node.id).replace("|", "\\|")
    cut = f"  *⟨cut: {node.cut_reason}⟩*" if node.cut_reason else ""
    if is_root:
        lines.append(f"{pad}- **`{tag}`** **{title}**{cut}")
    else:
        lines.append(f"{pad}- `{tag}` {title}{cut}")

    for j in node.justifications:
        prior = f", prior=`{j.prior:.2f}`" if j.prior is not None else ""
        n_alt = len(node.justifications)
        alt = f" (alt {node.justifications.index(j) + 1}/{n_alt})" if n_alt > 1 else ""
        lines.append(f"{pad}    - *via* `{j.strategy_type}`{prior}{alt}")
        for child in j.premises:
            _md_node(ir, child, lines, indent=indent + 2, is_root=False)
        for child in j.background:
            # background → reuse render, will pick up the 'background' cut_reason
            _md_node(ir, child, lines, indent=indent + 2, is_root=False)


def _anchor(text: str) -> str:
    import re

    s = text.lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "-", s.strip())
    return s[:60]


def to_json(ir: IR, trees: list[ReviewTree], smells: list[Smell]) -> dict[str, Any]:
    """Build a JSON-serializable dict describing trees + smells."""

    def dump_node(n: TreeNode) -> dict[str, Any]:
        return {
            "id": n.id,
            "kind": n.kind,
            "title": ir.short(n.id),
            "depth": n.depth,
            "cut_reason": n.cut_reason,
            "justifications": [
                {
                    "strategy_id": j.strategy_id,
                    "strategy_type": j.strategy_type,
                    "prior": j.prior,
                    "premises": [dump_node(c) for c in j.premises],
                    "background": [dump_node(c) for c in j.background],
                }
                for j in n.justifications
            ],
        }

    return {
        "package": ir.package,
        "trees": [
            {
                "root": rt.root,
                "root_title": ir.short(rt.root),
                "internal_count": len(rt.internal),
                "external_refs": rt.external_refs,
                "tree": dump_node(rt.root_node),
            }
            for rt in trees
        ],
        "smells": [
            {
                "kind": s.kind,
                "severity": s.severity,
                "target": s.target,
                "title": s.title,
                "detail": s.detail,
            }
            for s in smells
        ],
    }


# --------------------------------------------------------------------- main


def main() -> int:
    """CLI entry point."""
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "package",
        type=Path,
        help="Path to a gaia package directory OR directly to a .gaia/ir.json",
    )
    ap.add_argument("-N", "--depth", type=int, default=3)
    ap.add_argument("--max-sinks", type=int, default=8)
    ap.add_argument("--max-shared", type=int, default=4)
    ap.add_argument(
        "--max-uncertain",
        type=int,
        default=6,
        help="Max # of high-uncertainty (prior<0.7) claims as roots",
    )
    ap.add_argument(
        "--max-tree-size",
        type=int,
        default=8,
        help="Cap on a single tree's internal-node count; "
        "overflow becomes a new root in the residual sweep "
        "(0 = no cap)",
    )
    ap.add_argument(
        "--no-residual-sweep",
        action="store_true",
        help="Don't promote uncovered claims to roots after main pass",
    )
    ap.add_argument("--no-smells", action="store_true", help="Skip the authoring-smells report")
    ap.add_argument(
        "--format",
        choices=("text", "markdown", "json"),
        default="text",
        help="Output format (text=ASCII tree; markdown=review report; json=structured)",
    )
    ap.add_argument("--json", action="store_true", help="Shortcut for --format json")
    args = ap.parse_args()

    p: Path = args.package
    ir_path = p / ".gaia" / "ir.json" if p.is_dir() else p
    if not ir_path.exists():
        ap.error(f"IR not found: {ir_path}")

    ir = IR.load(ir_path)
    print(
        f"# Package: {ir.package}  "
        f"knowledges={len(ir.knowledges)}  strategies={len(ir.strategies)}",
        file=sys.stderr,
    )

    trees = decompose(
        ir,
        depth=args.depth,
        max_sinks=args.max_sinks,
        max_shared=args.max_shared,
        max_uncertain=args.max_uncertain,
        max_tree_size=args.max_tree_size if args.max_tree_size > 0 else None,
        residual_sweep=not args.no_residual_sweep,
    )

    smells = [] if args.no_smells else detect_smells(ir)

    fmt = "json" if args.json else args.format
    if fmt == "json":
        json.dump(to_json(ir, trees, smells), sys.stdout, indent=2)
        sys.stdout.write("\n")
    elif fmt == "markdown":
        sys.stdout.write(render_markdown(ir, trees, smells))
    else:
        render_text(ir, trees)
        render_summary(ir, trees)
        if not args.no_smells:
            render_smells(smells)

    return 0


if __name__ == "__main__":
    sys.exit(main())
