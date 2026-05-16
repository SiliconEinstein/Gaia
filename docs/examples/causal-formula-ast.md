# Formula AST — 自定义谓词与量化推理示例

`gaia.engine.lang.formula` 是 Gaia 0.5 的**类型化 Formula AST**，
把自然语言命题拆成结构化树节点，编译器可以遍历做类型检查、参数绑定、
降落到 IR。

**AST = Abstract Syntax Tree（抽象语法树）**。比如 "HbA1c < 7.0%"
被表示为 `LessEqual(FunctionApp(HbA1c, (patient,)), Constant(7.0, Real))` —
一棵可被编译器遍历的树，而不是需要 NLP 解析的原始文本。

> **v0.5 状态**：内置 `Causes` 谓词和 `causal()` 糖衣已移除，
> 改用 `PredicateSymbol` + `UserPredicate` 自定义。
> `Land`/`Implies`/`Forall` 的 connective lowering 在 alpha 阶段
> 尚未给生成的 operator 分配 ID，CLI 编译验证会报错。
> 本示例使用已验证通过 CLI 的 formula 子集。

## Formula AST 节点

### 谓词（Predicate）

| 节点 | 构造方式 | CLI 状态 |
|------|---------|---------|
| `Equals` | `equals(a, b)` | OK |
| `Greater` / `Less` / `GreaterEqual` / `LessEqual` | 直接构造 | OK |
| `UserPredicate` | `UserPredicate(symbol, args)` | OK |

### 项（Term）

| 节点 | CLI 状态 |
|------|---------|
| `Constant(value, type)` | OK — 带类型检查 |
| `Variable(symbol, domain)` | OK |
| `FunctionApp(symbol, args)` | OK — 编译时验证参数域 |
| `ArithOp("+/-/*//", left, right)` | OK |

### 连接词与量词（alpha 限制）

| 节点 | 状态 |
|------|------|
| `Land` / `Lor` / `Lnot` / `Implies` / `Iff` | 可构造，alpha lowering 未分配 operator ID |
| `Forall` / `Exists` | 可构造，alpha lowering 未分配 operator ID |

## 示例场景

二甲双胍是否降低 2 型糖尿病（T2DM）患者的心血管死亡率？

用 `UserPredicate` + 自定义 `PredicateSymbol` 声明因果谓词，
`FunctionSymbol` + `FunctionApp` 声明带类型的可观测函数，
`ArithOp` 声明派生指标。推理链用 `derive` + `contradict`，
证据比较用 `bayes.likelihood`。端到端通过 `gaia build compile`
和 `gaia run infer` 验证。

## 包结构

```
metformin-cvd-gaia/
├── pyproject.toml
└── src/
    └── metformin_cvd/
        ├── __init__.py
        └── priors.py
```

### `pyproject.toml`

```toml
[project]
name = "metformin-cvd-gaia"
version = "0.1.0"
description = "Gaia v0.5 formula AST example — metformin CVD benefit"
requires-python = ">=3.12"
dependencies = []

[tool.gaia]
type = "knowledge-package"
namespace = "biomed"

[tool.gaia.quality]
allow_holes = true
```

### `src/metformin_cvd/__init__.py`

```python
"""二甲双胍心血管获益 — Formula AST 自定义谓词与量化推理。"""

from gaia.engine.lang import (
    Constant, Domain, Nat, Probability, Real, Variable,
    FunctionSymbol, Greater, LessEqual,
    PredicateSymbol, UserPredicate,
    claim, equals, parameter,
    bayes, contradict, derive, equal, exclusive, note, observe,
)
from gaia.engine.lang.formula.term import FunctionApp, ArithOp

# ═════════════════════════════════════════════════════════════
# 1. UserPredicate — 自定义因果谓词
# ═════════════════════════════════════════════════════════════
#
# v0.5 移除了内置 Causes。用 PredicateSymbol + UserPredicate
# 声明自己的因果谓词——类型签名自定义，编译时验证参数域。

metformin = Variable(symbol="metformin", domain=Real)
cvd_death = Variable(symbol="cvd_death", domain=Real)

CausesSymbol = PredicateSymbol("Causes", arg_domains=(Real, Real))

metformin_reduces_cvd = claim(
    "二甲双胍治疗降低2型糖尿病患者心血管死亡率。",
    formula=UserPredicate(CausesSymbol, (metformin, cvd_death)),
    prior=0.5,
    label="metformin_reduces_cvd",
)

# ═════════════════════════════════════════════════════════════
# 2. PredicateSymbol + UserPredicate — 类型安全的自定义谓词
# ═════════════════════════════════════════════════════════════

PatientDomain = Domain("Patient", members=["T2DM individual"])

Improved = PredicateSymbol("Improved", arg_domains=(PatientDomain,))
patient_x = Variable(symbol="patient_x", domain=PatientDomain)

patient_improved = claim(
    "患者X的代谢指标改善。",
    formula=UserPredicate(Improved, (patient_x,)),
    prior=0.8, label="patient_improved",
)

# 多参数谓词：RespondsTo(patient, dose)
RespondsTo = PredicateSymbol("RespondsTo", arg_domains=(PatientDomain, Real))
dose = Variable(symbol="dose", domain=Real)

patient_responds = claim(
    "患者对二甲双胍2000 mg/日有响应。",
    formula=UserPredicate(RespondsTo, (patient_x, dose)),
    prior=0.7, label="patient_responds",
)

# ── 编译时类型安全 ──
# UserPredicate(Improved, (patient_x, dose))
#   → ValueError: arity mismatch（期望1个参数，给了2个）
# UserPredicate(RespondsTo, (Constant(0.5, Probability), dose))
#   → TypeError: domain mismatch（期望 PatientDomain，给了 Probability）
# UserPredicate(Improved, ("not_a_term",))
#   → TypeError: not a Term

# ═════════════════════════════════════════════════════════════
# 3. FunctionSymbol + FunctionApp — 带类型的可观测函数
# ═════════════════════════════════════════════════════════════

HbA1c = FunctionSymbol("HbA1c", arg_domains=(PatientDomain,), result_domain=Real)

hba1c_target = claim(
    "患者HbA1c < 7.0%。",
    formula=LessEqual(
        FunctionApp(HbA1c, (patient_x,)),
        Constant(7.0, Real),
    ),
    prior=0.9, label="hba1c_target",
)

hba1c_value = claim(
    "患者HbA1c = 6.5%。",
    formula=equals(FunctionApp(HbA1c, (patient_x,)), Constant(6.5, Real)),
    prior=0.9, label="hba1c_value",
)

# ── 编译时类型安全 ──
# FunctionApp(HbA1c, (Constant(0.5, Probability),))
#   → TypeError: domain mismatch（期望 PatientDomain，给了 Probability）

# ═════════════════════════════════════════════════════════════
# 4. ArithOp — 派生的量化指标
# ═════════════════════════════════════════════════════════════

hba1c_baseline = Variable(symbol="hba1c_baseline", domain=Real)
hba1c_endpoint = Variable(symbol="hba1c_endpoint", domain=Real)

clinically_meaningful = claim(
    "HbA1c降低 ≥ 1.0个百分点（临床有意义）。",
    formula=Greater(
        ArithOp("-", hba1c_baseline, hba1c_endpoint),
        Constant(1.0, Real),
    ),
    prior=0.8, label="clinically_meaningful",
)

# ═════════════════════════════════════════════════════════════
# 5. 机械论推理链 — derive() 连接 formula claim
# ═════════════════════════════════════════════════════════════

metformin_lowers_hba1c = claim(
    "二甲双胍降低HbA1c。", prior=0.85, label="metformin_lowers_hba1c"
)

glycemic_control = derive(
    "HbA1c<7.0% + 代谢改善 + ≥1.0pct降低 → HbA1c控制达标。",
    given=(hba1c_target, patient_improved, clinically_meaningful),
    label="glycemic_control",
)

hba1c_reduces_cvd = claim(
    "HbA1c控制达标降低CVD风险。", prior=0.75, label="hba1c_reduces_cvd"
)

mechanism_to_benefit = derive(
    "HbA1c控制达标 + 二甲双胍降低HbA1c → 二甲双胍通过HbA1c降低CVD风险。",
    given=(glycemic_control, metformin_lowers_hba1c, hba1c_reduces_cvd),
    label="mechanism_to_benefit",
)

mechanism_supports_causal = derive(
    "机械论链支持二甲双胍降低CVD死亡的因果声称。",
    given=(mechanism_to_benefit,),
    label="mechanism_supports_causal",
)

# ═════════════════════════════════════════════════════════════
# 6. 证据集成 — bayes.likelihood + derive + contradict
# ═════════════════════════════════════════════════════════════

p_cvd = Variable(symbol="p_cvd", domain=Probability)
k_cvd = Variable(symbol="k_cvd", domain=Nat)

ukpds_context = note(
    "UKPDS 34是二甲双胍在超重T2DM患者中的里程碑RCT。"
    "753名患者随机分配至二甲双胍或常规治疗，中位随访10.7年。"
)

h_effective = parameter(p_cvd, 0.082,
    content="二甲双胍有效：CVD死亡率 8.2%（28/342）。", prior=0.5,
    label="h_effective")
h_null = parameter(p_cvd, 0.124,
    content="二甲双胍无效：CVD死亡率 12.4%（与常规治疗相同）。", prior=0.5,
    label="h_null")

competing = exclusive(h_effective, h_null,
    background=[ukpds_context],
    rationale="二甲双胍对CVD死亡率要么有效，要么无效。",
    label="competing_hypotheses",
)

model_effective = bayes.model(
    h_effective, observable=k_cvd,
    distribution=bayes.Binomial(n=342, p=p_cvd),
    background=[ukpds_context],
    label="model_effective",
)
model_null = bayes.model(
    h_null, observable=k_cvd,
    distribution=bayes.Binomial(n=342, p=p_cvd),
    background=[ukpds_context],
    label="model_null",
)

data_cvd = claim(
    "UKPDS 34：二甲双胍组342例中28例CVD死亡。",
    formula=equals(k_cvd, Constant(28, Nat)),
)
observe_cvd = observe(data_cvd, rationale="UKPDS 34主要结局数据。",
                      label="observe_cvd")
data_cvd.label = "data_cvd"

cvd_likelihood = bayes.likelihood(
    data_cvd, model=model_effective, against=[model_null],
    exclusivity="none",
    background=[ukpds_context],
    label="cvd_likelihood",
)

null_excluded = claim(
    "零假设（二甲双胍无CVD获益）被UKPDS 34数据排除。",
    prior=0.5, label="null_excluded",
)
exclude_null = contradict(
    h_null, null_excluded,
    background=[ukpds_context],
    label="exclude_null",
)

evidence_supports_causal = derive(
    "UKPDS数据支持有效假设 + 机制链成立 → 二甲双胍降低CVD死亡。",
    given=(cvd_likelihood, exclude_null, mechanism_supports_causal),
    background=[ukpds_context],
    label="evidence_supports_causal",
)
```

### `src/metformin_cvd/priors.py`

```python
"""Prior records for the metformin CVD formula AST example."""

from gaia.engine.lang import register_prior
from metformin_cvd import (
    h_effective, h_null, hba1c_reduces_cvd, metformin_lowers_hba1c,
    observe_cvd,
)

register_prior(metformin_lowers_hba1c, 0.85,
    justification="UKPDS 34和其他RCT的meta-analysis一致显示HbA1c降低。")
register_prior(hba1c_reduces_cvd, 0.75,
    justification="多项流行病学研究证实HbA1c与CVD风险的独立关联。")
register_prior(h_effective, 0.5,
    justification="在观察UKPDS数据前，有效和无效概率相等。")
register_prior(h_null, 0.5,
    justification="在观察UKPDS数据前，有效和无效概率相等。")
register_prior(observe_cvd, 0.95,
    justification="UKPDS 34是高质量RCT，CVD死亡数据可靠。")
```

## 编译与推理

```bash
cd metformin-cvd-gaia

# 编译 → .gaia/ir.json
gaia build compile
# Compiled 34 knowledge, 6 strategies, 2 operators

# 推理 → .gaia/beliefs.json
gaia run infer
# Inferred 29 beliefs, Method: JT (exact), 2ms
```

查看推理结果：

```bash
python3 -c "
import json
with open('.gaia/beliefs.json') as f:
    data = json.load(f)
for entry in sorted(data['beliefs'], key=lambda x: -x['belief']):
    label = entry.get('label', '')
    print(f'{entry[\"belief\"]:.4f}  {label}')
"
```

预期输出：

```
0.9995  cvd_likelihood
0.9995  competing
0.9776  h_effective
0.9500  data_cvd
0.9362  evidence_supports_causal
0.9000  hba1c_value
0.9000  hba1c_target
0.8745  mechanism_supports_causal
0.8500  metformin_lowers_hba1c
0.8000  clinically_meaningful
0.8000  patient_improved
0.7874  glycemic_control
0.7505  mechanism_to_benefit
0.7500  hba1c_reduces_cvd
0.7000  patient_responds
0.5000  metformin_reduces_cvd
0.0220  h_null
0.0000  null_excluded
```

前三列结果验证：
- `h_effective` = 0.98 vs `h_null` = 0.02 — 数据强烈支持有效假设
- `evidence_supports_causal` = 0.94 — 证据 + 机制链推导成立
- `cvd_likelihood` ≈ 1.0 — 似然比较指向有效模型
- `metformin_reduces_cvd` = 0.50 — 因果声称本身等概率（取决于上下游推理）

## 类型安全保证

Formula AST 在 **claim 构造时**就验证类型：

```python
# 参数数量不匹配 → ValueError
UserPredicate(Improved, (patient_x, dose))  # 期望1个参数

# 域类型不匹配 → TypeError
UserPredicate(RespondsTo, (Constant(0.5, Probability), dose))
#   ↑ 期望 PatientDomain，给了 Probability

# 非 Term 参数 → TypeError
UserPredicate(Improved, ("not_a_term",))

# 函数参数域不匹配 → TypeError
FunctionApp(HbA1c, (Constant(0.5, Probability),))
#   ↑ 期望 PatientDomain，给了 Probability

# 值不匹配原语类型 → ValueError
Constant(3.14, Probability)  # 3.14 不在 [0, 1] 范围内
Constant(-1, Nat)            # Nat 不接受负数
```

## 编译器处理 Formula AST

| Formula 节点 | 编译行为 |
|-------------|---------|
| `Equals(var, Constant)` | 提取参数绑定 → `formula_bindings`，写入 IR parameter |
| `UserPredicate(symbol, args)` | 编译时验证 arity + domain，序列化到 metadata |
| `FunctionApp(symbol, args)` | 编译时验证 arity + domain，序列化到 metadata |
| `Greater` / `LessEqual` | 验证 Term 操作数，元数据序列化 |
| `ArithOp(op, left, right)` | 验证操作数和运算符，元数据序列化 |

## Formula AST vs Prose Claim

| | Prose claim | Formula claim |
|---|---|---|
| 声明 | `claim("p = 0.75")` | `claim("...", formula=equals(p, Constant(0.75, Prob)))` |
| 参数绑定 | 编译器解析字符串 | 编译器遍历 Equals AST 节点 |
| 类型检查 | 运行时隐式 | 构造时显式 |
| 因果声称 | `claim("X causes Y")` | `UserPredicate(CausesSymbol, (X, Y))` |
| 自定义谓词 | 无法表达 | `PredicateSymbol("Stable", (Domain,))` |
| 自定义函数 | 无法表达 | `FunctionSymbol("HbA1c", args, result)` |
| 派生指标 | 无法表达 | `ArithOp("-", baseline, endpoint)` |
| 下游用途 | 纯展示 | 编译器提取绑定、验证类型、降落到 IR |

## Mendelo 示例中的 Formula AST

Mendelo 示例的以下用法已经是 Formula AST 的一部分：

```python
# parameter() 的底层就是 Equals formula
parameter(p, 0.75)  →  claim(formula=Equals(p, Constant(0.75, Probability)))

# 观测数据的 formula 绑定
claim("...", formula=land(equals(n, Constant(395, Nat)),
                           equals(k, Constant(295, Nat))))
```

本示例在此基础上扩展了 `UserPredicate`、`FunctionApp`、`ArithOp`
和自定义 `PredicateSymbol`/`FunctionSymbol` 的用法。