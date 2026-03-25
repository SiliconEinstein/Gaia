# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Gaia is a Large Knowledge Model (LKM) — a billion-scale reasoning hypergraph for knowledge representation and inference. It stores knowledge as propositions and reasoning relationships via Graph IR (factor graphs), with a publish pipeline (build → canonicalize → publish → review → integrate) and probabilistic inference via loopy belief propagation.

**Stack:** Python 3.12+, FastAPI, Pydantic v2, LanceDB, Neo4j/Kuzu, NumPy/PyArrow

## Common Commands

```bash
# Install dependencies (always use uv, never pip)
uv sync

# Run all tests (auto-skips Neo4j tests if unavailable)
pytest

# Run tests with coverage
pytest --cov=libs --cov=services tests

# Run a single test file / single test
pytest tests/libs/storage/test_lance_content.py
pytest tests/libs/storage/test_models.py::test_knowledge_defaults

# Lint and format
ruff check .
ruff format .

# Run the API server
GAIA_LANCEDB_PATH=./data/lancedb/gaia \
  uvicorn services.gateway.app:create_app --factory --reload --host 0.0.0.0 --port 8000

# Run frontend dev server
cd frontend && npm install && npm run dev
```

All async tests run automatically via `asyncio_mode = "auto"`.

## Architecture

### Layer Structure

```
services/gateway/        → FastAPI HTTP API (routes, dependency injection)
    ↓ uses
libs/storage/            → Storage backends (LanceDB content, Neo4j/Kuzu graph, LanceDB vector)
libs/storage/models.py   → Core Pydantic models (Knowledge, Chain, Module, Package, etc.)
libs/inference/          → BP algorithm (factor graph, belief propagation)
libs/lang/               → Gaia Language v4 Typst DSL loader, compiler, and proof state analysis
```

Dependencies flow downward only. `libs` has no service dependencies.

### Gaia Language v4 DSL

Packages are authored as Typst projects (each with a `typst.toml` manifest).

- **Declarations:** `#setting`, `#question`, `#claim`, `#action`, `#relation` -- each emits a `figure(kind: "gaia-node")` in the Typst document.
- **Labels:** follow `<filename.label_name>` convention for cross-referencing within a package.
- **Reasoning links:** `from:` parameter lists premises on claims; `between:` parameter defines relation endpoints.
- **Cross-package deps:** `#gaia-bibliography(yaml("gaia-deps.yml"))` declares external knowledge references.
- **Graph IR extraction:** `typst query` extracts `gaia-node` figures into Graph IR (no `#export-graph()` call needed).
- **Runtime files:** Typst function definitions live in `libs/typst/gaia-lang-v4/`.

### Storage Layer (`libs/storage/`)

Three complementary backends managed by `StorageManager`:

| Backend | Store Class | Purpose |
|---------|------------|---------|
| **LanceDB** | `LanceContentStore` | Knowledge content, metadata, BM25 full-text search |
| **Neo4j/Kuzu** | `Neo4jGraphStore` / `KuzuGraphStore` | Graph topology (Knowledge→Chain relationships via `:PREMISE`/`:CONCLUSION`) |
| **Vector** | `LanceVectorStore` | Embedding similarity search |

Graph backend is optional — the system degrades gracefully without it. All writes go through three-write in `StorageManager.ingest_package()`: Content → Graph → Vector.

### Core Data Models (`libs/storage/models.py`)

- **Knowledge** — A proposition with `content`, `prior`, `type` (claim/question/setting/action), `keywords`, versioned by `(knowledge_id, version)`
- **Chain** — A reasoning link with `steps[]` (each step has `premises[]` → `conclusion`), `type` (deduction/induction/abstraction/contradiction/retraction)
- **Module** — Groups knowledge + chains within a package
- **Package** — A complete knowledge container (git repo)
- **ProbabilityRecord** — Per-step probability with source tracking
- **BeliefSnapshot** — BP result history

### Key Patterns

- **Fully async** — all I/O is `async def`, tests use `asyncio_mode = "auto"`
- **Dependency injection** — `services/gateway/deps.py` holds a global `Dependencies` singleton initialized at startup; tests inject custom instances via `create_app(dependencies=...)`
- **Graceful degradation** — Graph and vector stores are optional
- **Three-write atomicity** — `ingest_package()` writes Content (source of truth) → Graph → Vector with "preparing" → "committed" visibility gating
- **Versioned identity** — Knowledge keyed by `(knowledge_id, version)`, graph nodes use composite `knowledge_id@version`

### API Routes (`services/gateway/routes/`)

- **`packages.py`** — `POST /packages/ingest`, `GET /packages/{id}`, `GET /knowledge/{id}`, `GET /knowledge/{id}/versions`, `GET /knowledge/{id}/beliefs`, `GET /modules/{id}`, `GET /modules/{id}/chains`, `GET /chains/{id}/probabilities`

### Dependency Injection

`services/gateway/deps.py` holds a global `Dependencies` singleton initialized during FastAPI startup with a `StorageManager`.

## Testing

- Tests live in `tests/` mirroring the source structure
- Neo4j tests require a running Neo4j instance; CI provides one via service container
- E2E integration tests in `tests/integration/` exercise HTTP endpoints with real storage
- Test fixtures in `tests/fixtures/storage/` — paper fixtures for package ingest testing

## Code Style

- Ruff for linting/formatting, line length 100, target Python 3.12
- Type hints use PEP 604 union syntax (`X | None` not `Optional[X]`)
- Google-style docstrings
- Pydantic v2 API: `.model_dump()`, `.model_validate()`, `.model_validate_json()`

## Worktrees

Worktrees live in `.worktrees/` (gitignored). Create new worktrees there:

```bash
git worktree add .worktrees/<name> -b feature/<name>
```

## Workflow

每项工作完成后，**必须**提交 PR 到 main。流程：

1. 完成开发并确认测试通过
2. 运行 ruff lint 和 format 检查：
   ```bash
   ruff check .
   ruff format --check .
   ```
3. 修复所有 lint/format 错误
4. 提交 commit，push 分支，创建 PR
5. 创建 PR 后，**必须**用 `gh run list` 检查 CI 是否通过，若失败则查看日志修复：
   ```bash
   gh run list --branch <branch> --limit 1
   gh run view <run-id> --log-failed
   ```

## Skills

`.claude/skills/` 下定义了规范化的工作流 skill，执行任务时**必须**使用对应的 skill：

- **writing-plans** — 写 implementation plan 时使用
- **executing-plans** — 按 plan 执行实现时使用
- **using-superpowers** — 需要调用 superpowers（spec/plan 文档生成）时使用
- **subagent-driven-development** — 多 agent 并行开发时使用
- **test-driven-development** — 写测试时使用
- **verification-before-completion** — 完成任务前的验证流程
- **finishing-a-development-branch** — 收尾开发分支时使用
- **requesting-code-review / receiving-code-review** — 代码审查流程

不要跳过 skill 直接手动操作。

## LLM API

项目通过 litellm 调用 LLM，后端是内部 API 网关。

**API 配置**（在 `.env` 中）：
- `OPENAI_API_BASE` — 网关地址（`https://ai-gateway-internal.dp.tech`）
- `OPENAI_API_KEY` — API key

**模型命名**：网关的模型名与 OpenAI 官方不同，必须加 `openai/` 前缀让 litellm 通过 OpenAI 兼容接口调用：
```python
# ✅ 正确
litellm.acompletion(model="openai/chenkun/gpt-5-mini", ...)

# ❌ 错误 — litellm 不认识 provider
litellm.acompletion(model="chenkun/gpt-5-mini", ...)

# ❌ 错误 — 网关不认识这个模型名
litellm.acompletion(model="gpt-5-mini", ...)
```

**查看可用模型**：
```bash
source .env && curl -s "${OPENAI_API_BASE}/v1/models" \
  -H "Authorization: Bearer ${OPENAI_API_KEY}" | python3 -m json.tool | grep '"id"'
```

**需要设置全局 api_base**（在脚本入口处）：
```python
import litellm
litellm.api_base = os.getenv("OPENAI_API_BASE")
```

## Implementation Rules

- **严格遵守设计文档**：实现时不得擅自降级设计文档中明确指定的技术方案（如用 TF-IDF 替代 embedding + BM25）。如果实现上有困难或想简化，**必须先和用户商量**，不能自行决定偷工减料。
- **不确定就问**：对设计方案的任何偏离，无论多小，都要在实现前提出。
- **Plan 必须覆盖 spec 的每一步**：写 implementation plan 时，逐条核对 spec 中的每个步骤/流程，确保每一步都有对应的 task。遗漏步骤等于悄悄砍需求。

## Design Documents

Current specs live in `docs/foundations/` organized by architectural layer:

```
docs/foundations/theory/       → Pure theory (Jaynes, BP algorithm) — never changes
docs/foundations/rationale/    → Design philosophy, product scope — rarely changes
docs/foundations/graph-ir/     → Graph IR structural contract (CLI↔LKM shared layer)
docs/foundations/gaia-lang/    → Gaia Language (authoring DSL, shared by CLI and LKM)
docs/foundations/bp/           → BP computation semantics on Graph IR
docs/foundations/review/       → Review pipeline (shared by CLI and LKM)
docs/foundations/cli/          → CLI (local authoring, compilation, inference)
docs/foundations/lkm/          → LKM server (curation, global inference, storage, API)
```

Historical docs are in `docs/archive/`. Planning docs are in `docs/superpowers/plans/`.

## Documentation Policy

When editing architecture or foundation docs, read `docs/foundations/rationale/documentation-policy.md` first.

### Foundations Layer Rules

The `docs/foundations/` directory mirrors Gaia's three-layer compilation pipeline (Gaia Lang → Graph IR → BP) plus two product surfaces (CLI, LKM). Information flows **downward** — each layer references layers above it, never redefines.

| Layer | Responsibility | What belongs here |
|-------|---------------|-------------------|
| **theory/** | External theory (Jaynes, BP algorithm) | Definitions that exist independent of Gaia |
| **rationale/** | Gaia design philosophy, product scope | Why Gaia makes the choices it does |
| **graph-ir/** | Graph IR structural contract | Node schemas, factor types, canonicalization — defined ONCE here |
| **gaia-lang/** | Gaia Language (authoring DSL) | Language spec, knowledge types, package model — shared by CLI and LKM |
| **bp/** | BP computation on Graph IR | Factor potentials, inference algorithm, local vs global |
| **review/** | Review pipeline | Verification, review, gating — shared by CLI and LKM |
| **cli/** | CLI (local workflow) | Compiler, local inference, local storage |
| **lkm/** | LKM server (global workflow) | Curation, global inference, storage, API |

**Rules:**
1. **graph-ir/ is the single source of truth** for structural definitions (FactorNode, knowledge node schemas). BP, CLI, and LKM reference it, never redefine.
2. **bp/** defines computational semantics (potential functions). CLI and LKM reference it for algorithm details.
3. **cli/** owns Gaia Lang. LKM never references Gaia Lang — it operates on Graph IR.
4. **Never copy** a definition from another layer — link to it instead.
5. When a schema changes, update it in graph-ir/ first, then verify downstream references.

### General Doc Rules

- identify the doc's status (`Current canonical`, `Target design`, `Transitional`)
- identify whether the edit is a clarification, a replacement, or a proposal
- prefer replacing or archiving an obsolete conceptual model over endlessly patching it in place
- update index/archive/redirect files in the same branch when a canonical doc is added, replaced, or materially re-scoped

Do not silently mix:

- current canonical semantics
- target design
- runtime implementation quirks
- historical rationale

into one document.
