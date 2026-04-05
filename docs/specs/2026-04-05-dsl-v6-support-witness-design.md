# Gaia DSL v6: Support / Witness / Execution 设计

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | Gaia Lang v6 authoring model |
| 非目标 | 本文不直接修改 Gaia IR protected contract |

---

## 1. 问题重述

PR 333 的 v6 草稿试图同时解决四件事：

1. Python DSL 的表面语法
2. Curry-Howard 对齐
3. 科学论证中的工具调用 / Python 代码整合
4. Gaia IR 与 review / parameterization 的落点

这四件事混在一起时，最容易出现两个错误：

- 把“函数返回 Claim”误当成“Strategy 可以消失”
- 把“代码能运行 / tool 能执行”误当成“科学命题已经被证明”

本文给出一个更稳定的 v6 设计：把 Gaia 分成 `Claim / Support / Witness / Execution` 四层，并只让 authoring surface 做语法革新，不先破坏 IR core 的稳定边界。

### 1.1 给团队解释的一句话

可以先用下面这组口径和团队沟通：

- `Claim` 是要被相信或质疑的命题
- `Support` 是“为什么这些前提能支持这个结论”的推理桥
- `Witness` 是“这一次你拿什么具体东西来支撑这条桥”的过桥凭证
- `Execution` 只是生产 witness 的过程，不等于命题本身

如果只想记一句话，可以记成：

> `Support` 是推理桥，`Witness` 是过桥凭证。

分成两层的原因不是为了增加术语，而是为了区分两种不同的问题：

- 桥本身合不合理
- 这次拿来的凭证靠不靠谱

如果不分开，review 时就会把“论证结构弱”和“证据材料不可信”糊成同一种问题。

---

## 2. 第一性原理

### 2.1 Gaia 的中心对象不是程序，而是被相信的命题

Gaia 的输出是 belief over claims。无论作者写的是自然语言、Python、tool invocation、实验记录，最终被推理系统消费的，仍然是：

- 哪些 `Claim` 被引入
- 它们之间有哪些 `Support`
- 这些 support 背后有什么可审计的 `Witness`

### 2.2 Curry-Howard 给的是逻辑骨架，不是认识论全套

Curry-Howard 最适合约束 Gaia 的前三层：

| Gaia | Curry-Howard 中最接近的对象 | 作用 |
|------|-----------------------------|------|
| `Claim` | proposition / type | 被支撑的命题 |
| `Support` | implication-shaped constructor / proof constructor | 从前提到结论的支撑结构 |
| `Witness` | proof term / inhabitant | 让某个 claim 或 support 成立的具体对象 |

`Execution` 不直接属于 Curry-Howard。它只是生产 witness 的过程：

- Python function
- shell tool
- simulation
- experiment
- LLM call

Curry-Howard 不会自动回答这些 execution 是否可信、是否校准、是否覆盖充分、是否具有外推效力。这些问题属于 review / parameterization / provenance。

### 2.3 科学推理的关键不是“程序即证明”，而是“程序可产生 witness”

在纯证明助手里，proof term 可以直接 inhabit proposition。

在 Gaia 里，多数程序 / 工具 / 实验不会直接 inhabit 科学命题；它们更常见的作用是：

1. 产出一个 execution result witness
2. 该 witness 支撑一个中间 claim
3. 中间 claim 再参与更大的 support chain

因此，v6 不应把“代码”和“科学 claim”直接等同，而应明确中间层。

### 2.4 Python operator 和 type system 应如何复用

既然 v6 已经借用了 Curry-Howard 的一些直觉，一个自然问题是：

> 是否应该直接复用 Python 的 operator 和 type system，把 `tuple` / `Union` 之类直接当成逻辑联结词？

本文的结论是：

- 可以复用 Python operator 和 type hints
- 但它们只应作为 authoring facade
- 不应直接替代 Gaia 的 core ontology

更具体地说：

- 在值层，`Claim` 可以考虑支持 `&` / `|` / `~` 这类 operator sugar
- 在接口层，可以考虑用 type hints 表达一些 CH 风格的 authoring intent
- 但 lowering 后仍应回到显式的 `Claim / Support / Witness / Execution`

原因有三：

1. Python type system 回答的是“值长什么样”，而 Gaia claim 回答的是“命题是否成立、如何被支持、凭什么被相信”
2. `tuple[A, B]` 和 `A | B` 可以提供 conjunction / disjunction 的直觉，但它们本身不携带 claim identity、review state、provenance 或 witness path
3. 即使 authoring surface 长得像 `A & B` 或 `A | B`，Gaia 仍然需要显式 support、witness 和后续 review；这些语义无法直接塞进 Python type system 本身

因此，v6 更合理的方向是：

- operator 走值层 surface sugar
- type hints 走接口层 facade
- Gaia core 继续保持显式语义对象

一句话说：

> Python operators and types may shape the syntax, but they should not replace the ontology.

---

## 3. 四层模型

### 3.1 Claim

`Claim` 是 truth-bearer。它是 Gaia belief 的基本对象。

Claim 的要求：

- self-contained
- 可被支撑、反驳、复用
- 在图中承担 prior / posterior

不是 Claim 的东西：

- 某次 shell 执行过程本身
- 某段 Python 源码文本本身
- 某个日志文件路径本身

这些东西最多是 witness 或 witness 的 payload。

### 3.2 Support

`Support` 替代 `Strategy` 作为 v6 authoring 术语。

它表示：

> 一组前提 claim 如何支撑一个结论 claim。

Support 是一等对象，原因有三：

1. 它有独立语义家族：deduction / abduction / induction / analogy / infer / noisy_and / execution-backed
2. 它需要被 review
3. 它需要被组合、折叠、展开

在 v6 authoring surface 中，函数可以返回 `Claim`，但底层必须仍显式创建 `Support` 对象，并注册到 `claim.supports` 列表中。  
“返回 Claim”是语法糖；”Support 是一等对象”是语义骨架。

**基数说明：一个 Claim 可以拥有多条 Support。** 例如同一个结论既可以通过 deduction 获得支撑，又可以通过 induction 获得独立支撑。在 v5 中，`Knowledge.strategy` 是单值的——如果两条 strategy 共享同一个 conclusion，后者会覆盖前者的 back-reference（虽然两条 strategy 都会注册到 package 中）。v6 应消除这一缺陷：`claim.supports` 是一个列表，所有指向该 claim 的 support 都被保留。

为方便 authoring，提供 `claim.primary_support` 属性，返回 `supports[0]`（即最先注册的那条 support）。大多数 claim 只有一条 support，因此 `primary_support` 是最常用的访问路径。

### 3.3 Witness

`Witness` 是支撑关系背后的具体可审计对象。它回答：

> 为什么这条 support 值得被相信？

Witness 可能是：

- formal skeleton
- execution result
- validation result
- formal proof artifact
- experiment record
- dataset snapshot
- benchmark report

Witness 不一定直接对应一个单独的 claim，但通常应能被解释或提升为一个或多个显式 claim。

**Witness 保留 vs 提升为 Claim 的判定规则：**

Witness 应**保留为 witness metadata** 的情况：

- 该 witness 仅在当前 support 内使用，不被其他 support / claim 引用
- 该 witness 的可信度不需要独立 review（例如，已知可靠的标准库函数的返回值）
- 该 witness 是一次性的 execution artifact（日志、中间数据），不参与后续推理

Witness 应**提升为显式 Claim** 的情况：

- 该 witness 的某个属性会被其他 support 作为前提引用（可复用性）
- 该 witness 的可信度需要独立评估（可审计性）
- 该 witness 可能被质疑或反驳（可反驳性）
- 该 witness 的适用域需要被声明和限定（有界性）

一句话判定：

> 如果一个 witness 属性需要被 review、复用或反驳，它就不应只存在于 metadata 中。

### 3.4 Execution

`Execution` 是生产 witness 的过程。

典型 execution backend：

- 调用 Python function
- 调用外部 tool
- 跑数值模拟
- 跑 unit/property/integration tests
- 读取实验仪器输出

Execution 不直接进入 belief graph 的核心语义；它通过 witness 对图产生影响。

---

## 4. Support 的类型学

### 4.1 Formal Support

这些 support family 有 canonical skeleton，可直接落到现有 Gaia IR 的 named strategies：

- `deduction`
- `abduction`
- `induction`
- `analogy`
- `extrapolation`
- `elimination`
- `case_analysis`
- `mathematical_induction`

它们的核心语义由结构决定，而不是由 reviewer 直接给一条 support 边一个外生 cp。

### 4.2 Parameterized Support

这些 support 没有稳定的 canonical skeleton，或故意保留为 coarse probabilistic support：

- `infer`
- `noisy_and`

它们继续对应现有 parameterization contract 中的显式 strategy-level 条件概率。

### 4.3 Execution-Backed Support

这是 v6 新增的概念层，不要求 Gaia IR 立刻引入新的 protected type。

Execution-backed support 的特征：

- 结论仍然是 `Claim`
- support 本身带有 witness
- witness 由 execution 产生
- review 需要同时评估 support 结构与 witness 质量

它们不是新的“知识类型”，而是一类以 execution 产生 witness 的 support。

在语义层，v6 只需要一个 execution-backed support family。  
不同调用形态的差异应尽量体现在：

- witness kind
- execution metadata
- author-facing constructor sugar

而不应膨胀成多套 ontology。

---

## 5. `execute` / `check` / `formal_proof` 的本质

### 5.1 `execute`

`execute` 的本质不是“执行过程直接证明科学结论”，而是：

> 通过一次 execution 产出结果 witness，该 witness 支撑一个 result claim。

最自然的 authoring 形态不是：

```python
final_claim = execute(run_solver, given=[a, b], returns="...")
```

而是两段式：

```python
result = execute(
    run_solver,
    given=[mesh, boundary_condition],
    returns="The solver run produced pressure field P.",
)

conclusion = deduction(
    "The predicted pressure profile matches the hypothesis.",
    given=[result, bridge_claim],
)
```

也就是说，execution-backed constructor 通常先产出一个 execution-result claim，而不是直接产出最终 scientific claim。

### 5.2 `check`

`check` 的本质不是“单元测试即科学真理”，而是：

> 某个对象、实现、artifact 或运行结果在某个明确规范下，经检查通过，因此支撑一个 validity claim。

典型模式：

```python
solver_ok = check(
    solver_matches_spec,
    given=[scheme_spec, test_suite],
    returns="The solver implementation satisfies the stated numerical spec on the tested regime.",
)
```

注意：`check` 更自然支撑的是 validity / implementation claim，例如：

- 实现满足规范
- 在测试覆盖范围内行为正确
- 某个 checker 未发现违规
- 某个 artifact 通过一致性校验

它通常**不直接**支撑高层 scientific claim。要到达科学结论，仍需要额外的 bridge support，例如：

- 规范本身适用于该科学任务
- 测试覆盖足以代表目标 regime
- 模型假设与现实系统之间的桥接 claim 成立

### 5.3 `formal_proof`

`formal_proof` 不应成为新的顶层 ontology。它应被理解为：

> execution-backed support 中最强的一类 witness：formal proof witness

它比普通 `execute` / `check` 更接近 Curry-Howard，因为它携带的不是一般结果或检查输出，而是 proof-bearing witness。

但它仍然处于同一框架内：

- 需要 execution / checker / environment
- 需要 provenance
- 仍然可能需要 bridge claims 才能从形式模型走到科学命题

因此：

- `formal_proof` 是 specialized witness form
- 不是新的 knowledge type
- 也不是必须脱离 execution-backed support 单独建模的新 ontology

### 5.4 三者的关系

`execute`、`check` 和 `formal_proof` 的关系是：

- 都是 execution-backed support
- 都带 witness
- 都不应被理解为“Execution = Claim”

区别主要在返回 claim 的语义与 witness 强度：

| family | witness 主要表示 | 常见结论 |
|--------|------------------|----------|
| `execute` | 一次运行产生的结果 artifact | result claim / evidence claim |
| `check` | 某个检查过程通过的结果 | validity claim / implementation-validity claim |
| `formal_proof` | proof object 或 proof-checked artifact | formal theorem claim / proof-backed claim |

---

## 6. Review 与 Parameterization

### 6.1 结构上分开，运行时可折叠

v6 的核心原则：

> `Support` 与 `Witness` 在 source-of-truth 中应分开；在 inference engine 的 compiled view 中可以折叠成等效支持强度。

原因：

- support 的不确定性，和 witness 的不确定性，不是同一种不确定性
- 如果一开始就把两者压成一个数，后续无法解释误差来源

### 6.2 Review 的三类对象

概念上，review 应扩展为三类：

1. `review_claim(...)`
2. `review_support(...)`
3. `review_witness(...)`

其中：

- `review_claim`：继续给 explicit claim prior
- `review_support`：给 parameterized support 的结构强度，或给 formal support 的 judgment
- `review_witness`：评估 witness 的可信度、覆盖范围、适用域、校准状态

### 6.3 不同 support family 的 review 规则

#### Formal Support

对 formal support，review 的重点不应是直接给 support 一个外生 cp，而应是：

- review premise / interface claim 的 prior
- review generated public interface claims
- review reasoning judgment / justification

这与当前 Gaia 对 FormalStrategy 的 parameterization 语义一致。

#### Parameterized Support

对 `infer` / `noisy_and`，继续直接给 support-level 条件概率。

#### Execution-Backed Support

对 execution-backed support（包括 `execute` / `check` / `formal_proof`），review 应同时回答两件事：

1. 这类 support 从 witness 到 conclusion 的桥接是否合理
2. 该 witness 本身是否可信

在运行时，可以把二者折叠成 effective support strength：

```
effective_cp = f(
    support_family,
    witness_quality,
    bridge_claim_priors,
    premise_priors,
)
```

但这只是 compiled / assembled view，不是 authoring 时唯一持久化输入。

### 6.4 Witness 何时应提升为显式 Claim

§3.3 给出了 witness 保留 vs 提升的通用判定规则。以下是常见的需要提升为显式 claim 的 witness 属性：

| Witness 属性 | 为什么需要提升 |
|-------------|--------------|
| `tool_is_calibrated` | 会被多个 execution 复用，需要独立 review |
| `run_completed_successfully` | 可能被质疑（运行环境差异） |
| `artifact_is_not_corrupted` | 需要独立校验 |
| `test_suite_is_representative` | 是 bridge claim 的关键前提，需要独立评估 |
| `checker_matches_the_stated_spec` | 可能被反驳（规范不匹配） |
| `simulation_model_is_valid_under_assumption_H` | 有界性——适用域需要声明 |

相反，以下 witness 属性通常**不需要**提升：

| Witness 属性 | 为什么保留为 metadata |
|-------------|---------------------|
| `execution_duration_ms` | 纯 provenance 信息，不参与推理 |
| `output_file_path` | 技术 artifact 定位信息 |
| `random_seed` | 可复现性记录，不影响结论 |
| `library_version` | 除非版本差异影响结果，否则只是 provenance |

提升的根本原则（重申 §3.3）：

> 如果一个 witness 属性需要被 review、复用或反驳，它就不应只存在于 metadata 中。

---

## 7. v6 DSL 方向

### 7.1 表面语法

v6 推荐 surface syntax：

```python
claim_c = deduction("C", given=[a, b])
result = execute(run_tool, given=[x, y], returns="Tool run produced R.")
ok = check(check_impl, given=[spec, tests], returns="Implementation satisfies spec.")
thm = formal_proof("P(x) holds.", system="lean", theorem_ref="MyPkg.my_theorem")
```

所有这些函数都返回 `Claim`，但内部必须创建一条显式 `Support`。

### 7.2 运行时对象

概念上建议引入：

```python
class Claim(Knowledge):
    supports: list[Support] = []

    @property
    def primary_support(self) -> Support | None:
        return self.supports[0] if self.supports else None


class Support:
    family: str
    premises: list[Claim]
    conclusion: Claim
    background: list[Knowledge]
    witnesses: list[Witness]
    reason: ReasonInput
    sub_supports: list[Support] = []  # for composite (e.g. induction)


class Witness:
    kind: str
    payload: dict[str, Any]
    label: str | None = None
```

`Support` 是 v6 authoring terminology。  
在 Phase 1 兼容实现里，`Support` 可先只是 `gaia.lang.runtime.Strategy` 的别名或 DSL-facing rename。`claim.supports` 对应现有 v5 中 package 级别的 strategy registry（而非 `Knowledge.strategy` 单值 back-reference）。

### 7.3 `claim(..., given=[...])` 的地位

`claim(..., given=[...])` 仍然保留，作为最轻量的 sugar：

- 当作者不关心 support family，只想表达“这些前提支撑这个结论”时，用它
- 其默认 lowering 仍对应 `noisy_and`

这不与 v6 冲突；它只是最弱、最便捷的 support constructor。

---

## 8. 与现有 Gaia IR 的关系

### 8.1 不立即修改 protected contract

本文不要求立即修改：

- `gaia-ir/02-gaia-ir.md`
- `gaia-ir/06-parameterization.md`
- execution-backed support 的 protected contract

v6 的第一阶段只改变 Gaia Lang authoring model 与术语，不直接破坏现有 IR 边界。

### 8.2 Phase 1 映射

v6 authoring objects 到现有 IR 的最小映射：

| v6 概念 | v5 / 当前 IR 映射 |
|--------|-------------------|
| `Claim` | `Knowledge(type="claim")` |
| `Support` | `Strategy` |
| `Formal Support` | 现有 named strategy + formalization |
| `Parameterized Support` | `infer` / `noisy_and` |
| `Witness` | 暂存于 support metadata，或提升为显式 claim |
| `Execution-backed support` | 先在 Gaia Lang 侧定义；IR protected contract 后续单独设计 |

### 8.3 后续 protected-layer 工作

若 v6 在 authoring 层验证有效，再单独推进：

1. execution-backed support 的 protected IR contract
2. witness 的持久化 schema
3. `review_witness(...)` 的 sidecar contract
4. `formal_proof` witness 的 checker / environment contract

---

## 9. 与 v5 的兼容性和迁移

### 9.1 API 签名变化总结

| v5 签名 | v6 签名 | 变化性质 |
|---------|--------|---------|
| `deduction(premises, conclusion) -> Strategy` | `deduction(“C”, given=[a, b]) -> Claim` | 返回类型 + 参数风格 |
| `abduction(obs, hyp, alt) -> Strategy` | `abduction(“H”, observation=obs) -> Claim` | 返回类型 + 参数风格 |
| `induction(items, law) -> Strategy` | `induction(“L”, observations=[...]) -> Claim` | 返回类型 + 参数风格 |
| `claim(“C”, given=[a, b]) -> Knowledge` | `claim(“C”, given=[a, b]) -> Claim` | 返回类型细化（兼容） |
| `Knowledge.strategy: Strategy \| None` | `Claim.supports: list[Support]` | 单值→列表 |
| `review_strategy(...)` | `review_support(...)` | rename |

### 9.2 迁移原则

1. **Phase 1 双入口**：v5 签名继续可用，发出 `DeprecationWarning`，内部统一转为 v6 语义
2. **不强制 re-author**：已发布的 v5 packages（galileo, superconductivity 等）可在不修改源码的情况下继续 compile
3. **按需迁移**：新 package 推荐 v6 syntax；旧 package 在下次 major revision 时迁移
4. **工具辅助**：提供 `gaia migrate v5-to-v6` CLI 命令做机械化转换（重命名 + 参数重排），不做语义推断

### 9.3 induction() 的 v5 双模式保留

v5 的 `induction()` 支持两种使用模式：

- **Top-down**：`induction(observations, law, alt_exps=...)` — 给定 observations 和 law，自动生成 abduction sub-strategies
- **Bottom-up**：`induction(existing_abduction_strategies)` — 给定已有 abduction strategies，bundle 成 composite

v6 推荐 top-down claim-returning surface（`induction(“L”, observations=[...])`），但必须保留 bottom-up escape hatch，供需要精细控制 sub-support 结构的高级用法：

```python
# v6 top-down (推荐)
law = induction(“Law L”, observations=[obs1, obs2, obs3])

# v6 bottom-up (escape hatch)
s1 = abduction(“H”, observation=obs1)
s2 = abduction(“H”, observation=obs2)
law = composite_support(
    family=”induction”,
    premises=[obs1, obs2],
    conclusion=claim(“Law L”),
    sub_supports=[s1.primary_support, s2.primary_support],
)
```

---

## 10. 设计决策摘要

| 决策 | 结论 |
|------|------|
| `Strategy` 是否改名 | 在 v6 authoring 术语中改为 `Support` |
| “函数返回 Claim”是否意味着 support 消失 | 否。Support 仍是一等对象，返回 Claim 只是 surface sugar |
| `claim.support` 是单值还是列表 | 列表（`supports: list[Support]`），消除 v5 的 last-writer-wins 问题 |
| `execute` / `check` / `formal_proof` 是不是新的 knowledge type | 否。它们是同一 execution-backed support 模型上的不同 constructor sugar |
| `execute` 是否直接产出最终 scientific claim | 通常不应如此；更自然是先产出 result claim |
| `check` 是否等于科学证明 | 否。它主要支撑 validity claim |
| `formal_proof` 是否应另开 ontology | 否。它是 specialized witness form，但仍在同一框架内 |
| review 时是否把 support+witness 直接绑成一个 cp | source-of-truth 中不直接绑死；compiled view 可折叠为 effective cp |
| Curry-Howard 主要覆盖哪里 | `Claim / Support / Witness`，不直接覆盖 `Execution` |
| Witness 何时保留 vs 提升为 Claim | 需要 review/复用/反驳 → 提升；纯 provenance → 保留为 metadata |
| v5 已发布 packages 是否需要重写 | 否。Phase 1 双入口保证 v5 语法继续可用 |

---

## 11. 非目标

本文不试图在本轮同时解决：

- Python subclass-based `Claim` runtime
- dependent typing
- witness persistence schema
- execution-backed support 的 IR protected contract
- execution cache / reproducibility protocol

这些都应作为后续独立设计。

---

## 12. 推荐实施顺序

### Phase 1: 术语与 surface syntax

- 在 Gaia Lang 中引入 `Support` 术语
- 保留现有 `Strategy` 运行时对象作为兼容实现
- 扩展“函数返回 Claim，但内部创建 Support”的 surface API

### Phase 2: 类型层

- 真正引入 `Claim / Setting / Question` subclasses
- 收窄 DSL 签名到 `list[Claim]`

### Phase 3: execution-backed support

- 设计 `execute` / `check` / `formal_proof` 的 Gaia Lang API
- 明确 witness payload 与 claim promotion 规则

### Phase 4: review / parameterization 扩展

- 增加 `review_support(...)`
- 增加 `review_witness(...)`
- 明确 effective cp 的 assembled semantics

---

## 13. 一句话版本

Gaia v6 的核心不是“程序直接变成 claim”，而是：

> `Claim` 是被相信的命题；`Support` 是支撑结构；`Witness` 是支撑背后的具体对象；`Execution` 是生产 witness 的过程。

在这个框架下，Curry-Howard 给出的是 `Claim / Support / Witness` 的逻辑骨架，而 `execute`、`check` 与 `formal_proof` 则被自然地放入同一个 execution-backed support 模型中。
