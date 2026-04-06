# Operator & Strategy Redesign — Warrant-Based Audit

> **Status:** Proposal
>
> **Context:** 源于 2026-04-06 对 BP lowering / dead-end / factor graph 语义的深入讨论。
> 核心发现：因子图与 Jaynes MaxEnt 严格等价；operator 是命题逻辑连接词；
> 推理可靠性的唯一审计点是 IMPLIES 的 warrant。

## 1. 动机

### 1.1 当前问题

1. **implication 编码错误**：当前 `implication(variables=[A], conclusion=B)` 是一元算子，B 既是蕴含的后件又是输出变量，无法表达 "蕴含是否成立" 这一独立命题。
2. **directed/relation 分类缺乏原理**：当前 IR 将 operator 分为 Directed 和 Relation 两类，但区分理由不清晰。真正的区别在于 conclusion 的先验语义（断言 vs 计算），而非结构差异。
3. **FormalExpr 先验 bug**：FormalExpr 内部 relation operator 的 conclusion 被错误赋予 π=0.5（已在 PR #344 修复），根因是 lowering 按 operator type 猜 prior，而非由 strategy 语义决定。
4. **审计缺乏焦点**：reviewer 面对一整张因子图，不知道哪些点需要重点审查。
5. **noisy_and 与 deduction 冗余**：两者结构相同（AND + IMPLIES），仅推理强度不同。

### 1.2 核心 Insight

**因子图 = MaxEnt 联合分布**：

$$P(x_1, \ldots, x_n) \propto \prod_i \pi_i(x_i) \cdot \prod_a f_a(\mathbf{x}_a)$$

- Operator = 因子 $f_a$（确定性真值表，Cromwell 软化）
- Prior $\pi_i$ = unary factor（注入信息 or 不注入）
- 因子图中无 premise/conclusion 之分，所有变量对称
- 推理方向由 prior 决定，不由 operator 结构决定

**所有 operator 都是命题逻辑连接词**，结构上相同（三元 CONDITIONAL 因子），不同的只是真值表。

**IMPLIES 是唯一的推理审计点**：computation operator（AND, OR, NOT）的输出是确定性布尔函数，不可能 "不成立"；relation operator（IMPLIES, equivalence, contradiction, complement）的输出是一个断言，需要审计。而 equivalence / contradiction / complement 在 FormalExpr 中应尽量避免使用（增加 review 负担），大多数场景可通过直接连接真实 claim 来消除。

## 2. Operator 层改动

### 2.1 保留现有 operator，最小改动

| Operator | 当前 | 改动 |
|----------|------|------|
| conjunction | `variables=[A₁,...,Aₖ], conclusion=M` | 不动 |
| disjunction | `variables=[A₁,...,Aₖ], conclusion=D` | 不动 |
| equivalence | `variables=[A, B], conclusion=H` | 加 `warrant` 字段 |
| contradiction | `variables=[A, B], conclusion=H` | 加 `warrant` 字段 |
| complement | `variables=[A, B], conclusion=H` | 加 `warrant` 字段 |
| **implication** | `variables=[A], conclusion=B` | **改为二元**：`variables=[A, B], conclusion=H` |
| **not** | 不存在 | **新增**：`variables=[A], conclusion=H` |

### 2.2 Operator Schema

```
Operator:
    operator_id:    str | None
    scope:          str | None
    operator:       str              # not | conjunction | disjunction | equivalence
                                     # | contradiction | complement | implication
    variables:      list[str]        # 连接的 Knowledge IDs（有序）
    conclusion:     str              # 该 Operator 的输出 claim
    warrant:        str | None       # 逻辑依据（relation operator 专用）
    metadata:       dict | None
```

新增字段 `warrant: str | None`：
- Computation operator（conjunction, disjunction, not）：`warrant = None`
- Relation operator（implication, equivalence, contradiction, complement）：`warrant = "..."` 说明为什么这个关系成立

### 2.3 Implication 二元化

**旧**：`implication(variables=[A], conclusion=B)` — A 是前件，B 是后件兼输出。

**新**：`implication(variables=[A, B], conclusion=H)` — A 是前件，B 是后件，H = "A→B 成立" 是 helper claim。

H 是一个 `Knowledge(type=claim)`，走 helper claim 机制：
```
Knowledge(id=H, type="claim",
    content="implies(A, B)",
    metadata={
        "helper_kind": "implication_result",
        "warrant": "精确数学推导，无近似"
    })
```

H 的 prior 由 parameterization 层管理：
- FormalStrategy 默认：π(H) = 1-ε（确定性推导）
- Leaf Strategy：π(H) 由 reviewer 设定

### 2.4 NOT 算子

```
Operator(operator="not", variables=[A], conclusion=H)
```

H = ¬A。Computation operator，`warrant = None`。

### 2.5 Operator 分类

| 类别 | Operator | conclusion 含义 | warrant | π(conclusion) |
|------|----------|----------------|---------|---------------|
| **Computation** | conjunction, disjunction, not | 布尔函数值 | None | 0.5（计算） |
| **Relation** | implication, equivalence, contradiction, complement | 关系是否成立 | str | 由 parameterization 层决定 |

分类的本质：**conclusion 是否携带独立于 variables 先验的新信息**。computation 不携带（值由输入决定），relation 携带（关系是否成立是独立断言）。

## 3. Strategy 层改动

### 3.1 FormalStrategy 加 warrants

```
FormalStrategy(Strategy):
    formal_expr:     FormalExpr
    warrants:        list[str]       # 需要审计的 helper claim ID 列表
```

`warrants` 列出 FormalExpr 中所有 relation operator 的 conclusion claim ID。Reviewer 按此列表逐一审计。

### 3.2 Deduction 统一 noisy_and

**Deduction** 是原子推理单元：premise → conclusion via IMPLIES。

```
# 单前提
implication([A, C], conclusion=H, warrant="...")

# 多前提
conjunction([A, B], conclusion=M)
implication([M, C], conclusion=H, warrant="...")
```

区别 deduction 和 noisy_and 的唯一参数是 π(H)：
- π(H) = 1-ε → 确定性推导（FormalStrategy，无 reviewer 参数）
- π(H) < 1 → 弱推理（Leaf Strategy，reviewer 设定 π(H)）

**noisy_and 类型移除**，被 deduction + π(H) 参数覆盖。

反向推理（"结论成立时前提更可信"）通过第二个 IMPLIES 表达：
```
implication([C, M], conclusion=H₂, warrant="实验确认提升理论可信度")
```

等价于原 SOFT_ENTAILMENT(p1, p2)（见附录 A）。

### 3.3 各 FormalStrategy 的新编译方案

#### 3.3.1 Deduction

```
premises=[A, B], conclusion=C

conjunction([A, B], conclusion=M)                    # computation
implication([M, C], conclusion=H,                    # relation
    warrant="推导过程...")

warrants=[H]
```

单前提时省略 conjunction。

#### 3.3.2 Abduction

```
premises=[Obs], conclusion=Hyp
# 编译器自动生成 Alt (AlternativeExplanationForObs)

disjunction([Hyp, Alt], conclusion=Obs)              # Obs 直接做 conclusion，无中间变量

warrants=[]                                          # 无 relation operator！
```

关键简化：Obs 是真实 claim，直接做 disjunction 的 conclusion。**不需要 equivalence**，零 warrant。

#### 3.3.3 Elimination

```
premises=[Exh, C₁, E₁], conclusion=S
# Exh 是用户写的穷尽性 claim

disjunction([C₁, S], conclusion=Exh)                 # Exh 直接做 conclusion
contradiction([C₁, E₁], conclusion=Contra,            # relation
    warrant="E₁ 直接反驳 C₁")
implication([Exh, S], conclusion=H,                   # relation
    warrant="穷尽性下排除 C₁ 后 S 幸存")

warrants=[Contra, H]
```

关键简化：Exh 是用户写的真实 claim（穷尽性断言），直接做 disjunction conclusion。**不需要 equivalence**。

#### 3.3.4 Case Analysis

```
premises=[Exh, Case₁, Case₂, Case₃], conclusion=Concl
# Exh 是用户写的穷尽性 claim

disjunction([Case₁, Case₂], conclusion=D₁₂)          # binary chain
disjunction([D₁₂, Case₃], conclusion=Exh)             # Exh 直接做 conclusion

implication([Case₁, Concl], conclusion=H₁,            # relation
    warrant="Case₁ 条件下 Concl 成立因为...")
implication([Case₂, Concl], conclusion=H₂,            # relation
    warrant="Case₂ 条件下 Concl 成立因为...")
implication([Case₃, Concl], conclusion=H₃,            # relation
    warrant="Case₃ 条件下 Concl 成立因为...")

warrants=[H₁, H₂, H₃]
```

关键简化：**不需要 conjunction(Case, Sup)**。每个 case 的支持理由在 warrant 文本中说明，不引入 helper claim。IMPLIES 直接连真实 claim（Case → Concl），reviewer 一眼看懂。

### 3.4 Strategy 类型精简

| 新 | 旧 | 变化 |
|----|-----|------|
| deduction | deduction + noisy_and + analogy + extrapolation + mathematical_induction | π(H) 控制强度，语义标签保留在 type |
| abduction | abduction | 简化：去掉 equivalence |
| elimination | elimination | 简化：去掉 equivalence |
| case_analysis | case_analysis | 简化：去掉 conjunction+Sup |
| infer(cpt) | infer(cpt) | 保留，完全自定义 |
| induction | induction | 保留 CompositeStrategy |
| — | noisy_and | 删除 |

### 3.5 穷尽性 Claim 的处理

Elimination 和 case_analysis 的穷尽性 claim（Exh）：

- **由用户显式写出**：`Knowledge(type="claim", content="C₁ 和 S 穷尽所有可能")`
- **作为 strategy 的 premise**，不是 auto-generated helper
- **prior 由知识图管理**（作者对穷尽性的信心）
- **正常 claim review**，不走 warrant 机制

## 4. Warrant 审计

### 4.1 审计对象

每个 FormalStrategy 的 `warrants` 列表中的 helper claim。这些 claim 由 relation operator（implication, equivalence, contradiction, complement）生成。

### 4.2 IMPLIES 审计 Checklist

对于 `implication([A, B], conclusion=H)` 中的 H = "A→B"：

1. **充分性**：A 单独是否足以推出 B？有无隐含依赖不在 A 中？
2. **推导完整性**：从 A 到 B 的每一步是否有据可循？有无跳步？
3. **作用域匹配**：A 的适用范围是否覆盖 B 所在的情境？
4. **方向正确性**：确实是 A→B？不是 B→A 或 A↔B？
5. **逻辑有效性**：有无循环论证、肯定后件等谬误？

### 4.3 其他 Relation Operator 审计

| Operator | 审计问题 |
|----------|---------|
| equivalence | "A 和 B 真的等价吗？在所有情况下真值一致？" |
| contradiction | "A 和 B 真的矛盾吗？确实不能同时为真？" |
| complement | "A 和 B 真的互补吗？恰好一真一假？" |

### 4.4 审计结果

审计结果映射到 conclusion claim 的 prior（通过 parameterization 层）：

| 审计结论 | π(H) |
|---------|------|
| 逻辑上严格成立 | 1-ε |
| 基本成立，微小近似 | ~0.95 |
| 有明确逻辑缺口 | ~0.5-0.8 |
| 推导不成立 | ε |

## 5. Lowering 层影响

### 5.1 Prior 赋值

Lowering 不再按 operator type 猜 prior（删除 `_RELATION_OPS` blanket rule）。Prior 来源：

1. 知识图中 claim 的 PriorRecord（最高优先级）
2. FormalStrategy 语义默认值：relation operator conclusion → 1-ε，computation → 0.5
3. 全局默认 0.5

### 5.2 统一因子

所有 operator 在因子图中都是 CONDITIONAL 三元因子，CPT 由 operator type 查表得到。Lowering 路径统一，不区分 relation / computation。

### 5.3 多元 AND/OR

多元 conjunction / disjunction 在 lowering 时自动拆为二元链：
```
conjunction([A, B, C], conclusion=M)
  → conjunction([A, B], conclusion=__m1)
  → conjunction([__m1, C], conclusion=M)
```

## 6. 迁移

### 6.1 向后兼容

- 旧的 `implication(variables=[A], conclusion=B)` 需要迁移为 `implication(variables=[A, B], conclusion=H)`
- 旧的 `noisy_and` Strategy 迁移为 `deduction` + reviewer 设定 π(H)
- 现有 FormalExpr 中的 equivalence 大部分可消除（直接用真实 claim 做 conclusion）

### 6.2 实施顺序

1. 写 design spec（本文档）
2. 更新 IR 文档（02-gaia-ir.md §2, §3 — protected layer，需审批）
3. 更新 helper-claims 文档（04-helper-claims.md）
4. 实现代码改动（operator schema, formalize, lowering, tests）
5. 更新 BP 文档（potentials.md, inference.md, formal-strategy-lowering.md）

## 附录 A：SOFT_ENTAILMENT 分解为两个 IMPLIES

SOFT_ENTAILMENT(M, C, p1, p2) 等价于两个 IMPLIES：

```
IMPLIES([M, C, H₁])    π(H₁) = p1    # 正向
IMPLIES([C, M, H₂])    π(H₂) = p2    # 反向（逆否 ¬M→¬C）
```

验证：边缘化 H₁, H₂ 后有效势函数的比值与 SOFT_ENTAILMENT 完全一致：

$$\frac{\psi(M\!=\!1, C\!=\!1)}{\psi(M\!=\!1, C\!=\!0)} = \frac{p_1}{1-p_1} \qquad \frac{\psi(M\!=\!0, C\!=\!0)}{\psi(M\!=\!0, C\!=\!1)} = \frac{p_2}{1-p_2}$$

因此 SOFT_ENTAILMENT 不再需要作为独立的 FactorType。
