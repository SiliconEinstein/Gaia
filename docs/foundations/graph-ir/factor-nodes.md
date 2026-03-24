# Factor 节点

> **Status:** Target design — 基于 [reasoning-hypergraph.md](../theory/reasoning-hypergraph.md) §7 重新设计

本文档是 FactorNode 的唯一定义——Gaia 因子图中的约束节点。FactorNode 对应 theory 层中的**推理算子（reasoning operator）**。

## FactorNode Schema

```
FactorNode:
    factor_id:        str                # f_{sha256[:16]}，确定性

    # ── 三维类型系统 ──
    category:         str                # infer | toolcall | proof
    stage:            str                # initial | candidate | permanent
    reasoning_type:   str | None         # entailment | induction | abduction
                                         # | equivalent | contradict | None

    # ── 连接 ──
    premises:         list[str]          # knowledge node IDs — 承载性依赖，创建 BP 边
    contexts:         list[str]          # knowledge node IDs — 弱依赖，不创建 BP 边
    conclusion:       str | None         # 单个输出 knowledge 节点（双向算子为 None）

    # ── 追溯 ──
    source_ref:       SourceRef | None
    metadata:         dict | None
```

Factor 身份是确定性的：`f_{sha256[:16]}` 由源构造计算得出。相同的推理链接在重复构建时总是获得相同的 factor ID。

Factor 在两个身份层（local canonical、global canonical）之间共享——仅节点 ID 命名空间不同。

## 三维类型系统

### category：怎么得到结论的

| category | 说明 | 概率语义 |
|----------|------|---------|
| **infer** | 人或 agent 的推理判断 | 概率性，由 review 赋值 |
| **toolcall** | 计算过程（工具调用、模拟、数值求解） | 可根据可复现性打分，具体策略后续定义 |
| **proof** | 形式化证明（定理证明、形式验证） | 可设为 1.0（有效证明确定性成立），具体策略后续定义 |

**所有 category 都预留 probability 接口。** 概率值存储在 [parameterization.md](parameterization.md) 的覆盖层中，不内联在 factor 结构里。

### stage：审查到哪了

| stage | 说明 |
|-------|------|
| **initial** | 作者写入时的默认状态。`reasoning_type = None`。 |
| **candidate** | review/research agent 提议了具体推理类型，但尚未充分验证。 |
| **permanent** | 经过验证确认，正式具有明确的 BP 规则。 |

**生命周期规则：**

- `infer` 类 factor 经历完整生命周期：initial → candidate → permanent
- `toolcall` 和 `proof` 不经历生命周期——它们的语义在创建时就是明确的
- Template 实例化（entailment 特例）可跳过 review 直接升格为 permanent

### reasoning_type：具体什么逻辑关系

以下类型适用于 candidate 和 permanent 阶段。stage=initial 时 reasoning_type=None。

#### entailment（蕴含）

封闭断言之间的保真关系。**方向：前提 → 结论，保真。**

- A 为真 → B 必然为真
- A 为假 → 不能推断 B 的真假

```
premises:   [A]
conclusion: B
```

entailment 覆盖以下子场景：

- **抽象（abstraction）**：多个具体 claim 都蕴含一个更弱的公共结论
- **实例化（instantiation）**：从 template 或全称定律推导出具体 claim。probability=1.0，可跳过 review

示例：

- "水是 H₂O" entails "水的分子量为 18"
- Template `∀x. metal(x) → conducts(x)` + 绑定 {x=铜} → "铜导电"（instantiation）
- "PV=nRT 对理想气体成立" → "在 STP 下，1 mol 理想气体体积为 22.4 L"（instantiation）

#### induction（归纳）

从具体案例到更广假说的概率性支持。**方向：前提 → 结论，不保真。**

```
premises:   [A₁, A₂, ..., Aₙ]    # 具体案例
conclusion: B                      # 归纳假说
```

示例：

- "铜导电" + "铁导电" + "铝导电" → "所有金属都导电"
- "样本 A 在 90K 以下超导" + "样本 B 在 92K 以下超导" → "该类材料在 ~90K 以下表现出超导性"

#### abduction（溯因）

从观测到最佳解释。**方向：前提（假说）→ 结论（观测），不保真。**

因子图中，假说作为 premise，观测作为 conclusion。BP 通过反向消息自然实现"从观测推断假说"——观测的高信念提升假说的信念。多个竞争假说的 explaining away 也由此自然产生。

```
premises:   [hypothesis]
conclusion: observation
```

示例：

- "暗物质存在"（假说）→ "星系旋转曲线平坦"（观测）
- "该化合物含有铁离子"（假说）→ "溶液呈红色"（观测）

#### equivalent（等价）

**方向：双向，真值一致。** 相关断言的真值应保持一致。

```
premises:   [A, B]       # 参与者，无方向性
conclusion: None          # 双向没有"结论"
```

示例：

- "水的沸点是 100°C（1 atm）" ↔ "水的沸点是 212°F（1 atm）"

#### contradict（矛盾）

**方向：双向，真值取反。** 相关断言不应同时为真。

```
premises:   [A, B]       # 参与者，无方向性
conclusion: None          # 双向没有"结论"
```

示例：

- "暗能量是宇宙学常数" ⊥ "暗能量是动态标量场"

## 合法组合

| category | stage=initial | stage=candidate/permanent |
|----------|--------------|--------------------------|
| **infer** | reasoning_type=None | reasoning_type 必填 |
| **toolcall** | reasoning_type=None | 不经历 lifecycle，category 本身已编码语义 |
| **proof** | reasoning_type=None | 不经历 lifecycle，category 本身已编码语义 |

**不变量：**

1. `stage=initial` → `reasoning_type=None`
2. `stage=candidate\|permanent` 且 `category=infer` → `reasoning_type` 必填
3. `conclusion` 的 type 必须是 `claim`（如果 conclusion 非 None）
4. `premises` 中的 type 必须是 `claim`（参与 BP 的承载性前提）
5. `contexts` 中的 type 可以是 `claim | setting | question`（不参与 BP）
6. `type=template` 的节点只能作为 entailment factor 的 premise（instantiation 场景）
7. `equivalent` 和 `contradict` 的 `conclusion = None`，`premises` 至少包含 2 个节点

## Premise 与 Context 的区别

- **Premise**（`premises` 字段）：承载性依赖。前提为假会削弱结论的有效性。创建 BP 边——BP 沿这些连接发送和接收消息。只允许 `type=claim`（和 instantiation 场景中的 `type=template`）。
- **Context**（`contexts` 字段）：弱/背景依赖。不创建 BP 边。Setting 和 Question 作为推理输入时进入此字段。被参数化覆盖层在分配 factor 概率时使用。

这一区分的设计动机：Setting/Question 不参与 BP（theory §6.2-6.3），但它们在推理中提供背景信息。将它们放在 `contexts` 而非 `premises` 中，使 BP 引擎无需检查节点类型就知道哪些边参与消息传递。

## 关于撤回（retraction）

Graph IR 中没有 retraction factor 类型。撤回是一个**操作**，不是一种 factor：由原作者发起，将目标 knowledge 节点关联的所有 factor 的 probability 在 parameterization 中设为 0。该 knowledge 节点变成孤岛，belief 自然回到 prior。图结构不变——图是不可变的。

## 编译规则

| 源构造 | Knowledge 节点 | Factor 节点 |
|---|---|---|
| `#claim` / `#setting` / `#question`（无 `from:`） | 一个 knowledge 节点 | 无 |
| `#claim(from: ...)` | 一个 claim 节点 | 一个 factor（`category=infer, stage=initial`） |
| `#action(from: ...)` | 一个 claim 节点 | 一个 factor（`category=toolcall`） |
| `#relation(type: "contradiction", between: (A, B))` | 无 | 一个 factor（`reasoning_type=contradict, premises=[A,B]`） |
| `#relation(type: "equivalence", between: (A, B))` | 无 | 一个 factor（`reasoning_type=equivalent, premises=[A,B]`） |
| Template 实例化 | 一个 claim 节点 | 一个 factor（`reasoning_type=entailment, probability=1.0`） |

## 源代码

- `libs/graph_ir/models.py` -- Graph IR `FactorNode`
- `libs/storage/models.py` -- 存储 `FactorNode`
