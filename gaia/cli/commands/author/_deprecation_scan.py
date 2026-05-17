"""AST-driven discovery of deprecated DSL surface names (R4·❓C=A).

R3 carried a hand-curated ``_DEPRECATED_DSL_NAMES`` dict at the top of
:mod:`._prewrite`. That set was authored once against v0.5 engine
``DeprecationWarning`` sites and required manual sync if the engine added
or removed deprecations. R4 lifts that constant into a one-time AST scan
of the engine DSL source so the warning catalog stays aligned with the
shipping engine surface without per-engine-release maintenance.

Engine pattern survey
---------------------

The v0.5 engine does NOT use a ``@deprecated`` decorator (neither
``typing_extensions.deprecated`` nor a custom one). Deprecations are
expressed via direct ``warnings.warn(..., DeprecationWarning, ...)``
calls inside the deprecated function's body. Two shapes:

1. **Direct** — the call lives in the function body itself, with the
   deprecated function's name + replacement hint baked into the message
   string. Example
   (``gaia/engine/lang/dsl/strategies.py::noisy_and``)::

       def noisy_and(...):
           warnings.warn(
               "noisy_and() is deprecated for v0.5+ authoring; use derive() "
               "for deterministic reasoning ...",
               DeprecationWarning,
               stacklevel=2,
           )

2. **Indirect via helper** — the function calls a private helper
   (``_warn_deprecated_note_alias`` / ``_warn_deprecated_operator`` /
   ``_warn_deprecated_helper``) that owns the ``warnings.warn(...)``
   itself. The deprecated name + replacement hint live in the helper
   call's positional args. Example
   (``gaia/engine/lang/dsl/operators.py::contradiction``)::

       def contradiction(...):
           _warn_deprecated_operator(
               "contradiction",
               "contradict(a, b, rationale=...) for reviewable relations ...",
           )

This module recognises both shapes and unifies them into a single name
→ (replacement, since-version) mapping consumed by
:mod:`._prewrite._detect_deprecated_refs`.

Caching + fallback
------------------

The scan is invoked lazily on first access via :func:`get_deprecated_names`
and the result is cached for the lifetime of the cli process. Any name
that the AST scan does NOT pick up (e.g., a future engine deprecation
shape we don't model yet) is filled from a small ``_R3_FALLBACK_NAMES``
dict carried over from R3's hand-curated set; the fallback never wins
over a hit from the live scan.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

# Engine DSL source path. Resolved against the installed ``gaia`` package
# location so the scan stays portable across editable installs / wheel
# layouts.
import gaia.engine.lang.dsl as _engine_dsl_pkg

_DSL_DIR = Path(_engine_dsl_pkg.__file__).resolve().parent


# Helper functions in the engine whose first positional arg is the
# deprecated function-name + second positional arg is the replacement
# hint. Discovered empirically from the v0.5 source:
#
#   * ``_warn_deprecated_note_alias(name)`` — knowledge.py — single arg
#     (no replacement; implicitly "note()"); we hard-code the
#     replacement for this helper since it doesn't carry one.
#   * ``_warn_deprecated_helper(name, replacement)`` — propositional.py
#   * ``_warn_deprecated_operator(name, replacement)`` — operators.py
_HELPER_NAMES_WITH_REPLACEMENT: frozenset[str] = frozenset(
    {"_warn_deprecated_helper", "_warn_deprecated_operator"}
)
_HELPER_NAMES_FIXED_REPLACEMENT: dict[str, str] = {
    "_warn_deprecated_note_alias": "note()",
}


# Regex used to fish a short replacement hint out of a direct
# ``warnings.warn`` message. The engine's strings follow a
# ``"<name>() is deprecated ... ; use <replacement> ..."`` convention.
_USE_PATTERN = re.compile(r"\buse\s+([^.;]+?)(?:\s+for\b|[.;]|$)", re.IGNORECASE)


# Carry-over fallback from R3's hand-curated set. Used only for names
# the AST scan misses entirely (defensive); the scan is authoritative
# for any name it does find. Keys = deprecated name, values =
# (replacement, since-version).
_R3_FALLBACK_NAMES: dict[str, tuple[str, str]] = {
    # Note aliases (engine knowledge.py).
    "context": ("note", "0.5"),
    "setting": ("note", "0.5"),
    # Propositional (engine propositional.py).
    "not_": ("claim(formula=lnot(ClaimAtom(...)))", "0.5"),
    "and_": ("claim(formula=land(ClaimAtom(...), ...))", "0.5"),
    "or_": ("claim(formula=lor(ClaimAtom(...), ...))", "0.5"),
    # Operator helpers (engine operators.py).
    "contradiction": ("contradict()", "0.5"),
    "equivalence": ("equal()", "0.5"),
    "complement": ("exclusive()", "0.5"),
    "disjunction": ("lor()", "0.5"),
    # Strategies (engine strategies.py).
    "noisy_and": ("derive() / infer()", "0.5"),
}


# Cache of scan result so repeated cli invocations within one process
# (e.g. test runners) reuse the same dict.
_CACHED: dict[str, tuple[str, str]] | None = None


def get_deprecated_names() -> dict[str, tuple[str, str]]:
    """Return name → (replacement-hint, since-version) for deprecated DSL names.

    First call triggers an AST scan of ``gaia/engine/lang/dsl/**.py``;
    subsequent calls return the cached result. The mapping merges:

    1. live scan hits (authoritative);
    2. ``_R3_FALLBACK_NAMES`` entries for any name the scan did not pick
       up (defensive — catches engine deprecations expressed in a shape
       the scanner does not yet model).
    """
    global _CACHED
    if _CACHED is None:
        _CACHED = _scan_engine_for_deprecations()
        for name, replacement_tuple in _R3_FALLBACK_NAMES.items():
            _CACHED.setdefault(name, replacement_tuple)
    return _CACHED


def _scan_engine_for_deprecations() -> dict[str, tuple[str, str]]:
    """Walk every ``*.py`` under the engine DSL package and collect deprecations."""
    out: dict[str, tuple[str, str]] = {}
    if not _DSL_DIR.exists() or not _DSL_DIR.is_dir():
        return out
    for path in sorted(_DSL_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text())
        except (OSError, SyntaxError):
            continue
        _collect_from_module(tree, out=out)
    return out


def _collect_from_module(tree: ast.Module, *, out: dict[str, tuple[str, str]]) -> None:
    """Append deprecated-name entries discovered in one module's AST to ``out``."""
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        if node.name.startswith("_"):
            # Skip helper functions (they implement the warning, not declare it).
            continue
        entry = _entry_for_function(node)
        if entry is None:
            continue
        name, replacement = entry
        # First win for a name wins (rare; engine has no aliasing of
        # deprecations across files we've seen, but defensive).
        out.setdefault(name, (replacement, "0.5"))


def _entry_for_function(fn: ast.FunctionDef) -> tuple[str, str] | None:
    """Return ``(name, replacement)`` if ``fn``'s body emits a DeprecationWarning.

    Recognises two shapes:

    * **Direct** — ``warnings.warn(<msg>, DeprecationWarning, ...)``
      inside the function body. ``name = fn.name``; replacement parsed
      from ``<msg>``.
    * **Indirect** — ``_warn_deprecated_<kind>(<name>, <replacement>)``
      call. ``name`` and ``replacement`` come from the call's positional
      args.
    """
    for stmt in ast.walk(fn):
        # Direct: warnings.warn(..., DeprecationWarning, ...).
        if isinstance(stmt, ast.Call) and _is_warnings_warn(stmt.func):
            if not _has_deprecation_warning_arg(stmt):
                continue
            message = _first_string_arg(stmt)
            if message is None:
                continue
            replacement = _extract_replacement_hint(message) or "see DSL docs"
            return fn.name, replacement
        # Indirect: _warn_deprecated_*(name, replacement).
        if isinstance(stmt, ast.Call) and isinstance(stmt.func, ast.Name):
            helper_name = stmt.func.id
            if helper_name in _HELPER_NAMES_WITH_REPLACEMENT:
                args = [_constant_str(arg) for arg in stmt.args]
                if len(args) >= 2 and args[0] and args[1]:
                    return args[0], args[1]
                continue
            if helper_name in _HELPER_NAMES_FIXED_REPLACEMENT:
                args = [_constant_str(arg) for arg in stmt.args]
                if args and args[0]:
                    return args[0], _HELPER_NAMES_FIXED_REPLACEMENT[helper_name]
                continue
    return None


def _is_warnings_warn(node: ast.expr) -> bool:
    """Return ``True`` when ``node`` is ``warnings.warn`` (bare or attribute)."""
    if isinstance(node, ast.Attribute):
        return (
            node.attr == "warn" and isinstance(node.value, ast.Name) and node.value.id == "warnings"
        )
    return False


def _has_deprecation_warning_arg(call: ast.Call) -> bool:
    """Return ``True`` when ``call`` references ``DeprecationWarning`` in any arg."""
    for arg in call.args:
        if isinstance(arg, ast.Name) and arg.id == "DeprecationWarning":
            return True
        if isinstance(arg, ast.Attribute) and arg.attr == "DeprecationWarning":
            return True
    return False


def _first_string_arg(call: ast.Call) -> str | None:
    """Return the first positional arg of ``call`` as a string literal, if any."""
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    if isinstance(first, ast.JoinedStr):  # f-string
        parts: list[str] = []
        for piece in first.values:
            if isinstance(piece, ast.Constant) and isinstance(piece.value, str):
                parts.append(piece.value)
            elif isinstance(piece, ast.FormattedValue):
                parts.append("<expr>")
        return "".join(parts)
    return None


def _constant_str(node: ast.expr) -> str | None:
    """Return the constant string value of ``node`` if it is one."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _extract_replacement_hint(message: str) -> str | None:
    """Pull a short replacement hint from a deprecation message string.

    Heuristic: look for the first occurrence of ``"use <X>"`` and return
    ``<X>`` up to the next sentence boundary. Engine messages follow this
    pattern by convention. If nothing matches, return ``None`` so the
    caller can fall back to a generic hint.
    """
    match = _USE_PATTERN.search(message)
    if match is None:
        return None
    return match.group(1).strip().rstrip(",")


__all__ = ["get_deprecated_names"]
