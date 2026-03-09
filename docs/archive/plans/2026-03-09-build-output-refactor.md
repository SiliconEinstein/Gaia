# Build Output Refactor + Fixture Fix + Review Fingerprint

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix derived claims content, refactor build output to per-module Markdown for LLM review, add source fingerprint to review sidecar

**Architecture:** Fill all claim content in fixture; rewrite `save_build()` to emit per-module `.md` files; rewrite `review` to read Markdown and slice by `##` sections; add content hash to review sidecar and check on merge

**Tech Stack:** Python, hashlib, Markdown (plain text generation)

**Ref:** GitHub issue #64

---

## Task 1: Fix fixture — fill derived claims content

**Files:**
- Modify: `tests/fixtures/dsl_packages/galileo_falling_bodies/reasoning.yaml`

**What changes:**

Fill `content` for all 8 empty derived claims:

```yaml
- type: claim
  name: tied_pair_slower_than_heavy
  content: >
    复合体 HL 因轻球拖拽，下落速度应慢于单独的重球 H。
  prior: 0.5

- type: claim
  name: tied_pair_faster_than_heavy
  content: >
    复合体 HL 总重量大于单独的重球 H，下落速度应快于 H。
  prior: 0.5

- type: claim
  name: tied_balls_contradiction
  content: >
    同一定律对同一绑球系统同时预测"更慢"和"更快"，自相矛盾。
  prior: 0.6

- type: claim
  name: aristotle_contradicted
  content: >
    亚里士多德"重者下落更快"的定律因绑球矛盾而不能成立。
  prior: 0.5

- type: claim
  name: medium_difference_shrinks
  content: >
    介质越稀薄，轻重物体的下落速度差异越小。
  prior: 0.6

- type: claim
  name: air_resistance_is_confound
  content: >
    日常观察到的速度差异来自空气阻力，而非重量本身。
  prior: 0.5

- type: claim
  name: inclined_plane_supports_equal_fall
  content: >
    斜面实验支持"重量不是决定落体速度的首要因素"。
  prior: 0.55

- type: claim
  name: vacuum_prediction
  content: >
    在真空中，不同重量的物体应以相同速率下落。
  prior: 0.5
```

**Step 1:** Edit `reasoning.yaml`, replace all 8 `content: ""` claims with the content above.

**Step 2:** Run existing tests to make sure nothing breaks:
```bash
pytest tests/libs/dsl/ tests/cli/ -v
```
Expected: all pass (the tests don't assert on empty content).

**Step 3:** Verify template substitution is now correct:
```bash
python3 -c "
from libs.dsl.loader import load_package
from libs.dsl.resolver import resolve_refs
from libs.dsl.elaborator import elaborate_package
from pathlib import Path
result = elaborate_package(resolve_refs(load_package(Path('tests/fixtures/dsl_packages/galileo_falling_bodies'))))
for p in result.prompts:
    if p['chain'] == 'contradiction_chain':
        print(p['rendered'])
"
```
Expected: no blank gaps — should see actual claim text in the rendered output.

**Step 4:** Commit:
```bash
git add tests/fixtures/dsl_packages/galileo_falling_bodies/reasoning.yaml
git commit -m "fix: fill derived claims content in galileo fixture"
```

---

## Task 2: Rewrite `save_build()` to emit per-module Markdown

**Files:**
- Modify: `libs/dsl/build_store.py`
- Modify: `libs/dsl/elaborator.py` (no change to logic, just import for types)
- Test: `tests/cli/test_build.py`

**What changes:**

Rewrite `save_build()` to produce one `.md` file per module that has chains. Each file has:
- `# Module: {name}` header
- Per chain: `## {chain_name} ({edge_type})` section with premise → step → conclusion narrative

The function returns the build directory path (not a single file path).

**New `save_build` implementation:**

```python
def save_build(elaborated: ElaboratedPackage, build_dir: Path) -> Path:
    """Serialize elaborated package to per-module Markdown files in build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)

    pkg = elaborated.package

    # Index prompts by chain name
    prompts_by_chain: dict[str, list[dict]] = {}
    for p in elaborated.prompts:
        prompts_by_chain.setdefault(p["chain"], []).append(p)

    for mod in pkg.loaded_modules:
        chains = [d for d in mod.declarations if isinstance(d, ChainExpr)]
        if not chains:
            continue

        lines = [f"# Module: {mod.name}\n"]

        for chain in chains:
            ctx = elaborated.chain_contexts.get(chain.name, {})
            edge_type = ctx.get("edge_type", "deduction")
            lines.append(f"## {chain.name} ({edge_type})\n")

            # Premises
            for pref in ctx.get("premise_refs", []):
                snippet = (pref.get("content") or "").strip()
                prior_str = f", prior={pref['prior']}" if pref.get("prior") is not None else ""
                lines.append(f"**Premise:** {pref['name']} ({pref.get('type', '?')}{prior_str})")
                if snippet:
                    lines.append(f"> {snippet}\n")
                else:
                    lines.append("")

            # Steps
            for prompt in prompts_by_chain.get(chain.name, []):
                action = prompt["action"]
                step_num = prompt["step"]
                prior_str = ""
                # Find step prior from chain
                for s in chain.steps:
                    if s.step == step_num and hasattr(s, "prior") and s.prior is not None:
                        prior_str = f" (prior={s.prior})"
                        break

                if action == "__lambda__":
                    lines.append(f"**Step {step_num}**{prior_str}\n")
                else:
                    lines.append(f"**Step {step_num} — {action}**{prior_str}\n")

                lines.append(prompt["rendered"].strip() + "\n")

                # Evidence / Context
                direct = [a for a in prompt.get("args", []) if a.get("dependency") == "direct"]
                indirect = [a for a in prompt.get("args", []) if a.get("dependency") != "direct"]
                if direct:
                    evidence = ", ".join(
                        f"{a['ref']} ({a.get('decl_type', '?')}, prior={a.get('prior', '?')})"
                        for a in direct
                    )
                    lines.append(f"- Evidence: {evidence}")
                if indirect:
                    context = ", ".join(f"{a['ref']} ({a.get('decl_type', '?')})" for a in indirect)
                    lines.append(f"- Context: {context}")
                if direct or indirect:
                    lines.append("")

            # Conclusions
            for cref in ctx.get("conclusion_refs", []):
                prior_str = f", prior={cref['prior']}" if cref.get("prior") is not None else ""
                lines.append(f"**Conclusion:** {cref['name']} ({cref.get('type', '?')}{prior_str})\n")

        out_path = build_dir / f"{mod.name}.md"
        out_path.write_text("\n".join(lines))

    return build_dir
```

**Step 1:** Update tests in `tests/cli/test_build.py`:
- Change `test_build_creates_elaborated_yaml` → `test_build_creates_module_markdown_files`: assert `reasoning.md`, `aristotle.md`, `follow_up.md` exist (modules without chains like `motivation`, `setting` should NOT have files)
- Change `test_build_elaborated_yaml_has_chain_contexts` → `test_build_markdown_contains_chain_sections`: assert `reasoning.md` contains `## drag_prediction_chain` and `## contradiction_chain (contradiction)`
- Add `test_build_markdown_has_premise_and_conclusion`: assert `reasoning.md` contains `**Premise:**` and `**Conclusion:**`
- Keep `test_build_creates_gaia_dir`, `test_build_output_contains_module_count`, `test_build_invalid_path` unchanged

**Step 2:** Run tests to verify they fail:
```bash
pytest tests/cli/test_build.py -v
```

**Step 3:** Rewrite `save_build()` in `libs/dsl/build_store.py` with the implementation above.

**Step 4:** Run tests:
```bash
pytest tests/cli/test_build.py -v
```
Expected: all pass.

**Step 5:** Commit:
```bash
git add libs/dsl/build_store.py tests/cli/test_build.py
git commit -m "refactor: build output to per-module Markdown for LLM review"
```

---

## Task 3: Rewrite `review` command to read Markdown

**Files:**
- Modify: `cli/main.py` — `review` command
- Modify: `cli/llm_client.py` — simplify `_build_prompt`
- Test: `tests/cli/test_review.py`
- Test: `tests/cli/test_llm_client.py`

**What changes:**

The `review` command currently reads `elaborated.yaml` and assembles chain data from prompts + chain_contexts + package priors. After the refactor:

1. `review` reads all `.md` files from `build_dir`
2. Splits each file by `## ` to get per-chain sections
3. Each section becomes the LLM prompt directly (just append assessment instructions)
4. `_build_prompt` simplifies to: take chain Markdown section + append YAML format instructions

**New review flow in `cli/main.py`:**

```python
# Replace elaborated.yaml reading with:
md_files = sorted(build_dir.glob("*.md"))
if not md_files:
    typer.echo(f"Error: no build artifacts.\nRun 'gaia build {path}' first.", err=True)
    raise typer.Exit(1)

# Parse chain sections from all .md files
all_chain_data = []
for md_file in md_files:
    content = md_file.read_text()
    sections = content.split("\n## ")
    for i, section in enumerate(sections):
        if i == 0:
            continue  # skip module header
        # Re-add the ## prefix stripped by split
        chain_section = "## " + section
        # Extract chain name from "## chain_name (edge_type)"
        header_line = section.split("\n")[0]
        chain_name = header_line.split(" (")[0].strip()
        all_chain_data.append({
            "name": chain_name,
            "markdown": chain_section.strip(),
        })
```

**Simplified `_build_prompt`:**

```python
def _build_prompt(self, chain_data: dict) -> str:
    md = chain_data.get("markdown", "")
    if md:
        return (
            f"Review this reasoning chain:\n\n{md}\n\n"
            "For each step, assess whether the reasoning is logically valid.\n"
            "For each dependency, decide if it is 'direct' (conclusion depends on it) "
            "or 'indirect' (conclusion may still hold without it).\n\n"
            "Reply with ONLY a YAML document (no markdown fences, no extra text) "
            "in this exact format:\n\n"
            "steps:\n"
            "  - step: <number>\n"
            "    assessment: valid  # or questionable\n"
            "    suggested_prior: <float 0-1>\n"
            "    rewrite: null\n"
            "    dependencies:\n"
            "      - ref: <arg_name>\n"
            "        suggested: direct  # or indirect"
        )
    # Fallback for old-format chain_data (backward compat)
    return f"Review: {chain_data.get('name', '?')}"
```

**MockReviewClient changes:**

`review_chain` and `areview_chain` need to handle the new `chain_data` format (no `steps` key, just `markdown` + `name`). For mock, parse step numbers from markdown `**Step N` patterns:

```python
def review_chain(self, chain_data: dict) -> dict:
    import re
    steps = []
    md = chain_data.get("markdown", "")
    for match in re.finditer(r"\*\*Step (\d+)", md):
        step_num = int(match.group(1))
        # Extract prior if present: (prior=0.93)
        after = md[match.end():match.end() + 30]
        prior_match = re.search(r"prior=([\d.]+)", after)
        prior = float(prior_match.group(1)) if prior_match else 0.9
        steps.append({
            "step": step_num,
            "assessment": "valid",
            "suggested_prior": prior,
            "rewrite": None,
            "dependencies": [],
        })
    return {"chain": chain_data["name"], "steps": steps}
```

**Step 1:** Update tests:
- `test_llm_client.py`: update `test_mock_client_returns_valid_review` and `test_mock_client_preserves_existing_priors` to use markdown-based chain_data
- `test_review.py`: update `test_review_creates_sidecar` etc. — all should still work after `build` produces `.md` files
- Remove or update tests that reference `elaborated.yaml`

**Step 2:** Run tests to verify they fail.

**Step 3:** Implement the changes in `cli/main.py` and `cli/llm_client.py`.

**Step 4:** Run tests:
```bash
pytest tests/cli/test_review.py tests/cli/test_llm_client.py -v
```
Expected: all pass.

**Step 5:** Commit:
```bash
git add cli/main.py cli/llm_client.py tests/cli/test_review.py tests/cli/test_llm_client.py
git commit -m "refactor: review reads per-module Markdown, simplified prompt"
```

---

## Task 4: Add source fingerprint to review sidecar

**Files:**
- Modify: `cli/main.py` — `review` command (compute + write fingerprint)
- Modify: `cli/review_store.py` — `merge_review` (check fingerprint)
- Test: `tests/cli/test_review_store.py`
- Test: `tests/cli/test_review.py`

**What changes:**

1. In `review` command, after loading package, compute a fingerprint from the source YAML files:

```python
import hashlib

def _compute_source_fingerprint(pkg_path: Path) -> str:
    """SHA-256 of all YAML source files sorted by name."""
    h = hashlib.sha256()
    for yaml_file in sorted(pkg_path.glob("*.yaml")):
        h.update(yaml_file.read_bytes())
    return h.hexdigest()[:16]
```

2. Add `source_fingerprint` to review sidecar data:

```python
review_data = {
    "package": pkg.name,
    "model": "mock" if mock else model,
    "timestamp": now.isoformat(),
    "source_fingerprint": _compute_source_fingerprint(pkg_path),
    "chains": chain_reviews,
}
```

3. In `merge_review`, add optional fingerprint check:

```python
def merge_review(pkg: Package, review: dict, source_fingerprint: str | None = None) -> Package:
    review_fp = review.get("source_fingerprint")
    if source_fingerprint and review_fp and source_fingerprint != review_fp:
        import warnings
        warnings.warn(
            f"Review fingerprint mismatch: review was produced against {review_fp}, "
            f"but current source is {source_fingerprint}. "
            "Results may be stale.",
            stacklevel=2,
        )
    # ... rest unchanged
```

4. In `infer` and `publish` commands, compute fingerprint and pass to `merge_review`:

```python
fp = _compute_source_fingerprint(pkg_path)
pkg = merge_review(pkg, review, source_fingerprint=fp)
```

**Step 1:** Add tests to `tests/cli/test_review_store.py`:
- `test_merge_review_warns_on_fingerprint_mismatch`: verify `warnings.warn` is called when fingerprints differ
- `test_merge_review_no_warning_when_fingerprint_matches`: no warning when same

Add test to `tests/cli/test_review.py`:
- `test_review_sidecar_has_fingerprint`: verify review YAML contains `source_fingerprint` key

**Step 2:** Run tests to verify they fail.

**Step 3:** Implement `_compute_source_fingerprint` in `cli/main.py`, update `review`/`infer`/`publish` commands, update `merge_review` in `cli/review_store.py`.

**Step 4:** Run tests:
```bash
pytest tests/cli/test_review_store.py tests/cli/test_review.py tests/cli/test_infer.py -v
```
Expected: all pass.

**Step 5:** Commit:
```bash
git add cli/main.py cli/review_store.py tests/cli/test_review_store.py tests/cli/test_review.py
git commit -m "feat: add source fingerprint to review sidecar for stale detection"
```

---

## Task 5: Clean up dead code + full verification

**Files:**
- Modify: `libs/dsl/elaborator.py` — remove `chain_contexts` and `_build_chain_context` if no longer needed by build
- Modify: `libs/dsl/build_store.py` — remove old YAML serialization code
- Test: `tests/libs/dsl/test_elaborator.py` — remove/update chain_contexts tests if removed

**What changes:**

After Task 2-3, review no longer reads `elaborated.yaml`. Check if `chain_contexts` is still used:
- `save_build()` now uses `elaborated.chain_contexts` in the Markdown generation → **keep it**
- `_build_prompt` no longer needs `chain_data["context"]` → **remove old prompt tests that test context key**

Clean up:
1. Remove `test_prompt_includes_chain_type`, `test_prompt_shows_arg_content`, `test_prompt_handles_missing_context` from `test_llm_client.py` (prompt is now Markdown-based, tested differently)
2. Remove old elaborated.yaml import in `build_store.py` if not needed
3. Run full test suite + lint

**Step 1:** Clean up dead test cases and imports.

**Step 2:** Run lint:
```bash
ruff check libs/dsl/elaborator.py libs/dsl/build_store.py cli/llm_client.py cli/main.py cli/review_store.py
```

**Step 3:** Run full test suite:
```bash
pytest tests/ -q --ignore=tests/libs/storage/test_neo4j_store.py
```
Expected: all pass, no regressions.

**Step 4:** Integration test:
```bash
python -m cli.main build tests/fixtures/dsl_packages/galileo_falling_bodies
# Verify .md files exist and look correct
cat tests/fixtures/dsl_packages/galileo_falling_bodies/.gaia/build/reasoning.md

python -m cli.main review tests/fixtures/dsl_packages/galileo_falling_bodies --mock
python -m cli.main infer tests/fixtures/dsl_packages/galileo_falling_bodies

# Clean up
python -m cli.main clean tests/fixtures/dsl_packages/galileo_falling_bodies
```

**Step 5:** Commit:
```bash
git add -A
git commit -m "chore: clean up dead code after build output refactor"
```

---

## Verification

After all tasks:

```bash
# Lint
ruff check .

# Full test suite
pytest tests/ -q --ignore=tests/libs/storage/test_neo4j_store.py

# End-to-end manual test
python -m cli.main build tests/fixtures/dsl_packages/galileo_falling_bodies
cat tests/fixtures/dsl_packages/galileo_falling_bodies/.gaia/build/reasoning.md
python -m cli.main review --mock tests/fixtures/dsl_packages/galileo_falling_bodies
python -m cli.main review --mock --concurrency 3 tests/fixtures/dsl_packages/galileo_falling_bodies
python -m cli.main infer tests/fixtures/dsl_packages/galileo_falling_bodies
python -m cli.main clean tests/fixtures/dsl_packages/galileo_falling_bodies
```
