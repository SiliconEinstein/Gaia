# 语言规范

> **Status:** Target design
>
> **对齐基准：** `docs/specs/2026-03-25-gaia-lang-alignment-design.md`

本文档概述 Gaia Language v4 Typst DSL —— 知识包的创作界面。完整细节参见 `docs/archive/foundations-v2/language/gaia-language-spec.md`。

## 概览

Gaia Language v4 是一种基于 Typst 的 DSL。作者将知识包编写为标准 Typst 文档；编译器通过 `typst query` 提取结构化知识图。该语言提供三个声明函数、一个关系函数、四个论证策略以及一个跨包参考文献机制。

## 声明

所有声明都会生成带有隐藏元数据的 `figure(kind: "gaia-node")` 元素，从而可以通过单次查询进行提取。

| 函数 | 用途 | 参数 |
|---|---|---|
| `#setting[content]` | 上下文假设 | 仅内容主体 |
| `#question[content]` | 开放性问题 | 仅内容主体 |
| `#claim[content][proof]` | 可判真的断言 | `from:`（前提）、`kind:`（子类型） |

可选的第二个内容块 `[proof]` 包含带有 `@ref` 交叉引用的自然语言证明理由。

### Setting 语义

Setting 不携带 prior，不参与 BP。可作为 factor 的承载性前提（structural dependency），但不创建 BP 边。对齐 [04-reasoning-strategies.md §1.2](../theory/04-reasoning-strategies.md) 和 [gaia-ir.md §1.2](../gaia-ir/gaia-ir.md)。

Claim 可以通过 `from:` 引用 setting 作为前提。Setting 出现在编译后 FactorNode 的 `premises` 列表中，但按 gaia-ir §2.5 的 BP 参与规则，non-claim premise 不参与 BP 消息传递。

## 关系

`#relation` 声明结构约束，编译为 **FactorNode**（不是 KnowledgeNode）。

| 函数 | 用途 | 参数 |
|---|---|---|
| `#relation[content]` | 结构性约束 | `type:`（`"contradiction"` 或 `"equivalence"`）、`between:`（端点） |

**`between:`** —— `#relation` 上的必需参数，命名两个被约束的节点：
```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[描述]
```

### 编译目标

```typst
#relation(type: "contradiction", between: (<claim_a>, <claim_b>))[描述]
```

编译为：

```
FactorNode:
  category: infer
  stage: initial
  reasoning_type: contradict
  premises: [claim_a, claim_b]
  conclusion: None
```

Equivalence 同理（`reasoning_type: equivalent`）。参见 `gaia-ir/gaia-ir.md` 中 FactorNode schema 的定义。

## 关键参数

**`from:`** —— 一个标签引用元组，声明承载性前提：
```typst
#claim(from: (<setting.vacuum_env>, <obs.measurement>))[conclusion][proof]
```
单元素元组需要尾随逗号：`from: (<label>,)`。

**`kind:`** —— `#claim` 上的可选科学子类型（如 `"observation"`、`"hypothesis"`、`"computation"`、`"python"`）。记录证据类型；不改变 Gaia IR 拓扑结构。`kind` 编译为 `KnowledgeNode.metadata: {schema: <kind>}`。

### `from:` 编译映射

```typst
#claim(from: (<premise_a>, <premise_b>))[conclusion][proof]
```

编译为：

```
FactorNode:
  category: infer
  stage: initial
  reasoning_type: None
  premises: [premise_a, premise_b]
  conclusion: this_claim
  steps: [{reasoning: proof_content}]
  weak_points: []
```

- `category: infer`（默认，人类推理）
- `stage: initial`（待 review）
- `reasoning_type: None`（默认，由后续 review 确定具体类型。如果作者通过论证策略生成 factor，reasoning_type 由策略指定。）
- `steps` 来自 `[proof]` 内容块

### ∧ + ↝ 语义

`from:` 创建的粗因子，其多个前提遵循**合取 + 似然蕴含**语义（联合必要条件）。

论证策略（`#abduction` 等）生成细命题网络，由 entailment + equivalence + contradiction 组合而成，所有因子 p=1——推理效果通过 BP 消息传递协作实现。

参见 [03-propositional-operators.md](../theory/03-propositional-operators.md) 和 [05-formalization-methodology.md §2.4](../theory/05-formalization-methodology.md)。

## 论证策略

四个论证策略（argumentation strategies）提供比 `from:` 更精确的推理结构。编译器自动从粗命题网络展开为细命题网络。

**核心原理：**
- **粗命题网络：** 作者的自然推理方向，factor 有 weakpoint（p < 1）
- **细命题网络：** 编译器展开为 entailment (p≈1) + equivalence + contradiction 的组合
- 展开后所有链的 p ≈ 1，不确定性从"推理链强度"转移到"命题是否为真"

`from:` 保留作为通用 entailment（粗因子），论证策略是更精确的替代。

### `#abduction`（溯因）

**语法：**

```typst
#claim[暗物质存在] <hypo.dark_matter>
#claim(kind: "observation")[星系旋转曲线平坦] <obs.rotation>

#abduction(
  hypothesis: <hypo.dark_matter>,
  observation: <obs.rotation>,
)[暗物质引力效应使外围恒星轨道速度偏高，旋转曲线应保持平坦]
```

**粗命题网络：** `[] → H`（无合取 premise，H 是 conclusion）

**细命题网络：**
- O claim（predicted observation，编译器自动生成）
- entailment: H → O（steps = 作者的 justification body）
- equivalent: O ≡ O'（O' = 作者传入的 observation 引用）

**BP 路径：** O' belief 高（实验证据）→ equiv 传递给 O → entailment 反向消息提升 H 的 belief。

**参数说明：**
- `hypothesis:` — 指向一个 claim 的标签引用，是 abduction 的 conclusion（要论证的假说）
- `observation:` — 指向一个 claim 的标签引用，有自己独立的证据链
- Body — justification：为什么 H 能预测 O。编译为生成的 entailment factor 的 `steps` 字段。

### `#induction`（归纳）

**语法：**

```typst
#claim(kind: "observation")[铜导电] <obs.cu>
#claim(kind: "observation")[铁导电] <obs.fe>
#claim(kind: "observation")[铝导电] <obs.al>
#claim[所有金属都导电] <law.metal_conduct>

#induction(
  law: <law.metal_conduct>,
  instances: (<obs.cu>, <obs.fe>, <obs.al>),
)[金属的共同电子结构（自由电子气）使其具有导电性]
```

**粗命题网络：** `[A₁, A₂, A₃] → B`（实例是 premise，定律是 conclusion，合取语义）

**细命题网络：**
- entailment: B → A₁（p≈1）
- entailment: B → A₂（p≈1）
- entailment: B → A₃（p≈1）

**BP 路径：** 多个 Aᵢ belief 高（观测）→ 各 entailment 反向消息共同提升 B 的 belief。

**参数说明：**
- `law:` — 指向一个 claim 的标签引用，是归纳的 conclusion（一般性定律）
- `instances:` — 标签引用元组，支撑定律的具体观测实例
- Body — justification：为什么 B 能蕴含这些实例

### `#analogy`（类比）

**语法：**

```typst
#claim[光具有衍射现象] <source.light_diffraction>
#claim[电子具有衍射现象] <target.electron_diffraction>

#analogy(
  source: <source.light_diffraction>,
  target: <target.electron_diffraction>,
)[光和电子都满足波动方程，共享波动性的核心特征]
```

**粗命题网络：** `[source] → target`（source 是 premise，target 是 conclusion）

**细命题网络：**
- analogy_claim（编译器生成：两个系统具有结构类比关系）
- entailment: [source, analogy_claim] → target（p≈1）

**BP 路径：** source belief 高 + analogy_claim belief 高 → target 获得支持。如果类比被质疑（analogy_claim belief 下降），target 支持减弱。

**参数说明：**
- `source:` — 源系统的已知性质（高 belief 的 claim）
- `target:` — 目标系统的对应性质（要论证的 claim）
- Body — justification：为什么两个系统结构相似。编译为生成的 entailment factor 的 `steps` 字段。

**与 05-formalization-methodology.md 的关系：** [05-formalization-methodology.md §2.3](../theory/05-formalization-methodology.md) 的 analogy 模式有三个前提 `[G_src, M, S_target] → V_target`，其中 M 是类比桥梁，S_target 是目标域条件。本设计简化为 `[source, analogy_claim] → target`——`analogy_claim` 对应 M，而 S_target（目标域条件）在 v1 中不作为独立前提，作者可在 justification 中描述。如果目标域条件需要独立参与 BP，作者可用 `from:` 手动构建更精细的结构。

### `#extrapolation`（外推）

语法和编译结构与 `#analogy` 完全相同。语义区别：跨范围外推而非跨系统迁移。

**语法：**

```typst
#extrapolation(
  source: <obs.known_range>,
  target: <pred.extended_range>,
)[该温度区间无相变，同一物理机制仍主导电阻行为]
```

**粗命题网络：** `[source] → target`

**细命题网络：**
- extrapolation_claim（编译器生成：外推条件成立）
- entailment: [source, extrapolation_claim] → target（p≈1）

### 粗命题网络 → 细命题网络总结

| 策略 | 粗命题网络 | 细命题网络 |
|------|---------|---------|
| `#abduction` | `[] → H` | H→O + O≡O' |
| `#induction` | `[A₁..Aₙ] → B` | B→A₁, B→A₂, ... |
| `#analogy` | `[source] → target` | [source, analogy_claim]→target |
| `#extrapolation` | `[source] → target` | [source, extrap_claim]→target |

## 语言分类

| 类别 | 构件 | 作用 |
|------|------|------|
| **声明** | `#setting`, `#question`, `#claim` | 声明知识对象 |
| **关系** | `#relation(type: "contradiction" \| "equivalence")` | 结构约束（编译为 FactorNode） |
| **论证策略** | `#abduction`, `#induction`, `#analogy`, `#extrapolation` | 程序化生成细命题网络 |

## 标签

标签遵循 `<filename.label_name>` 约定：
```typst
#setting[...] <setting.vacuum_env>
#claim[...]   <reasoning.main_conclusion>
```

`filename.` 前缀是为了在模块间保持唯一性的命名约定。文内引用使用 `@label` 语法。

## 跨包引用

外部知识通过 `gaia-deps.yml` 声明并用 `#gaia-bibliography` 注册：

**`gaia-deps.yml`：**
```yaml
vacuum_prediction:
  package: "galileo_falling_bodies"
  version: "4.0.0"
  node: "vacuum_prediction"
  type: claim
  content: "In a vacuum, objects of different weights fall at the same rate."
```

**用法：**
```typst
#gaia-bibliography(yaml("gaia-deps.yml"))
#claim(from: (<local_derivation>, <vacuum_prediction>))[...][...]
```

`#gaia-bibliography` 创建隐藏的 `figure(kind: "gaia-ext")` 元素，使外部标签可被 Typst 的引用系统和提取管线解析。

## 提取

Gaia IR 通过 Typst 的内置查询机制提取：

```bash
# Local nodes
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-node")'

# External references
typst query --root <repo-root> lib.typ 'figure.where(kind: "gaia-ext")'
```

Python 加载器（`libs/lang/typst_loader.py::load_typst_package_v4`）将查询结果处理为 `{package, version, nodes, factors, constraints, dsl_version: "v4"}`。

## 包布局

支持两种布局：

**Vendored（新包的默认布局，由 `gaia init` 创建）：**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "_gaia/lib.typ": *
  _gaia/              # vendored runtime (copied by gaia init)
    lib.typ
    ...
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

**仓库相对路径（Gaia 仓库内的 fixtures 和开发用途）：**
```
my_package/
  typst.toml          # manifest: name, version, entrypoint
  lib.typ             # entrypoint: #import "/libs/typst/gaia-lang-v4/lib.typ": *
  motivation.typ      # module file
  reasoning.typ       # module file
  gaia-deps.yml       # (optional) cross-package references
```

推荐独立包使用 vendored 布局。仓库相对路径布局用于 `tests/fixtures/` 和 Gaia 仓库内的开发工作流。

## 运行时库

位于 `libs/typst/gaia-lang-v4/`。导出内容：

| 符号 | 来源 | 用途 |
|---|---|---|
| `setting`, `question`, `claim` | `declarations.typ` | 声明函数 |
| `relation` | `declarations.typ` | 关系函数 |
| `abduction`, `induction`, `analogy`, `extrapolation` | `declarations.typ` | 论证策略函数 |
| `gaia-bibliography` | `bibliography.typ` | 跨包引用注册 |
| `gaia-style` | `style.typ` | 文档展示规则和视觉样式 |

> **注：** 论证策略函数的运行时实现属于目标设计，尚未实现。

## 源码

- `libs/typst/gaia-lang-v4/` —— 运行时 Typst 函数定义
- `libs/lang/typst_loader.py` —— Python 提取加载器
- `docs/archive/foundations-v2/language/gaia-language-spec.md` —— 完整规范
- `docs/archive/foundations-v2/language/gaia-language-design.md` —— 设计原理
- `docs/specs/2026-03-25-gaia-lang-alignment-design.md` —— 本次对齐的设计文档
