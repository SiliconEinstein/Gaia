"""gaia init -- scaffold a new Gaia knowledge package."""

from __future__ import annotations

import re
import subprocess
import uuid
from pathlib import Path

import typer

from gaia.engine.packaging import GaiaPackagingError

# Minimal DSL template: just the canonical ``claim`` import and an empty
# ``__all__``. Subsequent ``gaia author <verb>`` commands populate
# ``__all__`` as statements are added. No placeholder demo statement —
# the package starts empty.
_DSL_BODY_NO_DOCSTRING = """\
from gaia.engine.lang import claim

__all__: list[str] = []
"""


_DSL_BODY_WITH_DOCSTRING = '''\
"""{docstring}"""

from gaia.engine.lang import claim

__all__: list[str] = []
'''


def _run_uv(
    args: list[str],
    *,
    cwd: Path,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    try:
        result = subprocess.run(args, cwd=cwd, text=True, capture_output=True)
    except FileNotFoundError as exc:
        raise GaiaPackagingError(
            "uv is not installed. Install it with: curl -LsSf https://astral.sh/uv/install.sh | sh"
        ) from exc
    if check and result.returncode != 0:
        stderr = result.stderr.strip() or result.stdout.strip() or "command failed"
        raise GaiaPackagingError(f"Error running {' '.join(args)}: {stderr}")
    return result


def _strip_authors_from_pyproject(pyproject_text: str) -> str:
    """Remove a leading ``[project] authors = [...]`` block written by ``uv init``.

    ``uv init`` populates ``authors`` from the local git config (``user.name`` /
    ``user.email``). For a public-tier scaffold we drop that line entirely;
    users add their own afterward. Matches both single-line and multi-line
    array forms.
    """
    # Multi-line form: `authors = [\n    { name = "...", email = "..." },\n]`
    pattern_multiline = re.compile(
        r"^authors\s*=\s*\[\s*\n(?:[^\]\n]*\n)*?\]\s*\n",
        re.MULTILINE,
    )
    pyproject_text = pattern_multiline.sub("", pyproject_text)
    # Single-line form: `authors = [{ name = "...", email = "..." }]`
    pattern_singleline = re.compile(r"^authors\s*=\s*\[.*\]\s*\n", re.MULTILINE)
    return pattern_singleline.sub("", pyproject_text)


def init_command(
    name: str = typer.Argument(help="Package name (must end with '-gaia')."),
    docstring: str | None = typer.Option(
        None,
        "--docstring",
        help=(
            "Module docstring for the generated src/<import_name>/__init__.py. "
            "Wrapped in triple quotes at line 1. Default: no docstring."
        ),
    ),
) -> None:
    """Create a new Gaia knowledge package.

    Example: ``gaia build init mypkg-gaia --docstring "My package."``
    """
    # --- validate name suffix ---------------------------------------------------
    if not name.endswith("-gaia"):
        suggested = f"{name}-gaia"
        typer.echo(
            f"Error: package name must end with '-gaia'. Did you mean '{suggested}'?",
            err=True,
        )
        raise typer.Exit(1)

    cwd = Path.cwd()
    pkg_dir = cwd / name

    # --- scaffold with uv init --lib -------------------------------------------
    try:
        _run_uv(["uv", "init", "--lib", name], cwd=cwd)
    except GaiaPackagingError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    # --- compute import name early (needed for both pyproject patch and rename) --
    # Wheel-build convention: dash → underscore, full name (no suffix stripping).
    # This matches the directory that ``uv init --lib`` creates, so the rename
    # below is a no-op for the common case and the pyproject wheel target is
    # consistent with the actual src/ layout.
    import_name = name.replace("-", "_")

    # --- patch pyproject.toml with [tool.hatch] + [tool.gaia] sections ---------
    # First strip any ``[project] authors`` block that ``uv init`` populated from
    # local git config — public-tier scaffold leaves authors empty so users
    # don't inadvertently expose internal email domains.
    pyproject_path = pkg_dir / "pyproject.toml"
    existing_pyproject = pyproject_path.read_text()
    cleaned_pyproject = _strip_authors_from_pyproject(existing_pyproject)
    if cleaned_pyproject != existing_pyproject:
        pyproject_path.write_text(cleaned_pyproject)

    gaia_uuid = str(uuid.uuid4())
    extra_sections = (
        f"\n[tool.hatch.build.targets.wheel]\n"
        f'packages = ["src/{import_name}"]\n'
        f"\n[tool.gaia]\n"
        f'type = "knowledge-package"\n'
        f'uuid = "{gaia_uuid}"\n'
    )
    with open(pyproject_path, "a") as f:
        f.write(extra_sections)

    # --- rename src/<uv_default_name>/ → src/<import_name>/ --------------------
    uv_default_name = name.replace("-", "_")
    src_dir = pkg_dir / "src"
    uv_pkg_dir = src_dir / uv_default_name
    target_pkg_dir = src_dir / import_name

    if uv_pkg_dir.exists() and uv_pkg_dir != target_pkg_dir:
        uv_pkg_dir.rename(target_pkg_dir)
    elif not uv_pkg_dir.exists() and not target_pkg_dir.exists():
        # Fallback: create the target directory if uv didn't create expected layout
        target_pkg_dir.mkdir(parents=True, exist_ok=True)

    # --- write DSL template into __init__.py -----------------------------------
    init_py = target_pkg_dir / "__init__.py"
    if docstring is not None:
        init_py.write_text(_DSL_BODY_WITH_DOCSTRING.format(docstring=docstring))
    else:
        init_py.write_text(_DSL_BODY_NO_DOCSTRING)

    # --- append Gaia ignore patterns to .gitignore --------------------------------
    # .gaia/ir.json and .gaia/ir_hash should be tracked (registry needs them).
    # Inference outputs and dep_beliefs cache should be ignored.
    gitignore_path = pkg_dir / ".gitignore"
    gaia_ignore_patterns = [
        ".gaia/beliefs.json",
        ".gaia/dep_beliefs/",
    ]
    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        # Remove overly broad ".gaia/" if uv or prior init added it
        if ".gaia/\n" in existing:
            existing = existing.replace(".gaia/\n", "")
        missing = [p for p in gaia_ignore_patterns if p not in existing]
        if missing:
            block = "\n# Gaia inference outputs (regenerated by gaia run infer)\n"
            block += "\n".join(missing) + "\n"
            with open(gitignore_path, "w") as f:
                f.write(existing.rstrip() + block)
    else:
        block = "# Gaia inference outputs (regenerated by gaia run infer)\n"
        block += "\n".join(gaia_ignore_patterns) + "\n"
        gitignore_path.write_text(block)

    # --- add gaia-lang dependency (warn on failure) ----------------------------
    try:
        _run_uv(["uv", "add", "gaia-lang"], cwd=pkg_dir)
    except GaiaPackagingError:
        typer.echo(
            f"Warning: could not add gaia-lang to {pkg_dir / 'pyproject.toml'}. "
            "Run 'uv add gaia-lang' from inside the new package directory "
            f"({pkg_dir}) to add it. "
            "This affects the new package's own Python environment — not "
            "the directory you are running gaia from. "
            "Skipping this step is fine if you plan to author with "
            "`gaia author …` from outside the package; the dependency is "
            "required only when the package is imported at runtime or "
            "compiled with `gaia build compile`.",
            err=True,
        )

    typer.echo(f"Created Gaia knowledge package: {name}")
    typer.echo(
        "\nNext steps:\n"
        f"  cd <parent of {name}>\n"
        f'  gaia author claim "..." --target ./{name}\n'
        "\n"
        "Author verbs run from the parent directory, with --target pointing\n"
        f"at ./{name}. Running them from inside {name} will not find gaia-lang.\n"
        f"\n  gaia build compile ./{name}\n"
        f"  gaia run infer ./{name}"
    )
