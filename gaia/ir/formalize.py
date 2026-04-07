"""IR-side formalization of named strategies into FormalStrategy skeletons.

Named reasoning families lower to canonical FormalExpr templates inside Gaia IR.
This module generates both the explicit intermediate Knowledge nodes and the
matching FormalStrategy for those templates.
"""

from __future__ import annotations

import hashlib
from collections import defaultdict
from dataclasses import dataclass
from typing import Any

from gaia.ir.knowledge import Knowledge, KnowledgeType, make_qid
from gaia.ir.operator import Operator
from gaia.ir.strategy import (
    FormalExpr,
    FormalStrategy,
    Step,
    StrategyType,
    _FORMAL_STRATEGY_TYPES,
)

_HELPER_KIND_BY_OPERATOR = {
    "conjunction": "conjunction_result",
    "disjunction": "disjunction_result",
    "equivalence": "equivalence_result",
    "contradiction": "contradiction_result",
    "complement": "complement_result",
}


@dataclass
class FormalizationResult:
    """Generated intermediate claims plus the fully-expanded FormalStrategy."""

    knowledges: list[Knowledge]
    strategy: FormalStrategy


def _sha256_hex(data: str, length: int = 16) -> str:
    return hashlib.sha256(data.encode()).hexdigest()[:length]


def _generated_claim_id(
    scope: str,
    strategy_type: StrategyType,
    premises: list[str],
    conclusion: str,
    role: str,
    index: int,
    *,
    namespace: str | None = None,
    package_name: str | None = None,
) -> tuple[str, str | None]:
    """Return (id, label) for a generated intermediate claim.

    Returns a QID built from namespace:package_name::__{role}_{hash8}.
    """
    payload = f"{scope}|{strategy_type.value}|{premises}|{conclusion}|{role}|{index}"
    hash8 = _sha256_hex(payload, length=8)
    label = f"__{role}_{hash8}"
    return make_qid(namespace, package_name, label), label  # type: ignore[arg-type]


def _generated_interface_claim_id(
    scope: str,
    strategy_type: StrategyType,
    anchor: str,
    conclusion: str,
    role: str,
    index: int,
    *,
    namespace: str | None = None,
    package_name: str | None = None,
) -> tuple[str, str | None]:
    """Return (id, label) for a generated interface claim.

    Returns a QID built from namespace:package_name::__{role}_{hash8}.
    """
    payload = f"{scope}|{strategy_type.value}|{anchor}|{conclusion}|{role}|{index}"
    hash8 = _sha256_hex(payload, length=8)
    label = f"__{role}_{hash8}"
    return make_qid(namespace, package_name, label), label  # type: ignore[arg-type]


class _TemplateBuilder:
    def __init__(
        self,
        scope: str,
        strategy_type: StrategyType,
        premises: list[str],
        conclusion: str,
        *,
        namespace: str | None = None,
        package_name: str | None = None,
    ):
        self.scope = scope
        self.strategy_type = strategy_type
        self.premises = list(premises)
        self.conclusion = conclusion
        self.namespace = namespace
        self.package_name = package_name
        self.knowledges: list[Knowledge] = []
        self._role_counters: dict[str, int] = defaultdict(int)
        self.interface_roles: dict[str, list[str]] = defaultdict(list)

    def add_latent(self, role: str, canonical_name: str) -> Knowledge:
        return self._add_claim(role=role, canonical_name=canonical_name, kind="latent_claim")

    def add_interface_claim(self, role: str, canonical_name: str, *, anchor: str) -> Knowledge:
        index = self._role_counters[role]
        self._role_counters[role] += 1

        claim_id, label = _generated_interface_claim_id(
            self.scope,
            self.strategy_type,
            anchor,
            self.conclusion,
            role,
            index,
            namespace=self.namespace,
            package_name=self.package_name,
        )
        metadata: dict[str, Any] = {
            "generated": True,
            "generated_kind": "interface_claim",
            "interface_role": role,
            "visibility": "strategy_interface",
            "canonical_name": canonical_name,
            "owning_strategy_type": self.strategy_type.value,
        }
        knowledge = Knowledge(
            id=claim_id,
            label=label,
            type=KnowledgeType.CLAIM,
            content=canonical_name,
            metadata=metadata,
        )
        self.knowledges.append(knowledge)
        self.interface_roles[role].append(knowledge.id)
        return knowledge

    def add_helper(self, operator_name: str, canonical_name: str) -> Knowledge:
        return self._add_claim(
            role=_HELPER_KIND_BY_OPERATOR[operator_name],
            canonical_name=canonical_name,
            kind="helper_claim",
            helper_kind=_HELPER_KIND_BY_OPERATOR[operator_name],
        )

    def _add_claim(
        self,
        *,
        role: str,
        canonical_name: str,
        kind: str,
        helper_kind: str | None = None,
    ) -> Knowledge:
        index = self._role_counters[role]
        self._role_counters[role] += 1

        claim_id, label = _generated_claim_id(
            self.scope,
            self.strategy_type,
            self.premises,
            self.conclusion,
            role,
            index,
            namespace=self.namespace,
            package_name=self.package_name,
        )
        metadata: dict[str, Any] = {
            "generated": True,
            "generated_kind": kind,
            "intermediate_role": role,
            "visibility": "formal_internal",
            "canonical_name": canonical_name,
            "owning_strategy_type": self.strategy_type.value,
        }
        if helper_kind is not None:
            metadata["helper_kind"] = helper_kind
            metadata["helper_visibility"] = "formal_internal"

        knowledge = Knowledge(
            id=claim_id,
            label=label,
            type=KnowledgeType.CLAIM,
            content=canonical_name,
            metadata=metadata,
        )
        self.knowledges.append(knowledge)
        return knowledge


def _all_true_name(variables: list[str]) -> str:
    return f"all_true({','.join(variables)})"


def _any_true_name(variables: list[str]) -> str:
    return f"any_true({','.join(variables)})"


def _same_truth_name(left: str, right: str) -> str:
    return f"same_truth({left},{right})"


def _explains_name(observation: str) -> str:
    return f"explains({observation})"


def _not_both_true_name(left: str, right: str) -> str:
    return f"not_both_true({left},{right})"


def _opposite_truth_name(left: str, right: str) -> str:
    return f"opposite_truth({left},{right})"


def _build_deduction(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) < 1:
        raise ValueError("deduction formalization requires at least 1 premise")
    if len(builder.premises) == 1:
        # Single premise: direct implication, no conjunction needed
        return [
            Operator(
                operator="implication",
                variables=[builder.premises[0]],
                conclusion=builder.conclusion,
            ),
        ]
    conjunction = builder.add_helper("conjunction", _all_true_name(builder.premises))
    return [
        Operator(operator="conjunction", variables=builder.premises, conclusion=conjunction.id),
        Operator(operator="implication", variables=[conjunction.id], conclusion=builder.conclusion),
    ]


def _build_mathematical_induction(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) != 2:
        raise ValueError("mathematical_induction formalization requires exactly 2 premises")
    conjunction = builder.add_helper("conjunction", _all_true_name(builder.premises))
    return [
        Operator(operator="conjunction", variables=builder.premises, conclusion=conjunction.id),
        Operator(operator="implication", variables=[conjunction.id], conclusion=builder.conclusion),
    ]


def _build_elimination(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) < 3 or len(builder.premises[1:]) % 2 != 0:
        raise ValueError(
            "elimination formalization requires premises=[Exhaustiveness, Candidate1, Evidence1, ...]"
        )
    exhaustiveness = builder.premises[0]
    builder.interface_roles["exhaustiveness"].append(exhaustiveness)
    remainder = builder.premises[1:]
    candidate_pairs = list(zip(remainder[::2], remainder[1::2], strict=True))
    for candidate, evidence in candidate_pairs:
        builder.interface_roles["eliminated_candidate"].append(candidate)
        builder.interface_roles["elimination_evidence"].append(evidence)

    disjunction = builder.add_helper(
        "disjunction",
        _any_true_name([candidate for candidate, _ in candidate_pairs] + [builder.conclusion]),
    )
    equivalence = builder.add_helper(
        "equivalence",
        _same_truth_name(disjunction.id, exhaustiveness),
    )

    contradiction_results = [
        builder.add_helper("contradiction", _not_both_true_name(candidate, evidence))
        for candidate, evidence in candidate_pairs
    ]

    elimination_gate_inputs = [exhaustiveness]
    operators = [
        Operator(
            operator="disjunction",
            variables=[candidate for candidate, _ in candidate_pairs] + [builder.conclusion],
            conclusion=disjunction.id,
        ),
        Operator(
            operator="equivalence",
            variables=[disjunction.id, exhaustiveness],
            conclusion=equivalence.id,
        ),
    ]

    for (candidate, evidence), contradiction in zip(
        candidate_pairs, contradiction_results, strict=True
    ):
        operators.append(
            Operator(
                operator="contradiction",
                variables=[candidate, evidence],
                conclusion=contradiction.id,
            )
        )
        elimination_gate_inputs.extend([evidence, contradiction.id])

    conjunction = builder.add_helper("conjunction", _all_true_name(elimination_gate_inputs))
    operators.append(
        Operator(
            operator="conjunction",
            variables=elimination_gate_inputs,
            conclusion=conjunction.id,
        )
    )
    operators.append(
        Operator(operator="implication", variables=[conjunction.id], conclusion=builder.conclusion)
    )
    return operators


def _build_case_analysis(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) < 3 or len(builder.premises[1:]) % 2 != 0:
        raise ValueError(
            "case_analysis formalization requires premises=[Exhaustiveness, Case1, Support1, ...]"
        )
    exhaustiveness = builder.premises[0]
    builder.interface_roles["exhaustiveness"].append(exhaustiveness)
    remainder = builder.premises[1:]
    case_pairs = list(zip(remainder[::2], remainder[1::2], strict=True))
    for case_claim, support in case_pairs:
        builder.interface_roles["case"].append(case_claim)
        builder.interface_roles["case_support"].append(support)

    disjunction = builder.add_helper(
        "disjunction",
        _any_true_name([case_claim for case_claim, _ in case_pairs]),
    )
    equivalence = builder.add_helper(
        "equivalence",
        _same_truth_name(disjunction.id, exhaustiveness),
    )
    operators = [
        Operator(
            operator="disjunction",
            variables=[case_claim for case_claim, _ in case_pairs],
            conclusion=disjunction.id,
        ),
        Operator(
            operator="equivalence",
            variables=[disjunction.id, exhaustiveness],
            conclusion=equivalence.id,
        ),
    ]
    for case_claim, support in case_pairs:
        conjunction = builder.add_helper(
            "conjunction",
            _all_true_name([case_claim, support]),
        )
        operators.append(
            Operator(
                operator="conjunction",
                variables=[case_claim, support],
                conclusion=conjunction.id,
            )
        )
        operators.append(
            Operator(
                operator="implication",
                variables=[conjunction.id],
                conclusion=builder.conclusion,
            )
        )
    return operators


def _build_abduction(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) not in {1, 2}:
        raise ValueError(
            "abduction formalization requires observation plus optional alternative explanation"
        )
    observation = builder.premises[0]
    if len(builder.premises) == 1:
        # The leak / alternative explanation is a public interface claim because
        # it carries independent uncertainty and may be supported elsewhere.
        alternative_explanation = builder.add_interface_claim(
            "alternative_explanation",
            f"alternative_explanation_for({observation})",
            anchor=observation,
        )
        builder.premises.append(alternative_explanation.id)
        alternative_explanation_id = alternative_explanation.id
    else:
        alternative_explanation_id = builder.premises[1]
    builder.interface_roles["observation"].append(observation)
    if len(builder.premises) == 2 and alternative_explanation_id == builder.premises[1]:
        if not builder.interface_roles["alternative_explanation"]:
            builder.interface_roles["alternative_explanation"].append(alternative_explanation_id)
    explanation_union = builder.add_helper(
        "disjunction",
        _explains_name(observation),
    )
    equivalence = builder.add_helper(
        "equivalence",
        _same_truth_name(explanation_union.id, observation),
    )
    return [
        Operator(
            operator="disjunction",
            variables=[builder.conclusion, alternative_explanation_id],
            conclusion=explanation_union.id,
        ),
        Operator(
            operator="equivalence",
            variables=[explanation_union.id, observation],
            conclusion=equivalence.id,
        ),
    ]


def _build_analogy(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) != 2:
        raise ValueError("analogy formalization requires exactly 2 premises")
    conjunction = builder.add_helper("conjunction", _all_true_name(builder.premises))
    return [
        Operator(operator="conjunction", variables=builder.premises, conclusion=conjunction.id),
        Operator(operator="implication", variables=[conjunction.id], conclusion=builder.conclusion),
    ]


def _build_extrapolation(builder: _TemplateBuilder) -> list[Operator]:
    if len(builder.premises) != 2:
        raise ValueError("extrapolation formalization requires exactly 2 premises")
    conjunction = builder.add_helper("conjunction", _all_true_name(builder.premises))
    return [
        Operator(operator="conjunction", variables=builder.premises, conclusion=conjunction.id),
        Operator(operator="implication", variables=[conjunction.id], conclusion=builder.conclusion),
    ]


_BUILDERS = {
    StrategyType.DEDUCTION: _build_deduction,
    StrategyType.ELIMINATION: _build_elimination,
    StrategyType.MATHEMATICAL_INDUCTION: _build_mathematical_induction,
    StrategyType.CASE_ANALYSIS: _build_case_analysis,
    StrategyType.ABDUCTION: _build_abduction,
    StrategyType.ANALOGY: _build_analogy,
    StrategyType.EXTRAPOLATION: _build_extrapolation,
}


def formalize_named_strategy(
    *,
    scope: str,
    type_: StrategyType | str,
    premises: list[str],
    conclusion: str,
    namespace: str | None = None,
    package_name: str | None = None,
    background: list[str] | None = None,
    steps: list[Step] | None = None,
    metadata: dict[str, Any] | None = None,
) -> FormalizationResult:
    """Generate the canonical FormalStrategy skeleton for a named strategy family.

    ``namespace`` and ``package_name`` are required so that generated
    intermediate Knowledge IDs use the QID format
    ({namespace}:{package_name}::__{role}_{hash8}).
    """
    if scope != "local":
        raise ValueError("formalize_named_strategy only supports scope='local'")
    if namespace is None or package_name is None:
        raise ValueError("formalize_named_strategy requires namespace and package_name")
    if type_ == "reductio":
        raise ValueError(
            "reductio is deferred in Gaia IR core; the public-interface contract for "
            "hypothetical assumption/consequence nodes is not yet fixed"
        )
    strategy_type = StrategyType(type_)
    if strategy_type not in _FORMAL_STRATEGY_TYPES:
        allowed = ", ".join(sorted(t.value for t in _FORMAL_STRATEGY_TYPES))
        raise ValueError(
            f"formalize_named_strategy only supports named FormalStrategy types: {allowed}; "
            f"got {strategy_type.value}"
        )

    builder = _TemplateBuilder(
        scope=scope,
        strategy_type=strategy_type,
        premises=premises,
        conclusion=conclusion,
        namespace=namespace,
        package_name=package_name,
    )
    if strategy_type == StrategyType.CASE_ANALYSIS and (metadata or {}).get(
        "include_other_relevant_case"
    ):
        raise ValueError(
            "open-world case_analysis is deferred; model residual uncertainty on the "
            "coverage/exhaustiveness claim instead"
        )
    operators = _BUILDERS[strategy_type](builder)
    strategy_metadata = dict(metadata or {})
    strategy_metadata["generated_formal_expr"] = True
    strategy_metadata["formalization_template"] = strategy_type.value
    if builder.interface_roles:
        strategy_metadata["interface_roles"] = dict(builder.interface_roles)

    strategy = FormalStrategy(
        scope=scope,
        type=strategy_type,
        premises=builder.premises,
        conclusion=conclusion,
        background=background,
        steps=steps,
        metadata=strategy_metadata,
        formal_expr=FormalExpr(operators=operators),
    )

    for knowledge in builder.knowledges:
        knowledge.metadata = dict(knowledge.metadata or {})
        knowledge.metadata["owning_strategy_id"] = strategy.strategy_id

    return FormalizationResult(knowledges=builder.knowledges, strategy=strategy)
