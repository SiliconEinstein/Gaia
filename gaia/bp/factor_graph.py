"""Factor graph representation for BP — aligned with theory and Gaia IR.

Theory: docs/foundations/theory/06-factor-graphs.md (operator to potential mapping)
IR: docs/foundations/gaia-ir/02-gaia-ir.md (Operator variables + conclusion)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum, auto
from typing import Sequence

logger = logging.getLogger(__name__)

CROMWELL_EPS: float = 1e-3


def _cromwell_clamp(value: float, label: str = "") -> float:
    clamped = max(CROMWELL_EPS, min(1.0 - CROMWELL_EPS, value))
    if clamped != value and label:
        logger.debug("Cromwell clamp: %s %.6g -> %.6g", label, value, clamped)
    return clamped


class FactorType(Enum):
    IMPLICATION = auto()
    CONJUNCTION = auto()
    DISJUNCTION = auto()
    EQUIVALENCE = auto()
    CONTRADICTION = auto()
    COMPLEMENT = auto()
    SOFT_ENTAILMENT = auto()
    CONDITIONAL = auto()


@dataclass(frozen=True)
class Factor:
    factor_id: str
    factor_type: FactorType
    variables: list[str]
    conclusion: str
    p1: float | None = None
    p2: float | None = None
    cpt: tuple[float, ...] | None = None
    directed: bool = False

    @property
    def all_vars(self) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for v in (*self.variables, self.conclusion):
            if v not in seen:
                seen.add(v)
                out.append(v)
        return out


class FactorGraph:
    def __init__(self) -> None:
        self.variables: dict[str, float] = {}
        self.factors: list[Factor] = []

    def add_variable(self, var_id: str, prior: float) -> None:
        self.variables[var_id] = _cromwell_clamp(prior, label=f"variable '{var_id}' prior")

    def observe(self, var_id: str, value: int) -> None:
        """Hard evidence: clamp variable to observed value (07-bp §1.7).

        Implemented by setting prior to near-0 or near-1 (Cromwell-bounded).
        This is equivalent to adding a unary delta factor.
        """
        if var_id not in self.variables:
            raise KeyError(f"Variable '{var_id}' not registered.")
        if value not in (0, 1):
            raise ValueError(f"observe() value must be 0 or 1, got {value}.")
        self.variables[var_id] = 1.0 - CROMWELL_EPS if value == 1 else CROMWELL_EPS

    def add_likelihood(
        self,
        var_id: str,
        likelihood_ratio: float,
    ) -> None:
        """Soft evidence: multiply variable's prior by likelihood ratio (07-bp §1.7).

        P_new(x=1) = normalize(π * lr, (1-π) * 1) where lr = P(E|x=1)/P(E|x=0).
        """
        if var_id not in self.variables:
            raise KeyError(f"Variable '{var_id}' not registered.")
        if likelihood_ratio <= 0:
            raise ValueError(f"likelihood_ratio must be > 0, got {likelihood_ratio}.")
        pi = self.variables[var_id]
        odds = pi / (1.0 - pi) * likelihood_ratio
        new_pi = odds / (1.0 + odds)
        self.variables[var_id] = _cromwell_clamp(new_pi, label=f"likelihood '{var_id}'")

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
        directed: bool = False,
    ) -> None:
        v_list = list(variables)
        if conclusion in v_list:
            raise ValueError(
                f"Factor '{factor_id}': conclusion '{conclusion}' must not appear in variables."
            )

        ft = factor_type
        fp1: float | None = None
        fp2: float | None = None
        fcpt: tuple[float, ...] | None = None

        if ft in (
            FactorType.IMPLICATION,
            FactorType.CONJUNCTION,
            FactorType.DISJUNCTION,
            FactorType.EQUIVALENCE,
            FactorType.CONTRADICTION,
            FactorType.COMPLEMENT,
        ):
            if p1 is not None or p2 is not None or cpt is not None:
                raise ValueError(f"Deterministic factor '{factor_id}' must not set p1/p2/cpt.")
            self._validate_deterministic(factor_id, ft, v_list)

        elif ft == FactorType.SOFT_ENTAILMENT:
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
            fp1, fp2 = p1c, p2c

        elif ft == FactorType.CONDITIONAL:
            if p1 is not None or p2 is not None:
                raise ValueError(f"CONDITIONAL '{factor_id}' must not set p1/p2.")
            if not v_list:
                raise ValueError(
                    f"CONDITIONAL '{factor_id}' requires at least one premise variable."
                )
            if cpt is None:
                raise ValueError(f"CONDITIONAL '{factor_id}' requires cpt.")
            expected = 1 << len(v_list)
            fcpt = tuple(_cromwell_clamp(float(x), label=f"cpt[{i}]") for i, x in enumerate(cpt))
            if len(fcpt) != expected:
                raise ValueError(
                    f"CONDITIONAL '{factor_id}': cpt length must be 2^k = {expected}, "
                    f"got {len(fcpt)}."
                )
        else:
            raise ValueError(f"Unknown FactorType: {ft!r}")

        self.factors.append(
            Factor(
                factor_id=factor_id,
                factor_type=factor_type,
                variables=v_list,
                conclusion=conclusion,
                p1=fp1,
                p2=fp2,
                cpt=fcpt,
                directed=directed,
            )
        )

    @staticmethod
    def _validate_deterministic(factor_id: str, ft: FactorType, v_list: list[str]) -> None:
        if ft == FactorType.IMPLICATION and len(v_list) != 2:
            raise ValueError(
                f"IMPLICATION '{factor_id}' requires exactly 2 variables, got {len(v_list)}."
            )
        if ft == FactorType.CONJUNCTION and len(v_list) < 2:
            raise ValueError(
                f"CONJUNCTION '{factor_id}' requires at least 2 variables, got {len(v_list)}."
            )
        if ft == FactorType.DISJUNCTION and len(v_list) < 2:
            raise ValueError(
                f"DISJUNCTION '{factor_id}' requires at least 2 variables, got {len(v_list)}."
            )
        if ft in (FactorType.EQUIVALENCE, FactorType.CONTRADICTION, FactorType.COMPLEMENT):
            if len(v_list) != 2:
                raise ValueError(
                    f"{ft.name} '{factor_id}' requires exactly 2 variables, got {len(v_list)}."
                )

    def get_var_to_factors(self) -> dict[str, list[int]]:
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
        lines = [f"FactorGraph: {len(self.variables)} variables, {len(self.factors)} factors"]
        lines.append("Variables:")
        for vid, prior in sorted(self.variables.items()):
            lines.append(f"  {vid:30s}  prior={prior:.4f}")
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
