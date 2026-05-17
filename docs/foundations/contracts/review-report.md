# 审查报告契约

> **Status:** Legacy / future-service contract, not the current v0.5 local CLI path
>
> **本页定位：** **Reference / Contracts** 区的数据契约（report schema 与字段定义）；review 流程本身的叙述见 Foundations / [Review Pipeline](../review/review-pipeline.md)。

本文档定义旧版 `ReviewOutput` 审查报告的数据契约。它描述的是早期
agent self-review / future ReviewService 可能输出的概率化报告格式，不是
当前 v0.5 `gaia run infer` 的输入。当前本地 `gaia run infer` 直接读取 compiled
IR、`priors.py` 写入的 claim metadata、连续推断记录和 dependency beliefs；
它不消费 `ReviewOutput`，也不因为缺少审查报告而跳过 belief 输出。

## 产出方与消费方

| 场景 | 产出方 | 消费方 |
|------|--------|--------|
| 旧本地工作流（已移出当前 CLI） | Agent self-review（调用 `ReviewClient`） | 旧 `pipeline_infer()` |
| 服务端工作流 | ReviewService（多 agent 审查） | 全局推理 pipeline |
| 测试 | 预备的 fixture 文件 | 测试中的 `pipeline_infer()` |

## ReviewOutput Schema

```python
@dataclass
class ReviewOutput:
    review: dict              # 原始审查数据
    node_priors: dict[str, float]    # Knowledge QID → 先验概率
    factor_params: dict[str, FactorParams]  # factor_id → 因子参数
    model: str                # 产生审查的 LLM 模型名称
    source_fingerprint: str | None = None  # 可选的源码指纹
```

### `node_priors`

将每个 local canonical node ID 映射到其先验概率。先验按知识类型分配：

| 知识类型 | 默认先验 |
|----------|----------|
| `setting` | 1.0 |
| `claim` | 0.5 |
| `question` | 0.5 |
| `action` | 0.5 |
| `contradiction` | 0.5 |
| `equivalence` | 0.5 |

### `factor_params`

将每个推理 factor ID 映射到其条件概率参数：

```python
@dataclass
class FactorParams:
    conditional_probability: float  # 条件概率 P(conclusion | premises)
```

值来自审查链步骤的 `conditional_prior` 字段；如果没有审查数据则默认为 1.0。

### `review`

原始审查数据，结构为：

```json
{
  "package": "package_name",
  "model": "model_name",
  "timestamp": "ISO 8601",
  "source_fingerprint": "...",
  "summary": "审查摘要文本",
  "chains": [
    {
      "chain": "conclusion_name",
      "steps": [
        {
          "step": "conclusion_name.1",
          "conditional_prior": 0.85,
          "weak_points": [],
          "explanation": "评估说明"
        }
      ]
    }
  ]
}
```

## 文件格式

旧 CLI 端审查报告保存为 `.gaia/review/review_output.json`，JSON 序列化的
ReviewOutput。当前 v0.5 本地 CLI 不再生成或读取该文件。

## 跨层引用

- **当前本地推理**（`gaia run infer` 如何从 compiled IR 和 priors 构造 factor graph）：参见 [../cli/inference.md](../cli/inference.md)
- **LKM 产出**（ReviewService 如何生成审查报告）：参见 [gaia-lkm](https://github.com/SiliconEinstein/gaia-lkm) 仓库

## 代码路径

| 组件 | 文件 |
|------|------|
| ReviewOutput 定义 | legacy / future service contract; no current `gaia/` implementation |
| 当前本地 infer 入口 | `gaia/cli/commands/infer.py` |
| 当前 IR → FactorGraph lowering | `gaia/engine/bp/lowering.py` |
| 当前推理引擎 | `gaia/engine/bp/engine.py` |
