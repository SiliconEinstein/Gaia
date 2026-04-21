# Gaia Lang v6 Implementation Plan — Phase 1: Knowledge Types + Parameterized Claims

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the flat `Knowledge(type=str)` with a class hierarchy (`Context`, `Setting`, `Claim`, `Question`) and add parameterized Claim support with docstring templates, `[@ref]` Knowledge parameters, `{param}` value parameters, Grounding metadata, and `Claim.supports` tracking.

**Architecture:** v6 introduces a Knowledge class hierarchy in `gaia/lang/runtime/` where `Claim` is the only probabilistic type. Parameterized Claims use Python class inheritance + docstring templates. The compiler (`gaia/lang/compiler/compile.py`) is updated to handle the new types and render templates. IR changes are minimal: add `"context"` to `KnowledgeType` and `value` to `Parameter`.

**Tech Stack:** Python 3.12+, dataclasses, Pydantic v2 (IR models), pytest

**Spec:** `docs/specs/2026-04-21-gaia-lang-v6-design.md` §1-3, `docs/specs/2026-04-21-gaia-ir-v6-design.md` §1

---

## Phased Implementation Overview

This is **Phase 1** of 5 phases:

1. **Phase 1** (this plan): Knowledge types + Parameterized Claims + Grounding
2. **Phase 2**: Action hierarchy (Derive/Observe/Compute/Equal/Contradict/Infer) + Claim.supports
3. **Phase 3**: Compiler updates (lower Actions to IR, action_label in metadata)
4. **Phase 4**: ReviewManifest + Review + auto-generated audit questions
5. **Phase 5**: InquiryState + Quality Gate CLI

Each phase is a separate PR with its own plan doc.

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `gaia/lang/runtime/knowledge.py` | Knowledge base class + Context, Setting, Claim, Question subclasses |
| `gaia/lang/runtime/grounding.py` | Grounding dataclass |
| `gaia/lang/runtime/param.py` | Param dataclass with UNBOUND sentinel |
| `tests/gaia/lang/test_knowledge_v6.py` | Tests for v6 Knowledge types |
| `tests/gaia/lang/test_parameterized_claims.py` | Tests for parameterized Claims |
| `tests/gaia/lang/test_grounding.py` | Tests for Grounding |

### Modified files

| File | Changes |
|---|---|
| `gaia/lang/runtime/nodes.py` | Import from new modules, keep v5 `Knowledge` as compat alias |
| `gaia/lang/runtime/package.py` | Handle new Knowledge subclasses in `_register_knowledge()` |
| `gaia/lang/dsl/knowledge.py` | Add `context()` function, keep v5 `claim()`/`setting()`/`question()` as compat wrappers |
| `gaia/lang/dsl/__init__.py` | Export new types + `context()` |
| `gaia/lang/__init__.py` | Export new types |
| `gaia/ir/knowledge.py` | Add `CONTEXT = "context"` to KnowledgeType, add `value` to Parameter |
| `gaia/lang/compiler/compile.py` | Handle Knowledge subclasses, render parameterized templates, store `content_template` + `grounding` in metadata |

---

## Chunk 1: Knowledge Class Hierarchy

### Task 1: Param dataclass and UNBOUND sentinel

**Files:**
- Create: `gaia/lang/runtime/param.py`
- Test: `tests/gaia/lang/test_parameterized_claims.py`

- [ ] **Step 1: Write failing test for Param and UNBOUND**

```python
# tests/gaia/lang/test_parameterized_claims.py
from gaia.lang.runtime.param import Param, UNBOUND


def test_param_unbound_sentinel():
    p = Param(name="value", type=float)
    assert p.value is UNBOUND
    assert p.value is not None


def test_param_bound():
    p = Param(name="value", type=float, value=5000.0)
    assert p.value == 5000.0
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py -v`
Expected: FAIL (module not found)

- [ ] **Step 3: Implement Param**

```python
# gaia/lang/runtime/param.py
"""Parameterization primitives for Gaia Lang v6."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


class _Unbound:
    """Sentinel for unbound parameters. Not None."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNBOUND"

    def __bool__(self) -> bool:
        return False


UNBOUND = _Unbound()


@dataclass
class Param:
    """A single parameter in a parameterized Knowledge type."""

    name: str
    type: type
    value: Any = field(default_factory=lambda: UNBOUND)
```

- [ ] **Step 4: Run test — verify it passes**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/param.py tests/gaia/lang/test_parameterized_claims.py
git commit -m "feat(lang): add Param dataclass with UNBOUND sentinel"
```

---

### Task 2: Grounding dataclass

**Files:**
- Create: `gaia/lang/runtime/grounding.py`
- Test: `tests/gaia/lang/test_grounding.py`

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_grounding.py
from gaia.lang.runtime.grounding import Grounding


def test_grounding_source_fact():
    g = Grounding(kind="source_fact", rationale="Extracted from Fig.2.")
    assert g.kind == "source_fact"
    assert g.rationale == "Extracted from Fig.2."
    assert g.source_refs == []


def test_grounding_with_source_refs():
    g = Grounding(kind="source_fact", rationale="From paper.", source_refs=["ctx_1"])
    assert g.source_refs == ["ctx_1"]


def test_grounding_invalid_kind():
    import pytest
    with pytest.raises(ValueError):
        Grounding(kind="invalid_kind", rationale="bad")
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/gaia/lang/test_grounding.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Grounding**

```python
# gaia/lang/runtime/grounding.py
"""Grounding metadata for root Claims."""

from __future__ import annotations

from dataclasses import dataclass, field

_VALID_KINDS = frozenset({"assumption", "source_fact", "definition", "imported", "judgment", "open"})


@dataclass
class Grounding:
    """Explains why a root Claim can have a prior."""

    kind: str
    rationale: str = ""
    source_refs: list[str] = field(default_factory=list)

    def __post_init__(self):
        if self.kind not in _VALID_KINDS:
            raise ValueError(f"Invalid grounding kind {self.kind!r}. Must be one of: {sorted(_VALID_KINDS)}")
```

- [ ] **Step 4: Run test — verify passes**

Run: `pytest tests/gaia/lang/test_grounding.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/grounding.py tests/gaia/lang/test_grounding.py
git commit -m "feat(lang): add Grounding dataclass for root Claim provenance"
```

---

### Task 3: Knowledge class hierarchy

**Files:**
- Create: `gaia/lang/runtime/knowledge.py`
- Test: `tests/gaia/lang/test_knowledge_v6.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/gaia/lang/test_knowledge_v6.py
from gaia.lang.runtime.knowledge import Knowledge, Context, Setting, Claim, Question
from gaia.lang.runtime.grounding import Grounding


def test_context_creation():
    ctx = Context("Raw experiment notes.")
    assert ctx.content == "Raw experiment notes."
    assert ctx.type == "context"


def test_setting_creation():
    s = Setting("Blackbody cavity at thermal equilibrium.")
    assert s.type == "setting"
    assert s.content == "Blackbody cavity at thermal equilibrium."


def test_claim_creation():
    c = Claim("Energy exchange is quantized.", prior=0.5)
    assert c.type == "claim"
    assert c.prior == 0.5
    assert c.supports == []


def test_claim_no_prior():
    c = Claim("A proposition.")
    assert c.prior is None


def test_claim_with_grounding():
    g = Grounding(kind="source_fact", rationale="From paper.")
    c = Claim("UV data.", prior=0.95, grounding=g)
    assert c.grounding.kind == "source_fact"


def test_question_creation():
    q = Question("Should we ship variant B?")
    assert q.type == "question"


def test_context_cannot_have_prior():
    import pytest
    with pytest.raises(TypeError):
        Context("raw text", prior=0.5)


def test_setting_cannot_have_prior():
    import pytest
    with pytest.raises(TypeError):
        Setting("background", prior=0.5)
```

- [ ] **Step 2: Run — verify fails**

Run: `pytest tests/gaia/lang/test_knowledge_v6.py -v`
Expected: FAIL

- [ ] **Step 3: Implement Knowledge hierarchy**

```python
# gaia/lang/runtime/knowledge.py
"""Gaia Lang v6 Knowledge class hierarchy."""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from gaia.lang.runtime.grounding import Grounding

if TYPE_CHECKING:
    from gaia.lang.runtime.package import CollectedPackage

_current_package: ContextVar[CollectedPackage | None] = ContextVar(
    "_current_package", default=None
)


@dataclass
class Knowledge:
    """Base knowledge node. Plain text, not in reasoning graph."""

    content: str
    type: str = "knowledge"
    title: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None
    _package: CollectedPackage | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _source_module: str | None = field(
        default=None, init=False, repr=False, compare=False
    )
    _declaration_index: int | None = field(
        default=None, init=False, repr=False, compare=False
    )

    def __post_init__(self):
        pkg = _current_package.get()
        source_module = None
        if pkg is None:
            from gaia.lang.runtime.package import infer_package_and_module

            pkg, source_module = infer_package_and_module()
        if pkg is not None:
            self._source_module = source_module
            self._package = pkg
            pkg._register_knowledge(self)

    def __hash__(self) -> int:
        return id(self)


@dataclass
class Context(Knowledge):
    """Raw unformalized text. Does not enter BP."""

    type: str = field(default="context", init=False)

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Context cannot have a prior.")
        super().__init__(content=content, **kwargs)


@dataclass
class Setting(Knowledge):
    """Formalized background. No probability."""

    type: str = field(default="setting", init=False)

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Setting cannot have a prior.")
        super().__init__(content=content, **kwargs)


@dataclass
class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    type: str = field(default="claim", init=False)
    prior: float | None = None
    grounding: Grounding | None = None
    supports: list = field(default_factory=list)  # list[Action], forward ref


@dataclass
class Question(Knowledge):
    """Open inquiry. Does not enter BP."""

    type: str = field(default="question", init=False)
    targets: list[Claim] = field(default_factory=list)

    def __init__(self, content: str, **kwargs):
        if "prior" in kwargs:
            raise TypeError("Question cannot have a prior.")
        targets = kwargs.pop("targets", [])
        super().__init__(content=content, **kwargs)
        self.targets = targets
```

- [ ] **Step 4: Run — verify passes**

Run: `pytest tests/gaia/lang/test_knowledge_v6.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/knowledge.py tests/gaia/lang/test_knowledge_v6.py
git commit -m "feat(lang): add v6 Knowledge class hierarchy (Context, Setting, Claim, Question)"
```

---

## Chunk 2: Parameterized Claims

### Task 4: Parameterized Claim subclassing with docstring templates

**Files:**
- Modify: `gaia/lang/runtime/knowledge.py` (add metaclass/init_subclass logic)
- Test: `tests/gaia/lang/test_parameterized_claims.py` (add more tests)

- [ ] **Step 1: Write failing tests for parameterized Claims**

```python
# append to tests/gaia/lang/test_parameterized_claims.py
from enum import Enum
from gaia.lang.runtime.knowledge import Claim, Setting
from gaia.lang.runtime.param import Param, UNBOUND


class MoleculeType(str, Enum):
    DNA = "DNA"
    RNA = "RNA"
    PROTEIN = "protein"


class CavityTemperature(Claim):
    """Cavity temperature is set to {value}K."""
    value: float


class InfoTransfer(Claim):
    """Information can transfer from {src} to {dst}."""
    src: MoleculeType
    dst: MoleculeType


def test_parameterized_claim_content_rendering():
    T = CavityTemperature(value=5000.0)
    assert T.content == "Cavity temperature is set to 5000.0K."


def test_parameterized_claim_parameters():
    T = CavityTemperature(value=5000.0)
    assert len(T.parameters) == 1
    assert T.parameters[0]["name"] == "value"
    assert T.parameters[0]["value"] == 5000.0


def test_parameterized_claim_enum():
    t = InfoTransfer(src=MoleculeType.DNA, dst=MoleculeType.RNA)
    assert t.content == "Information can transfer from DNA to RNA."


def test_partial_binding():
    t = InfoTransfer(src=MoleculeType.DNA)
    assert "{dst}" in t.content
    assert "DNA" in t.content
```

- [ ] **Step 2: Run — verify fails**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py::test_parameterized_claim_content_rendering -v`
Expected: FAIL

- [ ] **Step 3: Implement parameterized Claim via `__init_subclass__`**

Add to `gaia/lang/runtime/knowledge.py` in the `Claim` class:

```python
# In Claim class, add __init_subclass__ to collect typed fields from annotations
# and __init__ override to handle template rendering

class Claim(Knowledge):
    """Proposition with prior. Participates in BP."""

    type: str = field(default="claim", init=False)
    prior: float | None = None
    grounding: Grounding | None = None
    supports: list = field(default_factory=list)

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        # Collect parameter annotations (skip Knowledge/Claim base fields)
        base_fields = {
            "content", "type", "title", "background", "parameters",
            "provenance", "metadata", "label", "prior", "grounding",
            "supports", "targets",
        }
        cls._param_fields = {}
        for name, ann in getattr(cls, "__annotations__", {}).items():
            if name not in base_fields and not name.startswith("_"):
                cls._param_fields[name] = ann

    def __init__(self, content: str | None = None, **kwargs):
        # Separate param fields from Knowledge fields
        param_values = {}
        knowledge_kwargs = {}
        param_fields = getattr(self.__class__, "_param_fields", {})

        for k, v in kwargs.items():
            if k in param_fields:
                param_values[k] = v
            else:
                knowledge_kwargs[k] = v

        # Build parameters list
        params = []
        for name, ann in param_fields.items():
            val = param_values.get(name, UNBOUND)
            params.append({"name": name, "type": ann.__name__ if isinstance(ann, type) else str(ann), "value": val})

        # Render content from docstring template
        template = self.__class__.__doc__ or ""
        if content is None and template and param_fields:
            # Store template in metadata
            knowledge_kwargs.setdefault("metadata", {})["content_template"] = template
            # Render with available values
            render_values = {}
            for name in param_fields:
                val = param_values.get(name, UNBOUND)
                if val is not UNBOUND:
                    render_values[name] = val if not isinstance(val, Knowledge) else f"[@{val.label or '?'}]"
                # Leave unbound as {name} placeholder
            content = template.format_map(_SafeFormatDict(render_values))

        # Store param values on instance for access
        for name, val in param_values.items():
            object.__setattr__(self, name, val)

        super().__init__(content=content or "", parameters=params, **knowledge_kwargs)


class _SafeFormatDict(dict):
    """Returns {key} for missing keys instead of raising KeyError."""
    def __missing__(self, key):
        return f"{{{key}}}"
```

- [ ] **Step 4: Run — verify passes**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/knowledge.py tests/gaia/lang/test_parameterized_claims.py
git commit -m "feat(lang): add parameterized Claim subclassing with docstring templates"
```

---

### Task 5: Knowledge-typed parameters with [@ref] syntax

**Files:**
- Modify: `gaia/lang/runtime/knowledge.py` (update template rendering)
- Test: `tests/gaia/lang/test_parameterized_claims.py` (add tests)

- [ ] **Step 1: Write failing test**

```python
# append to tests/gaia/lang/test_parameterized_claims.py

class ABCounts(Claim):
    """[@experiment] recorded {ctrl_k}/{ctrl_n} control conversions."""
    experiment: Setting
    ctrl_n: int
    ctrl_k: int


def test_knowledge_parameter_ref_syntax(tmp_path):
    """Knowledge-typed params render as [@label]."""
    exp = Setting("AB test exp_123.")
    exp.label = "exp_123"
    counts = ABCounts(experiment=exp, ctrl_n=10_000, ctrl_k=500)
    assert "[@exp_123]" in counts.content
    assert "500/10000" in counts.content


def test_knowledge_parameter_stored_as_reference():
    """Knowledge param value is the object, not a string."""
    exp = Setting("AB test.")
    exp.label = "exp_123"
    counts = ABCounts(experiment=exp, ctrl_n=10_000, ctrl_k=500)
    param = [p for p in counts.parameters if p["name"] == "experiment"][0]
    assert param["value"] is exp
```

- [ ] **Step 2: Run — verify fails**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py::test_knowledge_parameter_ref_syntax -v`
Expected: FAIL

- [ ] **Step 3: Update template rendering for Knowledge params**

In `Claim.__init__`, update the rendering logic to detect Knowledge-typed values:

```python
# In the render_values loop:
for name in param_fields:
    val = param_values.get(name, UNBOUND)
    if val is not UNBOUND:
        if isinstance(val, Knowledge):
            render_values[name] = f"[@{val.label or '?'}]"
        else:
            render_values[name] = val
```

The `[@param_name]` in the docstring template is replaced by the refs resolver at compile time. At runtime, we render `[@label]` directly.

- [ ] **Step 4: Run — verify passes**

Run: `pytest tests/gaia/lang/test_parameterized_claims.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/knowledge.py tests/gaia/lang/test_parameterized_claims.py
git commit -m "feat(lang): support Knowledge-typed parameters with [@ref] syntax"
```

---

## Chunk 3: IR Updates + DSL Compat Layer

### Task 6: IR KnowledgeType.CONTEXT + Parameter.value

**Files:**
- Modify: `gaia/ir/knowledge.py`
- Test: `tests/gaia/ir/test_knowledge_ir.py` (or existing test file)

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/ir/test_knowledge_context.py
from gaia.ir.knowledge import KnowledgeType, Parameter


def test_context_knowledge_type():
    assert KnowledgeType.CONTEXT == "context"


def test_parameter_value_field():
    p = Parameter(name="experiment", type="Setting", value="github:pkg::exp_123")
    assert p.value == "github:pkg::exp_123"


def test_parameter_value_default_none():
    p = Parameter(name="x", type="int")
    assert p.value is None
```

- [ ] **Step 2: Run — verify fails**

Run: `pytest tests/gaia/ir/test_knowledge_context.py -v`
Expected: FAIL (CONTEXT not in enum, value not a field)

- [ ] **Step 3: Add CONTEXT to KnowledgeType and value to Parameter**

In `gaia/ir/knowledge.py`:

```python
class KnowledgeType(StrEnum):
    CLAIM = "claim"
    SETTING = "setting"
    QUESTION = "question"
    CONTEXT = "context"  # NEW v6
```

Find the `Parameter` class and add:

```python
class Parameter(BaseModel):
    name: str
    type: str
    value: Any | None = None  # NEW v6: bound value (JsonValue or QID string)
```

- [ ] **Step 4: Run — verify passes**

Run: `pytest tests/gaia/ir/test_knowledge_context.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite to verify no regressions**

Run: `pytest tests/ -x -q`
Expected: All existing tests still pass

- [ ] **Step 6: Commit**

```bash
git add gaia/ir/knowledge.py tests/gaia/ir/test_knowledge_context.py
git commit -m "feat(ir): add KnowledgeType.CONTEXT and Parameter.value for v6"
```

---

### Task 7: DSL compat layer — context() function + v5 wrappers

**Files:**
- Modify: `gaia/lang/dsl/knowledge.py`
- Modify: `gaia/lang/dsl/__init__.py`
- Modify: `gaia/lang/__init__.py`
- Test: `tests/gaia/lang/test_knowledge_v6.py` (add compat tests)

- [ ] **Step 1: Write tests for context() and v5 compat**

```python
# append to tests/gaia/lang/test_knowledge_v6.py

def test_context_dsl_function():
    from gaia.lang.dsl.knowledge import context
    ctx = context("Raw experiment notes.")
    assert ctx.type == "context"
    assert ctx.content == "Raw experiment notes."


def test_v5_claim_still_works():
    """v5 claim() function returns a v6 Claim."""
    from gaia.lang import claim
    c = claim("A proposition.")
    assert c.type == "claim"
    assert isinstance(c, Claim)


def test_v5_setting_still_works():
    from gaia.lang import setting
    s = setting("Background info.")
    assert s.type == "setting"
    assert isinstance(s, Setting)
```

- [ ] **Step 2: Run — verify fails (context not defined)**

- [ ] **Step 3: Add context() to DSL, update exports**

In `gaia/lang/dsl/knowledge.py` add:

```python
def context(content: str, **metadata) -> Knowledge:
    """Create a Context knowledge node."""
    from gaia.lang.runtime.knowledge import Context
    return Context(content, **(_flatten_metadata(metadata) if metadata else {}))
```

Update `gaia/lang/dsl/__init__.py` to export `context`.
Update `gaia/lang/__init__.py` to export `Context, Setting, Claim, Question, context, Grounding`.

Update existing `claim()`, `setting()`, `question()` to return v6 subclasses instead of `Knowledge(type=...)`.

- [ ] **Step 4: Run — verify passes**

Run: `pytest tests/gaia/lang/test_knowledge_v6.py -v`
Expected: PASS

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`
Expected: All pass (v5 packages still work)

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/dsl/knowledge.py gaia/lang/dsl/__init__.py gaia/lang/__init__.py tests/gaia/lang/test_knowledge_v6.py
git commit -m "feat(lang): add context() DSL, export v6 Knowledge types, v5 compat"
```

---

### Task 8: Compiler handles v6 Knowledge types

**Files:**
- Modify: `gaia/lang/compiler/compile.py`
- Test: `tests/gaia/lang/test_compiler.py` (add tests)

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_compiler_v6.py
from gaia.lang.runtime.knowledge import Claim, Setting, Context
from gaia.lang.runtime.grounding import Grounding


def test_compile_context_type(tmp_path):
    """Context Knowledge compiles with type='context'."""
    # Create a minimal package with a Context node
    # Use existing test fixtures pattern from test_compiler.py
    # Verify ir["knowledges"] contains a node with type="context"
    pass  # detailed implementation depends on existing test helpers


def test_compile_grounding_in_metadata(tmp_path):
    """Grounding metadata appears in compiled IR."""
    pass  # verify metadata.grounding in compiled knowledge node


def test_compile_parameterized_claim_template(tmp_path):
    """Parameterized Claim stores content_template in metadata."""
    pass  # verify metadata.content_template in compiled knowledge node


def test_compile_parameter_value(tmp_path):
    """Bound parameter values appear in compiled IR parameters."""
    pass  # verify Parameter.value in compiled knowledge node
```

Note: Detailed test implementations should follow existing patterns in `tests/gaia/lang/test_compiler.py` and `tests/cli/test_compile.py`.

- [ ] **Step 2: Run — verify fails**

- [ ] **Step 3: Update compiler**

Key changes in `gaia/lang/compiler/compile.py`:
1. `_content_hash()`: Include `content_template` + param values for parameterized Claims (not just content)
2. Knowledge IR construction: Set `type="context"` for Context nodes
3. Store `grounding` in `metadata.grounding` if present
4. Store `content_template` in `metadata.content_template` if present  
5. For Knowledge-typed parameters: store QID as `Parameter.value`

- [ ] **Step 4: Run — verify passes**

- [ ] **Step 5: Run full test suite**

Run: `pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/compiler/compile.py tests/gaia/lang/test_compiler_v6.py
git commit -m "feat(compiler): handle v6 Knowledge types, grounding, parameterized templates"
```

---

## Chunk 4: Integration Test

### Task 9: End-to-end v6 package with parameterized Claims

**Files:**
- Test: `tests/cli/test_compile_v6.py`

- [ ] **Step 1: Write end-to-end test**

Create a minimal v6 package using Context, Setting, Claim (parameterized), compile it, and verify the IR output.

```python
# tests/cli/test_compile_v6.py
"""End-to-end test: v6 Knowledge types compile to correct IR."""

from pathlib import Path
from typer.testing import CliRunner
from gaia.cli.main import app
import json

runner = CliRunner()


def test_v6_knowledge_types_compile(tmp_path):
    """A package using v6 Knowledge types (Context, Setting, Claim subclass) compiles."""
    pkg_dir = tmp_path / "v6_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "v6-pkg-gaia"\nversion = "1.0.0"\n'
        'description = "v6 test"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "v6_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import Context, Setting, Claim, Grounding\n\n"
        "ctx = Context('Raw AB test data from dashboard.')\n"
        "exp = Setting('AB test exp_123: 50/50 randomization.')\n"
        "hyp = Claim('Variant B is better.', prior=0.5,\n"
        "    grounding=Grounding(kind='judgment', rationale='Uninformative prior.'))\n"
        "__all__ = ['hyp']\n"
    )
    (pkg_src / "priors.py").write_text(
        "from . import hyp\n\n"
        "PRIORS: dict = {\n"
        '    hyp: (0.5, "uninformative"),\n'
        "}\n"
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0, f"Compile failed: {result.output}"

    ir_path = pkg_dir / ".gaia" / "ir.json"
    assert ir_path.exists()
    ir = json.loads(ir_path.read_text())

    # Verify context type exists
    types = {k["type"] for k in ir["knowledges"]}
    assert "context" in types

    # Verify grounding in metadata
    hyp_node = [k for k in ir["knowledges"] if k.get("label") == "hyp"][0]
    assert "grounding" in hyp_node.get("metadata", {}).get("gaia", {}) or \
           "grounding" in hyp_node.get("metadata", {})
```

- [ ] **Step 2: Run — verify passes**

Run: `pytest tests/cli/test_compile_v6.py -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/cli/test_compile_v6.py
git commit -m "test: add end-to-end v6 Knowledge types compilation test"
```

---

## Verification

After all tasks complete:

1. **Unit tests**: `pytest tests/gaia/lang/test_knowledge_v6.py tests/gaia/lang/test_parameterized_claims.py tests/gaia/lang/test_grounding.py -v`
2. **IR tests**: `pytest tests/gaia/ir/test_knowledge_context.py -v`
3. **Integration**: `pytest tests/cli/test_compile_v6.py -v`
4. **Full regression**: `pytest tests/ -x -q`
5. **Lint**: `ruff check . && ruff format --check .`

All existing v5 packages must continue to compile and infer correctly.
