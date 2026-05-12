"""Deprecated Bayes predict() alias."""

from __future__ import annotations

import warnings
from typing import Any

from gaia.lang.bayes.distributions.protocol import Distribution
from gaia.lang.bayes.verbs.model import model as _model
from gaia.lang.runtime import Claim, Knowledge, Variable


def predict(
    hypothesis: Claim,
    observable: Variable,
    *,
    distribution: Distribution,
    background: list[Knowledge] | None = None,
    rationale: str = "",
    label: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> Claim:
    """Create a Bayes predictive model through the deprecated alias."""
    warnings.warn(
        "bayes.predict(...) is deprecated; use bayes.model(...) for Bayes predictive models. "
        "from gaia.lang import predict now refers to the core Bayes-free prediction verb.",
        DeprecationWarning,
        stacklevel=2,
    )
    return _model(
        hypothesis,
        observable=observable,
        distribution=distribution,
        background=background,
        rationale=rationale,
        label=label,
        metadata=metadata,
    )
