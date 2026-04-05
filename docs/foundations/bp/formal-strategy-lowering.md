# FormalStrategy 因子图 Lowering：统一三元因子模型

> **Status:** Target design — 替代 #340 旧方案（二元因子 / dead-end 检测）
>
> 本文档论证 FormalStrategy 内部所有 Operator 的统一 lowering 方案。
> 依赖：[potentials.md](potentials.md)（factor potential 定义）、[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)（因子图理论）。

## 1. 统一因子模型

### 1.1 所有 Operator 都是 CONDITIONAL 三元因子

IR 中每个 Operator 有 `variables` 和 `conclusion`（[02-gaia-ir.md §2](../gaia-ir/02-gaia-ir.md)）。Lowering 时，**所有** Operator 统一映射为 CONDITIONAL 三元因子 $f(\text{variables}, \text{conclusion})$，CPT 编码真值表：

$$\psi = \text{cpt}[idx] \text{ 当 } H=1, \quad \psi = 1 - \text{cpt}[idx] \text{ 当 } H=0$$

各 Operator 对应的 CPT $P(H\!=\!1 \mid A, B)$：

| 算子 | (0,0) | (0,1) | (1,0) | (1,1) | 语义 |
|------|-------|-------|-------|-------|------|
| equivalence | 1 | 0 | 0 | 1 | $A = B$ |
| contradiction | 1 | 1 | 1 | 0 | $\neg(A \wedge B)$ |
| complement | 0 | 1 | 1 | 0 | $A \oplus B$ |
| conjunction | 0 | 0 | 0 | 1 | $A \wedge B$ |
| disjunction | 0 | 1 | 1 | 1 | $A \vee B$ |
| implication | 1 | 1 | 0 | 1 | $A \to B$（A 在 variables，B 是 conclusion） |

实际 lowering 使用 Cromwell 软化（$0 \to \varepsilon$，$1 \to 1-\varepsilon$）。

**不需要** EQUIVALENCE / CONTRADICTION / COMPLEMENT 等特化 FactorType。命名的算子类型只是 CPT 模板（syntactic sugar），在因子图层面全部归约为 CONDITIONAL。

### 1.2 因子图中无 premise / conclusion 之分

因子图只有两种实体：**变量**和**因子**。因子 $f(X_1, X_2, \ldots)$ 是对变量的联合约束，完全对称，没有方向。IR 的 "premise" 和 "conclusion" 是语义标签，到了因子图层全部变成变量。

联合分布：

$$P(x_1, \ldots, x_n) \propto \prod_i \pi_i(x_i) \cdot \prod_a f_a(\mathbf{x}_a)$$

每个变量的角色由其**先验** $\pi_i$ 决定：

- 有先验的变量 → 向图中**注入信息**（前提、观测、断言）
- 无先验的变量（$\pi = 0.5$，uniform）→ 从图中**接收信息**（推理输出）

## 2. Conclusion 先验的两种角色

所有 Operator 结构上相同（三元 CONDITIONAL），但 conclusion 的**先验**有本质区别。

### 2.1 断言型（Relation operator）

**equivalence / contradiction / complement**：conclusion $H$ 表达一个**关于 A、B 关系的独立断言**。

$H = (A \leftrightarrow B)$ 说的是 "A 和 B 真值一致"——这个信息**无法从** $\pi(A)$ 和 $\pi(B)$ 推导出来。它是关于 A、B 相关性的新信息。

因此 $\pi(H) = 1 - \varepsilon$：**算子的存在本身就是断言 "此关系成立"**。

效果：$H$ 向因子图注入信息，约束 A 和 B 的关系。

### 2.2 计算型（Directed operator）

**conjunction / disjunction / implication**：conclusion $M$ 是 variables 的**确定性函数值**。

$M = A \wedge B$ 可以从 $\pi(A)$ 和 $\pi(B)$ 直接算出（在独立假设下）。设 $\pi(M) = 1 - \varepsilon$ 会引入与 $\pi(A)$、$\pi(B)$ 重复的信息。

因此 $\pi(M) = 0.5$（uniform）：$M$ 是推理**输出**，其 belief 由 A、B 通过因子计算得出。

### 2.3 数学验证

设 $\pi(A\!=\!1) = a$，$\pi(B\!=\!1) = b$，考虑 conjunction $f(A, B, M)$。

**当 $\pi(M) = 0.5$ 时：**

$$\text{belief}(M\!=\!1) = \frac{ab(1-\varepsilon) + \varepsilon(1-ab)}{1} \xrightarrow{\varepsilon \to 0} ab$$

$M$ 的 belief 就是 $P(A) \cdot P(B)$——从 A、B 的先验**算出来**的联合概率。✓

**当 $\pi(M) = 1-\varepsilon$ 时：**

$$\text{belief}(M\!=\!1) \approx \frac{ab(1-\varepsilon)^2}{ab(1-\varepsilon)^2 + \varepsilon(1-\varepsilon)(1-ab)} \approx 1 - \frac{\varepsilon(1-ab)}{ab(1-\varepsilon)} \approx 1$$

$M$ 的 belief 恒定接近 1，不随 A、B 变化——退化为常数，不再是计算结果。✗

对比 equivalence $f(A, B, H)$，$\pi(H) = 1-\varepsilon$：

$$\text{belief}(H\!=\!1) \approx 1 \quad \text{（正确：断言"关系成立"，约束 A=B）}$$

| 先验 | conjunction belief(M) | equivalence belief(H) | 角色 |
|------|----------------------|----------------------|------|
| $0.5$ | $ab$（计算） | $ab + (1-a)(1-b)$（计算） | 推理输出 |
| $1-\varepsilon$ | $\approx 1$（常数） | $\approx 1$（常数） | 断言 |

Conjunction 需要 $\pi = 0.5$ 才能做有意义的计算；equivalence 需要 $\pi = 1-\varepsilon$ 才能激活约束。

## 3. Dead-end 行为分析

旧文档将 dead-end helper 变量视为 bug。实际上，两种先验下的 dead-end 行为**都是正确的**。

### 3.1 Dead-end 数学

设三元因子 $f(A, B, H)$，$H$ 只连接此因子（dead-end），边缘化 $H$：

$$\sum_H \pi(H) \cdot f(A, B, H) = \pi(H\!=\!1) \cdot \text{cpt}[idx] + \pi(H\!=\!0) \cdot (1 - \text{cpt}[idx])$$

**断言型 $\pi(H) = 1-\varepsilon$：**

- 当 $\text{cpt}[idx] = 1-\varepsilon$（关系成立）：$(1-\varepsilon)^2 + \varepsilon^2$
- 当 $\text{cpt}[idx] = \varepsilon$（关系不成立）：$2\varepsilon(1-\varepsilon)$
- 比值 $\approx (1-\varepsilon) / 2\varepsilon$，约束**保持激活** ✓

正确行为：断言 "A 和 B 等价" 应当约束 A、B，即使没有下游消费者。

**计算型 $\pi(M) = 0.5$：**

$$0.5 \cdot \text{cpt}[idx] + 0.5 \cdot (1 - \text{cpt}[idx]) = 0.5 \quad \forall (A, B)$$

常数，约束**完全消失** ✓

正确行为：纯计算结果（如 $M = A \wedge B$）在没有下游消费者时，不应反向约束 A、B。函数值没人用，就不该影响输入。

### 3.2 旧方案的问题

旧文档（#340）把 dead-end 约束消失视为 bug，提出了二元因子降级方案。但这基于两个错误前提：

1. **混淆了断言和计算**：relation operator 的 $H$ 是断言（需要 $\pi = 1-\varepsilon$），不是计算。正确的先验下 dead-end 约束不会消失。
2. **引入不必要的特殊路径**：二元因子、dead-end 检测、gate_var 都是为了修补一个不存在的 bug。

## 4. 各 FormalStrategy 的因子图

> 所有 Operator 统一为三元 CONDITIONAL 因子。Relation operator 的 conclusion 使用 $\pi = 1-\varepsilon$（断言），directed operator 的 conclusion 使用 $\pi = 0.5$（计算，中间变量）。

### 4.1 Abduction

**语义**：假说 $H$ 或替代解释 $\text{Alt}$ 解释观测 $\text{Obs}$。

**FormalStrategy 接口**：`premises=[Obs, Alt]`，`conclusion=H`。当只有一个前提（Obs）时，`formalize.py` 自动生成 Alt 作为 interface claim 并追加到 premises。

**当前**：
```
disjunction([H, Alt]) → D          # D: π=0.5，中间变量
equivalence([D, Obs]) → Eq         # Eq: π=1-ε，断言型
```

两个因子，Eq 是 dead-end 但 $\pi = 1-\varepsilon$ 保证约束不消失。D 连接 disjunction 和 equivalence 两个因子，信息正常流通。

**可选优化**：直接 `disjunction([H, Alt], conclusion=Obs)`，省去 D 和 Eq。这是一个 formalize.py 层面的简化（减少中间变量），不涉及因子类型的改变。

#### 4.1.1 完整 CPT：$P(H\!=\!1 \mid \text{Obs}, \text{Alt})$

单因子 $f(H, \text{Alt}, \text{Obs})$ 编码 $\text{Obs} = H \vee \text{Alt}$（Cromwell 软化）。

$$
P(H\!=\!1 \mid \text{Obs}, \text{Alt}) = \frac{\pi(H\!=\!1) \cdot f(1, \text{Alt}, \text{Obs})}{\sum_{h} \pi(H\!=\!h) \cdot f(h, \text{Alt}, \text{Obs})}
$$

逐行推导（$\varepsilon \to 0$）：

| Obs | Alt | $H\!=\!0$: $H \vee \text{Alt}$ vs Obs | $H\!=\!1$: $H \vee \text{Alt}$ vs Obs | $P(H\!=\!1)$ | 解释 |
|-----|-----|------|------|------|------|
| 0 | 0 | $0 = 0$ ✓ | $1 \neq 0$ ✗ | $\to 0$ | 无观测无替代 → H 必假 |
| 0 | 1 | $1 \neq 0$ ✗ | $1 \neq 0$ ✗ | $= h$ | 不一致（Cromwell），H 不更新 |
| 1 | 0 | $0 \neq 1$ ✗ | $1 = 1$ ✓ | $\to 1$ | 观测真但无替代 → H 必真 |
| 1 | 1 | $1 = 1$ ✓ | $1 = 1$ ✓ | $= h$ | 两者都能解释，H 不更新 |

关键行 (Obs=1, Alt=0) 详细推导：

$$
P(H\!=\!1 \mid 1, 0) = \frac{h(1-\varepsilon)}{(1-h)\varepsilon + h(1-\varepsilon)} \xrightarrow{\varepsilon \to 0} 1
$$

关键行 (Obs=0, Alt=0) 详细推导：

$$
P(H\!=\!1 \mid 0, 0) = \frac{h \cdot \varepsilon}{(1-h)(1-\varepsilon) + h \cdot \varepsilon} \xrightarrow{\varepsilon \to 0} 0
$$

#### 4.1.2 宏观统计量：$P(H\!=\!1 \mid \text{Obs}\!=\!1)$

在 BP expand 模式下，Alt 作为变量参与推理，其先验 $\pi(\text{Alt}) = a$ 被自动边缘化：

$$
P(H\!=\!1, \text{Obs}\!=\!1) \propto h \sum_{\text{Alt}} \pi(\text{Alt}) \cdot f(1, \text{Alt}, 1) = h(1-\varepsilon) \xrightarrow{\varepsilon \to 0} h
$$

（$H=1$ 时 $H \vee \text{Alt} = 1 = \text{Obs}$，对所有 Alt 一致）

$$
P(H\!=\!0, \text{Obs}\!=\!1) \propto (1-h) \sum_{\text{Alt}} \pi(\text{Alt}) \cdot f(0, \text{Alt}, 1)
$$

- $\text{Alt}=1$：$0 \vee 1 = 1 = \text{Obs}$ ✓，$f = 1-\varepsilon$。贡献 $a(1-\varepsilon)$
- $\text{Alt}=0$：$0 \vee 0 = 0 \neq 1 = \text{Obs}$ ✗，$f = \varepsilon$。贡献 $(1-a)\varepsilon$

$$
P(H\!=\!0, \text{Obs}\!=\!1) \propto (1-h)[a(1-\varepsilon) + (1-a)\varepsilon] \xrightarrow{\varepsilon \to 0} (1-h) \cdot a
$$

$$
\boxed{P(H\!=\!1 \mid \text{Obs}\!=\!1) = \frac{h}{h + a(1-h)}}
$$

与 `docs/foundations/theory/04-reasoning-strategies.md` §2.2 一致。✓

### 4.2 Elimination

**语义**：穷尽性 $\text{Exh}$ 声称候选 $C_1, C_2, \ldots, C_n$ 和幸存者 $S$ 穷尽所有可能；每个 $C_i$ 被证据 $E_i$ 反驳；推出 $S$。

**FormalStrategy 接口**：`premises=[Exh, C₁, E₁, C₂, E₂, ...]`，`conclusion=S`。

以 2 个 candidate 为例（n 个 candidate 的泛化是直接的：disjunction 变为 (n+1) 元，contradiction 和 conjunction 输入各增加对应项）。

**因子图**：
```
disjunction([C₁, C₂, S]) → D            # D: π=0.5，连接两个因子
equivalence([D, Exh]) → Eq              # Eq: π=1-ε，断言型（dead-end，约束保持）
contradiction([C₁, E₁]) → Contra₁       # Contra₁: π=1-ε，断言型（dead-end，约束保持）
contradiction([C₂, E₂]) → Contra₂       # Contra₂: π=1-ε，断言型（dead-end，约束保持）
conjunction([Exh, E₁, E₂]) → G          # G: π=0.5，连接两个因子
implication([G]) → S
```

与旧文档的"当前（有 bug）"完全相同——**没有 bug**。Eq、Contra₁、Contra₂ 是断言型 conclusion（$\pi = 1-\varepsilon$），dead-end 时约束正常保持。D 和 G 是计算型中间变量（$\pi = 0.5$），连接多个因子，信息正常流通。

注意：conjunction 的 variables 中**不包含** Contra 变量。contradiction 因子直接约束 $(C_i, E_i)$ 对，conjunction 只需要组合 Exh 和各 $E_i$。

#### 4.2.1 CPT 关键行：$P(S\!=\!1 \mid \text{Exh}, C_1, E_1, C_2, E_2)$

完整 CPT 有 $2^5 = 32$ 行。以下推导关键行（$\varepsilon \to 0$）：

| Exh | $E_1$ | $E_2$ | 约束效果 | $P(S\!=\!1)$ |
|-----|-------|-------|---------|-------------|
| 1 | 1 | 1 | $C_1\!=\!0, C_2\!=\!0$（均被反驳），$D=S$，$D=1$ | $\to 1$ |
| 1 | 1 | 0 | $C_1\!=\!0$，$C_2$ 自由，$C_2 \vee S = 1$ | $S$ 与 $C_2$ 竞争 |
| 1 | 0 | 0 | $C_1, C_2$ 均自由，$C_1 \vee C_2 \vee S = 1$ | 三方竞争 |
| 0 | 1 | 1 | $C_1\!=\!0, C_2\!=\!0$，穷尽性弱，$G=0$ | implication 路径不激活，S 依赖 disjunction 路径但 Exh=0 弱化 |

详细推导第一行（Exh=1, E₁=1, E₂=1）：
- contradiction：$E_i = 1 \Rightarrow C_i = 0$（$\pi(\text{Contra}_i) = 1-\varepsilon$ 激活约束）
- disjunction：$D = 0 \vee 0 \vee S = S$
- equivalence：$D = \text{Exh} = 1 \Rightarrow S = 1$（$\pi(\text{Eq}) = 1-\varepsilon$ 激活约束）
- conjunction：$G = 1 \wedge 1 \wedge 1 = 1$
- implication：$G = 1 \Rightarrow S = 1$

两条独立路径都推出 $S = 1$。✓

详细推导第二行（Exh=1, E₁=1, E₂=0，部分反驳）：
- $C_1 = 0$（被反驳），$C_2$ 自由（$E_2 = 0$ 时 contradiction 约束弱）
- $D = C_2 \vee S$，$D = \text{Exh} = 1$，所以 $C_2 \vee S = 1$
- $G = 1 \wedge 1 \wedge 0 = 0$，implication vacuously true
- $S$ 信念取决于 $C_2$ 的先验：$C_2$ 越高则 $S$ 越低（竞争关系）

正确的 elimination 语义：未被完全反驳时，幸存者与剩余候选竞争。✓

### 4.3 Case Analysis

**语义**：穷尽性 $\text{Exh}$ 声称 $\text{Case}_1, \text{Case}_2, \ldots$ 覆盖所有情况；每种情况 $\text{Case}_i$ 加上支持证据 $\text{Sup}_i$ 都蕴含结论 $\text{Concl}$。

**FormalStrategy 接口**：`premises=[Exh, Case₁, Sup₁, Case₂, Sup₂, ...]`，`conclusion=Concl`。

以 2 个 case 为例（n 个 case 的泛化是直接的：disjunction 增加变量，conjunction+implication 对增加对应项）。

**因子图**：
```
disjunction([Case₁, Case₂]) → D          # D: π=0.5，连接两个因子
equivalence([D, Exh]) → Eq              # Eq: π=1-ε，断言型（dead-end，约束保持）
conjunction([Case₁, Sup₁]) → G₁          # G₁: π=0.5，连接两个因子
implication([G₁]) → Concl
conjunction([Case₂, Sup₂]) → G₂          # G₂: π=0.5，连接两个因子
implication([G₂]) → Concl
```

同样与旧文档的"当前"写法相同——没有 bug。$G_1$、$G_2$ 连接 conjunction 和 implication 两个因子，信息正常流通。

#### 4.3.1 CPT 关键行：$P(\text{Concl}\!=\!1 \mid \text{Exh}, \text{Case}_i, \text{Sup}_i)$

完整 CPT 有 $2^5 = 32$ 行。关键行（$\varepsilon \to 0$）：

| Exh | Case₁ | Sup₁ | Case₂ | Sup₂ | $P(\text{Concl}\!=\!1)$ |
|-----|-------|------|-------|------|------------------------|
| 1 | 1 | 1 | 0 | 0 | $\to 1$（Case 1 路径） |
| 1 | 0 | 0 | 1 | 1 | $\to 1$（Case 2 路径） |
| 1 | 1 | 1 | 1 | 1 | $\to 1$（两条路径） |
| 1 | 1 | 0 | 0 | 0 | 弱（Sup₁=0，Case₁ 路径不完整） |
| 0 | 1 | 1 | 0 | 0 | 弱（Exh=0，穷尽性不成立） |

详细推导第一行（Exh=1, Case₁=1, Sup₁=1, Case₂=0, Sup₂=0）：
- equivalence：$D = 1$，即 $\text{Case}_1 \vee \text{Case}_2 = 1$（已满足）
- $G_1 = \text{Case}_1 \wedge \text{Sup}_1 = 1$
- implication：$G_1 = 1 \Rightarrow \text{Concl} = 1$ ✓
- $G_2 = 0$，implication vacuously true

单条路径推出结论。✓

## 5. 不受影响的策略

以下策略的 FormalExpr 只使用 conjunction + implication，所有 helper 都是计算型中间变量（$\pi = 0.5$，连接两个因子）：

| 策略 | FormalExpr 结构 | Helper 类型 |
|------|----------------|------------|
| deduction | conjunction(premises) → C, implication(C, concl) | 计算型中间变量 |
| analogy | conjunction(premises) → C, implication(C, concl) | 计算型中间变量 |
| extrapolation | conjunction(premises) → C, implication(C, concl) | 计算型中间变量 |
| mathematical_induction | conjunction([base, step]) → C, implication(C, law) | 计算型中间变量 |

注：deduction 单前提时跳过 conjunction，直接使用 implication 单因子，不产生 helper。

## 6. BP 独立性假设与 Conjunction

计算型 conclusion $\pi(M) = 0.5$ 下，$\text{belief}(M\!=\!1) = ab$（§2.3）。这等于 $P(A) \cdot P(B)$——隐含 A、B 独立性假设。

这是 BP 的 Bethe 近似的固有性质：每个因子节点将输入消息相乘，

$$m_{f \to M}(1) \propto m_{A \to f}(1) \cdot m_{B \to f}(1)$$

即使 A、B 通过其他路径相关，到了 conjunction 因子也被当作独立处理。在树图上精确，在环图上是近似。

这不是设计缺陷——BP 本身就是基于局部消息的近似推理。Conjunction 的 $\text{belief}(M) = ab$ 在独立假设下是精确的，在相关场景下是 Bethe 近似。

## 7. 实现要点

### 7.1 Lowering 统一路径

所有 Operator 使用相同的 lowering 路径：

```python
for op in formal_expr.operators:
    fid = generate_factor_id(op)
    cpt = operator_to_cpt(op.operator)  # 查表：equivalence→[1-ε,ε,ε,1-ε], ...
    add_conditional_factor(fid, op.variables, op.conclusion, cpt)
```

**不需要**：二元因子特殊路径、dead-end 检测、gate_var、`conclusion=None` 标记。

### 7.2 Conclusion 先验

| Operator 类别 | conclusion 先验 | 理由 |
|--------------|----------------|------|
| Relation（equivalence, contradiction, complement） | $1 - \varepsilon$ | 断言：算子的存在 = 关系成立 |
| Directed（conjunction, disjunction, implication） | $0.5$ | 计算：belief 由 variables 决定 |

判定规则：conclusion 的 $P(H\!=\!1)$ 能否从 $\pi(\text{variables})$ 推导出来？能 → 0.5（计算型）；不能 → $1-\varepsilon$（断言型）。

### 7.3 `potentials.md` 更新

将所有确定性算子统一为 CONDITIONAL + CPT 模板的描述，替代当前按 FactorType 分列的格式。

### 7.4 `inference.md` 更新

删除 gate_var 机制的描述。Relation operator 的 conclusion 通过 $\pi = 1-\varepsilon$ 自然激活约束，不需要门控变量。

## 参考

- 因子图理论：[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)
- BP 算法：[../theory/07-belief-propagation.md](../theory/07-belief-propagation.md)
- IR Operator 定义：[../gaia-ir/02-gaia-ir.md](../gaia-ir/02-gaia-ir.md) §2
- Helper claim 语义：[../gaia-ir/04-helper-claims.md](../gaia-ir/04-helper-claims.md)
- Factor potential 定义：[potentials.md](potentials.md)
