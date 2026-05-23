# References / Citations / Artifacts 收敛设计

> **Status:** Target design
> **Date:** 2026-05-23
> **Scope:** Gaia Lang DSL + compiler/checker + renderer + CLI authoring + user docs + skill contracts
> **Depends on:** [2026-04-09-references-and-at-syntax.md](2026-04-09-references-and-at-syntax.md), [2026-04-02-gaia-lang-v5-python-dsl-design.md](2026-04-02-gaia-lang-v5-python-dsl-design.md), [2026-04-04-compile-readme-design.md](2026-04-04-compile-readme-design.md)

## 0. 摘要

一句话：**不改 `@` / `[@key]` 核心语法；把 citation、knowledge reference、
figure、table、dataset、attachment 收敛成三层模型，并把 artifact 表达为
`NOTE + metadata`，而不是新的 `KnowledgeType`。**

PR 694 之前的设计已经正确指出：Gaia 现有引用表达散在 `refs`、`source_refs`、
`source_paper`、`metadata.figure`、body marker 和 compiler-generated provenance
之间，其中只有 body marker 会被编译器可靠解析和校验。但旧设计仍把 figure 往
独立 DSL / IR 类型方向推，容易把一个本质上是“包内可引用附件锚点”的东西过度建模。

本 spec 的收敛目标是：

1. **外部来源**只由 `references.json` 和 body 内 `[@CitationKey]` 表达。
2. **包内知识引用**只由 Gaia label / module binding 和 body 内 `[@local_label]` 表达。
3. **图表与附件引用**只由 `note(...)` 加 `metadata["gaia"]["artifact"]` 表达，并用
   `[@artifact_label]` 或 `background=[artifact_note]` 引用。

`figure()` 和 `artifact()` 可以存在，但它们是 authoring sugar：它们创建的仍然是
`KnowledgeType.NOTE`，不会新增 `KnowledgeType.ARTIFACT`，也不会新增 `Artifact`
subclass。

## 1. 现状核查

### 1.1 核心 `@` / `[@key]` 语法已经实现

2026-04-09 spec 头部仍标注为 target design，但源码核查显示核心链路已经落地：

| 能力 | 位置 | 状态 |
|---|---|---|
| Marker 提取 | `gaia/engine/lang/refs/extractor.py` | 已实现：裸 `@key`、strict `[@key]`、bracket group |
| 三态 resolve | `gaia/engine/lang/refs/resolver.py` | 已实现：citation / local knowledge / unresolved |
| `references.json` loader | `gaia/engine/lang/refs/loader.py` | 已实现：CSL-JSON schema、key grammar、CSL type 白名单 |
| 编译器接入 | `gaia/engine/lang/compiler/compile.py` | 已实现：扫描 content / reason / rationale，并写入 `metadata["gaia"]["provenance"]` |

因此本 spec 不重写核心语法。`@` / `[@key]`、strict miss 报错、opportunistic miss
保持字面量、label/citation key collision fail-fast、homogeneous bracket group 校验，
这些行为全部保留。

### 1.2 真正的问题在核心语法外围

现有“引用 / 来源 / provenance”机制至少有六条平行路径：

| 机制 | 写入位置 | 当前问题 |
|---|---|---|
| body 内 `[@key]` / `@key` | claim / note / strategy reason / action rationale 文本 | 已校验，是应保留的 canonical 路径 |
| `metadata["gaia"]["provenance"]` | 编译器派生 | 应继续作为派生产物，作者不应手写 |
| `refs` typed metadata | skill 契约和自由 `**metadata` | 编译器不读、不校验；非法 type 或缺字段会静默通过 |
| `observe(source_refs=[...])` | action metadata | 自由字符串，不 resolve `references.json` |
| `source_paper` | 自由 `**metadata` | 无消费者、无校验，容易被误当 canonical source |
| `metadata={"figure": ..., "caption": ...}` | 自由 metadata | 与 `refs.figure` 重叠，renderer 目前也没有统一消费 |

结果是同一件事会被表达三遍。例如一个 claim 可能同时写
`source_paper="Liu2015"`、`refs=({"type": "citation", "key": "Liu2015"},)`，
又在正文里写 `[@Liu2015]`。三者没有一致性检查，也没有单一真源。

### 1.3 `figure` 不是一个需要升格为 Knowledge 类型的概念

figure/table/dataset/attachment 的共性不是“新的科学知识类型”，而是：

- 它们需要一个 Gaia 本地 anchor，供 claim / note / rendered document 引用；
- 它们可能绑定一个外部 source 和 source-local locator，例如 `Liu2015` 的 `Fig. 3`；
- 它们可能绑定一个 package-local file path，例如 `artifacts/figures/liu2015_fig3.png`；
- 它们需要 caption / description 供 renderer 展示。

这些属性完全可以由 `note(...)` 的内容和 metadata 表达。新增 `KnowledgeType.ARTIFACT`
或 `ArtifactNote` subclass 会把 renderer/authoring 需要的结构推到 IR taxonomy 层，
牵动 package loading、label collection、export、compiler lowering、rendering 和
backward compatibility。当前没有必要。

## 2. 设计原则

1. **核心语法冻结。** 不改 `@` / `[@key]`、`references.json`、strict/opportunistic
   语义和 collision 规则。
2. **三层分离。** External source、local knowledge ref、package artifact anchor
   是三种不同对象，不能互相冒充。
3. **Artifact-as-note。** 图表和附件是 `KnowledgeType.NOTE`，由保留的
   `metadata["gaia"]["artifact"]` 标记；不新增 `KnowledgeType` 或 subclass。
4. **作者只写一次。** Citation 写在正文 marker；artifact source 写在 artifact note；
   compiler provenance 和 renderer output 都从这些 canonical 表达派生。
5. **可校验才叫契约。** 旧 `refs` 的问题是“像契约但无人执行”。新的 artifact schema
   必须由 compiler/checker 执行。
6. **最小 CLI。** CLI v1 负责生成和校验 artifact note，不负责复制文件、算 hash、
   建 asset registry 或做内容寻址。

## 3. 目标模型

收敛后只有三种 canonical 引用表达：

| 引用种类 | Canonical source | 编译器 / checker 责任 | 派生产物 |
|---|---|---|---|
| External citation | body 内 `[@CitationKey]`，key 来自 `references.json` | 已实现：extract / resolve / strict miss / collision / group validation | `metadata["gaia"]["provenance"].cited_refs`、rendered References |
| Local knowledge reference | body 内 `[@local_label]`，label 来自 package closure 中的 knowledge label | 已实现：label table resolve、collision、strict miss | `metadata["gaia"]["provenance"].referenced_claims`、rendered anchor link |
| Artifact / attachment reference | `artifact_label = note(..., metadata={"gaia": {"artifact": ...}})`，再用 `[@artifact_label]` 引用 | 新增：artifact schema、source/path/locator 校验 | rendered figure/table/link、artifact provenance |

关键不变量：

- Artifact 的 Gaia label 来自 module binding / existing label mechanism，例如
  `liu2015_fig3 = note(...)`。不要在 artifact metadata 里再放一个 `label` 字段。
- 论文内编号使用 `locator`，例如 `"Fig. 3"`、`"Table 2"`、
  `"Supplementary Data 1"`。`locator` 不是 Gaia label。
- Claim 引用 artifact 时引用的是包内 note anchor：`See [@liu2015_fig3].`
- Claim 是否直接引用外部文献，只由 claim 文本里的 `[@Liu2015]` 决定；artifact 的
  `source` 是 artifact 自己的 provenance，不隐式伪装成 claim 的 direct citation。

## 4. Artifact Note Schema

Canonical 存储形式是 `note(...) + metadata["gaia"]["artifact"]`：

```python
liu2015_fig3 = note(
    "Fibonacci scaling of the order parameter in the source paper.",
    metadata={
        "gaia": {
            "artifact": {
                "kind": "figure",
                "source": "Liu2015",
                "locator": "Fig. 3",
                "path": "artifacts/figures/liu2015_fig3.png",
                "caption": "Fibonacci scaling of the order parameter.",
            }
        }
    },
)
```

### 4.1 Required and optional fields

| Field | Required | Meaning | Validation |
|---|---:|---|---|
| `kind` | yes | Controlled artifact kind | Must be one of `figure`, `table`, `dataset`, `notebook`, `attachment` |
| `source` | no | Citation key in `references.json` for source-bound artifact | If present, must resolve to `references.json` |
| `locator` | no | Source-local locator, not Gaia label | Recommended when `source` is present; required for source-bound `figure` and `table` |
| `path` | no | Package-local file path | If present, must be relative, must not escape package root, and should exist during check |
| `caption` | no | Human caption for figure/table rendering | String |
| `description` | no | Human description for non-visual attachments | String |
| `media_type` | no | Optional MIME hint when extension is insufficient | String |

At least one of `source` or `path` must be present. This allows two important cases:

- Source-bound figure without local image: `source="Liu2015", locator="Fig. 3"`.
- Generated/local attachment without bibliographic source:
  `path="artifacts/data/simulation-results.parquet"`.

The schema intentionally does not include arbitrary URL fields. If an artifact points to an external
web resource, that resource should be a `references.json` entry and the artifact should use
`source=<key>`. If the package includes a local copy, use `path`.

### 4.2 `figure()` and `artifact()` helpers

The helper functions are authoring sugar only:

```python
liu2015_fig3 = figure(
    source="Liu2015",
    locator="Fig. 3",
    path="artifacts/figures/liu2015_fig3.png",
    caption="Fibonacci scaling of the order parameter.",
)
```

is equivalent to:

```python
liu2015_fig3 = artifact(
    kind="figure",
    source="Liu2015",
    locator="Fig. 3",
    path="artifacts/figures/liu2015_fig3.png",
    caption="Fibonacci scaling of the order parameter.",
)
```

and both lower to a normal `note(...)` with artifact metadata. The helper must return a `Knowledge`
whose `type` is `KnowledgeType.NOTE`; it must not create a new IR class.

The direct `note(..., metadata=...)` form remains valid and is the storage-level canonical form.
Helpers exist to reduce boilerplate and to let the CLI emit readable source.

### 4.3 Provenance behavior

Artifact provenance is deliberately not flattened into every claim that references the artifact.

- The artifact note validates and owns its `source`.
- A claim that says `See [@liu2015_fig3]` records `liu2015_fig3` under
  `referenced_claims` / local knowledge refs.
- The same claim records `Liu2015` under `cited_refs` only if the claim text also says
  `[@Liu2015]`.
- Renderers may include bibliography entries for artifact sources when the artifact block is rendered,
  but they should not pretend the parent claim directly cited a source it only reached transitively
  through an artifact.

This avoids double counting and keeps direct textual citation separate from artifact provenance.

## 5. Before / After

### 5.1 Citation

Before:

```python
liu2015_c1 = claim(
    r"The system exhibits Fibonacci-scaling emergence (see Fig. 3).",
    source_paper="Liu2015",
    refs=(
        {"type": "citation", "key": "Liu2015"},
        {"type": "figure", "id": "Fig. 3"},
        {"type": "equation", "id": "Eq. (5)"},
    ),
)
```

Problems: citation duplicated, figure locator has no source binding, equation pointer does not carry
content, and `refs` is not compiler-validated.

After:

```python
liu2015_fig3 = figure(
    source="Liu2015",
    locator="Fig. 3",
    path="artifacts/figures/liu2015_fig3.png",
    caption="Fibonacci scaling of the order parameter.",
)

liu2015_c1 = claim(
    r"The system exhibits Fibonacci-scaling emergence [@Liu2015]. "
    r"See [@liu2015_fig3].",
    background=[liu2015_fig3],
)
```

The citation is written once, the figure is a source-bound artifact note, and the local reference uses
the existing label mechanism.

### 5.2 Attachment

Before, there was no first-class place for package attachments other than ad hoc metadata:

```python
analysis_note = note(
    "The raw digitized points are in the supplemental spreadsheet.",
    metadata={"file": "supplement.xlsx", "source_paper": "Liu2015"},
)
```

After:

```python
liu2015_supplement = artifact(
    kind="attachment",
    source="Liu2015",
    locator="Supplementary Data 1",
    path="artifacts/attachments/liu2015_supplement.xlsx",
    description="Digitized source data used for the pressure-temperature curve.",
)

analysis_note = note(
    "The digitized source data are available as [@liu2015_supplement]."
)
```

This handles the “附件引用” case without adding an `Attachment` knowledge type.

### 5.3 Observation source

Before:

```python
measured_tc = observe(
    T_c,
    value=q(203, "K"),
    error=q(5, "K"),
    source_refs=["Drozdov 2015"],
)
```

After:

```python
measured_tc = observe(
    T_c,
    value=q(203, "K"),
    error=q(5, "K"),
    rationale="Reported superconducting transition temperature [@Drozdov2015].",
)
```

`rationale` is already scanned by the reference scanner, so the citation is resolved and recorded
through the same path as other citations.

## 6. CLI Design

The CLI should expose the artifact model directly because users should not have to hand-author nested
metadata for common cases.

### 6.1 `gaia author artifact`

General command:

```bash
gaia author artifact \
  --dsl-binding-name liu2015_supplement \
  --kind attachment \
  --source Liu2015 \
  --locator "Supplementary Data 1" \
  --path artifacts/attachments/liu2015_supplement.xlsx \
  --description "Digitized source data used for the pressure-temperature curve." \
  --target .
```

Behavior:

- Creates or updates a package module with a module-level binding named by `--dsl-binding-name`.
- Emits `artifact(...)` if the helper is available; otherwise emits equivalent `note(..., metadata=...)`.
- Does not copy files in v1. The user supplies a package-relative path to an existing or planned file.
- Defaults to not exporting the artifact. Export remains opt-in via the existing package export
  mechanism because most artifacts are support anchors, not public claims.
- Performs local validation for obvious issues: invalid kind, absolute path, `..` path escape, missing
  `source` key when `--source` is provided and `references.json` is available.

### 6.2 `gaia author figure`

Figure-specific sugar:

```bash
gaia author figure \
  --dsl-binding-name liu2015_fig3 \
  --source Liu2015 \
  --locator "Fig. 3" \
  --path artifacts/figures/liu2015_fig3.png \
  --caption "Fibonacci scaling of the order parameter." \
  --target .
```

This is exactly `gaia author artifact --kind figure` with better option names and help text.

### 6.3 What the CLI should not do in v1

Do not add a file registry, content hash store, asset copy command, DOI lookup, remote download, or
artifact import pipeline in this PR. Those can be added later if real workflows need them. The first
complete contract is: generate the anchor, validate the metadata, and let renderers consume it.

## 7. Compiler / Checker / Renderer Responsibilities

### 7.1 Compiler and checker

The compiler/check path should validate artifact notes wherever it already has enough context:

- `kind` is in the controlled set.
- At least one of `source` or `path` is present.
- If `source` is present, it resolves to `references.json`.
- If `source` and a source-bound visual kind are present, `locator` is required for `figure` and
  `table`.
- If `path` is present, it is package-relative and cannot escape the package root.
- Package check should warn or fail when `path` does not exist, depending on the command's strictness.
- Artifact notes are valid local knowledge targets, so `[@artifact_label]` should resolve through the
  existing label table.

Deprecated legacy fields should be handled explicitly:

- `refs`: warn in the transition release, then error in the next major release.
- `source_refs`: deprecate `observe(source_refs=...)`; use rationale `[@key]`.
- `source_paper`: warn that it is audit-only and ignored by compiler provenance. If users need to
  keep it, move it under an explicit audit namespace such as `metadata["gaia"]["audit"]`.
- `metadata.figure` / top-level `caption`: warn and point to artifact note schema.

The compiler must never treat these legacy fields as canonical citation data.

### 7.2 Renderer

Renderer behavior should follow the same three-layer split:

- `cited_refs` renders bibliographic citations and a References section.
- `referenced_claims` renders links to local knowledge anchors.
- Artifact notes render as figure/table blocks or attachment links based on `kind` and `path`.

For artifact notes:

- `figure` with an image path renders an image block plus caption/source/locator.
- `table` with a renderable path may render inline later; v1 may link the file if no table renderer
  exists.
- `dataset`, `notebook`, and `attachment` render as file links with description/source/locator.
- If an artifact has `source`, the rendered artifact block should expose source and locator, and the
  page-level bibliography may include that source.

## 8. Migration

| Old form | New form | Compatibility policy |
|---|---|---|
| `refs=({"type": "citation", ...},)` | Body `[@CitationKey]` | Warn in transition release, then error |
| `refs=({"type": "figure", "id": "Fig. 3"},)` | `figure(source=..., locator="Fig. 3", ...)` plus `[@artifact_label]` | Warn in transition release, then error |
| `refs=({"type": "equation", ...},)` | Inline the equation or result in claim content | Warn in transition release, then error |
| `observe(source_refs=[...])` | `observe(..., rationale="... [@CitationKey]")` | Deprecate parameter |
| `source_paper="Liu2015"` | Body `[@Liu2015]` or artifact `source="Liu2015"` | Audit-only; ignored by compiler provenance |
| `metadata={"figure": ..., "caption": ...}` | Artifact note with `kind="figure"` | Warn and migrate |

Skill and docs migration must update repo-bundled sources, not only local user mirrors:

- `gaia/_skills/gaia-formalize-coarse/...` examples that emit `refs`.
- `gaia/_skills/gaia-formalize-fine/...` examples that emit `metadata={"figure": ...}`.
- `docs/for-users/language-reference.md` examples that still recommend `source_refs`.
- Any `docs/foundations/gaia-lang/...` examples that use old `source_refs`.

## 9. Implementation Checklist

### PR 1: Spec, DSL helper, validation, CLI authoring

- [ ] Add artifact metadata schema helper or validator near the existing DSL/compiler boundary.
- [ ] Add `artifact(...)` and `figure(...)` helpers that return `KnowledgeType.NOTE`.
- [ ] Export the helpers through the same public DSL surface as `note(...)`.
- [ ] Validate artifact metadata during package compile/check.
- [ ] Deprecate `observe(source_refs=...)` and document rationale-based citations.
- [ ] Warn on legacy `refs`, `source_paper`, and `metadata.figure` forms.
- [ ] Add `gaia author artifact`.
- [ ] Add `gaia author figure` as sugar for `--kind figure`.
- [ ] Update repo-bundled Gaia skills and user docs.
- [ ] Add tests for helper output, schema validation, source resolution, unsafe paths, CLI emission,
      and local `[@artifact_label]` resolution.

### PR 2: Renderer consumption

- [ ] Render `cited_refs` into citations and References sections.
- [ ] Render `referenced_claims` as local anchor links.
- [ ] Render artifact notes as image/table/link blocks according to `kind`.
- [ ] Include artifact source/locator in rendered artifact blocks.
- [ ] Add renderer tests with one source-bound figure and one package-local attachment.

PR 2 may require citeproc/style dependencies; PR 1 does not.

## 10. Non-Goals

- Do not redesign `@` / `[@key]`.
- Do not add `KnowledgeType.ARTIFACT`.
- Do not add an `Artifact` or `ArtifactNote` subclass.
- Do not create separate `FigureKnowledge`, `DatasetKnowledge`, or attachment subtypes.
- Do not build file copying, hashing, DOI lookup, or remote import in v1.
- Do not make `source_paper` a canonical citation source.
- Do not change `claim(provenance=[PackageRef])`; it remains package/version provenance, not
  bibliographic citation.

## 11. Open Extension Points

The design leaves room for future work without committing to it now:

- Artifact hashes can be added under `metadata["gaia"]["artifact"]["digest"]` once packages need
  reproducible binary attachment verification.
- Additional `kind` values can be added when renderer behavior differs materially.
- A future `gaia artifact add` command can copy files into package-managed directories if repeated
  user workflows justify it.
- Cross-package artifact references should reuse the future cross-package knowledge-ref design rather
  than inventing a special artifact namespace.
