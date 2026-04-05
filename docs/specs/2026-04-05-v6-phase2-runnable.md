# v6 Phase 2: Runnable 支持 — lazy 计算图 + DAG 执行

| 属性 | 值 |
|------|---|
| 状态 | Draft |
| 日期 | 2026-04-05 |
| 范围 | gaia.lang Runnable 子树 + gaia build 执行流程 |
| 前置 | Phase 1（Support 继承树 + Knowledge 子类化） |
| 非目标 | Package 结构（Phase 3） |

---

## 1. 目标

在 Phase 1 的 Support 继承树上新增 `Runnable` 子树，支持"跑一个东西，拿结果当 Claim"的场景。

核心洞察（CH 视角）：

- **Pure support**（Formal / Infer）= Lean 的 Prop 世界：结构即证明，authoring 时立即 resolve
- **Runnable** = Lean 的 IO 世界：authoring 时声明函数签名，`gaia build` 时实际执行

Gaia package 本质上是一个 **lazy 计算图**：纯 Claim 是常量节点，Runnable 是计算节点，节点之间有依赖。

```
Support
├── Formal / Infer / Composite (incl. Induction)  (Phase 1, pure)
└── Runnable                                       ← 本阶段新增 (effectful)
    ├── Execution
    ├── Check
    └── FormalProof
```

---

## 2. Claim 的两种状态

Runnable 产出的 Claim 是 **promise**——图里有节点，但值还没算出来：

```python
geo = claim("方腔 10x10x10")                      # resolved
mesh = execute("生成网格", geo, fn=gen_mesh)        # promise
pressure = execute("压力场", mesh, bc, fn=run_cfd)  # promise（依赖 mesh）
conclusion = deduction("支持假设", pressure, criterion)  # promise（依赖 pressure）
```

Claim 增加状态标记：

```python
@dataclass
class Claim(Knowledge):
    support: Support | None = None
    resolved: bool = True  # Runnable 产出的 Claim → False
```

resolved 的传播规则：如果一个 Claim 的任何前提是 promise，它自身也是 promise。

---

## 3. Runnable 基类和子类

### 3.1 Runnable 基类

```python
@dataclass
class Runnable(Support):
    """lazy 计算节点的共同父类"""
    estimated_duration: float | None = None
    run_env: str | None = None
```

### 3.2 Execution（描述性："计算得到了 X"）

```python
@dataclass
class Execution(Runnable):
    callable_ref: Callable | str = ""
    execution_backend: str | None = None
```

```python
def execute(target: str | Claim, /, *, fn: Callable | str, given: list[Claim], ...) -> Claim
```

### 3.3 Check（验证性："实现满足 Y"）

```python
@dataclass
class Check(Runnable):
    checker_ref: Callable | str = ""
    checker_args: dict[str, Any] = field(default_factory=dict)
```

```python
def check(target: str | Claim, /, *, fn: Callable | str, given: list[Claim], ...) -> Claim
```

### 3.4 FormalProof（演绎性："定理 T 成立"）

```python
@dataclass
class FormalProof(Runnable):
    system: str = ""
    theorem_ref: str = ""
    proof_args: dict[str, Any] = field(default_factory=dict)
```

```python
def formal_proof(target: str | Claim, /, *, system: str, theorem_ref: str, given: list[Claim] | None = None, ...) -> Claim
```

---

## 4. 计算图模型

authoring code 产出的是一张混合图：

```
claim("方腔") ─────────────┐
                            ├─→ execute(gen_mesh) ──→ [mesh]
claim("边界条件") ──────────┤                           │
                            │                           ├─→ execute(run_cfd) ──→ [pressure]
claim("求解器已验证") ──────┘                           │                           │
                                                        │                           │
claim("L2 < 1%") ──────────────────────────────────────┘───→ deduction ──→ [conclusion]
```

- 圆角 = resolved Claim（纯声明或已执行）
- 方角 = promise Claim（待执行）
- 菱形 = Runnable 节点（计算任务）

从这张图中可以提取 **execution DAG**：只包含 Runnable 节点及其依赖关系，用于确定执行顺序。

---

## 5. `gaia build` 流程

```
gaia build mypackage/
  │
  ├─ 1. load：导入 Python 模块，执行 authoring code
  │     → 纯 Support 立即 resolve
  │     → Runnable 标记为 promise
  │
  ├─ 2. plan：提取 execution DAG
  │     → 拓扑排序 Runnable 节点
  │     → 确定可并行的任务组
  │
  └─ 3. execute：按 DAG 执行 Runnable
        → 入度为 0 的 Runnable 先执行（可并行）
        → 执行完成 → resolve promise Claim
        → 解锁下游 Runnable
        → 重复直到全部 resolved
        → 缓存执行结果
```

**`gaia build` 到此为止。** 不跑 BP。

后续流程：

```
gaia build mypackage/     →  resolved graph + execution 结果
  ↓
作者 self-review            →  检查 execution 结果，写/更新 review.py
  ↓
gaia infer mypackage/     →  在 reviewed + resolved 的图上跑 BP → beliefs
```

review 插在 build 和 infer 之间，保证概率层与结构层分离。

---

## 6. DAG 执行引擎

### 6.1 Phase 2 起步：graphlib

Python 3.9+ 标准库 `graphlib.TopologicalSorter` 做拓扑排序，加简单的顺序执行器：

```python
from graphlib import TopologicalSorter

dag = extract_execution_dag(package)  # 从 package 中提取 Runnable 依赖
ts = TopologicalSorter(dag)
ts.prepare()

while ts.is_active():
    ready = ts.get_ready()
    for node in ready:
        result = node.callable_ref(*resolve_inputs(node))
        node.conclusion.resolve(result)
        ts.done(node)
```

零外部依赖。

### 6.2 后续扩展：可插拔引擎接口

```python
class ExecutionEngine(Protocol):
    def execute(self, dag: ExecutionDAG) -> dict[Claim, Any]: ...

class GraphlibEngine(ExecutionEngine): ...     # 默认，stdlib
class DaskEngine(ExecutionEngine): ...          # 并行/分布式
class HamiltonEngine(ExecutionEngine): ...      # dataflow 风格
```

用户通过配置选择引擎：

```toml
# gaia.toml
[build]
engine = "graphlib"  # 默认
# engine = "dask"    # 需要 pip install gaia-lang[dask]
```

---

## 7. 缓存和增量执行

对 Runnable 的输入做 hash（前提 Claims 内容 + fn 身份），缓存执行结果：

- 输入不变 → 跳过执行，使用缓存
- 输入变化 → 重新执行，更新缓存
- 下游 Runnable 的缓存也失效（传递性）

类似 Make 的增量构建。Phase 2 先实现基于文件的简单缓存，后续可接入更复杂的方案。

---

## 8. 关键设计决策

### 8.1 对推理有影响的假设必须是 Claim

不设"介于 Claim 和 metadata 之间"的灰色地带：

- 对推理有影响 → 必须是 `given` 中的 Claim
- 纯 provenance → `support.metadata`

### 8.2 Runnable 通常不直接产出科学结论

`execute()` / `check()` / `formal_proof()` 产出的是中间 claim，到达科学结论通常还需要 bridge：

```python
pressure = execute("得到压力场", geo, bc, validated, fn=run_cfd)
criterion = claim("L2 误差 < 1% 即视为吻合")
conclusion = deduction("模拟支持方腔流存在稳定涡结构", pressure, criterion)
```

### 8.3 Review 在 build 之后、infer 之前

`gaia build` 只负责执行计算，不涉及概率。作者在 build 完成后检查 execution 结果，写 review（prior / judgment），然后再跑 `gaia infer`。

### 8.4 Review 机制

`review_support()` 对 Runnable 子类：reviewer 通过 review 前提 Claims 的 prior 来间接评估 Runnable support 的可信度。不需要为 Runnable 引入新的 review 机制。

---

## 9. 示例：完整流程

### 9.1 authoring

```python
# mypackage/__init__.py
from gaia.lang import claim, setting, deduction, execute, check

# 纯声明
geo = claim("计算域是 10x10x10 的方腔")
bc = claim("边界条件：上壁面速度 1m/s")
solver_validated = claim("该 CFD 求解器在低 Re 方腔流中已通过基准验证")
spec = claim("求解器应满足二阶精度收敛")
suite_representative = claim("回归测试集覆盖了目标 Re 数范围")
criterion = claim("压力场与参考解 L2 误差 < 1% 即视为吻合")

# Runnable — promise Claim
pressure = execute("CFD 计算得到压力场 P", geo, bc, solver_validated, fn=run_cfd)
solver_ok = check("求解器通过所有精度检查", spec, suite_representative, fn=run_tests)

# 纯推理 — 依赖 Runnable 结果
conclusion = deduction("模拟结果支持目标假设", pressure, solver_ok, criterion)
```

### 9.2 build

```bash
$ gaia build mypackage/
[load] 收集 8 claims, 3 supports (2 runnable)
[plan] execution DAG: run_cfd, run_tests (可并行)
[execute] run_cfd ... done (12.3s)
[execute] run_tests ... done (5.1s)
[done] 所有 promise resolved
```

### 9.3 review

```python
# mypackage/review.py
from gaia.review import review_claim, review_support, ReviewBundle

REVIEW = ReviewBundle(objects=[
    review_claim(solver_validated, prior=0.9, justification="Ghia 1982 偏差 < 0.5%"),
    review_claim(suite_representative, prior=0.7, justification="只覆盖到 Re=1000"),
    review_claim(criterion, prior=0.85),
    review_support(conclusion.support, judgment="good"),
])
```

### 9.4 infer

```bash
$ gaia infer mypackage/
[load] 加载 resolved graph + review
[infer] BP converged in 5 iterations
[result] conclusion: posterior=0.72
```

---

## 10. 不在本阶段做的事

- 分布式执行（Dask / Hamilton 集成）→ 后续扩展
- Runnable 的 IR protected contract
- Package 结构重组 → Phase 3
