# RLVR 式结论验证与参数学习

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.0 |
| 日期 | 2026-03-04 |
| 关联文档 | [scaling_belief_propagation.md](scaling_belief_propagation.md) §2.4, [agent_verifiable_memory.md](agent_verifiable_memory.md) §4, [theoretical_foundations.md](theoretical_foundations.md) §2, [version_dependency_environment.md](version_dependency_environment.md) |
| 状态 | Wishlist |

---

## 目录

1. [核心思想](#1-核心思想)
2. [为什么有必要](#2-为什么有必要)
3. [验证什么、更新什么](#3-验证什么更新什么)
4. [Verification Provider 接口](#4-verification-provider-接口)
5. [Probability 更新机制](#5-probability-更新机制)
6. [与 BP 的交互](#6-与-bp-的交互)
7. [触发时机](#7-触发时机)
8. [代码领域的适配](#8-代码领域的适配)
9. [与其他设计的关系](#9-与其他设计的关系)
10. [实施路线图](#10-实施路线图)

---

## 1. 核心思想

### 1.1 RLVR 类比

RLVR (Reinforcement Learning with Verifiable Rewards) 的核心思想：模型生成推理链产出答案，答案被外部验证，验证信号反馈回推理过程。

Gaia 可以实现完全同构的机制：

```
RLVR:
  思维链 → 答案 → 验证答案 → reward 反馈到策略

Gaia:
  推理边 (premises → conclusion) → 验证 conclusion → 结果反馈到 edge probability
```

### 1.2 信息流

```
Premise A ──┐
            ├── HyperEdge (probability=p) ──→ Conclusion C
Premise B ──┘
                                                    │
                                               验证 C
                                                    │
                                          ┌─────────┴─────────┐
                                          │ 代码 → 跑 test     │
                                          │ 数学 → 跑 Lean     │
                                          │ 其他 → LLM judge   │
                                          └─────────┬─────────┘
                                                    │
                                               验证结果
                                                    │
                                       Bayesian update edge probability
                                                    │
                                               触发 BP
                                                    │
                                          belief 级联更新
```

验证的是**结论**，但更新的是**推理边的 probability**。结论对不对 → 推理靠不靠谱。

---

## 2. 为什么有必要

### 2.1 当前 probability 来源太弱

当前 Gaia 的 edge probability 完全依赖 LLM review 打分。LLM 自己会幻觉，它给的 probability 能有多可靠？

```
可靠性梯度：

  LLM as judge     ~0.7 可靠（会幻觉、会误判）
  人工 review      ~0.9 可靠（会犯错但少）
  测试通过         ~0.95 可靠（覆盖率不是 100%）
  Lean 证明通过    =1.0 可靠（形式化证明，不可能错）
```

没有 verification，Gaia 的 60 亿参数（[scaling_belief_propagation.md](scaling_belief_propagation.md) §2.1）全部建立在 LLM 打分上——地基不牢。有了 verification，至少一部分参数被 ground truth 锚定。

### 2.2 从静态模型到学习系统

[scaling_belief_propagation.md](scaling_belief_propagation.md) §2.4 提出了"从推理到学习"的方向，但没有给出具体机制。Verification 就是这个机制：

```
当前 Gaia（静态）:
  edge probability 在 commit 时设定 → 之后永远不变
  Gaia 只做推理（BP 计算 belief），不学习

加入 Verification（学习）:
  edge probability 在 commit 时设定 → 结论被验证 → probability 更新
  推理结果反哺参数 → Gaia 从经验中学习
```

### 2.3 不同领域的验证手段

| 领域 | 结论示例 | 验证 Oracle | 验证可靠性 |
|------|---------|------------|-----------|
| 代码 | "函数 f 对 null 输入返回空列表" | 运行测试套件 | 高（~0.95，受覆盖率限制） |
| 数学 | "对所有 n≥1，命题 P(n) 成立" | Lean/Coq 编译 | 完美（=1.0，形式化证明） |
| 数据 | "查询 Q 返回非空结果集" | 执行 SQL | 高（~0.95） |
| 通用 | "材料 X 在高温下稳定" | LLM as judge | 低（~0.7，兜底方案） |

---

## 3. 验证什么、更新什么

### 3.1 验证的是结论，不是推理边本身

我们无法直接验证"这个推理过程是否正确"——但我们可以验证"这个推理过程产出的结论是否正确"。结论的正确性是推理可靠性的间接证据。

### 3.2 更新的是 edge probability，不是 node prior

这是最关键的设计选择。两个选项：

| 方案 | 做法 | 问题 |
|------|------|------|
| ~~直接改 conclusion 的 prior~~ | 验证通过 → prior 提高 | 绕过 BP，破坏模型一致性 |
| **改推理边的 probability** | 验证通过 → edge probability 提高 → BP 重算 belief | 信息通过 BP 正确传播 |

更新 edge probability 更好的原因：

1. **信息更丰富**：验证不只告诉你"C 对不对"，还告诉你"A+B→C 这个推理靠不靠谱"。如果同一条边的结论被反复验证为正确，说明这个推理模式可靠。

2. **可传播**：改了 edge probability 后，BP 把信息传播到图的其他部分。如果 C 同时是另一条推理边的前提，C 的 belief 变化影响下游——知识的级联更新。

3. **与 RLVR 类比一致**：RLVR 更新策略（推理过程），不是直接改答案。Gaia 更新 edge probability（推理可靠性），不是直接改 belief。

4. **保持 prior 的语义纯净**：prior 是"不考虑任何推理边时的初始信念"，代表独立于图结构的先验知识。验证得到的信息不是"独立先验"，而是"推理过程的可靠性评估"——应该体现在 edge probability 上。

---

## 4. Verification Provider 接口

### 4.1 核心抽象

```python
class VerificationResult(BaseModel):
    status: Literal["verified", "falsified", "inconclusive"]
    confidence: float          # 验证本身的可靠性 ∈ [0, 1]
    evidence: str              # 人类可读的解释
    artifact: dict = {}        # 领域特定: test report / proof object / LLM judgment


class VerificationProvider(ABC):
    """验证提供者抽象基类。不同领域注册不同实现。"""

    @property
    @abstractmethod
    def domain(self) -> str:
        """领域标识，如 'code-python', 'math-lean', 'general'"""

    @abstractmethod
    async def verify(
        self,
        conclusion: Node,
        premises: list[Node],
        edge: HyperEdge,
        context: dict,
    ) -> VerificationResult:
        """验证一条推理边的结论。

        Args:
            conclusion: 要验证的结论节点
            premises: 推理边的前提节点列表
            edge: 推理边本身（包含 reasoning 等信息）
            context: 领域特定上下文（测试路径、Lean 文件等）
        """
```

### 4.2 三个内置实现

**代码验证：TestVerificationProvider**

```python
class TestVerificationProvider(VerificationProvider):
    domain = "code-test"

    async def verify(self, conclusion, premises, edge, context):
        # context: {"repo_path": ..., "test_file": ..., "test_function": ...}
        result = await run_pytest(
            context["repo_path"],
            context["test_file"],
            context["test_function"],
        )
        if result.all_passed:
            return VerificationResult(
                status="verified",
                confidence=result.line_coverage,  # 覆盖率作为 confidence
                evidence=f"{result.passed}/{result.total} tests passed, "
                         f"coverage={result.line_coverage:.0%}",
                artifact={"report": result.report},
            )
        else:
            return VerificationResult(
                status="falsified",
                confidence=0.99,  # failing test 几乎是确定的反例
                evidence=f"Test failed: {result.first_failure}",
                artifact={"traceback": result.traceback},
            )
```

**数学验证：LeanVerificationProvider**

```python
class LeanVerificationProvider(VerificationProvider):
    domain = "math-lean"

    async def verify(self, conclusion, premises, edge, context):
        # context: {"lean_file": ..., "theorem_name": ...}
        result = await run_lean_check(context["lean_file"], context["theorem_name"])
        if result.proved:
            return VerificationResult(
                status="verified",
                confidence=1.0,  # 形式化证明是绝对的
                evidence=f"Formally proved: {context['theorem_name']}",
                artifact={"proof_terms": result.proof_terms},
            )
        else:
            # 注意：证不出来 ≠ 命题为假
            return VerificationResult(
                status="inconclusive",
                confidence=0.0,
                evidence=f"Proof attempt failed: {result.error}",
                artifact={"error": result.error},
            )
```

**通用兜底：LLMJudgeProvider**

```python
class LLMJudgeProvider(VerificationProvider):
    domain = "general"
    LLM_DISCOUNT = 0.7  # LLM 判断的可靠性折扣

    async def verify(self, conclusion, premises, edge, context):
        prompt = self._build_judge_prompt(conclusion, premises, edge)
        judgment = await self.llm_client.judge(prompt)
        return VerificationResult(
            status=judgment.status,
            confidence=judgment.confidence * self.LLM_DISCOUNT,
            evidence=judgment.explanation,
            artifact={"model": judgment.model, "raw_response": judgment.raw},
        )
```

LLM judge 的 confidence 乘以折扣系数（默认 0.7），反映 LLM 判断本身的不可靠性。这确保 LLM 验证的影响力弱于形式化验证。

### 4.3 Provider 注册

```python
class VerificationRegistry:
    """管理 VerificationProvider 注册和路由。"""

    def __init__(self):
        self._providers: dict[str, VerificationProvider] = {}
        self._fallback = LLMJudgeProvider()

    def register(self, provider: VerificationProvider):
        self._providers[provider.domain] = provider

    async def verify(self, conclusion, premises, edge, context) -> VerificationResult:
        domain = context.get("domain", "general")
        provider = self._providers.get(domain, self._fallback)
        return await provider.verify(conclusion, premises, edge, context)

# 初始化
registry = VerificationRegistry()
registry.register(TestVerificationProvider())
registry.register(LeanVerificationProvider())
# LLMJudgeProvider 作为 fallback，不需要注册
```

---

## 5. Probability 更新机制

### 5.1 贝叶斯更新

用贝叶斯更新将验证结果融入 edge probability，比硬编码的加减更有原则。

设：
- `p₀` = 当前 edge probability（先验）
- `v` = verification confidence ∈ [0, 1]

**结论被验证 (verified)：**

```
p₁ = p₀ × v / (p₀ × v + (1 - p₀) × (1 - v))
```

直觉：如果推理好（p₀ 高）且验证通过（v 高），后验 probability 很高。

```
示例: p₀=0.7, v=0.95 (测试通过，高覆盖率)
p₁ = 0.7×0.95 / (0.7×0.95 + 0.3×0.05)
   = 0.665 / 0.68
   ≈ 0.978

示例: p₀=0.5, v=1.0 (Lean 证明通过)
p₁ = 0.5×1.0 / (0.5×1.0 + 0.5×0.0)
   = 1.0     ← Lean 证明直接锚定到 1.0
```

**结论被证伪 (falsified)：**

```
p₁ = p₀ × (1-v) / (p₀ × (1-v) + (1-p₀) × v)
```

直觉：结论错了，推理大概率有问题。

```
示例: p₀=0.7, v=0.99 (测试失败，确定的反例)
p₁ = 0.7×0.01 / (0.7×0.01 + 0.3×0.99)
   = 0.007 / 0.304
   ≈ 0.023  ← 推理基本不可靠
```

**不确定 (inconclusive)：**

不更新。`p₁ = p₀`。

### 5.2 多次验证的累积

贝叶斯更新天然支持多次验证的累积——每次用上一次的后验作为新的先验：

```
初始:    p₀ = 0.5 (LLM 给的初始 probability)
第 1 次: 测试通过 (v=0.90) → p₁ = 0.90
第 2 次: 测试通过 (v=0.92) → p₂ = 0.99
第 3 次: 测试失败 (v=0.99) → p₃ = 0.08  ← 一次失败大幅拉低

多次通过累积信心，一次失败快速惩罚。符合直觉。
```

### 5.3 更新公式的性质

| 性质 | 说明 |
|------|------|
| 有界 | p₁ 始终在 [0, 1] 内 |
| 对称 | verified 和 falsified 的公式互为镜像 |
| 锚定 | Lean 证明 (v=1.0) 直接把 p 锚定到 1.0 或 0.0 |
| 累积 | 多次验证自然累积，无需额外机制 |
| 可逆 | 先 verified 后 falsified，probability 会正确下降 |

---

## 6. 与 BP 的交互

### 6.1 验证后触发局部 BP

```
验证完成
    │
    ▼
edge.probability 更新 (Bayesian update)
    │
    ▼
触发局部 BP (以 conclusion 为中心, 3-hop)
    │
    ▼
受影响节点的 belief 更新
    │
    ▼
写回 LanceDB
```

这复用现有的 `InferenceEngine.compute_local_bp()` 接口，不需要新的 BP 机制。

### 6.2 级联效应

验证的影响通过 BP 级联传播：

```
[A] ──edge1(p=0.7)──→ [C] ──edge2(p=0.8)──→ [E]

验证 C: 测试通过
  → edge1.probability: 0.7 → 0.978
  → BP 重算:
    C.belief 提高
    E.belief 也提高（因为 C 是 E 的前提，C 更可信了）
```

一条推理边的验证不仅影响直接结论，还沿着推理链传播到下游。

### 6.3 falsified 的级联

```
[A] ──edge1(p=0.7)──→ [C] ──edge2(p=0.8)──→ [E]

验证 C: 测试失败
  → edge1.probability: 0.7 → 0.023
  → BP 重算:
    C.belief 大幅下降
    E.belief 也下降（前提不可信了）
```

一次测试失败的影响自动传播到所有依赖这条推理链的下游节点——不需要手动追踪影响范围。

---

## 7. 触发时机

### 7.1 四种触发方式

| 触发方式 | 场景 | 延迟 |
|---------|------|------|
| **Merge 后自动** | 结论节点关联了测试/Lean 文件 → merge 后自动验证 | 秒级 |
| **API 手动请求** | 用户/agent 调用 `POST /verify/{edge_id}` | 按需 |
| **CI 集成** | 代码变更 → CI 触发 → 重跑相关验证 → 更新 probability | 分钟级 |
| **定期巡检** | 后台任务定期重跑验证（代码场景：代码可能已变更） | 小时级 |

### 7.2 验证端点

```
POST /verify/{edge_id}

Request:
{
    "provider": "code-test",          // 可选，不指定则自动路由
    "context": {                      // 领域特定
        "repo_path": "/path/to/repo",
        "test_file": "tests/test_config.py",
        "test_function": "test_empty_dict_returns_default"
    }
}

Response:
{
    "edge_id": 42,
    "verification": {
        "status": "verified",
        "confidence": 0.92,
        "evidence": "15/15 tests passed, coverage=92%"
    },
    "probability_update": {
        "old": 0.7,
        "new": 0.978
    },
    "affected_beliefs": {
        "101": {"old": 0.65, "new": 0.91},
        "205": {"old": 0.58, "new": 0.72}
    }
}
```

### 7.3 自动路由

如果不指定 provider，系统根据结论节点的元数据自动选择：

```python
def auto_select_provider(conclusion: Node, edge: HyperEdge) -> str:
    # 优先使用最可靠的验证手段
    if conclusion.extra.get("lean_theorem"):
        return "math-lean"
    if conclusion.extra.get("test_file"):
        return "code-test"
    return "general"  # fallback to LLM judge
```

可靠性高的 provider 优先。只有没有形式化验证手段时才退化到 LLM judge。

---

## 8. 代码领域的适配

Verification 最自然的第一个落地领域是代码，因为测试框架是最成熟的验证 oracle。

### 8.1 代码知识在 Gaia 中的表示

Gaia 不替代 LSP/AST 等结构工具。它存储的是现有工具**不覆盖**的高层语义知识：

| 知识类型 | 示例 | 现有工具 | Gaia 的价值 |
|---------|------|---------|-----------|
| 架构不变量 | "所有 API 路由经过 auth middleware" | 无 | 命题 + 测试验证 |
| 行为契约 | "函数 f 对 null 输入返回空列表" | 部分 (类型系统) | 命题 + 测试验证 + belief |
| 设计决策 | "选 React 因为需要 SSR" | 无 | 命题 + 推理链 |
| 性能约束 | "查询延迟 < 100ms" | 无 | 命题 + benchmark 验证 |
| 变更影响 | "改模块 A 影响模块 B" | 部分 (dep graph) | 命题 + BP 传播 |

### 8.2 代码场景的完整闭环

```
1. Agent 阅读代码，提取知识:
   Node: "AuthMiddleware 在所有 /api/ 路由前执行"
   type: paper-extract, prior: 0.7

2. 结构化服务创建 commit → review → merge
   belief = 0.7 (只有提取证据)

3. Verification 触发:
   TestVerificationProvider 运行:
     test_auth_middleware_on_all_api_routes()
   通过，coverage=0.92

4. Bayesian update:
   edge probability: 0.7 → 0.978
   BP: belief 0.7 → 0.91

5. 某天有人改了路由，忘了加 middleware:
   CI 重跑验证 → 测试失败 (confidence=0.99)

6. Bayesian update:
   edge probability: 0.978 → 0.023
   BP: belief 0.91 → 0.05

7. Agent 检测到 belief 骤降 → 报警
```

### 8.3 代码场景的特殊挑战

代码变化快，需要额外机制：

| 挑战 | 应对 |
|------|------|
| 代码变更使验证过期 | CI 集成：push 后重跑验证，更新 probability |
| 测试本身可能有 bug | verification confidence 永远 < 1.0（区别于 Lean） |
| 覆盖率不均匀 | 用函数级覆盖率（而非行级）作为 confidence |

---

## 9. 与其他设计的关系

### 9.1 与 Agent Verifiable Memory 的关系

[agent_verifiable_memory.md](agent_verifiable_memory.md) §4.2 的 confidence-gated progression 因 verification 变得更可靠：

```
无 verification:
  Agent 门控决策基于 LLM 打分的 probability → 不太可靠

有 verification:
  Agent 门控决策基于经过验证的 probability → 可靠
  测试通过 → belief 高 → 继续推理
  测试失败 → belief 低 → 回溯
```

### 9.2 与文本结构化服务的关系

[text_structuring_service.md](text_structuring_service.md) 的提取折扣（probability × 0.8）可以被 verification 覆盖：

```
文本提取: edge probability = LLM 建议 × 0.8 = 0.56
  ↓
Verification: 测试通过 (v=0.92)
  ↓
Bayesian update: 0.56 → 0.94

提取折扣被验证结果正确覆盖。
初始的保守估计不影响最终的参数质量。
```

### 9.3 与 BP 扩展的关系

[scaling_belief_propagation.md](scaling_belief_propagation.md) §2.4 提出"从推理到学习"但未给出机制。Verification 就是这个机制：

```
§2.4 原文: "没有什么阻止将来从数据中学习这些参数"

Verification 提供了具体路径:
  验证结论 → Bayesian update edge probability → 参数从经验中学习
```

### 9.4 与蕴含格理论的关系

[theoretical_foundations.md](theoretical_foundations.md) §5 区分了 abstraction（保真）和 induction（不保真）。Verification 与此直接相关：

| 边类型 | 理论性质 | Verification 预期 |
|--------|---------|------------------|
| abstraction | 保真 (probability 可 = 1.0) | 结论应该总是能被验证 |
| induction | 不保真 (probability < 1.0) | 结论可能被证伪——这正是 induction 的本质 |

如果一条 abstraction 边的结论被 falsified，说明提取有误（不是 abstraction 不保真，而是 LLM 错误分类了边类型）。如果一条 induction 边的结论被 falsified，这是正常的——induction 本来就是"冒险"。

### 9.5 与版本/依赖管理的关系

[version_dependency_environment.md](version_dependency_environment.md)：Verification 更新 edge probability → 触发 edge 版本变更 → 依赖该 edge 的 Knowledge Package 需要 version bump。具体来说，verification 结果（verified/falsified）通过 Bayesian update 改变 edge probability，这在版本管理框架下构成一次 edge 的 minor 或 major 变更（取决于 probability 变化幅度），进而触发下游依赖的 stale detection 和传播机制。

---

## 10. 实施路线图

### Phase 1：LLM Judge 兜底

| 任务 | 说明 |
|------|------|
| `VerificationProvider` 抽象 | 接口定义 + `VerificationResult` 模型 |
| `LLMJudgeProvider` | 通用 LLM 验证，带 confidence 折扣 |
| `POST /verify/{edge_id}` | 手动触发验证 |
| Bayesian update 逻辑 | probability 更新 + 写回存储 |
| 验证后触发局部 BP | 复用 `compute_local_bp()` |

### Phase 2：代码验证

| 任务 | 说明 |
|------|------|
| `TestVerificationProvider` | pytest 集成，覆盖率作为 confidence |
| CI 集成 | git push → 重跑相关验证 → 更新 probability |
| 验证时效性 | 记录 `last_verified_at`，过期标记为 stale |
| Merge 后自动验证 | 结论关联 test_file 时自动触发 |

### Phase 3：数学验证

| 任务 | 说明 |
|------|------|
| `LeanVerificationProvider` | Lean 4 编译集成 |
| 处理 inconclusive | 证不出 ≠ 为假，不更新 probability |
| Lean 代码生成 | 从 Gaia 命题自动生成 Lean theorem statement (探索性) |

### Phase 4：验证生态

| 任务 | 说明 |
|------|------|
| Provider 插件机制 | 用户注册自定义验证器 |
| 验证覆盖率仪表盘 | 图中有多少 edge 经过验证、多少未验证 |
| 自动路由优化 | 根据结论内容自动选择最合适的 provider |
| 批量验证 | 后台定期巡检，重跑已有验证 |
