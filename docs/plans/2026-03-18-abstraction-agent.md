# Abstraction Agent Implementation Plan

## Context

Spec §3.2.2 defines an abstraction agent. The core operation is: given a batch of claims, find groups that share a common weaker conclusion, extract that conclusion (intersection, NOT union), and flag contradiction candidates.

**Lesson from propositional_logic_analysis repo**: The old prompts had too many classification categories (subsumption / partial overlap / contradiction / unrelated), leading to frequent classification errors and union-instead-of-intersection mistakes. The new approach simplifies to a single focused operation.

**Three-step pipeline** (adapted from old repo's join → verify → refine):
1. **Abstract** — find abstraction groups + extract common conclusion + flag contradiction pairs
2. **Verify** — check each child individually entails the abstraction (one-child test)
3. **Refine** — fix failed abstractions (rewrite / abandon)

## Pipeline Design

### Step 1: Abstract (`abstraction_agent.md`)

**Task**: Given N claims, output abstraction groups.

**Input format**:
```
## Claim gcn_abc123:
Newton's second law states that force equals mass times acceleration, F = ma

## Claim gcn_def456:
The net force on an object equals its mass multiplied by its acceleration

## Claim gcn_ghi789:
...
```

**Output format** (JSON):
```json
{
  "groups": [
    {
      "group_id": "G1",
      "member_ids": ["gcn_abc123", "gcn_def456"],
      "abstraction": "The net force acting on an object is equal to the product of its mass and acceleration",
      "reason": "Both claims state Newton's second law with different phrasing",
      "contradiction_pairs": []
    },
    {
      "group_id": "G2",
      "member_ids": ["gcn_xxx", "gcn_yyy", "gcn_zzz"],
      "abstraction": "...",
      "reason": "...",
      "contradiction_pairs": [["gcn_xxx", "gcn_yyy"]]
    }
  ]
}
```

**Core prompt guidance**:
- A claim NOT in any group is fine — don't force grouping
- The abstraction must be the **intersection** of member claims — the weakest proposition all members independently entail
- Abstraction strips quantitative specifics, keeps qualitative common claims
- **One-child test (built into prompt)**: for every assertion in the abstraction, ask "would this still be supported if this child were the ONLY one?" If not, remove that assertion
- Short and correct > long and wrong — a 1-sentence abstraction is perfectly fine
- Flag pairs within a group that might contradict each other (same subject, incompatible values/claims)

**Core principle: no vacuous abstractions.** If the common part is too generic to be informative (e.g., "a material has a property"), do NOT create the group. A forced, empty abstraction is worse than none. Only abstract when the shared content is a substantive scientific statement.

**Worked examples for prompt:**

Example 1 — Quantitative divergence (abstraction + contradiction):
- Claim A: "Model X has Tc = 0.5"
- Claim B: "Model X has Tc = 0.4"
- ✅ **Abstraction**: "Model X exhibits a critical temperature Tc"
- **Contradiction pair**: [A, B] if values differ beyond reasonable error margin
- ❌ WRONG (union): "Model X has Tc between 0.4 and 0.5"

Example 2 — Different methods, same finding (abstraction, no contradiction):
- Claim A: "X-ray diffraction shows material A has tetragonal phase at 300K"
- Claim B: "Neutron scattering confirms material A has tetragonal phase at 200K"
- ✅ **Abstraction**: "Material A has a tetragonal crystal phase"

Example 3 — Same subject, incompatible structure (abstraction + contradiction):
- Claim A: "MgB₂ has an isotropic superconducting gap"
- Claim B: "MgB₂ has an anisotropic superconducting gap"
- ✅ **Abstraction**: "MgB₂ has a superconducting gap"
- **Contradiction pair**: [A, B] — isotropic vs anisotropic

Example 4 — Same subject, mutually exclusive causes (abstraction + contradiction):
- Claim A: "High-Tc pairing mechanism is from spin fluctuations"
- Claim B: "High-Tc pairing mechanism is from phonon coupling"
- ✅ **Abstraction**: "High-Tc superconductors have an electron pairing mechanism"
- **Contradiction pair**: [A, B]

Example 5 — Union error trap:
- Claim A: "Protein A binds receptor B"
- Claim B: "Protein A activates pathway C"
- ❌ WRONG (union): "Protein A binds receptor B and activates pathway C"
- ✅ Correct: "Protein A has biological activity" — but this is TOO VACUOUS → **don't group**

Example 6 — No valid abstraction:
- Claim A: "Water boils at 100°C at 1 atm"
- Claim B: "Iron melts at 1538°C at 1 atm"
- ❌ WRONG: "Substances undergo phase transitions" — too vacuous
- ✅ Correct: **don't group** — no substantive shared content

### Step 2: Verify (`verify_abstraction.md`)

**Task**: For each abstraction, verify entailment.

**Input**: One abstraction + its member claims
**Output**: Per-member pass/fail + union_error flag

```json
{
  "passed": true,
  "checks": [
    {"member_id": "gcn_abc123", "entails": true, "reason": "..."},
    {"member_id": "gcn_def456", "entails": true, "reason": "..."}
  ],
  "union_error": false,
  "union_error_detail": ""
}
```

### Step 3: Refine (`refine_abstraction.md`)

**Task**: Fix failed abstractions.

**Input**: Abstraction + members + verification feedback
**Output**: rewrite / abandon

```json
{
  "action": "rewrite",
  "revised_abstraction": "...",
  "reasoning": "Removed claim X which was only supported by member A"
}
```

## Files to Create

### 1. `libs/curation/prompts/abstraction_agent.md`

Focused prompt for Step 1. Key sections:
- Role: extract common weaker conclusions from groups of claims
- The ONE operation: find groups → extract intersection → flag contradictions
- Union vs. intersection guidance with worked examples (adapted from join_symmetric.md but simplified for general knowledge, not physics-specific)
- One-child test as mandatory self-check
- Output format: JSON

### 2. `libs/curation/prompts/verify_abstraction.md`

Adapted from verify_join.md but simplified:
- Only checks entailment (does each member entail the abstraction?)
- Flags union errors
- No tightness/substantiveness scores (simplify)

### 3. `libs/curation/prompts/refine_abstraction.md`

Adapted from join_refine.md:
- Given failed verification feedback, rewrite or abandon
- Focus on removing union-error claims

### 4. `libs/curation/abstraction.py`

Main module implementing the three-step pipeline:

```python
class AbstractionAgent:
    def __init__(self, model: str | None = "gpt-5-mini")

    # Step 1: Abstract
    async def _abstract_cluster(self, cluster: ClusterGroup, nodes: dict) -> ClusterAbstractionResult

    # Step 2: Verify
    async def _verify_abstraction(self, group: AbstractionGroup, nodes: dict) -> VerificationResult

    # Step 3: Refine
    async def _refine_abstraction(self, group: AbstractionGroup, verification: VerificationResult, nodes: dict) -> RefinedAbstraction

    # Full pipeline
    async def run(self, clusters: list[ClusterGroup], nodes: dict, max_workers: int = 10) -> AbstractionResult
```

Pipeline per cluster:
1. Call LLM with Step 1 prompt → get abstraction groups
2. For each group, call LLM with Step 2 prompt → verify
3. For failed groups, call LLM with Step 3 prompt → refine or abandon
4. For passed groups, call `create_abstraction()` → produce nodes + factors

All steps use `asyncio.Semaphore` for concurrency control (pattern from old repo).

### 5. `tests/libs/curation/test_abstraction.py`

Tests:
- Parse valid/malformed JSON from LLM
- One-child test catches union error in verify step
- Refine rewrites or abandons correctly
- End-to-end with mocked litellm: cluster → groups → nodes + factors
- Contradiction pairs are correctly extracted
- Clusters with <2 nodes are skipped

## Files to Modify

### 6. `libs/curation/models.py`

Add:
```python
class AbstractionGroup(BaseModel):
    group_id: str
    abstraction_content: str       # The common weaker conclusion
    member_node_ids: list[str]     # Claims being abstracted
    reason: str
    contradiction_pairs: list[tuple[str, str]] = []
    confidence: float = 0.0

class VerificationResult(BaseModel):
    group_id: str
    passed: bool
    checks: list[dict] = []        # Per-member entailment check
    union_error: bool = False

class AbstractionResult(BaseModel):
    new_nodes: list[GlobalCanonicalNode] = []
    new_factors: list[FactorNode] = []
    contradiction_candidates: list[ConflictCandidate] = []
    suggestions: list[CurationSuggestion] = []
```

Add `"create_abstraction"` to `CurationSuggestion.operation` Literal.

### 7. `libs/curation/operations.py`

Add `create_abstraction()`:
- Creates `GlobalCanonicalNode(knowledge_type="claim", kind="schema")` with deterministic ID
- Creates `FactorNode(type="instantiation")` per member: `premises=[schema_id]`, `conclusion=member_id`
- `package_id="__curation__"`

### 8. `libs/curation/scheduler.py`

Insert between classify (step 3) and conflict detection (step 4):
- Add `skip_abstraction: bool = False` and `abstraction_model: str | None` params
- New schema nodes added to `node_map`, new factors to `mutable_factors`
- Contradiction candidates fed to conflict detection step

### 9. `libs/curation/reviewer.py`

Add `create_abstraction` to `_build_user_message()` and `_review_rules()`.

## Critical Files Reference

| Purpose | File |
|---------|------|
| Old join prompt (adapt from) | `/Users/dp/Projects/propositional_logic_analysis/clustering/prompts/join_symmetric.md` |
| Old verify prompt (adapt from) | `/Users/dp/Projects/propositional_logic_analysis/clustering/prompts/verify_join.md` |
| Old refine prompt (adapt from) | `/Users/dp/Projects/propositional_logic_analysis/clustering/prompts/join_refine.md` |
| Old join impl (pattern) | `/Users/dp/Projects/propositional_logic_analysis/clustering/src/join_operation.py` |
| Old verify impl (pattern) | `/Users/dp/Projects/propositional_logic_analysis/clustering/src/verify_join_operation.py` |
| Old refine impl (pattern) | `/Users/dp/Projects/propositional_logic_analysis/clustering/src/join_refine_operation.py` |
| Gaia curation models | `libs/curation/models.py` |
| Gaia curation operations | `libs/curation/operations.py` |
| Gaia curation scheduler | `libs/curation/scheduler.py` |
| Gaia global graph models | `libs/global_graph/models.py` |
| Gaia test fixtures | `tests/libs/curation/conftest.py` |

## Verification

```bash
pytest tests/libs/curation/test_abstraction.py -v
pytest tests/libs/curation/ -v
ruff check libs/curation/ tests/libs/curation/
ruff format --check libs/curation/ tests/libs/curation/
```
