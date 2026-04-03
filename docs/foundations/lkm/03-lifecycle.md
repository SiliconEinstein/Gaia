# Write Side 生命周期

> **Status:** Target design

## 概述

Write side 描述数据如何进入 LKM 并最终反映在全局信念状态中。完整流程：

```
数据源 → Ingest (lower/extract) → Integrate (确定性去重) → Curation (语义去重) → Global BP
```

Ingest + integrate 是同步的、per-package 操作。Curation + BP 是异步的、全局操作。

## Ingest

Ingest 将外部数据转换为 local FactorGraph。两条 pipeline 针对不同数据源，产出相同的结构。

### Pipeline A：Gaia IR（社区内容）

```
已注册包 (Gaia IR + validated review reports)
  → lower: 展开 Strategy/Operator 到 leaf level，生成 private variable nodes
  → 注入参数化: PriorRecord + FactorParamRecord (from validated review reports, source_class: official)
  → local FactorGraph + 参数化记录
```

LKM 只消费通过 [Registry 完整验证流程](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/ecosystem/04-registry-operations.md) 的包——包括 reviewer 身份验证、assignment 匹配、report 数量达标、参数范围合法。

Lowering 是确定性的。详见 [Lowering 契约](https://github.com/SiliconEinstein/Gaia/blob/main/docs/foundations/gaia-ir/07-lowering.md)。

Lowering 过程中：
- 每个 Knowledge (claim/setting/question) → `visibility: "public"` 的 variable node
- FormalStrategy 展开产生的中间节点 → `visibility: "private"` 的 variable node
- Leaf Strategy (infer/noisy_and) → `factor_type: "strategy"` 的 factor node
- Operator (equivalence/contradiction/...) → `factor_type: "operator"` 的 factor node
- CompositeStrategy 展开为 leaf strategies，不出现在 FactorGraph 中

Validated review reports 提供 PriorRecord（`source_class: official`）和 FactorParamRecord（`source_class: official`）。

### Pipeline B：XML（存量论文）

```
论文 XML (arXiv, PubMed, ...)
  → rule-based extraction: 提取命题、推理关系、引用
  → 估计参数化: PriorRecord + FactorParamRecord
  → local FactorGraph + 参数化记录
```

Rule-based 确定性提取，不涉及 ML。参数由提取规则根据元数据（期刊等级、引用数等）估计。

### Source Class

两个数据源的参数质量差异通过参数化层的 `ParameterizationSource.source_class` 区分：

| 来源 | `source_class` | 说明 |
|------|---------------|------|
| 社区内容（经 Review） | `official` | 参数由 reviewer 赋值，经 registry 验证 |
| 存量论文（XML 提取） | `heuristic` | 参数由规则根据元数据估计 |

## Integrate

将 local FactorGraph 集成到 global FactorGraph。同步操作，per-package。**包含确定性去重。**

### Variable 去重（content_hash）

对每个 local variable node（仅 `visibility: "public"`）：

1. 计算 `content_hash`
2. 在 `global_variable_nodes` 中查找相同 `content_hash` 的 variable（走索引，O(1)）
3. **匹配** → 写入 CanonicalBinding（`decision=match_existing`），更新 global node 的 `local_members`
4. **无匹配** → 新建 GlobalVariableNode，写入 CanonicalBinding（`decision=create_new`）

这是 O(1) 哈希查找，确定性的，不涉及语义匹配。保证完全相同的命题从 integrate 开始就有稳定的 gcn_id。

`visibility: "private"` 的 variable 直接分配新 gcn_id，不走 hash 查找（它们是特定 FormalStrategy 的内部节点，不跨包去重）。

### Factor 去重（精确匹配）

对每个 local factor node：

1. 用 CanonicalBinding 将 premises/conclusion 的 local QIDs 映射为 gcn_ids
2. 在 `global_factor_nodes` 中查找相同 `premises + conclusion + factor_type + subtype` 的 factor
3. **匹配** → 复用已有 global factor，追加新的 FactorParamRecord（不同来源对同一推理关系的参数评估）
4. **无匹配** → 新建 GlobalFactorNode

`factor_type` 或 `subtype` 不同则视为独立 factor（不同类型的推理关系，不是重复）。

### 跨包引用解析（QID）

Gaia IR 中的 Knowledge 使用 QID（Qualified Node ID）作为 local identity：

```
{namespace}:{package_name}::{label}
```

其中 `namespace` 为 `reg`（注册表包）或 `paper`（提取的论文）。`package_name` 在各自 namespace 内保证全局唯一（`reg` 由 registry 强制，`paper` 由数据库 metadata ID 保证）。跨包引用在 IR 中直接使用目标 Knowledge 的 QID，不需要 `ext:` 特殊前缀——`package_name` 本身已经是 disambiguator。

Integrate 时的解析流程：

1. Factor 的 premises/conclusion 中出现非本包的 QID → 跨包引用
2. 查 CanonicalBinding 或 `global_variable_nodes` 找到该 QID 对应的 gcn_id
3. **命中** → 替换为 gcn_id
4. **未命中**（目标包尚未 ingest）→ 该 factor 被丢弃，记录在 `unresolved_cross_refs` 中，供后续 curation 阶段处理

### 写入存储

按 [写入协议](02-storage.md) 写入：local FactorGraph + CanonicalBinding + global FactorGraph + 参数化记录。

## Curation

异步批量的图维护操作。处理 integrate 无法发现的语义级冗余和冲突。

详见 [04-curation.md](04-curation.md)。

## Global BP

Curation 完成后，在 global FactorGraph 上运行 loopy BP。从 PriorRecord / FactorParamRecord 按 resolution_policy 解析出具体参数值，运行推理，结果写入 BeliefSnapshot。

详见 [05-global-inference.md](05-global-inference.md)。

## 流程时序

```
t0  Package A arrives → ingest → integrate (content_hash dedup + factor dedup)
t1  Package B arrives → ingest → integrate (same)
t2  Package C arrives → ingest → integrate (same)
t3  Curation runs (async)          — 语义匹配发现近义 variables，合并或创建 equivalence
t4  Global BP runs                 — beliefs updated
t5  Package D arrives → ingest → integrate
t6  Curation runs (incremental)
t7  Global BP runs
...
```

Curation 和 BP 的触发策略是可配置的：每次 integrate 后触发、按时间间隔批量触发、或手动触发。

## 当前实现

当前 write side 通过批处理脚本实现（`scripts/pipeline/run_full_pipeline.py`），7 个阶段作为子进程顺序执行。这是临时方案，用于初始数据填充和开发验证。

目标状态：ingest + integrate 由 HTTP 端点触发（`POST /packages/ingest`），curation 作为后台定时任务运行，BP 在 curation 完成后异步触发。
