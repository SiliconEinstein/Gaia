# ARM/ARA 到 Gaia v0.5 Package 的投影规范

Status: proposal
Date: 2026-05-19
Scope: ARM bundle, ARA artifact, embedded Gaia package, Gaia v0.5 action DSL, Gaia official registry

## 1. 目标

把 ARM 和 ARA 这两类 agent-facing research artifacts 变成 Gaia 可编译、可检查、可注册的 knowledge package。

核心目标有三个：

1. 尽量用程序转换直接生成一个 Gaia package。
2. 程序不能可靠判断的地方，先保留为 scaffold，不强行形式化。
3. 让用户选择是否进一步形式化；进一步形式化可以由 agent 过一遍，但必须可审计、可回滚。

一句话设计：

```text
ARM / ARA host artifact
  -> deterministic projector
  -> embedded Gaia scaffold package
  -> optional agent formalization
  -> Gaia compile/check/infer/register
```

## 2. 第一性原则

### 2.1 Host package 和 Gaia package 不是同一层

ARM/ARA 是研究对象的组织格式，负责保存论文、代码、trace、evidence、实验结果和 agent 操作上下文。

Gaia 是语义投影层，负责 claim、observation、dependency、inference、contradiction、hole、bridge、registry reference。

因此 Gaia 不应该吞掉 ARM/ARA，也不应该重写它们的目录协议。Gaia 只在 host 里提供一个嵌入式 knowledge root。

### 2.2 默认必须是安全的程序投影

程序投影默认只做确定性、低风险转换：

- Markdown/YAML/JSON 结构解析
- stable id 生成
- source anchor 绑定
- raw evidence 转成 `observe(...)`
- claim 文本转成 `claim(...)`
- 未形式化依赖转成 `depends_on(...)`
- 疑似关系转成 `candidate_relation(...)`

程序默认不得把一个 ARA/ARM 的普通引用硬升级成 `derive(...)`、`infer(...)`、`contradict(...)`、`equal(...)`。

### 2.3 形式化必须显式选择

进一步形式化是可选步骤。用户可以选择：

```text
scaffold only       只生成可编译 Gaia package
agent formalize     agent 读取 queue 后提出形式化升级
interactive         用户逐条确认形式化升级
strict publish      registry 发布前不允许 unresolved formalization queue
```

### 2.4 Registry 兼容使用 Gaia identity

ARM/ARA 内部路径不能成为跨包引用的 canonical identity。跨 Gaia package 引用必须使用：

```text
package_name
version or resolved git sha
qid / label
interface_hash
```

ARM/ARA 路径只作为 source anchor 写进 `source_map.json`。

## 3. 目录布局

### 3.1 Native embedded layout

目标布局：

```text
<host>/
  arm_manifest.json              # ARM only
  PAPER.md                       # ARA only
  logic/                         # ARA only
  knowledge/                     # ARM optional
  trace/
  evidence/
  src/

  gaia/
    projection.toml              # human-editable projection policy
    formalization.py             # optional user/agent-authored upgrades
    overlays/                    # optional curated fragments

  .gaia/
    package.toml                 # Gaia package identity for embedded root
    lock.json                    # Gaia registry dependencies
    source_map.json              # host anchors -> Gaia labels/qids/actions
    formalization_queue.jsonl    # items needing human/agent judgment
    generated/
      from_host.py               # deterministic generated Gaia v0.5 DSL
    manifests/
      exports.json
      premises.json
      holes.json
      bridges.json
    ir.json
    ir_hash
    beliefs.json                 # optional infer output
```

`gaia/` 是 Gaia source/projection policy 目录，不要求作为 Python import package。Native loader 应该用 path-based 或 synthetic-module loading，避免和 installed `gaia` library 发生 import-name 冲突。

### 3.2 Current v0.5 compatibility layout

当前 Gaia v0.5 loader 仍主要读取 `pyproject.toml` + `src/<import_name>/`。在 native embedded resolver 完成前，projector 可以生成一个隐藏 adapter package：

```text
<host>/
  gaia/
    projection.toml
    formalization.py

  .gaia/
    adapter/
      pyproject.toml
      src/<synthetic_import_name>/
        __init__.py              # imports generated/from_host.py + overlays
        from_host.py
        formalization.py
    source_map.json
    formalization_queue.jsonl
```

`gaia build compile <host>` 在兼容模式下实际编译 `.gaia/adapter/`，但输出仍同步回 `<host>/.gaia/ir.json` 和 `<host>/.gaia/manifests/`。

这使得现在就能生成可编译 package，同时不阻塞将来的 embedded resolver。

## 4. CLI 语义

不要新增 `gaia mount`。

用户心智模型：

```bash
gaia build init --embedded .
gaia build compile .
gaia pkg add <other-gaia-package>
gaia run infer .
gaia pkg register .
```

说明：

- `gaia build init --embedded <path>` 创建 `gaia/` 和 `.gaia/package.toml`。
- `gaia build compile <path>` 自动检测 ARM/ARA host，并运行 deterministic projector。
- `gaia pkg add` 只表示添加 Gaia semantic dependency，不表示挂载 host。
- `gaia build compile --formalize agent <path>` 可选触发 agent formalization。
- `gaia pkg register <path>` 注册 embedded Gaia package 的 registry projection。

当前 v0.5 已经把历史 flat verbs 移到 grouped commands，因此实现应以 `gaia pkg add` 为准；文档中可以把旧心智模型 `gaia add` 解释为同一语义。

## 5. Projection mode

### 5.1 `scaffold` mode, default

完全程序化，不调用 agent。

输出：

- `claim(...)`
- `note(...)`
- `question(...)`
- `observe(...)`
- `depends_on(...)`
- `candidate_relation(...)`
- `.gaia/source_map.json`
- `.gaia/formalization_queue.jsonl`

不得输出：

- 未审查的 `derive(...)`
- 未审查的 `infer(...)`
- 未审查的 `equal(...)`
- 未审查的 `contradict(...)`
- 未审查的 `exclusive(...)`
- 未审查的强概率参数

### 5.2 `formalized` mode

读取 `formalization_queue.jsonl`，由 agent 或用户把部分 scaffold 升级为 formal actions。

允许升级：

```text
depends_on       -> derive / infer / compute
candidate_relation(pattern="equal")       -> equal
candidate_relation(pattern="contradict")  -> contradict
candidate_relation(pattern="exclusive")   -> exclusive
raw measurement note                      -> observe(distribution, value=..., error=...)
related work registry match               -> gaia pkg add + fills
```

每个升级必须写入：

- 原 source anchor
- 升级理由
- reviewer/user/agent provenance
- confidence
- rejected alternatives, if any

### 5.3 `locked` mode

用于发布和 registry CI。

要求：

- source hashes 没有漂移
- generated code 与 source map 一致
- `gaia build compile` 通过
- `gaia build check` 通过
- registry-facing manifests 存在
- 如果 policy 要求 strict publish，`formalization_queue.jsonl` 中不得有 blocking item

## 6. ARM 投影规则

ARM 当前是 agent-ready manuscript / reproduction bundle。它的知识层可能是：

```text
knowledge/claims.json
```

或 manifest 中的：

```json
{
  "knowledge": {
    "claims_path": "knowledge/claims.json",
    "format": "flat-v1 | gaia-hypergraph-v1"
  }
}
```

### 6.1 ARM source categories

| ARM source | Programmatic projection | Agent/user needed |
|---|---|---|
| `arm_manifest.json` identity, title, DOI, authors | `.gaia/package.toml`, package metadata, `note(...)` | only if metadata conflict |
| `knowledge/claims.json` with stable claim ids | `claim(...)` + source map | if claim splitting/merging is ambiguous |
| `knowledge/claims.json` Gaia hypergraph | direct import to generated Gaia records when schema is recognized | if schema version unknown |
| `characterization.json` metrics/results | `observe(...)` for raw reported results | if mapping result -> hypothesis requires inference |
| `execution/`, scripts, notebooks, Dockerfile | `note(...)` refs, optional `compute(...)` only for deterministic known output functions | if execution result must support a claim |
| `trace/` agent logs | `note(...)`, source anchors, possible formalization queue | if trace contains claim/evidence not elsewhere captured |
| `rag/`, `skills/`, `sub_agent/` | `note(...)` / provenance metadata | usually no formalization |
| related upstream package ids | `gaia pkg add` if registry match is exact | if fuzzy package matching needed |

### 6.2 ARM default output

For an ARM bundle without explicit Gaia knowledge:

```python
from gaia.engine.lang import claim, note, observe, depends_on, candidate_relation

bundle = note("ARM bundle metadata ...", metadata={...})
metric = observe(
    "Reported metric X = ...",
    source_refs=["characterization.json#/metrics/X"],
    rationale="Programmatic projection from ARM characterization.",
    label="arm_metric_x_observed",
)
```

For an ARM bundle with `knowledge/claims.json`:

```python
c001 = claim(
    "...",
    title="ARM claim C001",
    metadata={"arm_id": "C001", "source": "knowledge/claims.json#/claims/0"},
)
depends_on(
    c001,
    given=metric,
    rationale="ARM claim references metric evidence; warrant type not yet reviewed.",
    label="arm_c001_depends_on_metric_x",
)
```

### 6.3 ARM formalization queue triggers

Add an item to `.gaia/formalization_queue.jsonl` when:

- claim has evidence refs but no explicit warrant type
- trace says a result supports/refutes a claim
- characterization metric implies a comparison or causal conclusion
- knowledge format is unknown or partially recognized
- related package reference is not an exact Gaia registry coordinate

## 7. ARA 投影规则

ARA 是 richer research artifact。它通常有：

```text
PAPER.md
logic/claims.md
logic/problem.md
logic/experiments.md
logic/related_work.md
logic/solution/
src/
trace/exploration_tree.yaml
evidence/tables/
evidence/figures/
```

ARA 内部有 `supported/refuted`、`dead_end`、`refutes`、`baseline`、`imports` 这类语义线索，但没有 Gaia 需要的 deterministic/statistical/contradiction 一等类型。

ARA 也有“引用其他研究对象”的能力，但它不是 Gaia 意义上的 package-to-package reference。`logic/related_work.md` 表达的是 DOI/arXiv/论文/方法级的 scholarly dependency；Gaia registry 表达的是可解析、可版本锁定、带 exported interface 的 semantic package dependency。

因此 ARA external refs 的默认规则是：

```text
ARA related_work entry
  -> source_map scholarly_reference record
  -> optional formalization_queue item

if exact Gaia registry match exists:
  -> gaia pkg add <matched-package>
  -> lock registry coordinate in .gaia/lock.json
  -> create bridge/fills candidate when a target interface is known

if no exact Gaia registry match:
  -> do not invent a package dependency
  -> keep DOI/arXiv/path as source provenance
  -> ask user/agent whether to bind or create a Gaia package
```

### 7.1 ARA source categories

| ARA source | Programmatic projection | Agent/user needed |
|---|---|---|
| `PAPER.md` frontmatter | package metadata, `note(...)` abstract, source hash | if missing identity |
| `logic/claims.md` Cxx blocks | `claim(...)` with `ara_id` | if claim should be split/merged |
| claim `Status: supported/refuted` | metadata + queue item when refuted | to decide `contradict(...)` |
| claim `Proof: [Exx]` | `depends_on(...)` from claim to experiment/evidence observations | to choose `infer(...)` or `derive(...)` |
| `logic/problem.md` observations | `claim(...)` or `note(...)` by structural rule | if observation is interpretive |
| `logic/experiments.md` | `note(...)` experiment plan; links to claims | to decide warrant strength |
| `evidence/tables/*`, `evidence/figures/*` | `observe(...)` with `source_refs` | if table needs numeric distribution modeling |
| `logic/related_work.md Type: imports/baseline/extends/bounds/refutes` | scholarly reference metadata; `gaia pkg add` only on exact Gaia registry match; `candidate_relation(...)` for refutes | to bind/create package, materialize `fills`, or materialize `contradict` |
| `trace/exploration_tree.yaml dead_end` | `note(...)` + queue item | if it refutes a formal claim |
| `src/` code/configs | `note(...)` refs; optional `compute(...)` for deterministic functions | if code output is a formal premise |

### 7.2 ARA default output

Example for ARA claim C02:

```python
from gaia.engine.lang import claim, note, observe, depends_on

c02 = claim(
    "Residual learning eliminates the degradation problem.",
    title="ARA C02",
    metadata={
        "ara_id": "C02",
        "ara_source": "logic/claims.md#C02",
        "ara_status": "supported",
    },
)

table2 = observe(
    "Table 2 reports the plain-vs-residual ImageNet validation comparison.",
    source_refs=["evidence/tables/table2_imagenet_plain_vs_residual.md"],
    rationale="Programmatic projection of ARA evidence table.",
    label="ara_c02_table2_observation",
)

ara_c02_depends_on_table2 = depends_on(
    c02,
    given=table2,
    rationale=(
        "ARA C02 cites this evidence, but the projector does not decide "
        "whether the warrant is statistical, deterministic, or causal."
    ),
    label="ara_c02_depends_on_table2",
    metadata={"projection_confidence": "programmatic"},
)
```

Optional agent formalization may upgrade this to:

```python
from gaia.engine.lang import infer, materialize

infer(
    table2,
    hypothesis=c02,
    p_e_given_h=0.9,
    p_e_given_not_h=0.2,
    rationale="Reviewed empirical comparison: table values directly support C02.",
    label="ara_c02_table2_infer",
)

materialize(
    ara_c02_depends_on_table2,
    by="ara_c02_table2_infer",
    rationale="User accepted empirical warrant.",
)
```

The numeric likelihood values above are not programmatic defaults. They require policy, reviewer, or user acceptance.

## 8. Gaia v0.5 action mapping

Use Gaia v0.5 action DSL as the canonical target.

| Situation | Gaia v0.5 target |
|---|---|
| Falsifiable scientific assertion | `claim(...)` |
| Background, method description, environment, code/config reference | `note(...)` |
| Open research question | `question(...)` |
| Raw reported fact, metric, table row, figure datapoint | `observe(...)` |
| Exact derivation / theorem / deterministic entailment | `derive(...)` |
| Empirical evidence for hypothesis with likelihood semantics | `infer(...)` |
| Deterministic code computation producing a claim-like output | `compute(...)` |
| Claim dependency without reviewed warrant | `depends_on(...)` |
| Possible equivalence / contradiction / exclusivity | `candidate_relation(...)` |
| Reviewed equivalence | `equal(...)` |
| Reviewed contradiction | `contradict(...)` |
| Reviewed closed binary alternative | `exclusive(...)` |
| Symmetric empirical association | `associate(...)` |
| Scaffold upgraded to formal graph record | `materialize(...)` |
| Cross-package interface filling | `fills(...)` |

Programmatic projector should prefer `depends_on(...)` and `candidate_relation(...)` when in doubt.

## 9. Source map schema

`<host>/.gaia/source_map.json` is the audit spine.

```json
{
  "schema_version": 1,
  "host_kind": "arm|ara",
  "host_root": ".",
  "projection_mode": "scaffold",
  "source_hash": "sha256:...",
  "records": [
    {
      "source_id": "ARA:C02",
      "source_path": "logic/claims.md",
      "source_anchor": "C02",
      "source_hash": "sha256:...",
      "gaia_label": "ara_c02",
      "gaia_qid": "github:resnet_ara::knowledge::ara_c02",
      "gaia_record_kind": "claim",
      "generated_file": ".gaia/generated/from_host.py",
      "projection_rule": "ara.claim_block.v1",
      "confidence": "programmatic",
      "requires_review": false
    },
    {
      "source_id": "ARA:C02->Table2",
      "source_path": "logic/claims.md",
      "source_anchor": "C02.Proof",
      "gaia_label": "ara_c02_depends_on_table2",
      "gaia_record_kind": "depends_on",
      "projection_rule": "ara.claim_proof_scaffold.v1",
      "confidence": "programmatic",
      "requires_review": true,
      "queue_id": "FQ0001"
    }
  ]
}
```

`confidence` values:

```text
programmatic  deterministic parse, no semantic judgment
projected     heuristic classifier inferred the type
agent         agent proposed the mapping
user          user confirmed the mapping
registry      resolved from Gaia registry metadata
```

## 10. Formalization queue schema

`<host>/.gaia/formalization_queue.jsonl` is append-only.

```json
{
  "queue_id": "FQ0001",
  "source_id": "ARA:C02->Table2",
  "source_refs": [
    "logic/claims.md#C02",
    "logic/experiments.md#E01",
    "evidence/tables/table2_imagenet_plain_vs_residual.md"
  ],
  "current_gaia_record": "ara_c02_depends_on_table2",
  "current_action": "depends_on",
  "candidate_actions": ["infer", "derive"],
  "reason_review_needed": "ARA Proof links evidence to claim but does not classify warrant type.",
  "blocking_for_publish": false,
  "status": "open"
}
```

Agent formalization may append:

```json
{
  "queue_id": "FQ0001",
  "status": "resolved",
  "chosen_action": "infer",
  "chosen_label": "ara_c02_table2_infer",
  "rationale": "The evidence is an empirical comparison with baseline metrics.",
  "provenance": "agent-proposed,user-confirmed",
  "supersedes": "open:FQ0001"
}
```

## 11. Deterministic projector algorithm

Pseudo-code:

```text
project(host_root):
  host_kind = detect_host_kind(host_root)
  package_id = derive_package_identity(host_root)
  read projection policy from gaia/projection.toml if present

  sources = collect_structured_sources(host_root, host_kind)
  source_hash = hash_sources(sources)

  records = []
  queue = []

  for source object:
    if object is package metadata:
      emit package.toml fields
    if object is claim:
      emit claim(...)
      add source_map record
    if object is raw evidence:
      emit observe(...)
      add source_map record
    if object is explicit question:
      emit question(...)
    if object is background/method/config/trace:
      emit note(...)
    if object is proof/dependency without formal warrant:
      emit depends_on(...)
      enqueue formalization item
    if object is possible relation:
      emit candidate_relation(...)
      enqueue formalization item

  write .gaia/generated/from_host.py
  write .gaia/source_map.json
  write .gaia/formalization_queue.jsonl
  compile generated package
```

Idempotence requirement:

```text
same host sources + same projection policy -> byte-stable generated file,
source_map, and queue ids
```

## 12. Agent formalization workflow

Agent formalization is a second pass, not part of default compile.

Workflow:

1. Read `formalization_queue.jsonl`.
2. Read cited ARM/ARA source spans.
3. Classify evidence/warrant type.
4. Propose Gaia v0.5 action upgrade.
5. If confidence is high and policy allows agent writes, write to `gaia/formalization.py`.
6. Otherwise present choices to user.
7. Re-run compile/check.
8. Update source map and queue resolution records.

Agent must not:

- invent source anchors
- assign strong probabilities without policy/user acceptance
- turn all proof links into `infer(...)`
- turn all failures into `contradict(...)`
- delete programmatic scaffold records unless replacing them through `materialize(...)`

## 13. User choice points

After scaffold compile, UI/CLI should present:

```text
Generated Gaia scaffold package:
  claims: N
  observations: M
  unformalized dependencies: K
  candidate relations: R
  registry dependencies resolved: D

Next:
  [1] keep scaffold package
  [2] run agent formalization on open queue
  [3] interactively review queue
  [4] publish only after formalization queue is clean
```

The default is `[1] keep scaffold package`.

This keeps package creation cheap and reliable. Formalization becomes a deliberate quality step.

## 14. Registry compatibility

For ARM and ARA embedded packages, registry-facing artifacts are Gaia artifacts:

```text
.gaia/ir.json
.gaia/ir_hash
.gaia/manifests/exports.json
.gaia/manifests/premises.json
.gaia/manifests/holes.json
.gaia/manifests/bridges.json
.gaia/source_map.json
.gaia/package.toml
.gaia/lock.json
```

Host files are included as provenance/source material, not as canonical identity.

### 14.1 ARA scholarly refs vs Gaia package refs

ARA `related_work.md` entries are not automatically Gaia package references.

The projector must classify each related-work entry into one of four states:

```text
source_only      keep as scholarly provenance only
candidate_match  possible Gaia registry match; needs review
registry_match   exact Gaia package match; safe to add
new_package      user/agent decided this external work should become a Gaia package
```

Only `registry_match` may be converted automatically into `gaia pkg add`.

Example `source_map.json` record for an unresolved ARA external ref:

```json
{
  "source_id": "ARA:RW01",
  "source_path": "logic/related_work.md",
  "source_anchor": "RW01",
  "gaia_record_kind": "scholarly_reference",
  "projection_rule": "ara.related_work.v1",
  "related_work_type": "refutes",
  "external_ids": ["arXiv:1505.00387", "arXiv:1507.06228"],
  "registry_binding": {
    "state": "candidate_match",
    "candidates": []
  },
  "requires_review": true,
  "queue_id": "FQ0101"
}
```

Example resolved Gaia dependency:

```json
{
  "source_id": "ARA:RW03",
  "source_path": "logic/related_work.md",
  "source_anchor": "RW03",
  "gaia_record_kind": "registry_dependency",
  "projection_rule": "ara.related_work.registry_match.v1",
  "related_work_type": "imports",
  "registry_binding": {
    "state": "registry_match",
    "package": "batch-normalization-gaia",
    "version": "1.0.0",
    "resolved_git_sha": "abc123..."
  },
  "requires_review": false
}
```

Cross-package references must use Gaia package identity:

```json
{
  "package": "resnet-ara-gaia",
  "version": "0.1.0",
  "target_qid": "github:resnet_ara::knowledge::ara_c02",
  "target_interface_hash": "sha256:..."
}
```

ARM/ARA paths may be included only as source anchors:

```json
{
  "source_path": "logic/claims.md",
  "source_anchor": "C02"
}
```

## 15. Validation requirements

Minimum validation for scaffold package:

- Detect host kind successfully.
- Every generated Gaia record has a source map entry.
- Every source map entry points to an existing file/path.
- Generated labels are stable and unique.
- Generated package compiles.
- `gaia build check` passes.
- No unreviewed relation is emitted as `derive/infer/equal/contradict/exclusive`.
- Queue items have source refs and candidate actions.

Additional validation for formalized package:

- Every materialized action references a prior scaffold or source map entry.
- Every probability-bearing action has provenance.
- Every contradiction/equivalence/exclusivity action has explicit textual evidence.
- Every `gaia pkg add` dependency resolves to registry metadata.
- `bridges.json` records interface hashes for cross-package fills.

## 16. Minimal implementation plan

### Phase 0: Adapter package, no Gaia loader change

Implement a standalone projector that writes:

```text
.gaia/adapter/pyproject.toml
.gaia/adapter/src/<synthetic_import>/from_host.py
.gaia/source_map.json
.gaia/formalization_queue.jsonl
```

Then call existing v0.5 compile path on `.gaia/adapter/`.

This is enough to prove ARM/ARA -> Gaia package without modifying Gaia loader.

### Phase 1: Embedded resolver

Teach Gaia package discovery to accept:

```text
.gaia/package.toml
gaia/
```

and execute `gaia/*.py` through a synthetic module name.

### Phase 2: Formalization queue integration

Add CLI support:

```bash
gaia build compile . --formalize agent
gaia build compile . --formalize interactive
```

or expose it through `gaia inquiry review` if that is the preferred review surface.

### Phase 3: Registry publish

Allow `gaia pkg register .` to register embedded roots, uploading source map and host provenance alongside standard Gaia manifests.

## 17. Non-goals

- Do not make ARM/ARA depend on Gaia.
- Do not make Gaia understand every ARM/ARA file semantically.
- Do not make `gaia pkg add` mean host mounting.
- Do not require agent formalization before a scaffold package can compile.
- Do not silently turn narrative proof references into formal inference.
- Do not use host paths as cross-package semantic identity.

## 18. Summary

ARM and ARA can both support Gaia through the same minimal bridge:

```text
host artifact
  + deterministic projector
  + source_map
  + formalization_queue
  -> embedded Gaia scaffold package
  -> optional formalization
  -> registry-compatible Gaia package
```

The important design choice is to separate package creation from semantic commitment.

Programmatic projection should make a package immediately. Agent/user formalization should improve the package, not be required to create it.
