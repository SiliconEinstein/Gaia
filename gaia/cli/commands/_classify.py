"""Shared knowledge node classification for check and readme commands."""

from __future__ import annotations

from dataclasses import dataclass, field

NOTE_TYPES = frozenset({"note", "setting", "context"})


@dataclass
class KnowledgeClassification:
    """Classification of knowledge nodes in a compiled IR."""

    strategy_conclusions: set[str] = field(default_factory=set)
    strategy_premises: set[str] = field(default_factory=set)
    strategy_background: set[str] = field(default_factory=set)
    operator_conclusions: set[str] = field(default_factory=set)
    operator_variables: set[str] = field(default_factory=set)


def classify_ir(ir: dict) -> KnowledgeClassification:
    """Classify knowledge nodes by their role in the reasoning graph."""
    c = KnowledgeClassification()

    def add_operator_roles(operators: list[dict]) -> None:
        for o in operators:
            if o.get("conclusion"):
                c.operator_conclusions.add(o["conclusion"])
            for v in o.get("variables", []):
                c.operator_variables.add(v)

    for s in ir.get("strategies", []):
        if s.get("conclusion"):
            c.strategy_conclusions.add(s["conclusion"])
        for p in s.get("premises", []):
            c.strategy_premises.add(p)
        for b in s.get("background", []):
            c.strategy_background.add(b)
        formal_expr = s.get("formal_expr") or {}
        add_operator_roles(formal_expr.get("operators", []))
    add_operator_roles(ir.get("operators", []))
    return c


def is_note_type(ktype: str) -> bool:
    """Return True for v6 notes and legacy non-probabilistic context nodes."""
    return ktype in NOTE_TYPES


def node_role(kid: str, ktype: str, c: KnowledgeClassification) -> str:
    """Return the role of a knowledge node: note, question, derived, structural,
    independent, background, or orphaned."""
    if is_note_type(ktype):
        return "note"
    if ktype == "question":
        return "question"
    if kid in c.operator_conclusions:
        return "structural"
    if kid in c.strategy_conclusions:
        return "derived"
    if kid in c.strategy_premises or kid in c.operator_variables:
        return "independent"
    if kid in c.strategy_background:
        return "background"
    return "orphaned"
