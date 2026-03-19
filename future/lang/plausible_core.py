"""Minimal plausible-reasoning kernel prototype.

This module is intentionally standalone. It does not integrate with the
existing YAML or Typst pipelines yet; the goal is to make the proposed core
design executable and inspectable in tests.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal


DeclarationKind = Literal["observation", "setting", "claim", "relation", "question"]
StructuralStatus = Literal["closed", "has_holes"]
OriginKind = Literal["global", "local", "assumption"]


class KernelError(ValueError):
    """Raised when a proof is structurally invalid."""


@dataclass(frozen=True)
class Proof:
    steps: list["Step"]


@dataclass(frozen=True)
class Observation:
    name: str
    text: str
    kind: DeclarationKind = "observation"
    proof: Proof | None = None


@dataclass(frozen=True)
class Setting:
    name: str
    text: str
    kind: DeclarationKind = "setting"
    proof: Proof | None = None


@dataclass(frozen=True)
class Claim:
    name: str
    text: str
    proof: Proof | None = None
    kind: DeclarationKind = "claim"


@dataclass(frozen=True)
class Relation:
    name: str
    relation_kind: Literal["contradiction", "equivalence"]
    text: str
    proof: Proof | None = None
    kind: DeclarationKind = "relation"


@dataclass(frozen=True)
class Question:
    name: str
    text: str
    kind: DeclarationKind = "question"
    proof: Proof | None = None


Declaration = Observation | Setting | Claim | Relation | Question


@dataclass(frozen=True)
class Use:
    name: str


@dataclass(frozen=True)
class Have:
    name: str
    statement: str
    proof: Proof


@dataclass(frozen=True)
class Assume:
    name: str
    statement: str
    proof: Proof


@dataclass(frozen=True)
class DeductionMode:
    supports: tuple[str, ...]


@dataclass(frozen=True)
class AbductionMode:
    observations: tuple[str, ...]
    alternatives: tuple[str, ...]
    warrant: str
    comparison: str


@dataclass(frozen=True)
class SynthesisMode:
    supports: tuple[str, ...]
    convergence: str


@dataclass(frozen=True)
class ContradictionMode:
    between: tuple[str, str]


CloseMode = DeductionMode | AbductionMode | SynthesisMode | ContradictionMode


@dataclass(frozen=True)
class Close:
    mode: CloseMode


@dataclass(frozen=True)
class Hole:
    reason: str


Step = Use | Have | Assume | Close | Hole


@dataclass(frozen=True)
class Program:
    declarations: list[Declaration]

    def index(self) -> dict[str, Declaration]:
        seen: dict[str, Declaration] = {}
        for declaration in self.declarations:
            if declaration.name in seen:
                raise KernelError(f"duplicate declaration '{declaration.name}'")
            seen[declaration.name] = declaration
        return seen


@dataclass(frozen=True)
class VisibleFact:
    name: str
    kind: str
    text: str
    origin: OriginKind


@dataclass(frozen=True)
class CheckedFinalStep:
    strategy: str
    premise_refs: list[VisibleFact] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    warrant: str | None = None
    comparison: str | None = None
    convergence: str | None = None
    between: list[str] = field(default_factory=list)
    review_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CheckedDerivedFact:
    name: str
    statement: str
    proof: "CheckedProof"


@dataclass(frozen=True)
class CheckedAssumption:
    name: str
    statement: str
    proof: "CheckedProof"


@dataclass(frozen=True)
class CheckedProof:
    goal_name: str
    goal_kind: str
    goal_text: str
    structural_status: StructuralStatus
    trace_lines: list[str]
    derived_facts: list[CheckedDerivedFact]
    assumptions: list[CheckedAssumption]
    final_step: CheckedFinalStep | None
    holes: list[str]


@dataclass(frozen=True)
class CheckedDeclaration:
    name: str
    kind: str
    text: str
    relation_kind: str | None
    proof: CheckedProof | None


@dataclass(frozen=True)
class CheckedProgram:
    declarations: dict[str, CheckedDeclaration]


@dataclass(frozen=True)
class PacketPremise:
    name: str
    kind: str
    text: str
    origin: str


@dataclass(frozen=True)
class PacketFinalStep:
    strategy: str
    supports: list[str] = field(default_factory=list)
    alternatives: list[str] = field(default_factory=list)
    warrant: str | None = None
    comparison: str | None = None
    convergence: str | None = None
    between: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ReviewPacketTarget:
    name: str
    kind: str
    text: str


@dataclass(frozen=True)
class DerivedFactPacket:
    name: str
    text: str
    structural_status: StructuralStatus
    proof_trace: list[str]
    final_step: PacketFinalStep | None
    holes: list[str]


@dataclass(frozen=True)
class ReviewPacket:
    target: ReviewPacketTarget
    structural_status: StructuralStatus
    direct_premises: list[PacketPremise]
    proof_trace: list[str]
    derived_facts: list[DerivedFactPacket]
    final_step: PacketFinalStep | None
    review_questions: list[str]
    holes: list[str]


def check_program(program: Program) -> CheckedProgram:
    """Check every declaration proof in the program."""
    declarations = program.index()
    checked: dict[str, CheckedDeclaration] = {}

    for declaration in program.declarations:
        proof = None
        if declaration.proof is not None:
            proof = _check_proof(
                declarations=declarations,
                proof=declaration.proof,
                goal_name=declaration.name,
                goal_kind=declaration.kind,
                goal_text=declaration.text,
                relation_kind=getattr(declaration, "relation_kind", None),
                scope={},
            )

        checked[declaration.name] = CheckedDeclaration(
            name=declaration.name,
            kind=declaration.kind,
            text=declaration.text,
            relation_kind=getattr(declaration, "relation_kind", None),
            proof=proof,
        )

    return CheckedProgram(declarations=checked)


def build_review_packet(checked: CheckedProgram, target_name: str) -> ReviewPacket:
    """Create a deterministic review packet from a checked declaration."""
    declaration = checked.declarations.get(target_name)
    if declaration is None:
        raise KernelError(f"unknown declaration '{target_name}'")
    if declaration.proof is None:
        raise KernelError(f"declaration '{target_name}' has no proof")

    proof = declaration.proof
    final_step = _packet_final_step(proof.final_step)
    direct_premises = []
    if proof.final_step is not None:
        direct_premises = [
            PacketPremise(
                name=premise.name,
                kind=premise.kind,
                text=premise.text,
                origin=premise.origin,
            )
            for premise in proof.final_step.premise_refs
        ]

    derived_facts = [
        DerivedFactPacket(
            name=derived.name,
            text=derived.statement,
            structural_status=derived.proof.structural_status,
            proof_trace=derived.proof.trace_lines,
            final_step=_packet_final_step(derived.proof.final_step),
            holes=derived.proof.holes,
        )
        for derived in proof.derived_facts
    ]

    return ReviewPacket(
        target=ReviewPacketTarget(
            name=declaration.name,
            kind=declaration.kind,
            text=declaration.text,
        ),
        structural_status=proof.structural_status,
        direct_premises=direct_premises,
        proof_trace=proof.trace_lines,
        derived_facts=derived_facts,
        final_step=final_step,
        review_questions=proof.final_step.review_questions if proof.final_step is not None else [],
        holes=proof.holes,
    )


def render_review_packet_markdown(packet: ReviewPacket) -> str:
    """Render a review packet as human-readable Markdown."""
    lines = [
        "# Review Target",
        "",
        f"- Name: {packet.target.name}",
        f"- Kind: {packet.target.kind}",
        f"- Structural status: {packet.structural_status}",
        "",
        "## Conclusion",
        "",
        packet.target.text,
        "",
    ]

    if packet.direct_premises:
        lines.extend(["## Direct Premises", ""])
        for premise in packet.direct_premises:
            lines.append(f"- {premise.name} [{premise.kind}, {premise.origin}]")
            lines.append(f"  {premise.text}")
        lines.append("")

    if packet.derived_facts:
        lines.extend(["## Derived Facts", ""])
        for derived in packet.derived_facts:
            lines.append(f"- {derived.name} [{derived.structural_status}]")
            lines.append(f"  {derived.text}")
            if derived.final_step is not None:
                lines.append(f"  final step: {derived.final_step.strategy}")
            if derived.holes:
                lines.append(f"  holes: {', '.join(derived.holes)}")
        lines.append("")

    if packet.proof_trace:
        lines.extend(["## Proof Trace", ""])
        for line in packet.proof_trace:
            lines.append(f"- {line}")
        lines.append("")

    if packet.final_step is not None:
        lines.extend(["## Final Step", "", f"- Strategy: {packet.final_step.strategy}"])
        if packet.final_step.supports:
            lines.append(f"- Supports: {', '.join(packet.final_step.supports)}")
        if packet.final_step.alternatives:
            lines.append(f"- Alternatives: {', '.join(packet.final_step.alternatives)}")
        if packet.final_step.warrant:
            lines.append(f"- Warrant: {packet.final_step.warrant}")
        if packet.final_step.comparison:
            lines.append(f"- Comparison: {packet.final_step.comparison}")
        if packet.final_step.convergence:
            lines.append(f"- Convergence: {packet.final_step.convergence}")
        if packet.final_step.between:
            lines.append(f"- Between: {', '.join(packet.final_step.between)}")
        lines.append("")

    if packet.review_questions:
        lines.extend(["## Review Questions", ""])
        for question in packet.review_questions:
            lines.append(f"- {question}")
        lines.append("")

    if packet.holes:
        lines.extend(["## Holes", ""])
        for hole in packet.holes:
            lines.append(f"- {hole}")
        lines.append("")

    return "\n".join(lines).rstrip()


def _packet_final_step(final_step: CheckedFinalStep | None) -> PacketFinalStep | None:
    if final_step is None:
        return None

    return PacketFinalStep(
        strategy=final_step.strategy,
        supports=[premise.name for premise in final_step.premise_refs],
        alternatives=final_step.alternatives,
        warrant=final_step.warrant,
        comparison=final_step.comparison,
        convergence=final_step.convergence,
        between=final_step.between,
    )


def _check_proof(
    declarations: dict[str, Declaration],
    proof: Proof,
    goal_name: str,
    goal_kind: str,
    goal_text: str,
    relation_kind: str | None,
    scope: dict[str, VisibleFact],
) -> CheckedProof:
    trace_lines: list[str] = []
    derived_facts: list[CheckedDerivedFact] = []
    assumptions: list[CheckedAssumption] = []
    local_scope = dict(scope)
    holes: list[str] = []
    final_step: CheckedFinalStep | None = None

    for index, step in enumerate(proof.steps):
        is_last = index == len(proof.steps) - 1

        if isinstance(step, Use):
            if not is_last and final_step is not None:
                raise KernelError(f"proof for '{goal_name}' continues after close")
            visible = _lookup_global(declarations, step.name)
            local_scope[step.name] = visible
            trace_lines.append(f"use {step.name}")
            continue

        if isinstance(step, Have):
            _ensure_new_local_name(step.name, local_scope, declarations)
            trace_lines.append(f"have {step.name}")
            checked_nested = _check_proof(
                declarations=declarations,
                proof=step.proof,
                goal_name=step.name,
                goal_kind="claim",
                goal_text=step.statement,
                relation_kind=None,
                scope=dict(local_scope),
            )
            derived_facts.append(
                CheckedDerivedFact(
                    name=step.name,
                    statement=step.statement,
                    proof=checked_nested,
                )
            )
            if checked_nested.structural_status == "closed":
                local_scope[step.name] = VisibleFact(
                    name=step.name,
                    kind="local_claim",
                    text=step.statement,
                    origin="local",
                )
            else:
                holes.append(f"derived fact '{step.name}' is incomplete")
            continue

        if isinstance(step, Assume):
            _ensure_new_local_name(step.name, local_scope, declarations)
            trace_lines.append(f"assume {step.name}")
            branch_scope = dict(local_scope)
            branch_scope[step.name] = VisibleFact(
                name=step.name,
                kind="assumption",
                text=step.statement,
                origin="assumption",
            )
            checked_branch = _check_proof(
                declarations=declarations,
                proof=step.proof,
                goal_name=goal_name,
                goal_kind=goal_kind,
                goal_text=goal_text,
                relation_kind=relation_kind,
                scope=branch_scope,
            )
            assumptions.append(
                CheckedAssumption(
                    name=step.name,
                    statement=step.statement,
                    proof=checked_branch,
                )
            )
            if checked_branch.structural_status != "closed":
                holes.append(f"assumption branch '{step.name}' is incomplete")
            continue

        if isinstance(step, Hole):
            if not is_last:
                raise KernelError(f"hole in '{goal_name}' must be the final step")
            holes.append(step.reason)
            trace_lines.append(f"hole: {step.reason}")
            continue

        if isinstance(step, Close):
            if not is_last:
                raise KernelError(f"close in '{goal_name}' must be the final step")
            final_step = _validate_close(
                declarations=declarations,
                goal_name=goal_name,
                goal_kind=goal_kind,
                relation_kind=relation_kind,
                scope=local_scope,
                mode=step.mode,
            )
            trace_lines.append(_close_trace(step.mode))
            continue

        raise KernelError(f"unsupported step in '{goal_name}': {step}")

    if final_step is None and not holes:
        holes.append("missing close step")

    status: StructuralStatus = "closed" if final_step is not None and not holes else "has_holes"
    return CheckedProof(
        goal_name=goal_name,
        goal_kind=goal_kind,
        goal_text=goal_text,
        structural_status=status,
        trace_lines=trace_lines,
        derived_facts=derived_facts,
        assumptions=assumptions,
        final_step=final_step if not holes else None,
        holes=holes,
    )


def _lookup_global(declarations: dict[str, Declaration], name: str) -> VisibleFact:
    declaration = declarations.get(name)
    if declaration is None:
        raise KernelError(f"unknown declaration '{name}'")
    kind = declaration.kind
    if kind == "relation":
        kind = getattr(declaration, "relation_kind")
    return VisibleFact(
        name=declaration.name,
        kind=kind,
        text=declaration.text,
        origin="global",
    )


def _ensure_new_local_name(
    name: str,
    scope: dict[str, VisibleFact],
    declarations: dict[str, Declaration],
) -> None:
    if name in scope or name in declarations:
        raise KernelError(f"local name '{name}' already exists")


def _resolve_visible_names(
    names: tuple[str, ...],
    scope: dict[str, VisibleFact],
    *,
    step_name: str,
) -> list[VisibleFact]:
    resolved: list[VisibleFact] = []
    for name in names:
        visible = scope.get(name)
        if visible is None:
            raise KernelError(f"{step_name} references '{name}' which is not in scope")
        resolved.append(visible)
    return resolved


def _validate_close(
    declarations: dict[str, Declaration],
    goal_name: str,
    goal_kind: str,
    relation_kind: str | None,
    scope: dict[str, VisibleFact],
    mode: CloseMode,
) -> CheckedFinalStep:
    if isinstance(mode, DeductionMode):
        supports = _resolve_visible_names(mode.supports, scope, step_name="deduction")
        _ensure_no_self_support(goal_name, supports)
        return CheckedFinalStep(
            strategy="deduction",
            premise_refs=supports,
            review_questions=[
                "Do the cited supports bear directly on the conclusion?",
                "Are there unstated intermediate steps?",
                "If the supports hold, should the conclusion hold as well?",
            ],
        )

    if isinstance(mode, AbductionMode):
        observations = _resolve_visible_names(mode.observations, scope, step_name="abduction")
        _ensure_no_self_support(goal_name, observations)
        alternatives = []
        for alternative_name in mode.alternatives:
            _lookup_global(declarations, alternative_name)
            if alternative_name == goal_name:
                raise KernelError(f"self-support detected in '{goal_name}'")
            alternatives.append(alternative_name)
        return CheckedFinalStep(
            strategy="abduction",
            premise_refs=observations,
            alternatives=alternatives,
            warrant=mode.warrant,
            comparison=mode.comparison,
            review_questions=[
                "Do the listed observations really fit the proposed explanation?",
                "Is the candidate explanation better than the listed alternatives?",
                "Are important alternatives missing from the comparison set?",
                "How strong is the support if the observations are accepted?",
            ],
        )

    if isinstance(mode, SynthesisMode):
        supports = _resolve_visible_names(mode.supports, scope, step_name="synthesis")
        if len(supports) < 2:
            raise KernelError("synthesis requires at least two supports")
        _ensure_no_self_support(goal_name, supports)
        return CheckedFinalStep(
            strategy="synthesis",
            premise_refs=supports,
            convergence=mode.convergence,
            review_questions=[
                "Are the support lines genuinely independent?",
                "Does the synthesis step ignore conflicting evidence?",
                "Do the lines of support converge strongly enough on the conclusion?",
            ],
        )

    if isinstance(mode, ContradictionMode):
        if goal_kind != "relation" or relation_kind != "contradiction":
            raise KernelError(
                f"contradiction close is only valid for contradiction relations, not '{goal_name}'"
            )
        between = _resolve_visible_names(mode.between, scope, step_name="contradiction")
        return CheckedFinalStep(
            strategy="contradiction",
            premise_refs=between,
            between=[item.name for item in between],
            review_questions=[
                "Are the paired claims genuinely incompatible?",
                "Does the proof make both sides strong enough before declaring contradiction?",
            ],
        )

    raise KernelError(f"unsupported close mode in '{goal_name}'")


def _ensure_no_self_support(goal_name: str, supports: list[VisibleFact]) -> None:
    if any(support.name == goal_name for support in supports):
        raise KernelError(f"self-support detected in '{goal_name}'")


def _close_trace(mode: CloseMode) -> str:
    if isinstance(mode, DeductionMode):
        return f"close via deduction({', '.join(mode.supports)})"
    if isinstance(mode, AbductionMode):
        return f"close via abduction({', '.join(mode.observations)})"
    if isinstance(mode, SynthesisMode):
        return f"close via synthesis({', '.join(mode.supports)})"
    if isinstance(mode, ContradictionMode):
        return f"close via contradiction({', '.join(mode.between)})"
    return "close"
