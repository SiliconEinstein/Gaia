"""``gaia pkg mount`` — non-invasively attach a Gaia knowledge package to a host.

The mount verb is the new, non-invasive on-ramp into Gaia. Where the
existing ``gaia pkg scaffold`` / ``gaia build init`` verbs *take over*
a directory (writing a ``pyproject.toml`` with ``[tool.gaia]``,
reshuffling ``src/<import>/``), ``mount`` only ever writes inside two
sibling folders the host does not already use:

```
<host>/
  gaia/                       # user-authored Gaia DSL  (created by mount)
    gaia.toml                 # package identity (name, version, namespace)
    __init__.py               # imports the deterministic projector
                              # output (from_ara/, from_arm/, from_host/)
  .gaia/                      # generated artifacts     (created by mount)
    .gitkeep                  # placeholder
    source_map.json           # audit spine (spec §9)
    formalization_queue.jsonl # follow-up items (spec §10)
```

Everything else in the host stays untouched. That is the whole point:
ARM bundles, ARA artifacts, plain ``uv pip`` packages, and even a
freshly cloned paper repo can be mounted into Gaia without touching
their existing layout, build config, or import names.

When the host is recognised as an ARM bundle (``arm_manifest.json``)
or ARA artifact (``PAPER.md`` + ``logic/``), the deterministic
projector (:mod:`gaia.engine.projector`) emits typed scaffolds for
each structured source: ``logic/claims.md`` Cxx blocks become
``claim(...)``, ``evidence/tables/*`` become ``observe(...)``, etc.
Each ambiguous projection is recorded with ``requires_review=True``
and seeded into the formalization queue so a later ``--formalize``
pass can upgrade it.

With ``--from <file>`` (repeatable) the user can additionally name
host files that should be projected through the generic
``note(...)`` rule on top of the typed projector output.
"""

from __future__ import annotations

import json
import re
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from gaia.cli.commands.author._envelope import (
    EXIT_INPUT_SYNTAX,
    EXIT_OK,
    EXIT_PREWRITE_STRUCTURAL,
    EXIT_SYSTEM_IO,
    AuthorResult,
    Diagnostic,
    emit,
)
from gaia.engine.layout import (
    EMBEDDED_GAIA_DIR,
    EMBEDDED_GAIA_MANIFEST,
    EMBEDDED_GAIA_OUTPUT_DIR,
)
from gaia.engine.manifest import (
    GaiaManifest,
    GaiaPackageBlock,
    GaiaProjectionBlock,
    GaiaQualityBlock,
    render_manifest,
)
from gaia.engine.projector import (
    HostKind,
    ProjectionResult,
    detect_host_kind,
    project_host,
    render_source_map,
)

_IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9_]+")


_PLAIN_INIT_TEMPLATE = '''\
"""{description}

Mounted by `gaia pkg mount` / `gaia build init --embedded`. Author DSL
statements here (or split across sibling files in this folder).

Imports inside this folder should use relative form (`from . import
some_claim`) — the folder is loaded under a synthetic Python name so
absolute imports through the user-facing name would not resolve.
"""

from gaia.engine.lang import claim  # noqa: F401 — placeholder import

__all__: list[str] = []
'''


_PROJECTED_INIT_TEMPLATE_ARA = '''\
"""{description}

Mounted by `gaia pkg mount` / `gaia build init --embedded` from an
ARA host. The deterministic projector wrote scaffold modules under
`from_ara/`; re-export everything they declare so the embedded
loader picks them up.
"""

from .from_ara import *  # noqa: F401,F403
from .from_ara import __all__ as _ara_all

__all__ = list(_ara_all)
'''


_PROJECTED_INIT_TEMPLATE_ARM = '''\
"""{description}

Mounted by `gaia pkg mount` / `gaia build init --embedded` from an
ARM bundle. The deterministic projector wrote scaffold modules under
`from_arm/`; re-export everything they declare so the embedded
loader picks them up.
"""

from .from_arm import *  # noqa: F401,F403
from .from_arm import __all__ as _arm_all

__all__ = list(_arm_all)
'''


@dataclass
class _MountPlan:
    """Resolved mount parameters after argument validation."""

    host_root: Path
    package_name: str
    namespace: str
    description: str
    seeds: list[Path]
    host_kind: HostKind
    host_kind_overridden: bool
    reproject: bool  # True when --reproject re-runs projector over existing mount


def _derive_default_name(host: Path) -> str:
    base = host.name or "gaia_pkg"
    base = base.removesuffix("-gaia")
    base = base.replace("-", "_").replace(".", "_")
    base = _SAFE_SLUG_RE.sub("_", base.lower()).strip("_")
    if not base or not _IDENT_RE.match(base):
        base = "gaia_pkg"
    return base


def _validate_inputs(
    *,
    host: Path,
    name: str | None,
    namespace: str | None,
    description: str | None,
    seeds: list[str],
    host_kind_override: str | None,
    reproject: bool,
) -> tuple[_MountPlan | None, list[Diagnostic]]:
    diagnostics: list[Diagnostic] = []

    if not host.exists():
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_missing",
                level="error",
                message=f"host directory does not exist: {host}",
                source="prewrite",
                where={"host": str(host)},
            )
        )
        return None, diagnostics
    if not host.is_dir():
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_invalid",
                level="error",
                message=f"host path is not a directory: {host}",
                source="prewrite",
                where={"host": str(host)},
            )
        )
        return None, diagnostics

    pkg_name = name or _derive_default_name(host)
    if not _IDENT_RE.match(pkg_name.replace("-", "_")):
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_invalid",
                level="error",
                message=(
                    f"package name {pkg_name!r} cannot be normalised to a valid Python "
                    "identifier (strip '-gaia', replace '-' with '_'). Pass --name to override."
                ),
                source="prewrite",
                where={"pkg_name": pkg_name},
            )
        )
        return None, diagnostics

    gaia_dir = host / EMBEDDED_GAIA_DIR
    manifest = gaia_dir / EMBEDDED_GAIA_MANIFEST
    if manifest.exists() and not reproject:
        diagnostics.append(
            Diagnostic(
                kind="prewrite.collision",
                level="error",
                message=(
                    f"host already has a Gaia mount at {manifest.relative_to(host)}. "
                    "Use `gaia pkg mount --reproject` to re-run the deterministic "
                    "projector while preserving your hand-authored files outside "
                    "gaia/from_*/ and gaia/formalization/."
                ),
                source="prewrite",
                where={"manifest": str(manifest)},
            )
        )
        return None, diagnostics
    if reproject and not manifest.exists():
        diagnostics.append(
            Diagnostic(
                kind="prewrite.target_missing",
                level="error",
                message=(
                    "--reproject requires an existing mount; no gaia/gaia.toml found "
                    f"at {manifest}. Run `gaia pkg mount` (without --reproject) first."
                ),
                source="prewrite",
                where={"manifest": str(manifest)},
            )
        )
        return None, diagnostics

    resolved_seeds: list[Path] = []
    for raw in seeds:
        candidate = (host / raw).resolve()
        try:
            candidate.relative_to(host)
        except ValueError:
            diagnostics.append(
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=(
                        f"--from seed {raw!r} resolves outside the host directory; "
                        "all seeds must be paths inside the host."
                    ),
                    source="prewrite",
                    where={"seed": raw, "host": str(host)},
                )
            )
            continue
        if not candidate.exists():
            diagnostics.append(
                Diagnostic(
                    kind="prewrite.target_missing",
                    level="error",
                    message=f"--from seed does not exist in host: {raw}",
                    source="prewrite",
                    where={"seed": raw, "host": str(host)},
                )
            )
            continue
        resolved_seeds.append(candidate)
    if diagnostics:
        return None, diagnostics

    if host_kind_override is not None:
        try:
            host_kind = HostKind(host_kind_override)
        except ValueError:
            diagnostics.append(
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=(
                        f"--host-kind {host_kind_override!r} is not recognised. "
                        f"Use one of: {sorted(k.value for k in HostKind)}."
                    ),
                    source="prewrite",
                    where={"host_kind": host_kind_override},
                )
            )
            return None, diagnostics
        kind_overridden = True
    else:
        host_kind = detect_host_kind(host)
        kind_overridden = False

    namespace_resolved = namespace or "github"
    description_resolved = description or f"Gaia knowledge package for {host.name}"
    return (
        _MountPlan(
            host_root=host,
            package_name=pkg_name,
            namespace=namespace_resolved,
            description=description_resolved,
            seeds=resolved_seeds,
            host_kind=host_kind,
            host_kind_overridden=kind_overridden,
            reproject=reproject,
        ),
        [],
    )


_PROJECTOR_MANAGED_DIRS = ("from_ara", "from_arm", "from_host")
"""Subdirectories under ``gaia/`` that the projector fully owns.

When ``--reproject`` is in play we wipe these before regenerating so
stale records (e.g. claims that the host deleted) do not linger.
Everything else under ``gaia/`` — ``__init__.py``, ``priors.py``,
``formalization/`` and any user-authored modules — is left untouched.
"""


def _write_mount(plan: _MountPlan) -> tuple[list[Path], ProjectionResult]:
    """Materialise the embedded layout and run the projector, returning written files.

    Idempotency for ``--reproject``:

    1. ``gaia/gaia.toml`` is **not** rewritten — preserves any user
       edits (description, dependencies, uuid).
    2. ``gaia/__init__.py`` is **not** rewritten — preserves any
       re-exports / imports the user added beyond the default template.
    3. The projector-managed ``gaia/from_*/`` subdirectories ARE
       wiped and rebuilt — those are the projector's exclusive
       territory.
    4. ``gaia/formalization/`` and any other user-authored modules
       under ``gaia/`` survive untouched.
    """
    import shutil  # local import keeps the cold-import surface narrow

    created: list[Path] = []
    gaia_dir = plan.host_root / EMBEDDED_GAIA_DIR
    out_dir = plan.host_root / EMBEDDED_GAIA_OUTPUT_DIR

    if plan.reproject:
        for managed in _PROJECTOR_MANAGED_DIRS:
            stale = gaia_dir / managed
            if stale.exists():
                shutil.rmtree(stale)
        out_dir.mkdir(parents=True, exist_ok=True)
    else:
        gaia_dir.mkdir(parents=True, exist_ok=False)
        out_dir.mkdir(parents=True, exist_ok=True)

    manifest_path = gaia_dir / EMBEDDED_GAIA_MANIFEST
    if not plan.reproject:
        manifest = GaiaManifest(
            package=GaiaPackageBlock(
                name=plan.package_name,
                version="0.1.0",
                namespace=plan.namespace,
                description=plan.description,
                uuid=str(_uuid.uuid4()),
                host_kind=plan.host_kind.value,
            ),
            quality=GaiaQualityBlock(allow_holes=True),
            projection=GaiaProjectionBlock(mode="scaffold"),
        )
        manifest_path.write_text(render_manifest(manifest))
        created.append(manifest_path)

    projection = project_host(plan.host_root, seeds=plan.seeds, host_kind=plan.host_kind)

    if plan.host_kind is HostKind.ARA:
        init_body = _PROJECTED_INIT_TEMPLATE_ARA.format(
            description=plan.description.replace('"', '\\"')
        )
    elif plan.host_kind is HostKind.ARM:
        init_body = _PROJECTED_INIT_TEMPLATE_ARM.format(
            description=plan.description.replace('"', '\\"')
        )
    else:
        init_body = _PLAIN_INIT_TEMPLATE.format(description=plan.description.replace('"', '\\"'))
    init_path = gaia_dir / "__init__.py"
    # Reproject preserves user edits to __init__.py; only a fresh
    # mount writes the projected-host template.
    if not init_path.exists():
        init_path.write_text(init_body)
        created.append(init_path)

    keep = out_dir / ".gitkeep"
    if not keep.exists():
        keep.write_text("")
        created.append(keep)

    for generated in projection.files:
        target = plan.host_root / Path(generated.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(generated.body)
        created.append(target)

    source_map = render_source_map(projection, host=plan.host_root)
    map_path = out_dir / "source_map.json"
    map_path.write_text(json.dumps(source_map, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    created.append(map_path)

    if projection.queue:
        queue_path = out_dir / "formalization_queue.jsonl"
        queue_path.write_text(
            "".join(
                json.dumps(item.to_json(), ensure_ascii=False, sort_keys=True) + "\n"
                for item in projection.queue
            )
        )
        created.append(queue_path)

    return created, projection


def mount_command(
    host: str = typer.Argument(
        ".",
        help=(
            "Path to the host directory to mount Gaia into. The host's own "
            "pyproject.toml, src/, ARM/ARA logic, evidence, etc. are not "
            "touched — Gaia only ever writes inside gaia/ and .gaia/."
        ),
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help=(
            "Package name written into gaia/gaia.toml. Defaults to a "
            "sanitised version of the host directory name. The trailing "
            "'-gaia' suffix is optional (no longer required by v0.5+)."
        ),
    ),
    namespace: str | None = typer.Option(
        None,
        "--namespace",
        help="QID namespace for the package. Defaults to 'github'.",
    ),
    description: str | None = typer.Option(
        None, "--description", help="Short description for gaia/gaia.toml."
    ),
    seed: list[str] = typer.Option(  # noqa: B008 — typer pattern
        [],
        "--from",
        help=(
            "Repeatable. Host-relative path to a file that should be projected "
            "into the new package as a scaffold-mode note(...) stub on top of "
            "the typed ARM/ARA projector output."
        ),
    ),
    host_kind: str | None = typer.Option(
        None,
        "--host-kind",
        help=(
            "Override the auto-detected host kind. One of 'arm', 'ara', "
            "'python-package', 'generic'. By default `gaia pkg mount` detects "
            "ARM by 'arm_manifest.json' and ARA by 'PAPER.md'+'logic/'."
        ),
    ),
    reproject: bool = typer.Option(
        False,
        "--reproject/--no-reproject",
        help=(
            "Re-run the deterministic projector against an already-mounted host. "
            "Preserves gaia/gaia.toml, gaia/__init__.py, gaia/formalization/, "
            "and any other user-authored modules; rebuilds only the projector-"
            "managed gaia/from_*/ subdirectories. Use after host source files "
            "change to refresh scaffolds without losing hand edits."
        ),
    ),
    human: bool = typer.Option(
        False, "--human", help="Render envelope in human-readable form instead of JSON."
    ),
    json_: bool = typer.Option(
        True, "--json/--no-json", help="JSON-first output (default; redundant for clarity)."
    ),
) -> None:
    r"""Mount a Gaia knowledge package on top of any host directory.

    Examples:

    .. code-block:: bash

        # Plain mount on an empty or arbitrary directory
        gaia pkg mount ./resnet-ara

        # ARM/ARA-style projection seeding from host files
        gaia pkg mount ./resnet-ara \
            --from logic/claims.md --from evidence/tables/table2.md
    """
    del json_
    host_path = Path(host).resolve()

    plan, pre_diagnostics = _validate_inputs(
        host=host_path,
        name=name,
        namespace=namespace,
        description=description,
        seeds=seed,
        host_kind_override=host_kind,
        reproject=reproject,
    )
    if plan is None:
        first = pre_diagnostics[0]
        code_map = {
            "prewrite.target_missing": EXIT_SYSTEM_IO,
            "prewrite.target_invalid": EXIT_SYSTEM_IO,
            "prewrite.collision": EXIT_INPUT_SYNTAX,
        }
        result = AuthorResult(
            verb="mount",
            status="error",
            code=code_map.get(first.kind, EXIT_PREWRITE_STRUCTURAL),
            payload={"host": str(host_path)},
            diagnostics=pre_diagnostics,
        )
        emit(result, human=human)
        return

    try:
        created, projection = _write_mount(plan)
    except (OSError, PermissionError) as exc:
        result = AuthorResult(
            verb="mount",
            status="error",
            code=EXIT_SYSTEM_IO,
            payload={"host": str(host_path)},
            diagnostics=[
                Diagnostic(
                    kind="prewrite.target_invalid",
                    level="error",
                    message=f"failed to write mount under {host_path}: {exc}",
                    source="prewrite",
                    where={"host": str(host_path)},
                )
            ],
        )
        emit(result, human=human)
        return

    payload: dict[str, Any] = {
        "host": str(host_path),
        "package_name": plan.package_name,
        "namespace": plan.namespace,
        "host_kind": plan.host_kind.value,
        "host_kind_overridden": plan.host_kind_overridden,
        "files_created": [str(p) for p in created],
        "source_map_records": len(projection.source_map),
        "queue_items": len(projection.queue),
        "projection_mode": "scaffold",
        "next_steps": (f"gaia build compile {host_path}\ngaia run infer {host_path}"),
    }
    emit(
        AuthorResult(verb="mount", status="ok", code=EXIT_OK, payload=payload),
        human=human,
    )


__all__ = ["mount_command"]
