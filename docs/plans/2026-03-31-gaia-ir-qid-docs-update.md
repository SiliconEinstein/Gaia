# Gaia IR QID Docs Update — Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update all `docs/foundations/gaia-ir/` documentation to reflect the new QID-based Knowledge identity scheme from the cross-package identity design (#272).

**Architecture:** Knowledge nodes switch from hash-based `lcn_` IDs to human-readable QID format `{namespace}:{package_name}::{label}`. Strategy and Operator keep hash-based IDs. Global Knowledge keeps `gcn_` prefix. All 7 gaia-ir docs need targeted edits — no structural rewrite, just identity scheme updates.

**Tech Stack:** Markdown documentation

**Design doc:** `docs/plans/2026-03-31-cross-package-identity-design.md`

---

## Key Changes Summary

| Before | After |
|--------|-------|
| `Knowledge.id`: `lcn_` prefix (local), `gcn_` prefix (global) | `Knowledge.id`: QID `{ns}:{pkg}::{label}` (local), `gcn_` prefix (global) |
| `lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}` | `{namespace}:{package_name}::{label}` |
| Strategy premises/conclusion reference `lcn_` IDs (local) | Strategy premises/conclusion reference QIDs (local) |
| No `label`, `package_name`, `namespace` fields on Knowledge | New fields: `label`, `package_name`, `namespace` |
| `LocalCanonicalGraph` has no `namespace` | New field: `namespace` |
| `content_hash` role unchanged | `content_hash` role unchanged |
| Strategy/Operator IDs unchanged | Strategy/Operator IDs unchanged |

---

## Chunk 1: Core Identity Spec (03-identity-and-hashing.md)

This is the single source of truth for identity rules. Must be updated first.

### Task 1: Update Knowledge Identity in 03-identity-and-hashing.md

**Files:**
- Modify: `docs/foundations/gaia-ir/03-identity-and-hashing.md`

- [ ] **Step 1: Update §2 "Knowledge 身份"**

Replace the local Knowledge ID definition. The section currently says:

```
lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}
```

Replace with QID definition:

```
{namespace}:{package_name}::{label}
```

Update §2.1 to explain:
- Local Knowledge uses QID as its `id`
- QID is name-addressed (not content-addressed)
- `(namespace, package_name, label)` is the stable identity triple
- Label must be unique within a package (enforced at compile/extraction time)
- Two namespaces: `reg` (registry packages) and `paper` (extracted papers)
- Examples: `reg:galileo_falling_bodies::vacuum_prediction`, `paper:{metadata_id}::cmb_power_spectrum`

Update the three behavioral bullets:
- Same package, same label → same QID (regardless of content change)
- Different package, same label → different QID (different package_name)
- Same package, label renamed → different QID (breaking change)

§2.2 Global Knowledge stays as-is (`gcn_` prefix, registry-assigned).

- [ ] **Step 2: Update §1 "三类标识" table**

Update the table row for `Knowledge.id`:

| 名称 | 作用 | 作用域 | 是否跨包稳定 | 是否可随 representative 变化 |
|------|------|--------|--------------|------------------------------|
| `Knowledge.id` | 标识一个具体 Knowledge 对象 | local: QID / global: gcn_ | local: 否（含 package_name）；global: 是 | 否 |

- [ ] **Step 3: Update §4 "Strategy 与 Operator 的身份"**

Add a note clarifying that Strategy/Operator IDs remain hash-based, but their references to Knowledge (in `premises`, `conclusion`, `variables`) now use QIDs (local) or `gcn_` (global) instead of `lcn_`.

- [ ] **Step 4: Update §6 "三者如何配合" scenario**

Replace the scenario walkthrough. Current example uses `lcn_A...`, `lcn_B...`. Update to use QIDs:

1. Author in package A writes a claim with label `vacuum_prediction` → QID `reg:galileo_falling_bodies::vacuum_prediction`
2. Author in package B writes same-content claim with label `vacuum_prediction` → QID `reg:newton_principia::vacuum_prediction`
3. Two QIDs are different (different `package_name`)
4. Two `content_hash` values are the same (same content)
5. Canonicalization uses `content_hash` fast path → both bound to same `gcn_...`
6. `gcn_id` remains stable even if representative changes

- [ ] **Step 5: Update §7 "Validation 要点"**

Update item 1: local `Knowledge.id` must be a valid QID (format: `{namespace}:{package_name}::{label}`). Remove reference to "local ID 规则" based on hash.

- [ ] **Step 6: Commit**

```bash
git add docs/foundations/gaia-ir/03-identity-and-hashing.md
git commit -m "docs(gaia-ir): update 03-identity-and-hashing for QID-based Knowledge identity"
```

---

## Chunk 2: Core Schema (02-gaia-ir.md)

### Task 2: Update Knowledge schema and identity in 02-gaia-ir.md

**Files:**
- Modify: `docs/foundations/gaia-ir/02-gaia-ir.md`

- [ ] **Step 1: Update §1.1 Knowledge Schema**

In the Knowledge schema block (line 32-48), change:

```
    id:                     str              # lcn_ 或 gcn_ 前缀
```

to:

```
    id:                     str              # QID（local）或 gcn_ 前缀（global）
    label:                  str              # 包内唯一的人类可读标签
    package_name:           str              # 所属包名
    namespace:              str              # reg | paper
```

- [ ] **Step 2: Update §1.1 field usage table**

Update the `id` row (line 54):

| 字段 | Local | Global |
|------|-------|--------|
| `id` | QID 格式 `{namespace}:{package_name}::{label}`，name-addressed | `gcn_` 前缀，注册中心分配的稳定 canonical identity |

- [ ] **Step 3: Update §1.1 "对象身份" paragraph**

Replace the paragraph at line 61. Current:
> **对象身份**：local 层 `id = lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}`。ID 包含 `package_id`...

New:
> **对象身份**：local 层 `id` 使用 QID 格式 `{namespace}:{package_name}::{label}`，是 name-addressed identity。`(namespace, package_name, label)` 三元组唯一标识一个 Knowledge 节点。Label 在包内唯一（编译期/提取期强制保证）。不同包中相同内容的节点有**不同的** QID（不同 `package_name`）。global 层 `gcn_id` 是稳定的 canonical identity；它不随着 representative 或 content_hash 变化而重写。

- [ ] **Step 4: Update §3.2 Strategy field usage table**

Update the `premises`/`conclusion` row (line 330):

| 字段 | Local | Global |
|------|-------|--------|
| `premises`/`conclusion` | QID | `gcn_` ID |

- [ ] **Step 5: Update strategy_id hash formula note**

In the `strategy_id` hash formula (line 336), the `sorted(premises)` and `conclusion` are Knowledge IDs. Add a note that in local scope these are now QIDs, in global scope they remain `gcn_` IDs.

- [ ] **Step 6: Commit**

```bash
git add docs/foundations/gaia-ir/02-gaia-ir.md
git commit -m "docs(gaia-ir): update 02-gaia-ir Knowledge schema for QID identity"
```

---

## Chunk 3: Overview Examples (01-overview.md)

### Task 3: Update examples and identity descriptions in 01-overview.md

**Files:**
- Modify: `docs/foundations/gaia-ir/01-overview.md`

- [ ] **Step 1: Update local layer example (lines 151-211)**

Replace all `lcn_` IDs with QID format. Use a consistent example package (e.g., `reg:ybco_superconductivity`):

```json
{
  "scope": "local",
  "namespace": "reg",
  "ir_hash": "sha256:...",
  "knowledges": [
    {
      "id": "reg:ybco_superconductivity::sample_superconducts_90k",
      "label": "sample_superconducts_90k",
      "type": "claim",
      "content": "该样本在 90 K 以下表现出超导性"
    },
    {
      "id": "reg:ybco_superconductivity::tc_measurement",
      "label": "tc_measurement",
      "type": "claim",
      "content": "YBa₂Cu₃O₇ 的超导转变温度为 92 ± 1 K"
    },
    {
      "id": "reg:ybco_superconductivity::research_context",
      "label": "research_context",
      "type": "setting",
      "content": "高温超导研究的当前进展"
    },
    {
      "_comment": "全称 claim（原 template）— 通用定律，含量化变量，参与 BP",
      "id": "reg:ybco_superconductivity::superconductor_zero_resistance",
      "label": "superconductor_zero_resistance",
      "type": "claim",
      "content": "∀{x}. superconductor({x}) → zero_resistance({x})",
      "parameters": [{"name": "x", "type": "material"}]
    },
    {
      "_comment": "绑定 setting — 实例化时提供具体参数值",
      "id": "reg:ybco_superconductivity::binding_ybco",
      "label": "binding_ybco",
      "type": "setting",
      "content": "x = YBa₂Cu₃O₇（YBCO）"
    },
    {
      "_comment": "实例化后的封闭 claim",
      "id": "reg:ybco_superconductivity::ybco_zero_resistance",
      "label": "ybco_zero_resistance",
      "type": "claim",
      "content": "superconductor(YBCO) → zero_resistance(YBCO)"
    }
  ],
  "strategies": [
    {
      "strategy_id": "lcs_d2c8...",
      "type": "infer",
      "premises": ["reg:ybco_superconductivity::sample_superconducts_90k"],
      "conclusion": "reg:ybco_superconductivity::tc_measurement",
      "background": ["reg:ybco_superconductivity::research_context"],
      "steps": [{"reasoning": "基于超导样品的电阻率骤降..."}]
    },
    {
      "_comment": "全称 claim 的实例化 — deduction, p₁=1.0",
      "strategy_id": "lcs_h7ea...",
      "type": "deduction",
      "premises": ["reg:ybco_superconductivity::superconductor_zero_resistance"],
      "conclusion": "reg:ybco_superconductivity::ybco_zero_resistance",
      "background": ["reg:ybco_superconductivity::binding_ybco"]
    }
  ],
  "operators": []
}
```

- [ ] **Step 2: Update global layer example (lines 213-267)**

Global layer keeps `gcn_` IDs — no change to the Knowledge IDs themselves. But update `local_members` references if present, and ensure the narrative explains that global layer references local QIDs through `local_members` / `representative_lcn`.

The global example already uses `gcn_` format, so only minor narrative updates are needed (no ID format changes in global examples).

- [ ] **Step 3: Update §身份与哈希 section (lines 327-342)**

Update the identity overview paragraph and table:

Current (line 331):
> - **对象身份**：`lcn_/gcn_`、`lcs_/gcs_`、`lco_/gco_`

New:
> - **对象身份**：Knowledge 使用 QID（local）/ `gcn_`（global）；Strategy 使用 `lcs_/gcs_`；Operator 使用 `lco_/gco_`

Update the table (lines 337-340):

| 层 | 范围 | Knowledge ID | Strategy/Operator ID | 内容 |
|----|------|-------------|---------------------|------|
| **LocalCanonicalGraph** | 单个包 | QID `{ns}:{pkg}::{label}` | `lcs_`, `lco_` | 存储完整 content + Strategy steps（内容仓库） |
| **GlobalCanonicalGraph** | 跨包 | `gcn_` | `gcs_`, `gco_` | 引用 representative，Strategy 无 steps（结构索引）+ Operator |

Update line 342:
> `Knowledge.content_hash` 独立于 QID：相同内容的 local 节点可以有不同 QID（不同包），但共享同一个 `content_hash`。

- [ ] **Step 4: Commit**

```bash
git add docs/foundations/gaia-ir/01-overview.md
git commit -m "docs(gaia-ir): update 01-overview examples and identity table for QID"
```

---

## Chunk 4: Canonicalization, Validation, Lowering, Parameterization

### Task 4: Update 05-canonicalization.md

**Files:**
- Modify: `docs/foundations/gaia-ir/05-canonicalization.md`

- [ ] **Step 1: Update §1 作用 (line 15)**

Current:
> - 将 `lcn_` / `lcs_` / `lco_` 映射到 `gcn_` / `gcs_` / `gco_`

New:
> - 将 local Knowledge QID / `lcs_` / `lco_` 映射到 `gcn_` / `gcs_` / `gco_`

- [ ] **Step 2: Update §5 CanonicalBinding (lines 99-109)**

Update `local_canonical_id` field to reflect QID:

```
CanonicalBinding:
    local_id:               str    # Knowledge: QID; Strategy: lcs_; Operator: lco_
    global_id:              str    # Knowledge: gcn_; Strategy: gcs_; Operator: gco_
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new" | "equivalent_candidate"
    reason:                 str    # 匹配原因（如 "cosine similarity 0.95"）
```

- [ ] **Step 3: Update §6 Strategy 提升 (lines 112-119)**

Current (line 115):
> 1. 从 CanonicalBinding 构建 `lcn_ -> gcn_` 映射
> 2. 从全局 Knowledge 元数据构建 `ext: -> gcn_` 映射（跨包引用解析）

New:
> 1. 从 CanonicalBinding 构建 `QID -> gcn_` 映射（本包 Knowledge）
> 2. 跨包引用的 QID 直接查找已有 global Knowledge（无需 `ext:` 特殊处理）

- [ ] **Step 4: Update §8.1 中间 Knowledge 的创建 (lines 142-148)**

Current (line 146):
> - Local 层：中间 Knowledge 获得 `lcn_` ID，归属于当前包

New:
> - Local 层：中间 Knowledge 获得 QID（`{ns}:{pkg}::{generated_label}`），归属于当前包

- [ ] **Step 5: Commit**

```bash
git add docs/foundations/gaia-ir/05-canonicalization.md
git commit -m "docs(gaia-ir): update 05-canonicalization for QID-based Knowledge identity"
```

### Task 5: Update 08-validation.md

**Files:**
- Modify: `docs/foundations/gaia-ir/08-validation.md`

- [ ] **Step 1: Update §2 Knowledge 校验 (lines 44-47)**

Current:
> 1. `id` 前缀与 graph scope 一致
>    - local: `lcn_`
>    - global: `gcn_`

New:
> 1. `id` 格式与 graph scope 一致
>    - local: 有效 QID 格式 `{namespace}:{package_name}::{label}`
>    - global: `gcn_` 前缀

Add new validation rules:
> 9. `label` 在同一 `LocalCanonicalGraph` 内必须唯一
> 10. `namespace` 必须属于允许集合（`reg` | `paper`）
> 11. `package_name` 必须与所属 `LocalCanonicalGraph.package` 一致

- [ ] **Step 2: Update §7.1 LocalCanonicalGraph (line 133)**

Current:
> 3. local 对象一律使用 `lcn_ / lcs_ / lco_`

New:
> 3. local Knowledge 使用 QID 格式；local Strategy 使用 `lcs_`；local Operator 使用 `lco_`

- [ ] **Step 3: Update §7.2 GlobalCanonicalGraph (line 139)**

Current:
> 2. global 对象一律使用 `gcn_ / gcs_ / gco_`

Keep as-is — global IDs are unchanged.

- [ ] **Step 4: Commit**

```bash
git add docs/foundations/gaia-ir/08-validation.md
git commit -m "docs(gaia-ir): update 08-validation Knowledge ID rules for QID"
```

### Task 6: Update 07-lowering.md

**Files:**
- Modify: `docs/foundations/gaia-ir/07-lowering.md`

- [ ] **Step 1: Update §2.1 identity preservation (line 53)**

Current:
> backend 在 runtime 层保留的是**对象 identity**（如 `gcn_...` / `lcn_...`），不是 `content_hash`。

New:
> backend 在 runtime 层保留的是**对象 identity**（如 Knowledge QID / `gcn_...`、Strategy `lcs_...` / `gcs_...`），不是 `content_hash`。

- [ ] **Step 2: Commit**

```bash
git add docs/foundations/gaia-ir/07-lowering.md
git commit -m "docs(gaia-ir): update 07-lowering identity reference for QID"
```

### Task 7: Update 06-parameterization.md

**Files:**
- Modify: `docs/foundations/gaia-ir/06-parameterization.md`

- [ ] **Step 1: Update PriorRecord schema (line 21)**

Current:
> `gcn_id:             str              # 全局 claim Knowledge ID`

This references global IDs — `gcn_` is unchanged. No edit needed here.

However, scan the file for any `lcn_` references. The file only uses `gcn_` and `gcs_` since parameterization is global-only. **No changes needed for 06-parameterization.md.**

- [ ] **Step 2: Confirm and skip commit**

Verify 06-parameterization.md has no `lcn_` references. If confirmed, skip commit for this file.

---

## Final Verification

### Task 8: Cross-reference check

- [ ] **Step 1: Grep for remaining `lcn_` in gaia-ir/ docs**

```bash
grep -n "lcn_" docs/foundations/gaia-ir/*.md
```

Expected: Only references in contexts that discuss global-layer concepts (like `representative_lcn` field name, `local_members`, `CanonicalBinding`) or in historical/migration notes. No references to `lcn_` as a Knowledge ID format.

Note: `representative_lcn` and `local_members` are field names that reference local Knowledge — these field names may need renaming to `representative_local` or similar, but that's a schema naming decision separate from the identity format change. Flag for discussion if found.

- [ ] **Step 2: Verify internal doc links still work**

```bash
# Check no broken cross-references within gaia-ir/
grep -r '\[.*\](.*\.md' docs/foundations/gaia-ir/ | grep -v node_modules
```

- [ ] **Step 3: Final commit (if any remaining fixes)**

```bash
git add docs/foundations/gaia-ir/
git commit -m "docs(gaia-ir): fix remaining lcn_ references after QID migration"
```
