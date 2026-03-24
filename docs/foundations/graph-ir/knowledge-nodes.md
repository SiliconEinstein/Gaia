# Knowledge 节点

> **Status:** Target design — 基于 [reasoning-hypergraph.md](../theory/reasoning-hypergraph.md) §6 重新设计

Knowledge 节点是 Gaia 因子图中的**变量节点**（variable node）。本文档定义两个身份层中的 knowledge 节点 schema。

Factor 节点见 [factor-nodes.md](factor-nodes.md)。概率参数见 [parameterization.md](parameterization.md)。

## 知识类型

Gaia 中有四种知识对象。**Claim 是唯一默认携带 probability 并参与 BP 的类型。**

### claim（断言）

封闭的、具有真值的科学断言。默认携带 probability（prior + belief），是 BP 的唯一承载对象。

示例：

- "在月球真空中，羽毛和锤子以相同速率下落。"
- "该样本在 90 K 以下表现出超导性。"
- "PV = nRT 对理想气体成立。"

#### Claim 的特化 schema

Claim 可以携带描述其产生方式的结构化元数据。以下是概念性示例，不构成封闭分类：

**观测（observation）**
```
content: "该样本在 90 K 以下表现出超导性"
metadata:
  schema: observation
  instrument: "四探针电阻率测量"
  conditions: "液氮温度区间, 10⁻⁶ Torr 真空"
  date: "2024-03-15"
```

**定量测量（measurement）**
```
content: "YBa₂Cu₃O₇ 的超导转变温度为 92 ± 1 K"
metadata:
  schema: measurement
  value: 92
  unit: "K"
  uncertainty: 1
  method: "电阻率-温度曲线拐点"
```

**计算结果（computation）**
```
content: "DFT 计算预测该材料的带隙为 1.2 eV"
metadata:
  schema: computation
  software: "VASP 6.4"
  functional: "PBE"
  basis: "PAW, 500 eV cutoff"
  convergence: "能量差 < 10⁻⁶ eV"
```

**文献断言（literature）**
```
content: "高温超导体的配对机制仍有争议"
metadata:
  schema: literature
  source: "Keimer et al., Nature 2015"
  doi: "10.1038/nature14165"
```

**理论推导（derivation）**
```
content: "在 Hartree-Fock 近似下，交换能正比于电子密度的 4/3 次方"
metadata:
  schema: derivation
  framework: "Hartree-Fock"
  assumptions: ["单行列式波函数", "均匀电子气"]
```

**经验规律（empirical law）**
```
content: "金属的电阻率与温度成线性关系（Bloch-Grüneisen 高温极限）"
metadata:
  schema: empirical_law
  domain: "固态物理"
  validity: "T >> Debye 温度"
```

具体的元数据 schema 由下层文档定义。Graph IR 层不限制 `metadata` 的结构。

### setting（背景设定）

研究的背景信息或动机性叙述。不携带 probability，不参与 BP。

Setting 可以直接作为 factor 的 context（提供背景），但不创建 BP 边。

示例：

- 某个领域的研究现状
- 一组实验的动机和出发点
- 已知的未解决挑战
- 某种近似方法或理论框架

### question（问题）

探究制品，表达待研究的方向。不携带 probability，不参与 BP。

Question 可以直接作为 factor 的 context（驱动探究方向），但不创建 BP 边。

示例：

- 未解决的科学问题
- 后续调查目标

### template（模板）

开放的命题模式，含自由变量。不直接参与 BP。

Template 的核心作用是**桥梁**：将 setting 或 question 包装为 claim，使其获得概率语义。Template 到 claim 的实例化是 entailment 的特例（probability=1.0）。

示例：

- `falls_at_rate(x, medium)` — 自由变量 `x`, `medium`
- `{method} can be applied in this {context}` — 自由变量 `method`, `context`
- `∀x. wave(x) → diffraction(x)` — 全称量化

## 1. LocalCanonicalNode（包级，来自 `gaia build`）

```
LocalCanonicalNode:
    local_canonical_id:     str              # SHA-256 内容寻址
    type:                   str              # claim | setting | question | template
    content:                str              # 知识内容（唯一存储位置）
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    source_refs:            list[SourceRef]
    metadata:               dict | None      # 特化 schema 数据（见 claim 特化）
```

**身份规则**：`local_canonical_id = SHA-256(type + content + sorted(parameters))`。相同类型、内容和参数的声明共享同一 ID。

**内容的唯一存储位置。** 所有知识的完整文本内容存储在 local canonical 节点上。Global 层不重复存储。

输出产物：`graph_ir/local_canonical_graph.json`

## 2. GlobalCanonicalNode（跨包，注册中心分配）

```
GlobalCanonicalNode:
    global_canonical_id:    str              # 注册中心分配（gcn_<sha256[:16]>）
    type:                   str              # claim | setting | question | template
    representative_lcn:     LocalCanonicalRef  # 代表性 local 节点（内容从此获取）
    member_local_nodes:     list[LocalCanonicalRef]  # 所有映射到此的 local 节点
    provenance:             list[PackageRef]  # 贡献包列表
    metadata:               dict | None
```

**不存储 content。** Global 节点通过 `representative_lcn` 引用一个 local canonical 节点来获取内容。这避免了跨包的长文本重复存储。

**代表性节点选择**：当多个 local 节点映射到同一 global 节点时，选择其中一个作为代表。选择策略是一个可演进的实现细节。

## 3. CanonicalBinding

```
CanonicalBinding:
    local_canonical_id:     str
    global_canonical_id:    str
    package_id:             str
    version:                str
    decision:               str    # "match_existing" | "create_new"
    reason:                 str    # 匹配原因（如 "cosine similarity 0.95"）
```

每条绑定记录了全局规范化中的决策：一个 local 节点是被匹配到现有 global 节点，还是触发了新 global 节点的创建。

## 输出产物

| 阶段 | 产物 | 内容 |
|---|---|---|
| `gaia build` | `graph_ir/local_canonical_graph.json` | 所有 `LocalCanonicalNode` + `FactorNode` |
| 审查/集成 | `CanonicalBinding` 记录 | Local 到 global 的映射决策 |

## 源代码

- `libs/graph_ir/models.py` -- `LocalCanonicalNode`, `FactorNode`
- `libs/storage/models.py` -- `GlobalCanonicalNode`, `CanonicalBinding`
- `libs/global_graph/canonicalize.py` -- `canonicalize_package()`
