# Gaia Lang Hole / Fills Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Companion docs:** [2026-04-08-registry-hole-bridge-index-design.md](2026-04-08-registry-hole-bridge-index-design.md)
>
> **Depends on:** [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md), [../foundations/gaia-ir/02-gaia-ir.md](../foundations/gaia-ir/02-gaia-ir.md)

## 1. Problem

当前 Gaia Lang v5 只有：

- `claim()`
- `setting()`
- `question()`
- 一组 reasoning strategies

这足够表达“论文内部怎么推理”，但不够清楚地表达两类生态语义：

1. **这个 claim 是一个公开缺口（hole）**
2. **这个 package 在声明：某个结果 fills 某个外部 hole**

今天作者当然可以用普通 `claim()` 和普通 `deduction()` 勉强表达这些意思，但会有两个问题：

- 对人类作者和 reviewer 来说，意图不够显式
- 对 package / registry 来说，难以稳定抽取 hole / bridge manifests

## 2. Design Goals

1. **Author-facing clarity**
   作者要能直接写出“这是一个 hole”和“我在 fills 某个 hole”。

2. **No new core IR primitive**
   Gaia IR 不新增 `HoleKnowledge` 或 `FillsStrategy` 这类 runtime schema。

3. **Registry-extractable**
   package 和 registry 可以机械地抽取 `holes.json` / `bridges.json`。

4. **Cross-package explicitness**
   `fills` 必须建立在显式 foreign reference 之上，而不是自由文本。

5. **Keep BP semantics separate**
   “这是在补洞”是生态意图；“补得有多强”仍然由已有 strategy semantics 决定。

## 3. Key Decisions

### 3.1 `hole` 是独立 authoring API

推荐新增：

```python
hole(...)
```

而不是只靠：

```python
claim(..., metadata={"proof_state": "hole"})
```

原因：

- 这是作者会高频直接用到的语义，不应埋在 metadata 里
- 代码审阅时一眼可见
- 编译器和 registry 提取规则更直接

但在 lowering 层，`hole()` 仍然编译成普通 `Knowledge(type="claim")`，只是 metadata 中带上 hole 标记。

### 3.2 `fills` 是 author-facing relation intent

推荐新增：

```python
fills(...)
```

但它**不是**新的 core strategy type。它只是作者层的 intent wrapper。

编译后仍然是普通 strategy：

- `deduction`
- 或 `infer`

外加 relation metadata，供 package / registry 抽取 bridge relation。

### 3.3 不新增 `Hole` 或 `Bridge` 的 IR schema

Gaia IR 继续保持现有边界：

- imported / exported / cross-package relation 不进入 core schema 变体
- `hole` 仍然是 `claim`
- `fills` 仍然是普通 strategy + metadata

这和现有 “foreign QID 是普通 Knowledge，不新增特殊 imported node type” 的边界保持一致。

## 4. `hole()` Design

### 4.1 API

```python
def hole(
    content: str,
    *,
    title: str | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Knowledge
```

返回值仍然是普通 `Knowledge(type="claim")`。

### 4.2 Lowered Form

`hole()` 在运行时等价于：

```python
claim(
    content,
    title=title,
    background=background,
    parameters=parameters,
    provenance=provenance,
    proof_state="hole",
    **metadata,
)
```

也就是说：

- 不新增 KnowledgeType
- 只是在 metadata 上固化 `proof_state = "hole"`

### 4.3 Restrictions

`hole()` 不接受 `given=...`。

理由：

- `given=` 会自动创建 in-package support strategy
- 一个已经被本包直接支撑起来的 claim，通常不应再声明成“公开缺口”

如果作者既想表达“这是当前论文的公开缺口”，又想附上一些弱背景支持，应该用：

- `background=[...]`
- 或普通 `claim(...)`，而不是 `hole(...)`

### 4.4 Export Semantics

`hole` 只有在进入 `__all__` 时，才成为**公开 hole interface**。

因此有三种层次：

1. `hole(...)` 但不 export
   只是 package 内部未解子目标

2. `hole(...)` 且 export
   成为 registry 可索引的 public hole

3. 普通 `claim(...)`
   不是 hole，即使它当前没有被证明

这很重要，因为我们不希望系统把所有叶子前提都自动暴露成公共接口。

### 4.5 Example

```python
from gaia.lang import claim, deduction, hole

main_theorem = claim("Main theorem of package A.")
key_missing_lemma = hole("A still-missing lemma required by the main theorem.")

deduction(
    premises=[key_missing_lemma],
    conclusion=main_theorem,
    reason="If the missing lemma were established, the main theorem would follow.",
)

__all__ = ["main_theorem", "key_missing_lemma"]
```

## 5. `fills()` Design

### 5.1 API

推荐最小 API：

```python
def fills(
    source: Knowledge,
    hole: Knowledge,
    *,
    mode: Literal["deduction", "infer"] | None = None,
    strength: Literal["exact", "partial", "conditional"] = "exact",
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy
```

### 5.2 Why `source` is singular

`fills` 的接口刻意只接受一个 `source` claim，而不是 `premises=[...]`。

原因：

- 生态层的 bridge relation 应该连的是“公开 claim -> 公开 hole”
- 如果 B 需要多个本地前提，应该先在包内推出一个本地 `source` result
- 然后再显式声明 `source fills hole`

这样 registry relation 结构最稳定，查询时也最清楚。

### 5.3 Lowering Rule

`fills()` 本身不是新的 strategy primitive，而是 lowering sugar：

- `mode="deduction"` 时：
  - lower 成 `deduction(premises=[source], conclusion=hole, ...)`
- `mode="infer"` 时：
  - lower 成 `infer(premises=[source], conclusion=hole, ...)`

若 `mode is None`，则按 `strength` 推断：

- `exact` -> `deduction`
- `partial` -> `infer`
- `conditional` -> `infer`

同时写入 strategy metadata：

```python
{
  "ecosystem_relation": {
    "type": "fills",
    "strength": "exact",
    "target_role": "hole"
  }
}
```

### 5.4 Why not make `fills` a new BP primitive

因为这里其实有两个正交维度：

1. **生态意图**
   这是在填别人的 hole

2. **逻辑强度**
   这是严格证明、弱支持，还是条件性支持

前者适合 authoring / registry metadata。  
后者适合继续复用已有的 `deduction` / `infer`。

如果把两者混成一个新的 runtime primitive，反而会污染 core IR。

### 5.5 Validation Intent

`fills(source, hole)` 在 authoring / compile 时应至少校验：

- `source.type == "claim"`
- `hole.type == "claim"`

在 package / registry 层进一步校验：

- 若 `hole` 是 foreign reference，则它应解析到对方 package 的 exported hole
- 若不是 foreign hole，则该 relation 不进入 registry bridge index

### 5.6 Example: B directly fills A

```python
from gaia.lang import claim, fills
from package_a import key_missing_lemma

b_result = claim("Theorem 3 in package B.")

fills(
    source=b_result,
    hole=key_missing_lemma,
    strength="exact",
    reason="Theorem 3 proves exactly the missing lemma exposed by package A.",
)

__all__ = ["b_result"]
```

### 5.7 Example: C publishes a bridge package

```python
from gaia.lang import fills
from package_a import key_missing_lemma
from package_b import b_result

fills(
    source=b_result,
    hole=key_missing_lemma,
    strength="conditional",
    mode="infer",
    reason="Under the assumptions compared in this package, B.result is sufficient to fill A.hole.",
)
```

这里 package C 可以没有本地 theorem claim。  
它的主要公开内容就是 cross-package relation 本身。

## 6. Worked Scenarios

### 6.1 Scenario A: B immediately knows it fills A

这个场景里：

- A 已经把缺失前提写成 exported `hole`
- B 在 formalize 时就知道自己的结论能填这个 hole

作者层的最小写法是：

```python
# package_a
from gaia.lang import claim, deduction, hole

main_theorem = claim("Main theorem of package A.")
key_missing_lemma = hole("A still-missing lemma required by the main theorem.")

deduction(
    premises=[key_missing_lemma],
    conclusion=main_theorem,
    reason="If the missing lemma were established, the main theorem would follow.",
)

__all__ = ["main_theorem", "key_missing_lemma"]
```

```python
# package_b
from gaia.lang import claim, fills
from package_a import key_missing_lemma

b_result = claim("Theorem 3 in package B.")

fills(
    source=b_result,
    hole=key_missing_lemma,
    strength="exact",
    reason="Theorem 3 proves exactly the missing lemma exposed by package A.",
)

__all__ = ["b_result"]
```

这里不需要单独 bridge package。  
B 自己就是 relation 的 declaring package。

### 6.2 Scenario B: B did not notice, later C discovers it

这个场景里：

- A 已经公开了 hole
- B 只发布了自己的 paper package，没有写 `fills`
- 后来 C 发现 `B.result fills A.hole`

那么：

```python
# package_b
from gaia.lang import claim

b_result = claim("Theorem 3 in package B.")
__all__ = ["b_result"]
```

```python
# package_c_bridge
from gaia.lang import fills
from package_a import key_missing_lemma
from package_b import b_result

fills(
    source=b_result,
    hole=key_missing_lemma,
    strength="conditional",
    mode="infer",
    reason="Under the assumptions compared in this bridge package, B.result is sufficient to fill A.hole.",
)
```

这里：

- B 不需要回头修改自己的 package
- C 用普通 `knowledge-package` 就能发布这条 relation
- `declared_by_owner_of_source = false` 将在 package / registry 层体现

### 6.3 Boundary Condition: A did not export a hole

如果 A 只是有一个内部前提，但没有把它显式写成 exported `hole`：

- B 仍然可以 import A 的普通 exported claim
- 但不能把这条关系当成正式的 `fills(hole=...)` 进入 hole/bridge 协议

也就是说，`fills` 的目标必须是显式公开的 hole interface，而不是任意 premise。

## 7. Why Separate APIs Are Better

### 7.1 Thought Experiment: hidden metadata only

如果只允许：

```python
claim(..., metadata={"proof_state": "hole"})
deduction(..., conclusion=foreign_hole)
```

机器当然能跑，但有三个问题：

- 代码一眼看不出作者 intent
- registry 很难稳定区分普通 cross-package deduction 和 fills relation
- reviewer 很难快速扫出 package 的 public holes

### 7.2 Thought Experiment: dedicated APIs

如果作者能直接写：

```python
hole(...)
fills(...)
```

那么：

- 代码层 intent 清晰
- package manifest 提取是机械的
- registry index 构建也不需要猜测

因此作者层应该有显式 API，runtime 层再 lower 到旧 primitive。

## 8. Interaction with Existing Gaia Lang

### 8.1 `claim`

- 继续是默认的科学断言构造
- 不自动推断 hole

### 8.2 `__all__`

- 仍然是唯一的 package public surface
- `hole` 是否公开，只取决于是否 export

### 8.3 Cross-package import

`fills` 不引入新 import 机制。仍然是：

```python
from package_a import exported_hole
```

即显式 foreign reference，而不是 registry 层自动绑定。

### 8.4 Review / BP

这次设计不改变 review / BP 核心规则：

- `hole` 仍然是 claim
- `fills` 仍然是 ordinary strategy
- package / registry 只是额外理解其生态意图

## 9. Proposed Minimal Runtime Surface

语言层建议新增：

```python
from gaia.lang import hole, fills
```

其中：

- `hole` 放在 `gaia.lang.dsl.knowledge`
- `fills` 放在 `gaia.lang.dsl.strategies`

作者默认导入面变成：

```python
from gaia.lang import (
    claim, hole, setting, question,
    contradiction, equivalence, complement, disjunction,
    noisy_and, infer, deduction, fills, abduction, analogy,
    extrapolation, elimination, case_analysis,
    mathematical_induction, composite,
)
```

## 10. Decisions

1. **`hole` 用独立 DSL 构造，不埋在 metadata-only 约定里。**
2. **`hole` lower 成普通 claim，不新增 IR node type。**
3. **`fills` 用独立 DSL 构造，但不新增 runtime strategy type。**
4. **`fills` 的逻辑强度继续复用 `deduction` / `infer`。**
5. **public hole 由 `hole(...) + export` 共同决定。**

## 11. Open Questions

1. `conditional` fills 是否需要结构化 `conditions=` 字段，而不只是自由文本 `reason`？
2. 是否需要额外的 `weak_fills()` / `refines_hole()` author sugar，还是统一留给 `fills(..., strength=...)`？
3. bridge package 如果完全没有本地 claim，README / narrative 应该如何渲染得更自然？
