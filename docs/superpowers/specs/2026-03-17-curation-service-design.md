# Curation Service Design

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-17 |
| 状态 | Draft |
| 关联文档 | [../../foundations/server/architecture.md](../../foundations/server/architecture.md) §5.3, [../../foundations/graph-ir.md](../../foundations/graph-ir.md), [../../foundations/theory/inference-theory.md](../../foundations/theory/inference-theory.md) §3 |

---

## 1. 动机

全局知识图由多个 package 的作者独立贡献。Package review（简化版）在 publish 时做自动 global canonicalization，但这是 per-package 的局部视角。有些问题只有站在全局视角才能发现：

- Review 时漏掉的跨 package 重复（措辞差异太大，自动匹配没发现）
- 跨 package 的隐含矛盾（各自 review 通过，但结论互相否定）
- 多次 merge/cleanup 后的图结构退化（悬空引用、孤立节点）
- 多个具体 claim 可以提炼出更高层的抽象或归纳

Curation Service 是离线全局图维护服务，与 BP Service 共同构成离线维护机制。执行顺序：**Curation → BP**——先在结构上清理图，再在清洁的图上跑信念传播。

## 2. 与 Review Engine 的分工

| | 简化版 Review Engine | Curation Service |
|---|---|---|
| **触发时机** | 实时，每次 publish | 定时调度（后续加事件驱动） |
| **视角** | 单个 package vs 全局图 | 全局图 vs 全局图 |
| **职责** | Global canonicalization（local node → global node 映射） | 发现 review 遗漏的全局问题 |
| **输出** | CanonicalBinding（立即生效） | 建议（需审核后执行） |

Review engine 保证 publish 后节点立刻进入 global graph。Curation 负责后续修正和增强。

## 3. 五个核心职责

### 3.1 Clustering（相似节点聚类）

发现全局图中语义相似但尚未关联的 GlobalCanonicalNode 组。

**做法**：
- 对所有 GlobalCanonicalNode 的 embedding 做 ANN 搜索，找高相似度 pair
- BM25 关键词匹配做二次确认（双路召回）
- 输出：候选相似组，每组带 similarity score

**不做**：判断相似组的关系类型——交给 classification 步骤。

### 3.2 知识关系处理

对聚类结果进行多种关系处理，拆分为四个独立操作：

#### 3.2.1 重复命题去重

对 content hash 完全相同的 GlobalCanonicalNode 进行合并。

- **判定标准**：content hash 精确匹配，零误判
- **图操作**：合并 GlobalCanonicalNode（保留较早创建的节点，将 member_local_nodes 合并，重定向 factor 引用）
- **执行方式**：全自动，无需审核

#### 3.2.2 Abstraction（抽象提炼）

分 batch 调用 abstraction agent，从聚类组中发现可抽象的知识组，创建抽象结构。

**输入**：3.1 聚类输出的相似组

**Agent 职责**：
1. 识别有共同点、可进行 abstract 的 knowledge group
2. 为每个 group 创建 abstraction factor 以及被 abstract 出的更弱的概括命题（schema node）
3. 给出可能产生矛盾的 candidate knowledge pair（移交 3.3 处理）

**图操作**：
- 创建 schema node（概括命题）+ instantiation factor（具体 → 抽象）
- 格论方向：向上（保真，p 可 = 1.0）

#### 3.2.3 Analysis（矛盾发现与归纳假设）

在 3.2.2 构建的 abstraction tree 基础上，调用 analyze agent 进行深层分析。

**输入**：3.2.2 产出的 abstraction tree（schema node + instantiation 结构）

**Agent 职责**：
1. 在 abstraction tree 中发现真正矛盾的命题——同一 schema 下的 instance 之间、或不同抽象层级之间存在语义冲突的 pair
2. 识别有意思的、可以被归纳的 hypothesis——多个 instance 呈现出某种 pattern，值得提出更强的泛化 claim

**输出**：
- Confirmed contradiction pair → 创建 contradiction factor，移交 3.3 进一步处理
- Induction hypothesis candidate → 记录为待验证假设，供后续 induction tree 构建使用

#### 3.2.4 LLM-based 等价判断（V2）

对语义等价但措辞/角度不同的命题进行等价关系识别。

- **判定方式**：LLM 判断两个命题是否语义等价
- **图操作**：创建 equivalence constraint factor
- **状态**：V2 再做

#### 3.2.5 Induction Tree 构建（后续）

从多个具体 instance 归纳出更强的泛化 claim，构建归纳树。

- **图操作**：创建泛化 claim + induction chain
- **格论方向**：向下（不保真，p 必须 < 1.0）
- **状态**：后续再做

### 3.3 Conflict Discovery（矛盾发掘）

检测图中隐含的矛盾——两个高置信度结论通过推理链互相否定，但未被显式标记为 contradiction。

**三级漏斗 pipeline**：

```
Level 1: BP 信号检测（零成本，BP 副产物）
  → 收敛不稳定的节点（damping 后仍震荡）
  → belief 在 0.4-0.6 附近、多次迭代变化方向交替的节点对
  → 输出：候选矛盾区域

Level 2: Sensitivity analysis（中等成本，需要多次 BP）
  → 对 Level 1 候选区域，逐个 clamp 节点为 true
  → 看哪些其他节点 belief 显著下降（A↑ 导致 B↓ = 对抗关系）
  → 输出：候选矛盾 pair + 对抗强度

Level 3: LLM 验证（高成本，只对少量候选）
  → 对 Level 2 的高置信候选，调 LLM 确认是否为语义矛盾
  → 输出：confirmed contradiction + 诊断报告
```

V1 先做 Level 1 + 2，Level 3 后续加。

参考旧版 §6.6 的三级 pipeline 思路（ANN + cross-encoder + LLM），但用 BP 信号替代语义相似度作为矛盾召回——因为矛盾的两个命题措辞往往不相似。

### 3.4 Structure Inspection（全图结构巡检）

检查图的健康状态：

| 检查项 | 严重度 | 说明 |
|--------|--------|------|
| 孤立节点 | warning | GlobalCanonicalNode 无任何 factor 连接 |
| 悬空 factor | error | Factor 引用的节点已被删除或合并 |
| 度数异常 | info | 某节点作为 premise 参与过多 factor（可能需要拆分） |
| 不连通子图 | info | 图分成多个不连通的 component |

输出：`StructureReport`，按严重度分级。

### 3.5 Cleanup（图清理）

基于上述步骤的输出执行图修改。

**执行策略（三档自动化）**：

| 置信度 | 处理方式 | 示例 |
|--------|---------|------|
| > 0.95 | 自动执行 | embedding cosine > 0.98 的合并 |
| 0.7 - 0.95 | Curation reviewer agent 审核后执行 | 等价关系创建、abstraction |
| < 0.7 | 丢弃 | 低置信度的矛盾猜测 |

**操作类型**：
- 合并节点：更新 GlobalCanonicalNode 的 member_local_nodes，重定向 factor 引用
- 创建 constraint：创建 equivalence 或 contradiction factor
- 创建 schema + instantiation：abstraction 产生新节点和 factor
- 创建 induction chain：induction 产生新 claim 和 reasoning factor（p < 1.0）
- 修复结构：移除悬空 factor，标记/归档孤立节点

每次操作生成 audit log，支持回滚。

## 4. 共用底层能力

Global canonicalization（review 阶段）、incremental curation（事件驱动，后续）、global curation（定时）三个流程共用同一组底层函数：

```
libs/curation/
  similarity.py     find_similar(node, candidates, threshold)  → vector + BM25
  conflict.py       detect_conflict(node_a, node_b, graph)     → belief sensitivity
  structure.py      check_structure(subgraph)                   → 图健康检查
  operations.py     merge_nodes(source, target, graph)          → 合并 + 重定向
                    create_constraint(node_a, node_b, type)     → 创建 factor
                    create_abstraction(instances, schema)        → schema + instantiation
                    create_induction(instances, generalization)  → claim + chain
```

区别只是搜索范围：

| 流程 | 范围 | 触发 |
|------|------|------|
| Global canonicalization | 1 个 local node vs 全局图 | publish 时实时 |
| Incremental curation | 新 package 节点 vs 邻域 | publish 后事件触发（后续） |
| Global curation | 全局 N:N | 定时调度 |

## 5. 调度流程

```
定时触发
  │
  ▼
cluster_similar_nodes()           ← 3.1 聚类
  │
  ▼
deduplicate_by_hash()            ← 3.2.1 重复命题去重（content hash）
  │
  ▼
abstract_knowledge_groups()      ← 3.2.2 Abstraction agent（分 batch）
  │                                  → 输出 abstraction tree（schema node + factor）
  │
  ▼
analyze_abstraction_tree()       ← 3.2.3 Analyze agent
  │                                  → 输出 contradiction pair → 3.3
  │                                  → 输出 induction hypothesis candidate
  │
  ▼
discover_contradictions()         ← 3.3 矛盾发掘（BP Level 1 + 2）
  │
  ▼
inspect_structure()               ← 3.4 结构巡检
  │
  ▼
generate_cleanup_plan()           ← 汇总所有建议
  │
  ├─ 置信度 > 0.95 → 自动执行
  ├─ 0.7 - 0.95 → curation reviewer agent 审核
  └─ < 0.7 → 丢弃
  │
  ▼
execute_cleanup(approved_plan)    ← 3.5 执行 + audit log
  │
  ▼
触发 BP Service                    ← 在清洁的图上跑信念传播
```

## 6. Curation Reviewer Agent

审核中等置信度建议的轻量 agent。与 package review agent 分离——判断标准不同：

- Package review：这个 package 的推理对不对？
- Curation review：这两个节点是不是同一个东西？这个抽象合理吗？

输入：一条 curation 建议（候选操作 + 证据 + 置信度）
输出：approve / reject / modify

## 7. V1 范围

| 功能 | V1 | 后续 |
|------|:---:|:---:|
| 定时调度 | ✓ | |
| 事件驱动（增量 curation） | | ✓ |
| Clustering（vector + BM25） | ✓ | |
| 重复命题去重（content hash） | ✓ | |
| Abstraction（abstraction agent） | ✓ | |
| Analysis（矛盾发现 + 归纳假设） | ✓ | |
| LLM-based 等价判断 | | ✓（V2） |
| Induction tree 构建 | | ✓ |
| Conflict discovery Level 1（BP 信号） | ✓ | |
| Conflict discovery Level 2（sensitivity） | ✓ | |
| Conflict discovery Level 3（LLM） | | ✓ |
| Structure inspection | ✓ | |
| Cleanup: 合并 / constraint 创建 | ✓ | |
| Cleanup: schema + instantiation | | ✓ |
| Cleanup: induction chain | | ✓ |
| 三档自动化执行策略 | ✓ | |
| Curation reviewer agent | ✓（简化版） | |
| Audit log + 回滚 | ✓ | |

## 8. 不在此次范围

- 简化版 review engine（global canonicalization）——单独设计
- BP Service 的改动
- LLM-based contradiction detection (Level 3)
- Cross-encoder 矛盾分类器训练
- LLM-based 等价判断（V2）
- Induction tree 构建
