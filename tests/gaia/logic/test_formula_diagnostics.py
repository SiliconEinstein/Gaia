from gaia.engine.ir.logic.diagnostics import (
    DiagnosticCondition,
    FormulaDiagnostic,
    FormulaDiagnosticReport,
    inspect_formula_graphs,
)


def test_formula_diagnostic_models_round_trip_json():
    condition = DiagnosticCondition(
        kind="joint_incompatibility",
        variables=["t:pkg::left", "t:pkg::right"],
        expression={
            "op": "and",
            "args": [{"var": "t:pkg::left"}, {"var": "t:pkg::right"}],
        },
        confidence_basis="hard_logic",
    )
    diagnostic = FormulaDiagnostic(
        code="cross_claim_incompatibility",
        severity="warning",
        scope="claim_pair",
        logic_strength="hard",
        source_claim="t:pkg::left",
        related_claims=["t:pkg::right"],
        formula_nodes=["fg:left", "fg:right"],
        condition=condition,
        message="Claims cannot both hold.",
    )
    report = FormulaDiagnosticReport(diagnostics=[diagnostic])

    round_tripped = FormulaDiagnosticReport.model_validate_json(report.model_dump_json())

    assert round_tripped == report
    assert round_tripped.has_fatal is False
    assert inspect_formula_graphs is not None
