# CLI Pipeline Convergence — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Converge the CLI `build → review → infer → publish --local` pipeline to produce correct, scalable data using v2 storage models.

**Architecture:** Four-stage immutable artifact pipeline. Build writes `manifest.json` + single `package.md`. Review reads `package.md`, writes structured YAML report. Infer reads manifest + review, runs BP, writes `infer_result.json`. Publish reads all artifacts, converts to v2 models, writes to `LanceContentStore` + `KuzuGraphStore`.

**Tech Stack:** Python 3.12+, Pydantic v2, LanceDB (`libs/storage_v2/lance_content_store.py`), Kuzu (`libs/storage_v2/kuzu_graph_store.py`), litellm

**Design doc:** `docs/plans/2026-03-10-cli-pipeline-convergence-design.md`

---

## Task 1: Add `title` field to Module model

**Files:**
- Modify: `libs/lang/models.py:176-181`
- Modify: `tests/fixtures/gaia_language_packages/galileo_falling_bodies/*.yaml` (5 module files)
- Modify: `tests/fixtures/gaia_language_packages/newton_principia/*.yaml` (4 module files)
- Modify: `tests/fixtures/gaia_language_packages/einstein_gravity/*.yaml` (4 module files)
- Test: `tests/libs/lang/test_loader.py`

**Step 1: Add title field to Module**

```python
# libs/lang/models.py:176-181
class Module(BaseModel):
    type: str  # reasoning_module, setting_module, etc.
    name: str
    title: str | None = None  # NEW: natural language title for display
    knowledge: list[Knowledge] = Field(default_factory=list)
    export: list[str] = Field(default_factory=list)
```

**Step 2: Add title to all fixture YAML module files**

Each module YAML already has a comment with its natural language title. Convert to a `title` field. Examples:

```yaml
# galileo: motivation.yaml
type: motivation_module
name: motivation
title: 研究动机 — 为什么要做这项研究

# galileo: setting.yaml
type: setting_module
name: setting
title: 背景与假设

# galileo: aristotle.yaml
type: reasoning_module
name: aristotle
title: 亚里士多德学说 — 即将被挑战的先验知识

# galileo: reasoning.yaml
type: reasoning_module
name: reasoning
title: 核心推理 — 伽利略的论证

# galileo: follow_up.yaml
type: follow_up_module
name: follow_up
title: 后续问题 — 未来研究
```

Do the same for Newton and Einstein module YAML files (read the existing comment on line 1 of each file to determine the title).

**Step 3: Run existing tests to verify backward compat**

Run: `pytest tests/libs/lang/ -v`
Expected: All PASS (title is optional, `None` default)

**Step 4: Add a test for title loading**

```python
# In tests/libs/lang/test_loader.py, add:
def test_module_title_loaded():
    """Module title field should be loaded from YAML."""
    pkg = load_package(GALILEO_DIR)
    aristotle = next(m for m in pkg.loaded_modules if m.name == "aristotle")
    assert aristotle.title is not None
    assert "亚里士多德" in aristotle.title
```

Run: `pytest tests/libs/lang/test_loader.py::test_module_title_loaded -v`
Expected: PASS

**Step 5: Commit**

```bash
git add libs/lang/models.py tests/fixtures/gaia_language_packages/ tests/libs/lang/test_loader.py
git commit -m "feat: add title field to Module model for natural language headings"
```

---

## Task 2: Add `delete_package()` to v2 stores

**Files:**
- Modify: `libs/storage_v2/content_store.py`
- Modify: `libs/storage_v2/graph_store.py`
- Modify: `libs/storage_v2/lance_content_store.py`
- Modify: `libs/storage_v2/kuzu_graph_store.py`
- Test: `tests/libs/storage_v2/test_lance_content.py`
- Test: `tests/libs/storage_v2/test_graph_store.py`

**Step 1: Add to ContentStore ABC**

```python
# libs/storage_v2/content_store.py — add after existing methods
    @abstractmethod
    async def delete_package(self, package_id: str) -> None:
        """Delete all data belonging to a package (idempotent re-publish)."""
```

**Step 2: Add to GraphStore ABC**

```python
# libs/storage_v2/graph_store.py — add after existing methods
    @abstractmethod
    async def delete_package(self, package_id: str) -> None:
        """Delete all nodes and relationships belonging to a package."""
```

**Step 3: Write failing test for LanceContentStore.delete_package**

```python
# tests/libs/storage_v2/test_lance_content.py — add:
async def test_delete_package_removes_all_data(content_store, closures, chains):
    """delete_package should remove closures, chains, and related records."""
    await content_store.write_closures(closures)
    await content_store.write_chains(chains)

    pkg_id = closures[0].source_package_id
    await content_store.delete_package(pkg_id)

    # All closures gone
    for c in closures:
        assert await content_store.get_closure(c.closure_id) is None

    # All chains gone
    result = await content_store.get_chains_by_module(chains[0].module_id)
    assert len(result) == 0


async def test_delete_package_is_idempotent(content_store):
    """Deleting a non-existent package should not raise."""
    await content_store.delete_package("nonexistent_pkg")  # should not raise
```

Run: `pytest tests/libs/storage_v2/test_lance_content.py::test_delete_package_removes_all_data -v`
Expected: FAIL (method not implemented)

**Step 4: Implement LanceContentStore.delete_package**

```python
# libs/storage_v2/lance_content_store.py — add method:
    async def delete_package(self, package_id: str) -> None:
        """Delete all data belonging to a package."""
        # Tables that have package_id or source_package_id columns
        table_col_pairs = [
            ("packages", "package_id"),
            ("modules", "package_id"),
            ("closures", "source_package_id"),
            ("chains", "package_id"),
            ("probabilities", "chain_id"),  # handled via chain_id prefix
        ]
        for table_name, col in table_col_pairs:
            try:
                table = self._db.open_table(table_name)
                if col == "chain_id":
                    # ProbabilityRecord has chain_id which starts with package_id
                    table.delete(f"{col} LIKE '{package_id}.%'")
                else:
                    table.delete(f"{col} = '{package_id}'")
            except Exception:
                pass  # Table may not exist yet

        # belief_history: keyed by closure_id which starts with package_id/
        try:
            table = self._db.open_table("belief_history")
            table.delete(f"closure_id LIKE '{package_id}/%'")
        except Exception:
            pass

        self._fts_dirty = True
```

Run: `pytest tests/libs/storage_v2/test_lance_content.py::test_delete_package_removes_all_data -v`
Expected: PASS

**Step 5: Write failing test for KuzuGraphStore.delete_package**

```python
# tests/libs/storage_v2/test_graph_store.py — add:
async def test_delete_package_removes_topology(graph_store, closures, chains):
    """delete_package should remove all closures and chains for a package."""
    await graph_store.write_topology(closures, chains)

    pkg_id = closures[0].source_package_id
    await graph_store.delete_package(pkg_id)

    # Verify nodes are gone by checking neighbor queries return empty
    result = await graph_store.get_neighbors(
        closures[0].closure_id, direction="both", chain_types=None, max_hops=1
    )
    assert len(result.closures) == 0
    assert len(result.chains) == 0
```

Run: `pytest tests/libs/storage_v2/test_graph_store.py::test_delete_package_removes_topology -v`
Expected: FAIL

**Step 6: Implement KuzuGraphStore.delete_package**

```python
# libs/storage_v2/kuzu_graph_store.py — add method:
    async def delete_package(self, package_id: str) -> None:
        """Delete all Closure and Chain nodes (and their relationships) for a package."""
        def _delete() -> None:
            conn = kuzu.Connection(self._db)
            # Delete chains belonging to this package (chain_id starts with package_id.)
            conn.execute(
                "MATCH (c:Chain) WHERE starts_with(c.chain_id, $prefix) DETACH DELETE c",
                {"prefix": f"{package_id}."},
            )
            # Delete closures belonging to this package (closure_vid starts with package_id/)
            conn.execute(
                "MATCH (c:Closure) WHERE starts_with(c.closure_vid, $prefix) DETACH DELETE c",
                {"prefix": f"{package_id}/"},
            )

        import asyncio
        await asyncio.get_event_loop().run_in_executor(None, _delete)
```

Run: `pytest tests/libs/storage_v2/test_graph_store.py::test_delete_package_removes_topology -v`
Expected: PASS

**Step 7: Run all v2 storage tests**

Run: `pytest tests/libs/storage_v2/ -v`
Expected: All PASS (93 existing + 3 new)

**Step 8: Commit**

```bash
git add libs/storage_v2/ tests/libs/storage_v2/
git commit -m "feat: add delete_package() to v2 content and graph stores"
```

---

## Task 3: Build manifest serialization

**Files:**
- Create: `cli/manifest.py`
- Test: `tests/cli/test_manifest.py`

**Step 1: Write failing test for manifest roundtrip**

```python
# tests/cli/test_manifest.py
"""Tests for build manifest serialization."""
from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


def test_manifest_roundtrip(tmp_path):
    """Serialize a resolved package to manifest.json and deserialize it back."""
    from cli.manifest import deserialize_package, save_manifest

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    manifest_path = save_manifest(pkg, tmp_path)
    assert manifest_path.exists()
    assert manifest_path.name == "manifest.json"

    restored = deserialize_package(manifest_path)
    assert restored.name == pkg.name
    assert len(restored.loaded_modules) == len(pkg.loaded_modules)

    # Check that knowledge objects survived
    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")
    claims = [d for d in reasoning.knowledge if d.type == "claim"]
    assert len(claims) > 0


def test_manifest_preserves_resolution_index(tmp_path):
    """Resolution index should allow Ref._resolved to be rebuilt."""
    from cli.manifest import deserialize_package, save_manifest
    from libs.lang.models import Ref

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    save_manifest(pkg, tmp_path)
    restored = deserialize_package(tmp_path / "manifest.json")

    # Check that _index was rebuilt
    assert len(restored._index) > 0

    # Check a specific Ref has _resolved rebuilt
    reasoning = next(m for m in restored.loaded_modules if m.name == "reasoning")
    ref = next(d for d in reasoning.knowledge if isinstance(d, Ref) and d.name == "heavier_falls_faster")
    assert ref._resolved is not None
    assert ref._resolved.name == "heavier_falls_faster"
```

Run: `pytest tests/cli/test_manifest.py -v`
Expected: FAIL (module not found)

**Step 2: Implement cli/manifest.py**

```python
"""Build manifest serialization/deserialization."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from libs.lang.models import Knowledge, Module, Package, Ref


def _compute_source_fingerprint(pkg_path: Path) -> str:
    """SHA-256 of all YAML source files sorted by name."""
    import hashlib

    h = hashlib.sha256()
    for yaml_file in sorted(pkg_path.glob("*.yaml")):
        h.update(yaml_file.read_bytes())
    return h.hexdigest()[:16]


def save_manifest(
    pkg: Package,
    build_dir: Path,
    pkg_path: Path | None = None,
) -> Path:
    """Serialize resolved package to manifest.json."""
    build_dir.mkdir(parents=True, exist_ok=True)

    # Serialize loaded_modules (excluded from default model_dump)
    modules_data = []
    for mod in pkg.loaded_modules:
        mod_data = mod.model_dump()
        # Serialize knowledge objects with discriminated types
        knowledge = []
        for decl in mod.knowledge:
            d = decl.model_dump()
            d["__type__"] = type(decl).__name__
            if isinstance(decl, Ref):
                d["target"] = decl.target
            knowledge.append(d)
        mod_data["knowledge"] = knowledge
        modules_data.append(mod_data)

    # Build resolution index from _index
    resolution_index = {}
    for path, obj in pkg._index.items():
        d = obj.model_dump()
        d["__type__"] = type(obj).__name__
        resolution_index[path] = d

    manifest = {
        "version": 1,
        "source_fingerprint": _compute_source_fingerprint(pkg_path) if pkg_path else "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "package": {
            "name": pkg.name,
            "version": pkg.version,
            "modules": pkg.modules_list,
            "export": pkg.export,
            "dependencies": [d.model_dump() for d in pkg.dependencies],
            "manifest": pkg.manifest.model_dump() if pkg.manifest else None,
        },
        "loaded_modules": modules_data,
        "resolution_index": resolution_index,
    }

    out_path = build_dir / "manifest.json"
    out_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return out_path


def deserialize_package(manifest_path: Path) -> Package:
    """Deserialize package from manifest.json, rebuilding _resolved pointers."""
    from libs.lang.models import (
        Action,
        Claim,
        Contradiction,
        Equivalence,
        InferAction,
        Question,
        Relation,
        RetractAction,
        Setting,
        Subsumption,
    )

    data = json.loads(manifest_path.read_text())
    pkg_data = data["package"]

    # Type registry for knowledge deserialization
    type_map: dict[str, type[Knowledge]] = {
        "Claim": Claim,
        "Setting": Setting,
        "Question": Question,
        "Ref": Ref,
        "ChainExpr": __import__("libs.lang.models", fromlist=["ChainExpr"]).ChainExpr,
        "InferAction": InferAction,
        "RetractAction": RetractAction,
        "Contradiction": Contradiction,
        "Equivalence": Equivalence,
        "Subsumption": Subsumption,
    }

    # Rebuild modules with typed knowledge
    loaded_modules = []
    for mod_data in data["loaded_modules"]:
        knowledge = []
        for k_data in mod_data["knowledge"]:
            type_name = k_data.pop("__type__", None)
            cls = type_map.get(type_name, Claim)
            knowledge.append(cls.model_validate(k_data))
        mod_data["knowledge"] = knowledge
        loaded_modules.append(Module.model_validate(mod_data))

    # Rebuild resolution index
    index: dict[str, Knowledge] = {}
    for path, obj_data in data.get("resolution_index", {}).items():
        type_name = obj_data.pop("__type__", None)
        cls = type_map.get(type_name, Claim)
        index[path] = cls.model_validate(obj_data)

    # Create package
    pkg = Package(
        name=pkg_data["name"],
        version=pkg_data.get("version"),
        modules=pkg_data.get("modules", []),
        export=pkg_data.get("export", []),
        loaded_modules=loaded_modules,
    )
    if pkg_data.get("manifest"):
        from libs.lang.models import Manifest
        pkg.manifest = Manifest.model_validate(pkg_data["manifest"])
    if pkg_data.get("dependencies"):
        from libs.lang.models import Dependency
        pkg.dependencies = [Dependency.model_validate(d) for d in pkg_data["dependencies"]]

    pkg._index = index

    # Rebuild Ref._resolved pointers
    for mod in loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, Ref):
                key = f"{mod.name}.{decl.name}"
                if key in index:
                    decl._resolved = index[key]

    return pkg
```

Run: `pytest tests/cli/test_manifest.py -v`
Expected: PASS

**Step 3: Commit**

```bash
git add cli/manifest.py tests/cli/test_manifest.py
git commit -m "feat: add manifest.json serialization for build stage"
```

---

## Task 4: Rewrite build_store for single package.md

**Files:**
- Modify: `libs/lang/build_store.py`
- Test: `tests/libs/lang/test_build_store.py`

**Step 1: Write test for new markdown format**

```python
# tests/libs/lang/test_build_store.py
"""Tests for build_store single package.md generation."""
from pathlib import Path

from libs.lang.build_store import save_build
from libs.lang.elaborator import elaborate_package
from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[2] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"


def test_save_build_creates_single_package_md(tmp_path):
    """Build should produce a single package.md, not per-module files."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)

    save_build(elaborated, tmp_path)

    package_md = tmp_path / "package.md"
    assert package_md.exists()
    content = package_md.read_text()

    # Should contain package name in title
    assert "galileo_falling_bodies" in content

    # Should contain all modules in order
    assert "[module:motivation]" in content
    assert "[module:setting]" in content
    assert "[module:aristotle]" in content
    assert "[module:reasoning]" in content
    assert "[module:follow_up]" in content

    # motivation should appear before reasoning
    assert content.index("[module:motivation]") < content.index("[module:reasoning]")


def test_save_build_has_chain_anchors(tmp_path):
    """Chain anchors should use [chain:name] format."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "[chain:synthesis_chain]" in content
    assert "[chain:drag_prediction_chain]" in content


def test_save_build_has_step_anchors(tmp_path):
    """Step anchors should use [step:chain_name.N] format."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "[step:synthesis_chain.2]" in content
    assert "[step:drag_prediction_chain.2]" in content


def test_save_build_has_direct_references(tmp_path):
    """Steps with direct dependencies should have 'Direct references:' sections."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "**Direct references:**" in content


def test_save_build_has_context_section(tmp_path):
    """Chains with indirect deps should have 'Context (indirect reference):' sections."""
    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    elaborated = elaborate_package(pkg)
    save_build(elaborated, tmp_path)

    content = (tmp_path / "package.md").read_text()
    assert "**Context (indirect reference):**" in content
```

Run: `pytest tests/libs/lang/test_build_store.py -v`
Expected: FAIL (old format doesn't match)

**Step 2: Rewrite build_store.py**

Rewrite `libs/lang/build_store.py` to produce a single `package.md` following the format specified in design doc §3. Key changes:

- Single file instead of per-module
- Module sections with `[module:name]` anchors and titles
- Knowledge declarations listed before chains
- Chain sections with `[chain:name]` and `[step:chain.N]` anchors
- Direct references expanded inline at each step
- Context (indirect) references at chain header
- Conclusion expanded at chain footer

The complete implementation should follow the example in the design doc. Reference the elaborated package's `chain_contexts` for premise/conclusion info and `prompts` for rendered step text. Use `mod.title or mod.name` for the section heading.

**Step 3: Run tests**

Run: `pytest tests/libs/lang/test_build_store.py -v`
Expected: All PASS

**Step 4: Run existing build pipeline tests to check for regressions**

Run: `pytest tests/libs/lang/test_build_review_pipeline.py -v`
Expected: May need adjustment (tests check for per-module .md files). Update assertions: change `md_files = list(build_dir.glob("*.md"))` checks to look for `package.md` instead.

**Step 5: Commit**

```bash
git add libs/lang/build_store.py tests/libs/lang/test_build_store.py tests/libs/lang/test_build_review_pipeline.py
git commit -m "feat: rewrite build_store to produce single package.md with structured anchors"
```

---

## Task 5: Update build() command to write manifest

**Files:**
- Modify: `cli/main.py:38-61`

**Step 1: Update build() to also save manifest.json**

```python
@app.command()
def build(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
) -> None:
    """Elaborate: parse + resolve + instantiate params."""
    from cli.manifest import save_manifest
    from libs.lang.build_store import save_build
    from libs.lang.elaborator import elaborate_package

    pkg_path = Path(path)
    try:
        pkg = _load_with_deps(pkg_path)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    elaborated = elaborate_package(pkg)

    build_dir = pkg_path / ".gaia" / "build"
    save_build(elaborated, build_dir)
    save_manifest(pkg, build_dir, pkg_path=pkg_path)

    n_mods = len(pkg.loaded_modules)
    n_prompts = len(elaborated.prompts)
    typer.echo(f"Built {pkg.name}: {n_mods} modules, {n_prompts} elaborated prompts")
    typer.echo(f"Artifacts: {build_dir}/")
```

**Step 2: Run CLI build tests**

Run: `pytest tests/cli/test_build.py -v` (if exists, otherwise run `pytest tests/cli/ -v`)
Expected: PASS

**Step 3: Commit**

```bash
git add cli/main.py
git commit -m "feat: build command writes manifest.json alongside package.md"
```

---

## Task 6: Review prompt + client rewrite

**Files:**
- Create: `cli/prompts/review_system.md`
- Modify: `cli/llm_client.py`
- Test: `tests/cli/test_llm_client.py`

**Step 1: Create review system prompt**

Create `cli/prompts/review_system.md` with the exact content from design doc §4 (the system prompt specifying terminology, workflow, and output format).

**Step 2: Write failing test for new review format**

```python
# tests/cli/test_llm_client.py
"""Tests for the review client."""
from cli.llm_client import MockReviewClient


def test_mock_review_uses_chain_scoped_step_ids():
    """Mock review should produce step IDs like 'chain_name.N'."""
    md = """### Chain: test_chain [chain:test_chain] (deduction)

**[step:test_chain.2]** (prior=0.9)

**Direct references:**
> **[claim] some_claim** (prior=0.8)
> Some content.

**Reasoning:**
> Some reasoning text.

**Conclusion:** [claim] result (prior=0.5)
> Result content.
"""
    client = MockReviewClient()
    result = client.review_chain({"name": "test_chain", "markdown": md})

    assert result["chain"] == "test_chain"
    assert len(result["steps"]) == 1
    assert result["steps"][0]["step"] == "test_chain.2"
    assert result["steps"][0]["conditional_prior"] == 0.9
    assert result["steps"][0]["weak_points"] == []


def test_mock_review_produces_summary():
    """Mock review should include a summary field."""
    md = """### Chain: c1 [chain:c1] (deduction)
**[step:c1.2]** (prior=0.85)
**Reasoning:**
> text
**Conclusion:** [claim] x (prior=0.5)
"""
    client = MockReviewClient()
    result = client.review_package({"package": "test_pkg", "markdown": md})

    assert "summary" in result
    assert "chains" in result
```

Run: `pytest tests/cli/test_llm_client.py -v`
Expected: FAIL

**Step 3: Rewrite llm_client.py**

Key changes:
- `ReviewClient` gets a `review_package(data)` method that sends entire `package.md` in one LLM call
- System prompt loaded from `cli/prompts/review_system.md`
- Response parsed as YAML with new format (step IDs like `chain_name.N`, `weak_points`, `conditional_prior`, `explanation`)
- `MockReviewClient` updated to parse `[step:chain_name.N]` anchors and produce matching format
- Keep `review_chain()` as backward-compat wrapper (delegates to single-chain review)

```python
"""LLM client for package review."""

from __future__ import annotations

import re
from pathlib import Path


class ReviewClient:
    """LLM-based package reviewer using litellm."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self._model = model
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent / "prompts" / "review_system.md"
        return prompt_path.read_text()

    def review_package(self, package_data: dict) -> dict:
        """Review entire package in one LLM call."""
        import litellm

        md = package_data.get("markdown", "")
        response = litellm.completion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Review the following knowledge package:\n\n{md}"},
            ],
        )
        return self._parse_response(response.choices[0].message.content)

    async def areview_package(self, package_data: dict) -> dict:
        """Async version of review_package."""
        import litellm

        md = package_data.get("markdown", "")
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Review the following knowledge package:\n\n{md}"},
            ],
        )
        return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, response: str) -> dict:
        """Parse LLM YAML response. Falls back to mock on failure."""
        import yaml

        try:
            parsed = yaml.safe_load(response)
            if isinstance(parsed, dict) and "chains" in parsed:
                return parsed
        except Exception:
            pass
        # Fallback
        return {"summary": "Parse error — falling back to defaults.", "chains": []}

    # Backward compat
    def review_chain(self, chain_data: dict) -> dict:
        return MockReviewClient().review_chain(chain_data)

    async def areview_chain(self, chain_data: dict) -> dict:
        return MockReviewClient().review_chain(chain_data)


class MockReviewClient:
    """Mock reviewer that parses step info from Markdown (no LLM calls)."""

    _STEP_RE = re.compile(r"\*\*\[step:([\w.]+\.(\d+))\]\*\*\s*\(prior=([\d.]+)\)")

    def review_package(self, package_data: dict) -> dict:
        """Parse all chains from package markdown."""
        md = package_data.get("markdown", "")
        chains = self._extract_chains(md)
        return {
            "summary": "Mock review — all steps accepted at author priors.",
            "chains": chains,
        }

    async def areview_package(self, package_data: dict) -> dict:
        return self.review_package(package_data)

    def review_chain(self, chain_data: dict) -> dict:
        """Review a single chain (backward compat)."""
        md = chain_data.get("markdown", "")
        chains = self._extract_chains(md)
        if chains:
            return chains[0]
        return {"chain": chain_data.get("name", "?"), "steps": []}

    async def areview_chain(self, chain_data: dict) -> dict:
        return self.review_chain(chain_data)

    def _extract_chains(self, md: str) -> list[dict]:
        """Extract chain reviews from markdown using [step:] anchors."""
        # Group steps by chain name
        chain_steps: dict[str, list[dict]] = {}
        for match in self._STEP_RE.finditer(md):
            full_id = match.group(1)        # e.g. "synthesis_chain.2"
            step_num_str = match.group(2)   # e.g. "2"
            prior = float(match.group(3))   # e.g. 0.94
            chain_name = full_id.rsplit(".", 1)[0]  # e.g. "synthesis_chain"

            chain_steps.setdefault(chain_name, []).append({
                "step": full_id,
                "weak_points": [],
                "conditional_prior": prior,
                "explanation": "",
            })

        return [
            {"chain": name, "steps": steps}
            for name, steps in chain_steps.items()
        ]
```

Run: `pytest tests/cli/test_llm_client.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/prompts/review_system.md cli/llm_client.py tests/cli/test_llm_client.py
git commit -m "feat: rewrite review client for whole-package review with structured weak points"
```

---

## Task 7: Update review command + merge_review

**Files:**
- Modify: `cli/main.py:65-133` (review command)
- Modify: `cli/review_store.py:42-82` (merge_review)
- Test: `tests/cli/test_review.py`

**Step 1: Update review() command**

Rewrite to read single `package.md` instead of per-module `.md` files:

```python
@app.command()
def review(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    mock: bool = typer.Option(False, "--mock", help="Use mock reviewer (no LLM calls)"),
    model: str = typer.Option("claude-sonnet-4-20250514", "--model", help="LLM model for review"),
) -> None:
    """LLM reviews package -> sidecar report (.gaia/reviews/)."""
    from datetime import datetime, timezone

    from cli.llm_client import MockReviewClient, ReviewClient
    from cli.review_store import write_review
    from libs.lang.loader import load_package

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"

    # 1. Read package.md
    package_md = build_dir / "package.md"
    if not package_md.exists():
        typer.echo(f"Error: no build artifacts.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    md_content = package_md.read_text()

    # 2. Load package metadata + fingerprint
    pkg = load_package(pkg_path)
    fingerprint = _compute_source_fingerprint(pkg_path)

    # 3. Review
    client = MockReviewClient() if mock else ReviewClient(model=model)
    package_data = {"package": pkg.name, "markdown": md_content}

    if mock:
        review_result = client.review_package(package_data)
    else:
        review_result = asyncio.run(client.areview_package(package_data))

    # 4. Write sidecar
    now = datetime.now(timezone.utc)
    review_data = {
        "package": pkg.name,
        "model": "mock" if mock else model,
        "timestamp": now.isoformat(),
        "source_fingerprint": fingerprint,
        "summary": review_result.get("summary", ""),
        "chains": review_result.get("chains", []),
    }
    review_path = write_review(review_data, reviews_dir)

    n_chains = len(review_data["chains"])
    typer.echo(f"Reviewed {n_chains} chains for {pkg.name}")
    typer.echo(f"Report: {review_path}")
```

**Step 2: Update merge_review for new format**

The new review format uses `conditional_prior` instead of `suggested_prior`, and step IDs are `chain_name.N` instead of bare `N`:

```python
# cli/review_store.py — update merge_review:
def merge_review(pkg: Package, review: dict, source_fingerprint: str | None = None) -> Package:
    """Merge review suggestions into package (deep copy -- original untouched)."""
    import warnings

    review_fp = review.get("source_fingerprint")
    if source_fingerprint and review_fp and source_fingerprint != review_fp:
        warnings.warn(
            f"Review fingerprint mismatch: review was produced against {review_fp}, "
            f"but current source is {source_fingerprint}. Results may be stale.",
            stacklevel=2,
        )

    merged = copy.deepcopy(pkg)

    chains_by_name: dict[str, ChainExpr] = {}
    for mod in merged.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, ChainExpr):
                chains_by_name[decl.name] = decl

    for chain_review in review.get("chains", []):
        chain = chains_by_name.get(chain_review["chain"])
        if not chain:
            continue
        for step_review in chain_review.get("steps", []):
            # Parse step number from "chain_name.N" or bare N
            step_id = step_review["step"]
            if isinstance(step_id, str) and "." in step_id:
                step_num = int(step_id.rsplit(".", 1)[1])
            else:
                step_num = int(step_id)

            step = next((s for s in chain.steps if s.step == step_num), None)
            if not step:
                continue

            # Support both old and new format
            prior = step_review.get("conditional_prior") or step_review.get("suggested_prior")
            if prior is not None and hasattr(step, "prior"):
                step.prior = prior

    return merged
```

**Step 3: Test**

Run: `pytest tests/cli/ -v`
Expected: All PASS

**Step 4: Commit**

```bash
git add cli/main.py cli/review_store.py
git commit -m "feat: review command reads single package.md, merge_review supports new format"
```

---

## Task 8: Infer result serialization + infer reads manifest

**Files:**
- Create: `cli/infer_store.py`
- Modify: `cli/main.py:167-244` (infer command)
- Test: `tests/cli/test_infer_store.py`

**Step 1: Create cli/infer_store.py**

```python
"""Infer result serialization/deserialization."""

from __future__ import annotations

import json
from pathlib import Path


def save_infer_result(
    pkg_name: str,
    variables: dict[str, dict],
    factors: list[dict],
    bp_run_id: str,
    review_file: str | None,
    source_fingerprint: str,
    infer_dir: Path,
) -> Path:
    """Save inference results to infer_result.json."""
    infer_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "version": 1,
        "package": pkg_name,
        "source_fingerprint": source_fingerprint,
        "review_file": review_file,
        "bp_run_id": bp_run_id,
        "variables": variables,
        "factors": factors,
    }

    out_path = infer_dir / "infer_result.json"
    out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    return out_path


def load_infer_result(path: Path) -> dict:
    """Load infer result from JSON file."""
    if not path.exists():
        raise FileNotFoundError(f"Infer result not found: {path}")
    return json.loads(path.read_text())
```

**Step 2: Update infer() to read manifest and write infer_result.json**

Modify `cli/main.py` infer command to:
1. Read `manifest.json` instead of re-parsing YAML (`deserialize_package()`)
2. After BP, save results to `infer_result.json`
3. Generate a `bp_run_id` (UUID)

```python
@app.command()
def infer(
    path: str = typer.Argument(".", help="Path to knowledge package directory"),
    review_file: str | None = typer.Option(None, "--review", help="Path to review sidecar file"),
) -> None:
    """Compile a factor graph (from review) and run BP to compute beliefs."""
    import uuid

    from cli.infer_store import save_infer_result
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, merge_review, read_review
    from libs.lang.compiler import compile_factor_graph
    from libs.inference.bp import BeliefPropagation
    from libs.inference.factor_graph import FactorGraph

    pkg_path = Path(path)
    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"
    infer_dir = pkg_path / ".gaia" / "infer"
    manifest_path = build_dir / "manifest.json"

    # 1. Read manifest
    if not manifest_path.exists():
        typer.echo(f"Error: no manifest.json.\nRun 'gaia build {path}' first.", err=True)
        raise typer.Exit(1)

    pkg = deserialize_package(manifest_path)

    # 2. Read review
    try:
        if review_file:
            review = read_review(Path(review_file))
            review_filename = review_file
        else:
            latest = find_latest_review(reviews_dir)
            review = read_review(latest)
            review_filename = latest.name
    except FileNotFoundError:
        typer.echo(
            f"Error: no review file found.\n"
            f"Run 'gaia review {path}' first, or specify --review <path>.",
            err=True,
        )
        raise typer.Exit(1)

    # 3. Merge review into package
    fp = _compute_source_fingerprint(pkg_path)
    pkg = merge_review(pkg, review, source_fingerprint=fp)

    # 4. Compile factor graph
    compiled_fg = compile_factor_graph(pkg)

    # 5. Run BP
    bp_fg = FactorGraph()
    name_to_id: dict[str, int] = {}
    for i, (name, prior) in enumerate(compiled_fg.variables.items()):
        node_id = i + 1
        name_to_id[name] = node_id
        bp_fg.add_variable(node_id, prior)

    for j, factor in enumerate(compiled_fg.factors):
        premise_ids = [name_to_id[n] for n in factor["premises"] if n in name_to_id]
        conclusion_ids = [name_to_id[n] for n in factor["conclusions"] if n in name_to_id]
        bp_fg.add_factor(
            edge_id=j + 1,
            premises=premise_ids,
            conclusions=conclusion_ids,
            probability=factor["probability"],
            edge_type=factor.get("edge_type", "deduction"),
        )

    bp = BeliefPropagation()
    beliefs = bp.run(bp_fg)

    # 6. Map back to names
    id_to_name = {v: k for k, v in name_to_id.items()}
    named_beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

    # 7. Save infer_result.json
    bp_run_id = str(uuid.uuid4())
    variables = {
        name: {"prior": compiled_fg.variables[name], "belief": named_beliefs.get(name)}
        for name in compiled_fg.variables
    }
    factors = compiled_fg.factors

    save_infer_result(
        pkg_name=pkg.name,
        variables=variables,
        factors=factors,
        bp_run_id=bp_run_id,
        review_file=review_filename if not isinstance(review_filename, str) else review_filename,
        source_fingerprint=fp,
        infer_dir=infer_dir,
    )

    # 8. Output
    typer.echo(f"Package: {pkg.name}")
    typer.echo(f"Variables: {len(compiled_fg.variables)}")
    typer.echo(f"Factors: {len(compiled_fg.factors)}")
    typer.echo(f"Artifacts: {infer_dir}/")
    typer.echo()
    typer.echo("Beliefs after BP:")
    for name, belief in sorted(named_beliefs.items()):
        prior = compiled_fg.variables.get(name, "?")
        typer.echo(f"  {name}: prior={prior} -> belief={belief:.4f}")
```

**Step 3: Test**

Run: `pytest tests/cli/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/infer_store.py cli/main.py tests/cli/test_infer_store.py
git commit -m "feat: infer reads manifest.json, writes infer_result.json"
```

---

## Task 9: lang_to_v2 converter

**Files:**
- Create: `cli/lang_to_v2.py`
- Test: `tests/cli/test_lang_to_v2.py`

**Step 1: Write failing tests**

```python
# tests/cli/test_lang_to_v2.py
"""Tests for Language → v2 storage model conversion."""
from pathlib import Path

from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def test_galileo_converts_to_v2():
    """Galileo package converts to v2 models with correct counts."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test-run")

    assert data.package.package_id == "galileo_falling_bodies"
    assert data.package.name == "galileo_falling_bodies"
    assert len(data.modules) == 5
    assert len(data.closures) > 0
    assert len(data.chains) > 0

    # Closure IDs should use / separator
    for c in data.closures:
        assert "/" in c.closure_id
        assert c.closure_id.startswith("galileo_falling_bodies/")

    # Chain IDs should use . separator
    for ch in data.chains:
        assert ch.chain_id.startswith("galileo_falling_bodies.")


def test_closure_dedup():
    """Same closure referenced from multiple modules should produce one Closure."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)
    data = convert_to_v2(pkg=pkg, review={}, beliefs={}, bp_run_id="test")

    ids = [c.closure_id for c in data.closures]
    assert len(ids) == len(set(ids)), f"Duplicate closure IDs: {ids}"


def test_cross_package_refs_not_duplicated():
    """Newton referencing Galileo closures should not re-create them."""
    from cli.lang_to_v2 import convert_to_v2

    galileo = load_package(GALILEO_DIR)
    galileo = resolve_refs(galileo)
    newton = load_package(NEWTON_DIR)
    newton = resolve_refs(newton, deps={"galileo_falling_bodies": galileo})

    data = convert_to_v2(pkg=newton, review={}, beliefs={}, bp_run_id="test")

    # Newton closures should only include Newton's own declarations
    for c in data.closures:
        assert c.source_package_id == "newton_principia"


def test_beliefs_become_snapshots():
    """Belief values should become BeliefSnapshot records."""
    from cli.lang_to_v2 import convert_to_v2

    pkg = load_package(GALILEO_DIR)
    pkg = resolve_refs(pkg)

    beliefs = {"vacuum_prediction": 0.82, "heavier_falls_faster": 0.35}
    data = convert_to_v2(pkg=pkg, review={}, beliefs=beliefs, bp_run_id="test-run")

    snapshots_by_name = {s.closure_id.split("/")[1]: s for s in data.belief_snapshots}
    assert snapshots_by_name["vacuum_prediction"].belief == 0.82
    assert snapshots_by_name["heavier_falls_faster"].belief == 0.35
```

Run: `pytest tests/cli/test_lang_to_v2.py -v`
Expected: FAIL

**Step 2: Implement cli/lang_to_v2.py**

Implement the converter following design doc §6 (Section 6). Full conversion logic for Package, Module, Closure, Chain, ChainStep, ProbabilityRecord, BeliefSnapshot.

Key implementation details:
- Walk `pkg.loaded_modules` in order
- For each Knowledge object: if Ref, follow `_resolved`; skip if target is from another package
- Skip ChainExpr, Action, Relation when building Closures (they become Chains)
- Dedup closures by `(closure_id, version)`
- For ChainExpr: walk steps, map StepApply/StepLambda to ChainStep with ClosureRef premises
- For Relation: create single-step Chain with all members as premises
- Review data → ProbabilityRecord with `source="llm_review"`
- Beliefs → BeliefSnapshot with `bp_run_id`

**Step 3: Run tests**

Run: `pytest tests/cli/test_lang_to_v2.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/lang_to_v2.py tests/cli/test_lang_to_v2.py
git commit -m "feat: add lang_to_v2 converter from Language models to v2 storage"
```

---

## Task 10: Rewrite _publish_local()

**Files:**
- Modify: `cli/main.py:293-430`
- Test: `tests/cli/test_publish.py`

**Step 1: Rewrite _publish_local()**

Replace entire function following design doc §7. Key changes:
- Read `manifest.json` + `infer_result.json` + `review_*.yaml` (no YAML re-parsing)
- Use `convert_to_v2()` to produce v2 models
- Use `LanceContentStore` + `KuzuGraphStore` directly (not v1 StorageManager)
- Delete by `package_id` before insert (idempotent)
- Write receipt.json

```python
async def _publish_local(pkg_path: Path, db_path: str) -> None:
    """Convert artifacts to v2 models and write to LanceDB + Kuzu."""
    from cli.infer_store import load_infer_result
    from cli.lang_to_v2 import convert_to_v2
    from cli.manifest import deserialize_package
    from cli.review_store import find_latest_review, read_review
    from libs.storage_v2.lance_content_store import LanceContentStore
    from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

    build_dir = pkg_path / ".gaia" / "build"
    reviews_dir = pkg_path / ".gaia" / "reviews"
    infer_dir = pkg_path / ".gaia" / "infer"
    publish_dir = pkg_path / ".gaia" / "publish"

    # 1. Read artifacts
    manifest_path = build_dir / "manifest.json"
    infer_path = infer_dir / "infer_result.json"

    if not manifest_path.exists():
        typer.echo("Error: no manifest.json. Run 'gaia build' first.", err=True)
        raise typer.Exit(1)
    if not infer_path.exists():
        typer.echo("Error: no infer_result.json. Run 'gaia infer' first.", err=True)
        raise typer.Exit(1)

    pkg = deserialize_package(manifest_path)
    infer_result = load_infer_result(infer_path)

    try:
        review = read_review(find_latest_review(reviews_dir))
    except FileNotFoundError:
        typer.echo("Error: no review file. Run 'gaia review' first.", err=True)
        raise typer.Exit(1)

    # 2. Extract beliefs from infer result
    beliefs = {
        name: var_data["belief"]
        for name, var_data in infer_result["variables"].items()
        if var_data.get("belief") is not None
    }

    # 3. Convert to v2 models
    data = convert_to_v2(
        pkg=pkg,
        review=review,
        beliefs=beliefs,
        bp_run_id=infer_result.get("bp_run_id", "unknown"),
    )

    # 4. Initialize v2 stores
    content = LanceContentStore(db_path)
    graph = KuzuGraphStore(f"{db_path}/kuzu")
    await graph.initialize_schema()

    # 5. Idempotent cleanup
    await content.delete_package(data.package.package_id)
    await graph.delete_package(data.package.package_id)

    # 6. Write LanceDB
    await content.write_closures(data.closures)
    await content.write_chains(data.chains)
    if data.probabilities:
        await content.write_probabilities(data.probabilities)
    if data.belief_snapshots:
        await content.write_belief_snapshots(data.belief_snapshots)

    # 7. Write Kuzu
    await graph.write_topology(data.closures, data.chains)
    if data.belief_snapshots:
        await graph.update_beliefs({
            s.closure_id: s.belief for s in data.belief_snapshots
        })

    # 8. Embeddings (optional)
    n_embeddings = 0
    try:
        import litellm

        pairs = [(c.closure_id, c.content) for c in data.closures if c.content.strip()]
        if pairs:
            ids, texts = zip(*pairs)
            response = litellm.embedding(model="text-embedding-3-small", input=list(texts))
            n_embeddings = len(response.data)
            # Future: write to v2 VectorStore
    except Exception as e:
        typer.echo(f"  Skipped embeddings: {e}")

    # 9. Write receipt
    import json
    from datetime import datetime, timezone

    publish_dir.mkdir(parents=True, exist_ok=True)
    receipt = {
        "version": 1,
        "package_id": data.package.package_id,
        "published_at": datetime.now(timezone.utc).isoformat(),
        "db_path": db_path,
        "stats": {
            "closures": len(data.closures),
            "chains": len(data.chains),
            "probabilities": len(data.probabilities),
            "belief_snapshots": len(data.belief_snapshots),
            "embeddings": n_embeddings,
        },
        "closure_ids": [c.closure_id for c in data.closures],
        "chain_ids": [ch.chain_id for ch in data.chains],
    }
    (publish_dir / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2)
    )

    emb_str = f"\n  Embeddings: {n_embeddings}" if n_embeddings else ""
    typer.echo(
        f"Published {pkg.name} to v2 storage:\n"
        f"  Closures: {len(data.closures)} written to LanceDB ({db_path})\n"
        f"  Chains: {len(data.chains)} written to LanceDB + Kuzu"
        f"{emb_str}"
    )

    await graph.close()
```

**Step 2: Update tests/cli/test_publish.py**

Update existing publish tests to work with the new v2 flow. Tests should verify:
- `receipt.json` is written
- Closures are stored in v2 `closures` table (not v1 `nodes`)
- Cross-package publish doesn't collide (3 packages, same DB)
- Idempotent re-publish

**Step 3: Run tests**

Run: `pytest tests/cli/test_publish.py -v`
Expected: PASS

**Step 4: Commit**

```bash
git add cli/main.py tests/cli/test_publish.py
git commit -m "feat: rewrite publish --local to use v2 storage models"
```

---

## Task 11: End-to-end integration test

**Files:**
- Create: `tests/cli/test_pipeline_e2e.py`

**Step 1: Write E2E test**

```python
# tests/cli/test_pipeline_e2e.py
"""End-to-end test: build → review(mock) → infer → publish --local for all 3 packages."""
import json
from pathlib import Path

import pytest

from libs.storage_v2.lance_content_store import LanceContentStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "gaia_language_packages"
GALILEO_DIR = FIXTURES / "galileo_falling_bodies"
NEWTON_DIR = FIXTURES / "newton_principia"
EINSTEIN_DIR = FIXTURES / "einstein_gravity"


def _run_pipeline(pkg_path: Path, db_path: str):
    """Run build → review(mock) → infer → publish --local."""
    from typer.testing import CliRunner
    from cli.main import app

    runner = CliRunner()

    result = runner.invoke(app, ["build", str(pkg_path)])
    assert result.exit_code == 0, f"build failed: {result.output}"

    result = runner.invoke(app, ["review", str(pkg_path), "--mock"])
    assert result.exit_code == 0, f"review failed: {result.output}"

    result = runner.invoke(app, ["infer", str(pkg_path)])
    assert result.exit_code == 0, f"infer failed: {result.output}"

    result = runner.invoke(app, ["publish", str(pkg_path), "--local", "--db-path", db_path])
    assert result.exit_code == 0, f"publish failed: {result.output}"


def test_galileo_full_pipeline(tmp_path):
    """Galileo: build → review → infer → publish."""
    db_path = str(tmp_path / "db")
    _run_pipeline(GALILEO_DIR, db_path)

    # Verify receipt
    receipt = json.loads((GALILEO_DIR / ".gaia" / "publish" / "receipt.json").read_text())
    assert receipt["package_id"] == "galileo_falling_bodies"
    assert receipt["stats"]["closures"] > 0


async def test_three_packages_no_id_collision(tmp_path):
    """All 3 packages published to same DB should not collide."""
    db_path = str(tmp_path / "db")

    _run_pipeline(GALILEO_DIR, db_path)
    _run_pipeline(NEWTON_DIR, db_path)
    _run_pipeline(EINSTEIN_DIR, db_path)

    # Verify all closures coexist
    store = LanceContentStore(db_path)
    all_closures = await store.list_closures()

    galileo_closures = [c for c in all_closures if c.source_package_id == "galileo_falling_bodies"]
    newton_closures = [c for c in all_closures if c.source_package_id == "newton_principia"]
    einstein_closures = [c for c in all_closures if c.source_package_id == "einstein_gravity"]

    assert len(galileo_closures) > 0
    assert len(newton_closures) > 0
    assert len(einstein_closures) > 0

    # No duplicate closure_ids
    all_ids = [c.closure_id for c in all_closures]
    assert len(all_ids) == len(set(all_ids))


def test_idempotent_republish(tmp_path):
    """Publishing same package twice should not create duplicates."""
    db_path = str(tmp_path / "db")
    _run_pipeline(GALILEO_DIR, db_path)
    _run_pipeline(GALILEO_DIR, db_path)

    receipt = json.loads((GALILEO_DIR / ".gaia" / "publish" / "receipt.json").read_text())
    assert receipt["stats"]["closures"] > 0
```

**Step 2: Run E2E tests**

Run: `pytest tests/cli/test_pipeline_e2e.py -v`
Expected: PASS

**Step 3: Clean up fixture .gaia directories**

After E2E tests, clean up any `.gaia/` directories left in fixture packages:

```bash
rm -rf tests/fixtures/gaia_language_packages/galileo_falling_bodies/.gaia/
rm -rf tests/fixtures/gaia_language_packages/newton_principia/.gaia/
rm -rf tests/fixtures/gaia_language_packages/einstein_gravity/.gaia/
```

Consider using `tmp_path` copies of fixtures in the E2E test to avoid this.

**Step 4: Run full test suite**

Run: `pytest -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add tests/cli/test_pipeline_e2e.py
git commit -m "test: add E2E pipeline test for build → review → infer → publish"
```

---

## Task 12: Update `gaia search` and `gaia show` for v2

**Files:**
- Modify: `cli/main.py` (search and show commands)

**Step 1: Identify search/show commands**

Read the current `search()` and `show()` implementations in `cli/main.py`. They currently query v1 `nodes` table. Update to query v2 `closures` table via `LanceContentStore`.

**Step 2: Update search to use v2**

Replace v1 `LanceStore` usage with v2 `LanceContentStore.search_bm25()`.

**Step 3: Update show to use v2**

Replace v1 node/edge lookup with v2 closure/chain lookup via `LanceContentStore.get_closure()` and `get_chains_by_module()`.

**Step 4: Test**

Run: `pytest tests/cli/ -v`
Expected: PASS

**Step 5: Commit**

```bash
git add cli/main.py
git commit -m "feat: update search and show commands to use v2 storage"
```

---

## Summary

| Task | Description | New Files | Modified Files |
|------|-------------|-----------|----------------|
| 1 | Module.title field | — | `models.py`, fixture YAMLs |
| 2 | delete_package() | — | v2 ABCs + implementations |
| 3 | Manifest serialization | `cli/manifest.py` | — |
| 4 | Single package.md | — | `build_store.py` |
| 5 | Build writes manifest | — | `cli/main.py` |
| 6 | Review prompt + client | `cli/prompts/review_system.md` | `cli/llm_client.py` |
| 7 | Review command + merge | — | `cli/main.py`, `cli/review_store.py` |
| 8 | Infer reads manifest | `cli/infer_store.py` | `cli/main.py` |
| 9 | lang_to_v2 converter | `cli/lang_to_v2.py` | — |
| 10 | Publish rewrite | — | `cli/main.py` |
| 11 | E2E integration test | `tests/cli/test_pipeline_e2e.py` | — |
| 12 | Search/show v2 | — | `cli/main.py` |

**Dependency order:** 1 → 4, 2 → 10, 3 → 5 → 8 → 10, 4 → 6 → 7, 9 → 10 → 11
