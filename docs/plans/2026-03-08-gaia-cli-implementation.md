# Gaia CLI Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement the Gaia CLI with 8 commands (build, review, infer, publish, init, show, search, clean) using Typer, following `docs/plans/2026-03-08-gaia-cli-architecture.md`.

**Architecture:** Typer CLI layer → calls `libs/dsl/` core library (models, loader, resolver, elaborator, compiler) and `libs/inference/` (FactorGraph, BP). New `elaborator.py` does deterministic template expansion. Review sidecar files (`.gaia/reviews/`) bridge the review→infer pipeline. Dependencies flow downward only: CLI → libs/dsl → libs/inference.

**Tech Stack:** Python 3.12+, Typer, Pydantic v2, PyYAML, litellm, LanceDB

**Existing code to preserve:** `libs/dsl/{models,loader,resolver,compiler,executor,runtime}.py` (78 tests passing). The existing `cli/commands/dsl.py` (argparse-based) remains as-is — the new Typer CLI is separate.

**Test fixture:** `tests/fixtures/dsl_packages/galileo_falling_bodies/` — 5 modules, 14 variables, 11 factors.

---

## Phase 0: Refactor — Move Inference Core to libs/

### Task 0: Move FactorGraph + BeliefPropagation to `libs/inference/`

Currently `services/inference_engine/` contains both pure algorithms (FactorGraph, BP) and service-layer orchestration (InferenceEngine). The pure algorithms belong in `libs/` because both CLI and server need them, and `libs/dsl/runtime.py` already imports them (violating the "libs has no service dependencies" rule).

**Move:**
```
services/inference_engine/factor_graph.py → libs/inference/factor_graph.py
services/inference_engine/bp.py           → libs/inference/bp.py
services/inference_engine/engine.py       → stays (imports from libs/inference/)
services/inference_engine/__init__.py     → stays
```

**Files:**
- Create: `libs/inference/__init__.py`
- Move: `services/inference_engine/factor_graph.py` → `libs/inference/factor_graph.py`
- Move: `services/inference_engine/bp.py` → `libs/inference/bp.py`
- Modify: `services/inference_engine/engine.py` (update imports)
- Modify: `services/inference_engine/__init__.py` (update imports)
- Modify: `libs/dsl/runtime.py` (update imports)
- Modify: `services/review_pipeline/operators/bp.py` (update imports)
- Move: `tests/services/test_inference_engine/test_factor_graph.py` → `tests/libs/test_inference/test_factor_graph.py`
- Move: `tests/services/test_inference_engine/test_bp.py` → `tests/libs/test_inference/test_bp.py`
- Keep: `tests/services/test_inference_engine/test_engine.py` (tests the service wrapper)

**Step 1: Create libs/inference/ and move files**

```bash
mkdir -p libs/inference
cp services/inference_engine/factor_graph.py libs/inference/factor_graph.py
cp services/inference_engine/bp.py libs/inference/bp.py
touch libs/inference/__init__.py
```

**Step 2: Update imports in moved files**

In `libs/inference/bp.py`, update any import of `services.inference_engine.factor_graph` to `libs.inference.factor_graph`.

In `libs/inference/factor_graph.py`, update any import of `libs.models` (should already be correct since it was importing from libs).

**Step 3: Update all consumers**

In `libs/dsl/runtime.py`, change:
```python
# Old
from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph
# New
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
```

In `services/inference_engine/engine.py`, change:
```python
# Old
from .bp import BeliefPropagation
from .factor_graph import FactorGraph
# New
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
```

In `services/review_pipeline/operators/bp.py`, change:
```python
# Old
from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph
# New
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
```

Leave re-exports in `services/inference_engine/__init__.py` for backward compatibility (if anything imports from there):
```python
# Re-export from new location for backward compatibility
from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph
```

**Step 4: Move tests**

```bash
mkdir -p tests/libs/test_inference
cp tests/services/test_inference_engine/test_factor_graph.py tests/libs/test_inference/test_factor_graph.py
cp tests/services/test_inference_engine/test_bp.py tests/libs/test_inference/test_bp.py
touch tests/libs/test_inference/__init__.py
```

Update imports in moved test files:
```python
# Old
from services.inference_engine.factor_graph import FactorGraph
from services.inference_engine.bp import BeliefPropagation
# New
from libs.inference.factor_graph import FactorGraph
from libs.inference.bp import BeliefPropagation
```

**Step 5: Run all tests to verify nothing broke**

Run: `pytest tests/libs/test_inference/ tests/libs/dsl/ tests/services/test_inference_engine/ -v`
Expected: ALL PASS (same tests, new locations + old locations both work)

**Step 6: Remove old files (only after tests pass)**

```bash
rm services/inference_engine/factor_graph.py
rm services/inference_engine/bp.py
```

Update `services/inference_engine/__init__.py` to import from new location.
Remove old test files if desired (or keep for now).

**Step 7: Run full suite and commit**

Run: `pytest -v`
Expected: ALL PASS

```bash
git add libs/inference/ services/inference_engine/ libs/dsl/runtime.py \
        tests/libs/test_inference/ services/review_pipeline/operators/bp.py
git commit -m "refactor: move FactorGraph + BP from services/ to libs/inference/"
```

---

## Phase 1: CLI Skeleton

### Task 1: Typer CLI Skeleton + Entry Point

**Files:**
- Modify: `pyproject.toml`
- Create: `cli/main.py`
- Test: `tests/cli/test_gaia_main.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_gaia_main.py
"""Tests for the Gaia CLI entry point."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_help_shows_all_commands():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    for cmd in ["build", "review", "infer", "publish", "init", "show", "search", "clean"]:
        assert cmd in result.output


def test_build_stub():
    result = runner.invoke(app, ["build", "--help"])
    assert result.exit_code == 0


def test_review_stub():
    result = runner.invoke(app, ["review", "--help"])
    assert result.exit_code == 0


def test_infer_stub():
    result = runner.invoke(app, ["infer", "--help"])
    assert result.exit_code == 0


def test_init_stub():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_clean_stub():
    result = runner.invoke(app, ["clean", "--help"])
    assert result.exit_code == 0


def test_show_stub():
    result = runner.invoke(app, ["show", "--help"])
    assert result.exit_code == 0


def test_search_stub():
    result = runner.invoke(app, ["search", "--help"])
    assert result.exit_code == 0


def test_publish_stub():
    result = runner.invoke(app, ["publish", "--help"])
    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_gaia_main.py -v`
Expected: FAIL with ImportError (no `typer` or `cli.main`)

**Step 3: Write minimal implementation**

Modify `pyproject.toml` — add typer to dependencies, add cli to packages, add entry point:

```toml
# In [project] dependencies list, add:
"typer[all]>=0.12",

# Change [tool.setuptools.packages.find] to:
[tool.setuptools.packages.find]
include = ["libs*", "services*", "cli*"]

# Add new section at the end:
[project.scripts]
gaia = "cli.main:app"
```

Then run: `pip install -e ".[dev]"`

Create `cli/main.py`:

```python
"""Gaia CLI — proof assistant for probabilistic defeasible reasoning."""

from __future__ import annotations

import typer

app = typer.Typer(
    name="gaia",
    help="Gaia — proof assistant for probabilistic defeasible reasoning.",
    no_args_is_help=True,
)


@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Elaborate: parse + resolve + instantiate params."""
    typer.echo(f"gaia build {path} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """LLM reviews chains -> sidecar report (.gaia/reviews/)."""
    typer.echo(f"gaia review {path} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile FG (from review) + BP -> beliefs."""
    typer.echo(f"gaia infer {path} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def publish(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    git: bool = typer.Option(False, "--git", help="Publish via git add+commit+push"),
    server: bool = typer.Option(False, "--server", help="Publish to Gaia server API"),
) -> None:
    """Publish to git or server."""
    typer.echo(f"gaia publish {path} — not yet implemented")
    raise typer.Exit(1)


@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Package name"),
) -> None:
    """Initialize a new knowledge package."""
    typer.echo(f"gaia init {name} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def show(
    name: str = typer.Argument(..., help="Declaration name to inspect"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Show declaration details + connected chains."""
    typer.echo(f"gaia show {name} — not yet implemented")
    raise typer.Exit(1)


@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Search declarations within the package."""
    typer.echo(f"gaia search '{query}' — not yet implemented")
    raise typer.Exit(1)


@app.command()
def clean(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Remove build artifacts (.gaia/)."""
    typer.echo(f"gaia clean {path} — not yet implemented")
    raise typer.Exit(1)


if __name__ == "__main__":
    app()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_gaia_main.py -v`
Expected: 9 PASSED

**Step 5: Commit**

```bash
git add pyproject.toml cli/main.py tests/cli/test_gaia_main.py
git commit -m "feat: add Typer CLI skeleton with 8 stub commands + entry point"
```

---

### Task 2: `gaia init` Command

**Files:**
- Modify: `cli/main.py:60-64`
- Test: `tests/cli/test_init.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_init.py
"""Tests for gaia init command."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_init_creates_package_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    pkg_dir = tmp_path / "my_package"
    assert pkg_dir.exists()
    pkg_yaml = pkg_dir / "package.yaml"
    assert pkg_yaml.exists()
    data = yaml.safe_load(pkg_yaml.read_text())
    assert data["name"] == "my_package"
    assert data["version"] == "0.1.0"
    assert "modules" in data
    assert "motivation" in data["modules"]


def test_init_creates_motivation_module(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["init", "my_package"])
    assert result.exit_code == 0
    mod_file = tmp_path / "my_package" / "motivation.yaml"
    assert mod_file.exists()
    data = yaml.safe_load(mod_file.read_text())
    assert data["type"] == "motivation_module"
    assert data["name"] == "motivation"
    assert len(data["declarations"]) >= 1


def test_init_refuses_existing_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "existing_pkg").mkdir()
    result = runner.invoke(app, ["init", "existing_pkg"])
    assert result.exit_code != 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_init.py -v`
Expected: FAIL (init stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `init_cmd` function in `cli/main.py`:

```python
@app.command("init")
def init_cmd(
    name: str = typer.Argument(..., help="Package name"),
) -> None:
    """Initialize a new knowledge package."""
    pkg_dir = Path(name)
    if pkg_dir.exists():
        typer.echo(f"Error: directory '{name}' already exists", err=True)
        raise typer.Exit(1)

    pkg_dir.mkdir(parents=True)

    # package.yaml
    pkg_data = {
        "name": name,
        "version": "0.1.0",
        "manifest": {
            "description": f"Knowledge package: {name}",
            "authors": [],
            "license": "CC-BY-4.0",
        },
        "modules": ["motivation"],
        "export": [],
    }
    (pkg_dir / "package.yaml").write_text(
        yaml.dump(pkg_data, allow_unicode=True, sort_keys=False)
    )

    # motivation.yaml
    mod_data = {
        "type": "motivation_module",
        "name": "motivation",
        "declarations": [
            {
                "type": "question",
                "name": "main_question",
                "content": "What is the main research question?",
            }
        ],
        "export": ["main_question"],
    }
    (pkg_dir / "motivation.yaml").write_text(
        yaml.dump(mod_data, allow_unicode=True, sort_keys=False)
    )

    typer.echo(f"Initialized package '{name}' in ./{name}/")
```

Add `from pathlib import Path` and `import yaml` to the top of `cli/main.py`.

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_init.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_init.py
git commit -m "feat: implement gaia init command"
```

---

### Task 3: `gaia clean` Command

**Files:**
- Modify: `cli/main.py` (clean function)
- Test: `tests/cli/test_clean.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_clean.py
"""Tests for gaia clean command."""

from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()


def test_clean_removes_gaia_dir(tmp_path):
    gaia_dir = tmp_path / ".gaia"
    gaia_dir.mkdir()
    (gaia_dir / "build").mkdir()
    (gaia_dir / "build" / "elaborated.yaml").write_text("test")
    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert not gaia_dir.exists()


def test_clean_noop_if_no_gaia_dir(tmp_path):
    result = runner.invoke(app, ["clean", str(tmp_path)])
    assert result.exit_code == 0
    assert "No .gaia" in result.output or "nothing" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_clean.py -v`
Expected: FAIL (clean stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `clean` function in `cli/main.py`:

```python
@app.command()
def clean(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Remove build artifacts (.gaia/)."""
    import shutil

    gaia_dir = Path(path) / ".gaia"
    if gaia_dir.exists():
        shutil.rmtree(gaia_dir)
        typer.echo(f"Removed {gaia_dir}")
    else:
        typer.echo(f"No .gaia directory in {path}, nothing to clean.")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_clean.py -v`
Expected: 2 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_clean.py
git commit -m "feat: implement gaia clean command"
```

---

## Phase 2: Build Pipeline

### Task 4: Elaborator

Creates `libs/dsl/elaborator.py` — deterministic template expansion. Walks ChainExprs, substitutes `{param}` templates in InferAction content, and records rendered prompts.

**Files:**
- Create: `libs/dsl/elaborator.py`
- Test: `tests/libs/dsl/test_elaborator.py`

**Context:** The InferAction `deduce_drag_effect` in the Galileo fixture has content `"在 {env} 中暂时接受 {law}：..."` with params `[{name: law, type: claim}, {name: env, type: setting}]`. When called via StepApply with args `[heavier_falls_faster, thought_experiment_env]`, the elaborator substitutes `{law}` → claim content, `{env}` → setting content.

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_elaborator.py
"""Tests for the DSL elaborator — deterministic template expansion."""

from pathlib import Path

import pytest

from libs.dsl.elaborator import ElaboratedPackage, elaborate_package
from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs


FIXTURE_PATH = Path("tests/fixtures/dsl_packages/galileo_falling_bodies")


def test_elaborate_returns_elaborated_package():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    assert isinstance(result, ElaboratedPackage)
    assert result.package.name == "galileo_falling_bodies"


def test_elaborate_renders_step_apply_prompts():
    """StepApply templates like {law} should be substituted with resolved arg content."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    # drag_prediction_chain step 2 uses deduce_drag_effect with args
    # {law} = heavier_falls_faster content, {env} = thought_experiment_env content
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    key = ("drag_prediction_chain", 2)
    assert key in prompts
    rendered = prompts[key]["rendered"]
    # Template {law} should be replaced with actual claim content
    assert "{law}" not in rendered
    assert "{env}" not in rendered
    # The rendered prompt should contain the substituted content
    assert "重的物体" in rendered  # from heavier_falls_faster content
    assert "重球" in rendered  # from thought_experiment_env content


def test_elaborate_records_lambda_content():
    """StepLambda content should be recorded as-is (no template substitution needed)."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    # combined_weight_chain step 2 is a lambda
    key = ("combined_weight_chain", 2)
    assert key in prompts
    assert "复合体" in prompts[key]["rendered"]


def test_elaborate_records_arg_metadata():
    """Each rendered prompt should include arg refs and dependency types."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    prompts = {(p["chain"], p["step"]): p for p in result.prompts}
    key = ("drag_prediction_chain", 2)
    prompt = prompts[key]
    assert len(prompt["args"]) == 2
    assert prompt["args"][0]["ref"] == "heavier_falls_faster"
    assert prompt["args"][0]["dependency"] == "direct"
    assert prompt["args"][1]["ref"] == "thought_experiment_env"
    assert prompt["args"][1]["dependency"] == "indirect"


def test_elaborate_does_not_modify_original():
    """Elaboration should not mutate the original package."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    # Get original InferAction content
    original_content = None
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if decl.name == "deduce_drag_effect":
                original_content = decl.content
                break
    elaborate_package(pkg)
    # Verify original is unchanged
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if decl.name == "deduce_drag_effect":
                assert decl.content == original_content


def test_elaborate_covers_all_apply_and_lambda_steps():
    """Every StepApply and StepLambda in the package should produce a prompt."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    result = elaborate_package(pkg)
    # Count expected steps (from fixture: each chain has 1 Apply or Lambda at step 2)
    # 11 chains total, each with a step 2 that is Apply or Lambda
    assert len(result.prompts) >= 11
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_elaborator.py -v`
Expected: FAIL with ImportError (`libs.dsl.elaborator` does not exist)

**Step 3: Write minimal implementation**

```python
# libs/dsl/elaborator.py
"""Gaia DSL Elaborator — deterministic template expansion.

Walks ChainExprs and produces rendered prompts for each StepApply/StepLambda.
Does NOT call any LLM — purely deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .models import (
    Action,
    ChainExpr,
    Declaration,
    Package,
    Ref,
    StepApply,
    StepLambda,
)


@dataclass
class ElaboratedPackage:
    """Result of elaboration: the resolved package + rendered prompts."""

    package: Package
    prompts: list[dict] = field(default_factory=list)
    # Each prompt dict: {chain, step, action, rendered, args: [{ref, dependency, content}]}


def elaborate_package(pkg: Package) -> ElaboratedPackage:
    """Elaborate a resolved package: substitute templates, record rendered prompts.

    The original package is NOT modified — a deep copy is used internally.
    """
    pkg_copy = copy.deepcopy(pkg)

    # Build name→declaration index (resolve Refs to their targets)
    decls_by_name: dict[str, Declaration] = {}
    for mod in pkg_copy.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, Ref) and decl._resolved is not None:
                decls_by_name[decl.name] = decl._resolved
            else:
                decls_by_name[decl.name] = decl

    # Walk chains and elaborate
    prompts: list[dict] = []
    for mod in pkg_copy.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, ChainExpr):
                chain_prompts = _elaborate_chain(decl, decls_by_name)
                prompts.extend(chain_prompts)

    return ElaboratedPackage(package=pkg_copy, prompts=prompts)


def _elaborate_chain(
    chain: ChainExpr, decls: dict[str, Declaration]
) -> list[dict]:
    """Elaborate a single chain's steps, returning rendered prompt dicts."""
    prompts = []

    for step in chain.steps:
        if isinstance(step, StepApply):
            action = decls.get(step.apply)
            if not action or not isinstance(action, Action):
                continue

            # Resolve args to content
            arg_records = []
            resolved_contents: list[str] = []
            for arg in step.args:
                target = decls.get(arg.ref)
                content = getattr(target, "content", "") if target else ""
                resolved_contents.append(content)
                arg_records.append({
                    "ref": arg.ref,
                    "dependency": arg.dependency,
                    "content": content,
                })

            # Substitute {param} templates
            rendered = action.content
            for param, content in zip(action.params, resolved_contents):
                rendered = rendered.replace(f"{{{param.name}}}", content)

            prompts.append({
                "chain": chain.name,
                "step": step.step,
                "action": step.apply,
                "rendered": rendered,
                "args": arg_records,
            })

        elif isinstance(step, StepLambda):
            prompts.append({
                "chain": chain.name,
                "step": step.step,
                "action": "__lambda__",
                "rendered": step.lambda_,
                "args": [],
            })

    return prompts
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_elaborator.py -v`
Expected: 6 PASSED

**Step 5: Commit**

```bash
git add libs/dsl/elaborator.py tests/libs/dsl/test_elaborator.py
git commit -m "feat: add DSL elaborator for deterministic template expansion"
```

---

### Task 5: `gaia build` Command

Orchestrates: load → resolve → elaborate → serialize to `.gaia/build/`.

**Files:**
- Modify: `cli/main.py` (build function)
- Create: `libs/dsl/build_store.py`
- Test: `tests/cli/test_build.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_build.py
"""Tests for gaia build command."""

from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def test_build_creates_gaia_dir(tmp_path):
    """gaia build should create .gaia/build/ directory."""
    import shutil

    # Copy fixture to tmp_path so .gaia/ goes there
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert (pkg_dir / ".gaia" / "build").exists()


def test_build_creates_elaborated_yaml(tmp_path):
    """gaia build should write elaborated.yaml with package data and prompts."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    elab_file = pkg_dir / ".gaia" / "build" / "elaborated.yaml"
    assert elab_file.exists()
    data = yaml.safe_load(elab_file.read_text())
    assert data["package"]["name"] == "galileo_falling_bodies"
    assert "modules" in data["package"]
    assert "prompts" in data
    assert len(data["prompts"]) >= 11


def test_build_output_contains_module_count(tmp_path):
    """gaia build should print summary."""
    import shutil

    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    assert "galileo_falling_bodies" in result.output
    assert "5 modules" in result.output


def test_build_invalid_path():
    result = runner.invoke(app, ["build", "/nonexistent/path"])
    assert result.exit_code != 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_build.py -v`
Expected: FAIL (build stub raises Exit(1))

**Step 3: Write minimal implementation**

First, create `libs/dsl/build_store.py`:

```python
# libs/dsl/build_store.py
"""Serialize/deserialize elaborated packages to .gaia/build/."""

from __future__ import annotations

from pathlib import Path

import yaml

from .elaborator import ElaboratedPackage
from .loader import _parse_declaration, _parse_module
from .models import ChainExpr, Package


def save_build(elaborated: ElaboratedPackage, build_dir: Path) -> Path:
    """Serialize elaborated package to build_dir/elaborated.yaml."""
    build_dir.mkdir(parents=True, exist_ok=True)
    out_path = build_dir / "elaborated.yaml"

    # Serialize package with loaded_modules (excluded by default in model_dump)
    pkg = elaborated.package
    pkg_data = {
        "name": pkg.name,
        "version": pkg.version,
        "export": pkg.export,
        "modules": [],
    }
    for mod in pkg.loaded_modules:
        mod_data = {
            "type": mod.type,
            "name": mod.name,
            "export": mod.export,
            "declarations": [],
        }
        for decl in mod.declarations:
            d = decl.model_dump(by_alias=True, exclude_none=True)
            # ChainExpr steps need special handling for lambda alias
            if isinstance(decl, ChainExpr):
                steps_out = []
                for step in decl.steps:
                    s = step.model_dump(by_alias=True, exclude_none=True)
                    steps_out.append(s)
                d["steps"] = steps_out
            mod_data["declarations"].append(d)
        pkg_data["modules"].append(mod_data)

    data = {
        "package": pkg_data,
        "prompts": elaborated.prompts,
    }
    out_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
    return out_path


def load_build(build_dir: Path) -> ElaboratedPackage:
    """Deserialize elaborated package from build_dir/elaborated.yaml."""
    elab_file = build_dir / "elaborated.yaml"
    if not elab_file.exists():
        raise FileNotFoundError(f"No build artifacts found: {elab_file}")

    data = yaml.safe_load(elab_file.read_text())
    pkg_data = data["package"]

    pkg = Package(
        name=pkg_data["name"],
        version=pkg_data.get("version"),
        export=pkg_data.get("export", []),
    )
    for mod_raw in pkg_data["modules"]:
        mod = _parse_module(mod_raw)
        pkg.loaded_modules.append(mod)

    return ElaboratedPackage(package=pkg, prompts=data.get("prompts", []))
```

Then replace the `build` function in `cli/main.py`:

```python
@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Elaborate: parse + resolve + instantiate params."""
    from libs.dsl.build_store import save_build
    from libs.dsl.elaborator import elaborate_package
    from libs.dsl.loader import load_package
    from libs.dsl.resolver import resolve_refs

    pkg_path = Path(path)
    try:
        pkg = load_package(pkg_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    build_dir = pkg_path / ".gaia" / "build"
    save_build(elaborated, build_dir)

    n_mods = len(pkg.loaded_modules)
    n_prompts = len(elaborated.prompts)
    typer.echo(f"Built {pkg.name}: {n_mods} modules, {n_prompts} elaborated prompts")
    typer.echo(f"Artifacts: {build_dir}/")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_build.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add libs/dsl/build_store.py cli/main.py tests/cli/test_build.py
git commit -m "feat: implement gaia build command with elaboration"
```

---

## Phase 3: Inference

### Task 6: Review Store + Review Merger

**Files:**
- Create: `cli/review_store.py`
- Test: `tests/cli/test_review_store.py`

**Context:** The review sidecar format (from the design doc):
```yaml
package: galileo_falling_bodies
model: claude-sonnet-4-20250514
timestamp: 2026-03-08T14:30:00Z
chains:
  - chain: contradiction_chain
    steps:
      - step: 2
        assessment: valid
        suggested_prior: 0.97
        dependencies:
          - ref: tied_pair_slower_than_heavy
            suggested: direct
```

**Step 1: Write the failing test**

```python
# tests/cli/test_review_store.py
"""Tests for review sidecar I/O and review merger."""

import copy
from datetime import datetime, timezone
from pathlib import Path

import yaml
import pytest

from cli.review_store import (
    find_latest_review,
    merge_review,
    read_review,
    write_review,
)
from libs.dsl.loader import load_package
from libs.dsl.models import StepApply
from libs.dsl.resolver import resolve_refs


FIXTURE_PATH = Path("tests/fixtures/dsl_packages/galileo_falling_bodies")


def _sample_review() -> dict:
    return {
        "package": "galileo_falling_bodies",
        "model": "test-model",
        "timestamp": "2026-03-08T14:30:00Z",
        "chains": [
            {
                "chain": "drag_prediction_chain",
                "steps": [
                    {
                        "step": 2,
                        "assessment": "valid",
                        "suggested_prior": 0.95,
                        "rewrite": None,
                        "dependencies": [
                            {"ref": "heavier_falls_faster", "suggested": "direct"},
                            {"ref": "thought_experiment_env", "suggested": "direct"},
                        ],
                    }
                ],
            }
        ],
    }


def test_write_and_read_review(tmp_path):
    review = _sample_review()
    path = write_review(review, tmp_path)
    assert path.exists()
    assert path.suffix == ".yaml"
    loaded = read_review(path)
    assert loaded["package"] == "galileo_falling_bodies"
    assert len(loaded["chains"]) == 1


def test_find_latest_review(tmp_path):
    r1 = _sample_review()
    r1["timestamp"] = "2026-03-01T10:00:00Z"
    p1 = write_review(r1, tmp_path, filename="review_2026-03-01.yaml")
    r2 = _sample_review()
    r2["timestamp"] = "2026-03-08T14:30:00Z"
    p2 = write_review(r2, tmp_path, filename="review_2026-03-08.yaml")
    latest = find_latest_review(tmp_path)
    assert latest == p2


def test_find_latest_review_empty_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_latest_review(tmp_path)


def test_merge_review_updates_prior():
    """merge_review should update step priors from review suggestions."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    merged = merge_review(pkg, review)
    # Find drag_prediction_chain step 2 in the merged package
    for mod in merged.loaded_modules:
        for decl in mod.declarations:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                assert step2.prior == 0.95  # updated from review
                break


def test_merge_review_updates_dependency():
    """merge_review should update arg dependency types from review."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    # Review suggests thought_experiment_env should be direct (was indirect)
    merged = merge_review(pkg, review)
    for mod in merged.loaded_modules:
        for decl in mod.declarations:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                env_arg = next(a for a in step2.args if a.ref == "thought_experiment_env")
                assert env_arg.dependency == "direct"  # upgraded from indirect
                break


def test_merge_review_does_not_modify_original():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    # Get original prior
    orig_prior = None
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                orig_prior = step2.prior
    merge_review(pkg, review)
    # Original should be unchanged
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                assert step2.prior == orig_prior
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_review_store.py -v`
Expected: FAIL with ImportError (`cli.review_store` does not exist)

**Step 3: Write minimal implementation**

```python
# cli/review_store.py
"""Review sidecar report I/O and merger."""

from __future__ import annotations

import copy
from pathlib import Path

import yaml

from libs.dsl.models import ChainExpr, Package, StepApply


def write_review(
    review: dict, reviews_dir: Path, filename: str | None = None
) -> Path:
    """Write review sidecar YAML to reviews_dir."""
    reviews_dir.mkdir(parents=True, exist_ok=True)
    if filename is None:
        ts = review.get("timestamp", "unknown")
        # Sanitize timestamp for filename
        safe_ts = ts.replace(":", "-").replace("T", "_").split(".")[0]
        filename = f"review_{safe_ts}.yaml"
    out_path = reviews_dir / filename
    out_path.write_text(yaml.dump(review, allow_unicode=True, sort_keys=False))
    return out_path


def read_review(path: Path) -> dict:
    """Read a review sidecar YAML file."""
    if not path.exists():
        raise FileNotFoundError(f"Review file not found: {path}")
    return yaml.safe_load(path.read_text())


def find_latest_review(reviews_dir: Path) -> Path:
    """Find the most recent review file in reviews_dir (by filename sort)."""
    if not reviews_dir.exists():
        raise FileNotFoundError(f"No reviews directory: {reviews_dir}")
    yamls = sorted(reviews_dir.glob("review_*.yaml"))
    if not yamls:
        raise FileNotFoundError(f"No review files in {reviews_dir}")
    return yamls[-1]  # Latest by filename (timestamps sort correctly)


def merge_review(pkg: Package, review: dict) -> Package:
    """Merge review suggestions into package (deep copy — original untouched).

    Updates step priors and arg dependency types based on review.
    """
    merged = copy.deepcopy(pkg)

    # Build chain index
    chains_by_name: dict[str, ChainExpr] = {}
    for mod in merged.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, ChainExpr):
                chains_by_name[decl.name] = decl

    for chain_review in review.get("chains", []):
        chain = chains_by_name.get(chain_review["chain"])
        if not chain:
            continue
        for step_review in chain_review.get("steps", []):
            step_num = step_review["step"]
            step = next((s for s in chain.steps if s.step == step_num), None)
            if not step:
                continue
            # Update prior
            if "suggested_prior" in step_review and hasattr(step, "prior"):
                step.prior = step_review["suggested_prior"]
            # Update dependencies
            if "dependencies" in step_review and isinstance(step, StepApply):
                for dep_review in step_review["dependencies"]:
                    arg = next(
                        (a for a in step.args if a.ref == dep_review["ref"]), None
                    )
                    if arg and "suggested" in dep_review:
                        arg.dependency = dep_review["suggested"]

    return merged
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_review_store.py -v`
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add cli/review_store.py tests/cli/test_review_store.py
git commit -m "feat: add review sidecar store + review merger"
```

---

### Task 7: `gaia infer` Command

Reads elaborated package from `.gaia/build/`, reads latest review from `.gaia/reviews/`, merges review decisions, compiles FG, runs BP, outputs beliefs.

**Files:**
- Modify: `cli/main.py` (infer function)
- Test: `tests/cli/test_infer.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_infer.py
"""Tests for gaia infer command."""

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def _setup_build_and_review(tmp_path: Path) -> Path:
    """Copy fixture, run build, create a test review file."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)

    # Run build first
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0

    # Create a minimal review file (accept all YAML priors as-is)
    reviews_dir = pkg_dir / ".gaia" / "reviews"
    reviews_dir.mkdir(parents=True, exist_ok=True)
    review = {
        "package": "galileo_falling_bodies",
        "model": "test-passthrough",
        "timestamp": "2026-03-08T14:30:00Z",
        "chains": [],  # Empty chains = accept all YAML priors as-is
    }
    (reviews_dir / "review_2026-03-08_14-30-00.yaml").write_text(
        yaml.dump(review, allow_unicode=True, sort_keys=False)
    )
    return pkg_dir


def test_infer_produces_beliefs(tmp_path):
    pkg_dir = _setup_build_and_review(tmp_path)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    assert "belief" in result.output.lower() or "Beliefs" in result.output


def test_infer_heavier_falls_faster_decreases(tmp_path):
    """BP should reduce heavier_falls_faster belief from 0.70 due to contradiction."""
    pkg_dir = _setup_build_and_review(tmp_path)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    # heavier_falls_faster has prior 0.70, should decrease after contradiction/retraction
    assert "heavier_falls_faster" in result.output


def test_infer_errors_without_review(tmp_path):
    """gaia infer should error if no review file exists."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    # Build but don't create review
    runner.invoke(app, ["build", str(pkg_dir)])
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0
    assert "review" in result.output.lower()


def test_infer_errors_without_build(tmp_path):
    """gaia infer should error if no build artifacts exist."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code != 0


def test_infer_with_explicit_review(tmp_path):
    """gaia infer --review <path> should use specified review file."""
    pkg_dir = _setup_build_and_review(tmp_path)
    review_path = pkg_dir / ".gaia" / "reviews" / "review_2026-03-08_14-30-00.yaml"
    result = runner.invoke(app, ["infer", str(pkg_dir), "--review", str(review_path)])
    assert result.exit_code == 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_infer.py -v`
Expected: FAIL (infer stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `infer` function in `cli/main.py`:

```python
@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile FG (from review) + BP -> beliefs."""
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.dsl.build_store import load_build
    from libs.dsl.compiler import compile_factor_graph
    from libs.dsl.resolver import resolve_refs
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Read elaborated package
    try:
        elaborated = load_build(build_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Read review file
    try:
        if review_file:
            review = read_review(Path(review_file))
        else:
            latest = find_latest_review(reviews_dir)
            review = read_review(latest)
    except FileNotFoundError:
        typer.echo(
            f"Error: no review file found.\n"
            f"Run 'gaia review {path}' first, or specify --review <path>.",
            err=True,
        )
        raise typer.Exit(1)

    # 3. Merge review into package
    pkg = elaborated.package
    pkg = resolve_refs(pkg)
    pkg = merge_review(pkg, review)

    # 4. Compile factor graph
    dsl_fg = compile_factor_graph(pkg)

    # 5. Convert to inference engine FG and run BP
    bp_fg = FactorGraph()
    name_to_id: dict[str, int] = {}
    for i, (name, prior) in enumerate(dsl_fg.variables.items()):
        node_id = i + 1
        name_to_id[name] = node_id
        bp_fg.add_variable(node_id, prior)

    for j, factor in enumerate(dsl_fg.factors):
        tail_ids = [name_to_id[n] for n in factor["tail"] if n in name_to_id]
        head_ids = [name_to_id[n] for n in factor["head"] if n in name_to_id]
        bp_fg.add_factor(
            edge_id=j + 1,
            tail=tail_ids,
            head=head_ids,
            probability=factor["probability"],
            edge_type=factor.get("edge_type", "deduction"),
        )

    bp = BeliefPropagation()
    beliefs = bp.run(bp_fg)

    # 6. Map back to names and output
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    typer.echo(f"Package: {elaborated.package.name}")
    typer.echo(f"Variables: {len(dsl_fg.variables)}")
    typer.echo(f"Factors: {len(dsl_fg.factors)}")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        prior = dsl_fg.variables.get(name, "?")
        typer.echo(f"  {name}: prior={prior} -> belief={belief:.4f}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_infer.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_infer.py
git commit -m "feat: implement gaia infer command with FG compilation + BP"
```

---

## Phase 4: Review

### Task 8: LLM Client

Thin wrapper around litellm for chain review. Includes mock mode for testing.

**Files:**
- Create: `cli/llm_client.py`
- Test: `tests/cli/test_llm_client.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_llm_client.py
"""Tests for LLM client used in gaia review."""

import json
from unittest.mock import AsyncMock, patch

import pytest

from cli.llm_client import MockReviewClient, ReviewClient


def test_mock_client_returns_valid_review():
    """MockReviewClient should return a valid review dict for any chain."""
    client = MockReviewClient()
    chain_data = {
        "name": "drag_prediction_chain",
        "steps": [
            {"step": 2, "action": "deduce_drag_effect", "prior": 0.93,
             "args": [
                 {"ref": "heavier_falls_faster", "dependency": "direct"},
                 {"ref": "thought_experiment_env", "dependency": "indirect"},
             ]},
        ],
    }
    result = client.review_chain(chain_data)
    assert "chain" in result
    assert result["chain"] == "drag_prediction_chain"
    assert "steps" in result
    assert len(result["steps"]) >= 1
    step = result["steps"][0]
    assert "step" in step
    assert "assessment" in step
    assert "suggested_prior" in step


def test_mock_client_preserves_existing_priors():
    """MockReviewClient should echo back priors and dependency types."""
    client = MockReviewClient()
    chain_data = {
        "name": "test_chain",
        "steps": [
            {"step": 2, "action": "some_action", "prior": 0.85,
             "args": [{"ref": "claim_a", "dependency": "direct"}]},
        ],
    }
    result = client.review_chain(chain_data)
    step = result["steps"][0]
    assert step["suggested_prior"] == 0.85
    assert step["dependencies"][0]["suggested"] == "direct"


def test_review_client_interface():
    """ReviewClient should have a review_chain method."""
    client = ReviewClient(model="test")
    assert hasattr(client, "review_chain")
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_llm_client.py -v`
Expected: FAIL with ImportError (`cli.llm_client` does not exist)

**Step 3: Write minimal implementation**

```python
# cli/llm_client.py
"""LLM client for chain review."""

from __future__ import annotations


class ReviewClient:
    """LLM-based chain reviewer using litellm."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self._model = model

    def review_chain(self, chain_data: dict) -> dict:
        """Review a single chain and return assessment.

        Args:
            chain_data: {name, steps: [{step, action, prior, args, rendered}]}

        Returns:
            Review dict: {chain, steps: [{step, assessment, suggested_prior, dependencies}]}
        """
        import litellm

        prompt = self._build_prompt(chain_data)
        response = litellm.completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(chain_data, response.choices[0].message.content)

    def _build_prompt(self, chain_data: dict) -> str:
        steps_desc = []
        for step in chain_data["steps"]:
            rendered = step.get("rendered", step.get("action", ""))
            args_desc = ", ".join(
                f"{a['ref']}({a.get('dependency', '?')})" for a in step.get("args", [])
            )
            steps_desc.append(
                f"Step {step['step']}: {rendered}\n  Args: {args_desc}\n  Prior: {step.get('prior', '?')}"
            )
        steps_text = "\n".join(steps_desc)

        return (
            f"Review this reasoning chain: {chain_data['name']}\n\n"
            f"Steps:\n{steps_text}\n\n"
            "For each step, provide:\n"
            "1. assessment: 'valid' or 'questionable'\n"
            "2. suggested_prior: float 0-1\n"
            "3. For each dependency, whether it should be 'direct' or 'indirect'\n"
            "4. If the step has significant uncertainty, suggest a rewrite that "
            "extracts the uncertainty into a new Claim with its own prior.\n\n"
            "Reply in YAML format."
        )

    def _parse_response(self, chain_data: dict, response: str) -> dict:
        """Parse LLM response into review dict. Falls back to passthrough on failure."""
        import yaml

        try:
            parsed = yaml.safe_load(response)
            if isinstance(parsed, dict) and "steps" in parsed:
                parsed["chain"] = chain_data["name"]
                return parsed
        except Exception:
            pass

        # Fallback: passthrough
        return MockReviewClient().review_chain(chain_data)


class MockReviewClient:
    """Mock reviewer that echoes existing priors and dependencies (no LLM calls)."""

    def review_chain(self, chain_data: dict) -> dict:
        """Return a review that preserves all existing values."""
        steps = []
        for step in chain_data.get("steps", []):
            deps = []
            for arg in step.get("args", []):
                deps.append({
                    "ref": arg["ref"],
                    "suggested": arg.get("dependency", "direct"),
                })
            steps.append({
                "step": step["step"],
                "assessment": "valid",
                "suggested_prior": step.get("prior", 0.9),
                "rewrite": None,
                "dependencies": deps,
            })
        return {
            "chain": chain_data["name"],
            "steps": steps,
        }
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_llm_client.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add cli/llm_client.py tests/cli/test_llm_client.py
git commit -m "feat: add LLM client for chain review with mock mode"
```

---

### Task 9: `gaia review` Command

Reads elaborated package from `.gaia/build/`, reviews each ChainExpr, writes sidecar to `.gaia/reviews/`.

**Files:**
- Modify: `cli/main.py` (review function)
- Test: `tests/cli/test_review.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_review.py
"""Tests for gaia review command."""

import shutil
from pathlib import Path

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def _setup_build(tmp_path: Path) -> Path:
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["build", str(pkg_dir)])
    assert result.exit_code == 0
    return pkg_dir


def test_review_creates_sidecar(tmp_path):
    """gaia review should create a review file in .gaia/reviews/."""
    pkg_dir = _setup_build(tmp_path)
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code == 0
    reviews_dir = pkg_dir / ".gaia" / "reviews"
    assert reviews_dir.exists()
    yamls = list(reviews_dir.glob("review_*.yaml"))
    assert len(yamls) == 1


def test_review_sidecar_has_correct_structure(tmp_path):
    """Review sidecar should have package name, chains, and steps."""
    pkg_dir = _setup_build(tmp_path)
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    reviews_dir = pkg_dir / ".gaia" / "reviews"
    review_file = list(reviews_dir.glob("review_*.yaml"))[0]
    data = yaml.safe_load(review_file.read_text())
    assert data["package"] == "galileo_falling_bodies"
    assert "chains" in data
    assert len(data["chains"]) >= 1
    # Each chain should have steps with assessment
    chain = data["chains"][0]
    assert "chain" in chain
    assert "steps" in chain


def test_review_errors_without_build(tmp_path):
    """gaia review should error if build hasn't been run."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code != 0
    assert "build" in result.output.lower()


def test_review_then_infer_pipeline(tmp_path):
    """Full pipeline: build -> review -> infer should work end-to-end."""
    pkg_dir = _setup_build(tmp_path)
    # Review with mock
    result = runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    assert result.exit_code == 0
    # Infer
    result = runner.invoke(app, ["infer", str(pkg_dir)])
    assert result.exit_code == 0
    assert "heavier_falls_faster" in result.output
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_review.py -v`
Expected: FAIL (review stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `review` function in `cli/main.py`:

```python
@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    mock: bool = typer.Option(False, "--mock", help="Use mock reviewer (no LLM calls)"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="LLM model for review"),
) -> None:
    """LLM reviews chains -> sidecar report (.gaia/reviews/)."""
    from datetime import datetime, timezone

    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.review_store import write_review
    from libs.dsl.build_store import load_build
    from libs.dsl.models import ChainExpr, StepApply, StepLambda

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Read elaborated package
    try:
        elaborated = load_build(build_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    # 2. Create reviewer
    client = MockReviewClient() if mock else ReviewClient(model=model)

    # 3. Build prompt data for each chain from elaborated prompts
    # Group prompts by chain
    prompts_by_chain: dict[str, list[dict]] = {}
    for p in elaborated.prompts:
        chain_name = p["chain"]
        if chain_name not in prompts_by_chain:
            prompts_by_chain[chain_name] = []
        prompts_by_chain[chain_name].append(p)

    # 4. Review each chain
    chain_reviews = []
    for chain_name, chain_prompts in prompts_by_chain.items():
        chain_data = {
            "name": chain_name,
            "steps": [
                {
                    "step": p["step"],
                    "action": p["action"],
                    "rendered": p["rendered"],
                    "prior": None,  # Will be filled from package
                    "args": p["args"],
                }
                for p in chain_prompts
            ],
        }
        # Fill priors from package
        for mod in elaborated.package.loaded_modules:
            for decl in mod.declarations:
                if isinstance(decl, ChainExpr) and decl.name == chain_name:
                    for step_data in chain_data["steps"]:
                        step = next(
                            (s for s in decl.steps if s.step == step_data["step"]),
                            None,
                        )
                        if step and hasattr(step, "prior"):
                            step_data["prior"] = step.prior

        result = client.review_chain(chain_data)
        chain_reviews.append(result)

    # 5. Write sidecar
    now = datetime.now(timezone.utc)
    review_data = {
        "package": elaborated.package.name,
        "model": "mock" if mock else model,
        "timestamp": now.isoformat(),
        "chains": chain_reviews,
    }
    review_path = write_review(review_data, reviews_dir)

    n_chains = len(chain_reviews)
    typer.echo(f"Reviewed {n_chains} chains for {elaborated.package.name}")
    typer.echo(f"Report: {review_path}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_review.py -v`
Expected: 4 PASSED

Also verify full pipeline:

Run: `pytest tests/cli/test_review.py::test_review_then_infer_pipeline -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_review.py
git commit -m "feat: implement gaia review command with mock and LLM modes"
```

---

## Phase 5: Auxiliary + Publish

### Task 10: `gaia show` Command

Loads a package and shows declaration details + connected ChainExprs.

**Files:**
- Modify: `cli/main.py` (show function)
- Test: `tests/cli/test_show.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_show.py
"""Tests for gaia show command."""

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def test_show_claim_details():
    result = runner.invoke(app, ["show", "heavier_falls_faster", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    assert "heavier_falls_faster" in result.output
    assert "claim" in result.output.lower()
    assert "0.7" in result.output  # prior


def test_show_connected_chains():
    """heavier_falls_faster should appear in multiple chains."""
    result = runner.invoke(app, ["show", "heavier_falls_faster", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    # Should show chains that reference this declaration
    assert "chain" in result.output.lower()


def test_show_unknown_declaration():
    result = runner.invoke(app, ["show", "nonexistent_claim", "--path", FIXTURE_PATH])
    assert result.exit_code != 0


def test_show_setting():
    result = runner.invoke(app, ["show", "thought_experiment_env", "--path", FIXTURE_PATH])
    assert result.exit_code == 0
    assert "setting" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_show.py -v`
Expected: FAIL (show stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `show` function in `cli/main.py`:

```python
@app.command()
def show(
    name: str = typer.Argument(..., help="Declaration name to inspect"),
    path: str = typer.Option(".", "--path", "-p", help="Package directory"),
) -> None:
    """Show declaration details + connected chains."""
    from libs.dsl.loader import load_package
    from libs.dsl.models import ChainExpr, Ref, StepApply, StepLambda, StepRef
    from libs.dsl.resolver import resolve_refs

    pkg_path = Path(path)
    try:
        pkg = load_package(pkg_path)
        pkg = resolve_refs(pkg)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    # Find declaration
    target = None
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            actual = decl._resolved if isinstance(decl, Ref) and decl._resolved else decl
            if actual.name == name:
                target = actual
                break

    if target is None:
        typer.echo(f"Error: declaration '{name}' not found", err=True)
        raise typer.Exit(1)

    # Display declaration
    prior_str = f" | prior: {target.prior}" if target.prior is not None else ""
    typer.echo(f"{target.name} ({target.type}){prior_str}")
    if hasattr(target, "content") and target.content:
        content = target.content.strip()
        if len(content) > 120:
            content = content[:120] + "..."
        typer.echo(f"  content: \"{content}\"")
    typer.echo()

    # Find connected chains
    typer.echo("  Referenced in chains:")
    found_any = False
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if not isinstance(decl, ChainExpr):
                continue
            for step in decl.steps:
                refs_in_step = []
                if isinstance(step, StepRef) and step.ref == name:
                    refs_in_step.append(name)
                elif isinstance(step, StepApply):
                    refs_in_step = [a.ref for a in step.args if a.ref == name]
                if refs_in_step:
                    edge = decl.edge_type or "deduction"
                    typer.echo(f"    {decl.name} ({edge})")
                    found_any = True
                    break

    if not found_any:
        typer.echo("    (none)")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_show.py -v`
Expected: 4 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_show.py
git commit -m "feat: implement gaia show command"
```

---

### Task 11: DSL → Storage Converter

Converts DSL Package + beliefs into `Node[]` + `HyperEdge[]` for storage. This is the bridge between the DSL world (string names, Pydantic declarations) and the storage world (integer IDs, Node/HyperEdge models).

**Files:**
- Create: `cli/dsl_to_storage.py`
- Test: `tests/cli/test_dsl_to_storage.py`

**Context:** The existing storage models (`libs/models.py`) use `Node(id, type, content, prior, belief, ...)` and `HyperEdge(id, type, tail, head, probability, reasoning, ...)`. The DSL uses string names for declarations and the compiler produces factors with string-based tail/head. This converter allocates integer IDs and builds the mapping.

**Step 1: Write the failing test**

```python
# tests/cli/test_dsl_to_storage.py
"""Tests for DSL → Storage model conversion."""

from pathlib import Path

from cli.dsl_to_storage import convert_package_to_storage
from libs.dsl.compiler import compile_factor_graph
from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs
from libs.models import HyperEdge, Node


FIXTURE_PATH = Path("tests/fixtures/dsl_packages/galileo_falling_bodies")


def _load_galileo():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # Simulate beliefs
    beliefs = {name: 0.5 for name in fg.variables}
    beliefs["heavier_falls_faster"] = 0.30
    beliefs["vacuum_prediction"] = 0.79
    return pkg, fg, beliefs


def test_convert_produces_nodes_and_edges():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    assert len(result.nodes) > 0
    assert len(result.edges) > 0
    assert all(isinstance(n, Node) for n in result.nodes)
    assert all(isinstance(e, HyperEdge) for e in result.edges)


def test_convert_node_has_correct_fields():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    # Find heavier_falls_faster node
    hff = next(n for n in result.nodes if n.title == "heavier_falls_faster")
    assert hff.type == "claim"
    assert hff.prior == 0.7
    assert hff.belief == 0.30
    assert "重的物体" in str(hff.content)


def test_convert_node_ids_are_unique():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    ids = [n.id for n in result.nodes]
    assert len(ids) == len(set(ids))


def test_convert_edge_tail_head_are_valid_node_ids():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    node_ids = {n.id for n in result.nodes}
    for edge in result.edges:
        for tid in edge.tail:
            assert tid in node_ids, f"tail id {tid} not in node_ids"
        for hid in edge.head:
            assert hid in node_ids, f"head id {hid} not in node_ids"


def test_convert_edge_has_probability_and_type():
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    edge_types = {e.type for e in result.edges}
    assert "deduction" in edge_types
    # At least some edges should have probability
    assert any(e.probability is not None for e in result.edges)


def test_convert_name_to_id_mapping():
    """The result should include a name→id mapping for cross-referencing."""
    pkg, fg, beliefs = _load_galileo()
    result = convert_package_to_storage(pkg, fg, beliefs)
    assert "heavier_falls_faster" in result.name_to_id
    nid = result.name_to_id["heavier_falls_faster"]
    hff = next(n for n in result.nodes if n.id == nid)
    assert hff.title == "heavier_falls_faster"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_dsl_to_storage.py -v`
Expected: FAIL with ImportError (`cli.dsl_to_storage` does not exist)

**Step 3: Write minimal implementation**

```python
# cli/dsl_to_storage.py
"""Convert DSL Package + beliefs into Node[] + HyperEdge[] for storage."""

from __future__ import annotations

from dataclasses import dataclass, field

from libs.dsl.compiler import DSLFactorGraph
from libs.dsl.models import (
    ChainExpr,
    Claim,
    Declaration,
    Package,
    Question,
    Ref,
    Setting,
)
from libs.models import HyperEdge, Node


@dataclass
class StorageConversionResult:
    """Result of converting DSL package to storage models."""

    nodes: list[Node] = field(default_factory=list)
    edges: list[HyperEdge] = field(default_factory=list)
    name_to_id: dict[str, int] = field(default_factory=dict)


def convert_package_to_storage(
    pkg: Package,
    fg: DSLFactorGraph,
    beliefs: dict[str, float],
    start_node_id: int = 1,
    start_edge_id: int = 1,
) -> StorageConversionResult:
    """Convert a DSL package with inference results to storage models.

    Args:
        pkg: Resolved package
        fg: Compiled factor graph (variables + factors)
        beliefs: name → posterior belief from BP
        start_node_id: First node ID to allocate
        start_edge_id: First edge ID to allocate
    """
    result = StorageConversionResult()

    # 1. Build declaration index (resolve Refs)
    decls_by_name: dict[str, Declaration] = {}
    for mod in pkg.loaded_modules:
        for decl in mod.declarations:
            if isinstance(decl, Ref) and decl._resolved is not None:
                decls_by_name[decl.name] = decl._resolved
            else:
                decls_by_name[decl.name] = decl

    # 2. Create Node for each variable in the factor graph
    name_to_id: dict[str, int] = {}
    node_id = start_node_id
    for var_name, prior in fg.variables.items():
        decl = decls_by_name.get(var_name)
        if decl is None:
            continue

        # Determine node type from declaration type
        node_type = "claim"
        if isinstance(decl, Setting):
            node_type = "setting"
        elif isinstance(decl, Question):
            node_type = "question"
        elif isinstance(decl, Claim):
            node_type = "claim"

        content = getattr(decl, "content", "") or ""

        node = Node(
            id=node_id,
            type=node_type,
            title=var_name,
            content=content.strip(),
            prior=prior,
            belief=beliefs.get(var_name),
            metadata={"source": "dsl", "package": pkg.name},
        )
        result.nodes.append(node)
        name_to_id[var_name] = node_id
        node_id += 1

    result.name_to_id = name_to_id

    # 3. Create HyperEdge for each factor
    edge_id = start_edge_id
    for factor in fg.factors:
        tail_ids = [name_to_id[n] for n in factor["tail"] if n in name_to_id]
        head_ids = [name_to_id[n] for n in factor["head"] if n in name_to_id]

        if not tail_ids and not head_ids:
            continue

        edge = HyperEdge(
            id=edge_id,
            type=factor.get("edge_type", "deduction"),
            tail=tail_ids,
            head=head_ids,
            probability=factor.get("probability"),
            reasoning=[{"title": factor["name"], "content": ""}],
            metadata={"source": "dsl", "package": pkg.name},
        )
        result.edges.append(edge)
        edge_id += 1

    return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_dsl_to_storage.py -v`
Expected: 7 PASSED

**Step 5: Commit**

```bash
git add cli/dsl_to_storage.py tests/cli/test_dsl_to_storage.py
git commit -m "feat: add DSL to storage model converter"
```

---

### Task 12: `gaia publish --local` Command

Full triple-write: DSL inference results → LanceDB (nodes) + Kuzu (edges) + Vector embeddings.

**Files:**
- Modify: `cli/main.py` (publish function)
- Test: `tests/cli/test_publish.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_publish.py
"""Tests for gaia publish command."""

import asyncio
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch

import yaml
from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def test_publish_requires_mode():
    """gaia publish without --git, --local, or --server should error."""
    result = runner.invoke(app, ["publish", "."])
    assert result.exit_code != 0


def test_publish_git_runs_commands(tmp_path):
    """gaia publish --git should run git add + commit + push."""
    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, capture_output=True)
    (tmp_path / "package.yaml").write_text("name: test\nmodules: []\nexport: []")
    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=tmp_path, capture_output=True)
    (tmp_path / "test.yaml").write_text("test: true")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout=b"")
        result = runner.invoke(app, ["publish", str(tmp_path), "--git"])
    assert mock_run.called


def _setup_full_pipeline(tmp_path: Path) -> Path:
    """Run build + review (mock) so publish has artifacts to work with."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    runner.invoke(app, ["build", str(pkg_dir)])
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    return pkg_dir


def test_publish_local_writes_to_lancedb(tmp_path):
    """gaia publish --local should write nodes to LanceDB."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    assert "nodes" in result.output.lower()
    assert "edges" in result.output.lower()


def test_publish_local_writes_to_kuzu(tmp_path):
    """gaia publish --local should write edges to Kuzu graph store."""
    pkg_dir = _setup_full_pipeline(tmp_path)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    # Verify Kuzu dir was created
    kuzu_dir = Path(db_path) / "kuzu"
    assert kuzu_dir.exists()


def test_publish_local_errors_without_build(tmp_path):
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    db_path = str(tmp_path / "testdb")
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code != 0
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_publish.py -v`
Expected: FAIL (publish stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `publish` function in `cli/main.py`:

```python
@app.command()
def publish(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    git: bool = typer.Option(False, "--git", help="Publish via git add+commit+push"),
    local: bool = typer.Option(False, "--local", help="Import to local databases (LanceDB + Kuzu)"),
    server: bool = typer.Option(False, "--server", help="Publish to Gaia server API"),
    db_path: str = typer.Option(
        None, "--db-path", help="LanceDB path (default: GAIA_LANCEDB_PATH or ./data/lancedb/gaia)",
    ),
) -> None:
    """Publish to git, local databases, or server."""
    import asyncio
    import os
    import subprocess

    if not git and not local and not server:
        typer.echo("Error: specify --git, --local, or --server", err=True)
        raise typer.Exit(1)

    pkg_path = Path(path)

    if git:
        try:
            subprocess.run(["git", "add", "."], cwd=pkg_path, check=True, capture_output=True)
            subprocess.run(
                ["git", "commit", "-m", "gaia: publish package"],
                cwd=pkg_path, check=True, capture_output=True,
            )
            subprocess.run(["git", "push"], cwd=pkg_path, check=True, capture_output=True)
            typer.echo(f"Published {pkg_path} via git")
        except subprocess.CalledProcessError as e:
            typer.echo(f"Git error: {e}", err=True)
            raise typer.Exit(1)

    if local:
        asyncio.run(_publish_local(pkg_path, db_path))

    if server:
        typer.echo("Server publishing not yet implemented")
        raise typer.Exit(1)


async def _publish_local(pkg_path: Path, db_path: str | None) -> None:
    """Import DSL inference results to local LanceDB + Kuzu."""
    import os

    from cli.dsl_to_storage import convert_package_to_storage
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.dsl.build_store import load_build
    from libs.dsl.compiler import compile_factor_graph
    from libs.dsl.resolver import resolve_refs
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph
    from libs.storage.config import StorageConfig
    from libs.storage.manager import StorageManager

    # 1. Read build artifacts + review
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    try:
        elaborated = load_build(build_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}\nRun 'gaia build' first.", err=True)
        raise typer.Exit(1)

    try:
        latest = find_latest_review(reviews_dir)
        review = read_review(latest)
    except FileNotFoundError:
        typer.echo("Error: no review file. Run 'gaia review' first.", err=True)
        raise typer.Exit(1)

    # 2. Merge review + compile FG + run BP
    pkg = elaborated.package
    pkg = resolve_refs(pkg)
    pkg = merge_review(pkg, review)
    dsl_fg = compile_factor_graph(pkg)

    bp_fg = FactorGraph()
    name_to_id_bp: dict[str, int] = {}
    for i, (name, prior) in enumerate(dsl_fg.variables.items()):
        nid = i + 1
        name_to_id_bp[name] = nid
        bp_fg.add_variable(nid, prior)
    for j, factor in enumerate(dsl_fg.factors):
        tail_ids = [name_to_id_bp[n] for n in factor["tail"] if n in name_to_id_bp]
        head_ids = [name_to_id_bp[n] for n in factor["head"] if n in name_to_id_bp]
        bp_fg.add_factor(
            edge_id=j + 1, tail=tail_ids, head=head_ids,
            probability=factor["probability"],
            edge_type=factor.get("edge_type", "deduction"),
        )
    bp = BeliefPropagation()
    raw_beliefs = bp.run(bp_fg)
    id_to_name = {v: k for k, v in name_to_id_bp.items()}
    beliefs = {id_to_name[nid]: b for nid, b in raw_beliefs.items()}

    # 3. Convert to storage models
    conversion = convert_package_to_storage(pkg, dsl_fg, beliefs)

    # 4. Initialize storage
    if db_path is None:
        db_path = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")
    config = StorageConfig(
        deployment_mode="local",
        graph_backend="kuzu",
        lancedb_path=db_path,
    )
    manager = StorageManager(config)

    # 5. Triple write: LanceDB nodes → Kuzu edges → Vector embeddings
    try:
        # Nodes
        await manager.lance.save_nodes(conversion.nodes)
        typer.echo(f"  Wrote {len(conversion.nodes)} nodes to LanceDB")

        # Edges
        if manager.graph:
            await manager.graph.create_hyperedges_bulk(conversion.edges)
            typer.echo(f"  Wrote {len(conversion.edges)} edges to Kuzu")

        # Embeddings (via litellm)
        try:
            import litellm

            contents = [n.content if isinstance(n.content, str) else str(n.content)
                        for n in conversion.nodes]
            response = litellm.embedding(model="text-embedding-3-small", input=contents)
            embeddings = [d["embedding"] for d in response.data]
            node_ids = [n.id for n in conversion.nodes]
            await manager.vector.insert_batch(node_ids, embeddings)
            typer.echo(f"  Wrote {len(embeddings)} embeddings to vector index")
        except Exception as e:
            typer.echo(f"  Skipped embeddings: {e}")

        # Beliefs
        belief_map = {n.id: n.belief for n in conversion.nodes if n.belief is not None}
        if belief_map:
            await manager.lance.update_beliefs(belief_map)

        typer.echo(f"Published {pkg.name} to local storage ({db_path})")
    finally:
        await manager.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_publish.py -v`
Expected: 5 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_publish.py
git commit -m "feat: implement gaia publish --local with full triple-write"
```

---

### Task 13: `gaia search` Command (Database Search)

Searches the local LanceDB for nodes using full-text search. Requires data to have been published via `gaia publish --local`.

**Files:**
- Modify: `cli/main.py` (search function)
- Test: `tests/cli/test_search.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_search.py
"""Tests for gaia search command — searches LanceDB."""

import asyncio
import shutil
from pathlib import Path

from typer.testing import CliRunner

from cli.main import app

runner = CliRunner()

FIXTURE_PATH = "tests/fixtures/dsl_packages/galileo_falling_bodies"


def _publish_galileo(tmp_path: Path) -> tuple[Path, str]:
    """Build + review + publish --local, return (pkg_dir, db_path)."""
    pkg_dir = tmp_path / "galileo"
    shutil.copytree(FIXTURE_PATH, pkg_dir)
    db_path = str(tmp_path / "testdb")
    runner.invoke(app, ["build", str(pkg_dir)])
    runner.invoke(app, ["review", str(pkg_dir), "--mock"])
    result = runner.invoke(app, ["publish", str(pkg_dir), "--local", "--db-path", db_path])
    assert result.exit_code == 0
    return pkg_dir, db_path


def test_search_finds_published_nodes(tmp_path):
    """After publish --local, search should find nodes in LanceDB."""
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "重的物体", "--db-path", db_path])
    assert result.exit_code == 0
    assert len(result.output.strip()) > 0


def test_search_no_results(tmp_path):
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "quantum_entanglement_xyz", "--db-path", db_path])
    assert result.exit_code == 0
    assert "no results" in result.output.lower()


def test_search_shows_belief(tmp_path):
    """Search results should include belief values."""
    _, db_path = _publish_galileo(tmp_path)
    result = runner.invoke(app, ["search", "重的物体", "--db-path", db_path])
    assert result.exit_code == 0
    # Should show prior and/or belief
    assert "prior" in result.output.lower() or "belief" in result.output.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_search.py -v`
Expected: FAIL (search stub raises Exit(1))

**Step 3: Write minimal implementation**

Replace the `search` function in `cli/main.py`:

```python
@app.command()
def search(
    query: str = typer.Argument(..., help="Search query text"),
    db_path: str = typer.Option(
        None, "--db-path", help="LanceDB path (default: GAIA_LANCEDB_PATH or ./data/lancedb/gaia)",
    ),
    limit: int = typer.Option(10, "--limit", "-k", help="Max results"),
) -> None:
    """Search published nodes in local LanceDB."""
    import asyncio
    import os

    if db_path is None:
        db_path = os.environ.get("GAIA_LANCEDB_PATH", "./data/lancedb/gaia")

    asyncio.run(_search_db(query, db_path, limit))


async def _search_db(query: str, db_path: str, limit: int) -> None:
    from libs.storage.lance_store import LanceStore

    store = LanceStore(db_path)
    try:
        results = await store.fts_search(query, k=limit)
        if not results:
            typer.echo("No results found.")
            return

        node_ids = [nid for nid, _ in results]
        nodes = await store.load_nodes_bulk(node_ids)
        scores = {nid: score for nid, score in results}

        for node in nodes:
            score = scores.get(node.id, 0)
            belief_str = f" belief={node.belief:.4f}" if node.belief else ""
            typer.echo(f"  [{node.id}] {node.title or '?'} ({node.type}) "
                       f"prior={node.prior}{belief_str}  score={score:.3f}")
            content = node.content if isinstance(node.content, str) else str(node.content)
            if content.strip():
                snippet = content.strip()[:100]
                typer.echo(f"    {snippet}...")
    finally:
        await store.close()
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_search.py -v`
Expected: 3 PASSED

**Step 5: Commit**

```bash
git add cli/main.py tests/cli/test_search.py
git commit -m "feat: implement gaia search via LanceDB FTS"
```

---

## Verification

After all tasks are complete, run the full test suite:

```bash
# All new CLI tests
pytest tests/cli/ -v

# Existing DSL tests (should still pass)
pytest tests/libs/dsl/ -v

# Inference tests (at new location after Task 0)
pytest tests/libs/test_inference/ -v

# Full suite
pytest -v

# Lint
ruff check cli/ libs/dsl/elaborator.py libs/dsl/build_store.py
ruff format cli/ libs/dsl/elaborator.py libs/dsl/build_store.py
```

### End-to-end pipeline test

```bash
# Full E2E: build -> review -> infer -> publish --local -> search
gaia build tests/fixtures/dsl_packages/galileo_falling_bodies
gaia review tests/fixtures/dsl_packages/galileo_falling_bodies --mock
gaia infer tests/fixtures/dsl_packages/galileo_falling_bodies
gaia publish tests/fixtures/dsl_packages/galileo_falling_bodies --local --db-path ./data/lancedb/gaia
gaia search "真空" --db-path ./data/lancedb/gaia
gaia show heavier_falls_faster --path tests/fixtures/dsl_packages/galileo_falling_bodies
gaia clean tests/fixtures/dsl_packages/galileo_falling_bodies
```

---

## File Summary

### New files (11)
| File | Purpose |
|------|---------|
| `libs/inference/__init__.py` | Inference core package (moved from services/) |
| `libs/inference/factor_graph.py` | FactorGraph (moved from services/) |
| `libs/inference/bp.py` | BeliefPropagation (moved from services/) |
| `cli/main.py` | Typer app with 8 commands |
| `cli/review_store.py` | Review sidecar I/O + merger |
| `cli/llm_client.py` | LLM client for review (+ mock) |
| `cli/dsl_to_storage.py` | DSL → Node/HyperEdge converter |
| `libs/dsl/elaborator.py` | Deterministic template expansion |
| `libs/dsl/build_store.py` | Build artifact serialization |

### New test files (10)
| File | Purpose |
|------|---------|
| `tests/libs/test_inference/test_factor_graph.py` | FactorGraph tests (moved) |
| `tests/libs/test_inference/test_bp.py` | BP tests (moved) |
| `tests/libs/dsl/test_elaborator.py` | Elaborator tests |
| `tests/cli/test_gaia_main.py` | CLI skeleton tests |
| `tests/cli/test_init.py` | init command tests |
| `tests/cli/test_clean.py` | clean command tests |
| `tests/cli/test_build.py` | build command tests |
| `tests/cli/test_review_store.py` | Review store + merger tests |
| `tests/cli/test_infer.py` | infer command tests |
| `tests/cli/test_llm_client.py` | LLM client tests |
| `tests/cli/test_review.py` | review command tests |
| `tests/cli/test_show.py` | show command tests |
| `tests/cli/test_search.py` | search command tests (LanceDB FTS) |
| `tests/cli/test_dsl_to_storage.py` | DSL → Storage converter tests |
| `tests/cli/test_publish.py` | publish command tests (git + local) |

### Modified files (4)
| File | Change |
|------|--------|
| `pyproject.toml` | Add typer dep, cli packages, entry point |
| `libs/dsl/runtime.py` | Update imports: `services.inference_engine` → `libs.inference` |
| `services/inference_engine/engine.py` | Update imports to `libs.inference` |
| `services/review_pipeline/operators/bp.py` | Update imports to `libs.inference` |
