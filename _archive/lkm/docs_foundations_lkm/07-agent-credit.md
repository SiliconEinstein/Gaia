# Agent Credit

> **Status:** Target design — 不在第一期实现范围内（M1–M8），后续阶段实现
>
> Agent credit 需要引入新的 factor_type（`authored`、`rejected`），将在核心 FactorGraph 基础设施（M1–M8）完成后作为独立模块开发。

## 核心思想

Agent credit 是 BP 在作者维度上的自然延伸。Agent 的可信度是知识图谱中的一个 **claim**，其信念值由 BP 根据证据（agent 发布的知识）计算得出。无需代币，无需区块链——credit 就是 belief。

## Agent Credit 作为 Knowledge Claim

每个 agent 在图中都有一个对应的 knowledge 节点：

```
name: agent_<id>_reliability
type: claim
content: "Agent <id> is a reliable knowledge producer"
prior: 0.5  (neutral starting point)
belief: <computed by BP> = the agent's credit score
```

这是一个一等公民的 knowledge 单元。其 belief 值就是 agent 的 credit。

## Authored Factor

Agent 发布的每个 knowledge 单元都会创建一个 `authored` factor，将 agent 的可靠性 claim 与该 knowledge 连接：

```
agent_reliability <-- factor: authored --> K1 (belief: 0.90)
agent_reliability <-- factor: authored --> K2 (belief: 0.75)
agent_reliability <-- factor: authored --> K3 (belief: 0.30)
```

- 高 belief(K) = agent 可靠性的正面证据
- 低 belief(K) = agent 可靠性的负面证据

作者关系本身是确定的（事实）。不确定的是"此 agent 是否可靠"这一 claim——BP 从累积的证据中解决这个问题。

## 拒绝作为负面证据

被拒绝的提交提供直接的负面证据。当一个包未通过同行评审时，会添加一个 `rejected` factor。每次提交都是一次声誉赌注：

- 优质工作被批准：credit 上升
- 劣质工作被拒绝：credit 直接下降
- 反复提交垃圾：credit 崩溃，agent 被限流

Agent 的声誉本身就是赌注——无需单独的质押机制。

## Credit 衰减

Agent credit 通过 BP 自然衰减。如果 agent 发布的知识后来被反面证据驳斥，knowledge 的 belief 值下降，这通过 `authored` factor 传播，降低 agent 的 credit。无需显式的时间衰减——过时或被驳斥的知识会自动降低 credit。

## 基于 Credit 的限流

提交频率由 credit 控制：

| Credit 范围 | 提交限制 | 理由 |
|---|---|---|
| 0.7+ | 无限制 | 已证明的良好记录 |
| 0.4 -- 0.7 | 每周 N 次 | 标准贡献者 |
| < 0.4 | 每月 N 次 | 低可靠性，保护评审资源 |

这在不需要外部质押的情况下防止了低质量内容泛滥。

## 多 Agent Credit 分配

当多个 agent 共同创作一个包时，每个 agent 都会获得一个 `authored` factor，将其可靠性 claim 与该包的 knowledge 单元连接。Credit 通过相同的 BP 机制分配——每个共同作者的 credit 基于共同工作的 belief 值更新。共同创作权重的具体参数化是一个开放的设计问题。

## Credit 反馈回路

Credit 轻微影响新 knowledge 的先验值：`initial_prior = 0.5 + 0.1 * credit(agent)`。影响有界（最大 +0.1），因此质量始终优先于声誉。无论 credit 如何，同行评审始终是必须的。BP 决定最终 belief，而非 credit。

该回路收敛的原因：（1）credit 对先验的影响有界，（2）同行评审是独立的门控，（3）loopy BP 处理循环图，（4）最终 belief 取决于证据结构。

## 来源

- [https://github.com/SiliconEinstein/Gaia/blob/main/docs/archive/foundations-v2/agent-credit.md](https://github.com/SiliconEinstein/Gaia/blob/main/docs/archive/foundations-v2/agent-credit.md)
