"""Gaia Lang v5/v6 — Knowledge DSL functions."""

from __future__ import annotations

import warnings
from typing import Any

from gaia.engine.lang.dsl.bool_expr import BoolExpr
from gaia.engine.lang.runtime import Claim, Knowledge, Note, Question
from gaia.engine.lang.runtime.knowledge import ClaimKind


def _metadata_with_legacy_kind(metadata: dict[str, Any], legacy_kind: str) -> dict[str, Any]:
    flattened = dict(_flatten_metadata(metadata))
    flattened.setdefault("legacy_kind", legacy_kind)
    return flattened


def _warn_deprecated_note_alias(name: str) -> None:
    warnings.warn(
        f"{name}() is deprecated for v0.5+ authoring; use note() instead.",
        DeprecationWarning,
        stacklevel=2,
    )


def note(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Declare non-probabilistic contextual material."""
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def context(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Deprecated compatibility wrapper for note()."""
    _warn_deprecated_note_alias("context")
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_metadata_with_legacy_kind(metadata, "context"),
    )


def setting(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Note:
    """Deprecated compatibility wrapper for note()."""
    _warn_deprecated_note_alias("setting")
    provenance = metadata.pop("provenance", None)
    return Note(
        content=content.strip(),
        format=format,
        title=title,
        provenance=provenance or [],
        metadata=_metadata_with_legacy_kind(metadata, "setting"),
    )


def question(
    content: str,
    *,
    title: str | None = None,
    format: str = "markdown",
    **metadata: Any,
) -> Question:
    """Declare a research question. No probability, no BP participation."""
    provenance = metadata.pop("provenance", None)
    targets = metadata.pop("targets", [])
    return Question(
        content=content.strip(),
        format=format,
        title=title,
        targets=targets,
        provenance=provenance or [],
        metadata=_flatten_metadata(metadata),
    )


def _flatten_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Unwrap nested metadata={"metadata": {...}} into a flat dict."""
    if "metadata" in metadata and isinstance(metadata["metadata"], dict) and len(metadata) == 1:
        return metadata["metadata"]
    return metadata


def claim(
    content: str,
    proposition: BoolExpr | None = None,
    *,
    title: str | None = None,
    format: str = "markdown",
    background: list[Knowledge] | None = None,
    parameters: list[dict[str, Any]] | None = None,
    provenance: list[dict[str, str]] | None = None,
    prior: float | None = None,
    formula: Any = None,
    kind: ClaimKind = ClaimKind.GENERAL,
    tolerance: float | None = None,
    **metadata: Any,
) -> Claim:
    """Declare a scientific assertion.

    Three authoring shapes:

    1. **Prose claim** — ``claim("Heliocentric model is correct.", prior=0.8)``.
       The proposition is conveyed in natural language. The optional ``prior``
       keyword is a low-priority shortcut routed through ``register_prior()``
       with ``source_id="claim_inline"``.
    2. **Predicate claim** — ``claim("Reaction is fast", k > 1e-2)``. The
       second positional argument is a :class:`BoolExpr` produced by
       comparing a :class:`Distribution` against a constant. The compiler
       registers a CDF-derived prior record for inequality predicates.
       See :class:`gaia.engine.lang.Distribution` for how to declare the
       underlying continuous quantity.
    3. **Formula claim** — ``claim(content, formula=Forall(...))`` for the
       predicate-logic surface (unchanged from v0.5).

    The ``tolerance`` keyword applies only when ``proposition`` is an equation
    (``lhs == rhs``). PR1 stores equation metadata and a neutral default prior;
    equation constraint lowering is deferred.
    """
    raw_metadata = _flatten_metadata(metadata)
    if proposition is not None:
        if not isinstance(proposition, BoolExpr):
            raise TypeError(
                "claim() second positional argument must be a BoolExpr produced "
                "by comparing a Distribution against another value (e.g. "
                "k > 1e-2). Got "
                f"{type(proposition).__name__}. For prose claims, omit the "
                "second argument; for predicate-logic claims, use the "
                "`formula=` keyword."
            )
        # The full lowering of predicate / equation propositions to claim
        # priors happens in `gaia.engine.lang.compiler.compile`; here we just stash
        # the BoolExpr on metadata for the compiler to read.
        if "predicate" in raw_metadata or "equation" in raw_metadata:
            raise TypeError(
                "claim() received both a proposition argument and a manually "
                "set metadata['predicate'] / metadata['equation'] entry — pick "
                "one."
            )
        slot = "equation" if proposition.op in {"==", "!="} else "predicate"
        raw_metadata = dict(raw_metadata)
        raw_metadata[slot] = proposition
        if tolerance is not None:
            if slot != "equation":
                raise TypeError(
                    "claim(tolerance=...) only applies to equation propositions "
                    "(``y == baseline + slope * x``); for inequality predicates the "
                    "prior is exact via CDF integration."
                )
            if not isinstance(tolerance, (int, float)) or float(tolerance) <= 0.0:
                raise ValueError(
                    f"claim(tolerance=...) must be a positive number, got {tolerance!r}."
                )
            raw_metadata["equation_tolerance"] = float(tolerance)
    elif tolerance is not None:
        raise TypeError(
            "claim(tolerance=...) requires a proposition (equation BoolExpr). "
            "It does nothing on a prose or formula claim."
        )
    c = Claim(
        content=content.strip(),
        format=format,
        title=title,
        background=background or [],
        parameters=parameters or [],
        provenance=provenance or [],
        prior=None,
        formula=formula,
        kind=kind,
        metadata=raw_metadata,
    )
    if prior is not None:
        # Route through register_prior so the inline value participates in the
        # same multi-source PriorRecord pipeline as everything else. The
        # "claim_inline" shortcut is intentionally low priority, below
        # generated continuous-inference priors and documented register_prior()
        # calls.
        from gaia.engine.lang.dsl.register_prior import register_prior

        register_prior(
            c,
            prior,
            source_id="claim_inline",
            justification="(inline default declared at claim() call site)",
        )
    return c
