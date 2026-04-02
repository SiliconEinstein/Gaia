"""End-to-end test: Galileo's falling bodies argument compiled to Gaia IR v2."""

import json

from gaia.lang import Package, claim, contradiction, setting
from gaia.lang.compiler import compile_package
from gaia.ir import LocalCanonicalGraph
from gaia.ir.validator import validate_local_graph


def test_galileo_falling_bodies():
    with Package("galileo_falling_bodies", namespace="reg", version="4.0.0") as pkg:
        # Background
        aristotle_doctrine = setting("""
            Aristotle's doctrine: heavier objects fall proportionally faster.
        """)

        # Observations
        heavy_falls_faster = claim(r"""
            Observations show heavier stones fall faster than feathers.
        """)

        # Thought experiment
        composite_slower = claim(r"""
            The tied composite should be slower (light ball drags heavy ball).
            $v_{\text{composite}} = \frac{m_1 v_1 + m_2 v_2}{m_1 + m_2}$
        """)

        composite_faster = claim(r"""
            The composite has greater mass, so it should be faster.
            $v_{\text{composite}} = k(m_1 + m_2) > k m_1$
        """)

        # Contradiction
        tied_ball = contradiction(
            composite_slower,
            composite_faster,
            reason="Same premise yields contradictory conclusions",
        )

        # Conclusions
        air_resistance = claim(
            """
            Observed speed differences are caused entirely by air resistance.
        """,
            given=[tied_ball],
        )

        vacuum_prediction = claim(
            r"""
            In a vacuum, objects of different mass fall at the same rate.
            $g \approx 9.8 \text{ m/s}^2$, independent of mass.
        """,
            given=[tied_ball, heavy_falls_faster],
        )

    # Assign labels (simulating variable name capture)
    for k in pkg.knowledge:
        for name, val in locals().items():
            if val is k and name != "k":
                k.label = name
                break

    ir = compile_package(pkg)

    # Structural checks
    assert ir["package_name"] == "galileo_falling_bodies"
    assert ir["package"]["version"] == "4.0.0"

    # Knowledge: setting(1) + claims(author: heavy_falls_faster, composite_slower,
    #   composite_faster + helper from contradiction: tied_ball + derived: air_resistance,
    #   vacuum_prediction) = 7 total
    claims = [k for k in ir["knowledges"] if k["type"] == "claim"]
    settings_list = [k for k in ir["knowledges"] if k["type"] == "setting"]
    assert len(settings_list) == 1
    assert len(claims) == 6
    assert len(ir["knowledges"]) == 7

    # Strategies: air_resistance has 1 noisy_and, vacuum_prediction has 1 noisy_and = 2
    assert len(ir["strategies"]) == 2
    for s in ir["strategies"]:
        assert s["type"] == "noisy_and"

    # Operators: 1 contradiction (top-level)
    assert len(ir["operators"]) == 1
    assert ir["operators"][0]["operator"] == "contradiction"

    # Input claims: heavy_falls_faster, composite_slower, composite_faster
    # (tied_ball is a helper, air_resistance and vacuum_prediction are derived)
    inputs = [k for k in ir["knowledges"] if k.get("is_input")]
    input_labels = {k["label"] for k in inputs}
    assert "heavy_falls_faster" in input_labels
    assert "composite_slower" in input_labels
    assert "composite_faster" in input_labels
    assert "vacuum_prediction" not in input_labels
    assert "air_resistance" not in input_labels

    # IR hash is present and valid
    assert ir["ir_hash"] is not None
    assert ir["ir_hash"].startswith("sha256:")
    assert len(ir["ir_hash"]) == 71  # "sha256:" + 64 hex chars
    result = validate_local_graph(LocalCanonicalGraph(**ir))
    assert result.valid, result.errors

    # Serializable to JSON
    json_str = json.dumps(ir, ensure_ascii=False, indent=2)
    assert len(json_str) > 0
