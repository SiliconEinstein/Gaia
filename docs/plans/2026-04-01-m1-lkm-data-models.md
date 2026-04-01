# M1: LKM Data Models — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define LKM's internal Pydantic v2 storage models in `gaia/lkm/models/`, independent of upstream `gaia.gaia_ir.*`.

**Architecture:** LKM has its own model layer that represents the dual local/global FactorGraph storage format. These models are the contract for M2 (storage), M3 (lowering), and M5 (integrate). Upstream Gaia IR models are the *input* format; LKM models are the *storage* format. No Gaia IR validators are duplicated — LKM only adds constraints specific to its own layer (e.g., `source_class` priority, `gcn_id` format).

**Tech Stack:** Python 3.12+, Pydantic v2

**Spec:** `docs/specs/2026-03-31-m1-data-models.md`

**Upstream reference (read-only, do not import):**
- `gaia/gaia_ir/knowledge.py` — Parameter, LocalCanonicalRef, content_hash algorithm
- `gaia/gaia_ir/strategy.py` — Step, StrategyType
- `gaia/gaia_ir/binding.py` — CanonicalBinding, BindingDecision
- `gaia/gaia_ir/parameterization.py` — PriorRecord, StrategyParamRecord, Cromwell clamping

---

## File Structure

```
gaia/lkm/
├── __init__.py
└── models/
    ├── __init__.py              # Public exports for all models
    ├── _hash.py                 # compute_content_hash() + new_gcn_id() + new_gfac_id()
    ├── variable.py              # Parameter, LocalCanonicalRef, LocalVariableNode, GlobalVariableNode
    ├── factor.py                # Step, LocalFactorNode, GlobalFactorNode
    ├── binding.py               # CanonicalBinding
    ├── parameterization.py      # PriorRecord, FactorParamRecord, ParameterizationSource
    └── inference.py             # BeliefSnapshot

tests/gaia/lkm/
├── __init__.py
└── models/
    ├── __init__.py
    └── test_models.py           # All M1 unit tests in one file
```

**Why one test file:** M1 models are pure data classes with minimal logic. Splitting tests across 6 files would be overhead for ~10 test functions. The critical tests are content_hash determinism and Cromwell clamping — both are small.

---

## Chunk 1: Helper Types + Hash Utilities

### Task 1: Create package structure and hash utilities

**Files:**
- Create: `gaia/lkm/__init__.py`
- Create: `gaia/lkm/models/__init__.py`
- Create: `gaia/lkm/models/_hash.py`

- [ ] **Step 1: Create `gaia/lkm/__init__.py`**

```python
"""Gaia LKM — Large Knowledge Model server."""
```

- [ ] **Step 2: Create `gaia/lkm/models/_hash.py`**

This is the internal utility module. `compute_content_hash` must match the upstream algorithm in `gaia/gaia_ir/knowledge.py:_compute_content_hash` exactly (same output for same inputs), but is independently implemented (no import).

```python
"""Internal hash and ID generation utilities."""

from __future__ import annotations

import hashlib
import uuid


def compute_content_hash(type_: str, content: str, parameters: list[tuple[str, str]]) -> str:
    """SHA-256(type + content + sorted(parameters)), no package_id.

    Parameters are pre-sorted (name, type) tuples — caller is responsible
    for extracting from Parameter models.

    Matches upstream gaia.gaia_ir.knowledge._compute_content_hash algorithm.
    """
    sorted_params = sorted(parameters)
    payload = f"{type_}|{content}|{sorted_params}"
    return hashlib.sha256(payload.encode()).hexdigest()


def new_gcn_id() -> str:
    """Generate a new global canonical variable node ID. UUID-based, assigned once."""
    return f"gcn_{uuid.uuid4().hex[:16]}"


def new_gfac_id() -> str:
    """Generate a new global canonical factor node ID. UUID-based, assigned once."""
    return f"gfac_{uuid.uuid4().hex[:16]}"
```

**Design note:** `compute_content_hash` takes `list[tuple[str, str]]` instead of `list[Parameter]` to avoid circular imports. Callers convert: `[(p.name, p.type) for p in params]`.

- [ ] **Step 3: Verify hash function matches upstream**

Run: `python -c "from gaia.lkm.models._hash import compute_content_hash; print(compute_content_hash('claim', 'test content', [('x', 'int'), ('y', 'str')]))"`

Then compare with upstream:
```python
python -c "
from gaia.gaia_ir.knowledge import Parameter, _compute_content_hash
print(_compute_content_hash('claim', 'test content', [Parameter(name='x', type='int'), Parameter(name='y', type='str')]))
"
```

Both must produce the same hash string.

- [ ] **Step 4: Commit**

```bash
git add gaia/lkm/__init__.py gaia/lkm/models/__init__.py gaia/lkm/models/_hash.py
git commit -m "feat(lkm): add M1 hash utilities — compute_content_hash, new_gcn_id, new_gfac_id"
```

---

### Task 2: Variable models

**Files:**
- Create: `gaia/lkm/models/variable.py`

- [ ] **Step 1: Create `gaia/lkm/models/variable.py`**

```python
"""Variable node models — local and global layers."""

from __future__ import annotations

from pydantic import BaseModel

from gaia.lkm.models._hash import compute_content_hash


class Parameter(BaseModel):
    """Quantified variable in a universal claim."""

    name: str
    type: str


class LocalCanonicalRef(BaseModel):
    """Reference to a local variable node."""

    local_id: str       # QID format
    package_id: str
    version: str


class LocalVariableNode(BaseModel):
    """Local layer variable node — stores content.

    Corresponds to a Knowledge in Gaia IR, flattened for LKM storage.
    """

    id: str                                             # QID: {namespace}:{package_name}::{label}
    type: str                                           # "claim" | "setting" | "question"
    visibility: str                                     # "public" | "private"
    content: str
    content_hash: str                                   # SHA-256, excludes package_id
    parameters: list[Parameter] = []
    source_package: str
    metadata: dict | None = None

    def recompute_content_hash(self) -> str:
        """Recompute content_hash from current fields. For verification only."""
        return compute_content_hash(
            self.type, self.content,
            [(p.name, p.type) for p in self.parameters],
        )


class GlobalVariableNode(BaseModel):
    """Global layer variable node — structure only, no content.

    Content is retrieved via representative_lcn → local_variable_nodes[local_id].content.
    """

    id: str                                             # gcn_id: "gcn_{uuid4_hex[:16]}"
    type: str                                           # "claim" | "setting" | "question"
    visibility: str                                     # "public" | "private"
    content_hash: str                                   # denormalized from representative_lcn
    parameters: list[Parameter] = []
    representative_lcn: LocalCanonicalRef
    local_members: list[LocalCanonicalRef] = []
    metadata: dict | None = None
```

**Design decisions:**
- No `Literal` type annotations for `type`/`visibility` — validation is done upstream in Gaia IR. LKM models are storage containers, not validation gates.
- `recompute_content_hash()` is a helper for verification, not auto-computed on construction (unlike upstream Knowledge which auto-computes in `model_validator`). This avoids surprising side effects in a storage model.

- [ ] **Step 2: Quick smoke test**

Run: `python -c "
from gaia.lkm.models.variable import LocalVariableNode, Parameter
node = LocalVariableNode(id='reg:galileo::claim1', type='claim', visibility='public', content='test', content_hash='abc', parameters=[], source_package='galileo')
print(node.model_dump())
"`

- [ ] **Step 3: Commit**

```bash
git add gaia/lkm/models/variable.py
git commit -m "feat(lkm): add M1 LocalVariableNode + GlobalVariableNode models"
```

---

### Task 3: Factor models

**Files:**
- Create: `gaia/lkm/models/factor.py`

- [ ] **Step 1: Create `gaia/lkm/models/factor.py`**

```python
"""Factor node models — local and global layers.

Unifies upstream Strategy and Operator into a single factor concept,
distinguished by factor_type field.
"""

from __future__ import annotations

from pydantic import BaseModel


class Step(BaseModel):
    """A single reasoning step (local layer only)."""

    reasoning: str
    premises: list[str] | None = None
    conclusion: str | None = None


class LocalFactorNode(BaseModel):
    """Local layer factor node — stores steps for strategies.

    Unifies Strategy and Operator from Gaia IR.
    """

    id: str                                     # "lfac_{sha256[:16]}"
    factor_type: str                            # "strategy" | "operator"
    subtype: str                                # see spec subtype table
    premises: list[str]                         # premise variable IDs (QIDs)
    conclusion: str                             # conclusion variable ID (QID)
    background: list[str] | None = None         # context IDs (strategy only)
    steps: list[Step] | None = None             # reasoning steps (strategy only)
    source_package: str
    metadata: dict | None = None


class GlobalFactorNode(BaseModel):
    """Global layer factor node — structure only, no steps.

    Steps are retrieved via representative_lfn → local_factor_nodes[lfn_id].steps.
    """

    id: str                                     # "gfac_{sha256[:16]}"
    factor_type: str                            # "strategy" | "operator"
    subtype: str
    premises: list[str]                         # premise gcn_ids
    conclusion: str                             # conclusion gcn_id
    representative_lfn: str                     # local factor ID (lfac_ prefix)
    source_package: str
    metadata: dict | None = None
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/models/factor.py
git commit -m "feat(lkm): add M1 LocalFactorNode + GlobalFactorNode models"
```

---

## Chunk 2: Binding, Parameterization, Inference, Exports + Tests

### Task 4: Binding model

**Files:**
- Create: `gaia/lkm/models/binding.py`

- [ ] **Step 1: Create `gaia/lkm/models/binding.py`**

```python
"""CanonicalBinding — local-to-global node mapping."""

from __future__ import annotations

from pydantic import BaseModel


class CanonicalBinding(BaseModel):
    """Records how a local node was mapped to a global node.

    Immutable after write — new package versions append new records.
    Covers both variable (QID → gcn_id) and factor (lfac_ → gfac_id) bindings.
    """

    local_id: str               # variable QID or lfac_ ID
    global_id: str              # gcn_id or gfac_id
    binding_type: str           # "variable" | "factor"
    package_id: str
    version: str
    decision: str               # "match_existing" | "create_new" | "equivalent_candidate"
    reason: str
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/models/binding.py
git commit -m "feat(lkm): add M1 CanonicalBinding model"
```

---

### Task 5: Parameterization models

**Files:**
- Create: `gaia/lkm/models/parameterization.py`

- [ ] **Step 1: Create `gaia/lkm/models/parameterization.py`**

```python
"""Parameterization models — probability parameters and their sources."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

CROMWELL_EPS: float = 1e-3
"""Cromwell's rule epsilon — all probabilities clamped to [EPS, 1-EPS]."""


def cromwell_clamp(value: float) -> float:
    """Clamp probability to (ε, 1-ε) per Cromwell's rule."""
    return max(CROMWELL_EPS, min(1 - CROMWELL_EPS, value))


class PriorRecord(BaseModel):
    """Prior probability for a global claim variable.

    Only visibility=public, type=claim variables should have PriorRecords.
    This constraint is enforced at the storage/integration layer, not here,
    because PriorRecord doesn't know the variable's visibility.

    Values are Cromwell-clamped on construction.
    """

    variable_id: str        # gcn_id
    value: float            # ∈ (ε, 1-ε)
    source_id: str          # → ParameterizationSource.source_id
    created_at: datetime

    def model_post_init(self, __context: Any) -> None:
        object.__setattr__(self, "value", cromwell_clamp(self.value))


class FactorParamRecord(BaseModel):
    """Conditional probability parameters for a global strategy factor.

    Only factor_type=strategy, subtype ∈ {infer, noisy_and} factors need this.
    Enforced at storage/integration layer.

    All values are Cromwell-clamped on construction.
    """

    factor_id: str                          # gfac_id
    conditional_probabilities: list[float]  # Cromwell clamped
    source_id: str
    created_at: datetime

    def model_post_init(self, __context: Any) -> None:
        clamped = [cromwell_clamp(p) for p in self.conditional_probabilities]
        object.__setattr__(self, "conditional_probabilities", clamped)


class ParameterizationSource(BaseModel):
    """Metadata about the origin of parameterization records.

    source_class is LKM-specific (not in upstream Gaia IR contract).
    Priority: official > heuristic > provisional (irreversible).
    """

    source_id: str
    source_class: str       # "official" | "heuristic" | "provisional"
    model: str              # reviewer ID or LLM model name
    policy: str | None = None
    config: dict | None = None
    created_at: datetime
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/models/parameterization.py
git commit -m "feat(lkm): add M1 PriorRecord, FactorParamRecord, ParameterizationSource"
```

---

### Task 6: Inference model

**Files:**
- Create: `gaia/lkm/models/inference.py`

- [ ] **Step 1: Create `gaia/lkm/models/inference.py`**

```python
"""BeliefSnapshot — BP inference result."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class BeliefSnapshot(BaseModel):
    """Snapshot of a global BP run.

    beliefs contains only visibility=public, type=claim variables.
    Reproducibility: graph_hash + resolution_policy + prior_cutoff uniquely
    determine the BP run.
    """

    snapshot_id: str
    timestamp: datetime
    graph_hash: str                     # deterministic hash of graph structure
    resolution_policy: str              # "latest" | "source:<source_id>"
    prior_cutoff: datetime              # parameter timestamp cutoff
    beliefs: dict[str, float]           # gcn_id → belief value
    converged: bool
    iterations: int
    max_residual: float
```

- [ ] **Step 2: Commit**

```bash
git add gaia/lkm/models/inference.py
git commit -m "feat(lkm): add M1 BeliefSnapshot model"
```

---

### Task 7: Public exports

**Files:**
- Modify: `gaia/lkm/models/__init__.py`

- [ ] **Step 1: Write `gaia/lkm/models/__init__.py`**

```python
"""LKM data models — internal storage format.

These models are independent of upstream gaia.gaia_ir.* (which is the ingest
input format, not the storage format).
"""

from gaia.lkm.models._hash import compute_content_hash, new_gcn_id, new_gfac_id
from gaia.lkm.models.binding import CanonicalBinding
from gaia.lkm.models.factor import GlobalFactorNode, LocalFactorNode, Step
from gaia.lkm.models.inference import BeliefSnapshot
from gaia.lkm.models.parameterization import (
    CROMWELL_EPS,
    FactorParamRecord,
    ParameterizationSource,
    PriorRecord,
    cromwell_clamp,
)
from gaia.lkm.models.variable import (
    GlobalVariableNode,
    LocalCanonicalRef,
    LocalVariableNode,
    Parameter,
)

__all__ = [
    # hash utilities
    "compute_content_hash",
    "new_gcn_id",
    "new_gfac_id",
    # variable models
    "Parameter",
    "LocalCanonicalRef",
    "LocalVariableNode",
    "GlobalVariableNode",
    # factor models
    "Step",
    "LocalFactorNode",
    "GlobalFactorNode",
    # binding
    "CanonicalBinding",
    # parameterization
    "CROMWELL_EPS",
    "cromwell_clamp",
    "PriorRecord",
    "FactorParamRecord",
    "ParameterizationSource",
    # inference
    "BeliefSnapshot",
]
```

- [ ] **Step 2: Verify imports work**

Run: `python -c "from gaia.lkm.models import LocalVariableNode, GlobalVariableNode, LocalFactorNode, GlobalFactorNode, CanonicalBinding, PriorRecord, FactorParamRecord, ParameterizationSource, BeliefSnapshot, compute_content_hash, new_gcn_id; print('All imports OK')"`

- [ ] **Step 3: Commit**

```bash
git add gaia/lkm/models/__init__.py
git commit -m "feat(lkm): add M1 models public exports"
```

---

### Task 8: Unit tests for critical logic

**Files:**
- Create: `tests/gaia/lkm/__init__.py`
- Create: `tests/gaia/lkm/models/__init__.py`
- Create: `tests/gaia/lkm/models/test_models.py`

These tests cover only the **LKM-specific** logic that isn't validated upstream:
1. `content_hash` cross-package stability and parameter-order independence
2. `content_hash` matches upstream algorithm exactly
3. Cromwell clamping on PriorRecord and FactorParamRecord
4. `gcn_id` / `gfac_id` format

**Not tested here** (validated upstream or low-value):
- QID format — validated by Gaia IR, tested in M3 lowering E2E
- Visibility constraints on PriorRecord — enforced at storage layer (M2)
- Serialization roundtrips — Pydantic guarantees

- [ ] **Step 1: Create test init files**

`tests/gaia/lkm/__init__.py` — empty file
`tests/gaia/lkm/models/__init__.py` — empty file

- [ ] **Step 2: Create `tests/gaia/lkm/models/test_models.py`**

```python
"""M1 unit tests — LKM-specific model logic only.

Does NOT duplicate Gaia IR validation tests (QID format, content_hash
auto-compute, etc.) — those are upstream's responsibility.
"""

from datetime import datetime, timezone

from gaia.lkm.models import (
    CROMWELL_EPS,
    FactorParamRecord,
    PriorRecord,
    compute_content_hash,
    cromwell_clamp,
    new_gcn_id,
    new_gfac_id,
)


class TestContentHash:
    """content_hash is the foundation of cross-package dedup — must be rock solid."""

    def test_cross_package_stable(self):
        """Same content with different packages must produce identical hash."""
        # content_hash excludes package_id by design
        params = [("x", "int"), ("y", "str")]
        h1 = compute_content_hash("claim", "YBCO superconducts at 90K", params)
        h2 = compute_content_hash("claim", "YBCO superconducts at 90K", params)
        assert h1 == h2

    def test_parameter_order_independent(self):
        """Parameter order must not affect hash."""
        h1 = compute_content_hash("claim", "test", [("x", "int"), ("y", "str")])
        h2 = compute_content_hash("claim", "test", [("y", "str"), ("x", "int")])
        assert h1 == h2

    def test_type_matters(self):
        """Different types must produce different hashes."""
        h1 = compute_content_hash("claim", "test content", [])
        h2 = compute_content_hash("setting", "test content", [])
        assert h1 != h2

    def test_matches_upstream(self):
        """Must produce same hash as gaia.gaia_ir.knowledge._compute_content_hash."""
        from gaia.gaia_ir.knowledge import Parameter as IRParameter
        from gaia.gaia_ir.knowledge import _compute_content_hash as upstream_hash

        lkm_hash = compute_content_hash("claim", "test", [("a", "material"), ("b", "temp")])
        upstream = upstream_hash(
            "claim", "test",
            [IRParameter(name="a", type="material"), IRParameter(name="b", type="temp")],
        )
        assert lkm_hash == upstream


class TestCromwellClamping:
    """Cromwell's rule: no P=0 or P=1 — prevents degenerate potentials in BP."""

    def test_prior_record_clamps_zero(self):
        pr = PriorRecord(
            variable_id="gcn_abc", value=0.0,
            source_id="s1", created_at=datetime.now(timezone.utc),
        )
        assert pr.value == CROMWELL_EPS

    def test_prior_record_clamps_one(self):
        pr = PriorRecord(
            variable_id="gcn_abc", value=1.0,
            source_id="s1", created_at=datetime.now(timezone.utc),
        )
        assert pr.value == 1 - CROMWELL_EPS

    def test_prior_record_normal_value_unchanged(self):
        pr = PriorRecord(
            variable_id="gcn_abc", value=0.7,
            source_id="s1", created_at=datetime.now(timezone.utc),
        )
        assert pr.value == 0.7

    def test_factor_param_clamps_all_values(self):
        fp = FactorParamRecord(
            factor_id="gfac_abc",
            conditional_probabilities=[0.0, 1.0, 0.5],
            source_id="s1", created_at=datetime.now(timezone.utc),
        )
        assert fp.conditional_probabilities == [CROMWELL_EPS, 1 - CROMWELL_EPS, 0.5]

    def test_cromwell_clamp_function(self):
        assert cromwell_clamp(-0.5) == CROMWELL_EPS
        assert cromwell_clamp(1.5) == 1 - CROMWELL_EPS
        assert cromwell_clamp(0.5) == 0.5


class TestIdGeneration:
    """gcn_id and gfac_id must have correct format and be unique."""

    def test_gcn_id_format(self):
        gid = new_gcn_id()
        assert gid.startswith("gcn_")
        assert len(gid) == 20  # "gcn_" + 16 hex chars

    def test_gfac_id_format(self):
        fid = new_gfac_id()
        assert fid.startswith("gfac_")
        assert len(fid) == 21  # "gfac_" + 16 hex chars

    def test_ids_are_unique(self):
        ids = {new_gcn_id() for _ in range(100)}
        assert len(ids) == 100
```

- [ ] **Step 3: Run tests**

Run: `pytest tests/gaia/lkm/models/test_models.py -v`

Expected: All tests pass.

- [ ] **Step 4: Commit**

```bash
git add tests/gaia/lkm/__init__.py tests/gaia/lkm/models/__init__.py tests/gaia/lkm/models/test_models.py
git commit -m "test(lkm): add M1 unit tests — content_hash, Cromwell clamping, ID generation"
```

---

## Post-completion

After all tasks pass, run full verification:

```bash
# All M1 tests
pytest tests/gaia/lkm/models/ -v

# Lint
ruff check gaia/lkm/models/ tests/gaia/lkm/models/
ruff format --check gaia/lkm/models/ tests/gaia/lkm/models/

# Import smoke test
python -c "from gaia.lkm.models import *; print('All M1 models importable')"
```

Then proceed to M2 (Storage Layer).
