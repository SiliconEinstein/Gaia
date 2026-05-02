"""Structured analyzers shared by `gaia check` and `gaia inquiry review`.

This module is the single source of truth for graph-health / prior-hole /
knowledge-breakdown analysis on a compiled Gaia IR. `gaia check` keeps
emitting human-readable lines via the wrappers in ``check.py``; `gaia
inquiry` consumes the structured dataclasses below directly.

No detection logic is duplicated in ``gaia.inquiry``.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gaia.cli.commands._classify import KnowledgeClassification, classify_ir, node_role


def get_prior(k: dict) -> float | None:
    """Return the prior stored in a knowledge node's metadata, or None."""
    meta = k.get("metadata") or {}
    return meta.get("prior")


@dataclass
class HoleEntry:
    """One independent claim, with or without a prior set."""

    cid: str
    label: str
    content: str
    prior: float | None
    prior_justification: str = ""

    @property
    def is_hole(self) -> bool:
        return self.prior is None


@dataclass
class KnowledgeBreakdown:
    """Role-based breakdown of all knowledge nodes in an IR."""

    settings: list[str] = field(default_factory=list)
    questions: list[str] = field(default_factory=list)
    independent: list[HoleEntry] = field(default_factory=list)
    derived: list[str] = field(default_factory=list)
    structural: list[str] = field(default_factory=list)
    background_only: list[str] = field(default_factory=list)
    orphaned: list[str] = field(default_factory=list)
    classification: KnowledgeClassification = field(default_factory=KnowledgeClassification)

    @property
    def holes(self) -> list[HoleEntry]:
        return [e for e in self.independent if e.is_hole]

    @property
    def covered(self) -> list[HoleEntry]:
        return [e for e in self.independent if not e.is_hole]


def analyze_knowledge_breakdown(ir: dict) -> KnowledgeBreakdown:
    """Walk the IR once and classify every knowledge node by structural role."""
    c = classify_ir(ir)
    out = KnowledgeBreakdown(classification=c)

    for k in ir.get("knowledges", []):
        ktype = k.get("type")
        kid = k["id"]
        label = k.get("label", kid.split("::")[-1])
        if ktype == "setting":
            out.settings.append(label)
            continue
        if ktype == "question":
            out.questions.append(label)
            continue
        if ktype != "claim":
            continue
        role = node_role(kid, "claim", c)
        if role == "structural":
            out.structural.append(label)
        elif role == "derived":
            out.derived.append(label)
        elif role == "independent":
            meta = k.get("metadata") or {}
            out.independent.append(
                HoleEntry(
                    cid=kid,
                    label=label,
                    content=k.get("content", ""),
                    prior=get_prior(k),
                    prior_justification=meta.get("prior_justification", ""),
                )
            )
        elif role == "background":
            out.background_only.append(label)
        else:
            out.orphaned.append(label)
    return out


def find_possible_duplicate_claims(ir: dict) -> list[tuple[str, str]]:
    """Heuristic: pairs of claims with identical normalized content.

    Conservative — only exact-match after whitespace collapse. Per spec §8
    `possible_duplicate_claims` is a graph-health hint, not an error.
    """
    claims = [k for k in ir.get("knowledges", []) if k.get("type") == "claim"]
    by_norm: dict[str, list[str]] = {}
    for k in claims:
        content = " ".join((k.get("content") or "").split()).lower()
        if not content:
            continue
        by_norm.setdefault(content, []).append(k.get("label", k["id"].split("::")[-1]))
    pairs: list[tuple[str, str]] = []
    for labels in by_norm.values():
        if len(labels) < 2:
            continue
        for i in range(len(labels)):
            for j in range(i + 1, len(labels)):
                pairs.append((labels[i], labels[j]))
    return pairs
