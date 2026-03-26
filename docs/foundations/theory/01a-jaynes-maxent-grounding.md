# Jaynes 落地：从约束到后验分布

> **Status:** Target design — foundation baseline
>
> 本文档讨论一个在 [01-plausible-reasoning.md](01-plausible-reasoning.md) 之后仍然缺失的问题：
> 如果概率是唯一一致的似然推理形式化，那么一个具体系统应如何从命题、约束和证据得到可计算的 posterior？
> 关于推理超图的结构，参见 [02-reasoning-factor-graph.md](02-reasoning-factor-graph.md)。
> 关于图上消息传递和 BP 算法，参见 [04-belief-propagation.md](04-belief-propagation.md)。
> 本文档不定义具体的编写语言语法、Graph IR 字段布局或数据库 schema。

## 1. 问题：Jaynes 给了规则，但系统还需要 posterior

[01-plausible-reasoning.md](01-plausible-reasoning.md) 解决的是认识论问题：

- 为什么科学推理需要概率而不是二值逻辑
- 为什么 Cox/Jaynes 规则是唯一一致的似然演算
- 为什么 MaxEnt 是信息不完整时唯一不额外加料的选择

但一个可执行系统还需要再走一步：

```text
命题 + 约束 + 证据
-> 一个具体的联合分布 p(x)
-> 各命题的边缘后验和条件后验
```

这一步如果不说清楚，"Jaynes 是基础" 仍然只是原则，不是可计算系统。

本文档要回答的就是：

1. 命题如何变成联合分布上的随机变量
2. 逻辑关系和经验知识如何变成约束
3. MaxEnt / Min-KL 的优化目标到底是什么
4. 局部算子（尤其是 induction）应如何理解
5. 一个具体的 Horn 例子怎样从约束走到 posterior

## 2. 语义起点：联合分布，而不是单条边的 `p`

给定原子命题集合：

```text
X_1, X_2, ..., X_n  ∈ {0,1}
```

一个完整世界是：

```text
x = (x_1, x_2, ..., x_n) ∈ Ω = {0,1}^n
```

这里：

- `X_i` 是第 `i` 个命题变量
- `x_i` 是这个变量在某个世界中的取值
- `x` 是整个系统的一次完整赋值

任意命题 `A` 都对应 `Ω` 的一个子集：

```text
[[A]] = { x ∈ Ω : x ⊨ A }
```

因此，只要系统采用 Jaynes 语义，最终对象就必然是某个联合分布：

```text
p(x | I)
```

所有 belief 都从它导出：

```text
P(A | I) = Σ_{x ∈ [[A]]} p(x | I)
P(A | B, I) = P(A ∧ B | I) / P(B | I)
```

所以：

> Jaynes 落地时，根对象不是"边的概率"，而是"在当前信息下的联合分布"。

边的 `p`、节点的 `prior`、关系的强弱，最终都必须对应到这个联合分布。

## 3. 信息 = 对联合分布的约束

定义在信息 `I` 下所有允许分布组成的可行集：

```text
C(I) = { p ∈ Δ(Ω) : p 满足 I 的全部约束 }
```

这里 `Δ(Ω)` 是 `Ω` 上所有概率分布的集合。

### 3.1 硬逻辑约束

硬逻辑不是直接生成数字，而是排除不允许的世界。

例如：

```text
A => B    ==>    P(A ∧ ¬B) = 0
```

矛盾关系：

```text
contradiction(A, B)    ==>    P(A ∧ B) = 0
```

观测为真：

```text
E observed true    ==>    P(E) = 1
```

### 3.2 软统计约束

经验性的科学知识通常是软约束。

例如：

```text
P(U=1) = π_1
P(V=1) = π_2
P(C=1 | U=1) = α_1
P(C=1 | V=1) = α_2
```

或更一般地：

```text
E_p[f_a(X)] = c_a
```

其中：

- `f_a(x)` 是第 `a` 个特征函数
- `c_a` 是我们对它的目标期望

### 3.3 为什么局部特征就够了

如果所有约束都写成局部特征和局部硬条件，那么 MaxEnt / Min-KL 的解会自动变成指数族：

```text
p*(x) = (1/Z) q(x) exp(Σ_a λ_a f_a(x)) ∏_b 1[h_b(x)=0]
```

这里：

- `q(x)` 是参考分布
- `f_a` 是软约束特征
- `λ_a` 是拉格朗日乘子
- `h_b(x)=0` 表示满足第 `b` 条硬约束
- `Z` 是归一化常数

这就是局部因子图形式的来源。  
因子图不是额外发明出来的语法糖，而是约束熵优化的自然结果。

## 4. 选择原则：MaxEnt 与 Min-KL

### 4.1 没有旧分布时：MaxEnt

如果当前没有既有信念状态，只知道一组约束，那么 Jaynes 的选择原则是：

```text
p* = argmax_{p ∈ C(I)} H(p)
H(p) = - Σ_x p(x) log p(x)
```

这等价于：

- 使用全部已知信息
- 不添加约束之外的额外结构

对于有限空间、非空凸约束集，最大熵解通常唯一。

### 4.2 有旧分布时：最小相对熵

如果系统已经有旧信念 `q(x)`，新信息到来时，不应每次重做纯 MaxEnt，而应做最小相对熵更新：

```text
p* = argmin_{p ∈ C(new)} KL(p || q)
KL(p || q) = Σ_x p(x) log (p(x) / q(x))
```

直觉上：

- 先前信念不应被无谓抹掉
- 新 posterior 应只做满足新约束所必需的最小改动

### 4.3 条件化是 Min-KL 的特例

若新信息只是硬证据 `E`，则新约束是：

```text
p(E) = 1
```

此时最小相对熵解正好退化为：

```text
p*(x) = q(x | E)
```

也就是普通 Bayes 条件化。

## 5. 局部算子怎么理解

### 5.1 entailment

最简单的硬 entailment：

```text
A => B    ==>    P(A ∧ ¬B) = 0
```

若做成局部因子，可写成：

```text
ψ_ent(A,B) = 1[A => B]
```

若做成软支持因子，则可写成：

```text
P(B=1 | A=1) = p
P(B=1 | A=0) = ε
```

这就是 [04-belief-propagation.md](04-belief-propagation.md) 里 noisy-AND + leak 的局部版本。

### 5.2 induction

induction 不是 truth-functional connective，因此严格说没有布尔意义上的"真值表"。  
它真正对应的是一个条件概率核。

最小的 Jaynes 式定义是：

```text
P(G=1 | I) = π
P(E_i=1 | G=1, I) = a
P(E_i=1 | G=0, I) = b
```

并加一个最小统计假设：

```text
E_1, ..., E_n 在给定 G 后条件独立且可交换
```

若记：

```text
s = Σ_i e_i
f = n - s
```

则 induction 因子的局部语义是：

```text
ψ_ind(e_1,...,e_n,g=1) = a^s (1-a)^f
ψ_ind(e_1,...,e_n,g=0) = b^s (1-b)^f
```

posterior 为：

```text
P(G=1 | e_1,...,e_n, I)
= [π a^s (1-a)^f] /
  [π a^s (1-a)^f + (1-π) b^s (1-b)^f]
```

因此 induction 的 `p` 不应理解成一个凭直觉写下的边权，而应理解成：

- 一个 prior
- 一个 likelihood model
- 以及由它们推出的 posterior

这和 [science-formalization.md](science-formalization.md) 中

```text
E₁ + E₂ + ... + Eₙ --[induction, p<1]--> G
```

的写法是兼容的；这里只是把那个 `p<1` 的来源写清楚了。

## 6. Worked Example 1：只有硬 Horn 规则

考虑四个变量：

```text
A, B, C, D ∈ {0,1}
```

并给定两条硬 Horn 规则：

```text
A ∧ B => C
D => C
```

### 6.1 约束

这些规则等价于：

```text
P(A=1, B=1, C=0) = 0
P(D=1, C=0) = 0
```

### 6.2 MaxEnt 目标

没有其他信息时，解：

```text
maximize   - Σ_x p(x) log p(x)
subject to p(x) = 0   for forbidden x
           Σ_x p(x) = 1
```

### 6.3 解

一共有 `16` 个世界。被禁止的有 `5` 个：

```text
0001, 0101, 1001, 1100, 1101
```

其余 `11` 个允许。MaxEnt 解就是：

```text
p*(x) = 1/11,   if x 满足两条规则
        0,      otherwise
```

也就是：

> 只有硬 Horn 规则时，MaxEnt posterior = 满足所有规则的世界上的均匀分布。

### 6.4 一些直接可算的后验

```text
P(C=1) = 8/11
P(C=1 | D=1) = 1
P(C=1 | A=1, B=1) = 1
P(D=1 | C=1) = 1/2
```

这个例子说明：

- 逻辑规则只定义了可行域
- MaxEnt 负责在可行域中选出唯一 posterior

## 7. Worked Example 2：软约束版本的 `AB -> C` 与 `D -> C`

现在把上面的例子改成软约束。

定义：

```text
U := A ∧ B
V := D
```

给定四个软约束：

```text
π_1 := P(U=1)
π_2 := P(V=1)
α_1 := P(C=1 | U=1)
α_2 := P(C=1 | V=1)
```

再加一个额外假设：

```text
U ⟂ V
```

### 7.1 约束的等价矩形式

```text
E[U]  = π_1
E[V]  = π_2
E[CU] = α_1 π_1
E[CV] = α_2 π_2
```

由于 `U` 与 `V` 独立，`P(U,V)` 已被固定：

```text
w_00 = (1-π_1)(1-π_2)
w_10 = π_1(1-π_2)
w_01 = (1-π_1)π_2
w_11 = π_1π_2
```

因此只剩下 `P(C | U,V)` 需要由 MaxEnt 选择。

### 7.2 优化目标

此时等价于最大化条件熵：

```text
maximize   Σ_{u,v} w_uv h(p_uv)
```

其中：

```text
p_uv := P(C=1 | U=u, V=v)
h(p) = -p log p - (1-p) log(1-p)
```

并满足：

```text
(1-π_2) p_10 + π_2 p_11 = α_1
(1-π_1) p_01 + π_1 p_11 = α_2
```

### 7.3 MaxEnt 解

唯一解有闭式结构：

```text
p_00 = 1/2
p_10 = σ(λ_1)
p_01 = σ(λ_2)
p_11 = σ(λ_1 + λ_2)
```

其中：

```text
σ(t) = 1 / (1 + e^{-t})
```

参数由下面两条方程唯一确定：

```text
(1-π_2) σ(λ_1) + π_2 σ(λ_1 + λ_2) = α_1
(1-π_1) σ(λ_2) + π_1 σ(λ_1 + λ_2) = α_2
```

注意：

```text
p_00 = P(C=1 | U=0, V=0) = 1/2
```

不是因为系统"偏好 0.5"，而是因为在这个最小模型里，你没有给任何关于 `U=0,V=0` 情况下 `C` 的额外约束。  
MaxEnt 只能把这个未约束状态放在熵最大的点。

### 7.4 数值例子

取：

```text
π_1 = 0.2
π_2 = 0.3
α_1 = 0.8
α_2 = 0.6
```

则解为：

```text
λ_1 ≈ 1.3341
λ_2 ≈ 0.1807
```

因此：

```text
P(C=1 | U=0, V=0) = 0.5000
P(C=1 | U=1, V=0) ≈ 0.7915
P(C=1 | U=0, V=1) ≈ 0.5451
P(C=1 | U=1, V=1) ≈ 0.8198
```

而 `q*(U,V,C)` 的 8 个状态概率为：

```text
(0,0,1): 0.2800   (0,0,0): 0.2800
(1,0,1): 0.1108   (1,0,0): 0.0292
(0,1,1): 0.1308   (0,1,0): 0.1092
(1,1,1): 0.0492   (1,1,0): 0.0108
```

这说明：

- MaxEnt 先补出完整联合分布
- 然后所有边缘和条件概率都可由该联合分布计算

## 8. 与 BP 的分工

本文档和 [04-belief-propagation.md](04-belief-propagation.md) 的分工必须严格区分：

- **本文档**：定义 posterior 的语义来源  
  也就是：世界空间、约束、MaxEnt、Min-KL、局部因子为何成立。

- **BP 文档**：定义给定局部因子后如何高效计算边缘后验  
  也就是：消息、更新、收敛、loopy BP、Bethe 近似。

换句话说：

```text
Jaynes/MaxEnt/Min-KL
-> 决定系统应该逼近哪个 posterior

Factorization
-> 把该 posterior 写成局部因子的乘积

BP
-> 近似或精确地求这些因子的边缘后验
```

如果跳过本文档这一步，系统就会只剩下：

```text
作者手写 p 和 π
```

而缺少它们与 Jaynes 理论之间的桥梁。

## 9. 结论

Jaynes 理论落地成具体系统时，最小完整链条是：

```text
命题语言
-> 可能世界 Ω
-> 约束集合 C(I)
-> MaxEnt / Min-KL 选 posterior
-> 写成局部因子
-> 用 BP 或其他算法求边缘
```

其中：

- `01-plausible-reasoning.md` 解释为什么必须用概率
- 本文档解释如何从约束走到 posterior
- `04-belief-propagation.md` 解释 posterior 怎样在图上计算

这三层缺一不可。

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Cox, R.T. "Probability, Frequency and Reasonable Expectation" (1946)
- Polya, G. *Mathematics and Plausible Reasoning* (1954)
- Shore, J.E. and Johnson, R.W. "Axiomatic Derivation of the Principle of Maximum Entropy and the Principle of Minimum Cross-Entropy" (1980)
