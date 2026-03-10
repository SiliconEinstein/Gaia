# CLI Pipeline Convergence Design

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the CLI `build → review → infer → publish --local` pipeline produce correct, scalable data in v2 storage format.

**Architecture:** Four-stage artifact pipeline where each stage reads upstream artifacts (never re-parses source YAML). Publish writes to v2 `LanceContentStore` + `KuzuGraphStore` (already implemented in `libs/storage_v2/`). Inference continues using `CompiledFactorGraph` for BP (unchanged).

**Tech Stack:** Python 3.12+, Pydantic v2, LanceDB (via `libs/storage_v2/lance_content_store.py`), Kuzu (via `libs/storage_v2/kuzu_graph_store.py`)

---

## 1. Identity Model

Every Closure and Chain gets a dual-layer identifier:

| Layer | Purpose | Example |
|-------|---------|---------|
| **closure_id / chain_id** (human-readable) | User reference, cross-package Ref, display, search | `galileo_falling_bodies/vacuum_prediction` |
| **content hash** (machine) | Dedup verification, version tracking | `sha256:a3f8c2e91b4d0567` |

### ID Generation

```python
import hashlib

def closure_content_hash(package_name: str, closure_name: str, content: str) -> str:
    """Deterministic content hash for dedup verification."""
    payload = f"{package_name}\0{closure_name}\0{content}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]

def edge_content_hash(package_name: str, edge_name: str,
                      premise_ids: list[str], conclusion_ids: list[str]) -> str:
    payload = f"{package_name}\0{edge_name}\0{','.join(sorted(premise_ids))}\0{','.join(sorted(conclusion_ids))}"
    return "sha256:" + hashlib.sha256(payload.encode()).hexdigest()[:16]
```

### ID Scheme

| Entity | ID Format | Example |
|--------|-----------|---------|
| Package | `package_name` | `galileo_falling_bodies` |
| Module | `{package_id}.{module_name}` | `galileo_falling_bodies.reasoning` |
| Closure | `{package_id}/{closure_name}` | `galileo_falling_bodies/vacuum_prediction` |
| Chain | `{module_id}.{chain_name}` | `galileo_falling_bodies.reasoning.synthesis_chain` |

Design notes:
- Closure uses `/` separator (distinguishes from intra-package `module.name` Ref syntax which uses `.`)
- `\0` separator in hash prevents field concatenation ambiguity
- 16 hex chars (64-bit) — collision-safe at 10B+ package scale
- Content hash excludes prior/belief (mutable state should not affect identity)
- Same content → same hash → re-publish is naturally idempotent

---

## 2. Four-Stage Artifact Pipeline

### Principle

Each stage produces immutable artifacts. Downstream stages only read artifacts, never re-parse source YAML.

### Directory Structure

```
.gaia/
├── build/
│   ├── manifest.json         # Serialized resolved Package + metadata
│   └── package.md            # Single reviewer markdown (all modules, narrative order)
├── reviews/
│   └── review_2026-03-10.yaml  # LLM review results
├── infer/
│   └── infer_result.json     # CompiledFactorGraph + BP beliefs
└── publish/
    └── receipt.json          # Record of what was published
```

### Data Flow

```
gaia build
  Input:  package YAML + dependency package YAMLs
  Process: load_package → resolve_refs → elaborate_package
  Output:  manifest.json + package.md (single file, all modules in narrative order)

gaia review
  Input:  .gaia/build/*.md (human-readable chain sections)
  Process: LLM per-chain review
  Output:  review_*.yaml (existing flow unchanged)

gaia infer
  Input:  manifest.json + review_*.yaml
  Process: deserialize Package → merge_review → compile_factor_graph → BP
  Output:  infer_result.json

gaia publish --local
  Input:  manifest.json + review_*.yaml + infer_result.json
  Process: convert_to_v2 → delete old package data → write v2 stores
  Output:  receipt.json + data in LanceDB + Kuzu
```

### manifest.json Format

```json
{
  "version": 1,
  "source_fingerprint": "sha256:...",
  "created_at": "2026-03-10T14:30:00Z",
  "package": {
    "name": "galileo_falling_bodies",
    "modules": ["aristotle", "reasoning", "..."],
    "export": ["vacuum_prediction", "..."],
    "loaded_modules": ["<full Module serialization with all Knowledge objects>"]
  },
  "resolution_index": {
    "reasoning.heavier_falls_faster": {
      "type": "claim",
      "name": "heavier_falls_faster",
      "content": "..."
    }
  }
}
```

- `package` = `Package.model_dump()` with full loaded_modules
- `resolution_index` = serialized `Package._index` for rebuilding `Ref._resolved` pointers
- `source_fingerprint` detects source changes (review and publish both check it)
- `version` field supports future format evolution

Deserialization:
1. `Package.model_validate(data["package"])` to rebuild Package
2. Walk modules, rebuild `Ref._resolved` from resolution_index
3. Rebuild `_index`

### infer_result.json Format

```json
{
  "version": 1,
  "source_fingerprint": "sha256:...",
  "review_file": "review_2026-03-10.yaml",
  "bp_run_id": "uuid-...",
  "variables": {
    "vacuum_prediction": { "prior": 0.5, "belief": 0.82 },
    "heavier_falls_faster": { "prior": 0.7, "belief": 0.35 }
  },
  "factors": [
    {
      "name": "synthesis_chain.step_2",
      "premises": ["aristotle_contradicted", "air_resistance_is_confound"],
      "conclusions": ["vacuum_prediction"],
      "probability": 0.9,
      "edge_type": "deduction"
    }
  ]
}
```

### receipt.json Format

```json
{
  "version": 1,
  "package_id": "galileo_falling_bodies",
  "published_at": "2026-03-10T15:00:00Z",
  "db_path": "/data/lancedb/gaia",
  "stats": {
    "closures": 14,
    "chains": 11,
    "probabilities": 22,
    "belief_snapshots": 14
  },
  "closure_ids": ["galileo_falling_bodies/vacuum_prediction", "..."],
  "chain_ids": ["galileo_falling_bodies.reasoning.synthesis_chain", "..."]
}
```

### Stage Responsibilities

| Stage | Responsibility | Computation |
|-------|---------------|-------------|
| build | Compile | parse + resolve + elaborate |
| review | Assess | LLM scoring (unchanged) |
| infer | Reason | merge_review + compile_factor_graph + BP |
| publish | Persist | v2 model conversion + DB write |

---

## 3. Build Output: Reviewer Markdown Format

### Principle

`gaia build` produces a **single `package.md`** file containing all modules in the narrative order declared in `package.yaml`. This is the document the LLM reviewer reads. It should tell a coherent story, not a bag of disconnected chains.

### Model Change Required

`Module` needs a `title` field for natural language headings:

```python
# libs/lang/models.py
class Module(BaseModel):
    type: str
    name: str
    title: str | None = None    # NEW: natural language title
    knowledge: list[Knowledge] = Field(default_factory=list)
    export: list[str] = Field(default_factory=list)
```

```yaml
# aristotle.yaml
type: reasoning_module
name: aristotle
title: 亚里士多德学说 — 即将被挑战的先验知识   # NEW
```

### Markdown Structure

```markdown
# {package manifest.description} ({package.name} v{version})

> {manifest.description}

---

## 一、{module.title} [module:{module.name}]

### Knowledge declarations (if any non-chain knowledge)

**[type] name** (prior=X)
> content...

### Chain: {chain.name} [chain:{chain.name}] ({edge_type})

**Context (indirect reference):**         ← indirect deps expanded; omit if none

> **[type] name** (prior=X)
> content...

**[step:{chain_name}.{step_num}]** (prior=X)

**Direct references:**                    ← direct deps expanded at each step
> **[type] name** (prior=X)
> content...
>
> **[type] name** (prior=X)
> content...

**Reasoning:**
> reasoning text...

**Conclusion:** [type] name (prior=X)
> content...

---

## 二、{next module.title} [module:{name}]
...
```

### Terminology (included in LLM review prompt)

```
Terminology:
- **Direct reference**: A premise the conclusion logically depends on.
  If removed, the conclusion no longer follows.
- **Indirect reference (context)**: Background information that frames
  the reasoning but is not strictly necessary for the conclusion.
```

### Example: Galileo Package (abridged)

```markdown
# 伽利略落体问题 (galileo_falling_bodies v1.0.0)

> 建模伽利略如何通过绑球思想实验、介质密度分析和斜面实验，
> 逐步反驳亚里士多德"重的物体下落更快"的学说，并推出
> "真空中不同重量的物体应以相同速率下落"的预测。

---

## 一、研究动机 [module:motivation]

**[question] main_question**
> 下落的速率是否真正取决于物体的重量？
> 如果"重者下落更快"只是空气阻力造成的表象，那么在思想实验、
> 控制条件实验以及真空极限下，应当分别看到怎样的结果？

---

## 二、背景与假设 [module:setting]

**[setting] thought_experiment_env** (prior=1.0)
> 想象一个重球 H 和一个轻球 L 从同一高度落下。
> 先分别考虑它们各自的"自然下落速度"，再考虑把二者用细绳绑成
> 复合体 HL 后一起下落，会得到什么结果。

**[setting] vacuum_env** (prior=1.0)
> 一个理想化的无空气阻力环境，
> 只保留重力作用，不让介质阻力参与落体过程。

---

## 三、亚里士多德学说 [module:aristotle]

**[claim] heavier_falls_faster** (prior=0.7)
> 重的物体比轻的物体下落得更快。下落速度与重量成正比。

**[claim] everyday_observation** (prior=0.95)
> 在日常空气环境中，从同一高度落下时，石头通常比羽毛更早落地；
> 重物看起来往往比轻物下落得更快。

### Chain: inductive_support [chain:inductive_support] (deduction)

**[step:inductive_support.2]** (prior=0.8)

**Direct references:**
> **[claim] everyday_observation** (prior=0.95)
> 在日常空气环境中，从同一高度落下时，石头通常比羽毛更早落地；
> 重物看起来往往比轻物下落得更快。

**Reasoning:**
> 日常经验反复呈现"重物先落地、轻物后落地"的现象，
> 如果不区分空气阻力等外在因素，人们很自然会把这种表象
> 归纳成一条普遍规律：重量越大，下落越快。

**Conclusion:** [claim] heavier_falls_faster (prior=0.7)
> 重的物体比轻的物体下落得更快。下落速度与重量成正比。

---

## 四、核心推理 [module:reasoning]

**[claim] tied_pair_slower_than_heavy** (prior=0.5)
> 复合体 HL 因轻球拖拽，下落速度应慢于单独的重球 H。

**[claim] tied_pair_faster_than_heavy** (prior=0.5)
> 复合体 HL 总重量大于单独的重球 H，下落速度应快于 H。

**[contradiction] tied_balls_contradiction** (prior=0.6)
> 同一定律对同一绑球系统同时预测"更慢"和"更快"，自相矛盾。
> **矛盾双方:** tied_pair_slower_than_heavy ↔ tied_pair_faster_than_heavy

**[claim] aristotle_contradicted** (prior=0.5)
> 亚里士多德"重者下落更快"的定律因绑球矛盾而不能成立。

*(... more claims ...)*

**[claim] vacuum_prediction** (prior=0.5)
> 在真空中，不同重量的物体应以相同速率下落。

### Chain: drag_prediction_chain [chain:drag_prediction_chain] (deduction)

**Context (indirect reference):**
> **[setting] thought_experiment_env** (prior=1.0)
> 想象一个重球 H 和一个轻球 L 从同一高度落下。
> 先分别考虑它们各自的"自然下落速度"，再考虑把二者用细绳绑成
> 复合体 HL 后一起下落，会得到什么结果。

**[step:drag_prediction_chain.2]** (prior=0.93)

**Direct references:**
> **[claim] heavier_falls_faster** (prior=0.7)
> 重的物体比轻的物体下落得更快。下落速度与重量成正比。

**Reasoning:**
> 在思想实验环境中暂时接受"重的物体比轻的物体下落得更快"：
> 轻球天然比重球下落更慢。于是当轻球与重球绑在一起时，
> 轻球应当拖慢重球，复合体 HL 的下落速度应慢于单独的重球 H。

**Conclusion:** [claim] tied_pair_slower_than_heavy (prior=0.5)
> 复合体 HL 因轻球拖拽，下落速度应慢于单独的重球 H。

### Chain: synthesis_chain [chain:synthesis_chain] (deduction)

**Context (indirect reference):**
> **[setting] vacuum_env** (prior=1.0)
> 一个理想化的无空气阻力环境，
> 只保留重力作用，不让介质阻力参与落体过程。

**[step:synthesis_chain.2]** (prior=0.94)

**Direct references:**
> **[claim] aristotle_contradicted** (prior=0.5)
> 亚里士多德"重者下落更快"的定律因绑球矛盾而不能成立。
>
> **[claim] air_resistance_is_confound** (prior=0.5)
> 日常观察到的速度差异来自空气阻力，而非重量本身。
>
> **[claim] inclined_plane_supports_equal_fall** (prior=0.55)
> 斜面实验支持"重量不是决定落体速度的首要因素"。

**Reasoning:**
> 如果亚里士多德定律因绑球矛盾而不能成立，
> 并且日常观察到的速度差异来自空气阻力，
> 再加上斜面实验支持"重量不是决定落体速度的首要因素"，
> 那么在理想化的无空气阻力环境这一极限条件下，
> 最合理的预测是：不同重量的物体应以相同速率下落。

**Conclusion:** [claim] vacuum_prediction (prior=0.5)
> 在真空中，不同重量的物体应以相同速率下落。

---

## 五、后续问题 [module:follow_up]

**[question] follow_up_question**
> 能否在足够接近真空的条件下直接比较重球与轻球的下落时间？

### Chain: next_steps [chain:next_steps] (deduction)

**[step:next_steps.2]**

**Direct references:**
> **[claim] vacuum_prediction** (prior=0.5)
> 在真空中，不同重量的物体应以相同速率下落。

**Reasoning:**
> 既然该 package 已经从思想实验、介质分析和斜面实验三条线索
> 汇聚到"真空中等速下落"的预测，
> 下一步就应当寻找足够接近真空的直接实验来验证这一点。

**Conclusion:** [question] follow_up_question
> 能否在足够接近真空的条件下直接比较重球与轻球的下落时间？
```

### LLM-Friendly Anchors

| Anchor | Purpose | Parse regex |
|--------|---------|-------------|
| `[module:name]` | Module-level locator | `\[module:(\w+)\]` |
| `[chain:name]` | Chain-level locator, used in review response | `\[chain:([\w.]+)\]` |
| `[step:chain.N]` | Globally unique step ID (no ambiguity across chains) | `\[step:([\w.]+\.(\d+))\]` |
| `[type] name` | Knowledge object type tag | `\[(\w+)\]\s+(\w+)` |

---

## 4. Review: Prompt, Workflow, and Report Format

### Design Principle

Review receives the **entire `package.md`** in a single LLM call, enabling global narrative assessment. The reviewer follows a structured 5-step workflow that separates reasoning quality from input reliability.

### System Prompt (`cli/prompts/review_system.md`)

```markdown
You are a scientific reasoning reviewer. Your task is to assess the logical
reliability of reasoning chains in a knowledge package.

## Terminology

- **Direct reference**: A premise the conclusion logically depends on.
  If this premise is false, the conclusion necessarily fails.
- **Indirect reference (context)**: Background information that frames
  the reasoning. The conclusion may still hold without it.
- **Weak point**: A hidden assumption, logical gap, or vulnerability in
  the reasoning that is NOT already declared as a reference. Express each
  weak point as a self-contained proposition (a complete statement that
  could be true or false independently).
- **Conditional prior**: The probability that the reasoning step is correct,
  ASSUMING all direct references are true. This isolates the quality of the
  reasoning itself from the reliability of its inputs.

## Workflow

1. **Read the entire package** to understand the narrative arc and how
   modules connect.
2. **For each chain**, read the reasoning process and judge whether the
   logic is sound.
3. **Identify weak points** — hidden assumptions or logical gaps not
   already declared as references. Summarize each as a self-contained
   proposition.
4. **Classify each weak point**:
   - `direct` — if this weak point is false, the conclusion fails
   - `indirect` — the conclusion could survive even if this is wrong
5. **Assign a conditional prior** — assuming all declared direct references
   are correct, how reliable is this reasoning step? (0.0–1.0)

## Output Format

Reply with ONLY a YAML document (no markdown fences, no extra text).
Use step IDs exactly as they appear in the document (e.g., `synthesis_chain.2`).
```

### User Prompt

```
Review the following knowledge package:

{package.md content}
```

### Review Report Format (`review_*.yaml`)

```yaml
package: galileo_falling_bodies
model: claude-sonnet-4-20250514
timestamp: '2026-03-10T14:30:00+00:00'
source_fingerprint: ca03712f5286bb4c

summary: >
  整体叙事连贯：从亚里士多德定律出发，通过绑球思想实验暴露矛盾，
  再从介质分析和斜面实验两条独立线索汇聚到真空等速下落的预测。
  主要弱点在于思想实验对"复合体行为"的理想化假设。

chains:
- chain: drag_prediction_chain
  steps:
  - step: drag_prediction_chain.2
    weak_points:
    - proposition: 绳子连接不改变两球各自的"自然速度"，力的传递是瞬时且完全的
      impact: direct
    - proposition: 思想实验中忽略了绳子自身的质量和弹性
      impact: indirect
    conditional_prior: 0.85
    explanation: >
      推理在理想化框架下有效，但"轻球拖慢重球"隐含了
      力的瞬时传递假设，这是一个关键的未声明前提。

- chain: combined_weight_chain
  steps:
  - step: combined_weight_chain.2
    weak_points: []
    conditional_prior: 0.93
    explanation: >
      在亚里士多德框架内，复合体总重量大于单个重球，
      因此下落更快是该理论的直接推论，逻辑无额外假设。

- chain: contradiction_chain
  steps:
  - step: contradiction_chain.2
    weak_points:
    - proposition: 两条预测确实针对完全相同的物理情境，没有隐含的条件差异
      impact: direct
    conditional_prior: 0.95
    explanation: >
      矛盾的识别是有力的——同一定律对同一系统给出互斥预测。
      唯一的弱点是是否存在未声明的边界条件差异。

- chain: synthesis_chain
  steps:
  - step: synthesis_chain.2
    weak_points:
    - proposition: 三条独立证据线索在逻辑上足以支持真空等速下落这一特定结论，而不仅仅是否定亚里士多德
      impact: direct
    - proposition: 从"亚里士多德定律错误"到"所有物体等速下落"之间没有其他可能的替代理论
      impact: indirect
    conditional_prior: 0.82
    explanation: >
      汇聚推理的方向正确，但从"重量不是唯一因素"到"完全等速"
      存在逻辑跳跃。证据只能否定简单正比关系，不能直接证明等速。
```

### Field Semantics

| Field | Type | Purpose |
|-------|------|---------|
| `summary` | str | Package-level narrative assessment (uses whole-document context) |
| `step` | str | Globally unique step ID, matches `[step:X]` anchor in markdown |
| `weak_points` | list | Hidden assumptions / logical gaps NOT already declared as references |
| `weak_points[].proposition` | str | Self-contained statement that could be true or false independently |
| `weak_points[].impact` | `direct` \| `indirect` | If false, does the conclusion fail? |
| `conditional_prior` | float | P(step correct \| all declared direct references are true) |
| `explanation` | str | Human-readable justification for the assessment |

### How Review Feeds into Inference

```python
# merge_review() updates:
# 1. conditional_prior → step.prior (used in factor graph compilation)
# 2. direct weak_points → recorded in review sidecar for traceability
#    (future: auto-create new Closures in the knowledge graph)
# 3. indirect weak_points → recorded only, no BP impact
```

### Changes vs Current Implementation

| Aspect | Current | New |
|--------|---------|-----|
| Input granularity | Per-chain markdown fragment | Entire `package.md` |
| LLM calls | N calls (one per chain) | 1 call (whole package) |
| Global context | None | Full narrative arc visible |
| Step ID format | `step: 2` (ambiguous across chains) | `step: chain_name.2` (globally unique) |
| Output per step | `assessment` + `suggested_prior` + `dependencies` | `weak_points` + `conditional_prior` + `explanation` |
| Weak points | Not captured | Self-contained propositions with impact classification |
| Package summary | Not captured | `summary` field with global assessment |
| `rewrite` field | Always null, unused | Removed |
| `dependencies` field | Rarely populated | Replaced by weak_points with richer semantics |

### Mock Review Client Update

`MockReviewClient` should produce the same format:
- Parse step IDs from `[step:chain_name.N]` anchors
- Extract existing priors as `conditional_prior`
- `weak_points: []` (mock doesn't discover weak points)
- `explanation: ""` (mock doesn't explain)
- `summary: "Mock review — all steps accepted at author priors."`

---

## 5. Storage: Align with v2 Schema

### Principle

CLI `publish --local` writes directly to v2 storage (`libs/storage_v2/`). No modification to v1 `Node/HyperEdge` models. The v2 stores (LanceContentStore, KuzuGraphStore) are already implemented with full test coverage.

### Gaia Language → v2 Storage Mapping

| Language Concept | v2 Storage Entity | ID Rule |
|-----------------|-------------------|---------|
| `Package` | `v2.Package` | `package_id` = globally unique str |
| `Module` | `v2.Module` | `module_id` = `{package_id}.{module_name}` |
| `Claim/Setting/Question` | `v2.Closure` | `closure_id` = `{package_id}/{name}`, `version` = int |
| `ChainExpr` | `v2.Chain` + `v2.ChainStep[]` | `chain_id` = `{module_id}.{chain_name}` |
| `StepApply/StepLambda` | `v2.ChainStep` | `step_index: int` |
| `Ref` (cross-pkg) | `v2.ClosureRef` in ChainStep | `(closure_id, version)` pinned |
| `Relation` | `v2.Chain` (special type) | contradiction / equivalence / subsumption |
| review `suggested_prior` | `v2.ProbabilityRecord` | `(chain_id, step_index)`, source="llm_review" |
| BP belief | `v2.BeliefSnapshot` | `(closure_id, version, bp_run_id)` |

### BP Inference (Unchanged)

`CompiledFactorGraph` from `libs/lang/compiler.py` continues to be used for BP inference in `gaia infer`. This aligns with storage-schema.md: "BP factor graph is built dynamically at runtime, not persisted."

### Write Targets

| Backend | Writes | Purpose |
|---------|--------|---------|
| LanceContentStore | packages, modules, closures, chains, probabilities, belief_history | Source of truth, BM25 search |
| KuzuGraphStore | Closure nodes, Chain nodes, PREMISE/CONCLUSION relationships | Graph topology queries |
| VectorStore | Embeddings (optional, future) | Embedding similarity search |

### Idempotent Cleanup

Before writing, delete all existing data for the package:

```python
await content_store.delete_package(package_id)  # New method needed
await graph_store.delete_package(package_id)     # New method needed
```

Deletes by `package_id` across all tables/nodes, then re-inserts fresh data.

---

## 6. `lang_to_v2.py` — Converter

### Interface

```python
@dataclass
class V2IngestData:
    package: v2.Package
    modules: list[v2.Module]
    closures: list[v2.Closure]
    chains: list[v2.Chain]
    probabilities: list[v2.ProbabilityRecord]
    belief_snapshots: list[v2.BeliefSnapshot]

def convert_to_v2(
    pkg: Package,                    # Deserialized from manifest.json
    review: dict,                    # review_*.yaml contents
    beliefs: dict[str, float],       # BP results from infer_result.json
    bp_run_id: str,                  # BP run identifier
) -> V2IngestData:
    ...
```

Conversion reads directly from Language models, NOT from CompiledFactorGraph.

### Conversion Rules

#### Package → v2.Package

```python
v2.Package(
    package_id   = pkg.name,
    name         = pkg.name,
    version      = pkg.version or "0.1.0",
    modules      = [f"{pkg.name}.{m}" for m in pkg.modules_list],
    exports      = [f"{pkg.name}/{name}" for name in pkg.export],
    submitter    = "cli",
    submitted_at = now,
    status       = "merged",
)
```

#### Module → v2.Module

```python
v2.Module(
    module_id    = f"{pkg.name}.{mod.name}",
    package_id   = pkg.name,
    name         = mod.name,
    role         = mod.type.replace("_module", ""),
    imports      = [ImportRef(...)],   # Extracted from Ref objects
    chain_ids    = [...],              # ChainExpr IDs in this module
    export_ids   = [f"{pkg.name}/{n}" for n in mod.export],
)
```

#### Knowledge → v2.Closure

```python
# Claim / Setting / Question → Closure (skip Ref, ChainExpr, Action)
for mod in pkg.loaded_modules:
    for decl in mod.knowledge:
        actual = decl._resolved if isinstance(decl, Ref) else decl
        if not isinstance(actual, (Claim, Setting, Question)):
            continue
        v2.Closure(
            closure_id        = f"{pkg.name}/{actual.name}",
            version           = 1,
            type              = actual.type,
            content           = actual.content,
            prior             = actual.prior or 0.5,
            keywords          = actual.keywords or [],
            source_package_id = pkg.name,
            source_module_id  = f"{pkg.name}.{mod.name}",
            created_at        = now,
        )
```

Dedup: same `(closure_id, version)` referenced from multiple modules → keep one copy.

#### ChainExpr → v2.Chain + ChainStep[]

```python
v2.Chain(
    chain_id   = f"{pkg.name}.{mod.name}.{chain.name}",
    module_id  = f"{pkg.name}.{mod.name}",
    package_id = pkg.name,
    type       = chain.edge_type or "deduction",
    steps      = [
        v2.ChainStep(
            step_index = i,
            premises   = [
                v2.ClosureRef(closure_id=f"{pkg.name}/{arg.ref}", version=1)
                for arg in step.args
            ],
            reasoning  = step.prompt or "",
            conclusion = v2.ClosureRef(
                closure_id=f"{pkg.name}/{next_ref.name}", version=1
            ),
        )
        for i, step in enumerate(apply_steps)
    ],
)
```

#### Relation → v2.Chain (special type)

```python
v2.Chain(
    chain_id   = f"{pkg.name}.{mod.name}.{relation.name}",
    type       = relation.type,  # "contradiction" / "equivalence" / "subsumption"
    steps      = [
        v2.ChainStep(
            step_index = 0,
            premises   = [ClosureRef(f"{pkg.name}/{m}", 1) for m in relation.members],
            reasoning  = "",
            conclusion = ClosureRef(f"{pkg.name}/{relation.name}", 1),
        )
    ],
)
```

#### Review → v2.ProbabilityRecord[]

```python
for chain_review in review["chains"]:
    for step_review in chain_review["steps"]:
        v2.ProbabilityRecord(
            chain_id      = chain_id_lookup[chain_review["chain"]],
            step_index    = step_review["step"],
            value         = step_review["suggested_prior"],
            source        = "llm_review",
            source_detail = review["model"],
            recorded_at   = now,
        )
```

#### Beliefs → v2.BeliefSnapshot[]

```python
for var_name, belief_val in beliefs.items():
    v2.BeliefSnapshot(
        closure_id  = f"{pkg.name}/{var_name}",
        version     = 1,
        belief      = belief_val,
        bp_run_id   = bp_run_id,
        computed_at = now,
    )
```

#### Cross-Package References

Cross-package Refs (e.g., Newton referencing Galileo's `vacuum_prediction`):
- `closure_id` = `"galileo_falling_bodies/vacuum_prediction"` (points to source package)
- `version` = source package's current version
- **Do NOT re-create Closure** — only reference via `ClosureRef` in ChainStep premises

---

## 7. `_publish_local()` Rewrite

### New Implementation

```python
async def _publish_local(pkg_path: Path, db_path: str) -> None:
    from libs.storage_v2.lance_content_store import LanceContentStore
    from libs.storage_v2.kuzu_graph_store import KuzuGraphStore

    # 1. Read artifacts (no source YAML)
    manifest = load_manifest(pkg_path / ".gaia" / "build" / "manifest.json")
    infer_result = load_infer_result(pkg_path / ".gaia" / "infer" / "infer_result.json")
    review = read_review(find_latest_review(pkg_path / ".gaia" / "reviews"))

    # 2. Deserialize Package from manifest
    pkg = deserialize_package(manifest)

    # 3. Convert to v2 models
    data = convert_to_v2(
        pkg=pkg,
        review=review,
        beliefs=infer_result["beliefs"],
        bp_run_id=infer_result.get("bp_run_id", str(uuid4())),
    )

    # 4. Initialize v2 stores
    content = LanceContentStore(db_path)
    graph = KuzuGraphStore(f"{db_path}/kuzu")
    await graph.initialize_schema()

    # 5. Idempotent cleanup (delete by package_id)
    await content.delete_package(data.package.package_id)
    await graph.delete_package(data.package.package_id)

    # 6. Write (LanceDB first, then Kuzu)
    await content.write_package(data.package)
    await content.write_closures(data.closures)
    await content.write_chains(data.chains)
    await content.write_probabilities(data.probabilities)
    await content.write_belief_snapshots(data.belief_snapshots)

    await graph.write_topology(data.closures, data.chains)
    await graph.update_beliefs({
        s.closure_id: s.belief
        for s in data.belief_snapshots
    })

    # 7. Embeddings (optional)
    try:
        import litellm
        pairs = [(c.closure_id, c.content) for c in data.closures if c.content.strip()]
        if pairs:
            ids, texts = zip(*pairs)
            response = litellm.embedding(model="text-embedding-3-small", input=list(texts))
            # Future: write to v2 VectorStore
    except Exception as e:
        typer.echo(f"  Skipped embeddings: {e}")

    # 8. Write receipt
    write_receipt(pkg_path / ".gaia" / "publish" / "receipt.json", data)

    typer.echo(f"Published {len(data.closures)} closures, "
               f"{len(data.chains)} chains to {db_path}")
```

### Changes Required to v2 Stores

Two new methods needed (not in current ABC):

| Store | New Method | Purpose |
|-------|-----------|---------|
| `LanceContentStore` | `delete_package(package_id)` | Delete all rows with matching package_id across all 6 tables |
| `KuzuGraphStore` | `delete_package(package_id)` | Delete all Closure/Chain nodes and relationships for package |

These support idempotent re-publish: delete old → insert fresh.

### Changes to Other CLI Commands

| Command | Change |
|---------|--------|
| `gaia build` | Add manifest.json serialization alongside existing .md output |
| `gaia infer` | Read manifest.json (not re-parse YAML), write infer_result.json |
| `gaia search` | Query v2 `closures` table instead of v1 `nodes` table |
| `gaia show` | Read v2 closures + chains instead of v1 nodes + hyperedges |
| `gaia review` | Reads single package.md (not per-module), updated prompt + response format |

---

## 8. Impact Summary

### New Files

| File | Purpose |
|------|---------|
| `cli/lang_to_v2.py` | Language → v2 storage model converter |
| `cli/manifest.py` | manifest.json serialize/deserialize helpers |
| `cli/infer_store.py` | infer_result.json serialize/deserialize helpers |
| `cli/prompts/review_system.md` | LLM review system prompt (terminology + instructions) |

### Modified Files

| File | Change |
|------|--------|
| `cli/main.py` | build: write manifest + single package.md; review: new prompt + report format; infer: read manifest + write infer_result; publish: rewrite to v2 |
| `cli/llm_client.py` | Updated prompt, new response parsing |
| `libs/storage_v2/lance_content_store.py` | Add `delete_package()` |
| `libs/storage_v2/kuzu_graph_store.py` | Add `delete_package()` |
| `libs/storage_v2/content_store.py` | Add `delete_package()` to ABC |
| `libs/storage_v2/graph_store.py` | Add `delete_package()` to ABC |

### Unchanged

| Component | Reason |
|-----------|--------|
| `libs/lang/compiler.py` | CompiledFactorGraph still used for BP in `gaia infer` |
| `libs/lang/elaborator.py` | Elaboration unchanged |
| `libs/lang/resolver.py` | Ref resolution unchanged |
| `libs/lang/loader.py` | Package loading unchanged (must parse `title` from YAML) |
| `libs/lang/models.py` | Module.title added (backward compatible, optional field) |
| `libs/lang/build_store.py` | Rewritten: single package.md with new format |
| `cli/review_store.py` | Review report format updated (see §3) |
| `services/` | Server code untouched |
| `libs/storage/` (v1) | Kept for backward compat, not modified |

### Test Plan

- Unit tests for `lang_to_v2.py` conversion (all 3 fixture packages)
- Unit tests for manifest.json roundtrip serialization
- Unit tests for infer_result.json roundtrip serialization
- Integration test: `build → review(mock) → infer → publish --local` for Galileo, Newton, Einstein
- Verify published data readable via `gaia search` and `gaia show`
- Verify cross-package publish (3 packages to same DB, no ID collision)
- Verify idempotent re-publish (publish twice, data unchanged)
