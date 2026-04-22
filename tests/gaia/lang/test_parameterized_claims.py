from enum import Enum

from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.param import Param, UNBOUND


class MoleculeType(str, Enum):
    DNA = "DNA"
    RNA = "RNA"
    PROTEIN = "protein"


class CavityTemperature(Claim):
    """Cavity temperature is set to {value}K."""

    value: float


class InfoTransfer(Claim):
    """Information can transfer from {src} to {dst}."""

    src: MoleculeType
    dst: MoleculeType


class ABCounts(Claim):
    """[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions."""

    experiment: Setting
    ctrl_n: int
    ctrl_k: int


def test_param_unbound_sentinel():
    p = Param(name="value", type=float)
    assert p.value is UNBOUND
    assert p.value is not None


def test_param_bound():
    p = Param(name="value", type=float, value=5000.0)
    assert p.value == 5000.0


def test_parameterized_claim_content_rendering():
    temp = CavityTemperature(value=5000.0)
    assert temp.content == "Cavity temperature is set to 5000.0K."


def test_parameterized_claim_parameters():
    temp = CavityTemperature(value=5000.0)
    assert len(temp.parameters) == 1
    assert temp.parameters[0]["name"] == "value"
    assert temp.parameters[0]["value"] == 5000.0


def test_parameterized_claim_enum():
    transfer = InfoTransfer(src=MoleculeType.DNA, dst=MoleculeType.RNA)
    assert transfer.content == "Information can transfer from DNA to RNA."


def test_partial_binding():
    transfer = InfoTransfer(src=MoleculeType.DNA)
    assert "{dst}" in transfer.content
    assert "DNA" in transfer.content


def test_knowledge_parameter_ref_syntax():
    """Knowledge-typed params render as [@label]."""
    exp = Setting("AB test exp_123.")
    exp.label = "exp_123"
    counts = ABCounts(experiment=exp, ctrl_n=10_000, ctrl_k=500)
    assert "[@exp_123]" in counts.content
    assert "500/10000" in counts.content


def test_knowledge_parameter_stored_as_reference():
    """Knowledge param value is the object, not a string."""
    exp = Setting("AB test.")
    exp.label = "exp_123"
    counts = ABCounts(experiment=exp, ctrl_n=10_000, ctrl_k=500)
    param = [p for p in counts.parameters if p["name"] == "experiment"][0]
    assert param["value"] is exp
