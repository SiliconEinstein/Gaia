# Gaia Research M2 Explore Scan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `gaia research explore --mode scan` consume normalized `gaia search lkm` JSON and write a package-native landscape artifact without pulling papers or writing source.

**Architecture:** Keep `gaia research` as a thin orchestration layer. M2 reads one or more saved/stdin LKM search envelopes, reuses the existing deterministic paper-lead builder from `gaia.lkm_explorer.engine.landscape`, and wraps the result into `.gaia/research/landscapes/*.json`. M2b will later port the selected deterministic utilities out of `gaia-lkm-explore`; M2 should not duplicate that logic.

**Tech Stack:** Typer list options, JSON/stdin parsing, package-local artifact writer, existing `LandscapeBatch` / `build_landscape`, pytest CLI tests.

---

## Success Criteria

- `gaia research explore <pkg> --mode scan --search-json <file>` writes one `.gaia/research/landscapes/scan-*.json` artifact.
- `--search-json -` reads normalized search JSON from stdin.
- The artifact includes query provenance, paper leads, pull candidates, candidate coverage gaps, a breadth-first coverage map, and candidate focuses.
- Pull budget defaults to `0`.
- `.gaia/lkm_packages/` is not created unless a later explicit pull milestone implements that behavior.
- Candidate focuses are marked `status: candidate` and are not written to `.gaia/inquiry/state.json`.
- The scan appends an `explore.scan.completed` event with artifact path and stats.
- The original M1 `--dry-run` planning path still works when no `--search-json` input is supplied.

## File Structure

- Modify `gaia/engine/research/artifacts.py`: add package-local artifact writer and manifest artifact index.
- Create `gaia/engine/research/landscape.py`: convert LKM search batches into package-native research landscape payloads.
- Modify `gaia/engine/research/__init__.py`: export M2 helpers.
- Modify `gaia/cli/commands/research.py`: add `--search-json`, `--query`, `--source`, `--out`, stdin parsing, and completed scan events.
- Modify `tests/cli/test_research.py`: add M2 CLI behavior tests.

## Task 1: Failing CLI Tests

**Files:**
- Modify: `tests/cli/test_research.py`

- [ ] **Step 1: Add normalized search fixture helpers**

Create small in-test envelopes with this shape:

```python
{
    "schema_version": 1,
    "query": {"text": "free fall", "provider": "lkm", "kind": "knowledge"},
    "results": [
        {
            "id": "lkm:bohrium:n1",
            "title": "Claim one",
            "source": {
                "paper_id": "P1",
                "paper_title": "Paper One",
                "doi": "10.1/example",
                "index_id": "bohrium",
            },
            "rank": {"score": 0.9},
        }
    ],
}
```

- [ ] **Step 2: Assert file-based scan artifact**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_scan_consumes_search_json_and_writes_landscape -q
```

Expected before implementation: fail because `--search-json` is not accepted.

- [ ] **Step 3: Assert stdin scan artifact**

Run:

```bash
uv run pytest tests/cli/test_research.py::test_research_scan_reads_search_json_from_stdin -q
```

Expected before implementation: fail because `--search-json -` is not implemented.

## Task 2: Artifact Writer

**Files:**
- Modify: `gaia/engine/research/artifacts.py`

- [ ] **Step 1: Add `write_research_artifact`**

Implement:

```python
def write_research_artifact(
    pkg: ResearchPackage,
    category: str,
    stem: str,
    payload: dict[str, Any],
    *,
    out: str | Path | None = None,
) -> Path:
    ...
```

It writes JSON with a trailing newline, stores default files under `.gaia/research/<category>/`, and appends artifact metadata to `manifest["artifacts"]`.

## Task 3: Landscape Payload Builder

**Files:**
- Create: `gaia/engine/research/landscape.py`

- [ ] **Step 1: Wrap existing paper-lead landscape**

Implement:

```python
@dataclass(frozen=True)
class ScanBatch:
    search_results: dict[str, Any]
    query: str | None = None
    source_qid: str | None = None
    path: str | None = None

def build_research_landscape(batches: list[ScanBatch], *, pull_budget: int = 0) -> dict[str, Any]:
    ...
```

The payload must include `kind: "research_landscape"`, `action: "explore.scan"`, `pull_budget`, `query_provenance`, `paper_leads`, `pull_candidates`, `candidate_coverage_gaps`, `coverage_map`, and `candidate_focuses`.

## Task 4: CLI Integration

**Files:**
- Modify: `gaia/cli/commands/research.py`

- [ ] **Step 1: Add scan input options**

Add repeatable options:

```python
search_json: list[str] | None = typer.Option(None, "--search-json")
query: list[str] | None = typer.Option(None, "--query")
source: list[str] | None = typer.Option(None, "--source")
out: str | None = typer.Option(None, "--out")
```

- [ ] **Step 2: Preserve dry-run planning path**

If no search JSON is supplied, require `--dry-run` and emit the existing `explore.scan.planned` event.

- [ ] **Step 3: Write completed scan artifact**

If search JSON is supplied, parse all batches, build the research landscape, write it, and append `explore.scan.completed`.

## Task 5: Verification And Commit

**Files:**
- Verify all touched M2 files.

- [ ] **Step 1: Run targeted checks**

Run:

```bash
uv run pytest tests/cli/test_research.py -q
uv run pytest tests/test_alpha0_docs.py -q
uv run ruff check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py
uv run ruff format --check gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py
uv run mypy gaia/engine/research gaia/cli/commands/research.py tests/cli/test_research.py
git diff --check
```

Expected: all pass.

- [ ] **Step 2: Commit**

```bash
git add docs/superpowers/plans/2026-06-01-gaia-research-m2-explore-scan.md \
  gaia/engine/research \
  gaia/cli/commands/research.py \
  tests/cli/test_research.py
git commit -m "feat(research): write scan landscape artifacts"
```
