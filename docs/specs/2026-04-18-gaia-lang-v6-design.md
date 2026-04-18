# Gaia Lang v6 设计

> **Status:** Draft
>
> **Date:** 2026-04-18
>
> **Supersedes:** [2026-04-05-dsl-v6-support-witness-api-design.md](2026-04-05-dsl-v6-support-witness-api-design.md), [2026-04-05-dsl-v6-support-witness-design.md](2026-04-05-dsl-v6-support-witness-design.md)
>
> **Scope:** Gaia Lang authoring DSL — Knowledge 类型体系、Action 体系、参数化与谓词逻辑、InquiryState、Compute decorator
>
> **Non-goal:** 本文档不修改 Gaia IR 保护层。所有 v6 DSL 构造编译到现有 Strategy + Operator IR。

---

## 1. 设计目标

1. **更好的 Knowledge 类型体系**：Knowledge 作为基类（纯文本，无概率），Claim/Setting/Question 作为子类，Claim 支持用户自定义子类作为参数化领域类型。
2. **统一的 Action 体系**：所有推理操作（Derive, Relate, Observe, Compute, Compose）都是 Python 函数 decorator，docstring 作为 warrant，prior 作为可靠度评估。
3. **参数化 Knowledge 与谓词逻辑**：通过 Claim 子类定义参数 schema（类型标注 + docstring 模板），Python 控制流实现 ∀ 展开，编译到 ground factor graph。
4. **Compute decorator**：任何 Python 函数加 `@Compute(prior=...)` 即可包装为 Action，输入输出为 Knowledge 类型，内部自动做值提取和结果包装。
5. **InquiryState**：以导出 Claim 为 goal 的推理进度视图，通过 `gaia check --inquiry` 展示。
6. **IR 零修改**：v6 的所有新概念是 DSL 层抽象，编译后产出与 v5 相同的 Strategy + Operator IR。

---

## 2. Knowledge 类型体系

### 2.1 类型层次

```
Knowledge               ← 纯文本背景知识，无概率，不进入推理图
├── Setting             ← 定义、环境条件、常量（无概率，taken as given）
├── Claim               ← 命题（有 prior，参与 BP）
│   ├── 用户自定义子类   ← 参数化领域类型（如 Temperature, InfoTransfer）
│   └── Question        ← 开放探究（标记未解决问题）
```

### 2.2 Knowledge 基类

纯文本知识，不进入推理图，不携带概率。用途：叙事性背景、包级/模块级 context。

```python
class Knowledge:
    content: str
    metadata: dict[str, Any] = {}
```

Package context 和 module context 通过 Python 的 module docstring 约定获取——编译器自动将 `__init__.py` 的 docstring 作为包级 context，各模块的 docstring 作为模块级 context：

```python
# __init__.py
"""Planck's analysis of blackbody radiation spectrum (1900).
Resolving the ultraviolet catastrophe by introducing energy quantization."""

# observations.py
"""Experimental measurements of blackbody spectrum."""
```

`gaia check` 输出时自动展示 context 层级：

```
Package: blackbody-radiation-gaia
  Context: Planck's analysis of blackbody radiation spectrum (1900)...

  Module: observations
    Context: Experimental measurements of blackbody spectrum.
    ...
```

### 2.3 Setting

定义性知识：环境条件、实验常量、规范引用。无概率，在推理图中作为 premise 参与，但不作为 BP 变量。

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

**核心规则：每个 Claim 都需要 warrant**。warrant 由 Action（Derive/Observe/Compute/...）提供。没有任何 Action 连接的裸 Claim 是 **structural hole**——即使在 priors.py 里赋了 prior 也不例外。prior 是对可信度的量化，warrant 是可信度的理由。二者缺一不可。

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

**部分绑定**（模板）：不传某个参数，该参数保持未绑定状态，可在后续 `bind()` 或 Action 调用时绑定。

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

## 3. Action 体系

### 3.1 核心设计：Action = 函数 decorator

所有 Action 都是 Python 函数 decorator：

- **函数名** = Action 的 label（可 import，可引用）
- **docstring** = warrant claim 的 content
- **类型标注** = premise 类型约束（输入）和 conclusion 类型（输出）
- **函数体** = 空（Derive/Observe/Relate）或 Python 代码（Compute）
- **`prior`** = 对这个 warrant 的信任度

```python
@Derive(prior=0.95)
def planck_resolves_catastrophe(result: Claim, data: Claim) -> Claim:
    """Planck spectrum matches observed data and resolves UV catastrophe."""
```

### 3.2 五种 Action

| Action | 语义 | 函数体 | IR 编译目标 |
|--------|------|--------|------------|
| **Derive** | 逻辑/推理推导 | 空（纯 docstring） | FormalStrategy (support/deduction/...) |
| **Relate** | 建立逻辑关系（矛盾、等价等） | 空 | Operator (contradiction/equivalence/...) |
| **Observe** | 经验观测，warrant = 方法论 | 空 | FormalStrategy (support) |
| **Compute** | 计算推导，warrant = 代码说明 | Python 代码 | FormalStrategy (support) + metadata |
| **Compose** | 子 Action 的层次化组合 | 子 Action 引用 | CompositeStrategy |

### 3.3 调用约定

Action 函数调用时传入 premise Knowledge，返回 conclusion Claim。如果 conclusion 已存在，用 `conclusion=` 参数指定（追加支持到已有 Claim）：

```python
# 创建新 Claim
quantum_hyp = planck_resolves(planck_result, uv_data)

# 追加支持到已有 Claim
einstein_photoelectric(photoelectric_obs, conclusion=quantum_hyp)
```

一个 Claim 可以有多个 Action 支持它。每个 Action 独立注册为一条 Strategy。

### 3.4 Derive

推理推导。函数体为空，docstring 说明推理理由。

```python
@Derive(prior=0.95)
def planck_resolves_catastrophe(result: Claim, data: Claim) -> Claim:
    """Planck spectrum matches observed data and resolves UV catastrophe.
    The quantum hypothesis is the only model that doesn't diverge."""
```

**编译**：根据 premise 数量和语义，编译为 `support`、`deduction` 等 FormalStrategy。默认编译为 `support`。

Derive 可以指定 strategy type：

```python
@Derive(prior=0.99, type="deduction")
def modus_ponens(p: Claim, p_implies_q: Claim) -> Claim:
    """By modus ponens: if P and P→Q, then Q."""
```

### 3.5 Relate

建立两个 Knowledge 之间的逻辑关系。

```python
@Relate("contradiction")
def energy_models_exclusive(classical: Claim, quantum: Claim):
    """Continuous vs quantized energy are mutually exclusive models."""

energy_models_exclusive(classical_hyp, quantum_hyp)
```

**编译**：编译为对应的 Operator（contradiction, equivalence, complement, disjunction）。

支持的 relation type：`contradiction`, `equivalence`, `complement`, `disjunction`, `implication`。

### 3.6 Observe

经验观测。函数体为空，docstring 说明观测方法论（方法、仪器、重复性等）。

```python
@Observe(prior=0.95)
def uv_catastrophe_measurement(lab: Setting, spectrometer: Setting) -> Claim:
    """Measured blackbody spectrum at 5 frequency points with calibrated
    UV-visible spectrometer. Reproduced by 3 independent laboratories."""

uv_data = uv_catastrophe_measurement(lab, spectrometer)
```

Observe 的 premise 通常是 Setting（实验条件），conclusion 是观测结果 Claim。

**编译**：编译为 `support` FormalStrategy，warrant 为 docstring。

### 3.7 Compute

将 Python 函数包装为 Action。唯一拥有实际函数体的 Action 类型。

```python
@Compute(prior=0.99)
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
6. docstring 第一行作为 warrant claim 的 content

**对用户零侵入**：已有的 Python 函数加一行 `@Compute(prior=...)` 即可。函数内部仍然操作 raw Python 值，不需要了解 Knowledge 系统。

**Compute 链式串联**：一个 Compute 的输出（Claim 子类）可以直接作为另一个 Compute 的输入，自动形成推理链。

### 3.8 Compose

层次化组合多个子 Action。

```python
@Compose(prior=0.85)
def abductive_inference(
    support_h: Derive,
    support_alt: Derive,
    compare: Derive
) -> Claim:
    """Abductive reasoning: compare two hypotheses' explanatory power
    for the same observation."""
```

**编译**：编译为 CompositeStrategy，子 Action 编译为 sub-strategies。

### 3.9 inline 版本

在循环或批量场景中，decorator 语法过于冗长。提供 `.inline()` 类方法：

```python
# decorator 版（有函数名，可引用）
@Derive(prior=0.95)
def planck_resolves(result: Claim, data: Claim) -> Claim:
    """Planck spectrum resolves UV catastrophe."""

# inline 版（匿名，适合循环）
Derive.inline(
    [obs], conclusion=claim,
    reason="Confirmed by decades of evidence",
    prior=0.99
)
```

两者编译到完全相同的 IR。inline 版的 Action 自动生成 label（从 conclusion 和 reason 推导），在 warrant review 中同样可见。

---

## 4. Warrant Review

### 4.1 Prior 的双层结构

| Prior | 谁设 | 含义 |
|-------|------|------|
| **Warrant prior**（Action 上的 `prior=`） | 作者 | 这条推理规则/观测方法/计算的可靠度 |
| **Claim prior**（priors.py 中的值） | Reviewer | 这个命题本身的可信度 |

作者在 DSL 中设定 warrant prior，reviewer 在 priors.py 中审查 claim prior。两者独立。

### 4.2 Warrant 导出

```bash
gaia check --warrants              # 带作者 prior（pre-filled）
gaia check --warrants --blind      # prior 留空（blank-slate）
```

**Pre-filled 模式**：导出所有 Action 的 warrant，带作者的 prior 预填。Reviewer 逐条确认或调整。

**Blank-slate 模式**：导出所有 Action 的 warrant，prior 留空。Reviewer 独立估计，避免锚定效应（anchoring bias）。

导出格式：

```python
# warrant_priors.py（gaia check --warrants 自动生成模板）
from .theory import planck_resolves_catastrophe, classical_fails
from .observations import uv_catastrophe_measurement
from .compute import planck_spectrum, rayleigh_jeans

WARRANT_PRIORS = {
    # Pre-filled: (author_prior, reviewer_justification)
    planck_resolves_catastrophe: (0.95, ""),
    classical_fails:             (0.90, ""),
    uv_catastrophe_measurement:  (0.95, ""),
    planck_spectrum:             (0.99, ""),
    rayleigh_jeans:              (0.99, ""),
}
```

**Action 函数是 Python 对象**，可以直接 import 作为 dict key。无需字符串引用。

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
    obs = Observe.inline(
        [molecular_bio_lab],
        reason=f"{name}: {evidence}",
        prior=0.99,
    )
    Derive.inline(
        [obs],
        conclusion=InfoTransfer(src=src, dst=dst),
        reason=f"{name} confirmed by independent evidence",
        prior=0.99,
    )
```

### 5.2 编译：Template → Ground

编译时，所有参数化 Knowledge 展开为 ground instances。每个 ground instance 是 factor graph 里的一个普通变量。IR 层看不到参数化——只有 ground factor graph。

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

  quantum_hyp ← planck_resolves_catastrophe(planck_result, uv_data) [0.95]
  │  "Planck spectrum resolves UV catastrophe."
  │
  ├─ planck_result ← planck_spectrum(T, freq) [0.99]
  │  "Planck's law: B(ν,T) = ..."
  │
  └─ uv_data ← uv_catastrophe_measurement(lab, spectrometer) [0.95]
     "Measured at 5 frequency points..."

  quantum_hyp ⊥ classical_hyp ← energy_models_exclusive
     "Mutually exclusive models."

━━━ Summary ━━━
  Warranted claims:  2/2 goals have Action chains
  Unwarranted:       0
  Reviewed warrants: 0/6
```

### 6.4 Hole 的两种类型

| 类型 | 含义 | 严重度 |
|------|------|--------|
| **Unwarranted** | Claim 没有任何 Action 连接（即使有 prior） | 结构性 hole |
| **Unreviewed** | 有 Action 但 warrant prior 未被 reviewer 确认 | 审查 hole |

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

---

## 7. 编译到 IR

v6 DSL 的所有构造编译到现有 Gaia IR，**IR 层零修改**。

| v6 DSL | 编译目标 |
|--------|---------|
| `Knowledge(...)` | 不进入 IR（metadata only） |
| `Setting(...)` | IR Knowledge (type=setting) |
| `Claim(...)` / Claim 子类 | IR Knowledge (type=claim) |
| `Question(...)` | IR Knowledge (type=question) |
| `@Derive` | FormalStrategy + FormalExpr |
| `@Relate` | Operator |
| `@Observe` | FormalStrategy (type=support) |
| `@Compute` | FormalStrategy (type=support) + metadata.compute |
| `@Compose` | CompositeStrategy |
| Claim 子类实例化 | IR Knowledge + parameters |
| `for` 循环展开 | N 个 ground IR Knowledge + N 个 ground Strategy |
| `conclusion=` 多支持 | 多个 Strategy 指向同一个 IR Knowledge |
| warrant (docstring) | warrant helper Claim |
| warrant prior | Strategy 的 CPT / warrant Claim 的 prior |

---

## 8. v5 → v6 迁移

### 8.1 术语对照

| v5 | v6 | 说明 |
|----|-----|------|
| `claim("...")` | `Claim("...")` 或自定义子类 | 大写，class 风格 |
| `setting("...")` | `Setting("...")` | 大写 |
| `question("...")` | `Question("...")` | 大写 |
| `support([a], b, prior=0.9)` | `@Derive(prior=0.9) def ...` | 函数 decorator |
| `deduction([a], b)` | `@Derive(prior=0.99, type="deduction") def ...` | 函数 decorator + type 参数 |
| `contradiction(a, b)` | `@Relate("contradiction") def ...` | 函数 decorator |
| `equivalence(a, b)` | `@Relate("equivalence") def ...` | 同上 |
| `noisy_and` | 废弃，用 `@Derive` | 已在 v5 中废弃 |
| `review_claim(...)` | `priors.py` PRIORS dict | 已在 0.4.2 废弃 |
| `review_strategy(...)` | `warrant_priors.py` | Action 函数作为 key |
| `composite(...)` | `@Compose` | 函数 decorator |
| `fills(source, target)` | 保持不变 | 跨包 premise 桥接 |

### 8.2 兼容性

v5 的函数式 API（`claim()`, `support()`, `deduction()` 等）保留为 deprecated 兼容层，内部编译到与 v6 相同的 IR。新包应使用 v6 API。

---

## 9. 未来方向

以下功能明确不在 v6.0 范围内，留给未来版本：

1. **嵌套量词**：`∀x ∃y. P(x, y)` — 需要 Skolemization
2. **Lifted inference**：大 domain 不做 grounding，直接 lifted BP
3. **交互式 InquiryState**：类似 Lean 的 tactic REPL
4. **`gaia run` 执行协议**：Compute 函数的远程执行和 witness 持久化
5. **Formal proof 集成**：`@FormalProof` decorator 连接外部证明器
6. **Reductio / retraction**：反证法和知识撤回语义
