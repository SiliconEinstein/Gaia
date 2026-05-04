"""Lower Gaia Lang Formula AST payloads into existing Gaia IR structures.

Milestone B starts with a deliberately small lowering contract: finite-domain
universal quantification grounds to one directed rigid implication operator per
domain member; finite-domain existential quantification grounds to a disjunction
over instances; top-level atom formulas annotate the source Claim instead of
creating duplicate orphan atoms.
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

_BindingMap = dict[int, dict[str, Any]]


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
            knowledge_map=knowledge_map,
        )
    if isinstance(formula, Exists):
        return _lower_exists(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )

    operator_name, _ = _connective_operator(formula)
    if operator_name is None:
        if not _is_atomic_formula(formula):
            raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
        return _lower_formula_to_claim(
            formula,
            target_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
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
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    variable = formula.variable
    domain = variable.domain
    if not isinstance(domain, Domain):
        raise ValueError("Forall formula lowering currently requires a finite Domain")

    generated_knowledges: list[IrKnowledge] = []
    generated_operators: list[IrOperator] = []
    generated_strategies: list[IrStrategy] = []
    for value in domain.members:
        binding = _quantifier_binding(variable, domain, value, source="forall")
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
        body_result = _lower_formula_to_claim(
            formula.body,
            target_id=instance_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            bindings={id(variable): binding},
        )
        _absorb_generated_result(
            generated_knowledges,
            generated_operators,
            generated_strategies,
            body_result,
        )

        implication_result = _implication_result(
            namespace=namespace,
            package_name=package_name,
            antecedent_id=claim_id,
            consequent_id=instance_id,
            formula_lowering="forall_grounding",
            metadata={
                "source_claim": claim_id,
                "binding": binding,
            },
        )
        generated_knowledges.extend(implication_result.knowledges)
        generated_operators.extend(implication_result.operators)

    return FormulaLoweringResult(
        knowledges=generated_knowledges,
        operators=generated_operators,
        strategies=generated_strategies,
    )


def _lower_exists(
    claim: Claim,
    formula: Exists,
    *,
    claim_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    variable = formula.variable
    domain = variable.domain
    if not isinstance(domain, Domain):
        raise ValueError("Exists formula lowering currently requires a finite Domain")

    generated_knowledges: list[IrKnowledge] = []
    generated_operators: list[IrOperator] = []
    generated_strategies: list[IrStrategy] = []
    instance_ids: list[str] = []
    for value in domain.members:
        binding = _quantifier_binding(variable, domain, value, source="exists")
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
        body_result = _lower_formula_to_claim(
            formula.body,
            target_id=instance_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
            bindings={id(variable): binding},
        )
        _absorb_generated_result(
            generated_knowledges,
            generated_operators,
            generated_strategies,
            body_result,
        )

    if len(instance_ids) == 1:
        alias_result = _equivalence_result(
            namespace=namespace,
            package_name=package_name,
            left_id=claim_id,
            right_id=instance_ids[0],
            formula_lowering="exists_grounding",
            metadata={
                "source_claim": claim_id,
                "binding": _quantifier_binding(
                    variable,
                    domain,
                    domain.members[0],
                    source="exists",
                ),
            },
        )
        generated_knowledges.extend(alias_result.knowledges)
        generated_operators.extend(alias_result.operators)
        return FormulaLoweringResult(
            knowledges=generated_knowledges,
            operators=generated_operators,
            strategies=generated_strategies,
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
        operators=[*generated_operators, exists_operator],
        strategies=generated_strategies,
    )


def _lower_formula_to_claim(
    formula: Any,
    *,
    target_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> FormulaLoweringResult:
    if isinstance(formula, ClaimAtom):
        return _lower_claim_atom_alias(
            formula,
            target_id=target_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )

    operator_name, _ = _connective_operator(formula)
    if operator_name is None:
        if not _is_atomic_formula(formula):
            raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
        return FormulaLoweringResult(
            metadata_updates={
                target_id: _source_atom_metadata(
                    formula,
                    knowledge_map=knowledge_map,
                    bindings=bindings,
                )
            },
            parameter_updates={
                target_id: _binding_parameters(formula, bindings=bindings),
            },
        )

    state = _FormulaState(
        namespace=namespace,
        package_name=package_name,
        knowledge_map=knowledge_map,
        bindings=bindings,
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
        bindings: _BindingMap | None = None,
    ):
        self.namespace = namespace
        self.package_name = package_name
        self.knowledge_map = knowledge_map
        self.bindings = bindings or {}
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
                bindings=self.bindings,
            ),
            "review": False,
        }
        bindings = _formula_bindings(formula, bindings=self.bindings)
        if bindings:
            metadata["formula_bindings"] = bindings
        if isinstance(formula, Causes):
            metadata["causal"] = {
                "cause": _term_descriptor(
                    formula.cause,
                    knowledge_map=self.knowledge_map,
                    bindings=self.bindings,
                ),
                "effect": _term_descriptor(
                    formula.effect,
                    knowledge_map=self.knowledge_map,
                    bindings=self.bindings,
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
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    metadata = {
        "formula_lowering": "atom",
        "formula_atom": _formula_descriptor(
            formula,
            knowledge_map=knowledge_map,
            bindings=bindings,
        ),
    }
    formula_bindings = _formula_bindings(formula, bindings=bindings)
    if formula_bindings:
        metadata["formula_bindings"] = formula_bindings
    if isinstance(formula, Causes):
        metadata["causal"] = {
            "cause": _term_descriptor(
                formula.cause,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
            "effect": _term_descriptor(
                formula.effect,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
        }
    return metadata


def _formula_descriptor(
    formula: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    if isinstance(formula, ClaimAtom):
        return {"kind": "claim", "qid": _claim_atom_qid(formula, knowledge_map)}
    if isinstance(formula, Equals):
        return _binary_formula_descriptor(
            "equals",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, NotEquals):
        return _binary_formula_descriptor(
            "not_equals",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, Greater):
        return _binary_formula_descriptor(
            "greater",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, GreaterEqual):
        return _binary_formula_descriptor(
            "greater_equal",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, Less):
        return _binary_formula_descriptor(
            "less",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, LessEqual):
        return _binary_formula_descriptor(
            "less_equal",
            formula.left,
            formula.right,
            knowledge_map,
            bindings,
        )
    if isinstance(formula, UserPredicate):
        return {
            "kind": "predicate",
            "symbol": _predicate_symbol_descriptor(formula.symbol),
            "args": [
                _term_descriptor(arg, knowledge_map=knowledge_map, bindings=bindings)
                for arg in formula.args
            ],
        }
    if isinstance(formula, Causes):
        return {
            "kind": "causes",
            "cause": _term_descriptor(
                formula.cause,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
            "effect": _term_descriptor(
                formula.effect,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
        }
    return {"kind": type(formula).__name__, "repr": repr(formula)}


def _binary_formula_descriptor(
    kind: str,
    left: Any,
    right: Any,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "left": _term_descriptor(left, knowledge_map=knowledge_map, bindings=bindings),
        "right": _term_descriptor(right, knowledge_map=knowledge_map, bindings=bindings),
    }


def _term_descriptor(
    term: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    if isinstance(term, Variable):
        descriptor = {
            "kind": "variable",
            "symbol": term.symbol,
            "domain": _domain_name(term.domain),
        }
        binding = (bindings or {}).get(id(term))
        if binding is not None:
            descriptor["value"] = binding["value"]
            descriptor["binding_source"] = binding["source"]
        elif term.value is not None:
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
            "args": [
                _term_descriptor(arg, knowledge_map=knowledge_map, bindings=bindings)
                for arg in term.args
            ],
            "result_domain": _domain_name(term.symbol.result_domain),
        }
    if isinstance(term, ArithOp):
        return {
            "kind": "arith",
            "op": term.op,
            "left": _term_descriptor(
                term.left,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
            "right": _term_descriptor(
                term.right,
                knowledge_map=knowledge_map,
                bindings=bindings,
            ),
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


def _formula_bindings(
    formula: Any,
    *,
    bindings: _BindingMap | None = None,
) -> list[dict[str, Any]]:
    formula_bindings = [dict(binding) for binding in (bindings or {}).values()]
    pair = _equals_variable_constant_pair(formula)
    if pair is None:
        return formula_bindings
    variable, constant = pair
    equals_binding = {
        "symbol": variable.symbol,
        "domain": _domain_name(variable.domain),
        "value": constant.value,
        "source": "formula",
    }
    if not any(binding["symbol"] == variable.symbol for binding in formula_bindings):
        formula_bindings.append(equals_binding)
    return formula_bindings


def _binding_parameters(
    formula: Any,
    *,
    bindings: _BindingMap | None = None,
) -> list[IrParameter]:
    parameters = [
        IrParameter(
            name=binding["symbol"],
            type=binding["domain"],
            value=binding["value"],
        )
        for binding in (bindings or {}).values()
    ]
    pair = _equals_variable_constant_pair(formula)
    if pair is None:
        return parameters
    variable, constant = pair
    parameter = IrParameter(
        name=variable.symbol,
        type=_domain_name(variable.domain),
        value=constant.value,
    )
    if not any(existing.name == parameter.name for existing in parameters):
        parameters.append(parameter)
    return parameters


def _quantifier_binding(
    variable: Variable,
    domain: Domain,
    value: Any,
    *,
    source: str,
) -> dict[str, Any]:
    return {
        "symbol": variable.symbol,
        "domain": _domain_name(domain),
        "value": value,
        "source": source,
    }


def _absorb_generated_result(
    knowledges: list[IrKnowledge],
    operators: list[IrOperator],
    strategies: list[IrStrategy],
    result: FormulaLoweringResult,
) -> None:
    knowledges.extend(result.knowledges)
    operators.extend(result.operators)
    strategies.extend(result.strategies)
    _apply_knowledge_updates(
        knowledges,
        metadata_updates=result.metadata_updates,
        parameter_updates=result.parameter_updates,
        preserve_instance_lowering=True,
    )


def _apply_knowledge_updates(
    knowledges: list[IrKnowledge],
    *,
    metadata_updates: dict[str, dict[str, Any]],
    parameter_updates: dict[str, list[IrParameter]],
    preserve_instance_lowering: bool = False,
) -> None:
    if not metadata_updates and not parameter_updates:
        return
    index_by_id = {k.id: i for i, k in enumerate(knowledges) if k.id}
    for qid in sorted(set(metadata_updates) | set(parameter_updates)):
        if qid not in index_by_id:
            continue
        index = index_by_id[qid]
        knowledge = knowledges[index]
        metadata = dict(knowledge.metadata or {})
        update = dict(metadata_updates.get(qid, {}))
        if (
            preserve_instance_lowering
            and metadata.get("formula_lowering") in {"forall_instance", "exists_instance"}
            and update.get("formula_lowering") == "atom"
        ):
            update.pop("formula_lowering")
            update["formula_body_lowering"] = "atom"
        metadata.update(update)

        parameters = list(knowledge.parameters or [])
        for param in parameter_updates.get(qid, []):
            existing = next((p for p in parameters if p.name == param.name), None)
            if existing is None:
                parameters.append(param)
                continue
            if existing.type != param.type or existing.value != param.value:
                raise ValueError(
                    f"formula binding for parameter {param.name!r} conflicts "
                    f"with existing parameter on {qid}"
                )

        knowledges[index] = knowledge.model_copy(
            update={
                "metadata": metadata or None,
                "parameters": parameters,
                "content_hash": None,
            }
        )
    return


def _lower_claim_atom_alias(
    atom: ClaimAtom,
    *,
    target_id: str,
    namespace: str,
    package_name: str,
    knowledge_map: dict[int, str],
) -> FormulaLoweringResult:
    referenced_id = _claim_atom_qid(atom, knowledge_map)
    metadata_updates = {
        target_id: {
            "formula_lowering": "atom",
            "formula_atom": {"kind": "claim", "qid": referenced_id},
            "formula_alias": {"qid": referenced_id},
        }
    }
    if referenced_id == target_id:
        return FormulaLoweringResult(metadata_updates=metadata_updates)

    result = _equivalence_result(
        namespace=namespace,
        package_name=package_name,
        left_id=referenced_id,
        right_id=target_id,
        formula_lowering="claim_atom_alias",
        metadata={
            "source_claim": target_id,
            "referenced_claim": referenced_id,
        },
    )
    return FormulaLoweringResult(
        knowledges=result.knowledges,
        operators=result.operators,
        strategies=result.strategies,
        metadata_updates=metadata_updates,
    )


def _equivalence_result(
    *,
    namespace: str,
    package_name: str,
    left_id: str,
    right_id: str,
    formula_lowering: str,
    metadata: dict[str, Any],
) -> FormulaLoweringResult:
    helper_id, helper_label = _equivalence_helper_id(
        namespace=namespace,
        package_name=package_name,
        left_id=left_id,
        right_id=right_id,
        formula_lowering=formula_lowering,
    )
    helper_metadata = {
        "generated": True,
        "generated_kind": "formula_helper",
        "helper_kind": "equivalence_result",
        "formula_lowering": formula_lowering,
        "review": False,
        **metadata,
    }
    operator_metadata = {
        "formula_lowering": formula_lowering,
        **metadata,
    }
    return FormulaLoweringResult(
        knowledges=[
            IrKnowledge(
                id=helper_id,
                label=helper_label,
                type=KnowledgeType.CLAIM,
                content=f"equivalence({left_id}, {right_id})",
                metadata=helper_metadata,
            )
        ],
        operators=[
            IrOperator(
                scope="local",
                operator="equivalence",
                variables=[left_id, right_id],
                conclusion=helper_id,
                metadata=operator_metadata,
            )
        ],
    )


def _implication_result(
    *,
    namespace: str,
    package_name: str,
    antecedent_id: str,
    consequent_id: str,
    formula_lowering: str,
    metadata: dict[str, Any],
) -> FormulaLoweringResult:
    helper_id, helper_label = _implication_helper_id(
        namespace=namespace,
        package_name=package_name,
        antecedent_id=antecedent_id,
        consequent_id=consequent_id,
        formula_lowering=formula_lowering,
    )
    helper_metadata = {
        "generated": True,
        "generated_kind": "formula_helper",
        "helper_kind": "implication_result",
        "formula_lowering": formula_lowering,
        "review": False,
        **metadata,
    }
    operator_metadata = {
        "formula_lowering": formula_lowering,
        **metadata,
    }
    return FormulaLoweringResult(
        knowledges=[
            IrKnowledge(
                id=helper_id,
                label=helper_label,
                type=KnowledgeType.CLAIM,
                content=f"implication({antecedent_id}, {consequent_id})",
                metadata=helper_metadata,
            )
        ],
        operators=[
            IrOperator(
                scope="local",
                operator="implication",
                variables=[antecedent_id, consequent_id],
                conclusion=helper_id,
                metadata=operator_metadata,
            )
        ],
    )


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


def _equivalence_helper_id(
    *,
    namespace: str,
    package_name: str,
    left_id: str,
    right_id: str,
    formula_lowering: str,
) -> tuple[str, str]:
    payload = "|".join(sorted([left_id, right_id, formula_lowering]))
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    label = f"__formula_equivalence_{digest}"
    return make_qid(namespace, package_name, label), label


def _implication_helper_id(
    *,
    namespace: str,
    package_name: str,
    antecedent_id: str,
    consequent_id: str,
    formula_lowering: str,
) -> tuple[str, str]:
    payload = "|".join([antecedent_id, consequent_id, formula_lowering])
    digest = hashlib.sha256(payload.encode()).hexdigest()[:8]
    label = f"__formula_implication_{digest}"
    return make_qid(namespace, package_name, label), label


def _safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = normalized.strip("_") or "x"
    if not re.match(r"[A-Za-z_]", normalized):
        normalized = f"_{normalized}"
    return normalized
