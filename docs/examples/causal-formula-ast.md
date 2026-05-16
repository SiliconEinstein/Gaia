# Formula AST — 自定义谓词与量化推理示例

`gaia.engine.lang.formula` 是 Gaia 0.5 的**类型化 Formula AST**，
把自然语言命题拆成结构化树节点，编译器可以遍历做类型检查、参数绑定、
降落到 IR。

**AST = Abstract Syntax Tree（抽象语法树）**。比如 "HbA1c < 7.0%"
被表示为 `LessEqual(FunctionApp(HbA1c, (patient,)), Constant(7.0, Real))` —
一棵可被编译器遍历的树，而不是需要 NLP 解析的原始文本。

> **v0.5 最新代码注意**：早期的 `causal()` 糖衣和内置 `Causes` 谓词已移除，
> 因果声称改用自定义 `PredicateSymbol` + `UserPredicate`（见 Part 1）。

## Formula AST 节点全景

### 谓词（Predicate）— 原子真值表达式

| 节点 | 构造方式 | 示例 |
|------|---------|------|
| `Equals` | `equals(a, b)` | `equals(ldl, Constant(70, Real))` |
| `NotEquals` | `NotEquals(left, right)` | 不等式 |
| `Greater` / `Less` / `GreaterEqual` / `LessEqual` | 直接构造 | `Greater(hba1c, Constant(6.5, Real))` |
| `UserPredicate` | `UserPredicate(symbol, args)` | 自定义谓词（如因果、稳定、响应） |
| `ClaimAtom` | `ClaimAtom(claim)` | 桥接到 claim graph |

### 连接词（Connective）— 复合公式

| 节点 | DSL 构造器 | 示例 |
|------|-----------|------|
| `Land` | `land(a, b, c)` | 多条件同时成立 |
| `Lor` | `lor(a, b)` | 至少一个成立 |
| `Lnot` | `lnot(a)` | 否定 |
| `Implies` | `implies(a, b)` | a → b |
| `Iff` | `iff(a, b)` | a ↔ b |

### 量词（Quantifier）— 变量绑定

| 节点 | DSL 构造器 | 示例 |
|------|-----------|------|
| `Forall` | `forall(v, body)` | 对所有患者 |
| `Exists` | `exists(v, body)` | 存在某个阈值 |

### 项（Term）— 值表达式

| 节点 | 示例 |
|------|------|
| `Constant` | `Constant(7.0, Real)` — 带类型检查 |
| `Variable` | `Variable(symbol="ldl", domain=Real)` |
| `FunctionApp` | `FunctionApp(HbA1c, (patient,))` |
| `ArithOp` | `ArithOp("-", baseline, endpoint)` |

### 类型原语

| 类型 | 合法值 |
|------|--------|
| `Nat` | 非负整数 |
| `Real` | 任意实数（int 或 float） |
| `Probability` | [0, 1] 范围内的实数 |
| `Bool` | True / False |

## 示例场景

二甲双胍是否降低 2 型糖尿病（T2DM）患者的心血管死亡率？

核心推断：用 `UserPredicate` + 自定义 `PredicateSymbol("Causes", ...)`
替代已移除的内置 `Causes` 谓词，展示自定义符号系统的完整能力。

## 完整代码

```python
"""二甲双胍心血管获益 — Formula AST 自定义谓词与量化推理示例。

从 UserPredicate + 自定义 PredicateSymbol 到 Forall 量化、
ClaimAtom 图桥接的完整 Formula AST 用法，包含 bayes.likelihood
证据比较和 derive 推理链的端到端集成。
"""

from gaia.engine.bp.engine import TRWBeliefPropagation
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.lang import (
    # ── 类型系统 ──
    Bool, Constant, Domain, Nat, Probability, Real, Variable,
    # ── Formula AST 构造器 ──
    ClaimAtom, Forall, FunctionSymbol, Greater, Implies, Land, LessEqual,
    PredicateSymbol, UserPredicate,
    claim, equals, exists, forall, implies, land, lnot, parameter,
    # ── DSL 动词 ──
    bayes, contradict, derive, equal, exclusive, note, observe,
    register_prior,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.formula.term import FunctionApp, ArithOp
from gaia.engine.lang.runtime.knowledge import ClaimKind, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="metformin_cvd_pkg", namespace="biomed")
token = _current_package.set(pkg)

try:
    # ═════════════════════════════════════════════════════════
    # 第 1 部分：UserPredicate 自定义因果谓词
    # ═════════════════════════════════════════════════════════
    #
    # v0.5 最新代码移除了内置 Causes 谓词和 causal() 糖衣。
    # 但你可以用 PredicateSymbol + UserPredicate 声明自己的因果谓词。
    # 这比内置谓词更强大：你可以定义任意类型签名的因果谓词，
    # 编译时自动验证参数的域类型。

    metformin = Variable(symbol="metformin", domain=Real)
    cvd_death = Variable(symbol="cvd_death", domain=Real)

    # 声明自定义因果谓词符号：Causes(Real, Real)
    CausesSymbol = PredicateSymbol("Causes", arg_domains=(Real, Real))

    metformin_reduces_cvd = claim(
        "二甲双胍治疗降低2型糖尿病患者心血管死亡率。",
        formula=UserPredicate(CausesSymbol, (metformin, cvd_death)),
        prior=0.5,
        kind=ClaimKind.GENERAL,
    )
    metformin_reduces_cvd.label = "metformin_reduces_cvd"

    # 验证：formula 是 UserPredicate，symbol.name == "Causes"
    from gaia.engine.lang.formula.predicate import UserPredicate as UP
    assert isinstance(metformin_reduces_cvd.formula, UP)
    assert metformin_reduces_cvd.formula.symbol.name == "Causes"
    # 编译器可以遍历 formula.symbol.arg_domains 验证因果声明两端类型

    # ═════════════════════════════════════════════════════════
    # 第 2 部分：PredicateSymbol + UserPredicate — 带类型的自定义谓词
    # ═════════════════════════════════════════════════════════
    #
    # PredicateSymbol 声明谓词的类型签名（名称 + 参数域列表）。
    # UserPredicate 应用该符号到具体 Term 参数——编译时验证
    # 参数数量、域类型、以及参数是否为 Term。

    PatientDomain = Domain("Patient", members=["T2DM individual"])

    # 单参数谓词：Improved(patient)
    Improved = PredicateSymbol("Improved", arg_domains=(PatientDomain,))

    patient_x = Variable(symbol="patient_x", domain=PatientDomain)
    patient_improved = claim(
        "患者X的代谢指标改善。",
        formula=UserPredicate(Improved, (patient_x,)),
        prior=0.8, kind=ClaimKind.GENERAL,
    )
    patient_improved.label = "patient_improved"

    # 多参数谓词：RespondsTo(patient, dose)
    RespondsTo = PredicateSymbol("RespondsTo", arg_domains=(PatientDomain, Real))
    dose = Variable(symbol="dose", domain=Real)

    patient_responds = claim(
        "患者对二甲双胍2000 mg/日有响应。",
        formula=UserPredicate(RespondsTo, (patient_x, dose)),
        prior=0.7, kind=ClaimKind.GENERAL,
    )
    patient_responds.label = "patient_responds"

    # ── 编译时类型安全保证 ──

    # 参数数量不匹配 → ValueError
    # UserPredicate(Improved, (patient_x, dose))  # 期望1个参数，给了2个

    # 域类型不匹配 → TypeError
    # UserPredicate(RespondsTo, (Constant(0.5, Probability), dose))
    #   # 期望 PatientDomain，给了 Probability

    # 非 Term 参数 → TypeError
    # UserPredicate(Improved, ("not_a_term",))

    # ═════════════════════════════════════════════════════════
    # 第 3 部分：FunctionSymbol + FunctionApp — 带类型的自定义函数
    # ═════════════════════════════════════════════════════════
    #
    # FunctionSymbol 声明函数的类型签名（参数域列表 → 结果域）。
    # FunctionApp 应用该符号到 Term 参数——返回一个 Term，
    # 可用在 Equals、Greater、LessEqual 等谓词中。

    HbA1c = FunctionSymbol("HbA1c", arg_domains=(PatientDomain,), result_domain=Real)
    CVD_Risk = FunctionSymbol("CVD_Risk", arg_domains=(PatientDomain,), result_domain=Probability)

    hba1c_target = claim(
        "患者HbA1c < 7.0%。",
        formula=LessEqual(
            FunctionApp(HbA1c, (patient_x,)),
            Constant(7.0, Real),
        ),
        prior=0.9, kind=ClaimKind.GENERAL,
    )
    hba1c_target.label = "hba1c_target"

    hba1c_value = claim(
        "患者HbA1c = 6.5%。",
        formula=equals(FunctionApp(HbA1c, (patient_x,)), Constant(6.5, Real)),
        prior=0.9, kind=ClaimKind.GENERAL,
    )
    hba1c_value.label = "hba1c_value"

    # ═════════════════════════════════════════════════════════
    # 第 4 部分：Forall 量词 — 总体层面的量化声称
    # ═════════════════════════════════════════════════════════
    #
    # Forall(variable, body) 绑定一个自由变量，声称 body 对该变量
    # 的所有取值成立。编译后 kind = ClaimKind.QUANTIFIED。

    patient = Variable(symbol="patient", domain=PatientDomain)
    hba1c_of_p = FunctionApp(HbA1c, (patient,))
    risk_of_p = FunctionApp(CVD_Risk, (patient,))

    hba1c_implies_low_risk = implies(
        LessEqual(hba1c_of_p, Constant(7.0, Real)),
        LessEqual(risk_of_p, Constant(0.15, Probability)),
    )

    glycemic_control_reduces_cvd_risk = claim(
        "对所有T2DM患者，HbA1c < 7.0%意味着CVD风险 ≤ 15%。",
        formula=Forall(patient, hba1c_implies_low_risk),
        prior=0.7, kind=ClaimKind.QUANTIFIED,
    )
    glycemic_control_reduces_cvd_risk.label = "glycemic_control_reduces_cvd_risk"
    assert glycemic_control_reduces_cvd_risk.kind is ClaimKind.QUANTIFIED

    # Exists：存在性声称
    # "存在对二甲双胍治疗响应良好的T2DM患者。"
    some_patient_benefits = claim(
        "存在对二甲双胍治疗响应良好的T2DM患者。",
        formula=exists(
            Variable(symbol="p", domain=PatientDomain),
            UserPredicate(RespondsTo, (
                Variable(symbol="p", domain=PatientDomain),
                Constant(2000, Real),
            )),
        ),
        prior=0.9, kind=ClaimKind.QUANTIFIED,
    )
    some_patient_benefits.label = "some_patient_benefits"

    # ═════════════════════════════════════════════════════════
    # 第 5 部分：Land + Implies — 机械论推理链
    # ═════════════════════════════════════════════════════════
    #
    # 机械论路径：AMPK 激活 ∧ 肝糖异生降低 ∧ HbA1c 达标
    #            → CVD 风险降低 → 心血管死亡降低

    ampk = Variable(symbol="ampk_activity", domain=Real)
    gluconeogenesis = Variable(symbol="gluconeogenesis", domain=Real)
    hba1c = Variable(symbol="hba1c", domain=Real)

    mechanism_premises = land(
        Greater(ampk, Constant(1.0, Real)),              # AMPK 激活
        LessEqual(gluconeogenesis, Constant(0.5, Real)), # 肝糖异生降低
        LessEqual(hba1c, Constant(7.0, Real)),           # HbA1c 达标
    )

    mechanism_implies_benefit = implies(
        mechanism_premises,
        LessEqual(cvd_death, Constant(0.05, Probability)),
    )

    mechanistic_pathway = claim(
        "AMPK激活 + 肝糖异生降低 + HbA1c达标 → CVD死亡风险 ≤ 5%。",
        formula=mechanism_implies_benefit,
        prior=0.6, kind=ClaimKind.GENERAL,
    )
    mechanistic_pathway.label = "mechanistic_pathway"

    # ═════════════════════════════════════════════════════════
    # 第 6 部分：ClaimAtom — 桥接 formula AST 到 claim graph
    # ═════════════════════════════════════════════════════════
    #
    # ClaimAtom 把另一个 Claim 的 truth 值作为 formula 中的原子命题。
    # 这样可以在 formula 层面组合已有 claim 的真值，实现跨图推理。

    metformin_lowers_hba1c = claim("二甲双胍降低HbA1c。", prior=0.85)
    metformin_lowers_hba1c.label = "metformin_lowers_hba1c"
    register_prior(metformin_lowers_hba1c, 0.85,
        justification="UKPDS 34和其他RCT的meta-analysis一致显示HbA1c降低。")

    # "如果 metformin 降低 HbA1c 且 HbA1c 降低减少 CVD 风险，
    #  则 metformin 减少 CVD 风险。"
    transitive_causal_chain = claim(
        "二甲双胍通过HbA1c降低间接降低CVD风险。",
        formula=implies(
            land(
                ClaimAtom(metformin_lowers_hba1c),
                ClaimAtom(glycemic_control_reduces_cvd_risk),
            ),
            ClaimAtom(metformin_reduces_cvd),
        ),
        prior=0.65, kind=ClaimKind.GENERAL,
    )
    transitive_causal_chain.label = "transitive_causal_chain"

    # ═════════════════════════════════════════════════════════
    # 第 7 部分：ArithOp — 派生的量化指标
    # ═════════════════════════════════════════════════════════
    #
    # ArithOp 支持 + - * / 四种算术运算，操作数必须是 Term。
    # 用于声明"变化量"、"差值"等派生指标。

    hba1c_baseline = Variable(symbol="hba1c_baseline", domain=Real)
    hba1c_endpoint = Variable(symbol="hba1c_endpoint", domain=Real)

    # HbA1c 降低量 = 基线 - 终点
    hba1c_reduction = ArithOp("-", hba1c_baseline, hba1c_endpoint)

    clinically_meaningful = claim(
        "HbA1c降低 ≥ 1.0个百分点（临床有意义）。",
        formula=Greater(hba1c_reduction, Constant(1.0, Real)),
        prior=0.8, kind=ClaimKind.GENERAL,
    )
    clinically_meaningful.label = "clinically_meaningful"

    # ═════════════════════════════════════════════════════════
    # 第 8 部分：端到端集成 — formula + bayes + derive
    # ═════════════════════════════════════════════════════════
    #
    # 将上述 Formula AST 用法与 bayes.likelihood + derive 推理链
    # 整合到一个完整的证据图中。

    # ── 8a. 可观测变量 ──
    # 两个独立变量（Mendel 示例的模式）：
    #   p_cvd = Probability 变量（Binomial 的 p 参数，被假设绑定）
    #   k_cvd = Nat 变量（观测计数，被 observation 公式匹配）
    p_cvd = Variable(symbol="p_cvd", domain=Probability)
    k_cvd = Variable(symbol="k_cvd", domain=Nat)

    ukpds_context = note(
        "UKPDS 34是二甲双胍在超重T2DM患者中的里程碑RCT。"
        "753名患者随机分配至二甲双胍或常规治疗，中位随访10.7年。"
    )

    # ── 8b. 竞争假设 — 绑定 Probability 参数 ──
    h_effective = parameter(p_cvd, 0.082,
        content="二甲双胍有效：CVD死亡率 8.2%（28/342）。", prior=0.5)
    h_effective.label = "h_effective"

    h_null = parameter(p_cvd, 0.124,
        content="二甲双胍无效：CVD死亡率 12.4%（与常规治疗相同）。", prior=0.5)
    h_null.label = "h_null"

    competing = exclusive(
        h_effective, h_null,
        background=[ukpds_context],
        rationale="二甲双胍对CVD死亡率要么有效，要么无效。",
        label="competing_hypotheses",
    )

    # ── 8c. 预测模型 — Binomial(n=342, p=p_cvd) ──
    model_effective = bayes.model(
        h_effective, observable=k_cvd,
        distribution=bayes.Binomial(n=342, p=p_cvd),
        background=[ukpds_context],
        rationale="有效假设预测 CVD 死亡服从 Binomial(342, p=0.082)。",
        label="model_effective",
    )
    model_null = bayes.model(
        h_null, observable=k_cvd,
        distribution=bayes.Binomial(n=342, p=p_cvd),
        background=[ukpds_context],
        rationale="零假设预测 CVD 死亡服从 Binomial(342, p=0.124)。",
        label="model_null",
    )

    # ── 8d. 观测数据 — Nat 计数 ──
    data_cvd = claim(
        "UKPDS 34：二甲双胍组342例中28例CVD死亡。",
        formula=equals(k_cvd, Constant(28, Nat)),
    )
    observe(data_cvd, rationale="UKPDS 34主要结局数据。", label="observe_cvd")
    data_cvd.label = "data_cvd"

    # ── 8e. 似然比较 ──
    cvd_likelihood = bayes.likelihood(
        data_cvd, model=model_effective, against=[model_null],
        exclusivity="exhaustive_pairwise_complement",
        background=[ukpds_context],
        label="cvd_likelihood",
    )

    # ── 8f. 推理链：因果声称 ↔ 机制 ↔ 证据 ──
    mechanism_supports_causal = derive(
        "机制链和传递因果链支持二甲双胍降低CVD死亡的因果声称。",
        given=(mechanistic_pathway, transitive_causal_chain),
        background=[ukpds_context],
        label="mechanism_supports_causal",
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
        "UKPDS数据+机制链支持因果声称。",
        given=(cvd_likelihood, mechanism_supports_causal, exclude_null),
        background=[ukpds_context],
        label="evidence_supports_causal",
    )

finally:
    _current_package.reset(token)

# ═════════════════════════════════════════════════════════
# 9. 编译与推理
# ═════════════════════════════════════════════════════════

compiled = compile_package_artifact(pkg)
fg = lower_local_graph(compiled.graph)
beliefs = TRWBeliefPropagation().run(fg).beliefs

causal_id = compiled.knowledge_ids_by_object[id(metformin_reduces_cvd)]
effective_id = compiled.knowledge_ids_by_object[id(h_effective)]
null_id = compiled.knowledge_ids_by_object[id(h_null)]
mechanism_id = compiled.knowledge_ids_by_object[id(mechanistic_pathway)]

print(f"Metformin reduces CVD death : {beliefs[causal_id]:.4f}")
print(f"h_effective (p=0.082)       : {beliefs[effective_id]:.4f}")
print(f"h_null (p=0.124)            : {beliefs[null_id]:.4f}")
print(f"Mechanistic pathway         : {beliefs[mechanism_id]:.4f}")

# 预期结果：
#   Metformin reduces CVD death : 0.59   ← 因果声称后验 > 0.5
#   h_effective                 : 0.98   ← 数据+机制强烈支持
#   h_null                      : 0.02   ← 几乎被排除
#   Mechanistic pathway         : 0.96   ← 机制链后验高
```

## 编译输出

```
42 knowledges, 8 operators, 5 strategies
TRW BP inference (38 variables, 2^38 too large for exact)
```

## 推理结果

```
Metformin reduces CVD death : 0.5900
h_effective (p=0.082)       : 0.9780
h_null (p=0.124)            : 0.0216
Mechanistic pathway         : 0.9574
```

## 编译器如何处理 Formula AST

| Formula 节点 | 编译行为 |
|-------------|---------|
| `Equals(var, Constant)` | 提取参数绑定 → `metadata["formula_bindings"]`，写入 IR parameter |
| `UserPredicate(symbol, args)` | 验证参数数量和域类型，序列化到 metadata |
| `Land(ops...)` / `Implies(...)` | 验证子 formula，保留在 metadata |
| `Forall(var, body)` / `Exists(var, body)` | 验证绑定变量，`ClaimKind.QUANTIFIED` |
| `Greater` / `LessEqual` | 验证 Term 操作数，元数据序列化 |
| `ClaimAtom(claim)` | 指向已有 claim 的 QID（跨公式图引用） |
| `FunctionApp(symbol, args)` | 编译时验证参数数量和域类型 |

## 类型安全保证

Formula AST 在 **claim 构造时**就捕获错误：

```python
# 参数数量不匹配 → ValueError
UserPredicate(Improved, (patient_x, dose))    # 期望1个参数

# 域类型不匹配 → TypeError
UserPredicate(RespondsTo, (Constant(0.5, Probability), dose))
#   ↑ 期望 PatientDomain，给了 Probability

# 非 Term 参数 → TypeError
UserPredicate(Improved, ("not_a_term",))

# 值不匹配原语类型 → ValueError
Constant(3.14, Probability)    # 3.14 不在 [0, 1] 范围内
Constant(-1, Nat)              # Nat 不接受负数
```

## Formula AST vs 旧的 prose claim

| | Prose claim | Formula claim |
|---|---|---|
| 声明 | `claim("p = 0.75")` | `claim("...", formula=equals(p, Constant(0.75, Prob)))` |
| 参数绑定 | 编译器解析字符串 | 编译器遍历 Equals AST 节点 |
| 类型检查 | 运行时隐式 | 构造时显式（`PrimitiveType.accepts()`） |
| 因果声称 | `claim("X causes Y")` | `UserPredicate(CausesSymbol, (X, Y))` |
| 复合逻辑 | 嵌入自然语言 | `land(a, implies(b, c))` — 可机器遍历 |
| 自定义谓词 | 无法表达 | `PredicateSymbol("Stable", (Domain,))` |
| 量化 | 无法表达 | `Forall(patient, body)` |
| 下游用途 | 纯展示 | 编译器提取绑定、验证类型、降落到 IR |

## 运行说明

此示例针对 Gaia v0.5 分支（`origin/v0.5`）。运行前：

```bash
git checkout origin/v0.5
pip install -e ".[dev]"
python examples/formula_ast_demo.py
```

## 与 v0.5 早期版本的区别

早期 v0.5 commit（`841269b4` 及之前）包含内置 `Causes` 谓词和 `causal()` 糖衣函数，
后续版本已移除。自定义 `PredicateSymbol` + `UserPredicate` 是更通用、更强大的替代方案——
你可以定义任意类型签名的因果、医学、物理谓词，编译器自动验证参数域。