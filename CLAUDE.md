<!-- BEGIN REFACTOR MORTAL BANNER · 2026-05-11 启动 -->

> 🚧 **REFACTOR IN PROGRESS — v0.5 工程质量基线对齐**
>
> 本仓库当前处于工程质量基线重构期间。所有 in-repo agent / 开发者动手前必须先按以下纪律操作：
>
> 1. **STATE 文档**：`.refactor/STATE.md` 是本次重构的实时进度文档。任何 agent / 开发者**动手前第一动作 = 读 STATE.md**，找到 task queue 中下一个 `pending` 项；干完后**退出前最后动作 = 更新 STATE.md**（mark `done` 或记 `breakpoint_notes`）。
> 2. **文档保真为头号纪律**：所有代码 / 类型注解 / docstring / 测试都必须严格匹配 `docs/foundations/**` 和 `docs/specs/**` 中描述的逻辑与语义。具体规则清单见 `.refactor/doc-fidelity-baseline.md`，agent 启动后必读。
> 3. **重构边界**：**不动** IR / 语义 / DSL 表面 / API 签名 / 算法 / 命名。本重构只做：工程基线注入（ruff / mypy / pytest / pre-commit config + CI）+ 补 type annotations + 补 Google docstrings + 补 test。
> 4. **🚨 doc-code 矛盾即停**：发现仓库 docs 与 code 在语义 / 行为层面**矛盾**（不是缺注解 / 缺 docstring 级的小差，而是实际逻辑分歧），**立即停手**，在 `.refactor/STATE.md` 当前 task `breakpoint_notes` 字段下记录（doc 段落引用 + code 文件:行号 + 矛盾描述 + 影响面），task status 标 `blocked`。**不要自行决断"哪边对"，也不要"顺手修齐"** — 重构 branch 只做工程基线，语义层矛盾一律升级。
> 5. **协作单**：本次重构由飞书协作单 `AM15dZDhjooNyaxZRhNc1Sawnce` 驱动；决策定盘 + ❓ 升回都走协作单。看板入口：`GAIA-LKM kanban` (`IUvrwMmwliAUDukbXfUcwwxEnmf`)。
> 6. **重构期间不开 PR — 仅 commit + push 到 `feat/v05-quality-baseline_rsw` branch**。本仓库 `CLAUDE.md § Workflow` 的「commit 完必开 PR」规则在重构期间替换为「commit + push feat branch 即可」；PR 在阶段 3 user explicit「ship/PR」handshake 后才开。
>
> **本 banner + `.refactor/` 目录是重构期间临时产物。** 重构 PR merge 完 + 用户明确说「清理重构产物」后，在收尾 PR 内一并删除。

<!-- END REFACTOR MORTAL BANNER -->

# CLAUDE.md

Instructions for Claude Code (claude.ai/code) working in this repo.

For project overview, architecture, CLI surface, and DSL reference, read `README.md` and `docs/foundations/`. This file is for **agent conventions only** — things you can't derive from reading the code.

## Common Commands

```bash
uv sync                          # install (always uv, never pip)
pytest                           # run tests
ruff check . && ruff format .    # lint + format
```

## Workflow

每项工作完成后，**必须**提交 PR 到 main：

1. 完成开发并确认测试通过
2. 跑 `ruff check .` 和 `ruff format --check .`，修干净
3. commit、push 分支、`gh pr create`
4. 创建 PR 后**必须**用 `gh run list --branch <branch> --limit 1` 检查 CI；失败则 `gh run view <run-id> --log-failed` 看日志修复

例外：版本号 bump、纯 README/CLAUDE.md 改动这类琐碎提交，按历史惯例可直接 push 到 main。

## Skills

`.claude/skills/` 下定义了规范化的工作流 skill，执行任务时**必须**使用对应的 skill：

- **writing-plans** — 写 implementation plan 时
- **executing-plans** — 按 plan 执行实现时
- **using-superpowers** — 调用 superpowers（spec/plan 文档生成）时
- **subagent-driven-development** — 多 agent 并行开发时
- **test-driven-development** — 写测试时
- **verification-before-completion** — 完成任务前的验证流程
- **finishing-a-development-branch** — 收尾开发分支时
- **requesting-code-review / receiving-code-review** — 代码审查流程

不要跳过 skill 直接手动操作。

## Implementation Rules

- **严格遵守设计文档**：实现时不得擅自降级设计文档中明确指定的技术方案（如用 TF-IDF 替代 embedding + BM25）。如有困难想简化，**必须先和用户商量**。
- **不确定就问**：对设计方案的任何偏离，无论多小，都要在实现前提出。
- **Plan 必须覆盖 spec 的每一步**：写 implementation plan 时逐条核对 spec，遗漏步骤等于悄悄砍需求。

## Scripts & Pipelines: Logging Is Mandatory

所有 CLI 脚本（`scripts/*.py`、`gaia/lkm/pipelines/*.py` 有 `__main__` 的）**必须**符合以下规范，否则后台运行就是黑盒：

1. **双 handler**：同时输出到 console 和 `logs/{name}-{timestamp}.log`
2. **`force=True`**：`logging.basicConfig` 必须加 `force=True` 覆盖已有配置（LanceDB/httpx import 时会初始化）
3. **每阶段打点**：每步开始/结束都 log，不只在最后 summary
4. **第一行输出 log 文件路径**：让用户立刻知道去哪看日志
5. **`print(..., flush=True)`**：logging 自动 flush，但普通 print 不会

模板：

```python
import logging, os, time

_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")
os.makedirs(_LOG_DIR, exist_ok=True)
_LOG_FILE = os.path.join(_LOG_DIR, f"{script_name}-{time.strftime('%Y%m%d-%H%M%S')}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(_LOG_FILE)],
    force=True,
)
logger = logging.getLogger(__name__)
logger.info("Log file: %s", _LOG_FILE)
```

**禁止**：后台跑脚本不看日志。跑完总要 tail 一下确认有输出。

## Code Style

- Ruff，line length 100，target Python 3.12
- 类型注解用 PEP 604（`X | None`，不是 `Optional[X]`）
- Google-style docstrings
- Pydantic v2 API：`.model_dump()` / `.model_validate()` / `.model_validate_json()`

## Worktrees

Worktrees 放在 `.worktrees/`（已 gitignore）：

```bash
git worktree add .worktrees/<name> -b feature/<name>
```

## Design Documents

Specs 在 `docs/foundations/` 按架构层组织：

```
docs/foundations/theory/       → Pure theory (Jaynes, BP) — 外部定义，从不变
docs/foundations/ecosystem/    → 业务生态 — 产品范围、去中心化架构、工作流
docs/foundations/gaia-ir/      → Gaia IR 结构契约（CLI↔LKM 共享）
docs/foundations/gaia-lang/    → Gaia Language（DSL，CLI 和 LKM 共享）
docs/foundations/bp/           → BP 计算语义
docs/foundations/review/       → Review pipeline
docs/foundations/cli/          → CLI（本地 authoring/compile/inference）
docs/foundations/lkm/          → LKM server（curation、global inference、storage、API）
```

历史文档在 `docs/archive/`，规划在 `docs/plans/`，设计在 `docs/specs/`。

## Documentation Policy

编辑架构或 foundation 文档前先读 `docs/documentation-policy.md`。

### Foundations 分层规则

`docs/foundations/` 镜像 Gaia 三层编译流水（Gaia Lang → Gaia IR → BP）+ 两个产品面（CLI、LKM）。信息**自上而下**流动 — 下层引用上层定义，**永不重复**。

| Layer | 责任 |
|-------|------|
| **theory/** | 外部理论（Jaynes、BP 算法）— 独立于 Gaia 的定义 |
| **ecosystem/** | 业务生态 — 产品范围、参与者关系 |
| **gaia-ir/** | Gaia IR 结构契约 — 节点 schema、factor 类型、canonicalization，**单一定义点** |
| **gaia-lang/** | Gaia Language（authoring DSL）— 语言规范、knowledge 类型、package 模型 |
| **bp/** | Gaia IR 上的 BP 计算 — factor 势能、推理算法 |
| **review/** | Review pipeline — 验证、审查、gating |
| **cli/** | CLI（本地工作流）— compiler、本地 inference、本地 storage |
| **lkm/** | LKM server（全局工作流）— curation、global inference、storage、API |

**规则：**
1. **gaia-ir/ 是结构定义的唯一来源**（FactorNode、knowledge 节点 schema）。bp/、cli/、lkm/ **引用**，不重定义。
2. **bp/** 定义计算语义。CLI 和 LKM 引用算法细节。
3. **cli/** 拥有 Gaia Lang。LKM **从不引用 Gaia Lang** — 它操作 Gaia IR。
4. 跨层定义**只链接，不复制**。
5. schema 改动先在 gaia-ir/ 改，再验证下游引用。

### Protected Layers (Change Control)

`gaia-ir/` 是 CLI↔LKM 的协议契约层。

**硬性规则：**
- Agent **禁止**直接修改 `docs/foundations/gaia-ir/` 下任何文件
- Agent **禁止**直接修改 `docs/foundations/theory/` 下任何文件（纯理论层，外部定义）
- 如果实现中发现 Gaia IR 定义需要调整，必须**停下来和用户沟通**：
  1. 当前定义是什么
  2. 为什么需要改
  3. 提议的改动内容
- 用户批准后，改动作为**独立 PR** 提交，不能混在功能 PR 里
- 合并后必须验证所有下游引用（bp/、cli/、lkm/）一致

### General Doc Rules

- 标明文档状态（`Current canonical` / `Target design` / `Transitional`）
- 标明改动性质（澄清 / 替换 / 提案）
- 优先**替换或归档**过时的概念模型，而不是无尽地原地打补丁
- canonical doc 添加、替换或重大重定范围时，**同 PR 更新**索引/归档/重定向文件
- **不要默默混合**：current canonical 语义、target design、运行时实现 quirk、历史背景 — 这些必须分开
