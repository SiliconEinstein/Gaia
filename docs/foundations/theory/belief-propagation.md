# Belief Propagation

> **Status:** Current canonical

## 1. 因子图

factor graph（因子图）是一种二部图，包含两种节点：

- **variable node（变量节点）**：具有先验分布的未知量。对于二值变量：状态为真（1）或假（0）。
- **factor node（因子节点）**：变量之间的约束或关系。每个因子连接一组变量子集，编码它们之间的交互方式。

```
Variable nodes = propositions or unknown quantities
  prior  -> initial plausibility, in (epsilon, 1 - epsilon)
  belief -> posterior plausibility computed by BP

Factor nodes = constraints or reasoning links
  connects a subset of variables
  potential function encodes constraint semantics
```

所有变量的联合概率分解为：

```
P(x1, ..., xn | I) proportional to  prod_j phi_j(x_j) * prod_a psi_a(x_S_a)
```

其中 phi_j 是变量 j 的先验（一元因子），psi_a 是因子 a 在其连接变量子集 S_a 上的势函数。势不是概率——它们不需要归一化。只有比值有意义。

## 2. Sum-Product 消息传递

消息是二维向量 `[p(x=0), p(x=1)]`，始终归一化使得和为 1。

### 算法

```
Initialize: all messages = [0.5, 0.5] (uniform, MaxEnt)
            priors = {var_id: [1-prior, prior]}

Repeat (up to max_iterations):

  1. Compute all variable -> factor messages (exclude-self rule):
     msg(v -> f) = prior(v) * prod_{f' != f} msg(f' -> v)
     Then normalize.

  2. Compute all factor -> variable messages (marginalize):
     msg(f -> v) = sum_{other vars} potential(assignment) * prod_{v' != v} msg(v' -> f)
     Then normalize.

  3. Damp and normalize:
     msg = alpha * new_msg + (1 - alpha) * old_msg
     Default alpha = 0.5.

  4. Compute beliefs:
     b(v) = normalize(prior(v) * prod_f msg(f -> v))
     Output belief = b(v)[1], i.e., p(x=1).

  5. Check convergence:
     If max |new_belief - old_belief| < threshold: stop.
```

关键设计要点：

- **双向消息**：变量到因子和因子到变量。反向抑制（modus tollens，否定后件式）自然产生。
- **排除自身规则（exclude-self rule）**：当变量 v 向因子 f 发送消息时，排除 f 自身的传入消息。这防止了循环自增强。
- **同步调度**：所有新消息都从旧消息计算，然后同时交换。因子排序不影响结果。
- **二维向量归一化**：消息始终和为 1，防止长链中的数值衰减。

### 与 Jaynes 规则的对应关系

| BP 操作 | Jaynes 规则 |
|---|---|
| 联合 = 势与先验的乘积 | 乘法规则 |
| 消息归一化 [p(0) + p(1) = 1] | 加法规则 |
| belief = 先验 * 因子到变量消息的乘积 | Bayes 定理（后验正比于先验 * 似然） |
| 变量到因子消息（排除自身） | 排除当前因子的背景信息 P(H\|X) |
| 因子到变量消息（边缘化） | 对其他变量边缘化后的似然 P(D\|HX) |

在树结构图上，BP 是精确的。在有环图上，它是一种近似。

## 3. Loopy BP 与收敛性

现实世界的因子图常包含环。loopy BP 通过迭代消息传递直到信念稳定来处理这种情况。

**阻尼（damping）** 防止在有环图上的振荡：

```
msg_new = alpha * computed_msg + (1 - alpha) * msg_old
```

当 alpha = 0.5（默认值）时，每次更新向新值移动一半。阻尼以收敛速度换取稳定性。

loopy BP 最小化 **Bethe 自由能**，这是真实自由能的变分近似。在稀疏图上，这种近似通常较好。系统始终产生一组信念——不存在"不可满足"的状态。不完整的信息产生不确定的信念，而非系统失败。

**Cromwell 规则**在两处强制执行：

1. **在构造时**：所有先验和条件概率都钳制在 [epsilon, 1-epsilon]，其中 epsilon = 10^-3。
2. **在势函数中**：noisy-AND 因子中的泄漏参数本身就是 Cromwell 下界，确保没有状态组合具有零势。

这防止了零概率阻断所有未来证据的退化更新。

关于 Gaia 的特定因子类型势函数，参见 `../bp/potentials.md`。

## 4. 构造性操作 vs BP 算子

以下区分是强制性的：

### 4.1 图构造/研究操作

这些操作创建或提议新的知识结构：

- 抽象（abstraction）
- 泛化（generalization）
- 隐含前提发现（hidden premise discovery）
- 独立证据审计（independent evidence audit）

它们**不是**自动的 BP 边类型。它们属于审查/策展流程——其结果可能最终产生新的 BP 因子，但操作本身不直接参与信念传播。

### 4.2 BP 算子族

这些算子决定了图被接受后信念更新如何传播：

- entailment（蕴含）
- induction（归纳）
- abduction（溯因）
- equivalent（等价）
- contradict（矛盾）

每种算子对应不同的势函数。Jaynes 式弱三段论是这些 BP 算子上的合约，不是新的语言声明。

算子类型的完整语义定义见 [scientific-ontology.md](scientific-ontology.md) §5。

## 5. 什么进入 BP

### 5.1 承载 BP 的对象

以下对象在审查/接受后可以进入 BP：

- Claim（封闭断言——唯一的 BP 承载类别，包括其所有结构特化：Observation、Measurement、RegimeAssumption 等）
- 已接受的 equivalent / contradict 关系

### 5.2 非 BP 对象

以下对象**不**直接进入 BP：

- Template
- Background
- Question
- infer 阶段的推理链接（尚未经过审查确认具体类型）
- candidate 阶段的推理链接（尚未经过充分验证）
- 审查发现
- 策展建议
- 循环审计制品
- 独立证据审计报告

## 参考文献

- Jaynes, E.T. *Probability Theory: The Logic of Science* (2003)
- Pearl, J. *Probabilistic Reasoning in Intelligent Systems* (1988)
- Yedidia, Freeman, Weiss. "Understanding Belief Propagation and its Generalizations" (2003)
