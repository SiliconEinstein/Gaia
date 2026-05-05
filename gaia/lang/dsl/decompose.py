"""Gaia Lang structural decomposition verb."""

from __future__ import annotations

from typing import Any

from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import ClaimAtom, is_formula
from gaia.lang.runtime.action import Decompose
from gaia.lang.runtime.knowledge import Claim, Knowledge


def _claim_atoms(formula: Any) -> tuple[Claim, ...]:
    if isinstance(formula, ClaimAtom):
        return (formula.claim,)
    if isinstance(formula, Land | Lor):
        return tuple(claim for operand in formula.operands for claim in _claim_atoms(operand))
    if isinstance(formula, Lnot):
        return _claim_atoms(formula.operand)
    if isinstance(formula, Implies):
        return (*_claim_atoms(formula.antecedent), *_claim_atoms(formula.consequent))
    if isinstance(formula, Iff):
        return (*_claim_atoms(formula.left), *_claim_atoms(formula.right))
    return ()


def _existing_decompose(whole: Claim) -> Decompose | None:
    for action in whole.supports:
        if isinstance(action, Decompose) and action.whole is whole:
            return action
    return None


def _decomposition_reaches(start: Claim, target: Claim, seen: set[int]) -> bool:
    if start is target:
        return True
    start_id = id(start)
    if start_id in seen:
        return False
    seen.add(start_id)
    for action in start.supports:
        if not isinstance(action, Decompose) or action.whole is not start:
            continue
        if any(_decomposition_reaches(part, target, seen) for part in action.parts):
            return True
    return False


def decompose(
    whole: Claim,
    *,
    parts: tuple[Claim, ...] | list[Claim],
    formula: Any,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Declare ``whole`` equivalent to ``formula`` over atomic ``parts``."""
    if not isinstance(whole, Claim):
        raise TypeError("decompose whole must be a Claim")
    part_tuple = tuple(parts)
    if not part_tuple:
        raise ValueError("decompose requires at least one part Claim")
    if any(not isinstance(part, Claim) for part in part_tuple):
        raise TypeError("decompose parts must be Claims")
    if len({id(part) for part in part_tuple}) != len(part_tuple):
        raise ValueError("decompose parts must be unique")
    if not is_formula(formula):
        raise TypeError("decompose formula must be a Formula")

    atom_claims = _claim_atoms(formula)
    atom_ids = {id(claim) for claim in atom_claims}
    part_ids = {id(part) for part in part_tuple}
    if id(whole) in atom_ids:
        raise ValueError("decompose formula must not reference the whole claim")
    missing = part_ids - atom_ids
    if missing:
        raise ValueError("every decompose part must appear in the formula")
    extra = atom_ids - part_ids
    if extra:
        raise ValueError("decompose formula may only reference listed parts")
    existing = _existing_decompose(whole)
    if existing is not None:
        suffix = f" by action {existing.label}" if existing.label else ""
        raise ValueError(f"decompose: claim is already decomposed{suffix}")
    if any(_decomposition_reaches(part, whole, set()) for part in part_tuple):
        raise ValueError("decompose would create a decomposition cycle")

    action = Decompose(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata=dict(metadata or {}),
        whole=whole,
        parts=part_tuple,
        formula=formula,
    )
    whole.supports.append(action)
    return whole
