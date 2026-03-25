# 科学知识的形式化 V2 — 从关键结论到 weak-point 子图

> **Status:** Candidate rewrite — theory alternative
>
> 本文档给出一个比 `science-formalization.md` 更适合科学论证的 formalization workflow。核心思想不是把所有条件概率 `p` 都推到 1，而是：
>
> 1. 先抽出关键结论（claims）和主推理链
> 2. 再识别其中真正承载不确定性的 weak points
> 3. 最后把这些 weak points 展开成局部子图，再重新接回主链
>
> 前置依赖：
> - [plausible-reasoning.md](plausible-reasoning.md) — deduction、induction、abduction、analogy 的理论来源
> - [reasoning-hypergraph.md](reasoning-hypergraph.md) — 什么能作为节点，什么能作为边
> - [belief-propagation.md](belief-propagation.md) — 图一旦建好之后，概率如何按 Bayes / BP 传播

## 1. 这个文档要解决什么问题

科学文本里的问题通常不是“没有推理”，而是**推理层次混在一起**。

同一段 prose 常常同时包含：

- 目标结论
- 对结论的直接支撑
- 观测整理出的经验趋势
- 从现象到原因的解释性跳跃
- 从已观测区间到极限情形的理想化外推
- 从代理系统到目标系统的类比或 proxy transfer

如果把这些内容直接压成一条 `infer(p=0.72)` 的边，那么 `p` 的语义就会变得非常含混：

- 它到底在量化 induction？
- 还是在量化 abduction？
- 还是在量化 idealization？
- 还是在量化 experiment-to-target 的 proxy relevance？

这正是 formalization 应当避免的。

本文档的出发点是：

> 在 Jaynes 框架里，图建好之后的概率传播是机械的；  
> 真正需要 formalization judgment 的，是图应该怎样被拆出来。

因此，formalization 的目标不是把不确定性消灭，而是把不确定性**放回它真正所在的位置**。

## 2. 总 workflow

### 2.1 Step 1 — 先抽关键结论和主推理链

第一步先不要急着把每个 weak point 都展开。

先做两件事：

- 抽出文章的关键结论（key claims）
- 抽出支撑这些结论的主推理链（main reasoning chain）

这一步的目标不是最终图，而是先回答：

1. 这篇论证最后想让我们相信什么？
2. 作者显式依赖了哪些中间判断？
3. 哪些 claim 是后续值得继续展开的？

这一阶段允许留下粗粒度的 `infer` 或尚未完全拆开的 support 关系。先把主骨架搭出来，比一开始就过度原子化更重要。

### 2.2 Step 2 — 识别主链中的 weak points

主链搭出来后，再问：其中哪些步骤是真正承载不确定性的地方？

所谓 weak point，不是“写得抽象”的地方，而是：

> 如果这一步失败，结论的可信度会明显下降；  
> 并且这一步本身可以被单独争论、支持或反驳。

典型 weak points 包括：

- **induction**：从有限实例到一般规律
- **abduction**：从现象到原因或最佳解释
- **analogy / proxy transfer**：从一个系统迁移到另一个系统
- **idealization / limit bridge**：从已观察趋势走向极限情形
- **hidden applicability condition**：某个推理实际依赖适用条件，但文本里没说清

这一步的判断准则是：

- 审稿人最可能质疑的是不是这一步？
- 这一步是否可能被其他论文独立支持？
- 这一步是否会在多个结论里复用？
- 这一步为假时，下游链条是否会明显受损？

如果答案是“是”，它就不该继续藏在长边里。

### 2.3 Step 3 — 把 weak points 展开成局部子图

weak point 一旦被识别出来，就不应只留下一个 prose label，而应被展开成局部子图（local subgraph）。

最基本的原则是：

- weak point 的**局部结论**应成为显式 claim
- 这个局部结论之后可以作为主链中的 premise
- 支撑这个局部结论的 induction / abduction / proxy / idealization 结构，应留在局部子图中

这一步做完后，主链通常会变成 noisy-and 风格的结构：

```text
premise_1 + premise_2 + ... + premise_n -> conclusion
```

而原先模糊地塞在一条边里的不确定性，会被搬到：

- 某个 weak-point claim 的 prior
- 或 weak-point 子图中的局部 plausible reasoning 边

## 3. weak-point 子图的四种基本模式

本节不是定义新的逻辑原语，而是给出四种常见的 formalization pattern。

### 3.1 Abduction pattern：hypothesis 预测 phenomenon

对 abduction，图里不要写成简单的 `phenomenon -> hypothesis`。

更好的写法是：

- hypothesis 本身是一个 claim
- hypothesis 预测某个 phenomenon claim
- 一旦 phenomenon 被观测支持，对 hypothesis 的更新交给 Bayes / BP 自动完成

最紧凑的形式是：

```text
O1 + O2 + ... + Ok --[induction/support]--> T
H --[abduction]--> T
```

其中：

- `H` = hypothesis / 解释性主张
- `T` = 被 hypothesis 预测、也被 observations 支撑的 phenomenon claim
- `O1 ... Ok` = 更原始的观察

这个 pattern 的关键点是：

- `T -> H` 的支持不是单独发明的 abductive rule
- 而是 `H -> T` 这条 likelihood 关系在观测到 `T` 之后的标准 Bayes 更新

如果理论侧的预测表述和数据侧的观测表述不是同一个命题，那么可以再拆成：

```text
H --[abduction]--> B
O1 + O2 + ... + Ok --[support]--> B'
equivalence(B, B')
```

只有在 `B` 和 `B'` 语义上确实不同的时候，才需要这层 `equivalence`。否则直接收敛到同一个 `T` 更干净。

### 3.2 Induction pattern：instances 整理成经验趋势或一般化主张

induction 的标准写法是：

```text
E1 + E2 + ... + En --[induction]--> G
```

其中：

- `E1 ... En` = 具体实例、实验结果、观测样本
- `G` = 一般化主张，或者整理后的经验趋势

在科学 formalization 里，`G` 不一定是一个“普遍规律”，它也可以只是一个足够明确、可被后续使用的 trend claim。

例如：

```text
O1: 水银等高阻力介质中差异更明显
O2: 空气等低阻力介质中差异更小
```

可以整理成：

```text
T: 介质阻力越小，轻重物体的下落速度差异越小
```

这里 `T` 就是 induction 的局部结论。之后别再把 `O1`、`O2` 直接塞到最终主链里，而是让 `T` 承担这个角色。

### 3.3 Idealization pattern：把极限外推写成显式 bridge claim

idealization / limit extrapolation 很常见，但它**不是** Polya 列出的新 reasoning primitive。

它在 formalization 中最好的处理方式是：

- 不把它伪装成新的 operator
- 而是把它写成一个显式的 bridge claim

形式上：

```text
H + L + C -> V
```

其中：

- `H` = 解释性假说
- `L` = idealization / limit bridge
- `C` = 目标情形的背景条件
- `V` = 最终结论

例如：

- `H`: 速度差异主要来自介质阻力
- `L`: 如果差异主要由介质阻力造成，那么在阻力趋于 0 的极限下，这种差异应消失
- `C`: 真空环境
- `V`: 真空中不同重量物体等速下落

idealization 的 uncertainty 不应留在一条模糊的 `infer` 边里，而应落在 `L` 这个 claim 自己身上。`L` 可以靠：

- prior
- 背景理论
- 其他实验
- 或进一步的局部子图

来获得支持。

### 3.4 Analogy / proxy pattern：代理系统到目标系统的迁移

analogy 最好只用在真正的跨系统迁移上。

形式上：

```text
E1 + E2 + ... + En --[induction]--> G
P --[applicability / proxy claim]
G + P -> V
```

其中：

- `G` = 在代理系统中成立的结果
- `P` = 为什么这个代理系统与目标系统具有 relevant similarity
- `V` = 关于目标系统的结论

在 Galileo 例子里，斜面实验到自由落体的迁移更像这一类，而不是 abduction 或 idealization。

## 4. 重新接回主链：noisy-and 结构应该长什么样

一个科学结论往往不是只靠一个 weak point，而是靠多个局部判断汇聚得到。

形式化之后，主链通常变成：

```text
local_conclusion_1
+ local_conclusion_2
+ ...
+ background_condition
-> target_conclusion
```

这就是 noisy-and 风格的 factor。

这个阶段有两个重要规则：

1. **不要重复计数**
如果 `O1`、`O2` 已经被整理成 `T`，那么下游主链里一般就不要再把 `O1`、`O2` 和 `T` 一起并列塞进去。

2. **不要把 rival 被削弱误写成 target 被证明**
某个旧理论 `A` 被 contradiction 削弱，并不自动等于新理论 `V` 被证明。削弱 rival theory 与正向支撑 target claim 是两条不同路径。

## 5. Galileo worked example

### 5.1 Round 0 — source material inventory

这个例子涉及四组源材料：

- **亚里士多德的落体命题**：重者下落更快
- **连球悖论**：同一前提推出“更慢”和“更快”两条互斥结论
- **介质观察**：介质越稠密，速度差异越明显；空气中致密球差异很小
- **斜面实验**：在代理系统中，重量不是决定运动快慢的首要因素

### 5.2 Step 1 — 先抽主链

最终目标结论是：

```text
V: 在真空中，不同重量的物体应以相同速率下落
```

先粗粒度地看，这个结论至少有两条正向支撑路径和一条负向削弱路径：

1. **解释-外推路径**
   `介质趋势 + 阻力解释 + 极限 bridge + 真空条件 -> V`

2. **代理实验路径**
   `斜面实验结果 + proxy relevance -> V`

3. **削弱 rival 路径**
   `亚里士多德定律 -> 连球矛盾 -> 削弱亚里士多德`

这里第三条路径削弱的是 rival theory，不应被直接当成 `V` 的主 premise。

### 5.3 Step 2 — 标出 weak points

把上述主链细看，会发现至少有四个 weak points：

1. **trend extraction**
   从介质观测整理出经验趋势

2. **abductive explanation**
   从经验趋势走向“差异主要由阻力造成”

3. **idealization bridge**
   从“差异由阻力造成”走向“零阻力极限下差异消失”

4. **proxy transfer**
   从斜面实验走向自由落体结论

### 5.4 Step 3 — 展开成局部子图

用下面这组节点：

```text
A  = 重者下落更快
R1 = 连球后整体比重球更慢
R2 = 连球后整体比重球更快
X  = A 在连球思想实验中自相矛盾

O1 = 在更高阻力的介质里，速度差异更明显
O2 = 在空气中，致密重物之间速度差异很小
T  = 介质阻力越小，速度差异越小
H  = 日常速度差异主要来自介质阻力，而不是重量本身决定的自由落体规律
L  = 如果差异主要由介质阻力造成，那么在阻力趋于 0 的极限下，这种差异应消失

G  = 斜面实验支持“重量不是决定下落快慢的首要因素”
P  = 斜面实验可作为自由落体规律的 relevant proxy
V  = 真空中不同重量物体等速下落
```

对应局部结构：

```text
A --[entailment]--> R1
A --[entailment]--> R2
contradiction(R1, R2) -> X
X backward weakens A

O1 + O2 --[induction]--> T
H --[abduction]--> T

H + L + vacuum_env -> V

inclined_plane_observations --[induction]--> G
G + P -> V
```

这个结构的关键优点是：

- `T` 承担了“经验趋势”的角色
- `H` 承担了“解释性假说”的角色
- `L` 承担了“idealization bridge”的角色
- `P` 承担了“proxy relevance”的角色

每个 weak point 都被放在了独立的位置上。

### 5.5 为什么这比单条粗边更好

如果把 Galileo 的中段论证压成：

```text
O1 + O2 + inclined_plane --[infer, p=0.72]--> V
```

那么我们根本不知道这个 `p=0.72` 量化的是什么。

而在 V2 结构中：

- `O1 + O2 -> T` 的不确定性是 induction
- `H -> T` 的不确定性是 abduction
- `L` 自己承担 idealization 的 uncertainty
- `G + P -> V` 承担 proxy transfer 的 uncertainty

这样一来，每一个 `p` 都只对应一种明确的语义角色。

## 6. `p` 在 V2 里意味着什么

V2 不要求所有 `p` 都接近 1。

它要求的是：

- 每个 `p` 都有清楚的对象
- 每条边都只承载一种主要的 plausible reasoning 角色
- propagation 的工作与 modeling 的工作彼此分离

换句话说：

- **建模时的 judgment** 在于：节点怎么切、weak point 放在哪里、哪些 claim 需要显式化
- **图上的更新** 则交给 Bayes / BP 自动完成

对 abduction 尤其如此：

> 不是要发明一个新的 abductive propagation rule；  
> 而是要把 “hypothesis predicts phenomenon” 这件事先写进图里。

一旦 phenomenon 被观测支持，对 hypothesis 的 posterior 更新就是标准 Bayes。

## 7. 与相邻文档的分工

- [plausible-reasoning.md](plausible-reasoning.md) 说明有哪些基本 plausible reasoning types。
- [reasoning-hypergraph.md](reasoning-hypergraph.md) 说明这些内容如何作为节点和边进入图。
- [belief-propagation.md](belief-propagation.md) 说明图建好之后如何机械地做概率更新。
- 本文档补上的是**formalization workflow 本身**：从主链、weak points 到局部子图，再回到 noisy-and 主链。

## 参考文献

- Aristotle. *De Caelo*, Book I, Part 6
- Galileo Galilei. *Discorsi e Dimostrazioni Matematiche intorno a due nuove scienze* (1638)
- Polya, G. *Mathematics and Plausible Reasoning* (1954)
- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Cox, R.T. "Probability, Frequency, and Reasonable Expectation" (1946)
