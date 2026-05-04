"""Lower Gaia Lang Formula AST payloads into existing Gaia IR structures.

Milestone B starts with a deliberately small lowering contract: finite-domain
universal quantification grounds to one derived instance claim per domain
member, with one directed deduction/implication from the universal claim to
each instance. It does not collapse the instances into a conjunction.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any

from gaia.ir import Knowledge as IrKnowledge
from gaia.ir import Operator as IrOperator
from gaia.ir import Strategy as IrStrategy
from gaia.ir.formalize import formalize_named_strategy
from gaia.ir.knowledge import KnowledgeType, make_qid
from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import ClaimAtom
from gaia.lang.formula.quantifier import Forall
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Claim


@dataclass(frozen=True)
class FormulaLoweringResult:
    knowledges: list[IrKnowledge]
    operators: list[IrOperator]
    strategies: list[IrStrategy]


def lower_claim_formula(
    claim: Claim,
    *,
    claim_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    """Lower the formula attached to a Claim, if Milestone B supports it."""
    formula = getattr(claim, "formula", None)
    if formula is None:
        return FormulaLoweringResult(knowledges=[], operators=[], strategies=[])
    if isinstance(formula, Forall):
        return _lower_forall(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
        )
    return _lower_formula_to_claim(
        formula,
        target_id=claim_id,
        namespace=namespace,
        package_name=package_name,
        knowledge_map=knowledge_map,
    )


def _lower_forall(
    claim: Claim,
    formula: Forall,
    *,
    claim_id: str,
    namespace: str,
    package_name: str,
) -> FormulaLoweringResult:
    variable = formula.variable
    domain = variable.domain
    if not isinstance(domain, Domain):
        raise ValueError("Forall formula lowering currently requires a finite Domain")

    generated_knowledges: list[IrKnowledge] = []
    generated_strategies: list[IrStrategy] = []
    for value in domain.members:
        binding = {
            "symbol": variable.symbol,
            "domain": domain.label or domain.title or domain.content,
            "value": value,
        }
        instance_id, instance_label = _forall_instance_id(
            namespace=namespace,
            package_name=package_name,
            source_claim_id=claim_id,
            symbol=variable.symbol,
            value=value,
        )
        generated_knowledges.append(
            IrKnowledge(
                id=instance_id,
                label=instance_label,
                type=KnowledgeType.CLAIM,
                content=f"{claim.content} [{variable.symbol}={value!r}]",
                metadata={
                    "generated": True,
                    "generated_kind": "formula_instance",
                    "formula_lowering": "forall_instance",
                    "source_claim": claim_id,
                    "binding": binding,
                    "visibility": "formula_grounding",
                    "review": False,
                },
            )
        )

        result = formalize_named_strategy(
            scope="local",
            type_="deduction",
            premises=[claim_id],
            conclusion=instance_id,
            namespace=namespace,
            package_name=package_name,
            metadata={
                "formula_lowering": "forall_grounding",
                "source_claim": claim_id,
                "binding": binding,
            },
        )
        generated_knowledges.extend(result.knowledges)
        generated_strategies.append(result.strategy)

    return FormulaLoweringResult(
        knowledges=generated_knowledges,
        operators=[],
        strategies=generated_strategies,
    )


def _lower_formula_to_claim(
    formula: Any,
    *,
    target_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    state = _FormulaState(
        namespace=namespace,
        package_name=package_name,
        knowledge_map=knowledge_map,
    )
    state.lower(formula, target_id=target_id)
    return FormulaLoweringResult(
        knowledges=state.knowledges,
        operators=state.operators,
        strategies=[],
    )


class _FormulaState:
    def __init__(
        self,
        *,
        namespace: str,
        package_name: str,
        knowledge_map: dict[int, str],
    ):
        self.namespace = namespace
        self.package_name = package_name
        self.knowledge_map = knowledge_map
        self.knowledges: list[IrKnowledge] = []
        self.operators: list[IrOperator] = []
        self._helper_counter = 0

    def lower(self, formula: Any, *, target_id: str | None = None) -> str:
        if isinstance(formula, ClaimAtom):
            return self._claim_atom_id(formula)

        operator_name, children = _connective_operator(formula)
        if operator_name is None:
            return self._atom_claim(formula)

        child_ids = [self.lower(child) for child in children]
        conclusion = target_id or self._helper_claim(operator_name, child_ids)
        self.operators.append(
            IrOperator(
                scope="local",
                operator=operator_name,
                variables=child_ids,
                conclusion=conclusion,
                metadata={"formula_lowering": "connective"},
            )
        )
        return conclusion

    def _claim_atom_id(self, atom: ClaimAtom) -> str:
        try:
            return self.knowledge_map[id(atom.claim)]
        except KeyError as exc:
            raise ValueError(
                "ClaimAtom references a claim that is not in the compiled package"
            ) from exc

    def _atom_claim(self, formula: Any) -> str:
        label, claim_id = self._generated_claim("formula_atom", repr(formula))
        self.knowledges.append(
            IrKnowledge(
                id=claim_id,
                label=label,
                type=KnowledgeType.CLAIM,
                content=repr(formula),
                metadata={
                    "generated": True,
                    "generated_kind": "formula_atom",
                    "formula_lowering": "atom",
                    "review": False,
                },
            )
        )
        return claim_id

    def _helper_claim(self, operator_name: str, child_ids: list[str]) -> str:
        label, claim_id = self._generated_claim(
            f"{operator_name}_result",
            f"{operator_name}|{child_ids}",
        )
        self.knowledges.append(
            IrKnowledge(
                id=claim_id,
                label=label,
                type=KnowledgeType.CLAIM,
                content=f"{operator_name}({', '.join(child_ids)})",
                metadata={
                    "generated": True,
                    "generated_kind": "formula_helper",
                    "helper_kind": f"{operator_name}_result",
                    "formula_lowering": "connective_helper",
                    "review": False,
                },
            )
        )
        return claim_id

    def _generated_claim(self, role: str, payload: str) -> tuple[str, str]:
        digest = hashlib.sha256(
            f"{self.namespace}|{self.package_name}|{role}|{payload}|{self._helper_counter}".encode()
        ).hexdigest()[:8]
        self._helper_counter += 1
        label = f"__{_safe_label(role)}_{digest}"
        return label, make_qid(self.namespace, self.package_name, label)


def _connective_operator(formula: Any) -> tuple[str | None, list[Any]]:
    if isinstance(formula, Land):
        return "conjunction", list(formula.operands)
    if isinstance(formula, Lor):
        return "disjunction", list(formula.operands)
    if isinstance(formula, Lnot):
        return "negation", [formula.operand]
    if isinstance(formula, Implies):
        return "implication", [formula.antecedent, formula.consequent]
    if isinstance(formula, Iff):
        return "equivalence", [formula.left, formula.right]
    return None, []


def _forall_instance_id(
    *,
    namespace: str,
    package_name: str,
    source_claim_id: str,
    symbol: str,
    value: Any,
) -> tuple[str, str]:
    payload = f"{source_claim_id}|{symbol}|{value!r}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    label = f"__forall_{_safe_label(symbol)}_{digest}"
    return make_qid(namespace, package_name, label), label


def _safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = normalized.strip("_") or "x"
    if not re.match(r"[A-Za-z_]", normalized):
        normalized = f"_{normalized}"
    return normalized
