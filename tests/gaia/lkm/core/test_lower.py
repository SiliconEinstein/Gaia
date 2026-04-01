"""E2E tests for M3 lowering: Gaia IR → LKM local nodes.

Loads IR fixtures (*_ir.json), runs lower(), compares with expected LKM fixtures (*.json).
"""

import pytest

from gaia.lkm.core.lower import lower
from tests.fixtures.lkm import load_ir, load_package


PACKAGES = ["galileo", "einstein", "newton", "dark_energy"]


class TestLoweringE2E:
    """Test lowering against all 4 fixture packages."""

    @pytest.mark.parametrize("name", PACKAGES)
    def test_variable_count_matches(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        assert len(result.local_variables) == len(expected.local_variables), (
            f"{name}: expected {len(expected.local_variables)} variables, "
            f"got {len(result.local_variables)}"
        )

    @pytest.mark.parametrize("name", PACKAGES)
    def test_factor_count_matches(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        assert len(result.local_factors) == len(expected.local_factors), (
            f"{name}: expected {len(expected.local_factors)} factors, "
            f"got {len(result.local_factors)}"
        )

    @pytest.mark.parametrize("name", PACKAGES)
    def test_variable_ids_match(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        result_ids = {v.id for v in result.local_variables}
        expected_ids = {v.id for v in expected.local_variables}
        assert result_ids == expected_ids, (
            f"{name}: ID mismatch.\n"
            f"  Missing: {expected_ids - result_ids}\n"
            f"  Extra: {result_ids - expected_ids}"
        )

    @pytest.mark.parametrize("name", PACKAGES)
    def test_variable_content_hashes_match(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        result_hashes = {v.id: v.content_hash for v in result.local_variables}
        expected_hashes = {v.id: v.content_hash for v in expected.local_variables}
        for vid in expected_hashes:
            assert result_hashes[vid] == expected_hashes[vid], (
                f"{name}: content_hash mismatch for {vid}"
            )

    @pytest.mark.parametrize("name", PACKAGES)
    def test_variable_types_match(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        result_types = {v.id: v.type for v in result.local_variables}
        expected_types = {v.id: v.type for v in expected.local_variables}
        for vid in expected_types:
            assert result_types[vid] == expected_types[vid], f"{name}: type mismatch for {vid}"

    @pytest.mark.parametrize("name", PACKAGES)
    def test_factor_subtypes_match(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        # Compare by (premises, conclusion, subtype) since IDs differ
        result_sigs = {
            (tuple(sorted(f.premises)), f.conclusion, f.subtype) for f in result.local_factors
        }
        expected_sigs = {
            (tuple(sorted(f.premises)), f.conclusion, f.subtype) for f in expected.local_factors
        }
        assert result_sigs == expected_sigs, (
            f"{name}: factor structure mismatch.\n"
            f"  Missing: {expected_sigs - result_sigs}\n"
            f"  Extra: {result_sigs - expected_sigs}"
        )

    @pytest.mark.parametrize("name", PACKAGES)
    def test_version_propagated(self, name):
        ir = load_ir(name)
        expected = load_package(name)
        result = lower(ir, version=expected.version)
        for v in result.local_variables:
            assert v.version == expected.version, f"Variable {v.id} missing version"
        for f in result.local_factors:
            assert f.version == expected.version, f"Factor {f.id} missing version"


class TestLoweringDeterminism:
    def test_same_input_same_output(self):
        """Lowering must be deterministic."""
        ir = load_ir("galileo")
        r1 = lower(ir, version="4.0.0")
        r2 = lower(ir, version="4.0.0")
        assert [v.id for v in r1.local_variables] == [v.id for v in r2.local_variables]
        assert [f.id for f in r1.local_factors] == [f.id for f in r2.local_factors]


class TestLoweringProperties:
    def test_all_variables_public(self):
        """All Knowledge nodes lower to public visibility (no FormalStrategy in fixtures)."""
        ir = load_ir("galileo")
        result = lower(ir, version="4.0.0")
        for v in result.local_variables:
            assert v.visibility == "public"

    def test_strategy_factors_have_steps(self):
        """Strategy factors should preserve reasoning steps."""
        ir = load_ir("galileo")
        result = lower(ir, version="4.0.0")
        strategy_factors = [f for f in result.local_factors if f.factor_type == "strategy"]
        for f in strategy_factors:
            assert f.steps is not None and len(f.steps) > 0, f"Strategy factor {f.id} missing steps"

    def test_operator_factors_no_steps(self):
        """Operator factors should have no steps."""
        ir = load_ir("galileo")
        result = lower(ir, version="4.0.0")
        operator_factors = [f for f in result.local_factors if f.factor_type == "operator"]
        for f in operator_factors:
            assert f.steps is None, f"Operator factor {f.id} should not have steps"

    def test_operator_factors_no_background(self):
        """Operator factors should have no background."""
        ir = load_ir("galileo")
        result = lower(ir, version="4.0.0")
        operator_factors = [f for f in result.local_factors if f.factor_type == "operator"]
        for f in operator_factors:
            assert f.background is None, f"Operator factor {f.id} should not have background"
