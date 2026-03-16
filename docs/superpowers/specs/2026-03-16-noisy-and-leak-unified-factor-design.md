# Design: Noisy-AND + Leak 统一势函数模型

| 属性 | 值 |
|------|---|
| 日期 | 2026-03-16 |
| 状态 | Draft |
| 影响文档 | `docs/foundations/theory/inference-theory.md`（主），`docs/foundations/bp-on-graph-ir.md`（从） |

---

## 动机

当前 `inference-theory.md` 的 reasoning factor 势函数在前提不全为真时设为 `1.0`（无约束）。这等价于 P(C|¬前提) = 0.5，违反了 Jaynes 的第四三段论（前提假 → 结论更不可信）。

当前 contradiction 和 equivalence 使用 gate 语义（关系节点只读，不接收 BP 消息），阻止了双向信息流，违反 Jaynes 核心原则：所有命题的可信度都应随证据更新。

## 变更摘要

1. **Reasoning factor**：引入 noisy-AND + leak 势函数，前提不全为真时 potential = ε（非 1.0）
2. **Contradiction / Equivalence**：移除 gate 语义，关系节点成为普通 factor 参与者
3. **Instantiation / Retraction**：保持不变（已通过四三段论验证）
4. **文档重构**：`inference-theory.md` 重组为"为什么 → 是什么 → 怎么算"

## 理论依据

### Jaynes 四三段论

从 Cox 定理推导的乘法规则、加法规则、贝叶斯定理，可以得到四个量化三段论：

1. **Modus Ponens**：前提真 → P(C|∧Pᵢ) = p
2. **弱确认**：结论真 → P(Pᵢ|C) > P(Pᵢ)
3. **Modus Tollens**：结论假 → P(Pᵢ|¬C) < P(Pᵢ)
4. **弱否定**：前提假 → P(C|¬Pᵢ) 应该很低

旧模型的 potential=1.0 使第四三段论失效：P(C|¬Pᵢ) = prior(C)，不下降。

### Noisy-AND + Leak

Gaia 的 chain 是 noisy-AND 语义：所有前提必须同时成立，结论才以概率 p 成立。"Noisy" = 即使前提全真，结论也可能因推理不完美而不成立（概率 1-p）。

Leak probability（Henrion 1989）编码"前提不全为真时，结论仍然成立的背景概率"。对 Gaia 的 chain，这个值应该极小（ε ≈ Cromwell 下界 10⁻³），因为前提是结论的近似必要条件。

势函数：

```
φ(P₁,...,Pₙ, C):
  all Pᵢ=1, C=1  →  p
  all Pᵢ=1, C=0  →  1-p
  any Pᵢ=0, C=1  →  ε        (leak)
  any Pᵢ=0, C=0  →  1-ε
```

在此模型下，四三段论全部成立。具体数值验证（π₁=0.9, π₂=0.8, p=0.9, ε=0.001）：

- 三段论 1：P(C|P₁=1,P₂=1) = 0.9 ✓
- 三段论 2：P(P₁|C=1) = 0.9997 > 0.9 ✓
- 三段论 3：P(P₁|C=0) = 0.716 < 0.9 ✓
- 三段论 4：P(C|P₁=0) ≈ ε ≈ 0.001 ✓

### 统一约束 Factor

Contradiction 和 equivalence 的关系节点从 gate 改为普通参与者：

**Contradiction**：

```
φ(C_contra, A₁,...,Aₙ):
  C_contra=1, all Aᵢ=1  →  ε    (矛盾成立且都真 → 几乎不可能)
  其他                    →  1
```

三个方向的消息：
- 关系成立 + 一方可信 → 压制另一方（保持）
- 弱证据先让步（保持，从 odds 乘法自然涌现）
- 双方都强 → 质疑关系本身（新能力，旧 gate 无法实现）

**Equivalence**：

```
φ(C_equiv, A, B):
  C_equiv=1, A=B  →  1-ε   (等价成立 + 一致 → 好)
  C_equiv=1, A≠B  →  ε     (等价成立 + 不一致 → 坏)
  C_equiv=0, 任意  →  1     (不等价 → 无约束)
```

### 不变的 Factor

**Instantiation**：potential=1.0 when schema=0 是正确的（¬∀x.P(x) ⊬ ¬P(a)）。

**Retraction**：potential=1.0 when E=0 是正确的（撤回证据不成立 ≠ 支持结论。C 由其他 factor 决定）。

### 合规性矩阵

```
                    三段论1  三段论2  三段论3  三段论4  变更
Reasoning (新)       ✓       ✓       ✓       ✓       noisy-AND + leak
Instantiation        ✓       ✓(弱)   ✓       ✓(正确)  不变
Retraction           ✓       ✓       ✓       ✓(正确)  不变
Contradiction (新)   ✓       ✓       ✓       ✓(新)    去 gate
Equivalence (新)     ✓       ✓       ✓       ✓(新)    去 gate
```

## 文档重构设计

由于 `bp-on-graph-ir.md` 仍是当前 `main` 上已成文的 runtime 语义参考，而它的同步改写会在后续 PR 完成，因此本次重写后的 `inference-theory.md` 必须显式标注为 **v2.0 target design**，不能表述成“当前 foundations 已完全收敛到该模型”。

`inference-theory.md` 重组为：

```
§1 Jaynes 第一性原理
   §1.1 Cox 定理与三条规则（精简引入，指向 theoretical-foundation.md）
   §1.2 四个三段论（完整推导）
   §1.3 对推理引擎的要求（四条设计约束）

§2 统一势函数模型
   §2.1 从条件概率到 Factor Potential
   §2.2 Noisy-AND + Leak：推理 factor 的势函数
   §2.3 约束 factor 的势函数（contradiction、equivalence）
   §2.4 各 factor 类型的合规性验证

§3 蕴含格中的 Abstraction 与 Induction
   （原 §2，基本不变，末尾加一段关联势函数约束）

§4 五种 Factor 类型
   §4.1 Reasoning（deduction / induction / abstraction / retraction）
   §4.2 Instantiation
   §4.3 Contradiction（三变量约束 factor，无 gate）
   §4.4 Equivalence（三变量约束 factor，无 gate）

§5 信念传播算法
   §5.1 因子图（原 §1.1）
   §5.2 Sum-Product 消息传递（原 §1.5）
   §5.3 Loopy BP 与 Damping（原 §1.3-§1.4）
   §5.4 Cromwell's Rule
   §5.5 BP 与 Jaynes 的闭环对应

§6 已知局限与演进方向（原 §4，更新）
§7 逻辑编程技术启发（原 §5，不变）
附录 A 术语对照（更新）
附录 B 与相关系统对比（不变）
```

## 对 bp-on-graph-ir.md 的影响

`bp-on-graph-ir.md` 是下游文档，需要同步更新：

- §3.1 Reasoning Factor：potential 表加 leak 行
- §3.3 Mutex Constraint：移除 gate，C_contra 成为普通参与者
- §3.4 Equiv Constraint：移除 gate，C_equiv 成为普通参与者
- §4 Gate Semantics：整节删除（或保留为历史设计说明）

这些变更在 `inference-theory.md` 完成后作为后续 PR 处理。

## 不在此次变更范围

- 代码实现（`libs/inference/bp.py` 的 `_evaluate_potential()` 修改）
- 测试更新
- Leak 参数的可配置性（当前默认 ε = Cromwell 下界）
- `theoretical-foundation.md` 的变更（该文档讲的是 Jaynes 纲领，不涉及具体势函数）
