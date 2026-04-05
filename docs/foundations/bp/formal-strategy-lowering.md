# FormalStrategy 因子图 Lowering：中间变量与二元因子

> **Status:** Target design — 修复 #340 的理论基础
>
> 本文档论证 FormalStrategy 内部 relation operator 的 lowering 方案。
> 依赖：[potentials.md](potentials.md)（factor potential 定义）、[../theory/06-factor-graphs.md](../theory/06-factor-graphs.md)（因子图理论）。
>
> 注意：本文档中标记为"修复后"的因子图是**目标设计**，当前 `formalize.py` 和 `lowering.py` 仍使用旧的三元因子模式。

## 1. 问题：Dead-end helper 变量中和约束

FormalStrategy 的 `FormalExpr` 包含一组 Operator，每个 Operator 产生一个 helper claim 作为 conclusion。当 helper claim **只连接到一个 factor**（dead-end）时，边缘化该变量后约束消失。

### 1.1 数学证明

设 factor $f(A, B, C)$ 编码确定性关系 $C = g(A, B)$（如 equivalence: $C = \mathbb{1}[A = B]$），使用 Cromwell 软化：$f = 1-\varepsilon$ 当 $C = g(A,B)$，$f = \varepsilon$ 当 $C \neq g(A,B)$。

若 $C$ 只连接此 factor，无先验（uniform $\pi_C = 0.5$），边缘化 $C$：

$$
\sum_C \pi_C(C) \cdot f(A, B, C) = 0.5 \cdot (1-\varepsilon) + 0.5 \cdot \varepsilon = 0.5 \quad \forall (A, B)
$$

有效势函数为常数，约束**完全消失**。

设 $\pi_C = 1 - \varepsilon$（当前文档约定），则：

$$
\sum_C \pi_C(C) \cdot f(A, B, C) = \pi_C(g(A,B)) \cdot (1-\varepsilon) + \pi_C(1-g(A,B)) \cdot \varepsilon
$$

- 当 $g(A,B) = 1$ 时：$(1-\varepsilon)^2 + \varepsilon^2 \approx (1-\varepsilon)^2$
- 当 $g(A,B) = 0$ 时：$2\varepsilon(1-\varepsilon)$

比值 $\approx (1-\varepsilon)/2\varepsilon \approx 500$，约束恢复。但 $\pi_C = 1-\varepsilon$ 是一个**实现 hack**——它引入了对 $C=1$ 的先验偏好，等效于"约束倾向于被满足"的额外假设。

### 1.2 中间变量 vs Dead-end 变量

关键区别：连接**两个以上 factor** 的中间变量不是 dead end，信息可以正常流过。

设变量 $D$ 连接 $f_1(X, D)$ 和 $f_2(D, Y)$，无先验（uniform）。BP 消息：

$$
m_{D \to f_2}(d) = m_{f_1 \to D}(d) \quad (\text{唯一传入消息，uniform prior 归一化后抵消})
$$

$f_1$ 的信息通过 $D$ 传递到 $f_2$，再传递到 $Y$。**信息流不中断。**

因此：
- **中间变量**（连接多个 factor）：无先验（uniform），信息正常流通 ✓
- **Dead-end 变量**（只连一个 factor）：边缘化后约束消失 ✗

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

实现判断标准：在 FormalExpr 的 operator 列表中，若某个 operator 的 conclusion **不被任何其他 operator 的 variables 引用**，则该 conclusion 是 dead end，使用二元因子。FormalExpr 内部 helper claim 的封装性由 IR 层保证（见 [../gaia-ir/04-helper-claims.md](../gaia-ir/04-helper-claims.md)），外部 strategy 不能引用它们。

### 2.3 中间变量不设先验

FormalExpr 内部的中间变量（连接多个 factor 的 helper claim）不应设先验。理论依据：

1. **确定性函数不携带独立不确定性**：$D = A \vee B$ 的真值完全由 $A, B$ 决定，不存在"$D$ 可能为真也可能为假"的独立不确定性
2. **Uniform prior = 无信息**：对二值变量，$\pi = 0.5$ 等价于不加 unary factor，不干扰消息传递
3. **非 uniform prior 引入额外约束**：$\pi_D = 1-\varepsilon$ 等价于加了一个"$D$ 倾向为真"的软约束，改变了因子图的语义

## 3. 各 FormalStrategy 的修复后因子图

> 以下各小节中"修复后"的因子图为**目标设计**，需要修改 `gaia/ir/formalize.py` 和 `gaia/bp/lowering.py` 来实现。

### 3.1 Abduction

**语义**：假说 $H$ 或替代解释 $\text{Alt}$ 解释观测 $\text{Obs}$。

**FormalStrategy 接口**：`premises=[Obs, Alt]`，`conclusion=H`。当只有一个前提（Obs）时，`formalize.py` 自动生成 Alt 作为 interface claim 并追加到 premises。

**当前（有 bug）**：
```
disjunction([H, Alt]) → D          # D 是中间变量
equivalence([D, Obs]) → Eq         # Eq 是 dead end ✗
```

**修复后**：直接因子 `disjunction([H, Alt], conclusion=Obs)`。无中间变量。

注意这里的修法与 elimination/case_analysis 不同：abduction 中 equivalence 的一端（Obs）是真实变量，所以可以直接让 disjunction 以 Obs 为 conclusion，省去 D 和 Eq 两个中间变量。Elimination/case_analysis 中 equivalence 连接的是中间变量 D 和输入变量 Exh，无法简化为单因子，只能将 equivalence 改为二元因子。

#### 3.1.1 完整 CPT：$P(H\!=\!1 \mid \text{Obs}, \text{Alt})$

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

#### 3.1.2 宏观统计量：$P(H\!=\!1 \mid \text{Obs}\!=\!1)$

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

### 3.2 Elimination

**语义**：穷尽性 $\text{Exh}$ 声称候选 $C_1, C_2, \ldots, C_n$ 和幸存者 $S$ 穷尽所有可能；每个 $C_i$ 被证据 $E_i$ 反驳；推出 $S$。

**FormalStrategy 接口**：`premises=[Exh, C₁, E₁, C₂, E₂, ...]`，`conclusion=S`。

以 2 个 candidate 为例（n 个 candidate 的泛化是直接的：disjunction 变为 (n+1) 元，contradiction_binary 和 conjunction 输入各增加对应项）。

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
disjunction([C₁, C₂, S]) → D            # 中间变量，连接 disjunction 和 equivalence_binary
equivalence_binary(D, Exh)                # 二元因子，无 Eq
contradiction_binary(C₁, E₁)             # 二元因子，无 Contra₁
contradiction_binary(C₂, E₂)             # 二元因子，无 Contra₂
conjunction([Exh, E₁, E₂]) → G           # Contra 变量消失，从输入中移除
implication([G]) → S
```

注意 conjunction 输入中移除了 Contra 变量。这是正确的：contradiction_binary 已经作为独立的二元因子直接约束 $(C_i, E_i)$ 对，不需要在 conjunction 中重复检查。

#### 3.2.1 CPT 关键行：$P(S\!=\!1 \mid \text{Exh}, C_1, E_1, C_2, E_2)$

完整 CPT 有 $2^5 = 32$ 行。以下推导关键行（$\varepsilon \to 0$）：

| Exh | $E_1$ | $E_2$ | 约束效果 | $P(S\!=\!1)$ |
|-----|-------|-------|---------|-------------|
| 1 | 1 | 1 | $C_1\!=\!0, C_2\!=\!0$（均被反驳），$D=S$，$D=1$ | $\to 1$ |
| 1 | 1 | 0 | $C_1\!=\!0$，$C_2$ 自由，$C_2 \vee S = 1$ | $S$ 与 $C_2$ 竞争 |
| 1 | 0 | 0 | $C_1, C_2$ 均自由，$C_1 \vee C_2 \vee S = 1$ | 三方竞争 |
| 0 | 1 | 1 | $C_1\!=\!0, C_2\!=\!0$，穷尽性弱，$G=0$ | implication 路径不激活，S 依赖 disjunction 路径但 Exh=0 弱化 |

详细推导第一行（Exh=1, E₁=1, E₂=1）：
- contradiction_binary：$E_i = 1 \Rightarrow C_i = 0$
- disjunction：$D = 0 \vee 0 \vee S = S$
- equivalence_binary：$D = \text{Exh} = 1 \Rightarrow S = 1$
- conjunction：$G = 1 \wedge 1 \wedge 1 = 1$
- implication：$G = 1 \Rightarrow S = 1$

两条独立路径都推出 $S = 1$。✓

详细推导第二行（Exh=1, E₁=1, E₂=0，部分反驳）：
- $C_1 = 0$（被反驳），$C_2$ 自由（$E_2 = 0$ 时 contradiction_binary 不约束 $C_2$）
- $D = C_2 \vee S$，$D = \text{Exh} = 1$，所以 $C_2 \vee S = 1$
- $G = 1 \wedge 1 \wedge 0 = 0$，implication vacuously true
- $S$ 信念取决于 $C_2$ 的先验：$C_2$ 越高则 $S$ 越低（竞争关系）

正确的 elimination 语义：未被完全反驳时，幸存者与剩余候选竞争。✓

### 3.3 Case Analysis

**语义**：穷尽性 $\text{Exh}$ 声称 $\text{Case}_1, \text{Case}_2, \ldots$ 覆盖所有情况；每种情况 $\text{Case}_i$ 加上支持证据 $\text{Sup}_i$ 都蕴含结论 $\text{Concl}$。

**FormalStrategy 接口**：`premises=[Exh, Case₁, Sup₁, Case₂, Sup₂, ...]`，`conclusion=Concl`。

以 2 个 case 为例（n 个 case 的泛化是直接的：disjunction 增加变量，conjunction+implication 对增加对应项）。

**当前（有 bug）**：
```
disjunction([Case₁, Case₂]) → D
equivalence([D, Exh]) → Eq              # dead end ✗
conjunction([Case₁, Sup₁]) → G₁
implication([G₁]) → Concl
conjunction([Case₂, Sup₂]) → G₂
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

#### 3.3.1 CPT 关键行：$P(\text{Concl}\!=\!1 \mid \text{Exh}, \text{Case}_i, \text{Sup}_i)$

完整 CPT 有 $2^5 = 32$ 行。关键行（$\varepsilon \to 0$）：

| Exh | Case₁ | Sup₁ | Case₂ | Sup₂ | $P(\text{Concl}\!=\!1)$ |
|-----|-------|------|-------|------|------------------------|
| 1 | 1 | 1 | 0 | 0 | $\to 1$（Case 1 路径） |
| 1 | 0 | 0 | 1 | 1 | $\to 1$（Case 2 路径） |
| 1 | 1 | 1 | 1 | 1 | $\to 1$（两条路径） |
| 1 | 1 | 0 | 0 | 0 | 弱（Sup₁=0，Case₁ 路径不完整） |
| 0 | 1 | 1 | 0 | 0 | 弱（Exh=0，穷尽性不成立） |

详细推导第一行（Exh=1, Case₁=1, Sup₁=1, Case₂=0, Sup₂=0）：
- equivalence_binary(D, Exh)：$D = 1$，即 $\text{Case}_1 \vee \text{Case}_2 = 1$（已满足）
- $G_1 = \text{Case}_1 \wedge \text{Sup}_1 = 1$
- implication：$G_1 = 1 \Rightarrow \text{Concl} = 1$ ✓
- $G_2 = 0$，implication vacuously true

单条路径推出结论。✓

## 4. 不受影响的策略

以下策略的 FormalExpr 只使用 conjunction + implication，不产生 relation operator dead-end 变量：

| 策略 | FormalExpr 结构 | Helper 类型 |
|------|----------------|------------|
| deduction | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| analogy | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| extrapolation | conjunction(premises) → C, implication(C, concl) | 中间变量 |
| mathematical_induction | conjunction([base, step]) → C, implication(C, law) | 中间变量 |

这些策略的 helper claim $C$ 连接 conjunction 和 implication 两个 factor，是中间变量，$\pi_C = 0.5$（无先验）时信息正常流通。**无需修改。**

注：deduction 单前提时跳过 conjunction，直接使用 implication 单因子，不产生 helper。

## 5. 实现要点

### 5.1 `formalize.py` 修改

1. **Abduction**：改为 `Operator(operator="disjunction", variables=[H, Alt], conclusion=Obs)`。不生成 D 和 Eq helper claim。单前提时自动生成的 Alt interface claim 不受影响。
2. **Elimination**：equivalence 和 contradiction 标记为无 conclusion（二元因子）；conjunction 的 variables 中移除 Contra 变量。
3. **Case analysis**：equivalence 标记为无 conclusion（二元因子）。

### 5.2 `lowering.py` 修改

1. **二元因子支持**：在 `_lower_strategy` 的 FormalExpr 路径中，检测 Operator 的 `conclusion` 是否为 `None`（二元因子标记）。若为 `None`，调用新的 `add_binary_factor(fid, ft, variables)` 而非 `add_factor(fid, ft, variables, conclusion)`。二元因子的势函数使用 §2.1 的真值表。
2. **中间变量先验**：`_ensure_claim_var` 对 FormalExpr 内部 helper claim 统一使用 $\pi = 0.5$（当前行为已正确），不使用 $1-\varepsilon$。
3. **Top-level operator**：conclusion 保持现有逻辑（它们可能被其他 strategy 引用，不是 dead end）。

### 5.3 `potentials.md` 更新

需要补充二元因子的势函数定义（§2.1 的真值表），与现有三元因子定义并列。

### 5.4 `inference.md` 更新

当前 `inference.md` 的 gate_var 机制将被本方案取代。Relation operator 不再需要 gate_var 来控制约束强度；dead-end 变量直接消除，中间变量使用 uniform prior。
