"""``gaia author compose`` / ``gaia author composition`` — validate + register.

R3·❓D=A (locked in 协作单 §三 / §五). The composition primitive is a
Python-decorator-level concept (its body is an arbitrary Python function
capturing nested ``Action`` invocations through a ContextVar; see
:mod:`gaia.engine.lang.runtime.composition`). The cli surface therefore
does not emit a statement to ``__init__.py`` like the other 17 author
verbs — instead, it takes a **file path** containing a
``@compose`` / ``@composition``-decorated function, validates the
shape, and registers ``(file, composition_name, version)`` into the
package's pyproject ``[tool.gaia]`` metadata so downstream tooling can
discover compositions without importing the package.

This lifts ``compose`` / ``composition`` from R1's "stub" status to
"live, just at a different cli shape" — file-based validate-and-register
instead of statement-emitting. Per the 协作单, post-R3 the inventory
reads "19 total: 17 statement-emitting + 2 file-based" rather than
"17 live + 2 stubbed".

CLI surface::

    gaia author compose --from-file <path> [--target <pkg-root>]
                       [--check / --no-check] [--human]
                       [--interactive] [--json/--no-json]

Validation contract (each failure exits 2 with a structured diagnostic):

* ``--from-file`` must exist + be valid Python.
* Exactly one ``@compose`` / ``@composition``-decorated ``FunctionDef``
  in the file (the **one-compose-per-file rule**). Decorators counted:
  bare ``@compose`` / ``@composition`` plus ``@<module>.compose`` /
  ``@<module>.composition`` Attribute-shaped references.
* The decorator must carry both ``name=`` and ``version=`` kwargs.
* The decorated function's return annotation must read ``Claim`` (or
  ``"Claim"`` as a forward-ref string). Missing annotation, or anything
  else, fails.
* Registration target: ``[tool.gaia.compositions]`` as a TOML
  array-of-tables in ``pyproject.toml``. Each entry carries
  ``name`` / ``version`` / ``file`` / ``function`` / ``registered_at``.
  We **insert-or-update by name**: re-running ``compose`` for the same
  ``name`` overwrites the entry (idempotent).

The ``composition`` alias verb in :mod:`._init_` reuses this impl with
``verb="composition"`` to keep the cli-surface inventory symmetric.
"""

from __future__ import annotations

import ast
import datetime
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from gaia.cli.commands.author._envelope import (
    EXIT_OK,
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)

_COMPOSE_DECORATOR_NAMES = frozenset({"compose", "composition"})

# Human-readable epilog example for ``--help`` output.
_EPILOG_EXAMPLE = """
Example pattern file (`pattern.py`):

    from gaia.engine.lang import compose, claim, derive

    @compose(name="my-pkg:my-pattern", version="1.0")
    def my_pattern(input_claim: Claim) -> Claim:
        result = derive(input_claim, given=[input_claim], label="warranted")
        return result

Registration target: ``[tool.gaia.compositions]`` array-of-tables in
the target package's pyproject.toml. Re-running with the same composition
name updates the existing entry in place (idempotent).
"""


# --------------------------------------------------------------------------- #
# AST inspection                                                              #
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class _ComposeDecoratorMatch:
    """A ``FunctionDef`` flagged as a composition pattern."""

    function: ast.FunctionDef
    decorator: ast.Call
    name: str
    version: str


def _is_compose_decorator(node: ast.expr) -> bool:
    """Return True when ``node`` looks like ``@compose(...)`` / ``@composition(...)``.

    Accepts bare ``compose`` / ``composition`` and ``<x>.compose`` /
    ``<x>.composition`` Attribute references (so ``@dsl.compose(...)``
    style imports still match).
    """
    if isinstance(node, ast.Call):
        return _is_compose_decorator(node.func)
    if isinstance(node, ast.Name):
        return node.id in _COMPOSE_DECORATOR_NAMES
    if isinstance(node, ast.Attribute):
        return node.attr in _COMPOSE_DECORATOR_NAMES
    return False


def _decorator_call(node: ast.expr) -> ast.Call | None:
    if isinstance(node, ast.Call) and _is_compose_decorator(node):
        return node
    return None


def _extract_string_kwarg(call: ast.Call, kwarg_name: str) -> str | None:
    for kw in call.keywords:
        if kw.arg != kwarg_name:
            continue
        if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _return_annotation_is_claim(fn: ast.FunctionDef) -> bool:
    if fn.returns is None:
        return False
    if isinstance(fn.returns, ast.Name):
        return fn.returns.id == "Claim"
    if isinstance(fn.returns, ast.Constant) and isinstance(fn.returns.value, str):
        return fn.returns.value.strip() == "Claim"
    return False


def _scan_for_compose_functions(tree: ast.Module) -> list[_ComposeDecoratorMatch | ast.FunctionDef]:
    """Return ``_ComposeDecoratorMatch`` (validated) / ``FunctionDef`` (raw) per hit.

    A raw ``FunctionDef`` is yielded for functions whose decorator matches
    but whose kwargs are malformed — the caller surfaces a precise error
    for those.
    """
    hits: list[_ComposeDecoratorMatch | ast.FunctionDef] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        decorator_call: ast.Call | None = None
        for deco in node.decorator_list:
            decorator_call = _decorator_call(deco)
            if decorator_call is not None:
                break
        if decorator_call is None:
            continue
        name = _extract_string_kwarg(decorator_call, "name")
        version = _extract_string_kwarg(decorator_call, "version")
        if name is None or version is None:
            hits.append(node)
            continue
        hits.append(
            _ComposeDecoratorMatch(
                function=node,
                decorator=decorator_call,
                name=name,
                version=version,
            )
        )
    return hits


# --------------------------------------------------------------------------- #
# Registration                                                                #
# --------------------------------------------------------------------------- #


def _emit_error(
    verb: str,
    *,
    kind: str,
    message: str,
    where: dict[str, Any] | None,
    human: bool,
) -> None:
    diag = Diagnostic(
        kind=kind,
        level="error",
        message=message,
        source="prewrite",
        where=where or {},
    )
    result = AuthorResult(
        verb=verb,
        status="error",
        code=exit_code_for_diagnostic(kind),
        payload={},
        diagnostics=[diag],
    )
    emit(result, human=human)


def _emit_success(
    verb: str,
    *,
    payload: dict[str, Any],
    warnings_list: list[str],
    human: bool,
) -> None:
    result = AuthorResult(
        verb=verb,
        status="ok",
        code=EXIT_OK,
        payload=payload,
        warnings=warnings_list,
    )
    emit(result, human=human)


def _validate_target_package(target_root: Path) -> tuple[str | None, str | None]:
    """Return ``(error_kind, error_message)``; both ``None`` means OK."""
    if not target_root.exists():
        return "prewrite.target_missing", f"target path does not exist: {target_root}"
    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return "prewrite.target_not_gaia_package", (
            f"no pyproject.toml under {target_root}; expected a Gaia knowledge package"
        )
    try:
        config = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return "prewrite.target_invalid", f"pyproject.toml is not valid TOML: {exc}"
    gaia_section = config.get("tool", {}).get("gaia", {})
    if gaia_section.get("type") != "knowledge-package":
        return "prewrite.target_not_gaia_package", (
            "target package is not a Gaia knowledge package: "
            "[tool.gaia].type must equal 'knowledge-package'"
        )
    return None, None


def _update_compositions_table(
    pyproject_path: Path,
    *,
    name: str,
    version: str,
    file_path: str,
    function: str,
) -> dict[str, Any]:
    """Insert-or-update a ``[[tool.gaia.compositions]]`` entry in pyproject.toml.

    We do *not* use a TOML round-trip library (the project pins
    ``tomllib`` for read-only access); instead we append a plain TOML
    block at the end of the file when the name is new, or surgically
    rewrite the existing block when the name already exists. The
    rewrite path uses naive line-based replacement because the table
    we own is small + isolated; the alternative would be pulling in
    ``tomli-w`` / ``tomlkit`` as a new build dep, which is out of R3's
    scope.

    Returns the entry dict that was written.
    """
    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    entry = {
        "name": name,
        "version": version,
        "file": file_path,
        "function": function,
        "registered_at": timestamp,
    }

    text = pyproject_path.read_text()

    # Identify existing entries by parsing the current document.
    try:
        current = tomllib.loads(text)
    except tomllib.TOMLDecodeError:
        current = {}
    compositions = current.get("tool", {}).get("gaia", {}).get("compositions", [])

    # Replace existing entry with same name (case-sensitive match).
    if any(c.get("name") == name for c in compositions if isinstance(c, dict)):
        # Naive marker-based replacement is brittle; safer route is to
        # strip out every existing ``[[tool.gaia.compositions]]`` block
        # and re-emit the full sequence in canonical order.
        lines = text.splitlines(keepends=True)
        rewritten: list[str] = []
        skip = False
        for line in lines:
            stripped = line.strip()
            if stripped == "[[tool.gaia.compositions]]":
                skip = True
                continue
            if skip and stripped.startswith("[") and stripped != "[[tool.gaia.compositions]]":
                skip = False
            if skip:
                continue
            rewritten.append(line)
        text = "".join(rewritten).rstrip() + "\n"

        # Re-emit the kept entries (excluding the one matching ``name``)
        # plus the new entry.
        kept = [c for c in compositions if isinstance(c, dict) and c.get("name") != name]
        kept.append(entry)
        text += "\n" + "\n".join(_render_compositions_block(kept)) + "\n"
    else:
        if not text.endswith("\n"):
            text += "\n"
        text += "\n" + "\n".join(_render_compositions_block([entry])) + "\n"

    pyproject_path.write_text(text)
    return entry


def _render_compositions_block(entries: list[dict[str, Any]]) -> list[str]:
    """Emit ``[[tool.gaia.compositions]]`` blocks as a list of TOML source lines."""
    out: list[str] = []
    for entry in entries:
        out.append("[[tool.gaia.compositions]]")
        for key in ("name", "version", "file", "function", "registered_at"):
            value = entry.get(key)
            if value is None:
                continue
            out.append(f'{key} = "{value}"')
        out.append("")  # blank separator
    if out and out[-1] == "":
        out.pop()
    return out


# --------------------------------------------------------------------------- #
# Verb implementation                                                         #
# --------------------------------------------------------------------------- #


def _load_pattern_file(verb: str, file_path: Path, *, human: bool) -> ast.Module | None:
    """Read + parse a pattern file; emit a diagnostic + return None on failure."""
    if not file_path.exists():
        _emit_error(
            verb,
            kind="prewrite.target_missing",
            message=f"--from-file does not exist: {file_path}",
            where={"file": str(file_path)},
            human=human,
        )
        return None
    try:
        source = file_path.read_text()
    except OSError as exc:
        _emit_error(
            verb,
            kind="prewrite.target_invalid",
            message=f"failed to read --from-file {file_path}: {exc}",
            where={"file": str(file_path)},
            human=human,
        )
        return None
    try:
        return ast.parse(source)
    except SyntaxError as exc:
        _emit_error(
            verb,
            kind="prewrite.syntax",
            message=f"--from-file {file_path} is not valid Python: {exc.msg}",
            where={"file": str(file_path), "line": exc.lineno or 0},
            human=human,
        )
        return None


def _select_single_compose_match(
    verb: str,
    matches: list[_ComposeDecoratorMatch | ast.FunctionDef],
    *,
    file_path: Path,
    human: bool,
) -> _ComposeDecoratorMatch | None:
    """Enforce the one-compose-per-file rule + decorator-shape contract."""
    if not matches:
        _emit_error(
            verb,
            kind="prewrite.syntax",
            message=(
                f"no @compose / @composition-decorated function found in {file_path} "
                "(one-compose-per-file rule)"
            ),
            where={"file": str(file_path)},
            human=human,
        )
        return None
    if len(matches) > 1:
        names = [
            m.function.name if isinstance(m, _ComposeDecoratorMatch) else m.name for m in matches
        ]
        _emit_error(
            verb,
            kind="prewrite.syntax",
            message=(
                f"multiple @compose-decorated functions found in {file_path}: "
                f"[{', '.join(names)}] (one-compose-per-file rule)"
            ),
            where={"file": str(file_path), "functions": names},
            human=human,
        )
        return None
    only = matches[0]
    if isinstance(only, ast.FunctionDef):
        _emit_error(
            verb,
            kind="prewrite.syntax",
            message=(
                f"@compose decorator on '{only.name}' is missing required "
                "name= / version= keyword arguments"
            ),
            where={"file": str(file_path), "function": only.name},
            human=human,
        )
        return None
    return only


def _run_compose(
    verb: str,
    *,
    from_file: str,
    target: str,
    human: bool,
) -> None:
    """Shared compose / composition implementation.

    R3·❓D=A path: read file → AST-validate compose decorator shape → if
    exactly one match, write into pyproject ``[tool.gaia.compositions]``.
    """
    target_root = Path(target).resolve()
    file_path = Path(from_file).resolve()

    # ---- pre: target structure ---------------------------------------- #
    err_kind, err_message = _validate_target_package(target_root)
    if err_kind is not None and err_message is not None:
        _emit_error(
            verb,
            kind=err_kind,
            message=err_message,
            where={"target": str(target_root)},
            human=human,
        )
        return

    # ---- pre: --from-file load + parse -------------------------------- #
    tree = _load_pattern_file(verb, file_path, human=human)
    if tree is None:
        return

    # ---- scan: count + validate compose decorators -------------------- #
    matches = _scan_for_compose_functions(tree)
    only = _select_single_compose_match(verb, matches, file_path=file_path, human=human)
    if only is None:
        return

    # ---- shape: return annotation is Claim ---------------------------- #
    if not _return_annotation_is_claim(only.function):
        if only.function.returns is None:
            actual = "no annotation"
        else:
            actual = ast.unparse(only.function.returns)
        _emit_error(
            verb,
            kind="prewrite.syntax",
            message=(
                f"@compose function '{only.function.name}' must declare a "
                f"'-> Claim' return annotation (got {actual})"
            ),
            where={"file": str(file_path), "function": only.function.name},
            human=human,
        )
        return

    # ---- register: insert/update pyproject compositions table -------- #
    pyproject_path = target_root / "pyproject.toml"
    try:
        entry = _update_compositions_table(
            pyproject_path,
            name=only.name,
            version=only.version,
            file_path=str(file_path),
            function=only.function.name,
        )
    except OSError as exc:
        _emit_error(
            verb,
            kind="prewrite.target_invalid",
            message=f"failed to update pyproject.toml: {exc}",
            where={"target": str(target_root)},
            human=human,
        )
        return

    _emit_success(
        verb,
        payload={
            "target": str(target_root),
            "file_path": str(file_path),
            "composition_name": entry["name"],
            "composition_version": entry["version"],
            "function": entry["function"],
            "registered_at": entry["registered_at"],
            "pyproject": str(pyproject_path),
        },
        warnings_list=[],
        human=human,
    )


# --------------------------------------------------------------------------- #
# Typer entry points                                                          #
# --------------------------------------------------------------------------- #


def compose_command(
    from_file: str = typer.Option(
        ...,
        "--from-file",
        help="Path to a Python file containing exactly one @compose-decorated function.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Reserved for symmetry; compose does not yet run gaia build check (default on).",
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Reserved for symmetry; compose does not currently surface warnings.",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Validate + register a @compose-decorated function into pkg metadata."""
    del json_, check, interactive
    _run_compose("compose", from_file=from_file, target=target, human=human)


# Add the example to the typer rich-help epilog by attaching __doc__ shaped text.
compose_command.__doc__ = (compose_command.__doc__ or "") + "\n" + _EPILOG_EXAMPLE


def composition_command(
    from_file: str = typer.Option(
        ...,
        "--from-file",
        help="Path to a Python file containing exactly one @composition-decorated function.",
    ),
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    check: bool = typer.Option(
        True,
        "--check/--no-check",
        help="Reserved for symmetry; composition does not yet run gaia build check (default on).",
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Reserved for symmetry; composition does not currently surface warnings.",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Alias of ``compose``; validate + register a @composition-decorated function."""
    del json_, check, interactive
    _run_compose("composition", from_file=from_file, target=target, human=human)


composition_command.__doc__ = (composition_command.__doc__ or "") + "\n" + _EPILOG_EXAMPLE


__all__ = ["compose_command", "composition_command"]
