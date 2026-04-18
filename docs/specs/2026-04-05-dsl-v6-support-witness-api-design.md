# Gaia DSL v6: Support / Witness API 设计

> **Status:** Draft
>
> **Companion concept spec:** [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md)
>
> **Note (2026-04-18):** References to `ReviewBundle`, `review_claim()`, and `review_strategy()` in this spec are outdated. Since gaia-lang 0.4.2, priors are assigned via `priors.py` and inline `reason+prior` pairing. See `docs/foundations/gaia-lang/package.md`.
>
> **Scope:** Gaia Lang v6 authoring API and review-side surface
>
> **Non-goal:** This document does not directly change Gaia IR protected contracts.

---

## 1. 设计目标

本文将 v6 的概念模型收束为一套**最小 API**，目标是回答五个问题：

1. v6 author-facing API 是否继续“函数返回 Claim”？
2. `Support` 在运行时如何体现？
3. `execute()` / `check()` / `formal_proof()` 的最小签名是什么？
4. review 侧如何区分 `claim / support / witness`？
5. 如何在不修改 protected IR 的前提下平滑落地？

结论先行：

- **是**，v6 继续采用“构造函数返回 `Claim`”的 surface syntax
- 但底层必须显式创建 `Support`，并挂到 `claim.support`
- `execute()` 返回 result claim
- `check()` 返回 validity claim
- `formal_proof()` 返回 proof-backed claim
- review surface 扩展为 `review_claim / review_support / review_witness`
- Phase 1 只在 Gaia Lang 侧引入这些 authoring APIs；IR 侧暂时把 `Support` 映射回 `Strategy`

---

## 2. 术语

| v6 术语 | 含义 | Phase 1 对应现状 |
|--------|------|------------------|
| `Claim` | 被支撑的命题 | `Knowledge(type="claim")` |
| `Support` | 从前提到结论的支撑结构 | `Strategy` |
| `Witness` | 支撑背后的具体可审计对象 | 暂无独立 runtime type，先挂在 metadata |
| `Execution` | 生产 witness 的过程 | 暂不进入 IR contract |

在 v6 文档和 API 中，优先使用 `Support`；在兼容实现中，它可以是现有 `Strategy` 的 DSL-facing rename。

---

## 3. 运行时对象

## 3.1 Claim

概念上，v6 目标对象为：

```python
@dataclass
class Claim(Knowledge):
    support: Support | None = None
```

Phase 1 兼容实现允许继续复用现有 runtime dataclass，并保留 `.strategy` 字段；但 v6 authoring API 应新增或文档化 `.support` 作为首选访问路径：

```python
claim.support is claim.strategy
```

## 3.2 Support

```python
@dataclass
class Support:
    family: str
    premises: list[Claim]
    conclusion: Claim
    background: list[Knowledge]
    witnesses: list[Witness]
    reason: ReasonInput
    metadata: dict[str, Any]
```

要求：

- `premises` 只接受 `Claim`
- `conclusion` 必须是 `Claim`
- `background` 可接受任意 `Knowledge`
- `witnesses` 缺省为空列表

Phase 1 中，`family` 直接对应现有 `Strategy.type`。

## 3.3 Witness

```python
@dataclass
class Witness:
    kind: str
    payload: dict[str, Any]
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
```

`payload` 是 authoring-layer object payload，不等同于持久化 schema。常见 `kind`：

- `formal`
- `execution_result`
- `validation_result`
- `formal_proof`
- `experiment`
- `dataset`
- `benchmark`

---

## 4. Authoring API 总则

### 4.1 Surface rule

v6 所有“创建新结论”的 DSL 构造器都返回 `Claim`：

```python
c = deduction("C", given=[a, b])
r = execute(run_solver, given=[mesh], returns="...")
ok = check(check_impl, given=[spec, tests], returns="...")
thm = formal_proof("P(a) holds.", system="lean", theorem_ref="MyPkg.theorem_a")
```

内部动作统一为：

1. 创建 conclusion claim
2. 创建 support
3. 将 support 赋给 `claim.support`
4. 自动注册 claim / support

### 4.2 Introspection rule

调用方如果需要操作 support，应通过：

```python
c.support
```

而不是把构造器本身做成返回 `Support`。

### 4.3 Escape hatch

保留显式 support constructor，供高级用法或 migration 使用：

```python
support(
    family="deduction",
    premises=[a, b],
    conclusion=c,
    reason="...",
)
```

它返回 `Support`，不返回 `Claim`。

---

## 5. Core Knowledge API

### 5.1 `claim()`

```python
def claim(
    content: str,
    *,
    title: str | None = None,
    given: list[Claim] | None = None,
    background: list[Knowledge] | None = None,
    parameters: list[dict] | None = None,
    provenance: list[dict[str, str]] | None = None,
    **metadata,
) -> Claim
```

语义：

- 纯显式 claim constructor
- 若给 `given=...`，则自动创建 `noisy_and` support

约束：

- `given` 只接受 `Claim`
- `background` 不进入 BP 前提集

### 5.2 `setting()` / `question()`

```python
def setting(content: str, *, title: str | None = None, **metadata) -> Setting
def question(content: str, *, title: str | None = None, **metadata) -> Question
```

保持 v5 语义，不参与 support premise typing。

---

## 6. Formal Support Constructors

这些 family 都返回 `Claim`，而不是 `Support`。

### 6.1 `deduction()`

```python
def deduction(
    content: str,
    /,
    *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

行为：

- 创建 `Claim(content=...)`
- 创建 `Support(family="deduction", premises=given, conclusion=claim, ...)`
- 返回该 claim

### 6.2 `abduction()`

```python
def abduction(
    content: str,
    /,
    *,
    observation: Claim,
    alternative: Claim | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

语义：

- `content` 描述 hypothesis claim
- 返回 hypothesis claim
- `alternative=None` 时，后端可继续沿用现有 public interface claim auto-generation 语义

### 6.3 `induction()`

为避免 API 混乱，v6 只保留一个 author-facing top-down form：

```python
def induction(
    content: str,
    /,
    *,
    observations: list[Claim],
    alternatives: list[Claim | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

语义：

- `content` 描述 law claim
- 返回 law claim
- 内部创建 `family="induction"` 的 composite support
- 每个 observation lowering 为 shared-conclusion abduction sub-support

### 6.4 其他 formal families

同样采用“内容作为第一个参数，返回 claim”的模式：

```python
def analogy(content: str, /, *, source: Claim, bridge: Claim, ...)
def extrapolation(content: str, /, *, source: Claim, continuity: Claim, ...)
def elimination(content: str, /, *, exhaustiveness: Claim, excluded: list[tuple[Claim, Claim]], ...)
def case_analysis(content: str, /, *, exhaustiveness: Claim, cases: list[tuple[Claim, Claim]], ...)
def mathematical_induction(content: str, /, *, base: Claim, step: Claim, ...)
```

`content` 始终描述返回的 conclusion claim。

---

## 7. Parameterized Support Constructors

### 7.1 `noisy_and()`

```python
def noisy_and(
    content: str,
    /,
    *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

这是 `claim(..., given=[...])` 的显式版本。

### 7.2 `infer()`

```python
def infer(
    content: str,
    /,
    *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

用于粗粒度、未分类 support。

---

## 8. Execution-Backed Support Constructors

## 8.1 共同原则

所有 execution-backed constructors 都：

1. 返回一个 `Claim`
2. 在 support 上附带至少一个 witness
3. 不直接执行外部过程（Phase 1）
4. 只声明“存在一个待执行或已记录的 execution-backed support”

Execution 本身属于 `gaia run` 或后续 pipeline，不属于纯结构 authoring。

其中返回 claim 的常见语义有三种：

- `execute()` 返回 result claim
- `check()` 返回 validity claim
- `formal_proof()` 返回 proof-backed claim

## 8.2 `execute()`

```python
def execute(
    fn: Callable[..., Any] | str,
    /,
    *,
    given: list[Claim],
    returns: str,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    execution_backend: str | None = None,
    execution_args: dict[str, Any] | None = None,
    **metadata,
) -> Claim
```

返回值：

- `returns` 描述 result claim content
- 函数返回该 result claim

附带 witness：

```python
Witness(
    kind="execution_result",
    payload={
        "callable_name": getattr(fn, "__name__", str(fn)),
        "callable_ref": fn,
        "execution_backend": execution_backend,
        "execution_args": execution_args or {},
        "declared_returns": returns,
    },
)
```

生成的 support：

```python
Support(
    family="execute",
    premises=given,
    conclusion=result_claim,
    witnesses=[...],
)
```

说明：

- `execute()` 默认产出的是 **execution result claim**
- `execution_backend` 只描述执行边界，不引入新的 ontology-level category
- 如果作者想直接把某次 execution output 当成高层 scientific claim，也允许，但不推荐

示例：

```python
pressure_field = execute(
    run_cfd,
    given=[geometry, boundary_condition],
    returns="The CFD run produced pressure field P for the stated geometry and boundary condition.",
    execution_backend="python",
)
```

## 8.3 `check()`

```python
def check(
    checker: Callable[..., Any],
    /,
    *,
    given: list[Claim],
    returns: str,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    checker_args: dict[str, Any] | None = None,
    **metadata,
) -> Claim
```

返回值：

- `returns` 描述 implementation-validity claim
- 返回该 claim

附带 witness：

```python
Witness(
    kind="validation_result",
    payload={
        "checker_name": checker.__name__,
        "checker_ref": checker,
        "checker_args": checker_args or {},
        "declared_returns": returns,
    },
)
```

推荐语义：

- `check()` 优先用于支撑“实现满足规范 / 在已测 regime 内行为正确 / artifact 通过校验”之类的 claim
- 不建议直接把它当成高层 scientific claim 的终点

示例：

```python
solver_ok = check(
    check_solver_against_spec,
    given=[scheme_spec, test_suite],
    returns="The solver implementation satisfies the stated numerical specification on the tested regime.",
)
```

## 8.4 `formal_proof()`

```python
def formal_proof(
    content: str,
    /,
    *,
    system: str,
    theorem_ref: str,
    given: list[Claim] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    proof_args: dict[str, Any] | None = None,
    **metadata,
) -> Claim
```

返回值：

- `content` 描述被证明的命题 claim
- 返回该 claim

附带 witness：

```python
Witness(
    kind="formal_proof",
    payload={
        "system": system,
        "theorem_ref": theorem_ref,
        "proof_args": proof_args or {},
    },
)
```

生成的 support：

```python
Support(
    family="execute",
    premises=list(given or []),
    conclusion=proved_claim,
    witnesses=[...],
)
```

说明：

- `formal_proof()` 不是新的 ontology-level category
- 它是 execution-backed support 中最强的一类 witness form
- 它比一般 `execute()` / `check()` 更接近 Curry-Howard，但仍可能需要 bridge claims 才能从形式模型走到科学命题

示例：

```python
stability_theorem = formal_proof(
    "Under assumptions H, scheme S is stable.",
    system="lean",
    theorem_ref="FluidLab.Stability.main",
    given=[scheme_spec, assumption_h],
)
```

## 8.5 Historical aliases

为兼容此前讨论，可保留历史别名，但不作为核心 ontology：

```python
toolcall(...) == execute(..., execution_backend="external")
```

`checked_code` 不建议保留为核心名字；优先统一为 `check(...)`。

---

## 9. Explicit Support Constructor

### 9.1 `support()`

```python
def support(
    *,
    family: str,
    premises: list[Claim],
    conclusion: Claim,
    background: list[Knowledge] | None = None,
    witnesses: list[Witness] | None = None,
    reason: ReasonInput = "",
    label: str | None = None,
    **metadata,
) -> Support
```

用途：

- migration
- advanced authoring
- explicit composition

### 9.2 `composite_support()`

```python
def composite_support(
    *,
    family: str = "infer",
    premises: list[Claim],
    conclusion: Claim,
    sub_supports: list[Support],
    background: list[Knowledge] | None = None,
    witnesses: list[Witness] | None = None,
    reason: ReasonInput = "",
    label: str | None = None,
    **metadata,
) -> Support
```

它是作者显式构造 composite support 的 escape hatch。  
普通 author-facing 情况下，`induction()` 应优先走上文的 claim-returning surface API。

---

## 10. Review API

## 10.1 设计原则

review surface 必须允许分开评估：

- claim prior
- support 结构强度 / judgment
- witness 质量

同时允许 inference engine 在运行时把它们折叠成 effective cp。

## 10.2 `review_claim()`

继续保持现有语义：

```python
def review_claim(
    subject: Claim,
    *,
    prior: float | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> ClaimReview
```

## 10.3 `review_support()`

```python
def review_support(
    subject: Support,
    *,
    conditional_probability: float | None = None,
    conditional_probabilities: list[float] | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> SupportReview
```

规则：

- 对 `infer` / `noisy_and`，可直接给条件概率
- 对 formal families，通常只给 `judgment / justification`
- 对 execution-backed families，可给高层 bridge judgment，但不要求把 witness 质量压成同一个数

## 10.4 `review_witness()`

```python
def review_witness(
    subject: Witness | tuple[Support, int],
    *,
    trust: float | None = None,
    judgment: str | None = None,
    scope: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> WitnessReview
```

`subject` 可以直接是 witness 对象；若 implementation 还没有独立 witness object identity，也可暂时通过 `(support, witness_index)` 寻址。

`trust` 不要求直接等于 support cp。它表达：

- 这份 witness 有多可信
- 它的适用域有多大
- 是否覆盖目标 regime

## 10.5 Folded assembled semantics

review source-of-truth 中，support 和 witness 分开存。  
运行时允许形成：

```text
effective_support_strength =
    fold(support_review, witness_reviews, premise_priors, bridge_claim_priors)
```

这份 folded strength 属于 compiled / assembled semantics，不是 authoring source-of-truth。

---

## 11. 兼容性

## 11.1 与 v5 显式 API 的关系

v5：

```python
c = claim("C")
s = deduction(premises=[a, b], conclusion=c)
```

v6 推荐：

```python
c = deduction("C", given=[a, b])
```

兼容策略：

- Phase 1 继续接受 v5 调用形式
- 发出 `DeprecationWarning`
- 内部统一转成 claim-returning surface semantics

## 11.2 与 `claim(..., given=[...])` 的关系

保持兼容，并继续 lowering 到 `noisy_and`。

## 11.3 与现有 review sidecar 的关系

Phase 1 中：

- `review_support()` 可暂时是 `review_strategy()` 的 rename / alias
- `SupportReview` 可先复用 `StrategyReview`
- `review_witness()` 是新增设计目标，不要求本轮立即落地到 protected contract
- `toolcall()` 可暂时作为 `execute()` 的兼容 alias

---

## 12. 最小例子

### 12.1 Formal support

```python
paradox = contradiction(composite_slower, composite_faster)

vacuum_law = deduction(
    "In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster],
    reason="Galileo's contradiction argument rejects the heavier-falls-faster doctrine.",
)
```

### 12.2 Execution-backed result claim

```python
pressure_field = execute(
    run_cfd,
    given=[geometry, boundary_condition],
    returns="The CFD run produced pressure field P for the stated geometry.",
    execution_backend="python",
)

prediction_ok = deduction(
    "The simulated pressure profile matches the hypothesis.",
    given=[pressure_field, bridge_claim],
)
```

### 12.3 Validation claim

```python
solver_ok = check(
    check_solver_against_spec,
    given=[scheme_spec, regression_suite],
    returns="The solver implementation satisfies the stated numerical specification on the tested regime.",
)

science_claim = deduction(
    "The computed phase boundary is trustworthy under the stated assumptions.",
    given=[solver_ok, model_validity_assumption, run_result_claim],
)
```

### 12.4 Formal-proof-backed claim

```python
stability_theorem = formal_proof(
    "Under assumptions H, scheme S is stable.",
    system="lean",
    theorem_ref="FluidLab.Stability.main",
    given=[scheme_spec, assumption_h],
)
```

### 12.5 Review side

```python
REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        review_claim(model_validity_assumption, prior=0.8),
        review_support(prediction_ok.support, judgment="good",
                       justification="Bridge from simulation result to hypothesis is appropriate."),
        review_witness(pressure_field.support.witnesses[0], trust=0.85,
                       justification="CFD tool is validated for this flow regime."),
    ],
)
```

---

## 13. Phase 1 实施范围

本 API spec 推荐的 Phase 1 实施只包括：

1. 将 `Support` 作为 `Strategy` 的 DSL-facing rename
2. 为 claim-returning constructors 建立统一 surface syntax
3. 为 `execute()` / `check()` / `formal_proof()` 建立 authoring-layer declaration API
4. 为 review surface 定义 `review_support()` alias
5. 暂时把 witness 存在 support metadata 或 runtime attachment 上

不包括：

- execution 真正执行
- witness 独立持久化 schema
- protected IR contract 更新
- `gaia run` artifact protocol

---

## 14. 一句话版本

v6 API 的最小原则是：

> 作者看到的是“构造器返回 Claim”；系统内部维护的是“Claim 挂着 Support，Support 带着 Witness”；review 则分别评估 claim、support 和 witness，并在运行时折叠出等效支持强度。
