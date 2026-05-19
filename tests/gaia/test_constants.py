from gaia import constants
from gaia.unit import Quantity, to_literal


def test_speed_of_light_aliases_same_quantity():
    assert constants.c is constants.speed_of_light
    assert isinstance(constants.c, Quantity)
    assert constants.c.to("m/s").magnitude == 299792458


def test_core_constants_are_quantities():
    names = [
        "h",
        "hbar",
        "k_B",
        "e",
        "G",
        "g_0",
        "N_A",
        "R",
        "sigma_SB",
        "eps_0",
        "mu_0",
        "m_e",
        "m_p",
        "m_n",
    ]

    for name in names:
        assert isinstance(getattr(constants, name), Quantity)


def test_constant_crosses_to_ir_literal():
    literal = to_literal(constants.c)

    assert literal.unit == "meter / second"
    assert literal.value == 299792458.0
