# 审查报告契约

> **Status:** Current canonical

本文档定义审查报告（ReviewOutput）的数据契约。该契约是 agent self-review（CLI 端）和 ReviewService（LKM 端）共享的输出格式，供 BP 推理消费。

## 产出方与消费方

| 场景 | 产出方 | 消费方 |
|------|--------|--------|
| 本地工作流 | Agent self-review（调用 `ReviewClient`） | `gaia infer` |
| 服务端工作流 | ReviewService（多 agent 审查） | 全局推理 pipeline |
| 测试 | 预备的 fixture 文件 | 测试中的 `pipeline_infer()` |

## ReviewOutput Schema

```python
@dataclass
class ReviewOutput:
    review: dict              # 原始审查数据
    node_priors: dict[str, float]    # lcn_id → 先验概率
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
| `observation` | 0.5 |
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

CLI 端审查报告保存为 `.gaia/review/review_output.json`，JSON 序列化的 ReviewOutput。

## 跨层引用

- **参数化模型**（ReviewOutput 如何转换为 LocalParameterization）：参见 [../gaia-ir/parameterization.md](../gaia-ir/parameterization.md)
- **CLI 消费**（`gaia infer` 如何加载审查报告）：参见 [../cli/local-inference.md](../cli/local-inference.md)
- **LKM 产出**（ReviewService 如何生成审查报告）：参见 [../lkm/review-pipeline.md](../lkm/review-pipeline.md)

## 代码路径

| 组件 | 文件 |
|------|------|
| ReviewOutput 定义 | `libs/pipeline.py:ReviewOutput` |
| FactorParams 定义 | `libs/graph_ir/models.py:FactorParams` |
| 先验构建器 | `libs/pipeline.py:_build_node_priors()` |
| 因子参数构建器 | `libs/pipeline.py:_build_factor_params()` |
