"""``gaia pkg scaffold`` — initialise a fresh Gaia knowledge package.

Maps the agent-first authoring story to package initialisation: given a
target directory and a package name, lay down the minimal layout that
the rest of the ``gaia author`` cycle needs (``pyproject.toml`` with
``[tool.gaia]`` block, ``src/<import_name>/__init__.py`` template,
``.gaia/`` artifact directory).

Why a new verb instead of reusing the legacy ``gaia init`` /
``gaia build init``? Two reasons:

1. **Agent-first envelope.** ``gaia init`` writes human-oriented text
   to stdout and shells out to ``uv``; ``gaia pkg scaffold`` emits the
   same uniform ``{status, code, verb, payload, warnings, diagnostics}``
   shape the ``gaia author <verb>`` family does, so an LLM agent can
   parse one envelope schema across the whole package lifecycle.
2. **Independent pre-validation surface.** ``scaffold`` knows about
   ``-gaia`` naming, namespace defaults, and ``--check`` integration
   that runs ``gaia build check`` against the freshly created package.

The ``scaffold`` verb writes its own pre-validation pipeline (target
directory absence + name ending + import-name validity) rather than
reusing :mod:`gaia.cli.commands.author._prewrite` — its 4 invariants
assume a *pre-existing* Gaia package, while ``scaffold`` creates one
from scratch. The JSON envelope is shared verbatim.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from gaia.cli.commands.author._authored import (
    AUTHORED_INIT_BODY,
    ROOT_REEXPORT_BLOCK,
)
from gaia.cli.commands.author._envelope import (
    EXIT_INPUT_SYNTAX,
    EXIT_OK,
    EXIT_PREWRITE_STRUCTURAL,
    EXIT_SYSTEM_IO,
    AuthorResult,
    Diagnostic,
    emit,
)
from gaia.cli.commands.author._postwrite import postwrite_check

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

_PYPROJECT_TEMPLATE_WITH_UUID = """\
[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
type = "knowledge-package"
uuid = "{uuid}"
namespace = "{namespace}"

[tool.gaia.quality]
allow_holes = true
"""


_PYPROJECT_TEMPLATE_NO_UUID = """\
[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/{import_name}"]

[tool.gaia]
type = "knowledge-package"
namespace = "{namespace}"

[tool.gaia.quality]
allow_holes = true
"""


# Minimal DSL template: the canonical ``claim`` import, an empty
# ``__all__`` public-surface list, and the ``authored/`` import block.
# Hand-authored DSL goes directly in this root ``__init__.py``; ``gaia
# author <verb>`` commands write into the composed ``authored/``
# submodule, which the root imports for package-local name resolution. No
# placeholder demo statement — the package starts empty and exports no
# public Knowledge until the author curates ``__all__``.
#
# The import line stays narrow (``claim`` only) for the default. The
# freshly scaffolded package is loadable by ``gaia build check`` because
# the import is satisfied and ``__all__`` is well-formed.
_INIT_BODY_NO_DOCSTRING = (
    "from gaia.engine.lang import claim\n\n__all__: list[str] = []\n\n" + ROOT_REEXPORT_BLOCK
)


_INIT_BODY_WITH_DOCSTRING = (
    '"""{docstring}"""\n\nfrom gaia.engine.lang import claim\n\n__all__: list[str] = []\n\n'
    + ROOT_REEXPORT_BLOCK
)


@dataclass
class _ScaffoldPlan:
    """Resolved scaffold parameters after argument validation."""

    target_root: Path
    pkg_name: str
    import_name: str
    namespace: str
    description: str
    pkg_uuid: str | None
    docstring: str | None


def _derive_import_name(pkg_name: str) -> str:
    return pkg_name.removesuffix("-gaia").replace("-", "_")


def _validate_inputs(
    *,
    target: Path,
    name: str | None,
    namespace: str | None,
    description: str | None,
    with_uuid: bool,
    docstring: str | None,
) -> tuple[_ScaffoldPlan | None, list[Diagnostic]]:
    """Run the scaffold-specific pre-validation."""
    diagnostics: list[Diagnostic] = []

    pkg_name = name or target.name
    if not pkg_name.endswith("-gaia"):
        suggested = f"{pkg_name}-gaia"
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_not_gaia_package",
                level="error",
                message=(
                    f"package name must end with '-gaia' (got {pkg_name!r}; "
                    f"did you mean {suggested!r}?)"
                ),
                source="prewrite",
                where={"pkg_name": pkg_name},
            )
        )
        return None, diagnostics

    # import_name is derived from [project].name per the engine
    # convention (``foo-gaia`` → ``foo``); no override flag, since an
    # override could lay down a package the engine couldn't load.
    import_name = _derive_import_name(pkg_name)
    if not _IDENTIFIER_RE.match(import_name) or import_name.startswith("__"):
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_invalid",
                level="error",
                message=(
                    f"derived import name {import_name!r} is not a valid Python "
                    "module identifier (derived from --name by stripping "
                    "'-gaia' and converting '-' to '_'; pick a different "
                    "--name to fix)"
                ),
                source="prewrite",
                where={"import_name": import_name, "pkg_name": pkg_name},
            )
        )
        return None, diagnostics

    # Refuse to lay down a package whose import name collides with a
    # stdlib module. The engine's ``importlib.import_module`` would
    # return the stdlib module instead of the package and produce an
    # inscrutable "not a Gaia package" error downstream.
    import sys as _sys

    if import_name in _sys.stdlib_module_names:
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_invalid",
                level="error",
                message=(
                    f"derived import name {import_name!r} collides with a "
                    "Python stdlib module; pick a different --name"
                ),
                source="prewrite",
                where={"import_name": import_name, "pkg_name": pkg_name},
            )
        )
        return None, diagnostics

    namespace_resolved = namespace or import_name

    if target.exists() and any(target.iterdir()):
        # Refuse to write into a non-empty directory — keeps idempotency
        # honest (running scaffold twice should produce identical output
        # only if the first run was clean).
        offenders = [p.name for p in sorted(target.iterdir())]
        diagnostics.append(
            Diagnostic(
                kind="prewrite.collision",
                level="error",
                message=(
                    f"target directory {target} is not empty (contains: "
                    + ", ".join(offenders[:5])
                    + (", ...)" if len(offenders) > 5 else ")")
                ),
                source="prewrite",
                where={"target": str(target), "existing": offenders[:5]},
            )
        )
        return None, diagnostics

    # uuid is opt-in via --with-uuid (both shipping example packages
    # omit it). Default is no uuid.
    pkg_uuid = str(uuid.uuid4()) if with_uuid else None
    desc_resolved = description or f"Gaia knowledge package: {pkg_name}"
    return (
        _ScaffoldPlan(
            target_root=target,
            pkg_name=pkg_name,
            import_name=import_name,
            namespace=namespace_resolved,
            description=desc_resolved,
            pkg_uuid=pkg_uuid,
            docstring=docstring,
        ),
        [],
    )


def _scaffold_layout(plan: _ScaffoldPlan) -> list[Path]:
    """Lay down the package directory structure and return the created files."""
    created: list[Path] = []
    plan.target_root.mkdir(parents=True, exist_ok=True)

    pyproject_path = plan.target_root / "pyproject.toml"
    if plan.pkg_uuid is not None:
        pyproject_text = _PYPROJECT_TEMPLATE_WITH_UUID.format(
            name=plan.pkg_name,
            description=plan.description,
            import_name=plan.import_name,
            uuid=plan.pkg_uuid,
            namespace=plan.namespace,
        )
    else:
        pyproject_text = _PYPROJECT_TEMPLATE_NO_UUID.format(
            name=plan.pkg_name,
            description=plan.description,
            import_name=plan.import_name,
            namespace=plan.namespace,
        )
    pyproject_path.write_text(pyproject_text)
    created.append(pyproject_path)

    src_pkg = plan.target_root / "src" / plan.import_name
    src_pkg.mkdir(parents=True)
    init_py = src_pkg / "__init__.py"
    if plan.docstring is not None:
        init_text = _INIT_BODY_WITH_DOCSTRING.format(docstring=plan.docstring)
    else:
        init_text = _INIT_BODY_NO_DOCSTRING
    init_py.write_text(init_text)
    created.append(init_py)

    # ``authored/`` submodule — the canonical home for every ``gaia author
    # <verb>`` write. The root ``__init__.py`` imports its public runtime
    # bindings and merges only curated authored exports into ``__all__``.
    authored_dir = src_pkg / "authored"
    authored_dir.mkdir()
    authored_init = authored_dir / "__init__.py"
    authored_init.write_text(AUTHORED_INIT_BODY)
    created.append(authored_init)

    gaia_dir = plan.target_root / ".gaia"
    gaia_dir.mkdir()
    gaia_keep = gaia_dir / ".gitkeep"
    gaia_keep.write_text("")
    created.append(gaia_keep)

    return created


def _next_steps_text(plan: _ScaffoldPlan) -> str:
    """Return a plain-text Next-step block for the scaffolded package."""
    parent = plan.target_root.parent
    pkg_rel = plan.target_root.name
    return (
        f"Next:\n"
        f"  cd {parent}\n"
        f'  gaia author claim "..." --target ./{pkg_rel}\n'
        f"\n"
        f"Point every verb at the package with --target ./{pkg_rel} (author\n"
        f"verbs and `gaia pkg add`) or the path argument (`gaia build compile`\n"
        f"/ `gaia run infer`). The same target works from the parent directory\n"
        f"or from inside the package.\n"
        f"\n"
        f"  gaia pkg add --lkm-paper <id> --target ./{pkg_rel}\n"
        f"  gaia build compile ./{pkg_rel}\n"
        f"  gaia run infer ./{pkg_rel}"
    )


def _emit_scaffold_envelope(
    *,
    plan: _ScaffoldPlan,
    created: list[Path],
    post_diagnostics: list[Diagnostic],
    post_warnings: list[Diagnostic],
    counts: dict[str, int] | None,
    human: bool,
) -> None:
    payload: dict[str, Any] = {
        "pkg_path": str(plan.target_root),
        "pkg_name": plan.pkg_name,
        "import_name": plan.import_name,
        "namespace": plan.namespace,
        "uuid": plan.pkg_uuid,
        "docstring": plan.docstring,
        "files_created": [str(p) for p in created],
    }
    if counts is not None:
        payload["check"] = counts
    elif not post_diagnostics:
        payload["check"] = "skipped"
    if not post_diagnostics:
        payload["next_steps"] = _next_steps_text(plan)
    if post_diagnostics:
        result = AuthorResult(
            verb="scaffold",
            status="error",
            code=EXIT_PREWRITE_STRUCTURAL,
            payload=payload,
            warnings=[w.message for w in post_warnings],
            diagnostics=post_diagnostics,
        )
    else:
        result = AuthorResult(
            verb="scaffold",
            status="ok",
            code=EXIT_OK,
            payload=payload,
            warnings=[w.message for w in post_warnings],
            diagnostics=list(post_warnings),
        )
    emit(result, human=human)


def scaffold_command(
    target: str = typer.Option(
        ...,
        "--target",
        help=(
            "Path to the directory to initialise (must be empty or non-existent). "
            "Author verbs are run from outside the package, with --target <path>."
        ),
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="Package name (must end with '-gaia'); defaults to target dir name.",
    ),
    namespace: str | None = typer.Option(
        None,
        "--namespace",
        help="Package namespace; defaults to the import name.",
    ),
    description: str | None = typer.Option(
        None, "--description", help="Short description for pyproject.toml."
    ),
    with_uuid: bool = typer.Option(
        False,
        "--with-uuid",
        help=(
            "Generate a [tool.gaia].uuid for the package. Default is to omit "
            "the field (matches the shipping example packages)."
        ),
    ),
    docstring: str | None = typer.Option(
        None,
        "--docstring",
        help=(
            "Module docstring for the generated src/<import_name>/__init__.py. "
            "Wrapped in triple quotes at line 1. Default: no docstring."
        ),
    ),
    check: bool = typer.Option(
        False,
        "--check/--no-check",
        help=(
            "Run post-write `gaia build check` on the freshly created package. "
            "Default off — a fresh scaffold has no declarations yet, which the "
            "engine treats as an error. Re-run with `gaia build check` once "
            "author commands have added statements."
        ),
    ),
    human: bool = typer.Option(
        False, "--human", help="Render the envelope in human-readable form instead of JSON."
    ),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        help="Prompt on pre-write warnings (no-op for scaffold — it emits no warnings).",
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Scaffold a fresh Gaia knowledge package.

    Example:

    .. code-block:: bash

        gaia pkg scaffold --target ./mypkg-gaia --name mypkg-gaia \
            --docstring "My package."
    """
    del json_, interactive  # see helper-doc rationale

    target_root = Path(target).resolve()

    plan, pre_diagnostics = _validate_inputs(
        target=target_root,
        name=name,
        namespace=namespace,
        description=description,
        with_uuid=with_uuid,
        docstring=docstring,
    )
    if plan is None:
        # Pick semantic exit code from the first diagnostic kind.
        first = pre_diagnostics[0]
        code = {
            "prewrite.target_not_gaia_package": EXIT_SYSTEM_IO,
            "prewrite.target_invalid": EXIT_SYSTEM_IO,
            "prewrite.collision": EXIT_INPUT_SYNTAX,
        }.get(first.kind, EXIT_PREWRITE_STRUCTURAL)
        result = AuthorResult(
            verb="scaffold",
            status="error",
            code=code,
            payload={"target": str(target_root)},
            diagnostics=pre_diagnostics,
        )
        emit(result, human=human)
        return

    try:
        created = _scaffold_layout(plan)
    except (OSError, PermissionError) as exc:
        result = AuthorResult(
            verb="scaffold",
            status="error",
            code=EXIT_SYSTEM_IO,
            payload={"target": str(target_root)},
            diagnostics=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"failed to lay out scaffold under {target_root}: {exc}",
                    source="prewrite",
                    where={"target": str(target_root)},
                )
            ],
        )
        emit(result, human=human)
        return

    post_diagnostics: list[Diagnostic] = []
    post_warnings: list[Diagnostic] = []
    counts: dict[str, int] | None = None
    if check:
        post = postwrite_check(target_root)
        post_diagnostics.extend(post.diagnostics)
        post_warnings.extend(post.warnings)
        if post.ok:
            counts = {
                "knowledge_count": post.knowledge_count,
                "strategy_count": post.strategy_count,
                "operator_count": post.operator_count,
            }

    _emit_scaffold_envelope(
        plan=plan,
        created=created,
        post_diagnostics=post_diagnostics,
        post_warnings=post_warnings,
        counts=counts,
        human=human,
    )
    if not post_diagnostics and human:
        typer.echo("\n" + _next_steps_text(plan))


__all__ = ["scaffold_command"]
