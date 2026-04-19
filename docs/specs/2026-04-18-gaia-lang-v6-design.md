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
2. **薄 Knowledge 类型体系**：Knowledge 作为未分化文本兜底类型（无概率），Setting/Claim/Question 作为不同用途的知识对象；Warrant 是 Claim 子类，用来表示可审查的论证步骤；Claim 支持用户自定义子类作为参数化领域类型。
3. **无 Action IR / 无额外调用层**：`Claim.supported_by(...)`、`Claim.derived_from(...)`、`match()`、`contradict()`、`compute()` 等只是 DSL 层 constructor。编译后只保留 Gaia IR 的 Knowledge、Strategy、Operator 以及 metadata/provenance。
4. **只有 Compute 使用 decorator**：Compute 真正包装并执行 Python 函数体，因此保留 `@compute(...)`。Derive、Observe、Relate、Compose 不使用 decorator。
5. **参数化 Knowledge 与谓词逻辑**：通过 Claim 子类定义参数 schema（类型标注 + docstring 模板），Python 控制流实现 ∀ 展开，编译到 ground factor graph。
6. **InquiryState**：以导出 Claim 为 goal 的推理进度视图，通过 `gaia check --inquiry` 展示。
7. **IR-first 可编译性**：v6 每个 author-facing 构造都必须说明如何落到 Gaia IR。允许的最小 IR 扩展是 `Parameter.value`；不新增 Action 节点或额外调用层对象。

---

## 2. Knowledge 类型体系

### 2.1 类型层次

```
Knowledge              ← 未分化文本/叙事背景/兜底对象，无概率，不进入推理图
├── Setting            ← 定义、环境条件、常量（无概率，taken as given）
├── Claim              ← 命题（有 prior，参与 BP）
│   ├── Warrant        ← 论证步骤本身的可审查 claim（带 pattern）
│   └── 用户自定义子类 ← 参数化领域类型（如 Force, InfoTransfer）
└── Question           ← 开放探究（标记未解决问题，不是 Claim）
```

**核心类型各有硬判定标准：**

| 类型 | 硬标准 |
|------|--------|
| Knowledge | 不进入推理图，未分化文本 |
| Setting | 无概率，taken as given |
| Claim | 有概率，参与 BP |
| Warrant | Claim 子类，表示“这条支持/关系/计算步骤成立” |
| Question | 标记为开放探究 |

Hypothesis、theory、law、prediction、observation、fact、judgment 等不设为独立类型——它们是 Claim 在推理图中扮演的角色，由支持它的 `Warrant.pattern` 和 graph topology 决定，不由类型标签决定。例如同一个 Claim 可以同时被 observation pattern 和 derivation pattern 的 Warrant 支持，不需要改变类型。

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

未分化文本知识，不进入推理图，不携带概率。用途：叙事性背景、包级/模块级 context、尚未决定是否要提升为 Claim/Setting/Question 的文献材料。

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
    root_kind: Literal["assumption", "axiom", "source_fact", "imported_reviewed"] | None = None
    root_reason: str | None = None
```

**核心规则：每个导出或非独立 Claim 都需要 Warrant 或 explicit root declaration**。Warrant 由 `supported_by(...)`、`derived_from(...)`、`match()`、`contradict()`、`compute()` 等 DSL constructor 创建。没有 incoming Warrant、且没有 `root_kind` 的裸 Claim 是 **structural hole**——即使在 priors.py 里赋了 prior 也不例外。prior 是对可信度的量化，Warrant/root declaration 是可信度进入图的理由。二者缺一不可。

合法 root 只用于真正的推理起点：

```python
model_assumption = Claim(
    "The cavity is in thermal equilibrium.",
    root_kind="assumption",
    root_reason="Modeling assumption for Planck's derivation.",
)

imported_result = Claim(
    "The Stefan-Boltzmann law has been independently reviewed in package X.",
    root_kind="imported_reviewed",
)
```

Definitions、实验环境、常量和规范引用优先建模为 `Setting`。只有需要参与 BP 的命题性起点才使用 `root_kind`。

### 2.5 Warrant

`Warrant` 是 `Claim` 的子类，用来表示“某个论证步骤成立”。它不是新的 Gaia IR Knowledge type；编译到 IR 时仍是 `Knowledge(type="claim")`，只是带有 `metadata.kind = "warrant"` 和结构化属性。

```python
class Warrant(Claim):
    label: str | None = None
    pattern: str
    question: Question
    reason: str
    inputs: list[Claim] = []
    conclusion: Claim | None = None
    context: list[Setting] = []
```

`pattern` 表示 warrant 的论证模式，例如：

```text
observation, citation, prediction, derivation, computation,
match, contradict, induction, abduction, explanation,
generalization, elimination
```

`pattern` 是 Warrant 的属性，不是 Claim 类型。它记录这条 warrant 在当前论证图里的角色；同一个普通 Claim 后续可以被不同 pattern 的 Warrant 反复支持，而 Claim identity 不需要改变。

`question` 由编译器从 `pattern + inputs + conclusion` 自动生成，作者不手写。这个 Question 是给 reviewer 的审计问题，不参与 BP，也不是 support premise。`reason` 是作者对这个 Question 的回答，即当前 Gaia Lang 已有的 `reason+prior` 语义中的 `reason`。

Warrant prior 的语义是：在 `question` 所声明的审计问题上，reviewer 认为这个 warrant 成立的概率。对 support 类 warrant，它通常是条件化的："假设 inputs 为真，这个 reason 是否足以支持 conclusion？" 这与旧 review 流程里的 `conditional_prior` 对齐。

重要 warrant 应该由用户显式提供 `label`，以便后续引用、review 和 inquiry 展示。未显式标注时编译器可以生成稳定 label，但 published package 应优先使用可读 label。因为 Warrant 本身也是 Claim，后续 `supported_by(inputs=[...])` 可以直接把某个 relation Warrant 或 support Warrant 当作输入引用。

### 2.6 Claim 子类——参数化领域类型

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

### 2.7 Question

开放探究，标记未解决的问题。可参数化。

```python
class ProteinTransferQuestion(Question):
    """Can protein sequence information transfer to {dst}?"""
    dst: MoleculeType
```

Warrant 也会自动携带生成的 Question，用来定义 reviewer 应该估计哪个 prior。这类 generated Question 是审计表单的一部分，不是新的科学 claim，也不进入 BP。

### 2.8 Param dataclass

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

### 3.1 核心设计：Claim + Warrant + Relation

v6.0 的 authoring surface 只保留一组核心构造，加一个窄的确定性推导 shortcut：

| DSL surface | 语义 | IR 编译目标 |
|---------|------|------------|
| `claim.supported_by(...)` | 创建一个 `Warrant`，说明 inputs 如何支持 receiver Claim | `Warrant` claim + `Strategy(type="support")` |
| `claim.derived_from(...)` | 确定性推导 shortcut，返回 authoring `prior=1` 的 derivation Warrant | `Warrant(pattern="derivation")` + `Strategy(type="support")` |
| `match(a, b, ...)` | 创建一个 `Warrant`，说明两个 Claim 在当前论证中匹配 | `Operator(operator="equivalence")` + Warrant/helper Claim |
| `contradict(a, b, ...)` | 创建一个 `Warrant`，说明两个 Claim 在当前论证中冲突 | `Operator(operator="contradiction")` + Warrant/helper Claim |
| `compute(...)` / `@compute(...)` | 执行 Python 函数，生成输出 Claim 和 computation Warrant | 输出 Claim + Warrant claim + `Strategy(type="support")` + compute metadata |

不在 v6.0 主 surface 中暴露 `derive()`、`observe()`、`abduct()`、`induce()`、`explain()`、`compose()`，也不暴露 IR operator 名称 `equivalence()` / `contradiction()`。这些都可以在后续作为 sugar 或 advanced API 添加，但第一版保持一个核心：**Claim 由 Warrant 支持，Warrant 是可引用、可 review 的 Claim 子类**。

### 3.2 `Claim.supported_by`

`supported_by` 是通用 support API。receiver Claim 是 conclusion；`inputs` 是支持它的 Claim/Warrant；`pattern` 说明这条 warrant 的论证模式；`reason` 是作者给出的理由文本；`label` 给这条 warrant 一个可引用名字。`reason` 对 published Warrant 应该必填；`prior` 是可选作者默认值，reviewer 可以之后覆盖。

```python
claim.supported_by(
    *,
    inputs: list[Claim | Warrant],
    pattern: str,
    label: str | None = None,
    reason: str,
    prior: float | None = None,
    context: list[Setting] = [],
    source: Any | None = None,
) -> Warrant
```

```python
quantum = Claim("Energy exchange is quantized.")

finite_radiation = Claim("High-frequency blackbody radiation remains finite.")
w_prediction = finite_radiation.supported_by(
    inputs=[quantum],
    pattern="prediction",
    label="quantization_predicts_finite_high_frequency_radiation",
    reason="Quantized exchange suppresses ultraviolet divergence.",
    prior=0.94,
)
```

返回值是 `Warrant`：

```python
assert isinstance(w_prediction, Warrant)
assert w_prediction.pattern == "prediction"
assert w_prediction.conclusion is finite_radiation
assert w_prediction.inputs == [quantum]
```

Observation、citation、induction、abduction、explanation 等都用同一个 API 表达：

```python
observed_finite = Claim("High-frequency blackbody radiation is experimentally finite.")
w_observation = observed_finite.supported_by(
    inputs=[],
    pattern="observation",
    label="planck_1900_reports_finite_high_frequency_radiation",
    source=planck_1900,
    reason="Planck 1900 reports finite high-frequency blackbody measurements.",
    prior=0.95,
)

quantum.supported_by(
    inputs=[agreement, anomaly],
    pattern="explanation",
    label="quantization_explains_uv_anomaly",
    reason=(
        "The quantum prediction matches the finite observation, while the "
        "classical prediction contradicts it."
    ),
    prior=0.93,
)
```

**编译**：

```text
Warrant(...) -> IR Knowledge(type="claim", metadata.kind="warrant", metadata.pattern=..., metadata.reason=..., metadata.question_id=...)
Warrant.question -> IR Knowledge(type="question", metadata.generated=true, refs=...)
claim.supported_by(inputs=[...]) -> Strategy(type="support", premises=[warrant, *inputs], conclusion=claim)
```

把 Warrant 放进 premises 后，v6.0 不需要 zero-premise support：即使 observation/citation 没有普通 input Claim，也仍然有一个 observation/citation Warrant 作为 support premise。`source`、`context`、citation refs 和 source location 都进入 Warrant 的 metadata/provenance。

#### 自动生成 Warrant Question

每个 Warrant 都带一个由编译器生成的 Question。Question 的文本由 `pattern`、`inputs`、`conclusion` 和可选 `context` 派生，使用引用语义指向已有 Knowledge，而不是把 Claim 文本复制进字符串：

```python
w.question = generate_warrant_question(
    pattern=w.pattern,
    inputs=w.inputs,
    conclusion=w.conclusion,
    context=w.context,
)
```

示例模板：

| Pattern | 自动生成的审计 Question |
|---------|------------------------|
| `prediction` | "Assuming @input claims, is @conclusion a valid prediction?" |
| `observation` | "Does the cited source or observed record establish @conclusion?" |
| `derivation` | "Assuming @input claims, does the derivation support @conclusion?" |
| `explanation` | "Do @input warrants/claims make @conclusion a good explanation?" |
| `match` | "Do @a and @b match in the intended comparison context?" |
| `contradict` | "Can @a and @b not both be true in the intended context?" |
| `computation` | "Does the computation from @inputs correctly support @conclusion?" |

这里的 `@...` 表示引用语义：Question metadata 保存 referenced Knowledge/Warrant 的 stable ID，render 时再展示对应内容。Question 不参与 BP；它定义的是 Warrant prior 要回答的审计问题。`reason` 是作者对这个 Question 的回答，`prior` 是作者默认给出的 yes-probability，reviewer 可以覆盖。

#### `Claim.derived_from`

`derived_from` 是 v6.0 保留的窄 shortcut，用来表达作者认为没有概率强弱的确定性推导。它等价于 `supported_by(pattern="derivation", prior=1)`，但 API 不暴露 `pattern` 或 `prior` 参数。

```python
claim.derived_from(
    *,
    inputs: list[Claim | Warrant],
    label: str | None = None,
    reason: str,
    context: list[Setting] = [],
    source: Any | None = None,
) -> Warrant
```

```python
instance = Claim("YBCO satisfies P.")
law = Claim("For all in-scope cuprates, P holds.")
in_scope = Claim("YBCO is an in-scope cuprate.")

w_derivation = instance.derived_from(
    inputs=[law, in_scope],
    label="ybco_p_by_universal_instantiation",
    reason="Universal instantiation from the cuprate law.",
)
```

返回的 Warrant 固定为：

```python
assert w_derivation.pattern == "derivation"
assert w_derivation.prior == 1
```

`derived_from` 的 generated Question 仍然存在，例如：

```text
"Assuming @inputs, does the derivation support @conclusion?"
```

但它的 review 语义是 binary/structural：接受则保留 `prior=1`，不接受则应打回修改，或改写成普通 `supported_by(pattern="derivation", prior=...)` 来表达不确定的经验性支持。当前 Gaia Lang / IR validator 要求 compiled `metadata["prior"]` 遵守 Cromwell's rule，因此编译器持久化时把 fixed `1` 归一化为 `1-ε`；这是存储层约束，不改变 v6 authoring surface 的语义。

### 3.3 Relation wrappers

`match()` 和 `contradict()` 是用户侧 relation wrappers。它们返回 `Warrant`，因为 relation result 本身就是“这两个 Claim 的关系成立”的可审查 claim。

```python
match(
    a: Claim,
    b: Claim,
    *,
    label: str | None = None,
    reason: str,
    prior: float | None = None,
) -> Warrant

contradict(
    a: Claim,
    b: Claim,
    *,
    label: str | None = None,
    reason: str,
    prior: float | None = None,
) -> Warrant
```

```python
agreement = match(
    finite_radiation,
    observed_finite,
    label="quantum_prediction_matches_observed_finite_radiation",
    reason="The predicted finite high-frequency behavior matches the reported observation.",
    prior=0.93,
)

anomaly = contradict(
    classical_divergence,
    observed_finite,
    label="classical_prediction_contradicts_observed_finite_radiation",
    reason="Classical theory predicts divergence, but measured radiation is finite.",
    prior=0.96,
)
```

`match()` 生成 `Warrant(pattern="match")`，并 lower 到 Gaia IR 的 `Operator(operator="equivalence")`；`contradict()` 生成 `Warrant(pattern="contradict")`，并 lower 到 `Operator(operator="contradiction")`。raw IR operator constructor 不进入 v6.0 authoring surface。

### 3.4 compute

Compute 将 Python 函数的执行结果连接到推理图中。它是 v6.0 唯一保留的 decorator 方向，因为它真的包装并执行 Python 函数体；`@compute` decorator 是 `compute()` 函数的语法糖。

#### 3.4.1 底层结构：`compute()` 函数

```python
result = compute(
    fn=planck_spectrum_fn,          # 一个普通 Python callable
    inputs=[T, freq],               # 输入 Knowledge 列表
    conclusion=SpectralRadiance,    # 输出 Claim 类型（参数化子类）
    output_param="value",           # fn 返回值绑定到 conclusion 的哪个参数
    label="planck_spectrum_computation",
    reason="Planck's law: B(ν,T) = (2hν³/c²) · 1/(exp(hν/kT) - 1).",
    prior=0.99,
)
```

`compute()` 的职责：

1. 从每个 input Knowledge 的 bound parameters 中提取 raw value（默认要求 input 只有一个 bound value；复杂情况显式传 `extractors`）
2. 用提取的 raw value 调用 `fn`
3. 将返回值绑定到 `conclusion` 类型指定的 Claim 子类实例（默认绑定到 `output_param`）
4. 创建 `Warrant(pattern="computation", label=label, inputs=inputs, conclusion=result)`
5. 注册 Strategy 连接 `[warrant, *inputs] → 输出 Claim`
6. 在 Warrant / Strategy metadata 中记录函数名、代码 hash、输入输出参数、source location
7. 返回输出 Claim

`compute()` 返回输出 Claim。生成的 computation Warrant 由 `label` 稳定引用；需要直接操作 warrant 时，implementation 可以提供 unpack/handle API，但 v6.0 语义上只要求 label 可引用。

**编译**：编译为输出 Claim + `Warrant(pattern="computation")` + `Strategy(type="support", premises=[warrant, *inputs], conclusion=result)` + compute metadata。reason 文本来自 `reason` 参数（或 `fn.__doc__`）。

#### 3.4.2 语法糖：`@compute` decorator

```python
@compute(
    inputs={"T": CavityTemperature, "freq": TestFrequency},
    conclusion=SpectralRadiance,
    output_param="value",
    label="planck_spectrum_computation",
    prior=0.99,
)
def planck_spectrum(T: float, freq: float) -> float:
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

Decorator 做的事等价于：

```python
def planck_spectrum_fn(T: float, freq: float) -> float:
    ...

result = compute(
    fn=planck_spectrum_fn,
    inputs=[CavityTemperature(value=5000.0), TestFrequency(value=1e15)],
    conclusion=SpectralRadiance,
    output_param="value",
    label="planck_spectrum_computation",
    reason=planck_spectrum_fn.__doc__,
    prior=0.99,
)
```

Decorator 通过 decorator 参数声明 Knowledge binding，通过 Python 函数签名保留 raw-value 计算语义：
- `inputs={"T": CavityTemperature}` 说明调用时参数 `T` 必须是 `CavityTemperature` Claim 实例
- wrapper 从 `CavityTemperature(value=...)` 中提取 raw `value`，把 raw float 传给函数体
- `conclusion=SpectralRadiance` 和 `output_param="value"` 说明返回 raw value 如何包装成输出 Claim
- docstring → Warrant reason
- label → Warrant label / review key
- prior → decorator 参数

**对函数体零侵入**：函数内部仍然操作 raw Python 值，不需要了解 Knowledge 系统。需要声明的是 Gaia wrapper 如何把 Knowledge input/output 绑定到 raw Python 参数和值。

**Compute 链式串联**：一个 Compute 的输出（Claim 子类）可以直接作为另一个 Compute 的输入，自动形成推理链。

### 3.5 Deferred sugar

`derive()`、`observe()`、`h.predict()`、`claim.predicted_from()`、`induce()`、`abduct()`、`explain()`、`compose()` 都不进入 v6.0 core。它们可以在后续版本作为 `supported_by(...)` 的 sugar 或 advanced composition API 添加，但不能改变底层语义：

```python
p = Claim("High-frequency blackbody radiation remains finite.")
p.supported_by(
    inputs=[quantum],
    pattern="prediction",
    label="quantization_predicts_finite_radiation",
    reason="Quantized exchange suppresses ultraviolet divergence.",
)
```

任何 sugar 都必须展开为：

```text
new/existing Claim + Warrant(pattern=...) + Strategy/Operator
```

### 3.6 Provenance and references

v6.0 的主路径是把已有科学文献或当前研究结果 formalize 成可推理的 Gaia epistemic graph。它不引入第二套 citation / provenance 模型，而是复用 Gaia 现有的 references and provenance pipeline，具体对齐 [References & `@` Syntax Unification Design](./2026-04-09-references-and-at-syntax.md)。

`Knowledge.content`、`Claim.content`、`Warrant.reason` 和自动生成的 `Warrant.question.content` 都应该进入现有 refs resolver。解析成功的 citation refs 与 referenced claims 写入既有 provenance metadata：

```python
knowledge.metadata["gaia"]["provenance"] = {
    "cited_refs": ["Planck1901", "planck_1901_fig2_scan"],
    "referenced_claims": ["blackbody_data_claim"],
}
```

v6 surface 上有三类来源语义，分别复用现有通道：

| 来源 | 表达方式 | 编译结果 |
|------|----------|----------|
| 本包或 imported package 里的 claim / knowledge | `[@label]` 或 `@label` | `metadata["gaia"]["provenance"]["referenced_claims"]` |
| 论文、书、网页、数据集、软件、图表、实验日志、`artifacts/` 或其他包内材料 | package root 的 `references.json`，CSL-JSON dict-by-key；content / reason 里用 `[@key]` 或 `@key` 引用 | `metadata["gaia"]["provenance"]["cited_refs"]` |
| package-version source lineage | 现有 `Knowledge.provenance` / `claim(..., provenance=[...])` | IR `Knowledge.provenance: list[PackageRef]` |

因此，本地 artifact 不应该通过新的 v6 object 表达。若一个文件是 claim 的证据来源，就把它登记成 `references.json` 里的 CSL entry，再在 `Claim.content` 或 `Warrant.reason` 中引用。CSL 1.0.2 已支持 `figure`、`graphic`、`dataset`、`software`、`document`、`report`、`webpage` 等类型；`URL` 可以指向 DOI / 外部 URL，也可以指向 package-relative 文件路径。`metadata.figure` 仍然可以给 GitHub Pages / Wiki renderer 用来展示图片，但它是 presentation metadata，不是 provenance source of truth。

```json
{
  "Planck1901": {
    "type": "article-journal",
    "title": "On the Law of Distribution of Energy in the Normal Spectrum",
    "author": [{"family": "Planck", "given": "Max"}],
    "issued": {"date-parts": [[1901]]}
  },
  "planck_1901_fig2_scan": {
    "type": "figure",
    "title": "Scanned blackbody spectrum figure used for UV deviation extraction",
    "URL": "artifacts/planck_1901/fig2.png"
  },
  "planck_lab_log": {
    "type": "dataset",
    "title": "Digitized blackbody radiation measurements",
    "URL": "data/planck_lab_log.csv"
  }
}
```

```python
uv_data = Claim(
    "Measured blackbody spectrum deviates from Rayleigh-Jeans law "
    "[@Planck1901] [@planck_1901_fig2_scan]."
)

uv_data.supported_by(
    inputs=[],
    pattern="observation",
    label="planck_1901_reports_uv_deviation",
    context=[lab, spectrometer],
    reason=(
        "Figure 2 reports systematic deviation at high frequency "
        "[@planck_1901_fig2_scan]; the digitized table is [@planck_lab_log]."
    ),
    prior=0.95,
)
```

跨包和 imported claim 的 provenance 仍遵循现有 owner boundary：consumer package 可以引用 foreign claim，但不能把本地 citation 写回 foreign node。Bridge reason 可以被 validate；是否保留为 bridge-local provenance 是后续生态层问题，不改变 Gaia IR。

如果后续需要更严格的 artifact resolver，例如校验 package-relative path 是否存在、记录 checksum、或接入 storage `resources.json` / `attachments.json`，也应该作为现有 refs pipeline 的扩展，把结果写回同一个 `metadata["gaia"]["provenance"]` 命名空间，而不是在 v6 action / claim surface 上另起一套 evidence attachment 系统。

---

## 4. Warrant Review

### 4.1 Prior 的双层结构

| Prior | 谁设 | 含义 |
|-------|------|------|
| **Domain Claim prior** | Reviewer | 科学命题本身的可信度 |
| **Warrant prior** | 作者默认值 + Reviewer 审查 | 这条支持、关系、计算或观测 warrant 是否成立 |

`Warrant` 是 `Claim` 子类，所以 warrant prior 本质上就是 Warrant claim 的 prior。区别只在 review UI：domain Claim 和 Warrant 分开导出、分开审查。Warrant 的 review item 展示自动生成的 `question`、作者写的 `reason`、以及引用到的 `inputs` / `conclusion`。`derived_from(...)` 生成的是 fixed-prior structural Warrant，不暴露概率估计；其他 Warrant 的 prior 可以由 reviewer 覆盖。Strategy 本身不再承载 v6 authoring-level prior；它只连接 `premises=[warrant, *inputs]` 到 conclusion。

当前 Gaia Lang 编译后：

| DSL object | 编译后 prior 位置 |
|-------------|------------------|
| 普通 `Claim` | Claim Knowledge 的 `metadata["prior"]`，通常由 `priors.py` 注入 |
| `Warrant` from `supported_by(...)` | Warrant Knowledge 的 `metadata["prior"]` |
| `Warrant` from `derived_from(...)` | Warrant Knowledge 的 fixed prior；authoring 为 `1`，compiled metadata 归一化为 `1-ε` |
| `Warrant` from `match(...)` / `contradict(...)` | relation Warrant Knowledge 的 `metadata["prior"]` |
| `Warrant` from `compute(...)` / `@compute(...)` | computation Warrant Knowledge 的 `metadata["prior"]` |

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
    "warrant:quantization_predicts_finite_high_frequency_radiation": (0.94, ""),
    "warrant:planck_1900_reports_finite_high_frequency_radiation":   (0.95, ""),
    "warrant:quantum_prediction_matches_observed_finite_radiation":  (0.93, ""),
    "warrant:quantization_explains_uv_anomaly":                      (0.93, ""),
}
```

模板里可以使用可读 warrant label；编译器最终解析为 Warrant claim 的稳定 IR ID，并把 reviewer 确认后的值写回 Warrant Knowledge 的 prior metadata。Review 不依赖 Python 函数对象身份，也不要求用户引用 Strategy/Operator id。

Review UI 中每条 Warrant 的 `prior` 应解释为对其 `question` 的回答概率。例如 prediction Warrant 的 prior 不是 `conclusion` 自身的 prior，而是：

```text
P("Assuming @inputs, is @conclusion a valid prediction?" = yes)
```

这保留了现有 Gaia Lang 的 `reason+prior` 配对纪律：没有 `reason` 的 prior 不可审计；没有对应 Question 的 prior 没有明确语义。

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

    reported.supported_by(
        inputs=[],
        pattern="observation",
        label=f"{name}_reports_{src}_to_{dst}",
        context=[molecular_bio_lab],
        reason=f"{name}: {evidence}",
        prior=0.99,
    )

    InfoTransfer(src=src, dst=dst).supported_by(
        inputs=[reported],
        pattern="derivation",
        label=f"{name}_supports_info_transfer_{src}_to_{dst}",
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

  quantum_hyp ← warrant:quantization_explains_uv_anomaly [pattern=explanation, prior=0.93]
  │  "Quantum prediction matches observation while classical prediction contradicts it."
  │
  ├─ agreement ← match:quantum_prediction_matches_observed_finite_radiation [0.93]
  │  "The predicted finite spectrum matches measured data."
  │
  ├─ anomaly ← contradict:classical_prediction_contradicts_observed_finite_radiation [0.96]
  │  "Classical divergence conflicts with finite measured radiation."
  │
  ├─ planck_result ← warrant:planck_spectrum_computation [pattern=computation, prior=0.99]
  │  "Planck's law: B(ν,T) = ..."
  │
  └─ uv_data ← warrant:planck_1900_reports_finite_high_frequency_radiation [pattern=observation, prior=0.95]
     "Measured at 5 frequency points..."

━━━ Summary ━━━
  Warranted claims:  2/2 goals have warrant chains
  Unwarranted:       0
  Reviewed warrants: 0/6
```

### 6.4 Hole 的两种类型

| 类型 | 含义 | 严重度 |
|------|------|--------|
| **Unwarranted** | 非 Warrant Claim 没有 incoming support Strategy，且不是 `root_kind` allowed root（即使有 prior） | 结构性 hole |
| **Unreviewed** | 有非 fixed-prior Warrant 但 Warrant prior 未被 reviewer 确认 | 审查 hole |

核心原则：**prior ≠ justification**。普通 Claim 需要 incoming Warrant 或 explicit root declaration；Warrant 本身是可审查的理由 claim，由 reviewer 通过 warrant review 接受或调整。

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

v6 DSL 的所有构造都直接编译到 Gaia IR。这里的核心约束是：不新增 Action IR，不新增额外层级；作者写的是 Python DSL，编译产物仍然只有现有 IR Knowledge、Strategy、Operator 以及 metadata/provenance。

| v6 DSL | 编译目标 |
|--------|---------|
| `Knowledge(...)` | 不进入 IR（metadata only） |
| `Setting(...)` | IR Knowledge (type=setting) |
| `Claim(...)` / Claim 子类 | IR Knowledge (type=claim)，参数化实例记录 `parameters`；`root_kind` 作为 allowed-root metadata |
| `Warrant(...)` | IR Knowledge (type=claim)，`metadata.kind="warrant"`，`metadata.pattern=...`，`metadata.reason=...`，`metadata.question_id=...`，可带 `metadata["prior"]` |
| `Question(...)` | IR Knowledge (type=question) |
| 自动生成的 `Warrant.question` | IR Knowledge (type=question)，`metadata.generated=true`，refs 指向 inputs/conclusion/context |
| `claim.supported_by(...)` | 创建 Warrant + `Strategy(type="support", premises=[warrant, *inputs], conclusion=claim)` |
| `claim.derived_from(...)` | 创建 fixed-prior `Warrant(pattern="derivation")` + `Strategy(type="support", premises=[warrant, *inputs], conclusion=claim)`；compiled prior 归一化为 `1-ε` |
| `compute(...)` / `@compute(...)` | 输出 Claim + computation Warrant + `Strategy(type="support")` + compute metadata |
| `match(...)` | Warrant/helper Claim + `Operator(operator="equivalence", variables=[a,b], conclusion=warrant)` |
| `contradict(...)` | Warrant/helper Claim + `Operator(operator="contradiction", variables=[a,b], conclusion=warrant)` |
| Claim 子类实例化 | ground IR Knowledge + bound parameters |
| `for` 循环展开 | N 个 ground IR Knowledge + N 个 ground Strategy / Operator |
| 多个 `supported_by(...)` | 多个 Warrant + 多个 Strategy 指向同一个 IR Knowledge |
| `reason=` | Warrant.reason / provenance metadata |
| warrant prior | Warrant Knowledge 的 `metadata["prior"]` |

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
- 不新增 zero-premise support。v6.0 用 Warrant 作为 support premise，因此 observation/citation 也可以编译为普通 support edge。

### 7.3 稳定 ID 与 review key

`gaia check --warrants` 可以输出可读 label，但最终必须解析到 Warrant claim 的 IR stable ID。实现上可以把 Python 变量名、函数名、source location、warrant hash 等 traceability 信息放进 `metadata`，不需要扩展 IR schema。多个 warrant 即使 inputs/conclusion 相同，也必须通过显式 `label` 或 source trace 区分，避免 review 时合并成同一项。

---

## 8. v5 → v6 迁移

### 8.1 术语对照

| v5 | v6 | 说明 |
|----|-----|------|
| `claim("...")` | `Claim("...")` 或自定义子类 | 大写，class 风格 |
| `setting("...")` | `Setting("...")` | 大写 |
| `question("...")` | `Question("...")` | 大写 |
| `support([a], b, prior=0.9)` | `b.supported_by(inputs=[a], pattern="derivation", reason=..., prior=0.9)` | 创建 Warrant + support Strategy |
| `deduction([a], b)` | `b.derived_from(inputs=[a], reason=...)` | 确定性推导 shortcut，返回 `prior=1` Warrant |
| `contradiction(a, b)` | `contradict(a, b, reason=..., prior=...)` | 用户侧只暴露科学语义 wrapper |
| `equivalence(a, b)` | `match(a, b, reason=..., prior=...)` | 用户侧只暴露科学语义 wrapper |
| `noisy_and` | 废弃，用 `supported_by(..., pattern=...)` | 已在 v5 中废弃 |
| `review_claim(...)` | `priors.py` PRIORS dict | 已在 0.4.2 废弃 |
| `review_strategy(...)` | `warrant_priors.py` | Warrant label / Warrant stable ID 作为 key |
| `composite(...)` | deferred | 后续可作为 advanced composition API |
| `fills(source, target)` | 保持不变 | 跨包 premise 桥接 |

### 8.2 兼容性

v5 的函数式 API（`claim()`, `support()`, `deduction()` 等）保留为 deprecated 兼容层，内部编译到与 v6 相同的 IR。新包应使用 v6 API。旧的 `support()` / `deduction()` 可直接映射到 `Claim.supported_by(..., pattern=...)`；旧的 raw operator 函数属于 IR/compat 层，不作为 v6.0 authoring surface。

---

## 9. 未来方向

以下功能明确不在 v6.0 范围内，留给未来版本：

1. **嵌套量词**：`∀x ∃y. P(x, y)` — 需要 Skolemization
2. **Lifted inference**：大 domain 不做 grounding，直接 lifted BP
3. **交互式 InquiryState**：类似 Lean 的 tactic REPL
4. **`gaia run` 执行协议**：Compute 函数的远程执行和 witness 持久化
5. **Formal proof / model checking witness**：用普通 witness 函数连接外部证明器或模型检查器；不新增 decorator，除非它确实需要包装可执行函数体并复用 `compute` 机制
6. **Reductio / retraction**：反证法和知识撤回语义
