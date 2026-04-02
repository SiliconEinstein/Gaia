# Double Counting Problem — 分布式知识协作中的核心问题

> **Status:** Idea
>
> 本文档从第一性原理分析 Gaia 在 GitHub package 协作生态中的核心难题：不是“如何发明独立证据算子”，而是“如何在开放协作中避免把同一命题、同一证据源或同一论证改写重复计数”。

## 1. 问题陈述

Gaia 的协作模型是：

- 每个研究者或 agent 都可以独立创建 Gaia package
- package 通过 GitHub 发布、review、rebuttal 和演化
- 后续研究者、reviewer、LKM 或其他用户可以发现跨 package 的关系

这天然会产生一个系统性问题：

> 不同 package 往往在彼此未知的情况下，重复陈述同一个命题、复用同一证据源、或只是重写旧论证。若系统把这些都当成新的独立支持路径，后验 belief 就会被系统性高估。

这就是 **double counting problem**。

它不是某个边角问题，而是开放世界知识协作中的主问题之一。

## 2. 第一性原理

### 2.1 概率论不会自动解决错误建图

在因子图 / BP 里，结论节点 `X` 的 belief 具有乘积结构：

```text
b(X) ∝ π(X) × ∏ μ_{f→X}
```

这个乘积成立的前提不是“系统使用了概率论”，而是：

```text
P(e1, e2 | X, I) = P(e1 | X, I) × P(e2 | X, I)
```

也就是：来自不同路径的消息必须携带条件独立的信息。

因此：

- **若图已正确表达共享来源、共享前提和命题同一性**，BP 会自然累积独立证据
- **若图把重复信息误画成多条独立路径**，BP 会自然地重复计数

概率论保证的是“在正确图上的一致推理”，不是“自动帮你发现图错了”。

### 2.2 真正需要区分的是三个对象

在分布式协作里，必须区分：

1. **Truth variable**：系统真正要判断真假的命题
2. **Package occurrence**：某个 package 中出现的一次具体陈述或论证产物
3. **Support path**：支撑这个命题的推理链 / 证据链

如果不区分这三者，系统就会把：

- “同一个命题的两次出现”
- “同一个命题的新证据”
- “同一个命题的旧论证改写”

错误地当成同一种东西处理。

## 3. 为什么 GitHub 生态特别容易产生 double counting

GitHub 协作有几个天然特征：

1. **晚到发现**：作者写 package 时通常不知道别人的 package 已经提出过同一命题。
2. **分布式发布**：不同仓库独立演化，不共享单一写时 identity。
3. **改写常见**：后来者可能是在重述、整理、抽象、细化或重新包装旧结论。
4. **共享来源隐蔽**：两个 package 可能都建立在同一数据集、同一实验平台、同一校准链或同一未显式写出的理论假设上。

因此，一个开放协作系统不能把“多 package 同向支持”默认解释为“独立证据”。

## 4. double counting 的真正来源

### 4.1 命题身份未统一

两个 package 中的 `A` 和 `B` 实际说的是同一个 proposition，但系统暂时把它们当成两个不同节点。

后果：

- 支持 `A` 的路径和支持 `B` 的路径在全局图里表现为两套并行结构
- 一旦后续再通过 `equivalence` 或相似性把它们联系起来，系统容易既保留两份 truth variable，又让它们相互增信

这会高估后验。

### 4.2 共享证据源未显式入图

即使两个 package 的结论确实指向同一个命题，支撑它们的路径也可能共享高风险上游因：

- 同一实验数据集
- 同一仪器校准
- 同一仿真模型
- 同一未声明的领域假设
- 同一旧 package 的核心结论

若这些共享来源不入图，BP 会把两条路径当成条件独立，从而重复计数。

### 4.3 论证修订被误当作新增证据

后来者可能不是在提供新证据，而是在：

- 精炼旧论证
- 改进表述
- 补全缺失前提
- 换一种 formalization

这类工作有价值，但它们通常不应自动变成新的独立 likelihood factor。

## 5. 系统必须能区分的四种情况

对任意两个晚到发现相关的 package 结论 `A`、`B`，系统至少要能区分：

### 5.1 Duplicate

`A` 与 `B` 其实是同一个 proposition 的两次出现，且它们背后的核心论据并不独立。

这是最典型的 double counting 风险。

### 5.2 Same Proposition, New Independent Evidence

`A` 与 `B` 说的是同一个 proposition，但 `B` 背后确实带来了新的、条件独立的 support path。

这是系统真正应该允许“证据累积”的场景。

### 5.3 Same Proposition, Dependent Restatement

`B` 看起来像新论证，实际上主要是在重写、转述或轻度重构 `A`。

它应当保留 provenance 价值，但不应被当成新的独立证据。

### 5.4 Refinement

`B` 不是 `A` 的 duplicate，而是：

- `A` 的特化
- `A` 的推广
- `A` 的条件化版本
- `A` 的更精确版本

这时不应做 identity merge，而应建立 refinement / specialization 关系。

## 6. 为什么“独立证据算子”不是核心答案

如果图已经正确，那么独立证据不需要单独发明一个核心 primitive：

- 多条真正独立的 support paths 最终汇入同一 truth variable
- BP 的标准 message product 就会自然累积它们

因此，系统设计的难点不是“如何编码独立证据”本身，而是：

1. 如何发现命题同一性
2. 如何发现共享来源
3. 如何把这些发现转化为新的、可审查的公开知识制品
4. 如何在这些制品被接受后，重写全局图，避免重复计数

## 7. 关键约束：修正动作本身必须通过新 package 完成

在 Gaia 的治理模型里，不能让 LKM 或某个后台服务私自修改全局知识图。

正确原则应是：

> 当某人发现 `A` 和 `B` 其实是同一个命题，或发现二者存在重要依赖 / refinement 关系时，这个“对齐 / 合并 / 修正”动作本身必须作为一个新的 Gaia package 提交，经 review / rebuttal / 接受后，才能成为 LKM 采纳的规范来源。

这条约束的意义非常大：

- **公开性**：合并不是后台黑盒操作，而是公开论证
- **可 rebuttal**：原作者或他人可以反驳“你说它们是同一个命题”的判断
- **可版本化**：对齐判断本身可以迭代
- **可追溯**：LKM 的全局图变更始终有 package-level provenance

因此：

- **package 是规范来源**
- **LKM materialization 是接受后的派生执行**

## 8. 这类“修正 package”应当表达什么

当贡献者发现 `A` 与 `B` 相关时，他不应直接修改全局图，而应提交一个新的 package。这个 package 至少要表达三类内容：

### 8.1 引用对象

它必须能够明确引用外部 package 中的节点或策略：

- `A_ref`
- `B_ref`
- 相关 support path / strategy 引用

没有外部引用能力，就无法把“晚到发现的关系”变成正式知识。

### 8.2 关系判断

它必须给出一个明确的调查结论，例如：

- `duplicate`
- `same proposition with independent evidence`
- `dependent restatement`
- `refinement`
- `contradiction`
- `unresolved`

这不是 metadata 小标签，而是 package 内需要被 review 的核心主张。

### 8.3 支持审查

它必须解释：

- 为什么 `A` 与 `B` 说的是同一件事，或不是
- 它们的 support path 是否共享高风险前提
- 若共享，哪些节点应当显式补入图中

这个 package 的价值不是“再加一个 factor”，而是**修正全局图的形状**。

## 9. 接受这类 package 后，LKM 应做什么

一旦这个 alignment / curation package 被接受，LKM 可以做确定性的 materialization：

1. 创建或确认 canonical proposition
2. 建立 package occurrence 到 canonical proposition 的映射
3. 将原本汇入多个重复节点的 support path 重写到 canonical proposition
4. 根据 package 中接受的独立性判断，决定这些路径是：
   - 可独立累积
   - 需要共享上游来源
   - 需要暂停参数并重新审查
5. 重新运行 parameterization / inference

注意：

- **被接受的 package 决定“应该如何改图”**
- **LKM 只负责执行这次公开决议**

## 10. 由此推导出的设计要求

### 10.1 Core IR 的重点不是发明更多“独立性算子”

Core IR 更应关注：

- package-local 结构表达
- 外部节点 / 策略引用能力
- provenance 边界
- reviewable alignment package 的可表达性

### 10.2 系统必须支持“occurrence”和“canonical proposition”的区分

这是 double counting 问题的核心抽象。

同一个 proposition 可以有多个 package occurrence。  
系统不能把 occurrence 的数量直接等同于独立 evidence 的数量。

### 10.3 系统必须支持“论证修订”与“新增证据”的区分

否则后来的 formalization、清理、重写都会被误计入新证据。

### 10.4 修正应当是 package-native，而不是 admin-native

alignment、duplicate 调查、refinement 判定都应当优先表现为 package 提交，而不是后台特权操作。

这是 Gaia 与传统“中心数据库后台纠错”系统的根本区别。

## 11. 反模式

以下设计方向容易掩盖或恶化 double counting：

### 11.1 把 duplicate 问题伪装成新的推理节点

如果 `A` 和 `B` 本来是同一个 proposition，却通过：

- `equivalence(A, B)`
- 再加一个新的“binding 结论 C”

来处理，那么系统实际上保留了多个 truth variable，只是试图用额外因子把它们绑起来。

这更像概率 patch，而不是身份修正。

### 11.2 把“独立证据”做成作者自报的核心语义

“是否独立”本身是需要审查的结论，不应由作者单方面声明后直接进入推理。

### 11.3 让 LKM 私自改图而不经过 package

这会破坏 Gaia 的 package-first 治理模型，也会削弱可审计性。

## 12. 最短结论

Gaia 在开放 GitHub 协作中的核心难题不是：

> 如何表示 independent evidence

而是：

> 如何在 package-first 的分布式生态里，持续发现、审查并修正“同一命题被重复出现、同一证据源被重复使用、旧论证被误当作新证据”这些情况，从而构造一个不会 double count 的全局图。

更简洁地说：

- **独立证据的累积**是概率推理在正确图上的自然结果
- **double counting 的避免**才是知识协作系统真正困难的部分

## 13. Open Questions

1. alignment / curation package 的最小 profile 应是什么：`investigation` 还是单独 profile？
2. 外部 claim / strategy 引用的最小 IR contract 应是什么？
3. duplicate 与 refinement 的边界由谁最终裁决：reviewer、editor、还是多 reviewer 合议？
4. 当 alignment package 被接受后，LKM 的 materialization 是否需要“暂停参数并强制重新 review”作为默认安全动作？
5. 对“同一 proposition 但部分证据独立、部分证据共享”的混合情况，最小可接受的 graph rewrite 规则是什么？
