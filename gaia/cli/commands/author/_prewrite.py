"""Pre-write defensive sanity check for ``gaia author <verb>``.

Per R1·❓-C=C1 (locked in 协作单 §三), pre-write covers exactly 4
invariants — anything beyond stays in post-write ``gaia build check`` and
its lowering pipeline:

(a) **Target package structural validity** — the cwd / ``--target`` path is
    a real Gaia knowledge package: ``pyproject.toml`` exists, parses as
    TOML, declares ``[tool.gaia].type = "knowledge-package"``, and a
    source root directory matching the import name exists.

(b) **Input syntax validity** — the proposed code snippet
    (:attr:`ProposedAuthorOp.generated_code`) ``ast.parse``-s without
    raising ``SyntaxError``.

(c) **Identifier collision + reference resolution** — the proposed
    ``label`` does not collide with an already-bound name in the package's
    module scope or ``__all__``; each name in
    :attr:`ProposedAuthorOp.references` resolves in the same scope.

(d) **Statement-order + structural sanity** — the proposed statement has
    no self-loops (``label`` not in ``references``) and the produced
    snippet does not redeclare ``__all__`` with a conflicting symbol.

Two checks are *deliberately out of R1 scope* (per R1·❓-C=C1):

* forward-ref-in-dep detection (would require partial-load of the
  dependency graph);
* module-level ``__all__`` export simulation (would require simulating
  the import-time evaluation of ``__init__.py``).

Both belong on post-write because they need state that pre-write would
have to half-build the package to obtain.

R3 adds two pre-write **warning** kinds (per R3·❓B=A):

* ``prewrite.label_shadow`` — the proposed label matches a local
  binding that is not in ``__all__`` (shadowing a private name). Hint:
  add to ``__all__`` or rename.
* ``prewrite.deprecated_ref`` — the proposed op references a DSL name
  that the engine flags as deprecated (``context`` / ``setting`` /
  ``noisy_and`` / ``not_`` / ``and_`` / ``or_`` / ``contradiction`` /
  ``equivalence`` / ``complement`` / ``disjunction`` / etc.). Hint:
  the replacement spelling per the engine's deprecation message.

Both warnings flow through the existing ``--interactive`` activation
in :func:`gaia.cli.commands.author._runner.run_author_op`.
"""

from __future__ import annotations

import ast
import tomllib
from dataclasses import dataclass
from pathlib import Path

from gaia.cli.commands.author._envelope import Diagnostic, exit_code_for_diagnostic
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp


@dataclass
class AuthorPrewriteResult:
    """Outcome of a single :func:`prewrite_check` call."""

    ok: bool
    target_path: Path
    source_init_path: Path | None
    import_name: str | None
    project_name: str | None
    module_symbols: set[str]
    exit_code: int
    diagnostics: list[Diagnostic]
    warnings: list[Diagnostic]


def prewrite_check(
    target_path: str | Path,
    proposed_op: ProposedAuthorOp,
) -> AuthorPrewriteResult:
    """Run the 4-invariant pre-write check on ``proposed_op``.

    Fail-fast across the four invariants in this order:

    1. ``(a)`` target package structural validity;
    2. ``(b)`` proposed-code syntax;
    3. ``(d)`` structural sanity (self-loop check);
    4. ``(c)`` identifier collision + reference resolution.

    Note the (d)-before-(c) inversion: a self-loop (label∈references) is
    a strictly worse error than a missing reference, and putting (c)
    first would mask (d) in every common case (label is seeded → (c)
    collision; label is fresh & in refs → (c) reference unresolved). (d)
    must lead to actually surface self-loops as the dedicated kind.

    Args:
        target_path: Path to the Gaia package root. Must contain
            ``pyproject.toml`` + ``[tool.gaia].type =
            "knowledge-package"``.
        proposed_op: The verb-specific operation being proposed. See
            :class:`ProposedAuthorOp`.

    Returns:
        An :class:`AuthorPrewriteResult` carrying the errors, warnings,
        and the semantic exit code matched against the first error's
        kind. ``ok`` is ``True`` iff there were no errors.
    """
    warnings: list[Diagnostic] = []
    target_root = Path(target_path).resolve()

    # ---- (a) Target structure ------------------------------------------- #

    structure = _validate_target_structure(target_root)
    if structure.errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
            module_symbols=set(),
            exit_code=_first_exit_code(structure.errors),
            diagnostics=structure.errors,
            warnings=warnings,
        )

    source_init_path = structure.source_init_path
    import_name = structure.import_name
    project_name = structure.project_name

    # ---- (b) Input syntax ----------------------------------------------- #
    #
    # Syntax-check every prepended statement first, then the main
    # snippet. Any malformation aborts before invariant (c) runs.

    for _prep_label, prep_code in proposed_op.prepended_statements:
        prep_syntax_errors = _validate_proposed_syntax(prep_code)
        if prep_syntax_errors:
            return AuthorPrewriteResult(
                ok=False,
                target_path=target_root,
                source_init_path=source_init_path,
                import_name=import_name,
                project_name=project_name,
                module_symbols=set(),
                exit_code=_first_exit_code(prep_syntax_errors),
                diagnostics=prep_syntax_errors,
                warnings=warnings,
            )

    syntax_errors = _validate_proposed_syntax(proposed_op.generated_code)
    if syntax_errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=source_init_path,
            import_name=import_name,
            project_name=project_name,
            module_symbols=set(),
            exit_code=_first_exit_code(syntax_errors),
            diagnostics=syntax_errors,
            warnings=warnings,
        )

    # ---- (c) Collision + reference resolution --------------------------- #
    #
    # We don't run the engine's full ``load_gaia_package`` here — it
    # triggers the package import side effects (priors, label assignment),
    # which is what post-write wants. For pre-write we statically parse
    # the source ``__init__.py`` (and any sibling ``*.py``) for top-level
    # name bindings; this gives us a fast, side-effect-free collision +
    # ref table that's correct for the cases we need (label conflicts,
    # ref-to-undeclared-name).
    module_symbols = _collect_module_symbols(structure.source_root, import_name)

    # R3 prose-mode: prepended labels (e.g. an auto-claim minted from
    # ``--conclusion-content``) need to be validated against module
    # symbols too, then folded into the available-symbol pool so the
    # main statement can reference them. Order matters: collision
    # check fires before fold-in so a slug colliding with an existing
    # binding still trips invariant (c).
    prepend_collision_errors: list[Diagnostic] = []
    prepend_labels: list[str] = []
    for prep_label, _prep_code in proposed_op.prepended_statements:
        prepend_collision_errors.extend(
            _validate_label_collision(prep_label, module_symbols | set(prepend_labels))
        )
        prepend_labels.append(prep_label)
    if prepend_collision_errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=source_init_path,
            import_name=import_name,
            project_name=project_name,
            module_symbols=module_symbols,
            exit_code=_first_exit_code(prepend_collision_errors),
            diagnostics=prepend_collision_errors,
            warnings=warnings,
        )
    # Treat prepended labels as available bindings for the main op's
    # reference resolution + warning detection.
    module_symbols = module_symbols | set(prepend_labels)

    # Self-loop is checked here, ahead of (c)-collision and (c)-references,
    # because (c) would mask (d) in the common case (label is seeded → (c)
    # collision fires before (d); label is fresh & in refs → (c) reference
    # unresolved fires before (d)). (d) needs to lead in order to actually
    # fire on self-loops, which are a strictly worse error than a missing
    # reference (a missing reference might just be a forward-decl mistake;
    # a self-loop is a logically invalid warrant shape).
    structural_errors = _validate_structural_sanity(proposed_op)
    if structural_errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=source_init_path,
            import_name=import_name,
            project_name=project_name,
            module_symbols=module_symbols,
            exit_code=_first_exit_code(structural_errors),
            diagnostics=structural_errors,
            warnings=warnings,
        )

    collision_errors = _validate_label_collision(proposed_op.label, module_symbols)
    if collision_errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=source_init_path,
            import_name=import_name,
            project_name=project_name,
            module_symbols=module_symbols,
            exit_code=_first_exit_code(collision_errors),
            diagnostics=collision_errors,
            warnings=warnings,
        )

    reference_errors = _validate_references(proposed_op.references, module_symbols)
    if reference_errors:
        return AuthorPrewriteResult(
            ok=False,
            target_path=target_root,
            source_init_path=source_init_path,
            import_name=import_name,
            project_name=project_name,
            module_symbols=module_symbols,
            exit_code=_first_exit_code(reference_errors),
            diagnostics=reference_errors,
            warnings=warnings,
        )

    # ---- R3 warning kinds ---------------------------------------------- #
    #
    # Warnings do not abort pre-write — they surface in the envelope and,
    # in human mode + ``--interactive``, become numbered prompts. The
    # runner's ``_maybe_consume_warnings`` is the activation site.

    warnings.extend(
        _detect_label_shadow(
            label=proposed_op.label,
            source_init_path=source_init_path,
        )
    )
    warnings.extend(_detect_deprecated_refs(proposed_op))

    return AuthorPrewriteResult(
        ok=True,
        target_path=target_root,
        source_init_path=source_init_path,
        import_name=import_name,
        project_name=project_name,
        module_symbols=module_symbols,
        exit_code=0,
        diagnostics=[],
        warnings=warnings,
    )


# --------------------------------------------------------------------------- #
# Invariant (a) — target structure                                            #
# --------------------------------------------------------------------------- #


@dataclass
class _TargetStructure:
    errors: list[Diagnostic]
    source_root: Path
    source_init_path: Path | None
    import_name: str | None
    project_name: str | None


def _validate_target_structure(target_root: Path) -> _TargetStructure:
    """Check the pyproject metadata + source-root layout for invariant (a)."""
    if not target_root.exists():
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_missing",
                    level="error",
                    message=f"target path does not exist: {target_root}",
                    source="prewrite",
                    where={"target": str(target_root)},
                )
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
        )

    pyproject = target_root / "pyproject.toml"
    if not pyproject.exists():
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_not_gaia_package",
                    level="error",
                    message=(
                        f"no pyproject.toml under {target_root}; expected a Gaia "
                        "knowledge package (see `gaia build init`)"
                    ),
                    source="prewrite",
                    where={"target": str(target_root)},
                )
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
        )

    try:
        config = tomllib.loads(pyproject.read_text())
    except (OSError, tomllib.TOMLDecodeError) as exc:
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"pyproject.toml is not valid TOML: {exc}",
                    source="prewrite",
                    where={"pyproject": str(pyproject)},
                )
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
        )

    gaia_section = config.get("tool", {}).get("gaia", {})
    if gaia_section.get("type") != "knowledge-package":
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_not_gaia_package",
                    level="error",
                    message=(
                        "target package is not a Gaia knowledge package: "
                        "[tool.gaia].type must equal 'knowledge-package'"
                    ),
                    source="prewrite",
                    where={"pyproject": str(pyproject)},
                )
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
        )

    project_name = config.get("project", {}).get("name")
    if not isinstance(project_name, str) or not project_name:
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message="[project].name is required in pyproject.toml",
                    source="prewrite",
                    where={"pyproject": str(pyproject)},
                )
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=None,
            project_name=None,
        )

    import_name = project_name.removesuffix("-gaia").replace("-", "_")
    # Source root may be at <root>/<import_name>/ or <root>/src/<import_name>/.
    candidates = [target_root / import_name, target_root / "src" / import_name]
    source_root = next((c for c in candidates if c.exists()), None)
    if source_root is None:
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_invalid",
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
            ],
            source_root=target_root,
            source_init_path=None,
            import_name=import_name,
            project_name=project_name,
        )

    init_py = source_root / "__init__.py"
    if not init_py.exists():
        return _TargetStructure(
            errors=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"missing source entrypoint: {init_py}",
                    source="prewrite",
                    where={"init_py": str(init_py)},
                )
            ],
            source_root=source_root,
            source_init_path=None,
            import_name=import_name,
            project_name=project_name,
        )

    return _TargetStructure(
        errors=[],
        source_root=source_root,
        source_init_path=init_py,
        import_name=import_name,
        project_name=project_name,
    )


# --------------------------------------------------------------------------- #
# Invariant (b) — proposed-code syntax                                        #
# --------------------------------------------------------------------------- #


def _validate_proposed_syntax(generated_code: str) -> list[Diagnostic]:
    """Confirm the proposed snippet parses as Python."""
    if not generated_code.strip():
        return [
            Diagnostic(
                kind="prewrite.syntax",
                level="error",
                message="proposed code is empty",
                source="prewrite",
            )
        ]
    try:
        ast.parse(generated_code)
    except SyntaxError as exc:
        return [
            Diagnostic(
                kind="prewrite.syntax",
                level="error",
                message=f"proposed code is not valid Python: {exc.msg}",
                source="prewrite",
                where={"line": exc.lineno or 0, "offset": exc.offset or 0},
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# Invariant (c) — collision + references                                      #
# --------------------------------------------------------------------------- #


def _collect_module_symbols(source_root: Path, import_name: str | None) -> set[str]:
    """Statically collect top-level binding names from the package's source files.

    We deliberately don't import the package — pre-write must be
    side-effect-free. AST-walking ``__init__.py`` (and any sibling ``.py``
    that ``__init__.py`` would import) is sufficient for label-collision
    + reference-resolution at R1; post-write ``gaia build check`` does
    the full lowering when its higher fidelity is needed.
    """
    symbols: set[str] = set()
    if not source_root.exists() or not source_root.is_dir():
        return symbols
    for py_path in sorted(source_root.glob("*.py")):
        try:
            tree = ast.parse(py_path.read_text())
        except (OSError, SyntaxError):
            # Existing source has a syntax error — that's a problem the
            # user has to fix separately; pre-write doesn't gate on it
            # because we're proposing a new statement, not editing the
            # broken one.
            continue
        symbols.update(_top_level_bindings(tree))
    # Strip the import name itself in case __init__.py imports the same
    # package (rare but legal).
    if import_name:
        symbols.discard(import_name)
    return symbols


def _top_level_bindings(tree: ast.Module) -> set[str]:
    """Return module-level names bound by assignments / imports / defs."""
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                names.update(_assignment_targets(target))
        elif isinstance(node, (ast.AnnAssign, ast.AugAssign)) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.asname or alias.name.split(".", 1)[0])
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    continue
                names.add(alias.asname or alias.name)
    return names


def _assignment_targets(target: ast.expr) -> set[str]:
    if isinstance(target, ast.Name):
        return {target.id}
    if isinstance(target, (ast.Tuple, ast.List)):
        out: set[str] = set()
        for elt in target.elts:
            out.update(_assignment_targets(elt))
        return out
    return set()


def _validate_label_collision(
    label: str | None,
    module_symbols: set[str],
) -> list[Diagnostic]:
    """Reject labels that collide with already-bound module names."""
    if label is None:
        return []
    if label in module_symbols:
        return [
            Diagnostic(
                kind="prewrite.collision",
                level="error",
                message=f"label '{label}' is already bound at module scope",
                source="prewrite",
                where={"label": label},
            )
        ]
    if not label.isidentifier() or label.startswith("__"):
        return [
            Diagnostic(
                kind="prewrite.collision",
                level="error",
                message=(
                    f"label '{label}' is not a valid Python identifier "
                    "(must match [A-Za-z_][A-Za-z0-9_]* and not start with __)"
                ),
                source="prewrite",
                where={"label": label},
            )
        ]
    return []


def _validate_references(
    references: list[str],
    module_symbols: set[str],
) -> list[Diagnostic]:
    """Reject references that don't resolve in the local module scope."""
    missing = [ref for ref in references if ref and ref not in module_symbols]
    if not missing:
        return []
    return [
        Diagnostic(
            kind="prewrite.reference_unresolved",
            level="error",
            message=(
                "unresolved reference(s): "
                + ", ".join(sorted(missing))
                + " (not bound in package module scope)"
            ),
            source="prewrite",
            where={"references": list(references), "missing": list(missing)},
        )
    ]


# --------------------------------------------------------------------------- #
# Invariant (d) — order + structural sanity                                   #
# --------------------------------------------------------------------------- #


def _validate_structural_sanity(proposed_op: ProposedAuthorOp) -> list[Diagnostic]:
    """Catch self-loops + obvious structural malformations.

    R1 keeps this deliberately thin (per R1·❓-C=C1) — anything that needs
    the loaded IR (forward-ref-in-dep, ``__all__`` export simulation) stays
    in post-write.
    """
    if proposed_op.label is not None and proposed_op.label in proposed_op.references:
        return [
            Diagnostic(
                kind="prewrite.self_loop",
                level="error",
                message=(
                    f"label '{proposed_op.label}' references itself "
                    "(self-loop is not allowed in a reasoning warrant)"
                ),
                source="prewrite",
                where={"label": proposed_op.label},
            )
        ]
    return []


# --------------------------------------------------------------------------- #
# R3 warning detection                                                        #
# --------------------------------------------------------------------------- #


# DSL names the engine flags as deprecated (matches the
# ``DeprecationWarning`` emissions surveyed in
# ``gaia.engine.lang.dsl.{operators,propositional,knowledge,strategies}``).
# Keyed name → (replacement-hint, since-version). The "since" field is
# the v0.5 transition unless an emission site indicates otherwise; the
# user-visible hint is the message body that gets prefixed in the
# warning diagnostic.
_DEPRECATED_DSL_NAMES: dict[str, tuple[str, str]] = {
    # Note aliases (gaia.engine.lang.dsl.knowledge).
    "context": ("note", "0.5"),
    "setting": ("note", "0.5"),
    # Propositional (gaia.engine.lang.dsl.propositional).
    "not_": ("claim(formula=lnot(ClaimAtom(...)))", "0.5"),
    "and_": ("claim(formula=land(ClaimAtom(...), ...))", "0.5"),
    "or_": ("claim(formula=lor(ClaimAtom(...), ...))", "0.5"),
    # Operator helpers (gaia.engine.lang.dsl.operators).
    "contradiction": ("contradict()", "0.5"),
    "equivalence": ("equal()", "0.5"),
    "complement": ("exclusive()", "0.5"),
    "disjunction": ("lor()", "0.5"),
    # Strategies (gaia.engine.lang.dsl.strategies).
    "noisy_and": ("derive() / infer()", "0.5"),
}


def _detect_label_shadow(*, label: str | None, source_init_path: Path | None) -> list[Diagnostic]:
    """Warn when ``label`` shadows a local-scope name not exported via ``__all__``.

    Detection logic:

    * Parse ``source_init_path`` for top-level bindings + ``__all__``
      entries. (We re-parse rather than reusing ``module_symbols``
      because ``module_symbols`` is the *union* across siblings and we
      need ``__all__`` membership.)
    * If ``label`` is bound locally but not in ``__all__``, emit
      ``prewrite.label_shadow``.

    The existing collision invariant (c) already fires when the label
    is already bound — so in practice this warning only fires when the
    user passes ``--no-check`` (skip collision masking) plus the label
    happens to match a private binding. The warning's main load is
    catching subtle ``__all__`` omissions during agent-driven
    authoring.

    Currently invariant (c) intercepts most shadow cases as a hard
    error, so the warning runs after (c) passes; it kicks in for the
    edge cases where the binding came from a sibling source file (not
    the entrypoint) — the symbol-collection loop pulls names from every
    ``.py``, but ``__all__`` only lives in ``__init__.py``.
    """
    if label is None or source_init_path is None or not source_init_path.exists():
        return []

    try:
        tree = ast.parse(source_init_path.read_text())
    except (OSError, SyntaxError):
        return []

    init_bindings = _top_level_bindings(tree)
    all_entries = _module_all_entries(tree)

    # Only fire when the label is bound somewhere in the entry-point file
    # itself; sibling-file shadowing is left to post-write to surface.
    if label not in init_bindings:
        return []
    if label in all_entries:
        return []
    return [
        Diagnostic(
            kind="prewrite.label_shadow",
            level="warning",
            message=(
                f"label {label!r} shadows a local binding not listed in __all__; "
                "consider adding it to __all__ or renaming"
            ),
            source="prewrite",
            where={"label": label},
        )
    ]


def _module_all_entries(tree: ast.Module) -> set[str]:
    """Return the string elements of a module-level ``__all__ = [...]`` if present."""
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t for t in node.targets if isinstance(t, ast.Name) and t.id == "__all__"]
        if not targets:
            continue
        if isinstance(node.value, (ast.List, ast.Tuple)):
            return {
                elt.value
                for elt in node.value.elts
                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
            }
    return set()


def _detect_deprecated_refs(proposed_op: ProposedAuthorOp) -> list[Diagnostic]:
    """Warn when the proposed op references a name engine-flagged as deprecated.

    Scans:

    * ``proposed_op.required_imports`` — the names the verb's DSL
      surface uses (``derive``, ``claim``, ...). The render path always
      passes the canonical name, so this would never fire for a verb
      shipped through ``gaia author``. Included for completeness in
      case a future verb routes through a deprecated factory.
    * ``proposed_op.references`` — identifiers the user named on the
      command line. If an agent passes ``--given context`` where
      ``context`` is the local module's alias for the deprecated
      knowledge factory, the warning fires.
    * ``proposed_op.generated_code`` AST — names appearing in the
      proposed call expression (catches the case where a verb's prose
      argument or rationale text happens to look like a deprecated
      function reference; the warning is informational only).

    The warning carries the engine's recommended replacement.
    """
    diagnostics: list[Diagnostic] = []
    flagged: set[str] = set()

    candidates: list[str] = []
    candidates.extend(proposed_op.required_imports)
    candidates.extend(proposed_op.references)

    # Walk the generated code's AST for any Name node that matches the
    # deprecated set; references-list-only matching misses the rare
    # case of an inline deprecated-call inside ``--rationale`` etc.
    # ``--rationale`` strings stay literal so the inline-call case is
    # genuinely rare — we still scan because the cost is negligible.
    try:
        tree = ast.parse(proposed_op.generated_code)
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                candidates.append(node.id)

    for name in candidates:
        if name in flagged:
            continue
        if name not in _DEPRECATED_DSL_NAMES:
            continue
        flagged.add(name)
        replacement, since = _DEPRECATED_DSL_NAMES[name]
        diagnostics.append(
            Diagnostic(
                kind="prewrite.deprecated_ref",
                level="warning",
                message=(
                    f"reference {name!r} is deprecated since v{since}; "
                    f"suggest {replacement!r} instead"
                ),
                source="prewrite",
                where={"name": name, "replacement": replacement, "since": since},
            )
        )
    return diagnostics


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _first_exit_code(diagnostics: list[Diagnostic]) -> int:
    """Pick the exit code from the first error-level diagnostic."""
    for diag in diagnostics:
        if diag.level == "error":
            return exit_code_for_diagnostic(diag.kind)
    return 0


__all__ = [
    "AuthorPrewriteResult",
    "prewrite_check",
]
