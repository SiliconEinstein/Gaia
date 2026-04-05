# v6 Phase 2: Runnable 支持 — execute / check / formal_proof

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | gaia.lang Runnable 子树 |
| 前置 | Phase 1（Support 继承树 + Knowledge 子类化） |
| 非目标 | Package 结构（Phase 3）、execution 真正执行 |

---

## 1. 目标

在 Phase 1 的 Support 继承树上新增 `Runnable` 子树，支持三种"跑一个东西，拿结果当 Claim"的场景：

```
Support
├── Formal / Infer / Composite (incl. Induction)  (Phase 1)
└── Runnable                                       ← 本阶段新增
    ├── Execution
    ├── Check
    └── FormalProof
```

核心原则不变：**Claim in, Claim out。** 所有 Runnable 构造器返回 Claim。

---

## 2. Runnable 基类

```python
@dataclass
class Runnable(Support):
    """需要"跑一个东西"的 support 的共同父类"""
    estimated_duration: float | None = None  # 预估运行时长（秒）
    run_env: str | None = None               # 运行环境描述
```

共同特征：都有一个"要跑的东西"+ 运行相关的基础参数。

Phase 2 的 authoring 只声明 Runnable 结构，不真正执行。真正执行属于 `gaia run` pipeline（后续设计）。

---

## 3. 三个子类

三个子类区分语义意图——跑的结果主张什么：

### 3.1 Execution（描述性："计算得到了 X"）

```python
@dataclass
class Execution(Runnable):
    callable_ref: Callable | str = ""
    execution_backend: str | None = None  # python / shell / remote
```

构造器（第一参数统一为 `str | Claim`，与 Phase 1 所有构造器一致）：

```python
def execute(
    target: str | Claim, /, *,
    fn: Callable | str,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    execution_backend: str | None = None,
    estimated_duration: float | None = None,
    **metadata,
) -> Claim
```

示例：

```python
solver_validated = claim("该 CFD 求解器在低 Re 方腔流中已通过基准验证")

pressure = execute(
    "CFD 计算得到方腔内的压力场 P",
    fn=run_cfd,
    given=[geometry, bc, solver_validated],
)
```

### 3.2 Check（验证性："实现满足 Y"）

```python
@dataclass
class Check(Runnable):
    checker_ref: Callable | str = ""
    checker_args: dict[str, Any] = field(default_factory=dict)
```

构造器：

```python
def check(
    target: str | Claim, /, *,
    fn: Callable | str,
    given: list[Claim],
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    checker_args: dict[str, Any] | None = None,
    estimated_duration: float | None = None,
    **metadata,
) -> Claim
```

示例：

```python
suite_covers_target = claim("回归测试集覆盖了目标 Re 数范围")

solver_ok = check(
    "求解器在回归测试集上通过了所有精度检查",
    fn=run_regression_tests,
    given=[spec, suite_covers_target],
)
```

### 3.3 FormalProof（演绎性："定理 T 成立"）

```python
@dataclass
class FormalProof(Runnable):
    system: str = ""              # lean / coq / isabelle
    theorem_ref: str = ""         # e.g. "FluidLab.Stability.main"
    proof_args: dict[str, Any] = field(default_factory=dict)
```

构造器：

```python
def formal_proof(
    target: str | Claim, /, *,
    system: str,
    theorem_ref: str,
    given: list[Claim] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
    title: str | None = None,
    label: str | None = None,
    proof_args: dict[str, Any] | None = None,
    estimated_duration: float | None = None,
    **metadata,
) -> Claim
```

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

## 4. 关键设计决策

### 4.1 对推理有影响的假设必须是 Claim

不设"介于 Claim 和 metadata 之间"的灰色地带：

- 对推理有影响 → 必须是 `given` 中的 Claim（solver 已验证、测试集覆盖目标场景等）
- 纯 provenance → `support.metadata`（运行时长、文件路径、random seed、库版本等）

判定规则：

> 需要 review、复用或反驳 → Claim。纯记录 → metadata。

### 4.2 Runnable 通常不直接产出科学结论

`execute()` / `check()` / `formal_proof()` 产出的是中间 claim（result / validity / proof-backed），到达科学结论通常还需要 bridge：

```python
# execution 产出 result claim
pressure = execute(run_cfd, given=[geo, bc, validated], returns="得到压力场")

# bridge 连接到科学结论
match_criterion = claim("L2 误差 < 1% 即视为吻合")
conclusion = deduction(
    "模拟支持方腔流存在稳定涡结构",
    given=[pressure, match_criterion],
)
```

### 4.3 Review

`review_support()` 对 Runnable 子类的行为：reviewer 通过 review 前提 Claims 的 prior 来间接评估 Runnable support 的可信度。不需要为 Runnable 引入新的 review 机制。

---

## 5. 不在本阶段做的事

- execution 真正执行（属于 `gaia run`）
- execution cache / reproducibility protocol
- Runnable 的 IR protected contract
- Package 结构重组 → Phase 3
