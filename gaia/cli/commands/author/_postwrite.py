"""Post-write integration with ``gaia build check``.

Per R1·❓-D=D1 (locked in 协作单 §三): pre-write and post-write are
**separate gates**. Pre-write always runs fail-fast (no flag); post-write
``gaia build check`` runs by default after a successful write, gated by
``--check / --no-check`` (default on). When pre-write fails, post-write is
short-circuited — there's no point running compile-grade validation
against a write that did not happen.

This module talks to the engine through its programmatic API
(``load_gaia_package`` + ``compile_loaded_package_artifact``) rather than
shelling out to ``gaia build check``: it's faster, lets us thread our
diagnostic ``where`` records, and avoids subprocess marshalling.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gaia.cli.commands.author._envelope import Diagnostic
from gaia.engine.ir import LocalCanonicalGraph
from gaia.engine.ir.validator import validate_local_graph
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
    validate_fills_relations,
)


@dataclass
class PostWriteResult:
    """Outcome of the post-write ``gaia build check``-equivalent pass."""

    ok: bool
    diagnostics: list[Diagnostic]
    warnings: list[Diagnostic]
    knowledge_count: int = 0
    strategy_count: int = 0
    operator_count: int = 0


def postwrite_check(target_path: str | Path) -> PostWriteResult:
    """Run the post-write build-grade check on ``target_path``.

    Returns a structured :class:`PostWriteResult` instead of raising — the
    verb-level caller decides whether to convert the failure into a
    diagnostic on the envelope or surface it differently. Diagnostics are
    tagged ``source="postwrite"`` so JSON consumers can distinguish them
    from pre-write entries.

    The implementation mirrors ``gaia.cli.commands.check._load_check_artifacts``
    + ``_collect_check_diagnostics`` but only carries the **structural**
    pieces — we skip the optional inquiry / quality-gate / warrants
    passes that ``gaia build check`` flags add on top.
    """
    target = Path(target_path)

    try:
        loaded = load_gaia_package(target)
        apply_package_priors(loaded)
        compiled = compile_loaded_package_artifact(loaded)
    except GaiaPackagingError as exc:
        return PostWriteResult(
            ok=False,
            diagnostics=[
                Diagnostic(
                    kind="postwrite.compile_fail",
                    level="error",
                    message=str(exc),
                    source="postwrite",
                    where={"target": str(target)},
                )
            ],
            warnings=[],
        )

    ir = compiled.to_json()

    diagnostics: list[Diagnostic] = []
    warnings: list[Diagnostic] = []

    try:
        validate_fills_relations(loaded, compiled)
    except GaiaPackagingError as exc:
        diagnostics.append(
            Diagnostic(
                kind="postwrite.check_fail",
                level="error",
                message=str(exc),
                source="postwrite",
                where={"target": str(target)},
            )
        )

    validation = validate_local_graph(LocalCanonicalGraph(**ir))
    for err in validation.errors:
        diagnostics.append(
            Diagnostic(
                kind="postwrite.check_fail",
                level="error",
                message=err,
                source="postwrite",
                where={"target": str(target)},
            )
        )
    for warn in validation.warnings:
        warnings.append(
            Diagnostic(
                kind="postwrite.check_fail",
                level="warning",
                message=warn,
                source="postwrite",
                where={"target": str(target)},
            )
        )

    return PostWriteResult(
        ok=not diagnostics,
        diagnostics=diagnostics,
        warnings=warnings,
        knowledge_count=len(ir["knowledges"]),
        strategy_count=len(ir["strategies"]),
        operator_count=len(ir["operators"]),
    )


__all__ = ["PostWriteResult", "postwrite_check"]
