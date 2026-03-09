# Gaia DSL Runtime Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete DSL runtime that loads YAML knowledge packages, executes reasoning chains (LLM + tools), runs belief propagation, and displays results.

**Architecture:** Four-phase pipeline: Load (YAML → Pydantic AST) → Execute (walk chains, call LLM/tools) → Infer (build factor graph, run BP) → Inspect (display beliefs). New code lives in `libs/dsl/`. Reuses existing `FactorGraph` and `BeliefPropagation` from `services/inference_engine/`. LLM calls abstracted behind an `ActionExecutor` interface for testability.

**Tech Stack:** Python 3.12+, Pydantic v2, PyYAML, existing BP engine (`services/inference_engine/`), pytest

**Test fixture:** `tests/fixtures/dsl_packages/galileo_falling_bodies/` (6 YAML files covering all DSL features)

---

## Task 1: DSL Pydantic Models

**Files:**
- Create: `libs/dsl/__init__.py`
- Create: `libs/dsl/models.py`
- Test: `tests/libs/dsl/test_models.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/__init__.py
# (empty)

# tests/libs/dsl/test_models.py
from libs.dsl.models import (
    Claim, Question, Setting,
    InferAction, ToolCallAction,
    ChainExpr, Ref,
    Module, Package,
    StepRef, StepApply, StepLambda,
    Param, Arg,
)


def test_claim_creation():
    c = Claim(name="test", content="some claim", prior=0.8)
    assert c.type == "claim"
    assert c.prior == 0.8


def test_infer_action_with_params():
    a = InferAction(
        name="reductio",
        params=[Param(name="hyp", type="claim")],
        return_type="claim",
        content="对 {hyp} 运用归谬法",
        prior=0.9,
    )
    assert a.type == "infer_action"
    assert len(a.params) == 1


def test_chain_expr_steps():
    chain = ChainExpr(
        name="my_chain",
        steps=[
            StepRef(step=1, ref="premise"),
            StepApply(
                step=2,
                apply="reductio",
                args=[Arg(ref="premise", dependency="direct")],
                prior=0.9,
            ),
            StepRef(step=3, ref="conclusion"),
        ],
    )
    assert chain.type == "chain_expr"
    assert len(chain.steps) == 3


def test_ref_declaration():
    r = Ref(name="premise", target="other_module.premise")
    assert r.type == "ref"
    assert r.target == "other_module.premise"


def test_module_with_declarations():
    m = Module(
        type="reasoning_module",
        name="reasoning",
        declarations=[
            Claim(name="c1", content="test"),
        ],
        export=["c1"],
    )
    assert m.type == "reasoning_module"
    assert len(m.declarations) == 1


def test_package():
    p = Package(
        name="test_pkg",
        version="1.0.0",
        modules_list=["mod_a", "mod_b"],
        export=["conclusion"],
    )
    assert p.name == "test_pkg"
    assert p.version == "1.0.0"


def test_prior_defaults_to_none():
    c = Claim(name="test", content="no prior")
    assert c.prior is None


def test_step_discriminator():
    """Steps are distinguished by which key is present: ref, apply, or lambda_."""
    s1 = StepRef(step=1, ref="x")
    s2 = StepApply(step=2, apply="f", args=[])
    s3 = StepLambda(step=3, lambda_="some reasoning")
    assert s1.ref == "x"
    assert s2.apply == "f"
    assert s3.lambda_ == "some reasoning"
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_models.py -v`
Expected: FAIL (ModuleNotFoundError: No module named 'libs.dsl')

**Step 3: Write minimal implementation**

```python
# libs/dsl/__init__.py
# (empty)

# libs/dsl/models.py
"""Gaia DSL Pydantic models — the type system as Python classes."""

from __future__ import annotations

from pydantic import BaseModel, Field


# ── Terminals ──────────────────────────────────────────────

class Param(BaseModel):
    name: str
    type: str


class Arg(BaseModel):
    ref: str
    dependency: str | None = None  # "direct" | "indirect" (V3)


class Manifest(BaseModel):
    description: str | None = None
    authors: list[str] = Field(default_factory=list)
    license: str | None = None


# ── Steps (in a ChainExpr) ────────────────────────────────

class StepRef(BaseModel):
    step: int
    ref: str


class StepApply(BaseModel):
    step: int
    apply: str
    args: list[Arg] = Field(default_factory=list)
    prior: float | None = None


class StepLambda(BaseModel):
    step: int
    lambda_: str = Field(alias="lambda")
    prior: float | None = None

    model_config = {"populate_by_name": True}


Step = StepRef | StepApply | StepLambda


# ── Declarations (unified — everything is Knowledge) ──────

class Declaration(BaseModel):
    """Base for all declarations. Subclasses set type as a literal."""
    type: str
    name: str
    metadata: dict | None = None
    prior: float | None = None


class Claim(Declaration):
    type: str = "claim"
    content: str = ""


class Question(Declaration):
    type: str = "question"
    content: str = ""


class Setting(Declaration):
    type: str = "setting"
    content: str = ""


class InferAction(Declaration):
    type: str = "infer_action"
    params: list[Param] = Field(default_factory=list)
    return_type: str | None = None
    content: str = ""


class ToolCallAction(Declaration):
    type: str = "toolcall_action"
    params: list[Param] = Field(default_factory=list)
    return_type: str | None = None
    content: str = ""
    tool: str | None = None


class ChainExpr(Declaration):
    type: str = "chain_expr"
    steps: list[Step] = Field(default_factory=list)


class Ref(Declaration):
    type: str = "ref"
    target: str = ""


# ── Module ────────────────────────────────────────────────

DECLARATION_TYPE_MAP: dict[str, type[Declaration]] = {
    "claim": Claim,
    "question": Question,
    "setting": Setting,
    "infer_action": InferAction,
    "toolcall_action": ToolCallAction,
    "chain_expr": ChainExpr,
    "ref": Ref,
}


class Module(BaseModel):
    type: str  # reasoning_module, setting_module, etc.
    name: str
    declarations: list[Declaration] = Field(default_factory=list)
    export: list[str] = Field(default_factory=list)


# ── Package ───────────────────────────────────────────────

class Package(BaseModel):
    name: str
    version: str | None = None
    manifest: Manifest | None = None
    modules_list: list[str] = Field(default_factory=list, alias="modules")
    export: list[str] = Field(default_factory=list)
    # Populated after loading module files:
    loaded_modules: list[Module] = Field(default_factory=list, exclude=True)

    model_config = {"populate_by_name": True}
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_models.py -v`
Expected: PASS (9 tests)

**Step 5: Commit**

```bash
git add libs/dsl/ tests/libs/dsl/
git commit -m "feat(dsl): add Pydantic models for DSL type system"
```

---

## Task 2: YAML Loader

**Files:**
- Create: `libs/dsl/loader.py`
- Test: `tests/libs/dsl/test_loader.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_loader.py
from pathlib import Path

from libs.dsl.loader import load_package
from libs.dsl.models import (
    Claim, InferAction, ChainExpr, Ref, Module, Package,
)

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_load_package_metadata():
    pkg = load_package(FIXTURE_DIR)
    assert pkg.name == "galileo_falling_bodies"
    assert pkg.version == "1.0.0"
    assert pkg.manifest is not None
    assert "伽利略" in pkg.manifest.authors[0]


def test_load_package_modules():
    pkg = load_package(FIXTURE_DIR)
    assert len(pkg.loaded_modules) == 5
    names = {m.name for m in pkg.loaded_modules}
    assert names == {"motivation", "setting", "aristotle", "reasoning", "follow_up"}


def test_module_types():
    pkg = load_package(FIXTURE_DIR)
    type_map = {m.name: m.type for m in pkg.loaded_modules}
    assert type_map["motivation"] == "motivation_module"
    assert type_map["setting"] == "setting_module"
    assert type_map["reasoning"] == "reasoning_module"
    assert type_map["follow_up"] == "follow_up_module"


def test_declarations_parsed():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    # Should have: 3 refs + 2 infer_actions + 3 claims + 3 chain_exprs = 11
    assert len(reasoning.declarations) == 11


def test_claim_with_prior():
    pkg = load_package(FIXTURE_DIR)
    aristotle = next(m for m in pkg.loaded_modules if m.name == "aristotle")
    heavier = next(d for d in aristotle.declarations if d.name == "heavier_falls_faster")
    assert isinstance(heavier, Claim)
    assert heavier.prior == 0.7
    assert "重的物体" in heavier.content


def test_infer_action_with_params():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    reductio = next(d for d in reasoning.declarations if d.name == "reductio_ad_absurdum")
    assert isinstance(reductio, InferAction)
    assert len(reductio.params) == 2
    assert reductio.params[0].name == "hypothesis"
    assert reductio.return_type == "claim"
    assert "{hypothesis}" in reductio.content


def test_chain_expr_steps():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    chain = next(d for d in reasoning.declarations if d.name == "refutation_chain")
    assert isinstance(chain, ChainExpr)
    assert len(chain.steps) == 3
    # Step 1: ref
    assert chain.steps[0].ref == "heavier_falls_faster"
    # Step 2: apply with args
    assert chain.steps[1].apply == "reductio_ad_absurdum"
    assert chain.steps[1].args[0].dependency == "direct"
    # Step 3: ref
    assert chain.steps[2].ref == "aristotle_contradicted"


def test_ref_declaration():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.declarations if d.name == "heavier_falls_faster")
    assert isinstance(ref, Ref)
    assert ref.target == "aristotle.heavier_falls_faster"


def test_lambda_step():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    confound = next(d for d in reasoning.declarations if d.name == "confound_chain")
    assert isinstance(confound, ChainExpr)
    # Step 2 should be a lambda
    step2 = confound.steps[1]
    assert hasattr(step2, "lambda_")
    assert "空气阻力" in step2.lambda_


def test_exports():
    pkg = load_package(FIXTURE_DIR)
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    assert "vacuum_prediction" in reasoning.export


def test_load_nonexistent_raises():
    import pytest
    with pytest.raises(FileNotFoundError):
        load_package(Path("/nonexistent/path"))
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_loader.py -v`
Expected: FAIL (ImportError: cannot import name 'load_package')

**Step 3: Write minimal implementation**

```python
# libs/dsl/loader.py
"""Load a Gaia DSL package from YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from .models import (
    DECLARATION_TYPE_MAP,
    Arg,
    ChainExpr,
    Declaration,
    Module,
    Package,
    Step,
    StepApply,
    StepLambda,
    StepRef,
)


def load_package(path: Path) -> Package:
    """Load a package directory: package.yaml + module YAML files."""
    path = Path(path)
    pkg_file = path / "package.yaml"
    if not pkg_file.exists():
        raise FileNotFoundError(f"Package manifest not found: {pkg_file}")

    with open(pkg_file) as f:
        pkg_data = yaml.safe_load(f)

    pkg = Package.model_validate(pkg_data)

    # Load each module file
    for module_name in pkg.modules_list:
        mod_file = path / f"{module_name}.yaml"
        if not mod_file.exists():
            raise FileNotFoundError(f"Module file not found: {mod_file}")
        with open(mod_file) as f:
            mod_data = yaml.safe_load(f)
        module = _parse_module(mod_data)
        pkg.loaded_modules.append(module)

    return pkg


def _parse_module(data: dict) -> Module:
    """Parse a module YAML dict into a Module with typed declarations."""
    declarations = [_parse_declaration(d) for d in data.get("declarations", [])]
    return Module(
        type=data["type"],
        name=data["name"],
        declarations=declarations,
        export=data.get("export", []),
    )


def _parse_declaration(data: dict) -> Declaration:
    """Parse a single declaration dict into the correct Declaration subclass."""
    decl_type = data.get("type", "")
    cls = DECLARATION_TYPE_MAP.get(decl_type)

    if cls is None:
        # Unknown type — return base Declaration
        return Declaration.model_validate(data)

    if cls is ChainExpr:
        # Parse steps specially
        raw_steps = data.get("steps", [])
        steps = [_parse_step(s) for s in raw_steps]
        return ChainExpr(
            name=data["name"],
            steps=steps,
            prior=data.get("prior"),
            metadata=data.get("metadata"),
        )

    return cls.model_validate(data)


def _parse_step(data: dict) -> Step:
    """Parse a step dict into StepRef, StepApply, or StepLambda."""
    step_num = data.get("step", 0)

    if "apply" in data:
        args = [Arg.model_validate(a) for a in data.get("args", [])]
        return StepApply(
            step=step_num,
            apply=data["apply"],
            args=args,
            prior=data.get("prior"),
        )

    if "lambda" in data:
        return StepLambda(
            step=step_num,
            **{"lambda": data["lambda"]},
            prior=data.get("prior"),
        )

    if "ref" in data:
        return StepRef(step=step_num, ref=data["ref"])

    raise ValueError(f"Unknown step format: {data}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_loader.py -v`
Expected: PASS (11 tests)

**Step 5: Commit**

```bash
git add libs/dsl/loader.py tests/libs/dsl/test_loader.py
git commit -m "feat(dsl): YAML loader — parse package and module files"
```

---

## Task 3: Reference Resolver

**Files:**
- Create: `libs/dsl/resolver.py`
- Test: `tests/libs/dsl/test_resolver.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_resolver.py
from pathlib import Path

import pytest

from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs, ResolveError
from libs.dsl.models import Claim

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_resolve_simple_ref():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # reasoning module refs heavier_falls_faster from aristotle
    reasoning = next(m for m in resolved.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.declarations if d.type == "ref" and d.name == "heavier_falls_faster")
    assert ref._resolved is not None
    assert isinstance(ref._resolved, Claim)
    assert "重的物体" in ref._resolved.content


def test_resolve_all_refs():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # All refs should be resolved
    for module in resolved.loaded_modules:
        for decl in module.declarations:
            if decl.type == "ref":
                assert decl._resolved is not None, f"Unresolved ref: {module.name}.{decl.name}"


def test_resolve_cross_module():
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    follow_up = next(m for m in resolved.loaded_modules if m.name == "follow_up")
    vp_ref = next(d for d in follow_up.declarations if d.name == "vacuum_prediction")
    assert vp_ref._resolved is not None


def test_resolve_undefined_ref_raises():
    pkg = load_package(FIXTURE_DIR)
    # Add a bad ref
    from libs.dsl.models import Ref
    bad_module = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    bad_module.declarations.append(Ref(name="nonexistent", target="fake_module.fake_name"))
    with pytest.raises(ResolveError, match="fake_module"):
        resolve_refs(pkg)


def test_build_declaration_index():
    """All declarations should be findable by module.name path."""
    pkg = load_package(FIXTURE_DIR)
    resolved = resolve_refs(pkg)
    # Check that we can look up any exported declaration
    assert resolved._index["aristotle.heavier_falls_faster"] is not None
    assert resolved._index["setting.vacuum_env"] is not None
    assert resolved._index["reasoning.vacuum_prediction"] is not None
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_resolver.py -v`
Expected: FAIL (ImportError: cannot import name 'resolve_refs')

**Step 3: Write minimal implementation**

```python
# libs/dsl/resolver.py
"""Resolve Ref declarations to their target knowledge objects."""

from __future__ import annotations

from .models import Declaration, Package, Ref


class ResolveError(Exception):
    """Raised when a Ref target cannot be resolved."""


def resolve_refs(pkg: Package) -> Package:
    """Resolve all Ref declarations in the package.

    Builds a declaration index (module.name -> Declaration),
    then links each Ref._resolved to its target Declaration.
    """
    # Build index: "module_name.decl_name" -> Declaration
    index: dict[str, Declaration] = {}
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if decl.type != "ref":
                key = f"{module.name}.{decl.name}"
                index[key] = decl

    # Resolve each Ref
    for module in pkg.loaded_modules:
        for decl in module.declarations:
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

Note: add `_resolved` and `_index` fields to models:

```python
# Add to Ref class in models.py:
class Ref(Declaration):
    type: str = "ref"
    target: str = ""
    _resolved: Declaration | None = None  # populated by resolver

# Add to Package class in models.py:
class Package(BaseModel):
    # ... existing fields ...
    _index: dict[str, Declaration] = {}  # populated by resolver
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_resolver.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add libs/dsl/resolver.py tests/libs/dsl/test_resolver.py libs/dsl/models.py
git commit -m "feat(dsl): reference resolver — link Ref declarations to targets"
```

---

## Task 4: Factor Graph Compiler

**Files:**
- Create: `libs/dsl/compiler.py`
- Test: `tests/libs/dsl/test_compiler.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_compiler.py
from pathlib import Path

from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs
from libs.dsl.compiler import compile_factor_graph

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_compile_produces_factor_graph():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # Factor graph should have variable nodes and factor nodes
    assert len(fg.variables) > 0
    assert len(fg.factors) > 0


def test_variable_nodes_are_claims_and_settings():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # Variable nodes should include knowledge objects with priors
    # heavier_falls_faster (prior=0.7), everyday_observation (prior=0.95),
    # thought_experiment_env (prior=1.0), vacuum_env (prior=1.0),
    # aristotle_contradicted (prior=0.5), air_resistance_is_confound (prior=0.5),
    # vacuum_prediction (prior=0.5)
    assert len(fg.variables) >= 7


def test_factor_nodes_from_chain_steps():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # Factors from: refutation_chain step2, confound_chain step2 (lambda),
    # synthesis_chain step2, inductive_support step2 (lambda), next_steps step2 (lambda)
    assert len(fg.factors) >= 5


def test_direct_dependency_creates_edge():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # refutation_chain: heavier_falls_faster --direct--> aristotle_contradicted
    # Find a factor connecting these two variables
    has_direct = any(
        f for f in fg.factors
        if "heavier_falls_faster" in str(f.get("tail", []))
    )
    assert has_direct


def test_indirect_dependency_excluded_from_edges():
    """Indirect dependencies should NOT create BP edges."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # thought_experiment_env is used as indirect in refutation_chain
    # It should NOT appear as a tail in that factor
    refutation_factors = [
        f for f in fg.factors
        if f.get("name") == "refutation_chain.step_2"
    ]
    if refutation_factors:
        factor = refutation_factors[0]
        assert "thought_experiment_env" not in [
            t for t in factor.get("tail", [])
        ]


def test_exported_only_in_factor_graph():
    """Only exported declarations participate in BP."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    fg = compile_factor_graph(pkg)
    # main_question (from motivation) is exported
    # but it's a Question type — Questions don't participate in BP
    var_names = set(fg.variables.keys())
    assert "main_question" not in var_names
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_compiler.py -v`
Expected: FAIL (ImportError: cannot import name 'compile_factor_graph')

**Step 3: Write minimal implementation**

```python
# libs/dsl/compiler.py
"""Compile a resolved DSL package into a factor graph for BP."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import (
    ChainExpr,
    Claim,
    Declaration,
    Package,
    Ref,
    Setting,
    StepApply,
    StepLambda,
    StepRef,
)


# Types that participate in BP as variable nodes
BP_VARIABLE_TYPES = {"claim", "setting"}


@dataclass
class DSLFactorGraph:
    """Factor graph built from DSL package structure.

    variables: name -> prior
    factors: list of {name, tail: [name], head: [name], probability}
    """
    variables: dict[str, float] = field(default_factory=dict)
    factors: list[dict] = field(default_factory=list)


def compile_factor_graph(pkg: Package) -> DSLFactorGraph:
    """Compile a resolved package into a factor graph.

    Variable nodes: Claims and Settings with priors.
    Factor nodes: Applications and Lambdas from ChainExpr steps.
    Edges: determined by direct dependencies (indirect excluded).
    """
    fg = DSLFactorGraph()

    # Collect all declarations across modules (resolving refs)
    all_decls: dict[str, Declaration] = {}
    exported: set[str] = set()

    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Ref):
                # Use the resolved target
                if decl._resolved is not None:
                    all_decls[decl.name] = decl._resolved
            else:
                all_decls[decl.name] = decl
        exported.update(module.export)

    # Add variable nodes (Claims and Settings with priors)
    for name, decl in all_decls.items():
        if decl.type in BP_VARIABLE_TYPES:
            prior = decl.prior if decl.prior is not None else 1.0
            fg.variables[name] = prior

    # Add factor nodes from ChainExpr steps
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if not isinstance(decl, ChainExpr):
                continue
            _compile_chain(decl, all_decls, fg)

    return fg


def _compile_chain(
    chain: ChainExpr,
    all_decls: dict[str, Declaration],
    fg: DSLFactorGraph,
) -> None:
    """Compile a ChainExpr into factor nodes connecting variable nodes."""
    steps = chain.steps
    for i, step in enumerate(steps):
        if isinstance(step, (StepApply, StepLambda)):
            # This step is a factor node
            factor_name = f"{chain.name}.step_{step.step}"
            probability = step.prior if step.prior is not None else 1.0

            # Tail: direct dependencies from args (for Apply)
            # or the previous ref step (for Lambda)
            tail = []
            head = []

            if isinstance(step, StepApply):
                for arg in step.args:
                    if arg.dependency == "direct":
                        # Resolve arg ref name
                        ref_name = arg.ref
                        if ref_name in fg.variables:
                            tail.append(ref_name)
            elif isinstance(step, StepLambda):
                # Lambda: previous step is the implicit input
                if i > 0:
                    prev = steps[i - 1]
                    if isinstance(prev, StepRef) and prev.ref in fg.variables:
                        tail.append(prev.ref)

            # Head: next ref step is the output
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef) and next_step.ref in fg.variables:
                    head.append(next_step.ref)

            if tail or head:
                fg.factors.append({
                    "name": factor_name,
                    "tail": tail,
                    "head": head,
                    "probability": probability,
                })
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_compiler.py -v`
Expected: PASS (6 tests)

**Step 5: Commit**

```bash
git add libs/dsl/compiler.py tests/libs/dsl/test_compiler.py
git commit -m "feat(dsl): factor graph compiler — ChainExpr to BP graph"
```

---

## Task 5: Action Executor

**Files:**
- Create: `libs/dsl/executor.py`
- Test: `tests/libs/dsl/test_executor.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_executor.py
from pathlib import Path

import pytest

from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs
from libs.dsl.executor import execute_package, ActionExecutor
from libs.dsl.models import Claim

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


class MockExecutor(ActionExecutor):
    """Mock LLM executor that returns fixed responses."""

    def __init__(self):
        self.calls: list[dict] = []

    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        self.calls.append({"type": "infer", "content": content, "args": args})
        # Substitute params into content as a simple mock
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return f"[推理结果] {result}"

    def execute_lambda(self, content: str, input_text: str) -> str:
        self.calls.append({"type": "lambda", "content": content, "input": input_text})
        return f"[Lambda结果] {content}"


def test_execute_fills_empty_claims():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    execute_package(pkg, executor)

    # aristotle_contradicted was empty, should now have content
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    ac = next(d for d in reasoning.declarations if d.name == "aristotle_contradicted")
    assert ac.content != ""


def test_execute_calls_infer_action():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    execute_package(pkg, executor)

    # Should have called execute_infer for reductio_ad_absurdum and synthesize
    infer_calls = [c for c in executor.calls if c["type"] == "infer"]
    assert len(infer_calls) >= 2


def test_execute_calls_lambda():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    execute_package(pkg, executor)

    # Should have called execute_lambda for confound_chain lambda
    lambda_calls = [c for c in executor.calls if c["type"] == "lambda"]
    assert len(lambda_calls) >= 1


def test_execute_preserves_existing_content():
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    execute_package(pkg, executor)

    # heavier_falls_faster already had content, should not be overwritten
    aristotle = next(m for m in pkg.loaded_modules if m.name == "aristotle")
    hff = next(d for d in aristotle.declarations if d.name == "heavier_falls_faster")
    assert "重的物体" in hff.content


def test_execute_chain_order():
    """Chains are executed in step order, earlier chains before later ones."""
    pkg = load_package(FIXTURE_DIR)
    pkg = resolve_refs(pkg)
    executor = MockExecutor()
    execute_package(pkg, executor)

    # vacuum_prediction (output of synthesis_chain) should have content
    # because refutation_chain and confound_chain ran first
    reasoning = next(m for m in pkg.loaded_modules if m.name == "reasoning")
    vp = next(d for d in reasoning.declarations if d.name == "vacuum_prediction")
    assert vp.content != ""
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_executor.py -v`
Expected: FAIL (ImportError: cannot import name 'execute_package')

**Step 3: Write minimal implementation**

```python
# libs/dsl/executor.py
"""Execute a DSL package — walk chains, call actions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    ChainExpr,
    Claim,
    Declaration,
    InferAction,
    Package,
    Ref,
    Setting,
    StepApply,
    StepLambda,
    StepRef,
    ToolCallAction,
)


class ActionExecutor(ABC):
    """Abstract interface for executing actions (LLM, tools, etc.)."""

    @abstractmethod
    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        """Execute an InferAction. Returns the reasoning result text."""

    @abstractmethod
    def execute_lambda(self, content: str, input_text: str) -> str:
        """Execute a Lambda step. Returns the reasoning result text."""


def execute_package(pkg: Package, executor: ActionExecutor) -> None:
    """Execute all ChainExprs in the package, filling in empty claims.

    Walks each chain's steps in order. For Application and Lambda steps,
    calls the executor and writes the result to the output claim.
    """
    # Build lookup: name -> Declaration (across all modules, resolving refs)
    decls: dict[str, Declaration] = {}
    actions: dict[str, InferAction | ToolCallAction] = {}

    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Ref):
                if decl._resolved is not None:
                    decls[decl.name] = decl._resolved
            else:
                decls[decl.name] = decl
                if isinstance(decl, (InferAction, ToolCallAction)):
                    actions[decl.name] = decl

    # Execute each ChainExpr
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, ChainExpr):
                _execute_chain(decl, decls, actions, executor)


def _execute_chain(
    chain: ChainExpr,
    decls: dict[str, Declaration],
    actions: dict[str, InferAction | ToolCallAction],
    executor: ActionExecutor,
) -> None:
    """Execute a single ChainExpr."""
    steps = chain.steps

    for i, step in enumerate(steps):
        if isinstance(step, StepApply):
            action = actions.get(step.apply)
            if action is None:
                continue

            # Build args dict: param_name -> content
            args_content: dict[str, str] = {}
            for j, arg in enumerate(step.args):
                ref_decl = decls.get(arg.ref)
                if ref_decl is not None and hasattr(ref_decl, "content"):
                    param_name = (
                        action.params[j].name
                        if j < len(action.params)
                        else arg.ref
                    )
                    args_content[param_name] = ref_decl.content

            # Execute
            result = executor.execute_infer(action.content, args_content)

            # Write result to the next step's claim (if empty)
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef):
                    target = decls.get(next_step.ref)
                    if target is not None and hasattr(target, "content"):
                        if not target.content or not target.content.strip():
                            target.content = result

        elif isinstance(step, StepLambda):
            # Get input from previous step
            input_text = ""
            if i > 0:
                prev = steps[i - 1]
                if isinstance(prev, StepRef):
                    prev_decl = decls.get(prev.ref)
                    if prev_decl is not None and hasattr(prev_decl, "content"):
                        input_text = prev_decl.content

            result = executor.execute_lambda(step.lambda_, input_text)

            # Write result to the next step's claim (if empty)
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef):
                    target = decls.get(next_step.ref)
                    if target is not None and hasattr(target, "content"):
                        if not target.content or not target.content.strip():
                            target.content = result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_executor.py -v`
Expected: PASS (5 tests)

**Step 5: Commit**

```bash
git add libs/dsl/executor.py tests/libs/dsl/test_executor.py
git commit -m "feat(dsl): action executor — walk chains, call LLM/tools"
```

---

## Task 6: DSL Runtime (Load → Execute → Infer → Inspect)

**Files:**
- Create: `libs/dsl/runtime.py`
- Test: `tests/libs/dsl/test_runtime.py`

**Step 1: Write the failing test**

```python
# tests/libs/dsl/test_runtime.py
from pathlib import Path

from libs.dsl.runtime import DSLRuntime, RuntimeResult
from libs.dsl.executor import ActionExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


class MockExecutor(ActionExecutor):
    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return f"[推理结果] {result}"

    def execute_lambda(self, content: str, input_text: str) -> str:
        return f"[Lambda结果] {content}"


def test_runtime_full_pipeline():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)

    assert isinstance(result, RuntimeResult)
    assert result.package.name == "galileo_falling_bodies"
    assert len(result.beliefs) > 0
    assert result.factor_graph is not None


def test_runtime_beliefs_computed():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)

    # heavier_falls_faster has prior=0.7, after BP it should change
    assert "heavier_falls_faster" in result.beliefs
    # vacuum_prediction has prior=0.5
    assert "vacuum_prediction" in result.beliefs


def test_runtime_load_only():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.load(FIXTURE_DIR)

    assert result.package.name == "galileo_falling_bodies"
    assert len(result.package.loaded_modules) == 5
    # No beliefs yet (not inferred)
    assert len(result.beliefs) == 0


def test_runtime_inspect():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)
    summary = result.inspect()

    # Should contain variable and factor counts
    assert "variables" in summary
    assert "factors" in summary
    assert "beliefs" in summary
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/libs/dsl/test_runtime.py -v`
Expected: FAIL (ImportError: cannot import name 'DSLRuntime')

**Step 3: Write minimal implementation**

```python
# libs/dsl/runtime.py
"""Gaia DSL Runtime — Load → Execute → Infer → Inspect."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from services.inference_engine.bp import BeliefPropagation
from services.inference_engine.factor_graph import FactorGraph

from .compiler import DSLFactorGraph, compile_factor_graph
from .executor import ActionExecutor, execute_package
from .loader import load_package
from .models import Package
from .resolver import resolve_refs


@dataclass
class RuntimeResult:
    """Result of running the DSL pipeline."""
    package: Package
    factor_graph: DSLFactorGraph | None = None
    beliefs: dict[str, float] = field(default_factory=dict)

    def inspect(self) -> dict:
        """Return a summary of the runtime result."""
        return {
            "package": self.package.name,
            "modules": len(self.package.loaded_modules),
            "variables": len(self.factor_graph.variables) if self.factor_graph else 0,
            "factors": len(self.factor_graph.factors) if self.factor_graph else 0,
            "beliefs": dict(self.beliefs),
        }


class DSLRuntime:
    """Main runtime: Load → Execute → Infer → Inspect."""

    def __init__(self, executor: ActionExecutor | None = None):
        self._executor = executor

    def load(self, path: Path | str) -> RuntimeResult:
        """Load and validate a package (no execution or inference)."""
        pkg = load_package(Path(path))
        pkg = resolve_refs(pkg)
        return RuntimeResult(package=pkg)

    def run(self, path: Path | str) -> RuntimeResult:
        """Full pipeline: Load → Execute → Infer."""
        result = self.load(path)

        # Execute (if executor provided)
        if self._executor:
            execute_package(result.package, self._executor)

        # Infer (build factor graph + run BP)
        dsl_fg = compile_factor_graph(result.package)
        result.factor_graph = dsl_fg

        # Convert DSLFactorGraph to inference engine FactorGraph
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
                tail_ids=tail_ids,
                head_ids=head_ids,
                probability=factor["probability"],
            )

        # Run BP
        bp = BeliefPropagation()
        beliefs = bp.run(bp_fg)

        # Map back to names
        id_to_name = {v: k for k, v in name_to_id.items()}
        result.beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

        return result
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/libs/dsl/test_runtime.py -v`
Expected: PASS (4 tests)

**Step 5: Commit**

```bash
git add libs/dsl/runtime.py tests/libs/dsl/test_runtime.py
git commit -m "feat(dsl): runtime — full Load → Execute → Infer → Inspect pipeline"
```

---

## Task 7: Integration Test — Full Galileo Pipeline

**Files:**
- Test: `tests/libs/dsl/test_integration.py`

**Step 1: Write the integration test**

```python
# tests/libs/dsl/test_integration.py
"""End-to-end integration test: load galileo package, execute, run BP, inspect."""

from pathlib import Path

from libs.dsl.runtime import DSLRuntime
from libs.dsl.executor import ActionExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


class MockLLM(ActionExecutor):
    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return result

    def execute_lambda(self, content: str, input_text: str) -> str:
        return content


def test_galileo_full_pipeline():
    """Full pipeline: load → execute → infer → inspect."""
    runtime = DSLRuntime(executor=MockLLM())
    result = runtime.run(FIXTURE_DIR)

    # Package loaded correctly
    assert result.package.name == "galileo_falling_bodies"
    assert len(result.package.loaded_modules) == 5

    # Factor graph built
    assert len(result.factor_graph.variables) >= 7
    assert len(result.factor_graph.factors) >= 5

    # Beliefs computed
    assert len(result.beliefs) >= 7

    # Key belief checks:
    # heavier_falls_faster starts at prior=0.7
    # After being used as input to refutation and confound chains,
    # its belief should remain close to its prior or change based on BP
    assert 0.0 <= result.beliefs["heavier_falls_faster"] <= 1.0
    assert 0.0 <= result.beliefs["vacuum_prediction"] <= 1.0

    # Print summary
    summary = result.inspect()
    assert summary["package"] == "galileo_falling_bodies"
    assert summary["modules"] == 5
    assert summary["variables"] >= 7
    assert summary["factors"] >= 5


def test_galileo_empty_claims_filled():
    """Execute phase should fill in empty claims."""
    runtime = DSLRuntime(executor=MockLLM())
    result = runtime.run(FIXTURE_DIR)

    reasoning = next(m for m in result.package.loaded_modules if m.name == "reasoning")
    for decl in reasoning.declarations:
        if hasattr(decl, "content") and decl.name in [
            "aristotle_contradicted",
            "air_resistance_is_confound",
            "vacuum_prediction",
        ]:
            assert decl.content != "", f"{decl.name} should have content after execution"


def test_galileo_branching_structure():
    """Two chains branch from heavier_falls_faster, merge at synthesis."""
    runtime = DSLRuntime(executor=MockLLM())
    result = runtime.run(FIXTURE_DIR)

    fg = result.factor_graph
    # heavier_falls_faster should appear as tail in at least 2 factors
    # (refutation_chain and confound_chain)
    hff_factors = [f for f in fg.factors if "heavier_falls_faster" in f["tail"]]
    assert len(hff_factors) >= 2, "heavier_falls_faster should feed into 2+ chains"

    # vacuum_prediction should appear as head in synthesis_chain
    vp_factors = [f for f in fg.factors if "vacuum_prediction" in f["head"]]
    assert len(vp_factors) >= 1, "vacuum_prediction should be output of synthesis"
```

**Step 2: Run test**

Run: `pytest tests/libs/dsl/test_integration.py -v`
Expected: PASS (3 tests)

**Step 3: Commit**

```bash
git add tests/libs/dsl/test_integration.py
git commit -m "test(dsl): integration test — full galileo pipeline"
```

---

## Task 8: CLI Commands

**Files:**
- Create: `cli/commands/dsl.py`
- Create: `cli/__main__.py` (if not exists)
- Test: `tests/cli/test_dsl_cli.py`

**Step 1: Write the failing test**

```python
# tests/cli/test_dsl_cli.py
from pathlib import Path
from unittest.mock import patch

from cli.commands.dsl import load_cmd, run_cmd

FIXTURE_DIR = Path(__file__).parents[1] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


def test_load_cmd(capsys):
    load_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "5 modules" in captured.out


def test_run_cmd(capsys):
    run_cmd(str(FIXTURE_DIR))
    captured = capsys.readouterr()
    assert "galileo_falling_bodies" in captured.out
    assert "beliefs" in captured.out.lower() or "belief" in captured.out.lower()
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/cli/test_dsl_cli.py -v`
Expected: FAIL (ImportError)

**Step 3: Write minimal implementation**

```python
# cli/commands/dsl.py
"""Gaia DSL CLI commands."""

from __future__ import annotations

from pathlib import Path

from libs.dsl.executor import ActionExecutor
from libs.dsl.runtime import DSLRuntime


class StubExecutor(ActionExecutor):
    """Stub executor that echoes content (no real LLM)."""

    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return result

    def execute_lambda(self, content: str, input_text: str) -> str:
        return content


def load_cmd(path: str) -> None:
    """Load and validate a DSL package."""
    runtime = DSLRuntime()
    result = runtime.load(Path(path))
    pkg = result.package

    print(f"Package: {pkg.name}")
    if pkg.version:
        print(f"Version: {pkg.version}")
    print(f"Loaded: {len(pkg.loaded_modules)} modules")
    for mod in pkg.loaded_modules:
        decl_count = len(mod.declarations)
        export_count = len(mod.export)
        print(f"  {mod.type} {mod.name}: {decl_count} declarations, {export_count} exports")
    print(f"Package exports: {', '.join(pkg.export)}")


def run_cmd(path: str) -> None:
    """Load, execute, and run BP on a DSL package."""
    runtime = DSLRuntime(executor=StubExecutor())
    result = runtime.run(Path(path))

    print(f"Package: {result.package.name}")
    summary = result.inspect()
    print(f"Variables: {summary['variables']}")
    print(f"Factors: {summary['factors']}")
    print()
    print("Beliefs after BP:")
    for name, belief in sorted(result.beliefs.items()):
        fg = result.factor_graph
        prior = fg.variables.get(name, "?")
        print(f"  {name}: prior={prior} -> belief={belief:.4f}")
```

**Step 4: Run test to verify it passes**

Run: `pytest tests/cli/test_dsl_cli.py -v`
Expected: PASS (2 tests)

**Step 5: Commit**

```bash
git add cli/ tests/cli/
git commit -m "feat(dsl): CLI commands — gaia load / gaia run"
```

---

## Task 9: Lint and Final Verification

**Step 1: Run full test suite**

```bash
pytest tests/libs/dsl/ tests/cli/test_dsl_cli.py -v
```

Expected: All tests PASS

**Step 2: Run linter**

```bash
ruff check libs/dsl/ cli/ tests/libs/dsl/ tests/cli/test_dsl_cli.py
ruff format libs/dsl/ cli/ tests/libs/dsl/ tests/cli/test_dsl_cli.py
```

**Step 3: Run existing tests to verify no regressions**

```bash
pytest tests/ -x -q --ignore=tests/libs/storage/test_neo4j_store.py
```

Expected: All existing tests still pass

**Step 4: Commit any fixes**

```bash
git add -A
git commit -m "chore(dsl): lint and format"
```

---

## Summary

| Task | Component | Tests | Description |
|------|-----------|-------|-------------|
| 1 | `libs/dsl/models.py` | 9 | Pydantic models for DSL type system |
| 2 | `libs/dsl/loader.py` | 11 | YAML loader — parse package + modules |
| 3 | `libs/dsl/resolver.py` | 5 | Reference resolver — link Refs to targets |
| 4 | `libs/dsl/compiler.py` | 6 | Factor graph compiler — ChainExpr to BP graph |
| 5 | `libs/dsl/executor.py` | 5 | Action executor — walk chains, call LLM/tools |
| 6 | `libs/dsl/runtime.py` | 4 | Runtime — full Load → Execute → Infer → Inspect |
| 7 | Integration test | 3 | End-to-end galileo pipeline |
| 8 | `cli/commands/dsl.py` | 2 | CLI commands — load / run |
| 9 | Lint + verify | — | Final checks |

**Total:** ~45 tests, ~8 new files, ~800 lines of new code.

**Pipeline:**
```
YAML files → Load → AST → Execute (LLM/tools) → Infer (BP) → Beliefs
                ↑                                      ↑
            loader.py                             compiler.py
            resolver.py                           runtime.py
```
