# Cross-Package Resolution & Integration Tests

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enable cross-package ref resolution so Newton (depends on Galileo) and Einstein (depends on Newton + Galileo) can run through the full load → resolve → execute → infer pipeline, and write integration tests for all three packages.

**Architecture:** Extend `resolve_refs()` with an optional `deps` parameter that adds dependency packages' module-exported declarations to the resolution index. Cross-package refs use 3-part paths (`pkg.module.name`) while intra-package refs use 2-part paths (`module.name`). The `GaiaRuntime` gains a `deps` parameter so callers can wire up the dependency chain manually. No auto-discovery — YAGNI.

**Tech Stack:** Python 3.12, Pydantic v2, pytest (asyncio_mode=auto)

---

## Expected Numbers (for assertions)

| Package | Modules | BP Variables | Factors | Deps |
|---------|---------|-------------|---------|------|
| Galileo | 5 | 14 | 11 | none |
| Newton | 4 | 12 | 4 | Galileo |
| Einstein | 4 | 15 | 10 | Newton, Galileo |

**Newton variables (12):** first_law, second_law, third_law, law_of_gravity, mass_equivalence, near_earth_surface, force_equation_result, acceleration_independent_of_mass, galileo_equivalence, newton_contradicts_aristotle, newton_vs_aristotle, two_path_rejection_of_aristotle

**Newton factors (4):** 4 chain step factors (force_equating, mass_independence, theoretical_contradiction, two_path_rejection). Relations `galileo_equivalence` and `newton_vs_aristotle` have only 1 related var in fg.variables (cross-package refs are not exported locally) → no constraint factors.

**Einstein variables (15):** eotvos_experiment, maxwell_electromagnetism, soldner_deflection, equivalence_principle, light_must_bend_in_gravity, einstein_field_equations, gr_light_deflection, mercury_perihelion, gr_subsumes_newton_weak_field, deflection_contradiction, eddington_confirms_gr, soldner_prediction_disfavored, apollo15_feather_drop, apollo15_confirms_equal_fall, three_path_convergence. (`newton_subsumed_by_gr` is subsumption → excluded from BP.)

**Einstein factors (10):** 9 chain step factors + 1 `deflection_contradiction` constraint (both `gr_light_deflection` and `soldner_deflection` are exported → 2 related vars → binary constraint).

---

### Task 1: Cross-Package Resolver — Failing Tests

**Files:**
- Create: `tests/libs/lang/test_cross_package_resolver.py`

**Step 1: Write failing tests**

```python
"""Tests for cross-package ref resolution."""

import pytest
from libs.lang.loader import load_package
from libs.lang.models import Claim, Ref
from libs.lang.resolver import ResolveError, resolve_refs

from pathlib import Path

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_resolve_intra_package_still_works():
    """Backward compat: single-package resolve without deps."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    # Galileo has no cross-package refs, should resolve fine
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.knowledge if isinstance(d, Ref) and d.name == "heavier_falls_faster")
    assert ref._resolved is not None
    assert ref._resolved.name == "heavier_falls_faster"


def test_cross_package_ref_resolves():
    """Newton refs to Galileo should resolve when Galileo is provided as dep."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    implications = next(m for m in newton.loaded_modules if m.name == "implications")
    ref = next(d for d in implications.knowledge if isinstance(d, Ref) and d.name == "galileo_vacuum_prediction")
    assert ref._resolved is not None
    assert ref._resolved.name == "vacuum_prediction"


def test_cross_package_ref_fails_without_dep():
    """Newton refs to Galileo fail if Galileo is not provided."""
    newton = load_package(NEWTON_DIR)
    with pytest.raises(ResolveError, match="galileo_falling_bodies"):
        resolve_refs(newton)


def test_transitive_deps_resolve():
    """Einstein refs to both Newton and Galileo should resolve."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )

    prior_knowledge = next(m for m in einstein.loaded_modules if m.name == "prior_knowledge")
    ref = next(d for d in prior_knowledge.knowledge if isinstance(d, Ref) and d.name == "newton_gravity")
    assert ref._resolved is not None
    assert ref._resolved.name == "law_of_gravity"


def test_dep_non_exported_name_not_resolvable():
    """A dep module's non-exported declaration should NOT be resolvable."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    # Build a minimal package that tries to ref a non-exported name from Galileo.
    # Galileo's 'reasoning' module does NOT export 'tied_pair_slower_than_heavy'.
    from libs.lang.models import Module, Package

    mod = Module(
        type="reasoning_module",
        name="test_mod",
        knowledge=[
            Ref(
                name="sneaky_ref",
                target="galileo_falling_bodies.reasoning.tied_pair_slower_than_heavy",
            )
        ],
        export=[],
    )
    pkg = Package(name="test_pkg", type="test", modules=[], loaded_modules=[mod])

    with pytest.raises(ResolveError, match="sneaky_ref"):
        resolve_refs(pkg, deps={"galileo_falling_bodies": galileo})
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/libs/lang/test_cross_package_resolver.py -v
```

Expected: FAIL — `resolve_refs()` does not accept `deps` parameter yet.

**Step 3: Commit the failing tests**

```bash
git add tests/libs/lang/test_cross_package_resolver.py
git commit -m "test: add failing tests for cross-package ref resolution"
```

---

### Task 2: Cross-Package Resolver — Implementation

**Files:**
- Modify: `libs/lang/resolver.py`

**Step 1: Implement deps parameter**

```python
"""Resolve Ref knowledge objects to their target knowledge objects."""

from __future__ import annotations

from .models import Knowledge, Package, Ref


class ResolveError(Exception):
    """Raised when a Ref target cannot be resolved."""


def resolve_refs(pkg: Package, deps: dict[str, Package] | None = None) -> Package:
    """Resolve all Ref knowledge objects in the package.

    Builds a knowledge index (module.name -> Knowledge),
    then links each Ref._resolved to its target Knowledge object.

    Args:
        pkg: The package to resolve.
        deps: Optional mapping of dependency package name -> resolved Package.
              Cross-package refs use 3-part paths: "pkg_name.module_name.decl_name".
              Only module-exported declarations from deps are resolvable.
    """
    # Build index: "module_name.name" -> Knowledge (intra-package)
    index: dict[str, Knowledge] = {}
    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if decl.type != "ref":
                key = f"{module.name}.{decl.name}"
                index[key] = decl

    # Add cross-package index: "pkg_name.module_name.name" -> Knowledge
    if deps:
        for dep_name, dep_pkg in deps.items():
            for module in dep_pkg.loaded_modules:
                exported = set(module.export)
                for decl in module.knowledge:
                    if decl.type != "ref" and decl.name in exported:
                        key = f"{dep_name}.{module.name}.{decl.name}"
                        index[key] = decl

    # Resolve each Ref
    for module in pkg.loaded_modules:
        for decl in module.knowledge:
            if isinstance(decl, Ref):
                target = index.get(decl.target)
                if target is None:
                    raise ResolveError(
                        f"Cannot resolve ref '{module.name}.{decl.name}' "
                        f"-> '{decl.target}': target not found"
                    )
                decl._resolved = target

    pkg._index = index
    return pkg
```

**Step 2: Run tests**

```bash
pytest tests/libs/lang/test_cross_package_resolver.py -v
```

Expected: ALL PASS

**Step 3: Run existing tests to verify no regression**

```bash
pytest tests/libs/lang/ -v
```

Expected: ALL PASS (backward compatible since `deps` defaults to `None`)

**Step 4: Commit**

```bash
git add libs/lang/resolver.py
git commit -m "feat: support cross-package ref resolution via deps parameter"
```

---

### Task 3: Runtime Deps Support — Failing Tests

**Files:**
- Create: `tests/libs/lang/test_runtime_deps.py`

**Step 1: Write failing tests**

```python
"""Tests for GaiaRuntime with cross-package dependencies."""

from pathlib import Path

from libs.lang.runtime import GaiaRuntime

from .conftest import PassthroughExecutor

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


async def test_runtime_load_with_deps():
    """Runtime.load accepts deps parameter."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.load(GALILEO_DIR)
    newton = await runtime.load(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    assert newton.package.name == "newton_principia"
    assert len(newton.package.loaded_modules) == 4


async def test_runtime_run_with_deps():
    """Runtime.run accepts deps and produces full results."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    assert newton.package.name == "newton_principia"
    assert newton.factor_graph is not None
    assert len(newton.beliefs) > 0
```

**Step 2: Run tests to verify they fail**

```bash
pytest tests/libs/lang/test_runtime_deps.py -v
```

Expected: FAIL — `load()` and `run()` don't accept `deps` yet.

**Step 3: Commit**

```bash
git add tests/libs/lang/test_runtime_deps.py
git commit -m "test: add failing tests for runtime deps support"
```

---

### Task 4: Runtime Deps Support — Implementation

**Files:**
- Modify: `libs/lang/runtime.py`

**Step 1: Add deps to load() and run()**

In `GaiaRuntime.load()`, add `deps` parameter and pass to `resolve_refs`:

```python
async def load(
    self, path: Path | str, deps: dict[str, Package] | None = None
) -> RuntimeResult:
    """Load and validate a package (no execution or inference)."""
    pkg = load_package(Path(path))
    pkg = resolve_refs(pkg, deps=deps)
    return RuntimeResult(package=pkg)
```

In `GaiaRuntime.run()`, add `deps` parameter and pass to `load`:

```python
async def run(
    self, path: Path | str, deps: dict[str, Package] | None = None
) -> RuntimeResult:
    """Full pipeline: Load -> Execute -> Infer."""
    result = await self.load(path, deps=deps)
    await self.execute(result)
    await self.infer(result)
    return result
```

**Step 2: Run tests**

```bash
pytest tests/libs/lang/test_runtime_deps.py -v
```

Expected: ALL PASS

**Step 3: Run all lang tests**

```bash
pytest tests/libs/lang/ -v
```

Expected: ALL PASS

**Step 4: Commit**

```bash
git add libs/lang/runtime.py
git commit -m "feat: add deps parameter to GaiaRuntime.load() and run()"
```

---

### Task 5: Newton Integration Test

**Files:**
- Modify: `tests/libs/lang/test_integration.py`

**Step 1: Write Newton integration test**

Add to `test_integration.py`:

```python
NEWTON_DIR = FIXTURE_DIR.parent / "newton_principia"


async def test_newton_full_pipeline():
    """Newton depends on Galileo: load -> resolve cross-pkg -> execute -> infer."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )

    assert newton.package.name == "newton_principia"
    assert len(newton.package.loaded_modules) == 4

    # Factor graph: 12 BP variables, 4 chain step factors
    assert len(newton.factor_graph.variables) == 12
    assert len(newton.factor_graph.factors) == 4

    # Beliefs computed
    assert len(newton.beliefs) == 12

    # Key claims updated from priors
    assert newton.beliefs["acceleration_independent_of_mass"] != 0.5
    assert newton.beliefs["force_equation_result"] != 0.5

    # Edge types — all deduction (no relation constraints fire for Newton)
    edge_types = {f["edge_type"] for f in newton.factor_graph.factors}
    assert edge_types == {"deduction"}

    summary = newton.inspect()
    assert summary["package"] == "newton_principia"
    assert summary["variables"] == 12
    assert summary["factors"] == 4


async def test_newton_cross_package_refs_resolved():
    """Cross-package refs to Galileo should resolve to actual Knowledge objects."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )

    implications = next(m for m in newton.package.loaded_modules if m.name == "implications")

    # galileo_vacuum_prediction ref should resolve to Galileo's vacuum_prediction
    ref = next(d for d in implications.knowledge if hasattr(d, "target") and d.name == "galileo_vacuum_prediction")
    assert ref._resolved is not None
    assert ref._resolved.name == "vacuum_prediction"
    assert hasattr(ref._resolved, "content")

    # aristotle_law ref should resolve to Galileo's heavier_falls_faster
    ref2 = next(d for d in implications.knowledge if hasattr(d, "target") and d.name == "aristotle_law")
    assert ref2._resolved is not None
    assert ref2._resolved.name == "heavier_falls_faster"
```

**Step 2: Run**

```bash
pytest tests/libs/lang/test_integration.py -v
```

Expected: ALL PASS (including existing Galileo tests)

**Step 3: Commit**

```bash
git add tests/libs/lang/test_integration.py
git commit -m "test: add Newton integration tests with cross-package deps"
```

---

### Task 6: Einstein Integration Test

**Files:**
- Modify: `tests/libs/lang/test_integration.py`

**Step 1: Write Einstein integration test**

Add to `test_integration.py`:

```python
EINSTEIN_DIR = FIXTURE_DIR.parent / "einstein_gravity"


async def test_einstein_full_pipeline():
    """Einstein depends on Newton + Galileo: full transitive dependency chain."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    einstein = await runtime.run(
        EINSTEIN_DIR,
        deps={
            "newton_principia": newton.package,
            "galileo_falling_bodies": galileo.package,
        },
    )

    assert einstein.package.name == "einstein_gravity"
    assert len(einstein.package.loaded_modules) == 4

    # Factor graph: 15 BP variables, 10 factors (9 chain + 1 relation constraint)
    assert len(einstein.factor_graph.variables) == 15
    assert len(einstein.factor_graph.factors) == 10

    # Beliefs computed
    assert len(einstein.beliefs) == 15

    # Subsumption excluded from BP
    assert "newton_subsumed_by_gr" not in einstein.beliefs

    # Key claims updated from priors
    assert einstein.beliefs["equivalence_principle"] != 0.5
    assert einstein.beliefs["gr_light_deflection"] != 0.85
    assert einstein.beliefs["three_path_convergence"] != 0.5

    # deflection_contradiction constraint should produce relation_contradiction edge type
    edge_types = {f["edge_type"] for f in einstein.factor_graph.factors}
    assert "relation_contradiction" in edge_types
    assert "deduction" in edge_types

    summary = einstein.inspect()
    assert summary["package"] == "einstein_gravity"
    assert summary["variables"] == 15
    assert summary["factors"] == 10


async def test_einstein_deflection_contradiction_constraint():
    """The deflection_contradiction should create a binary constraint between gr and soldner predictions."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    einstein = await runtime.run(
        EINSTEIN_DIR,
        deps={
            "newton_principia": newton.package,
            "galileo_falling_bodies": galileo.package,
        },
    )

    # Find the contradiction constraint factor
    constraint = next(
        f for f in einstein.factor_graph.factors
        if f["edge_type"] == "relation_contradiction"
    )
    assert set(constraint["premises"]) == {"gr_light_deflection", "soldner_deflection"}
    assert constraint["conclusions"] == []
    assert constraint["gate_var"] == "deflection_contradiction"


async def test_einstein_subsumption_is_metadata_only():
    """Subsumption should exist as Knowledge but not participate in BP."""
    runtime = GaiaRuntime(executor=PassthroughExecutor())
    galileo = await runtime.run(GALILEO_DIR)
    newton = await runtime.run(
        NEWTON_DIR,
        deps={"galileo_falling_bodies": galileo.package},
    )
    einstein = await runtime.run(
        EINSTEIN_DIR,
        deps={
            "newton_principia": newton.package,
            "galileo_falling_bodies": galileo.package,
        },
    )

    # Subsumption exists as a knowledge declaration
    gr_module = next(m for m in einstein.package.loaded_modules if m.name == "general_relativity")
    subsumption = next(d for d in gr_module.knowledge if d.name == "newton_subsumed_by_gr")
    assert subsumption.type == "subsumption"

    # But NOT in factor graph variables
    assert "newton_subsumed_by_gr" not in einstein.factor_graph.variables

    # And NOT in beliefs
    assert "newton_subsumed_by_gr" not in einstein.beliefs
```

**Step 2: Run**

```bash
pytest tests/libs/lang/test_integration.py -v
```

Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/libs/lang/test_integration.py
git commit -m "test: add Einstein integration tests with transitive cross-package deps"
```

---

### Task 7: Build + Review Pipeline Integration Test

**Files:**
- Create: `tests/libs/lang/test_build_review_pipeline.py`

**Step 1: Write integration test for build → review → infer pipeline**

```python
"""Integration test: build (elaborate) → review (mock) → infer for all three packages."""

from pathlib import Path

from libs.lang.build_store import save_build
from libs.lang.compiler import compile_factor_graph
from libs.lang.elaborator import elaborate_package
from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_galileo_elaborate_and_build(tmp_path):
    """Galileo package can be elaborated and built."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    assert len(elaborated.prompts) >= 10
    assert len(elaborated.chain_contexts) >= 5

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    md_files = list(build_dir.glob("*.md"))
    assert len(md_files) >= 2


def test_newton_elaborate_and_build(tmp_path):
    """Newton (with Galileo dep) can be elaborated and built."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})
    elaborated = elaborate_package(newton)

    assert len(elaborated.prompts) >= 4
    assert len(elaborated.chain_contexts) >= 4

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    md_files = list(build_dir.glob("*.md"))
    assert len(md_files) >= 1


def test_einstein_elaborate_and_build(tmp_path):
    """Einstein (with Newton + Galileo deps) can be elaborated and built."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )
    elaborated = elaborate_package(einstein)

    assert len(elaborated.prompts) >= 8
    assert len(elaborated.chain_contexts) >= 7

    build_dir = tmp_path / "build"
    save_build(elaborated, build_dir)
    md_files = list(build_dir.glob("*.md"))
    assert len(md_files) >= 2


def test_all_three_compile_factor_graphs():
    """All three packages compile valid factor graphs with expected sizes."""
    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)

    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    einstein = load_package(EINSTEIN_DIR)
    einstein = resolve_refs(
        einstein,
        deps={"newton_principia": newton, "galileo_falling_bodies": galileo},
    )

    fg_g = compile_factor_graph(galileo)
    fg_n = compile_factor_graph(newton)
    fg_e = compile_factor_graph(einstein)

    # Galileo: 14 variables, 11 factors
    assert len(fg_g.variables) == 14
    assert len(fg_g.factors) == 11

    # Newton: 12 variables, 4 factors
    assert len(fg_n.variables) == 12
    assert len(fg_n.factors) == 4

    # Einstein: 15 variables, 10 factors
    assert len(fg_e.variables) == 15
    assert len(fg_e.factors) == 10
```

**Step 2: Run**

```bash
pytest tests/libs/lang/test_build_review_pipeline.py -v
```

Expected: ALL PASS (assuming Tasks 1-6 done)

**Step 3: Commit**

```bash
git add tests/libs/lang/test_build_review_pipeline.py
git commit -m "test: add build/elaborate pipeline integration tests for all three packages"
```

---

### Task 8: Final — Run Full Suite + Lint

**Step 1: Run full test suite**

```bash
pytest tests/libs/lang/ -v
```

Expected: ALL PASS

**Step 2: Lint**

```bash
ruff check .
ruff format --check .
```

Expected: PASS. If not, fix and commit:

```bash
ruff check --fix .
ruff format .
git add -u
git commit -m "chore: fix lint/format"
```

**Step 3: Run full project tests for regression**

```bash
pytest -x
```

Expected: ALL PASS
