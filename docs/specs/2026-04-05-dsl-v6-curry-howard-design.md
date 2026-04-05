# Gaia DSL v6: Curry-Howard Draft Notes

| 属性 | 值 |
|------|---|
| 状态 | Historical Draft |
| 日期 | 2026-04-05 |
| 说明 | 本文保留为历史草稿入口，不再作为当前 v6 设计依据 |

---

## 1. 状态说明

这份文档记录了 PR 333 早期的 v6 思路：试图直接用 Curry-Howard 统一：

- `Claim` 的 authoring 语法
- `Strategy` 的函数化表达
- tool / Python execution 的接入方式
- 形式证明与科学推理的关系

后续讨论表明，这份草稿把几件正交的事情混在了一起，因此不再适合作为当前 v6 设计的主文档。

它的主要问题有三类：

1. 把“函数返回 `Claim`”过度等同于“`Support` 可以消失”
2. 把 Python / tool execution 过度等同于直接的 scientific proof
3. 没有把 `Claim / Support / Witness / Execution` 这几层分开

因此，本文档现在只保留为历史记录和讨论入口。

---

## 2. 当前阅读路径

请改为阅读下面三份新 spec：

1. 概念总纲：
   [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md)

2. 最小 authoring / review API：
   [2026-04-05-dsl-v6-support-witness-api-design.md](2026-04-05-dsl-v6-support-witness-api-design.md)

3. 现有 Python package 的 Gaia layer 集成：
   [2026-04-05-gaia-layer-existing-python-packages-design.md](2026-04-05-gaia-layer-existing-python-packages-design.md)

建议顺序：

1. 先读概念总纲，理解 `Claim / Support / Witness / Execution` 四层
2. 再读 API spec，看 `deduction / execute / check / formal_proof`
3. 最后读 package-layer spec，看如何给现有 Python package 加 Gaia 适配层

---

## 3. 被替代后的核心结论

旧稿里仍然值得保留的 insight，只保留到下面这个层次：

- Curry-Howard 对 Gaia 有启发，但只应主要约束 `Claim / Support / Witness`
- “构造器返回 `Claim`”是合适的 authoring surface
- 现有 Python package 的函数可以被提升成 Gaia support constructor

但这些 insight 现在都已经在新的分层框架里重写：

- `Strategy` 在 v6 authoring 术语中改称 `Support`
- `Support` 不消失，只是被 surface API 隐藏在 claim-returning constructor 后面
- tool / Python / theorem prover 都统一进入 execution-backed support
- `formal_proof` 是 specialized witness form，不是新的顶层 ontology

---

## 4. 为什么不再沿用旧稿

这份旧稿最容易误导读者的地方包括：

- 把“代码能运行”表述得过于接近“代码即证明”
- 把 `toolcall` 作为过于独立的设计中心
- 过早把 subclass-based `Claim` runtime、typed knowledge hierarchy、DSL sugar、IR contract 混成一轮设计

新的三份 spec 的处理方式是：

- 先稳定概念分层
- 再定义最小 API
- 最后定义 package integration pattern

这样可以避免在 authoring surface、execution semantics、review model、IR contract 之间来回缠绕。

---

## 5. 兼容说明

如果后续需要引用这份旧稿，请只把它当成：

- PR 333 的历史背景
- Curry-Howard 讨论的来源草稿
- 被 superseded 的设计记录

不要再把它当成当前 v6 的 normative spec。

---

## 6. 一句话版本

这份 Curry-Howard 草稿保留为历史记录；当前 v6 设计已经迁移到以 `Claim / Support / Witness / Execution` 为核心的三份新 spec 中。
