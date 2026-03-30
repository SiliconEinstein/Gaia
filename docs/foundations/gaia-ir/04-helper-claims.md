# Helper Claims

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 中结构型 helper claim 的建模纪律与 public/private 边界。

## 目的

当前文档里的 `helper claim` 专指**结构型 result claim**：

- 它是 `claim`
- 它由结构关系或 formal skeleton 确定性地产生
- 它的作用是让这些结构结果也能被图中的其他部分直接引用

本文件不再把 `prediction`、`instance`、`bridge`、`continuity` 这类语义中间命题统称为 helper claim。它们在当前 contract 下仍然只是普通 `claim`，必要时作为中间 claim 显式出现。

如果未来确实有必要，再单独引入“semantic helper claim”这一更宽的分类。

## 1. 定位

Helper claim **不是新的 Knowledge 类型**。它始终编码为：

```text
Knowledge(type=claim)
```

它和普通 claim 的差别不在 schema primitive，而在来源：

- 普通 claim 主要表达科学命题本身
- helper claim 主要表达结构关系的标准结果

一旦进入 Gaia IR，helper claim 仍然遵循普通 `claim` 的规则：

- 可以被引用
- 可以被 canonicalize
- 在图中拥有自己的节点身份

## 2. 当前范围

当前 contract 下，helper claim 主要包括以下结构型结果：

| helper_kind | 来源 | 例子 |
|-------------|------|------|
| `conjunction_result` | conjunction | `M = A ∧ B` |
| `disjunction_result` | disjunction | `D = A ∨ B ∨ C` |
| `equivalence_result` | equivalence | `Eq = same_truth(A,B)` |
| `contradiction_result` | contradiction | `Contra = not_both_true(A,B)` |
| `complement_result` | complement | `Comp = opposite_truth(A,B)` |
| `formal_intermediate` | 其他 FormalExpr 局部步骤 | 某个仅为继续布线而显式存在的中间项 |

这些 helper claim 的共同点是：

- 它们通常由 compiler / reviewer 按 operator 结构确定性生成
- 它们本身仍是 `claim`
- 它们默认不是新的自由参数入口

当前 contract 下，**每个 Operator 都有 `conclusion`**。  
对 `equivalence` / `contradiction` / `complement` / `disjunction`，这个 `conclusion` 就是结构型 helper claim。

## 3. Public / Private 边界

Helper claim 的核心不是“有没有科学语义”，而是它是否越过了 strategy 的外部接口。

### 3.1 私有 Helper Claim

私有 helper claim 满足：

- 它是某个 `FormalStrategy` 内部 skeleton 的一部分
- 它不出现在该 Strategy 的 `premises` / `conclusion` 中
- 其他外部 Strategy 默认**不能**直接把它当作 `premises` 使用

例如 `conjunction([A, B, M], conclusion=M)` 里的 `M`，如果只服务于单个 `FormalStrategy`，就属于私有 helper claim。

### 3.2 公共 Helper Claim

公共 helper claim 满足以下任一条件：

- 它本来就是某个 Strategy 的外部 `premise` 或 `conclusion`
- 它需要被多个 Strategy 共享
- 它需要被单独审查、引用、canonicalize 或比较

一旦满足这些条件，它就不再只是“内部中间节点”，而应被视为显式公共 `claim`。

### 3.3 提升规则

默认规则是：

- helper claim 可以先作为私有内部节点存在
- 一旦需要跨 Strategy 复用，就必须提升为公共 claim

提升后：

- 它仍然是 `Knowledge(type=claim)`
- 但不再享有“只能在单个 FormalStrategy 内部使用”的封装边界

## 4. 推荐元数据

Helper claim 不需要新增 schema 字段，但推荐在 `metadata` 中记录其角色：

| 字段 | 说明 |
|------|------|
| `helper_kind` | `conjunction_result` / `equivalence_result` / `contradiction_result` 等 |
| `helper_visibility` | `private` 或 `public` |
| `canonical_name` | 稳定、可复现的规范命名 |

这些字段是推荐约定，不是新的 core primitive。

## 5. Canonical Naming

`content` 负责给人看，`canonical_name` 负责稳定标识 helper claim 的规范身份。

推荐规则：

- 结构型 helper claim 优先使用稳定 functor 形式
- `canonical_name` 放在 `metadata` 中，而不是升级成新的顶层 schema 字段

推荐例子：

```text
all_true(A,B)
same_truth(A,B)
not_both_true(A,B)
opposite_truth(A,B)
any_true(A,B,...)
```

## 6. 与 Parameterization 的关系

Helper claim 不引入新的 `StrategyParamRecord` 规则。

当前默认是：

- helper claim 仍然是 `claim`
- 但结构型 helper claim 默认**不**成为新的独立 prior 输入口
- 它们的值默认由对应的 Operator 或 formal skeleton 决定

因此，对直接 `FormalStrategy` 来说：

- public helper claim 和 private helper claim 都可能参与其导出的等效 conditional behavior
- 但只有 private helper claim 才允许在运行时被该 `FormalStrategy` 安全地 marginalize 掉
- 一旦某个 helper claim 被提升成公共 claim 并被外部复用，就不应再把包含它的 `FormalStrategy` 压成单个黑盒条件概率视图

## 7. 例子

### 7.1 Relation Operator

```text
Operator(operator=contradiction, variables=[A, B], conclusion=Contra_AB)
```

这里：

- `Contra_AB` 是结构型 helper claim
- 它推荐有稳定的 `canonical_name`，例如 `not_both_true(A,B)`
- 它不应默认再引入独立 prior
- 若未来有别的 Strategy 需要显式引用“`A` 与 `B` 不可同真”这一事实，它可以直接引用这个 helper claim

### 7.2 FormalStrategy 内部合取结果

```text
FormalStrategy(type=analogy, premises=[SourceLaw, BridgeClaim], conclusion=Target):
  formal_expr:
    - conjunction([SourceLaw, BridgeClaim, M], conclusion=M)
    - implication([M, Target], conclusion=Target)
```

这里：

- `BridgeClaim` 是普通 `premise claim`，不是 helper claim
- `M` 是结构型 helper claim
- 若 `M` 只服务于这条 FormalStrategy，则它默认是私有 helper claim

## 8. 当前边界

本文件当前**不**把以下内容写成 Gaia IR core contract：

- helper claim 的唯一 hash / ID 生成算法
- 结构型 helper claim 的统一 prior policy
- semantic helper claim 分类

这些都可以以后继续推进，但不影响当前 helper claim 作为结构型 result claim 重新进入主文档体系。
