# Gaia Lang Public Premise / Fills Design

> **Status:** Proposal
>
> **Date:** 2026-04-08
>
> **Note (2026-04-18):** References to "review sidecar" in this spec are outdated. Since gaia-lang 0.4.2, priors are assigned via `priors.py`. See `docs/foundations/gaia-lang/package.md`.
>
> **Companion docs:** [2026-04-08-gaia-package-hole-bridge-design.md](2026-04-08-gaia-package-hole-bridge-design.md), [2026-04-08-registry-hole-bridge-index-design.md](2026-04-08-registry-hole-bridge-index-design.md)
>
> **Depends on:** [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md), [../foundations/gaia-ir/02-gaia-ir.md](../foundations/gaia-ir/02-gaia-ir.md)
>
> **Supersedes:** the earlier hole / fills proposal merged via PRs #362 and #364. Open implementation PRs #365 / #366 / #367 target the superseded design and should be replaced rather than merged as-is.

## 1. Problem

前一版 hole / fills 设计把 `hole` 当成作者显式写出来的 source-level object：

- `hole(...)`
- `fills(source=..., hole=...)`

这在 authoring 上直观，但有两个根本问题：

1. **`hole` 不是永久本体类型**
   同一个 claim 在 `A@1.0.0` 里可能是未解前提，在 `A@1.1.0` 里可能已被内部证明，在 `A@1.2.0` 里甚至可能变成 foreign dependency。  
   所以 `hole` 更像某个 package release 上的接口角色，而不是 IR 里永久存在的 node type。

2. **公开缺口不应依赖作者手工标注**
   对一篇 package 来说，凡是被 exported claims 依赖、且没有在本包内部 discharge 的 boundary premise，本质上就是这篇工作的公开前提接口。  
   如果这些东西只有作者手写 `hole(...)` 才出现，协议会偏离论文结构本身。

因此，本设计改用下面的核心模型：

- 源码里继续用普通 `claim(...)`
- `__all__` 继续表示作者显式公开的结果面
- 编译器从 export surface 自动推出 `public premises`
- `public premises` 再按当前 release 分类成：
  - `local_hole`
  - `foreign_dependency`
- `fills` 绑定的是 **release-scoped premise interface snapshot**，不是“永远叫 hole 的对象”

## 2. Design Goals

1. **First-principles package semantics**
   公开缺口来自 exported claims 的推理边界，而不是来自作者额外写了什么 marker。

2. **No new core IR node type**
   Gaia IR 里不引入 `HoleKnowledge`。`hole` 是 manifest / registry 层的 release-scoped role。

3. **Stable cross-package relations**
   `fills` 必须绑定到具体 release 的 premise interface，而不是漂浮的 source symbol。

4. **Keep authoring simple**
   作者继续写普通 `claim()` 和普通推理；bridge 作者只需显式声明 `fills(...)`。

5. **Separate reasoning from packaging**
   `content_hash` / `ir_hash` 仍属于 IR；interface-level hashing 留在 package manifests，不进入 core IR。

## 3. Key Decisions

### 3.1 `__all__` 只表示 author-declared public exports

`__all__` 仍然是 package 作者显式声明的 public surface。

它不直接等价于：

- holes
- public premises
- bridge targets

它只回答一个问题：

- “这个 package 想把哪些知识节点当成公开结果 / 公开接口暴露出去？”

后续哪些节点构成 `public premises`，由编译器从这些 exports 的依赖闭包中自动推出。

### 3.2 `hole` 是 release-scoped interface role，不是 source primitive

本设计不再把 `hole(...)` 作为协议核心，并且明确决定将其从主线 authoring surface 中移除。

真正的 hole 身份由编译结果决定：

- 对 exported claims 的依赖分析结果
- 相对于某个具体 release
- 以 manifest 中的 `role = "local_hole"` 体现

因此：

- 唯一稳定的 source primitive 仍然是 `claim(...)`
- 作者不能通过 `hole(...)` 直接“声明” hole 身份
- 旧原型实现若已存在，应在 replacement implementation 中删除

#### 命名说明：为什么叫 "hole"？

⚠️ "hole" 这个词在日常英文里常让人误以为是"缺失/未解引用"，但在本协议里它的准确含义是：

> 当前 package 里**已声明**的叶子 claim（没有本地支持策略），它在这个 release 的接口层面可以被下游包通过 `fills` **选择性精炼**。

关键点：

- **一个 `local_hole` 不是 bug，也不是未完成状态**。它是包的合法公开前提 —— 作者把某个命题作为原始证据/观察/abduction 替代方案留在叶子位置，让论文整体结构保持真实。
- **一个 `local_hole` 不会阻塞编译、推理或注册**。它在 `ir.json` 里是普通的 `claim` node，在 BP 里按 review sidecar 给的 prior 参与推理。
- **一个 `local_hole` 是否被下游 fill 是可选的**。大多数 self-contained 的论文包永远不会被下游 fill，这是正常状态。

反例（便于排歧义）：

- ❌ `local_hole` ≠ "未解引用" — 未解引用会让 validator 报错，根本进不到 manifest
- ❌ `local_hole` ≠ "缺失依赖" — 跨包依赖的 leaf 走 `foreign_dependency` 角色，不是 `local_hole`
- ❌ `local_hole` ≠ "TODO 标记" — 作者不需要"填补"本地 hole；整个包完全 self-contained 时所有 hole 都会一直是 hole

如果你读完 `holes.json` 里有 32 个 entry 却没有任何 fill 关系，这是**正确**的状态 —— 它只是告诉下游生态"这 32 个原始证据位置**可能**可以被更强的观察工作 refine"。真实例子见 `watson-rfdiffusion-2023-gaia@0.1.1`：32 个 local holes，其中 20 个是原始观察（如 denoising_process 的实验描述），12 个是 abduction 的替代解释（如 alt_nonspecific_binding_p53_mdm2）。包本身完全合法，这些 holes 也不需要被填。

### 3.3 `fills` 仍然保留，但 target 不再语义化为“永久 hole object”

推荐的 author-facing API 改成：

```python
fills(source=..., target=...)
```

而不是：

```python
fills(source=..., hole=...)
```

原因不是“target 可以不是 hole”，而是：

- target 在 source 层只是一个 claim reference
- 它是否属于可填补的 public premise
- 以及它在当前 release 上是不是 `local_hole`

都应由编译阶段根据 manifests 决定，而不是依赖 imported Python object 上有没有 hole marker。

### 3.4 `public premise` 与 `exported conclusion` 必须区分

同一个 claim 在 package 接口里可能同时扮演两个角色：

- 它是作者显式 export 的 public claim
- 它又是另一个 exported claim 的 boundary premise

因此 manifest 层必须允许同一 QID 同时出现在：

- `exports.json`
- `premises.json`

角色不是互斥的，而是相对于接口视角定义的。

## 4. Public Premise Derivation

### 4.1 Definitions

对某个 package release：

- **export root**
  - 任何出现在 `__all__` 中的 claim
- **local support**
  - 当前 package 内某条 strategy 的 `conclusion == claim`
- **boundary premise**
  - 位于某个 export root 上游依赖闭包中，但没有被本包继续向上 discharge 的 claim

boundary premise 再分成：

- `local_hole`
  - boundary premise 是本包本地 claim
- `foreign_dependency`
  - boundary premise 是 foreign imported claim

### 4.2 Phase 1 Algorithm

对每个 exported claim root：

1. 从该 root 反向收集所有 local supporting strategies
2. 对这些 strategies 的 `premises` 递归继续向上追溯
3. 遇到没有 local support 的 claim 时停止
4. 将其记为一个 `public premise`

分类规则：

- `qid.package == current_package` -> `local_hole`
- `qid.package != current_package` -> `foreign_dependency`

Phase 1 只分析 claim premises，不把 `background` 自动升级成 public premise。

### 4.3 Important Consequences

1. **不是所有 leaf 都公开**
   只有落在 exported claims 依赖闭包中的 boundary premise 才进入 public premise surface。

2. **不是所有 public premise 都是 hole**
   foreign imported claim 是 `foreign_dependency`，不是 `local_hole`。

3. **hole 会过时**
   同一个 QID 在不同 release 上可以：
   - 是 `local_hole`
   - 不是 public premise
   - 是 `foreign_dependency`

因此 bridge 不能只绑定 QID，必须绑定 interface snapshot。

## 5. `fills()` Design

### 5.1 API

推荐的最小 author-facing API：

```python
def fills(
    source: Knowledge,
    target: Knowledge,
    *,
    mode: Literal["deduction", "infer"] | None = None,
    strength: Literal["exact", "partial", "conditional"] = "exact",
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy
```

其中：

- `source` 是支持性结果
- `target` 是一个 claim reference
- `target` 是否真的是可填补 hole，不由 source object 决定，而由 compile-time interface validation 决定

### 5.2 Lowering Rule

`fills()` 仍然不是新的 core strategy primitive。

lowering 规则保持不变：

- `mode="deduction"` -> lower 成 `deduction`
- `mode="infer"` -> lower 成 `infer`
- `mode is None`
  - `exact` -> `deduction`
  - `partial` -> `infer`
  - `conditional` -> `infer`

同时写入 namespaced relation metadata：

```python
{
  "gaia": {
    "relation": {
      "type": "fills",
      "strength": "exact",
      "mode": "deduction"
    }
  }
}
```

本 lowering 规则与上一版 proposal 的强弱映射保持一致，不把这次 redesign 的成本扩散到 BP 语义层。

### 5.3 Compile-Time Validation

`fills(source, target)` 在 compile 时必须通过两层校验：

1. **source 校验**
   - `source` 必须是 claim
   - 若 source 是 foreign claim，则其 package 必须出现在依赖约束中

2. **target 校验**
   - `target` 必须是 claim
   - 编译器不能只看 source object metadata
   - 必须根据当前 release 对应的 interface manifests，确认 target 在被引用 release 上是 `local_hole`

如果 target 当前只是：

- 普通 exported claim
- foreign dependency
- 已被后续版本内部消解的旧 hole

则该 `fills` 不成立，编译应报错或要求更新 target snapshot。

### 5.4 `target_resolved_version` Resolution Rule

当 `fills(target=foreign_claim)` 指向依赖包时，compile 必须同时确定：

- 作者声明的 dependency range
- 当前环境实际验证到的 dependency release

本设计明确采用：

- `target_dependency_req`
  - 来自 `pyproject.toml` 的依赖约束
- `target_resolved_version`
  - 来自当前 Python 环境中实际安装并被 import 解析到的 dependency version

也就是说，Phase 1 不做：

- “满足约束的最新 registry 版本”查询
- “满足约束的最低版本”推断
- 离线情况下的 registry lookup

compile 只对“当前环境里实际被解析到的那个依赖 release”负责。

## 6. Release-Scoped Target Binding

### 6.1 Why QID Alone Is Not Enough

只记录：

- `target_qid = github:package_a::key_missing_lemma`

是不够的，因为下面三种情况都会发生：

1. `A@1.0.0` 中它是 `local_hole`
2. `A@1.1.0` 中它已被内部证明，不再是 hole
3. `A@1.2.0` 中内容改写了，但 QID 没变

所以 `fills` 必须绑定到一个 **premise interface snapshot**。

### 6.2 Target Snapshot Fields

bridge relation 的 target 至少要携带：

- `target_qid`
- `target_resolved_version`
- `target_interface_hash`

其中：

- `target_qid` 标识“这是哪个 claim”
- `target_resolved_version` 标识“这是哪个 release”
- `target_interface_hash` 标识“在这个 release 上它的接口状态是什么”

### 6.3 `interface_hash` 不进入 Gaia IR

`interface_hash` 属于 package / manifest 层，而不是 Gaia IR。

原因：

- 它依赖 `public premise` 分类结果
- 它是 release-scoped
- 它是为了 package compatibility / bridge stability 服务

因此边界应是：

- `content_hash`: node IR
- `ir_hash`: graph IR
- `interface_hash`: manifest

## 7. Scenario Walkthroughs

### 7.1 Scenario A: B 直接 fills A 的缺口

A 的源码只需要正常表达论文结构：

```python
from gaia.lang import claim, deduction

main_theorem = claim("Main theorem.")
key_missing_lemma = claim("A missing lemma.")

deduction(
    premises=[key_missing_lemma],
    conclusion=main_theorem,
    reason="Main theorem depends on the lemma.",
)

__all__ = ["main_theorem"]
```

编译 A 后：

- `exports.json` 中有 `main_theorem`
- `premises.json` 中自动出现 `key_missing_lemma`
- 且其 role 为 `local_hole`

B 写：

```python
from gaia.lang import claim, fills
from package_a import key_missing_lemma

b_result = claim("Theorem 3 proves the missing lemma.")

fills(
    source=b_result,
    target=key_missing_lemma,
    reason="Theorem 3 establishes A's missing premise.",
)

__all__ = ["b_result"]
```

compile B 时：

- 读取 A 在依赖版本上的 premise interface manifest
- 确认 `key_missing_lemma` 在该 release 上是 `local_hole`
- 在 B 的 `bridges.json` 中记录一条 release-scoped bridge relation

### 7.2 Scenario B: B 没发现，后来 C 才发现

B 只是正常发布自己的 package。

后来 C 做一个小 bridge package：

```python
from gaia.lang import fills
from package_a import key_missing_lemma
from package_b import b_result

fills(
    source=b_result,
    target=key_missing_lemma,
    reason="B's result fills A's public premise interface.",
)
```

这个 package 可以没有本地 claim。  
它的价值完全在于：

- 将 `B.result -> A@version.premise_snapshot` 公开成 bridge relation

## 8. Compatibility / Migration

### 8.1 Earlier `hole()` Prototype

如果代码库里已经存在 `hole(...)` 原型实现，本设计的明确迁移决策是：

- 删除 `hole()` 作为公开 source primitive
- 删除相关 DSL 校验与测试
- 不提供“作者声明 hole 身份”的兼容语义

这样可以避免 source marker 和 compiler 派生角色发生分歧。

### 8.2 Earlier `fills(..., hole=...)`

如果已有实现使用：

```python
fills(source=..., hole=...)
```

迁移方向应是：

- 参数名改成 `target`
- compile validation 改成查 target interface manifest
- 不再要求 imported object 自带 hole marker

因为旧实现尚未合入主线，本设计不提供 `hole=` -> `target=` 的长期兼容 alias。

## 9. Non-Goals

- 不在 Lang 层引入 global canonicalization
- 不把 bridge relation 变成新的 BP primitive
- 不要求作者显式枚举所有 premise interfaces
- 不要求 `hole` 身份跨版本稳定
