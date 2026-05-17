# 如何为你的图选择 BP 推理算法

> **Status:** Current canonical (v0.5 + BP refactor 2026-05-13)
>
> **定位：** 这是给**作者 / 包写作者**的决策导向页，回答"我该选哪个 BP 算法、怎么估 treewidth、不同选择会差多少"。
> 算法的内部参数、消息传递公式、Cromwell clamp 等技术合约见 [`inference.md`](inference.md)；纯 BP 算法理论见 [`../theory/07-belief-propagation.md`](../theory/07-belief-propagation.md)。
> 本页**不**重复 [`inference.md`](inference.md) 中的阈值规则与诊断字段定义，只把它们组织成可直接照着走的决策流程。

## 1. 一分钟决策树

99% 的情况下你不需要选——`gaia run infer` 走 `InferenceEngine.run`，它会按下表自动路由：

```text
                            ┌─────────────────────────────────┐
                            │  你的 FactorGraph (n 个变量)    │
                            └────────────────┬────────────────┘
                                             │
                              ┌──────────────┴──────────────┐
                              │  n > mf_node_limit (=2000)? │
                              └──────────────┬──────────────┘
                                  yes        │       no
                          ┌──────────────────┘       └────────────────┐
                          ▼                                            ▼
              ┌───────────────────────┐                ┌───────────────────────┐
              │  Mean Field VI        │                │ jt_treewidth(graph)   │
              │  + UserWarning ⚠      │                │ ≤ jt_max_treewidth    │
              │  非生产级（见 §3）    │                │ (=20) ?               │
              └───────────────────────┘                └──────────┬────────────┘
                                                            yes   │   no
                                                        ┌─────────┘   └─────────┐
                                                        ▼                       ▼
                                              ┌───────────────────┐   ┌──────────────────┐
                                              │ Junction Tree     │   │ TRW-BP           │
                                              │ (精确，O(n·2^tw)) │   │ (有界近似)       │
                                              └───────────────────┘   └──────────────────┘
```

阈值在 `gaia.engine.bp.engine.EngineConfig` 中可改：`jt_max_treewidth=20`、`mf_node_limit=2000`。算法选择的代码位置见 [`inference.md`](inference.md) 的「实现」一节。

什么时候应该**手动覆盖** auto——见 §4。

## 2. 怎么知道我的图的 treewidth？

Treewidth 是 BP 复杂度的关键参数。Gaia 用 min-fill 启发式估算（最大极大团减一）。三种方式获取：

### 2.1 看 `gaia run infer` 的日志（推荐）

无需任何额外工具。`InferenceEngine.run` 在选定算法后会 log 一行：

```text
InferenceEngine: JT (exact), treewidth=6, 142.3ms
InferenceEngine: TRW-BP, treewidth=24, 318.7ms
```

第二个数字就是 min-fill 估出的 treewidth。看到 `treewidth=24` 而 JT 没被选中，说明你的图刚好踩到 JT 阈值（20）以上。

### 2.2 在 Python 里直接查

```python
from gaia.engine.bp import jt_treewidth, lower_local_graph

fg = lower_local_graph(local_graph)
tw = jt_treewidth(fg)
print(f"treewidth ≈ {tw}")
```

`jt_treewidth(graph: FactorGraph) -> int` 是公开 API（`gaia/engine/bp/junction_tree.py`），内部跑 min-fill triangulation 然后取最大极大团 size − 1。

### 2.3 心算（粗略）

不查命令时，下面是常见 IR 形态的 treewidth 量级：

| Gaia IR 形态 | 典型 treewidth | 备注 |
|---|---|---|
| 链式推理（`a₁ → a₂ → … → aₙ`） | 2 | 任何算法都精确，不必选 |
| 树状（一个 root 的有限分支） | 1 | 同上 |
| Block-DAG（独立小块通过少量共享节点连接） | 4–8 | 实测 [`tests/test_bp_large_scale.py::build_block_dag`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/tests/test_bp_large_scale.py)，JT 适合 |
| 单包含 1–2 条强 cycle 的 DAG | 5–15 | JT 仍可能精确 |
| Diamond-heavy（很多 ⟨A→{B,C}→D⟩ 结构） | 10–25+ | 接近或越过 JT 阈值 |
| Loopy（多条 cycle 互相纠缠） | 25+ | 通常进入 TRW-BP 路径 |
| Schema-ground 平铺成大 LKM-style 图（n > 2000） | 不再决定路径 | n 限制先触发 → MF VI（带 warning） |

通用经验：**只要图里没有大量"多 premise 共享 conclusion 同时 conclusion 又互相支撑"的密集子结构，treewidth 多半在 JT 范围内**。

## 3. 不同算法的精度成本对比

下表总结仓库实测结果（block-DAG 形态，`jaynes_ref` 严格 BP 作 ground truth），以便你判断"用 X 替代 Y 会损失多少"：

| 算法 | 何时用 | 精度（vs exact） | 时间复杂度 | 实测来源 |
|---|---|---|---|---|
| **Exact (brute-force)** | n ≤ ~20 测试场景 | ground truth | O(2^n) | [`test_bp_large_scale.py::test_small_graph_exact_match`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/tests/test_bp_large_scale.py) |
| **Junction Tree** | tw ≤ 20 | 精确（误差 < 1e-3 ⇒ 与 brute-force 在 Cromwell 量级一致） | O(n · 2^tw) | 同上 |
| **TRW-BP** | tw > 20 或当 JT 内存爆 | 与 JT 差 < 1e-3（千分之一），block-DAG 50/100/250 实测 | O(I · k · F) per iter, I ≤ 200 | [`test_bp_large_scale.py::test_medium_graph_jt_vs_trw`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/tests/test_bp_large_scale.py) |
| **Mean Field VI** | n > 2000 fallback | **30%–79% 系统误差**（block-DAG 上）。**非生产级。** | O(n · F · 2^k) per sweep | [`inference.md` § Mean Field VI](inference.md#mean-field-vi)、[`test_bp_large_scale.py::test_large_graph_mean_field`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/tests/test_bp_large_scale.py) (`max_diff < 0.3` 容忍阈值即说明这一点) |

读法：

- **JT vs Exact** —— Cromwell ε = 1e-3 是误差地板；JT 在所有 tw ≤ 20 的图上"和 brute-force 完全一致"在工程意义上等价于"精确"。
- **TRW-BP vs JT** —— 千分之一差距，对 belief 排序（who is more credible）几乎无影响；对 belief 数值（一个 claim 是 0.752 还是 0.751）也不影响下游决策。
- **MF VI vs TRW-BP** —— 这一档差距是 30%~79%，**完全可以反转 belief 顺序**。Gaia 把它放在 `n > 2000` 的 fallback 位置 + UserWarning 是承认"我们目前没有更好的大图算法"，不是推荐使用。

## 4. 什么时候应该手动覆盖 auto

`InferenceEngine.run(method=...)` 接受 `"auto"` / `"jt"` / `"trw_bp"` / `"mean_field"`。下列场景应当显式指定：

| 场景 | 建议显式 method | 理由 |
|---|---|---|
| 大图（n > 2000）但 belief 数值要求高 | `"trw_bp"` | 绕过 MF VI 的 30%~79% 误差。代价：可能跑 30 秒到几分钟。仓库目前推荐这条 escape hatch，参见 [`inference.md`](inference.md) 「实现」一节的算法选择策略第 1 条。 |
| 中等图（n ~ 1000）且 treewidth 接近 20，要复现别人 JT 结果 | `"jt"` | 强制 JT；如果 treewidth 实际 > 20 会触发内存/时间爆炸——所以仅在你**已经知道** treewidth ≤ 20 时用。 |
| 调试 BP 收敛性、对比两个算法 | `"trw_bp"` 然后 `"jt"` 各跑一次 | 比较 `result.beliefs` 看分歧位置；高 `direction_changes` 计数（见 [`inference.md` § TRWDiagnostics](inference.md#trwdiagnostics)）的变量是冲突信号。 |
| 写测试需要 ground truth | `from gaia.engine.bp import exact_inference` | 直接用 brute-force（n ≤ 20）；不走 `InferenceEngine.run`。 |
| 故意要 MF VI 测大图近似 | `"mean_field"` | 唯一合法的 MF VI 用法：你接受 30%~79% 误差，目标是看 belief 量级是否合理而非数值。 |

## 5. `infer()` 和 `InferenceEngine.run` 的差别

仓库里有两条入口；新代码**应该用 `InferenceEngine.run`**：

| API | 大图 fallback | 阈值常量 | 何时用 |
|---|---|---|---|
| `gaia.engine.bp.infer(graph, method="auto")` | **Loopy BP** (`_LOOPY_BP_NODE_LIMIT = 2000`) | 模块级私有 | Legacy convenience：旧代码、不需要 CLI parity 的小图测试 |
| `gaia.engine.bp.engine.InferenceEngine().run(graph, method="auto")` | **Mean Field VI**（带 `UserWarning`） | `EngineConfig.mf_node_limit = 2000` | CLI 主路径（`gaia run infer`）、新代码 |

二者除了大图 fallback 不同（Loopy BP vs MF VI），其他完全一致：treewidth ≤ 20 都走 JT，否则走 TRW-BP。**这条差异是历史包袱**，预期未来收敛到 `InferenceEngine`。Test 注释（[`test_bp_large_scale.py::test_auto_routing`](https://github.com/SiliconEinstein/Gaia/blob/v0.5/tests/test_bp_large_scale.py)）也指出 Loopy BP 在仓库内"与 TRW-BP 实测匹配，diff < 1e-9"——所以 `infer()` 在大图上其实**比** `InferenceEngine` 更准，但不发 warning，容易让用户对算法状态产生错觉。

简而言之：

- **写新代码 / 想和 CLI 输出一致** → `InferenceEngine`；
- **维护旧代码或写小图单元测试** → `infer()` 也行；
- **千万不要在同一个工程里混用两条路径**——它们在 `n > 2000` 时会给出**不同算法**的结果。

## 6. 常见症状 → 推荐处理

| 你看到的现象 | 可能原因 | 建议 |
|---|---|---|
| `UserWarning: Mean Field VI fallback (n > 2000)` | 走了大图 fallback | 加 `method="trw_bp"` 显式覆盖；如果可以拆图，把 schema/ground 分两次 lower 后单独推（见 [`local-vs-global.md`](local-vs-global.md)）。 |
| JT 跑了几分钟 / 进程被 kill | treewidth 实测 > 20，强制 JT 触发 O(2^tw) 爆炸 | 切回 auto 或 `method="trw_bp"`。 |
| TRW-BP 不收敛（`converged=False`） | damping 不够，或图里有强冲突 | 看 [`inference.md` § TRWDiagnostics](inference.md#trwdiagnostics) 的 `direction_changes`；高 count 的变量是矛盾源头。考虑增大 `damping`（默认 0.5）。 |
| 两次跑同一个图结果不同 | 你在不同 API 路径上跑（一次 `infer()`、一次 `InferenceEngine`）且 n > 2000 | 见 §5；统一走 `InferenceEngine`。 |
| 想让 JT 处理 tw > 20 的图 | JT 复杂度 O(n · 2^tw)，2^25 ≈ 3300 万；2^30 ≈ 10 亿 | 不可行。把图按 schema/ground 拆分，或接受 TRW-BP 近似。 |

## 7. 进一步阅读

- [`inference.md`](inference.md) — 各算法的参数、Cromwell clamp、Diagnostics 字段、消息计算公式
- [`../theory/07-belief-propagation.md`](../theory/07-belief-propagation.md) — sum-product 消息传递的纯算法理论
- [`local-vs-global.md`](local-vs-global.md) — 本地包推理 vs LKM 全局推理的边界
- [`potentials.md`](potentials.md) — FactorType 与势函数定义
- [`../cli/inference.md`](../cli/inference.md) — `gaia run infer` CLI 入口、`--priors` / `--dep-beliefs` / `--depth` 的语义
