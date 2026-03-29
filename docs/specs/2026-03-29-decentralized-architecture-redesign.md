# 重新设计 03-decentralized-architecture.md 的内容结构

> **Date:** 2026-03-29
> **Status:** Approved
> **Target file:** `docs/foundations/ecosystem/03-decentralized-architecture.md`

## 背景

当前 `03-decentralized-architecture.md` 同时承担"架构总纲"和"具体业务流程展开"两个角色，但两边都没做好：

- **和子文档大面积重复**：注册结构 TOML 示例（05 的职责）、curation 两阶段完整流程图（06 的职责）、open questions 对比表（05 的职责）、三类候选详解（06 的职责）
- **缺少端到端业务主线叙事**：读者看不到"整个系统怎么转起来"
- **过于简略的架构解释**：参与者和分层只有表格，没有解释每个组件为什么存在

## 设计目标

03 作为去中心化架构的 overview：

1. 让读者理解这个架构是什么、有哪些参与者和基础设施
2. 让读者理解为什么需要每一层（逐层递进）
3. 让读者看到从包创建到证据汇聚的完整业务流转
4. 每个环节点到为止，细节指向 04-07 子文档
5. 不使用 Gaia IR 层的术语

## 重写后的文档结构

### 1. 开头

```
# 去中心化架构

Status: Current canonical

本文档是 Gaia 去中心化架构的总纲——参与者、基础设施、
以及从包创建到证据汇聚的完整业务流转。
各环节的展开详见 04-07。
```

### 2. 参与者与基础设施

六类实体表：

| 实体 | 角色 | 职责概述 |
|------|------|---------|
| 作者（人类/AI agent） | 贡献者 | 创建知识包，声明依赖，编译，本地推理，发布 |
| LKM Server ×N | 贡献者 + 全局推理 | 全局推理；发现跨包关系后以 curation 包贡献 |
| Review Server ×N | 审核员 | 审核推理逻辑，给条件概率初始值 |
| Knowledge Repo | 基础设施 | 托管包源码、编译产物、review report |
| Official Registry | 基础设施 | 注册包/reviewer/LKM，存储推理结果，去重 |
| LKM Repo ×N | 基础设施 | 各 LKM 各自的运营仓库，Issues 管理其 research tasks |

两个关键设计点：
- LKM 和人类是并列贡献者，走完全相同的流程，没有捷径
- 一切通过 git 交互（commit、PR、Issues），不绑定 GitHub

### 3. Git 作为通用交互面

简述所有参与者通过 git 交互。以 GitHub 为例但不绑定。

### 4. 架构图

保留现有 Mermaid 图，微调：
- Review Server ×N、LKM Server ×N
- LKM Repo 标注为 ×N
- 连线说明表保留

### 5. 架构分层（逐层递进）

每一层解决前一层的局限，让读者理解每个组件存在的理由：

**纯包层：两个 git 仓库就能推理**
- 最简场景：创建包、声明依赖、本地编译和推理
- 依赖指向方式：已注册 → 引用 Registry 包标识；未注册 → 直接引用 git URL + tag
- 能力：本地推理、版本化、完全离线
- 局限：只看到直接依赖图，没有跨包去重，没有独立审核

**+ Review Server：推理链获得可信参数**
- 审核推理逻辑，给条件概率初始值
- 没有 review 的推理链可以注册但推理引擎跳过
- 新增能力：独立逻辑审核，推理链有可信参数
- 局限：仍只看到直接依赖，独立证据无法汇聚

**+ Official Registry：证据开始汇聚**
- 注册、去重（区分引用 vs 独立推导）、推理链激活、增量推理
- 新增能力：跨包去重、证据汇聚、增量推理
- 局限：embedding 匹配可能漏掉语义重复，看不到跨 Registry 关系

**+ LKM Server：全局推理与跨包关系发现**
- 拉取全局图运行十亿节点级推理
- 发现跨包关系（等价、矛盾、连接），以 research task 发布到自己的 LKM Repo
- 确认后以 curation 包走标准流程贡献
- 新增能力：全局推理收敛、跨包关系自动发现、弥补去重遗漏

### 6. 端到端业务流转

用 Alice 发布超导研究包、LKM 发现等价关系的完整场景串联：

**主线：包从创建到证据汇聚（① - ⑦）**
1. Alice 创建包，声明依赖 → 详见 04
2. 编译 + 本地推理预览 → 详见 04
3. Review Server 审核，给条件概率，rebuttal → 详见 06
4. 向 Registry 注册，CI 验证 → 详见 05
5. Registry 去重 + 推理链激活 + 增量推理 → 详见 05
6. LKM 全局推理发现 Alice 和 Bob 的结论相似，创建 research task → 详见 06
7. 调查确认 → curation 包 → 审核 → 注册 → 增量推理 → 详见 06, 07

**支线：社区协作**
- 浏览各 LKM Repo 的 research tasks
- 在 Registry Issues 提交 open question
- 基于 open question 创建新包

**错误修正**（一句话概述四种场景，详见 07）
- 迟发现的重复命题 → 合并，暂停参数，re-review
- 矛盾发现 → 推理引擎自动压低双方可信度
- 推理链撤回 → 标记撤回，重算下游
- 依赖包重大更新 → 通知下游，下游自主决定

### 7. 设计原则

精简为架构层面的核心原则：

| 原则 | 体现 |
|------|------|
| 包即 git 仓库 | 不依赖任何中心服务 |
| Git 是通用协议 | 所有参与者通过 commit / PR / Issues 交互 |
| 每一层可选增强 | 纯包可离线工作，Registry 和 LKM 是增值层 |
| 两类贡献者并列 | 人类/agent 和 LKM 走同样的流程，无特权 |
| 依赖优先引用 Registry | 已注册包通过 Registry 标识引用，未注册直接引用 git URL |
| Review 在包级别 | 审核发生在注册之前，report 存入包内 |
| 新推理链需有参数才生效 | 没有 review = 没有条件概率 = 推理引擎跳过 |
| 多级推理 | 包级 + Registry 增量 + LKM 全局 |
| 错误可修正 | 暂停 → re-review → 恢复，全程可审计 |

### 8. 各环节详解 + 参考文献

链接到 04-07 子文档和 00-pipeline-overview、01-product-scope。

## 砍掉的内容（回归子文档职责）

| 当前 03 中的内容 | 移交到 |
|-----------------|--------|
| "两类贡献者"详细对比表 | 参与者表已覆盖 |
| "Review Server 的定位"小节 | 06 |
| 注册结构（TOML 示例、目录树） | 05 |
| Reviewer.toml / LKM.toml 示例 | 05 |
| 注册流程详细步骤 | 05 |
| LKM Curation 两阶段完整流程图 | 06 |
| Open Questions 对比表 | 05 |
| 三类候选详解（equivalence/contradiction/connection） | 06 |
| "为什么用 Issues 而非 git 文件"论述 | 06 |

## 新增的内容

| 内容 | 目的 |
|------|------|
| 逐层递进的架构分层叙事 | 让读者理解每个组件为什么存在 |
| 端到端业务流转场景（Alice 的故事） | 让读者看到系统怎么转起来 |
| 依赖引用两种路径 | 已注册引用 Registry，未注册引用 git URL |
| LKM Server ×N、LKM Repo ×N | 修正单实例假设 |

## 不变的内容

- 文档定位：去中心化架构的 overview
- 01 (product-scope) 和 02 (domain-vocabulary) 不动（02 可能同步更新术语）
- 04-07 子文档内容不动
