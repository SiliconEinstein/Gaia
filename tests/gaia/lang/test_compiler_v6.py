from gaia.lang.compiler.compile import compile_package_artifact
from gaia.lang.runtime.grounding import Grounding
from gaia.lang.runtime.knowledge import Claim, Context, Note
from gaia.lang.runtime.package import CollectedPackage


def test_compile_note_type_and_format():
    """Note Knowledge compiles with type='note' and first-class format."""
    with CollectedPackage("v6_test") as pkg:
        note = Note("Raw experiment notes.", format="text")
        note.label = "ctx"
    ir = compile_package_artifact(pkg).to_json()
    node = next(k for k in ir["knowledges"] if k["label"] == "ctx")
    assert node["type"] == "note"
    assert node["format"] == "text"


def test_compile_legacy_context_as_note():
    with CollectedPackage("v6_test") as pkg:
        ctx = Context("Raw experiment notes.")
        ctx.label = "ctx"
    ir = compile_package_artifact(pkg).to_json()
    node = next(k for k in ir["knowledges"] if k["label"] == "ctx")
    assert node["type"] == "note"
    assert node["format"] == "markdown"
    assert node["metadata"]["legacy_kind"] == "context"


def test_compile_grounding_in_metadata():
    """Grounding metadata appears in compiled IR."""
    with CollectedPackage("v6_test") as pkg:
        claim = Claim(
            "Measured spectrum deviates from Rayleigh-Jeans law.",
            grounding=Grounding(kind="source_fact", rationale="Extracted from Fig.2."),
        )
        claim.label = "uv_data"
    ir = compile_package_artifact(pkg).to_json()
    node = next(k for k in ir["knowledges"] if k["label"] == "uv_data")
    assert node["metadata"]["grounding"]["kind"] == "source_fact"
    assert "Fig.2" in node["metadata"]["grounding"]["rationale"]


def test_compile_parameterized_claim_template():
    """Parameterized Claim stores content_template in metadata."""

    class TemperatureClaim(Claim):
        """Cavity temperature is set to {value}K."""

        value: float

    with CollectedPackage("v6_test") as pkg:
        temp = TemperatureClaim(value=5000.0)
        temp.label = "temp"
    ir = compile_package_artifact(pkg).to_json()
    node = next(k for k in ir["knowledges"] if k["label"] == "temp")
    assert node["content"] == "Cavity temperature is set to 5000.0K."
    assert node["metadata"]["content_template"] == "Cavity temperature is set to {value}K."


def test_compile_parameter_value():
    """Bound parameter values appear in compiled IR parameters."""

    class ABCounts(Claim):
        """[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions."""

        experiment: Note
        ctrl_n: int
        ctrl_k: int

    with CollectedPackage("v6_test") as pkg:
        exp = Note("AB test exp_123.")
        exp.label = "exp_123"
        counts = ABCounts(experiment=exp, ctrl_n=10_000, ctrl_k=500)
        counts.label = "counts"
    ir = compile_package_artifact(pkg).to_json()
    node = next(k for k in ir["knowledges"] if k["label"] == "counts")
    params = {p["name"]: p for p in node["parameters"]}
    assert params["ctrl_n"]["value"] == 10_000
    assert params["ctrl_k"]["value"] == 500
    assert params["experiment"]["value"] == "github:v6_test::exp_123"
