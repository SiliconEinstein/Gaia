# Gaia 包管理与证据系统设计

| 文档属性 | 值 |
|---------|---|
| 状态 | **Proposal** |
| 日期 | 2026-03-28 |
| 设计决策 | [decentralized-architecture.md](../foundations/ecosystem/03-decentralized-architecture.md) |
| 关联文档 | [02-gaia-ir.md](../foundations/gaia-ir/02-gaia-ir.md), [package-model.md](../foundations/gaia-lang/package-model.md) |

## 1. 目的

定义 Gaia 去中心化包管理架构的具体实现方案。设计决策和原则见 [decentralized-architecture.md](../foundations/ecosystem/03-decentralized-architecture.md)。

## 2. 包模型

### 2.1 身份与版本

**身份：UUID + 人类可读名（Julia 模型）。** 不同作者可能创建同名包，UUID 避免冲突，也为未来多 registry 做准备。

```toml
# typst.toml
[package]
uuid = "336ed68f-0bac-5ca0-87d4-7b16caf5d00b"
name = "galileo-falling-bodies"
version = "4.0.0"
```

**版本：semver，重新定义 breaking change 含义。**

| semver | 含义 | 例子 |
|--------|------|------|
| MAJOR | 导出 claim 语义变化或撤回 | "Tc = 92K" → "Tc = 89K" |
| MINOR | 新增 claim/strategy，已有导出不变 | 增加新实验证据 |
| PATCH | 措辞修正、metadata 更新，语义不变 | 修正错别字 |

### 2.2 依赖声明

依赖直接指向 git 仓库，不依赖注册表：

```yaml
# gaia-deps.yml
vacuum_prediction:
  repo: "https://github.com/galileo/falling-bodies"
  tag: "v4.0.0"
  node: "vacuum_prediction"
  content_hash: "sha256:a3f2..."
  role: premise                    # premise | independent_evidence | refinement
```

`role` 是作者的可选声明（默认 `premise`），表达"我的工作和这个已有 claim 是什么关系"。这是效率辅助（帮 reviewer 快速定位），不是安全机制——系统正确性不依赖作者诚实。

### 2.3 锁文件

```yaml
# gaia-lock.yml（自动生成，纳入 VCS）
lock_version: 1
generated_at: "2026-03-28T12:00:00Z"

resolved:
  vacuum_prediction:
    repo: "https://github.com/galileo/falling-bodies"
    commit: "abc123def..."
    content_hash: "sha256:a3f2..."
```

| 操作 | 行为 |
|------|------|
| `gaia build` | 有 lock → 用精确版本；无 lock → 解析并生成 |
| `gaia update` | 重新解析到最新兼容版本，更新 lock |
| `gaia update <dep>` | 只更新指定依赖 |

**可重现性保证**：source + gaia-deps.yml + gaia-lock.yml → 确定性 LocalCanonicalGraph → ir_hash 可验证。

### 2.4 编译产物

```
my-package/
  typst.toml
  gaia-deps.yml
  gaia-lock.yml
  src/
    ...
  .gaia/                        # 编译产物（纳入 VCS）
    ir.json                     # LocalCanonicalGraph
    ir_hash                     # 完整性校验
    beliefs.json                # 导出 claim 的 beliefs
```

## 3. 包级概率流动

### 3.1 `gaia build` + `gaia infer` 流程

`gaia build` 是确定性编译，不运行 BP。`gaia infer` 在编译产物上运行 local BP。

```
gaia build:
  1. 解析 gaia-deps.yml + gaia-lock.yml
  2. 拉取依赖包的 .gaia/beliefs.json → 获取 premise beliefs
  3. 编译 LocalCanonicalGraph
  4. 输出 .gaia/ir.json + ir_hash

gaia infer:
  5. 在 LocalCanonicalGraph 上运行 local BP（融合依赖 beliefs 作为 premise priors）
  6. 输出 .gaia/beliefs.json
```

### 3.2 流动示例

```
Package A (基础实验)          Package B (理论推导)         Package C (应用预测)
  claim₁ = 0.90  ──pull──►   claim₃ = 0.82  ──pull──►  claim₅ = 0.71
  claim₂ = 0.85  ──pull──►   claim₄ = 0.76

A 更新 → claim₁: 0.95
B 重新 build + infer → claim₃: 0.86
C 重新 build + infer → claim₅: 0.74
```

### 3.3 更新传播

| 模式 | 触发方式 | 适用场景 |
|------|---------|---------|
| Lazy（默认） | 下游 `gaia update && gaia build && gaia infer` | 最简单，下游决定何时更新 |
| Pull | CI 定期检查依赖 beliefs 变化 | GitHub Actions cron |
| Push | 上游发布时 webhook 通知 | 活跃维护的包 |

## 4. Registry 实现

### 4.1 仓库结构

```
github.com/gaia-project/registry/
├── packages/                          # 包注册信息
│   ├── galileo-falling-bodies/
│   │   ├── Package.toml               # uuid, name, repo URL
│   │   ├── Versions.toml              # 版本 → ir_hash → git tag
│   │   └── Deps.toml                  # 每个版本的依赖
│   └── newton-principia/
│       └── ...
├── reviews/                           # 参数化记录
│   ├── sources.jsonl                  # ParameterizationSource
│   ├── priors/                        # PriorRecord（按 content_hash 分文件）
│   └── strategies/                    # StrategyParamRecord
├── beliefs/                           # 增量 BP 输出（按 shard 存储）
│   ├── index.json                     # content_hash → belief 索引
│   └── shards/
├── merges/                            # 迟发现合并记录
│   └── merges.jsonl
└── .github/workflows/
    ├── register.yml                   # 注册验证
    ├── review.yml                     # review 合规检查
    └── incremental-bp.yml             # 增量局部 BP
```

### 4.2 注册流程

```
作者在包仓库 release tag v4.0.0
  ↓
@GaiaRegistrator register（GitHub App / issue comment）
  ↓
Bot 创建 PR 到 registry 仓库：
  + packages/my-package/Package.toml
  + packages/my-package/Versions.toml（新增条目）
  + packages/my-package/Deps.toml
  ↓
CI 自动验证（register.yml）：
  ✓ 克隆包仓库，重新编译 IR，验证 ir_hash
  ✓ 依赖全部在 registry 中可解析
  ✓ Schema 合法
  ↓
等待期（新包 3 天，版本更新 1 小时）
  ↓
自动合并
```

### 4.3 Review 流程

任何人通过 PR 提交 review：

```json
// reviews/priors/sha256_a1b2.json
{
  "content_hash": "sha256:a1b2...",
  "value": 0.75,
  "source_id": "reviewer_alice_mit",
  "created_at": "2026-03-28T15:00:00Z"
}
```

CI 验证（review.yml）：content_hash 存在、value ∈ [ε, 1-ε]（Cromwell's rule）、source 信息完整。合并后自动触发增量 BP。

## 5. Registry 增量 BP

Registry 层提供增量局部 BP 作为快速反馈机制。每次变更只需计算受影响的局部子图，无需等待 LKM 全局 BP。LKM 的全局 BP 仍然存在，用于十亿节点规模的完整证据汇聚（参见 [global-inference.md](../foundations/lkm/global-inference.md)）。

### 5.1 触发与范围

```yaml
# incremental-bp.yml
on:
  push:
    paths: ['reviews/**']

steps:
  - name: Identify affected subgraph
    run: gaia affected-subgraph --change $CHANGE --hops 3

  - name: Run local BP on subgraph
    run: gaia incremental-bp --subgraph affected.json --threshold 1e-4

  - name: Update changed beliefs
    run: gaia update-beliefs --output beliefs/shards/
```

| 触发 | 子图大小 | 耗时 |
|------|---------|------|
| 新包注册 | ~100-500 nodes | 毫秒 |
| 新 review | ~50-200 nodes | 毫秒 |
| 合并操作 | ~200-1000 nodes | 几十毫秒 |

计算量与总图大小无关。高连接度节点用 lazy propagation（截断传播，按需计算）。

### 5.2 beliefs 存储

按 Knowledge 分片存储：

```
beliefs/
  index.json                    # content_hash → belief 索引
  shards/
    00/sha256_00a1...json       # 单个 Knowledge 的 belief
    01/...
```

包 `gaia infer` 时只拉取自己依赖的那几个 belief 文件。

## 6. Review 流程

Reviewer 对每条待审 Strategy 做两件事：标注关系、赋参数。

### 6.1 sub_strategy 关系标注

CompositeStrategy 内部的 sub_strategies 之间的关系：

| 关系 | 含义 | 展开时 BP 行为 |
|------|------|---------------|
| **independent** | 独立证据（不同实验/方法/数据） | 独立 factor |
| **duplicate** | 同一论证的不同表述 | 不额外贡献 |
| **refinement** | 细化已有推理的内部结构 | 替代被细化者（更精细） |

标注依据不是 premises 是否相同，而是推理过程本身是否独立——这在 Strategy 的 steps 中，只有 reviewer 能判断。

### 6.2 参数赋值

| 对象 | 操作 |
|------|------|
| independent sub_strategy | 赋 StrategyParamRecord → 展开时成为独立 factor |
| duplicate sub_strategy | 不赋参数 |
| refinement sub_strategy | 升级被细化的 Strategy 为 FormalStrategy/CompositeStrategy |
| CompositeStrategy 本身 | 赋折叠参数（综合内部结构） |

### 6.3 判断流程

```
Reviewer 审查新 sub_strategy gcs_B：

Q1: gcs_B 的推理和已有 sub_strategies 的关系？

├── 本质相同的论证 → duplicate
│   → 不赋参数，保留在 sub_strategies 中做记录
│
├── 展开了已有推理的内部结构 → refinement
│   → 已有 Strategy 升级为 FormalStrategy/CompositeStrategy
│   → 折叠参数不变（或 reviewer 微调）
│   → 粗图 BP 不变；细图多了展开选项
│
└── 提供了独立的证据 → independent
    → 赋 StrategyParamRecord
    → 展开时成为新 factor
```

### 6.4 作者声明的角色

作者在 `gaia-deps.yml` 中的 `role` 声明是帮助 reviewer 的线索：

- 有声明 → reviewer 验证声明是否准确
- 无声明（作者不知道已有工作）→ canonicalization 仍能匹配 Knowledge，Strategy 仍进 review queue
- 虚假声明 → 无害，reviewer 会纠正

## 7. 迟发现合并

措辞不同但语义相同的 Knowledge 可能漏过匹配。这是正常的，不是异常。

### 7.1 合并流程

```
1. 发现 gcn_A ≈ gcn_B（reviewer / agent / 社区成员）
2. 提交 merge PR 到 registry
3. Reviewer 确认
4. 执行：
   a. gcn_B → gcn_A，所有引用重定向
   b. gcn_B 标记为 merged（保留审计记录）
   c. 受影响 Strategy 暂停参数（BP 回退到安全状态）
5. 级联 re-review：重新评估受影响 Strategy 的独立性
6. 增量 BP
```

### 7.2 记录格式

```jsonl
// merges/merges.jsonl
{
  "merged_from": "sha256:gcn_B_hash",
  "merged_into": "sha256:gcn_A_hash",
  "reason": "semantic duplicate discovered by reviewer_alice",
  "confirmed_by": "reviewer_bob",
  "merged_at": "2026-04-15T10:00:00Z",
  "affected_strategies": ["gcs_2", "gcs_4"],
  "re_review_status": "pending"
}
```

暂停参数这一步确保系统在 re-review 完成前回退到保守状态——可能少算证据，但不会 double counting。

## 8. 多分辨率与 CompositeStrategy

CompositeStrategy 折叠/展开支持多分辨率 BP：

```
折叠（粗图）：
  gcs_comp 是一个 factor，一组 conditional_probabilities
  → reviewer 综合内部结构设定折叠参数

展开（细图）：
  sub_strategies 按各自 premises 连接
  → independent 的成为独立 factor
  → duplicate 的不贡献
  → refinement 的替代被细化者
```

新包的细化工作（为已有粗 Strategy 提供内部结构）也通过 CompositeStrategy 处理——升级已有 Strategy 的内部结构，折叠视图不变，展开视图更精细。
