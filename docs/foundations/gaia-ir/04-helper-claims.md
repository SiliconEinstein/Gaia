# Helper Claims

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 中结构型 helper claim 的建模纪律与 public/private 边界。

## 目的

当前文档里的 `helper claim` 专指**结构型 result claim**：

- 它是 `claim`
- 它由结构关系或 formal skeleton 确定性地产生
- 它的作用是让这些结构结果也能被图中的其他部分直接引用

本文件不再把 `AlternativeExplanationForObs`、`BridgeClaim`、`ContinuityClaim` 这类语义接口命题统称为 helper claim。它们虽然也可能由 formalization 自动补齐，但因为可能承载独立 prior、也可能被其他 Strategy 支撑，所以必须保持为 **public interface claim**。

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

这些 helper claim 的共同点是：

- 它们通常由 compiler / reviewer 按 operator 结构确定性生成
- 它们本身仍是 `claim`
- 它们默认不是新的自由参数入口
- 它们若保持 private，就必须能被安全 marginalize，而不能偷偷引入新的 prior 自由度

当前 contract 下，**每个 Operator 都有 `conclusion`**。  
对 `equivalence` / `contradiction` / `complement` / `disjunction`，这个 `conclusion` 就是结构型 helper claim。

不是所有 formalization 自动生成的 claim 都属于本表。例如 abduction 自动补齐的 `AlternativeExplanationForObs` 是 public interface claim，因为它可能带 prior，也可能被别的 Strategy 支撑。

## 3. FormalExpr 内部 claim 的封装

Helper claim 出现在两个位置，规则不同：

- **顶层 Operator 的 conclusion**（如顶层 `equivalence([C1, C2], conclusion=Eq)`）：这些 helper claim 是图中的普通可见节点，可以被任何 Strategy 引用
- **FormalExpr 内部的中间 claim**（如 FormalStrategy 内部的 conjunction 结果 M）：这些是该 FormalStrategy 的**私有节点**

### 3.1 私有节点的硬约束

FormalExpr 内部产生但不出现在任何 Strategy 的 `premises` / `conclusion` 中的中间 claim，属于该 FormalStrategy 的私有节点。

**硬约束：私有节点禁止被外部 Strategy 引用。**

**硬约束：私有节点不得承载独立 PriorRecord。** 任何需要独立 prior 的 claim，必须提升为该 Strategy 的接口节点（`premises` 或 `conclusion`），而不能藏在 `formal_expr` 私有层。

**为什么？** FormalStrategy 的核心价值是封装——它可以被折叠（marginalization）为一个等效的 P(conclusion | premises)，对外只暴露接口。折叠要求对内部变量做变量消去（求和消掉），这只有在没有外部代码依赖这些内部变量的身份时才是安全的。如果允许外部引用内部变量，消去就会破坏外部引用，折叠就不可能了。

因此，私有节点的不可引用性保证了 FormalStrategy **总是可以被折叠的**。

### 3.2 示例

```text
FormalStrategy(type=analogy, premises=[SourceLaw, BridgeClaim], conclusion=Target):
  formal_expr:
    - conjunction([SourceLaw, BridgeClaim], conclusion=M)
    - implication([M], conclusion=Target)
```

这里 M 是私有节点——它只被 `formal_expr` 内部引用，不出现在任何 Strategy 的 premises/conclusion 中。外部 Strategy 不能直接引用 M。

推理引擎可以选择：
- **折叠**：对 M 做变量消去，整个 FormalStrategy 等效为 P(Target | SourceLaw, BridgeClaim)
- **展开**：保留 M 作为 runtime 节点，直接在展开后的图上推理

两种方式都合法，因为 M 是严格私有的。选择哪种由推理引擎的 `expand_set` 决定。

### 3.3 如果需要共享中间结果

如果某个中间结果确实需要被多个 Strategy 使用，不应直接引用 FormalExpr 内部的私有节点，而应**重构图结构**：

- 把共享的 claim 作为两个（或多个）Strategy 之间的显式接口节点
- 原来的 FormalStrategy 可能需要拆分为多个 Strategy，以便共享节点出现在 premises/conclusion 中

这是编译期 / review 期的图结构调整，不是运行时操作

## 4. 推荐元数据

Helper claim 不需要新增 schema 字段，但推荐在 `metadata` 中记录其角色：

| 字段 | 说明 |
|------|------|
| `helper_kind` | `conjunction_result` / `equivalence_result` / `contradiction_result` 等 |
| `helper_visibility` | `top_level` 或 `formal_internal` |
| `canonical_name` | 稳定、可复现的规范命名 |

这些字段是推荐约定，不是新的 core primitive。

## 5. Canonical Naming

`content` 负责给人看，`canonical_name` 负责稳定标识 helper claim 的规范身份。

推荐规则：

- 结构型 helper claim 优先使用稳定的函数式命名（如 `not_both_true(A,B)`）
- `canonical_name` 放在 `metadata` 中，而不是升级成新的顶层 schema 字段
- 当前这是不同实现之间建议统一的命名惯例，不作为 Gaia IR core validation 的硬性字段

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

**硬性规则：**

- 结构型 helper claim **禁止**携带独立的 `PriorRecord`
- helper claim 仍然是 `claim`，但在 parameterization 层不作为自由参数入口
- 需要独立 prior 的自动生成节点（如 abduction 的 `AlternativeExplanationForObs`）不属于 helper claim；它们必须保持为 public interface claim

**为什么禁止？** 因为 helper claim 的概率分布没有自由度——它完全被 Operator 的确定性约束（真值表）决定。

具体来说，Operator 不引入任何概率假设，它只在联合分布中加入一个硬约束。以 `conjunction([A, B], conclusion=M)` 为例：

- Operator 的约束是：`M=1 iff A=1 ∧ B=1`
- 给定 A 和 B 的值，M 的值就唯一确定了——M 没有独立的"先验"可言
- M 的边缘概率 P(M=1) 完全取决于 A 和 B 在完整图上的联合分布 P(A, B)
- 特别注意：P(M=1) **不等于** P(A=1) × P(B=1)，除非 A 和 B 恰好独立。如果 A 和 B 通过图中其他路径有依赖关系（例如共享前提），conjunction 不会抹掉这些依赖
- 如果给 M 再赋一个独立的 PriorRecord，就等于在已经确定性约束的变量上额外叠加一个自由参数，产生矛盾

同理，`equivalence([O, Obs], conclusion=Eq)` 中的 Eq 也完全由 O 和 Obs 的真值决定，没有自由度

因此，FormalStrategy 内部的私有 helper claim 可以被安全地 marginalize 掉——这正是 FormalStrategy 能够折叠为等效条件概率 P(conclusion | premises) 的数学基础

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
    - conjunction([SourceLaw, BridgeClaim], conclusion=M)
    - implication([M], conclusion=Target)
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
