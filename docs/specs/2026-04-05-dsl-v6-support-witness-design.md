# Gaia DSL v6: Claim + Support 设计

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | Gaia Lang v6 authoring model |
| 非目标 | 本文不直接修改 Gaia IR protected contract |

---

## 1. 问题重述

PR 333 的 v6 草稿试图同时解决四件事：

1. Python DSL 的表面语法
2. Curry-Howard 对齐
3. 科学论证中的工具调用 / Python 代码整合
4. Gaia IR 与 review / parameterization 的落点

这四件事混在一起时，最容易出现两个错误：

- 把"函数返回 Claim"误当成"Support 可以消失"
- 把"代码能运行 / tool 能执行"误当成"科学命题已经被证明"

本文给出一个更稳定的 v6 设计：围绕 **Claim + Support 继承树** 两个核心概念，用 Support 子类区分不同的支撑方式，所有构造器 callable、返回 Claim。

### 1.1 给团队解释的一句话

- `Claim` 是要被相信或质疑的命题
- `Support` 是"为什么这些前提能支持这个结论"——它有多种子类型（formal、infer、execute、check、formal_proof、composite）

如果只想记一句话：

> 作者看到的永远是 **Claim in, Claim out**。Support 是内部自动创建的支撑结构。

---

## 2. 第一性原理

### 2.1 Gaia 的中心对象不是程序，而是被相信的命题

Gaia 的输出是 belief over claims。无论作者写的是自然语言、Python、tool invocation、实验记录，最终被推理系统消费的，仍然是：

- 哪些 `Claim` 被引入
- 它们之间有哪些 `Support`（及其子类型）

### 2.2 Curry-Howard 给的是逻辑骨架，不是认识论全套

Curry-Howard 最适合约束 Gaia 的核心结构：

| Gaia | Curry-Howard 中最接近的对象 | 作用 |
|------|-----------------------------|------|
| `Claim` | proposition / type | 被支撑的命题 |
| `Support` | implication-shaped constructor | 从前提到结论的支撑结构 |

但 Curry-Howard 不会自动回答 execution 是否可信、测试覆盖是否充分、模型是否适用。这些问题通过 **将相关假设显式声明为 Claim** 来解决，而不是引入额外的概念层。

### 2.3 科学推理的关键不是"程序即证明"，而是"程序产出的结果需要桥接到科学结论"

在纯证明助手里，proof term 可以直接 inhabit proposition。

在 Gaia 里，多数程序 / 工具 / 实验不会直接证明科学命题。更常见的模式是：

1. execution 产出一个 result claim（如"CFD 计算得到压力场 P"）
2. 通过 bridge claim 和 deduction 连接到科学结论

因此，v6 不应把"代码"和"科学 claim"直接等同，而应要求显式的桥接。

### 2.4 Python operator 和 type system 应如何复用

- 可以复用 Python operator 和 type hints 作为 authoring facade
- 但 lowering 后仍应回到显式的 Claim + Support
- Python type system 回答"值长什么样"，Gaia 回答"命题是否成立、如何被支持"

> Python operators and types may shape the syntax, but they should not replace the ontology.

---

## 3. 核心模型：Claim + Support 继承树

### 3.1 Claim

`Claim` 是 truth-bearer。它是 Gaia belief 的基本对象。

Claim 的要求：

- self-contained
- 可被支撑、反驳、复用
- 在图中承担 prior / posterior

不是 Claim 的东西：

- 某次 shell 执行过程本身（→ provenance，记在 support.metadata）
- 某段 Python 源码文本本身
- 某个日志文件路径本身

### 3.2 Support 继承树

`Support` 替代 `Strategy` 作为 v6 authoring 术语。它是基类，通过子类区分不同的支撑方式：

```
Support (base)
├── Formal
│   ├── Deduction
│   ├── Abduction        # observation, alternative
│   ├── Analogy          # source, bridge
│   ├── Extrapolation    # source, continuity
│   ├── Elimination      # exhaustiveness, excluded
│   ├── CaseAnalysis     # exhaustiveness, cases
│   └── MathInduction    # base, step
├── Infer                # infer() — general CPT
│   └── NoisyAnd         # noisy_and(), claim(..., given=[...])
├── Execution
├── Check
├── FormalProof
└── Composite
```

**核心原则：所有 support 构造器都是 callable 的，返回 Claim。**

```python
c = deduction("C", given=[a, b])              # → Claim (Deduction)
c = abduction("H", observation=obs)           # → Claim (Abduction)
c = infer("C", given=[a, b])                  # → Claim (Infer)
c = execute(run_cfd, given=[...], returns="…") # → Claim (Execution)
c = check(run_tests, given=[...], returns="…") # → Claim (Check)
c = formal_proof("…", system="lean", ...)      # → Claim (FormalProof)
```

作者永远面对 **Claim in, Claim out**。Support 在内部自动创建，挂在 `claim.support` 上。

**基数说明：一个 Claim 只挂一条 Support。** 如果同一个结论需要多条独立的 support 路径，应使用 `Composite` 聚合：

```python
s1 = support(family="deduction", premises=[a, b], conclusion=c)
s2 = support(family="induction", premises=[obs1, obs2], conclusion=c)
composite_support(
    premises=[a, b, obs1, obs2],
    conclusion=c,
    sub_supports=[s1, s2],
)
```

### 3.3 对推理有影响的假设必须是 Claim

v6 的一个关键设计决策是：**不设"介于 Claim 和 metadata 之间"的灰色地带。**

- 对推理有影响的假设（solver 已验证、测试集覆盖目标场景、模型在目标条件下适用）→ 必须是 `given` 中的 Claim
- 纯 provenance 信息（运行时长、文件路径、random seed、库版本）→ 记在 `support.metadata`

判定规则：

> 需要 review、复用或反驳 → Claim。纯记录 → metadata。

---

## 4. Support 子类详述

### 4.1 Formal 及其子类

有 canonical skeleton 的 support，核心语义由结构决定。每个 formal family 是一个独立子类，用类型安全字段表达语义角色：

| 子类 | 语义角色字段 |
|------|------------|
| `Deduction` | `given: list[Claim]` |
| `Abduction` | `observation: Claim`, `alternative: Claim \| None` |
| `Analogy` | `source: Claim`, `bridge: Claim` |
| `Extrapolation` | `source: Claim`, `continuity: Claim` |
| `Elimination` | `exhaustiveness: Claim`, `excluded: list[tuple[Claim, Claim]]` |
| `CaseAnalysis` | `exhaustiveness: Claim`, `cases: list[tuple[Claim, Claim]]` |
| `MathInduction` | `base: Claim`, `step: Claim` |

reviewer 不直接给 cp，而是 review premise/interface claim 的 prior 和 reasoning judgment。

### 4.2 Infer 及其子类

没有稳定 canonical skeleton 的粗粒度 support：

`Infer` 本身就是通用 CPT（2^k 参数），`infer()` 直接创建它。`NoisyAnd` 是它的特化——所有前提联合必要，由 `noisy_and()` 和 `claim(..., given=[...])` 创建。

reviewer 直接给 support-level 条件概率。

### 4.3 Execution

运行计算，产出 result claim：

```python
pressure = execute(
    run_cfd,
    given=[geometry, bc, solver_validated],
    returns="CFD 计算得到方腔内的压力场 P",
)
```

- `callable_ref`：要执行的函数或工具引用
- `execution_backend`：执行环境（python / shell / remote）
- 这些字段是 support 子类的类型安全属性，不是 dict

注意：`execute()` 通常先产出一个 result claim，再通过 deduction + bridge claim 连接到科学结论：

```python
match_criterion = claim("压力场与参考解 L2 误差 < 1% 即视为吻合")
conclusion = deduction(
    "模拟结果支持方腔流在 Re=100 下存在稳定涡结构",
    given=[pressure, match_criterion],
)
```

### 4.4 Check

验证实现/artifact 满足规范，产出 validity claim：

```python
solver_ok = check(
    run_regression_tests,
    given=[spec, suite_covers_target],
    returns="求解器在回归测试集上通过了所有精度检查",
)
```

- `checker_ref`：检查函数引用
- `checker_args`：检查参数

`check()` 支撑的是 validity claim（实现满足规范），通常不直接支撑高层 scientific claim。

### 4.5 FormalProof

形式证明系统验证通过，产出 proof-backed claim：

```python
stability = formal_proof(
    "在假设 H 下，格式 S 是稳定的",
    system="lean",
    theorem_ref="FluidLab.Stability.main",
    given=[scheme_spec, assumption_h],
)
```

- `system`：证明系统（lean / coq / isabelle）
- `theorem_ref`：定理引用
- `proof_args`：证明参数

这是所有 support 子类中最接近 Curry-Howard 的，但仍然可能需要 bridge claims 才能从形式模型走到科学命题。

### 4.6 Composite

聚合多条子 support：

```python
composite_support(
    premises=[a, b, obs1, obs2],
    conclusion=c,
    sub_supports=[s1, s2],
)
```

用于 induction bundle（多条 abduction 聚合）、converging evidence（多条独立路径支撑同一结论）等场景。

---

## 5. Review 与 Parameterization

### 5.1 Review 的两类对象

v6 的 review surface：

1. `review_claim(...)` — 给 claim prior
2. `review_support(...)` — 给 support judgment / cp

其中 `review_support` 的行为取决于 support 子类：

| Support 子类 | reviewer 怎么评估 |
|-------------|------------------|
| Formal | judgment + justification（不直接给 cp） |
| Infer | 直接给 conditional probability |
| Execution | review 前提 claims（solver 已验证等） |
| Check | review 前提 claims（测试集覆盖等） |
| FormalProof | review 前提 claims + 证明系统可信度 |
| Composite | 递归 review 各条 sub_support |

### 5.2 不同 support 子类的 review 规则

#### Formal

review 的重点：

- premise / interface claim 的 prior
- generated public interface claims
- reasoning judgment / justification

#### Infer

继续直接给 support-level 条件概率。

#### Execution / Check / FormalProof

对推理有影响的假设已经是前提 Claim，reviewer 直接 review 这些 claim 的 prior。provenance 信息（运行时长、版本等）在 `support.metadata` 中，不参与 BP。

---

## 6. 运行时对象

### 6.1 类层次

```python
@dataclass
class Support:
    """基类"""
    premises: list[Claim]
    conclusion: Claim
    background: list[Knowledge] = field(default_factory=list)
    reason: ReasonInput = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Formal 及其子类 ---

@dataclass
class Formal(Support):
    """Formal 基类"""
    pass

@dataclass
class Deduction(Formal):
    pass  # premises 即 given

@dataclass
class Abduction(Formal):
    observation: Claim
    alternative: Claim | None = None

@dataclass
class Analogy(Formal):
    source: Claim
    bridge: Claim

@dataclass
class Extrapolation(Formal):
    source: Claim
    continuity: Claim

@dataclass
class Elimination(Formal):
    exhaustiveness: Claim
    excluded: list[tuple[Claim, Claim]]

@dataclass
class CaseAnalysis(Formal):
    exhaustiveness: Claim
    cases: list[tuple[Claim, Claim]]

@dataclass
class MathInduction(Formal):
    base: Claim
    step: Claim


# --- Infer ---

@dataclass
class Infer(Support):
    """infer() — general CPT"""
    pass

@dataclass
class NoisyAnd(Infer):
    """noisy_and(), claim(..., given=[...])"""
    pass


# --- Execution-backed ---

@dataclass
class Execution(Support):
    callable_ref: Callable | str = ""
    execution_backend: str | None = None

@dataclass
class Check(Support):
    checker_ref: Callable | str = ""
    checker_args: dict[str, Any] = field(default_factory=dict)

@dataclass
class FormalProof(Support):
    system: str = ""
    theorem_ref: str = ""
    proof_args: dict[str, Any] = field(default_factory=dict)


# --- Composite ---

@dataclass
class Composite(Support):
    sub_supports: list[Support] = field(default_factory=list)
```

### 6.2 Claim

```python
@dataclass
class Claim(Knowledge):
    support: Support | None = None
```

`claim.support` 保持单值。多条 support 通过 `Composite` 聚合。

### 6.3 `claim(..., given=[...])` 的地位

`claim(..., given=[...])` 仍然保留，作为最轻量的 sugar：

- 当作者不关心 support 子类，只想表达"这些前提支撑这个结论"时，用它
- 内部创建 `NoisyAnd`

---

## 7. 与现有 Gaia IR 的关系

### 7.1 不立即修改 protected contract

v6 的第一阶段只改变 Gaia Lang authoring model 与术语，不直接破坏现有 IR 边界。

### 7.2 Phase 1 映射

| v6 概念 | v5 / 当前 IR 映射 |
|--------|-------------------|
| `Claim` | `Knowledge(type="claim")` |
| `Support` (base) | `Strategy` |
| `Formal` | 现有 named strategy + formalization |
| `Infer` | `infer` / `noisy_and` |
| `Execution` | 先在 Gaia Lang 侧定义；IR protected contract 后续设计 |
| `Check` | 同上 |
| `FormalProof` | 同上 |
| `Composite` | `Strategy(sub_strategies=[...])` |

### 7.3 后续 protected-layer 工作

若 v6 在 authoring 层验证有效，再单独推进：

1. Execution / Check / FormalProof 的 protected IR contract
2. `review_support(...)` 对不同子类的 dispatch 规则

---

## 8. 与 v5 的兼容性和迁移

### 8.1 API 签名变化总结

| v5 签名 | v6 签名 | 变化性质 |
|---------|--------|---------|
| `deduction(premises, conclusion) -> Strategy` | `deduction("C", given=[a, b]) -> Claim` | 返回类型 + 参数风格 |
| `abduction(obs, hyp, alt) -> Strategy` | `abduction("H", observation=obs) -> Claim` | 返回类型 + 参数风格 |
| `induction(items, law) -> Strategy` | `induction("L", observations=[...]) -> Claim` | 返回类型 + 参数风格 |
| `claim("C", given=[a, b]) -> Knowledge` | `claim("C", given=[a, b]) -> Claim` | 返回类型细化（兼容） |
| `Knowledge.strategy: Strategy \| None` | `Claim.support: Support \| None` | rename（语义不变） |
| `review_strategy(...)` | `review_support(...)` | rename |

### 8.2 迁移原则

1. **Phase 1 双入口**：v5 签名继续可用，发出 `DeprecationWarning`，内部统一转为 v6 语义
2. **不强制 re-author**：已发布的 v5 packages 可在不修改源码的情况下继续 compile
3. **按需迁移**：新 package 推荐 v6 syntax；旧 package 在下次 major revision 时迁移
4. **工具辅助**：提供 `gaia migrate v5-to-v6` CLI 命令做机械化转换

---

## 9. 设计决策摘要

| 决策 | 结论 |
|------|------|
| `Strategy` 是否改名 | 在 v6 中改为 `Support`（基类），子类区分不同支撑方式 |
| "函数返回 Claim"是否意味着 support 消失 | 否。Support 仍是一等对象，返回 Claim 只是 surface sugar |
| 是否需要 Witness 作为独立概念 | 否。对推理有影响的 → Claim；纯记录 → support.metadata |
| 是否需要 Execution 作为独立概念层 | 否。吸收进 Support 子类（Execution 等） |
| `claim.support` 是单值还是列表 | 单值。多条 support 通过 Composite 聚合 |
| Support 用扁平 family 字段还是继承树 | 全继承树。每个 formal family 也是独立子类，类型安全表达语义角色 |
| 所有 support 构造器是否都返回 Claim | 是。Claim in, Claim out |
| `execute` 是否直接产出最终 scientific claim | 通常不应如此；更自然是先产出 result claim，再通过 bridge 连接 |
| `check` 是否等于科学证明 | 否。它主要支撑 validity claim |
| `formal_proof` 是否应另开 ontology | 否。它是 Support 的一个子类 |
| Curry-Howard 主要覆盖哪里 | Claim + Support 结构 |
| v5 已发布 packages 是否需要重写 | 否。Phase 1 双入口保证 v5 语法继续可用 |

---

## 10. 非目标

本文不试图在本轮同时解决：

- dependent typing
- execution cache / reproducibility protocol
- Execution / Check / FormalProof 的 IR protected contract

---

## 11. 推荐实施顺序

### Phase 1: Support 继承树 + claim-returning surface

- 引入 `Support` 基类和六个子类
- 保留 `Strategy` 作为 Phase 1 兼容实现
- 所有构造器改为返回 Claim

### Phase 2: 类型层

- 引入 `Claim / Setting / Question` subclasses
- 收窄 DSL 签名到 `list[Claim]`

### Phase 3: execution-backed support

- 落地 `execute` / `check` / `formal_proof` 的 Gaia Lang API
- 设计 IR protected contract

### Phase 4: review 扩展

- `review_support(...)` 对不同子类的 dispatch

---

## 12. 一句话版本

Gaia v6 的核心是：

> 作者看到的永远是 **Claim in, Claim out**。不同的支撑方式（formal、infer、execute、check、formal_proof、composite）由 Support 继承树的子类区分，内部自动创建，挂在 `claim.support` 上。
