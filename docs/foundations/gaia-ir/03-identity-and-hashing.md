# Identity And Hashing — 身份与哈希

> **Status:** Target design
>
> **⚠️ Protected Contract Layer** — 本文档定义 Gaia IR 中对象身份、内容指纹与图哈希的边界。它回答“哪些值标识对象本身，哪些值只是帮助匹配或完整性校验”。

## 目的

Gaia IR 里至少有三类容易混淆的“标识”：

- **对象身份**：`Knowledge.id`、`Strategy.strategy_id`、`Operator.operator_id`
- **内容指纹**：`Knowledge.content_hash`
- **图哈希**：`LocalCanonicalGraph.ir_hash`

它们的职责不同，不能混用。

## 1. 三类标识

| 名称 | 作用 | 作用域 | 是否跨包稳定 | 是否可随 representative 变化 |
|------|------|--------|--------------|------------------------------|
| `Knowledge.id` | 标识一个具体 Knowledge 对象 | local / global | local: 否；global: 是 | 否 |
| `Knowledge.content_hash` | 标识 Knowledge 的内容指纹 | local / global | 是 | 是 |
| `LocalCanonicalGraph.ir_hash` | 标识整个 local graph 的 canonical serialization | local graph | 不适用 | 不适用 |

## 2. Knowledge 身份

### 2.1 Local Knowledge

local `Knowledge.id` 是**包上下文敏感**的：

```text
lcn_{SHA-256(package_id + type + content + sorted(parameters))[:16]}
```

因此：

- 同包、同内容、同参数结构 → 相同 `lcn_id`
- 不同包、同内容 → 不同 `lcn_id`
- 同包、内容变化 → `lcn_id` 变化

local `id` 是对象身份，不是跨包去重键。

### 2.2 Global Knowledge

global `Knowledge.id` 是注册中心分配的稳定 canonical identity：

- 一旦某个 global Knowledge 被创建并获得 `gcn_id`，它的 `id` 就不因 representative 切换而变化
- `gcn_id` 不等于内容哈希
- `gcn_id` 也不应被重新计算

也就是说，global `id` 是“这个 canonical 节点是谁”，不是“它当前由哪段内容代表”。

## 3. Knowledge 内容指纹

`Knowledge.content_hash` 是跨包稳定的内容指纹：

```text
SHA-256(type + content + sorted(parameters))
```

它**不包含** `package_id`。

因此：

- 不同包中同内容的 local Knowledge 拥有相同的 `content_hash`
- 同一个 global Knowledge 更换 `representative_lcn` 时，`content_hash` 可能随代表内容同步更新
- `content_hash` 不是对象主键，不能替代 `id`

### 3.1 典型用途

- **Canonicalization 快速路径**
  新 local Knowledge 进入全局图时，先用 `content_hash` 做精确匹配；命中则直接 `match_existing`
- **查询与去重索引**
  global 层保存一份从 `representative_lcn` 同步来的 `content_hash`，供 canonicalization / curation 查询

### 3.2 不应如何使用

- 不能把 `content_hash` 当作 global `id`
- 不能把两个 `content_hash` 相同的节点自动视为“同一条推理链”
- 不能用 `content_hash` 替代 `CanonicalBinding`

`content_hash` 只说明“内容完全一致”，不说明它在图中的结构角色完全一致。

## 4. Strategy 与 Operator 的身份

当前 contract 下：

- `Strategy` 只有 `strategy_id`
- `Operator` 只有 `operator_id`

它们没有独立的 `content_hash` 概念。

原因是：

- Knowledge 有自然的“文本 / 参数内容”
- Strategy 与 Operator 的主要身份来自图结构角色，而不是一段可独立去重的内容文本

是否需要为 Strategy / Operator 引入独立内容指纹，当前不属于 Gaia IR contract。

## 5. 图哈希

`LocalCanonicalGraph.ir_hash` 是对整个 local graph 的 canonical serialization 计算出的确定性哈希。

它的作用是：

- 编译完整性校验
- 重编译后的一致性验证

它**不是**：

- 任一单个 Knowledge 的身份
- 任一单个 Knowledge 的内容指纹
- global graph 的长期标识

当前 contract 下：

- 只有 local graph 使用整体 `ir_hash`
- global graph 是增量变化的，不要求整体哈希

## 6. 三者如何配合

一个最常见的场景：

1. 作者在包 A 中写出一个 claim，生成 `lcn_A...`
2. 作者在包 B 中写出同样内容的 claim，生成 `lcn_B...`
3. 两者 `id` 不同，因为 `package_id` 不同
4. 两者 `content_hash` 相同，因为内容一致
5. canonicalization 用 `content_hash` 命中快速路径，把它们都绑定到同一个 `gcn_...`
6. 这个 global 节点未来即使更换 `representative_lcn`，`gcn_id` 仍不变

这正是“对象身份”和“内容指纹”必须分离的原因。

## 7. Validation 要点

validator 至少应检查：

1. local `Knowledge.id` 是否满足 local ID 规则
2. `content_hash` 若存在，是否与 `type + content + sorted(parameters)` 一致
3. global `Knowledge` 若保存了 `content_hash`，它是否与当前代表内容保持同步
4. `ir_hash` 若定义，是否与 canonical serialization 一致

这些检查的细分边界见 [08-validation.md](08-validation.md)。

## 8. 与其他文档的分工

- [02-gaia-ir.md](02-gaia-ir.md)：定义对象字段本身
- [05-canonicalization.md](05-canonicalization.md)：定义如何利用 `content_hash` 做匹配与提升
- [08-validation.md](08-validation.md)：定义应如何校验这些字段
- [01-overview.md](01-overview.md)：给出高层总览
