"""Review sidecar report I/O and merger."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from libs.lang.models import ChainExpr, Package, StepApply


def write_review(review: dict, reviews_dir: Path, filename: str | None = None) -> Path:
    """Write review sidecar YAML to reviews_dir."""
    reviews_dir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        ts = review.get("timestamp", "unknown")
        safe_ts = ts.replace(":", "-").replace("T", "_").split(".")[0]
        filename = f"review_{safe_ts}.yaml"
    out_path = reviews_dir / filename
    out_path.write_text(yaml.dump(review, allow_unicode=True, sort_keys=False))
    return out_path


def read_review(path: Path) -> dict:
    """Read a review sidecar YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Review file not found: {path}")
    return yaml.safe_load(path.read_text())


def find_latest_review(reviews_dir: Path) -> Path:
    """Find the most recent review file in reviews_dir (by filename sort)."""
    if not reviews_dir.exists():
        raise FileNotFoundError(f"No reviews directory: {reviews_dir}")
    yamls = sorted(reviews_dir.glob("review_*.yaml"))
    if not yamls:
        raise FileNotFoundError(f"No review files in {reviews_dir}")
    return yamls[-1]


def merge_review(pkg: Package, review: dict, source_fingerprint: str | None = None) -> Package:
    """Merge review suggestions into package (deep copy -- original untouched).

    Updates step priors and arg dependency types based on review.
    """
    import warnings

    review_fp = review.get("source_fingerprint")
    if source_fingerprint and review_fp and source_fingerprint != review_fp:
        warnings.warn(
            f"Review fingerprint mismatch: review was produced against {review_fp}, "
            f"but current source is {source_fingerprint}. Results may be stale.",
            stacklevel=2,
        )

    merged = copy.deepcopy(pkg)

    chains_by_name: dict[str, ChainExpr] = {}
    for mod in merged.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, ChainExpr):
                chains_by_name[decl.name] = decl

    for chain_review in review.get("chains", []):
        chain = chains_by_name.get(chain_review["chain"])
        if not chain:
            continue
        for step_review in chain_review.get("steps", []):
            step_num = step_review["step"]
            step = next((s for s in chain.steps if s.step == step_num), None)
            if not step:
                continue
            if "suggested_prior" in step_review and hasattr(step, "prior"):
                step.prior = step_review["suggested_prior"]
            if "dependencies" in step_review and isinstance(step, StepApply):
                for dep_review in step_review["dependencies"]:
                    arg = next((a for a in step.args if a.ref == dep_review["ref"]), None)
                    if arg and "suggested" in dep_review:
                        arg.dependency = dep_review["suggested"]

    return merged
