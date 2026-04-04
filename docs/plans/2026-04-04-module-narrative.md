# Module Narrative Order Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reuse Python modules as Gaia modules with declaration-order narrative. Knowledge gets `module`, `declaration_index`, `exported` fields in IR. README uses these for section grouping.

**Architecture:** Runtime captures source module name and per-module declaration index during `Knowledge.__post_init__`. Compiler reads these + `__all__` to populate new IR fields. README generator uses `module_order` + `declaration_index` instead of topological sort when available.

**Tech Stack:** Python stdlib only. No new dependencies.

**Spec:** `docs/specs/2026-04-04-module-narrative-design.md`

---

## File Structure

| File | Action | Responsibility |
|------|--------|---------------|
| `gaia/lang/runtime/nodes.py` | Modify | Add `_source_module`, `_declaration_index` to Knowledge |
| `gaia/lang/runtime/package.py` | Modify | Track module counters and module order in CollectedPackage |
| `gaia/ir/knowledge.py` | Modify | Add `module`, `declaration_index`, `exported` fields |
| `gaia/ir/graphs.py` | Modify | Add `module_order` to LocalCanonicalGraph |
| `gaia/lang/compiler/compile.py` | Modify | Populate new IR fields from runtime data + `__all__` |
| `gaia/cli/commands/_readme.py` | Modify | Use module_order + declaration_index for narrative |
| `tests/gaia/lang/test_module_narrative.py` | Create | Tests for runtime tracking + compilation |
| `tests/cli/test_readme.py` | Modify | Test module-aware README generation |

---

## Chunk 1: Runtime tracking

### Task 1: Capture source module and declaration index

**Files:**
- Modify: `gaia/lang/runtime/nodes.py`
- Modify: `gaia/lang/runtime/package.py`
- Create: `tests/gaia/lang/test_module_narrative.py`

- [ ] **Step 1: Write failing tests for module tracking**

```python
# tests/gaia/lang/test_module_narrative.py
"""Tests for module narrative tracking."""

from gaia.lang.runtime.nodes import Knowledge, _current_package
from gaia.lang.runtime.package import CollectedPackage


def test_declaration_index_increments_within_module():
    pkg = CollectedPackage("test_pkg")
    with pkg:
        a = Knowledge(content="A.", type="claim")
        b = Knowledge(content="B.", type="claim")
        c = Knowledge(content="C.", type="claim")
    assert a._declaration_index == 0
    assert b._declaration_index == 1
    assert c._declaration_index == 2


def test_module_order_tracks_first_seen():
    pkg = CollectedPackage("test_pkg")
    # Simulate declarations from different modules
    a = Knowledge(content="A.", type="claim")
    a._source_module = "s1_intro"
    b = Knowledge(content="B.", type="claim")
    b._source_module = "s2_model"
    c = Knowledge(content="C.", type="claim")
    c._source_module = "s1_intro"

    pkg._register_knowledge(a)
    pkg._register_knowledge(b)
    pkg._register_knowledge(c)

    assert pkg._module_order == ["s1_intro", "s2_model"]
    assert a._declaration_index == 0
    assert b._declaration_index == 0  # first in s2_model
    assert c._declaration_index == 1  # second in s1_intro


def test_none_module_for_init_file():
    pkg = CollectedPackage("test_pkg")
    a = Knowledge(content="A.", type="claim")
    a._source_module = None
    pkg._register_knowledge(a)
    assert a._declaration_index == 0
    assert pkg._module_order == []  # None module not tracked in order
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/gaia/lang/test_module_narrative.py -v`

- [ ] **Step 3: Implement runtime tracking**

In `gaia/lang/runtime/nodes.py`, add fields to Knowledge:

```python
@dataclass
class Knowledge:
    ...
    _source_module: str | None = field(default=None, init=False, repr=False, compare=False)
    _declaration_index: int | None = field(default=None, init=False, repr=False, compare=False)
```

In `gaia/lang/runtime/package.py`, update CollectedPackage:

```python
class CollectedPackage:
    def __init__(self, name: str, *, namespace: str = "github", version: str = "0.1.0"):
        ...
        self._module_counters: dict[str | None, int] = {}
        self._module_order: list[str] = []

    def _register_knowledge(self, k: Knowledge):
        self.knowledge.append(k)
        module = k._source_module
        if module not in self._module_counters:
            if module is not None:
                self._module_order.append(module)
            self._module_counters[module] = 0
        k._declaration_index = self._module_counters[module]
        self._module_counters[module] += 1
```

Update `infer_package_from_callstack` to return both package and module name. Then in `Knowledge.__post_init__`, store the module name:

```python
# package.py
def infer_package_and_module() -> tuple[CollectedPackage | None, str | None]:
    """Infer package and relative module name from the call stack."""
    module_name = _caller_module_name()
    if not module_name:
        return None, None
    pyproject = _pyproject_for_module(module_name)
    if pyproject is None:
        return None, None
    pkg = _load_inferred_package(pyproject)
    if pkg is None:
        return None, None
    # Compute relative module name: strip package prefix
    relative = module_name.removeprefix(f"{pkg.name}.")
    if relative == pkg.name or relative == "__init__":
        relative = None  # root module
    return pkg, relative
```

```python
# nodes.py — Knowledge.__post_init__
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
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/gaia/lang/test_module_narrative.py -v`

- [ ] **Step 5: Commit**

```bash
git add gaia/lang/runtime/nodes.py gaia/lang/runtime/package.py tests/gaia/lang/test_module_narrative.py
git commit -m "feat(lang): track source module and declaration index for narrative order"
```

---

## Chunk 2: IR fields + compiler

### Task 2: Add IR fields

**Files:**
- Modify: `gaia/ir/knowledge.py`
- Modify: `gaia/ir/graphs.py`

- [ ] **Step 1: Add fields to IR Knowledge**

```python
# gaia/ir/knowledge.py — add after provenance field:
class Knowledge(BaseModel):
    ...
    module: str | None = None
    declaration_index: int | None = None
    exported: bool = False
```

- [ ] **Step 2: Add module_order to LocalCanonicalGraph**

```python
# gaia/ir/graphs.py
class LocalCanonicalGraph(BaseModel):
    ...
    module_order: list[str] | None = None
```

Note: `module`, `declaration_index`, and `exported` should NOT participate in `ir_hash` computation (they are presentational, not semantic). Exclude them from `_canonicalize_knowledge_dump`:

```python
def _canonicalize_knowledge_dump(data: dict[str, Any]) -> dict[str, Any]:
    canonical = dict(data)
    canonical["parameters"] = sorted(canonical.get("parameters", []), key=_json_sort_key)
    if canonical.get("provenance") is not None:
        canonical["provenance"] = sorted(canonical["provenance"], key=_json_sort_key)
    # Exclude narrative fields from content hash
    canonical.pop("module", None)
    canonical.pop("declaration_index", None)
    canonical.pop("exported", None)
    return canonical
```

Also exclude `module_order` from graph-level hash — it's not in `_canonical_json` since that only hashes knowledges/operators/strategies.

- [ ] **Step 3: Run existing IR tests to verify no breakage**

Run: `pytest tests/ir/ -v`

- [ ] **Step 4: Commit**

```bash
git add gaia/ir/knowledge.py gaia/ir/graphs.py
git commit -m "feat(ir): add module, declaration_index, exported fields to Knowledge"
```

---

### Task 3: Populate IR fields in compiler

**Files:**
- Modify: `gaia/lang/compiler/compile.py`
- Modify: `gaia/cli/_packages.py`
- Create: `tests/cli/test_module_compile.py`

- [ ] **Step 1: Write failing test for module fields in compiled IR**

```python
# tests/cli/test_module_compile.py
"""Tests for module narrative fields in compiled IR."""

import json

from typer.testing import CliRunner

from gaia.cli.main import app

runner = CliRunner()


def test_compile_single_file_no_module(tmp_path):
    """Single-file package: module=None, declaration_index tracks order."""
    pkg_dir = tmp_path / "single_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "single-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "single_pkg"
    pkg_src.mkdir()
    (pkg_src / "__init__.py").write_text(
        "from gaia.lang import claim, setting\n\n"
        'env = setting("Environment.")\n'
        'a = claim("First.")\n'
        'b = claim("Second.")\n'
        '__all__ = ["b"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())

    by_label = {k["label"]: k for k in ir["knowledges"]}
    assert by_label["env"]["module"] is None
    assert by_label["env"]["declaration_index"] == 0
    assert by_label["a"]["declaration_index"] == 1
    assert by_label["b"]["declaration_index"] == 2
    assert by_label["b"]["exported"] is True
    assert by_label["a"]["exported"] is False
    assert ir.get("module_order") is None  # single file, no modules


def test_compile_multi_file_module_order(tmp_path):
    """Multi-file package: module and module_order populated."""
    pkg_dir = tmp_path / "multi_pkg"
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        '[project]\nname = "multi-pkg-gaia"\nversion = "1.0.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    pkg_src = pkg_dir / "multi_pkg"
    pkg_src.mkdir()
    (pkg_src / "sec_a.py").write_text(
        "from gaia.lang import claim\n\n"
        'x = claim("X from section A.")\n'
        'y = claim("Y from section A.")\n'
    )
    (pkg_src / "sec_b.py").write_text(
        "from gaia.lang import claim\n\n"
        'z = claim("Z from section B.")\n'
    )
    (pkg_src / "__init__.py").write_text(
        "from .sec_a import *\n"
        "from .sec_b import *\n\n"
        '__all__ = ["z"]\n'
    )

    result = runner.invoke(app, ["compile", str(pkg_dir)])
    assert result.exit_code == 0

    ir = json.loads((pkg_dir / ".gaia" / "ir.json").read_text())

    by_label = {k["label"]: k for k in ir["knowledges"]}
    assert by_label["x"]["module"] == "sec_a"
    assert by_label["y"]["module"] == "sec_a"
    assert by_label["z"]["module"] == "sec_b"
    assert by_label["x"]["declaration_index"] == 0
    assert by_label["y"]["declaration_index"] == 1
    assert by_label["z"]["declaration_index"] == 0
    assert by_label["z"]["exported"] is True
    assert by_label["x"]["exported"] is False
    assert ir["module_order"] == ["sec_a", "sec_b"]
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Update compiler to populate new fields**

In `gaia/lang/compiler/compile.py`, update the knowledge IR construction:

```python
# In compile_package_artifact, where ir_knowledges is built:
ir_knowledges = [
    IrKnowledge(
        id=knowledge_map[id(k)],
        label=k.label,
        type=k.type,
        content=k.content,
        parameters=[IrParameter(**p) for p in k.parameters],
        provenance=_knowledge_provenance(k),
        metadata=_knowledge_metadata(k),
        module=k._source_module if hasattr(k, "_source_module") else None,
        declaration_index=k._declaration_index if hasattr(k, "_declaration_index") else None,
        exported=False,  # set below
    )
    for k in knowledge_nodes
]
```

In `gaia/cli/_packages.py`, mark exported labels. Add a method or update `_assign_labels` to record exports:

```python
# After _assign_labels is called in load_gaia_package:
export_names = getattr(module, "__all__", None)
if isinstance(export_names, list):
    pkg._exported_labels = set(export_names)
else:
    pkg._exported_labels = set()
```

Then in the compiler, set `exported`:

```python
exported_labels = getattr(pkg, "_exported_labels", set())
for ir_k in ir_knowledges:
    if ir_k.label in exported_labels:
        ir_k.exported = True
```

Set `module_order` on the graph:

```python
module_order = pkg._module_order if pkg._module_order else None
# ... pass to graph construction
```

The compiled package dict gets the new field:

```python
# In to_json() or wherever the IR dict is built:
result["module_order"] = module_order
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/cli/test_module_compile.py -v`

- [ ] **Step 5: Run full test suite**

Run: `pytest -x -q`

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/compiler/compile.py gaia/cli/_packages.py tests/cli/test_module_compile.py
git commit -m "feat(compiler): populate module, declaration_index, exported in IR"
```

---

## Chunk 3: README integration

### Task 4: Update README generation to use module narrative

**Files:**
- Modify: `gaia/cli/commands/_readme.py`
- Modify: `tests/cli/test_readme.py`

- [ ] **Step 1: Write failing test**

```python
# Add to tests/cli/test_readme.py

def test_narrative_order_uses_module_order():
    """When module_order is present, use it instead of topo sort."""
    ir = {
        "module_order": ["sec_a", "sec_b"],
        "knowledges": [
            {"id": "ns:p::z", "label": "z", "type": "claim", "content": "Z.",
             "module": "sec_b", "declaration_index": 0, "exported": True},
            {"id": "ns:p::x", "label": "x", "type": "claim", "content": "X.",
             "module": "sec_a", "declaration_index": 0, "exported": False},
            {"id": "ns:p::y", "label": "y", "type": "claim", "content": "Y.",
             "module": "sec_a", "declaration_index": 1, "exported": False},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    pos_x = md.index("#### x")
    pos_y = md.index("#### y")
    pos_z = md.index("#### z")
    # sec_a before sec_b, x before y within sec_a
    assert pos_x < pos_y < pos_z
    # Module headings
    assert "### sec_a" in md
    assert "### sec_b" in md


def test_exported_marker_in_readme():
    ir = {
        "knowledges": [
            {"id": "ns:p::a", "label": "a", "type": "claim", "content": "A.",
             "exported": True},
            {"id": "ns:p::b", "label": "b", "type": "claim", "content": "B.",
             "exported": False},
        ],
        "strategies": [],
        "operators": [],
    }
    md = render_knowledge_nodes(ir)
    # Exported claim gets a marker
    assert "★" in md.split("#### a")[1].split("#### b")[0]
```

- [ ] **Step 2: Run tests to verify they fail**

- [ ] **Step 3: Update `_narrative_order` and `render_knowledge_nodes`**

```python
# _readme.py — update _narrative_order
def _narrative_order(ir: dict) -> list[dict]:
    """Return knowledge nodes in narrative reading order."""
    module_order = ir.get("module_order")
    nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]

    if module_order and any(k.get("module") for k in nodes):
        # Module-aware ordering
        module_rank = {m: i for i, m in enumerate(module_order)}

        def sort_key(k):
            mod = k.get("module")
            idx = k.get("declaration_index", 0)
            mod_rank = module_rank.get(mod, 999) if mod else -1
            return (mod_rank, idx)

        return sorted(nodes, key=sort_key)
    else:
        # Fallback: topo sort
        layers = topo_layers(ir)

        def sort_key(k):
            kid = k["id"]
            ktype = k["type"]
            if ktype == "question":
                return (999, 0, k.get("label", ""))
            if ktype == "setting":
                return (-1, 0, k.get("label", ""))
            return (layers.get(kid, 0), 1, k.get("label", ""))

        return sorted(nodes, key=sort_key)
```

Update `render_knowledge_nodes` to:
1. Group by module (section headings: `### module_name`)
2. Mark exported claims with ★

```python
# In render_knowledge_nodes, replace type-based grouping with module-based:
current_module = object()  # sentinel
for k in ordered:
    module = k.get("module")
    label = k.get("label", "")
    exported = k.get("exported", False)

    # Module heading (when module_order is available)
    if module_order and module != current_module:
        current_module = module
        heading = module if module else "Root"
        sections.append(f"### {heading}")
        sections.append("")

    # ... rest of node rendering, with ★ on exported
    marker = " ★" if exported else ""
    sections.append(f"#### {label}{marker}")
```

When no `module_order` (fallback), keep current type-based grouping (Settings/Claims/Questions).

- [ ] **Step 4: Run tests**

Run: `pytest tests/cli/test_readme.py -v`

- [ ] **Step 5: Run full test suite + lint**

Run: `pytest -x -q && ruff check . && ruff format --check .`

- [ ] **Step 6: Commit**

```bash
git add gaia/cli/commands/_readme.py tests/cli/test_readme.py
git commit -m "feat(cli): README uses module narrative order and exported markers"
```

---

### Task 5: Smoke test on electron liquid package

- [ ] **Step 1: Compile with --readme**

```bash
cd ~/project/SuperconductivityElectronLiquids.gaia
uv run gaia compile --readme
```

Verify: single-file package → fallback to topo sort (same as before), `exported` flags on `__all__` items, declaration_index in IR.

- [ ] **Step 2: Verify IR has new fields**

```bash
python3 -c "
import json
with open('.gaia/ir.json') as f:
    ir = json.load(f)
for k in ir['knowledges'][:5]:
    print(k['label'], k.get('module'), k.get('declaration_index'), k.get('exported'))
"
```

- [ ] **Step 3: Check README for exported markers**

Verify ★ appears on `__all__` entries in the README.

- [ ] **Step 4: Fix any issues and commit**
