"""Shared ReviewManifest loading helpers for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from gaia.cli._packages import GaiaCliError
from gaia.ir import Review, ReviewManifest
from gaia.lang.review.manifest import generate_review_manifest

REVIEW_MANIFEST_REL_PATH = Path(".gaia") / "review_manifest.json"


def _generated_manifest(compiled) -> ReviewManifest:
    return getattr(compiled, "review", None) or generate_review_manifest(compiled)


def merge_review_manifests(
    generated: ReviewManifest,
    persisted: ReviewManifest,
) -> ReviewManifest:
    """Merge persisted review rounds onto the generated target list.

    Generated entries ensure newly compiled v6 action targets still appear as
    unreviewed. Persisted entries preserve manual reviewer decisions for matching
    target ids. Stale persisted targets are ignored because they no longer map to
    the compiled package.
    """

    generated_target_ids = {review.target_id for review in generated.reviews}
    reviews = list(generated.reviews)
    reviews.extend(
        review for review in persisted.reviews if review.target_id in generated_target_ids
    )
    return ReviewManifest(reviews=reviews)


def latest_reviews(manifest: ReviewManifest) -> list[Review]:
    latest: dict[str, Review] = {}
    for review in manifest.reviews:
        current = latest.get(review.target_id)
        if current is None or review.round > current.round:
            latest[review.target_id] = review
    return sorted(latest.values(), key=lambda review: review.action_label)


def load_or_generate_review_manifest(pkg_path: str | Path, compiled) -> ReviewManifest:
    generated = _generated_manifest(compiled)
    path = Path(pkg_path) / REVIEW_MANIFEST_REL_PATH
    if not path.exists():
        return generated

    try:
        data = json.loads(path.read_text())
        persisted = ReviewManifest.model_validate(data)
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        raise GaiaCliError(f"Error: {path} is not a valid ReviewManifest: {exc}") from exc
    return merge_review_manifests(generated, persisted)
