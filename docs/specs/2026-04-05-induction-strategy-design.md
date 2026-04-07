# Induction Strategy Design

> **Status:** Target design
> **Date:** 2026-04-05
> **Scope:** Gaia IR + Gaia Lang DSL + Skills

## Goal

将归纳（induction）从 Gaia IR 的 deferred 状态提升为正式支持的 CompositeStrategy 类型，同时保持 IR core 的原子性和正交性。

## Background

### 理论基础

归纳的微观结构是**溯因的并行重复**（见 `theory/04-reasoning-strategies.md` §2.3）：

```
Law ──┐
      ├──∨──→ D₁      D₁ ↔ Obs₁
AltExp₁ ─┘
      ⋮
Law ──┐
      ├──∨──→ Dₙ      Dₙ ↔ Obsₙ
AltExpₙ ─┘
```

后验（假设各 AltExpᵢ 在 Law 给定后条件独立）：`P(Law=1 | all Obsᵢ=1) = π(Law) / [π(Law) + (1−π(Law))·∏ᵢ ρᵢ]`

### 当前状态

Gaia IR core 当前 defer induction（`02-gaia-ir.md:573-586`），理由是它与 abduction 在语义上不正交。`formalize.py` 遇到 `type=induction` 直接抛错。

### 为什么现在引入

1. **归纳是科学推理中最常见的 pattern 之一**，defer 导致作者必须手写 n 条 abduction，体验差且易错
2. **CompositeStrategy 已存在**，归纳恰好是它的 canonical use case — 不需要引入新的原子 primitive
3. **语义标注价值**：多条 abduction 共享 conclusion 不等于归纳意图；CompositeStrategy 提供显式的语义标签，供 review / LKM / 可视化使用

## Design

### 核心定义

> **归纳 = CompositeStrategy(type=induction)，包装 n 条共享同一 conclusion (Law) 的 abduction 子策略。**

归纳效应（观测越多 → Law 越可信）是因子图拓扑的 emergent property：n 条 abduction 共享 Law 节点，BP 自然算出 ∏ᵢ ρᵢ → 0 的累积效应。不引入新的 Operator 类型或 formalize 逻辑。

### IR 表示

```
CompositeStrategy:
    type:           "induction"
    premises:       [Obs₁, Obs₂, ..., Obsₙ]  # 汇总（可含显式 AltExpᵢ）
    conclusion:     Law
    sub_strategies: [abd₁_id, abd₂_id, ..., abdₙ_id]

# 每条子策略是独立的 FormalStrategy（经 formalize 展开）
FormalStrategy:
    type:           "abduction"
    premises:       [Obsᵢ, AltExpᵢ]    # AltExpᵢ 可由 formalize 自动生成
    conclusion:     Law
    formal_expr:
        - disjunction([Law, AltExpᵢ], conclusion=Dᵢ)
        - equivalence([Dᵢ, Obsᵢ], conclusion=Eqᵢ)
```

**`law.strategy` 最终只指向 CompositeStrategy。** Top-down 模式中子 abduction 创建时会临时设 `law.strategy`，但 CompositeStrategy 创建时覆写为最终值。Bottom-up 模式中子 abduction 已设的值同样被覆写。

### 不引入的概念

- **GlobalAltExp / SystematicExpl**：归纳的原子定义是纯粹的"n 条溯因共享 conclusion"。全局替代解释是独立的建模选择，作者可在论证图中用其他已有机制（operator、strategy）表达，不属于归纳本身。
- **新的 Operator 类型**：归纳的所有结构由 abduction 的 disjunction + equivalence 骨架承载。
- **新的 formalize 逻辑**：CompositeStrategy 不直接 formalize（已有 `TypeError` guard）。子 abduction 走已有 `_build_abduction` 路径。

### DSL API

单一 `induction()` 函数，运行时检测两种模式：

```python
def induction(
    items: list[Knowledge] | list[Strategy],
    law: Knowledge | None = None,
    *,
    alt_exps: list[Knowledge | None] | None = None,
    background: list[Knowledge] | None = None,
    reason: ReasonInput = "",
) -> Strategy:
```

**模式检测机制：** 检查 `items[0]` 的类型（`isinstance(items[0], Strategy)`）。`Strategy` 和 `Knowledge` 是不相关的 dataclass，不会混淆。列表为空时直接报错（两种模式都至少需要 2 个元素）。不允许混合 Knowledge 和 Strategy。

#### 模式 1: Top-down（传 Knowledge 列表）

```python
law = claim("所有金属受热膨胀")
obs1 = claim("铁受热膨胀")
obs2 = claim("铜受热膨胀")
obs3 = claim("银受热膨胀")

induction([obs1, obs2, obs3], law)
```

行为：
1. 对每个 `(obsᵢ, altᵢ)` 调用已有 `abduction()` 函数创建子策略（每次调用会临时设 `law.strategy`，这是预期的）
2. 包装为 `_composite_strategy(type_="induction", conclusion=law, sub_strategies=[...])`
3. `_composite_strategy` 最终将 `law.strategy` 覆写为 CompositeStrategy（覆盖前面的临时值）

#### 模式 2: Bottom-up（传 Strategy 列表）

```python
abd1 = abduction(obs1, law, alt1)
abd2 = abduction(obs2, law, alt2)
abd3 = abduction(obs3, law, alt3)

induction([abd1, abd2, abd3])
```

行为：
1. 校验所有子策略的 `conclusion` 是同一个 claim（Python 对象 identity，即 `is` 比较）
2. 校验所有子策略的 `type == "abduction"`
3. 从子策略推导 `law`（如果传了 `law`，校验 identity 一致性）
4. 汇总 premises，包装为 CompositeStrategy
5. 将 `law.strategy` 覆写为 CompositeStrategy

#### AltExp 处理（仅 top-down 模式）

| 参数 | 行为 |
|------|------|
| `alt_exps=None`（默认） | 全部由 abduction formalize 自动生成 interface claim |
| `alt_exps=[alt1, None, alt3]` | 混合：有值的使用显式 claim，None 的自动生成 |
| `alt_exps=[alt1, alt2, alt3]` | 全部使用显式 claim |

长度必须与 observations 一致。Bottom-up 模式忽略 `alt_exps`（每个 abduction 已经自带）。

#### background 参数传播

`background` 传递给 CompositeStrategy 本身。Top-down 模式中，每个子 abduction 也会接收同一份 `background`。Bottom-up 模式中，子 abduction 各自已有 background，不会被覆盖。

#### 校验规则

- Top-down：`len(items) >= 2`（至少 2 个观测才构成归纳）
- Bottom-up：所有 Strategy 必须是 `type=abduction`，且 `conclusion` 相同
- `alt_exps` 提供时长度必须等于 `len(items)`

### 类型枚举

在 `StrategyType` 中添加：

```python
INDUCTION = "induction"   # CompositeStrategy wrapping shared-conclusion abductions
```

### Formalize 变更

移除 `formalize.py` 中 `type == "induction"` 的 `raise ValueError`。CompositeStrategy(type=induction) 不走 formalize — 已有 `TypeError` guard（`strategy.py:150-151`）阻止对 CompositeStrategy 调用 formalize。子 abduction 各自独立走 `_build_abduction` 路径。

### 编译器路径

`compile_strategy()` 的 dispatch 顺序已经正确：先检查 `s.sub_strategies`（→ `IrCompositeStrategy`），再检查 `s.type in _COMPILE_TIME_FORMAL_STRATEGIES`。`induction` 的 `sub_strategies` 非空，所以会走 `IrCompositeStrategy` 分支。子 abduction 的 `type=abduction` 在 `_COMPILE_TIME_FORMAL_STRATEGIES` 中，各自独立编译为 `IrFormalStrategy`。不需要修改编译器。

## 变更清单

### Protected layer（独立 PR）

| 文件 | 位置 | 变更 |
|------|------|------|
| `docs/foundations/gaia-ir/02-gaia-ir.md` | §3.3 type 表 `:359` | `induction` 行改为：`induction` / 无独立 strategy-level 参数 / CompositeStrategy / 包装 n 条共享结论的 abduction 子策略；归纳效应由因子图拓扑涌现 |
| `docs/foundations/gaia-ir/02-gaia-ir.md` | §3.5 命名策略 `:573-586` | 替换 defer 段落为正式的 CompositeStrategy 定义和示例 |

### Code（功能 PR）

| 文件 | 变更 |
|------|------|
| `gaia/ir/strategy.py` | 添加 `INDUCTION = "induction"` 到 `StrategyType` |
| `gaia/ir/formalize.py` | 移除 induction `raise ValueError` |
| `gaia/lang/dsl/strategies.py` | 添加 `induction()` 函数 |
| `gaia/lang/__init__.py` | 导出 `induction` |

### Skills

| 文件 | 变更 |
|------|------|
| `.claude/skills/gaia-ir-authoring/SKILL.md` | Step 4 添加 `induction` 用法示例 |
| `.claude/skills/paper-formalization/SKILL.md` | 添加 induction 识别和使用指导 |

### Tests

| 文件 | 变更 |
|------|------|
| `tests/gaia/lang/test_strategies.py` | top-down 模式测试（含/不含 alt_exps） |
| `tests/gaia/lang/test_strategies.py` | bottom-up 模式测试 |
| `tests/gaia/lang/test_strategies.py` | 校验规则测试（< 2 obs, 不一致 conclusion 等） |
| `tests/gaia/lang/test_compiler.py` | 编译后 IR 中 CompositeStrategy + sub abductions 正确 |

## 不变量

- Theory 层（`docs/foundations/theory/`）不修改 — 归纳的理论定义已经正确
- BP 层不修改 — CompositeStrategy 的 lowering 由子策略各自处理
- 现有 abduction 行为不变 — induction 完全复用，不修改 `_build_abduction`
- 现有 `composite()` DSL 函数不变 — `induction()` 是独立的便捷函数
