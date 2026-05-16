# Formula AST — 因果推断示例：二甲双胍与 2 型糖尿病心血管死亡

`gaia.engine.lang.formula` 是 Gaia 0.5 新增的**类型化 Formula AST**，
把自然语言命题拆成结构化树节点，编译器可以遍历做类型检查、参数绑定、
降落到 IR，而不是解析字符串。

AST = **Abstract Syntax Tree（抽象语法树）**。比如"高 LDL 导致心脏病"
被表示为 `Causes(Constant("高 LDL"), Constant("心脏病"))` ——
一棵可被编译器遍历的树，而不是需要 NLP 解析的原始文本。

## Formula AST 节点全景

### 谓词（Predicate）— 原子真值表达式

| 节点 | DSL 构造器 | 示例 |
|------|-----------|------|
| `Equals` | `equals(a, b)` | `equals(ldl, Constant(70, Real))` |
| `NotEquals` | — | `NotEquals(left, right)` |
| `Greater` / `Less` / `GreaterEqual` / `LessEqual` | — | `Greater(hba1c, Constant(6.5, Real))` |
| `Causes` | `causes(cause, effect)` | `causes(co2, temp)` |
| `UserPredicate` | — | `UserPredicate(Stable, (plaque,))` |
| `ClaimAtom` | — | `ClaimAtom(another_claim)` — 桥接到 claim graph |

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
| `Constant` | `Constant(70, Real)` — 带类型检查的字面量 |
| `Variable` | `Variable(symbol="ldl", domain=Real)` |
| `FunctionApp` | `FunctionApp(CVDRisk, (patient,))` |
| `ArithOp` | `ArithOp("-", ldl_baseline, ldl_30wk)` |

### 四种 ClaimKind

| 枚举值 | 用途 |
|--------|------|
| `GENERAL` | 默认，无特殊 formula |
| `PARAMETER` | `parameter(v, value)` — 变量绑定 |
| `CAUSAL` | `causal(cause, effect)` — 因果标记 |
| `QUANTIFIED` | `forall` / `exists` 体 |

## 示例场景

二甲双胍是否降低 2 型糖尿病（T2DM）患者的心血管死亡率？

- **因果声称**：二甲双胍 → 心血管死亡降低
- **机制链**：AMPK 激活 → 肝糖异生降低 → HbA1c 降低 → CVD 风险降低
- **证据**：UKPDS 34 随机对照试验（n=753 超重 T2DM 患者）
- **可观测指标**：HbA1c（连续）和 CVD 死亡事件（离散）

## 完整代码

```python
"""二甲双胍心血管获益 — Formula AST 因果推断示例。

从 causal() 糖衣到 PredicateSymbol、Forall、ClaimAtom 的完整 Formula AST 用法，
包含 bayes.likelihood 证据比较和 derive 推理链的混合编排。
"""

from gaia.engine.bp.exact import exact_inference
from gaia.engine.bp.lowering import lower_local_graph
from gaia.engine.lang import (
    # ── 类型系统 ──
    Bool,
    Constant,
    Domain,
    Nat,
    Probability,
    Real,
    Variable,
    # ── Formula AST 构造器 ──
    ClaimAtom,
    Forall,
    FunctionSymbol,
    Greater,
    Implies,
    Land,
    LessEqual,
    PredicateSymbol,
    UserPredicate,
    causal,
    claim,
    equals,
    exists,
    forall,
    implies,
    land,
    lnot,
    parameter,
    # ── DSL 动词 ──
    bayes,
    contradict,
    derive,
    equal,
    exclusive,
    note,
    observe,
    register_prior,
    support,
)
from gaia.engine.lang.compiler.compile import compile_package_artifact
from gaia.engine.lang.runtime.knowledge import ClaimKind, _current_package
from gaia.engine.lang.runtime.package import CollectedPackage

pkg = CollectedPackage(name="metformin_cvd_pkg", namespace="biomed")
token = _current_package.set(pkg)

try:
    # ═════════════════════════════════════════════════════════
    # 第 1 部分：causal() 糖衣 — 最简单的因果声称入口
    # ═════════════════════════════════════════════════════════
    #
    # causal() 做什么：
    #   1. 构造 Causes(cause=metformin, effect=cvd_death) formula 节点
    #   2. 创建 ClaimKind.CAUSAL 类型的 claim
    #   3. 编译器将 formula 序列化到 metadata["causal"] 和 metadata["formula_atom"]
    #
    # 编译后的 IR knowledge 节点上会有：
    #   metadata["formula_atom"] = {"kind": "causes", ...}
    #   metadata["causal"] = {"cause": {...}, "effect": {...}}

    metformin = Variable(symbol="metformin", domain=Real)
    cvd_death = Variable(symbol="cvd_death", domain=Real)

    metformin_reduces_cvd = causal(
        metformin,
        cvd_death,
        describe="二甲双胍治疗降低 2 型糖尿病患者心血管死亡率。",
        prior=0.5,
    )
    metformin_reduces_cvd.label = "metformin_reduces_cvd"

    # 验证：formula 是 Causes AST 节点
    from gaia.engine.lang.formula.predicate import Causes
    assert isinstance(metformin_reduces_cvd.formula, Causes)
    assert metformin_reduces_cvd.kind is ClaimKind.CAUSAL
    # Causes 节点的 cause/effect 字段可被编译器遍历：
    assert metformin_reduces_cvd.formula.cause is metformin
    assert metformin_reduces_cvd.formula.effect is cvd_death

    # ═════════════════════════════════════════════════════════
    # 第 2 部分：PredicateSymbol + UserPredicate — 自定义类型化谓词
    # ═════════════════════════════════════════════════════════
    #
    # PredicateSymbol 声明一个谓词的类型签名（名称 + 参数域）。
    # UserPredicate 应用该符号到具体 Term 参数——编译时验证
    # 参数数量和域类型。

    # 声明谓词符号：Improved(patient) — 患者的代谢指标是否改善
    PatientDomain = Domain("Patient", members=["T2DM individual"])
    Improved = PredicateSymbol(
        "Improved",
        arg_domains=(PatientDomain,),  # 接受一个 Patient 域的参数
    )

    # 应用谓词到具体变量——编译时验证参数类型
    patient_x = Variable(symbol="patient_x", domain=PatientDomain)
    patient_improved = claim(
        "患者 X 的代谢指标改善。",
        formula=UserPredicate(Improved, (patient_x,)),
        prior=0.8,
        kind=ClaimKind.GENERAL,
    )
    patient_improved.label = "patient_improved"

    # 可以声明更复杂的谓词，带多个参数和不同域
    RespondsTo = PredicateSymbol(
        "RespondsTo",
        arg_domains=(PatientDomain, Real),  # (患者, 剂量)
    )
    dose = Variable(symbol="dose", domain=Real)
    patient_responds = claim(
        "患者对二甲双胍 2000 mg/日有响应。",
        formula=UserPredicate(RespondsTo, (patient_x, dose)),
        prior=0.7,
        kind=ClaimKind.GENERAL,
    )
    patient_responds.label = "patient_responds"

    # ═════════════════════════════════════════════════════════
    # 第 3 部分：FunctionSymbol + FunctionApp — 自定义类型化函数
    # ═════════════════════════════════════════════════════════
    #
    # FunctionSymbol 声明函数的类型签名（参数域 → 结果域）。
    # FunctionApp 应用该符号到 Term 参数——返回一个 Term，
    # 可用在 Equals、Greater 等谓词中。

    # 声明函数符号：HbA1c(patient) → Real
    HbA1c = FunctionSymbol(
        "HbA1c",
        arg_domains=(PatientDomain,),     # 接受一个 Patient
        result_domain=Real,                # 返回 Real
    )

    # 声明函数符号：CVD_Risk(patient) → Probability
    CVD_Risk = FunctionSymbol(
        "CVD_Risk",
        arg_domains=(PatientDomain,),
        result_domain=Probability,
    )

    # 在 Equals 谓词中使用 FunctionApp
    from gaia.engine.lang.formula.term import FunctionApp

    hba1c_target = claim(
        "患者 HbA1c < 7.0%。",
        formula=LessEqual(
            FunctionApp(HbA1c, (patient_x,)),
            Constant(7.0, Real),
        ),
        prior=0.9,
        kind=ClaimKind.GENERAL,
    )
    hba1c_target.label = "hba1c_target"

    # 也可以用 equals() 糖衣：
    hba1c_value = claim(
        "患者 HbA1c = 6.5%。",
        formula=equals(
            FunctionApp(HbA1c, (patient_x,)),
            Constant(6.5, Real),
        ),
        prior=0.9,
        kind=ClaimKind.GENERAL,
    )
    hba1c_value.label = "hba1c_value"

    # ═════════════════════════════════════════════════════════
    # 第 4 部分：Forall 量词 — 总体层面的声称
    # ═════════════════════════════════════════════════════════
    #
    # Forall(variable, body) 绑定一个自由变量，声称 body 对该变量
    # 的所有取值成立。与 parameter() 不同：parameter 绑定到具体值，
    # Forall 声明对域中所有元素成立。
    #
    # 编译后 kind = ClaimKind.QUANTIFIED。

    # "对所有 T2DM 患者，若 HbA1c < 7.0% 则 CVD 风险降低"
    patient = Variable(symbol="patient", domain=PatientDomain)
    hba1c_of_p = FunctionApp(HbA1c, (patient,))
    risk_of_p = FunctionApp(CVD_Risk, (patient,))

    # 构造全称量化声称的 body formula
    hba1c_implies_low_risk = implies(
        LessEqual(hba1c_of_p, Constant(7.0, Real)),
        LessEqual(risk_of_p, Constant(0.15, Probability)),
    )

    glycemic_control_reduces_cvd_risk = claim(
        "对所有 T2DM 患者，HbA1c < 7.0% 意味着 CVD 风险 ≤ 15%。",
        formula=Forall(patient, hba1c_implies_low_risk),
        prior=0.7,
        kind=ClaimKind.QUANTIFIED,
    )
    glycemic_control_reduces_cvd_risk.label = "glycemic_control_reduces_cvd_risk"

    # 也可以用 exists() 声明存在性声称
    some_patient_benefits = claim(
        "存在对二甲双胍治疗响应良好的 T2DM 患者。",
        formula=exists(
            Variable(symbol="p", domain=PatientDomain),
            UserPredicate(RespondsTo, (
                Variable(symbol="p", domain=PatientDomain),
                Constant(2000, Real),
            )),
        ),
        prior=0.9,
        kind=ClaimKind.QUANTIFIED,
    )
    some_patient_benefits.label = "some_patient_benefits"

    # ═════════════════════════════════════════════════════════
    # 第 5 部分：Land + Implies — 机械论推理链
    # ═════════════════════════════════════════════════════════
    #
    # 机械论路径：AMPK 激活 ∧ 肝糖异生降低 ∧ HbA1c 降低
    #            → CVD 风险降低 → 心血管死亡降低

    ampk = Variable(symbol="ampk_activity", domain=Real)
    gluconeogenesis = Variable(symbol="gluconeogenesis", domain=Real)
    hba1c = Variable(symbol="hba1c", domain=Real)

    # 机制链的每一步都是带 formula 的 claim
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
        "AMPK 激活 + 肝糖异生降低 + HbA1c 达标 → CVD 死亡风险 ≤ 5%。",
        formula=mechanism_implies_benefit,
        prior=0.6,
        kind=ClaimKind.GENERAL,
    )
    mechanistic_pathway.label = "mechanistic_pathway"

    # ═════════════════════════════════════════════════════════
    # 第 6 部分：ClaimAtom — 桥接 formula AST 到 claim graph
    # ═════════════════════════════════════════════════════════
    #
    # ClaimAtom 把另一个 Claim 的 truth 值作为 formula 中的原子命题。
    # 这样可以在 formula 层面组合已有 claim 的真值。

    metformin_lowers_hba1c = claim(
        "二甲双胍降低 HbA1c。",
        prior=0.85,
    )
    metformin_lowers_hba1c.label = "metformin_lowers_hba1c"
    register_prior(metformin_lowers_hba1c, 0.85,
        justification="UKPDS 34 和其他 RCT 的 meta-analysis 一致显示 HbA1c 降低。")

    # 用 ClaimAtom 在 formula 中引用已有 claim：
    # "如果 metformin 降低 HbA1c 且 HbA1c 降低减少 CVD 风险，
    #  则 metformin 减少 CVD 风险。"
    transitive_causal_chain = claim(
        "二甲双胍通过 HbA1c 降低间接降低 CVD 风险。",
        formula=implies(
            land(
                ClaimAtom(metformin_lowers_hba1c),
                ClaimAtom(glycemic_control_reduces_cvd_risk),
            ),
            ClaimAtom(metformin_reduces_cvd),
        ),
        prior=0.65,
        kind=ClaimKind.GENERAL,
    )
    transitive_causal_chain.label = "transitive_causal_chain"

    # ═════════════════════════════════════════════════════════
    # 第 7 部分：ArithOp — 派生的量化指标
    # ═════════════════════════════════════════════════════════
    #
    # ArithOp 支持 + - * / 四种算术运算，操作数必须是 Term。
    # 用于声明"变化量"、"差值"等派生指标。

    from gaia.engine.lang.formula.term import ArithOp

    hba1c_baseline = Variable(symbol="hba1c_baseline", domain=Real)
    hba1c_endpoint = Variable(symbol="hba1c_endpoint", domain=Real)

    # HbA1c 降低量 = 基线 - 终点
    hba1c_reduction = ArithOp("-", hba1c_baseline, hba1c_endpoint)

    clinically_meaningful = claim(
        "HbA1c 降低 ≥ 1.0 个百分点（临床有意义）。",
        formula=Greater(hba1c_reduction, Constant(1.0, Real)),
        prior=0.8,
        kind=ClaimKind.GENERAL,
    )
    clinically_meaningful.label = "clinically_meaningful"

    # ═════════════════════════════════════════════════════════
    # 第 8 部分：完整的端到端集成
    # ═════════════════════════════════════════════════════════
    #
    # 将上述 Formula AST 用法与 bayes.likelihood + derive 推理链
    # 整合到一个完整的证据图中。

    # ── 8a. 可观测指标 ──
    responders = Variable(symbol="responders", domain=Nat)
    hba1c_obs = Variable(symbol="hba1c_obs", domain=Real)

    # UKPDS 34 背景
    ukpds_context = note(
        "UKPDS 34 是二甲双胍在超重 T2DM 患者中的里程碑 RCT。"
        "753 名患者随机分配至二甲双胍或常规治疗，中位随访 10.7 年。"
        "主要结局：全因死亡、糖尿病相关死亡、心肌梗死。"
    )

    # ── 8b. 两个竞争假设 ──
    h_effective = parameter(
        responders, 0.12,   # 12% 绝对风险降低
        content="二甲双胍有效：CVD 死亡率绝对降低 12%。",
        prior=0.5,
    )
    h_effective.label = "h_effective"

    h_null = parameter(
        responders, 0.0,
        content="二甲双胍无效：CVD 死亡率无差异。",
        prior=0.5,
    )
    h_null.label = "h_null"

    competing = exclusive(
        h_effective,
        h_null,
        background=[ukpds_context],
        rationale="二甲双胍对 CVD 死亡率要么有效，要么无效。",
        label="competing_hypotheses",
    )

    # ── 8c. 预测模型 — 结合推导出的量化指标 ──
    model_effective = bayes.model(
        h_effective,
        observable=responders,
        distribution=bayes.Binomial(n=753, p=responders),
        background=[ukpds_context],
        rationale="有效假设预测 CVD 死亡服从 Binomial(753, p=0.12)。",
        label="model_effective",
    )

    model_null = bayes.model(
        h_null,
        observable=responders,
        distribution=bayes.Binomial(n=753, p=responders),
        background=[ukpds_context],
        rationale="零假设预测 CVD 死亡服从 Binomial(753, p=0.0)。",
        label="model_null",
    )

    # ── 8d. 观测数据 ──
    data_cvd = claim(
        "UKPDS 34：二甲双胍组 CVD 死亡 28/342，常规治疗组 51/411。",
        formula=land(
            equals(responders, Constant(28, Nat)),
        ),
    )
    observe(data_cvd, rationale="UKPDS 34 主要结局数据。", label="observe_cvd")
    data_cvd.label = "data_cvd"

    # ── 8e. 似然比较 ──
    cvd_likelihood = bayes.likelihood(
        data_cvd,
        model=model_effective,
        against=[model_null],
        exclusivity="exhaustive_pairwise_complement",
        background=[ukpds_context],
        label="cvd_likelihood",
    )

    # ── 8f. 推理链：因果声称 ↔ 机制 ↔ 证据 ──
    # 机制支持因果声称
    mechanism_supports_causal = support(
        [mechanistic_pathway, transitive_causal_chain],
        metformin_reduces_cvd,
        background=[ukpds_context],
        rationale="AMPK→糖异生→HbA1c→CVD 风险的机械论链支持因果声称。",
        label="mechanism_supports_causal",
    )

    # 如果零假设被排除，进一步加强因果声称
    null_excluded = claim(
        "零假设（二甲双胍无 CVD 获益）被 UKPDS 34 数据排除。",
        prior=0.5,
        label="null_excluded",
    )

    exclude_null = contradict(
        h_null,
        null_excluded,
        background=[ukpds_context],
        rationale="UKPDS 34 数据不支持零假设。",
        label="exclude_null",
    )

    # 证据 + 机制链联合支持因果声称
    evidence_supports_causal = support(
        [cvd_likelihood, mechanism_supports_causal, exclude_null],
        metformin_reduces_cvd,
        background=[ukpds_context],
        rationale="UKPDS 数据 + 机械论链 → 二甲双胍降低 CVD 死亡。",
        label="evidence_supports_causal",
    )

finally:
    _current_package.reset(token)

# ═════════════════════════════════════════════════════════
# 9. 编译与推理
# ═════════════════════════════════════════════════════════

compiled = compile_package_artifact(pkg)
beliefs, _ = exact_inference(lower_local_graph(compiled.graph))

causal_id = compiled.knowledge_ids_by_object[id(metformin_reduces_cvd)]
effective_id = compiled.knowledge_ids_by_object[id(h_effective)]
null_id = compiled.knowledge_ids_by_object[id(h_null)]
cvd_likelihood_id = compiled.knowledge_ids_by_object[id(cvd_likelihood)]

print(f"Metformin reduces CVD death : {beliefs[causal_id]:.4f}")
print(f"h_effective posterior       : {beliefs[effective_id]:.4f}")
print(f"h_null posterior            : {beliefs[null_id]:.4f}")
print(f"Likelihood comparison       : {beliefs[cvd_likelihood_id]:.4f}")

# 预期：causal claim 后验 > 0.5（机制 + 证据双重支持）
#       h_effective >> h_null（Bayes 因子 28 vs 0 在二项模型下极强）
```

## 编译器如何处理 Formula AST

编译时，`compile_package_artifact()` 识别 claim 上的 formula 字段：

| Formula 节点 | 编译行为 |
|-------------|---------|
| `Equals(var, Constant)` | 提取参数绑定 → `metadata["formula_bindings"]`，写入 IR parameter |
| `Causes(cause, effect)` | 序列化 → `metadata["formula_atom"]` + `metadata["causal"]` |
| `Land(ops...)` | 验证所有子 formula，保留在 metadata 中（等 v0.6 connective lowering） |
| `Implies/Forall/Exists` | 验证类型，元数据序列化 |
| `Greater/LessEqual` | 验证 Term 操作数，元数据序列化 |
| `ClaimAtom(claim)` | 指向已有 claim 的 QID（跨公式图引用） |
| `UserPredicate/FunctionApp` | 编译时验证参数数量和域类型 |

## 类型安全保证

Formula AST 的核心设计原则是**编译时类型安全**——在 claim 构造时就捕获错误：

```python
# ❌ 编译时拒绝：参数数量不匹配
PredicateSymbol("Stable", arg_domains=(PatientDomain, Real))  # 期望 2 个参数
UserPredicate(Stable, (patient_x,))                             # 只给 1 个 → ValueError

# ❌ 编译时拒绝：域类型不匹配
FunctionSymbol("HbA1c", arg_domains=(PatientDomain,), result_domain=Real)
FunctionApp(HbA1c, (Constant(3.14, Probability),))  # Probability ≠ PatientDomain

# ❌ 编译时拒绝：在 Equals 中使用非 Term
Equals(left="not a term", right=Constant(1.0, Real))  # TypeError

# ✅ 正确用法
UserPredicate(Stable, (patient_x, Constant(2000, Real)))  # 参数数量 + 类型都匹配
```

## Formula AST vs 旧的 prose claim

| | 旧方式（prose claim） | 新方式（formula claim） |
|---|---|---|
| 声明 | `claim("p = 0.75")` | `claim("...", formula=equals(p, Constant(0.75, Prob)))` |
| 参数绑定 | 编译器解析字符串 | 编译器遍历 Equals AST 节点 |
| 类型检查 | 运行时隐式 | 构造时显式（`PrimitiveType.accepts()`） |
| 因果声称 | `claim("X causes Y")` | `causal(X, Y)` → `ClaimKind.CAUSAL` |
| 复合逻辑 | 嵌入自然语言 | `land(a, implies(b, c))` — 可机器遍历 |
| 下游用途 | 纯展示 | 编译器提取绑定、验证类型、降落到 IR |

## 与 Mendel/bayes 示例的关系

Mendel 示例中的 `parameter(p, 0.75)` 和 `equals(k, Constant(295, Nat))` 实际上
已经在用 Formula AST——`parameter()` 和 `claim(formula=...)` 的底层就是 `Equals`
predicate 节点。本示例展示了 Formula AST 的完整能力，从最简单的 `causal()` 糖衣
到自定义符号、量词、和 ClaimAtom 图桥接。