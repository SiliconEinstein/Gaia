"""Parameterization — claim prior records for Gaia IR graphs.

Implements docs/foundations/gaia-ir/06-parameterization.md.

Multi-source PriorRecord is the canonical representation: each Claim may have
multiple PriorRecords from different sources (``user_priors`` for the author,
``continuous_inference`` for engine-derived values, ``reviewer_*`` for human
reviewer overrides, etc.). At compile time, ``ResolutionPolicy.resolve()``
picks the winning record per claim — the winning value is written into
``Knowledge.metadata["prior"]`` for downstream BP / render / brief consumers,
while every record (winner and losers) remains in ``metadata["prior_records"]``
for audit, ``gaia check --hole`` display, and the ``prior_dissent`` /
``prior_overridden`` diagnostics.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, model_validator

CROMWELL_EPS: float = 1e-3
"""Cromwell's rule epsilon — all probabilities clamped to [EPS, 1-EPS]."""


def _clamp(value: float) -> float:
    return max(CROMWELL_EPS, min(1 - CROMWELL_EPS, value))


DEFAULT_PRIORITY_ORDER: tuple[str, ...] = (
    "calibration_*",  # Historical calibration outputs (future feature)
    "user_priors",  # Explicit register_prior() with default source
    "reviewer_*",  # Human reviewer overrides
    "continuous_inference",  # #581 continuous parameter inference engine
    "evidence_factor_*",  # #560 EvidenceFactor-derived priors
    "agent_*",  # LLM agent automated suggestions
    "claim_inline",  # claim(prior=X) shortcut — lowest deliberate tier
    "*",  # Catch-all (latest record wins for unmatched sources)
)
"""Default priority order for the ``explicit_priority`` resolution strategy.

The ranking embodies two principles:

1. **Explicit deliberation outranks shortcuts.** Any prior set via an explicit
   ``register_prior()`` call (``"user_priors"`` and beyond) wins over a
   ``claim(prior=X)`` inline shortcut, which sits at the second-to-last tier.
   The inline form is convenient for first-pass guesses but its justification
   is an auto-generated placeholder, so a properly documented ``register_prior``
   call should always be able to override it.
2. **Author intent outranks engine output, except for retrospective
   calibration.** Calibration based on real outcome data sits above
   ``user_priors`` because it incorporates evidence the author may not have
   had at write-time. The author's hand-written ``register_prior`` comes next,
   ahead of reviewer overrides, engine outputs (``continuous_inference``,
   ``evidence_factor_*``), automated agent suggestions, the ``claim_inline``
   shortcut, and finally the catch-all.

Authors may override this ranking per-package by exporting a custom
``RESOLUTION_POLICY`` in ``priors.py``.

Wildcards: ``"*"`` matches any source_id (catch-all); ``"prefix_*"`` matches
any source_id starting with ``prefix_``. Wildcards may only appear at the end
of a pattern.
"""


def _matches(source_id: str, pattern: str) -> bool:
    """Match a source_id against a priority-order pattern.

    Patterns: exact match (``"user_priors"``), trailing wildcard
    (``"reviewer_*"``), or universal wildcard (``"*"``). Wildcards in any
    other position raise ValueError.
    """
    if pattern == "*":
        return True
    if "*" in pattern:
        if not pattern.endswith("*") or pattern.count("*") != 1:
            raise ValueError(
                f"Invalid priority_order pattern {pattern!r}: wildcards may only "
                "appear at the end (e.g. 'reviewer_*')."
            )
        return source_id.startswith(pattern[:-1])
    return source_id == pattern


class PriorRecord(BaseModel):
    """Prior probability for a claim Knowledge.

    Only type=claim Knowledge has PriorRecord. Values are Cromwell-clamped.
    Multiple records for the same knowledge_id may exist from different sources.
    """

    knowledge_id: str
    value: float
    source_id: str
    justification: str = ""
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        """Set default timestamp and apply Cromwell clamping after validation."""
        if self.created_at is None:
            object.__setattr__(self, "created_at", datetime.now(UTC))
        object.__setattr__(self, "value", _clamp(self.value))


class ParameterizationSource(BaseModel):
    """Metadata about the model/policy that produced a batch of records."""

    source_id: str
    model: str
    policy: str | None = None
    config: dict[str, Any] | None = None
    created_at: datetime


class ResolutionPolicy(BaseModel):
    """Policy for resolving multiple parameterization records before BP runs.

    Strategies:

    - ``"explicit_priority"`` (default): rank records by ``priority_order``
      pattern matching, with most-recent record winning within each pattern
      group. Patterns support trailing wildcards (``"reviewer_*"``) and a
      catch-all (``"*"``). When ``priority_order`` is omitted,
      :data:`DEFAULT_PRIORITY_ORDER` is used.
    - ``"latest"``: pick the most recent record per Knowledge/Strategy by
      ``created_at`` timestamp, source-agnostic.
    - ``"source"``: use only records matching the configured ``source_id``,
      latest within that source.

    ``prior_cutoff`` filters records to those created at or before the given
    timestamp, enabling reproducible BP runs against a historical snapshot of
    the claim-prior layer.
    """

    strategy: Literal["explicit_priority", "latest", "source"] = "explicit_priority"
    source_id: str | None = None
    priority_order: list[str] | None = None
    prior_cutoff: datetime | None = None

    @model_validator(mode="after")
    def _validate_strategy_inputs(self) -> ResolutionPolicy:
        if self.strategy == "source" and self.source_id is None:
            raise ValueError("strategy='source' requires source_id to be set")
        if self.priority_order is not None:
            for pattern in self.priority_order:
                # Trigger pattern validation early so misspellings fail at
                # policy-construction time rather than at resolve time.
                _matches("__probe__", pattern)
        return self

    def resolve(self, records: list[PriorRecord]) -> PriorRecord | None:
        """Pick the winning PriorRecord under this policy.

        Returns ``None`` when no record passes the filter (e.g. empty input,
        cutoff filters everything out, or a ``"source"`` strategy whose target
        ``source_id`` is absent).

        Algorithm:

        1. Filter by ``prior_cutoff`` if set.
        2. Dispatch on ``strategy``:

           - ``"latest"``: return the record with the most recent ``created_at``.
           - ``"source"``: filter to records matching ``self.source_id``,
             return the latest within that subset (or None if subset empty).
           - ``"explicit_priority"``: walk ``priority_order`` (or
             :data:`DEFAULT_PRIORITY_ORDER`) and for each pattern, find all
             matching records; the first non-empty pattern wins, with the
             most recent record breaking ties within that pattern. If no
             pattern matches any record, fall back to global recency.
        """
        candidates = list(records)
        if self.prior_cutoff is not None:
            cutoff = self.prior_cutoff
            candidates = [r for r in candidates if r.created_at <= cutoff]
        if not candidates:
            return None

        if self.strategy == "latest":
            return max(candidates, key=lambda r: r.created_at)

        if self.strategy == "source":
            assert self.source_id is not None  # validator-enforced
            matching = [r for r in candidates if r.source_id == self.source_id]
            if not matching:
                return None
            return max(matching, key=lambda r: r.created_at)

        if self.strategy == "explicit_priority":
            order = self.priority_order or list(DEFAULT_PRIORITY_ORDER)
            for pattern in order:
                matching = [r for r in candidates if _matches(r.source_id, pattern)]
                if matching:
                    return max(matching, key=lambda r: r.created_at)
            # No pattern matched (DEFAULT_PRIORITY_ORDER includes "*" so this
            # is unreachable in practice; covered for custom orders without
            # a catch-all).
            return max(candidates, key=lambda r: r.created_at)

        raise ValueError(f"Unknown ResolutionPolicy strategy: {self.strategy!r}")


def default_resolution_policy() -> ResolutionPolicy:
    """Return the package-default ResolutionPolicy.

    Equivalent to ``ResolutionPolicy()`` but more discoverable. Use this when
    a package's ``priors.py`` does not export a custom ``RESOLUTION_POLICY``.
    """
    return ResolutionPolicy()
