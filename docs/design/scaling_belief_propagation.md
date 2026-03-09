# 十亿级 Loopy Belief Propagation 扩展方案

| 文档属性 | 值 |
|---------|---|
| 版本 | 1.1 |
| 日期 | 2026-03-04 |
| 关联文档 | [phase1_billion_scale.md](../archive/design/phase1_billion_scale.md) §6, [inference-theory.md](../foundations/inference-theory.md) §1 |
| 状态 | Draft |

---

## 目录

1. [问题陈述](#1-问题陈述)
2. [Gaia 作为参数化统计模型](#2-gaia-作为参数化统计模型)
3. [现状分析](#3-现状分析)
4. [业界方案综述](#4-业界方案综述)
5. [Gaia 扩展策略](#5-gaia-扩展策略)
6. [分布式图分区](#6-分布式图分区)
7. [异步调度与残差优先](#7-异步调度与残差优先)
8. [分层多分辨率 BP](#8-分层多分辨率-bp)
9. [高性能实现](#9-高性能实现)
10. [收敛加速技术](#10-收敛加速技术)
11. [实施路线图](#11-实施路线图)

---

## 1. 问题陈述

Gaia Phase 1 目标规模：

| 指标 | 数量 |
|------|------|
| 命题节点 (变量) | 10^9 |
| 超边 (因子) | 5 × 10^9 |
| BP 消息吞吐目标 | 10^6 messages/sec |
| 全局 BP 单次扫描目标 | ~30 分钟 |

当前 BP 引擎是 ~150 行 Python/NumPy 原型，仅支持局部 BP（3-hop 子图，~500 节点）。`run_global_bp()` 尚未实现。

核心挑战：**如何在十亿变量、五十亿因子的 factor graph 上执行 loopy BP，使全局一致性维护在可接受时间内完成？**

### 1.1 为什么单机方案不够

粗略内存估算（假设每个消息 8 bytes float64）：

```
每条超边的消息数 = |tail| + |head| ≈ 4 (平均)
总消息数 = 5 × 10^9 × 4 = 2 × 10^10
消息存储 = 2 × 10^10 × 8B = 160 GB

加上变量 belief 数组、因子索引结构等辅助数据，
单机内存需求 ≈ 250-400 GB
```

这超出了普通服务器的内存容量（通常 64-128 GB），且不留余量给操作系统和其他服务。即使用大内存机器（512 GB+），单线程遍历 50 亿因子也无法在 30 分钟内完成。

---

## 2. Gaia 作为参数化统计模型

本节澄清一个关键认识：Gaia 不只是一个"知识库 + 推理引擎"——它本身就是一个 **参数化统计模型 (parametric statistical model)**。理解这一点对本文档的所有扩展策略至关重要：我们不是在"扩展一个数据库的查询引擎"，而是在**扩展一个 60 亿参数模型的推理过程**。

### 2.1 参数在哪里

Gaia 的 factor graph 包含两类参数：

```
Node.prior:            10^9 个，每个 ∈ [0, 1]   ← 变量的先验分布
HyperEdge.probability: 5 × 10^9 个，每个 ∈ [0, 1]   ← 因子势函数
─────────────────────────────────────────────────
总参数量:              ~6 × 10^9
```

60 亿参数。和 GPT-J (6B) 在同一个数量级。

### 2.2 模型在哪里

Factor graph 定义了一个联合概率分布：

```
P(x₁, x₂, ..., xₙ) ∝ ∏ᵢ priorᵢ(xᵢ) × ∏ⱼ factorⱼ(x_tail, x_head)
```

BP 在这个分布上做近似推断，计算每个变量的边缘分布（即 `Node.belief`）。这完全是标准的概率图模型 (PGM) 框架。

### 2.3 与 LLM 的本质对比

Gaia 和 LLM 都是 "large model"，但参数的性质完全不同：

| | LLM (e.g. GPT-J 6B) | Gaia (Phase 1) |
|---|---|---|
| 模型类型 | 神经网络 (Transformer) | 概率图模型 (Factor Graph) |
| 参数量 | ~6 × 10^9 | ~6 × 10^9 |
| 参数含义 | **不可解释**的权重矩阵 | **可解释**：每个参数是一个具体命题的置信度或推理步骤的可靠性 |
| 参数来源 | SGD 从语料中学习 | 人/LLM 通过 commit workflow 写入 |
| 知识存储 | 隐式（编码在权重中） | 显式（每个参数有语义标签） |
| 推理算法 | 前向传播 (~ms) | 信念传播 (~min 全局) |
| 可审计性 | 无法追溯某个输出来自哪些"知识" | 每个 belief 可追溯到具体的推理链 |

两者处于同一参数规模，但一个是黑盒，一个是白盒。这是 "Large Knowledge Model" 这个名称的核心立论：**同等规模的参数，完全不同的可解释性**。

### 2.4 从推理到学习

当前 Gaia 的参数（prior 和 probability）是在 commit 时由人/LLM 设定的。BP 只做推理（计算 belief），不修改参数本身。

但 factor graph 模型天然支持参数学习：

```
当前：
  参数 (prior, probability) → 固定 → BP 推理 → belief
                                      ↑
                                    只做推理

未来可能：
  参数 (prior, probability) → BP 推理 → belief → 与观测对比
         ↑                                            │
         └────────── 梯度更新 ←───────────────────────┘
                    (EM / BP-as-differentiable-layer)
```

具体场景：

- **论文预测验证**：一篇论文预测"材料X在温度T下超导"，后续实验证实了 → 自动提高相关 edge 的 probability
- **Belief 校准**：统计历史上 belief > 0.9 的命题中有多少最终被 contradiction → 如果 belief 系统性偏高，调整 prior 分布
- **端到端微分**：PGMax 已支持 `jax.grad` 对 BP 过程求导 → 可以直接用梯度下降优化 edge probability，使 belief 拟合某个目标（如专家标注的可信度）

一旦加入参数学习，Gaia 就不只是"存储知识并推理"，而是**从知识的积累中自我校准**——这是从 knowledge base 到 knowledge model 的质变。

### 2.5 对本文档的意义

这个认识重新定义了 BP 扩展的目标：

| 原来的理解 | 修正后的理解 |
|-----------|------------|
| 扩展一个图数据库的推理查询 | 扩展一个 60 亿参数统计模型的推理 |
| BP 是一个辅助功能 | BP 是模型的核心——没有 BP，参数就只是存储，不产生 belief |
| 性能优化是工程问题 | 性能优化直接决定"模型"能否运转 |
| 全局 BP 是可选的一致性维护 | 全局 BP 是模型的完整推理——局部 BP 只是近似 |

本文档后续所有扩展策略，都应在这个框架下理解：我们在扩展的不是数据库，而是模型。

---

## 3. 现状分析

### 3.1 当前实现

```
libs/inference/
├── factor_graph.py   ← 内存因子图（dict + list）
└── bp.py             ← loopy BP（v2f/f2v 消息传递）
```

**关键局限（详见 [inference-theory.md](../foundations/inference-theory.md) §4）**：

| 局限 | 影响 |
|------|------|
| 无 v2f/f2v 消息分离 | 多因子消息 last-write-wins，结果不正确 |
| 边类型不区分 | contradiction/retraction 未实现 |
| 边逐条串行加载 | I/O 瓶颈 |
| 全局 BP 未实现 | `NotImplementedError` |

### 3.2 设计文档已规划但未实现的目标

来自 [phase1_billion_scale.md](../archive/design/phase1_billion_scale.md) §6 和推理引擎设计文档：

- 分区大小 ~10^4 节点，32 并行 worker
- 每次全局扫描 ~30 分钟
- BP 消息在进程内存完成，不依赖 Redis
- Phase 2 迁移到 C++/Rust + gRPC

---

## 4. 业界方案综述

### 4.1 PGMax (DeepMind)

- **方法**：纯 JAX 函数式实现，GPU 加速 loopy BP
- **实测规模**：RBM benchmark 1,284 变量 / 393,284 因子
- **优势**：比 pgmpy/pomegranate 快 1000×；支持 vmap 批处理、JIT 编译、自动微分
- **局限**：单 GPU 显存约束，已验证规模与十亿级差距 3-4 个数量级
- **参考价值**：消息传递的 gather/scatter 并行化模式可借鉴；对密集子图的 GPU 加速方案

> 来源：Zhou et al., "PGMax: Factor Graphs for Discrete Probabilistic Graphical Models and Loopy Belief Propagation in JAX", JMLR 2024

### 4.2 DLBP (Distributed Loopy BP)

- **方法**：分布式 LBP，专门处理 power-law 度分布的真实图
- **核心贡献**：将高度数节点的消息计算分散到多台机器，避免 power-law 图中的负载不均
- **扩展性**：相对机器数和边数均近线性扩展
- **参考价值**：Gaia 的知识图谱也符合 power-law 分布（少数命题被大量引用），DLBP 的负载均衡策略直接适用

> 来源：Jo, Yoo, and Kang, "Fast and Scalable Distributed Loopy Belief Propagation on Real-World Graphs", WSDM 2018

### 4.3 GraphLab / PowerGraph

- **方法**：GAS (Gather-Apply-Scatter) 计算模型，将单个高度数顶点的计算分散到多台机器
- **实测规模**：十亿级顶点和边
- **核心特性**：异步执行、优先调度、图感知放置
- **参考价值**：GAS 模型天然适合 BP 的消息收集-更新-分发模式

> 来源：Gonzalez et al., "PowerGraph: Distributed Graph-Parallel Computation on Natural Graphs", OSDI 2012

### 4.4 Splash BP

- **方法**：残差驱动的优先调度 + 共享内存并行
- **核心思想**：只更新残差最大的消息，跳过已收敛区域
- **效果**：减少 5-10× 计算量，同时改善收敛质量
- **参考价值**：直接可集成到 Gaia 的 BP 引擎中

> 来源：Gonzalez, Low, and Guestrin, "Residual Splash for Optimally Parallelizing Belief Propagation", AISTATS 2009

### 4.5 方案对比

| 方案 | 已验证规模 | 分布式 | GPU | 适用场景 |
|------|-----------|--------|-----|---------|
| **PGMax** | ~40 万因子 | 否 | 是 | 中等规模、需要微分的场景 |
| **DLBP** | 十亿边 | 是 | 否 | power-law 真实图 |
| **PowerGraph** | 十亿级 | 是 | 否 | 通用图并行计算 |
| **Splash BP** | 百万级 | 共享内存 | 否 | 单机多核优化 |

**结论**：没有一个现成方案可以直接搬来用。Gaia 需要组合多种技术：PowerGraph/DLBP 的分布式策略 + Splash BP 的调度优化 + PGMax 的 GPU 加速思路 + Gaia 自身的层次结构特性。

---

## 5. Gaia 扩展策略

总体策略：**分区 + 调度 + 分层 + 高性能实现**，四者缺一不可。

```
                    ┌─────────────────────────┐
                    │    分布式图分区 (§6)      │  ← 解决内存和并行度
                    │  10^9 → ~10^5 分区       │
                    └────────┬────────────────┘
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
    ┌─────────────┐ ┌──────────────┐ ┌──────────────┐
    │ 残差调度(§7) │ │ 分层 BP (§8) │ │ 高性能(§9)   │
    │ 跳过已收敛   │ │ 利用层次结构  │ │ Rust + GPU   │
    │ 减少 5-10×  │ │ 局部→全局    │ │ 10^6 msg/s   │
    └─────────────┘ └──────────────┘ └──────────────┘
```

---

## 6. 分布式图分区

### 6.1 为什么图分区质量至关重要

分区的目标是最小化跨分区边（cross-partition edges），因为每条跨分区边在每轮 BP 迭代中都需要网络通信。

```
差的分区（随机哈希）：
  50 亿边中 30% 跨分区 → 15 亿条消息/轮需要网络传输
  通信量 = 15 × 10^9 × 8B × 2(双向) = 240 GB/轮

好的分区（图感知）：
  50 亿边中 3% 跨分区 → 1.5 亿条消息/轮需要网络传输
  通信量 = 1.5 × 10^9 × 8B × 2 = 24 GB/轮

差距：10× 通信量 → 直接影响每轮迭代时间
```

### 6.2 分区策略选型

| 方案 | 分区质量 | 计算成本 | 适合 Gaia 的理由 |
|------|---------|---------|-----------------|
| **哈希分区** | 差 (跨边~30%) | O(N) | 实现简单，可作为 baseline |
| **METIS / KaHIP** | 好 (跨边~3-5%) | O(N log N) | 经典图分区算法，成熟可靠 |
| **Neo4j 社区检测** | 好 | 已在 Neo4j 中 | 利用已有拓扑存储，无需额外计算 |
| **论文聚类** | 自然 | O(N) | 同论文的命题天然高度连接 |

**推荐方案：论文聚类 + Neo4j 社区检测的两级分区**

Gaia 的图有一个独特优势：命题节点天然按论文来源聚类。

```
第 1 级分区：按论文来源聚类
  ─────────────────────────
  每篇论文 ~50 个命题，paper-extract 边密集连接
  10^7 篇论文 → 10^7 个初始聚类

第 2 级分区：Neo4j Louvain 社区检测合并相关论文
  ─────────────────────────────────────────
  相关论文（共享 abstraction/induction 边）合并为社区
  10^7 → ~10^5 分区，每分区 ~10^4 节点
```

### 6.3 分区间通信协议

```
Worker A (持有分区 P_a)          Worker B (持有分区 P_b)
         │                                │
         │  1. 分区内 BP 迭代              │  1. 分区内 BP 迭代
         │                                │
         │  2. 收集边界消息                │  2. 收集边界消息
         │     {node_id: message}          │     {node_id: message}
         │                                │
         ├──────── 交换边界消息 ────────────┤
         │        (gRPC streaming)         │
         │                                │
         │  3. 用收到的消息更新边界节点     │  3. 用收到的消息更新边界节点
         │                                │
         │  4. 检查全局收敛                │  4. 报告局部最大残差
         │                                │
```

每轮迭代分为两个阶段：
1. **本地阶段**：分区内部正常 BP 迭代（无通信开销）
2. **同步阶段**：交换边界消息、更新边界节点

可以配置本地阶段的内部迭代次数（例如每做 5 轮本地迭代交换一次边界消息），以减少通信频率。

---

## 7. 异步调度与残差优先

### 7.1 问题：同步 BP 的浪费

标准同步 BP 每轮更新所有 5 × 10^9 条边的消息。但实际上，经过前几轮迭代后，绝大部分消息已接近收敛，继续更新是浪费。

### 7.2 Residual BP

核心思想：维护一个优先队列，按消息变化量（残差）排序，只更新残差最大的节点。

```python
# 伪代码
residuals = MaxHeap()  # (residual_value, node_id)

# 初始化：所有节点入堆
for node in all_nodes:
    residuals.push(compute_residual(node), node.id)

while residuals.max() > convergence_threshold:
    node = residuals.pop()
    old_belief = beliefs[node.id]

    # 更新该节点的所有入边消息
    for factor in node.incoming_factors:
        update_factor_to_variable_message(factor, node)

    # 更新 belief
    beliefs[node.id] = compute_belief(node)

    # 更新邻居的残差
    for neighbor in node.neighbors:
        new_residual = compute_residual(neighbor)
        residuals.update(neighbor.id, new_residual)
```

### 7.3 与分布式的结合

Residual BP 在分布式环境下的实现：

- **分区内**：每个 worker 维护本地优先队列，优先更新局部残差最大的节点
- **分区间**：边界节点的残差变化触发跨分区消息交换（仅在残差超过阈值时通信）
- **全局收敛**：coordinator 收集所有 worker 报告的局部最大残差，当全局最大残差 < threshold 时停止

**预期收益**：相比同步全量更新，减少 5-10× 的消息计算量。

### 7.4 与现有代码的兼容性

当前 `bp.py` 已有 `convergence_threshold` 和 `damping`，只需：
1. 将顺序遍历改为优先队列驱动
2. 增加残差计算逻辑
3. 保持 damping 不变

---

## 8. 分层多分辨率 BP

### 8.1 利用 Gaia 的天然层次结构

Gaia 的超图不是均匀的——它有清晰的语义层次：

```
Level 0: paper-extract 节点群
         ──────────────────
         同一篇论文内的命题 + 推理链
         特点：局部稠密，跨论文连接少
         规模：每群 ~50 节点

Level 1: abstraction / induction 节点
         ────────────────────────────
         跨论文的概括和归纳
         特点：连接不同 Level 0 群
         规模：~10^8 节点

Level 2: conjecture 节点
         ─────────────
         高层猜想，全局稀疏连接
         特点：度数高但数量少
         规模：~10^6 节点（估算）
```

### 8.2 自底向上的分层 BP

```
┌─────────────────────────────────────────────────┐
│ Phase 1: Level 0 群内精确/近似 BP                │
│                                                  │
│   Paper A 群        Paper B 群        Paper C 群 │
│   ┌─────────┐      ┌─────────┐      ┌─────────┐│
│   │ n1→n2→n3│      │ n4→n5   │      │ n6→n7→n8││
│   │   ↘n4   │      │  ↘n6    │      │   ↘n9   ││
│   └────┬────┘      └────┬────┘      └────┬────┘│
│        │                │                │      │
│   摘要: belief     摘要: belief     摘要: belief │
│   向量 for 群 A    向量 for 群 B    向量 for 群 C│
└────────┼────────────────┼────────────────┼──────┘
         ▼                ▼                ▼
┌─────────────────────────────────────────────────┐
│ Phase 2: Level 1 节点 BP（使用群摘要作为输入）    │
│                                                  │
│   abstraction_1 (A群+B群 → 概括)                 │
│   induction_1   (B群+C群 → 归纳)                 │
│   ...                                            │
└─────────────────────────┬───────────────────────┘
                          ▼
┌─────────────────────────────────────────────────┐
│ Phase 3: Level 2 全局 BP（conjecture 节点）       │
│                                                  │
│   节点少 (~10^6)，可以跑完整 BP                   │
└─────────────────────────────────────────────────┘
```

### 8.3 群摘要的计算

每个 Level 0 群（论文内子图）的 BP 完成后，产出该群的**边界信念摘要**：

```python
class ClusterSummary:
    cluster_id: int
    boundary_beliefs: dict[int, float]  # 与外部有连接的节点 → belief
    internal_confidence: float          # 群内 BP 收敛程度
```

Level 1 BP 使用这些摘要值作为输入，而非重新遍历 Level 0 的所有节点。

### 8.4 正确性分析

分层 BP 是标准 loopy BP 的近似：

- **Level 0 群如果无环**：群内 BP 是精确的（树上 BP 保证收敛且精确）
- **Level 0 群有环**：群内 loopy BP 是近似的，但局部子图通常环路少、收敛快
- **跨层传播**：摘要信念引入近似误差，类似于 cluster variational method

实践中，这种分层近似的误差通常远小于 loopy BP 本身在有环图上的近似误差。

---

## 9. 高性能实现

### 9.1 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| BP 消息计算内核 | **Rust** (rayon 并行) | 内存安全、零成本抽象、编译后性能接近 C++ |
| 密集子图 GPU 加速 | **CUDA** 或 **JAX** (可选) | PGMax 证明了 gather/scatter 模式在 GPU 上有效 |
| 分布式通信 | **gRPC streaming** | 与现有 FastAPI 栈兼容，双向流式传输边界消息 |
| Python 绑定 | **PyO3** | Rust → Python 绑定，与现有 `InferenceEngine` 接口兼容 |
| 消息存储 | 进程内存 (mmap) | 符合现有设计决策（无 Redis），大分区可 mmap 到 SSD |

### 9.2 数据布局优化

BP 的性能瓶颈往往不是计算，而是内存访问模式。关键优化：

```
传统布局（当前实现）：
  factors = [{"edge_id": 1, "tail": [1,2], "head": [3], "prob": 0.9}, ...]
  → Python dict，内存不连续，cache miss 严重

优化布局（CSR-like 压缩格式）：
  factor_tails:  [1, 2, | 3, 4, 5, | ...]     ← 连续数组
  tail_offsets:  [0,     2,         5,   ...]   ← 每个因子的 tail 起始位置
  factor_heads:  [3, | 6, 7, | ...]             ← 连续数组
  head_offsets:  [0,  1,      3,   ...]
  factor_probs:  [0.9, 0.85, ...]               ← 连续 float64 数组
  beliefs:       [0.8, 0.7, 1.0, ...]           ← 连续 float64 数组

→ 顺序内存访问，cache-friendly，SIMD 可向量化
```

### 9.3 性能预估

```
单核 Rust (顺序访问连续内存):
  每次消息更新 ≈ 几次乘法 + 查表 ≈ ~50ns
  单核吞吐 ≈ 2 × 10^7 messages/sec

32 核并行 (rayon work-stealing):
  吞吐 ≈ 5 × 10^8 messages/sec（考虑 cache 竞争和同步开销）

单机 50 亿因子 × 4 消息/因子 = 200 亿消息/轮:
  每轮 ≈ 200 × 10^9 / 5 × 10^8 ≈ 400 秒 ≈ 7 分钟

Residual BP 减少 5× 有效消息量:
  每轮有效计算 ≈ 1.4 分钟

50 轮迭代 × 1.4 分钟 ≈ 70 分钟（单机全局 BP）
```

分布式（4 台机器，分区后跨分区边 < 5%）：

```
本地计算 ≈ 70 / 4 ≈ 18 分钟
通信开销 ≈ ~2 分钟/轮 × 50 轮（流水线化后）
总计 ≈ 20-25 分钟
```

这接近 30 分钟的目标。如果配合分层 BP（Level 0 群内只需 1 次 BP 而非每轮重算），可进一步缩短。

---

## 10. 收敛加速技术

### 10.1 已采用

| 技术 | 当前状态 | 参数 |
|------|---------|------|
| Damping | 已实现 | `_damping = 0.5` |
| 提前停止 | 已实现 | `_convergence_threshold = 1e-6` |

### 10.2 计划采用

| 技术 | 原理 | 预期效果 |
|------|------|---------|
| **Residual scheduling** | 只更新残差最大的消息 | 减少 5-10× 计算量 |
| **Adaptive damping** | 根据残差动态调整 damping | 加快收敛初期速度 |
| **树检测** | 识别无环子图，用精确 BP | 树结构一轮即精确收敛 |

### 10.3 可选探索

| 技术 | 原理 | 适用条件 |
|------|------|---------|
| **Lifted BP** | 合并结构对称的节点 | 大量结构相似的 paper-extract 模式 |
| **Mini-batch BP** | 每轮只在随机子图上更新 | 超大图上快速获得粗粒度近似 |
| **Tree-reweighted BP (TRW-BP)** | 用生成树凸组合保证收敛 | 环路密集时改善收敛性 |

### 10.4 Lifted BP 在 Gaia 中的可行性

Gaia 中可能存在大量结构对称的模式：

```
论文 A:  [前提1, 前提2] → [结论1]   prob=0.9
论文 B:  [前提3, 前提4] → [结论2]   prob=0.9

如果两条边的局部拓扑结构相同（2-tail, 1-head, 相同 probability），
且前提/结论的 belief 值相近，可以合并为一个 "lifted 因子" 处理。
```

Lifted BP 的潜在压缩比取决于 Gaia 图的对称程度，需要在真实数据上测量。如果压缩比 > 10×，值得投入。

---

## 11. 实施路线图

### Phase 1a：修正当前原型

**目标**：正确性优先，为后续优化建立 baseline。

| 任务 | 关联 Issue |
|------|-----------|
| 实现标准 v2f / f2v 消息分离 | — |
| 修复多因子消息聚合（聚合后更新，而非 last-write-wins） | — |
| 实现 contradiction 反向抑制 | #23, #24 |
| 实现 retraction 排除 | #23, #24 |
| 批量加载边（替换逐条 await） | — |
| 添加 BP 正确性测试（小图精确解对照） | — |

### Phase 1b：单机性能优化

**目标**：在单机上支持 ~10^6 节点规模的 BP。

| 任务 | 说明 |
|------|------|
| CSR 格式数据布局 | 替换 Python dict，连续内存访问 |
| Residual scheduling | 优先队列驱动，减少无效计算 |
| NumPy 向量化 | 利用 SIMD 加速消息计算（Rust 之前的过渡方案） |
| 分层 BP 原型 | 利用 paper 聚类做两级 BP |
| Benchmark 框架 | 固定测试图（10^3 / 10^4 / 10^5 / 10^6 节点），追踪性能回归 |

### Phase 1c：分布式全局 BP

**目标**：实现 `run_global_bp()`，支持十亿节点。

| 任务 | 说明 |
|------|------|
| 图分区服务 | 论文聚类 + Neo4j Louvain 社区检测 |
| Rust BP 内核 | rayon 并行 + CSR 布局 + PyO3 绑定 |
| gRPC 边界消息交换 | 分区间通信协议 |
| 全局收敛检测 | coordinator 收集局部残差 |
| 分层 BP 生产化 | Level 0/1/2 三级 BP |
| 增量 BP | merge 后只重新传播受影响的子图，而非全局重算 |

### Phase 2：进阶优化（远期）

| 方向 | 说明 |
|------|------|
| GPU 加速密集子图 | 对 Level 0 内的密集群用 CUDA/JAX |
| Adaptive damping | 根据局部残差自动调节 |
| Lifted BP | 如果对称度测量结果好 |
| 嵌入辅助 BP | embedding 相似度调节消息权重 |

---

## 附录 A：关键参考文献

| 文献 | 核心贡献 | 与 Gaia 的关联 |
|------|---------|---------------|
| Zhou et al., JMLR 2024. "PGMax" | JAX BP, GPU 加速 | GPU 消息传递模式 |
| Jo, Yoo, Kang, WSDM 2018. "DLBP" | 分布式 LBP, power-law 图 | 分区和负载均衡 |
| Gonzalez et al., OSDI 2012. "PowerGraph" | GAS 模型, 十亿级图计算 | 计算模型参考 |
| Gonzalez, Low, Guestrin, AISTATS 2009. "Residual Splash" | 残差优先调度 | 调度策略 |
| Gonzalez et al., UAI 2009. "Distributed Parallel Inference" | 分布式因子图推理 | 分区间通信协议 |

## 附录 B：与现有架构的接口

分布式 BP 引擎需要与以下组件交互：

```
Neo4j (图拓扑)
  ├── 读取：get_subgraph(), 社区检测结果
  └── 接口：Cypher 查询 (现有 Neo4jGraphStore)

LanceDB (主存储)
  ├── 读取：Node.prior
  ├── 写回：Node.belief
  └── 接口：load_nodes_bulk(), update_beliefs() (现有接口)

Commit Engine (触发源)
  ├── merge 后触发局部 BP (同步，现有)
  └── merge 后触发增量全局 BP (异步，待实现)

API Gateway (查询入口)
  └── Layer 2 Research API 调用 compute_local_bp() (现有接口)
```

BP 引擎对外暴露的接口不变：

```python
class InferenceEngine:
    async def compute_local_bp(self, center_node_ids, hops=3) -> dict[int, float]
    async def run_global_bp(self) -> None  # 由 NotImplementedError → 分布式实现
```
