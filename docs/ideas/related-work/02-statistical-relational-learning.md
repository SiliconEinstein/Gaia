# 第二章：统计关系学习与概率逻辑编程

> **状态：** 研究调研（2026-04-03）
>
> **定位：** Gaia 学术论文文献综述。本章深入分析统计关系学习（Statistical Relational Learning, SRL）和概率逻辑编程（Probabilistic Logic Programming, PLP）领域的核心系统，与 Gaia 的 "类型化科学命题 DSL → factor graph → belief propagation" 管线做详细对比。

---

## 2.1 Markov Logic Networks (Richardson & Domingos, 2006)

### 2.1.1 完整架构

Markov Logic Networks（MLN）是统计关系学习领域影响最深远的框架之一。其核心思想极其优雅：将一阶逻辑（FOL）公式附上实数权重，再通过 grounding 将其转换为 Markov 随机场（MRF），从而统一了逻辑推理与概率推理。

**完整管线如下：**

```
加权一阶逻辑公式集合 {(wᵢ, Fᵢ)}
        ↓ grounding（对常量域枚举）
Markov 随机场（无向图模型）
        ↓ 推理
边缘概率 / MAP 赋值
```

具体地，给定一组加权公式 `{(w₁, F₁), (w₂, F₂), ...}` 和一个常量域 `C = {c₁, c₂, ..., cₙ}`，MLN 定义了所有 ground atom 上的概率分布：

```
P(X = x) = (1/Z) exp(Σᵢ wᵢ · nᵢ(x))
```

其中 `nᵢ(x)` 是公式 `Fᵢ` 在世界 `x` 中被满足的 grounding 数量，`Z` 是配分函数。直觉上，一个世界违反的高权重公式越少，其概率越高。硬约束可以用 `w = +∞` 表示（违反即概率为零）。

### 2.1.2 具体例子：吸烟与癌症

经典的 MLN 例子：

```
// 公式与权重
1.5  Smokes(x) → Cancer(x)          // 吸烟者倾向于得癌症
1.1  Friends(x, y) → (Smokes(x) ↔ Smokes(y))  // 朋友间吸烟习惯趋同
```

常量域 `C = {Alice, Bob}`。Grounding 过程产生如下 ground 公式：

```
1.5  Smokes(Alice) → Cancer(Alice)
1.5  Smokes(Bob) → Cancer(Bob)
1.1  Friends(Alice, Bob) → (Smokes(Alice) ↔ Smokes(Bob))
1.1  Friends(Bob, Alice) → (Smokes(Bob) ↔ Smokes(Alice))
1.1  Friends(Alice, Alice) → (Smokes(Alice) ↔ Smokes(Alice))
1.1  Friends(Bob, Bob) → (Smokes(Bob) ↔ Smokes(Bob))
```

每条 ground 公式变为 MRF 中的一个 factor（势函数 `φ = exp(w)` 当满足，`φ = 1` 当不满足）。所有 ground atom 变为 MRF 中的变量节点。由此得到一个标准的无向概率图模型，可以用各种图模型推理算法求解。

### 2.1.3 Grounding 瓶颈

这里暴露了 MLN 最根本的可扩展性问题：**组合爆炸**。

对于 k-元谓词和 n 个常量，一个谓词就产生 O(n^k) 个 ground atom。对于含 `Friends(x, y)` 的公式，2 个常量产生 4 个 grounding，但 1000 个常量就产生 1,000,000 个 grounding。更糟的是，如果有多个高元谓词和多条公式，ground MRF 的规模迅速达到内存极限。

关键认识：这个 grounding 瓶颈**并非实现上的缺陷，而是架构性的根本问题**。MLN 将所有知识编码为一阶逻辑公式的同质集合，推理时必须将其全部展开为命题逻辑级别的 ground 实例。这与数据库查询的 "推拉模型" 类似——MLN 选择了 "全推" 策略，将所有可能的推理路径在 grounding 阶段物化。

### 2.1.4 推理：MC-SAT 算法

MLN 的推理算法经历了多代演进。最有效的通用算法是 MC-SAT（Poon & Domingos, 2006），它巧妙地结合了可满足性求解（SAT）和马尔可夫链蒙特卡洛（MCMC）：

1. 从一个满足所有硬约束的赋值开始
2. 对每条软约束公式 `(wᵢ, Fᵢ)`，若当前赋值满足它，以概率 `1 - exp(-wᵢ)` 将其加入 "活跃约束集" `M`
3. 用 SampleSAT（均匀采样 `M` 中所有约束的满足赋值）生成下一个样本
4. 重复以上过程收集样本，统计各 ground atom 的边缘概率

MC-SAT 的优势在于它利用 SAT 求解器在离散空间中高效跳转，避免了 Gibbs 采样在高度耦合分布上的混合问题。但其代价是：(a) 仍然需要完整 grounding，(b) 对连续变量不适用，(c) 采样质量难以理论保证。

### 2.1.5 权重学习

MLN 的参数学习目标是从数据中学习公式权重。标准方法是最大化伪似然（pseudo-likelihood）的梯度下降：

```
∂/∂wᵢ log PL(X=x) = nᵢ(x) - Σ_x' P(Xₗ = x'ₗ | MB_x(Xₗ)) · nᵢ(x')
```

即：每条公式在训练数据中的实际满足次数，减去在 Markov blanket 条件分布下的期望满足次数。这避免了计算配分函数 Z，但仍需对每个变量的 Markov blanket 做条件推理。

### 2.1.6 工程系统：Alchemy 与 Tuffy

- **Alchemy**（华盛顿大学）：MLN 的参考实现。完全内存计算，grounding 后的 MRF 存储为邻接表。常量域超过数千即遇到内存瓶颈。
- **Tuffy**（Niu et al., 2011，详见 §2.6）：将 grounding 下推到 RDBMS（PostgreSQL），利用数据库的索引和查询优化加速 grounding 过程。关键洞察是 grounding 本质上就是关系代数的连接操作。Tuffy 在百万级常量上实现了数量级的加速。
- **Alchemy 2**：引入 lifted inference（在一阶级别直接推理，避免完全 grounding），但仅对特定公式结构有效。

### 2.1.7 与 Gaia 的详细对比

| 维度 | MLN | Gaia | 差异为何重要 |
|------|-----|------|-------------|
| **知识表示** | 加权一阶逻辑公式（同质集合） | 类型化知识节点（claim/setting/question）+ 命名推理策略（Strategy） | MLN 中所有公式地位相同；Gaia 区分 "这是一个观测事实" 和 "这是一条推理链接"，反映了科学实践中命题与推理过程的本体论区分。例如 "YBCO 在 90K 超导" 是 claim，"BCS 理论预测超导→零电阻" 是 deduction Strategy——两者在 Gaia 中有完全不同的图结构和 factor 行为。 |
| **Grounding** | 全量枚举 O(n^k) ground atoms | 无 grounding 阶段——知识直接以命题级别声明 | Gaia 的知识节点就是命题本身，不需要从谓词+常量展开。一篇论文提出 20 个 claim 和 5 条推理链，Gaia 的图就有 25 个节点和 5 条 Strategy——不受 "常量域大小" 影响。 |
| **推理结构** | 所有公式编译为同构的 MRF factor | 不同推理类型（deduction/abduction/analogy）编译为**不同结构的 factor graph** | 这是 Gaia 的核心创新。MLN 中 "A→B"（演绎）和 "B 可由 A 解释"（溯因）都变成相同的 MRF factor。Gaia 中 deduction 使用条件概率 factor，abduction 使用 explaining-away 结构，analogy 使用桥接 factor——信息传播的方向和语义不同。 |
| **参数来源** | 从训练数据中通过梯度下降学习权重 | 人类 reviewer 设定 prior，BP 传播更新 belief | 科学推理中没有 "训练数据" 来学习 "BCS 理论的权重"。prior 来自领域专家判断，这是设计上的根本选择。 |
| **推理算法** | MC-SAT（MCMC + SAT 混合） | Loopy Belief Propagation（消息传递） | BP 是确定性的迭代算法，给出近似边缘概率，不需要采样。适合需要可复现结果的科学推理场景。 |
| **可扩展性** | 受 grounding 瓶颈限制；Tuffy 用 RDBMS 缓解 | 图规模与知识量线性相关，无 grounding 爆炸 | 一个包含 10,000 个 claim 的科学知识库在 Gaia 中是 10,000 个节点的 factor graph；在 MLN 中，如果用谓词建模则需要 grounding。 |
| **领域通用性 vs 领域特化** | 通用统计关系学习框架 | 专为科学推理设计 | Gaia 的类型系统（claim/setting/question）和推理类型（deduction/abduction/analogy/extrapolation）编码了科学方法论的结构。通用框架需要用户自己用逻辑公式重新发明这些结构。 |
| **类型系统** | 无类型（所有 ground atom 等价） | 三级类型：Knowledge 类型 × Strategy 类型 × Operator 类型 | 类型系统使得编译器可以在推理前做静态检查——例如 "setting 不能有 prior" "contradiction 只连接 claim" 这些约束在 MLN 中无法表达。 |
| **包模型与版本** | 无——所有公式在同一全局集合中 | Package → Module → Knowledge/Chain 层级；QID 命名空间；跨包引用 | 科学知识有明确的归属（哪篇论文提出了哪个 claim）。Gaia 的包模型追踪 provenance，MLN 无此概念。 |
| **审查系统** | 无 | 人类 reviewer 设定 prior 并审查推理结构 | 科学知识的概率不能从语料库统计学习；它来自同行评审。Gaia 将审查过程内化为系统的一等公民。 |

**核心洞察：** MLN 将所有公式视为**同质的加权软约束**。一条演绎推理 `∀x. Smokes(x) → Cancer(x)` 和一条溯因推理 `∀x. Cancer(x) → ∃y. CausedBy(x, y)` 在 MLN 中地位完全相同——都是带权重的子句，编译到相同结构的 MRF factor。

Gaia 的核心贡献在于：**不同认识论角色的推理应当产生不同结构的 factor graph**。具体例子：

考虑材料科学中一个简单场景：

- 演绎（deduction）："BCS 理论 + YBCO 是常规超导体 → YBCO 有 Cooper 对"。在 Gaia 中编译为条件概率 factor：前提为真时结论的条件概率为 p（接近 1.0）。信息**正向传播**：前提的 belief 增加时，结论的 belief 也增加。
- 溯因（abduction）："观测到 YBCO 超导 + BCS 理论可以解释超导现象 → BCS 理论获得支持"。在 Gaia 中编译为 explaining-away 结构。关键差异：如果有**竞争性解释**（如非常规超导机制），两个解释之间会形成 "explaining away" 效应——一个解释变得更可信时，另一个的可信度降低。MLN 中无法自然表达这种竞争关系。

这不仅仅是语法糖的问题。不同的 factor 结构意味着不同的信息传播方向和语义，最终导致不同的推理结果。

---

## 2.2 ProbLog (De Raedt et al., 2007) 与 DeepProbLog (2018)

### 2.2.1 ProbLog 架构

ProbLog 来自另一个传统：概率逻辑编程。它在 Prolog 的基础上为每个事实附加独立概率，通过编译到知识编译目标（BDD 或 d-DNNF）执行精确推理。

**架构管线：**

```
概率 Prolog 程序 {pᵢ :: factᵢ} + 确定性规则
        ↓ grounding（SLD 解析 + 相关性剪枝）
ground 程序
        ↓ Clark completion + 知识编译
BDD（Binary Decision Diagram）或 d-DNNF
        ↓ 加权模型计数（WMC）
查询的精确概率
```

### 2.2.2 具体例子

```prolog
% 概率事实
0.3 :: burglary.
0.1 :: earthquake.

% 确定性规则
alarm :- burglary.
alarm :- earthquake.

calls(X) :- alarm, neighbor(X).

% 背景知识
neighbor(mary).
neighbor(john).

% 查询
?:: calls(mary).  % 查询 mary 打电话的概率
```

ProbLog 首先对查询 `calls(mary)` 做 SLD 解析（Prolog 的标准解析过程），找到所有推导路径：

```
calls(mary) ← alarm, neighbor(mary)
  alarm ← burglary         [路径 1: burglary=true]
  alarm ← earthquake       [路径 2: earthquake=true]
```

然后构造布尔公式：`calls(mary) ↔ (burglary ∨ earthquake)`，编译为 BDD：

```
      burglary
       /    \
      T      earthquake
     /        /    \
  calls=T    T      F
            /        \
         calls=T   calls=F
```

在 BDD 上做加权模型计数：`P(calls(mary)) = 0.3 + 0.1 - 0.3 × 0.1 = 0.37`。

### 2.2.3 WMC vs BP：两种计算边缘概率的路径

ProbLog 的加权模型计数（WMC）和 Gaia 的 Belief Propagation（BP）都能计算边缘概率，但路径完全不同：

- **WMC**：将概率模型编译为布尔公式的紧凑表示（BDD/d-DNNF），然后在该表示上通过动态规划精确计算概率。编译阶段可能是指数级的（BDD 大小在最坏情况下指数于变量数），但一旦编译完成，查询是多项式时间的。本质上是 **"编译 + 精确计数"** 的范式。
- **BP**：在 factor graph 上直接迭代传递消息，每次迭代更新所有节点的信念。不需要全局编译阶段，但在有环图上是近似的（loopy BP 不保证收敛到精确边缘概率）。本质上是 **"迭代 + 近似传播"** 的范式。

二者的权衡：WMC 在小规模问题上给出精确解，但 BDD 编译的空间复杂度限制了可处理的规模；BP 天然适合大规模稀疏图，且增量更新高效（新增一个 claim 不需要重新编译整个 BDD），但在高度耦合的子图上可能不精确。

对于 Gaia 的场景——科学知识库是典型的大规模稀疏图（大量 claim，每条推理链只涉及少量前提和结论）——BP 是更自然的选择。

### 2.2.4 DeepProbLog (Manhaeve et al., 2018)

DeepProbLog 的突破在于引入 **neural predicates**：用神经网络输出概率事实，再纳入 ProbLog 的概率逻辑推理框架。

```prolog
nn(digit_net, [X], Y, [0,1,2,3,4,5,6,7,8,9]) :: digit(X, Y).
addition(X, Y, Z) :- digit(X, DX), digit(Y, DY), Z is DX + DY.
```

这里 `digit_net` 是一个图像分类神经网络，将 MNIST 图像映射为数字的概率分布。关键创新是梯度可以从逻辑层反向传播到神经网络，实现端到端训练。

这与 Gaia 的关系：Gaia 当前的 prior 来自人类 reviewer，但 DeepProbLog 的思路——**将感知模块的输出作为推理系统的概率输入**——在未来是可借鉴的方向。例如，LLM 对一个 claim 的置信度评估可以作为 Gaia 的 prior 来源之一。

### 2.2.5 与 Gaia 的详细对比

| 维度 | ProbLog | Gaia | 差异为何重要 |
|------|---------|------|-------------|
| **语法** | Prolog（Horn 子句 + 概率事实） | Typst DSL → Python IR（Knowledge + Strategy + Operator） | Prolog 语法面向逻辑编程专家；Gaia 的 Typst DSL 面向科学领域作者——声明 claim、描述推理关系，不需要理解逻辑编程范式。 |
| **编译目标** | BDD / d-DNNF（布尔电路） | Factor graph（变量节点 + factor 节点） | BDD 是对布尔函数的紧凑表示，适合精确推理但对变量序影响敏感。Factor graph 是对联合分布的分解表示，天然适合消息传递推理。 |
| **推理算法** | 加权模型计数（精确） | Loopy BP（近似） | ProbLog 给出精确概率但受限于 BDD 编译规模；Gaia 在大规模图上可行但结果是近似的。对科学推理的实际需求来说，"这个 claim 的可信度大约是 0.85" 足够有用，精确到 0.851342 并无额外价值。 |
| **概率语义** | 独立概率事实（所有选择互相独立） | 条件概率 factor（premises → conclusion 的条件概率） | ProbLog 的独立假设适合建模独立随机事件；Gaia 的条件概率直接编码 "如果前提成立，结论有多大概率成立" 的科学推理模式。 |
| **增量更新** | 需要重新编译 BDD | BP 可增量传播 | 科学知识库是持续演化的——新论文发表新 claim、新实验推翻旧结论。增量更新能力对 Gaia 至关重要。 |
| **推理类型区分** | 无（所有推导路径等价） | 命名推理策略（deduction/abduction/analogy/extrapolation） | 同 MLN 对比中的论点——ProbLog 中所有推导路径的概率组合方式相同，不区分演绎和溯因。 |
| **领域特化** | 通用概率逻辑编程 | 科学推理 | ProbLog 需要用户用 Prolog 子句手动编码科学推理结构；Gaia 的 DSL 直接提供 claim、deduction、abduction 等一等公民概念。 |

---

## 2.3 Probabilistic Soft Logic (Bach et al., 2017)

### 2.3.1 架构

PSL 的核心创新是将 MLN 的离散世界模型替换为**连续松弛**：所有变量取 [0,1] 区间的连续值，逻辑公式用 Lukasiewicz t-norm 松弛为连续函数，违反约束的代价用 hinge loss 衡量。

**管线：**

```
加权 Datalog 规则（类 Prolog 语法）
        ↓ grounding（同 MLN，但产生连续变量）
Hinge-loss Markov Random Field (HL-MRF)
        ↓ 凸优化（ADMM / consensus optimization）
MAP 赋值 x* ∈ [0,1]^n
```

关键公式：对规则 `w: A(x) ∧ B(x) → C(x)`，PSL 将其松弛为：

```
损失 = w · max(0, A(x) + B(x) - 1 - C(x))²
```

这是一个凸二次函数——所有规则的总损失仍然是凸的，因此可以用标准凸优化算法（如 ADMM）找到全局最优的 MAP 赋值。

### 2.3.2 连续真值的吸引力与局限

PSL 的连续真值 [0,1] 表面上很适合科学推理——"这个 claim 70% 可信" 可以直接编码为 0.7。而且凸优化保证多项式时间复杂度和全局最优解，避免了 MLN 的采样近似问题。

但仔细分析后会发现根本性的局限：

1. **只有 MAP，没有完整边缘概率。** PSL 求解的是 "使得总违反代价最小的单一赋值"，而非每个变量的概率分布。对于科学推理来说，知道 "claim A 在最优赋值中是 0.7" 远不如知道 "claim A 的完整后验分布——均值 0.7，95% 置信区间 [0.55, 0.85]" 有用。后者告诉你不确定性的程度——这是科学推理最关心的。

2. **Lukasiewicz t-norm 的语义合理性。** PSL 将 `A ∧ B` 编码为 `max(0, A + B - 1)`。当 `A = 0.7, B = 0.6` 时，`A ∧ B = 0.3`。这在某些场景下直觉上合理，但在科学推理中，两个独立 claim 联合为真的概率不一定遵循 t-norm（例如独立事件应该是乘法 `0.7 × 0.6 = 0.42`）。

3. **无法表达竞争性解释。** 凸优化意味着没有 explaining-away 效应——多个解释可以同时取高值。但在科学推理中，竞争性假说之间的 "此消彼长" 关系是核心现象。

### 2.3.3 与 Gaia 的对比

Gaia 通过 BP 计算**完整边缘概率**（每个 claim 的后验信念分布）；PSL 计算 **MAP 赋值**（使总代价最小的单一最优赋值）。

对科学推理而言，这个区别是根本性的。科学家不仅想知道 "最可能的世界长什么样"（MAP），更想知道 "这个 claim 在各种证据组合下有多确定"（边缘概率）。一个 MAP 值为 0.7 的 claim 可能有非常窄的后验分布（几乎确定是 0.7），也可能有很宽的分布（不确定性极大）——PSL 无法区分这两种情况，但 Gaia 可以。

此外，PSL 的凸性虽然保证了计算效率，但代价是**丧失了多模态分布的表达能力**。当科学共同体对一个问题有两种截然不同的主流观点时（例如暗物质是 WIMP 还是 axion），概率分布应该是双峰的——这在 PSL 的凸框架中无法表达。

---

## 2.4 BLOG (Milch et al., 2005)

### 2.4.1 开放世界语义

BLOG（Bayesian Logic）最独特的贡献是**开放世界假设**（Open-world assumption）：模型中的对象数量本身是一个随机变量。

```blog
type Publication;
type Researcher;

#Researcher ~ Poisson(50);  // 研究者数量未知，先验为 Poisson(50)

random Boolean publishes(Researcher r, Publication p);
random Boolean cites(Publication p1, Publication p2);
```

这与 MLN/ProbLog 的**封闭世界假设**形成鲜明对比——后者要求预先给定所有常量。

### 2.4.2 与科学知识的关系

科学知识的一个核心特征是**开放性**：新的 claim 随时可能出现（新论文发表），新的推理链接随时可能建立（旧理论被用于解释新现象），甚至新的知识类型可能出现。BLOG 的开放世界语义直觉上与科学知识的这种开放性契合。

然而，BLOG 的解决方案——将对象数量建模为随机变量——对于科学知识管理来说过于底层。科学知识的 "开放性" 不是说 "claim 的数量服从泊松分布"，而是说 "新的 claim 可以由新参与者在新包中发布"。

### 2.4.3 Gaia 的包模型作为替代方案

Gaia 用**包模型**（Package model）解决开放世界问题，这是一种完全不同的架构策略：

- **BLOG 方式**：在模型内部用随机变量表达 "可能存在未知的对象"。推理时需要对对象空间求边缘化（通常通过 MCMC 采样）。
- **Gaia 方式**：在模型外部用包管理系统支持增量扩展。新知识以新 Package 的形式 `publish`，通过 `review → integrate` 流程进入全局知识图。每个包有命名空间（QID）和 provenance 追踪。

Gaia 的方式更符合科学实践的实际运作模式：新知识不是 "随机涌现" 的，而是有归属、有审查、有版本的。包模型将开放世界问题从概率推理层面提升到知识管理层面，避免了 BLOG 在推理时对未知对象空间做 MCMC 积分的计算代价。

---

## 2.5 DeepDive (Stanford, 2015)

### 2.5.1 完整架构

DeepDive 是与 Gaia 在工程架构上最相似的系统。由 Stanford 的 Christopher Re 团队开发，用于从非结构化文本中提取知识并进行概率推理。

**完整管线：**

```
DDlog 规则（Datalog 变体）+ 非结构化文本
        ↓ 特征抽取 + grounding（下推到 PostgreSQL/Greenplum）
大规模 factor graph（数十亿 factor）
        ↓ Gibbs sampling（DimmWitted 并行引擎）
变量的边缘概率 + 学习的 factor 权重
```

**DDlog 规则示例：**

```ddlog
// 如果两个人出现在同一篇文章中，且句子模式匹配 "X married Y"，则他们可能是配偶
has_spouse(p1, p2) :-
    person_mention(p1, sentence_id, begin1, end1),
    person_mention(p2, sentence_id, begin2, end2),
    feature_married_pattern(sentence_id, begin1, end1, begin2, end2).

// 权重由系统从 distant supervision 数据自动学习
@weight(f)
has_spouse(p1, p2) :- feature(p1, p2, f).
```

DDlog 规则编译为 SQL 查询在数据库中执行 grounding，生成 factor graph。然后用 DimmWitted（一个针对 NUMA 架构优化的并行 Gibbs sampler）做推理。

### 2.5.2 DeepDive 与 Gaia 的共享骨架

**二者共享的架构模式是：**

1. **DSL 前端** → 2. **编译到 factor graph** → 3. **概率推理**

这个三阶段管线在两个系统中都是核心架构。DeepDive 用 DDlog 声明规则，Gaia 用 Typst DSL 声明知识和推理。DeepDive 编译到 factor graph + Gibbs sampling，Gaia 编译到 factor graph + Belief Propagation。

### 2.5.3 根本性哲学差异

尽管架构骨架相似，两个系统的设计哲学截然不同：

**DeepDive 问的问题是："这个事实在文本中是否被提及？"** 它的目标是信息抽取——从维基百科、新闻、论文等文本中提取结构化知识（人物关系、疾病-基因关联等）。Factor graph 中的变量是 "X 和 Y 是否是配偶关系"，factor 编码的是文本特征（"X married Y" 这个模式在多大程度上暗示配偶关系）。

**Gaia 问的问题是："给定推理结构，这个科学 claim 有多可信？"** 它的目标是科学推理——在已经形式化的知识图中传播概率信念。Factor graph 中的变量是 "claim A 是否为真"，factor 编码的是推理关系（"A 通过 deduction 以条件概率 p 支持 B"）。

这个哲学差异导致了以下具体区别：

**参数来源完全不同。** DeepDive 从 distant supervision（远程监督）学习 factor 权重。Distant supervision 的核心假设是：已知知识库中存在的事实在文本中被提及时，提取特征大致正确。例如，如果 Freebase 中记录了 "Obama 的配偶是 Michelle"，那么包含 "Obama" 和 "Michelle" 的句子中的文本模式可以用来学习 "配偶关系" 的 factor 权重。

这种方法对信息抽取很有效，但对科学推理**完全不适用**。原因很根本：**科学真理不能从语料库统计中学习**。你不能通过数有多少篇论文声称 "高温超导的机制是 X" 来决定 X 的可信度——这是诉诸权威谬误的统计版本。科学 claim 的可信度取决于推理结构的质量（实验是否严谨、推理链是否有效），而非该 claim 在文献中出现的频率。

因此，Gaia 的参数来自**人类 reviewer 的判断**。reviewer 评估一条推理链的强度（"这个 deduction 的条件概率应该是 0.95 因为 BCS 理论经过了大量实验验证"），这些参数通过 BP 传播到整个知识图。这不是技术选择的差异，而是对 "知识可信度从何而来" 这个问题的根本不同回答。

**推理结构的粒度不同。** DeepDive 的 factor graph 通常是 "扁平" 的——大量变量通过特征 factor 连接，没有层级结构。Gaia 的 factor graph 是**结构化的**——Knowledge 节点通过 Strategy（推理声明）和 Operator（逻辑约束）连接，形成有语义意义的子图（一条 deduction 链、一组 abduction 竞争解释等）。

**可解释性不同。** DeepDive 的推理结果是 "这个事实为真的概率是 0.92"，解释需要回溯到文本特征（"因为有 37 个句子匹配了 married 模式"）。Gaia 的推理结果附带完整的推理路径——"claim A 的 belief 是 0.85，因为它作为 deduction 的结论被支持（条件概率 0.95），而前提 B 的 belief 是 0.90"。这种结构化的可解释性对科学推理至关重要。

### 2.5.4 工程细节对比

| 维度 | DeepDive | Gaia |
|------|----------|------|
| **推理引擎** | DimmWitted (Gibbs sampling, NUMA 优化) | Loopy BP (消息传递) |
| **数据存储** | PostgreSQL / Greenplum | LanceDB (内容) + Neo4j/Kuzu (图拓扑) + LanceDB (向量) |
| **规模** | 数十亿 factor（信息抽取量级） | 知识库级别（万-百万 claim 量级） |
| **前端 DSL** | DDlog (Datalog 变体) | Typst DSL (科学排版 + 知识声明) |
| **输入** | 非结构化文本 | 结构化科学命题 |
| **输出** | 实体关系的概率 | 科学 claim 的后验信念 |

---

## 2.6 Tuffy (Niu et al., 2011)

### 2.6.1 核心洞察：Grounding 就是关系代数

Tuffy 的核心贡献是认识到 MLN 的 grounding 过程本质上是**关系代数的连接操作**（join），因此可以下推到关系数据库中高效执行。

考虑公式 `Friends(x, y) → (Smokes(x) ↔ Smokes(y))`。Grounding 这条公式等价于：

```sql
SELECT f.x, f.y
FROM Friends f
-- 对每个 (x, y) 对生成一个 ground clause
```

Tuffy 将谓词存储为 PostgreSQL 表，grounding 变为 SQL JOIN 查询，充分利用数据库的查询优化器、索引和磁盘 I/O 管理。在此基础上，Tuffy 还做了以下优化：

1. **基于代价的 grounding 分区**：将 ground MRF 划分为独立或弱耦合的分区，分别推理。
2. **增量 grounding**：当数据变化时只重新 grounding 受影响的部分。
3. **利用数据库的并行性**：PostgreSQL 的并行查询自然地加速 grounding。

### 2.6.2 对 Gaia 可扩展性的启示

Tuffy 的成功说明了一个深刻的架构原则：**推理系统的可扩展性瓶颈往往不在推理本身，而在推理前的预处理阶段**。

Gaia 没有 grounding 瓶颈（因为知识直接以命题级别声明），但有类似的预处理挑战：

1. **包编译**：将 Typst 源文件编译为 Gaia IR（factor graph）——这一步目前在 CLI 本地执行，性能取决于 Typst 编译器。
2. **跨包连接**：当新包引用旧包中的 Knowledge 时，需要解析跨包引用（QID 查找）并将新 factor 连接到全局图。
3. **全局 BP 传播**：新知识加入后，BP 需要重新传播以更新受影响节点的 belief。

Tuffy 的经验提示 Gaia 可以借鉴 "下推到数据库" 的策略：例如将跨包引用解析下推到图数据库（Neo4j/Kuzu）的查询层，将 BP 的消息传递利用图数据库的遍历引擎加速。但 Gaia 的规模预期（万到百万级 claim）远小于 Tuffy 处理的规模（亿级 ground atom），因此当前阶段这不是优先问题。

---

## 2.7 本章总结

统计关系学习的核心框架（MLN、ProbLog、PSL）和工程系统（DeepDive、Tuffy）共同构成了 "逻辑 + 概率" 的技术版图。它们的共同模式是：

```
声明式逻辑语言 → 编译 / grounding → 概率图模型 → 推理
```

Gaia 共享这个高层模式，但在每个阶段都有根本性的差异化设计：

1. **声明层**：不是通用逻辑公式，而是为科学推理量身设计的类型化 DSL（claim/setting/question + deduction/abduction/analogy）。
2. **编译层**：不是同质的 grounding（所有公式 → 同构 factor），而是**语义驱动的编译**（不同推理类型 → 不同 factor graph 结构）。这是 Gaia 最核心的学术贡献。
3. **参数层**：不是从数据学习权重，而是从人类审查获取 prior。这反映了对 "科学知识的可信度从何而来" 这个问题的不同哲学立场。
4. **推理层**：使用 BP 而非 MCMC/WMC/凸优化，提供确定性的、可增量更新的边缘概率计算。
5. **工程层**：包模型 + 审查系统 + 版本追踪，将知识管理的社会过程内化为系统的一等公民。

这些差异不是独立的设计选择，而是从同一个根本洞察推导出来的：**科学推理不是通用逻辑推理的特例——它有自己的认识论结构（演绎、溯因、类比各有不同的推理语义），自己的参数来源（同行评审而非数据统计），自己的社会过程（发表、审查、整合）。一个好的科学推理系统应当将这些结构编码为一等公民，而不是强迫用户用通用逻辑公式重新发明它们。**
