# Canonicalization — 规范化

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本目录定义 CLI↔LKM 结构契约。变更需要独立 PR 并经负责人审查批准。

Canonicalization 定义如何将 local canonical 实体映射到 global canonical 实体，即从包内身份提升到跨包身份。

Gaia IR 的核心结构定义见 [02-gaia-ir.md](02-gaia-ir.md)。全局规范化服务端流程见 [../lkm/global-canonicalization.md](../lkm/global-canonicalization.md)。

## 1. 作用

Canonicalization 负责：

- 将 `lcn_` / `lcs_` / `lco_` 映射到 `gcn_` / `gcs_` / `gco_`
- 统一跨包语义等价的 Knowledge 身份
- 利用 `content_hash` 提供同内容节点的精确匹配快速路径
- 将 local Strategy 提升到 global graph
- 决定何时做 binding，何时创建 equivalence 候选

## 2. Knowledge 身份映射与 Strategy 集成

Canonicalization 里有两个不同问题，不能混在一起：

- **Knowledge 身份映射**：这个 local Knowledge 是否与某个 existing global Knowledge 表达的是**同一个 proposition**
- **Strategy 集成**：在结论已经绑定到某个 global Knowledge 之后，这条新的推理链应如何接到全局图里

这两层分离后，`content_hash` 快速路径、binding、equivalence 和证据独立性就不会互相打架。

### 2.1 同一个 proposition → Binding

若 local Knowledge 与某个 global Knowledge 表达的是**同一个 proposition**，则做 CanonicalBinding（`decision = "match_existing"`）。

- 这是**节点身份**问题
- 它回答的是“这是不是同一个命题节点”
- 它不直接回答“这条新推理链是否提供了独立证据”

exact content match（如 `content_hash` 相同）是最强的同一 proposition 信号；无 exact match 时，再由 embedding / review 判断是否仍应 bind 到现有 global Knowledge。

### 2.2 不同 proposition 但 truth-coupled → Equivalence

Equivalence Operator 只用于**不同 proposition** 之间的 truth-coupling：

- 它们不是同一个 canonical Knowledge
- 但 review 认为它们在 truth 上应联动
- 这时保留两个 global Knowledge，并在它们之间建立 equivalence

换句话说，equivalence 不是“同一 proposition 的第二条证据链”的表达方式；同一 proposition 的额外支持路径仍然应该汇聚到同一个 global Knowledge。

### 2.3 Binding 后的 Strategy 集成

当 local conclusion 已绑定到某个 global Knowledge 后，再处理这条 local Strategy 如何进入全局图。

如果新包的 Strategy（提升到全局后）与已有 Strategy 共享相同前提和结论，**必须合并为 CompositeStrategy**，不能让多条独立 Strategy 并列指向同一 Knowledge，否则概率推理会对同一组证据 double count。

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

如果已有 Strategy 尚未被包装为 CompositeStrategy，canonicalization 在发现第二条 Strategy 时创建 CompositeStrategy 并将两者放入 `sub_strategies`。后续同 premise-set / conclusion 的 Strategy 追加到同一 CompositeStrategy。

典型场景：

- 相同前提，不同推理方法
- 仅引用（local Knowledge 只作为 premise 或 background，不是任何 Strategy 的 conclusion）

如果新的 Strategy 指向**同一个 bound global Knowledge**，但 premise-set 不同、证据来源独立，则它应作为**另一条支持路径**接入同一个结论节点，而不是创建新的 global Knowledge。

### 2.4 无匹配 → create_new

若没有合适的 existing global Knowledge，则为前所未见的 proposition 创建新的 global Knowledge（`decision = "create_new"`）。

### 2.5 review 候选：equivalent_candidate

若 canonicalization 认为“它不是同一个 proposition，但可能与现有某个 proposition truth-coupled”，则可记为 `equivalent_candidate`，留给 review 决定是否创建 equivalence Operator。

```text
全局图：
  Strategy_A (包 A): [...] -> C1
  Strategy_B (包 B): [...] -> C2
  Operator: equivalence(C1, C2)
```

两个 Knowledge 节点各自通过自己的 Strategy chain 获得 belief，equivalence Operator 让 belief 互相传导。

### 2.6 判断方式

“是否为同一个 proposition”与“是否为独立证据”是两个不同判断：

- proposition identity 主要用于决定 `match_existing` 还是 `create_new`
- evidence independence 主要用于决定 binding 后如何集成新的 Strategy

前提集合的重叠度、推理方法差异、证据来源独立性等，主要影响的是后者；review 层可以 override 默认策略。

## 3. 参与规范化的 Knowledge 类型

**所有知识类型都参与全局规范化：** `claim`（含全称 claim）、`setting`、`question`。

- **claim**：跨包身份统一是概率推理的基础。全称 claim（`parameters` 非空）跨包共享同一通用定律
- **setting**：不同包可能描述相同背景，统一后可被多个推理引用
- **question**：同一科学问题可被多个包提出

## 4. 匹配策略

匹配按优先级依次尝试：

1. **Content hash 精确匹配（快速路径）**：`content_hash` 相同 → 直接命中“exact same proposition”候选，跳过 embedding 检索。
2. **Embedding 相似度（主要）**：余弦相似度，阈值 0.90。
3. **TF-IDF 回退**：无 embedding 模型时使用。

`content_hash` 使用 `SHA-256(type + content + sorted(parameters))`，不含 `package_id`；因此它适合做跨包同内容的精确命中，但不替代最终的 global `id`，也不替代 binding 后的 Strategy 集成判断。

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
- **`toolcall` / `proof`**：当前没有稳定 canonical FormalExpr，默认保留为 CompositeStrategy
