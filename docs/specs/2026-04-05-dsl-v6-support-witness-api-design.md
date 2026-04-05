# Gaia DSL v6: Authoring API 设计

> **Status:** Draft
>
> **Companion concept spec:** [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md)
>
> **Scope:** Gaia Lang v6 authoring API and review-side surface
>
> **Non-goal:** This document does not directly change Gaia IR protected contracts.

---

## 1. 设计目标

本文将 v6 的概念模型收束为一套**最小 API**，目标是回答四个问题：

1. v6 author-facing API 是否继续"函数返回 Claim"？
2. Support 继承树在运行时如何体现？
3. `execute()` / `check()` / `formal_proof()` 的最小签名是什么？
4. 如何在不修改 protected IR 的前提下平滑落地？

结论先行：

- **是**，v6 所有 support 构造器都返回 `Claim`（Claim in, Claim out）
- 底层创建对应的 Support 子类实例，挂到 `claim.support`
- `execute()` 返回 result claim，`check()` 返回 validity claim，`formal_proof()` 返回 proof-backed claim
- review surface 为 `review_claim` + `review_support`（后者按子类 dispatch）
- Phase 1 在 Gaia Lang 侧引入 Support 继承树；IR 侧暂时映射回 `Strategy`

---

## 2. 术语

| v6 术语 | 含义 | Phase 1 对应现状 |
|--------|------|------------------|
| `Claim` | 被支撑的命题 | `Knowledge(type="claim")` |
| `Support` | 支撑基类 | `Strategy` |
| `Formal` | 有 canonical skeleton 的 support | 现有 named strategy |
| `Infer` | 参数化 support | `infer` / `noisy_and` |
| `Execution` | 运行计算产出 result | 先在 Lang 侧定义 |
| `Check` | 验证满足规范 | 先在 Lang 侧定义 |
| `FormalProof` | 形式证明验证通过 | 先在 Lang 侧定义 |
| `Composite` | 聚合多条子 support | `Strategy(sub_strategies=[...])` |

---

## 3. 运行时对象

### 3.1 Support 继承树

完整继承树见概念 spec §3.2 和 §6.1。这里列出 API 签名涉及的关键子类：

```python
@dataclass
class Support:
    """基类"""
    premises: list[Claim]
    conclusion: Claim
    background: list[Knowledge] = field(default_factory=list)
    reason: ReasonInput = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# Formal 子类 — 每个 formal family 一个子类
class Formal(Support): ...
class Deduction(Formal): ...
class Abduction(Formal):
    observation: Claim
    alternative: Claim | None = None
class Analogy(Formal):
    source: Claim
    bridge: Claim
# ... 其余 formal families 见概念 spec §6.1


# Infer
class Infer(Support): ...      # infer() — general CPT
class NoisyAnd(Infer): ...  # noisy_and(), claim(..., given=[...])


# Execution-backed 子类
class Execution(Support):
    callable_ref: Callable | str = ""
    execution_backend: str | None = None

class Check(Support):
    checker_ref: Callable | str = ""
    checker_args: dict[str, Any] = field(default_factory=dict)

class FormalProof(Support):
    system: str = ""
    theorem_ref: str = ""
    proof_args: dict[str, Any] = field(default_factory=dict)


# Composite
class Composite(Support):
    sub_supports: list[Support] = field(default_factory=list)
```

Phase 1 中，所有子类可先作为 `Strategy` 的 thin wrapper 实现。

### 3.2 Claim

```python
@dataclass
class Claim(Knowledge):
    support: Support | None = None
```

`claim.support` 保持单值。多条独立 support 通过 `Composite` 聚合。

Phase 1 兼容：`claim.strategy` 保留为 `claim.support` 的别名。

### 3.3 对推理有影响的假设必须是 Claim

v6 不设"介于 Claim 和 metadata 之间"的灰色地带：

- 对推理有影响 → 必须是 `given` 中的 Claim（solver 已验证、测试集覆盖目标场景等）
- 纯 provenance → `support.metadata`（运行时长、文件路径、random seed 等）

---

## 4. Authoring API 总则

### 4.1 Surface rule

v6 所有 support 构造器都返回 `Claim`：

```python
c = deduction("C", given=[a, b])
r = execute(run_solver, given=[mesh], returns="...")
ok = check(check_impl, given=[spec, tests], returns="...")
thm = formal_proof("P(a) holds.", system="lean", theorem_ref="MyPkg.theorem_a")
```

内部动作统一为：

1. 创建 conclusion claim
2. 创建对应 Support 子类实例
3. 将 support 赋给 `claim.support`
4. 自动注册 claim / support

### 4.2 Introspection rule

```python
c.support                  # 访问 support
c.support.sub_supports     # 若为 Composite，访问子 support
```

### 4.3 Escape hatch

保留显式 support constructor，供高级用法或 migration：

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

若给 `given=...`，内部创建 `NoisyAnd`。

### 5.2 `setting()` / `question()`

```python
def setting(content: str, *, title: str | None = None, **metadata) -> Setting
def question(content: str, *, title: str | None = None, **metadata) -> Question
```

---

## 6. Formal Constructors

所有返回 `Claim`，内部创建对应的 `Formal` 子类。

### 6.1 `deduction()`

```python
def deduction(
    content: str, /, *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

### 6.2 `abduction()`

```python
def abduction(
    content: str, /, *,
    observation: Claim,
    alternative: Claim | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

### 6.3 `induction()`

```python
def induction(
    content: str, /, *,
    observations: list[Claim],
    alternatives: list[Claim | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

内部创建 `Composite(sub_supports=[Abduction_1, Abduction_2, ...])`。

需要精细控制 sub-support 结构时，直接使用 `composite_support()`（§9）。

### 6.4 其他 formal families

```python
def analogy(content: str, /, *, source: Claim, bridge: Claim, ...)
def extrapolation(content: str, /, *, source: Claim, continuity: Claim, ...)
def elimination(content: str, /, *, exhaustiveness: Claim, excluded: list[tuple[Claim, Claim]], ...)
def case_analysis(content: str, /, *, exhaustiveness: Claim, cases: list[tuple[Claim, Claim]], ...)
def mathematical_induction(content: str, /, *, base: Claim, step: Claim, ...)
```

---

## 7. Infer Constructors

### 7.1 `noisy_and()`（→ NoisyAnd）

```python
def noisy_and(
    content: str, /, *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

`claim(..., given=[...])` 的显式版本。

### 7.2 `infer()`（→ Infer）

```python
def infer(
    content: str, /, *,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    **metadata,
) -> Claim
```

---

## 8. Execution-Backed Constructors

### 8.1 共同原则

所有 execution-backed constructors：

1. 返回 `Claim`
2. 内部创建对应的 Support 子类（`Execution` / `Check` / `FormalProof`）
3. Phase 1 不直接执行外部过程——只声明 support 结构
4. 对推理有影响的假设（solver 已验证、测试集有代表性等）必须作为 `given` 中的 Claim

### 8.2 `execute()`

```python
def execute(
    fn: Callable[..., Any] | str, /, *,
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

- `returns` 描述 result claim content
- `fn`、`execution_backend`、`execution_args` 记入 `Execution` 的类型安全字段
- 运行时长、库版本等 provenance 自动记入 `support.metadata`

示例：

```python
solver_validated = claim("该 CFD 求解器在低 Re 方腔流中已通过基准验证")

pressure = execute(
    run_cfd,
    given=[geometry, bc, solver_validated],
    returns="CFD 计算得到方腔内的压力场 P",
)
```

### 8.3 `check()`

```python
def check(
    checker: Callable[..., Any], /, *,
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

- `returns` 描述 validity claim
- `checker`、`checker_args` 记入 `Check` 的类型安全字段

示例：

```python
suite_covers_target = claim("回归测试集覆盖了目标 Re 数范围")

solver_ok = check(
    run_regression_tests,
    given=[spec, suite_covers_target],
    returns="求解器在回归测试集上通过了所有精度检查",
)
```

### 8.4 `formal_proof()`

```python
def formal_proof(
    content: str, /, *,
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

- `system`、`theorem_ref`、`proof_args` 记入 `FormalProof` 的类型安全字段

示例：

```python
stability = formal_proof(
    "在假设 H 下，格式 S 是稳定的",
    system="lean",
    theorem_ref="FluidLab.Stability.main",
    given=[scheme_spec, assumption_h],
)
```

---

## 9. Composite Constructor

```python
def composite_support(
    *,
    premises: list[Claim],
    conclusion: Claim,
    sub_supports: list[Support],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    label: str | None = None,
    **metadata,
) -> Support
```

用途：聚合多条子 support（induction bundle、converging evidence 等）。返回 `Support`，不返回 `Claim`。

---

## 10. Review API

### 10.1 `review_claim()`

```python
def review_claim(
    subject: Claim, *,
    prior: float | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> ClaimReview
```

### 10.2 `review_support()`

```python
def review_support(
    subject: Support, *,
    conditional_probability: float | None = None,
    conditional_probabilities: list[float] | None = None,
    judgment: str | None = None,
    justification: str = "",
    metadata: dict[str, Any] | None = None,
) -> SupportReview
```

行为按 Support 子类 dispatch：

| Support 子类 | reviewer 怎么评估 |
|-------------|------------------|
| Formal | judgment + justification |
| Infer | conditional probability |
| Execution / Check / FormalProof | review 前提 claims 的 prior |
| Composite | 递归 review 各条 sub_support |

---

## 11. 最小例子

### 11.1 Formal support

```python
paradox = contradiction(composite_slower, composite_faster)

vacuum_law = deduction(
    "在真空中所有物体以相同速度下落",
    given=[paradox, heavy_faster],
    reason="伽利略的矛盾论证",
)
```

### 11.2 Execution → bridge → 科学结论

```python
solver_validated = claim("该 CFD 求解器在低 Re 方腔流中已通过基准验证")

pressure = execute(
    run_cfd,
    given=[geometry, bc, solver_validated],
    returns="CFD 计算得到方腔内的压力场 P",
)

match_criterion = claim("压力场与参考解 L2 误差 < 1% 即视为吻合")

conclusion = deduction(
    "模拟结果支持方腔流在 Re=100 下存在稳定涡结构",
    given=[pressure, match_criterion],
)
```

### 11.3 Check → bridge → 科学结论

```python
suite_covers_target = claim("回归测试集覆盖了目标 Re 数范围")

solver_ok = check(
    run_regression_tests,
    given=[spec, suite_covers_target],
    returns="求解器在回归测试集上通过了所有精度检查",
)

model_assumptions = claim("不可压 NS 方程在目标条件下适用")

trustworthy = deduction(
    "该求解器的计算结果在目标条件下可信",
    given=[solver_ok, model_assumptions],
)
```

### 11.4 Formal proof

```python
stability = formal_proof(
    "在假设 H 下，格式 S 是稳定的",
    system="lean",
    theorem_ref="FluidLab.Stability.main",
    given=[scheme_spec, assumption_h],
)
```

### 11.5 Review

```python
REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        review_claim(solver_validated, prior=0.9,
                     justification="在 Ghia 1982 基准上偏差 < 0.5%"),
        review_claim(match_criterion, prior=0.85),
        review_support(conclusion.support, judgment="good",
                       justification="Bridge from simulation result to hypothesis is appropriate."),
    ],
)
```

---

## 12. 兼容性

### 12.1 与 v5 显式 API 的关系

v5：`deduction(premises=[a, b], conclusion=c) -> Strategy`
v6：`deduction("C", given=[a, b]) -> Claim`

Phase 1 继续接受 v5 形式，发出 `DeprecationWarning`。

### 12.2 与 `claim(..., given=[...])` 的关系

保持兼容，内部创建 `NoisyAnd`。

### 12.3 与现有 review sidecar 的关系

- `review_support()` = `review_strategy()` 的 rename
- `SupportReview` 可先复用 `StrategyReview`

---

## 13. v5 → v6 迁移策略

### 13.1 迁移工具

`gaia migrate v5-to-v6` CLI 命令，机械化转换：

| v5 模式 | v6 转换 |
|---------|--------|
| `c = claim("C"); deduction([a,b], c)` | `c = deduction("C", given=[a, b])` |
| `c = claim("C"); abduction(obs, c, alt)` | `c = abduction("C", observation=obs, alternative=alt)` |
| `review_strategy(s, ...)` | `review_support(s, ...)` |
| `c.strategy` | `c.support` |

### 13.2 Deprecation 时间线

- **v6.0**：v5 API 发 `DeprecationWarning`，功能保留
- **v7.0**：移除 v5 API

---

## 14. Phase 1 实施范围

包括：

1. Support 继承树（六个子类）
2. Claim-returning constructors
3. `execute()` / `check()` / `formal_proof()` authoring-layer API
4. `review_support()` alias

不包括：

- execution 真正执行
- protected IR contract 更新
- `gaia run` artifact protocol

---

## 15. 一句话版本

> 作者看到的永远是 **Claim in, Claim out**。不同的支撑方式由 Support 继承树的子类区分（Formal、Infer、Execution、Check、FormalProof、Composite），内部自动创建，挂在 `claim.support` 上。
