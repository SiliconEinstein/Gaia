# `gaia compile . --github` — Knowledge Package Presentation

> **Status:** Proposal
>
> **Context:** 当前 `gaia compile . --readme` 生成的 README 是 1000+ 行的 claim 平铺罗列，
> Mermaid 图包含所有节点难以阅读。需要分层展示：Wiki 给 agent 消费，README 和 GitHub Pages 给人类阅读。

## 1. 总体架构

```
Python DSL 源码 + artifacts/ + beliefs.json
        ↓
gaia compile . --github       ← 确定性，Python 代码
        ↓
.github-output/               ← 骨架 + 数据 + React 模板
        ↓
agent skill /gaia:publish     ← LLM 填写叙事（可用 Ralph Loop 迭代）
        ↓
README.md + wiki/ + docs/     ← 最终产物，git push 后自动部署
```

### 三层展示，三类受众

| 渠道 | 受众 | 优化方向 | 生成方式 |
|------|------|---------|---------|
| **Wiki** | Agent | 结构化、可解析、完整参考 | 确定性（Python） |
| **README** | Human | 叙事、直觉、一眼看懂 | 骨架确定性 + LLM 叙事 |
| **GitHub Pages** | Human | 交互式论文、图文并茂 | React 模板确定性 + LLM 叙事 |

## 2. `gaia compile . --github` 输出

### 2.1 输出结构

```
.github-output/
├── wiki/                              # 确定性，给 agent 消费
│   ├── Home.md                        # 目录 + claim 索引
│   ├── Module-motivation.md           # 每个 module 一页
│   ├── Module-s2-method.md
│   └── Inference-Results.md           # beliefs 完整表
├── docs/                              # GitHub Pages (React app)
│   ├── package.json                   # 固定 React 模板
│   ├── vite.config.ts
│   ├── src/                           # 固定 React 模板
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── KnowledgeGraph.tsx     # Cytoscape.js 交互图
│   │   │   ├── SectionView.tsx        # 章节叙事渲染
│   │   │   ├── ClaimDetail.tsx        # claim 详情侧栏
│   │   │   └── LanguageSwitch.tsx     # EN/中文切换
│   │   └── index.css
│   ├── public/
│   │   ├── data/
│   │   │   ├── graph.json            # 知识图数据
│   │   │   ├── beliefs.json          # BP 结果
│   │   │   ├── meta.json             # 包元数据（名称、描述、作者）
│   │   │   └── sections/             # 叙事 placeholder（agent 填写）
│   │   │       ├── motivation.md
│   │   │       └── s2-method.md
│   │   └── assets/                   # 从 artifacts/ 复制的图片
│   └── .github/
│       └── workflows/
│           └── pages.yml             # GitHub Actions: build + deploy
├── README.md                          # 骨架 + placeholder
└── manifest.json                      # 生成清单，agent 读取
```

### 2.2 确定性生成的内容

#### Wiki 页面

每个 module 一页，格式固定（agent 可解析）：

```markdown
# Module: motivation

## Claims

### bcs_theory
- **QID:** `github:package::bcs_theory`
- **Type:** setting
- **Content:** Bardeen-Cooper-Schrieffer (BCS) theory...
- **Prior:** —
- **Belief:** —

### adiabatic_approx
- **QID:** `github:package::adiabatic_approx`
- **Type:** claim
- **Content:** In conventional metals, the typical phonon frequency...
- **Prior:** 0.95
- **Belief:** 0.90
- **Derived from:** deduction([adiabatic_approx])
- **Reasoning:** The adiabatic condition...
- **Referenced by:** [me_framework], [eft_eph_vertex]
```

#### graph.json

```json
{
  "nodes": [
    {
      "id": "github:pkg::claim_a",
      "label": "Claim A",
      "type": "claim",
      "module": "motivation",
      "prior": 0.9,
      "belief": 0.85,
      "exported": true,
      "content": "...",
      "metadata": {"figure": "assets/fig3.png"}
    }
  ],
  "edges": [
    {
      "source": "github:pkg::premise",
      "target": "github:pkg::conclusion",
      "type": "strategy",
      "strategy_type": "deduction",
      "reason": "..."
    }
  ]
}
```

#### 简化 Mermaid 图（README 用）

算法：
1. **必选** 所有 exported conclusions（`__all__`），标 ⭐
2. 计算所有 claim 的 |belief - prior|，取偏差最大的 top N（使总节点 ≤ 15）
3. 保留选中节点之间的 strategy/operator 边
4. 每个节点标注 `Label (prior → belief)`
5. 颜色：exported = 绿色，高偏差 = 黄色/红色

#### README 骨架

```markdown
# 📄 Package Title

[![Interactive Paper](https://img.shields.io/badge/📖_Interactive_Paper-GitHub_Pages-blue)](https://user.github.io/repo)
[![Knowledge Reference](https://img.shields.io/badge/📚_Reference-Wiki-green)](https://github.com/user/repo/wiki)

<!-- NARRATIVE_SUMMARY: agent 填写 -->

## Key Findings

| Conclusion | Prior → Belief | Summary |
|-----------|---------------|---------|
| ⭐ Tc(Al) predicted | — → 0.93 | ... |
| ⭐ Vacuum law | 0.30 → 0.96 | ... |

## Overview

```mermaid
[简化 Mermaid 图]
```

## Key Figures

<!-- FIGURES: agent 从 metadata.figure 选取最重要的图片嵌入 -->

📖 [Read the full interactive paper →](https://user.github.io/repo)
📚 [Detailed claim reference →](https://github.com/user/repo/wiki)
```

#### React 模板

固定的 React 应用，随 gaia-lang 包分发。特性：

- **交互式知识图**：Cytoscape.js，节点颜色 = belief 强度
- **点击节点**：侧栏展开 claim content + reasoning + prior → belief
- **章节叙事**：从 `sections/*.md` 加载，markdown 渲染
- **图片嵌入**：claim metadata 里的 figure 引用自动内联
- **Abduction 高亮**：hypothesis vs alternative 并排对比
- **Contradiction 高亮**：赢的一方绿色，输的红色
- **语言切换**：EN / 中文
- **响应式布局**：桌面和移动端都可读

#### GitHub Actions workflow

```yaml
name: Deploy Pages
on:
  push:
    branches: [main]
    paths: ['docs/**']
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: cd docs && npm ci && npm run build
      - uses: actions/upload-pages-artifact@v3
        with: { path: docs/dist }
  deploy:
    needs: build
    permissions:
      pages: write
      id-token: write
    environment:
      name: github-pages
    runs-on: ubuntu-latest
    steps:
      - uses: actions/deploy-pages@v4
```

#### manifest.json

```json
{
  "package_name": "superconductivity-electron-liquids-gaia",
  "generated_at": "2026-04-06T12:00:00Z",
  "wiki_pages": ["Home.md", "Module-motivation.md", ...],
  "readme_placeholders": ["NARRATIVE_SUMMARY", "FIGURES"],
  "pages_sections": ["motivation.md", "s2-method.md", ...],
  "assets": ["fig3.png", "fig5.png"],
  "exported_conclusions": ["tc_al_predicted", "tc_li_predicted", ...],
  "total_claims": 42,
  "total_beliefs": 42
}
```

## 3. Agent Skill: `/gaia:publish`

### 3.1 职责

读取 `.github-output/manifest.json`，基于 DSL 源码 + beliefs 生成：

1. **README 叙事摘要** — 一段话总结核心贡献和意义
2. **README 图片选取** — 从 metadata.figure 中选最重要的 1-3 张嵌入
3. **Pages 章节叙事** — 每个 module 一段自然语言，串联推理逻辑（不是列 claim）
4. **中文版本** — README 保持英文，Pages 和 Wiki 生成中文版
5. **Critical Analysis** — 弱点和证据缺口摘要

### 3.2 执行方式

可以用 Ralph Loop 迭代（配合 chrome-devtools-mcp 检查 Pages 渲染效果）：

```
/ralph-loop "Read .github-output/manifest.json. Fill all placeholders 
in README.md and docs/public/data/sections/. Read the Python DSL source 
code and beliefs.json. Write narrative summaries, embed figures, generate 
Chinese translations. Check docs/ rendering with Chrome DevTools.
Output <promise>PUBLISH COMPLETE</promise> when all placeholders filled 
and pages render correctly." --max-iterations 10
```

### 3.3 质量标准

- 所有 exported conclusions 在 README 里提到
- 所有 placeholder 被填充
- 所有 metadata.figure 的图片在 Pages 中嵌入
- Pages 在浏览器中正常渲染
- 中英文版本内容一致

## 4. GitHub 仓库配置

`gaia compile . --github` 完成后提示：

```
Generated .github-output/. Next steps:
1. Copy wiki/ to your repo's wiki:
   git clone https://github.com/USER/REPO.wiki.git
   cp .github-output/wiki/* REPO.wiki/
   cd REPO.wiki && git add -A && git commit -m "Update wiki" && git push

2. Copy docs/ and README.md to your repo:
   cp -r .github-output/docs .
   cp .github-output/README.md .

3. Run /gaia:publish to fill narrative content

4. Push and enable GitHub Pages (source: GitHub Actions)

5. Update repo About:
   gh repo edit --description "..." --homepage "https://USER.github.io/REPO"
```

## 5. 实施顺序

1. **Wiki 生成**（确定性，最简单）— 从 IR 生成结构化 markdown 页面
2. **简化 Mermaid 图算法** — exported + 高偏差节点选取
3. **README 骨架** — badge + 简化图 + 结论表 + placeholder
4. **graph.json 生成** — 节点 + 边 + metadata
5. **React 模板** — Cytoscape.js 交互图 + 章节渲染 + 语言切换
6. **GitHub Actions workflow** — 自动 build + deploy
7. **`/gaia:publish` skill** — LLM 叙事填写
8. **manifest.json + CLI 集成** — 把以上串到 `gaia compile . --github`
