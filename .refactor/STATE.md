# Refactor STATE — v0.5 Quality Baseline Alignment

**当前阶段**: 阶段 0 收尾 → 阶段 1 待启动
**最后更新**: 2026-05-11 22:55 (阶段 0 完成)
**Branch**: `feat/v05-quality-baseline_rsw`（切自 `origin/v0.5` HEAD `8e8e771f`）
**协作单**: 飞书 doc_token `AM15dZDhjooNyaxZRhNc1Sawnce` — 决策定盘 + ❓ 升回 + Caveats 在那
**看板入口**: GAIA-LKM kanban (`IUvrwMmwliAUDukbXfUcwwxEnmf`)

---

## 如何使用本文档（in-repo agent / 开发者必读）

**动手前第一动作**: 读完本文档 → 读 `.refactor/doc-fidelity-baseline.md` → 找下一个 `pending` task → 在该 task 下写 `claimed_by` + `claimed_at`，status 标 `in-progress`。

**干活期间**: 任何中途断点都要更新对应 task 的 `breakpoint_notes`（按行号/symbol 精确）。每次重大节点 commit 时顺手更新 STATE.md 把 task status 推进。

**退出前最后动作**: task 完成 → status 标 `done` + 填 `completed_at`。task 未完成（context 用完 / 时间到 / 中断）→ status 维持 `in-progress`，但 **必须** 把 `breakpoint_notes` 写到「下一 agent 能无缝接力」的精度（具体到：哪个文件 / 哪个 symbol / 已修改 vs 待修改 / 当前 mypy/ruff 错误片段）。

**🚨 发现 doc-code 矛盾**: 立即停手 → task status 标 `blocked` → `breakpoint_notes` 写 doc 段落引用 + code 文件:行号 + 矛盾描述 + 影响面 → 在本文档「Doc-Code 矛盾记录」section 同步登记 → 通知用户回 home_agent 找 Claude 升回协作单 ❓ 段。**不要自行决断「哪边对」，也不要「顺手修齐」**。

---

## 阶段 ☐ Tracker

- [x] **阶段 0 — 仓库 prepare**（Claude 主导）
  - 完成项: 0.1 branch、0.2 文档保真 baseline、0.3 mortal banner、0.4 STATE.md 框架、0.5 baseline 数值、0.6 commit+push、0.7 iteration playbook
- [ ] **阶段 1 — 工程基线注入**（user 派 agent 接力）
  - 进度: 0 / 9 work units
- [ ] **🚦 Checkpoint α**: 阶段 1 完成 → user 回 home_agent 找 Claude 验收
- [ ] **阶段 2 — 全量补全**（user 派 agent serial 接力 task queue）
  - 进度: 0 / 25 work units（8 modules × annotations + 8 × docstrings + tests + coverage 兜底）
- [ ] **🚦 Checkpoint β**: 阶段 2 完成 → user 回 home_agent 找 Claude 验收
- [ ] **阶段 3 — 验收 + PR**
- [ ] **🚦 Checkpoint γ**: PR body 起草 + ship handshake
- [ ] **收尾 R.x — PR merge 后**: 删 mortal banner + `.refactor/` + 恢复 canon 默认 CD

---

## Baseline 数值（阶段 0.5 测得 · 2026-05-11）

| 指标 | 当前 | 目标 | Gap |
|------|-----:|-----:|----:|
| pytest 通过 | 1605 | 全绿 | 0 |
| pytest skipped | 3 | — | — |
| pytest warnings | 58 | (酌情清) | 58 |
| pytest 总耗时 | 75.71s | (保持) | — |
| **coverage TOTAL** | **90%** | ≥ 90% | **0（已达标）** |
| ruff (current minimal config) | 0 | 0 | 0 |
| **ruff (expanded 15 select)** | **2563** | 0 | **2563** |
| - 其中 `D` rules (docstrings) | ~1700 | 0 | ~1700 |
| - 其中 `RUF001/002/003` (ambig chars) | ~347 | 0 | ~347（需 per-file ignore 或本地化处理） |
| - 其中 `C901` (complexity) | 91 | 0 | 91 |
| - 其中 fix 可自动修复 | 305 | — | 自动 |
| **mypy strict** | **586** errors in **74** files (146 src files) | 0 | **586** |

**Notes**:
- coverage 已达 90% — **阶段 2.3 补 test 工作或为空**，仅在 mypy/docstring 增添时同步保持 coverage 不掉
- 几个模块 coverage 低于 90%：`gaia/lang/dsl/scaffold.py` (74%) / `gaia/trace/loader.py` (78%) / `gaia/lang/runtime/composition.py` (87%) / `gaia/trace/diagnostics.py` (89%) — 可作 阶段 2.3 选做项
- D-rules 占 ruff 错误近 70%，与「补 Google docstrings」工作 align
- RUF001/002/003 多为中文 docstrings/comments 含 ambiguous chars — 阶段 1.1 ruff config 可能需要 per-file ignore 或文件级 `noqa`

---

## Task Queue

### 阶段 1 — 工程基线注入（每 work unit 在该 branch 内单 commit 或合并 commit）

- [ ] **1.1** `pyproject.toml` — ruff lint full select（lbg 15 大类 + mccabe 9 + Google docstrings + per-file ignores）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
  - 参考: 协作单 § 必须迁移 #1
- [ ] **1.2** `pyproject.toml` — mypy strict 段 + dev extras 加 mypy + types-* stubs + tests overrides
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
  - 参考: 协作单 § 必须迁移 #2
- [ ] **1.3** `pyproject.toml` — pytest addopts 加 `--strict-markers` + `--cov-fail-under=90`；dev extras 加 pre-commit
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
  - 参考: 协作单 § 必须迁移 #4
- [ ] **1.4** 新 `.pre-commit-config.yaml` — 卫生 hooks + ruff (check --fix / format) + local mypy hook + exclude `^\.refactor/` + exclude `^tmp/`
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
  - 参考: 协作单 § 必须迁移 #3
- [ ] **1.5** `.github/workflows/ci.yml` — 改用 `uv sync --extra dev` + 加 mypy step
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
  - 参考: 协作单 § 必须迁移 #5
- [ ] **1.6** 新 `codecov.yml`（如启用 codecov bot；当前仓库无 codecov.yml，需新建对齐 lbg-cli 风格或保持本地强门兜底）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: 决策 — 是否启用 codecov bot？lbg-cli 是无的，仅靠 pyproject `--cov-fail-under` 本地强门。可选 (a) 不建 codecov.yml，仅本地强门兜底；(b) 建 codecov.yml + 本地强门双层兜底。
  - 参考: 协作单 § 顺手清理（codecov.yml 部分）
- [ ] **1.7** 新 `Makefile` —（酌情）`bootstrap / lint / typecheck / test / check` targets
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **1.8** 新 `CONTRIBUTING.md` — 开发者本地装规范指南（`uv sync --extra dev` + `pre-commit install` + `make check`）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **1.9** `CLAUDE.md` 全面重构（参考 Claude Code `/init` 标准）— 顶部 mortal banner 已在阶段 0 写好；本步落剩余段落（工程规范 / 本地装步骤 / 重构边界 / 文档保真纪律 / 测试要求 / 项目说明 link 到 README）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: 当前 CLAUDE.md 已经较精简（157 行），主要 update 集中在：(a) 增工程规范强约束段；(b) 增本地装步骤段；(c) 删 Skills 段（重构期间冻结；按 /init 标准非常规段）；(d) 重构边界声明段。
  - 参考: 协作单 § CLAUDE.md 工程化升级

> **阶段 1 完成判定**：以上 9 项全 `done` + `uv sync --extra dev` + `pre-commit run --all-files` 全绿（注意：此时 mypy strict 和 ruff 全 select 必然爆量错误，pre-commit hooks 配置允许 failing — 详见 1.4 / 1.9 设计）

> **🚦 Checkpoint α — 阶段 1 完成后**：user 把当前 STATE.md + 实际配置一并带回 home_agent，找 Claude 验收 config sanity + 阶段 2 task queue 复核

### 阶段 2 — 全量补全（agent serial 接力，每 work unit ≈ 1 module / 1 agent run）

#### 2.1 Type annotations 直到 mypy strict 干净（ordering: 叶子先 / 依赖后）

- [ ] **2.1-top** gaia 顶层文件（`__init__.py`、`constants.py`、`stats.py`、`unit.py`）— 小、独立、leaf 级
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **2.1-logic** `gaia/logic/`（2 个 .py，small）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **2.1-ir** `gaia/ir/`（IR 结构 — 改前必读 `doc-fidelity-baseline.md` § Protected layers + § Core invariants）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: ⚠️ 涉及 IR 协议契约，类型注解严格匹配 `docs/foundations/gaia-ir/` 中定义；不动 schema、不改 API 签名
- [ ] **2.1-bp** `gaia/bp/`（BP 算法 — 改前必读 `doc-fidelity-baseline.md` § BP semantics）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: ⚠️ 不动 message-passing 算法 / 不改 potential 函数语义
- [ ] **2.1-lang** `gaia/lang/`（DSL — 大模块，多子目录：dsl/、formula/、refs/、review/、runtime/、types/）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: 子目录建议子-work-unit 拆，agent 可在本 task 下拆为 2.1-lang-dsl / 2.1-lang-formula 等并 inline 更新此 STATE
- [ ] **2.1-trace** `gaia/trace/`
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **2.1-inquiry** `gaia/inquiry/`
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: —
- [ ] **2.1-cli** `gaia/cli/`（CLI 入口 — 改前必读 `doc-fidelity-baseline.md` § Behavior contracts）
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: ⚠️ CLI surface 是用户 visible 行为契约，不动命令名 / 参数 / output 格式
- [ ] **2.1-tests** `tests/` 全量
  - status: `pending` | claimed_by: — | claimed_at: — | completed_at: — | breakpoint_notes: tests/ 允许较松 mypy（per-file ignores）— 见协作单 § 必须迁移 #2 (tests overrides)

> 2.1 完成判定: `mypy --strict gaia/ tests/` 0 errors（tests 按 overrides 允许部分 D 类放松）

#### 2.2 Google docstrings 直到 ruff D 干净（ordering: 同 2.1）

- [ ] **2.2-top** | [ ] **2.2-logic** | [ ] **2.2-ir** | [ ] **2.2-bp** | [ ] **2.2-lang** | [ ] **2.2-trace** | [ ] **2.2-inquiry** | [ ] **2.2-cli** | [ ] **2.2-tests**
  - 每 work unit 字段同 2.1 模式（status / claimed_by / claimed_at / completed_at / breakpoint_notes）
  - 共同 brief 要点：docstring 内容**严格匹配** `docs/foundations/**` 描述；空 docstring 必填具体内容；不允许 paraphrase 加意；中文 docstring 注意 RUF001/002/003 ambiguous chars

> 2.2 完成判定: `ruff check . --select D` 0 errors（或 tests 部分 per-file `D100-D107` ignore）

#### 2.3 Coverage 兜底（baseline 已达 90% — 视后续 annotation/docstring 改动是否拉低 coverage 而定）

- [ ] **2.3-monitor** 每 work unit 完成后跑 `pytest --cov=gaia --cov-report=term`，若 TOTAL 跌破 90% → 在本 work unit 下补 test 拉回
  - status: `pending` | breakpoint_notes: 这是 ongoing 监控，不作 single agent run

> 2.3 完成判定: `pytest --cov-fail-under=90` 全绿

#### 2.4 全量收口 acceptance gate

- [ ] **2.4** 全量跑：`pre-commit run --all-files` + `pytest --cov` + `mypy --strict` — 全绿，coverage ≥ 90%
  - status: `pending` | breakpoint_notes: —

> **🚦 Checkpoint β — 阶段 2 完成后**：user 回 home_agent 找 Claude 验收（抽样 doc 保真 cross-check + acceptance gate 全绿确认）

### 阶段 3 — 验收 + PR

- [ ] **3.1** 全套验收 gate 再跑一遍
- [ ] **3.2** 🚦 **Checkpoint γ**: user 回 home_agent 找 Claude 起草 PR body
- [ ] **3.3** user push + open PR — **需 user explicit「ship / PR」handshake**

### 收尾 R — PR merge 后单独触发

- [ ] **R.1** 删 `gaia/CLAUDE.md` 顶部 mortal banner
- [ ] **R.2** 删 `gaia/.refactor/` 目录
- [ ] **R.3** 协作单标全部完成；collaboration-mode.md 默认 CD = Claude 自动恢复

---

## Checkpoint History

| Checkpoint | 时间 | Outcome | Notes |
|------------|------|---------|-------|
| 阶段 0 init | 2026-05-11 | (待 commit 后 done) | branch 切好 / mortal banner / STATE 框架 / baseline 数值 / doc fidelity baseline |
| α 阶段 1→2 | (未到) | — | — |
| β 阶段 2→3 | (未到) | — | — |
| γ 阶段 3 PR 开前 | (未到) | — | — |

---

## Doc-Code 矛盾记录

（agent 发现 doc 与 code 语义/行为矛盾时 mirror 在这里，同步升回协作单 ❓ 段）

### M1 — `docs/foundations/gaia-ir/01-overview.md` 引用过时模块路径 `gaia/gaia_ir/...`

- **发现于**: 阶段 0.2 doc fidelity baseline 抓取（subagent）
- **Doc 段落**: `docs/foundations/gaia-ir/01-overview.md` 在源码布局段引用 `gaia/gaia_ir/...`
- **Code 实际位置**: `gaia/ir/` （`gaia/ir/__init__.py` / `gaia/ir/graphs.py` 等；用户导入路径 `from gaia.ir import ...`）
- **矛盾性质**: doc 侧 stale wording — 代码模块从未叫 `gaia.gaia_ir`，doc 中的 `gaia/gaia_ir/` 是旧表述
- **影响面**: 任何照 doc 路径 grep code 的 agent 会找不到文件 → 可能误判 code 缺失或自行重命名；refactor agent 不可「顺手」把 code 改名 `gaia.ir → gaia.gaia_ir` 以匹配 doc（会破坏所有用户 import）
- **建议处置**: 以 **code 为准**（`gaia.ir` 是 canonical）；修 doc — 但 doc 在 `docs/foundations/gaia-ir/` 下，CLAUDE.md § Protected Layers 标明该目录 agent 禁止修改，需与用户确认 fix 路径（doc fix 是否纳入本次 refactor PR 还是另开 doc fix PR）
- **状态**: ❓ 待升回协作单确认（subagent flagged in baseline doc § 9 risk #1 + #17）
- **Mirror 自**: `.refactor/doc-fidelity-baseline.md` § 9 (risk surface) item 1 + 17

### M2 — `StrategyType` enum 跨文档不一致（轻度，非 blocker）

- **发现于**: 阶段 0.2
- **不一致**: `gaia-ir/02-gaia-ir.md §3.3` 列 `support` 为 named-canonical，但 `gaia-ir/08-validation.md §4` 允许集**不含** `support`，且 `noisy_and` 同时被标 deprecated 又被验证器允许
- **建议处置**: 保留当前 validator 实际行为（不论 doc 怎么写）；refactor 期 agent 跑 IR validation 测试以现行代码为准
- **状态**: 非 blocker — agent 见到 `support` / `noisy_and` 时保留原状即可。**不**升回协作单；记此供 agent 自查
- **Mirror 自**: `.refactor/doc-fidelity-baseline.md` § 9 risk #2 + #16

（M3 起空位备未来 agent 升回用）

---

## 关键参考速查

- **协作单决策清单**：飞书 doc `AM15dZDhjooNyaxZRhNc1Sawnce` § 一·决策清单
- **文档保真 baseline**：`.refactor/doc-fidelity-baseline.md`（必读）
- **CLAUDE.md mortal banner**：仓库根 `CLAUDE.md` 顶部
- **看板锚点**：`https://dptechnology.feishu.cn/wiki/IUvrwMmwliAUDukbXfUcwwxEnmf`
- **Branch**: `feat/v05-quality-baseline_rsw` (origin/v0.5 HEAD `8e8e771f`)
