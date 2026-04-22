from gaia.bp import lower_local_graph
from gaia.ir import ReviewManifest, ReviewStatus
from gaia.lang import Claim, derive, equal
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.review.manifest import generate_review_manifest
from gaia.lang.runtime.package import CollectedPackage


def _accepted_manifest(manifest: ReviewManifest) -> ReviewManifest:
    return ReviewManifest(
        reviews=[
            review.model_copy(update={"status": ReviewStatus.ACCEPTED})
            for review in manifest.reviews
        ]
    )


def test_unreviewed_strategy_excluded_from_bp():
    with CollectedPackage("review_bp") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = derive("B.", given=a, rationale="A implies B.", label="derive_b")
        b.label = "b"

    compiled = compile_package_artifact(pkg)
    manifest = generate_review_manifest(compiled)
    factor_graph = lower_local_graph(compiled.graph, review_manifest=manifest)
    assert not factor_graph.factors


def test_accepted_strategy_included_in_bp():
    with CollectedPackage("review_bp") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = derive("B.", given=a, rationale="A implies B.", label="derive_b")
        b.label = "b"

    compiled = compile_package_artifact(pkg)
    manifest = _accepted_manifest(generate_review_manifest(compiled))
    factor_graph = lower_local_graph(compiled.graph, review_manifest=manifest)
    assert factor_graph.factors


def test_unreviewed_operator_excluded_from_bp():
    with CollectedPackage("review_bp") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        helper = equal(a, b, rationale="Same.", label="same")
        helper.label = "same_helper"

    compiled = compile_package_artifact(pkg)
    manifest = generate_review_manifest(compiled)
    factor_graph = lower_local_graph(compiled.graph, review_manifest=manifest)
    assert not factor_graph.factors
    assert factor_graph.variables["github:review_bp::same_helper"] == 0.5


def test_accepted_review_does_not_set_priors():
    with CollectedPackage("review_bp") as pkg:
        a = Claim("A.")
        a.label = "a"
        b = Claim("B.")
        b.label = "b"
        helper = equal(a, b, rationale="Same.", label="same")
        helper.label = "same_helper"

    compiled = compile_package_artifact(pkg)
    manifest = _accepted_manifest(generate_review_manifest(compiled))
    factor_graph = lower_local_graph(compiled.graph, review_manifest=manifest)
    assert factor_graph.variables["github:review_bp::same_helper"] == 1.0 - 1e-3
