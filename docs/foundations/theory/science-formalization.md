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

这一步产生的图是粗糙的：许多推理链被标记为 `infer`（未分类），算子类型和布线方向尚不明确。

### 2.3 Round 2 — 识别算子类型与布线

粗图的核心问题不是"p 应该是多少"，而是"这条推理链的算子类型是什么"。每种算子在因子图上有**明确的布线方向和概率更新规则**（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §7.3）：

| 算子类型 | 布线方向 | p 的含义 | p 为什么接近 1 |
|---------|---------|---------|--------------|
| **entailment** | 前提→结论，保真 | "前提真则结论必然真" | 逻辑蕴含本身就是确定性的 |
| **induction** | 多个实例（前提）→ 一般规律（结论） | "如果这些实例全部成立，规律成立的概率" | 每增加一个前提实例，支撑更强 |
| **abduction** | 假说（前提）→ 观测（结论） | "如果假说为真，我们会观测到这个现象" | 假说与观测的对应关系通常是明确的 |
| **contradiction** | 双向，真值取反 | — | BP 自动处理互斥 |
| **equivalence** | 双向，真值一致 | — | BP 自动锁定一致性 |

**关键洞察**：当算子类型被正确识别、布线方向正确后，每条链上的 p 通常**自然接近 1**。p < 1 往往是因为算子类型错误或布线不完整 — 隐含前提没有显式化。

### 2.4 Round 3 — 正确部署算子

对 Round 2 识别出的每条推理链，按其算子类型正确布线：

**Abduction 的正确布线**：认识论上我们从观测推向假说，但因子图中假说是前提、观测是结论。p 回答的是"如果假说为真，能否预期这个观测"— 这通常接近 1。BP 的**反向消息**自动完成从观测到假说的推断：观测的高 belief 通过反向消息提升假说的 belief。

```
错误:  (O₁) + (O₂) --[abduction, p≈0.7]--> (H)   ← 布线反了，p 不确定

正确:  (H) --[abduction, p≈1]--> (O₁)   "假说为真→预期观测到 O₁"
       (H) --[abduction, p≈1]--> (O₂)   "假说为真→预期观测到 O₂"
       BP 反向消息: O₁, O₂ 的高 belief → H 的 belief 上升
```

**Induction 的正确布线**：每个具体实例是一个独立的前提节点。noisy-AND 语义意味着所有前提同时成立才支撑结论。增加更多前提实例 = 增加更多证据 = 更强的归纳支撑。

```
粗糙:  (E) --[induction, p≈0.85]--> (V)   ← 把实验当成一个整体

精细:  (E_θ₁) + (E_θ₂) + ... + (E_θₙ) --[induction, p≈1]--> (V)
       每个 E_θᵢ: "倾角 θᵢ 下 s∝t²，与质量无关"
       p≈1: "如果所有倾角都成立，等速下落成立"
```

**不确定性的转移**：正确部署算子后，p 接近 1，剩余的不确定性从"推理链的强度"转移到"前提命题是否为真"。后者可以被网络中的其他证据约束（观测、实验、其他推理路径），前者不能。

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

从原文中提取命题和推理链。这一步先不纠结算子类型，用 `infer` 标记不确定的链：

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
| **E** | 斜面实验：s ∝ t²，与质量无关，对所有倾角成立 | claim（实验） |

**因子节点（推理链）：**

```
f1: A --[entailment, p≈1]--> T₁     "若重者快，轻球拖拽重球"
f2: A --[entailment, p≈1]--> T₂     "若重者快，绑后更重应更快"
f3: T₁ + T₂ --[contradiction]-->     "同一前提推出矛盾结论"
f4: A + V --[contradiction]-->        "速度正比重量 vs. 等速下落"

f5: O₁ + O₂ --[infer, p=?]--> H      "观测→假说（算子待定）"
f6: H --[infer, p=?]--> V             "假说→预测（算子待定）"
f7: E --[infer, p=?]--> V             "实验→结论（算子待定）"
```

f1-f4 的算子类型明确（entailment 和 contradiction），p 值确定。f5-f7 标记为 `infer` — 算子类型和布线方向尚未确定。

### 3.3 Round 2 — 识别算子类型

**f5：观测→空气阻力假说 — 应为 abduction**

伽利略从"介质越密差异越大"推断"空气阻力是原因"。这是典型的溯因推理（inference to best explanation）。按 abduction 的布线规则（参见 [reasoning-hypergraph.md](reasoning-hypergraph.md) §7.3）：**假说是前提，观测是结论**。p 回答的问题变成"如果空气阻力确实是原因，我们是否预期观测到介质越密差异越大"— 答案几乎是确定的（p ≈ 1）。BP 的反向消息自动完成从观测到假说的推断。

**f6：空气阻力假说→真空等速 — 应为 entailment**

如果空气阻力是速度差异的唯一原因（H），那么去除空气阻力（真空）后差异消失（V）。这是逻辑蕴含，不是类比。p ≈ 1。

**f7：斜面实验→等速下落 — 应为 induction**

斜面实验在多个倾角、多次重复下观测到 s ∝ t²（与质量无关）。这是从多个具体实例归纳出一般规律。应将每个实验实例拆为独立前提。

### 3.4 Round 3 — 正确部署算子

**路径 1：连球悖论（entailment + contradiction）**

这条路径在 Round 1 已经正确，无需修改。连球论证是纯逻辑演绎：

```
A --[entailment, p≈1]--> T₁    "若重者快，轻球拖拽使整体变慢"
A --[entailment, p≈1]--> T₂    "若重者快，绑后更重应更快"
T₁ + T₂ --[contradiction]-->    "T₁ 与 T₂ 不可能同时为真"
```

BP 结果：T₁ 和 T₂ 矛盾 → 共同前提 A 的 belief 被压低。这就是 modus tollens 的自然实现。

**路径 2：介质观测（abduction，正确布线）**

将 f5 按 abduction 规则重新布线 — 假说为前提，观测为结论：

```
H --[abduction, p≈1]--> O₁    "空气阻力是原因→密介质差异大"
H --[abduction, p≈1]--> O₂    "空气阻力是原因→空气中差异微小"
H --[entailment, p≈1]--> V    "阻力是唯一原因→真空中等速"
```

每条链的 p 都接近 1，因为它们回答的是"如果假说为真，能否预期这个观测"— 这几乎是假说本身的定义。

BP 反向消息的效果：O₁ 和 O₂ 已被观测到（belief 高）→ 反向消息提升 H 的 belief → H 的高 belief 正向传播到 V。

如果存在竞争假说 H'（如"重量本身决定速度，与介质无关"），它也会连接到 O₁ 和 O₂，但无法同时解释"水银中只有金能下沉"和"空气中差异微乎其微"。BP 的 explaining away 机制自动偏好 H 而压低 H'。

**路径 3：斜面实验（induction，拆分实例）**

将 f7 拆为多个独立观测实例作为前提：

```
E_θ₁ + E_θ₂ + ... + E_θₙ + E_m₁ + E_m₂ --[induction, p≈1]--> V

其中:
  E_θᵢ: "倾角 θᵢ 下 s ∝ t²，与质量无关"  （实验实例）
  E_mⱼ: "材料 mⱼ 的球在所有倾角下表现一致"  （实验实例）
```

p ≈ 1 的含义："如果所有这些实验实例都成立，那么一般规律（等速下落）成立。"这是一个强归纳 — 100 次重复实验，所有倾角，所有测试材料都一致。

noisy-AND 语义在此发挥作用：每增加一个前提实例（更多倾角、更多材料），归纳支撑更强。如果某个新实例失败（某种材料在某个倾角下不符合 s ∝ t²），该实例的 belief 降低，通过 noisy-AND 压低 V 的 belief — 系统自动处理反例。

**精炼后的完整图：**

三条路径都已正确部署算子，所有链的 p ≈ 1：

| 路径 | 算子类型 | 链数 | p 值 |
|------|---------|------|------|
| 连球悖论 | entailment + contradiction | 3 | ≈ 1 |
| 介质观测 | abduction + entailment | 3 | ≈ 1 |
| 斜面实验 | induction | 1（多前提） | ≈ 1 |

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

### 4.1 正确部署算子使 p → 1

一条 p < 1 的推理链通常意味着算子类型错误或布线不完整。修正方法对应算子类型：

- **Abduction 布线反了**：如果把观测当前提、假说当结论，p 不确定（"从这些观测能多大程度推出假说？"）。反转布线后，p 变成"假说为真时预期这个观测吗？"— 通常接近 1。推断工作交给 BP 反向消息。
- **Induction 前提不足**：如果把多个观测打包成一个节点，丢失了 noisy-AND 的逐实例支撑。拆分为多个前提后，每增加一个实例都强化归纳。
- **隐含前提**：推理依赖未显式声明的假设。将其显式化为新节点后，原链变为多前提的 p ≈ 1 链。
- **竞争假说未建模**：存在替代解释但未显式声明。将竞争假说加入图中，BP 的 explaining away 自动处理竞争。

每次修正都将不确定性从"推理链的强度 p"转移到"命题是否为真"。后者可以被网络中的其他证据约束，前者不能。

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
