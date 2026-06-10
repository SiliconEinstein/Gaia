"""``gaia author composition`` (+ deprecated alias ``compose``) — validate + register.

The composition primitive is a Python-decorator-level concept (its body
is an arbitrary Python function capturing nested ``Action`` invocations
through a ContextVar; see :mod:`gaia.engine.lang.runtime.composition`).
The cli surface therefore does not emit a statement to ``__init__.py``
like the other 17 author verbs — instead, it takes a **file path**
containing a ``@compose`` / ``@composition``-decorated function,
validates the shape, and registers ``(file, composition_name, version)``
into the package's pyproject ``[tool.gaia]`` metadata so downstream
tooling can discover compositions without importing the package.

The author inventory totals 19 verbs: 17 statement-emitting plus the
file-based ``composition`` validate-and-register verb and its
deprecated ``compose`` alias, both documented here.

CLI surface::

    gaia author composition --from-file <path> [--target <pkg-root>]
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

``composition`` is the canonical verb; ``compose`` is a deprecated alias
kept for compatibility (it reads as the inverse of ``decompose``, which it
is not — see issue #759). Both reuse this impl, distinguished by ``verb=``;
the ``compose`` spelling surfaces a deprecation warning in the envelope.

``--check`` (default on) drives a real :func:`postwrite_check` against
the target package after registration succeeds. Semantics:

* Pre-write / shape failures still abort before any write touches disk
  (no registration on failure).
* Registration is the **truth-bearing** action: once the
  ``pyproject.toml`` write completes, the entry stays on disk
  regardless of post-write outcome. The author-time discipline is
  "register first, validate second" — composition registration is a
  metadata fact, while postwrite validates compilation hygiene of the
  whole package.
* If post-write fails, the envelope reports ``status="error"``,
  ``code=1``, ``source="postwrite"`` so an agent can detect "compose
  registered but the target package does not compile cleanly" and
  decide whether to rollback by hand (typically by re-running
  ``compose`` with a fixed pattern file, or removing the entry
  manually). The payload still carries the registration details, so
  the agent has the breadcrumbs for both the registered entry and the
  failure mode.
* ``--no-check`` skips post-write entirely; payload carries
  ``check: "skipped"``.
"""

from __future__ import annotations

import ast
import datetime
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import tomli_w
import typer

from gaia.cli.commands.author._envelope import (
    EXIT_OK,
    EXIT_PREWRITE_STRUCTURAL,
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)
from gaia.cli.commands.author._postwrite import postwrite_check

_COMPOSE_DECORATOR_NAMES = frozenset({"compose", "composition"})

# Human-readable epilog example for ``--help`` output.
_EPILOG_EXAMPLE = """
Invoke:

    $ gaia author composition --from-file pattern.py --target ./my-pkg
    $ gaia author compose --from-file pattern.py --target ./my-pkg  (deprecated alias)

Example pattern file (`pattern.py`):

    from gaia.engine.lang import composition, claim, derive

    @composition(name="my-pkg:my-pattern", version="1.0")
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


def _emit_postwrite_failure(
    verb: str,
    *,
    payload: dict[str, Any],
    diagnostics: list[Diagnostic],
    warnings_list: list[str],
    human: bool,
) -> None:
    """Emit an envelope reflecting a postwrite failure with registration preserved.

    Composition registration is the truth-bearing action; once it
    completes, the entry stays on disk regardless of the subsequent
    post-write compile check. The envelope reports the failure mode
    (``status="error"``, exit 1, source="postwrite") and carries the
    registration payload so the caller has both pieces of state to act
    on.
    """
    payload = dict(payload)
    payload["check"] = "failed"
    result = AuthorResult(
        verb=verb,
        status="error",
        code=EXIT_PREWRITE_STRUCTURAL,
        payload=payload,
        warnings=warnings_list,
        diagnostics=diagnostics,
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


def _strip_compositions_blocks(text: str) -> str:
    """Remove every ``[[tool.gaia.compositions]]`` block from ``text``.

    The boundaries are TOML-table headers (``[`` at column 0, ignoring
    whitespace) which the parser rejects when they appear inside a
    string, so user-controlled strings containing literal lines matching
    ``[[tool.gaia.compositions]]`` can't trick the skipper. We still
    tokenise by line to preserve unrelated comments / whitespace
    outside the compositions array. After we strip we run
    ``tomllib.loads`` to confirm the remainder is still valid TOML; if
    not, we restore the original and raise.
    """
    lines = text.splitlines(keepends=True)
    kept: list[str] = []
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
        kept.append(line)
    return "".join(kept)


def _update_compositions_table(
    pyproject_path: Path,
    *,
    name: str,
    version: str,
    file_path: str,
    function: str,
) -> dict[str, Any]:
    r"""Insert-or-update a ``[[tool.gaia.compositions]]`` entry in pyproject.toml.

    Values are TOML-escaped via ``tomli_w`` so user-controlled strings
    (e.g. a malicious composition ``name=`` carrying ``\"`` or newline)
    can't break out of the string literal and corrupt the pyproject.
    The rewrite path still tokenises by table headers, but every
    emitted value is escaped through the real TOML writer.

    Returns the entry dict that was written.
    """
    timestamp = datetime.datetime.now(datetime.UTC).isoformat(timespec="seconds")
    entry: dict[str, Any] = {
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
    compositions_raw = current.get("tool", {}).get("gaia", {}).get("compositions", [])
    if not isinstance(compositions_raw, list):
        compositions_raw = []
    compositions: list[dict[str, Any]] = [c for c in compositions_raw if isinstance(c, dict)]

    # Replace existing entry with same name (case-sensitive match), or
    # append. Both paths funnel through the same TOML-aware emitter.
    kept = [c for c in compositions if c.get("name") != name]
    kept.append(entry)

    stripped = _strip_compositions_blocks(text)
    if not stripped.endswith("\n"):
        stripped += "\n"

    rendered = _render_compositions_toml(kept)
    new_text = stripped.rstrip() + "\n\n" + rendered
    if not new_text.endswith("\n"):
        new_text += "\n"

    # Sanity-check: the rewritten document must still be parseable TOML
    # and must round-trip the entries we just wrote.
    try:
        parsed = tomllib.loads(new_text)
    except tomllib.TOMLDecodeError as exc:  # pragma: no cover - defensive
        raise OSError(f"compose: rewritten pyproject.toml is not valid TOML: {exc}") from exc
    parsed_entries = parsed.get("tool", {}).get("gaia", {}).get("compositions", [])
    if not isinstance(parsed_entries, list) or len(parsed_entries) != len(kept):
        raise OSError(
            "compose: TOML rewrite lost composition entries "
            f"(expected {len(kept)}, got {len(parsed_entries)})"
        )

    pyproject_path.write_text(new_text)
    return entry


def _render_compositions_toml(entries: list[dict[str, Any]]) -> str:
    """Emit ``[[tool.gaia.compositions]]`` blocks through tomli_w.

    Each entry becomes one table in the array-of-tables. The TOML
    writer escapes strings according to the spec (control chars,
    quotes, backslashes), so user-controlled values can't break out
    of the string literal.
    """
    if not entries:
        return ""
    # ``tomli_w`` doesn't expose a "render this array-of-tables fragment"
    # API; build a wrapper doc and serialise the full thing, then strip
    # the wrapper. The output for ``{"tool": {"gaia": {"compositions": [...]}}}``
    # is the canonical ``[[tool.gaia.compositions]]`` block sequence.
    return tomli_w.dumps({"tool": {"gaia": {"compositions": entries}}})


# --------------------------------------------------------------------------- #
# Verb implementation                                                         #
# --------------------------------------------------------------------------- #


def _assert_compose_file_outside_package(
    verb: str,
    *,
    file_path: Path,
    target_root: Path,
    human: bool,
) -> bool:
    """Reject a pattern file that resolves under the target package's source root.

    Audit §A.8: ``--from-file`` is `ast.parse`d (no execution), but if
    the agent allows the attacker to drop the file *inside*
    ``src/<import_name>/`` then the postwrite ``load_gaia_package``
    will ``importlib.import_module`` it, which executes arbitrary code.
    The defense closes the gap by requiring the pattern file to live
    outside the package source tree. Convention: pattern files live in
    a sibling directory next to the package root.
    """
    import tomllib as _tomllib

    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return True
    try:
        config = _tomllib.loads(pyproject.read_text())
    except (OSError, _tomllib.TOMLDecodeError):
        return True
    project_name = config.get("project", {}).get("name")
    if not isinstance(project_name, str):
        return True
    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    candidate_roots = [target_root / import_name, target_root / "src" / import_name]
    resolved_file = file_path.resolve()
    for candidate in candidate_roots:
        if not candidate.exists():
            continue
        candidate_resolved = candidate.resolve()
        try:
            resolved_file.relative_to(candidate_resolved)
        except ValueError:
            continue
        _emit_error(
            verb,
            kind="prewrite.expr_unsafe",
            message=(
                f"--from-file {file_path} resolves inside the target package's "
                f"source root ({candidate_resolved}); pattern files must live "
                "outside src/<import_name>/ so the engine doesn't import them "
                "on load"
            ),
            where={"file": str(file_path), "source_root": str(candidate_resolved)},
            human=human,
        )
        return False
    return True


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
    check: bool,
) -> None:
    """Shared compose / composition implementation.

    Read file → AST-validate compose decorator shape → if exactly one
    match, write into pyproject ``[tool.gaia.compositions]``.

    When ``check`` is True (default), run :func:`postwrite_check`
    against the target package after a successful registration.
    Registration is preserved on disk regardless of the postwrite
    outcome; the envelope distinguishes "registered and verified" from
    "registered but failed validation".
    """
    deprecation_warnings = (
        ["'gaia author compose' is deprecated; use 'gaia author composition'"]
        if verb == "compose"
        else []
    )
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

    # ---- pre: --from-file path-escape guard --------------------------- #
    # Reject pattern files that resolve inside the target package's
    # source root, where the engine's postwrite check would
    # ``importlib.import_module`` them.
    if not _assert_compose_file_outside_package(
        verb,
        file_path=file_path,
        target_root=target_root,
        human=human,
    ):
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

    payload: dict[str, Any] = {
        "target": str(target_root),
        "file_path": str(file_path),
        "composition_name": entry["name"],
        "composition_version": entry["version"],
        "function": entry["function"],
        "registered_at": entry["registered_at"],
        "pyproject": str(pyproject_path),
    }

    # ---- postwrite: optional --check integration --------------------- #
    #
    # --check runs ``postwrite_check`` against the target package after
    # registration. Registration stays on disk regardless of postwrite
    # outcome — composition registration is metadata about which
    # patterns the package owns; postwrite validates that the package
    # itself compiles cleanly. The two are decoupled by design.
    if not check:
        payload["check"] = "skipped"
        _emit_success(verb, payload=payload, warnings_list=deprecation_warnings, human=human)
        return

    post = postwrite_check(target_root)
    warnings_messages = [*deprecation_warnings, *(w.message for w in post.warnings)]
    if not post.ok:
        _emit_postwrite_failure(
            verb,
            payload=payload,
            diagnostics=post.diagnostics,
            warnings_list=warnings_messages,
            human=human,
        )
        return
    payload["check"] = {
        "knowledge_count": post.knowledge_count,
        "strategy_count": post.strategy_count,
        "operator_count": post.operator_count,
    }
    _emit_success(verb, payload=payload, warnings_list=warnings_messages, human=human)


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
        help=(
            "Run postwrite_check against the target package after registration "
            "(default on). Registration is preserved on disk even when post-check "
            "fails — the envelope reports source='postwrite' so the caller can "
            "detect a register-but-validation-broken state."
        ),
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render the envelope in human-readable form instead of JSON.",
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help=("Reserved for symmetry; the deprecation notice is envelope-only and never prompts."),
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Deprecated alias of ``composition``; validate + register a pattern file."""
    del json_, interactive
    _run_compose("compose", from_file=from_file, target=target, human=human, check=check)


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
        help=(
            "Run postwrite_check against the target package after registration "
            "(default on). Registration is preserved on disk even when post-check "
            "fails — the envelope reports source='postwrite' so the caller can "
            "detect a register-but-validation-broken state."
        ),
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
    r"""Validate + register a @composition-decorated function into pkg metadata."""
    del json_, interactive
    _run_compose("composition", from_file=from_file, target=target, human=human, check=check)


composition_command.__doc__ = (composition_command.__doc__ or "") + "\n" + _EPILOG_EXAMPLE


__all__ = ["compose_command", "composition_command"]
