"""Lower Gaia Lang Formula AST payloads into existing Gaia IR structures.

Milestone B starts with a deliberately small lowering contract: finite-domain
universal quantification grounds to one directed deduction/implication per
domain member; finite-domain existential quantification grounds to a
disjunction over instances; top-level atom formulas annotate the source Claim
instead of creating duplicate orphan atoms.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import Any

from gaia.ir import Knowledge as IrKnowledge
from gaia.ir import Operator as IrOperator
from gaia.ir import Parameter as IrParameter
from gaia.ir import Strategy as IrStrategy
from gaia.ir.formalize import formalize_named_strategy
from gaia.ir.knowledge import KnowledgeType, make_qid
from gaia.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.lang.formula.predicate import (
    Causes,
    ClaimAtom,
    Equals,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
)
from gaia.lang.formula.quantifier import Exists, Forall
from gaia.lang.formula.symbols import PredicateSymbol
from gaia.lang.formula.term import ArithOp, Constant, FunctionApp
from gaia.lang.runtime.domain import Domain
from gaia.lang.runtime.knowledge import Claim
from gaia.lang.runtime.variable import Variable
from gaia.lang.types.primitives import PrimitiveType


@dataclass(frozen=True)
class FormulaLoweringResult:
    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    parameter_updates: dict[str, list[IrParameter]] = field(default_factory=dict)


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
        return FormulaLoweringResult()
    if isinstance(formula, Forall):
        return _lower_forall(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
        )
    if isinstance(formula, Exists):
        return _lower_exists(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
        )

    operator_name, _ = _connective_operator(formula)
    if operator_name is None:
        if not _is_atomic_formula(formula):
            raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
        return FormulaLoweringResult(
            metadata_updates={
                claim_id: _source_atom_metadata(formula, knowledge_map=knowledge_map)
            },
            parameter_updates={
                claim_id: _binding_parameters(formula),
            },
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
            "domain": _domain_name(domain),
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
                parameters=[
                    IrParameter(
                        name=variable.symbol,
                        type=_domain_name(domain),
                        value=value,
                    )
                ],
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


def _lower_exists(
    claim: Claim,
    formula: Exists,
    *,
    claim_id: str,
    namespace: str,
    package_name: str,
) -> FormulaLoweringResult:
    variable = formula.variable
    domain = variable.domain
    if not isinstance(domain, Domain):
        raise ValueError("Exists formula lowering currently requires a finite Domain")
    if len(domain.members) < 2:
        raise ValueError("Exists formula lowering currently requires at least two Domain members")

    generated_knowledges: list[IrKnowledge] = []
    instance_ids: list[str] = []
    for value in domain.members:
        binding = {
            "symbol": variable.symbol,
            "domain": _domain_name(domain),
            "value": value,
        }
        instance_id, instance_label = _exists_instance_id(
            namespace=namespace,
            package_name=package_name,
            source_claim_id=claim_id,
            symbol=variable.symbol,
            value=value,
        )
        instance_ids.append(instance_id)
        generated_knowledges.append(
            IrKnowledge(
                id=instance_id,
                label=instance_label,
                type=KnowledgeType.CLAIM,
                content=f"{claim.content} [{variable.symbol}={value!r}]",
                parameters=[
                    IrParameter(
                        name=variable.symbol,
                        type=_domain_name(domain),
                        value=value,
                    )
                ],
                metadata={
                    "generated": True,
                    "generated_kind": "formula_instance",
                    "formula_lowering": "exists_instance",
                    "source_claim": claim_id,
                    "binding": binding,
                    "visibility": "formula_grounding",
                    "review": False,
                },
            )
        )

    exists_operator = IrOperator(
        scope="local",
        operator="disjunction",
        variables=instance_ids,
        conclusion=claim_id,
        metadata={
            "formula_lowering": "exists_grounding",
            "source_claim": claim_id,
        },
    )
    return FormulaLoweringResult(
        knowledges=generated_knowledges,
        operators=[exists_operator],
        strategies=[],
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
            if not _is_atomic_formula(formula):
                raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
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
        metadata = {
            "generated": True,
            "generated_kind": "formula_atom",
            "formula_lowering": "atom",
            "formula_atom": _formula_descriptor(
                formula,
                knowledge_map=self.knowledge_map,
            ),
            "review": False,
        }
        bindings = _formula_bindings(formula)
        if bindings:
            metadata["formula_bindings"] = bindings
        if isinstance(formula, Causes):
            metadata["causal"] = {
                "cause": _term_descriptor(
                    formula.cause,
                    knowledge_map=self.knowledge_map,
                ),
                "effect": _term_descriptor(
                    formula.effect,
                    knowledge_map=self.knowledge_map,
                ),
            }
        self.knowledges.append(
            IrKnowledge(
                id=claim_id,
                label=label,
                type=KnowledgeType.CLAIM,
                content=repr(formula),
                metadata=metadata,
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


def _is_atomic_formula(formula: Any) -> bool:
    return isinstance(
        formula,
        (
            Causes,
            ClaimAtom,
            Equals,
            Greater,
            GreaterEqual,
            Less,
            LessEqual,
            NotEquals,
            UserPredicate,
        ),
    )


def _source_atom_metadata(
    formula: Any,
    *,
    knowledge_map: dict[int, str],
) -> dict[str, Any]:
    metadata = {
        "formula_lowering": "atom",
        "formula_atom": _formula_descriptor(formula, knowledge_map=knowledge_map),
    }
    bindings = _formula_bindings(formula)
    if bindings:
        metadata["formula_bindings"] = bindings
    if isinstance(formula, Causes):
        metadata["causal"] = {
            "cause": _term_descriptor(formula.cause, knowledge_map=knowledge_map),
            "effect": _term_descriptor(formula.effect, knowledge_map=knowledge_map),
        }
    return metadata


def _formula_descriptor(formula: Any, *, knowledge_map: dict[int, str]) -> dict[str, Any]:
    if isinstance(formula, ClaimAtom):
        return {"kind": "claim", "qid": _claim_atom_qid(formula, knowledge_map)}
    if isinstance(formula, Equals):
        return _binary_formula_descriptor("equals", formula.left, formula.right, knowledge_map)
    if isinstance(formula, NotEquals):
        return _binary_formula_descriptor("not_equals", formula.left, formula.right, knowledge_map)
    if isinstance(formula, Greater):
        return _binary_formula_descriptor("greater", formula.left, formula.right, knowledge_map)
    if isinstance(formula, GreaterEqual):
        return _binary_formula_descriptor(
            "greater_equal", formula.left, formula.right, knowledge_map
        )
    if isinstance(formula, Less):
        return _binary_formula_descriptor("less", formula.left, formula.right, knowledge_map)
    if isinstance(formula, LessEqual):
        return _binary_formula_descriptor("less_equal", formula.left, formula.right, knowledge_map)
    if isinstance(formula, UserPredicate):
        return {
            "kind": "predicate",
            "symbol": _predicate_symbol_descriptor(formula.symbol),
            "args": [_term_descriptor(arg, knowledge_map=knowledge_map) for arg in formula.args],
        }
    if isinstance(formula, Causes):
        return {
            "kind": "causes",
            "cause": _term_descriptor(formula.cause, knowledge_map=knowledge_map),
            "effect": _term_descriptor(formula.effect, knowledge_map=knowledge_map),
        }
    return {"kind": type(formula).__name__, "repr": repr(formula)}


def _binary_formula_descriptor(
    kind: str,
    left: Any,
    right: Any,
    knowledge_map: dict[int, str],
) -> dict[str, Any]:
    return {
        "kind": kind,
        "left": _term_descriptor(left, knowledge_map=knowledge_map),
        "right": _term_descriptor(right, knowledge_map=knowledge_map),
    }


def _term_descriptor(term: Any, *, knowledge_map: dict[int, str]) -> dict[str, Any]:
    if isinstance(term, Variable):
        descriptor = {
            "kind": "variable",
            "symbol": term.symbol,
            "domain": _domain_name(term.domain),
        }
        if term.value is not None:
            descriptor["value"] = term.value
        return descriptor
    if isinstance(term, Constant):
        return {
            "kind": "constant",
            "value": term.value,
            "primitive": term.primitive.name,
        }
    if isinstance(term, FunctionApp):
        return {
            "kind": "function",
            "symbol": term.symbol.name,
            "args": [_term_descriptor(arg, knowledge_map=knowledge_map) for arg in term.args],
            "result_domain": _domain_name(term.symbol.result_domain),
        }
    if isinstance(term, ArithOp):
        return {
            "kind": "arith",
            "op": term.op,
            "left": _term_descriptor(term.left, knowledge_map=knowledge_map),
            "right": _term_descriptor(term.right, knowledge_map=knowledge_map),
        }
    if isinstance(term, ClaimAtom):
        return {"kind": "knowledge", "qid": _claim_atom_qid(term, knowledge_map)}
    return {"kind": type(term).__name__, "repr": repr(term)}


def _predicate_symbol_descriptor(symbol: PredicateSymbol) -> dict[str, Any]:
    return {
        "name": symbol.name,
        "arg_domains": [_domain_name(domain) for domain in symbol.arg_domains],
    }


def _claim_atom_qid(atom: ClaimAtom, knowledge_map: dict[int, str]) -> str:
    try:
        return knowledge_map[id(atom.claim)]
    except KeyError as exc:
        raise ValueError(
            "ClaimAtom references a claim that is not in the compiled package"
        ) from exc


def _formula_bindings(formula: Any) -> list[dict[str, Any]]:
    pair = _equals_variable_constant_pair(formula)
    if pair is None:
        return []
    variable, constant = pair
    return [
        {
            "symbol": variable.symbol,
            "domain": _domain_name(variable.domain),
            "value": constant.value,
            "source": "formula",
        }
    ]


def _binding_parameters(formula: Any) -> list[IrParameter]:
    pair = _equals_variable_constant_pair(formula)
    if pair is None:
        return []
    variable, constant = pair
    return [
        IrParameter(
            name=variable.symbol,
            type=_domain_name(variable.domain),
            value=constant.value,
        )
    ]


def _equals_variable_constant_pair(formula: Any) -> tuple[Variable, Constant] | None:
    if not isinstance(formula, Equals):
        return None
    if isinstance(formula.left, Variable) and isinstance(formula.right, Constant):
        return formula.left, formula.right
    if isinstance(formula.right, Variable) and isinstance(formula.left, Constant):
        return formula.right, formula.left
    return None


def _domain_name(domain: PrimitiveType | Domain) -> str:
    if isinstance(domain, PrimitiveType):
        return domain.name
    return domain.label or domain.title or domain.content or "Domain"


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


def _exists_instance_id(
    *,
    namespace: str,
    package_name: str,
    source_claim_id: str,
    symbol: str,
    value: Any,
) -> tuple[str, str]:
    payload = f"{source_claim_id}|{symbol}|{value!r}"
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    label = f"__exists_{_safe_label(symbol)}_{digest}"
    return make_qid(namespace, package_name, label), label


def _safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = normalized.strip("_") or "x"
    if not re.match(r"[A-Za-z_]", normalized):
        normalized = f"_{normalized}"
    return normalized
