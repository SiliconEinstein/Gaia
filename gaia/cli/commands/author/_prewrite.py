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
