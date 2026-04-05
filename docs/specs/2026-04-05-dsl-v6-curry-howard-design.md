# Gaia DSL v6: Curry-Howard Aligned Redesign

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | `gaia/lang/dsl/`, `gaia/lang/runtime/nodes.py`, 测试, 文档 |
| 不变 | `gaia/ir/`, `gaia/bp/`, `gaia/cli/commands/`, 编译器核心逻辑 |

---

## 1. 动机

### 1.1 当前 DSL 的问题

当前 DSL 中，所有命题都用 `Knowledge(type="claim"|"setting"|"question")` 表示，策略函数接收 conclusion 作为参数并返回 Strategy：

```python
a = claim("Evidence A")          # Knowledge(type="claim")
b = claim("Evidence B")          # Knowledge(type="claim")
c = claim("Conclusion")          # Knowledge(type="claim") — 独立创建
s = deduction(premises=[a, b], conclusion=c)  # s: Strategy, c 已存在
```

三个问题：

1. **类型校验缺失**：`claim()`、`setting()`、`question()` 都返回 `Knowledge`，type checker 无法区分。Setting 可以传入 `deduction(premises=[setting_obj])` 而不报错。

2. **认识论结构被掩盖**：`a = claim("A")` 和 `c = claim("C")` 写法相同，看不出 c 是推导出来的。claim 的认识论地位（公理 vs 定理）只能通过追踪 strategy 引用才能发现。

3. **不符合 Curry-Howard 精神**：在 CH 中，定理（结论）是由证明（推理）构造出来的，不是独立存在然后被"连接"的。当前 DSL 先独立创建 conclusion，再用 strategy 连接，违反了"证明构造定理"的语义。

### 1.2 设计原则

| Jaynes | Polya | Curry-Howard | Factor Graph | Review |
|--------|-------|-------------|-------------|--------|
| 先验 vs 后验 | 输入 vs 输出 | 公理 vs 定理 | 根变量 vs 叶变量 | 需要 prior vs 不需要 |

五个视角指向同一结论：**直接断言的命题**和**推导出来的命题**有根本区别，DSL 的语法应该反映这个区别。

### 1.3 Curry-Howard 在 Python 中的定位

完整的 CH 同构要求命题是类型（`VacuumLaw` 是一个 type），证明是该类型的居民。Python 没有 dependent type，无法让类型携带运行时字符串内容，因此完整 CH 不可行。

Gaia 采用的是 **两层 CH 对齐**：

| 层级 | CH 对齐 | Python 实现 |
|------|---------|------------|
| **类型层** | 命题类别区分 | `Claim` vs `Setting` vs `Question` 子类，type checker 可校验 |
| **类型层** | 推理是函数 | 策略签名 `(str, given: list[Claim]) -> Claim`，前提→结论 |
| **值层** | 不完整 | 命题内容 `content` 是运行时字符串，不是类型 |

这意味着 type checker 可以保证结构正确（Setting 不能当前提），但不能保证语义正确（���个 Claim 的内容是否逻辑一致）——后者由 BP 推理处理。

### 1.4 目标

- **Knowledge 子类化**：`Claim`、`Setting`、`Question` 成为独立类型，策略函数签名用类型约束前提和结论
- **策略返回 Claim**：结论是策略的产出物（返回值），不是输入参数
- **IR 不变**：改动限制在 DSL 层和编译器的 DSL→IR 转换逻辑，IR schema、BP 引擎、CLI 命令不受影响
- **向后兼容路径**：提供迁移期，旧写法通过 deprecation warning 过渡

---

## 2. 核心设计

### 2.1 Knowledge 类型层级

```python
@dataclass
class Knowledge:
    """知识声明基类。"""
    content: str
    label: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    parameters: list[dict] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class Claim(Knowledge):
    """科学断言 — 唯一携带概率、参与 BP 推理的类型。"""
    strategy: Strategy | None = None
    operator: Operator | None = None

@dataclass
class Setting(Knowledge):
    """背景上下文 — 无概率，不参与 BP。"""
    pass

@dataclass
class Question(Knowledge):
    """开放研究问题 — 不参与 BP。"""
    pass
```

类型校验效果：

```python
bg = Setting("Background")
a = Claim("Evidence")

deduction("Conclusion", given=[bg, a])
#                              ^^ mypy error: Setting is not Claim
```

### 2.2 策略函数签名：结论作为返回值

**改前：**

```python
def deduction(premises: list[Knowledge], conclusion: Knowledge, *,
              reason: str = "") -> Strategy
```

**改后：**

```python
def deduction(content: str, /, *, given: list[Claim],
              reason: str = "") -> Claim
```

- 第��个 positional 参数 `content: str` 是结论命题的内容
- `given` 替代 `premises`，类型从 `list[Knowledge]` 收窄为 `list[Claim]`
- 返回 `Claim`（结论），不再返回 `Strategy`
- `reason` 是推理论证，可以是多段长文本
- `Strategy` 对象在函数内部创建并通过 `__post_init__` 自动注册，用户不直接接触

### 2.3 所有策略函数的新签名

```python
# ── 通用策略 ──

def noisy_and(content: str, /, *, given: list[Claim],
              reason: str = "") -> Claim

def infer(content: str, /, *, given: list[Claim],
          reason: str = "") -> Claim

# ── 命名策略（编译时自动 formalize 为 FormalStrategy）──

def deduction(content: str, /, *, given: list[Claim],
              reason: str = "") -> Claim

def abduction(content: str, /, *, observation: Claim,
              reason: str = "") -> Claim

def analogy(content: str, /, *, source: Claim, bridge: Claim,
            reason: str = "") -> Claim

def extrapolation(content: str, /, *, source: Claim, continuity: Claim,
                  reason: str = "") -> Claim

def elimination(content: str, /, *, exhaustiveness: Claim,
                excluded: list[tuple[Claim, Claim]],
                reason: str = "") -> Claim

def case_analysis(content: str, /, *, exhaustiveness: Claim,
                  cases: list[tuple[Claim, Claim]],
                  reason: str = "") -> Claim

def mathematical_induction(content: str, /, *, base: Claim, step: Claim,
                           reason: str = "") -> Claim
```

### 2.4 Operator 函数（不变，已经返回 Claim）

Operator 函数当前已经返回 helper Claim，签名只需要收窄类型：

```python
def contradiction(a: Claim, b: Claim, *, reason: str = "") -> Claim
def equivalence(a: Claim, b: Claim, *, reason: str = "") -> Claim
def complement(a: Claim, b: Claim, *, reason: str = "") -> Claim
def disjunction(*claims: Claim, reason: str = "") -> Claim
```

### 2.5 内部实现

策略函数内部创建 `Claim` 和 `Strategy` 对象，通过 `__post_init__` 自动注册，返回 `Claim`：

```python
def deduction(content: str, /, *, given: list[Claim],
              reason: str = "") -> Claim:
    conclusion = Claim(content=content)
    strategy = Strategy(type="deduction", premises=list(given),
                        conclusion=conclusion, reason=reason)
    conclusion.strategy = strategy
    return conclusion
```

用户只看到 `Claim` 进 `Claim` 出。`Strategy` 是内部实现细节。

### 2.6 Claim 上的 operator 字段

新增 `Claim.operator` 字段，让 operator 产出的 claim 也能追溯来源：

```python
# operators.py
def contradiction(a: Claim, b: Claim, *, reason: str = "") -> Claim:
    helper = Claim(
        content=f"not_both_true({a.label or 'A'}, {b.label or 'B'})",
        metadata={"helper_kind": "contradiction_result"},
    )
    op = Operator(operator="contradiction", variables=[a, b],
                  conclusion=helper, reason=reason)
    helper.operator = op
    return helper
```

---

## 3. 使用示例

### 3.1 Galileo 落体（完整包）

```python
"""galileo_falling_bodies/knowledge.py — 直接断言的命题（公理）"""
from gaia.lang import Claim, Setting

aristotle = Setting("Aristotle's doctrine: heavier objects fall faster.")
heavy_faster = Claim("Heavy stones fall faster in air.")
composite_slower = Claim("Tied composite should be slower (light drags heavy).")
composite_faster = Claim("Tied composite should be faster (greater total mass).")
```

```python
"""galileo_falling_bodies/reasoning.py — 推导出来的命题（定理）"""
from gaia.lang import deduction, contradiction
from .knowledge import heavy_faster, composite_slower, composite_faster

paradox = contradiction(composite_slower, composite_faster,
    reason="Same Aristotelian premise yields opposite predictions")

vacuum_law = deduction(
    "In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster],
    reason="""
    Galileo's thought experiment: consider two stones, one heavy and one
    light. According to Aristotle, the heavy stone falls faster. Now tie
    them together into a composite.

    The composite is heavier than the heavy stone alone, so by Aristotle's
    principle it should fall faster. But the light stone, being slower,
    should drag the heavy one back, making the composite fall slower.

    The same object must fall both faster AND slower — a contradiction.
    Therefore Aristotle's premise is wrong, and in the absence of air
    resistance all bodies fall at the same rate.
    """,
)
```

```python
"""galileo_falling_bodies/__init__.py"""
from .knowledge import aristotle, heavy_faster, composite_slower, composite_faster
from .reasoning import paradox, vacuum_law

__all__ = [
    "aristotle", "heavy_faster", "composite_slower",
    "composite_faster", "paradox", "vacuum_law",
]
```

对比旧写法：

```python
# v5（旧）：conclusion 是输入参数，strategy 是返回值
c = claim("In vacuum all bodies fall at the same rate.")
s = deduction(premises=[paradox, heavy_faster], conclusion=c, reason="...")

# v6（新）：conclusion 是返回值，strategy 是内部细节
c = deduction("In vacuum all bodies fall at the same rate.",
              given=[paradox, heavy_faster], reason="...")
```

### 3.2 推理链（隐式 Composite）

```python
from gaia.lang import Claim, noisy_and

evidence_a = Claim("Experimental observation A.")
evidence_b = Claim("Experimental observation B.")

intermediate = noisy_and("Joint evidence is consistent.",
    given=[evidence_a, evidence_b])

conclusion = noisy_and("Main hypothesis confirmed.",
    given=[intermediate])

# evidence_a → intermediate → conclusion 的推理链
# 自动存在于对象图中，不需要显式 composite()
```

### 3.3 Review sidecar

```python
"""galileo_falling_bodies/reviews/self_review.py"""
from gaia.review import ReviewBundle, review_claim, review_strategy
from .. import heavy_faster, composite_slower, composite_faster, vacuum_law

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        # 直接断言的 Claim → 需要 prior
        review_claim(heavy_faster, prior=0.8,
            judgment="supporting",
            justification="Well-documented observation in air."),
        review_claim(composite_slower, prior=0.6,
            judgment="tentative",
            justification="Plausible under Aristotelian framework."),
        review_claim(composite_faster, prior=0.6,
            judgment="tentative",
            justification="Also plausible under Aristotelian framework."),
        # paradox (contradiction 产出) → 不需要 prior
        # vacuum_law (deduction 产出) → 不需要 prior
    ],
)
```

---

## 4. 编译器影响

### 4.1 不变的部分

- `__post_init__` 自动注册机制不变
- `importlib.import_module()` 发现机制不变
- IR schema (`LocalCanonicalGraph`, `Strategy`, `Knowledge`) 不变
- `ir.json` 输出格式不变

### 4.2 需要改的部分

| 模块 | 改动 |
|------|------|
| `gaia/lang/runtime/nodes.py` | Knowledge 拆为 Claim/Setting/Question 子类；Claim 新增 operator 字段 |
| `gaia/lang/dsl/strategies.py` | 所有策略函数改签名（content 第一参数，given 替代 premises，返回 Claim） |
| `gaia/lang/dsl/operators.py` | 类型标注从 Knowledge 收窄为 Claim |
| `gaia/lang/dsl/knowledge.py` | `claim()` 返回 `Claim`，`setting()` 返回 `Setting`，`question()` 返回 `Question` |
| `gaia/lang/compiler/compile.py` | 适配子类：`isinstance(k, Claim)` 替代 `k.type == "claim"` |
| `gaia/lang/__init__.py` | 导出新类型 |

### 4.3 IR 映射

| DSL (v6) | IR (不变) |
|----------|----------|
| `Claim(content="X")` | `Knowledge(id="...", type="claim", content="X")` |
| `Setting(content="X")` | `Knowledge(id="...", type="setting", content="X")` |
| `deduction("C", given=[a,b])` 返回的 Claim | `Knowledge(type="claim")` + `Strategy(type="deduction", premises=[...], conclusion=...)` |

编译器将 DSL 的 `Claim`/`Setting`/`Question` 统一映射到 IR 的 `Knowledge(type=...)`，IR 层无需区分子类。

---

## 5. 向后兼容

### 5.1 迁移策略

**Phase 1（本次）**：新 API 实现，旧 API 保留但标记 deprecated。

```python
# 旧写法 — 仍然工作，发出 deprecation warning
c = claim("C")
s = deduction(premises=[a, b], conclusion=c)

# 新写法
c = deduction("C", given=[a, b])
```

**Phase 2（后续）**：移除旧 API。

### 5.2 检测旧写法

当 `deduction()` 收到 `conclusion=` 参数时，触发 `DeprecationWarning` 并走旧代码路径：

```python
def deduction(
    content: str | None = None,
    /,
    *,
    given: list[Claim] | None = None,
    # deprecated
    premises: list[Knowledge] | None = None,
    conclusion: Knowledge | None = None,
    reason: str = "",
) -> Claim:
    if conclusion is not None:
        warnings.warn("conclusion= is deprecated, use positional content", DeprecationWarning)
        # 旧路径
        ...
    # 新路径
    ...
```

---

## 6. 未来扩展（不在本次范围）

以下设计方向已讨论但推迟到后续迭代：

- **装饰器语法**：`@claim(deduction, given=[...]) def vacuum_law(): ...`，函数名自动成为 label，docstring 提供 content（第一段）和 reason（其余段落），`return Claim(...)` 提供结构化元数据
- **Currying**：`derive = deduction(given=[a, b])` 返回 Derivation 对象，`c = derive("C")` 完成推导。装饰器本质上就是 currying 的语法糖
- **结构化 reason**：reason 字段支持 Step 列表、Markdown、引用等结构化格式。长 reason 在装饰器模式下可以放在 docstring 里
- **完整 Claim 子类型化**：进一步区分 AxiomClaim（直接断言）和 DerivedClaim（策略产出），编码更多 CH 层级信息

---

## 7. 测试计划

| 测试 | 验证内容 |
|------|---------|
| 类型校验 | Setting 不能传入 `given=`；Question 不能作为结论 |
| 策略返回 Claim | `deduction("C", given=[a])` 返回 Claim，`.strategy` 已设置 |
| 编译一致性 | 新 DSL 编译出的 `ir.json` 与旧 DSL 完全相同 |
| 推理链 | 链式 `noisy_and` 自动形成对象图，`gaia infer` 结果正确 |
| 向后兼容 | 旧写法 `deduction(premises=[a], conclusion=c)` 发出 warning 但正常工作 |
| Review | 策略产出的 Claim 不要求 PriorRecord |
| E2E | Galileo 例子端到端：compile → check → infer → beliefs.json |
