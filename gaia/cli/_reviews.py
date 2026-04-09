"""Shared review sidecar loading utilities for Gaia CLI commands."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from gaia.cli._packages import GaiaCliError, LoadedGaiaPackage, _import_fresh
from gaia.ir import ParameterizationSource, PriorRecord, ResolutionPolicy, StrategyParamRecord
from gaia.review import ClaimReview, GeneratedClaimReview, ReviewBundle, StrategyReview


@dataclass
class LoadedGaiaReview:
    name: str
    module_name: str
    module_path: Path
    bundle: ReviewBundle


@dataclass
class ResolvedGaiaReview:
    source: ParameterizationSource
    resolution_policy: ResolutionPolicy
    objects: list[dict[str, Any]]
    priors: list[PriorRecord]
    strategy_params: list[StrategyParamRecord]

    def content_hash(self) -> str:
        """Canonical hash of the resolved review's inference-relevant content.

        Includes only the fields that affect BP outputs: (knowledge_id, prior_value)
        for priors, (strategy_id, conditional_probabilities) for strategy params.
        Deliberately excludes source_id, policy metadata, judgments, justifications,
        and timestamps — those are bookkeeping that should not invalidate a render.

        Used by `gaia infer` to stamp `beliefs.json` with a content hash, and by
        `gaia render` to detect when a review sidecar has been edited between
        infer and render (the IR hash alone cannot catch this because review
        priors/params are not part of the IR).
        """
        payload = {
            "priors": sorted(
                [
                    {"knowledge_id": record.knowledge_id, "value": record.value}
                    for record in self.priors
                ],
                key=lambda item: item["knowledge_id"],
            ),
            "strategy_params": sorted(
                [
                    {
                        "strategy_id": record.strategy_id,
                        "conditional_probabilities": list(record.conditional_probabilities),
                    }
                    for record in self.strategy_params
                ],
                key=lambda item: item["strategy_id"],
            ),
        }
        canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def to_json(self, *, ir_hash: str, gaia_lang_version: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ir_hash": ir_hash,
            "review_content_hash": self.content_hash(),
            "source": self.source.model_dump(mode="json", exclude_none=True),
            "resolution_policy": self.resolution_policy.model_dump(
                mode="json",
                exclude_none=True,
            ),
            "objects": self.objects,
            "priors": [record.model_dump(mode="json", exclude_none=True) for record in self.priors],
            "strategy_params": [
                record.model_dump(mode="json", exclude_none=True) for record in self.strategy_params
            ],
        }
        if gaia_lang_version is not None:
            payload["gaia_lang_version"] = gaia_lang_version
        return payload


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _discover_review_candidates(loaded: LoadedGaiaPackage) -> dict[str, tuple[str, Path]]:
    package_dir = loaded.source_root / loaded.import_name
    candidates: dict[str, tuple[str, Path]] = {}

    legacy_path = package_dir / "review.py"
    if legacy_path.exists():
        candidates["review"] = (f"{loaded.import_name}.review", legacy_path)

    reviews_dir = package_dir / "reviews"
    if reviews_dir.exists():
        for path in sorted(reviews_dir.glob("*.py")):
            if path.name == "__init__.py":
                continue
            review_name = path.stem
            if review_name in candidates:
                raise GaiaCliError(
                    f"Error: duplicate review name {review_name!r} in package review sidecars."
                )
            candidates[review_name] = (f"{loaded.import_name}.reviews.{review_name}", path)

    return candidates


def _load_review_candidate(
    *,
    review_name: str,
    module_name: str,
    module_path: Path,
) -> LoadedGaiaReview:
    try:
        module = _import_fresh(module_name)
    except ModuleNotFoundError as exc:
        if exc.name == module_name:
            return None
        raise GaiaCliError(f"Error importing review sidecar: {exc}") from exc
    except Exception as exc:
        raise GaiaCliError(f"Error importing review sidecar: {exc}") from exc

    bundle = getattr(module, "REVIEW", None)
    if not isinstance(bundle, ReviewBundle):
        raise GaiaCliError(f"Error: {module_path.name} must export REVIEW = ReviewBundle(...).")
    return LoadedGaiaReview(
        name=review_name,
        module_name=module_name,
        module_path=module_path,
        bundle=bundle,
    )


def load_gaia_review(
    loaded: LoadedGaiaPackage,
    *,
    review_name: str | None = None,
) -> LoadedGaiaReview | None:
    """Load a package review sidecar.

    Supports:
    - legacy `<package>/review.py`
    - multi-review `<package>/reviews/<name>.py`
    """
    candidates = _discover_review_candidates(loaded)
    if not candidates:
        return None

    if review_name is None:
        if len(candidates) == 1:
            review_name = next(iter(candidates))
        else:
            available = ", ".join(sorted(candidates))
            raise GaiaCliError(
                "Error: multiple review sidecars found; choose one with "
                f"`--review <name>`. Available: {available}"
            )
    elif review_name not in candidates:
        available = ", ".join(sorted(candidates))
        raise GaiaCliError(f"Error: unknown review sidecar {review_name!r}. Available: {available}")

    module_name, module_path = candidates[review_name]
    loaded_review = _load_review_candidate(
        review_name=review_name,
        module_name=module_name,
        module_path=module_path,
    )
    if loaded_review is None:
        return None
    return loaded_review


def resolve_gaia_review(loaded_review, compiled) -> ResolvedGaiaReview:
    """Resolve runtime review objects to IR parameterization records."""
    source = ParameterizationSource(
        source_id=loaded_review.bundle.source_id,
        model=loaded_review.bundle.model or "agent-authored",
        policy=loaded_review.bundle.policy,
        config=loaded_review.bundle.config,
        created_at=_utc_now(),
    )
    resolution_policy = ResolutionPolicy(strategy="source", source_id=source.source_id)

    priors: list[PriorRecord] = []
    strategy_params: list[StrategyParamRecord] = []
    objects: list[dict[str, Any]] = []

    for review in loaded_review.bundle.objects:
        if isinstance(review, ClaimReview):
            knowledge_id = compiled.knowledge_ids_by_object.get(id(review.subject))
            if knowledge_id is None:
                raise GaiaCliError(
                    "Error: review_claim() references a Knowledge outside this package."
                )
            if review.prior is not None:
                priors.append(
                    PriorRecord(
                        knowledge_id=knowledge_id,
                        value=review.prior,
                        source_id=source.source_id,
                    )
                )
            objects.append(
                {
                    "kind": "claim",
                    "knowledge_id": knowledge_id,
                    "label": review.subject.label,
                    "judgment": review.judgment,
                    "justification": review.justification,
                    "prior": review.prior,
                    "metadata": review.metadata or None,
                }
            )
            continue

        if isinstance(review, GeneratedClaimReview):
            strategy = compiled.strategies_by_object.get(id(review.subject))
            if strategy is None:
                raise GaiaCliError(
                    "Error: review_generated_claim() references a Strategy outside this package."
                )
            interface_roles = (strategy.metadata or {}).get("interface_roles", {})
            if not isinstance(interface_roles, dict):
                raise GaiaCliError(
                    f"Error: strategy '{strategy.strategy_id}' does not expose interface roles."
                )
            targets = interface_roles.get(review.role)
            if not isinstance(targets, list) or review.occurrence >= len(targets):
                raise GaiaCliError(
                    f"Error: strategy '{strategy.strategy_id}' has no interface role "
                    f"{review.role!r} at occurrence {review.occurrence}."
                )
            knowledge_id = targets[review.occurrence]
            if review.prior is not None:
                priors.append(
                    PriorRecord(
                        knowledge_id=knowledge_id,
                        value=review.prior,
                        source_id=source.source_id,
                    )
                )
            objects.append(
                {
                    "kind": "generated_claim",
                    "strategy_id": strategy.strategy_id,
                    "strategy_label": review.subject.label,
                    "knowledge_id": knowledge_id,
                    "role": review.role,
                    "occurrence": review.occurrence,
                    "judgment": review.judgment,
                    "justification": review.justification,
                    "prior": review.prior,
                    "metadata": review.metadata or None,
                }
            )
            continue

        if isinstance(review, StrategyReview):
            strategy = compiled.strategies_by_object.get(id(review.subject))
            if strategy is None:
                raise GaiaCliError(
                    "Error: review_strategy() references a Strategy outside this package."
                )

            conditional_probabilities: list[float] | None = None
            strategy_type = str(strategy.type)
            if (
                review.conditional_probability is not None
                or review.conditional_probabilities is not None
            ):
                if strategy_type == "noisy_and":
                    conditional_probabilities = (
                        list(review.conditional_probabilities)
                        if review.conditional_probabilities is not None
                        else [review.conditional_probability]
                    )
                elif strategy_type == "infer":
                    if review.conditional_probabilities is None:
                        raise GaiaCliError(
                            "Error: infer strategies require "
                            "review_strategy(..., conditional_probabilities=[...])."
                        )
                    conditional_probabilities = list(review.conditional_probabilities)
                else:
                    raise GaiaCliError(
                        f"Error: strategy '{strategy.strategy_id}' has type '{strategy_type}' and "
                        "does not accept conditional probabilities."
                    )

            if conditional_probabilities is not None:
                strategy_params.append(
                    StrategyParamRecord(
                        strategy_id=strategy.strategy_id,
                        conditional_probabilities=conditional_probabilities,
                        source_id=source.source_id,
                    )
                )

            objects.append(
                {
                    "kind": "strategy",
                    "strategy_id": strategy.strategy_id,
                    "label": review.subject.label,
                    "type": strategy_type,
                    "judgment": review.judgment,
                    "justification": review.justification,
                    "conditional_probabilities": conditional_probabilities,
                    "metadata": review.metadata or None,
                }
            )
            continue

        raise GaiaCliError(f"Error: unsupported review object type {type(review)!r}.")

    return ResolvedGaiaReview(
        source=source,
        resolution_policy=resolution_policy,
        objects=objects,
        priors=priors,
        strategy_params=strategy_params,
    )
