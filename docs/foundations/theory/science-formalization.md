# 科学知识的形式化 — 从自然语言到推理超图

> **Status:** Target design — foundation baseline
>
> 本文档定义如何将科学论述形式化为推理超图，并论证形式化后的条件概率 p 可以趋向客观。
> 前置依赖：
> - [plausible-reasoning.md](plausible-reasoning.md) — 为什么用概率（Cox 定理、Jaynes 框架）
> - [reasoning-hypergraph.md](reasoning-hypergraph.md) — 推理超图的结构（命题、算子、因子图）
> - [belief-propagation.md](belief-propagation.md) — 如何在超图上计算信念（noisy-AND、BP 算法）

## 1. 问题：p 是唯一的主观参数

BP 文档（参见 [belief-propagation.md](belief-propagation.md)）指出，整个推理系统中唯一的主观判断是作者给出的**条件概率 p** — "这条推理有多强"。其他一切要么由理论唯一确定（noisy-AND 模型、Cromwell 下界 ε），要么随网络证据积累而递减（节点先验 π），要么由知识内容本身决定（图结构）。

这引出一个根本问题：**p 能否客观化？** 如果不能，那么整个系统的输出就依赖于个人判断，与传统的专家打分无异。如果能，Gaia 就是一个从科学文本到客观信念的机械推理系统。

本文档论证：通过充分的形式化分解，p 可以被推向 1（或接近 1），从而消除主观性。

## 2. Formalization 方法论

形式化是一个**逐步精炼**的过程。每一轮产生一张图，后一轮的图比前一轮更精细，但覆盖相同的知识内容。

### 2.1 Round 0 — 原文

起点是科学家的自然语言论述。论文、专著、实验报告中的段落是 formalization 的原料。这一步不做任何结构化，只是收集和标注原始文本。

### 2.2 Round 1 — 粗图

从自然语言中提取：

- **命题（变量节点）**：每个可以为真或假的断言
- **推理链（因子节点）**：命题之间的推理关系，标注类型（deduction、induction、abduction）和初始条件概率 p

这一步产生的图是粗糙的：某些推理链的 p 值不确定（例如 p = 0.7），因为推理中包含隐含假设或跳跃步骤。这些不确定的 p 就是**弱点（weak point）**。

### 2.3 Round 2 — 识别弱点

对粗图中每条 p < 1 的推理链追问：**为什么 p 不是 1？**

常见原因：

- **隐含前提**：推理依赖未显式声明的假设
- **归纳跳跃**：从有限观测推广到普遍规律
- **溯因缺口**：存在竞争性的替代解释
- **外推极限**：从可观测范围外推到不可观测范围

每个原因都指向一个可以进一步分解的方向。

### 2.4 Round 3 — 精炼：分解弱链

对每个弱点，将隐含假设**显式化为新的命题节点**，将跳跃步骤**分解为多条子链**。目标是让每条子链的 p 接近 1：

```
Round 1:  (A) --[f, p=0.7]--> (B)

Round 3:  (A) --[f1, p≈1]--> (A')
          (A') + (C_new) --[f2, p≈1]--> (B)
```

不确定性从"推理链的强度"转移到"新命题是否为真"。这些新命题的真值由网络中其他证据决定，而不再依赖作者对 p 的主观判断。

**关键洞察**：每次分解都将一条 p < 1 的链替换为多条 p ≈ 1 的链加上新的原子命题。分解可以递归进行，直到所有链的 p 都足够接近 1。

### 2.5 约束收敛：equivalence 与 contradiction

当所有推理链的 p ≈ 1 后，系统中剩余的自由度只有原子命题的先验 π。但科学知识不是孤立的 — 命题之间存在大量约束关系：

- **Equivalence**：不同推理路径得出相同结论（如伽利略的逻辑论证和牛顿的数学推导都指向"真空中等速下落"）
- **Contradiction**：互斥的命题（如亚里士多德的速度正比于重量 vs. 伽利略的等速下落）
- **多条独立推理链**：同一个命题被多条独立路径支撑

Cox 定理保证：给定推理网络的结构和所有 p 值，存在**唯一的**一致性信念赋值。当网络中的 equivalence 和 contradiction 足够多时，π 的初始选择变得无关紧要（参见 [belief-propagation.md](belief-propagation.md) §5 关于 π 的递减效应）。

因此：**充分形式化 + 充分约束 → 客观信念**。

## 3. 走通例子：伽利略的落体

### 3.1 Round 0 — 原文

**亚里士多德**，*De Caelo* I.6（Stocks 译）：

> "A given weight moves a given distance in a given time; a weight which is as great and more moves the same distance in a less time, the times being in inverse proportion to the weights. For instance, if one weight is twice another, it will take half as long over a given movement."
>
> 一个给定的重量在给定时间内移动给定的距离；一个更大的重量在更短的时间内移动同样的距离，时间与重量成反比。例如，如果一个重量是另一个的两倍，它通过同样的运动所需时间就是一半。

**伽利略**，*Discorsi e Dimostrazioni Matematiche intorno a due nuove scienze*（1638），连球悖论（Crew & de Salvio 译）：

> "If then we take two bodies whose natural speeds are different, it is clear that on uniting the two, the more rapid one will be partly retarded by the slower, and the slower will be somewhat hastened by the swifter. [...] But if this is true, and if a large stone moves with a speed of, say, eight while a smaller moves with a speed of four, then when they are united, the system will move with a speed less than eight; but the two stones when tied together make a stone larger than that which before moved with a speed of eight. Hence the heavier body moves with less speed than the lighter; an effect which is contrary to your supposition."
>
> 如果我们取两个自然速度不同的物体，显然将二者结合后，较快的会被较慢的部分拖慢，较慢的会被较快的部分加速。[……] 但如果这是对的，而且一块大石头以速度八下落、一块小石头以速度四下落，那么将它们绑在一起后，系统的速度将小于八；然而这两块绑在一起的石头比原来速度为八的那块更重。于是更重的物体反而比更轻的运动得更慢——这与你的假设恰恰相反。

**伽利略**，同上，介质观测：

> "I then began to combine these two facts and to consider what would happen if bodies of different weight were placed in media of different resistances; and I found that the differences in speed were greater in those media which were the more resistant."
>
> 于是我开始把这两个事实结合起来，考虑如果将不同重量的物体放入不同阻力的介质中会怎样；我发现，介质阻力越大，速度差异越大。

> "In a medium of quicksilver, gold not merely sinks to the bottom more rapidly than lead but it is the only substance that will descend at all; all other metals and stones rise to the surface and float. On the other hand the variation of speed in air between balls of gold, lead, copper, porphyry, and other heavy materials is so slight that in a fall of 100 cubits a ball of gold would surely not outstrip one of copper by as much as four fingers. Having observed this I came to the conclusion that in a medium totally devoid of resistance all bodies would fall with the same speed."
>
> 在水银介质中，金不仅比铅下沉得更快，而且是唯一能下沉的物质；所有其他金属和石头都浮到表面。另一方面，金球、铅球、铜球、斑岩球及其他重材料球在空气中的速度差异非常微小，以至于从一百腕尺高处落下，金球领先铜球绝不超过四指。观察到这些之后，我得出结论：在完全没有阻力的介质中，所有物体将以相同的速度下落。

**伽利略**，同上，斜面实验（Third Day）：

> "A piece of wooden moulding or scantling, about 12 cubits long, half a cubit wide, and three finger-breadths thick, was taken; on its edge was cut a channel a little more than one finger in breadth; having made this groove very straight, smooth, and polished, and having lined it with parchment, also as smooth and polished as possible, we rolled along it a hard, smooth, and very round bronze ball."
>
> 取一根木条，约十二腕尺长、半腕尺宽、三指厚；在其边缘切出一道略宽于一指的沟槽；将此沟槽打磨得非常直、光滑且抛光，并衬以同样光滑抛光的羊皮纸，然后沿沟槽滚下一个坚硬、光滑且非常圆的青铜球。

> "Having performed this operation and having assured ourselves of its reliability, we rolled the ball only one-quarter the length of the channel; and having measured the time of its descent, we found it precisely one-half of the former. Next, trying other distances, compared with one another and with that of the whole length, and with other experiments repeated a full hundred times, we always found that the spaces traversed were to each other as the squares of the times, and this was true for all inclinations of the plane."
>
> 完成此操作并确认其可靠性后，我们让球只滚过沟槽的四分之一长度；测量其下降时间，恰好是前者的一半。接着尝试其他距离，彼此比较并与全长比较，实验重复了整整一百次，我们始终发现：所经过的距离之比等于时间之比的平方，对斜面的所有倾角都成立。

### 3.2 Round 1 — 粗图

从原文中提取命题和推理链：

**变量节点（命题）：**

| 节点 | 内容 | 类型 |
|------|------|------|
| **A** | 下落速度与重量成正比 | claim（亚里士多德） |
| **O₁** | 介质越密，不同重量物体的速度差异越大 | claim（观测） |
| **O₂** | 空气中金球与铜球从 100 腕尺落下差距不超过四指 | claim（观测） |
| **H** | 空气阻力（而非重量本身）是速度差异的原因 | claim（假说） |
| **V** | 真空中所有物体以相同速度下落 | claim（预测） |
| **T₁** | 连球系统速度 < 重球速度（拖拽论证） | claim（演绎） |
| **T₂** | 连球系统速度 > 重球速度（总重量论证） | claim（演绎） |
| **X** | 亚里士多德理论自相矛盾 | claim（结论） |
| **E** | 斜面实验：s ∝ t²，与质量无关，对所有倾角成立 | claim（实验） |

**因子节点（推理链）：**

```
f1: A --[deduction, p≈1]--> T₁     "若重者快，轻球拖拽重球"
f2: A --[deduction, p≈1]--> T₂     "若重者快，绑后更重应更快"
f3: T₁ + T₂ --[contradiction]--> X  "同一前提推出矛盾"
f4: X --[contradiction]--> A        "亚里士多德理论被否定"

f5: O₁ + O₂ --[abduction, p≈0.7]--> H   "空气阻力是最佳解释"
f6: H --[analogy, p≈0.8]--> V            "外推到真空极限"
f7: E --[induction, p≈0.85]--> V         "斜面实验支持等速下落"
```

**弱点标注**：f5、f6、f7 的 p 值不确定，需要进一步分析。

### 3.3 Round 2 — 弱点分析

**弱点 f5（p≈0.7）— 溯因：为什么是空气阻力？**

为什么 p 不是 1？因为从"介质越密差异越大"到"空气阻力是原因"之间存在跳跃：也许差异来自其他机制（如介质浮力、介质与物体的相互作用方式等）。作者需要显式排除替代解释。

**弱点 f6（p≈0.8）— 类比外推：空气→真空**

为什么 p 不是 1？因为从有限介质密度外推到密度为零是一个极限操作。我们观测了水银、水、空气，但从未观测过真空。"趋势会延续到极限"是一个假设，不是必然。

**弱点 f7（p≈0.85）— 归纳：斜面→自由落体**

为什么 p 不是 1？因为：（a）斜面上的滚动不等于自由落体；（b）只测了有限种材料和倾角；（c）"对所有倾角成立"暗示自由落体（倾角 90°）也成立，但这是外推。

### 3.4 Round 3 — 精炼图

**分解 f5（溯因 → 子网络）：**

新增命题：
- **H₁**：密度更大的介质对运动物体施加更大的阻力（经验事实，如在水中行走比在空气中困难）
- **H₂**：如果速度差异源于介质阻力，那么阻力越大（介质越密）差异应越大
- **H₃**：观测模式（O₁）与阻力假说的预测（H₂）一致

```
原来:  O₁ + O₂ --[f5, p≈0.7]--> H

精炼:  H₁ --[deduction, p≈1]--> H₂    "阻力大→差异大（逻辑推演）"
       H₂ + O₁ --[deduction, p≈1]--> H₃  "预测与观测一致"
       H₃ --[abduction, p≈0.95]--> H     "一致性支持假说"
```

残余弱点：f5' 的 p≈0.95 而非 1，因为"观测与预测一致"不排除其他解释。但 p 已从 0.7 提升到 0.95。如果需要进一步提升，可以显式加入"排除替代解释"的命题（如"浮力无法解释空气中的微小差异"），进一步逼近 p→1。

**分解 f6（类比外推 → 子网络）：**

新增命题：
- **L₁**：水银→水→空气构成介质密度递减序列
- **L₂**：在此序列中速度差异单调递减（水银中巨大→空气中微小）
- **L₃**：单调递减序列在密度→0 的极限下差异→0

```
原来:  H --[f6, p≈0.8]--> V

精炼:  L₁ --[deduction, p≈1]--> L₂      "密度递减→阻力递减"
       O₁ + O₂ --[deduction, p≈1]--> L₂   "观测确认单调递减"
       L₂ --[deduction, p≈0.95]--> L₃     "单调递减→极限为零"
       L₃ + H --[deduction, p≈1]--> V     "阻力为零 + 阻力是原因→等速"
```

残余弱点：L₂→L₃ 的 p≈0.95，因为"三个数据点的单调趋势延续到极限"本身是一个归纳假设。但配合其他独立证据路径（连球悖论、斜面实验），这个假设可以被网络约束进一步强化。

**分解 f7（斜面归纳 → 子网络）：**

新增命题：
- **I₁**：斜面是"稀释"的重力 — 沿斜面分量 = g·sin(θ)
- **I₂**：s ∝ t² 对所有测试倾角成立（实验事实）
- **I₃**：如果对所有 θ < 90° 成立，极限 θ→90° 也成立

```
原来:  E --[f7, p≈0.85]--> V

精炼:  I₁ --[deduction, p≈1]--> I₂'     "加速度 = g·sin(θ)，与质量无关"
       E --[deduction, p≈1]--> I₂        "实验确认"
       I₁ + I₂ --[deduction, p≈1]--> I₃  "物理定律在极限处连续"
       I₃ --[deduction, p≈1]--> V        "θ=90° 即自由落体"
```

斜面这条路径在精炼后所有链的 p ≈ 1，因为几何分解 g·sin(θ) 是精确的数学关系。

### 3.5 约束网络与 belief 收敛

精炼后的图有三条独立路径通向 V（真空等速下落）：

1. **逻辑路径**：A → T₁ + T₂ → X → ¬A（亚里士多德自相矛盾）→ V 获得消极支撑
2. **观测路径**：O₁ + O₂ → H → V（介质观测 + 空气阻力假说 + 外推）
3. **实验路径**：E → I₁ + I₂ + I₃ → V（斜面实验 + 几何论证）

加上约束关系：

- **Contradiction**：A ⊗ V — 亚里士多德的"速度正比于重量"与"等速下落"互斥
- **Equivalence**（跨包）：V ≡ 牛顿 F=ma + F=mg → a=g — 不同理论框架得出相同结论

三条独立路径 + contradiction + equivalence 构成了密集的约束网络。在这个网络上运行 BP：

- A 的 belief 被连球悖论（逻辑路径）和实验证据同时压低 → 趋向 ε
- V 的 belief 被三条独立路径同时支撑 → 趋向 1-ε
- π 的初始值几乎无关紧要 — 三条独立证据链的因子消息远比 π 强

**这就是客观性的来源**：不是因为某个作者"选择"了正确的 p，而是因为充分的形式化将每条链的 p 都推向了 1，然后网络拓扑和约束关系决定了唯一的 belief 分布。

## 4. 为什么 p 可以客观化

### 4.1 分解原理：任何 p < 1 的链都可以被分解

一条 p < 1 的推理链意味着"前提全部为真时，结论仍不确定"。这种不确定性一定来自某个未显式声明的原因：

- 如果是**隐含前提**，将其显式化为新节点，原链变为多前提的 p ≈ 1 链
- 如果是**归纳跳跃**，将跳跃分解为"观测→模式→外推假设"的子链
- 如果是**溯因缺口**，显式列出竞争假说并用 contradiction 关系建模
- 如果是**外推极限**，将连续性/单调性假设显式化为可独立验证的命题

每次分解都严格减少"不确定性在 p 中的份额"，增加"不确定性在命题真值中的份额"。后者可以被网络中的其他证据约束，前者不能。

### 4.2 Cox 定理 + 充分约束 → 唯一 belief

Cox 定理（参见 [plausible-reasoning.md](plausible-reasoning.md)）保证：在满足一致性条件的前提下，给定信息 I，每个命题的合理性 P(A|I) 是唯一确定的。

当推理超图中：

1. **所有推理链的 p ≈ 1**（通过充分分解实现）
2. **存在足够多的 equivalence 和 contradiction**（科学知识的内在约束）
3. **存在多条独立路径指向同一命题**（科学验证的标准实践）

那么 π 的影响被因子消息淹没（参见 [belief-propagation.md](belief-propagation.md) §5），belief 收敛到由网络拓扑和 p 值（≈ 1）唯一决定的值。这就是 Cox 定理在因子图上的具体体现：**充分的形式化消除了参数选择的任意性，使得 belief 成为知识结构的客观函数。**

### 4.3 与科学实践的对应

这一形式化过程精确对应科学社区的实际工作方式：

| 形式化步骤 | 科学实践 |
|-----------|---------|
| 识别 p < 1 的弱链 | 同行评审质疑论证中的薄弱环节 |
| 将隐含前提显式化 | 审稿人要求作者明确假设和适用条件 |
| 分解归纳跳跃 | 要求更多实验数据、更大样本量 |
| 列出竞争假说 | 要求讨论替代解释（alternative explanations） |
| 添加 equivalence/contradiction | 独立实验室复现、不同方法得到相同结论 |
| π 被因子消息淹没 | 科学共识从证据中涌现，而非从个人先验偏好中产生 |

科学进步，在 Gaia 的视角下，就是**持续的 formalization 精炼** — 每一代科学家将上一代遗留的弱点分解得更细，添加更多约束关系，使得信念越来越由证据结构决定而非由个人判断决定。

## 参考文献

- Aristotle. *De Caelo*, Book I, Part 6. Trans. J.L. Stocks (Oxford, 1922)
- Aristotle. *Physics*, Book IV, Part 8. Trans. R.P. Hardie & R.K. Gaye (Oxford, 1930)
- Galileo Galilei. *Discorsi e Dimostrazioni Matematiche intorno a due nuove scienze* (1638). Trans. H. Crew & A. de Salvio (Macmillan, 1914)
- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Cox, R.T. "Probability, Frequency, and Reasonable Expectation" (1946)
