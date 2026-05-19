# Infer Given Switch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make v0.5 `infer` expose a clean claim-returning API while lowering `given` as a Bayesian switch variable.

**Architecture:** Keep `infer` as the user-facing heuristic probability verb. The public DSL returns the evidence/conclusion claim `E`; the reviewable infer warrant remains internal metadata on the generated action/warrant record. Lowering treats `given` claims as BP variables: no `given` keeps the current binary CPT, while one or more `given` claims activate a switch CPT with neutral baseline `0.5` when the gate is false.

**Tech Stack:** Python, Gaia Lang runtime actions, Gaia IR `Strategy`, Gaia BP `CONDITIONAL` factors, pytest, ruff.

---

### Task 1: Update Infer DSL API Semantics

**Files:**
- Modify: `gaia/lang/dsl/infer_verb.py`
- Modify: `gaia/lang/runtime/action.py`
- Test: `tests/gaia/lang/test_infer.py`

- [x] **Step 1: Write failing tests**

Add tests showing:

```python
def test_infer_returns_evidence_claim_and_keeps_internal_warrant():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        result = infer(e, hypothesis=h, p_e_given_h=0.8, rationale="H supports E.")

    action = pkg.actions[0]
    assert result is e
    assert action in e.supports
    assert action.helper is not None
    assert action.helper is not e
    assert action.warrants == [action.helper]
    assert action.p_e_given_not_h == 0.5


def test_infer_accepts_given_claims_as_gate_conditions():
    with CollectedPackage("v6_test") as pkg:
        h = Claim("H.")
        e = Claim("E.")
        g = Claim("G.")
        result = infer(e, hypothesis=h, given=g, p_e_given_h=0.8, rationale="If G, H supports E.")

    action = pkg.actions[0]
    assert result is e
    assert action.given == (g,)
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project . pytest tests/gaia/lang/test_infer.py -q
```

Expected: the new return-value/default/given tests fail against the old helper-returning API.

- [x] **Step 3: Implement minimal DSL/runtime changes**

Change `Infer` action to include:

```python
given: tuple[Claim, ...] = ()
```

Change `infer(...)` to:

```python
given: Claim | tuple[Claim, ...] | list[Claim] | None = (),
p_e_given_not_h: float | Claim | None = 0.5,
```

Normalize `given` to a tuple of Claims, store it on the action, include it in helper metadata, and return `evidence` instead of the helper claim.

- [x] **Step 4: Run tests**

Run:

```bash
uv run --project . pytest tests/gaia/lang/test_infer.py -q
```

Expected: all infer DSL tests pass after updating old expectations.

### Task 2: Compile Given Into Infer Strategy Premises

**Files:**
- Modify: `gaia/lang/compiler/compile.py`
- Test: `tests/gaia/lang/test_compiler_actions.py`
- Test: `tests/cli/test_compile_v6_actions.py`

- [x] **Step 1: Write failing compile tests**

Add a compiler test with one gate:

```python
gate = Claim("Gate.")
gate.label = "g"
infer(e, hypothesis=h, given=gate, p_e_given_h=0.8, rationale="Bayes.", label="bayes_update")
```

Assert:

```python
assert strategy.premises == ["github:v6_actions::h", "github:v6_actions::g"]
assert strategy.conditional_probabilities == [0.5, 0.5, 0.5, 0.8]
assert strategy.metadata["given"] == ["github:v6_actions::g"]
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
uv run --project . pytest tests/gaia/lang/test_compiler_actions.py::test_compile_infer_action_with_given_switch_cpt -q
```

Expected: test fails because `Infer` has no compiled `given` switch yet.

- [x] **Step 3: Implement compiler changes**

Register `action.given`, compile `premises=[hypothesis, *given]`, and build:

```python
if action.given:
    conditional_probabilities = [0.5] * (1 << (1 + len(action.given)))
    gate_mask = sum(1 << i for i in range(1, 1 + len(action.given)))
    # For one given and premise order [H, G], gate_mask is idx 2.
    conditional_probabilities[gate_mask] = p_e_given_not_h
    conditional_probabilities[gate_mask | 1] = p_e_given_h
else:
    conditional_probabilities = [p_e_given_not_h, p_e_given_h]
```

Use a helper if needed to compute active indices generically for multiple `given` claims.

- [x] **Step 4: Run compile tests**

Run:

```bash
uv run --project . pytest tests/gaia/lang/test_compiler_actions.py tests/cli/test_compile_v6_actions.py -q
```

Expected: compiler and CLI action tests pass with updated API expectations.

### Task 3: Verify BP Switch Behavior

**Files:**
- Test: `tests/test_lowering.py`
- Modify only if needed: `gaia/bp/lowering.py`

- [x] **Step 1: Add BP regression tests**

Add tests proving the compiled CPT shape has the intended BP behavior:

```python
def test_infer_given_switch_cpt_gates_relation_when_gate_false():
    h = "github:lowertest::h"
    g_id = "github:lowertest::g"
    e = "github:lowertest::e"
    graph = _lg(
        knowledges=[
            Knowledge(id=h, type="claim", content="H"),
            Knowledge(id=g_id, type="claim", content="G"),
            Knowledge(id=e, type="claim", content="E"),
        ],
        strategies=[
            Strategy(
                scope="local",
                type="infer",
                premises=[h, g_id],
                conclusion=e,
                conditional_probabilities=[0.5, 0.5, 0.1, 0.9],
            )
        ],
    )
    fg = lower_local_graph(graph, node_priors={h: 0.99, g_id: 0.01})
    beliefs, _ = exact_inference(fg)
    assert beliefs[e] == pytest.approx(0.5, abs=0.02)
```

Add a second test with `g_id: 0.99` showing `E` rises with `H`.

- [x] **Step 2: Run lowering tests to verify current behavior**

Run:

```bash
uv run --project . pytest tests/test_lowering.py -q
```

Expected: tests pass if compiler emits the right CPT; no lowering production change should be necessary.

### Task 4: Review Metadata And Docs

**Files:**
- Modify: `docs/superpowers/plans/2026-05-04-infer-given-switch.md`
- Modify docs only if tests reveal active user docs referencing helper return directly.

- [x] **Step 1: Search active docs/tests for helper-return assumptions**

Run:

```bash
rg -n "infer\\(|likelihood helper|p_e_given_not_h|helper_kind.*likelihood" docs tests gaia
```

Update only active docs/tests needed for the changed API. Do not rewrite archived docs in this PR.

- [x] **Step 2: Confirm helper claims remain non-prior inputs**

Run targeted `gaia check` or existing tests around warrants/holes if touched.

### Task 5: Final Verification

**Files:**
- No new files unless failures require small fixes.

- [x] **Step 1: Focused tests**

Run:

```bash
uv run --project . pytest tests/gaia/lang/test_infer.py tests/gaia/lang/test_compiler_actions.py tests/cli/test_compile_v6_actions.py tests/test_lowering.py -q
```

- [x] **Step 2: Lint and format checks**

Run:

```bash
uv run --project . ruff format --check .
uv run --project . ruff check .
```

- [ ] **Step 3: Full test suite**

Run:

```bash
uv run --project . pytest
```

Expected: full suite passes, with only existing known warnings.
