# 数学归纳法 — 确定性归纳策略

> **Status:** Idea — 依赖 template 机制，暂不纳入 v1 实现范围

## 动机

当前系统的 induction 策略（见 [04-reasoning-strategies.md](../foundations/theory/04-reasoning-strategies.md) §3.3）是**经验归纳**——从有限实例推断一般规律，本质上不确定（p<1）。但数学归纳法（mathematical induction）是一种**确定性**推理：基础情形 + 归纳步骤 → 全称命题，p=1。

两者虽然都叫"归纳"，但在因子图上结构完全不同：

| | 经验归纳 | 数学归纳 |
|---|---|---|
| **确信来源** | 证据积累（实例越多越可信） | 论证结构（两条前提即可证明） |
| **确定性** | p < 1，渐近趋向 1 | p = 1，演绎确定 |
| **反例处理** | 反例削弱一般规律的 belief | 不存在反例（若存在则归纳步骤有误） |
| **因子数量** | 随实例数 n 增长 | 固定（不依赖实例数） |

数学归纳法在形式化数学论证中广泛使用。如果 Gaia 要覆盖数学领域的知识建模，需要支持这一推理模式。

## 核心结构

数学归纳法的三要素：

1. **基础情形（base case）**：P(0) 成立
2. **归纳步骤（inductive step）**：∀n. P(n) → P(n+1)
3. **结论**：∀n. P(n)

### Theory 层：推理策略

数学归纳法是第八种推理策略，归入**确定性**类别（与 deduction 相同）。

**粗因子图：** [base, step]→T（base 和 step 为前提，T 为 template）

**细因子图展开：**
- 蕴含 base→T(0) (p=1)（基础情形验证 template 的第 0 个实例）
- 蕴含 [T(n), step]→T(n+1) (p=1)（归纳步骤：已知第 n 个实例 + 步骤声明 → 第 n+1 个实例）
- 归纳公理：base + step → T (p=1)（template 本身获得 belief=1）

**关键：** 归纳公理是一条**元级蕴含**——它的结论不是一个 claim，而是一个 template。这意味着 template 节点的 belief 被提升到 1，等价于"对所有 n，P(n) 成立"。

### 与经验归纳的因子图对比

**经验归纳**（现有 induction 策略）：

```
B (一般规律)
 ├─ ent(p=1) → A₁ ≡ O₁✓     多个实例的反向消息
 ├─ ent(p=1) → A₂ ≡ O₂✓     渐进提升 B 的 belief
 └─ ent(p=1) → Aₙ ≡ Oₙ✓     n 越大 belief 越高，但 < 1
```

**数学归纳**：

```
T: P(n) [template]
 ↑ mathematical-induction (p=1)
 ├── P(0) [claim, 基础情形]
 └── "∀n. P(n)→P(n+1)" [claim, 归纳步骤]
```

两条前提确定性地证明 template，不需要枚举实例。

### BP 行为

数学归纳因子的 potential 函数是确定性的（与 deduction 相同）：

| base belief | step belief | T belief |
|:-----------:|:-----------:|:--------:|
| 1 | 1 | **1** |
| 1 | 0 | 0 |
| 0 | 1 | 0 |
| 0 | 0 | 0 |

等价于合取蕴含 (base ∧ step) → T (p=1)。

**前向消息：** base 和 step 都具有高 belief 时，T 获得高 belief（归纳证明成立）。

**反向消息（C1 弱三段论）：** 如果 T 的某个实例被质疑（T(k) belief 降低），反向消息压低 step 的 belief——归纳步骤本身存在问题。这对应数学中"找到归纳步骤的漏洞"。

### Graph IR 层

#### 方案 A：复用 entailment

不引入新的 reasoning_type。将数学归纳视为一种特殊的 entailment 模式：

```
FactorNode:
  reasoning_type: entailment
  premises: [base_case_claim, inductive_step_claim]
  conclusion: template_node
```

优点：不需要修改 graph-ir 的 reasoning_type 枚举。

缺点：与普通 entailment 混淆。结论是 template 而非 claim，这在当前不变量（§2.2 不变量 5）中是特殊情况——当前 template 只能作为 entailment 的 premise（instantiation 场景），而非 conclusion。

#### 方案 B：新增 reasoning_type

```
reasoning_type: entailment | induction | abduction
               | equivalent | contradict
               | mathematical_induction    # 新增
```

```
FactorNode:
  reasoning_type: mathematical_induction
  premises: [base_case_claim, inductive_step_claim]
  conclusion: template_node
```

优点：语义清晰，与经验归纳区分明确。

缺点：增加 reasoning_type 枚举，需要 graph-ir 变更（protected layer）。

#### 不变量变更

无论哪种方案，都需要放宽不变量 5：

> 当前：`type=template` 的节点只能作为 entailment factor 的 premise（instantiation 场景）
>
> 修改为：`type=template` 的节点可作为 premise（instantiation）或 conclusion（mathematical_induction）

#### 归纳步骤的表示

归纳步骤 "∀n. P(n) → P(n+1)" 是一个**关于 template 实例间蕴含关系的元级断言**。它可以表示为：

- 一个普通的 claim 节点，其 content 为自然语言描述（如 "若命题对 n 成立，则对 n+1 也成立"）
- 关联到 template 节点的元数据中，记录它是哪个 template 的归纳步骤

这不需要 graph-ir 结构变更——claim 本身足以承载这一信息。归纳步骤的**正确性**（它是否真的被证明了）体现在它的 belief 值上。

### Gaia Lang 层

#### 语法草案

```typst
// 声明 template
#claim(kind: "law")[对所有自然数 n，1+2+...+n = n(n+1)/2] <sum.formula>

// 声明基础情形
#claim(kind: "observation")[当 n=1 时，1 = 1×2/2 成立] <sum.base>

// 声明归纳步骤
#claim[
  若 1+2+...+k = k(k+1)/2 成立，
  则 1+2+...+k+(k+1) = k(k+1)/2 + (k+1) = (k+1)(k+2)/2，
  即对 k+1 也成立
] <sum.step>

// 数学归纳
#mathematical-induction(
  law: <sum.formula>,
  base: <sum.base>,
  step: <sum.step>,
)[基础情形直接验证；归纳步骤通过代数恒等式证明]
```

#### 参数说明

- `law:` — 待证明的全称命题（claim label，通常 kind="law"）
- `base:` — 基础情形（claim label）
- `step:` — 归纳步骤（claim label）
- Body — 论证说明

#### 编译器行为

编译器将 `#mathematical-induction` 展开为：

```
KnowledgeNode: <sum.formula>  (type: claim, kind: law)
KnowledgeNode: <sum.base>     (type: claim, kind: observation)
KnowledgeNode: <sum.step>     (type: claim)
FactorNode:
  reasoning_type: mathematical_induction  (或 entailment)
  premises: [<sum.base>, <sum.step>]
  conclusion: <sum.formula>
  stage: initial
```

## 例子：自然数求和公式

### 原文

**命题：** 对所有自然数 n ≥ 1，有 $1 + 2 + \cdots + n = \frac{n(n+1)}{2}$。

**证明：**

*基础情形：* 当 n=1 时，左边 = 1，右边 = 1×2/2 = 1，等式成立。

*归纳步骤：* 假设对某个 k ≥ 1，等式 $1+2+\cdots+k = \frac{k(k+1)}{2}$ 成立。则：

$$1 + 2 + \cdots + k + (k+1) = \frac{k(k+1)}{2} + (k+1) = \frac{(k+1)(k+2)}{2}$$

即对 k+1 也成立。

*结论：* 由数学归纳法，命题对所有 n ≥ 1 成立。■

### Gaia 形式化

#### Step 1：提取命题

| 节点 | 内容 | 类型 |
|------|------|------|
| **S** | 1+2+...+n = n(n+1)/2 对所有自然数 n ≥ 1 成立 | law（待证） |
| **B** | 当 n=1 时，1 = 1×2/2 成立 | observation（基础情形） |
| **I** | 若对 k 成立，则 1+2+...+k+(k+1) = k(k+1)/2+(k+1) = (k+1)(k+2)/2，对 k+1 也成立 | claim（归纳步骤） |

#### Step 2：因子图

```
S (law, 待证)
 ↑ mathematical-induction (p=1)
 ├── B (基础情形, belief=1, 直接验证)
 └── I (归纳步骤, belief=1, 代数恒等式)
```

因子图非常简单——一个因子、两个前提、一个结论。B 和 I 的 belief 都高（直接验证/代数推导），因此 S 的 belief 被提升到 1。

#### Step 3：BP 分析

这个例子中没有 weakpoint——B 和 I 都是确定性的。因此粗因子图即为细因子图，无需进一步展开。

如果有人质疑归纳步骤 I（例如代数推导有误），I 的 belief 降低，mathematical-induction 因子的反向消息使 S 的 belief 相应降低。这正确反映了"归纳步骤有漏洞则结论不可靠"的逻辑。

### 与经验归纳的对比

同一个公式 S，如果用经验归纳而非数学归纳：

```
S (law)
 ├─ ent(p=1) → P₁ (n=1时成立) ≡ O₁✓ (验证 1=1)
 ├─ ent(p=1) → P₂ (n=2时成立) ≡ O₂✓ (验证 1+2=3)
 ├─ ent(p=1) → P₃ (n=3时成立) ≡ O₃✓ (验证 1+2+3=6)
 └─ ...
```

经验归纳需要枚举实例，每个实例贡献一条反向消息。即使验证了 1000 个实例，S 的 belief 也不会达到 1（可能存在反例）。数学归纳只需两条前提就达到 belief=1——这正是数学证明比经验验证更强的根本原因。

## 扩展

### 强归纳（Strong Induction）

归纳步骤从"P(n)→P(n+1)"改为"P(0)∧P(1)∧...∧P(n)→P(n+1)"——假设所有 ≤n 的情形都成立。

在因子图上，强归纳和普通归纳的外部结构相同（base + step → law），区别仅在于 step 的内容描述。因子图不需要额外结构——step 是一个 claim，其内容表达了更强的归纳假设。

### 结构归纳（Structural Induction）

对递归数据结构（树、列表、表达式等）的归纳。base case 对应基础构造子，inductive step 对应递归构造子。

同样复用 mathematical-induction 因子——template 的参数从自然数 n 变为结构类型。

### 超穷归纳（Transfinite Induction）

对序数的归纳，包含极限步骤。理论上可用同一框架表示，但 Gaia 目前应该不需要。

## 依赖

- **template 机制**（见 [template-mechanism.md](template-mechanism.md)）— 数学归纳的结论是 template 节点，需要 template 参与 BP 的机制
- **graph-ir 变更**（如果采用方案 B）— 新增 reasoning_type，放宽不变量 5
- **gaia-lang 语法设计** — 需要 `#mathematical-induction` 策略语法

## 参考

- [../foundations/theory/04-reasoning-strategies.md](../foundations/theory/04-reasoning-strategies.md) §3.1, §3.3 — deduction 和 induction 策略
- [../foundations/theory/03-propositional-operators.md](../foundations/theory/03-propositional-operators.md) — 逻辑算子定义
- [../foundations/theory/03-propositional-operators.md](../foundations/theory/03-propositional-operators.md) — 粗/细因子图
- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §1.2, §2.2 — template 类型和 reasoning_type 定义
- [../foundations/gaia-lang/knowledge-types.md](../foundations/gaia-lang/knowledge-types.md) — Gaia Lang 知识类型
- [template-mechanism.md](template-mechanism.md) — template 机制设计
