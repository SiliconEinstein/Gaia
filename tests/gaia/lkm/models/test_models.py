"""M1 unit tests — LKM-specific model logic only.

Does NOT duplicate Gaia IR validation tests (QID format, content_hash
auto-compute, etc.) — those are upstream's responsibility.
"""

from datetime import datetime, timezone

from gaia.lkm.models import (
    CROMWELL_EPS,
    FactorParamRecord,
    PriorRecord,
    compute_content_hash,
    cromwell_clamp,
    new_gcn_id,
    new_gfac_id,
)


class TestContentHash:
    """content_hash is the foundation of cross-package dedup — must be rock solid."""

    def test_cross_package_stable(self):
        """Same content with different packages must produce identical hash."""
        params = [("x", "int"), ("y", "str")]
        h1 = compute_content_hash("claim", "YBCO superconducts at 90K", params)
        h2 = compute_content_hash("claim", "YBCO superconducts at 90K", params)
        assert h1 == h2

    def test_parameter_order_independent(self):
        """Parameter order must not affect hash."""
        h1 = compute_content_hash("claim", "test", [("x", "int"), ("y", "str")])
        h2 = compute_content_hash("claim", "test", [("y", "str"), ("x", "int")])
        assert h1 == h2

    def test_type_matters(self):
        """Different types must produce different hashes."""
        h1 = compute_content_hash("claim", "test content", [])
        h2 = compute_content_hash("setting", "test content", [])
        assert h1 != h2

    def test_matches_upstream(self):
        """Must produce same hash as gaia.gaia_ir.knowledge._compute_content_hash."""
        from gaia.gaia_ir.knowledge import Parameter as IRParameter
        from gaia.gaia_ir.knowledge import _compute_content_hash as upstream_hash

        lkm_hash = compute_content_hash("claim", "test", [("a", "material"), ("b", "temp")])
        upstream = upstream_hash(
            "claim",
            "test",
            [IRParameter(name="a", type="material"), IRParameter(name="b", type="temp")],
        )
        assert lkm_hash == upstream


class TestCromwellClamping:
    """Cromwell's rule: no P=0 or P=1 — prevents degenerate potentials in BP."""

    def test_prior_record_clamps_zero(self):
        pr = PriorRecord(
            variable_id="gcn_abc",
            value=0.0,
            source_id="s1",
            created_at=datetime.now(timezone.utc),
        )
        assert pr.value == CROMWELL_EPS

    def test_prior_record_clamps_one(self):
        pr = PriorRecord(
            variable_id="gcn_abc",
            value=1.0,
            source_id="s1",
            created_at=datetime.now(timezone.utc),
        )
        assert pr.value == 1 - CROMWELL_EPS

    def test_prior_record_normal_value_unchanged(self):
        pr = PriorRecord(
            variable_id="gcn_abc",
            value=0.7,
            source_id="s1",
            created_at=datetime.now(timezone.utc),
        )
        assert pr.value == 0.7

    def test_factor_param_clamps_all_values(self):
        fp = FactorParamRecord(
            factor_id="gfac_abc",
            conditional_probabilities=[0.0, 1.0, 0.5],
            source_id="s1",
            created_at=datetime.now(timezone.utc),
        )
        assert fp.conditional_probabilities == [CROMWELL_EPS, 1 - CROMWELL_EPS, 0.5]

    def test_cromwell_clamp_function(self):
        assert cromwell_clamp(-0.5) == CROMWELL_EPS
        assert cromwell_clamp(1.5) == 1 - CROMWELL_EPS
        assert cromwell_clamp(0.5) == 0.5


class TestIdGeneration:
    """gcn_id and gfac_id must have correct format and be unique."""

    def test_gcn_id_format(self):
        gid = new_gcn_id()
        assert gid.startswith("gcn_")
        assert len(gid) == 20  # "gcn_" + 16 hex chars

    def test_gfac_id_format(self):
        fid = new_gfac_id()
        assert fid.startswith("gfac_")
        assert len(fid) == 21  # "gfac_" + 16 hex chars

    def test_ids_are_unique(self):
        ids = {new_gcn_id() for _ in range(100)}
        assert len(ids) == 100
