import json

from gaia.cli.commands._review_manifest import load_or_generate_review_manifest
from gaia.ir import ReviewManifest, ReviewStatus
from gaia.lang import Claim, derive
from gaia.lang.compiler import compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage


def _compiled_with_reviewable_action():
    with CollectedPackage("review_io") as pkg:
        a = Claim("A.")
        a.label = "a"
        c = derive("C.", given=a, rationale="A implies C.", label="derive_c")
        c.label = "c"
    return compile_package_artifact(pkg)


def test_load_or_generate_review_manifest_uses_generated_default(tmp_path):
    compiled = _compiled_with_reviewable_action()

    manifest = load_or_generate_review_manifest(tmp_path, compiled)

    assert isinstance(manifest, ReviewManifest)
    assert len(manifest.reviews) == 1
    assert manifest.reviews[0].status == ReviewStatus.UNREVIEWED


def test_load_or_generate_review_manifest_merges_persisted_latest_status(tmp_path):
    compiled = _compiled_with_reviewable_action()
    generated = compiled.review
    assert generated is not None
    accepted_review = generated.reviews[0].model_copy(
        update={"status": ReviewStatus.ACCEPTED, "round": 2}
    )
    review_path = tmp_path / ".gaia" / "review_manifest.json"
    review_path.parent.mkdir()
    review_path.write_text(
        json.dumps(
            ReviewManifest(reviews=[accepted_review]).model_dump(mode="json"),
            indent=2,
        )
    )

    manifest = load_or_generate_review_manifest(tmp_path, compiled)

    assert manifest.latest_status(accepted_review.target_id) == ReviewStatus.ACCEPTED
