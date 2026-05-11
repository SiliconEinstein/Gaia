# LKM Package Integration Design

**Status:** Draft  
**Author:** Claude (AI assistant)  
**Date:** 2026-05-11  
**Target:** v0.6 (Phase 1), v0.7 (Phase 2)

---

## Overview

This spec defines how Gaia integrates with the Bohrium Large Knowledge Model (LKM) as an upstream knowledge source. The design treats each LKM paper as a Gaia knowledge package, following the package management patterns established by modern tools like `uv`, `cargo`, and `npm`.

**Core principle:** LKM papers are dependencies, not monolithic imports. Users declare them in `pyproject.toml`, install them via `gaia add`, and reference them in their own Gaia DSL code.

---

## Motivation

### Current State (v0.5)

LKM integration exists only through agent skills (`gaia-lkm-skills` repo):
- Agent reads LKM API responses
- Agent manually writes Gaia DSL code
- No standardized way to track LKM provenance in Gaia IR
- No reusability across projects

### Problems

1. **Agent-dependent** — Without an agent, users cannot leverage LKM
2. **No provenance tracking** — LKM claim IDs, paper DOIs, evidence chains are lost after agent writes DSL
3. **No reusability** — If two projects need the same LKM paper, agent rewrites it twice
4. **No version control** — If LKM updates a paper's evidence chain, no way to track or update

### Goals

1. **CLI-first** — `gaia add lkm:claim-id` works without an agent
2. **Provenance in IR** — LKM metadata flows into `Knowledge.metadata`, visible in `gaia starmap`
3. **Reusability** — Multiple projects can share the same LKM paper package
4. **Version tracking** — `gaia.lock` pins LKM paper versions, `gaia update` refreshes them
5. **Agent-friendly** — Agents can still use `gaia lkm` commands instead of raw HTTP calls

---

## Design

### 1. Package Model

#### LKM Paper = Gaia Package

Each LKM paper is a standalone Gaia knowledge package:

```
lkm-paper-{paper_id}/
├── pyproject.toml          # Package manifest
├── paper.gaia.py           # Generated Gaia DSL from LKM evidence chains
├── priors.py               # Priors for claims in this paper
└── README.md               # Paper metadata (title, authors, DOI)
```

**Naming convention:**
- Package name: `lkm-paper-{paper_id}`
- Namespace: `lkm` (all LKM packages share this namespace)
- QID format: `lkm:lkm-paper-{paper_id}::{symbol}`

**Example:**
- LKM paper ID `812085204238729217`
- Package name: `lkm-paper-812085204238729217`
- QID: `lkm:lkm-paper-812085204238729217::gan_bandgap`

#### Version Strategy

LKM papers don't have explicit versions. We derive versions from `updated_at` timestamps:

```
version = "YYYY.M.D"
```

Examples:
- `2024.4.15` — paper updated on April 15, 2024
- `2024.4.15.1` — second update on the same day

---

### 2. Package Storage Modes

Following `uv`'s design, Gaia supports three storage modes:

#### Mode 1: Project-local (default, Phase 1)

```
my-research/
├── pyproject.toml
├── plan.gaia.py
├── .gaia/
│   ├── packages/           # ← Dependencies stored here
│   │   ├── lkm-paper-812085@2024.4.15/
│   │   └── lkm-paper-923847@2024.5.10/
│   └── ir.json
└── gaia.lock
```

**Pros:**
- Simple, self-contained
- No global state
- Easy to understand

**Cons:**
- Duplicate downloads if multiple projects use the same paper
- Larger project directories

**Configuration:**
```toml
# pyproject.toml
[tool.gaia]
package-mode = "project"  # default
```

---

#### Mode 2: Managed (recommended, Phase 2)

```
~/.local/share/gaia/
└── packages/
    ├── lkm-paper-812085@2024.4.15/
    ├── lkm-paper-923847@2024.5.10/
    └── ...

my-research/
├── pyproject.toml
├── plan.gaia.py
├── .gaia/
│   ├── packages/           # ← Symlinks to global cache
│   │   ├── lkm-paper-812085@2024.4.15 -> ~/.local/share/gaia/packages/...
│   │   └── lkm-paper-923847@2024.5.10 -> ~/.local/share/gaia/packages/...
│   └── ir.json
└── gaia.lock
```

**Pros:**
- **Global cache** — Multiple projects share the same package, download once
- **Version isolation** — Different versions of the same paper coexist
- **Space efficient** — Projects only store symlinks

**Cons:**
- Requires managing global cache
- Windows symlink support varies

**Configuration:**
```toml
# ~/.config/gaia/config.toml
[packages]
mode = "managed"
cache-dir = "~/.local/share/gaia/packages"
```

---

#### Mode 3: Workspace (Phase 3, future)

For monorepos with multiple Gaia packages:

```
my-lab/
├── workspace.toml
├── .gaia/
│   └── packages/           # Shared by all workspace members
│       ├── lkm-paper-812085/
│       └── lkm-paper-923847/
├── gan-research/
│   ├── pyproject.toml
│   └── plan.gaia.py
├── sic-research/
│   ├── pyproject.toml
│   └── plan.gaia.py
└── gaia.lock               # Workspace-level lock
```

**workspace.toml:**
```toml
[workspace]
members = ["gan-research", "sic-research"]

[workspace.packages]
mode = "workspace"
```

---

### 3. CLI Commands

#### `gaia add` — Add LKM package as dependency

```bash
# Add by claim ID (auto-discovers paper)
gaia add lkm:gcn_812085204238729217

# Add by paper ID (imports entire paper)
gaia add lkm-paper:812085204238729217

# Add with depth control
gaia add lkm:gcn_812085204238729217 --depth 1
```

**Behavior:**
1. Call `GET /claims/{id}/evidence` to fetch evidence chain
2. Extract paper ID from `data.papers`
3. Generate package structure:
   - `pyproject.toml` with LKM metadata
   - `paper.gaia.py` with Gaia DSL code
   - `priors.py` with default priors
4. Store package:
   - **Project mode:** Write to `.gaia/packages/lkm-paper-{id}@{version}/`
   - **Managed mode:** Write to global cache, symlink to project
5. Update `pyproject.toml` dependencies
6. Update `gaia.lock`

**`--depth` parameter:**
- `--depth 0` — Only import conclusion claim, no premises
- `--depth 1` — Import conclusion + direct premises (default)
- `--depth 2` — Recursively import premises of premises
- `--depth all` — Import entire evidence chain

---

#### `gaia sync` — Synchronize dependencies

```bash
gaia sync
```

**Behavior:**
1. Read `pyproject.toml` dependencies
2. Read `gaia.lock`
3. For each `lkm-paper-*` dependency:
   - Check if package exists locally (or in global cache)
   - If missing → download from LKM
   - If version mismatch → update
4. Update `gaia.lock` if needed

**Idempotent:** Multiple runs produce the same result.

---

#### `gaia remove` — Remove LKM package

```bash
gaia remove lkm-paper-812085204238729217
```

**Behavior:**
1. Remove from `pyproject.toml` dependencies
2. Remove from `.gaia/packages/` (or remove symlink in managed mode)
3. Update `gaia.lock`
4. **Check references** — Warn if `plan.gaia.py` still imports from this package

---

#### `gaia lkm search` — Search LKM claims

```bash
# Search and display results
gaia lkm search "GaN bandgap" --top-k 10

# Search and interactively add
gaia lkm search "GaN bandgap" --add
```

**Output:**
```
Found 10 LKM claims:

1. gcn_812085204238729217  "GaN bandgap is 3.4 eV"
   Paper: Smith et al. (2016) DOI: 10.1088/...
   Chains: 3

2. gcn_923847192837492  "GaN bandgap (HSE) is 3.5 eV"
   Paper: Doe et al. (2018) DOI: 10.1103/...
   Chains: 5

...

Add packages? [y/N/select]
```

**`--add` behavior:**
- `y` — Add all results
- `N` — Don't add
- `select` — Interactive selection (like `uv add --interactive`)

---

#### `gaia lkm list` — List installed LKM packages

```bash
gaia lkm list
```

**Output:**
```
Installed LKM packages:

lkm-paper-812085204238729217@2024.4.15
  Claims: gan_bandgap, pbe_underestimate
  Paper: Smith et al. (2016)
  DOI: 10.1088/0953-8984/28/22/224001

lkm-paper-923847192837492@2024.5.10
  Claims: gan_bandgap_hse
  Paper: Doe et al. (2018)
  DOI: 10.1103/PhysRevB.97.085142

Total: 2 packages
```

---

#### `gaia update` — Update LKM packages (Phase 2)

```bash
# Update specific package
gaia update lkm-paper-812085204238729217

# Update all LKM packages
gaia update --lkm
```

**Behavior:**
1. Re-fetch evidence chain from LKM API
2. Check if `updated_at` changed
3. If changed:
   - Regenerate `paper.gaia.py`
   - Bump version in `pyproject.toml`
   - Update `gaia.lock`
4. If user manually edited `paper.gaia.py`:
   - **Warn** and skip update (preserve user changes)
   - Use `--force` to override

---

#### `gaia cache` — Manage global cache (Phase 2, managed mode only)

```bash
# List cached packages
gaia cache list

# Clean unused packages
gaia cache clean

# Clean packages older than 30 days
gaia cache clean --older-than 30d

# Keep only latest 2 versions of each package
gaia cache clean --keep-latest 2
```

**`gaia cache list` output:**
```
Global package cache: ~/.local/share/gaia/packages

lkm-paper-812085204238729217
  ├─ 2024.4.15  (used by 2 projects)
  ├─ 2024.3.10  (unused)
  └─ 2024.2.05  (unused)

lkm-paper-923847192837492
  └─ 2024.5.10  (used by 1 project)

Total: 3 packages, 5 versions, 120 MB

Run `gaia cache clean` to remove unused versions.
```

---

### 4. User Workflow

#### Step 1: Search LKM

```bash
cd my-research
gaia lkm search "GaN bandgap DFT"
```

#### Step 2: Add relevant papers

```bash
gaia add lkm:gcn_812085204238729217
gaia add lkm:gcn_923847192837492
```

This updates `pyproject.toml`:
```toml
[project]
name = "gan-research"
dependencies = [
    "lkm-paper-812085204238729217",
    "lkm-paper-923847192837492",
]
```

And creates `gaia.lock`:
```json
{
  "version": 1,
  "packages": [
    {
      "name": "lkm-paper-812085204238729217",
      "version": "2024.4.15",
      "source": "lkm",
      "lkm_paper_id": "812085204238729217",
      "lkm_claim_ids": ["gcn_812085204238729217"],
      "downloaded_at": "2026-05-11T10:23:45Z"
    }
  ]
}
```

#### Step 3: Reference LKM claims in user code

```python
# plan.gaia.py
from gaia.lang import claim, contradict
from lkm.lkm_paper_812085 import gan_bandgap_pbe
from lkm.lkm_paper_923847 import gan_bandgap_hse

# User's own experimental result
my_measurement = claim("Our measured GaN bandgap is 3.2 eV")

# Compare with LKM claims
contradict(
    my_measurement,
    gan_bandgap_pbe,
    prior=0.7,
    rationale="Experimental vs DFT-PBE discrepancy"
)

contradict(
    gan_bandgap_pbe,
    gan_bandgap_hse,
    prior=0.5,
    rationale="PBE vs HSE functional difference"
)
```

#### Step 4: Compile and infer

```bash
gaia compile  # Auto-syncs dependencies if needed
gaia infer
```

The compiled IR includes:
- User's claims: `mylab:gan-research::my_measurement`
- LKM claims: `lkm:lkm-paper-812085::gan_bandgap_pbe`

#### Step 5: Visualize

```bash
gaia starmap --show-packages
```

Different packages rendered in different colors:
- User's package (`mylab:gan-research`) — green
- LKM packages (`lkm:lkm-paper-*`) — blue
- Cross-package edges — dashed lines

---

### 5. Generated Package Structure

When `gaia add lkm:gcn_812085204238729217` runs, it generates:

```
.gaia/packages/lkm-paper-812085204238729217@2024.4.15/
├── pyproject.toml
├── paper.gaia.py
├── priors.py
└── README.md
```

#### `pyproject.toml`

```toml
[project]
name = "lkm-paper-812085204238729217"
version = "2024.4.15"

[tool.gaia]
type = "knowledge-package"
namespace = "lkm"

[tool.gaia.lkm]
paper_id = "812085204238729217"
doi = "10.1088/0953-8984/28/22/224001"
title = "DFT bandgap calculations for GaN"
authors = "Smith, J. | Doe, A."
publication_date = "2016-04-15"
imported_claims = ["gcn_812085204238729217"]
depth = 1
```

#### `paper.gaia.py`

```python
"""
LKM Paper: 812085204238729217
Title: DFT bandgap calculations for GaN
DOI: 10.1088/0953-8984/28/22/224001
Authors: Smith, J. | Doe, A.
Publication Date: 2016-04-15

Auto-generated by `gaia add lkm:gcn_812085204238729217`
Do not edit manually — changes will be overwritten by `gaia update`
"""
from gaia.lang import claim, note, derive

# Paper metadata
paper_ref = note(
    "Smith et al., J. Phys.: Condens. Matter 28, 224001 (2016)",
    metadata={
        "doi": "10.1088/0953-8984/28/22/224001",
        "lkm_paper_id": "812085204238729217",
    }
)

# System and method context
gan_system = note("GaN in wurtzite structure")
dft_method = note("DFT calculation with PBE functional")

# Main claim from this paper
gan_bandgap_pbe = claim(
    "GaN bandgap is 3.4 eV",
    metadata={
        "lkm_claim_id": "gcn_812085204238729217",
        "lkm_paper_id": "812085204238729217",
    }
)

# Premises (depth >= 1)
pbe_underestimate = claim(
    "PBE functional underestimates bandgaps by ~1 eV",
    metadata={
        "lkm_claim_id": "gcn_812085204238729218",
        "lkm_paper_id": "812085204238729217",
    }
)

# Evidence chain
derive(
    gan_bandgap_pbe,
    given=[pbe_underestimate, dft_method, gan_system],
    background=[paper_ref],
    rationale="DFT-PBE calculation on wurtzite GaN"
)

__all__ = [
    "gan_bandgap_pbe",
    "pbe_underestimate",
    "gan_system",
    "dft_method",
    "paper_ref",
]
```

#### `priors.py`

```python
"""
Default priors for claims in this LKM paper.
Users can override by importing and modifying in their own priors.py
"""
from gaia.lang import prior
from . import paper

# Main claim: high confidence (published result)
prior(paper.gan_bandgap_pbe, 0.9)

# Premise: well-known DFT limitation
prior(paper.pbe_underestimate, 0.95)
```

#### `README.md`

```markdown
# LKM Paper: 812085204238729217

**Title:** DFT bandgap calculations for GaN  
**Authors:** Smith, J. | Doe, A.  
**DOI:** [10.1088/0953-8984/28/22/224001](https://doi.org/10.1088/0953-8984/28/22/224001)  
**Publication Date:** 2016-04-15  
**LKM Paper ID:** 812085204238729217

## Imported Claims

- `gan_bandgap_pbe` (gcn_812085204238729217): "GaN bandgap is 3.4 eV"
- `pbe_underestimate` (gcn_812085204238729218): "PBE functional underestimates bandgaps by ~1 eV"

## Import Depth

This package was imported with `--depth 1`, including:
- Conclusion claim
- Direct premises

To import deeper evidence chains, run:
```bash
gaia add lkm:gcn_812085204238729217 --depth 2
```

## Usage

```python
from lkm.lkm_paper_812085 import gan_bandgap_pbe, pbe_underestimate
```

## Provenance

This package was auto-generated from the Bohrium LKM API.  
**Do not edit `paper.gaia.py` manually** — changes will be overwritten by `gaia update`.

To customize, fork this package:
```bash
gaia lkm fork lkm-paper-812085204238729217
```
```

---

### 6. Configuration System

#### Configuration Hierarchy

```
~/.config/gaia/config.toml          # Global configuration
    ↓ (override)
<project>/.gaia/config.toml         # Project configuration
    ↓ (override)
Environment variables               # Highest priority
```

#### Global Config: `~/.config/gaia/config.toml`

```toml
# Gaia Global Configuration

[packages]
mode = "managed"  # "project" | "managed" | "workspace"
cache-dir = "~/.local/share/gaia/packages"

[search]
mode = "hybrid"  # "local" | "hybrid" | "semantic"
embedding-model = "BAAI/bge-large-en-v1.5"  # or e5-mistral-7b / MiniLM-L6-v2
rerank-model = "cross-encoder/ms-marco-MiniLM-L-12-v2"
prefetch-lkm = false
prefetch-limit = 1000
auto-update = true
index-dir = ".gaia/search_index"

[lkm]
base-url = "https://open.bohrium.com/openapi/v1/lkm"
access-key-env = "LKM_ACCESS_KEY"
timeout = 30
max-retries = 3
retry-delay = 1

[cache]
auto-clean = false
clean-after-days = 30
```

#### Project Config: `<project>/.gaia/config.toml`

```toml
[search]
embedding-model = "sentence-transformers/all-MiniLM-L6-v2"
auto-update = false
```

#### Project Config: `pyproject.toml`

```toml
[tool.gaia]
type = "knowledge-package"
namespace = "mylab"
package-mode = "managed"

[tool.gaia.packages]
prefer-local = false
```

#### Environment Variables

```bash
export LKM_ACCESS_KEY="your-bohrium-access-key"
export GAIA_LKM_BASE_URL="https://custom-lkm.example.com/api/v1"
export GAIA_EMBEDDING_MODEL="BAAI/bge-large-en-v1.5"
export GAIA_SEARCH_MODE="semantic"
```

#### Configuration CLI

```bash
gaia config init                    # Interactive setup
gaia config show                    # Show all config
gaia config show search.embedding-model
gaia config set search.embedding-model "BAAI/bge-large-en-v1.5"
gaia config validate                # Validate configuration
```

---

### 7. Integration with Existing Gaia Features

#### `gaia compile` — Auto-sync dependencies

```bash
gaia compile
```

**Behavior:**
1. Check if `.gaia/packages/` matches `gaia.lock`
2. If mismatch → auto-run `gaia sync` (like `uv run` auto-syncs)
3. Compile user's `plan.gaia.py` + all dependency packages
4. Generate IR with QIDs from all packages

---

#### `gaia inquiry hunt-contradictions` — Auto-search LKM (Phase 2)

```bash
gaia inquiry hunt-contradictions --use-lkm
```

**Behavior:**
1. Read all `claim()` in `plan.gaia.py`
2. For each claim, call `POST /claims/match` to search LKM
3. Find similar claims with different values
4. Auto-add corresponding LKM papers as dependencies
5. Generate contradiction suggestions in `.gaia/inquiry/suggestions.py`

**Example output:**
```python
# .gaia/inquiry/suggestions.py
from plan import my_gan_bandgap
from lkm.lkm_paper_923847 import gan_bandgap_hse

# Auto-generated suggestion (similarity: 0.92, value diff: 0.2 eV)
contradict(
    my_gan_bandgap,
    gan_bandgap_hse,
    prior=0.6,
    rationale="PBE vs HSE functional | new_question: Which is more accurate?"
)
```

User reviews and manually copies to `plan.gaia.py`.

---

#### `gaia starmap` — Visualize package provenance (Phase 2)

```bash
gaia starmap --show-packages
```

**Rendering:**
- User's claims: green nodes
- LKM claims: blue nodes with paper icon
- Hover shows: paper title, authors, DOI
- Click opens LKM web UI (if available)

---

### 8. LKM API Client

#### `gaia/lkm/client.py`

```python
import httpx
from typing import Optional

class LKMClient:
    def __init__(self, base_url: str, access_key: str):
        self.base_url = base_url
        self.headers = {"accessKey": access_key}
    
    def search_claims(self, query: str, top_k: int = 20) -> dict:
        """POST /claims/match"""
        response = httpx.post(
            f"{self.base_url}/claims/match",
            json={"text": query, "top_k": top_k},
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()
    
    def get_evidence(self, claim_id: str) -> dict:
        """GET /claims/{id}/evidence"""
        response = httpx.get(
            f"{self.base_url}/claims/{claim_id}/evidence",
            headers=self.headers,
        )
        response.raise_for_status()
        return response.json()
```

---

### 9. Package Generator

#### `gaia/lkm/package_gen.py`

```python
from pathlib import Path
from typing import Optional

def generate_package(
    evidence: dict,
    output_dir: Path,
    depth: int = 1,
) -> None:
    """
    Generate a Gaia package from LKM evidence chain.
    
    Args:
        evidence: LKM evidence response from GET /claims/{id}/evidence
        output_dir: Where to write the package
        depth: How deep to traverse premises (0 = conclusion only)
    """
    # Extract paper metadata
    paper_id = extract_paper_id(evidence)
    paper_meta = evidence["data"]["papers"][f"paper:{paper_id}"]
    
    # Generate pyproject.toml
    write_pyproject(output_dir, paper_id, paper_meta)
    
    # Generate paper.gaia.py
    write_gaia_dsl(output_dir, evidence, depth)
    
    # Generate priors.py
    write_priors(output_dir, evidence)
    
    # Generate README.md
    write_readme(output_dir, paper_meta, evidence)
```

---

### 10. Unified Search System (inspired by LeanSearch)

#### Overview

Gaia provides unified search across three knowledge sources:

```
┌─────────────────────────────────────────────────────────┐
│                    gaia search                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐ │
│  │   Local      │  │   Virtual    │  │   Remote     │ │
│  │   Package    │  │   Env        │  │   (LKM)      │ │
│  └──────────────┘  └──────────────┘  └──────────────┘ │
│         ↓                 ↓                  ↓          │
│  ┌─────────────────────────────────────────────────┐   │
│  │    Unified Vector Search (ChromaDB + E5)        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

**Design inspiration:** [LeanSearch](https://leansearch.net/) — semantic search for Lean's Mathlib.

#### CLI Commands

```bash
gaia search "GaN bandgap DFT"                  # Search all sources
gaia search "GaN bandgap" --scope local        # Only current project
gaia search "GaN bandgap" --scope venv         # Only installed packages
gaia search "GaN bandgap" --scope remote       # Only LKM API
gaia search "GaN bandgap" --augment            # Query augmentation
gaia search "GaN bandgap" --add                # Interactive add

gaia search --init                             # Initialize index
gaia search --init --prefetch-lkm              # Pre-fetch LKM claims
gaia search --rebuild                          # Rebuild index
gaia search --status                           # Show index status
```

#### Search Architecture

**Hybrid Strategy:**

```
User query → Query augmentation (optional)
    ↓
┌─────────────────────┬─────────────────────┐
│  Local + Venv       │  Remote LKM         │
│  Vector search      │  API search         │
│  ChromaDB           │  /claims/match      │
└─────────────────────┴─────────────────────┘
    ↓                       ↓
    └───────────┬───────────┘
                ↓
        Merge & Re-rank → Top-k results
```

**Key Features:**
1. Task-instructed embeddings
2. Query augmentation with LLM
3. Cross-encoder re-ranking

#### Index Management

```bash
gaia search --init
```

**Behavior:**
1. Scan local package + virtual env
2. Optionally pre-fetch popular LKM claims
3. Embed all documents
4. Store in `.gaia/search_index/`

**Auto-update:** After `gaia compile` or `gaia add lkm:...`

**Index size:** ~1200 claims × 16 KB = ~19 MB

---

## Implementation Plan

## Implementation Plan

### Phase 1: Project-local Mode (v0.6)

**Goal:** Basic LKM package management with project-local storage

**Deliverables:**
- [ ] `gaia/config.py` — Hierarchical configuration loader
- [ ] `gaia/lkm/client.py` — LKM HTTP API client with retry logic
- [ ] `gaia/lkm/package_gen.py` — Generate Gaia package from LKM evidence
- [ ] `gaia/cli/commands/config.py` — Configuration management
  - [ ] `gaia config init` — Interactive setup
  - [ ] `gaia config show/set` — View/modify config
- [ ] `gaia/cli/commands/lkm.py` — LKM package commands
  - [ ] `gaia lkm search <query>` — Search LKM
  - [ ] `gaia add lkm:<claim-id>` — Add LKM package
  - [ ] `gaia remove lkm-paper-<id>` — Remove LKM package
  - [ ] `gaia lkm list` — List installed LKM packages
- [ ] `gaia sync` — Sync dependencies to `.gaia/packages/`
- [ ] `gaia.lock` format + read/write
- [ ] `gaia compile` — Auto-load packages from `.gaia/packages/`
- [ ] Tests + documentation

**Timeline:** 2-3 weeks

---

### Phase 2: Managed Mode + Unified Search (v0.7)

**Goal:** Global package cache + semantic search across all knowledge sources

**Deliverables:**
- [ ] Global cache `~/.local/share/gaia/packages/`
- [ ] `gaia config set package-mode managed`
- [ ] `gaia sync --migrate` — Migrate from project to managed mode
- [ ] `gaia cache list/clean` — Manage global cache
- [ ] `usage.json` — Track package usage across projects
- [ ] `gaia update` — Update LKM packages
- [ ] **Unified Search System:**
  - [ ] `gaia/search/indexer.py` — Build/update search index
  - [ ] `gaia/search/engine.py` — Unified search engine
  - [ ] `gaia search` — Search across local/venv/remote
  - [ ] Task-instructed embeddings (LeanSearch-style)
  - [ ] Query augmentation with LLM
  - [ ] Cross-encoder re-ranking
  - [ ] Auto-update index after compile/add
- [ ] `gaia inquiry hunt-contradictions --use-lkm`
- [ ] `gaia starmap --show-packages`
- [ ] Tests + documentation

**Timeline:** 4-5 weeks

---

### Phase 3: Workspace Mode (v0.8+)

**Goal:** Monorepo support with shared dependencies

**Deliverables:**
- [ ] `workspace.toml` format
- [ ] `gaia workspace init/add`
- [ ] Workspace-level `gaia.lock`
- [ ] Tests + documentation

**Timeline:** 2-3 weeks

---

## Open Questions

1. **Default mode:** Should we default to `project` or `managed`?
   - Proposal: Default to `project` in Phase 1, recommend `managed` in docs

2. **Windows symlink fallback:** If symlinks not supported, use junction/hardlink or copy?
   - Proposal: Try symlink → junction → hardlink → copy (in that order)

3. **Manual edits:** If user edits `.gaia/packages/*/paper.gaia.py`, what should `gaia update` do?
   - Proposal: Warn and skip update (preserve user changes), use `--force` to override

4. **Version conflicts:** If two projects need different versions of the same LKM paper?
   - Proposal: Both versions coexist in global cache, each project symlinks to its version

5. **LKM API rate limits:** How to handle rate limiting?
   - Proposal: Exponential backoff + cache responses locally

6. **Offline mode:** Should `gaia compile` work without LKM access?
   - Proposal: Yes, if `gaia.lock` + `.gaia/packages/` are present

7. **Embedding model selection:** Should we default to large (e5-mistral-7b) or small (MiniLM)?
   - Proposal: Default to `BAAI/bge-large-en-v1.5` (good balance: 1.3GB, high quality)
   - Let users choose lighter model via `gaia config init`

8. **Search index location:** Project-local (`.gaia/search_index/`) or global cache?
   - Proposal: Project-local by default (each project has its own index)
   - Allows different projects to use different embedding models

---

## Alternatives Considered

### Alternative 1: Monolithic Import

Import all LKM claims into a single `lkm_imports.py` file.

**Rejected because:**
- No version tracking per paper
- No reusability across projects
- Hard to update individual papers

### Alternative 2: Claim-level Packages

Each LKM claim is a separate package (`lkm-claim-{claim_id}`).

**Rejected because:**
- Too fine-grained (thousands of packages)
- Loses paper-level context
- Harder to manage dependencies

### Alternative 3: No Package Abstraction

Just download LKM evidence JSON, let users manually write Gaia DSL.

**Rejected because:**
- No reusability
- No provenance tracking
- Agent-dependent

---

## References

- [uv documentation](https://docs.astral.sh/uv/)
- [Cargo book](https://doc.rust-lang.org/cargo/)
- [npm documentation](https://docs.npmjs.com/)
- [gaia-lkm-skills repo](https://github.com/SiliconEinstein/gaia-lkm-skills)
- [LKM API documentation](https://open.bohrium.com/openapi/v1/lkm)
- [LeanSearch](https://leansearch.net/) — Semantic search for Lean's Mathlib
- [LeanSearch paper (arXiv:2403.13310)](https://arxiv.org/html/2403.13310v2) — A Semantic Search Engine for Mathlib4
- [Lean Finder paper (arXiv:2510.15940)](https://arxiv.org/html/2510.15940v1) — Semantic Search for Mathlib That Understands User Intents

---

## Appendix: Example Session

```bash
# 1. Initialize global config
gaia config init
# Prompts:
#   LKM Access Key: **** (from https://bohrium.dp.tech)
#   Embedding model: [1] e5-mistral / [2] bge-large / [3] MiniLM
#   Choose: 2

# Or set manually
export LKM_ACCESS_KEY="your-bohrium-key"
gaia config set search.embedding-model "BAAI/bge-large-en-v1.5" --global

# 2. Initialize project
gaia init my-research
cd my-research

# 3. Initialize search index
gaia search --init
# Output: Loading embedding model: BAAI/bge-large-en-v1.5
#         Indexing local package... 0 claims
#         ✓ Indexed 0 claims

# 4. Search LKM (remote)
gaia search "GaN bandgap DFT" --scope remote
# Output: 10 results from LKM API

# 5. Add relevant papers
gaia add lkm:gcn_812085204238729217
gaia add lkm:gcn_923847192837492

# 6. Check installed packages
gaia lkm list
# Output:
#   lkm-paper-812085@2024.4.15
#   lkm-paper-923847@2024.5.10

# 7. Write user code
cat > plan.gaia.py <<EOF
from gaia.lang import claim, contradict
from lkm.lkm_paper_812085 import gan_bandgap_pbe
from lkm.lkm_paper_923847 import gan_bandgap_hse

my_measurement = claim("Our measured GaN bandgap is 3.2 eV")

contradict(my_measurement, gan_bandgap_pbe, prior=0.7)
contradict(gan_bandgap_pbe, gan_bandgap_hse, prior=0.5)
EOF

# 8. Compile (auto-updates search index)
gaia compile
# Output: Syncing dependencies...
#         Updating search index...
#         Indexing local package... 1 claim
#         Indexing virtual env... 2 claims
#         ✓ Indexed 3 claims
#         Compiling...

# 9. Search across all sources
gaia search "GaN bandgap"
# Output:
# [LOCAL] mylab:gan-research::my_measurement
# [VENV] lkm:lkm-paper-812085::gan_bandgap_pbe
# [VENV] lkm:lkm-paper-923847::gan_bandgap_hse

# 10. Infer
gaia infer

# 11. Visualize
gaia starmap --show-packages

# 12. Later: update LKM packages
gaia update --lkm
```
