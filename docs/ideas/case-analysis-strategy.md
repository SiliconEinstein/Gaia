# Case Analysis 论证策略 — 分情况讨论

> **Status:** Idea — 需要析取（∨）原语支持，暂不纳入 v1 实现范围

## 动机

分情况讨论（proof by cases / case analysis）是数学证明中最常用的技术之一：将问题按穷尽的情形划分，在每个情形下分别证明结论成立。

典型场景："证明 n²+n 对所有自然数都是偶数"——分 n 为奇数和偶数两种情形，各自推出结论。

当前 9 种推理策略中，**Elimination**（排除法，见 [elimination-strategy.md](elimination-strategy.md)）也依赖穷尽的情形划分，但两者的证明机制不同：

| | Case Analysis | Elimination |
|---|---|---|
| **方法** | 在每个 case 下**正面推出** C | **否定**除 survivor 外的所有 case |
| **结论** | 外部命题 C（不是 case 之一） | case 之一 Hⱼ（survivor） |
| **性质** | 建设性（constructive） | 破坏性（destructive） |
| **依赖** | 析取 ∨ | 否定 negation |
| **典型领域** | 数学（极常用） | 科学（极常用） |

两者共享"穷尽性前提"，但因子图展开结构完全不同，不存在包含关系。

## 核心结构

Case Analysis 的三要素：

1. **穷尽划分（exhaustive partition）**：A₁∨A₂∨...∨Aₖ 成立
2. **逐 case 论证**：对每个 Aᵢ，都能推出 C
3. **结论**：C

### Theory 层：推理策略

Case Analysis 是第九种推理策略，归入**确定性**类别。

**类型：** 确定性（当穷尽划分和各 case 的蕴含都是 p=1 时，结论 p=1）。

**粗因子图：** [A₁∨...∨Aₖ]→C（穷尽情形划分蕴含 C）

**细因子图展开：**
- 析取 A₁∨A₂∨...∨Aₖ (p=1)（穷尽性声明）
- 蕴含 A₁→C (p=1)
- 蕴含 A₂→C (p=1)
- ...
- 蕴含 Aₖ→C (p=1)

**BP 路径：** 析取因子确保至少一个 Aᵢ 具有高 belief。每条蕴含 Aᵢ→C 的前向消息将 Aᵢ 的 belief 传递给 C。由于析取保证至少一条路径活跃，C 获得高 belief。

**注意：** Case Analysis 使用析取（∨）原语。当前 [03-propositional-operators.md](../foundations/theory/03-propositional-operators.md) 已定义析取为四种逻辑原语之一，但 graph-ir 尚未有对应的 reasoning_type。

### 与 Elimination 的因子图对比

**Case Analysis：** 析取 + 蕴含

```
A₁∨A₂∨A₃ (析取, p=1)
    ├── A₁ → C (蕴含, p=1)
    ├── A₂ → C (蕴含, p=1)
    └── A₃ → C (蕴含, p=1)
∴ C
```

**Elimination：** 矛盾 + 否定 + 蕴含

```
contradict(H₁, E₁)
contradict(H₂, E₂)
negation(H₁, ¬H₁)
negation(H₂, ¬H₂)
蕴含 [¬H₁, ¬H₂] → H₃ (p=1)
∴ H₃
```

逻辑上 `[¬H₁∧¬H₂]→H₃` 等价于 `H₁∨H₂∨H₃`（De Morgan），穷尽性表达方式不同但等价。关键区别在于证明路径：Case Analysis 在每个 case 下建设性地推出 C；Elimination 破坏性地排除其他 case。

### Graph IR 层

#### 穷尽划分的表示

穷尽划分 A₁∨A₂∨...∨Aₖ 需要一个**析取因子**。当前 graph-ir 的 reasoning_type 枚举中没有析取类型。两种方案：

**方案 A：新增 `disjunction` reasoning_type**

```
FactorNode:
  reasoning_type: disjunction
  premises: [A₁, A₂, ..., Aₖ]
  conclusion: None   # 与 equivalent/contradict 相同，无方向性
```

potential 函数：至少一个 premise 为真，即 ¬(A₁=0 ∧ A₂=0 ∧ ... ∧ Aₖ=0)。

**方案 B：编码为辅助节点 + 蕴含**

```
KnowledgeNode: D = "A₁或A₂或...或Aₖ之一成立"  (claim, belief 高)
FactorNode: entailment, premises: [D, A₁], conclusion: C
FactorNode: entailment, premises: [D, A₂], conclusion: C
...
```

方案 B 不改 graph-ir，但丢失了析取的结构语义。

#### Case Analysis 的整体 FactorNode

```
FactorNode:
  reasoning_type: case_analysis     # 或复用 entailment
  premises: [A₁, A₂, ..., Aₖ]     # 各情形
  conclusion: C
  metadata:
    exhaustive: true                 # 标记穷尽性
```

编译器展开为细因子图后，此粗因子被替换为析取 + k 条蕴含。

### Gaia Lang 层

#### 语法草案

```typst
#claim[n²+n 对所有自然数 n 都是偶数] <thm.even>

#claim[n 是偶数] <case.even>
#claim[n 是奇数] <case.odd>

#claim[
  若 n=2k，则 n²+n = 4k²+2k = 2(2k²+k)，是偶数
] <proof.even>

#claim[
  若 n=2k+1，则 n²+n = (2k+1)(2k+2) = 2(2k+1)(k+1)，是偶数
] <proof.odd>

#case-analysis(
  cases: (<case.even>, <case.odd>),
  conclusion: <thm.even>,
  proofs: (<proof.even>, <proof.odd>),
)[每个自然数要么是偶数要么是奇数（穷尽），
  两种情形下 n²+n 都是偶数]
```

#### 参数说明

- `cases:` — 穷尽的情形列表（claim label tuple）
- `conclusion:` — 待证结论（claim label）
- `proofs:` — 每个 case 下的论证（claim label tuple，与 cases 一一对应）
- Body — 穷尽性论证：为什么这些 case 覆盖了所有可能

#### 编译器行为

编译器将 `#case-analysis` 展开为：

```
1. 穷尽性（析取）：
   - disjunction(case.even, case.odd)  或等价表示

2. 逐 case 蕴含：
   - entailment: [case.even, proof.even] → thm.even (p=1)
   - entailment: [case.odd, proof.odd] → thm.even (p=1)
```

其中 `proof.even` 和 `proof.odd` 作为各 case 下的论证步骤，与对应 case 共同构成蕴含的前提。

## 例子：证明 n²+n 恒为偶数

### 原文

**命题：** 对所有自然数 n，n²+n 是偶数。

**证明：** 分两种情形讨论。

*情形 1：n 为偶数。* 设 n=2k，则 n²+n = (2k)²+2k = 4k²+2k = 2(2k²+k)，是偶数。

*情形 2：n 为奇数。* 设 n=2k+1，则 n²+n = (2k+1)²+(2k+1) = (2k+1)(2k+2) = 2(2k+1)(k+1)，是偶数。

由于每个自然数要么是偶数要么是奇数，两种情形穷尽了所有可能，因此 n²+n 恒为偶数。■

### Gaia 形式化

#### Step 1：提取命题

| 节点 | 内容 | 类型 |
|------|------|------|
| **C** | n²+n 对所有自然数 n 都是偶数 | law（待证） |
| **A₁** | n 是偶数 | claim（情形 1） |
| **A₂** | n 是奇数 | claim（情形 2） |
| **P₁** | 若 n=2k，则 n²+n = 2(2k²+k)，是偶数 | claim（情形 1 的推导） |
| **P₂** | 若 n=2k+1，则 n²+n = 2(2k+1)(k+1)，是偶数 | claim（情形 2 的推导） |

#### Step 2：因子图

```
C (待证)
 ↑ case-analysis
 ├── A₁∨A₂ (析取, 穷尽: 奇偶性)
 ├── [A₁, P₁] → C (蕴含, p=1)
 └── [A₂, P₂] → C (蕴含, p=1)
```

#### Step 3：BP 分析

- A₁∨A₂ 的 belief 高（奇偶穷尽是基本数论事实）
- P₁ 的 belief 高（代数恒等式，直接验证）
- P₂ 的 belief 高（代数恒等式，直接验证）
- 两条蕴含分别从情形 1 和情形 2 支撑 C
- C 获得高 belief

如果有人质疑穷尽性（例如 n=0 是否算偶数？），析取因子的 belief 降低，C 的支撑相应减弱。如果有人质疑某个 case 的推导（例如 P₁ 的代数计算有误），对应的蕴含变弱，但另一条路径仍提供部分支撑。

### 与 Elimination 处理同一问题的对比

同样的情形划分（奇数/偶数），如果用 Elimination：

```
H₁: n²+n 不总是偶数（存在反例）
H₂: n²+n 总是偶数

"总是偶数"与"不总是偶数"穷尽了所有可能
证据排除 H₁ → survivor H₂
```

这虽然可行，但不自然——Elimination 适合"从多个竞争假说中筛选"的科学场景，不适合"分类讨论每种情况都成立"的数学场景。Case Analysis 更直接地表达了数学证明的结构。

## 穷尽性的关键性

与 Elimination 一样，Case Analysis 的有效性依赖于穷尽性声明 A₁∨...∨Aₖ 的正确性。

穷尽性的来源通常是：
- **数学结构**：奇偶性（每个整数要么奇要么偶）、正负零（每个实数满足 >0, <0, =0 之一）
- **定义穷举**：枚举一个有限集的所有元素
- **逻辑排中律**：A∨¬A（需要经典逻辑，直觉主义逻辑不接受）

穷尽性声明本身可以是一个需要论证的 claim（例如"每个自然数要么是偶数要么是奇数"），也可以是一个不证自明的 setting。在因子图中，它的 belief 直接影响结论的 belief。

## 扩展

### 多分支 Case Analysis

不限于两个 case。例如对整数 mod 3 讨论（三种情形），对有限群的阶讨论，等。语法自然扩展：

```typst
#case-analysis(
  cases: (<case.r0>, <case.r1>, <case.r2>),
  conclusion: <thm>,
  proofs: (<proof.r0>, <proof.r1>, <proof.r2>),
)[n mod 3 穷尽 {0,1,2} 三种情形]
```

### 嵌套 Case Analysis

某个 case 下的论证本身可以是另一个 case analysis。编译器递归展开即可。

### 不完全穷尽 Case Analysis

如果穷尽性 A₁∨...∨Aₖ 的 belief 不是 1（例如作者无法证明穷尽性），Case Analysis 退化为不确定推理（p<1）。这与 Elimination 中"穷尽性被质疑"的情况类似（见 [elimination-strategy.md](elimination-strategy.md)）。

## 依赖

- **析取原语（∨）的 Graph IR 支持** — theory 层已定义析取为四种逻辑原语之一（见 [03-propositional-operators.md](../foundations/theory/03-propositional-operators.md)），但 graph-ir 的 reasoning_type 枚举中尚无对应类型
- **gaia-lang 语法设计** — 需要 `#case-analysis` 策略语法

## 参考

- [../foundations/theory/04-reasoning-strategies.md](../foundations/theory/04-reasoning-strategies.md) §3 — 推理策略概览
- [../foundations/theory/03-propositional-operators.md](../foundations/theory/03-propositional-operators.md) — 析取算子定义
- [../foundations/theory/03-propositional-operators.md](../foundations/theory/03-propositional-operators.md) — 粗/细因子图
- [../foundations/graph-ir/graph-ir.md](../foundations/graph-ir/graph-ir.md) §2.2 — reasoning_type 定义
- [elimination-strategy.md](elimination-strategy.md) — 排除法（共享穷尽性前提的平行策略）
- [../specs/2026-03-25-gaia-lang-alignment-design.md](../specs/2026-03-25-gaia-lang-alignment-design.md) §4 — 当前论证策略设计
