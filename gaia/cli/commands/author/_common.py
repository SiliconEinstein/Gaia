"""Shared helpers for ``gaia author`` verbs.

R2 lifts the duplicate ``_parse_metadata`` / ``_split_csv`` / metadata-error
envelope helpers out of every per-verb file into one place. The shape stays
identical to what R1's ``claim`` / ``equal`` / ``derive`` did inline — this
module is a refactor, not a behavior change.

R10 (post-review hardening round) extends this module with the
literal-or-identifier validator and the identifier-only csv splitter that
close the RCE family of findings: every ``--value`` / ``--n`` / ``--p`` /
``--alpha`` / etc. flag must now route its value through
:func:`parse_literal_or_identifier`, and every reference-list flag (``--given``,
``--against``, ``--data``, ``--whole`` / ``--parts``, ``--by``, etc.) must
route through :func:`split_csv_idents`. Free-form CSV (``--source-refs``,
``--imports``) keeps the existing :func:`split_csv`.
"""

from __future__ import annotations

import ast
import json
import re
from collections.abc import Sequence
from typing import Any

from gaia.cli.commands.author._envelope import (
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)


def parse_metadata(metadata_json: str | None) -> tuple[dict[str, Any] | None, str | None]:
    """Decode the ``--metadata`` JSON option into a dict (or return an error string)."""
    if metadata_json is None:
        return None, None
    try:
        parsed = json.loads(metadata_json)
    except json.JSONDecodeError as exc:
        return None, f"--metadata is not valid JSON: {exc}"
    if not isinstance(parsed, dict):
        return None, "--metadata must encode a JSON object (got non-object value)"
    return parsed, None


def split_csv(value: str | None) -> list[str]:
    """Split a comma-separated CLI option into a clean list of tokens.

    Free-form variant — tokens are returned unvalidated. Use this for
    flags that accept arbitrary strings (e.g. ``--source-refs``,
    ``--imports``). For identifier-bearing flags, prefer
    :func:`split_csv_idents` so the cli rejects malformed input at the
    flag boundary instead of letting it leak into generated source.
    """
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


# Identifier shape — matches Python's grammar for module-level names. We
# explicitly reject the leading-double-underscore form because dunder
# names would collide with reserved Python attributes and create
# attribute-access vectors when spliced into rendered source.
_BARE_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class PrewriteUnsafeError(ValueError):
    """Raised when a flag value fails literal-or-identifier validation.

    The cli's `--value` / `--n` / `--p` / etc. surfaces splice the
    user-supplied text directly into rendered Python source that the
    postwrite step imports. Without input validation, an attacker can
    pass ``__import__('os').system('id')`` and gain RCE on import. The
    validator accepts only Python literals (numbers, strings, bools,
    None, lists/tuples/dicts of literals) and bare identifiers; this
    raise surfaces every other shape so the caller can emit a
    ``prewrite.expr_unsafe`` diagnostic before any write happens.
    """


def _is_bare_identifier(text: str) -> bool:
    if not _BARE_IDENTIFIER_RE.match(text):
        return False
    return not text.startswith("__")


def _is_signed_number(text: str) -> bool:
    """Detect a leading-sign numeric literal (`-3`, `+1.5e-2`).

    Python's :func:`ast.literal_eval` rejects bare ``-3`` because the
    minus is parsed as a unary op. The cli accepts these on flags like
    ``--value -3`` so we recognise the shape explicitly. Multi-character
    safety is preserved because we fall through to ``literal_eval`` on
    the absolute value, which only succeeds for an actual numeric
    literal.
    """
    if not text or text[0] not in "+-":
        return False
    body = text[1:].strip()
    if not body:
        return False
    try:
        result = ast.literal_eval(body)
    except (ValueError, SyntaxError):
        return False
    return isinstance(result, (int, float, complex))


def parse_literal_or_identifier(
    value: str,
    *,
    references_sink: list[str] | None = None,
    allow_negative: bool = True,
) -> tuple[str, str]:
    """Validate ``value`` is a Python literal or bare identifier.

    Args:
        value: The flag's raw string. Stripped before inspection.
        references_sink: If provided and ``value`` is a bare identifier,
            the identifier is appended to this list so the verb's
            ``ProposedAuthorOp.references`` resolves it against module
            scope at prewrite.
        allow_negative: When ``True`` (default), recognise a leading
            ``-`` / ``+`` numeric literal that :func:`ast.literal_eval`
            would otherwise reject.

    Returns:
        A ``(kind, rendered)`` tuple where ``kind`` is ``"literal"`` or
        ``"identifier"`` and ``rendered`` is the validated text suitable
        for verbatim splicing into rendered source.

    Raises:
        PrewriteUnsafeError: when ``value`` is neither a literal nor a
            bare identifier. The error message names the value so a
            consumer can route it through ``prewrite.expr_unsafe``.

    A few examples (paper-only, not executed):

    * ``"395"`` → ``("literal", "395")``
    * ``"-3.14"`` → ``("literal", "-3.14")`` (when ``allow_negative=True``)
    * ``"True"`` → ``("literal", "True")``
    * ``"DOMINANT_COUNT"`` → ``("identifier", "DOMINANT_COUNT")`` and
      ``references_sink`` gains an entry if supplied.
    * ``"__import__('os').system('id')"`` →
      :class:`PrewriteUnsafeError`.
    """
    text = value.strip()
    if not text:
        raise PrewriteUnsafeError("value is empty")
    # Bare identifier path — also handles ``True`` / ``False`` / ``None``
    # because they match ``_BARE_IDENTIFIER_RE``. We do not push reserved
    # constants into ``references_sink`` (they don't resolve as
    # module-scope bindings).
    if _is_bare_identifier(text):
        if text in {"True", "False", "None"}:
            return "literal", text
        if references_sink is not None:
            references_sink.append(text)
        return "identifier", text
    # Literal path — accept anything ``ast.literal_eval`` accepts.
    try:
        ast.literal_eval(text)
        return "literal", text
    except (ValueError, SyntaxError):
        pass
    if allow_negative and _is_signed_number(text):
        return "literal", text
    raise PrewriteUnsafeError(
        f"value {value!r} is neither a Python literal nor a bare identifier; "
        "the cli splices flag values directly into generated source, so "
        "unsupported expressions are refused at the flag boundary"
    )


def split_csv_idents(value: str | None) -> tuple[list[str], str | None]:
    """Split a CSV flag and require every token to be a bare identifier.

    Returns ``(tokens, error_message)``. ``error_message`` is ``None``
    on success, or a human-readable string on the first malformed
    token. The caller pairs the error with the ``prewrite.expr_unsafe``
    kind via :func:`emit_syntax_error`.

    Use this for every reference-bearing CSV flag (``--given`` /
    ``--against`` / ``--data`` / ``--by`` / ``--parts`` / ``--whole``
    / ``--targets`` / ``--claims`` / etc.). Free-form CSVs (e.g.
    ``--source-refs``, ``--imports``) keep :func:`split_csv`.
    """
    tokens = split_csv(value)
    for token in tokens:
        if not _is_bare_identifier(token):
            return (
                [],
                f"identifier {token!r} is not a valid Python identifier "
                "(reference flags must be comma-separated bare identifiers)",
            )
    return tokens, None


def emit_syntax_error(
    verb: str,
    message: str,
    *,
    target: str,
    human: bool,
    kind: str = "prewrite.syntax",
) -> None:
    """Emit a pre-write syntax-error envelope and exit.

    Used by per-verb option parsers when an option is shaped wrong (bad JSON,
    empty mutually-required input, etc.) — surfaces the failure with the
    standard ``prewrite.syntax`` kind + ``EXIT_INPUT_SYNTAX`` (``2``) code
    before the runner pipeline gets called. Callers can override ``kind`` for
    related-but-distinct surfaces like ``prewrite.expr_unsafe`` (sandbox
    rejection) without forking the helper.
    """
    diag = Diagnostic(
        kind=kind,
        level="error",
        message=message,
        source="prewrite",
    )
    result = AuthorResult(
        verb=verb,
        status="error",
        code=exit_code_for_diagnostic(diag.kind),
        payload={"target": target},
        diagnostics=[diag],
    )
    emit(result, human=human)


def normalize_file_option(file: str | None) -> str | None:
    """Normalize ``--file`` input for ``ProposedAuthorOp.target_file``.

    The runner treats ``None`` as "use the source-root ``__init__.py``" so
    the existing behaviour for the default case stays unchanged. A bare
    string is passed through; whitespace + leading-dot prefixes (``./``)
    are trimmed because users intuitively type them but `pathlib.Path`
    sees them as separate path components.
    """
    if file is None:
        return None
    stripped = file.strip()
    if not stripped:
        return None
    while stripped.startswith("./"):
        stripped = stripped[2:]
    return stripped or None


def build_sibling_imports(
    references: Sequence[str],
    *,
    target_file: str | None,
) -> tuple[tuple[str, str], ...]:
    """Render the sibling-imports tuple for a verb's ``ProposedAuthorOp``.

    Lifted from the original ``register_prior`` inline pattern so every
    verb supporting ``--file <sibling>.py`` can call the same helper.
    Returns an empty tuple when ``target_file`` is ``None`` or
    ``__init__.py`` (the writer skips the cross-file import insertion in
    that case anyway, but emitting an empty tuple keeps the verb shape
    uniform). Otherwise pairs each reference with an empty source-
    package marker that the writer interprets as ``default_package``
    (the target package's own import name).

    Note (audit §C.6): the empty-string source is the intentional shape
    — :func:`gaia.cli.commands.author._writer._select_new_imports`
    falls back through ``pkg = "" or default_package or ""`` so the
    sibling import lands on ``from <import_name> import <symbol>``. A
    caller wanting to override the source package can build the tuple
    by hand and pass a literal package path; the helper covers the
    common case.
    """
    if not target_file or target_file == "__init__.py":
        return ()
    # Deduplicate while preserving order — multiple verbs feed the same
    # reference more than once (e.g. ``compute`` lists conclusion_type
    # and fn and each given identifier; if a verb repeats one, the
    # writer would only honour the first anyway).
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for ref in references:
        if not ref or ref in seen:
            continue
        seen.add(ref)
        out.append((ref, ""))
    return tuple(out)


__all__ = [
    "PrewriteUnsafeError",
    "build_sibling_imports",
    "emit_syntax_error",
    "normalize_file_option",
    "parse_literal_or_identifier",
    "parse_metadata",
    "split_csv",
    "split_csv_idents",
]
