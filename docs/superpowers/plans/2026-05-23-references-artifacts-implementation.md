# References Artifacts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the PR 694 PR-1 contract: artifact-as-note helpers, validation, `source_refs` deprecation, and `gaia author artifact/figure`.

**Architecture:** Keep artifact semantics at the authoring/metadata layer. `artifact()` and `figure()` create ordinary `note(...)` objects with `metadata["gaia"]["artifact"]`; compiler validation reads that metadata and the existing label/reference scanner continues to resolve `[@artifact_label]`. CLI commands generate those helpers through the existing `ProposedAuthorOp` and writer pipeline.

**Tech Stack:** Python 3.12, Gaia Lang runtime/DSL, Typer CLI, pytest.

---

## File Structure

- Create `gaia/engine/lang/dsl/artifacts.py`: owns artifact kind constants, metadata construction, lexical metadata validation, and the `artifact()` / `figure()` helper functions.
- Modify `gaia/engine/lang/dsl/__init__.py`: export the new helpers from the DSL package.
- Modify `gaia/engine/lang/__init__.py`: export the new helpers from the public `gaia.engine.lang` surface.
- Modify `gaia/engine/lang/compiler/compile.py`: validate artifact metadata during compile and warn on legacy reference fields.
- Modify `gaia/engine/lang/dsl/support.py`: deprecate `observe(source_refs=...)` with warnings while preserving current storage.
- Create `gaia/cli/commands/author/artifact.py`: implement `gaia author artifact` and `gaia author figure`.
- Modify `gaia/cli/commands/author/__init__.py`: export CLI command callables.
- Modify `gaia/cli/main.py`: register `author artifact` and `author figure`.
- Modify `tests/cli/author/conftest.py`: import `artifact` and `figure` in fixture packages.
- Create `tests/gaia/lang/test_artifacts.py`: unit tests for helpers and compile-time validation.
- Create `tests/cli/author/test_artifact.py`: CLI tests for artifact and figure authoring.
- Modify `tests/gaia/lang/test_observe_continuous.py`: assert `source_refs` emits `DeprecationWarning`.
- Modify `tests/cli/author/test_observe.py`: assert CLI output still writes `source_refs` and surfaces the deprecation only during check-capable flows if applicable.
- Modify repo-bundled skills/docs after code is green: remove examples that emit `refs`, `source_paper` as canonical data, or `metadata={"figure": ...}`.

## Task 1: Artifact DSL Helpers

**Files:**
- Create: `gaia/engine/lang/dsl/artifacts.py`
- Modify: `gaia/engine/lang/dsl/__init__.py`
- Modify: `gaia/engine/lang/__init__.py`
- Test: `tests/gaia/lang/test_artifacts.py`

- [ ] **Step 1: Write failing helper tests**

Add `tests/gaia/lang/test_artifacts.py`:

```python
from __future__ import annotations

import pytest

from gaia.engine.lang import artifact, figure
from gaia.engine.lang.runtime.knowledge import KnowledgeType


def test_artifact_returns_note_with_gaia_artifact_metadata() -> None:
    node = artifact(
        kind="attachment",
        source="Liu2015",
        locator="Supplementary Data 1",
        path="artifacts/attachments/liu2015.xlsx",
        description="Digitized source data.",
    )

    assert node.type == KnowledgeType.NOTE
    assert node.content == "Digitized source data."
    assert node.metadata["gaia"]["artifact"] == {
        "kind": "attachment",
        "source": "Liu2015",
        "locator": "Supplementary Data 1",
        "path": "artifacts/attachments/liu2015.xlsx",
        "description": "Digitized source data.",
    }


def test_figure_is_artifact_sugar() -> None:
    node = figure(
        source="Liu2015",
        locator="Fig. 3",
        path="artifacts/figures/liu2015_fig3.png",
        caption="Fibonacci scaling.",
    )

    assert node.type == KnowledgeType.NOTE
    assert node.content == "Fibonacci scaling."
    assert node.metadata["gaia"]["artifact"]["kind"] == "figure"
    assert node.metadata["gaia"]["artifact"]["caption"] == "Fibonacci scaling."


def test_artifact_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="artifact kind"):
        artifact(kind="movie", path="artifacts/movie.mp4")


def test_artifact_requires_source_or_path() -> None:
    with pytest.raises(ValueError, match="source or path"):
        artifact(kind="dataset", description="No anchor.")


def test_figure_requires_source_bound_locator() -> None:
    with pytest.raises(ValueError, match="locator"):
        figure(source="Liu2015", caption="Missing locator.")
```

- [ ] **Step 2: Run helper tests and verify they fail**

Run:

```bash
python -m pytest tests/gaia/lang/test_artifacts.py -q
```

Expected: import failure for `artifact` / `figure`.

- [ ] **Step 3: Add the helper module**

Create `gaia/engine/lang/dsl/artifacts.py`:

```python
"""Artifact-as-note helpers for Gaia Lang."""

from __future__ import annotations

from pathlib import PurePosixPath
from typing import Any

from gaia.engine.lang.dsl.knowledge import note
from gaia.engine.lang.runtime import Note

ARTIFACT_KINDS = frozenset({"figure", "table", "dataset", "notebook", "attachment"})
_LOCATOR_REQUIRED_WITH_SOURCE = frozenset({"figure", "table"})


def _validate_relative_artifact_path(path: str) -> None:
    parsed = PurePosixPath(path)
    if parsed.is_absolute() or ".." in parsed.parts:
        raise ValueError(
            "artifact path must be package-relative and must not escape the package root"
        )


def build_artifact_metadata(
    *,
    kind: str,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
) -> dict[str, Any]:
    """Build and validate metadata for a Gaia artifact note."""
    if kind not in ARTIFACT_KINDS:
        allowed = ", ".join(sorted(ARTIFACT_KINDS))
        raise ValueError(f"artifact kind {kind!r} is not supported; expected one of: {allowed}")
    if not source and not path:
        raise ValueError("artifact metadata requires at least one of source or path")
    if source and kind in _LOCATOR_REQUIRED_WITH_SOURCE and not locator:
        raise ValueError(f"artifact kind {kind!r} requires locator when source is set")
    if path is not None:
        _validate_relative_artifact_path(path)
    artifact: dict[str, Any] = {"kind": kind}
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
    ):
        if value is not None:
            artifact[key] = value
    return artifact


def artifact(
    *,
    kind: str,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
    content: str | None = None,
    title: str | None = None,
) -> Note:
    """Create a note carrying structured artifact metadata."""
    artifact_meta = build_artifact_metadata(
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
    )
    note_content = content or caption or description or locator or path or source or kind
    return note(note_content, title=title, metadata={"gaia": {"artifact": artifact_meta}})


def figure(
    *,
    source: str | None = None,
    locator: str | None = None,
    path: str | None = None,
    caption: str | None = None,
    description: str | None = None,
    media_type: str | None = None,
    content: str | None = None,
    title: str | None = None,
) -> Note:
    """Create a figure artifact note."""
    return artifact(
        kind="figure",
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )


__all__ = ["ARTIFACT_KINDS", "artifact", "build_artifact_metadata", "figure"]
```

- [ ] **Step 4: Export helpers**

In `gaia/engine/lang/dsl/__init__.py`, add:

```python
from gaia.engine.lang.dsl.artifacts import artifact, figure
```

and add `"artifact"` and `"figure"` to `__all__`.

In `gaia/engine/lang/__init__.py`, include `artifact` and `figure` in the `from gaia.engine.lang.dsl import (...)` block and add both names to `__all__`.

- [ ] **Step 5: Run helper tests**

Run:

```bash
python -m pytest tests/gaia/lang/test_artifacts.py -q
```

Expected: all tests in the file pass.

## Task 2: Compile-Time Artifact Validation and Legacy Warnings

**Files:**
- Modify: `gaia/engine/lang/compiler/compile.py`
- Test: `tests/gaia/lang/test_artifacts.py`

- [ ] **Step 1: Add failing compile validation tests**

Append to `tests/gaia/lang/test_artifacts.py`:

```python
import warnings

from gaia.engine.lang import claim, note
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import package


def test_compile_rejects_artifact_source_missing_from_references() -> None:
    fig = figure(source="Missing2015", locator="Fig. 3")

    with package("artifact_source_missing") as pkg:
        pkg.add(fig)

    with pytest.raises(Exception, match="Missing2015"):
        compile_package_artifact(pkg, references={})


def test_compile_resolves_artifact_label_as_local_reference() -> None:
    fig = figure(source="Liu2015", locator="Fig. 3", caption="A figure.")
    c = claim("See [@fig3].")

    with package("artifact_reference") as pkg:
        fig.label = "fig3"
        c.label = "claim1"
        pkg.add(fig)
        pkg.add(c)

    compiled = compile_package_artifact(
        pkg,
        references={"Liu2015": {"id": "Liu2015", "type": "article-journal", "title": "T"}},
    )
    by_id = {k.id: k for k in compiled.graph.knowledges}
    assert by_id["github:artifact_reference::claim1"].metadata["gaia"]["provenance"][
        "referenced_claims"
    ] == ["github:artifact_reference::fig3"]


def test_compile_warns_on_legacy_refs_metadata() -> None:
    c = claim("Legacy metadata.", refs=[{"type": "citation", "key": "Liu2015"}])

    with package("legacy_refs") as pkg:
        c.label = "legacy"
        pkg.add(c)

    with pytest.warns(DeprecationWarning, match="refs"):
        compile_package_artifact(pkg)


def test_compile_warns_on_source_paper_metadata() -> None:
    c = claim("Legacy source paper.", source_paper="Liu2015")

    with package("legacy_source_paper") as pkg:
        c.label = "legacy"
        pkg.add(c)

    with pytest.warns(DeprecationWarning, match="source_paper"):
        compile_package_artifact(pkg)
```

- [ ] **Step 2: Run validation tests and verify they fail**

Run:

```bash
python -m pytest tests/gaia/lang/test_artifacts.py -q
```

Expected: source-missing and warning tests fail because compiler validation is not wired.

- [ ] **Step 3: Wire validation into compiler**

In `gaia/engine/lang/compiler/compile.py`, import the validator helpers:

```python
from gaia.engine.lang.dsl.artifacts import ARTIFACT_KINDS
```

Add helper functions near `_knowledge_metadata`:

```python
def _warn_legacy_reference_metadata(metadata: dict[str, Any]) -> None:
    for key in ("refs", "source_paper"):
        if key in metadata:
            warnings.warn(
                f"metadata[{key!r}] is deprecated for Gaia references; use body "
                "[@CitationKey] markers or metadata['gaia']['artifact'] instead.",
                DeprecationWarning,
                stacklevel=3,
            )
    if "figure" in metadata or "caption" in metadata:
        warnings.warn(
            "top-level figure/caption metadata is deprecated; use "
            "metadata['gaia']['artifact'] with kind='figure'.",
            DeprecationWarning,
            stacklevel=3,
        )


def _validate_artifact_metadata(
    knowledge: Knowledge,
    *,
    references: dict[str, Any],
) -> None:
    artifact = (knowledge.metadata.get("gaia") or {}).get("artifact")
    if artifact is None:
        return
    if not isinstance(artifact, dict):
        raise ValueError("metadata['gaia']['artifact'] must be a dict")
    kind = artifact.get("kind")
    if kind not in ARTIFACT_KINDS:
        raise ValueError(f"artifact kind {kind!r} is not supported")
    source = artifact.get("source")
    path = artifact.get("path")
    if not source and not path:
        raise ValueError("artifact metadata requires at least one of source or path")
    if source is not None and source not in references:
        raise ReferenceError(
            f"artifact source {source!r} on {knowledge.label or knowledge.content!r} "
            "does not exist in references.json"
        )
    locator = artifact.get("locator")
    if source and kind in {"figure", "table"} and not locator:
        raise ValueError(f"source-bound artifact kind {kind!r} requires locator")
    if path is not None:
        parsed = PurePosixPath(str(path))
        if parsed.is_absolute() or ".." in parsed.parts:
            raise ValueError(
                f"artifact path {path!r} must be package-relative and must not escape root"
            )
```

Also add imports at the top:

```python
import warnings
from pathlib import PurePosixPath
```

Call `_warn_legacy_reference_metadata(metadata)` inside `_knowledge_metadata()` after copying metadata.
Call `_validate_artifact_metadata(knowledge, references=self.references)` from `_ReferenceScanner.scan()`
before `check_collisions(...)`.

- [ ] **Step 4: Run focused tests**

Run:

```bash
python -m pytest tests/gaia/lang/test_artifacts.py tests/gaia/lang/refs tests/gaia/lang/compiler/test_refs_integration.py -q
```

Expected: all selected tests pass.

## Task 3: Deprecate `observe(source_refs=...)`

**Files:**
- Modify: `gaia/engine/lang/dsl/support.py`
- Test: `tests/gaia/lang/test_observe_continuous.py`
- Test: `tests/cli/author/test_observe.py`

- [ ] **Step 1: Write failing deprecation tests**

In `tests/gaia/lang/test_observe_continuous.py`, change the existing source-ref test to:

```python
def test_observe_distribution_records_source_refs_with_deprecation_warning():
    T_c = Normal("T_c", mu=200, sigma=20)
    with pytest.warns(DeprecationWarning, match="source_refs"):
        obs = observe(T_c, value=203, error=5, source_refs=["Drozdov 2015"])
    assert obs.metadata.get("source_refs") == ["Drozdov 2015"]
```

In `tests/cli/author/test_observe.py`, add:

```python
def test_observe_source_refs_still_renders_for_transition(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "observe",
            "--conclusion",
            "hypothesis",
            "--source-refs",
            "Drozdov2015",
            "--dsl-binding-name",
            "obs_with_legacy_source",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "source_refs=['Drozdov2015']" in written
```

- [ ] **Step 2: Run deprecation tests and verify failure**

Run:

```bash
python -m pytest tests/gaia/lang/test_observe_continuous.py::test_observe_distribution_records_source_refs_with_deprecation_warning tests/cli/author/test_observe.py::test_observe_source_refs_still_renders_for_transition -q
```

Expected: the first test fails because no warning is emitted.

- [ ] **Step 3: Emit warning in DSL**

In `gaia/engine/lang/dsl/support.py`, add:

```python
import warnings
```

Add helper near `_OBSERVE_VALUE_SENTINEL`:

```python
def _warn_source_refs_deprecated(source_refs: list[str] | None) -> None:
    if source_refs:
        warnings.warn(
            "observe(source_refs=...) is deprecated; put citations in rationale "
            "with [@CitationKey] so the reference scanner can resolve them.",
            DeprecationWarning,
            stacklevel=3,
        )
```

Call `_warn_source_refs_deprecated(source_refs)` at the top of `observe()` after the docstring and
before dispatching to distribution/variable/discrete branches.

- [ ] **Step 4: Run deprecation tests**

Run:

```bash
python -m pytest tests/gaia/lang/test_observe_continuous.py::test_observe_distribution_records_source_refs_with_deprecation_warning tests/cli/author/test_observe.py::test_observe_source_refs_still_renders_for_transition -q
```

Expected: both tests pass.

## Task 4: CLI Artifact and Figure Commands

**Files:**
- Create: `gaia/cli/commands/author/artifact.py`
- Modify: `gaia/cli/commands/author/__init__.py`
- Modify: `gaia/cli/main.py`
- Modify: `tests/cli/author/conftest.py`
- Test: `tests/cli/author/test_artifact.py`

- [ ] **Step 1: Update fixture imports**

In `tests/cli/author/conftest.py`, add `artifact` and `figure` to `_INIT_TEMPLATE` imports:

```python
from gaia.engine.lang import (
    ClaimAtom,
    artifact,
    associate,
    candidate_relation,
    claim,
    compute,
    contradict,
    decompose,
    depends_on,
    derive,
    equal,
    exclusive,
    figure,
    iff,
    implies,
    infer,
    land,
    lnot,
    lor,
    materialize,
    note,
    observe,
    parameter,
    question,
    register_prior,
)
```

- [ ] **Step 2: Write failing CLI tests**

Create `tests/cli/author/test_artifact.py`:

```python
"""CLI E2E tests for ``gaia author artifact`` and ``gaia author figure``."""

from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app

from .conftest import FixturePackage

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _parse(output: str) -> dict[str, object]:
    for line in reversed(output.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            return json.loads(line)
    raise AssertionError(f"no JSON envelope in output: {output!r}")


def test_author_artifact_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "liu2015_supplement",
            "--kind",
            "attachment",
            "--source",
            "Liu2015",
            "--locator",
            "Supplementary Data 1",
            "--path",
            "artifacts/attachments/liu2015.xlsx",
            "--description",
            "Digitized source data.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    envelope = _parse(result.output)
    assert envelope["verb"] == "artifact"
    written = gaia_package.source_init.read_text()
    assert "liu2015_supplement = artifact(" in written
    assert "kind='attachment'" in written
    assert "source='Liu2015'" in written
    assert "path='artifacts/attachments/liu2015.xlsx'" in written


def test_author_figure_happy_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "figure",
            "--dsl-binding-name",
            "liu2015_fig3",
            "--source",
            "Liu2015",
            "--locator",
            "Fig. 3",
            "--path",
            "artifacts/figures/liu2015_fig3.png",
            "--caption",
            "Fibonacci scaling.",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 0, result.output
    written = gaia_package.source_init.read_text()
    assert "liu2015_fig3 = figure(" in written
    assert "source='Liu2015'" in written
    assert "locator='Fig. 3'" in written
    assert "caption='Fibonacci scaling.'" in written


def test_author_artifact_rejects_unsafe_path(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "bad_artifact",
            "--kind",
            "attachment",
            "--path",
            "../escape.txt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 2
    envelope = _parse(result.output)
    diagnostics = envelope["diagnostics"]
    assert isinstance(diagnostics, list)
    assert diagnostics[0]["kind"] == "prewrite.syntax"


def test_author_artifact_collision_exits_3(gaia_package: FixturePackage) -> None:
    result = runner.invoke(
        app,
        [
            "author",
            "artifact",
            "--dsl-binding-name",
            "hypothesis",
            "--kind",
            "attachment",
            "--path",
            "artifacts/file.txt",
            "--target",
            str(gaia_package.root),
            "--no-check",
        ],
    )
    assert result.exit_code == 3
```

- [ ] **Step 3: Run CLI tests and verify they fail**

Run:

```bash
python -m pytest tests/cli/author/test_artifact.py -q
```

Expected: command is not registered or import fails.

- [ ] **Step 4: Implement author command module**

Create `gaia/cli/commands/author/artifact.py`:

```python
"""``gaia author artifact`` and ``gaia author figure`` commands."""

from __future__ import annotations

from pathlib import PurePosixPath

import typer

from gaia.cli.commands.author._common import emit_syntax_error, normalize_file_option
from gaia.cli.commands.author._proposed_op import ProposedAuthorOp
from gaia.cli.commands.author._runner import run_author_op
from gaia.engine.lang.dsl.artifacts import ARTIFACT_KINDS, build_artifact_metadata


def _validate_cli_artifact(
    *,
    verb: str,
    kind: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    target: str,
    human: bool,
) -> bool:
    try:
        build_artifact_metadata(
            kind=kind,
            source=source,
            locator=locator,
            path=path,
            caption=caption,
            description=description,
            media_type=media_type,
        )
    except ValueError as exc:
        emit_syntax_error(verb, str(exc), target=target, human=human)
        return False
    if path is not None:
        parsed = PurePosixPath(path)
        if parsed.is_absolute() or ".." in parsed.parts:
            emit_syntax_error(
                verb,
                "artifact --path must be package-relative and must not escape package root",
                target=target,
                human=human,
            )
            return False
    return True


def _render_artifact_statement(
    *,
    binding_name: str,
    kind: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    content: str | None,
    title: str | None,
) -> str:
    kwargs = [f"kind={kind!r}"]
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
        ("content", content),
        ("title", title),
    ):
        if value is not None:
            kwargs.append(f"{key}={value!r}")
    return f"{binding_name} = artifact({', '.join(kwargs)})"


def _render_figure_statement(
    *,
    binding_name: str,
    source: str | None,
    locator: str | None,
    path: str | None,
    caption: str | None,
    description: str | None,
    media_type: str | None,
    content: str | None,
    title: str | None,
) -> str:
    kwargs: list[str] = []
    for key, value in (
        ("source", source),
        ("locator", locator),
        ("path", path),
        ("caption", caption),
        ("description", description),
        ("media_type", media_type),
        ("content", content),
        ("title", title),
    ):
        if value is not None:
            kwargs.append(f"{key}={value!r}")
    return f"{binding_name} = figure({', '.join(kwargs)})"


def artifact_command(
    dsl_binding_name: str = typer.Option(
        ..., "--dsl-binding-name", help="Python module-scope identifier to bind."
    ),
    kind: str = typer.Option(..., "--kind", help=f"Artifact kind: {', '.join(sorted(ARTIFACT_KINDS))}."),
    source: str | None = typer.Option(None, "--source", help="Citation key in references.json."),
    locator: str | None = typer.Option(None, "--locator", help="Source-local locator."),
    path: str | None = typer.Option(None, "--path", help="Package-relative artifact path."),
    caption: str | None = typer.Option(None, "--caption", help="Caption for visual artifacts."),
    description: str | None = typer.Option(None, "--description", help="Description for attachments."),
    media_type: str | None = typer.Option(None, "--media-type", help="Optional MIME type."),
    content: str | None = typer.Option(None, "--content", help="Override note content."),
    title: str | None = typer.Option(None, "--title", help="Optional note title."),
    target: str = typer.Option(".", "--target", help="Path to the target Gaia package."),
    file: str | None = typer.Option(None, "--file", help="Relative module file under src/<import_name>."),
    export: bool = typer.Option(False, "--export/--no-export", help="Export the artifact binding."),
    check: bool = typer.Option(True, "--check/--no-check", help="Run post-write build check."),
    human: bool = typer.Option(False, "--human", help="Render human-readable output."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt on pre-write warnings."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output."),
) -> None:
    del json_
    if not _validate_cli_artifact(
        verb="artifact",
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        target=str(target),
        human=human,
    ):
        return
    generated_code = _render_artifact_statement(
        binding_name=dsl_binding_name,
        kind=kind,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )
    proposed_op = ProposedAuthorOp(
        verb="artifact",
        kind="reasoning",
        label=dsl_binding_name,
        references=[],
        generated_code=generated_code,
        required_imports=("artifact",),
        target_file=normalize_file_option(file),
        export=export,
    )
    run_author_op(proposed_op, target=target, human=human, check=check, interactive=interactive)


def figure_command(
    dsl_binding_name: str = typer.Option(
        ..., "--dsl-binding-name", help="Python module-scope identifier to bind."
    ),
    source: str | None = typer.Option(None, "--source", help="Citation key in references.json."),
    locator: str | None = typer.Option(None, "--locator", help="Source-local figure locator."),
    path: str | None = typer.Option(None, "--path", help="Package-relative image path."),
    caption: str | None = typer.Option(None, "--caption", help="Figure caption."),
    description: str | None = typer.Option(None, "--description", help="Optional description."),
    media_type: str | None = typer.Option(None, "--media-type", help="Optional MIME type."),
    content: str | None = typer.Option(None, "--content", help="Override note content."),
    title: str | None = typer.Option(None, "--title", help="Optional note title."),
    target: str = typer.Option(".", "--target", help="Path to the target Gaia package."),
    file: str | None = typer.Option(None, "--file", help="Relative module file under src/<import_name>."),
    export: bool = typer.Option(False, "--export/--no-export", help="Export the figure binding."),
    check: bool = typer.Option(True, "--check/--no-check", help="Run post-write build check."),
    human: bool = typer.Option(False, "--human", help="Render human-readable output."),
    interactive: bool = typer.Option(False, "--interactive", help="Prompt on pre-write warnings."),
    json_: bool = typer.Option(True, "--json/--no-json", help="JSON-first output."),
) -> None:
    del json_
    if not _validate_cli_artifact(
        verb="figure",
        kind="figure",
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        target=str(target),
        human=human,
    ):
        return
    generated_code = _render_figure_statement(
        binding_name=dsl_binding_name,
        source=source,
        locator=locator,
        path=path,
        caption=caption,
        description=description,
        media_type=media_type,
        content=content,
        title=title,
    )
    proposed_op = ProposedAuthorOp(
        verb="figure",
        kind="reasoning",
        label=dsl_binding_name,
        references=[],
        generated_code=generated_code,
        required_imports=("figure",),
        target_file=normalize_file_option(file),
        export=export,
    )
    run_author_op(proposed_op, target=target, human=human, check=check, interactive=interactive)


__all__ = ["artifact_command", "figure_command"]
```

- [ ] **Step 5: Register commands**

In `gaia/cli/commands/author/__init__.py`, import `artifact_command` and `figure_command`, then add
them to `__all__`.

In `gaia/cli/main.py`, import both commands and register them under the knowledge tier:

```python
author_app.command(name="artifact")(artifact_command)
author_app.command(name="figure")(figure_command)
```

Also update the author help strings to include `artifact / figure`.

- [ ] **Step 6: Run CLI tests**

Run:

```bash
python -m pytest tests/cli/author/test_artifact.py tests/cli/author/test_note.py -q
```

Expected: artifact, figure, and note CLI tests pass.

## Task 5: Docs and Repo-Bundled Skill Cleanup

**Files:**
- Modify: `docs/for-users/language-reference.md`
- Modify: `docs/specs/2026-04-09-references-and-at-syntax.md`
- Modify: repo-bundled files under `gaia/_skills/`
- Test: focused text search and selected tests

- [ ] **Step 1: Locate legacy examples**

Run:

```bash
rg -n "source_refs|source_paper|refs=|metadata=\\{[\"']figure|\\brefs:" docs gaia/_skills tests examples
```

Expected: list of old examples to migrate or document as legacy.

- [ ] **Step 2: Update user language reference**

In `docs/for-users/language-reference.md`, add a concise “References, Citations, and Artifacts”
section that includes these examples:

```python
claim("Bell inequalities are violated in experiment [@Aspect1982].")
note("See the source-bound figure [@liu2015_fig3].")
liu2015_fig3 = figure(
    source="Liu2015",
    locator="Fig. 3",
    path="artifacts/figures/liu2015_fig3.png",
    caption="Fibonacci scaling of the order parameter.",
)
```

State that `claim(provenance=[...])` is package/version provenance, not bibliographic citation.
Replace `observe(..., source_refs=[...])` examples with `rationale="... [@Key]"`.

- [ ] **Step 3: Update repo-bundled skills**

For `gaia/_skills/gaia-formalize-coarse/...` and `gaia/_skills/gaia-formalize-fine/...`, replace
examples that emit `refs` or `metadata={"figure": ...}` with the artifact-note pattern:

```python
source_fig = figure(
    source="SourceKey",
    locator="Fig. 1",
    path="artifacts/figures/source_fig1.png",
    caption="Short caption.",
)
```

and reference it from claims with `[@source_fig]` or `background=[source_fig]`.

- [ ] **Step 4: Update 2026-04-09 spec status**

Change the status line in `docs/specs/2026-04-09-references-and-at-syntax.md` to say the core
reference scanner is implemented, while renderer/artifact integration is tracked by the 2026-05-23
spec.

- [ ] **Step 5: Search for unintentional old-form recommendations**

Run:

```bash
rg -n "source_refs|source_paper|refs=|metadata=\\{[\"']figure|\\brefs:" docs gaia/_skills
```

Expected: remaining hits are either historical discussion in specs or explicit deprecation warnings,
not active authoring recommendations.

## Task 6: Final Verification

**Files:**
- No new files unless verification exposes a targeted fix.

- [ ] **Step 1: Run focused unit and CLI tests**

Run:

```bash
python -m pytest tests/gaia/lang/test_artifacts.py tests/gaia/lang/test_observe_continuous.py tests/gaia/lang/refs tests/gaia/lang/compiler/test_refs_integration.py tests/cli/author/test_artifact.py tests/cli/author/test_observe.py tests/cli/author/test_note.py -q
```

Expected: selected tests pass.

- [ ] **Step 2: Run a manual compile probe**

Create a temporary package with `gaia build init`, add `references.json`, author one figure and one
claim referencing it, then compile:

```bash
tmpdir="$(mktemp -d)"
python -m gaia.cli.main build init "$tmpdir/artifact-probe-gaia"
cd "$tmpdir/artifact-probe-gaia"
printf '[{"id":"Liu2015","type":"article-journal","title":"Probe"}]\n' > references.json
python -m gaia.cli.main author figure --dsl-binding-name liu2015_fig3 --source Liu2015 --locator "Fig. 3" --caption "Probe figure." --no-check
python -m gaia.cli.main author claim "See [@liu2015_fig3] and [@Liu2015]." --dsl-binding-name probe_claim --no-check
python -m gaia.cli.main build compile .
```

Expected: compile succeeds and `.gaia/ir.json` contains `liu2015_fig3` as a note with
`metadata.gaia.artifact.kind == "figure"`.

- [ ] **Step 3: Run lint-style checks used by this repo**

Run:

```bash
python -m pytest tests/cli/author/test_artifact.py tests/gaia/lang/test_artifacts.py -q
```

Expected: repeated focused slice passes after docs/skill edits.

- [ ] **Step 4: Commit implementation**

Run:

```bash
git add gaia tests docs
git commit -m "feat: add artifact reference authoring"
```

Expected: one implementation commit after the existing design and plan commits.
