# Independent Evidence 与条件独立性

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-19 |
| 状态 | **Draft — foundation design** |
| 关联文档 | [inference-theory.md](inference-theory.md) — BP 算法理论, [../bp-on-graph-ir.md](../bp-on-graph-ir.md) — BP 在 Graph IR 上的运行, [../graph-ir.md](../graph-ir.md) — Graph IR 结构定义 |

---

## 1. 问题

当两条独立推导路径得出同一结论时，这一"殊途同归"在认识论上具有显著意义——它应当提升该结论的可信度。本文档讨论 Gaia 中的独立证据审查问题（historically discussed as corroboration）、其与 BP 的关系、条件独立性的判定标准、以及 canonicalization / curation 阶段应如何处理这类问题。

核心论点：**Independent evidence review 不是语言 relation type，不是 BP 的 constraint factor，而是 canonicalization / curation 阶段的独立性审查 artifact。** Belief 的提升来自合并后图结构的自然 BP 传播，不需要额外的 factor 类型。

## 2. BP 理论基础

### 2.1 Message 乘积的前提

Factor graph 上 BP 计算节点 X 的 belief：

```
b(X=T) ∝ π(X) × ∏_{f ∈ neighbors(X)} μ_{f→X}(T)
```

其中 μ_{f→X} 是 factor f 发给 X 的 message。**这个乘积成立的前提**是各 factor 传来的 message 携带条件独立的信息：

```
P(e₁, e₂ | X) = P(e₁ | X) × P(e₂ | X)
```

即两条 evidence path 在给定 X 的条件下独立。若此条件不满足，message 乘积会高估 belief——这就是 evidence double-counting。

### 2.2 Canonicalization 后的图结构

设两个 package 分别推导出同一结论：

```
Package A:  A₁ → A₂ → ... → X_A
Package B:  B₁ → B₂ → ... → X_B
```

Canonicalization 确认 X_A ≡ X_B，合并为单一节点 X。合并后 X 有两条 factor path 汇入：

```
b(X=T) ∝ π(X) × μ_{pathA→X}(T) × μ_{pathB→X}(T)
```

**如果两条路径条件独立**，BP 自然给出正确的、更高的 belief——无需任何额外 factor。如果路径**不条件独立**，这个乘积会 double-count 共享的 evidence。

### 2.3 隐藏共因导致条件独立性失效

如果存在隐藏变量 H（不在 graph 中），同时是 Path A 和 Path B 的上游因：

```
        H (hidden)
       / \
      v   v
  Path A   Path B
      \   /
       v v
        X
```

真实的后验应该对 H 求和：

```
P(X=T | e₁, e₂) = Σ_H P(X=T | H) · P(H | e₁, e₂)
```

但 BP 在不知道 H 的情况下直接计算 `P(e₁|X) × P(e₂|X)`。两个结果近似相等**当且仅当**：

- `P(H=T) ≈ 1`（H 几乎确定为真，marginalization trivial）
- 或 H 与 X 因果无关

## 3. Independent Evidence Review 的精确语义

### 3.1 定义

Independent evidence review 处理的是一个认识论声明：

> 节点 X 经由两条（或多条）推理路径得出，且这些路径的高危前提互不重叠。因此 canonicalization 合并 X 后，BP 可以安全地从多路径汇聚中获得 belief 提升。

Independent evidence review **不是**语言节点，也不是 BP 的 factor 类型。它是：

1. **Curation / canonicalization 审查对象**：判断多路径支持是否真的独立
2. **独立性论证文档**：记录为什么高危前提不重叠，或哪些地方需要补图
3. **Premise completeness audit 的触发器**：审查过程会发现并补全隐藏前提

### 3.2 与现有 constraint factor 的区分

| | mutex_constraint | equiv_constraint | independent_evidence_review |
|---|---|---|---|
| 本质 | BP factor（惩罚 T,T） | BP factor（奖励一致） | Curation / review artifact |
| Graph IR 表现 | FactorNode | FactorNode | 不生成 FactorNode；只记录审查结果 |
| Belief 影响 | 通过 factor potential | 通过 factor potential | 通过图结构（合并后多路径 BP） |
| 触发方式 | 作者声明或系统探测 | 作者声明或系统探测 | Agent 审查确认 |

### 3.3 为什么独立证据不需要 constraint factor

Canonicalization 合并等价节点后，BP 通过标准 message passing 自动处理多路径汇聚。额外的 constraint factor 会导致**双重计算**——图结构已经编码了多路径信息，再加一个 factor 等于把同一信息数了两遍。

## 4. Agent 审查：条件独立性判定

### 4.1 判定标准

Agent 需要确认的精确问题：

> **是否存在隐藏变量 H，同时满足：**
> 1. H 是 Path A 和 Path B 的共同上游因（causal ancestor）
> 2. H 的 prior 显著低于 1（genuinely uncertain）
> 3. H 的真假会实质性影响两条路径的结论

如果这样的 H 不存在 → 条件独立成立 → canonicalize + BP 安全。

如果这样的 H 存在 → **把 H 显式加入 graph** → BP 通过共享的 H 正确处理依赖关系。

### 4.2 隐藏前提的分类与风险

| 类别 | 例子 | 通常的 prior | double-counting 风险 |
|------|------|-------------|-------------------|
| 逻辑基础 | 经典逻辑有效、数学一致 | ≈ 1 | 可忽略 |
| 方法论 | 两条路用了同一种数学技巧 | 较高但非确定 | 低–中 |
| 物理假设 | 物理定律在所有地点/时间普适 | 高 | 低 |
| 经验数据 | 两条路共享同一数据源或校准 | 取决于数据质量 | 中–高 |
| 领域假设 | 某个未声明的物理定律被两条路都隐含使用 | 变化大 | **高危** |

核心原则：**我们只显式提取高危前提（prior 不接近 1 的前提）。** 独立证据审查关心的是高危前提的独立性，不是所有前提的独立性。高置信度的背景知识（逻辑、基本数学）即使被 double-count，对 belief 的影响也在 ε 量级内。

### 4.3 交叉审查流程（Bidirectional Premise Completeness Audit）

Independent evidence review 的核心价值不仅是判定独立性，更是**发现隐藏前提**。一条路的显式前提可以作为 checklist，探测另一条路的隐含依赖。

```
Step 1: 收集两条路的显式前提集合
        explicit_A = ancestors(X via Path A)
        explicit_B = ancestors(X via Path B)

Step 2: 结构独立性检查（自动化）
        shared = explicit_A ∩ explicit_B
        → 如果 shared ≠ ∅：路径不结构独立，报告共享节点

Step 3: 交叉审查（Agent 核心工作）
        for each P in explicit_B:
            "Path A 是否隐含依赖 P？"
            → 如果是：把 P 加入 Path A 的 graph（补全）
        for each P in explicit_A:
            "Path B 是否隐含依赖 P？"
            → 如果是：把 P 加入 Path B 的 graph（补全）

Step 4: 在补全后的 graph 上重新检查结构独立性
        → 如果独立：canonicalize + BP 安全
        → 如果不独立：graph 已经正确了，BP 会通过共享节点正确处理

Step 5: 无论独立性审查是否通过，graph 都变得更完整
```

**关键洞察**：即使独立证据最终被否定（路径不独立），审查过程仍然有价值——它发现了之前遗漏的前提，使 graph 更完整，使 BP 结果更准确。

### 4.4 三种场景的处理

| 场景 | 能否发现？ | 处理方式 |
|------|-----------|---------|
| H 在 Path A 隐藏，Path B 显式 | ✅ 交叉审查 | 补全 Path A 的 graph，BP 正确处理 |
| H 在 Path A 显式，Path B 隐藏 | ✅ 交叉审查 | 补全 Path B 的 graph，BP 正确处理 |
| H 在两条路都隐藏 | ❌ 交叉审查无法发现 | 靠领域 checklist + ε 安全余量 |

第三种场景是根本性限制。缓解手段：

1. **领域知识 checklist**：针对特定领域维护常见隐含假设清单，Agent 审查时逐项排查
2. **对抗性审查**：让第二个 Agent 专门尝试找共享隐藏前提
3. **ε 安全余量**：noisy-AND 的 ε 参数（见 [inference-theory.md](inference-theory.md) §2.2）本质上编码"即使所有已知前提成立，结论仍有 ε 概率为假"——这为未知隐藏前提提供了系统性的安全余量

## 5. Canonicalization / Curation 中的独立证据处理

### 5.1 整体流程

```
1. 系统自动探测潜在等价节点
   （语义相似度、同一物理量的不同表述）
        ↓
2. 生成 open question 进入 review 队列
   （不自动合并，不自动修改 belief）
        ↓
3. Agent 调查
   a. 确认语义等价性（是否真的是同一 claim）
   b. 执行交叉审查（bidirectional premise completeness audit）
   c. 补全发现的隐藏前提
   d. 在补全后的 graph 上判定条件独立性
        ↓
4. Agent 输出独立证据审查报告
   （存为 review artifact / annotation，而非 relation 或 factor）
        ↓
5. Canonicalize 合并节点
        ↓
6. 标准 BP 在更完整的 graph 上运行
   → belief 提升是图结构的自然结果
```

### 5.2 设计原则

1. **机器提出假说，Agent 论证，人类审查，BP 计算**——没有任何 belief 变化是自动发生的
2. **解决方案永远是补全 graph，不是给 BP 加 patch**——BP on correct graph = correct answer
3. **Independent evidence review 是 graph 补全的最佳时机**——交叉审查自然暴露隐藏前提
4. **ε 是最后的安全网**——对无法发现的隐藏共因，noisy-AND 的 leak probability 提供系统性保护

## 6. 在当前 Gaia 中的落点

Gaia Language 不提供 `corroboration` relation，也不提供对应 declaration。作者只需把不同支持路径写成普通 `claim(from:)` 推理链。系统如果要讨论“多路径支持是否真的独立、是否可以安全叠加”，应该在 canonicalization / curation 阶段基于这些路径生成审查 artifact，而不是在 source 中引入新的 relation type 或 factor type。

当前约束是：
- **不生成 `corroboration` FactorNode**
- **不生成 `corroboration` relation node**
- **不为它单独设计 BP potential**
- **belief 提升只来自合并后的真实多路径结构**

## 7. Open Questions

1. **N-ary independent evidence**：三条以上路径汇聚时，是否需要验证所有路径 pairwise 独立，还是全局联合独立？
2. **Partial independence**：如果两条路径共享部分前提但非全部，如何量化独立证据的强度折扣？
3. **Domain checklist 标准化**：是否应该为每个学科领域维护一份标准的"常见隐含假设"清单？
4. **自动语义相似度**：用什么模型/方法自动探测跨 package 的潜在等价节点？
