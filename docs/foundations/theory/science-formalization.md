# 科学知识的形式化 — 把不确定性放回它真正所在的位置

> **Status:** Target design — foundation baseline
>
> 本文档定义如何将科学论述形式化为推理超图，并解释为什么 formalization 的目标不是把所有条件概率 `p` 都推到 1，而是把不确定性局部化为可检查的前提、桥接主张和少量明确的 plausible reasoning 步骤。
>
> 前置依赖：
> - [plausible-reasoning.md](plausible-reasoning.md) — 科学推理中的 deduction、induction、abduction 与 analogy
> - [reasoning-hypergraph.md](reasoning-hypergraph.md) — 推理超图的结构（命题、算子、因子图）
> - [belief-propagation.md](belief-propagation.md) — 如何在超图上计算信念（noisy-AND、BP 算法）

## 1. 问题：`p` 的主观性究竟来自哪里

在 BP 框架里，作者需要给出的核心判断是每条推理链的条件概率 `p`。`belief-propagation.md` 已经说明：这是系统里最主要的自由度。

但这不意味着作者是在凭感觉给一条边打分。更准确地说：

- `p` 衡量的是**这一步推理在当前形式化下还剩下多少不确定性**
- 一条边的 `p` 很低，往往不是因为作者“主观”，而是因为**多个不同的推理跳跃被糊在了一条边里**

而这些推理跳跃，正是 [plausible-reasoning.md](plausible-reasoning.md) 里讨论的内容：

- **induction**：从有限实例走向一般规律
- **abduction**：从观测走向原因或最佳解释
- **analogy**：把一个结构迁移到另一个对象或情景

这些都不是保真的。即使前提全真，结论也仍可能为假。科学推理中的不确定性主要来自这里，而不是来自 deduction、equivalence、contradiction 这样的结构关系本身。

因此，formalization 的核心问题不是“如何把每条边的 `p` 都调到接近 1”，而是：

> 如何把一段自然语言论述里混在一起的 induction / abduction / analogy / 适用条件 / 理想化假设拆开，使真正不确定的部分被显式表示出来？

如果这一步做对了，`p` 就不会消失，但它会被**局部化**。系统不再面对一条笼统的“这段论证大概有多靠谱”的边，而是面对几个可单独讨论、可单独反驳、可被其他证据支持的节点和局部链条。

## 2. Formalization 的目标

formalization 不是把科学文本改写成“伪装成纯演绎”的东西。它的目标是把科学论证拆成三层：

1. **直接陈述的内容**：观测、测量、定理、模型结论、作者明确说出的判断
2. **桥接主张与适用条件**：把观测接到结论中间真正起作用的假设、解释、外推条件、理想化前提
3. **剩余的推理关系**：在这些节点都显式化之后，还无法消掉的 induction / abduction / entailment / contradiction / equivalence

好的 formalization 结果不是“没有不确定性”，而是：

- 不确定性集中在少数明确的地方
- 每个不确定步骤都能被命名、引用、争论和复用
- 剩余链条更短、更局部、更容易给出 `p`

## 3. 方法：把不可靠的推理过程提炼成 premises

### 3.1 Round 0 — 原文

起点是论文、教材、实验报告或评论文章中的自然语言论述。

这一步只做两件事：

- 标出作者的主要结论
- 标出支撑这些结论的文本片段

此时先不要急着给 `p`。因为在自然语言状态下，一段话通常同时混合了观测、解释、外推和默认假设。

### 3.2 Round 1 — 粗图

先做一个粗粒度图：

- 把可判真假的断言提为节点
- 把“这段话支持那段话”的关系先连成粗边

此时允许存在很多语义尚不清晰的 `infer` 边。粗图的作用不是给出最终概率，而是暴露出哪里还是一整团没有拆开的推理。

### 3.3 Round 2 — 找出真正的不确定跳跃

对每一条低可信、过长或语义含混的粗边，问四个问题：

1. 这里是否存在**归纳**？也就是从有限样本跳到一般规律。
2. 这里是否存在**溯因**？也就是从现象跳到原因或解释。
3. 这里是否存在**类比或跨场景迁移**？也就是把一个体系中的模式搬到另一个体系。
4. 这里是否偷偷使用了**适用条件、理想化、背景假设、测量解释**，但没有写出来？

如果答案是“有”，那么这条边的低 `p` 往往不是一个原子判断，而是多种 plausible reasoning 混在一起的结果。

### 3.4 Round 3 — 把这些跳跃提炼成显式 premises / claims

当一个不可靠的推理过程里含有若干独立的 plausible reasoning 步骤时，优先把这些步骤的**产物**提炼成显式节点。常见类型包括：

- **解释性主张**：例如“空气阻力是速度差异的主要原因”
- **一般化主张**：例如“该材料族在约 90K 以下表现出超导性”
- **适用条件**：例如“斜面实验可以作为自由落体的代理”
- **理想化前提**：例如“其他阻力和形变效应可忽略”
- **桥接原则**：例如“如果差异来源于介质阻力，那么在零阻力极限下差异应消失”

这样做的效果不是“把 uncertainty 删除”，而是把 uncertainty 从一条含混的边里搬出来，放到：

- 新节点的 `prior`
- 或这些新节点自己的支撑链条
- 或少量仍然必须保留为 induction / abduction 的局部边

提炼完成后，剩余链条常常会更接近以下两种情况之一：

- **entailment / 近似演绎**：如果桥接主张已经作为前提给出，剩余推出关系相对直接
- **局部的 plausible reasoning**：仍然需要 induction / abduction，但不再把多个不确定跳跃揉成一条边

### 3.5 什么时候应该提炼为 premise

满足以下任一条件时，通常应单独提炼：

- 这一步是结论跨出证据范围的关键位置
- 审稿人最可能质疑的正是这一步
- 这一步将来可能被其他论文独立支持或反驳
- 这一步会在多个结论之间复用
- 如果它为假，原结论的可信度会明显下降

反过来，如果一个中间步骤只是局部措辞改写、没有独立语义价值，也不会成为争议焦点，就不必强行拆成节点。

formalization 的目标是**暴露 load-bearing uncertainty**，不是把每句话原子化。

## 4. 一个更准确的 Galileo 例子

### 4.1 Round 0 — 保留原文

按照本文前面的规则，例子不应直接从“节点和边”开始，而应先保留会被形式化的原文片段。否则读者看不到后续那些中间主张究竟是从哪里抽出来的。

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

从这些原文出发，下一步才是演示“如果直接压成一条粗边会出什么问题”。

### 4.2 错误写法：把整段论证压成一条低 `p` 的边

如果把伽利略关于落体的论证写成下面这种形式：

```text
O₁ + O₂ + E --[infer, p=0.65]--> V

O₁: 介质越密，不同重量物体的速度差异越大
O₂: 在空气中，金球与铜球的速度差异极小
E: 斜面实验中 s ∝ t²，且与质量无关
V: 真空中所有物体以相同速度下落
```

这个 `p=0.65` 没有解释力。因为这条边至少混合了四种不同的东西：

- 从 `O₁ + O₂` 到“空气阻力是原因”的**abduction**
- 从有限实验到一般规律的**induction**
- 从斜面体系到自由落体体系的**analogy / 适用性迁移**
- 从“差异来自阻力”到“真空中差异消失”的**桥接前提**

这时争论会变成对一个模糊数字的争论，而不是对具体论证位置的争论。

### 4.3 更好的写法：把不确定跳跃拆出来

更合理的形式化应当把这些中间主张提出来：

| 节点 | 内容 | 角色 |
|------|------|------|
| **A** | 下落速度与重量成正比 | 亚里士多德主张 |
| **T₁** | 连球后整体比重球更慢 | 由 A 导出的演绎结果 |
| **T₂** | 连球后整体比重球更快 | 由 A 导出的演绎结果 |
| **O₁** | 介质越密，速度差异越大 | 观测 |
| **O₂** | 空气中不同重球速度差异极小 | 观测 |
| **H** | 介质阻力是观测到速度差异的主要原因 | 解释性主张 |
| **L** | 如果差异主要来自介质阻力，那么在零阻力极限下差异应消失 | 桥接前提 |
| **E₁...Eₙ** | 不同倾角、不同重复下的斜面实验结果 | 实例观测 |
| **G** | 在已测试条件下，下落行为表现出质量无关性 | 归纳出的中间主张 |
| **P** | 斜面实验可作为自由落体规律的相关代理 | 适用条件 / 类比桥梁 |
| **V** | 真空中所有物体以相同速度下落 | 目标结论 |

对应的图不再是一条大边，而是几条局部链：

```text
A --[entailment, p≈1]--> T₁
A --[entailment, p≈1]--> T₂
T₁ + T₂ --[contradiction]--> ⊥

H --[abduction, p<1]--> O₁
H --[abduction, p<1]--> O₂
H + L --[entailment, p≈1]--> V

E₁ + E₂ + ... + Eₙ --[induction, p<1]--> G
G + P --[entailment, p≈1]--> V
```

在执行层，这意味着 `O₁`、`O₂` 的高 belief 会通过反向消息支撑 `H`；但在 formalization 层，更关键的是先把 `H` 作为独立的解释性主张提出来，而不是把它藏在一条从观测直达结论的粗边里。

这里最重要的变化不是某个 `p` 变大了，而是：

- 关于 `H` 的解释性不确定性被留在围绕 `H`、`O₁`、`O₂` 的局部 abduction 子图里
- `induction` 的不确定性被留在 `E₁ + ... + Eₙ -> G`
- 从 `H` 到 `V` 的外推不再藏在边里，而是由显式前提 `L` 承担
- 从斜面实验到自由落体的迁移不再藏在边里，而是由显式前提 `P` 承担

### 4.4 为什么拆开以后“剩余链条更可靠”

因为原来那条粗边里的不确定性并不是同一种不确定性：

- 有的是“这个解释是否成立”
- 有的是“有限样本能否推广”
- 有的是“这个实验体系能否代表另一个体系”
- 有的是“这个极限推论是否成立”

把它们拆开以后，剩余链条通常只表达一种更局部的关系。例如：

- `H + L -> V` 不再承担“空气阻力是否真是原因”这个问题，它只承担“如果 H 和 L 成立，那么 V 是否跟着来”
- `G + P -> V` 不再承担“实验结果是否足以归纳出 G”这个问题，它只承担“如果 G 和 P 成立，那么是否可推出 V”

这就是“把不可靠的推理过程提炼成 premises 后，剩下的推理链更可靠”的确切含义。

它不是说所有不保真推理都被消灭了，而是说：

> 不保真性被隔离到了 `H`、`L`、`G`、`P` 这些可命名、可讨论、可被独立支持或反驳的位置上。

### 4.5 形式化之后，争论会落在什么地方

重写后的图让审查和后续研究有了明确落点：

- 如果有人怀疑“介质阻力是主要原因”，他在攻击 `H`
- 如果有人怀疑“零阻力极限可这样外推”，他在攻击 `L`
- 如果有人怀疑“斜面实验足以推广到自由落体”，他在攻击 `P`
- 如果有人提出新实验反例，他可能直接削弱 `G`

这比争论一个模糊的 `infer(p=0.65)` 更接近真实科学实践。

## 5. `p` 如何因此变得更可判断

formalization 之后，`p` 的判断会更稳定，但原因不是“所有 `p` 都趋向 1”。真正发生的是：

1. **每条边更局部**：`p` 只对应一种清楚的推理角色。
2. **可比性更强**：不同作者对同一类 induction 或 abduction 更容易形成一致判断。
3. **反驳更精确**：新证据会打到具体前提或桥接主张，而不是笼统打碎整条边。
4. **可复用性更强**：`H`、`L`、`P`、`G` 这类节点可被其他包复用、支撑或矛盾。
5. **网络约束更强**：equivalence、contradiction 和独立证据路径会约束这些中间主张的 belief。

所以，客观性来自下面这个过程：

```text
自然语言中的模糊论证
-> 找出其中的 plausible reasoning 跳跃
-> 把跳跃产物和桥接条件显式化
-> 把剩余 uncertainty 局部化到少量节点和边
-> 让这些节点和边进入更大的证据网络
-> belief 由网络约束而不是单次主观打分决定
```

## 6. 与相邻文档的分工

- [plausible-reasoning.md](plausible-reasoning.md) 说明**不确定性为什么存在**：因为科学推理包含 induction、abduction、analogy 等不保真步骤。
- [reasoning-hypergraph.md](reasoning-hypergraph.md) 说明**这些内容如何进图**：哪些是节点，哪些是算子。
- [belief-propagation.md](belief-propagation.md) 说明**进图之后如何计算**：给定 `p` 和 `prior` 后如何得到 belief。
- 本文档说明的是**formalist 在写图时应当如何处理不确定性**：不是把它藏进一条粗边，而是把它显式拆成可检查的 premises、桥接主张和局部推理关系。

## 参考文献

- Aristotle. *De Caelo*, Book I, Part 6. Trans. J.L. Stocks (Oxford, 1922)
- Aristotle. *Physics*, Book IV, Part 8. Trans. R.P. Hardie & R.K. Gaye (Oxford, 1930)
- Galileo Galilei. *Discorsi e Dimostrazioni Matematiche intorno a due nuove scienze* (1638). Trans. H. Crew & A. de Salvio (Macmillan, 1914)
- Polya, G. *Mathematics and Plausible Reasoning* (1954)
- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Cox, R.T. "Probability, Frequency, and Reasonable Expectation" (1946)
