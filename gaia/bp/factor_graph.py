"""Factor graph representation for BP — aligned with theory and Gaia IR.

Theory: docs/foundations/theory/06-factor-graphs.md (operator to potential mapping)
IR: docs/foundations/gaia-ir/02-gaia-ir.md (Operator variables + conclusion)
"""

from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum, auto
from math import isfinite

logger = logging.getLogger(__name__)

CROMWELL_EPS: float = 1e-3
_DETERMINISTIC_FACTOR_TYPES = frozenset(
    {
        "IMPLICATION",
        "NEGATION",
        "CONJUNCTION",
        "DISJUNCTION",
        "EQUIVALENCE",
        "CONTRADICTION",
        "COMPLEMENT",
    }
)


def _cromwell_clamp(value: float, label: str = "") -> float:
    clamped = max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))
    if clamped != value and label:
        logger.debug("Cromwell clamp: %s %.6g -> %.6g", label, value, clamped)
    return clamped


class FactorType(Enum):
    """Supported binary-factor potential families for Gaia BP lowering."""

    IMPLICATION = auto()
    NEGATION = auto()
    CONJUNCTION = auto()
    DISJUNCTION = auto()
    EQUIVALENCE = auto()
    CONTRADICTION = auto()
    COMPLEMENT = auto()
    SOFT_ENTAILMENT = auto()
    CONDITIONAL = auto()
    PAIRWISE_POTENTIAL = auto()


@dataclass(frozen=True)
class Factor:
    """Factor node connecting premise variables to a conclusion variable.

    Attributes:
        factor_id: Stable identifier for diagnostics and merged graphs.
        factor_type: Potential family used to evaluate assignments.
        variables: Premise variable IDs in factor-specific order.
        conclusion: Conclusion or paired variable ID.
        p1: Optional positive-case probability for soft entailment factors.
        p2: Optional negative-case probability for soft entailment factors.
        cpt: Optional conditional probability table or pairwise weights.
    """

    factor_id: str
    factor_type: FactorType
    variables: list[str]
    conclusion: str
    p1: float | None = None
    p2: float | None = None
    cpt: tuple[float, ...] | None = None

    @property
    def all_vars(self) -> list[str]:
        """Return premise variables plus conclusion with duplicates removed."""
        seen: set[str] = set()
        out: list[str] = []
        for v in (*self.variables, self.conclusion):
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out


class FactorGraph:
    """Mutable binary factor graph consumed by BP, JT, GBP, and exact inference."""

    def __init__(self) -> None:
        """Initialize an empty factor graph with no variables or factors."""
        self.variables: dict[str, float] = {}
        self.unary_factors: dict[str, float] = {}
        self.factors: list[Factor] = []

    def add_variable(self, var_id: str, prior: float | None = None) -> None:
        """Register a binary variable, optionally with an explicit unary factor.

        ``variables`` records the neutral display/initial measure for every
        variable. Only ``unary_factors`` is a Jaynes-style external information
        term multiplied into the joint distribution.
        """
        if prior is None:
            self.variables.setdefault(var_id, 0.5)
            return
        clamped = _cromwell_clamp(prior, label=f"variable '{var_id}' unary")
        self.variables[var_id] = clamped
        self.unary_factors[var_id] = clamped

    def observe(self, var_id: str, value: int) -> None:
        """Hard evidence: clamp variable to observed value (07-bp §1.7).

        Implemented by setting a unary evidence factor to near-0 or near-1
        (Cromwell-bounded).
        This is equivalent to adding a unary delta factor.
        """
        if var_id not in self.variables:
            raise KeyError(f"Variable '{var_id}' not registered.")
        if value not in (0, 1):
            raise ValueError(f"observe() value must be 0 or 1, got {value}.")
        self.add_variable(var_id, 1.0 - CROMWELL_EPS if value == 1 else CROMWELL_EPS)

    def add_likelihood(
        self,
        var_id: str,
        likelihood_ratio: float,
    ) -> None:
        """Soft evidence: multiply variable's unary factor by likelihood ratio (07-bp §1.7).

        P_new(x=1) = normalize(π * lr, (1-π) * 1) where lr = P(E|x=1)/P(E|x=0).
        """
        if var_id not in self.variables:
            raise KeyError(f"Variable '{var_id}' not registered.")
        if likelihood_ratio <= 0:
            raise ValueError(f"likelihood_ratio must be > 0, got {likelihood_ratio}.")
        pi = self.unary_factors.get(var_id, self.variables.get(var_id, 0.5))
        odds = pi / (1.0 - pi) * likelihood_ratio
        new_pi = odds / (1.0 + odds)
        self.add_variable(var_id, new_pi)

    def add_factor(
        self,
        factor_id: str,
        factor_type: FactorType,
        variables: Sequence[str],
        conclusion: str,
        *,
        p1: float | None = None,
        p2: float | None = None,
        cpt: Sequence[float] | None = None,
    ) -> None:
        """Add a validated factor to the graph.

        Args:
            factor_id: Stable factor identifier.
            factor_type: Potential family to add.
            variables: Premise variable IDs in factor-specific order.
            conclusion: Conclusion or paired variable ID.
            p1: Optional soft-entailment ``P(conclusion=1 | premise=1)``.
            p2: Optional soft-entailment ``P(conclusion=0 | premise=0)``.
            cpt: Optional conditional table or pairwise potential weights.

        Raises:
            ValueError: If the factor shape or parameters violate the
                contract for ``factor_type``.
        """
        v_list = list(variables)
        if conclusion in v_list:
            raise ValueError(
                f"Factor '{factor_id}': conclusion '{conclusion}' must not appear in variables."
            )

        fp1, fp2, fcpt = self._validate_factor_parameters(
            factor_id=factor_id,
            factor_type=factor_type,
            v_list=v_list,
            p1=p1,
            p2=p2,
            cpt=cpt,
        )

        self.factors.append(
            Factor(
                factor_id=factor_id,
                factor_type=factor_type,
                variables=v_list,
                conclusion=conclusion,
                p1=fp1,
                p2=fp2,
                cpt=fcpt,
            )
        )

    @staticmethod
    def _validate_factor_parameters(
        *,
        factor_id: str,
        factor_type: FactorType,
        v_list: list[str],
        p1: float | None,
        p2: float | None,
        cpt: Sequence[float] | None,
    ) -> tuple[float | None, float | None, tuple[float, ...] | None]:
        """Validate factor-family parameters and return normalized payloads."""
        if factor_type.name in _DETERMINISTIC_FACTOR_TYPES:
            return FactorGraph._validate_deterministic_parameters(
                factor_id, factor_type, v_list, p1, p2, cpt
            )
        if factor_type == FactorType.SOFT_ENTAILMENT:
            return FactorGraph._validate_soft_entailment_parameters(factor_id, v_list, p1, p2, cpt)
        if factor_type == FactorType.CONDITIONAL:
            return FactorGraph._validate_conditional_parameters(factor_id, v_list, p1, p2, cpt)
        if factor_type == FactorType.PAIRWISE_POTENTIAL:
            return FactorGraph._validate_pairwise_parameters(factor_id, v_list, p1, p2, cpt)
        raise ValueError(f"Unknown FactorType: {factor_type!r}")

    @staticmethod
    def _validate_deterministic_parameters(
        factor_id: str,
        factor_type: FactorType,
        v_list: list[str],
        p1: float | None,
        p2: float | None,
        cpt: Sequence[float] | None,
    ) -> tuple[None, None, None]:
        """Validate deterministic factor arity and reject free parameters."""
        if p1 is not None or p2 is not None or cpt is not None:
            raise ValueError(f"Deterministic factor '{factor_id}' must not set p1/p2/cpt.")
        FactorGraph._validate_deterministic(factor_id, factor_type, v_list)
        return None, None, None

    @staticmethod
    def _validate_soft_entailment_parameters(
        factor_id: str,
        v_list: list[str],
        p1: float | None,
        p2: float | None,
        cpt: Sequence[float] | None,
    ) -> tuple[float, float, None]:
        """Validate and Cromwell-clamp soft-entailment parameters."""
        if cpt is not None:
            raise ValueError(f"SOFT_ENTAILMENT '{factor_id}' must not set cpt.")
        if len(v_list) != 1:
            raise ValueError(
                f"SOFT_ENTAILMENT '{factor_id}' requires exactly 1 premise variable, "
                f"got {len(v_list)}."
            )
        if p1 is None or p2 is None:
            raise ValueError(f"SOFT_ENTAILMENT '{factor_id}' requires p1 and p2.")
        p1c = _cromwell_clamp(p1, label=f"factor '{factor_id}' p1")
        p2c = _cromwell_clamp(p2, label=f"factor '{factor_id}' p2")
        if p1c + p2c <= 1.0:
            raise ValueError(
                f"SOFT_ENTAILMENT '{factor_id}' requires p1 + p2 > 1 "
                f"(after Cromwell clamp got {p1c + p2c})."
            )
        return p1c, p2c, None

    @staticmethod
    def _validate_conditional_parameters(
        factor_id: str,
        v_list: list[str],
        p1: float | None,
        p2: float | None,
        cpt: Sequence[float] | None,
    ) -> tuple[None, None, tuple[float, ...]]:
        """Validate and Cromwell-clamp a conditional CPT."""
        if p1 is not None or p2 is not None:
            raise ValueError(f"CONDITIONAL '{factor_id}' must not set p1/p2.")
        if not v_list:
            raise ValueError(f"CONDITIONAL '{factor_id}' requires at least one premise variable.")
        if cpt is None:
            raise ValueError(f"CONDITIONAL '{factor_id}' requires cpt.")
        expected = 1 << len(v_list)
        fcpt = tuple(_cromwell_clamp(float(x), label=f"cpt[{i}]") for i, x in enumerate(cpt))
        if len(fcpt) != expected:
            raise ValueError(
                f"CONDITIONAL '{factor_id}': cpt length must be 2^k = {expected}, got {len(fcpt)}."
            )
        return None, None, fcpt

    @staticmethod
    def _validate_pairwise_parameters(
        factor_id: str,
        v_list: list[str],
        p1: float | None,
        p2: float | None,
        cpt: Sequence[float] | None,
    ) -> tuple[None, None, tuple[float, ...]]:
        """Validate pairwise potential weights without Cromwell clamping."""
        if p1 is not None or p2 is not None:
            raise ValueError(f"PAIRWISE_POTENTIAL '{factor_id}' must not set p1/p2.")
        if len(v_list) != 1:
            raise ValueError(
                f"PAIRWISE_POTENTIAL '{factor_id}' requires exactly 1 variable plus "
                f"the paired conclusion variable, got {len(v_list)} variables."
            )
        if cpt is None:
            raise ValueError(f"PAIRWISE_POTENTIAL '{factor_id}' requires cpt.")
        fcpt = tuple(float(x) for x in cpt)
        if len(fcpt) != 4:
            raise ValueError(
                f"PAIRWISE_POTENTIAL '{factor_id}': cpt length must be 4, got {len(fcpt)}."
            )
        if any((not isfinite(x)) or x < 0.0 for x in fcpt):
            raise ValueError(
                f"PAIRWISE_POTENTIAL '{factor_id}' requires finite non-negative weights."
            )
        if sum(fcpt) <= 0.0:
            raise ValueError(
                f"PAIRWISE_POTENTIAL '{factor_id}' requires at least one positive weight."
            )
        return None, None, fcpt

    @staticmethod
    def _validate_deterministic(factor_id: str, ft: FactorType, v_list: list[str]) -> None:
        if ft == FactorType.IMPLICATION and len(v_list) != 2:
            raise ValueError(
                f"IMPLICATION '{factor_id}' requires exactly 2 variables, got {len(v_list)}."
            )
        if ft == FactorType.NEGATION and len(v_list) != 1:
            raise ValueError(
                f"NEGATION '{factor_id}' requires exactly 1 variable, got {len(v_list)}."
            )
        if ft == FactorType.CONJUNCTION and len(v_list) < 2:
            raise ValueError(
                f"CONJUNCTION '{factor_id}' requires at least 2 variables, got {len(v_list)}."
            )
        if ft == FactorType.DISJUNCTION and len(v_list) < 2:
            raise ValueError(
                f"DISJUNCTION '{factor_id}' requires at least 2 variables, got {len(v_list)}."
            )
        if (
            ft in (FactorType.EQUIVALENCE, FactorType.CONTRADICTION, FactorType.COMPLEMENT)
            and len(v_list) != 2
        ):
            raise ValueError(
                f"{ft.name} '{factor_id}' requires exactly 2 variables, got {len(v_list)}."
            )

    def get_var_to_factors(self) -> dict[str, list[int]]:
        """Return a reverse index from variable ID to incident factor indices."""
        index: dict[str, list[int]] = {vid: [] for vid in self.variables}
        for fi, factor in enumerate(self.factors):
            for vid in factor.all_vars:
                if vid in index:
                    index[vid].append(fi)
                else:
                    logger.warning(
                        "Factor '%s' references undeclared variable '%s'.",
                        factor.factor_id,
                        vid,
                    )
        return index

    def validate(self) -> list[str]:
        """Return structural validation errors without mutating the graph."""
        errors: list[str] = []
        for fi, factor in enumerate(self.factors):
            seen: set[str] = set()
            for vid in factor.all_vars:
                if vid not in self.variables:
                    errors.append(
                        f"Factor[{fi}] '{factor.factor_id}': variable '{vid}' not registered."
                    )
                if vid in seen:
                    errors.append(
                        f"Factor[{fi}] '{factor.factor_id}': "
                        f"variable '{vid}' appears more than once in all_vars."
                    )
                seen.add(vid)
        return errors

    def summary(self) -> str:
        """Return a human-readable summary of variables, unary factors, and factors."""
        lines = [f"FactorGraph: {len(self.variables)} variables, {len(self.factors)} factors"]
        lines.append("Variables:")
        for vid, measure in sorted(self.variables.items()):
            unary = self.unary_factors.get(vid)
            if unary is None:
                lines.append(f"  {vid:30s}  latent_measure={measure:.4f}")
            else:
                lines.append(f"  {vid:30s}  unary={unary:.4f}")
        lines.append("Factors:")
        for factor in self.factors:
            extra = ""
            if factor.p1 is not None and factor.p2 is not None:
                extra = f"  p1={factor.p1:.4f}  p2={factor.p2:.4f}"
            if factor.cpt is not None:
                extra += f"  cpt_len={len(factor.cpt)}"
            lines.append(
                f"  [{factor.factor_type.name:18s}] {factor.factor_id}"
                f"  variables={factor.variables}  conclusion={factor.conclusion}{extra}"
            )
        return "\n".join(lines)
