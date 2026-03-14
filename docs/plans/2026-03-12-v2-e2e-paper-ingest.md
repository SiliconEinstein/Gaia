# Storage V2 E2E: Paper Ingest Pipeline

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end pipeline that converts XML paper reasoning chains into v2 storage models, uploads them through server API endpoints, and verifies reads — with unimplemented server features marked as xfail.

**Architecture:** A Python script parses 3 papers' `_combine.xml` files into v2 fixture JSON. New FastAPI v2 routes expose ingest + read endpoints backed by real StorageManager v2 (LanceDB + Kuzu). Integration tests upload fixtures via HTTP and verify all reads.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, LanceDB, Kuzu, pytest + httpx AsyncClient

---

## File Structure

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `scripts/papers_to_v2.py` | Parse XML papers → v2 fixture JSON |
| Create | `tests/fixtures/storage_v2/papers/` | Output directory for generated fixtures |
| Create | `services/gateway/routes/v2.py` | V2 API routes (ingest + read) |
| Modify | `services/gateway/deps.py` | Add StorageManager v2 initialization |
| Modify | `services/gateway/app.py` | Mount v2 router |
| Create | `tests/integration/test_v2_e2e.py` | E2E integration tests |
| Create | `docs/plans/2026-03-12-server-v2-commit-review-merge.md` | Future scope doc |

---

## Chunk 1: XML → V2 Fixture Conversion Script

### Task 1: XML Parser + V2 Model Converter

**Files:**
- Create: `scripts/papers_to_v2.py`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/package.json`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/modules.json`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/knowledge.json`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/chains.json`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/probabilities.json`
- Create: `tests/fixtures/storage_v2/papers/<doi_slug>/beliefs.json`

**Context:**

Each paper directory in `tests/fixtures/papers/` contains:
- `conclusion_N_reasoning_chain_combine.xml` — full inference unit with `<premises>`, `<reasoning>`, `<conclusion>`
- `conclusion_N.xml` — standalone conclusion text
- `select_conclusion.xml` — list of all conclusions

The `_combine.xml` format:
```xml
<inference_unit>
  <notations>...</notations>
  <premises>
    <premise id="1" title="...">text <ref>[N]</ref></premise>
    ...
  </premises>
  <reasoning>
    <step title="...">text [@premise-N, @premise-M]</step>
    ...
  </reasoning>
  <conclusion title="...">text</conclusion>
</inference_unit>
```

**Mapping rules:**
- 1 paper → 1 Package (package_id = DOI slug, e.g. `paper_10_1038332139a0`)
- 1 paper → 1 Module (role = "reasoning")
- Each unique premise (deduped by title across conclusions) → Knowledge (type = "claim", prior = 0.7)
- Each conclusion → Knowledge (type = "claim", prior = 0.5)
- Each reasoning chain → Chain (type = "deduction")
- Each `<step>` → ChainStep with:
  - `premises`: resolved from `@premise-N` refs in step text
  - `reasoning`: step text
  - `conclusion`: the conclusion Knowledge of that chain (or next step's ref if multi-step chains feed into each other — for simplicity, all steps in a chain point to the chain's final conclusion)
- Mock probabilities: each chain step gets ProbabilityRecord(value=0.7, source="author")
- Mock beliefs: each knowledge item gets BeliefSnapshot(belief=prior, bp_run_id="mock")

- [ ] **Step 1: Write the conversion script**

```python
#!/usr/bin/env python3
"""Convert paper XML reasoning chains to v2 storage fixture JSON.

Usage:
    python scripts/papers_to_v2.py

Reads from: tests/fixtures/papers/*/conclusion_*_reasoning_chain_combine.xml
Writes to:  tests/fixtures/storage_v2/papers/<doi_slug>/{package,modules,knowledge,chains,probabilities,beliefs}.json
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PAPERS_DIR = Path("tests/fixtures/papers")
OUTPUT_DIR = Path("tests/fixtures/storage_v2/papers")

NOW = datetime(2026, 3, 12, tzinfo=timezone.utc).isoformat()


def doi_to_slug(dirname: str) -> str:
    """Convert DOI directory name to a safe package_id slug."""
    return "paper_" + re.sub(r"[^a-zA-Z0-9]", "_", dirname).strip("_").lower()


def parse_combine_xml(path: Path) -> dict:
    """Parse a conclusion_N_reasoning_chain_combine.xml file.

    Returns dict with keys: premises (list), reasoning_steps (list), conclusion (dict).
    """
    tree = ET.parse(path)
    root = tree.getroot()

    premises = []
    for p in root.findall(".//premise"):
        text = "".join(p.itertext()).strip()
        # Remove <ref> content from the text
        for ref in p.findall("ref"):
            ref_text = ref.text or ""
            text = text.replace(ref_text, "").strip()
        premises.append({
            "id": p.get("id"),
            "title": p.get("title", ""),
            "content": text,
        })

    # Also handle <assumption> tags (same structure as premise)
    for a in root.findall(".//assumption"):
        text = "".join(a.itertext()).strip()
        for ref in a.findall("ref"):
            ref_text = ref.text or ""
            text = text.replace(ref_text, "").strip()
        premises.append({
            "id": a.get("id"),
            "title": a.get("title", ""),
            "content": text,
        })

    steps = []
    for s in root.findall(".//reasoning/step"):
        text = "".join(s.itertext()).strip()
        # Extract @premise-N references
        refs = re.findall(r"@premise-(\d+)", text)
        steps.append({
            "title": s.get("title", ""),
            "text": text,
            "premise_refs": refs,
        })

    conclusion_el = root.find(".//conclusion")
    conclusion = {
        "title": conclusion_el.get("title", "") if conclusion_el is not None else "",
        "content": "".join(conclusion_el.itertext()).strip() if conclusion_el is not None else "",
    }

    return {"premises": premises, "reasoning_steps": steps, "conclusion": conclusion}


def convert_paper(paper_dir: Path) -> dict:
    """Convert one paper directory to v2 fixture data.

    Returns dict with keys: package, modules, knowledge, chains, probabilities, beliefs.
    """
    slug = doi_to_slug(paper_dir.name)
    module_id = f"{slug}.reasoning"

    # Collect all combine XMLs
    combine_files = sorted(paper_dir.glob("conclusion_*_reasoning_chain_combine.xml"))
    if not combine_files:
        return None

    # Parse all chains, dedup premises by title
    all_premises: dict[str, dict] = {}  # title -> premise data
    chain_data: list[dict] = []  # (chain_index, parsed data)

    for i, f in enumerate(combine_files, 1):
        parsed = parse_combine_xml(f)
        # Dedup premises by title
        local_id_to_global: dict[str, str] = {}
        for p in parsed["premises"]:
            title = p["title"]
            if title not in all_premises:
                kid = f"{slug}/{_slugify(title)}"
                all_premises[title] = {**p, "knowledge_id": kid}
            local_id_to_global[p["id"]] = all_premises[title]["knowledge_id"]
        chain_data.append({
            "index": i,
            "parsed": parsed,
            "local_to_global": local_id_to_global,
        })

    # Build Knowledge items (premises + conclusions)
    knowledge_items = []
    for title, p in all_premises.items():
        knowledge_items.append({
            "knowledge_id": p["knowledge_id"],
            "version": 1,
            "type": "claim",
            "content": p["content"],
            "prior": 0.7,
            "keywords": [],
            "source_package_id": slug,
            "source_package_version": "1.0.0",
            "source_module_id": module_id,
            "created_at": NOW,
            "embedding": None,
        })

    # Add conclusion knowledge items + build chains
    chains = []
    for cd in chain_data:
        parsed = cd["parsed"]
        local_to_global = cd["local_to_global"]
        conc_title = parsed["conclusion"]["title"]
        conc_kid = f"{slug}/{_slugify(conc_title)}"

        # Add conclusion as knowledge (dedup)
        if not any(k["knowledge_id"] == conc_kid for k in knowledge_items):
            knowledge_items.append({
                "knowledge_id": conc_kid,
                "version": 1,
                "type": "claim",
                "content": parsed["conclusion"]["content"],
                "prior": 0.5,
                "keywords": [],
                "source_package_id": slug,
                "source_package_version": "1.0.0",
                "source_module_id": module_id,
                "created_at": NOW,
                "embedding": None,
            })

        # Build chain steps
        chain_id = f"{slug}.reasoning.chain_{cd['index']}"
        steps = []
        for si, step in enumerate(parsed["reasoning_steps"]):
            premise_refs = []
            for ref_id in step["premise_refs"]:
                if ref_id in local_to_global:
                    premise_refs.append({
                        "knowledge_id": local_to_global[ref_id],
                        "version": 1,
                    })
            steps.append({
                "step_index": si,
                "premises": premise_refs,
                "reasoning": step["text"],
                "conclusion": {"knowledge_id": conc_kid, "version": 1},
            })

        if steps:
            chains.append({
                "chain_id": chain_id,
                "module_id": module_id,
                "package_id": slug,
                "package_version": "1.0.0",
                "type": "deduction",
                "steps": steps,
            })

    # Build module
    modules = [{
        "module_id": module_id,
        "package_id": slug,
        "package_version": "1.0.0",
        "name": "reasoning",
        "role": "reasoning",
        "imports": [],
        "chain_ids": [c["chain_id"] for c in chains],
        "export_ids": [k["knowledge_id"] for k in knowledge_items
                       if k["prior"] == 0.5],  # conclusions are exports
    }]

    # Build package
    package = {
        "package_id": slug,
        "name": slug,
        "version": "1.0.0",
        "description": f"Reasoning chains extracted from paper {paper_dir.name}",
        "modules": [module_id],
        "exports": modules[0]["export_ids"],
        "submitter": "paper_extractor",
        "submitted_at": NOW,
        "status": "merged",
    }

    # Mock probabilities (0.7 for each step)
    probabilities = []
    for chain in chains:
        for step in chain["steps"]:
            probabilities.append({
                "chain_id": chain["chain_id"],
                "step_index": step["step_index"],
                "value": 0.7,
                "source": "author",
                "source_detail": None,
                "recorded_at": NOW,
            })

    # Mock beliefs (belief = prior for each knowledge item)
    beliefs = []
    for k in knowledge_items:
        beliefs.append({
            "knowledge_id": k["knowledge_id"],
            "version": 1,
            "belief": k["prior"],
            "bp_run_id": "mock_bp_run",
            "computed_at": NOW,
        })

    return {
        "package": package,
        "modules": modules,
        "knowledge": knowledge_items,
        "chains": chains,
        "probabilities": probabilities,
        "beliefs": beliefs,
    }


def _slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80].strip("_")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    papers = sorted(PAPERS_DIR.iterdir())
    for paper_dir in papers:
        if not paper_dir.is_dir() or paper_dir.name == "images":
            continue
        result = convert_paper(paper_dir)
        if result is None:
            print(f"SKIP {paper_dir.name}: no combine XMLs found")
            continue

        out_dir = OUTPUT_DIR / doi_to_slug(paper_dir.name)
        out_dir.mkdir(parents=True, exist_ok=True)

        for key, data in result.items():
            path = out_dir / f"{key}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        n_k = len(result["knowledge"])
        n_c = len(result["chains"])
        print(f"OK {paper_dir.name} -> {out_dir.name}: {n_k} knowledge, {n_c} chains")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the script and verify output**

Run: `python scripts/papers_to_v2.py`

Expected: 3 paper directories created under `tests/fixtures/storage_v2/papers/`, each with 6 JSON files. Verify:
- Each `package.json` has `package_id`, `version`, `status="merged"`
- Each `knowledge.json` has items with `knowledge_id`, `content`, `prior`
- Each `chains.json` has chains with `steps` containing `premises` and `conclusion` refs
- All `knowledge_id` refs in chains resolve to items in `knowledge.json`

- [ ] **Step 3: Validate fixtures load as v2 models**

Write a quick validation in the script (or run interactively):
```python
# At end of main(), validate each fixture loads as Pydantic models
from libs.storage_v2.models import Package, Module, Knowledge, Chain, ProbabilityRecord, BeliefSnapshot
for paper_dir in OUTPUT_DIR.iterdir():
    pkg = Package.model_validate_json((paper_dir / "package.json").read_text())
    mods = [Module.model_validate(m) for m in json.loads((paper_dir / "modules.json").read_text())]
    knowledge = [Knowledge.model_validate(k) for k in json.loads((paper_dir / "knowledge.json").read_text())]
    chains = [Chain.model_validate(c) for c in json.loads((paper_dir / "chains.json").read_text())]
    print(f"  Validated {paper_dir.name}: {pkg.package_id}")
```

- [ ] **Step 4: Commit**

```bash
git add scripts/papers_to_v2.py tests/fixtures/storage_v2/papers/
git commit -m "feat: add paper XML to v2 fixture conversion script"
```

---

## Chunk 2: Server V2 API Endpoints

### Task 2: V2 Dependencies Initialization

**Files:**
- Modify: `services/gateway/deps.py`

**Context:** The existing `Dependencies` class initializes v1 `StorageManager` from `libs.storage`. We need to add v2 `StorageManager` from `libs.storage_v2` alongside it.

- [ ] **Step 1: Write failing test**

Create `tests/integration/test_v2_e2e.py` with a minimal fixture that verifies v2 deps initialize:

```python
"""V2 storage end-to-end integration tests.

Tests exercise the full v2 API through HTTP endpoints backed by real
LanceDB + Kuzu storage (no mocks).
"""

import pytest
from httpx import ASGITransport, AsyncClient

from services.gateway.app import create_app
from services.gateway.deps import Dependencies
from libs.storage import StorageConfig as V1StorageConfig
from libs.storage_v2.config import StorageConfig as V2StorageConfig


@pytest.fixture
async def v2_client(tmp_path):
    """Create app with real v2 storage (LanceDB + Kuzu on disk)."""
    v1_config = V1StorageConfig(lancedb_path=str(tmp_path / "lance_v1"))
    v2_config = V2StorageConfig(
        lancedb_path=str(tmp_path / "lance_v2"),
        graph_backend="kuzu",
        kuzu_path=str(tmp_path / "kuzu_v2"),
    )
    dep = Dependencies(config=v1_config, v2_config=v2_config)
    dep.initialize(v1_config)
    # v1 graph not needed for v2 tests
    dep.storage.graph = None

    app = create_app(dependencies=dep)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    await dep.cleanup()


class TestV2Health:
    async def test_v2_storage_initialized(self, v2_client):
        resp = await v2_client.get("/health")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Health -xvs`
Expected: FAIL — `Dependencies.__init__()` doesn't accept `v2_config`

- [ ] **Step 3: Add v2 storage to Dependencies**

Modify `services/gateway/deps.py`:

```python
# Add import at top:
from libs.storage_v2.config import StorageConfig as V2StorageConfig
from libs.storage_v2.manager import StorageManager as V2StorageManager

# In Dependencies.__init__:
def __init__(self, config: StorageConfig | None = None, v2_config: V2StorageConfig | None = None):
    self.config = config or StorageConfig()
    self.v2_config = v2_config
    self.storage: StorageManager | None = None
    self.storage_v2: V2StorageManager | None = None
    # ... rest unchanged

# In Dependencies.initialize, add after existing init:
    if self.v2_config is not None:
        self.storage_v2 = V2StorageManager(self.v2_config)
        await_or_sync = self.storage_v2  # will be initialized in startup event

# In Dependencies.cleanup:
    if self.storage_v2:
        await self.storage_v2.close()
```

Note: Since `V2StorageManager.initialize()` is async, it must be called in the FastAPI startup event. Update `app.py` startup:

```python
@app.on_event("startup")
async def startup():
    if active_deps.storage is None:
        active_deps.initialize()
    if active_deps.storage_v2 is not None and active_deps.storage_v2.content_store is None:
        await active_deps.storage_v2.initialize()
```

Also propagate v2 in `create_app` when custom dependencies injected:
```python
if dependencies is not None:
    deps.storage_v2 = dependencies.storage_v2
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Health -xvs`
Expected: PASS

- [ ] **Step 5: Run existing tests to verify no regression**

Run: `pytest tests/integration/test_e2e.py -x -q`
Expected: All pass (v2 is additive, doesn't break v1)

- [ ] **Step 6: Commit**

```bash
git add services/gateway/deps.py services/gateway/app.py tests/integration/test_v2_e2e.py
git commit -m "feat: add v2 StorageManager to Dependencies + app startup"
```

### Task 3: V2 Ingest Endpoint

**Files:**
- Create: `services/gateway/routes/v2.py`
- Modify: `services/gateway/app.py` (mount router)

**Context:** The ingest endpoint accepts a full package payload and calls `StorageManager.ingest_package()`. It also accepts optional probabilities and beliefs to write via passthrough methods.

- [ ] **Step 1: Write failing test**

Add to `tests/integration/test_v2_e2e.py`:

```python
import json
from pathlib import Path

PAPER_FIXTURES = Path("tests/fixtures/storage_v2/papers")


def _load_paper_fixture(slug: str) -> dict:
    """Load a paper's v2 fixture JSON files."""
    d = PAPER_FIXTURES / slug
    return {
        "package": json.loads((d / "package.json").read_text()),
        "modules": json.loads((d / "modules.json").read_text()),
        "knowledge": json.loads((d / "knowledge.json").read_text()),
        "chains": json.loads((d / "chains.json").read_text()),
        "probabilities": json.loads((d / "probabilities.json").read_text()),
        "beliefs": json.loads((d / "beliefs.json").read_text()),
    }


class TestV2Ingest:
    async def test_ingest_paper_package(self, v2_client):
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        assert len(slugs) >= 1, "Need at least 1 paper fixture"

        data = _load_paper_fixture(slugs[0])
        resp = await v2_client.post("/v2/packages/ingest", json=data)
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["package_id"] == data["package"]["package_id"]
        assert body["status"] == "ingested"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Ingest -xvs`
Expected: FAIL — 404 (route doesn't exist)

- [ ] **Step 3: Create v2 routes**

Create `services/gateway/routes/v2.py`:

```python
"""V2 storage API routes — package ingest + read endpoints."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from libs.storage_v2.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    KnowledgeEmbedding,
    Module,
    Package,
    ProbabilityRecord,
)
from services.gateway.deps import deps

router = APIRouter(prefix="/v2", tags=["v2"])


class IngestRequest(BaseModel):
    package: dict
    modules: list[dict]
    knowledge: list[dict]
    chains: list[dict]
    probabilities: list[dict] = []
    beliefs: list[dict] = []
    embeddings: list[dict] = []


class IngestResponse(BaseModel):
    package_id: str
    status: str
    knowledge_count: int
    chain_count: int


@router.post("/packages/ingest", response_model=IngestResponse, status_code=201)
async def ingest_package(request: IngestRequest):
    """Ingest a complete package into v2 storage."""
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")

    # Parse models
    pkg = Package.model_validate(request.package)
    modules = [Module.model_validate(m) for m in request.modules]
    knowledge_items = [Knowledge.model_validate(k) for k in request.knowledge]
    chains = [Chain.model_validate(c) for c in request.chains]
    embeddings = [KnowledgeEmbedding.model_validate(e) for e in request.embeddings] or None

    # Ingest (state machine: preparing → committed)
    await deps.storage_v2.ingest_package(
        package=pkg,
        modules=modules,
        knowledge_items=knowledge_items,
        chains=chains,
        embeddings=embeddings if embeddings else None,
    )

    # Write supplementary data
    if request.probabilities:
        records = [ProbabilityRecord.model_validate(p) for p in request.probabilities]
        await deps.storage_v2.add_probabilities(records)
    if request.beliefs:
        snapshots = [BeliefSnapshot.model_validate(b) for b in request.beliefs]
        await deps.storage_v2.write_beliefs(snapshots)

    return IngestResponse(
        package_id=pkg.package_id,
        status="ingested",
        knowledge_count=len(knowledge_items),
        chain_count=len(chains),
    )
```

Mount in `services/gateway/app.py`:
```python
from .routes.v2 import router as v2_router
# ...
app.include_router(v2_router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Ingest -xvs`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add services/gateway/routes/v2.py services/gateway/app.py
git commit -m "feat: add POST /v2/packages/ingest endpoint"
```

### Task 4: V2 Read Endpoints

**Files:**
- Modify: `services/gateway/routes/v2.py`

- [ ] **Step 1: Write failing tests**

Add to `tests/integration/test_v2_e2e.py`:

```python
class TestV2Read:
    @pytest.fixture(autouse=True)
    async def _ingest_first_paper(self, v2_client):
        """Ingest the first paper fixture before each test."""
        slugs = [d.name for d in sorted(PAPER_FIXTURES.iterdir()) if d.is_dir()]
        self._fixture = _load_paper_fixture(slugs[0])
        resp = await v2_client.post("/v2/packages/ingest", json=self._fixture)
        assert resp.status_code == 201

    async def test_get_package(self, v2_client):
        pkg_id = self._fixture["package"]["package_id"]
        resp = await v2_client.get(f"/v2/packages/{pkg_id}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["package_id"] == pkg_id
        assert body["status"] == "merged"

    async def test_get_package_not_found(self, v2_client):
        resp = await v2_client.get("/v2/packages/nonexistent")
        assert resp.status_code == 404

    async def test_get_knowledge(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["knowledge_id"] == kid
        assert body["content"] == self._fixture["knowledge"][0]["content"]

    async def test_get_knowledge_versions(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}/versions")
        assert resp.status_code == 200
        versions = resp.json()
        assert len(versions) >= 1
        assert versions[0]["knowledge_id"] == kid

    async def test_get_module(self, v2_client):
        mid = self._fixture["modules"][0]["module_id"]
        resp = await v2_client.get(f"/v2/modules/{mid}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["module_id"] == mid
        assert body["role"] == "reasoning"

    async def test_get_module_chains(self, v2_client):
        mid = self._fixture["modules"][0]["module_id"]
        resp = await v2_client.get(f"/v2/modules/{mid}/chains")
        assert resp.status_code == 200
        chains = resp.json()
        assert len(chains) == len(self._fixture["chains"])
        # Verify chain structure
        for chain in chains:
            assert "chain_id" in chain
            assert "steps" in chain
            assert len(chain["steps"]) > 0

    async def test_get_chain_probabilities(self, v2_client):
        chain_id = self._fixture["chains"][0]["chain_id"]
        resp = await v2_client.get(f"/v2/chains/{chain_id}/probabilities")
        assert resp.status_code == 200
        probs = resp.json()
        assert len(probs) > 0
        assert probs[0]["chain_id"] == chain_id
        assert probs[0]["source"] == "author"

    async def test_get_knowledge_beliefs(self, v2_client):
        kid = self._fixture["knowledge"][0]["knowledge_id"]
        resp = await v2_client.get(f"/v2/knowledge/{kid}/beliefs")
        assert resp.status_code == 200
        beliefs = resp.json()
        assert len(beliefs) >= 1
        assert beliefs[0]["knowledge_id"] == kid
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Read -xvs`
Expected: FAIL — 404 / 405 for all read routes

- [ ] **Step 3: Implement read routes**

Add to `services/gateway/routes/v2.py`:

```python
@router.get("/packages/{package_id}")
async def get_package(package_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    pkg = await deps.storage_v2.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return pkg.model_dump()


@router.get("/knowledge/{knowledge_id}")
async def get_knowledge(knowledge_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    k = await deps.storage_v2.get_knowledge(knowledge_id)
    if k is None:
        raise HTTPException(status_code=404, detail="Knowledge not found")
    return k.model_dump()


@router.get("/knowledge/{knowledge_id}/versions")
async def get_knowledge_versions(knowledge_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    versions = await deps.storage_v2.get_knowledge_versions(knowledge_id)
    return [v.model_dump() for v in versions]


@router.get("/knowledge/{knowledge_id}/beliefs")
async def get_knowledge_beliefs(knowledge_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    beliefs = await deps.storage_v2.get_belief_history(knowledge_id)
    return [b.model_dump() for b in beliefs]


@router.get("/modules/{module_id}")
async def get_module(module_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    m = await deps.storage_v2.get_module(module_id)
    if m is None:
        raise HTTPException(status_code=404, detail="Module not found")
    return m.model_dump()


@router.get("/modules/{module_id}/chains")
async def get_module_chains(module_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    chains = await deps.storage_v2.get_chains_by_module(module_id)
    return [c.model_dump() for c in chains]


@router.get("/chains/{chain_id}/probabilities")
async def get_chain_probabilities(chain_id: str):
    if deps.storage_v2 is None:
        raise HTTPException(status_code=503, detail="V2 storage not initialized")
    probs = await deps.storage_v2.get_probability_history(chain_id)
    return [p.model_dump() for p in probs]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2Read -xvs`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add services/gateway/routes/v2.py tests/integration/test_v2_e2e.py
git commit -m "feat: add v2 read endpoints (package, knowledge, module, chain)"
```

---

## Chunk 3: Full E2E Tests + Multi-Package + Future Scope

### Task 5: Multi-Package Ingest and Cross-Read Test

**Files:**
- Modify: `tests/integration/test_v2_e2e.py`

- [ ] **Step 1: Write test**

```python
class TestV2MultiPackageE2E:
    """Ingest all 3 paper packages and verify cross-package reads."""

    async def test_ingest_all_papers_then_read(self, v2_client):
        slugs = sorted([d.name for d in PAPER_FIXTURES.iterdir() if d.is_dir()])
        assert len(slugs) == 3, f"Expected 3 paper fixtures, got {len(slugs)}"

        # Ingest all 3
        for slug in slugs:
            data = _load_paper_fixture(slug)
            resp = await v2_client.post("/v2/packages/ingest", json=data)
            assert resp.status_code == 201, f"Ingest {slug} failed: {resp.text}"

        # Verify each package readable
        for slug in slugs:
            data = _load_paper_fixture(slug)
            pkg_id = data["package"]["package_id"]

            # Package
            resp = await v2_client.get(f"/v2/packages/{pkg_id}")
            assert resp.status_code == 200, f"Package {pkg_id} not found"

            # All knowledge items
            for k in data["knowledge"]:
                resp = await v2_client.get(f"/v2/knowledge/{k['knowledge_id']}")
                assert resp.status_code == 200, f"Knowledge {k['knowledge_id']} not found"

            # Module
            for m in data["modules"]:
                resp = await v2_client.get(f"/v2/modules/{m['module_id']}")
                assert resp.status_code == 200, f"Module {m['module_id']} not found"

                # Chains for module
                resp = await v2_client.get(f"/v2/modules/{m['module_id']}/chains")
                assert resp.status_code == 200
                chains = resp.json()
                expected = len([c for c in data["chains"] if c["module_id"] == m["module_id"]])
                assert len(chains) == expected
```

- [ ] **Step 2: Run test**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2MultiPackageE2E -xvs`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_v2_e2e.py
git commit -m "test: add multi-package v2 e2e test"
```

### Task 6: xfail Tests for Unimplemented Server Features

**Files:**
- Modify: `tests/integration/test_v2_e2e.py`

- [ ] **Step 1: Write xfail tests**

```python
class TestV2ServerCommitReviewMerge:
    """Server-side v2 commit/review/merge pipeline — NOT YET IMPLEMENTED.

    These tests document the expected API surface for server-side v2 operations.
    See docs/plans/2026-03-12-server-v2-commit-review-merge.md for design.
    """

    @pytest.mark.xfail(reason="Server-side v2 commit not implemented", strict=True)
    async def test_submit_v2_commit(self, v2_client):
        resp = await v2_client.post("/v2/commits", json={
            "operations": [
                {"type": "add_knowledge", "knowledge": {
                    "knowledge_id": "test/k1", "version": 1, "type": "claim",
                    "content": "Test claim", "prior": 0.5,
                    "source_package_id": "test", "source_module_id": "test.mod",
                    "created_at": "2026-03-12T00:00:00Z",
                }}
            ]
        })
        assert resp.status_code == 201

    @pytest.mark.xfail(reason="Server-side v2 review not implemented", strict=True)
    async def test_submit_v2_review(self, v2_client):
        resp = await v2_client.post("/v2/commits/test-commit/review")
        assert resp.status_code == 202

    @pytest.mark.xfail(reason="Server-side v2 merge not implemented", strict=True)
    async def test_merge_v2_commit(self, v2_client):
        resp = await v2_client.post("/v2/commits/test-commit/merge")
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 search not implemented", strict=True)
    async def test_v2_bm25_search(self, v2_client):
        resp = await v2_client.post("/v2/search/knowledge", json={
            "text": "superconductivity",
            "top_k": 10,
        })
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 vector search not implemented", strict=True)
    async def test_v2_vector_search(self, v2_client):
        resp = await v2_client.post("/v2/search/vector", json={
            "embedding": [0.1] * 512,
            "top_k": 10,
        })
        assert resp.status_code == 200

    @pytest.mark.xfail(reason="Server-side v2 topology search not implemented", strict=True)
    async def test_v2_topology_search(self, v2_client):
        resp = await v2_client.post("/v2/search/topology", json={
            "seed_ids": ["test/k1"],
            "hops": 2,
        })
        assert resp.status_code == 200
```

- [ ] **Step 2: Run tests**

Run: `pytest tests/integration/test_v2_e2e.py::TestV2ServerCommitReviewMerge -xvs`
Expected: All xfail (6 tests marked as expected failures)

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_v2_e2e.py
git commit -m "test: add xfail tests for unimplemented v2 server features"
```

### Task 7: Future Scope Documentation

**Files:**
- Create: `docs/plans/2026-03-12-server-v2-commit-review-merge.md`

- [ ] **Step 1: Write doc**

```markdown
# Server-Side V2 Commit/Review/Merge Pipeline

**Status:** Not yet implemented. See xfail tests in `tests/integration/test_v2_e2e.py::TestV2ServerCommitReviewMerge`.

## Current State

V2 storage currently supports:
- `POST /v2/packages/ingest` — bulk ingest (CLI-originated data)
- `GET /v2/packages/{id}`, `GET /v2/knowledge/{id}`, etc. — read endpoints

## Planned Endpoints

### Commit Workflow
- `POST /v2/commits` — submit operations (add_knowledge, add_chain, modify_knowledge, etc.)
- `GET /v2/commits/{id}` — get commit status
- `POST /v2/commits/{id}/review` — trigger async review (LLM + BP)
- `GET /v2/commits/{id}/review` — poll review status
- `GET /v2/commits/{id}/review/result` — get review result
- `POST /v2/commits/{id}/merge` — apply to storage

### Search
- `POST /v2/search/knowledge` — BM25 full-text search
- `POST /v2/search/vector` — embedding similarity search
- `POST /v2/search/topology` — graph traversal search

## Design Considerations

1. **V2 CommitEngine**: Needs to be built on top of v2 StorageManager, not v1.
   The v1 CommitEngine operates on Node/HyperEdge; v2 operates on Knowledge/Chain.

2. **Review Pipeline**: Can reuse existing operators (BP, embedding, etc.) but needs
   adapters for v2 models.

3. **Merge**: Already implemented as `StorageManager.ingest_package()` for bulk writes.
   Individual operations (modify single knowledge item) need additional methods.

4. **Search**: StorageManager already has `search_bm25()`, `search_vector()`,
   `search_topology()`. Just need HTTP route wrappers + request/response models.
```

- [ ] **Step 2: Commit**

```bash
git add docs/plans/2026-03-12-server-v2-commit-review-merge.md
git commit -m "docs: add future scope for server-side v2 commit/review/merge"
```

### Task 8: Final Verification

- [ ] **Step 1: Run full v2 e2e test suite**

Run: `pytest tests/integration/test_v2_e2e.py -v`
Expected: All passing tests PASS, all xfail tests XFAIL

- [ ] **Step 2: Run full test suite to verify no regressions**

Run: `pytest -x -q`
Expected: All existing tests still pass

- [ ] **Step 3: Lint check**

Run: `ruff check . && ruff format --check .`
Expected: Clean

- [ ] **Step 4: Commit any remaining fixes**

```bash
git add -A && git commit -m "chore: final lint/format fixes"
```
