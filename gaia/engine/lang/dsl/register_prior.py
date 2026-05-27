"""register_prior — explicit prior registration with multi-source support.

Also exposes :func:`resolve_priors_to_metadata`, the pure-computation step
that walks a sequence of Claim objects, runs the supplied
:class:`gaia.engine.ir.ResolutionPolicy` over each claim's ``prior_records``, and
writes the winner to ``metadata['prior']``, ``metadata['prior_justification']``,
and ``metadata['prior_source_id']``. This step is invoked both by the CLI's
``apply_package_priors`` (with the package-level ``RESOLUTION_POLICY``) and by
``compile_package_artifact`` (idempotently, with a safety-net default policy
for callers that bypass the CLI).

This is the canonical way to attach a load-bearing prior to a Claim in Gaia
v0.5+. The ``claim(prior=...)`` kwarg remains as a low-priority compatibility
shortcut that internally records a ``source_id="claim_inline"`` PriorRecord.
The legacy ``PRIORS = {...}`` dict in ``priors.py`` is rejected at compile time
with a migration error.

Multiple priors may be registered for the same Claim from different sources
(``"user_priors"`` for the author, ``"continuous_inference"`` for
``#581``-style engines, ``"reviewer_<name>"`` for human reviewers, etc.).
The compile-time ``ResolutionPolicy`` picks the winner while preserving the
losing records for audit (see ``gaia.engine.ir.parameterization.ResolutionPolicy``
and the ``prior_dissent`` / ``prior_overridden`` diagnostics).

Records are stored on ``claim.metadata["prior_records"]`` as a list of dicts
(JSON-friendly so they survive IR serialization). The compile-time pipeline
in ``gaia.cli._packages`` reads this list, applies the ResolutionPolicy, and
writes the winning value/source/justification to metadata for downstream BP /
render / brief consumers — none of which have to change.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from gaia.engine.ir.parameterization import CROMWELL_EPS
from gaia.engine.lang._boolean_valued import is_boolean_valued
from gaia.engine.lang.runtime.knowledge import Claim

PRIOR_RECORDS_METADATA_KEY = "prior_records"
"""Metadata key under which the per-claim list of PriorRecord dicts is stored."""

DEFAULT_SOURCE_ID = "user_priors"
"""Default source_id used when an author calls ``register_prior`` without
specifying one. Engines, reviewers, and agents must pass an explicit
source_id matching their namespace (e.g. ``"continuous_inference"``,
``"reviewer_alice"``, ``"agent_xyz"``)."""


def register_prior(
    claim: Any,
    value: float,
    *,
    justification: str,
    source_id: str = DEFAULT_SOURCE_ID,
    created_at: datetime | None = None,
) -> None:
    """Register a prior probability for a claim from a named source.

    This is the canonical (and after v0.5, the only) way to attach a prior to
    a Claim. The author writes register_prior calls in ``priors.py`` (auto-
    imported by ``gaia build compile``) or anywhere else in the package; engines and
    reviewers use the same API with an appropriate ``source_id``.

    Args:
        claim: The Claim instance to attach the prior to.
        value: Prior probability. Must be inside the Cromwell bounds
            ``[CROMWELL_EPS, 1 - CROMWELL_EPS]`` — values outside this range
            are rejected with ValueError (no silent clamping; engines writing
            extreme values almost always indicate a bug).
        justification: Required non-empty rationale string. Empty or
            whitespace-only justifications are rejected.
        source_id: Source identifier; defaults to ``"user_priors"`` for
            author-written priors. Engines, reviewers, and agents must pass
            an explicit ``source_id`` so the ResolutionPolicy can rank them.
            Common namespaces: ``"user_priors"``, ``"continuous_inference"``,
            ``"reviewer_*"``, ``"calibration_*"``, ``"agent_*"``,
            ``"evidence_factor_*"``.
        created_at: Optional explicit timestamp. Defaults to ``datetime.now(UTC)``.
            Provide an explicit value for reproducible package builds or when
            registering historical priors.

    Raises:
        TypeError: If ``claim`` is not a Claim instance, if a Boolean-valued
            expression is passed instead of an explicit Claim, or if ``value``
            is not a numeric scalar (booleans are explicitly rejected to catch
            mistakes like ``register_prior(c, True)``).
        ValueError: If ``value`` is outside Cromwell bounds, ``source_id`` is
            empty/whitespace, or ``justification`` is empty/whitespace.

    Examples:
        Author writes in ``priors.py``::

            from gaia.engine.lang import register_prior
            from . import aristotle_model, medium_model

            register_prior(aristotle_model, 0.5,
                           justification="Neutral before the thought experiment.")
            register_prior(medium_model, 0.5,
                           justification="Neutral before the thought experiment.")

        Reviewer writes alternative priors in ``priors_reviewer_alice.py``::

            register_prior(aristotle_model, 0.05,
                           source_id="reviewer_alice",
                           justification="Tied-body argument is decisive against A.")
    """
    if not isinstance(claim, Claim):
        if is_boolean_valued(claim):
            raise TypeError(
                "register_prior() does not auto-lift Boolean-valued expressions. "
                "Attach priors only to an explicit claim(..., formula=...) or "
                "claim(..., proposition=...) helper so the prior has a named, "
                "auditable target."
            )
        raise TypeError(
            f"register_prior() claim must be a Claim instance, "
            f"got {type(claim).__name__}. Pass the Claim object returned by "
            f"claim(), not its label or content string."
        )
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(
            f"register_prior() value must be a numeric scalar in "
            f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}], "
            f"got {type(value).__name__}: {value!r}."
        )
    value_f = float(value)
    if value_f != value_f:  # NaN check
        raise ValueError("register_prior() value must be finite, got NaN.")
    if value_f < CROMWELL_EPS or value_f > 1 - CROMWELL_EPS:
        label = claim.label or claim.content[:40]
        raise ValueError(
            f"register_prior({label!r}, value={value_f}) outside Cromwell bounds "
            f"[{CROMWELL_EPS}, {1 - CROMWELL_EPS}]. "
            f"Values at the boundary almost always indicate a bug or an "
            f"observation that should be expressed via observe() instead. "
            f"Use observe(claim) to pin a claim to true (1 - CROMWELL_EPS), "
            f"or contradict() to pin it to false."
        )
    if not isinstance(source_id, str) or not source_id.strip():
        raise ValueError(
            f"register_prior() source_id must be a non-empty string, "
            f"got {source_id!r}. Use the default 'user_priors' for author-"
            f"written priors, or a namespaced id like 'continuous_inference', "
            f"'reviewer_alice', 'calibration_2026q2'."
        )
    if not isinstance(justification, str) or not justification.strip():
        label = claim.label or claim.content[:40]
        raise ValueError(
            f"register_prior({label!r}) requires a non-empty justification. "
            f"Setting a prior is methodologically heavy; document the source / "
            f"reasoning so future reviewers can audit the choice."
        )

    record = {
        "value": value_f,
        "source_id": source_id.strip(),
        "justification": justification.strip(),
        "created_at": (created_at or datetime.now(UTC)).isoformat(),
    }

    records = claim.metadata.setdefault(PRIOR_RECORDS_METADATA_KEY, [])
    if not isinstance(records, list):
        raise TypeError(
            f"register_prior() found existing claim.metadata[{PRIOR_RECORDS_METADATA_KEY!r}] "
            f"of type {type(records).__name__}, expected list. The metadata key is "
            f"reserved by register_prior — do not write it directly."
        )
    records.append(record)


def get_prior_records(claim: Claim) -> list[dict[str, Any]]:
    """Return the list of prior records registered on a Claim, or empty list.

    Returned dicts are JSON-shaped: ``value`` (float), ``source_id`` (str),
    ``justification`` (str), ``created_at`` (ISO-8601 str).
    """
    if not isinstance(claim, Claim):
        raise TypeError(f"get_prior_records() expects a Claim, got {type(claim).__name__}.")
    records = claim.metadata.get(PRIOR_RECORDS_METADATA_KEY, [])
    if not isinstance(records, list):
        return []
    return list(records)


def resolve_priors_to_metadata(
    knowledges: Any,
    policy: Any,
) -> None:
    """Run ``policy.resolve()`` over every Claim's prior_records in-place.

    Walks the supplied ``knowledges`` iterable (typically
    ``CollectedPackage.knowledge``), and for each :class:`Claim` with one or
    more dict records under ``metadata['prior_records']`` constructs the
    corresponding :class:`gaia.engine.ir.PriorRecord` instances, asks the supplied
    :class:`gaia.engine.ir.ResolutionPolicy` for the winner, and writes the winner's
    value/justification/source to ``metadata['prior']`` /
    ``metadata['prior_justification']`` / ``metadata['prior_source_id']``. All
    records (winner and losers) stay in ``prior_records`` for downstream audit,
    ``gaia build check --hole`` display, and the ``prior_dissent`` /
    ``prior_overridden`` diagnostics.

    Idempotent: re-running the same policy over the same records produces the
    same winner because ``prior_records`` is not mutated.

    Raises:
        ValueError: If a record has malformed ``created_at`` (not a string or
            datetime).
        TypeError: If ``metadata['prior_records']`` is not a list.
    """
    for knowledge in knowledges:
        if not isinstance(knowledge, Claim):
            continue
        records_data = knowledge.metadata.get(PRIOR_RECORDS_METADATA_KEY)
        if not records_data:
            continue
        if not isinstance(records_data, list):
            label = knowledge.label or knowledge.content[:40]
            raise TypeError(
                f"Claim {label!r} has metadata[{PRIOR_RECORDS_METADATA_KEY!r}] "
                f"of type {type(records_data).__name__}, expected list. The "
                "metadata key is reserved by register_prior() — do not write "
                "it directly."
            )
        kid = knowledge.label or knowledge.content[:40]
        records = [_record_from_dict(r, knowledge_id=kid) for r in records_data]
        winner = policy.resolve(records)
        if winner is None:
            continue
        knowledge.metadata["prior"] = winner.value
        knowledge.metadata["prior_justification"] = winner.justification
        knowledge.metadata["prior_source_id"] = winner.source_id


def _record_from_dict(record_data: dict[str, Any], *, knowledge_id: str) -> Any:
    """Convert a register_prior metadata dict into a PriorRecord for resolution."""
    from gaia.engine.ir.parameterization import PriorRecord

    raw_created_at = record_data.get("created_at")
    if isinstance(raw_created_at, str):
        created_at = datetime.fromisoformat(raw_created_at)
    elif isinstance(raw_created_at, datetime):
        created_at = raw_created_at
    elif raw_created_at is None:
        # IR-side records have created_at stripped to keep ir_hash stable;
        # use epoch so they sort below freshly-registered records.
        created_at = datetime(1970, 1, 1, tzinfo=UTC)
    else:
        raise ValueError(
            f"prior_records[{knowledge_id!r}] entry has malformed created_at "
            f"({type(raw_created_at).__name__})."
        )
    return PriorRecord(
        knowledge_id=knowledge_id,
        value=float(record_data["value"]),
        source_id=str(record_data["source_id"]),
        justification=str(record_data.get("justification", "")),
        created_at=created_at,
    )
