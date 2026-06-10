"""``gaia author list`` — snapshot the current authoring state of a Gaia package.

Walks every non-auxiliary ``.py`` file under ``src/<import_name>/`` as
Python AST (no engine import, no compile pipeline) and reports each
top-level author-verb statement: kind, binding name, content preview,
file/line, whether the binding is exported via ``__all__``. Reads
``[[tool.gaia.compositions]]`` entries from ``pyproject.toml`` for the
trailing compositions section.

The verb is read-only — it never writes to disk and does not share the
write/postwrite pipeline with the other 19 author verbs. The envelope
shape, ``--target`` / ``--file`` flag spellings, and exit-code semantics
match the rest of the author surface so an agent consumer can route
``gaia author list`` through the same dispatch table.

Statement shapes recognised at module scope (``tree.body`` only — author
verbs never nest under ``if`` / ``def`` / ``class``):

1. ``<name> = <callable>(...)`` — bound assignment. ``content`` is the
   first positional arg when it is a string literal, else ``None``.
2. Two-statement claim-with-label pair:
   ``my_claim = claim(...)`` followed by ``my_claim.label = "..."``.
   The follow-up ``.label = ...`` is folded into the same row.
3. Bare expression call (``<callable>(...)``) — only emitted when
   ``--unbound`` is set.

Anything else (tuple unpacking, nested scopes, non-author callables) is
skipped silently.

Auxiliary modules (``priors.py``, ``review.py``, ``reviews/<sub>.py``)
are skipped — these mirror the engine's
:func:`gaia.engine.packaging._is_auxiliary_source_module` rule (the
function is private; we replicate the rule with a code comment pointing
back at the canonical location).
"""

from __future__ import annotations

import ast
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import typer

from gaia.cli.commands.author._common import normalize_file_option
from gaia.cli.commands.author._envelope import (
    EXIT_OK,
    EXIT_SYSTEM_IO,
    AuthorResult,
    Diagnostic,
    emit,
    exit_code_for_diagnostic,
)

# ---------------------------------------------------------------------------- #
# Recognised author callables                                                  #
# ---------------------------------------------------------------------------- #

# Statement-emitting author verbs (callables that produce DSL objects bound at
# module scope). The list mirrors the 17 statement-emitting verbs plus the
# typed-term factories ``Variable`` / ``Constant``. Hyphenated cli verbs map
# to underscored callables in source (``depends-on`` → ``depends_on``); the
# output ``kind`` always uses the underscored callable form. ``composition``
# (and its deprecated ``compose`` alias) is NOT in this set — compositions
# live in pyproject.toml and are handled by the trailing compositions section.
_AUTHOR_CALLABLES: frozenset[str] = frozenset(
    {
        "claim",
        "note",
        "question",
        "equal",
        "contradict",
        "exclusive",
        "decompose",
        "derive",
        "observe",
        "compute",
        "infer",
        "associate",
        "parameter",
        "register_prior",
        "Variable",
        "Constant",
        "depends_on",
        "candidate_relation",
        "materialize",
    }
)


def _callable_to_kind(callable_name: str) -> str:
    """Map a callable name to its output ``kind`` value.

    ``Variable`` and ``Constant`` split into two distinct kinds (per
    spec); everything else maps callable name → kind 1:1 (already
    underscored).
    """
    if callable_name == "Variable":
        return "variable"
    if callable_name == "Constant":
        return "constant"
    return callable_name


# ---------------------------------------------------------------------------- #
# Auxiliary-source rule (mirrors gaia.engine.packaging._is_auxiliary_source_module)
# ---------------------------------------------------------------------------- #


def _is_auxiliary_source_module(parts: tuple[str, ...]) -> bool:
    """Return True for auxiliary modules excluded from the author surface.

    Mirrors :func:`gaia.engine.packaging._is_auxiliary_source_module`
    (engine-private). Author-list walks the same file set the engine
    skips when collecting DSL objects, so we replicate the rule here
    with a comment-pointer back at the canonical location. If the engine
    rule changes, update this helper to match.
    """
    if "reviews" in parts:
        return True
    return len(parts) == 1 and parts[0] in {"priors", "review"}


# ---------------------------------------------------------------------------- #
# Binding record                                                               #
# ---------------------------------------------------------------------------- #


@dataclass
class _Binding:
    """One author-verb statement extracted from a source file."""

    name: str | None  # None for bare-expression calls (``--unbound`` mode)
    kind: str
    file: str  # Path relative to the source root (e.g. ``"__init__.py"``)
    line: int  # 1-based line number of the statement
    content: str | None  # First positional string-literal arg, else None
    label: str | None = None  # Folded-in ``.label = "..."`` follow-up
    exported: bool | None = None  # True / False / None (dynamic __all__)
    shadowed_by: int | None = None  # Line of an overriding later assignment
    bare: bool = False  # True when emitted as bare-expression statement

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {
            "name": self.name,
            "kind": self.kind,
            "file": self.file,
            "line": self.line,
            "content": self.content,
            "exported": self.exported,
            "shadowed_by": self.shadowed_by,
        }
        if self.label is not None:
            out["label"] = self.label
        if self.bare:
            out["bare"] = True
        return out


@dataclass
class _FileScan:
    """Per-file extraction result."""

    relpath: str  # Path under the source root, e.g. ``"__init__.py"``
    bindings: list[_Binding] = field(default_factory=list)
    bare_calls: list[_Binding] = field(default_factory=list)
    all_state: str = "missing"  # "literal" / "missing" / "dynamic"
    all_names: frozenset[str] = field(default_factory=frozenset)
    warnings: list[str] = field(default_factory=list)
    parse_error: str | None = None


# ---------------------------------------------------------------------------- #
# AST extraction                                                               #
# ---------------------------------------------------------------------------- #


def _callable_name(call: ast.Call) -> str | None:
    """Return the bare callable name when shape is ``Name(...)`` or ``mod.Name(...)``.

    Returns the unqualified rightmost identifier; anything more exotic
    (``getattr(x, "y")(...)`` etc.) returns None.
    """
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _content_from_call(call: ast.Call) -> str | None:
    """Return the first positional arg when it is a string literal.

    Matches the author-verb convention where the leading positional
    carries the human-readable content (``claim("text", ...)``,
    ``note("text", ...)``, etc.). Anything non-string returns None.
    """
    if not call.args:
        return None
    first = call.args[0]
    if isinstance(first, ast.Constant) and isinstance(first.value, str):
        return first.value
    return None


def _extract_all_block(tree: ast.Module) -> tuple[str, frozenset[str]]:
    """Inspect ``tree`` for a top-level ``__all__ = [...]`` assignment.

    Returns ``(state, names)`` where ``state`` is one of:

    * ``"literal"`` — ``__all__`` is a list/tuple of string literals.
      ``names`` contains the literal entries.
    * ``"missing"`` — no top-level ``__all__`` found.
    * ``"dynamic"`` — ``__all__`` present but RHS is computed / not a
      literal list/tuple of strings.
    """
    target: ast.expr | None = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets
        ):
            target = node.value
            break
        if (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and node.target.id == "__all__"
            and node.value is not None
        ):
            target = node.value
            break
    if target is None:
        return "missing", frozenset()
    if not isinstance(target, (ast.List, ast.Tuple)):
        return "dynamic", frozenset()
    names: list[str] = []
    for elt in target.elts:
        if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
            names.append(elt.value)
        else:
            return "dynamic", frozenset()
    return "literal", frozenset(names)


def _is_string_attribute_assign(node: ast.Assign) -> tuple[str, str, str] | None:
    """Recognise ``<binding>.label = "<text>"`` follow-up shape.

    Returns ``(binding_name, attr, value)`` or None. Only the
    one-target / string-literal-RHS shape is matched, matching the
    ``claim``-with-label idiom emitted by ``gaia author claim --label``.
    """
    if len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Attribute):
        return None
    if not isinstance(target.value, ast.Name):
        return None
    if not isinstance(node.value, ast.Constant) or not isinstance(node.value.value, str):
        return None
    return target.value.id, target.attr, node.value.value


def _handle_bound_assignment(
    node: ast.Assign,
    *,
    relpath: str,
    scan: _FileScan,
    name_to_idx: dict[str, int],
) -> bool:
    """Try to interpret ``node`` as a ``<name> = <author-call>(...)`` binding.

    Returns True when consumed (recognised or recognised-but-skipped); the
    caller short-circuits further shape checks. Returns False when the
    shape doesn't match the bound-assignment pattern so the caller can
    try other shapes (e.g. ``.label = ...``).
    """
    if (
        len(node.targets) != 1
        or not isinstance(node.targets[0], ast.Name)
        or not isinstance(node.value, ast.Call)
    ):
        return False
    callable_name = _callable_name(node.value)
    if callable_name not in _AUTHOR_CALLABLES:
        return False
    binding_name = node.targets[0].id
    binding = _Binding(
        name=binding_name,
        kind=_callable_to_kind(callable_name),
        file=relpath,
        line=node.lineno,
        content=_content_from_call(node.value),
    )
    # Shadow detection: if a previous binding with the same name exists
    # in this file, stamp it.
    if binding_name in name_to_idx:
        prior_idx = name_to_idx[binding_name]
        scan.bindings[prior_idx].shadowed_by = node.lineno
    name_to_idx[binding_name] = len(scan.bindings)
    scan.bindings.append(binding)
    return True


def _handle_label_follow_up(
    node: ast.Assign,
    *,
    scan: _FileScan,
    name_to_idx: dict[str, int],
) -> bool:
    """Try to interpret ``node`` as a ``<binding>.label = "..."`` follow-up."""
    attr_match = _is_string_attribute_assign(node)
    if attr_match is None:
        return False
    target_name, attr, value = attr_match
    if attr == "label" and target_name in name_to_idx:
        scan.bindings[name_to_idx[target_name]].label = value
    return True


def _handle_bare_call(
    node: ast.Expr,
    *,
    relpath: str,
    scan: _FileScan,
) -> None:
    """Record a bare ``<author-call>(...)`` expression statement."""
    if not isinstance(node.value, ast.Call):
        return
    callable_name = _callable_name(node.value)
    if callable_name not in _AUTHOR_CALLABLES:
        return
    scan.bare_calls.append(
        _Binding(
            name=None,
            kind=_callable_to_kind(callable_name),
            file=relpath,
            line=node.lineno,
            content=_content_from_call(node.value),
            bare=True,
        )
    )


def _stamp_exported(scan: _FileScan) -> None:
    """Set ``exported`` on every binding now that ``__all__`` state is known."""
    for binding in scan.bindings:
        if scan.all_state == "dynamic":
            binding.exported = None
        elif scan.all_state == "missing":
            binding.exported = False
        else:
            binding.exported = binding.name in scan.all_names


def _scan_module(source: str, relpath: str) -> _FileScan:
    """Walk a module's top-level statements and extract author-verb bindings.

    Reassignment handling: when the same name binds twice (``foo = claim(...)``
    then ``foo = derive(...)``), the earlier binding is marked
    ``shadowed_by = <later_line>``; the later wins for output. We keep the
    earlier in the list (with the shadow pointer) so an agent can detect
    reassignment without re-running the scan.
    """
    scan = _FileScan(relpath=relpath)
    try:
        tree = ast.parse(source, filename=relpath)
    except SyntaxError as exc:
        scan.parse_error = f"{relpath}: line {exc.lineno or 0}: {exc.msg}"
        return scan

    all_state, all_names = _extract_all_block(tree)
    scan.all_state = all_state
    scan.all_names = all_names
    if all_state == "dynamic":
        scan.warnings.append(
            f"{relpath}: __all__ is dynamic / non-literal; exported = null for all bindings"
        )

    # Track binding name → index in scan.bindings so a later same-name
    # assignment can stamp a shadow pointer on the prior one.
    name_to_idx: dict[str, int] = {}

    for node in tree.body:
        if isinstance(node, ast.Assign):
            # Shape (1): bound assignment ``<name> = <callable>(...)``;
            # falls through to shape (2) when not a bound author call.
            if _handle_bound_assignment(node, relpath=relpath, scan=scan, name_to_idx=name_to_idx):
                continue
            # Shape (2): ``<binding>.label = "<text>"`` follow-up.
            _handle_label_follow_up(node, scan=scan, name_to_idx=name_to_idx)
            continue
        if isinstance(node, ast.Expr):
            # Shape (3): bare ``<callable>(...)`` as an expression statement.
            _handle_bare_call(node, relpath=relpath, scan=scan)

    _stamp_exported(scan)
    return scan


# ---------------------------------------------------------------------------- #
# File enumeration                                                             #
# ---------------------------------------------------------------------------- #


def _enumerate_source_files(source_root: Path) -> list[Path]:
    """Return the non-auxiliary ``.py`` files under ``source_root``.

    Mirrors the engine's package-load walk (sorted, recursive,
    auxiliary-skipped) without importing the engine module — keeps
    the verb pure-AST.
    """
    out: list[Path] = []
    for path in sorted(source_root.rglob("*.py")):
        relative = path.relative_to(source_root)
        if relative.name == "__init__.py":
            if relative.parent == Path("."):
                parts: tuple[str, ...] = ()
            else:
                parts = relative.parent.parts
        else:
            parts = relative.with_suffix("").parts
        # The root __init__.py (parts == ()) is always included.
        if parts and _is_auxiliary_source_module(parts):
            continue
        out.append(path)
    return out


# ---------------------------------------------------------------------------- #
# Target validation                                                            #
# ---------------------------------------------------------------------------- #


@dataclass
class _ResolvedTarget:
    """Successfully validated target directory."""

    target_root: Path
    pyproject: Path
    source_root: Path
    import_name: str
    project_name: str


def _resolve_target(target_root: Path) -> tuple[_ResolvedTarget | None, Diagnostic | None]:
    """Validate the target directory and return a ``_ResolvedTarget`` or error."""
    if not target_root.exists():
        return None, Diagnostic(
            kind="prewrite.target_missing",
            level="error",
            message=f"target path does not exist: {target_root}",
            source="prewrite",
            where={"target": str(target_root)},
        )
    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return None, Diagnostic(
            kind="prewrite.target_no_pyproject",
            level="error",
            message=(f"no pyproject.toml under {target_root}; expected a Gaia knowledge package"),
            source="prewrite",
            where={"target": str(target_root)},
        )
    try:
        config = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return None, Diagnostic(
            kind="prewrite.target_bad_toml",
            level="error",
            message=f"pyproject.toml is not valid TOML: {exc}",
            source="prewrite",
            where={"pyproject": str(pyproject)},
        )
    gaia_section = config.get("tool", {}).get("gaia", {})
    if gaia_section.get("type") != "knowledge-package":
        return None, Diagnostic(
            kind="prewrite.target_not_gaia_package",
            level="error",
            message=(
                "target package is not a Gaia knowledge package: "
                "[tool.gaia].type must equal 'knowledge-package'"
            ),
            source="prewrite",
            where={"pyproject": str(pyproject)},
        )
    project_name = config.get("project", {}).get("name")
    if not isinstance(project_name, str) or not project_name:
        return None, Diagnostic(
            kind="prewrite.target_invalid",
            level="error",
            message="[project].name is required in pyproject.toml",
            source="prewrite",
            where={"pyproject": str(pyproject)},
        )
    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    candidates = [target_root / import_name, target_root / "src" / import_name]
    source_root = next((c for c in candidates if c.exists()), None)
    if source_root is None:
        return None, Diagnostic(
            kind="prewrite.target_no_source_root",
            level="error",
            message=(
                f"package source directory '{import_name}/' not found "
                "(expected at one of: "
                + ", ".join(str(c.relative_to(target_root)) + "/" for c in candidates)
                + ")"
            ),
            source="prewrite",
            where={"import_name": import_name, "target": str(target_root)},
        )
    init_py = source_root / "__init__.py"
    if not init_py.exists():
        return None, Diagnostic(
            kind="prewrite.target_no_init_py",
            level="error",
            message=f"missing source entrypoint: {init_py}",
            source="prewrite",
            where={"init_py": str(init_py)},
        )
    return (
        _ResolvedTarget(
            target_root=target_root,
            pyproject=pyproject,
            source_root=source_root,
            import_name=import_name,
            project_name=project_name,
        ),
        None,
    )


# ---------------------------------------------------------------------------- #
# Compositions reading                                                         #
# ---------------------------------------------------------------------------- #


def _read_compositions(pyproject: Path) -> list[dict[str, Any]]:
    """Read ``[[tool.gaia.compositions]]`` entries from pyproject.toml.

    Returns a list of dicts shaped
    ``{"name": str, "kind": "composition", "target": str, "version": str}``.
    The ``kind`` field is always ``"composition"`` (the deprecated
    ``compose`` alias shares the same registration table).
    ``target`` is the function reference recorded at registration time
    (e.g. ``"galileo_v05_compositions.galileo_v05"``); we render it as
    ``<module>.<function>`` if both are present, else the file path.

    See :func:`gaia.cli.commands.author.compose._update_compositions_table`
    for the writer side — this function is its symmetric reader.
    """
    try:
        config = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError):
        return []
    raw = config.get("tool", {}).get("gaia", {}).get("compositions", [])
    if not isinstance(raw, list):
        return []
    out: list[dict[str, Any]] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        name = entry.get("name")
        version = entry.get("version")
        file_path = entry.get("file")
        function = entry.get("function")
        if not isinstance(name, str):
            continue
        target_repr: str
        if isinstance(function, str) and isinstance(file_path, str):
            target_repr = f"{file_path}:{function}"
        elif isinstance(file_path, str):
            target_repr = file_path
        else:
            target_repr = ""
        out.append(
            {
                "name": name,
                "kind": "composition",
                "target": target_repr,
                "version": version if isinstance(version, str) else "",
            }
        )
    return out


# ---------------------------------------------------------------------------- #
# Human rendering                                                              #
# ---------------------------------------------------------------------------- #


def _abbrev(content: str | None, width: int = 40) -> str:
    """Shorten ``content`` to ``width`` chars, suffixing ``…`` on overflow."""
    if content is None:
        return "(no content)"
    flat = " ".join(content.split())
    if len(flat) <= width:
        return flat
    return flat[: width - 1] + "…"


def _render_human(
    *,
    rows: list[_Binding],
    summary: dict[str, Any],
    compositions: list[dict[str, Any]],
    warnings_list: list[str],
) -> str:
    """Render the human (non-JSON) output."""
    lines: list[str] = []

    if rows:
        header = f"{'Kind':<18} | {'Name':<22} | {'Content (abbrev)':<40} | {'File':<24} | Exported"
        separator = "-" * 18 + "-+-" + "-" * 22 + "-+-" + "-" * 40 + "-+-" + "-" * 24 + "-+--------"
        lines.append(header)
        lines.append(separator)
        for binding in rows:
            name_repr = binding.name if binding.name is not None else "(unbound)"
            content_repr = _abbrev(binding.content)
            if binding.label is not None:
                content_repr = (content_repr + f"  [label: {binding.label!r}]")[:40]
            if binding.shadowed_by is not None:
                name_repr = name_repr + " (shadowed)"
            exported = "—" if binding.exported is None else ("yes" if binding.exported else "no")
            lines.append(
                f"{binding.kind:<18} | {name_repr:<22} | "
                f"{content_repr:<40} | "
                f"{binding.file:<24} | {exported}"
            )
        lines.append("")

    total = summary["total"]
    by_kind: dict[str, int] = summary["by_kind"]
    files_count = summary["files"]
    file_word = "file" if files_count == 1 else "files"
    binding_word = "binding" if total == 1 else "bindings"
    breakdown = ", ".join(f"{count} {kind}" for kind, count in sorted(by_kind.items()))
    summary_line = f"{total} {binding_word} across {files_count} {file_word}"
    if breakdown:
        summary_line += f": {breakdown}"
    lines.append(summary_line)

    exported_count = summary.get("exported", 0)
    if total:
        lines.append(f"Exported via __all__: {exported_count}/{total}")

    if compositions:
        lines.append("")
        lines.append("Compositions registered in pyproject.toml:")
        for entry in compositions:
            name = entry.get("name", "")
            kind = entry.get("kind", "composition")
            target = entry.get("target", "")
            lines.append(f"  {name:<20} ({kind:<12}) {target}")
    elif total == 0 and not warnings_list:
        # Empty package — keep output clean.
        pass

    for warning in warnings_list:
        lines.append(f"warning: {warning}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------- #
# list_command helpers                                                         #
# ---------------------------------------------------------------------------- #


def _emit_target_error(diag: Diagnostic, *, target_root: Path, human: bool) -> None:
    """Emit a target-resolution failure envelope."""
    result = AuthorResult(
        verb="list",
        status="error",
        code=EXIT_SYSTEM_IO,
        payload={"target": str(target_root)},
        diagnostics=[diag],
    )
    emit(result, human=human)


def _select_scanned_files(
    *,
    resolved: _ResolvedTarget,
    target_file_rel: str | None,
    target_root: Path,
    human: bool,
    warnings_list: list[str],
) -> list[Path] | None:
    """Determine which files to scan, or emit + return None on failure."""
    if target_file_rel is None:
        return _enumerate_source_files(resolved.source_root)

    # ``--file <relative>`` resolves against the ``authored/`` submodule
    # first (the canonical home for CLI-authored statements), falling back
    # to the package root for hand-authored modules. This mirrors the
    # author write surface, where ``--file priors.py`` routes to
    # ``authored/priors.py``.
    authored_candidate = resolved.source_root / "authored" / target_file_rel
    candidate = (
        authored_candidate
        if authored_candidate.exists()
        else resolved.source_root / target_file_rel
    )
    if not candidate.exists():
        diag = Diagnostic(
            kind="prewrite.target_missing",
            level="error",
            message=(
                f"--file points at {candidate} which does not exist under "
                f"the source root ({resolved.source_root})"
            ),
            source="prewrite",
            where={"file": target_file_rel, "source_root": str(resolved.source_root)},
        )
        _emit_target_error(diag, target_root=target_root, human=human)
        return None

    # Auxiliary-file warning: the engine reserves ``priors.py`` /
    # ``review.py`` / ``reviews/`` as Knowledge-free zones; warn but still
    # scan (some agents may still want the empty result). The role applies
    # by basename regardless of the ``authored/`` prefix, so evaluate the
    # path relative to the authored root when the candidate lives there.
    authored_root = resolved.source_root / "authored"
    try:
        rel = candidate.resolve().relative_to(authored_root.resolve())
    except ValueError:
        try:
            rel = candidate.resolve().relative_to(resolved.source_root.resolve())
        except ValueError:
            rel = Path(target_file_rel)
    if rel.name == "__init__.py":
        parts: tuple[str, ...] = rel.parent.parts
    else:
        parts = rel.with_suffix("").parts
    if parts and _is_auxiliary_source_module(parts):
        warnings_list.append(
            f"--file {target_file_rel} is an auxiliary module "
            "(engine skips it on load); scanning anyway"
        )
    return [candidate]


def _run_scans(
    *,
    scanned_files: list[Path],
    source_root: Path,
) -> tuple[list[_FileScan], list[Diagnostic], list[str]]:
    """Run AST scans across the given paths; return (scans, parse_errors, warnings)."""
    file_scans: list[_FileScan] = []
    parse_errors: list[Diagnostic] = []
    warnings_list: list[str] = []
    for file_path in scanned_files:
        try:
            source = file_path.read_text()
        except OSError as exc:
            parse_errors.append(
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"failed to read {file_path}: {exc}",
                    source="prewrite",
                    where={"file": str(file_path)},
                )
            )
            continue
        try:
            relpath = str(file_path.relative_to(source_root))
        except ValueError:
            relpath = file_path.name
        scan = _scan_module(source, relpath)
        file_scans.append(scan)
        if scan.parse_error is not None:
            parse_errors.append(
                Diagnostic(
                    kind="prewrite.syntax",
                    level="error",
                    message=scan.parse_error,
                    source="prewrite",
                    where={"file": relpath},
                )
            )
        warnings_list.extend(scan.warnings)
    return file_scans, parse_errors, warnings_list


def _assemble_rows(
    *, file_scans: list[_FileScan], unbound: bool, kind: str | None
) -> list[_Binding]:
    """Flatten per-file scans into a single row list with kind filter applied."""
    rows: list[_Binding] = []
    for scan in file_scans:
        rows.extend(scan.bindings)
        if unbound:
            rows.extend(scan.bare_calls)
    if kind is not None:
        rows = [b for b in rows if b.kind == kind]
    return rows


def _build_summary(rows: list[_Binding], compositions_count: int) -> dict[str, Any]:
    """Build the ``summary`` sub-dict for the envelope payload."""
    by_kind: dict[str, int] = {}
    for binding in rows:
        by_kind[binding.kind] = by_kind.get(binding.kind, 0) + 1
    return {
        "total": len(rows),
        "by_kind": by_kind,
        "exported": sum(1 for b in rows if b.exported is True),
        "files": len({b.file for b in rows}),
        "compositions": compositions_count,
    }


def _emit_outcome(
    *,
    target_root: Path,
    resolved: _ResolvedTarget,
    rows: list[_Binding],
    compositions: list[dict[str, Any]],
    summary: dict[str, Any],
    warnings_list: list[str],
    parse_errors: list[Diagnostic],
    human: bool,
) -> None:
    """Render the envelope (JSON or human) and raise typer.Exit."""
    payload: dict[str, Any] = {
        "target": str(target_root),
        "import_name": resolved.import_name,
        "bindings": [b.to_dict() for b in rows],
        "compositions": compositions,
        "summary": summary,
    }
    if parse_errors:
        for diag in parse_errors:
            print(diag.message, file=sys.stderr)
        result = AuthorResult(
            verb="list",
            status="error",
            code=exit_code_for_diagnostic(parse_errors[0].kind),
            payload=payload,
            warnings=warnings_list,
            diagnostics=parse_errors,
        )
        if human:
            text = _render_human(
                rows=rows,
                summary=summary,
                compositions=compositions,
                warnings_list=warnings_list + [d.message for d in parse_errors],
            )
            typer.echo(text)
            raise typer.Exit(result.code)
        emit(result, human=False)
        return
    if human:
        text = _render_human(
            rows=rows,
            summary=summary,
            compositions=compositions,
            warnings_list=warnings_list,
        )
        typer.echo(text)
        raise typer.Exit(EXIT_OK)
    result = AuthorResult(
        verb="list",
        status="ok",
        code=EXIT_OK,
        payload=payload,
        warnings=warnings_list,
    )
    emit(result, human=False)


# ---------------------------------------------------------------------------- #
# Verb entry point                                                             #
# ---------------------------------------------------------------------------- #


def list_command(
    target: str = typer.Option(
        ".", "--target", help="Path to the target Gaia package (default: cwd)."
    ),
    file: str | None = typer.Option(
        None,
        "--file",
        help=(
            "Relative path under ``src/<import_name>/`` to scope the scan "
            "to a single source file (e.g. ``__init__.py`` or "
            "``observations.py``). Default: every non-auxiliary ``.py`` "
            "file under the source root."
        ),
    ),
    kind: str | None = typer.Option(
        None,
        "--kind",
        help=(
            "Filter to one binding kind (e.g. ``claim`` / ``derive`` / "
            "``variable``). The value matches the ``kind`` column / "
            "JSON field — use the underscored callable form."
        ),
    ),
    unbound: bool = typer.Option(
        False,
        "--unbound",
        help=(
            "Include bare-expression statements (calls without an LHS "
            "binding) in the output. Default off — bare calls are "
            "frequently scaffolding noise."
        ),
    ),
    human: bool = typer.Option(
        False,
        "--human",
        help="Render output as a human-readable table instead of the JSON envelope.",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    """List author-verb bindings in a Gaia DSL package.

    Walks every ``.py`` file under the package source root as Python AST
    (no engine import, no compile pipeline) and reports every top-level
    author-verb statement: kind, binding name, content preview, file,
    line, and whether the binding is exported via ``__all__``. Reads
    ``[[tool.gaia.compositions]]`` entries from ``pyproject.toml`` for
    the trailing compositions section.

    The verb is read-only; it never writes to disk and does not share
    the write/postwrite pipeline used by the other 19 author verbs.

    Example:
        gaia author list --target ./my-pkg-gaia --human
        gaia author list --target ./my-pkg --kind claim --json
    """
    del json_  # JSON-vs-human is governed by --human; --json is a courtesy alias.

    target_root = Path(target).resolve()

    resolved, target_diag = _resolve_target(target_root)
    if resolved is None:
        # _resolve_target guarantees a diagnostic when resolved is None.
        assert target_diag is not None
        _emit_target_error(target_diag, target_root=target_root, human=human)
        return

    warnings_list: list[str] = []
    target_file_rel = normalize_file_option(file)
    scanned_files = _select_scanned_files(
        resolved=resolved,
        target_file_rel=target_file_rel,
        target_root=target_root,
        human=human,
        warnings_list=warnings_list,
    )
    if scanned_files is None:
        return

    file_scans, parse_errors, scan_warnings = _run_scans(
        scanned_files=scanned_files, source_root=resolved.source_root
    )
    warnings_list.extend(scan_warnings)

    rows = _assemble_rows(file_scans=file_scans, unbound=unbound, kind=kind)
    compositions = _read_compositions(resolved.pyproject)
    summary = _build_summary(rows, len(compositions))

    _emit_outcome(
        target_root=target_root,
        resolved=resolved,
        rows=rows,
        compositions=compositions,
        summary=summary,
        warnings_list=warnings_list,
        parse_errors=parse_errors,
        human=human,
    )


__all__ = ["list_command"]
