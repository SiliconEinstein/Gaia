"""Gaia Lang v6 scaffold verbs."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from typing import TYPE_CHECKING, Any

from gaia.engine.lang._boolean_valued import is_boolean_valued
from gaia.engine.lang.dsl._lift import _lift_to_claim
from gaia.engine.lang.runtime.action import (
    Associate,
    CandidateRelation,
    Contradict,
    DependsOn,
    Equal,
    Exclusive,
    GaiaGraph,
    MaterializationLink,
    Scaffold,
)
from gaia.engine.lang.runtime.knowledge import Claim, Knowledge

if TYPE_CHECKING:
    from gaia.engine.lang.runtime.package import CollectedPackage

_CANDIDATE_RELATION_KINDS = frozenset(
    {
        "equal",
        "contradict",
        "exclusive",
    }
)


def _as_claim_tuple(given: Any) -> tuple[Any, ...]:
    """Normalize ``given`` into a tuple of items for downstream verb logic.

    Accepts a single ``Knowledge``/Boolean-valued expression (returned as a
    1-tuple) or any iterable of such items. The single-expression case is
    detected via :func:`is_boolean_valued` so that callers can write e.g.
    ``depends_on(c, given=p1 & p2)`` without wrapping in ``[…]``.
    """
    if isinstance(given, Knowledge) or is_boolean_valued(given):
        return (given,)
    return tuple(given)


def depends_on(
    conclusion: Any,
    *,
    given: Any,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> DependsOn:
    """Record unformalized load-bearing dependencies for a Claim.

    ``conclusion`` and every entry of ``given`` may be any Boolean-valued
    expression (``Claim``, ``ClaimAtom``, Formula node, or ``BoolExpr``);
    non-``Claim`` inputs are lifted to helper Claims at the verb boundary
    per RFC #703.
    """
    conclusion = _lift_to_claim(conclusion, verb="depends_on", position="conclusion")
    given_tuple = tuple(
        _lift_to_claim(item, verb="depends_on", position=f"given[{i}]")
        for i, item in enumerate(_as_claim_tuple(given))
    )
    if not given_tuple:
        raise ValueError("depends_on requires at least one given Claim")
    return DependsOn(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata=dict(metadata or {}),
        conclusion=conclusion,
        given=given_tuple,
    )


def candidate_relation(
    *,
    claims: list[Any] | tuple[Any, ...],
    pattern: str | None = None,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> CandidateRelation:
    """Record a hypothesized relation without triggering formal semantics.

    Every entry of ``claims`` may be any Boolean-valued expression
    (``Claim``, ``ClaimAtom``, Formula node, or ``BoolExpr``);
    non-``Claim`` inputs are lifted to helper Claims at the verb boundary
    per RFC #703.
    """
    claim_tuple = tuple(
        _lift_to_claim(item, verb="candidate_relation", position=f"claims[{i}]")
        for i, item in enumerate(claims)
    )
    if len(claim_tuple) < 2:
        raise ValueError("candidate_relation requires at least two Claims")
    if pattern is not None and pattern not in _CANDIDATE_RELATION_KINDS:
        allowed = ", ".join(sorted(_CANDIDATE_RELATION_KINDS))
        raise ValueError(f"candidate_relation pattern must be one of: {allowed}")
    if pattern == "contradict" and len(claim_tuple) != 2:
        raise ValueError('candidate_relation(pattern="contradict") requires exactly two Claims')
    return CandidateRelation(
        label=label,
        rationale=rationale,
        background=list(background or []),
        metadata=dict(metadata or {}),
        claims=claim_tuple,
        pattern=pattern,
    )


def materialize(
    scaffold: Scaffold,
    *,
    by: GaiaGraph
    | Claim
    | str
    | list[GaiaGraph | Claim | str]
    | tuple[GaiaGraph | Claim | str, ...],
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> MaterializationLink:
    """Record a checked link from scaffold to formal graph records."""
    if not isinstance(scaffold, Scaffold):
        raise TypeError("materialize scaffold must be a Scaffold")
    pkg = _materialization_package(scaffold)
    records = _resolve_materializers(scaffold, by)
    if not records:
        raise ValueError("materialize requires at least one by record")
    for record in records:
        if isinstance(record, Scaffold):
            raise TypeError("materialize by records must not be Scaffold records")
        if record._package is not pkg or record not in pkg.actions:
            raise ValueError("materialize by records must belong to the scaffold package")
    core_claims = _scaffold_core_claims(scaffold)
    core_ids = {id(claim) for claim in core_claims}
    if not any(_record_references_claims(record, core_ids) for record in records):
        raise ValueError("materialize by records must reference at least one scaffold core claims")
    _validate_pattern_consistency(scaffold, records)

    link = MaterializationLink(
        scaffold=scaffold,
        by=records,
        label=label,
        rationale=rationale,
        metadata=dict(metadata or {}),
    )
    pkg._register_materialization(link)
    return link


def _materialization_package(scaffold: Scaffold) -> CollectedPackage:
    pkg = scaffold._package
    if pkg is None:
        from gaia.engine.lang.runtime.knowledge import _current_package

        pkg = _current_package.get()
    if pkg is None or scaffold._package is not pkg or scaffold not in pkg.actions:
        raise ValueError("materialize requires a scaffold registered in a package")
    return pkg


def _resolve_materializers(
    scaffold: Scaffold,
    by: GaiaGraph
    | Claim
    | str
    | list[GaiaGraph | Claim | str]
    | tuple[GaiaGraph | Claim | str, ...],
) -> tuple[GaiaGraph, ...]:
    items = by if isinstance(by, list | tuple) else (by,)
    return tuple(_resolve_materializer(scaffold, item) for item in items)


def _resolve_materializer(scaffold: Scaffold, item: GaiaGraph | Claim | str) -> GaiaGraph:
    if isinstance(item, GaiaGraph):
        return item
    if isinstance(item, Claim):
        producers = [
            action
            for action in item.from_actions
            # Defensive: scaffold records should not be claim attachments.
            if isinstance(action, GaiaGraph) and not isinstance(action, Scaffold)
        ]
        if len(producers) == 1:
            return producers[0]
        if not producers:
            raise ValueError("materialize by Claim has no producing graph record")
        raise ValueError("materialize by Claim is ambiguous; use a graph label")
    if isinstance(item, str):
        pkg = scaffold._package
        if pkg is None:
            from gaia.engine.lang.runtime.knowledge import _current_package

            pkg = _current_package.get()
        if pkg is None:
            raise ValueError(
                "materialize by label requires an active package or registered scaffold"
            )
        matches = [action for action in pkg.actions if getattr(action, "label", None) == item]
        if len(matches) == 1:
            return matches[0]
        if not matches:
            raise ValueError(f"materialize could not resolve graph label {item!r}")
        raise ValueError(f"materialize graph label {item!r} is ambiguous")
    raise TypeError(
        f"materialize by entries must be GaiaGraph, Claim, or str, got {type(item).__name__}"
    )


def _scaffold_core_claims(scaffold: Scaffold) -> tuple[Claim, ...]:
    if isinstance(scaffold, DependsOn):
        claims = [scaffold.conclusion, *scaffold.given]
        return tuple(claim for claim in claims if isinstance(claim, Claim))
    if isinstance(scaffold, CandidateRelation):
        return scaffold.claims
    raise TypeError(f"{type(scaffold).__name__} does not define scaffold core claims")


def _record_references_claims(record: GaiaGraph, claim_ids: set[int]) -> bool:
    return any(id(claim) in claim_ids for claim in _iter_record_claims(record))


def _iter_record_claims(value: Any) -> tuple[Claim, ...]:
    """Find semantic claim references for materialization core-claim checks.

    Ambient fields such as background, warrants, and metadata do not count as
    references that formalize a scaffold obligation.
    """
    seen: set[int] = set()
    claims: list[Claim] = []

    def visit(item: Any, *, field_name: str | None = None) -> None:
        if field_name in {"background", "warrants", "metadata"}:
            return
        if isinstance(item, Claim):
            key = id(item)
            if key not in seen:
                seen.add(key)
                claims.append(item)
            return
        if isinstance(item, dict):
            for child in item.values():
                visit(child)
            return
        if isinstance(item, list | tuple | set | frozenset):
            for child in item:
                visit(child)
            return
        if is_dataclass(item):
            for data_field in fields(item):
                if data_field.name.startswith("_"):
                    continue
                visit(getattr(item, data_field.name), field_name=data_field.name)

    visit(value)
    return tuple(claims)


def _relation_pattern(record: GaiaGraph) -> str | None:
    if isinstance(record, Equal):
        return "equal"
    if isinstance(record, Contradict):
        return "contradict"
    if isinstance(record, Exclusive):
        return "exclusive"
    if isinstance(record, Associate):
        return record.pattern
    return None


def _validate_pattern_consistency(scaffold: Scaffold, records: tuple[GaiaGraph, ...]) -> None:
    if not isinstance(scaffold, CandidateRelation) or scaffold.pattern is None:
        return
    for record in records:
        pattern = _relation_pattern(record)
        if pattern is not None and pattern != scaffold.pattern:
            raise ValueError(
                f"materialize pattern mismatch: scaffold pattern {scaffold.pattern!r} "
                f"cannot be materialized by {pattern!r}"
            )
