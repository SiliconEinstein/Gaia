# Gaia Lang Package Restructure Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restructure gaia-lang into a proper Python package with standard language toolchain layout: rename `gaia_ir` → `ir`, reorganize `lang/` internals, move CLI into `gaia/lang/cli/`, and connect compiler to output IR Pydantic models.

**Architecture:** Three changes — (1) rename `gaia/gaia_ir/` → `gaia/ir/` and update all 67 import references across 18 files; (2) reorganize `gaia/lang/` into `dsl/`, `runtime/`, `compiler/` sub-packages; (3) move CLI from top-level `cli/commands/compile.py` into `gaia/lang/cli/`.

**Tech Stack:** Python 3.12+, Pydantic v2, Typer, ruff

**Working branch:** `feature/gaia-lang-v5` (in worktree `.worktrees/gaia-lang-v5`)

---

## File Structure

### Renames / moves

```
gaia/gaia_ir/              →  gaia/ir/                    # rename
gaia/lang/core.py          →  gaia/lang/runtime/nodes.py  # split
gaia/lang/core.py          →  gaia/lang/runtime/package.py # split
gaia/lang/__init__.py      →  gaia/lang/dsl/knowledge.py  # move logic out
gaia/lang/operators.py     →  gaia/lang/dsl/operators.py   # move into dsl/
gaia/lang/strategies.py    →  gaia/lang/dsl/strategies.py  # move into dsl/
gaia/lang/compiler.py      →  gaia/lang/compiler/compile.py # move into compiler/
cli/commands/compile.py    →  gaia/lang/cli/commands/compile.py # move CLI into package
```

### Final target structure

```
gaia/
├── ir/                          # Renamed from gaia_ir (IR v2 Pydantic models)
│   ├── __init__.py
│   ├── knowledge.py
│   ├── strategy.py
│   ├── operator.py
│   ├── graphs.py
│   ├── formalize.py
│   ├── parameterization.py
│   └── validator.py
│
├── lang/                        # DSL package (restructured)
│   ├── __init__.py              # Pure re-exports: from gaia.lang import claim, Package
│   ├── dsl/                     # User-facing API functions
│   │   ├── __init__.py
│   │   ├── knowledge.py         # claim(), setting(), question()
│   │   ├── operators.py         # contradiction(), equivalence(), ...
│   │   └── strategies.py        # noisy_and(), deduction(), ...
│   ├── runtime/                 # DSL runtime objects
│   │   ├── __init__.py
│   │   ├── nodes.py             # Knowledge, Strategy, Operator dataclasses
│   │   └── package.py           # Package context manager
│   ├── compiler/                # DSL → IR compilation
│   │   ├── __init__.py
│   │   ├── compile.py           # compile_package() → LocalCanonicalGraph
│   │   └── canonicalize.py      # QID, content_hash, strategy_id, ir_hash
│   └── cli/                     # CLI commands (part of gaia-lang package)
│       ├── __init__.py
│       ├── main.py              # Typer app entry point
│       └── commands/
│           ├── __init__.py
│           └── compile.py       # gaia compile
│
├── bp/                          # Belief propagation (unchanged, update imports)
└── lkm/                         # LKM (unchanged, update imports)
```

---

## Chunk 1: Rename gaia_ir → ir

This must go first because everything else depends on it. Pure mechanical rename + import updates.

### Task 1: Rename directory and update all internal imports

**Files:**
- Rename: `gaia/gaia_ir/` → `gaia/ir/`
- Modify: all `.py` files inside `gaia/ir/` — update self-references
- Modify: `gaia/bp/lowering.py`
- Modify: `gaia/lkm/core/lower.py`, `gaia/lkm/pipelines/lower.py`
- Modify: all files in `tests/gaia_ir/`
- Modify: `tests/test_lowering.py`
- Modify: `tests/gaia/lkm/models/test_models.py`
- Modify: `tests/fixtures/lkm/__init__.py`
- Rename: `tests/gaia_ir/` → `tests/ir/`

- [ ] **Step 1: Rename the directory**

```bash
cd /Users/kunchen/project/Gaia/.worktrees/gaia-lang-v5
git mv gaia/gaia_ir gaia/ir
git mv tests/gaia_ir tests/ir
```

- [ ] **Step 2: Global find-and-replace imports**

Replace `gaia.gaia_ir` with `gaia.ir` across all 18 files (67 occurrences):

```bash
# In gaia/ir/ (internal self-references)
find gaia/ir -name '*.py' -exec sed -i '' 's/gaia\.gaia_ir/gaia.ir/g' {} +

# In gaia/bp/
sed -i '' 's/gaia\.gaia_ir/gaia.ir/g' gaia/bp/lowering.py

# In gaia/lkm/
sed -i '' 's/gaia\.gaia_ir/gaia.ir/g' gaia/lkm/core/lower.py gaia/lkm/pipelines/lower.py

# In tests/
find tests -name '*.py' -exec sed -i '' 's/gaia\.gaia_ir/gaia.ir/g' {} +
```

- [ ] **Step 3: Run all tests**

```bash
pytest tests/ir/ tests/test_lowering.py -v
```

Expected: All pass (pure rename, no logic change).

- [ ] **Step 4: Lint and format**

```bash
ruff check gaia/ir/ gaia/bp/ gaia/lkm/ tests/ir/ tests/test_lowering.py
ruff format gaia/ir/ gaia/bp/ gaia/lkm/ tests/ir/ tests/test_lowering.py
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor: rename gaia/gaia_ir → gaia/ir

Pure rename + import update. 67 occurrences across 18 files.
No logic changes."
```

---

## Chunk 2: Reorganize gaia/lang/ internals

Split the flat structure into `dsl/`, `runtime/`, `compiler/` sub-packages.

### Task 2: Split core.py into runtime/nodes.py + runtime/package.py

**Files:**
- Create: `gaia/lang/runtime/__init__.py`
- Create: `gaia/lang/runtime/nodes.py` (Knowledge, Strategy, Operator + ContextVar)
- Create: `gaia/lang/runtime/package.py` (Package class)
- Delete: `gaia/lang/core.py`
- Modify: all files that import from `gaia.lang.core`

- [ ] **Step 1: Create runtime/ directory**

```bash
mkdir -p gaia/lang/runtime
```

- [ ] **Step 2: Create nodes.py** — move Knowledge, Strategy, Operator, _current_package ContextVar from core.py

The `_current_package` ContextVar stays with the nodes since `Knowledge.__post_init__` uses it.

- [ ] **Step 3: Create package.py** — move Package class from core.py

Package imports `_current_package` from nodes.

- [ ] **Step 4: Create runtime/__init__.py** — re-export all

```python
from gaia.lang.runtime.nodes import Knowledge, Strategy, Operator, _current_package
from gaia.lang.runtime.package import Package
```

- [ ] **Step 5: Update all imports** from `gaia.lang.core` to `gaia.lang.runtime`

Files to update:
- `gaia/lang/operators.py` (currently `from gaia.lang.core import Knowledge, Operator`)
- `gaia/lang/strategies.py` (currently `from gaia.lang.core import Knowledge, Operator, Strategy`)
- `gaia/lang/compiler.py` (currently `from gaia.lang.core import Knowledge, Operator, Package, Strategy`)
- `gaia/lang/__init__.py` (currently `from gaia.lang.core import Knowledge, Package, Strategy, Operator`)
- `cli/commands/compile.py` (currently `from gaia.lang.core import Package as GaiaPackage, Knowledge`)

- [ ] **Step 6: Delete core.py**

```bash
rm gaia/lang/core.py
```

- [ ] **Step 7: Run tests**

```bash
pytest tests/gaia/lang/ -v
```

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(lang): split core.py into runtime/nodes.py + runtime/package.py"
```

---

### Task 3: Move DSL functions into dsl/ sub-package

**Files:**
- Create: `gaia/lang/dsl/__init__.py`
- Move: `gaia/lang/operators.py` → `gaia/lang/dsl/operators.py`
- Move: `gaia/lang/strategies.py` → `gaia/lang/dsl/strategies.py`
- Create: `gaia/lang/dsl/knowledge.py` — extract claim/setting/question from `__init__.py`
- Modify: `gaia/lang/__init__.py` — pure re-exports only

- [ ] **Step 1: Create dsl/ directory and move files**

```bash
mkdir -p gaia/lang/dsl
git mv gaia/lang/operators.py gaia/lang/dsl/operators.py
git mv gaia/lang/strategies.py gaia/lang/dsl/strategies.py
```

- [ ] **Step 2: Create dsl/knowledge.py** — extract claim(), setting(), question() from __init__.py

- [ ] **Step 3: Update imports inside dsl/ files** — change `from gaia.lang.core` to `from gaia.lang.runtime`

- [ ] **Step 4: Create dsl/__init__.py** — re-export all DSL functions

- [ ] **Step 5: Simplify lang/__init__.py** — pure re-exports from runtime and dsl

```python
# gaia/lang/__init__.py — pure re-exports
from gaia.lang.runtime import Knowledge, Strategy, Operator, Package
from gaia.lang.dsl import (
    claim, setting, question,
    contradiction, equivalence, complement, disjunction,
    noisy_and, infer, deduction, abduction, analogy, extrapolation,
)

__all__ = [
    "Knowledge", "Strategy", "Operator", "Package",
    "claim", "setting", "question",
    "contradiction", "equivalence", "complement", "disjunction",
    "noisy_and", "infer", "deduction", "abduction", "analogy", "extrapolation",
]
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/gaia/lang/ -v
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(lang): move DSL functions into dsl/ sub-package"
```

---

### Task 4: Move compiler into compiler/ sub-package

**Files:**
- Create: `gaia/lang/compiler/__init__.py`
- Move: `gaia/lang/compiler.py` → `gaia/lang/compiler/compile.py`
- Modify: tests and CLI that import `gaia.lang.compiler`

- [ ] **Step 1: Create compiler/ directory and move**

```bash
mkdir -p gaia/lang/compiler
git mv gaia/lang/compiler.py gaia/lang/compiler/compile.py
```

- [ ] **Step 2: Create compiler/__init__.py**

```python
from gaia.lang.compiler.compile import compile_package

__all__ = ["compile_package"]
```

- [ ] **Step 3: Update imports** — `from gaia.lang.compiler import compile_package` still works via __init__.py, so external imports don't change. Update internal imports in compile.py (`from gaia.lang.core` → `from gaia.lang.runtime`).

- [ ] **Step 4: Run tests**

```bash
pytest tests/gaia/lang/ -v
```

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(lang): move compiler into compiler/ sub-package"
```

---

## Chunk 3: Move CLI into gaia/lang/cli/

### Task 5: Move CLI into gaia/lang/cli/

**Files:**
- Create: `gaia/lang/cli/__init__.py`
- Create: `gaia/lang/cli/main.py` — new Typer app for gaia-lang commands
- Create: `gaia/lang/cli/commands/__init__.py`
- Move: compile command logic into `gaia/lang/cli/commands/compile.py`
- Modify: `cli/main.py` — register gaia.lang.cli commands (or redirect)
- Modify: `pyproject.toml` — update `[project.scripts]` entry

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p gaia/lang/cli/commands
```

- [ ] **Step 2: Create gaia/lang/cli/main.py** — Typer app with compile command

```python
"""Gaia Lang CLI — knowledge package authoring tools."""
import typer

app = typer.Typer(
    name="gaia",
    help="Gaia Lang — knowledge package authoring toolkit.",
    no_args_is_help=True,
)

from gaia.lang.cli.commands.compile import compile_command
app.command(name="compile")(compile_command)
```

- [ ] **Step 3: Move compile command** into `gaia/lang/cli/commands/compile.py`

Adapt from `cli/commands/compile.py`, update imports to use `gaia.lang.runtime` and `gaia.lang.compiler`.

- [ ] **Step 4: Update cli/main.py** — import and mount the lang CLI

```python
# In the existing cli/main.py, add:
from gaia.lang.cli.main import app as lang_app
# Register lang commands on the main app
```

Or alternatively, update `[project.scripts]` to point to the new entry:

```toml
[project.scripts]
gaia = "gaia.lang.cli.main:app"
```

- [ ] **Step 5: Update tests** — adjust imports in `tests/cli/test_compile.py`

- [ ] **Step 6: Run tests**

```bash
pytest tests/gaia/lang/ tests/cli/ -v
```

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(lang): move CLI into gaia/lang/cli/"
```

---

## Chunk 4: Final verification

### Task 6: Full test suite + lint + verify package structure

- [ ] **Step 1: Run ALL tests**

```bash
pytest -v
```

- [ ] **Step 2: Lint and format**

```bash
ruff check .
ruff format --check .
```

- [ ] **Step 3: Verify import paths work**

```python
# These should all work:
from gaia.ir import Knowledge, Strategy, Operator, LocalCanonicalGraph
from gaia.lang import claim, setting, question, contradiction, Package
from gaia.lang.compiler import compile_package
from gaia.lang.runtime import Knowledge as LangKnowledge
from gaia.bp.lowering import lower_to_factor_graph
```

- [ ] **Step 4: Verify CLI works**

```bash
python -m gaia.lang.cli.main compile --help
```

- [ ] **Step 5: Commit any fixes**

- [ ] **Step 6: Final commit**

```bash
git commit -m "refactor: complete gaia-lang package restructure

- gaia/gaia_ir/ → gaia/ir/ (cleaner import path)
- gaia/lang/ split into dsl/ + runtime/ + compiler/ + cli/
- CLI moved from top-level cli/ into gaia/lang/cli/
- All 30+ lang tests + existing IR/BP tests passing"
```

---

## Summary

| Task | What changes | Files affected |
|------|-------------|---------------|
| 1 | `gaia_ir` → `ir` rename | 18 files, 67 import occurrences |
| 2 | Split `core.py` → `runtime/` | 6 files |
| 3 | Move DSL functions → `dsl/` | 5 files |
| 4 | Move compiler → `compiler/` | 3 files |
| 5 | Move CLI → `gaia/lang/cli/` | 4 files |
| 6 | Full verification | all |
