"""``gaia author artifact`` and ``gaia author figure`` commands."""

from __future__ import annotations

import typer

from gaia.cli.commands.author._common import emit_syntax_error, normalize_file_option
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op
from gaia.engine.lang.dsl.artifacts import ARTIFACT_KINDS, build_artifact_metadata


def _validate_cli_artifact(
    *,
    verb: str,
    kind: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    target: str,
    human: bool,
) -> None:
    try:
        build_artifact_metadata(
            kind=kind,
            source=source,
            locator=locator,
            path=path,
            caption=caption,
            description=description,
            media_type=media_type,
        )
    except ValueError as exc:
        emit_syntax_error(verb, str(exc), target=target, human=human)


def _render_artifact_statement(
    *,
    binding_name: str,
    kind: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    content: str | None,
    title: str | None,
) -> str:
    kwargs = [f"kind={kind!r}"]
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
        ("content", content),
        ("title", title),
    ):
        if value is not None:
            kwargs.append(f"{key}={value!r}")
    return f"{binding_name} = artifact({', '.join(kwargs)})"


def _render_figure_statement(
    *,
    binding_name: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    content: str | None,
    title: str | None,
) -> str:
    kwargs: list[str] = []
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
        ("content", content),
        ("title", title),
    ):
        if value is not None:
            kwargs.append(f"{key}={value!r}")
    return f"{binding_name} = figure({', '.join(kwargs)})"


def artifact_command(
    dsl_binding_name: str = typer.Option(
        ..., "--dsl-binding-name", help="Python module-scope identifier to bind."
    ),
    kind: str = typer.Option(
        ...,
        "--kind",
        help=f"Artifact kind: {', '.join(sorted(ARTIFACT_KINDS))}.",
    ),
    source: str | None = typer.Option(None, "--source", help="Citation key in references.json."),
    locator: str | None = typer.Option(None, "--locator", help="Source-local locator."),
    path: str | None = typer.Option(None, "--path", help="Package-relative artifact path."),
    caption: str | None = typer.Option(None, "--caption", help="Caption for visual artifacts."),
    description: str | None = typer.Option(
        None, "--description", help="Description for attachments."
    ),
    media_type: str | None = typer.Option(None, "--media-type", help="Optional MIME type."),
    content: str | None = typer.Option(None, "--content", help="Override note content."),
    title: str | None = typer.Option(None, "--title", help="Optional note title."),
    target: str = typer.Option(".", "--target", help="Path to the target Gaia package."),
    file: str | None = typer.Option(
        None, "--file", help="Relative module file under src/<import_name>."
    ),
    export: bool = typer.Option(False, "--export/--no-export", help="Export the artifact binding."),
    check: bool = typer.Option(True, "--check/--no-check", help="Run post-write build check."),
    human: bool = typer.Option(False, "--human", help="Render human-readable output."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt on pre-write warnings."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output."),
) -> None:
    """Append an ``artifact(...)`` note anchor statement."""
    del json_
    _validate_cli_artifact(
        verb="artifact",
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        target=str(target),
        human=human,
    )
    generated_code = _render_artifact_statement(
        binding_name=dsl_binding_name,
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )
    proposed_op = ProposedAuthorOp(
        verb="artifact",
        kind="reasoning",
        label=dsl_binding_name,
        references=[],
        generated_code=generated_code,
        required_imports=("artifact",),
        target_file=normalize_file_option(file),
        export=export,
    )
    run_author_op(proposed_op, target=target, human=human, check=check, interactive=interactive)


def figure_command(
    dsl_binding_name: str = typer.Option(
        ..., "--dsl-binding-name", help="Python module-scope identifier to bind."
    ),
    source: str | None = typer.Option(None, "--source", help="Citation key in references.json."),
    locator: str | None = typer.Option(None, "--locator", help="Source-local figure locator."),
    path: str | None = typer.Option(None, "--path", help="Package-relative image path."),
    caption: str | None = typer.Option(None, "--caption", help="Figure caption."),
    description: str | None = typer.Option(None, "--description", help="Optional description."),
    media_type: str | None = typer.Option(None, "--media-type", help="Optional MIME type."),
    content: str | None = typer.Option(None, "--content", help="Override note content."),
    title: str | None = typer.Option(None, "--title", help="Optional note title."),
    target: str = typer.Option(".", "--target", help="Path to the target Gaia package."),
    file: str | None = typer.Option(
        None, "--file", help="Relative module file under src/<import_name>."
    ),
    export: bool = typer.Option(False, "--export/--no-export", help="Export the figure binding."),
    check: bool = typer.Option(True, "--check/--no-check", help="Run post-write build check."),
    human: bool = typer.Option(False, "--human", help="Render human-readable output."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt on pre-write warnings."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output."),
) -> None:
    """Append a ``figure(...)`` artifact note anchor statement."""
    del json_
    _validate_cli_artifact(
        verb="figure",
        kind="figure",
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        target=str(target),
        human=human,
    )
    generated_code = _render_figure_statement(
        binding_name=dsl_binding_name,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )
    proposed_op = ProposedAuthorOp(
        verb="figure",
        kind="reasoning",
        label=dsl_binding_name,
        references=[],
        generated_code=generated_code,
        required_imports=("figure",),
        target_file=normalize_file_option(file),
        export=export,
    )
    run_author_op(proposed_op, target=target, human=human, check=check, interactive=interactive)


__all__ = ["artifact_command", "figure_command"]
