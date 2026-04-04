# Design: Python Module = Gaia Module + Narrative Order

**Status:** Target design
**Date:** 2026-04-04

## Goal

Reuse Python's module system as the Gaia module system. Each `.py` file in a package is a module (maps to a paper section). Knowledge declaration order within a module is the narrative order. Package-level `__init__.py` import order is the module narrative. `__all__` marks exported conclusions.

## Motivation

The current system compiles all knowledge into a flat, unordered IR. README generation must "guess" narrative order via topological sort. But paper formalizations have a human-authored narrative (section order), and this information is already implicit in the Python source — just not captured.

## Design

### Three layers of change

#### 1. Runtime layer (`gaia/lang/runtime/`)

**Knowledge registration** captures source module and declaration index:

```python
# nodes.py
class Knowledge:
    ...
    _source_module: str | None = None     # relative module name, e.g. "s3_downfolding"
    _declaration_index: int | None = None # position within that module (0, 1, 2, ...)
```

**CollectedPackage** tracks per-module counters and module order:

```python
# package.py
class CollectedPackage:
    ...
    _module_counters: dict[str, int]     # module_name → next index
    _module_order: list[str]             # modules in first-seen order

    def _register_knowledge(self, k: Knowledge):
        self.knowledge.append(k)
        module = k._source_module
        if module is not None:
            if module not in self._module_counters:
                self._module_order.append(module)
                self._module_counters[module] = 0
            k._declaration_index = self._module_counters[module]
            self._module_counters[module] += 1
```

**Source module extraction** — `_caller_module_name()` already walks the call stack and extracts the module name. Currently the result is discarded after finding the package. Change: store it on the Knowledge as `_source_module`, converted to a relative name (strip the package prefix).

```python
# In Knowledge.__post_init__:
module_name = _caller_module_name()  # e.g. "superconductivity_electron_liquids.s3_downfolding"
# Strip package prefix → "s3_downfolding"
# For __init__.py → None (root module, no separate name)
```

For single-file packages (everything in `__init__.py`), `_source_module` is `None` and the package acts as one implicit module. Declaration order within `__init__.py` is the narrative.

#### 2. IR layer (`gaia/ir/`)

**Knowledge** gets two new optional fields:

```python
# gaia/ir/knowledge.py
class Knowledge(BaseModel):
    ...
    module: str | None = None            # source module relative name
    declaration_index: int | None = None # order within that module
    exported: bool = False               # True if in package __all__
```

**LocalCanonicalGraph** gets module ordering:

```python
# gaia/ir/graphs.py
class LocalCanonicalGraph(BaseModel):
    ...
    module_order: list[str] | None = None  # ["s1_introduction", "s2_model", ...]
```

All new fields are optional — old IR files remain valid.

#### 3. Compiler layer (`gaia/lang/compiler/compile.py`)

During compilation:

1. Read `_source_module` and `_declaration_index` from each runtime Knowledge → write to IR `module` and `declaration_index`
2. Read `_module_order` from CollectedPackage → write to IR `module_order`
3. Read the user package's `__all__` → set `exported = True` on matching Knowledge nodes

**`__all__` resolution:** The compiler already loads the user's Python module. After import, read `__all__` from the module's namespace. Match labels against `__all__` entries to set `exported`.

#### 4. README generation (`gaia/cli/commands/_readme.py`)

Update `_narrative_order()`:

```python
def _narrative_order(ir: dict) -> list[dict]:
    module_order = ir.get("module_order")
    if module_order is not None:
        # Use declared module + declaration order
        module_rank = {m: i for i, m in enumerate(module_order)}
        def sort_key(k):
            mod = k.get("module")
            idx = k.get("declaration_index", 0)
            mod_rank = module_rank.get(mod, 999)
            return (mod_rank, idx)
        nodes = [k for k in ir["knowledges"] if not _is_helper(k.get("label", ""))]
        return sorted(nodes, key=sort_key)
    else:
        # Fallback: topological sort (current behavior)
        return _topo_narrative_order(ir)
```

README sections grouped by module:

```markdown
## Knowledge Nodes

### Section I: Introduction
#### bcs_framework
...
#### adiabatic_approx
...

### Section III: Downfolding the BSE
#### pair_propagator_decomposition
...
```

Module headings use the module's docstring if available, otherwise the module name.

Exported conclusions get a visual marker:

```markdown
#### tc_improvement_over_phenomenological ★
```

## Example: multi-file electron liquid package

```
superconductivity_electron_liquids/
├── __init__.py
│     from .s1_introduction import *
│     from .s2_model import *
│     from .s3_downfolding import *
│     from .s4_pseudopotential import *
│     from .s5_eph_coupling import *
│     from .s6_superconductors import *
│     from .reasoning import *
│
├── s1_introduction.py      → bcs_framework, migdal_eliashberg, adiabatic_approx, main_question
├── s2_model.py             → electron_phonon_action, bse_kernel_decomposition, precursory_cooper_flow
├── s3_downfolding.py       → pair_propagator_decomposition, cross_term_suppressed, downfolded_bse, ...
├── s4_pseudopotential.py   → ueg_vertex_challenge, homotopic_expansion, vdiagmc_method, mu_vdiagmc_values
├── s5_eph_coupling.py      → individual_corrections_large, corrections_cancel, dfpt_reliable, ...
├── s6_superconductors.py   → ab_initio_workflow, tc_al_predicted, tc_li_predicted, ...
└── reasoning.py            → derive_downfolded_bse, derive_pcf, derive_mu_values, ...
```

`__init__.py`:
```python
from .s1_introduction import *
from .s2_model import *
from .s3_downfolding import *
from .s4_pseudopotential import *
from .s5_eph_coupling import *
from .s6_superconductors import *
from .reasoning import *

__all__ = [
    "ab_initio_workflow",
    "tc_improvement_over_phenomenological",
]
```

## Backward compatibility

- Single-file packages (everything in `__init__.py`): `module = None`, `module_order = None`. README falls back to topological sort. No change in behavior.
- `exported` defaults to `False`. Old packages without `__all__` work unchanged.
- `declaration_index` is `None` for old IR — README fallback handles this.
- `ir_hash` will change for recompiled packages (new fields in canonical JSON) — this is expected.

## Not in scope

- Module-level docstrings as section descriptions (can add later)
- Enforcing one-module-per-section (convention, not constraint)
- Cross-package module references
