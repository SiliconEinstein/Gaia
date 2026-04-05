# FormalStrategy 因子图 Lowering：中间变量与二元因子

> **Status:** Target design — 修复 #340 的理论基础
>
> 本文档论证 FormalStrategy 内部 relation operator 的 lowering 方案。
> 依赖：[potentials.md](potentials.md)（factor potential 定义）、[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)（因子图理论）。

## 1. 问题：Dead-end helper 变量中和约束

FormalStrategy 的 `FormalExpr` 包含一组 Operator，每个 Operator 产生一个 helper claim 作为 conclusion。当 helper claim **只连接到一个 factor**（dead-end）时，边缘化该变量后约束消失。

### 1.1 数学证明

设 factor $f(A, B, C)$ 编码确定性关系 $C = g(A, B)$（如 equivalence: $C = \mathbb{1}[A = B]$）。

若 $C$ 只连接此 factor，无先验（uniform $\pi_C = 0.5$），边缘化 $C$：

$$
\sum_C f(A, B, C) = \sum_C \delta(C = g(A, B)) = 1 \quad \forall (A, B)
$$

有效势函数为常数，约束**完全消失**。

设 $\pi_C = 1 - \varepsilon$（当前文档约定），则：

$$
\sum_C \pi_C(C) \cdot f(A, B, C) = \pi_C(g(A,B)) \cdot (1-\varepsilon) + \pi_C(1-g(A,B)) \cdot \varepsilon
$$

当 $g(A,B) = 1$ 时 $\approx (1-\varepsilon)^2$；当 $g(A,B) = 0$ 时 $\approx 2\varepsilon(1-\varepsilon)$。约束恢复，但 $\pi_C = 1-\varepsilon$ 是一个**实现 hack**——它引入了对 $C=1$ 的先验偏好，等效于"约束倾向于被满足"的额外假设。

### 1.2 中间变量 vs Dead-end 变量

关键区别：连接**两个以上 factor** 的中间变量不是 dead end，信息可以正常流过。

设变量 $D$ 连接 $f_1(X, D)$ 和 $f_2(D, Y)$，无先验。BP 消息：

$$
m_{D \to f_2}(d) = m_{f_1 \to D}(d) \quad (\text{唯一传入消息})
$$

$f_1$ 的信息通过 $D$ 传递到 $f_2$，再传递到 $Y$。**信息流不中断。**

因此：
- **中间变量**（连接多个 factor）：无先验（uniform），信息正常流通 ✓
- **Dead-end 变量**（只连一个 factor）：无论 prior 为何值，边缘化后约束消失 ✗

## 2. 解决方案：Relation operator 改为二元因子

### 2.1 二元因子真值表

将三元因子 $f(A, B, C)$（$C = g(A,B)$，$C$ 是 dead end）替换为二元因子 $f'(A, B)$，直接编码"关系成立"（即 $g(A,B) = 1$ 时高权重）：

| Operator | $f'(0,0)$ | $f'(0,1)$ | $f'(1,0)$ | $f'(1,1)$ | 语义 |
|----------|-----------|-----------|-----------|-----------|------|
| EQUIVALENCE | $1-\varepsilon$ | $\varepsilon$ | $\varepsilon$ | $1-\varepsilon$ | $A = B$ |
| CONTRADICTION | $1-\varepsilon$ | $1-\varepsilon$ | $1-\varepsilon$ | $\varepsilon$ | $\neg(A \wedge B)$ |
| COMPLEMENT | $\varepsilon$ | $1-\varepsilon$ | $1-\varepsilon$ | $\varepsilon$ | $A \oplus B$ |

n 元 DISJUNCTION $f'(A_1, \ldots, A_n)$：全 0 时 $\varepsilon$，否则 $1-\varepsilon$。

**这些二元因子等价于将三元因子的 $C=1$ 行提取并 Cromwell 软化。**

### 2.2 何时使用二元 vs 三元因子

| 情况 | 因子类型 | 说明 |
|------|---------|------|
| **Top-level operator**（conclusion 是知识图中的 claim） | 三元因子 | conclusion 可能被其他 strategy 引用，不是 dead end |
| **FormalExpr 内部，conclusion 连接其他 operator** | 三元因子 | 中间变量，信息正常流通 |
| **FormalExpr 内部，conclusion 是 dead end** | **二元因子** | 消除 dead-end 变量 |

实现判断标准：在 FormalExpr 的 operator 列表中，若某个 operator 的 conclusion **不被任何其他 operator 的 variables 引用**，则该 conclusion 是 dead end，使用二元因子。

### 2.3 中间变量不设先验

FormalExpr 内部的中间变量（连接多个 factor 的 helper claim）不应设先验。理论依据：

1. **确定性函数不携带独立不确定性**：$D = A \vee B$ 的真值完全由 $A, B$ 决定，不存在"$D$ 可能为真也可能为假"的独立不确定性
2. **Uniform prior = 无信息**：对二值变量，$\pi = 0.5$ 等价于不加 unary factor，不干扰消息传递
3. **非 uniform prior 引入额外约束**：$\pi_D = 1-\varepsilon$ 等价于加了一个"$D$ 倾向为真"的软约束，改变了因子图的语义

## 3. 各 FormalStrategy 的修复后因子图

### 3.1 Abduction

**语义**：假说 $H$ 或替代解释 $\text{Alt}$ 解释观测 $\text{Obs}$。

**当前（有 bug）**：
```
disjunction([H, Alt]) → D          # D 是中间变量
equivalence([D, Obs]) → Eq         # Eq 是 dead end ✗
```

**修复后**：直接因子 `disjunction([H, Alt], conclusion=Obs)`。无中间变量。

**验证**：设 $\pi(H) = h$，$\pi(\text{Alt}) = a$，$\pi(\text{Obs}) = o$。

单因子 $f(H, \text{Alt}, \text{Obs})$ 编码 $\text{Obs} = H \vee \text{Alt}$。

$$
P(H\!=\!1) \propto h \sum_{\text{Alt}, \text{Obs}} \pi(\text{Alt}) \cdot \pi(\text{Obs}) \cdot f(1, \text{Alt}, \text{Obs})
$$

当 $H = 1$ 时 $H \vee \text{Alt} = 1$，所以 $f = 1-\varepsilon$ 当 $\text{Obs}=1$，$f = \varepsilon$ 当 $\text{Obs}=0$。

$$
P(H\!=\!1) \propto h \cdot [o(1-\varepsilon) + (1-o)\varepsilon] \xrightarrow{\varepsilon \to 0} h \cdot o
$$

$$
P(H\!=\!0) \propto (1-h) \cdot [a \cdot o(1-\varepsilon) + (1-a) \cdot o \cdot \varepsilon + \ldots] \xrightarrow{\varepsilon \to 0} (1-h) \cdot a \cdot o
$$

$$
\boxed{P(H\!=\!1 \mid \text{Obs}\!=\!1) = \frac{h}{h + a(1-h)}}
$$

与 `docs/foundations/theory/04-reasoning-strategies.md` §2.2 一致。✓

### 3.2 Elimination

**语义**：穷尽性 $\text{Exh}$ 声称候选 $C_1, C_2, \ldots$ 和幸存者 $S$ 穷尽所有可能；每个 $C_i$ 被证据 $E_i$ 反驳；推出 $S$。

以 2 个 candidate 为例。

**当前（有 bug）**：
```
disjunction([C₁, C₂, S]) → D
equivalence([D, Exh]) → Eq              # dead end ✗
contradiction([C₁, E₁]) → Contra₁       # dead end ✗
contradiction([C₂, E₂]) → Contra₂       # dead end ✗
conjunction([Exh, E₁, Contra₁, E₂, Contra₂]) → G
implication([G]) → S
```

**修复后**：
```
disjunction([C₁, C₂, S]) → D            # 中间变量，连接 disjunction 和 equivalence
equivalence_binary(D, Exh)                # 二元因子，无 Eq
contradiction_binary(C₁, E₁)             # 二元因子，无 Contra₁
contradiction_binary(C₂, E₂)             # 二元因子，无 Contra���
conjunction([Exh, E₁, E₂]) → G           # Contra 变量消失，从输入中移除
implication([G]) → S
```

**验证** $P(S\!=\!1 \mid \text{Exh}\!=\!1, E_1\!=\!1, E_2\!=\!1)$：

硬约束下（$\varepsilon \to 0$）：
- $\text{contradiction\_binary}(C_i, E_i)$：$E_i = 1 \Rightarrow C_i = 0$
- $\text{disjunction}$：$D = C_1 \vee C_2 \vee S = 0 \vee 0 \vee S = S$
- $\text{equivalence\_binary}(D, \text{Exh})$：$D = \text{Exh} = 1 \Rightarrow S = 1$
- $\text{conjunction}$：$G = \text{Exh} \wedge E_1 \wedge E_2 = 1$
- $\text{implication}$：$G = 1 \Rightarrow S = 1$

两条独立路径（disjunction+equivalence 和 conjunction+implication）都推出 $S = 1$。✓

**验证** $P(S\!=\!1 \mid \text{Exh}\!=\!1, E_1\!=\!1, E_2\!=\!0)$（部分反驳）：

- $C_1 = 0$（被反驳），$C_2$ 自由
- $D = C_2 \vee S$，$D = \text{Exh} = 1$，所以 $C_2 \vee S = 1$
- $G = 1 \wedge 1 \wedge 0 = 0$，implication vacuously true
- $S$ 信念取决于 $C_2$ 的先验：$C_2$ 越高则 $S$ 越低（竞争关系）

正确的 elimination 语义：未被完全反驳时，幸存者与剩余候选竞争。✓

### 3.3 Case Analysis

**语义**：穷尽性 $\text{Exh}$ 声称 $\text{Case}_1, \text{Case}_2, \ldots$ 覆盖所有情况；每种情况 $\text{Case}_i$ 加上支持证据 $\text{Sup}_i$ 都蕴含结论 $\text{Concl}$。

以 2 个 case 为例。

**当前（有 bug）**：
```
disjunction([Case₁, Case₂]) → D
equivalence([D, Exh]) → Eq              # dead end ✗
conjunction([Case₁, Sup₁]) → G₁
implication([G₁]) → Concl
conjunction([Case₂, Sup₂]) ��� G₂
implication([G₂]) → Concl
```

**修复后**：
```
disjunction([Case₁, Case₂]) → D          # 中间变量
equivalence_binary(D, Exh)                # 二元因子
conjunction([Case₁, Sup₁]) → G₁
implication([G₁]) → Concl
conjunction([Case₂, Sup₂]) → G₂
implication([G₂]) → Concl
```

注意 conjunction + implication 的 helper ($G_1$, $G_2$) 不需要修改——它们是中间变量（连接 conjunction 和 implication 两个 factor），信息正常流通。

**验证** $P(\text{Concl}\!=\!1 \mid \text{Exh}\!=\!1, \text{Sup}_1\!=\!1, \text{Sup}_2\!=\!1)$：

- $\text{equivalence\_binary}(D, \text{Exh})$：$D = 1$，即 $\text{Case}_1 \vee \text{Case}_2 = 1$
- 无论哪个 Case 为真：
  - $\text{Case}_i = 1, \text{Sup}_i = 1 \Rightarrow G_i = 1 \Rightarrow \text{Concl} = 1$

两条 implication 路径独立支持 Concl。✓

**验证** $P(\text{Concl}\!=\!1 \mid \text{Exh}\!=\!1, \text{Case}_1\!=\!1, \text{Sup}_1\!=\!1, \text{Case}_2\!=\!0, \text{Sup}_2\!=\!0)$：

- $G_1 = 1 \Rightarrow \text{Concl} = 1$（Case 1 路径）
- $G_2 = 0$，implication vacuously true（Case 2 不参与）

由单条路径推出结论。✓

## 4. 不受影响的策略

以下策略的 FormalExpr 只使用 conjunction + implication，不产生 relation operator dead-end 变量：

| 策略 | FormalExpr 结构 | Helper 类型 |
|------|----------------|------------|
| deduction | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| analogy | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| extrapolation | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| mathematical_induction | conjunction([base, step]) → C, implication(C, law) | 中间变量 |

这些策略的 helper claim $C$ 连接 conjunction 和 implication 两个 factor，是中间变量，$\pi_C = 0.5$（无先验）时信息正常流通。**无需修改。**

## 5. 实现要点

1. **`formalize.py`**：对 abduction，改为 `disjunction([H, Alt], conclusion=Obs)` 单因子，不生成 D 和 Eq
2. **`formalize.py`**：对 elimination / case_analysis 中的 equivalence dead end，改为二元因子；对 elimination 中的 contradiction dead end，改为二元因子并从 conjunction 输入中移除
3. **`lowering.py`**：支持无 conclusion 的二元因子类型（或复用现有三元因子但自动检测 dead end 并边缘化）
4. **`lowering.py`**：FormalExpr 内部 helper claim 统一使用 $\pi = 0.5$（无先验），不使用 $1-\varepsilon$
5. **Top-level operator** 的 conclusion 保持现有逻辑（它们可能被其他 strategy 引用，不是 dead end）
