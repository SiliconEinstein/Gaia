"""End-to-end examples: Galileo, Newton, Einstein — coarse & fine graphs.

Builds Gaia IR LocalCanonicalGraphs by hand, lowers them to FactorGraphs,
and runs BP to verify belief propagation produces sensible posteriors.
"""

from __future__ import annotations

from gaia.bp import lower_local_graph
from gaia.bp.bp import BeliefPropagation
from gaia.bp.exact import exact_inference
from gaia.gaia_ir import Knowledge, Operator, Strategy, LocalCanonicalGraph


NS, PKG_G, PKG_N, PKG_E = "reg", "galileo", "newton", "einstein"


def _qid(pkg: str, label: str) -> str:
    return f"{NS}:{pkg}::{label}"


def _claim(pkg: str, label: str, content: str) -> Knowledge:
    return Knowledge(id=_qid(pkg, label), type="claim", content=content)


def _lg(pkg: str, **kw) -> LocalCanonicalGraph:
    kw.setdefault("namespace", NS)
    kw.setdefault("package_name", pkg)
    return LocalCanonicalGraph(**kw)


# ============================================================================
# Galileo — Falling Bodies
# ============================================================================


class TestGalileoCoarse:
    """Coarse graph: 4 premises → noisy_and → vacuum_prediction."""

    def _build(self):
        tied_balls = _claim("galileo", "tied_balls_contradiction", "绑球矛盾")
        air_resist = _claim("galileo", "air_resistance_is_confound", "介质阻力是混淆因素")
        inclined = _claim("galileo", "inclined_plane_observation", "斜面实验")
        vacuum_env = _claim("galileo", "vacuum_env", "真空环境设定")
        vacuum_pred = _claim("galileo", "vacuum_prediction", "真空中等速下落")

        s = Strategy(
            scope="local",
            type="noisy_and",
            premises=[tied_balls.id, air_resist.id, inclined.id, vacuum_env.id],
            conclusion=vacuum_pred.id,
        )
        return _lg(
            "galileo",
            knowledges=[tied_balls, air_resist, inclined, vacuum_env, vacuum_pred],
            strategies=[s],
        ), s

    def test_builds_and_validates(self):
        g, s = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("galileo", "tied_balls_contradiction"): 0.9,
                _qid("galileo", "air_resistance_is_confound"): 0.85,
                _qid("galileo", "inclined_plane_observation"): 0.95,
                _qid("galileo", "vacuum_env"): 0.99,
            },
            strategy_conditional_params={s.strategy_id: [0.9]},
        )
        assert not fg.validate()
        beliefs, _ = exact_inference(fg)
        vp = beliefs[_qid("galileo", "vacuum_prediction")]
        assert vp > 0.6, f"vacuum_prediction belief too low: {vp:.4f}"

    def test_strong_premises_raise_conclusion(self):
        g, s = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("galileo", "tied_balls_contradiction"): 0.95,
                _qid("galileo", "air_resistance_is_confound"): 0.95,
                _qid("galileo", "inclined_plane_observation"): 0.98,
                _qid("galileo", "vacuum_env"): 0.99,
            },
            strategy_conditional_params={s.strategy_id: [0.95]},
        )
        beliefs, _ = exact_inference(fg)
        vp = beliefs[_qid("galileo", "vacuum_prediction")]
        assert vp > 0.8, f"Expected high belief, got {vp:.4f}"


class TestGalileoFine:
    """Fine graph: decomposed tied-ball argument with contradiction operator."""

    def _build(self):
        heavier_faster = _claim("galileo", "heavier_falls_faster", "重者下落更快")
        thought_exp = _claim("galileo", "thought_experiment_env", "思想实验环境")
        composite_slower = _claim("galileo", "composite_is_slower", "HL慢于H")
        composite_faster = _claim("galileo", "composite_is_faster", "HL快于H")
        contra_helper = _claim("galileo", "tied_balls_contra_h", "矛盾helper")
        medium_obs = _claim("galileo", "medium_density_observation", "介质密度观察")
        inclined_obs = _claim("galileo", "inclined_plane_observation", "斜面观察")
        air_resist = _claim("galileo", "air_resistance_is_confound", "介质阻力")
        vacuum_env = _claim("galileo", "vacuum_env", "真空环境")
        vacuum_pred = _claim("galileo", "vacuum_prediction", "真空中等速下落")

        # composite_is_slower: noisy_and from heavier_faster + thought_exp
        s1 = Strategy(
            scope="local",
            type="noisy_and",
            premises=[heavier_faster.id, thought_exp.id],
            conclusion=composite_slower.id,
        )
        # composite_is_faster: noisy_and from heavier_faster + thought_exp
        s2 = Strategy(
            scope="local",
            type="noisy_and",
            premises=[heavier_faster.id, thought_exp.id],
            conclusion=composite_faster.id,
        )
        contra_op = Operator(
            operator_id="lco_001",
            scope="local",
            operator="contradiction",
            variables=[composite_slower.id, composite_faster.id],
            conclusion=contra_helper.id,
        )
        # air_resistance from medium_density_observation
        s3 = Strategy(
            scope="local",
            type="noisy_and",
            premises=[medium_obs.id],
            conclusion=air_resist.id,
        )
        # vacuum_prediction from all evidence
        s4 = Strategy(
            scope="local",
            type="noisy_and",
            premises=[contra_helper.id, air_resist.id, inclined_obs.id, vacuum_env.id],
            conclusion=vacuum_pred.id,
        )

        g = _lg(
            "galileo",
            knowledges=[
                heavier_faster,
                thought_exp,
                composite_slower,
                composite_faster,
                contra_helper,
                medium_obs,
                inclined_obs,
                air_resist,
                vacuum_env,
                vacuum_pred,
            ],
            operators=[contra_op],
            strategies=[s1, s2, s3, s4],
        )
        return g, {
            s1.strategy_id: [0.95],
            s2.strategy_id: [0.95],
            s3.strategy_id: [0.85],
            s4.strategy_id: [0.9],
        }

    def test_contradiction_suppresses_premise(self):
        g, sp = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("galileo", "heavier_falls_faster"): 0.7,
                _qid("galileo", "thought_experiment_env"): 0.99,
                _qid("galileo", "medium_density_observation"): 0.95,
                _qid("galileo", "inclined_plane_observation"): 0.95,
                _qid("galileo", "vacuum_env"): 0.99,
            },
            strategy_conditional_params=sp,
        )
        assert not fg.validate()
        beliefs, _ = exact_inference(fg)
        # Contradiction between composite_slower and composite_faster suppresses
        # the shared premise heavier_falls_faster
        hff = beliefs[_qid("galileo", "heavier_falls_faster")]
        assert hff < 0.7, f"heavier_falls_faster should decrease, got {hff:.4f}"
        # vacuum_prediction should still be supported
        vp = beliefs[_qid("galileo", "vacuum_prediction")]
        assert vp > 0.5, f"vacuum_prediction too low: {vp:.4f}"

    def test_bp_converges_on_fine_graph(self):
        g, sp = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("galileo", "heavier_falls_faster"): 0.7,
                _qid("galileo", "thought_experiment_env"): 0.99,
                _qid("galileo", "medium_density_observation"): 0.95,
                _qid("galileo", "inclined_plane_observation"): 0.95,
                _qid("galileo", "vacuum_env"): 0.99,
            },
            strategy_conditional_params=sp,
        )
        bp = BeliefPropagation(damping=0.5, max_iterations=100)
        result = bp.run(fg)
        assert result.diagnostics.converged


# ============================================================================
# Newton — Principia derivation chain
# ============================================================================


class TestNewtonCoarse:
    """Coarse graph: deduction chain to freefall_acceleration."""

    def _build(self):
        kepler = _claim("newton", "kepler_third_law", "开普勒第三定律")
        second_law = _claim("newton", "second_law", "牛顿第二定律")
        third_law = _claim("newton", "third_law", "牛顿第三定律")
        pendulum = _claim("newton", "pendulum_experiment", "摆锤实验")
        near_earth = _claim("newton", "near_earth_surface", "近地表面条件")

        inverse_sq = _claim("newton", "inverse_square_force", "反平方力")
        gravity_law = _claim("newton", "law_of_gravity", "万有引力定律")
        mass_eq = _claim("newton", "mass_equivalence", "质量等价")
        freefall = _claim("newton", "freefall_acceleration", "自由落体加速度")

        # deduction: kepler + second_law → inverse_square
        s1 = Strategy(
            scope="local",
            type="deduction",
            premises=[kepler.id, second_law.id],
            conclusion=inverse_sq.id,
        )
        # deduction: inverse_square + third_law → law_of_gravity
        s2 = Strategy(
            scope="local",
            type="deduction",
            premises=[inverse_sq.id, third_law.id],
            conclusion=gravity_law.id,
        )
        # deduction: pendulum + second_law + gravity_law → mass_equivalence
        s3 = Strategy(
            scope="local",
            type="deduction",
            premises=[pendulum.id, second_law.id, gravity_law.id],
            conclusion=mass_eq.id,
        )
        # deduction: second_law + gravity_law + mass_eq + near_earth → freefall
        s4 = Strategy(
            scope="local",
            type="deduction",
            premises=[second_law.id, gravity_law.id, mass_eq.id, near_earth.id],
            conclusion=freefall.id,
        )

        return _lg(
            "newton",
            knowledges=[
                kepler,
                second_law,
                third_law,
                pendulum,
                near_earth,
                inverse_sq,
                gravity_law,
                mass_eq,
                freefall,
            ],
            strategies=[s1, s2, s3, s4],
        )

    def test_deduction_chain_propagates(self):
        g = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("newton", "kepler_third_law"): 0.95,
                _qid("newton", "second_law"): 0.99,
                _qid("newton", "third_law"): 0.99,
                _qid("newton", "pendulum_experiment"): 0.95,
                _qid("newton", "near_earth_surface"): 0.99,
            },
        )
        assert not fg.validate()
        beliefs, _ = exact_inference(fg)
        ff = beliefs[_qid("newton", "freefall_acceleration")]
        assert ff > 0.7, f"freefall belief too low: {ff:.4f}"
        # Each deduction step with high-prior premises should produce high belief
        isq = beliefs[_qid("newton", "inverse_square_force")]
        assert isq > 0.7, f"inverse_square belief: {isq:.4f}"

    def test_weakening_premise_cascades(self):
        """Lower Kepler's prior → inverse_square drops → downstream drops."""
        g = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("newton", "kepler_third_law"): 0.3,
                _qid("newton", "second_law"): 0.99,
                _qid("newton", "third_law"): 0.99,
                _qid("newton", "pendulum_experiment"): 0.95,
                _qid("newton", "near_earth_surface"): 0.99,
            },
        )
        beliefs, _ = exact_inference(fg)
        isq = beliefs[_qid("newton", "inverse_square_force")]
        assert isq < 0.6, f"inverse_square should be lower with weak Kepler: {isq:.4f}"


# ============================================================================
# Einstein — GR light deflection + contradiction with Soldner
# ============================================================================


class TestEinsteinContradiction:
    """Einstein graph: GR vs Soldner contradiction on light deflection."""

    def _build(self):
        equiv_principle = _claim("einstein", "light_bends_in_gravity", "光在引力场中弯曲")
        field_eqs = _claim("einstein", "einstein_field_equations", "爱因斯坦场方程")
        gr_deflect = _claim("einstein", "gr_light_deflection", "GR预测1.75角秒")
        soldner = _claim("einstein", "soldner_deflection", "牛顿微粒说预测0.87角秒")
        contra_h = _claim("einstein", "deflection_contradiction_h", "矛盾helper")
        mercury_obs = _claim("einstein", "mercury_perihelion", "水星进动观测")
        mercury_gr = _claim("einstein", "gr_mercury_precession", "GR解释水星进动")

        # GR deflection from equivalence_principle + field_equations
        s1 = Strategy(
            scope="local",
            type="deduction",
            premises=[equiv_principle.id, field_eqs.id],
            conclusion=gr_deflect.id,
        )
        contra_op = Operator(
            operator_id="lco_001",
            scope="local",
            operator="contradiction",
            variables=[gr_deflect.id, soldner.id],
            conclusion=contra_h.id,
        )
        # Mercury precession from field_equations + observation
        s2 = Strategy(
            scope="local",
            type="deduction",
            premises=[field_eqs.id, mercury_obs.id],
            conclusion=mercury_gr.id,
        )

        return _lg(
            "einstein",
            knowledges=[
                equiv_principle,
                field_eqs,
                gr_deflect,
                soldner,
                contra_h,
                mercury_obs,
                mercury_gr,
            ],
            operators=[contra_op],
            strategies=[s1, s2],
        )

    def test_contradiction_suppresses_soldner(self):
        g = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("einstein", "light_bends_in_gravity"): 0.9,
                _qid("einstein", "einstein_field_equations"): 0.95,
                _qid("einstein", "soldner_deflection"): 0.6,
                _qid("einstein", "mercury_perihelion"): 0.98,
            },
        )
        assert not fg.validate()
        beliefs, _ = exact_inference(fg)
        gr = beliefs[_qid("einstein", "gr_light_deflection")]
        sol = beliefs[_qid("einstein", "soldner_deflection")]
        # GR supported by deduction; Soldner suppressed by contradiction
        assert gr > sol, f"GR ({gr:.4f}) should dominate Soldner ({sol:.4f})"

    def test_mercury_independent_support(self):
        """Mercury precession deduction: high field_eqs prior → high mercury_gr belief."""
        g = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("einstein", "light_bends_in_gravity"): 0.9,
                _qid("einstein", "einstein_field_equations"): 0.95,
                _qid("einstein", "soldner_deflection"): 0.5,
                _qid("einstein", "mercury_perihelion"): 0.98,
            },
        )
        beliefs, _ = exact_inference(fg)
        mgr = beliefs[_qid("einstein", "gr_mercury_precession")]
        assert mgr > 0.7, f"mercury GR belief should be high: {mgr:.4f}"

    def test_bp_converges(self):
        g = self._build()
        fg = lower_local_graph(
            g,
            node_priors={
                _qid("einstein", "light_bends_in_gravity"): 0.9,
                _qid("einstein", "einstein_field_equations"): 0.95,
                _qid("einstein", "soldner_deflection"): 0.6,
                _qid("einstein", "mercury_perihelion"): 0.98,
            },
        )
        bp = BeliefPropagation(damping=0.5, max_iterations=100)
        result = bp.run(fg)
        assert result.diagnostics.converged
