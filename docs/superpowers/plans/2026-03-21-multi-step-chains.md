# Multi-Step Chains from XML Reasoning Steps — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Populate Chain objects with multi-step reasoning text from XML extraction, instead of empty single-step wrappers.

**Architecture:** `paper_to_typst.py` saves a `reasoning_steps.json` sidecar alongside each Typst package (mapping conclusion names to their step-by-step reasoning). `storage_converter.py` reads this sidecar and generates multi-step `ChainStep` objects with populated `reasoning` text. Graceful fallback: if no sidecar exists, behavior is unchanged (single-step, empty reasoning).

**Tech Stack:** Python, JSON sidecar files, existing Pydantic models (Chain, ChainStep)

**Issue:** #175

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `scripts/paper_to_typst.py` | Modify (~L603) | Save `reasoning_steps.json` sidecar after priors.json |
| `libs/graph_ir/storage_converter.py` | Modify (~L219-263) | Accept optional reasoning_steps, generate multi-step chains |
| `scripts/pipeline/persist_to_db.py` | Modify | Load reasoning_steps.json and pass to converter |
| `tests/libs/graph_ir/test_storage_converter.py` | Modify | Add multi-step chain tests |
| `tests/scripts/test_paper_to_typst.py` | New test | Test reasoning_steps.json generation |

---

## Task 1: Save reasoning_steps.json in paper_to_typst.py

**Files:**
- Modify: `scripts/paper_to_typst.py:603` (after priors.json write)
- Test: `tests/scripts/test_paper_to_typst.py` (new test class)

The sidecar format maps conclusion knowledge names to their ordered reasoning steps:

```json
{
  "conclusion_name_1": [
    {"step_index": 0, "reasoning": "First step text..."},
    {"step_index": 1, "reasoning": "Second step text..."}
  ],
  "conclusion_name_2": [...]
}
```

- [ ] **Step 1: Write failing test for reasoning_steps.json generation**

Add to `tests/scripts/test_paper_to_typst.py` (this file tests `paper_to_yaml.py` parsing functions and `paper_to_typst.py` generation):

```python
class TestReasoningStepsJson:
    """Test reasoning_steps.json sidecar generation."""

    def test_build_reasoning_steps(self):
        from scripts.paper_to_typst import build_reasoning_steps

        step2_data = [
            {
                "conclusion_id": "1",
                "conclusion_title": "Result A",
                "conclusion_content": "We found A.",
                "steps": [
                    {"id": "1", "text": "Starting from X.", "citations": [], "figures": []},
                    {"id": "2", "text": "Therefore A.", "citations": ["[3]"], "figures": []},
                ],
            },
        ]
        conclusion_names = {"1": "result_a"}  # conclusion_id → knowledge_name

        result = build_reasoning_steps(step2_data, conclusion_names)

        assert "result_a" in result
        assert len(result["result_a"]) == 2
        assert result["result_a"][0]["step_index"] == 0
        assert result["result_a"][0]["reasoning"] == "Starting from X."
        assert result["result_a"][1]["step_index"] == 1
        assert result["result_a"][1]["reasoning"] == "Therefore A."

    def test_build_reasoning_steps_empty(self):
        from scripts.paper_to_typst import build_reasoning_steps

        result = build_reasoning_steps([], {})
        assert result == {}
```

- [ ] **Step 2: Run test — verify it fails**

Run: `cd /Users/dp/Projects/Gaia/.worktrees/multi-step-chains && pytest tests/scripts/test_paper_to_typst.py::TestReasoningStepsJson -v`
Expected: `ImportError: cannot import name 'build_reasoning_steps'`

- [ ] **Step 3: Implement build_reasoning_steps function**

In `scripts/paper_to_typst.py`, add near the other helper functions:

```python
def build_reasoning_steps(
    step2_data: list[dict],
    conclusion_names: dict[str, str],
) -> dict[str, list[dict]]:
    """Build reasoning_steps map from step2 XML extraction.

    Args:
        step2_data: Parsed step2 chains, each with conclusion_id and steps[].
        conclusion_names: Map conclusion_id → knowledge_name (slugified).

    Returns:
        Dict mapping knowledge_name → list of {step_index, reasoning}.
    """
    result: dict[str, list[dict]] = {}
    for chain in step2_data:
        conc_id = chain.get("conclusion_id", "")
        conc_name = conclusion_names.get(conc_id)
        if not conc_name:
            continue
        steps = []
        for i, step in enumerate(chain.get("steps", [])):
            text = step.get("text", "").strip()
            if text:
                steps.append({"step_index": i, "reasoning": text})
        if steps:
            result[conc_name] = steps
    return result
```

- [ ] **Step 4: Run test — verify it passes**

Run: `pytest tests/scripts/test_paper_to_typst.py::TestReasoningStepsJson -v`

- [ ] **Step 5: Wire sidecar write into process_paper**

In `scripts/paper_to_typst.py`, after the `priors.json` write (~L603), add:

```python
    # Save reasoning_steps.json — multi-step reasoning from LLM extraction (step2)
    # Used by storage_converter to populate Chain.steps with reasoning text
    conclusion_names: dict[str, str] = {}
    for conc in step1_data["conclusions"]:
        conclusion_names[conc["id"]] = _truncate_name(_slugify(conc["title"]))
    reasoning_steps = build_reasoning_steps(step2_data, conclusion_names)
    if reasoning_steps:
        (pkg_dir / "reasoning_steps.json").write_text(
            json.dumps(reasoning_steps, indent=2, ensure_ascii=False)
        )
```

- [ ] **Step 6: Commit**

```bash
git add scripts/paper_to_typst.py tests/scripts/test_paper_to_typst.py
git commit -m "feat: save reasoning_steps.json sidecar in paper_to_typst"
```

---

## Task 2: Multi-step chain generation in storage_converter.py

**Files:**
- Modify: `libs/graph_ir/storage_converter.py:91-263`
- Test: `tests/libs/graph_ir/test_storage_converter.py`

- [ ] **Step 1: Write failing test for multi-step chain generation**

Add to `tests/libs/graph_ir/test_storage_converter.py`:

```python
class TestMultiStepChains:
    """Test multi-step chain generation from reasoning_steps."""

    def test_chain_has_multiple_steps_when_reasoning_provided(self, basic_result):
        """When reasoning_steps is provided, chains should have multi-step reasoning."""
        # basic_result is the fixture from existing tests
        lcg = basic_result.local_graph
        params = basic_result.params

        # Find a reasoning factor to build reasoning_steps for
        reasoning_factor = next(
            (f for f in lcg.factor_nodes if f.type in ("infer", "reasoning")), None
        )
        assert reasoning_factor is not None
        conc_name = reasoning_factor.source_ref.knowledge_name

        reasoning_steps = {
            conc_name: [
                {"step_index": 0, "reasoning": "First we observe X."},
                {"step_index": 1, "reasoning": "From X we derive Y."},
                {"step_index": 2, "reasoning": "Therefore Z follows."},
            ]
        }

        result = convert_graph_ir_to_storage(lcg, params, reasoning_steps=reasoning_steps)

        # Find the chain for this conclusion
        matching = [c for c in result.chains if conc_name in c.chain_id]
        assert len(matching) == 1
        chain = matching[0]
        assert len(chain.steps) == 3
        assert chain.steps[0].reasoning == "First we observe X."
        assert chain.steps[1].reasoning == "From X we derive Y."
        assert chain.steps[2].reasoning == "Therefore Z follows."
        # All steps share the same conclusion
        assert all(s.conclusion == chain.steps[0].conclusion for s in chain.steps)

    def test_chain_falls_back_to_single_step(self, basic_result):
        """Without reasoning_steps, chains remain single-step with empty reasoning."""
        result = convert_graph_ir_to_storage(basic_result.local_graph, basic_result.params)
        for chain in result.chains:
            assert len(chain.steps) == 1
            assert chain.steps[0].reasoning == ""
```

- [ ] **Step 2: Run test — verify it fails**

Run: `pytest tests/libs/graph_ir/test_storage_converter.py::TestMultiStepChains -v`
Expected: `TypeError: unexpected keyword argument 'reasoning_steps'`

- [ ] **Step 3: Add reasoning_steps parameter to convert_graph_ir_to_storage**

In `libs/graph_ir/storage_converter.py`, modify the function signature:

```python
def convert_graph_ir_to_storage(
    lcg: LocalCanonicalGraph,
    params: LocalParameterization,
    beliefs: dict[str, float] | None = None,
    bp_run_id: str = "local_bp",
    reasoning_steps: dict[str, list[dict]] | None = None,  # NEW
) -> GraphIRIngestData:
```

- [ ] **Step 4: Replace single-step chain generation with multi-step logic**

Replace the chain building block (~L219-263) with:

```python
    # -- Build chains from reasoning factors --
    chains: list[storage.Chain] = []
    module_chain_ids: dict[str, list[str]] = {m.module_id: [] for m in modules}
    _FACTOR_TO_CHAIN_TYPE: dict[str, str] = {
        "reasoning": "deduction",
        "infer": "deduction",
        "abstraction": "abstraction",
        "contradiction": "contradiction",
        "equivalence": "contradiction",
    }
    for f in lcg.factor_nodes:
        chain_type = _FACTOR_TO_CHAIN_TYPE.get(f.type, "deduction")

        premises_kid = [lcn_to_kid[p] for p in f.premises if p in lcn_to_kid]
        conclusion_kid = lcn_to_kid.get(f.conclusion) if f.conclusion else None
        if not premises_kid or conclusion_kid is None:
            continue

        mod_name = f.source_ref.module if f.source_ref else "unknown"
        module_id = f"{package_id}.{mod_name}"
        chain_id = f"{package_id}.{mod_name}.{f.factor_id}"

        premise_refs = [
            storage.KnowledgeRef(knowledge_id=kid, version=1) for kid in premises_kid
        ]
        conclusion_ref = storage.KnowledgeRef(knowledge_id=conclusion_kid, version=1)

        # Check for multi-step reasoning from sidecar
        conc_name = f.source_ref.knowledge_name if f.source_ref else None
        steps_data = (reasoning_steps or {}).get(conc_name, []) if conc_name else []

        if steps_data:
            # Multi-step chain: each step has the same premises/conclusion but
            # carries its own reasoning text
            steps = [
                storage.ChainStep(
                    step_index=s["step_index"],
                    premises=premise_refs if s["step_index"] == 0 else [],
                    reasoning=s["reasoning"],
                    conclusion=conclusion_ref,
                )
                for s in steps_data
            ]
        else:
            # Fallback: single-step chain (no reasoning text available)
            steps = [
                storage.ChainStep(
                    step_index=0,
                    premises=premise_refs,
                    reasoning="",
                    conclusion=conclusion_ref,
                )
            ]

        chains.append(
            storage.Chain(
                chain_id=chain_id,
                module_id=module_id,
                package_id=package_id,
                package_version=package_version,
                type=chain_type,
                steps=steps,
            )
        )
        if module_id in module_chain_ids:
            module_chain_ids[module_id].append(chain_id)
```

- [ ] **Step 5: Run tests — verify all pass**

Run: `pytest tests/libs/graph_ir/test_storage_converter.py -v`

- [ ] **Step 6: Commit**

```bash
git add libs/graph_ir/storage_converter.py tests/libs/graph_ir/test_storage_converter.py
git commit -m "feat: support multi-step chains in storage_converter"
```

---

## Task 3: Wire reasoning_steps.json in persist_to_db.py

**Files:**
- Modify: `scripts/pipeline/persist_to_db.py` (load reasoning_steps.json, pass to converter)

- [ ] **Step 1: Read persist_to_db.py to find where convert_graph_ir_to_storage is called**

- [ ] **Step 2: Add reasoning_steps.json loading**

Near where `local_parameterization.json` is loaded, add:

```python
    reasoning_steps_path = pkg_dir / "graph_ir" / "reasoning_steps.json"
    reasoning_steps = (
        json.loads(reasoning_steps_path.read_text()) if reasoning_steps_path.exists() else None
    )
```

And pass it to the converter call:

```python
    ingest_data = convert_graph_ir_to_storage(
        lcg, params, beliefs=beliefs, bp_run_id=bp_run_id,
        reasoning_steps=reasoning_steps,
    )
```

- [ ] **Step 3: Also copy reasoning_steps.json to graph_ir/ during build**

In `scripts/paper_to_typst.py`, the sidecar is written to the package root. But `build_graph_ir.py` outputs to `graph_ir/`. The `persist_to_db.py` reads from `graph_ir/`. So we need to either:
- (a) Have `build_graph_ir.py` copy reasoning_steps.json into `graph_ir/`, or
- (b) Have `persist_to_db.py` look in the package root

Option (a) follows the established priors.json pattern — `build_graph_ir.py` already reads priors.json from the package root. Add a copy step:

In `scripts/pipeline/build_graph_ir.py`, after writing graph_ir outputs, add:

```python
    # Copy reasoning_steps.json to graph_ir/ for downstream consumers
    reasoning_steps_path = pkg_dir / "reasoning_steps.json"
    if reasoning_steps_path.exists():
        import shutil
        shutil.copy2(reasoning_steps_path, graph_dir / "reasoning_steps.json")
```

- [ ] **Step 4: Run existing tests to verify no regressions**

Run: `pytest tests/ -q`

- [ ] **Step 5: Commit**

```bash
git add scripts/pipeline/persist_to_db.py scripts/pipeline/build_graph_ir.py
git commit -m "feat: load reasoning_steps.json in persist_to_db pipeline"
```

---

## Task 4: Add fixture and integration test

**Files:**
- Create: `tests/fixtures/gaia_language_packages/galileo_falling_bodies_typst/reasoning_steps.json`
- Modify: `tests/libs/graph_ir/test_storage_converter.py`

- [ ] **Step 1: Create a reasoning_steps.json fixture**

Based on the galileo_falling_bodies_typst package, create a fixture with sample reasoning for one of its conclusions.

- [ ] **Step 2: Write integration test**

Test that the full flow (load graph IR + reasoning_steps → convert → verify multi-step chains) works end-to-end.

- [ ] **Step 3: Run all tests**

Run: `pytest tests/ -q`

- [ ] **Step 4: Lint and commit**

```bash
ruff check . && ruff format .
git add -A && git commit -m "test: add fixture and integration test for multi-step chains"
```
