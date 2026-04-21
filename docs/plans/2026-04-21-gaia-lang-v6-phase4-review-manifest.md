# Gaia Lang v6 Implementation Plan — Phase 4: ReviewManifest

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ReviewManifest with Review records, auto-generated audit questions, multi-round review support, and pessimistic default (unreviewed Strategies don't participate in inference).

**Architecture:** ReviewManifest is a package-level artifact separate from the semantic graph. The compiler auto-generates Review entries for each Action/Strategy with `status="unreviewed"`. `gaia check --warrants` exports the manifest for review. BP lowering skips strategies whose latest Review status is not "accepted". Audit questions are templated from Action type with `[@...]` refs.

**Tech Stack:** Python 3.12+, Pydantic v2, pytest

**Spec:** `docs/specs/2026-04-21-gaia-lang-v6-design.md` §9; `docs/specs/2026-04-21-gaia-ir-v6-design.md` §3

**Depends on:** Phase 1 + Phase 2 + Phase 3

---

## File Structure

### New files

| File | Responsibility |
|---|---|
| `gaia/ir/review.py` | ReviewManifest, Review, ReviewStatus Pydantic models |
| `gaia/lang/review/manifest.py` | Manifest generation from compiled package (auto-generate Reviews with audit questions) |
| `gaia/lang/review/templates.py` | Audit question templates per Action type |
| `tests/gaia/ir/test_review.py` | Review model tests |
| `tests/gaia/lang/test_review_manifest.py` | Manifest generation tests |
| `tests/cli/test_check_warrants.py` | CLI `--warrants` tests |

### Modified files

| File | Changes |
|---|---|
| `gaia/ir/graphs.py` | `GaiaPackageArtifact` gains `review: ReviewManifest \| None` |
| `gaia/bp/lowering.py` | Skip strategies without accepted Review |
| `gaia/cli/commands/check.py` | Add `--warrants` and `--warrants --blind` flags |
| `gaia/cli/commands/infer.py` | Pass ReviewManifest to BP lowering |

---

## Chunk 1: ReviewManifest Models

### Task 1: Review and ReviewManifest Pydantic models

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/ir/test_review.py
from gaia.ir.review import Review, ReviewManifest, ReviewStatus


def test_review_status_enum():
    assert ReviewStatus.UNREVIEWED == "unreviewed"
    assert ReviewStatus.ACCEPTED == "accepted"
    assert ReviewStatus.REJECTED == "rejected"
    assert ReviewStatus.NEEDS_INPUTS == "needs_inputs"


def test_review_creation():
    r = Review(
        review_id="rev_001",
        action_label="planck_resolves",
        strategy_id="lcs_abc123",
        status=ReviewStatus.UNREVIEWED,
        audit_question="Do premises suffice to establish [@quantum_hyp]?",
        round=1,
    )
    assert r.status == "unreviewed"
    assert r.action_label == "planck_resolves"


def test_review_manifest():
    r = Review(review_id="rev_001", action_label="a", strategy_id="lcs_1", status="unreviewed", audit_question="?", round=1)
    m = ReviewManifest(reviews=[r])
    assert len(m.reviews) == 1


def test_review_manifest_latest_status():
    r1 = Review(review_id="rev_001", action_label="a", strategy_id="lcs_1", status="unreviewed", audit_question="?", round=1)
    r2 = Review(review_id="rev_002", action_label="a", strategy_id="lcs_1", status="accepted", audit_question="?", round=2)
    m = ReviewManifest(reviews=[r1, r2])
    assert m.latest_status("lcs_1") == "accepted"
```

- [ ] **Step 2: Implement**

```python
# gaia/ir/review.py
"""ReviewManifest — package-level review layer for Gaia IR v6."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ReviewStatus(StrEnum):
    UNREVIEWED = "unreviewed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NEEDS_INPUTS = "needs_inputs"


class Review(BaseModel):
    review_id: str
    action_label: str
    strategy_id: str
    status: ReviewStatus
    audit_question: str
    reviewer_notes: str | None = None
    timestamp: str | None = None
    round: int = 1


class ReviewManifest(BaseModel):
    reviews: list[Review] = []

    def latest_status(self, strategy_id: str) -> ReviewStatus | None:
        relevant = [r for r in self.reviews if r.strategy_id == strategy_id]
        if not relevant:
            return None
        return max(relevant, key=lambda r: r.round).status
```

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

---

## Chunk 2: Audit Question Templates

### Task 2: Auto-generate audit questions from Action type

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/lang/test_review_manifest.py

def test_audit_question_for_derive():
    question = generate_audit_question("derive", conclusion_label="quantum_hyp")
    assert "[@quantum_hyp]" in question
    assert "premises" in question.lower()


def test_audit_question_for_observe():
    question = generate_audit_question("observe", conclusion_label="uv_data")
    assert "[@uv_data]" in question
    assert "observation" in question.lower() or "reliable" in question.lower()


def test_audit_question_for_infer():
    question = generate_audit_question("infer", hypothesis_label="quantum_hyp", evidence_label="spectrum")
    assert "[@quantum_hyp]" in question
    assert "[@spectrum]" in question


def test_audit_question_for_equal():
    question = generate_audit_question("equal", a_label="pred", b_label="obs")
    assert "[@pred]" in question
    assert "[@obs]" in question
```

- [ ] **Step 2: Implement**

```python
# gaia/lang/review/templates.py

_TEMPLATES = {
    "derive": "Do the listed premises suffice to establish [@{conclusion}]?",
    "observe": "Is the observation of [@{conclusion}] reliable under the stated conditions?",
    "compute": "Is the computation of [@{conclusion}] correctly implemented?",
    "infer": "Is the statistical association between [@{hypothesis}] and [@{evidence}] valid at the stated probabilities?",
    "equal": "Are [@{a}] and [@{b}] truly equivalent?",
    "contradict": "Do [@{a}] and [@{b}] truly contradict?",
}


def generate_audit_question(action_type: str, **labels) -> str:
    template = _TEMPLATES.get(action_type, "Is this reasoning step valid?")
    return template.format_map(labels)
```

- [ ] **Step 3: Commit**

### Task 3: Manifest generation from compiled package

- [ ] **Step 1: Write test** — compile a package, generate ReviewManifest, verify one Review per Strategy
- [ ] **Step 2: Implement `generate_review_manifest()`** — walks compiled strategies, creates Review entries
- [ ] **Step 3: Commit**

---

## Chunk 3: BP Integration

### Task 4: BP lowering respects Review status

- [ ] **Step 1: Write failing test**

```python
# tests/gaia/bp/test_review_gating.py

def test_unreviewed_strategy_excluded_from_bp():
    """Unreviewed strategy should NOT contribute to inference."""
    # Build a simple graph: A → B via deduction
    # ReviewManifest has the strategy as "unreviewed"
    # Run BP → B's posterior should equal its prior (no update)


def test_accepted_strategy_included_in_bp():
    """Accepted strategy participates in inference."""
    # Same graph, but Review status = "accepted"
    # Run BP → B's posterior should be updated
```

- [ ] **Step 2: Modify lowering.py**

In `lower_local_graph()`, accept optional `ReviewManifest`. Before lowering each strategy, check `manifest.latest_status(strategy_id)`. Skip if not "accepted".

- [ ] **Step 3: Run — verify passes**
- [ ] **Step 4: Commit**

---

## Chunk 4: CLI Integration

### Task 5: `gaia check --warrants` command

- [ ] **Step 1: Write test**

```python
# tests/cli/test_check_warrants.py

def test_check_warrants_outputs_review_list(tmp_path):
    """gaia check --warrants lists all strategies with audit questions."""
    # Create package with derive + equal, compile
    # Run gaia check --warrants
    # Verify output contains audit questions


def test_check_warrants_blind(tmp_path):
    """gaia check --warrants --blind omits author priors."""
    pass
```

- [ ] **Step 2: Implement in check.py** — add `--warrants` flag, generate + display ReviewManifest
- [ ] **Step 3: Commit**

---

## Verification

1. `pytest tests/gaia/ir/test_review.py -v`
2. `pytest tests/gaia/lang/test_review_manifest.py -v`
3. `pytest tests/gaia/bp/test_review_gating.py -v`
4. `pytest tests/cli/test_check_warrants.py -v`
5. `pytest tests/ -x -q` (full regression)
6. `ruff check . && ruff format --check .`
