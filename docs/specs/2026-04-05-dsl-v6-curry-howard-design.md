# Gaia DSL v6: 从第一性原理出发的设计

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |

---

## 1. 三条第一性原理

### 1.1 Jaynes：概率是逻辑的扩展

每个命题都有一个信念度（degree of belief），取值 [0, 1]。信念的更新遵循概率规则（Bayes' theorem），而非布尔逻辑。确定性逻辑是概率的特例（P=0 或 P=1）。

**对 Gaia 的推论**：每个科学命题（Claim）携带概率。推理结构（Strategy）决定了信念如何在命题之间传播。BP 是执行 Jaynes 框架的计算引擎。

### 1.2 Curry-Howard：命题即类型，证明即程序

在类型论中：
- 命题是类型
- 证明是该类型的居民（值）
- 蕴含 A → B 是函数类型
- 构造一个 A → B 的函数 = 证明了 A 蕴含 B

**对 Gaia 的推论**：知识节点应该是类型（class），推理应该是函数（callable），推理的产物应该是返回值。

### 1.3 Python：万物皆对象

Python 中每个值都有类型（class）。class 本身也是对象（type 的实例）。函数是对象。模块是对象。数据是对象。一切都可以被引用、传递、内省。

**对 Gaia 的推论**：任何 Python 对象都可以成为知识节点。不需要手动把代码"翻译"成字符串——对象本身就是知识的载体。

---

## 2. 从原理推导出的设计

### 2.1 命题的四种存在方式

从三条原理出发，Python 中的命题（Claim）有四种来源，每种有不同的 proof：

```
                        有 proof                    无 proof
                ┌─────────────────────┐    ┌──────────────────┐
                │                     │    │                  │
  声明式       │  ③ 逻辑推导          │    │  ① 纯断言        │
  (content     │  deduction(...)      │    │  class X(Claim)  │
   已知)       │  proof = 推理结构    │    │  proof = 无      │
                │                     │    │                  │
                ├─────────────────────┤    ├──────────────────┤
                │                     │    │                  │
  计算式       │  ④ 工具调用          │    │  ② 代码即证明    │
  (content     │  toolcall(fn, ...)   │    │  class M(Claim): │
   由程序      │  proof = 外部计算    │    │    def f(self)... │
   产生)       │                     │    │  proof = 代码    │
                │                     │    │                  │
                └─────────────────────┘    └──────────────────┘
```

#### ① 纯断言（公理）

命题直接声明，没有 proof。信念完全来自 reviewer 赋的 prior。

```python
class heavy_faster(Claim):
    """Heavy stones fall faster in air."""
```

这是 CH 中的**公理**：假设类型存在，不需要构造居民。在 Gaia 中，reviewer 赋 `prior=0.8` 表达信念度。

#### ② 代码即证明

命题由 Python class 承载。class 的存在和正确行为本身就是 proof。

```python
class NewtonianGravity(Claim):
    """F = G * m1 * m2 / r^2"""
    G = 6.674e-11

    def force(self, m1: float, m2: float, r: float) -> float:
        return self.G * m1 * m2 / r**2
```

这是 CH 中的**类型即命题**：class 定义声明了命题（"牛顿引力按 F=Gm1m2/r² 计算"），代码能运行就是 proof of computability。注意：代码能跑 ≠ 科学上正确，所以仍然需要 reviewer 赋 prior 表达信任度。

任何已有的 Python 对象也可以包装成 Claim：

```python
gravity = Claim(NewtonianGravity)       # 外部 class
compute = Claim(compute_gravity)        # function
data = Claim(experimental_dataframe)    # 数据
```

`Claim()` 接受任意 Python 对象：`str` → 用作 content；其他 → 取 `__doc__` 作 content，对象存入 metadata。

#### ③ 逻辑推导（定理）

命题由推理策略从已有命题推导出来。策略函数是 `list[Claim] → Claim` 的函数。

```python
vacuum_law = deduction(
    "In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster],
    reason="Contradiction in Aristotle's doctrine forces a new law",
)
```

这是 CH 中的**函数调用即证明构造**：`deduction(given=[a, b])` 接受前提，返回结论。返回值是 Claim 实例——它被"构造"出来了，有 proof（推理结构）。

#### ④ 工具调用

命题由外部计算产生。工具函数也是 `list[Claim] → Claim`，但内部执行外部程序。

```python
drag = toolcall(cfd_simulation, given=[reynolds, geometry])
```

声明时产出 helper Claim（占位），`gaia run` 执行工具后填充实际 content。这和 `contradiction` 产出 helper Claim 的模式完全对称。

### 2.2 四种命题的统一视角

四种来源不同，但在知识图谱中的身份相同：**都是 Claim 节点**。区别仅在于：

| 来源 | content 来源 | proof | 信念来源 |
|------|-------------|-------|---------|
| ① 纯断言 | 作者写的字符串 | 无 | reviewer prior |
| ② 代码即证明 | class docstring | 代码能跑 | reviewer prior（信任代码的程度） |
| ③ 逻辑推导 | 作者写的字符串 | 推理结构（Strategy） | BP 从前提传播 |
| ④ 工具调用 | 工具产出（运行后填充） | 外部计算 | reviewer 对工具的信任度 + BP |

BP 不关心 proof 的种类——它只看 factor graph 的拓扑结构和参数。

### 2.3 Knowledge 类型层级

CH 要求类型级别区分命题的类别。Gaia 有三种知识类别，只有 Claim 参与推理：

```python
class Knowledge:
    """知识声明基类。"""
    content: str
    label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

class Claim(Knowledge):
    """科学断言 — 携带概率，参与 BP 推理。"""
    strategy: Strategy | None = None    # 推理策略（如果是推导出来的）
    operator: Operator | None = None    # 逻辑算子（如果是算子产出的）

class Setting(Knowledge):
    """背景上下文 — 无概率，不参与 BP。"""
    pass

class Question(Knowledge):
    """开放研究问题 — 不参与 BP。"""
    pass
```

Type checker 保证 Setting 和 Question 不能参与推理：

```python
deduction("C", given=[Setting("bg"), Claim("a")])
#                      ^^^^^^^ mypy error: Setting is not Claim
```

### 2.4 推理函数：Claim → Claim

CH 说推理（蕴含）是函数。所以策略函数的签名是 `(str, given: list[Claim]) → Claim`：

```python
def deduction(content: str, /, *, given: list[Claim], reason: str = "") -> Claim
def noisy_and(content: str, /, *, given: list[Claim], reason: str = "") -> Claim
def abduction(content: str, /, *, observation: Claim, reason: str = "") -> Claim
def analogy(content: str, /, *, source: Claim, bridge: Claim, reason: str = "") -> Claim
# ... 其他策略同理
```

逻辑算子也是 `Claim → Claim`，产出 helper Claim：

```python
def contradiction(a: Claim, b: Claim, *, reason: str = "") -> Claim
def equivalence(a: Claim, b: Claim, *, reason: str = "") -> Claim
def disjunction(*claims: Claim, reason: str = "") -> Claim
```

工具调用同理：

```python
def toolcall(tool: Callable[..., Claim], /, *, given: list[Claim], reason: str = "") -> Claim
```

**统一模式**：所有产出新 Claim 的操作都是 `Claim → Claim` 的函数。Strategy/Operator 是内部实现细节，用户只看到 Claim 进 Claim 出。

### 2.5 公理 vs 定理的语法区分

CH 中公理（假设存在）和定理（由证明构造）有根本区别。新 DSL 让语法反映这个区别：

```python
# 公理：class 声明（类型存在即可，不需要构造实例）
class heavy_faster(Claim):
    """Heavy stones fall faster in air."""

# 代码即证明：class 声明 + 实现
class NewtonianGravity(Claim):
    """F = G * m1 * m2 / r^2"""
    def force(self, m1, m2, r): ...

# 定理：由策略函数构造（函数调用 = 证明构造）
vacuum_law = deduction("In vacuum all fall at same rate.",
    given=[paradox, heavy_faster])

# 工具产出：helper Claim（工具执行 = 证明）
drag = toolcall(cfd_simulation, given=[reynolds, geometry])
```

读代码就能看出每个命题的认识论地位——不需要追踪 Strategy 引用。

### 2.6 推理链即调用链

CH 中复合证明是函数组合。在新 DSL 中，推理链就是函数调用的链：

```python
evidence = Claim("Experimental observation.")
intermediate = noisy_and("Evidence supports mechanism.", given=[evidence])
conclusion = deduction("Final theory.", given=[intermediate, background])

# evidence → intermediate → conclusion
# 推理链自动编码在对象图中，不需要显式 composite()
```

`fold_composite_to_cpt()` 可以在需要时计算任意子图的聚合 CPT。

### 2.7 CH 在 Python 中的边界

Python 没有 dependent type，因此 CH 对齐是**两层**的：

| 层级 | 对齐的 | 不对齐的 |
|------|--------|---------|
| 类型层 | `Claim` vs `Setting` vs `Question` 的区分；`list[Claim] → Claim` 的函数签名 | 具体命题内容不是类型（"F=ma" 是字符串，不是 type） |
| 值层 | 策略调用 = 证明构造；class 定义 = 命题声明 | 不能表达 "对所有 n, P(n) 成立"（需要 dependent type） |

type checker 保证结构正确（Setting 不能当前提）。语义正确性由 BP + review 处理。

---

## 3. 完整示例：Galileo 落体

```python
"""galileo_falling_bodies/knowledge.py — 公理和代码即证明"""
from gaia.lang import Claim, Setting

# ① 纯断言（公理）
class aristotle(Setting):
    """Aristotle's doctrine: heavier objects fall faster."""

class heavy_faster(Claim):
    """Heavy stones fall faster in air."""

class composite_slower(Claim):
    """Tied composite should be slower (light drags heavy)."""

class composite_faster(Claim):
    """Tied composite should be faster (greater total mass)."""

# ② 代码即证明
class GalileoModel(Claim):
    """All objects fall at the same rate: t = sqrt(2h/g)"""
    def predict(self, mass: float, height: float) -> float:
        return (2 * height / 9.81) ** 0.5
```

```python
"""galileo_falling_bodies/reasoning.py — 定理和工具调用"""
from gaia.lang import deduction, contradiction, toolcall
from .knowledge import heavy_faster, composite_slower, composite_faster, GalileoModel

# ③ 逻辑推导（定理）
paradox = contradiction(composite_slower, composite_faster,
    reason="Same Aristotelian premise yields opposite predictions")

vacuum_law = deduction(
    "In vacuum all bodies fall at the same rate.",
    given=[paradox, heavy_faster],
    reason="""
    Galileo's thought experiment: consider two stones, one heavy and one
    light. Tying them together yields a composite that must fall both
    faster (greater mass) and slower (light drags heavy) — contradiction.
    Therefore Aristotle's premise is wrong.
    """,
)

# ④ 工具调用
def drop_simulation(model: Claim, height: Claim) -> Claim:
    """Simulate dropping two objects from a height."""
    # ... actual computation ...
    return Claim("Both objects hit ground simultaneously.",
                 parameters={"delta_t": 0.001})

tower = Claim("Leaning Tower of Pisa, height = 56m")
experiment = toolcall(drop_simulation, given=[GalileoModel, tower])

confirmation = deduction(
    "Galileo's law confirmed by simulation.",
    given=[experiment, vacuum_law],
    reason="Simulation matches theoretical prediction",
)
```

```python
"""galileo_falling_bodies/reviews/self_review.py"""
from gaia.review import ReviewBundle, review_claim
from .. import heavy_faster, composite_slower, composite_faster, GalileoModel

REVIEW = ReviewBundle(
    source_id="self_review",
    objects=[
        # 纯断言 → 需要 prior
        review_claim(heavy_faster, prior=0.8),
        review_claim(composite_slower, prior=0.6),
        review_claim(composite_faster, prior=0.6),
        # 代码即证明 → 需要 prior（表达对代码的信任度）
        review_claim(GalileoModel, prior=0.95),
        # 推导出的 claim（paradox, vacuum_law, experiment, confirmation）→ 不需要 prior
    ],
)
```

---

## 4. 内部实现

### 4.1 Strategy/Operator 是内部对象

用户只看到 `Claim`。`Strategy` 和 `Operator` 在策略/算子函数内部创建，通过 `__post_init__` 自动注册到 CollectedPackage：

```python
def deduction(content: str, /, *, given: list[Claim], reason: str = "") -> Claim:
    conclusion = Claim(content=content)
    strategy = Strategy(type="deduction", premises=list(given),
                        conclusion=conclusion, reason=reason)
    conclusion.strategy = strategy
    return conclusion

def toolcall(tool: Callable[..., Claim], /, *, given: list[Claim], reason: str = "") -> Claim:
    helper = Claim(
        content=f"{tool.__name__}({', '.join(c.label or '?' for c in given)})",
        metadata={"helper_kind": "toolcall_result", "tool_fn": tool},
    )
    Strategy(type="toolcall", premises=list(given),
             conclusion=helper, reason=reason or tool.__doc__ or "")
    return helper
```

### 4.2 IR 层不变

编译器将 DSL 对象映射到 IR：

| DSL (v6) | IR (不变) |
|----------|----------|
| `class X(Claim)` | `Knowledge(type="claim", content=X.__doc__)` |
| `Claim(some_object)` | `Knowledge(type="claim", content=obj.__doc__)` + metadata |
| `Setting("X")` | `Knowledge(type="setting", content="X")` |
| `deduction("C", given=[a,b])` | `Knowledge(type="claim")` + `Strategy(type="deduction")` |
| `toolcall(fn, given=[a,b])` | `Knowledge(type="claim")` + `Strategy(type="toolcall")` |
| `contradiction(a, b)` | `Knowledge(type="claim")` + `Operator(operator="contradiction")` |

### 4.3 BP 层不变

Factor graph lowering 不关心命题的来源——只看拓扑结构。所有 Claim 都是变量节点，所有 Strategy/Operator 都是因子节点。

`toolcall` 在 lowering 时按 `noisy_and` 处理（reviewer 赋 `conditional_probability` 表达对工具的信任度）。

---

## 5. 向后兼容

旧写法通过检测 `conclusion=` 参数自动走旧路径并发出 DeprecationWarning：

```python
# 旧：仍然工作
c = claim("C")
s = deduction(premises=[a, b], conclusion=c)

# 新：推荐
c = deduction("C", given=[a, b])
```

---

## 6. 未来扩展（语法糖）

以下是语法层面的增强，不改变核心语义：

- **装饰器**：`@claim(deduction, given=[...]) def name(): """content"""`
- **Currying**：`derive = deduction(given=[a, b]); c = derive("C")`
- **结构化 reason**：Step 列表、Markdown、引用
- **`gaia run`**：执行 toolcall，填充 helper Claim 的实际 content

---

## 7. 测试计划

| 测试 | 验证内容 |
|------|---------|
| 类型校验 | Setting 不能传入 `given=`；Question 不能作为结论 |
| 纯断言 | `class X(Claim)` 注册为 knowledge node，content 取自 docstring |
| 代码即证明 | `class M(Claim): def f(self)...` 注册为 Claim，metadata 记录 class |
| Claim(obj) | `Claim(any_python_object)` 取 `__doc__` 作 content |
| 策略返回 Claim | `deduction("C", given=[a])` 返回 Claim，`.strategy` 已设置 |
| toolcall | `toolcall(fn, given=[a])` 返回 helper Claim |
| 推理链 | 链式调用自动形成对象图，`gaia infer` 结果正确 |
| 向后兼容 | 旧写法 `deduction(premises=[a], conclusion=c)` 发出 warning 但正常工作 |
| 编译一致性 | 新 DSL 编译出的 `ir.json` 与旧 DSL 结构相同 |
| E2E | Galileo 例子端到端：compile → check → infer → beliefs.json |
