# v6 Phase 1: gaia.lang 重构 — Knowledge 子类化 + Support 继承树

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | gaia.lang runtime + DSL |
| 前置 | 无 |
| 非目标 | Runnable（Phase 2）、Package 结构（Phase 3） |

---

## 1. 目标

重构 `gaia.lang`，解决 v5 的两个结构性问题：

1. `Knowledge` 是扁平的 `type: str` 区分——没有类型安全
2. `Strategy` 是扁平的 `type: str` 区分——不同 family 的语义角色靠 premises 列表下标约定

重构后：

- `Knowledge` 子类化为 `Claim` / `Setting` / `Question`
- `Strategy` 改名为 `Support`，子类化为完整继承树
- 所有 support 构造器返回 `Claim`（Claim in, Claim out）

---

## 2. Knowledge 子类化

### 2.1 现状（v5）

```python
@dataclass
class Knowledge:
    content: str
    type: str  # "claim" | "setting" | "question"
    ...
    strategy: Strategy | None = None
```

所有节点共用一个类，`type` 字段区分。DSL 函数签名写 `list[Knowledge]`，无法在类型层面区分 claim 和 setting。

### 2.2 目标（v6）

```python
@dataclass
class Knowledge:
    """基类：所有知识节点的共同字段"""
    content: str
    title: str | None = None
    background: list[Knowledge] = field(default_factory=list)
    provenance: list[dict[str, str]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    label: str | None = None


@dataclass
class Claim(Knowledge):
    """可被支撑、反驳、携带 prior/posterior 的命题"""
    support: Support | None = None
    parameters: list[dict] = field(default_factory=list)


@dataclass
class Setting(Knowledge):
    """背景假设，不参与 BP"""
    pass


@dataclass
class Question(Knowledge):
    """研究问题，不参与 BP"""
    pass
```

关键变化：

- `support` 只在 `Claim` 上（Setting/Question 不需要）
- `parameters` 只在 `Claim` 上（用于 universal claims 的参数化）
- DSL 签名可以收窄：`given: list[Claim]`（而非 `list[Knowledge]`）
- `background` 保留在基类上（所有节点都可以有背景引用）

### 2.3 `type` 字段的处理

Phase 1 保留 `type` 字段用于序列化/IR lowering 兼容：

```python
class Claim(Knowledge):
    type: str = "claim"   # 固定值，用于序列化

class Setting(Knowledge):
    type: str = "setting"

class Question(Knowledge):
    type: str = "question"
```

后续版本可以用 `isinstance()` 替代 `type` 字段检查。

---

## 3. Support 继承树

### 3.1 现状（v5）

```python
@dataclass
class Strategy:
    type: str  # "deduction" | "abduction" | "noisy_and" | ...
    premises: list[Knowledge]
    conclusion: Knowledge | None
    ...
    sub_strategies: list[Strategy]
```

所有 strategy 共用一个类，`type` 字段区分。不同 family 的语义角色（如 abduction 的 observation/alternative）靠 premises 列表下标约定。

### 3.2 目标（v6）

```
Support (base)
├── Formal
│   ├── Deduction
│   ├── Abduction              # observation, alternative
│   ├── Analogy                # source, bridge
│   ├── Extrapolation          # source, continuity
│   ├── Elimination            # exhaustiveness, excluded
│   ├── CaseAnalysis           # exhaustiveness, cases
│   └── MathInduction          # base, step
├── Infer
│   └── NoisyAnd
└── Composite                  # sub_supports
    └── Induction              # sub_supports 全是 Abduction
```

### 3.3 类定义

```python
@dataclass
class Support:
    """基类"""
    premises: list[Claim]
    conclusion: Claim
    background: list[Knowledge] = field(default_factory=list)
    reason: ReasonInput = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Formal ---

@dataclass
class Formal(Support):
    pass

@dataclass
class Deduction(Formal):
    pass

@dataclass
class Abduction(Formal):
    observation: Claim = None
    alternative: Claim | None = None

@dataclass
class Analogy(Formal):
    source: Claim = None
    bridge: Claim = None

@dataclass
class Extrapolation(Formal):
    source: Claim = None
    continuity: Claim = None

@dataclass
class Elimination(Formal):
    exhaustiveness: Claim = None
    excluded: list[tuple[Claim, Claim]] = field(default_factory=list)

@dataclass
class CaseAnalysis(Formal):
    exhaustiveness: Claim = None
    cases: list[tuple[Claim, Claim]] = field(default_factory=list)

@dataclass
class MathInduction(Formal):
    base: Claim = None
    step: Claim = None


# --- Infer ---

@dataclass
class Infer(Support):
    pass

@dataclass
class NoisyAnd(Infer):
    pass


# --- Composite ---

@dataclass
class Composite(Support):
    sub_supports: list[Support] = field(default_factory=list)

@dataclass
class Induction(Composite):
    """sub_supports 全是 Abduction"""
    pass
```

### 3.4 `claim.support` 基数与自动聚合

`claim.support` 单值。当同一个 Claim 被附加多条 support 时，自动聚合为 `Composite`：

```python
c = claim("C")
deduction(c, given=[a, b])              # c.support = Deduction(...)
induction(c, observations=[obs1, obs2]) # c.support 自动变为 Composite(sub_supports=[Deduction, Induction])
```

规则：

1. 第一次附加 → `claim.support = s`
2. 第二次附加 → `claim.support = Composite(sub_supports=[原 support, 新 support])`
3. 后续附加 → 追加到 `claim.support.sub_supports`

---

## 4. DSL 构造器

### 4.1 核心原则

**Claim in, Claim out。** 第一个参数可以是 `str`（创建新 Claim）或 `Claim`（附加 support 到已有 Claim）：

```python
# 模式 1：str → 创建新 Claim 并附加 support
c = deduction("C", given=[a, b])

# 模式 2：Claim → 附加 support 到已有 Claim（多条自动聚合为 Composite）
c = claim("C")
deduction(c, given=[a, b])
induction(c, observations=[obs1, obs2])
# c.support 现在是 Composite(sub_supports=[Deduction, Induction])
```

内部动作：

1. 若第一个参数是 `str` → 创建 Claim
2. 创建对应 Support 子类实例
3. 附加到 `claim.support`（多条自动聚合，见 §3.4）
4. 注册到 package
5. 返回 Claim

### 4.2 Knowledge 构造器

```python
def claim(content, *, title=None, given=None, background=None, parameters=None, provenance=None, **metadata) -> Claim
def setting(content, *, title=None, **metadata) -> Setting
def question(content, *, title=None, **metadata) -> Question
```

`claim(..., given=[...])` 内部创建 `NoisyAnd`。

### 4.3 Formal 构造器

所有第一参数类型为 `str | Claim`：

```python
def deduction(target, /, *, given: list[Claim], ...) -> Claim
def abduction(target, /, *, observation: Claim, alternative: Claim | None = None, ...) -> Claim
def induction(target, /, *, observations: list[Claim], alternatives: list[Claim | None] | None = None, ...) -> Claim
def analogy(target, /, *, source: Claim, bridge: Claim, ...) -> Claim
def extrapolation(target, /, *, source: Claim, continuity: Claim, ...) -> Claim
def elimination(target, /, *, exhaustiveness: Claim, excluded: list[tuple[Claim, Claim]], ...) -> Claim
def case_analysis(target, /, *, exhaustiveness: Claim, cases: list[tuple[Claim, Claim]], ...) -> Claim
def mathematical_induction(target, /, *, base: Claim, step: Claim, ...) -> Claim
```

`induction()` 内部创建 `Induction(Composite)` 实例，sub_supports 全是 Abduction。

### 4.4 Infer 构造器

```python
def noisy_and(target, /, *, given: list[Claim], ...) -> Claim
def infer(target, /, *, given: list[Claim], ...) -> Claim
```

### 4.6 Operator（不变）

`contradiction()` / `equivalence()` / `complement()` / `disjunction()` 保持 v5 语义不变。

---

## 5. Review

### 5.1 rename

- `review_strategy()` → `review_support()`
- `StrategyReview` → `SupportReview`
- `review_claim()` 不变
- `review_generated_claim()` 不变

### 5.2 review_support() dispatch

| Support 子类 | reviewer 怎么评估 |
|-------------|------------------|
| Formal | judgment + justification（不直接给 cp） |
| Infer / NoisyAnd | conditional probability |
| Composite | 递归 review 各条 sub_support |

---

## 6. v5 兼容

### 6.1 双入口

Phase 1 继续接受 v5 调用形式，发出 `DeprecationWarning`：

```python
# v5（继续可用）
c = claim("C")
s = deduction(premises=[a, b], conclusion=c)  # → DeprecationWarning

# v6（推荐）
c = deduction("C", given=[a, b])
```

### 6.2 属性别名

```python
claim.strategy  # → claim.support 的别名
Knowledge.type  # 保留，用于序列化兼容
```

### 6.3 迁移工具

`gaia migrate v5-to-v6` CLI，机械化转换：

| v5 | v6 |
|----|-----|
| `c = claim("C"); deduction([a,b], c)` | `c = deduction("C", given=[a, b])` |
| `c = claim("C"); abduction(obs, c, alt)` | `c = abduction("C", observation=obs, alternative=alt)` |
| `review_strategy(s, ...)` | `review_support(s, ...)` |
| `c.strategy` | `c.support` |

---

## 7. 不在本阶段做的事

- Runnable（execute / check / formal_proof）→ Phase 2
- Package 结构重组（gaia/ 目录）→ Phase 3
- IR protected contract 修改
- Execution 真正执行
