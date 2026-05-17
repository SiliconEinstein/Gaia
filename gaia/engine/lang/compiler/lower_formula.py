"""Lower Gaia Lang Formula AST payloads into existing Gaia IR structures.

Milestone B starts with a deliberately small lowering contract: finite-domain
universal quantification grounds to one directed deduction/implication per
domain member; finite-domain existential quantification grounds to a
disjunction over instances; top-level atom formulas annotate the source Claim
instead of creating duplicate orphan atoms.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

from gaia.engine.ir import Knowledge as IrKnowledge
from gaia.engine.ir import Operator as IrOperator
from gaia.engine.ir import Parameter as IrParameter
from gaia.engine.ir import Strategy as IrStrategy
from gaia.engine.ir.formalize import formalize_named_strategy
from gaia.engine.ir.formula import (
    FormulaEdge,
    FormulaGraph,
    FormulaNode,
    FormulaNodeKind,
    formula_node_id,
)
from gaia.engine.ir.knowledge import KnowledgeType, make_qid
from gaia.engine.ir.operator import OperatorType
from gaia.engine.lang.formula.connective import Iff, Implies, Land, Lnot, Lor
from gaia.engine.lang.formula.predicate import (
    ClaimAtom,
    Equals,
    Greater,
    GreaterEqual,
    Less,
    LessEqual,
    NotEquals,
    UserPredicate,
)
from gaia.engine.lang.formula.primitives import PrimitiveType
from gaia.engine.lang.formula.quantifier import Exists, Forall
from gaia.engine.lang.formula.symbols import PredicateSymbol
from gaia.engine.lang.formula.term import ArithOp, Constant, FunctionApp
from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.runtime.knowledge import Claim
from gaia.engine.lang.runtime.variable import Variable

_BindingMap = dict[int, dict[str, Any]]


@dataclass(frozen=True)
class FormulaLoweringResult:
    """IR records and source-claim updates emitted by formula lowering."""

    knowledges: list[IrKnowledge] = field(default_factory=list)
    operators: list[IrOperator] = field(default_factory=list)
    strategies: list[IrStrategy] = field(default_factory=list)
    metadata_updates: dict[str, dict[str, Any]] = field(default_factory=dict)
    parameter_updates: dict[str, list[IrParameter]] = field(default_factory=dict)
    formula_graphs: list[FormulaGraph] = field(default_factory=list)


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
    formula_graph = build_formula_graph(
        formula,
        source_claim_id=claim_id,
        knowledge_map=knowledge_map,
    )
    if isinstance(formula, Forall):
        result = _lower_forall(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )
        result.formula_graphs.append(formula_graph)
        return result
    if isinstance(formula, Exists):
        result = _lower_exists(
            claim,
            formula,
            claim_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )
        result.formula_graphs.append(formula_graph)
        return result

    operator_name, _ = _connective_operator(formula)
    if operator_name is None:
        if not _is_atomic_formula(formula):
            raise NotImplementedError(f"Unsupported formula lowering: {type(formula).__name__}")
        result = _lower_formula_to_claim(
            formula,
            target_id=claim_id,
            namespace=namespace,
            package_name=package_name,
            knowledge_map=knowledge_map,
        )
        result.formula_graphs.append(formula_graph)
        return result

    result = _lower_formula_to_claim(
        formula,
        target_id=claim_id,
        namespace=namespace,
        package_name=package_name,
        knowledge_map=knowledge_map,
    )
    result.formula_graphs.append(formula_graph)
    return result


def canonical_formula_descriptor(
    formula: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    """Return the canonical descriptor used for formula atom nodes."""
    return _formula_descriptor(formula, knowledge_map=knowledge_map, bindings=bindings)


def canonical_term_descriptor(
    term: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    """Return the canonical descriptor used for formula term nodes."""
    return _term_descriptor(term, knowledge_map=knowledge_map, bindings=bindings)


def build_formula_graph(
    formula: Any,
    *,
    source_claim_id: str,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> FormulaGraph:
    """Build the content-addressed formula graph for one source claim."""
    builder = _FormulaGraphBuilder(knowledge_map=knowledge_map, bindings=bindings)
    root = builder.formula_node(formula)
    return FormulaGraph(
        source_claim=source_claim_id,
        root=root,
        nodes=list(builder.nodes.values()),
        edges=builder.edges,
    )


class _FormulaGraphBuilder:
    def __init__(
        self,
        *,
        knowledge_map: dict[int, str],
        bindings: _BindingMap | None = None,
    ) -> None:
        self.knowledge_map = knowledge_map
        self.bindings = bindings
        self.nodes: dict[str, FormulaNode] = {}
        self.edges: list[FormulaEdge] = []
        self._edge_keys: set[tuple[str, str, str, int | None]] = set()
        self._binder_counter = 0
        self._variable_binders: dict[int, list[str]] = {}

    def formula_node(self, formula: Any) -> str:
        if _is_atomic_formula(formula):
            return self._atomic_formula_node(formula)

        operator_name, children = _connective_operator(formula)
        if operator_name is not None:
            child_ids = [self.formula_node(child) for child in children]
            descriptor = {
                "kind": "op",
                "operator": str(operator_name),
                "children": child_ids,
            }
            node_id = self._add_node("op", descriptor)
            self._add_connective_edges(node_id, operator_name, child_ids)
            return node_id

        if isinstance(formula, (Forall, Exists)):
            binder_id = self._push_binder(formula.variable)
            try:
                variable_id = self.term_node(formula.variable)
                body_id = self.formula_node(formula.body)
            finally:
                self._pop_binder(formula.variable)
            quantifier = "forall" if isinstance(formula, Forall) else "exists"
            descriptor = {
                "kind": "quantifier",
                "quantifier": quantifier,
                "variable": formula.variable.symbol,
                "variable_id": variable_id,
                "binder": binder_id,
                "domain": _domain_name(formula.variable.domain),
                "body": body_id,
            }
            node_id = self._add_node("quantifier", descriptor)
            self._add_edge(FormulaEdge(source=node_id, target=variable_id, role="bound_variable"))
            self._add_edge(FormulaEdge(source=node_id, target=body_id, role="body"))
            return node_id

        raise NotImplementedError(f"Unsupported formula graph: {type(formula).__name__}")

    def term_node(self, term: Any) -> str:
        descriptor = self._term_descriptor(term)
        if isinstance(term, Variable):
            return self._add_node("variable", descriptor)
        if isinstance(term, Constant):
            return self._add_node("constant", descriptor)
        if isinstance(term, FunctionApp):
            node_id = self._add_node("term", descriptor)
            for index, arg in enumerate(term.args):
                self._add_edge(
                    FormulaEdge(
                        source=node_id,
                        target=self.term_node(arg),
                        role="arg",
                        index=index,
                    )
                )
            return node_id
        if isinstance(term, ArithOp):
            node_id = self._add_node("term", descriptor)
            self._add_edge(
                FormulaEdge(source=node_id, target=self.term_node(term.left), role="left")
            )
            self._add_edge(
                FormulaEdge(source=node_id, target=self.term_node(term.right), role="right")
            )
            return node_id
        if isinstance(term, ClaimAtom):
            return self._add_node("atom", descriptor)
        return self._add_node("term", descriptor)

    def _atomic_formula_node(self, formula: Any) -> str:
        descriptor = self._formula_descriptor(formula)
        node_id = self._add_node("atom", descriptor)
        if isinstance(formula, UserPredicate):
            for index, arg in enumerate(formula.args):
                self._add_edge(
                    FormulaEdge(
                        source=node_id,
                        target=self.term_node(arg),
                        role="arg",
                        index=index,
                    )
                )
        binary_terms = _binary_formula_terms(formula)
        if binary_terms is not None:
            left, right = binary_terms
            self._add_edge(FormulaEdge(source=node_id, target=self.term_node(left), role="left"))
            self._add_edge(FormulaEdge(source=node_id, target=self.term_node(right), role="right"))
        return node_id

    def _add_connective_edges(
        self,
        node_id: str,
        operator_name: OperatorType,
        child_ids: list[str],
    ) -> None:
        if operator_name == OperatorType.IMPLICATION:
            self._add_edge(FormulaEdge(source=node_id, target=child_ids[0], role="antecedent"))
            self._add_edge(FormulaEdge(source=node_id, target=child_ids[1], role="consequent"))
            return
        if operator_name == OperatorType.EQUIVALENCE:
            self._add_edge(FormulaEdge(source=node_id, target=child_ids[0], role="left"))
            self._add_edge(FormulaEdge(source=node_id, target=child_ids[1], role="right"))
            return
        for index, child_id in enumerate(child_ids):
            self._add_edge(
                FormulaEdge(source=node_id, target=child_id, role="operand", index=index)
            )

    def _add_node(self, kind: FormulaNodeKind, descriptor: dict[str, Any]) -> str:
        node_id = formula_node_id(descriptor)
        self.nodes.setdefault(node_id, FormulaNode(id=node_id, kind=kind, descriptor=descriptor))
        return node_id

    def _add_edge(self, edge: FormulaEdge) -> None:
        key = (edge.source, edge.target, edge.role, edge.index)
        if key in self._edge_keys:
            return
        self._edge_keys.add(key)
        self.edges.append(edge)

    def _push_binder(self, variable: Variable) -> str:
        binder_id = f"b{self._binder_counter}"
        self._binder_counter += 1
        self._variable_binders.setdefault(id(variable), []).append(binder_id)
        return binder_id

    def _pop_binder(self, variable: Variable) -> None:
        binders = self._variable_binders[id(variable)]
        binders.pop()
        if not binders:
            del self._variable_binders[id(variable)]

    def _active_binder(self, variable: Variable) -> str | None:
        binders = self._variable_binders.get(id(variable))
        if not binders:
            return None
        return binders[-1]

    def _formula_descriptor(self, formula: Any) -> dict[str, Any]:
        if isinstance(formula, UserPredicate):
            descriptor = canonical_formula_descriptor(
                formula,
                knowledge_map=self.knowledge_map,
                bindings=self.bindings,
            )
            descriptor["args"] = [self._term_descriptor(arg) for arg in formula.args]
            return descriptor
        binary_terms = _binary_formula_terms(formula)
        if binary_terms is not None:
            left, right = binary_terms
            descriptor = canonical_formula_descriptor(
                formula,
                knowledge_map=self.knowledge_map,
                bindings=self.bindings,
            )
            descriptor["left"] = self._term_descriptor(left)
            descriptor["right"] = self._term_descriptor(right)
            return descriptor
        return canonical_formula_descriptor(
            formula,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )

    def _term_descriptor(self, term: Any) -> dict[str, Any]:
        descriptor = canonical_term_descriptor(
            term,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )
        if isinstance(term, Variable):
            binder_id = self._active_binder(term)
            if binder_id is not None:
                descriptor["binder"] = binder_id
            return descriptor
        if isinstance(term, FunctionApp):
            descriptor["args"] = [self._term_descriptor(arg) for arg in term.args]
            return descriptor
        if isinstance(term, ArithOp):
            descriptor["left"] = self._term_descriptor(term.left)
            descriptor["right"] = self._term_descriptor(term.right)
            return descriptor
        return descriptor


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
        operator=OperatorType.DISJUNCTION,
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

    if _is_binding_conjunction(formula):
        formula_bindings = _formula_bindings(formula, bindings=bindings)
        return FormulaLoweringResult(
            metadata_updates={
                target_id: {
                    "formula_lowering": "binding_conjunction",
                    "formula_bindings": formula_bindings,
                }
            },
            parameter_updates={
                target_id: _binding_parameters(formula, bindings=bindings),
            },
        )

    state = _FormulaState(
        namespace=namespace,
        package_name=package_name,
        source_claim_id=target_id,
        knowledge_map=knowledge_map,
        bindings=bindings,
    )
    state.lower(formula, target_id=target_id)
    formula_bindings = _formula_bindings(formula, bindings=bindings)
    binding_parameters = _binding_parameters(formula, bindings=bindings)
    metadata_updates: dict[str, dict[str, Any]] = {}
    parameter_updates: dict[str, list[IrParameter]] = {}
    if formula_bindings:
        metadata_updates[target_id] = {"formula_bindings": formula_bindings}
    if binding_parameters:
        parameter_updates[target_id] = binding_parameters
    return FormulaLoweringResult(
        knowledges=state.knowledges,
        operators=state.operators,
        strategies=[],
        metadata_updates=metadata_updates,
        parameter_updates=parameter_updates,
    )


class _FormulaState:
    def __init__(
        self,
        *,
        namespace: str,
        package_name: str,
        source_claim_id: str,
        knowledge_map: dict[int, str],
        bindings: _BindingMap | None = None,
    ):
        self.namespace = namespace
        self.package_name = package_name
        self.source_claim_id = source_claim_id
        self.knowledge_map = knowledge_map
        self.bindings = bindings or {}
        self.knowledges: list[IrKnowledge] = []
        self.operators: list[IrOperator] = []
        self.generated_claims_by_key: dict[tuple[str, str], str] = {}

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
        descriptor = canonical_formula_descriptor(
            formula,
            knowledge_map=self.knowledge_map,
            bindings=self.bindings,
        )
        node_id = formula_node_id(descriptor)
        label, claim_id, created = self._generated_claim("formula_atom", node_id)
        if not created:
            return claim_id

        metadata = {
            "generated": True,
            "generated_kind": "formula_atom",
            "formula_lowering": "atom",
            "formula_atom": descriptor,
            "formula_node_id": node_id,
            "source_claim": self.source_claim_id,
            "review": False,
        }
        bindings = _formula_bindings(formula, bindings=self.bindings)
        if bindings:
            metadata["formula_bindings"] = bindings
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
        operator_label = str(operator_name)
        semantic_key = json.dumps(
            {"operator": operator_label, "children": child_ids},
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        label, claim_id, created = self._generated_claim(
            f"{operator_label}_result",
            semantic_key,
        )
        if not created:
            return claim_id

        self.knowledges.append(
            IrKnowledge(
                id=claim_id,
                label=label,
                type=KnowledgeType.CLAIM,
                content=f"{operator_label}({', '.join(child_ids)})",
                metadata={
                    "generated": True,
                    "generated_kind": "formula_helper",
                    "helper_kind": f"{operator_label}_result",
                    "formula_lowering": "connective_helper",
                    "source_claim": self.source_claim_id,
                    "review": False,
                },
            )
        )
        return claim_id

    def _generated_claim(self, role: str, semantic_key: str) -> tuple[str, str, bool]:
        cache_key = (role, semantic_key)
        if cache_key in self.generated_claims_by_key:
            claim_id = self.generated_claims_by_key[cache_key]
            return claim_id.rsplit("::", 1)[-1], claim_id, False

        digest = hashlib.sha256(
            "|".join(
                [
                    self.namespace,
                    self.package_name,
                    self.source_claim_id,
                    role,
                    semantic_key,
                ]
            ).encode()
        ).hexdigest()[:8]
        label = f"__{_safe_label(role)}_{digest}"
        claim_id = make_qid(self.namespace, self.package_name, label)
        self.generated_claims_by_key[cache_key] = claim_id
        return label, claim_id, True


def _connective_operator(formula: Any) -> tuple[OperatorType | None, list[Any]]:
    if isinstance(formula, Land):
        return OperatorType.CONJUNCTION, list(formula.operands)
    if isinstance(formula, Lor):
        return OperatorType.DISJUNCTION, list(formula.operands)
    if isinstance(formula, Lnot):
        return OperatorType.NEGATION, [formula.operand]
    if isinstance(formula, Implies):
        return OperatorType.IMPLICATION, [formula.antecedent, formula.consequent]
    if isinstance(formula, Iff):
        return OperatorType.EQUIVALENCE, [formula.left, formula.right]
    return None, []


def _is_atomic_formula(formula: Any) -> bool:
    return isinstance(
        formula,
        (
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


def _binary_formula_terms(formula: Any) -> tuple[Any, Any] | None:
    if isinstance(formula, (Equals, NotEquals, Greater, GreaterEqual, Less, LessEqual)):
        return formula.left, formula.right
    return None


def _source_atom_metadata(
    formula: Any,
    *,
    knowledge_map: dict[int, str],
    bindings: _BindingMap | None = None,
) -> dict[str, Any]:
    metadata: dict[str, Any] = {
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
    for variable, constant in _equals_variable_constant_pairs(formula):
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
    for variable, constant in _equals_variable_constant_pairs(formula):
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
                operator=OperatorType.EQUIVALENCE,
                variables=[left_id, right_id],
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


def _equals_variable_constant_pairs(formula: Any) -> list[tuple[Variable, Constant]]:
    pair = _equals_variable_constant_pair(formula)
    if pair is not None:
        return [pair]
    if isinstance(formula, Land):
        pairs: list[tuple[Variable, Constant]] = []
        for operand in formula.operands:
            pairs.extend(_equals_variable_constant_pairs(operand))
        return pairs
    return []


def _is_binding_conjunction(formula: Any) -> bool:
    return (
        isinstance(formula, Land)
        and bool(formula.operands)
        and all(_equals_variable_constant_pair(operand) is not None for operand in formula.operands)
    )


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


def _safe_label(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9_]+", "_", value.strip())
    normalized = normalized.strip("_") or "x"
    if not re.match(r"[A-Za-z_]", normalized):
        normalized = f"_{normalized}"
    return normalized
