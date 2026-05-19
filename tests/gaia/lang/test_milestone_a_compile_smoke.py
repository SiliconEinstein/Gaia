"""Milestone A compile smoke — packages declaring Variables/Domains compile cleanly.

Codex review blocker #1: Variable/Domain are Lang-only and must not enter the
IR-bound knowledge map. This test declares both inside a CollectedPackage,
runs compile_package_artifact, and asserts the resulting IR contains a Claim
but no `variable` or `domain` typed entries.
"""

from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.dsl.knowledge import claim
from gaia.engine.lang.formula.primitives import Nat
from gaia.engine.lang.runtime.domain import Domain
from gaia.engine.lang.runtime.knowledge import Claim, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage
from gaia.engine.lang.runtime.variable import Variable


def test_package_with_variables_and_domains_compiles_cleanly():
    pkg = CollectedPackage(name="t_smoke", namespace="t")
    token = _current_package.set(pkg)
    try:
        # Lang-only declarations.
        Particle = Domain(content="Particles", members=["p1", "p2"])  # noqa: F841
        n = Variable(symbol="n", domain=Nat, value=395)  # noqa: F841

        # An IR-bound Claim — this MUST appear in compiled output.
        Claim(content="A regular claim.", prior=0.5, label="C1")
    finally:
        _current_package.reset(token)

    artifact = compile_package_artifact(pkg)

    # CompiledPackage exposes the IR via .graph.knowledges (LocalCanonicalGraph).
    knowledges = artifact.graph.knowledges
    types = {str(k.type) for k in knowledges}

    assert "variable" not in types, (
        f"variable leaked into IR knowledge — Lang-only registration failed. "
        f"Types in IR: {sorted(types)}"
    )
    assert "domain" not in types, (
        f"domain leaked into IR knowledge — Lang-only registration failed. "
        f"Types in IR: {sorted(types)}"
    )
    assert any(str(k.type) == "claim" for k in knowledges), "no claim found in compiled artifact"


def _compile_claim_metadata(make_claim):
    """Compile a single-claim package and return the IR metadata of that claim.

    Runs the same prior-resolution step as ``apply_package_priors`` (in CLI
    flows) so DSL-level inline priors and explicit ``register_prior`` calls
    both surface as ``metadata['prior']`` in the IR.
    """
    from gaia.engine.ir import default_resolution_policy
    from gaia.engine.lang.dsl.register_prior import resolve_priors_to_metadata

    pkg = CollectedPackage(name="t_prior_smoke", namespace="t")
    token = _current_package.set(pkg)
    try:
        make_claim()
    finally:
        _current_package.reset(token)

    resolve_priors_to_metadata(pkg.knowledge, default_resolution_policy())
    artifact = compile_package_artifact(pkg)
    claims = [k for k in artifact.graph.knowledges if str(k.type) == "claim"]
    assert len(claims) == 1
    return claims[0].metadata or {}


def test_dsl_claim_inline_prior_compiles_to_ir_metadata():
    """claim(prior=X) routes through register_prior(claim_inline).

    Resolution at compile time writes the resulting value to
    metadata['prior'] for downstream BP / render / brief consumers.
    """
    metadata = _compile_claim_metadata(lambda: claim("A prior-bearing claim.", prior=0.85))
    assert metadata["prior"] == 0.85
    records = metadata.get("prior_records") or []
    assert len(records) == 1
    assert records[0]["source_id"] == "claim_inline"
    assert records[0]["value"] == 0.85


def test_runtime_claim_prior_compiles_to_ir_metadata():
    metadata = _compile_claim_metadata(lambda: Claim("A prior-bearing claim.", prior=0.85))
    assert metadata["prior"] == 0.85


def test_existing_metadata_prior_overrides_runtime_claim_prior():
    metadata = _compile_claim_metadata(
        lambda: Claim("A prior-bearing claim.", prior=0.2, metadata={"prior": 0.85})
    )
    assert metadata["prior"] == 0.85
