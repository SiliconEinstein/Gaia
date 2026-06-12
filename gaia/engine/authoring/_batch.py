"""Batch authoring API for engine/SDK callers."""

from __future__ import annotations

import contextlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from gaia.cli.commands.author._authored import ensure_authored_submodule
from gaia.cli.commands.author._postwrite import postwrite_check
from gaia.cli.commands.author._prewrite import prewrite_check
from gaia.cli.commands.author._writer import append_statement
from gaia.engine.authoring._ops import ProposedAuthorOp


@dataclass(frozen=True)
class AuthoringDiagnostic:
    """Engine-facing authoring diagnostic."""

    kind: str
    level: str
    message: str
    source: str
    where: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuthorBatchWrite:
    """One statement written during a batch."""

    verb: str
    label: str | None
    written_to: Path
    snippet: str


@dataclass(frozen=True)
class AuthoringCheckSummary:
    """Final package validation counts for a successful checked batch."""

    knowledge_count: int
    strategy_count: int
    operator_count: int


@dataclass(frozen=True)
class AuthorBatchResult:
    """Structured result of :func:`run_author_batch`."""

    ok: bool
    writes: list[AuthorBatchWrite] = field(default_factory=list)
    diagnostics: list[AuthoringDiagnostic] = field(default_factory=list)
    warnings: list[AuthoringDiagnostic] = field(default_factory=list)
    check: AuthoringCheckSummary | None = None


def run_author_batch(
    target: str | Path,
    operations: list[ProposedAuthorOp],
    *,
    check: bool = True,
) -> AuthorBatchResult:
    """Write multiple author operations with one final validation pass.

    Operations are prewrite-checked and written in order, so later operations
    may reference labels introduced by earlier operations in the same batch.
    If any prewrite, write, or final postwrite step fails, files touched by the
    batch are restored to their pre-batch contents.
    """
    target_path = Path(target).resolve()
    if not operations:
        return AuthorBatchResult(ok=True)

    first_pre = prewrite_check(target_path, operations[0])
    if not first_pre.ok:
        return AuthorBatchResult(
            ok=False,
            diagnostics=_diagnostics(first_pre.diagnostics),
            warnings=_diagnostics(first_pre.warnings),
        )
    assert first_pre.source_root is not None
    snapshot = _snapshot_source(first_pre.source_root)
    writes: list[AuthorBatchWrite] = []
    warnings: list[AuthoringDiagnostic] = _diagnostics(first_pre.warnings)

    first_result = _write_prechecked_operation(operations[0], first_pre)
    if isinstance(first_result, AuthorBatchResult):
        _restore_source(first_pre.source_root, snapshot)
        return first_result
    writes.extend(first_result)

    for operation in operations[1:]:
        pre = prewrite_check(target_path, operation)
        warnings.extend(_diagnostics(pre.warnings))
        if not pre.ok:
            _restore_source(first_pre.source_root, snapshot)
            return AuthorBatchResult(
                ok=False,
                writes=[],
                diagnostics=_diagnostics(pre.diagnostics),
                warnings=warnings,
            )
        write_result = _write_prechecked_operation(operation, pre)
        if isinstance(write_result, AuthorBatchResult):
            _restore_source(first_pre.source_root, snapshot)
            return write_result
        writes.extend(write_result)

    if not check:
        return AuthorBatchResult(ok=True, writes=writes, warnings=warnings)

    post = postwrite_check(target_path)
    warnings.extend(_diagnostics(post.warnings))
    if not post.ok:
        _restore_source(first_pre.source_root, snapshot)
        return AuthorBatchResult(
            ok=False,
            writes=[],
            diagnostics=_diagnostics(post.diagnostics),
            warnings=warnings,
        )
    return AuthorBatchResult(
        ok=True,
        writes=writes,
        warnings=warnings,
        check=AuthoringCheckSummary(
            knowledge_count=post.knowledge_count,
            strategy_count=post.strategy_count,
            operator_count=post.operator_count,
        ),
    )


def _write_prechecked_operation(
    operation: ProposedAuthorOp,
    pre: Any,
) -> list[AuthorBatchWrite] | AuthorBatchResult:
    assert pre.source_root is not None
    assert pre.source_init_path is not None
    assert pre.import_name is not None
    write_target = pre.write_target_path or pre.source_init_path
    try:
        ensure_authored_submodule(pre.source_root, pre.source_init_path)
        cross_module_imports = tuple(
            (ref, "") for ref in dict.fromkeys(operation.references) if ref in pre.root_only_symbols
        )
        return _append_operation(
            operation,
            write_target=write_target,
            import_name=pre.import_name,
            cross_module_imports=cross_module_imports,
        )
    except (OSError, PermissionError) as exc:
        return AuthorBatchResult(
            ok=False,
            diagnostics=[
                AuthoringDiagnostic(
                    kind="authoring.write_failed",
                    level="error",
                    message=str(exc),
                    source="writer",
                    where={"target": str(write_target)},
                )
            ],
        )


def _append_operation(
    operation: ProposedAuthorOp,
    *,
    write_target: Path,
    import_name: str,
    cross_module_imports: tuple[tuple[str, str], ...],
) -> list[AuthorBatchWrite]:
    writes: list[AuthorBatchWrite] = []
    for prep_label, prep_code in operation.prepended_statements:
        prep_write = append_statement(
            write_target,
            prep_code,
            new_label=prep_label,
            required_imports=("claim", *operation.required_imports),
            export=operation.export,
        )
        writes.append(
            AuthorBatchWrite(
                verb=operation.verb,
                label=prep_label,
                written_to=prep_write.path,
                snippet=prep_write.appended,
            )
        )

    main_write = append_statement(
        write_target,
        operation.generated_code,
        new_label=operation.label,
        sibling_imports=(*operation.sibling_imports, *cross_module_imports),
        foreign_imports=operation.foreign_imports,
        import_package_name=import_name,
        required_imports=operation.required_imports,
        export=operation.export,
    )
    writes.append(
        AuthorBatchWrite(
            verb=operation.verb,
            label=operation.label,
            written_to=main_write.path,
            snippet=main_write.appended,
        )
    )
    return writes


def _diagnostics(items: list[Any]) -> list[AuthoringDiagnostic]:
    return [
        AuthoringDiagnostic(
            kind=str(item.kind),
            level=str(item.level),
            message=str(item.message),
            source=str(item.source),
            where=dict(getattr(item, "where", {}) or {}),
        )
        for item in items
    ]


def _snapshot_source(source_root: Path) -> dict[Path, str]:
    return {path: path.read_text(encoding="utf-8") for path in source_root.rglob("*.py")}


def _restore_source(source_root: Path, snapshot: dict[Path, str]) -> None:
    for path in sorted(source_root.rglob("*.py"), reverse=True):
        if path not in snapshot:
            path.unlink()
    for path, source in snapshot.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
    for directory in sorted(
        (path for path in source_root.rglob("*") if path.is_dir()),
        key=lambda item: len(item.parts),
        reverse=True,
    ):
        if directory == source_root:
            continue
        with contextlib.suppress(OSError):
            directory.rmdir()
