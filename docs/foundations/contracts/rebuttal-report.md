# 反驳报告契约

> **Status:** Target design

本文档定义反驳报告（RebuttalReport）的数据契约。当审查发现阻塞性问题时，作者或 agent 提交反驳，ReviewService 据此重新评估。

## 产出方与消费方

| 场景 | 产出方 | 消费方 |
|------|--------|--------|
| 本地工作流 | Agent（针对 self-review 发现的问题） | Agent 自身（决定是否修改源码并重新 build） |
| 服务端工作流 | 作者/Agent（针对同行评审发现的问题） | ReviewService（重新评估，最多 5 轮） |

## RebuttalReport Schema

```python
@dataclass
class RebuttalReport:
    package: str                    # 包名称
    review_ref: str                 # 对应的审查报告标识
    timestamp: str                  # ISO 8601
    responses: list[RebuttalEntry]  # 逐条反驳
```

### RebuttalEntry

```python
@dataclass
class RebuttalEntry:
    chain: str           # 被质疑的推理链名称
    step: str            # 被质疑的步骤 ID
    action: str          # "accept" | "dispute" | "revise"
    explanation: str     # 反驳说明
    revised_source: str | None = None  # 如果 action="revise"，修改后的源码片段
```

### `action` 语义

| 值 | 含义 |
|----|------|
| `accept` | 作者接受审查意见，承诺修改 |
| `dispute` | 作者不同意审查意见，提供反驳理由 |
| `revise` | 作者已修改源码，提供修改后的版本 |

## 反驳周期

服务端 ReviewService 支持最多 5 轮反驳周期：

1. 审查发现阻塞性问题 → 返回审查报告
2. 作者提交反驳报告
3. ReviewService 重新评估被争议的步骤
4. 重复直到通过或达到最大轮次

## 文件格式

CLI 端反驳报告保存为 `.gaia/review/rebuttal.json`。

## 跨层引用

- **审查报告契约**（反驳所针对的审查报告格式）：参见 [review-report.md](review-report.md)
- **审查 Pipeline**（反驳周期的完整流程）：参见 [../lkm/review-pipeline.md](../lkm/review-pipeline.md)
