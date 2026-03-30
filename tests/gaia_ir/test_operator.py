"""Tests for Operator data model — §2.4 inputs/conclusion separation."""

import pytest
from gaia.gaia_ir import Operator, OperatorType


class TestOperatorType:
    def test_six_types(self):
        assert set(OperatorType) == {
            "implication",
            "equivalence",
            "contradiction",
            "complement",
            "disjunction",
            "conjunction",
        }


class TestOperatorCreation:
    """Valid construction for each operator type under the new contract."""

    def test_implication(self):
        op = Operator(operator="implication", variables=["gcn_a"], conclusion="gcn_b")
        assert op.variables == ["gcn_a"]
        assert op.conclusion == "gcn_b"

    def test_conjunction(self):
        op = Operator(
            operator="conjunction",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_m",
        )
        assert op.variables == ["gcn_a", "gcn_b"]
        assert op.conclusion == "gcn_m"

    def test_equivalence(self):
        op = Operator(operator="equivalence", variables=["gcn_a", "gcn_b"], conclusion="gcn_h")
        assert op.conclusion == "gcn_h"

    def test_contradiction(self):
        op = Operator(operator="contradiction", variables=["gcn_a", "gcn_b"], conclusion="gcn_h")
        assert op.conclusion == "gcn_h"

    def test_complement(self):
        op = Operator(operator="complement", variables=["gcn_a", "gcn_b"], conclusion="gcn_h")
        assert op.conclusion == "gcn_h"

    def test_disjunction(self):
        op = Operator(
            operator="disjunction",
            variables=["gcn_a", "gcn_b", "gcn_c"],
            conclusion="gcn_h",
        )
        assert op.conclusion == "gcn_h"

    def test_conjunction_many_inputs(self):
        op = Operator(
            operator="conjunction",
            variables=["a", "b", "c", "d"],
            conclusion="m",
        )
        assert len(op.variables) == 4

    def test_disjunction_two_inputs(self):
        op = Operator(operator="disjunction", variables=["a", "b"], conclusion="h")
        assert len(op.variables) == 2


class TestConclusionSeparation:
    """§2.4: conclusion must never appear in variables."""

    def test_conclusion_in_variables_rejected(self):
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(operator="implication", variables=["a"], conclusion="a")

    def test_conjunction_conclusion_in_variables_rejected(self):
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(operator="conjunction", variables=["a", "b", "m"], conclusion="m")

    def test_equivalence_conclusion_in_variables_rejected(self):
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(operator="equivalence", variables=["a", "b"], conclusion="a")

    def test_disjunction_conclusion_in_variables_rejected(self):
        with pytest.raises(ValueError, match="must not appear in variables"):
            Operator(operator="disjunction", variables=["a", "b"], conclusion="a")


class TestArityConstraints:
    """§2.4: variable count constraints per operator type."""

    def test_implication_rejects_zero_variables(self):
        with pytest.raises(ValueError, match="exactly 1 variable"):
            Operator(operator="implication", variables=[], conclusion="b")

    def test_implication_rejects_two_variables(self):
        with pytest.raises(ValueError, match="exactly 1 variable"):
            Operator(operator="implication", variables=["a", "b"], conclusion="c")

    def test_conjunction_rejects_one_variable(self):
        with pytest.raises(ValueError, match="at least 2 variables"):
            Operator(operator="conjunction", variables=["a"], conclusion="m")

    def test_equivalence_rejects_three_variables(self):
        with pytest.raises(ValueError, match="exactly 2 variables"):
            Operator(operator="equivalence", variables=["a", "b", "c"], conclusion="h")

    def test_equivalence_rejects_one_variable(self):
        with pytest.raises(ValueError, match="exactly 2 variables"):
            Operator(operator="equivalence", variables=["a"], conclusion="h")

    def test_contradiction_rejects_three_variables(self):
        with pytest.raises(ValueError, match="exactly 2 variables"):
            Operator(operator="contradiction", variables=["a", "b", "c"], conclusion="h")

    def test_complement_rejects_three_variables(self):
        with pytest.raises(ValueError, match="exactly 2 variables"):
            Operator(operator="complement", variables=["a", "b", "c"], conclusion="h")

    def test_disjunction_rejects_one_variable(self):
        with pytest.raises(ValueError, match="at least 2 variables"):
            Operator(operator="disjunction", variables=["a"], conclusion="h")


class TestConclusionRequired:
    """conclusion is now a required field (str, not str | None)."""

    def test_missing_conclusion_rejected(self):
        with pytest.raises(Exception):
            Operator(operator="implication", variables=["a"])

    def test_missing_conclusion_equivalence_rejected(self):
        with pytest.raises(Exception):
            Operator(operator="equivalence", variables=["a", "b"])


class TestOperatorScope:
    def test_standalone_with_id(self):
        op = Operator(
            operator_id="gco_abc",
            scope="global",
            operator="equivalence",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_h",
        )
        assert op.operator_id == "gco_abc"
        assert op.scope == "global"

    def test_embedded_no_scope(self):
        """Operators inside FormalExpr don't need scope or id."""
        op = Operator(operator="implication", variables=["a"], conclusion="b")
        assert op.scope is None
        assert op.operator_id is None

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be one of"):
            Operator(scope="detached", operator="equivalence", variables=["a", "b"], conclusion="h")

    def test_local_scope_requires_lco_prefix(self):
        with pytest.raises(ValueError, match="lco_ prefix"):
            Operator(
                operator_id="gco_wrong",
                scope="local",
                operator="equivalence",
                variables=["a", "b"],
                conclusion="h",
            )

    def test_global_scope_requires_gco_prefix(self):
        with pytest.raises(ValueError, match="gco_ prefix"):
            Operator(
                operator_id="lco_wrong",
                scope="global",
                operator="equivalence",
                variables=["a", "b"],
                conclusion="h",
            )
