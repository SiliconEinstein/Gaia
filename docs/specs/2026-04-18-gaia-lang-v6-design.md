# Gaia Lang v6 设计

> **Status:** Draft
>
> **Date:** 2026-04-18
>
> **Supersedes:** [2026-04-05-dsl-v6-support-witness-api-design.md](2026-04-05-dsl-v6-support-witness-api-design.md), [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md)
>
> **Scope:** Gaia Lang authoring DSL — Knowledge 类型体系、claim-first warranted reasoning API、参数化与谓词逻辑、InquiryState、Compute decorator
>
> **Non-goal:** 本文档不引入 Action IR 或额外调用层对象。v6 DSL 构造必须编译成 Gaia IR 的 Knowledge、Strategy、Operator、CompositeStrategy。

---

## 1. 设计目标

1. **Claim-first authoring**：作者先声明要讨论的 Claim，再用带 warrant 的 DSL 函数把 Claim 连接起来。Gaia Lang 不是 proof assistant 或 model checker，而是面向科学 Claim 的 probabilistic structured argumentation system。
2. **薄 Knowledge 类型体系**：Knowledge 作为基类（纯文本，无概率），Setting/Claim/Question 作为不同用途的知识对象；Claim 支持用户自定义子类作为参数化领域类型。
3. **无 Action IR / 无额外调用层**：`derive()`、`observe()`、`contradiction()`、`induction()` 等只是 DSL 层 constructor。编译后只保留 Gaia IR 的 Knowledge、Strategy、Operator、CompositeStrategy。
4. **只有 Compute 使用 decorator**：Compute 真正包装并执行 Python 函数体，因此保留 `@compute(...)`。Derive、Observe、Relate、Compose 不使用 decorator。
5. **参数化 Knowledge 与谓词逻辑**：通过 Claim 子类定义参数 schema（类型标注 + docstring 模板），Python 控制流实现 ∀ 展开，编译到 ground factor graph。
6. **InquiryState**：以导出 Claim 为 goal 的推理进度视图，通过 `gaia check --inquiry` 展示。
7. **IR-first 可编译性**：v6 每个 author-facing 构造都必须说明如何落到 Gaia IR。允许的最小 IR 扩展是 `Parameter.value`；不新增 Action 节点或额外调用层对象。

---

## 2. Knowledge 类型体系

### 2.1 类型层次

```
Knowledge              ← 纯文本背景知识，无概率，不进入推理图
├── Setting            ← 定义、环境条件、常量（无概率，taken as given）
├── Claim              ← 命题（有 prior，参与 BP）
│   └── 用户自定义子类 ← 参数化领域类型（如 Force, InfoTransfer）
└── Question           ← 开放探究（标记未解决问题，不是 Claim）
```

**四种类型，各有硬判定标准：**

| 类型 | 硬标准 |
|------|--------|
| Knowledge | 不进入推理图，纯文本 |
| Setting | 无概率，taken as given |
| Claim | 有概率，参与 BP |
| Question | 标记为开放探究 |

Hypothesis、theory、law、prediction、observation、fact、judgment 等不设为独立类型——它们是 Claim 在推理图中扮演的角色，由 support record（`derive`/`observe`/`compute`/`match`/`contradict` 等）决定，不由类型标签决定。例如同一个 Claim 可以同时被 observation（经验数据支持）和 derivation（理论推导支持）双重支持，不需要改变类型。

**参数化**：Setting/Claim/Question 都可以通过 class 继承定义参数化版本。class 定义谓词 schema，instance 是 ground formula：

```python
# class = 谓词定义（模板）
class Force(Claim):
    """Force is {value} N."""
    value: float

# instance = ground formula
Force(value=10.0)  # "Force is 10.0 N" — factor graph 中的一个变量
```

Python 的 class/instance 就是谓词逻辑的 predicate/formula，无需额外概念。

### 2.2 Knowledge 基类

纯文本知识，不进入推理图，不携带概率。用途：叙事性背景、包级/模块级 context。

```python
class Knowledge:
    content: str
    metadata: dict[str, Any] = {}
```

Package context 和 module context 通过专用类型定义——`PackageContext` 和 `ModuleContext` 是 Knowledge 的子类，编译器按类型识别：

```python
# __init__.py — 包级 context
from gaia.lang import PackageContext

context = PackageContext(
    "Planck's analysis of blackbody radiation spectrum (1900). "
    "Resolving the ultraviolet catastrophe by introducing energy quantization."
)

# observations.py — 模块级 context
from gaia.lang import ModuleContext

context = ModuleContext("Experimental measurements of blackbody spectrum.")
```

编译器校验：一个包只能有一个 PackageContext（在 `__init__.py`），一个模块只能有一个 ModuleContext。变量名任意，编译器按类型识别。

`gaia check` 输出时自动展示 context 层级：

```
Package: blackbody-radiation-gaia
  Context: Planck's analysis of blackbody radiation spectrum (1900)...

  Module: observations
    Context: Experimental measurements of blackbody spectrum.
    ...
```

### 2.3 Setting

定义性知识：环境条件、实验常量、规范引用。无概率，可作为 Strategy 的 `background` / `context` 参与解释，但不作为 BP 变量，也不作为 probabilistic premise。

```python
aashto = Setting("AASHTO LRFD Bridge Design Specifications, 9th Edition")
lab = Setting("Blackbody cavity experiment at thermal equilibrium")
```

### 2.4 Claim

命题，携带 `prior`，参与 BP 推理。

```python
class Claim(Knowledge):
    prior: float | None = None
```

**核心规则：每个导出或非独立 Claim 都需要 warrant**。warrant 由 `derive()`、`observe()`、`compute()`、relation、composition 等 DSL 函数提供。没有任何 Strategy / Operator 连接的裸 Claim 是 **structural hole**——即使在 priors.py 里赋了 prior 也不例外。prior 是对可信度的量化，warrant 是可信度的理由。二者缺一不可。

### 2.5 Claim 子类——参数化领域类型

用户通过继承 Claim 定义参数化的领域类型。class 定义 schema，docstring 是 `str.format()` 模板，类型标注定义参数：

```python
class CavityTemperature(Claim):
    """Cavity temperature is set to {value}K."""
    value: float

class TestFrequency(Claim):
    """Test frequency is {value} Hz."""
    value: float

class InfoTransfer(Claim):
    """Information can transfer from {src} to {dst}."""
    src: MoleculeType
    dst: MoleculeType
```

**class 定义 = 类型 schema**。实例化时绑定具体值，`content` 由 docstring 模板自动渲染：

```python
T = CavityTemperature(value=5000.0)
# T.content = "Cavity temperature is set to 5000.0K."
# T.parameters = [Param("value", type=float, value=5000.0)]

dna_to_rna = InfoTransfer(src=MoleculeType.DNA, dst=MoleculeType.RNA)
# dna_to_rna.content = "Information can transfer from DNA to RNA."
```

**部分绑定**（模板）：不传某个参数，该参数保持未绑定状态，可在后续 `bind()` 或 DSL 函数调用时绑定。

```python
# 未绑定——模板
info_transfer = InfoTransfer  # class 本身即模板
# 等价于 parameters=[Param("src", type=MoleculeType), Param("dst", type=MoleculeType)]

# 部分绑定
dna_transfer = InfoTransfer(src=MoleculeType.DNA)
# dst 未绑定
```

**实现**：`Knowledge.__init_subclass__` 或 metaclass 收集类型标注，生成 Param 列表。`__init__` 时用 `str.format(**bound_params)` 渲染 content。未绑定参数在 content 中保留 `{param_name}` 占位符。

### 2.6 Question

开放探究，标记未解决的问题。可参数化。

```python
class ProteinTransferQuestion(Question):
    """Can protein sequence information transfer to {dst}?"""
    dst: MoleculeType
```

### 2.7 Param dataclass

参数的内部表示：

```python
@dataclass
class Param:
    name: str
    type: type          # Python type/class（float, str, Enum 子类等）
    value: Any = UNBOUND  # sentinel，未绑定时不是 None
```

参数的 `type` 字段始终是 Python type/class。对于 Enum 类型，domain 自动从 `Enum.__members__` 获取。

---

## 3. Warranted Reasoning API

### 3.1 核心设计：Claim-first, IR-first

v6 不引入通用 reasoning decorator，也不引入额外调用层。`derive()`、`observe()` 等只是 DSL 层动词；编译后只剩 Gaia IR 对象：

| DSL 函数 | 语义 | IR 编译目标 |
|---------|------|------------|
| `derive(...)` | Claim premises 支持 Claim conclusion | `Strategy(type="support" / "deduction" / ...)` |
| `observe(...)` | 观测 warrant 支持观测 Claim | `Strategy(type="support")` 或 `Strategy(type="infer")` |
| `@compute(...)` | 执行 Python 函数并生成/支持 Claim | `Strategy(type="support")` + compute metadata |
| `match(...)` / `contradict(...)` | prediction-observation 比较 | `Operator(type="equivalence" / "contradiction")` + helper Claim |
| `contradiction(...)`, `equivalence(...)`, ... | Claim 间逻辑约束 | `Operator` + helper Claim |
| `abduction(...)`, `induction(...)`, `compose(...)` | 组合已有 Strategy | `CompositeStrategy` |

只有 `compute` 使用 decorator，因为它真的包装并执行 Python 函数体。`derive`、`observe`、relation、composition 都是普通函数调用。

### 3.2 derive

`derive()` 是最常用的支持边 constructor：作者显式声明 conclusion，再给出 premises、reason、prior。

```python
quantum_hyp = Claim("Energy exchange is quantized.")
planck_result = Claim("Planck spectrum matches blackbody observations.")
uv_data = Claim("Measured blackbody spectrum deviates from Rayleigh-Jeans law.")

s = derive(
    [planck_result, uv_data],
    conclusion=quantum_hyp,
    reason="Planck spectrum matches observed data and resolves UV catastrophe.",
    prior=0.95,
)
```

`derive()` 返回 Strategy handle，供 `induction()`、`abduction()`、`compose()` 等组合函数使用。一个 Claim 可以有多个 incoming Strategy。

**编译**：默认编译为 `Strategy(type="support")`。需要严格逻辑推导时可指定 strategy type：

```python
derive(
    [p, p_implies_q],
    conclusion=q,
    type="deduction",
    reason="By modus ponens: if P and P→Q, then Q.",
    prior=0.99,
)
```

### 3.3 observe

`observe()` 表示经验观测、测量、实验记录等 witness。观测对象必须是显式 Claim，实验条件、仪器、规范等放在 `context`。

```python
lab = Setting("Blackbody cavity at thermal equilibrium.")
spectrometer = Setting("Calibrated UV-visible spectrometer.")
uv_data = Claim("Measured blackbody spectrum deviates from Rayleigh-Jeans law.")

obs = observe(
    conclusion=uv_data,
    context=[lab, spectrometer],
    reason="Measured at 5 frequency points with calibrated UV-visible spectrometer.",
    prior=0.95,
)
```

如果观测依赖不确定的上游 Claim，把它们放入 `premises`：

```python
calibrated = Claim("The spectrometer calibration is within tolerance.")

observe(
    [calibrated],
    conclusion=uv_data,
    context=[lab],
    reason="Measured after calibration check.",
    prior=0.95,
)
```

**编译**：

- 有 Claim premises：编译为 `Strategy(type="support", premises=[...], conclusion=...)`，`context` 编译为 `background`。
- 无 Claim premises：编译为 `Strategy(type="infer", premises=[], conclusion=...)`，并为该 infer 策略提供单项 CPT `[prior]`。这使用现有 infer 语义，不新增 zero-premise support。

### 3.4 relations

Relation 不是 Strategy。它们是 Claim 间的确定性逻辑约束。

**Prediction-observation 比较**：`match()` 和 `contradict()` 是科学推理的核心操作——比较 prediction 和 observation 是否吻合：

```python
agreement = match(
    spectrum_prediction,
    spectrum_observation,
    reason="The predicted Planck spectrum agrees with measured data.",
    prior=0.93,
)

conflict = contradict(
    classical_prediction,
    observed_finite,
    reason="Classical theory predicts divergence, but observation reports finite radiation.",
    prior=0.96,
)
```

`match()` 编译为 `Operator(type="equivalence")`，`contradict()` 编译为 `Operator(type="contradiction")`。返回值是 helper Claim，可以作为其他 derive 的 premise（例如 `h.explains(evidence=[agreement])`）。

**其他逻辑约束**：

```python
contradiction(a, b, reason="...", prior=0.99)
equivalence(a, b, reason="...", prior=0.95)
complement(a, b, reason="...", prior=0.99)
disjunction([a, b, c], reason="...", prior=0.95)
implication(a, b, reason="...", prior=0.95)
```

**编译**：编译为 top-level `Operator`，并生成 helper Claim 承载 relation warrant prior。

`match`/`contradict` 和 `equivalence`/`contradiction` 的区别是语义意图，不是 IR 结构——前者用于 prediction-observation 比较，后者用于一般逻辑约束。编译到相同的 IR Operator。

### 3.5 compute

将 Python 函数包装为 executable witness。Compute 是唯一拥有实际函数体、也唯一使用 decorator 的 DSL 构造。

```python
@compute(output=SpectralRadiance, reason="Planck's analytical law.", prior=0.99)
def planck_spectrum(T: CavityTemperature, freq: TestFrequency) -> SpectralRadiance:
    """Planck's law: B(ν,T) = (2hν³/c²) · 1/(exp(hν/kT) - 1).
    Exact analytical formula, no approximation."""
    import math
    h, c, k = 6.626e-34, 3e8, 1.38e-23
    return (2 * h * freq**3 / c**2) / (math.exp(h * freq / (k * T)) - 1)

result = planck_spectrum(
    CavityTemperature(value=5000.0),
    TestFrequency(value=1e15)
)
# result 是 SpectralRadiance(value=...)，content 由模板自动渲染
```

**Decorator 职责**：

1. 检查函数签名中的类型标注
2. 调用时：从输入 Knowledge 的 parameters 中按名称提取 value
3. 用提取的 raw value 调用原始函数
4. 将返回值包装为返回类型标注指定的 Claim 子类
5. 注册 Strategy 连接输入 Knowledge → 输出 Claim
6. 在 Strategy metadata 中记录 `kind="compute"`、函数名、代码 hash、输入输出参数、source location

**对用户零侵入**：已有的 Python 函数加一行 `@compute(output=..., prior=...)` 即可。函数内部仍然操作 raw Python 值，不需要了解 Knowledge 系统。

**Compute 链式串联**：一个 Compute 的输出（Claim 子类）可以直接作为另一个 Compute 的输入，自动形成推理链。

### 3.6 composition

组合函数只接收已经创建的 Strategy handle，不接收 decorator、模板或函数对象。

```python
s1 = derive([law], conclusion=obs1, reason="law predicts obs1", prior=0.9)
s2 = derive([law], conclusion=obs2, reason="law predicts obs2", prior=0.9)

ind = induction(
    s1,
    s2,
    conclusion=law,
    reason="Independent observations confirm the same law.",
)
```

强语义组合（`abduction()`、`induction()`）优先使用命名函数；`compose()` 是低阶 escape hatch：

```python
compose(
    [s1, s2, s3],
    conclusion=target,
    type="infer",
    reason="These sub-arguments jointly establish the target.",
)
```

**编译**：编译为 `CompositeStrategy`，`sub_strategies` 引用子 Strategy 的稳定 ID。

### 3.7 Provenance and references

v6.0 的主路径是把已有科学文献或当前研究结果 formalize 成可推理的 Gaia epistemic graph。它不引入第二套 citation / provenance 模型，而是复用 Gaia 现有的 references and provenance pipeline。

`Claim.content` 和所有 warrant 文本都应该进入现有 refs resolver。warrant 文本包括 `derive(..., reason=...)`、`observe(..., reason=...)`、`@compute(..., reason=...)`、relation 的 `reason=...` 和 composition 的 `reason=...`。解析成功的 citation refs 与 referenced claims 写入既有 provenance metadata，例如 `metadata.gaia.provenance.cited_refs` 和 `metadata.gaia.provenance.referenced_claims`。

```python
uv_data = Claim(
    "Measured blackbody spectrum deviates from Rayleigh-Jeans law [@Planck1901]."
)

observe(
    conclusion=uv_data,
    context=[lab, spectrometer],
    reason="Figure 2 reports systematic deviation at high frequency [@Planck1901].",
    prior=0.95,
)
```

跨包和 imported claim 的 provenance 仍遵循现有 owner boundary：consumer package 可以引用 foreign claim，但不能把本地 citation 写回 foreign node。Bridge reason 可以被 validate；是否保留为 bridge-local provenance 是后续生态层问题，不改变 Gaia IR。

---

## 4. Warrant Review

### 4.1 Prior 的双层结构

| Prior | 谁设 | 含义 |
|-------|------|------|
| **Warrant prior**（DSL warrant 上的 `prior=`） | 作者 | 这条推理规则、观测方法、计算或关系声明的可靠度 |
| **Claim prior**（priors.py 中的值） | Reviewer | 这个命题本身的可信度 |

作者在 DSL 中设定 warrant prior，reviewer 审查 claim prior 和 warrant prior。两者独立：Claim prior 量化命题本身的先验可信度，warrant prior 量化“这条连接为什么成立”的可靠度。

编译后，warrant prior 总是挂在 Gaia IR 中已经存在的对象上：

| DSL warrant | 编译后 prior 位置 |
|-------------|------------------|
| `derive(...)` / `@compute(...)` / 有 premise 的 `observe(...)` | `Strategy.metadata["prior"]`，需要形式化时再传播到生成的 helper Claim |
| 无 premise 的 `observe(...)` | `Strategy(type="infer")` 的 `StrategyParamRecord(conditional_probabilities=[prior])` |
| `contradiction(...)` / `equivalence(...)` 等 relation | `Operator` 仍是确定性约束；不确定性由生成的 helper Claim 的 prior 承载 |
| `abduction(...)` / `induction(...)` / `compose(...)` | `CompositeStrategy.metadata["prior"]` 或 composition-validity helper Claim |

### 4.2 Warrant 导出

```bash
gaia check --warrants              # 带作者 prior（pre-filled）
gaia check --warrants --blind      # prior 留空（blank-slate）
```

**Pre-filled 模式**：导出所有 warrant target，带作者的 prior 预填。Reviewer 逐条确认或调整。

**Blank-slate 模式**：导出所有 warrant target，prior 留空。Reviewer 独立估计，避免锚定效应（anchoring bias）。

导出格式：

```python
# warrant_priors.py（gaia check --warrants 自动生成模板）
WARRANT_PRIORS = {
    # Pre-filled: target_id_or_alias: (author_prior, reviewer_justification)
    "strategy:planck_resolves_catastrophe": (0.95, ""),
    "strategy:uv_catastrophe_measurement":  (0.95, ""),
    "strategy:planck_spectrum":             (0.99, ""),
    "relation:energy_models_exclusive":     (0.99, ""),
}
```

模板里可以使用可读 alias；编译器最终解析为稳定 IR ID（`strategy_id`、`operator_id` 或 helper Claim ID）。Review 不依赖 Python 函数对象身份，因为 `derive()` / `observe()` / relation 本身不是函数定义，也没有可 import 的 warrant 对象。

### 4.3 Claim Prior 审查

Claim 的 prior 仍通过 priors.py 审查：

```python
# priors.py
from . import quantum_hyp, classical_hyp

PRIORS = {
    quantum_hyp:   (0.8, "Supported by multiple independent lines of evidence"),
    classical_hyp: (0.1, "Contradicted by blackbody spectrum observations"),
}
```

### 4.4 推理用的最终 prior

优先级链：`reviewer override > author default > structural default`

---

## 5. 参数化与谓词逻辑

### 5.1 Python 即谓词逻辑

Gaia 寄生在 Python 之上，直接利用 Python 的数据结构和控制流实现谓词逻辑：

- **Python `for`** = ∀（全称量化）
- **Python `if`** = 条件
- **Python 函数** = 参数化 schema
- **Python Enum** = 有限 domain

```python
class MoleculeType(str, Enum):
    DNA = "DNA"
    RNA = "RNA"
    PROTEIN = "protein"

class InfoTransfer(Claim):
    """Information can transfer from {src} to {dst}."""
    src: MoleculeType
    dst: MoleculeType

# Python for = ∀
for src, dst, name, evidence in confirmed_transfers:
    reported = Claim(f"{name} reports information transfer from {src} to {dst}.")

    obs = observe(
        conclusion=reported,
        context=[molecular_bio_lab],
        reason=f"{name}: {evidence}",
        prior=0.99,
    )

    derive(
        [reported],
        conclusion=InfoTransfer(src=src, dst=dst),
        reason=f"{name} confirmed by independent evidence",
        prior=0.99,
    )
```

### 5.2 编译：Template → Ground

编译时，所有参数化 Knowledge 展开为 ground instances。每个 ground instance 是 factor graph 里的一个普通变量。IR 层不保留 lifted template；它只看到 ground Knowledge 以及这些 Knowledge 上的 bound parameter metadata。

### 5.3 Domain 与 Grounding 覆盖率

对于 Enum 类型参数，domain 自动从 `Enum.__members__` 获取。`gaia check --inquiry` 显示 grounding 覆盖率：

```
Goal: info_transfer (exported, parameterized)
  Grounded: 4/9 bindings
  Ungrounded: 5 bindings
```

### 5.4 scope

v6 先支持单层 ∀（覆盖 90% 的科学推理场景）。嵌套量词、lifted inference 留给未来版本。

---

## 6. InquiryState

### 6.1 概念

InquiryState 是知识包的推理进度快照——以导出 Claim 为 goal，展示每个 goal 的依赖树、warrant 覆盖度、structural holes。

命名来源：科学探究（inquiry）的状态，与 Gaia 的概率认识论（Jaynes）一脉相承。

### 6.2 复用 `gaia check`

不引入新命令，扩展现有 `gaia check`：

```bash
gaia check                     # 现有：结构校验
gaia check --holes             # 现有：显示 holes
gaia check --inquiry           # 新增：goal-oriented InquiryState
gaia check --warrants          # 新增：导出 warrant 列表
gaia check --warrants --blind  # 新增：blank-slate 模式
gaia check --gate              # 新增：质量门控
```

### 6.3 InquiryState 输出

```
$ gaia check --inquiry

Package: blackbody-radiation-gaia
  Context: Planck's analysis of blackbody radiation spectrum (1900)...

━━━ Goal 1: quantum_hyp (exported) ━━━
  Status: WARRANTED (needs review)

  quantum_hyp ← derive:planck_resolves_catastrophe(planck_result, uv_data) [0.95]
  │  "Planck spectrum resolves UV catastrophe."
  │
  ├─ planck_result ← compute:planck_spectrum(T, freq) [0.99]
  │  "Planck's law: B(ν,T) = ..."
  │
  └─ uv_data ← observe:uv_catastrophe_measurement() [0.95]
     "Measured at 5 frequency points..."

  quantum_hyp ⊥ classical_hyp ← relation:energy_models_exclusive
     "Mutually exclusive models."

━━━ Summary ━━━
  Warranted claims:  2/2 goals have warrant chains
  Unwarranted:       0
  Reviewed warrants: 0/6
```

### 6.4 Hole 的两种类型

| 类型 | 含义 | 严重度 |
|------|------|--------|
| **Unwarranted** | Claim 没有任何 Strategy / Operator 连接（即使有 prior） | 结构性 hole |
| **Unreviewed** | 有 warrant 但 warrant prior 未被 reviewer 确认 | 审查 hole |

核心原则：**prior ≠ justification**。没有 warrant 的 Claim 是 hole，不管有没有 prior。

### 6.5 Quality Gate

可配置的质量门控标准，CI 可用：

```toml
# pyproject.toml
[tool.gaia.quality]
min_posterior = 0.7           # 导出 claim 最低后验
max_unreviewed_warrants = 0   # 不允许未审查 warrant
allow_holes = false           # 不允许 structural hole
```

```bash
gaia check --gate   # 检查是否满足质量标准
```

### 6.6 Deferred: inquiry trace

`gaia check --inquiry` 展示的是当前 epistemic graph 的状态：哪些导出 Claim 已经有 warrant，哪些 warrant 还没有 review，哪些 Claim 仍是 structural hole。它不是完整 discovery-history log。

Timeline、failed hypotheses、experiment planning、hypothesis revision、lab-notebook style notes、package-version evolution 等 inquiry trace 功能明确不在 v6.0 范围内。未来的 inquiry trace 层可以引用 Claim / Strategy / Operator 的 stable ID，但不应改变本文定义的 Gaia IR contract，也不应把历史过程误编译成 belief graph 里的 probabilistic premise。

---

## 7. 编译到 IR

v6 DSL 的所有构造都直接编译到 Gaia IR。这里的核心约束是：不新增 Action IR，不新增额外层级；作者写的是 Python DSL，编译产物仍然只有 Knowledge、Strategy、FormalStrategy、Operator、CompositeStrategy 和 parameterization records。

| v6 DSL | 编译目标 |
|--------|---------|
| `Knowledge(...)` | 不进入 IR（metadata only） |
| `Setting(...)` | IR Knowledge (type=setting) |
| `Claim(...)` / Claim 子类 | IR Knowledge (type=claim)，参数化实例记录 `parameters` |
| `Question(...)` | IR Knowledge (type=question) |
| `derive(...)` | `Strategy(type="support" / "deduction" / ...)`；需要形式化时展开为 `FormalStrategy + FormalExpr` |
| 有 premise 的 `observe(...)` | `Strategy(type="support", premises=[...], conclusion=...)`，`context` → `background` |
| 无 premise 的 `observe(...)` | `Strategy(type="infer", premises=[], conclusion=...)` + `StrategyParamRecord(conditional_probabilities=[prior])` |
| `@compute(...)` | 输出 Claim + `Strategy(type="support")` + `metadata.compute` |
| `match(...)` / `contradict(...)` | `Operator(type="equivalence" / "contradiction")` + helper Claim |
| `contradiction(...)` / `equivalence(...)` 等 relation | top-level `Operator` + helper Claim |
| `abduction(...)` / `induction(...)` / `compose(...)` | `CompositeStrategy(sub_strategies=[strategy_id, ...])` |
| Claim 子类实例化 | ground IR Knowledge + bound parameters |
| `for` 循环展开 | N 个 ground IR Knowledge + N 个 ground Strategy / Operator |
| `conclusion=` 多支持 | 多个 Strategy 指向同一个 IR Knowledge |
| `reason=` | `Strategy.steps` / `metadata`，relation 则进入 helper Claim / Operator metadata |
| warrant prior | `Strategy.metadata["prior"]`、`StrategyParamRecord` 或 helper Claim prior |

### 7.1 必需 IR 扩展

唯一建议的 schema 扩展是给 `Parameter` 增加 bound value：

```python
class Parameter(BaseModel):
    name: str
    type: str
    value: Any | None = None
```

原因：v6 的 Claim 子类是模板，实例化后需要把 `CavityTemperature(value=5000.0)`、`CavityTemperature(value=6000.0)` 这样的 ground binding 保留在 IR 中，供 coverage、render、review 和跨包匹配使用。未绑定模板不进入 ground inference；编译时只能输出 ground instances。

### 7.2 明确不做的 IR 扩展

- 不新增 Action 节点。
- 不新增额外调用层对象。
- 不新增 `observe` strategy type。
- 不新增 zero-premise support。无 premise 的 `observe()` 编译为现有 `infer`，因为 `infer` 的 CPT 长度是 `2^k`，当 `k=0` 时自然是单项 `[prior]`。

### 7.3 稳定 ID 与 review key

`gaia check --warrants` 可以输出可读 alias，但最终必须解析到 IR stable ID。实现上可以把 Python 变量名、函数名、source location、reason hash 等 traceability 信息放进 `metadata`，不需要扩展 IR schema。多个 warrant 即使 premise/conclusion 相同，也必须通过 source trace 或显式 alias 区分，避免 review 时合并成同一项。

---

## 8. v5 → v6 迁移

### 8.1 术语对照

| v5 | v6 | 说明 |
|----|-----|------|
| `claim("...")` | `Claim("...")` 或自定义子类 | 大写，class 风格 |
| `setting("...")` | `Setting("...")` | 大写 |
| `question("...")` | `Question("...")` | 大写 |
| `support([a], b, prior=0.9)` | `derive([a], conclusion=b, prior=0.9)` | 普通函数调用 |
| `deduction([a], b)` | `derive([a], conclusion=b, type="deduction", prior=0.99)` | 普通函数调用 + type 参数 |
| `contradiction(a, b)` | `contradiction(a, b, reason=..., prior=...)` 或 `contradict(a, b, ...)` | relation 函数 |
| `equivalence(a, b)` | `equivalence(a, b, reason=..., prior=...)` 或 `match(a, b, ...)` | relation 函数 |
| `noisy_and` | 废弃，用 `derive(..., type="support")` | 已在 v5 中废弃 |
| `review_claim(...)` | `priors.py` PRIORS dict | 已在 0.4.2 废弃 |
| `review_strategy(...)` | `warrant_priors.py` | Strategy / Operator / helper Claim stable ID 或 alias 作为 key |
| `composite(...)` | `compose(...)` / `abduction(...)` / `induction(...)` | 组合 Strategy handle |
| `fills(source, target)` | 保持不变 | 跨包 premise 桥接 |

### 8.2 兼容性

v5 的函数式 API（`claim()`, `support()`, `deduction()` 等）保留为 deprecated 兼容层，内部编译到与 v6 相同的 IR。新包应使用 v6 API。旧的 `support()` 可直接映射到 `derive(..., type="support")`；旧的 relation 函数语义保留，但 v6 明确它们不是 decorator。

---

## 9. 未来方向

以下功能明确不在 v6.0 范围内，留给未来版本：

1. **嵌套量词**：`∀x ∃y. P(x, y)` — 需要 Skolemization
2. **Lifted inference**：大 domain 不做 grounding，直接 lifted BP
3. **交互式 InquiryState**：类似 Lean 的 tactic REPL
4. **`gaia run` 执行协议**：Compute 函数的远程执行和 witness 持久化
5. **Formal proof / model checking witness**：用普通 witness 函数连接外部证明器或模型检查器；不新增 decorator，除非它确实需要包装可执行函数体并复用 `compute` 机制
6. **Reductio / retraction**：反证法和知识撤回语义
