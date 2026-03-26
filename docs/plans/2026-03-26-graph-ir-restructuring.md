# Gaia IR 重构 Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 按照设计文档 `docs/specs/2026-03-26-graph-ir-restructuring-design.md`，更新 `docs/foundations/gaia-ir/` 下所有文档，完成推理层与计算层分离的四实体架构重写。

**Architecture:** 将原 KnowledgeNode + FactorNode 二实体架构重构为 Knowledge + Strategy + Operator + FormalExpr 四实体架构。Strategy 承载 ↝ 语义（noisy-AND），Operator 承载确定性算子，FormalExpr 记录 Strategy→Operator 展开。

**Tech Stack:** Markdown 文档（无代码变更）

**Important context:**
- 设计文档: `docs/specs/2026-03-26-graph-ir-restructuring-design.md`
- Theory 引用: `docs/foundations/theory/03-propositional-operators.md`（算子定义）, `docs/foundations/theory/04-reasoning-strategies.md`（策略微观结构）, `docs/foundations/theory/06-factor-graphs.md`（势函数映射）
- 本目录是 Protected Contract Layer，变更需要独立 PR

---

## Chunk 1: gaia-ir.md 重写

### Task 1: gaia-ir.md — §1 Knowledge（原 §1 KnowledgeNode）

**Files:**
- Modify: `docs/foundations/gaia-ir/gaia-ir.md:1-145`

- [ ] **Step 1: 更新文档头和导航**

将开头的状态说明更新，保持 Protected Contract Layer 警告不变。更新导航链接，增加对设计文档的引用。

- [ ] **Step 2: 重写 §1 标题和引导文字**

将 `## 1. Knowledge 节点（变量节点）` 改为 `## 1. Knowledge（命题节点）`。引导段更新为："Knowledge 表示命题。对应原 KnowledgeNode，schema 基本一致。"

- [ ] **Step 3: 重写 §1.1 Schema**

将 KnowledgeNode schema 替换为 Knowledge schema（设计文档 §3.2）：

```
Knowledge:
    id:                     str              # lcn_ 或 gcn_ 前缀
    type:                   str              # claim | setting | question | template
    parameters:             list[Parameter]  # 仅 template：自由变量列表
    source_refs:            list[SourceRef]
    metadata:               dict | None

    # ── local 层 ──
    content:                str | None

    # ── 来源追溯 ──
    provenance:             list[PackageRef] | None

    # ── global 层 ──
    representative_lcn:     LocalCanonicalRef | None
    member_local_nodes:     list[LocalCanonicalRef] | None
```

字段使用表和身份规则保持不变，仅将 `KnowledgeNode` 全部替换为 `Knowledge`。

- [ ] **Step 4: 确认 §1.2 四种知识类型不变**

四种类型（claim/setting/question/template）定义、示例均保持不变。仅更新引用，将 `knowledge 节点` 改为 `Knowledge`，`factor` 改为 `Strategy`。

- [ ] **Step 5: 提交**

```bash
git add docs/foundations/gaia-ir/gaia-ir.md
git commit -m "docs(gaia-ir): rename KnowledgeNode to Knowledge in §1"
```

---

### Task 2: gaia-ir.md — §2 Strategy（原 §2 FactorNode）

**Files:**
- Modify: `docs/foundations/gaia-ir/gaia-ir.md:146-356`

- [ ] **Step 1: 重写 §2 标题和引导文字**

将 `## 2. Factor 节点（因子节点）` 改为 `## 2. Strategy（推理声明）`。引导段改为："Strategy 表示推理声明——前提通过某种推理支持结论。是 ↝ 的载体，采用 noisy-AND 语义。对应原 FactorNode。"

- [ ] **Step 2: 重写 §2.1 Schema**

将 FactorNode schema 替换为 Strategy schema（设计文档 §3.3）：

```
Strategy:
    strategy_id:    str                # lcs_ 或 gcs_ 前缀（local/global canonical strategy）
    scope:          str                # "local" | "global"
    stage:          str                # initial | candidate | permanent

    # ── 统一类型 ──
    type:           str                # 见 §2.2

    # ── 连接 ──
    premises:       list[str]          # Knowledge IDs（仅 claim premise 创建 BP 边）
    conclusion:     str | None         # 单个输出 Knowledge

    # ── 条件概率（值在 parameterization 层） ──
    # type ∈ {infer, None}:        [q₁,...,qₖ], qᵢ = P(C=1 | Aᵢ=1, 其余前提=1)
    # type = soft_implication:     [p₁, p₂],    p₁ = P(C=1|A=1), p₂ = P(C=0|A=0)
    # type ∈ {9 strategies}:       不需要（有 FormalExpr，参数在 Operator 层）
    conditional_probabilities: list[float] | None

    # ── local 层 ──
    steps:          list[Step] | None
    weak_points:    list[str] | None

    # ── 追溯 ──
    source_ref:     SourceRef | None
    metadata:       dict | None        # 包含 context: list[str] 等
```

注意：
- ID 前缀从 `lcf_`/`gcf_` 改为 `lcs_`/`gcs_`
- 删除 `category` 和 `reasoning_type` 字段
- 新增统一 `type` 字段
- 新增 `conditional_probabilities` 字段（替代 parameterization 层的单 float `probability`）
- 删除 `subgraph` 字段（被 FormalExpr 替代）

- [ ] **Step 3: 重写 §2.2 统一类型系统**

替换原来的"三维类型系统"（category/stage/reasoning_type）为统一类型字段（设计文档 §3.3.1）。

将原 §2.2 替换为新的 `### 2.2 统一类型字段`：

```
type:
    # 推理（经历 lifecycle: initial → candidate → permanent）
    infer                      # 默认，未分类推理（noisy-AND，需要 conditional_probabilities）
    soft_implication            # 单前提完整二参数模型（需要 conditional_probabilities）

    # 9 种命名策略（经历 lifecycle，自带 FormalExpr，不需要 conditional_probabilities）
    deduction                  # 演绎
    abduction                  # 溯因
    induction                  # 归纳
    analogy                    # 类比
    extrapolation              # 外推
    reductio                   # 归谬
    elimination                # 排除
    mathematical_induction     # 数学归纳
    case_analysis              # 分情况讨论

    # 非推理（不经历 lifecycle）
    toolcall                   # 计算 / 工具调用
    proof                      # 形式化证明
```

包含 type → 属性派生表（设计文档 §3.3.1 的表）。

- [ ] **Step 4: 重写 §2.3 Noisy-AND 语义**

新增 `### 2.3 Noisy-AND 语义` 小节（设计文档 §3.3.2 内容）。解释：
- ∧ + ↝ 隐含结构
- 每个前提的独立条件概率 qᵢ
- Soft-implication 模式（type=soft_implication 时的 [p₁, p₂]）
- 与 theory §5 的对应关系

- [ ] **Step 5: 重写 §2.4 Lifecycle**

替换原来的 stage 说明为新的 lifecycle 描述（设计文档 §3.3.3）：

```
type=infer（默认）
    ↓ reviewer 识别策略
type=<named_strategy>（自动获得 FormalExpr）
    ↓ review 验证
stage=permanent
```

- [ ] **Step 6: 更新 §2.5 合法组合与不变量**

更新原 §2.3 的合法组合表为新的 type 体系。更新不变量列表中的术语（FactorNode→Strategy, knowledge node→Knowledge 等）。

- [ ] **Step 7: 更新 §2.6 Premise/WeakPoint/Context 区别**

保留原 §2.4 的三者区别说明，仅将术语从 factor/knowledge 替换为 Strategy/Knowledge。

- [ ] **Step 8: 更新 §2.7 BP 参与规则**

保留原 §2.5 的 BP 参与规则，更新术语。将原 §2.5 中 "Non-claim premise 在 BP 中被跳过" 这些规则原样保留。

- [ ] **Step 9: 提交**

```bash
git add docs/foundations/gaia-ir/gaia-ir.md
git commit -m "docs(gaia-ir): replace FactorNode with Strategy in §2, unify type system"
```

---

### Task 3: gaia-ir.md — §3 Operator + §4 FormalExpr（新章节）

**Files:**
- Modify: `docs/foundations/gaia-ir/gaia-ir.md`（在 §2 之后新增 §3 和 §4）

- [ ] **Step 1: 新增 §3 Operator（结构约束）**

在原 §2 之后新增 `## 3. Operator（结构约束）`（设计文档 §3.4）。内容包括：

Schema:
```
Operator:
    operator_id:    str                # lco_ 或 gco_ 前缀
    scope:          str                # "local" | "global"
    operator:       str                # 算子类型
    variables:      list[str]          # 连接的 Knowledge IDs（有序）
    conclusion:     str | None         # 有向算子的输出（无向算子为 None）
    stage:          str                # candidate | permanent
    source:         str                # "standalone" | "formal_expr:<strategy_id>"
    source_ref:     SourceRef | None
    metadata:       dict | None
```

算子类型与势函数表（6 种算子：implication, equivalence, contradiction, complement, disjunction, conjunction）。

来源说明（standalone vs formal_expr）。

- [ ] **Step 2: 新增 §4 FormalExpr — Schema + BP 编译规则**

新增 `## 4. FormalExpr（Strategy → Operator 展开）`（设计文档 §3.5）。内容包括：

Schema:
```
FormalExpr:
    formal_expr_id:          str
    source_strategy_id:      str
    operators:               list[Operator]
    intermediate_knowledges: list[Knowledge]
```

BP 编译规则（统一为一条）：
```
if Strategy 有 FormalExpr:
    BP 在 FormalExpr 的 Operator 层运行
    Strategy 自身不需要 conditional_probabilities
    不确定性转移到中间 Knowledge 的先验 π 上
else:
    BP 将 Strategy 编译为 ↝ 因子
    使用 Strategy 的 conditional_probabilities
```

- [ ] **Step 3: 新增 §4.1 确定性策略 FormalExpr 模板**

添加 5 种确定性策略的展开模板（设计文档 §3.5.1 上半部分）：
- deduction（∧ + →）
- mathematical_induction（∧ + →，语义区别于 deduction）
- reductio（→ + ⊗ + ⊕）
- elimination（n×⊗ + n×⊕ + ∧ + →）
- case_analysis（∨ + n×(∧ + →)）

每个模板包含 Strategy 输入、intermediate Knowledges、Operators 列表。

- [ ] **Step 4: 新增 §4.2 非确定性策略 FormalExpr 模板 + §4.3 层级规则**

添加 4 种非确定性策略的展开模板（设计文档 §3.5.1 下半部分）：
- abduction（→ + ↔，不确定性来自中间 Knowledge O 的先验）
- induction（n×(→ + ↔)，溯因的并行重复）
- analogy（∧ + →，不确定性来自 BridgeClaim 先验）
- extrapolation（∧ + →，不确定性来自 ContinuityClaim 先验）

然后添加 §4.3 FormalExpr 层级规则（设计文档 §3.5.2）：
- 只在 global 层产生
- 确定性策略可自动生成
- 非确定性策略需要手动创建中间 Knowledge 并赋先验

- [ ] **Step 5: 提交**

```bash
git add docs/foundations/gaia-ir/gaia-ir.md
git commit -m "docs(gaia-ir): add Operator §3 and FormalExpr §4 entities"
```

---

### Task 4: gaia-ir.md — §5 规范化更新 + §6 撤回更新 + 映射表

**Files:**
- Modify: `docs/foundations/gaia-ir/gaia-ir.md`（原 §3 规范化节→新 §5，原 §2.7 撤回→新 §6）

- [ ] **Step 1: 更新规范化章节编号和术语**

将原 §3 规范化改为 §5。全局替换术语：
- `KnowledgeNode` → `Knowledge`
- `FactorNode` → `Strategy`
- `knowledge node` → `Knowledge`
- `factor` → `Strategy`（在 factor lifting 上下文中）
- `knowledge` → `Knowledge`

- [ ] **Step 2: 更新 §5.1 equivalent candidate 机制**

原来 canonicalization 创建的 equivalent candidate 是 `FactorNode(reasoning_type=equivalent)`。现在改为 `Operator(operator=equivalence, source="standalone", stage=candidate)`。更新对应描述和 CanonicalBinding schema。

- [ ] **Step 3: 更新 §5.5 Factor 提升为 Strategy 提升**

将原 §3.5 "Factor 提升" 改为 "Strategy 提升"。前缀映射改为 `lcs_ → gcs_`。说明 global Strategy 不携带 steps。

- [ ] **Step 4: 更新 §6 撤回（retraction）**

原 §2.7 关于撤回的说明移到新的 §6。更新术语：将 "factor" 改为 "Strategy"。

**关键变更：** 原撤回机制是 "为目标 factor 添加 FactorParamRecord，probability 设为 ε"。现在 `conditional_probabilities` 是 list[float]，撤回时需要将**所有条目**设为 Cromwell 下界 ε。即：对 noisy-AND 的 [q₁,...,qₖ] 全部设为 ε，对 soft_implication 的 [p₁, p₂] 全部设为 ε。

- [ ] **Step 5: 新增 §7 与原 Gaia IR 的映射**

在文档末尾新增映射表（设计文档 §4）和 Future Work（设计文档 §6），帮助读者理解从旧概念到新概念的变化。

- [ ] **Step 6: 新增 §8 设计决策记录**

将设计文档 §7 的 7 条设计决策作为附录纳入 gaia-ir.md，让读者理解重构的理由：
- Strategy 保持 noisy-AND 语义（theory §5 证明 ∧ + ↝ 是最基本的多前提组合）
- Operator 从 Strategy 分离（↔/⊗/⊕ 是确定性算子，不是推理声明）
- FormalExpr 作为独立实体（推理层和计算层的分离点）
- 确定性策略视为"有 trivial FormalExpr"（统一 BP 编译规则）
- type 合并三个字段（category/reasoning_type/link_type 实为同一维度）
- conditional_probabilities 为 list[float]（统一 noisy-AND 和 soft_implication）
- 9 种命名策略自带 FormalExpr（微观结构由 theory 预定义）

- [ ] **Step 7: 更新源代码引用**

将文档末尾的源代码引用更新：
- `LocalCanonicalNode` → 注明将重命名
- `FactorNode` → 注明将重命名为 Strategy
- 新增 Operator、FormalExpr 的未来源文件位置

- [ ] **Step 8: 提交**

```bash
git add docs/foundations/gaia-ir/gaia-ir.md
git commit -m "docs(gaia-ir): update canonicalization, retraction, add mapping and design decisions"
```

---

## Chunk 2: overview.md + parameterization.md + belief-state.md

### Task 5: overview.md 更新

**Files:**
- Modify: `docs/foundations/gaia-ir/overview.md`

- [ ] **Step 1: 更新 §一 Gaia IR 结构描述**

更新 "整体结构" JSON 示例，将 `knowledge_nodes` 改为 `knowledges`，`factor_nodes` 改为 `strategies`，新增 `operators` 数组。

更新 FactorNode 内的字段为新 Strategy schema（统一 type 替代三维类型）。

- [ ] **Step 2: 更新 Knowledge/Factor 概述为 Knowledge/Strategy/Operator**

- "Knowledge 节点（变量节点）" → "Knowledge（命题节点）"
- "Factor 节点（因子节点）" → "Strategy（推理声明）"
- 新增 Operator 和 FormalExpr 的简要描述
- 更新三维类型系统表为统一 type

- [ ] **Step 3: 更新 "两层身份" 表**

| 层 | 范围 | ID 前缀 | 内容 |
|----|------|---------|------|
| **LocalCanonicalGraph** | 单个包 | `lcn_`, `lcs_`, `lco_` | 完整 content + Strategy steps |
| **GlobalCanonicalGraph** | 跨包 | `gcn_`, `gcs_`, `gco_` | 结构索引 + Operator + FormalExpr |

- [ ] **Step 4: 更新 §二 Parameterization 概述**

更新 `FactorParamRecord` 示例为 `StrategyParamRecord`，`factor_id` → `strategy_id`，`probability` → `conditional_probabilities`。

- [ ] **Step 5: 更新 "完备性" 表**

更新表中的术语：
- `knowledge 节点` → `Knowledge`
- `factor 节点` → `Strategy + Operator`
- `FactorParamRecord` → `StrategyParamRecord`
- 新增 FormalExpr 行

- [ ] **Step 6: 更新源代码引用**

更新文档末尾的源代码引用，匹配 gaia-ir.md 中的更新。

- [ ] **Step 7: 提交**

```bash
git add docs/foundations/gaia-ir/overview.md
git commit -m "docs(gaia-ir): update overview for four-entity architecture"
```

---

### Task 6: parameterization.md 更新

**Files:**
- Modify: `docs/foundations/gaia-ir/parameterization.md`

- [ ] **Step 1: 更新 FactorParamRecord → StrategyParamRecord**

```
StrategyParamRecord:
    strategy_id:            str              # 全局 Strategy ID (gcs_ 前缀)
    conditional_probabilities: list[float]   # noisy-AND: [q₁,...,qₖ]; soft_implication: [p₁, p₂]
    source_id:              str
    created_at:             str
```

更新关键规则中的字段说明。

- [ ] **Step 2: 新增 9 种命名策略的参数规则**

新增说明：当 Strategy.type 为 9 种命名策略之一时，不需要 StrategyParamRecord。参数化通过 FormalExpr 中间 Knowledge 的 PriorRecord 实现。

- [ ] **Step 3: 新增 Operator 参数说明**

新增说明：Operator 是纯确定性的（ψ ∈ {0, 1}），不需要参数记录。

- [ ] **Step 4: 更新 BP 运行时组装规则**

更新 resolution policy 说明中的 `factor` 为 `Strategy`。新增编译路径选择规则：
- 有 FormalExpr → Operator 层运行（参数在中间 Knowledge 的 PriorRecord）
- 无 FormalExpr → 使用 StrategyParamRecord.conditional_probabilities

- [ ] **Step 5: 更新 Factor probability 来源为 Strategy probability 来源**

更新：
- `infer` → conditional_probabilities 由 review 赋值
- `toolcall` / `proof` → 保持后续定义
- Canonicalization 产生的 equivalent candidate 现在是 Operator(source="standalone")，其 placeholder 规则更新

- [ ] **Step 6: 更新源代码引用**

- [ ] **Step 7: 提交**

```bash
git add docs/foundations/gaia-ir/parameterization.md
git commit -m "docs(gaia-ir): update parameterization for Strategy + Operator model"
```

---

### Task 7: belief-state.md 更新

**Files:**
- Modify: `docs/foundations/gaia-ir/belief-state.md`

- [ ] **Step 1: 更新 Schema 中的术语**

将文档中所有 `factor` 替换为 `Strategy`，`knowledge 节点` / `KnowledgeNode` 替换为 `Knowledge`。

- [ ] **Step 2: 新增 BP 编译路径记录**

在 BeliefState schema 中新增：

```
    # ── 编译信息（可选诊断） ──
    compilation_summary:      dict | None     # Strategy → 编译路径（"direct" 或 "formal_expr"）
```

说明：BP 运行时记录每个 Strategy 的编译路径——是直接编译为 ↝ 因子还是通过 FormalExpr 在 Operator 层运行。用于诊断和可重现性。

- [ ] **Step 3: 更新关键规则**

保持 "beliefs 只对 Claim" 规则不变。更新 "组装时每个 factor 都必须有值" 为 "组装时每个 Strategy（type=infer 或 soft_implication）都必须有 conditional_probabilities 值"。

- [ ] **Step 4: 更新源代码引用**

- [ ] **Step 5: 提交**

```bash
git add docs/foundations/gaia-ir/belief-state.md
git commit -m "docs(gaia-ir): update belief-state for compilation path tracking"
```

---

## Chunk 3: 交叉验证与收尾

### Task 8: 交叉引用验证

**Files:**
- Read: 所有 4 个 gaia-ir 文档
- Read: `docs/foundations/theory/04-reasoning-strategies.md`
- Read: `docs/foundations/theory/03-propositional-operators.md`

- [ ] **Step 1: 验证术语一致性**

在所有 4 个文档中搜索以下旧术语，确保全部替换：
- `KnowledgeNode` → `Knowledge`
- `FactorNode` → `Strategy`
- `factor_id` → `strategy_id`（在 Strategy 上下文中）
- `lcf_` → `lcs_`
- `gcf_` → `gcs_`
- `reasoning_type` → `type`（在 Strategy 上下文中）
- `category` → 不应再出现为独立字段
- `subgraph` → `FormalExpr`

Run: `grep -rn "KnowledgeNode\|FactorNode\|factor_id\|lcf_\|gcf_\|reasoning_type\|subgraph" docs/foundations/gaia-ir/`
Expected: 无匹配（或仅在 "与原 Gaia IR 的映射" 历史对比表中出现）

- [ ] **Step 2: 验证跨文档链接**

确认以下引用链接仍然正确：
- `gaia-ir.md` 内的 §N 交叉引用（章节号已变化）
- `overview.md` → `gaia-ir.md` 的链接
- `parameterization.md` → `gaia-ir.md` 的链接
- `belief-state.md` → `gaia-ir.md` 的链接
- 所有文档 → theory 文档的链接

- [ ] **Step 3: 验证设计文档完整覆盖**

逐条核对 `docs/specs/2026-03-26-graph-ir-restructuring-design.md` 中的每个决策，确认已体现在 gaia-ir 文档中：

| 设计文档章节 | 对应 gaia-ir 文档位置 |
|-------------|----------------------|
| §3.2 Knowledge | gaia-ir.md §1 |
| §3.3 Strategy + §3.3.1-4 | gaia-ir.md §2 |
| §3.4 Operator | gaia-ir.md §3 |
| §3.5 FormalExpr + §3.5.1-2 | gaia-ir.md §4 |
| §4 映射表 | gaia-ir.md §7 |
| §5.1 parameterization | parameterization.md |
| §5.2 belief-state | belief-state.md |
| §5.3 overview | overview.md |
| §5.4 canonicalization | gaia-ir.md §5 |
| §6 Future Work | gaia-ir.md §7 |
| §7 Design Decisions | gaia-ir.md §8 |

- [ ] **Step 4: 提交（如有修复）**

```bash
git add docs/foundations/gaia-ir/
git commit -m "docs(gaia-ir): fix cross-references and terminology consistency"
```

### Task 9: 最终验证与 PR

- [ ] **Step 1: 运行 ruff（确认无 Python 变更引入问题）**

Run: `ruff check . && ruff format --check .`
Expected: 无变更（本 PR 只改文档）

- [ ] **Step 2: 运行 pytest（确认文档变更未破坏任何东西）**

Run: `pytest --tb=short -q`
Expected: 全部通过（文档变更不影响测试）

- [ ] **Step 3: 创建 PR**

```bash
git push -u origin docs/theory-restructuring
gh pr create --title "docs(gaia-ir): restructure to four-entity architecture" \
  --body "..."
```

- [ ] **Step 4: 检查 CI**

Run: `gh run list --branch docs/theory-restructuring --limit 1`
Expected: CI 通过
