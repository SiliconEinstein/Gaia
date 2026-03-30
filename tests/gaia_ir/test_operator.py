"""Tests for Operator data model."""

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
    def test_equivalence(self):
        op = Operator(operator="equivalence", variables=["gcn_a", "gcn_b"])
        assert op.conclusion is None

    def test_contradiction(self):
        op = Operator(operator="contradiction", variables=["gcn_a", "gcn_b"])
        assert op.conclusion is None

    def test_complement(self):
        op = Operator(operator="complement", variables=["gcn_a", "gcn_b"])
        assert op.conclusion is None

    def test_implication(self):
        op = Operator(
            operator="implication",
            variables=["gcn_a", "gcn_b"],
            conclusion="gcn_b",
        )
        assert op.conclusion == "gcn_b"

    def test_conjunction(self):
        op = Operator(
            operator="conjunction",
            variables=["gcn_a", "gcn_b", "gcn_m"],
            conclusion="gcn_m",
        )
        assert op.conclusion == "gcn_m"

    def test_disjunction(self):
        op = Operator(
            operator="disjunction",
            variables=["gcn_a", "gcn_b", "gcn_c"],
        )
        assert op.conclusion is None


class TestOperatorValidation:
    def test_equivalence_rejects_conclusion(self):
        with pytest.raises(ValueError, match="conclusion=None"):
            Operator(operator="equivalence", variables=["a", "b"], conclusion="a")

    def test_contradiction_rejects_conclusion(self):
        with pytest.raises(ValueError, match="conclusion=None"):
            Operator(operator="contradiction", variables=["a", "b"], conclusion="a")

    def test_complement_rejects_three_variables(self):
        with pytest.raises(ValueError, match="exactly 2"):
            Operator(operator="complement", variables=["a", "b", "c"])

    def test_implication_requires_conclusion(self):
        with pytest.raises(ValueError, match="requires conclusion"):
            Operator(operator="implication", variables=["a", "b"])

    def test_implication_requires_two_variables(self):
        with pytest.raises(ValueError, match="exactly 2"):
            Operator(operator="implication", variables=["a", "b", "c"], conclusion="c")

    def test_implication_requires_conclusion_as_last_variable(self):
        with pytest.raises(ValueError, match="variables\\[-1\\]"):
            Operator(operator="implication", variables=["a", "b"], conclusion="a")

    def test_conjunction_requires_conclusion(self):
        with pytest.raises(ValueError, match="requires conclusion"):
            Operator(operator="conjunction", variables=["a", "b", "m"])

    def test_conjunction_requires_conclusion_as_last_variable(self):
        with pytest.raises(ValueError, match="variables\\[-1\\]"):
            Operator(operator="conjunction", variables=["a", "b", "m"], conclusion="a")

    def test_conclusion_must_be_in_variables(self):
        with pytest.raises(ValueError, match="must appear in variables"):
            Operator(operator="implication", variables=["a", "b"], conclusion="c")

    def test_disjunction_rejects_conclusion(self):
        with pytest.raises(ValueError, match="conclusion=None"):
            Operator(operator="disjunction", variables=["a", "b"], conclusion="a")


class TestOperatorScope:
    def test_standalone_with_id(self):
        op = Operator(
            operator_id="gco_abc",
            scope="global",
            operator="equivalence",
            variables=["gcn_a", "gcn_b"],
        )
        assert op.operator_id == "gco_abc"
        assert op.scope == "global"

    def test_embedded_no_scope(self):
        """Operators inside FormalExpr don't need scope or id."""
        op = Operator(operator="implication", variables=["a", "b"], conclusion="b")
        assert op.scope is None
        assert op.operator_id is None

    def test_invalid_scope_rejected(self):
        with pytest.raises(ValueError, match="scope must be one of"):
            Operator(scope="detached", operator="equivalence", variables=["a", "b"])

    def test_local_scope_requires_lco_prefix(self):
        with pytest.raises(ValueError, match="lco_ prefix"):
            Operator(
                operator_id="gco_wrong",
                scope="local",
                operator="equivalence",
                variables=["a", "b"],
            )

    def test_global_scope_requires_gco_prefix(self):
        with pytest.raises(ValueError, match="gco_ prefix"):
            Operator(
                operator_id="lco_wrong",
                scope="global",
                operator="equivalence",
                variables=["a", "b"],
            )
