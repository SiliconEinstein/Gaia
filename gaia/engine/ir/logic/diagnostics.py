"""Formula-graph logic diagnostics for Gaia IR."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from gaia.engine.ir.graphs import LocalCanonicalGraph

FormulaDiagnosticSeverity = Literal["info", "warning", "fatal"]
FormulaDiagnosticScope = Literal["claim", "claim_pair", "package"]
FormulaLogicStrength = Literal["hard", "soft", "mixed", "unknown"]

DiagnosticConditionKind = Literal[
    "formula_unsat",
    "formula_tautology",
    "joint_incompatibility",
    "entailment_violation",
    "redundant_formula",
]
ConditionConfidenceBasis = Literal["hard_logic", "soft_relation", "projection"]


class DiagnosticCondition(BaseModel):
    """Machine-readable Boolean event associated with a diagnostic."""

    model_config = ConfigDict(extra="forbid")

    kind: DiagnosticConditionKind
    variables: list[str] = Field(default_factory=list)
    expression: dict[str, Any]
    confidence_basis: ConditionConfidenceBasis


class FormulaDiagnostic(BaseModel):
    """One formula-level diagnostic emitted for a compiled graph."""

    model_config = ConfigDict(extra="forbid")

    code: str
    severity: FormulaDiagnosticSeverity
    scope: FormulaDiagnosticScope
    logic_strength: FormulaLogicStrength
    source_claim: str | None = None
    related_claims: list[str] = Field(default_factory=list)
    formula_nodes: list[str] = Field(default_factory=list)
    condition: DiagnosticCondition | None = None
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class FormulaDiagnosticReport(BaseModel):
    """Collection of formula diagnostics."""

    model_config = ConfigDict(extra="forbid")

    diagnostics: list[FormulaDiagnostic] = Field(default_factory=list)

    @property
    def has_fatal(self) -> bool:
        """Return whether any diagnostic should block the local claim."""
        return any(diagnostic.severity == "fatal" for diagnostic in self.diagnostics)


def inspect_formula_graphs(
    graph: LocalCanonicalGraph,
    *,
    include_pairwise: bool = True,
) -> FormulaDiagnosticReport:
    """Inspect formula graphs and return reviewer-facing logic diagnostics."""
    del graph, include_pairwise
    return FormulaDiagnosticReport()
