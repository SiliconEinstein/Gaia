# Canonicalization — 规范化

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Canonicalization 定义如何将 local canonical 实体映射到 global canonical 实体，即从包内身份提升到跨包身份。

Gaia IR 的核心结构定义见 [02-gaia-ir.md](02-gaia-ir.md)。全局规范化服务端流程见 [dp-gaia](https://github.com/SiliconEinstein/dp-gaia) 仓库。

## 1. 作用

Canonicalization 负责：

- 将 `lcn_` / `lcs_` / `lco_` 映射到 `gcn_` / `gcs_` / `gco_`
- 统一跨包语义等价的 Knowledge 身份
- 利用 `content_hash` 提供同内容节点的精确匹配快速路径
- 将 local Strategy 提升到 global graph
- 决定何时做 binding，何时创建 equivalence 候选

## 2. Binding 与 Equivalence

Canonicalization 中存在两种本质不同的关系：

- **CanonicalBinding（身份映射）**：local Knowledge 和 global Knowledge 是**同一个命题**的不同表示。纯引用关系，不提供新证据，不创建图结构。多条从相同前提出发的推理路径收敛到同一个 Knowledge，以不同的 Strategy 表达。
- **Equivalence Operator（等价声明）**：两个独立的 global Knowledge 被声明为**等价**。从不同前提独立推出相同结论，这本身是新证据（独立验证），概率推理会在两者之间传播 belief。

**Binding 与 Equivalence 的判断发生在 Strategy（推理链）层面，而非 Knowledge（结论）层面。** 核心问题不是“这个结论和已有结论是不是一样”，而是“这条新的推理链是否为该结论提供了独立证据”。

### 2.1 未增加独立证据 → Binding

结论 Knowledge 绑定到已有 global Knowledge（`CanonicalBinding.decision = "match_existing"`）。

当新包的 Strategy（提升到全局后）与已有 Strategy 共享相同前提和结论，**必须合并为 CompositeStrategy**，不能让多条独立 Strategy 并列指向同一 Knowledge，否则概率推理会对同一组证据 double count。

```text
合并前（double counting，错误）：
  Strategy_A: [P1, P2] -> C
  Strategy_B: [P1, P2] -> C

合并后（正确）：
  CompositeStrategy: [P1, P2] -> C
    sub_strategies:
      - Strategy_A
      - Strategy_B
```

如果已有 Strategy 尚未被包装为 CompositeStrategy，canonicalization 在发现第二条 Strategy 时创建 CompositeStrategy 并将两者放入 `sub_strategies`。后续新包的 Strategy 追加到同一 CompositeStrategy。

典型场景：

- 相同前提，不同推理方法
- 仅引用（local Knowledge 只作为 premise 或 background，不是任何 Strategy 的 conclusion）

### 2.2 增加独立证据 → Equivalence

为新结论创建新的 global Knowledge（`CanonicalBinding.decision = "equivalent_candidate"`），在新旧两个 global Knowledge 之间提议一个 equivalence Operator（候选项由 review 层管理，确认后写入 IR）。

```text
全局图：
  Strategy_A (包 A): [...] -> C1
  Strategy_B (包 B): [...] -> C2
  Operator: equivalence(C1, C2)
```

两个 Knowledge 节点各自通过自己的 Strategy chain 获得 belief，equivalence Operator 让 belief 互相传导，正确建模“独立验证增强可信度”。

### 2.3 无匹配 → create_new

为前所未见的命题创建新的 global Knowledge（`CanonicalBinding.decision = "create_new"`）。

### 2.4 判断方式

“是否增加独立证据”是语义判断，IR 层不规定具体判定策略。前提集合的重叠度是最重要的结构信号，但不是唯一判据；推理方法差异、证据来源独立性等也可能构成独立证据。Canonicalization 可以基于前提重叠度做默认判断，review 层可以 override。

## 3. 参与规范化的 Knowledge 类型

**所有知识类型都参与全局规范化：** `claim`（含全称 claim）、`setting`、`question`。

- **claim**：跨包身份统一是概率推理的基础。全称 claim（`parameters` 非空）跨包共享同一通用定律
- **setting**：不同包可能描述相同背景，统一后可被多个推理引用
- **question**：同一科学问题可被多个包提出

## 4. 匹配策略

匹配按优先级依次尝试：

1. **Content hash 精确匹配（快速路径）**：`content_hash` 相同 → 直接 `match_existing`，跳过 embedding。
2. **Embedding 相似度（主要）**：余弦相似度，阈值 0.90。
3. **TF-IDF 回退**：无 embedding 模型时使用。

`content_hash` 使用 `SHA-256(type + content + sorted(parameters))`，不含 `package_id`；因此它适合做跨包同内容的精确命中，但不替代最终的 global `id`。

**过滤规则：**

- 仅相同 `type` 的候选者才有资格
- 含 `parameters` 的 claim 额外比较参数结构：count + types 按序匹配，忽略 name（α-equivalence，见 Issue #234）

## 5. CanonicalBinding

```text
CanonicalBinding:
    local_canonical_id:     str
    global_canonical_id:    str
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new" | "equivalent_candidate"
    reason:                 str    # 匹配原因（如 "cosine similarity 0.95"）
```

## 6. Strategy 提升

Knowledge 规范化完成后，local Strategy 提升到全局图：

1. 从 CanonicalBinding 构建 `lcn_ -> gcn_` 映射
2. 从全局 Knowledge 元数据构建 `ext: -> gcn_` 映射（跨包引用解析）
3. 对每个 local Strategy，解析所有 premise、conclusion 和 background ID
4. 含未解析引用的 Strategy 被丢弃（记录在 `unresolved_cross_refs` 中）

**Global Strategy 不携带 steps。** Local Strategy 的 `steps` 保留在 local canonical 层。Global Strategy 只保留结构信息（`type`、`premises`、`conclusion`、形态及其字段），不复制推理内容。需要查看推理细节时，通过 CanonicalBinding 回溯到 local 层。

## 7. Global 层的内容引用

Global 层**通常不存储内容**：

- **Global Knowledge** 通过 `representative_lcn` 引用 local canonical Knowledge 获取 content。当多个 local Knowledge 映射到同一 global Knowledge 时，选择一个作为代表，所有映射记录在 `local_members` 中。
- **Global Knowledge** 可额外保存一份从 `representative_lcn` 同步来的 `content_hash`，作为 denormalized 查询索引；representative 变更时更新该字段，但 `gcn_id` 不变。
- **Global Strategy** 不携带 `steps`。推理过程文本保留在 local 层。

**例外：** LKM 服务器直接创建的 Knowledge（包括 FormalExpr 展开的中间 Knowledge）没有 local 来源，其 content 直接存储在 global Knowledge 上。

Global 层是**结构索引**，local 层是**内容仓库**。

## 8. Strategy 形态与层级规则

**三种形态均可出现在 local 和 global 层：**

- **基本 Strategy**：local 层（compiler 产出）和 global 层（提升后）均可。
- **CompositeStrategy**：local 层（作者在包内构造层次化论证）和 global 层（reviewer/agent 分解）均可。
- **FormalStrategy**：local 层和 global 层均可；当某个原子子结构被 fully expand 为确定性 skeleton 时使用。

### 8.1 中间 Knowledge 的创建

展开操作可能需要创建中间 Knowledge（如 deduction 的 conjunction 结果 `M`、abduction 的 prediction `O`）。这些 Knowledge 由执行展开的 compiler/reviewer/agent **显式创建**，不由 FormalExpr 自动产生。

- Local 层：中间 Knowledge 获得 `lcn_` ID，归属于当前包
- Global 层：中间 Knowledge 获得 `gcn_` ID，content 直接存在 global Knowledge 上

### 8.2 FormalExpr 的生成方式

- **确定性命名策略**（`deduction`、`reductio`、`elimination`、`mathematical_induction`、`case_analysis`）：FormalExpr 骨架通常由 type 唯一确定，可在分类确认时自动生成
- **带隐式桥接/预测/实例的命名策略**（`abduction`、`induction`、`analogy`、`extrapolation`）：当 prediction、instance、bridge/continuity claim 等中间 Knowledge 已显式存在时，可直接生成对应的 FormalExpr。若更大的论证需要保留 hierarchy，则再由外层 CompositeStrategy 组合这些 leaf FormalStrategy
- **`toolcall` / `proof`**：deferred，未引入
