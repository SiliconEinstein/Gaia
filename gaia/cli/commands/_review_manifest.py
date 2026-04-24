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
    target ids. When a target id changes but the stable action label, target kind,
    and audit question are unchanged, persisted rounds are reattached to the new
    target id so accepted reviews are not silently dropped by hash churn.
    """

    generated_target_ids = {review.target_id for review in generated.reviews}
    generated_by_stable_key: dict[tuple[str, str, str], Review] = {}
    duplicate_stable_keys: set[tuple[str, str, str]] = set()
    for review in generated.reviews:
        key = (review.action_label, review.target_kind, review.audit_question)
        if key in generated_by_stable_key:
            duplicate_stable_keys.add(key)
        else:
            generated_by_stable_key[key] = review

    reviews = list(generated.reviews)
    for review in persisted.reviews:
        if review.target_id in generated_target_ids:
            reviews.append(review)
            continue

        key = (review.action_label, review.target_kind, review.audit_question)
        generated_review = generated_by_stable_key.get(key)
        if generated_review is None or key in duplicate_stable_keys:
            continue
        reviews.append(
            review.model_copy(
                update={
                    "review_id": generated_review.review_id,
                    "target_id": generated_review.target_id,
                }
            )
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
