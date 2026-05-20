# CLI-authored Mendel — bayes + Variable observation + multi-file walkthrough

> **Companion to** [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md) and the hand-authored package at `src/mendel_v0_5/__init__.py`. This document shows how the Mendel single-factor cross example can be authored end-to-end through `gaia author <verb>`, `gaia bayes <verb>`, and `gaia pkg <verb>`, without hand-editing the Python source. It mirrors the galileo walkthrough at `examples/galileo-v0-5-gaia/CLI-AUTHORED.md` and exercises the harder of the two v0.5 example packages: `bayes` group + `Variable` + Variable-targeted `observe(..., value=...)` + multi-file (`priors.py`) + `--background` on every relation verb.

> **Reproduction semantics**: this walkthrough reproduces the IR (knowledge/strategy content + counts + types) of the hand-authored package, not the byte-text source. See the equivalence test under `tests/cli/mendel_demo/` for the asserted axes; a small set of source-text divergences (chiefly the single-`--label` discipline) is documented at end-of-doc and is intrinsic-by-design.

## What you get

A scripted sequence of cli invocations produces a separately-scaffolded
`mendel-v0-5-gaia` package that compiles to a `LocalCanonicalGraph` with:

- **3 notes** + **23 user-authored claims** + **17 auto-generated warrant claims** + **1 auto-bayes-implication helper claim** = **44 knowledge nodes** total — same counts as the hand-authored package.
- **9 derive strategies** — same count and structure.
- **7 structural operators** (1 `exclusive` + 3 `equal` + 3 `contradict`) — same count and structure.
- **6 register-prior records** in a sibling `priors.py` module — same layout as the hand-authored package.

The two packages are **content-equivalent at the IR-content-set level** for every user-authored Claim or note. The pytest fixture at `tests/cli/mendel_demo/test_equivalence.py` re-runs the cli sequence fresh and asserts these invariants on every PR-gate run using the multi-level equivalence helper (`tests/cli/_equivalence_levels.py`).

## Cli surface exercised end-to-end

Mendel touches every cli capability that galileo did not:

| Capability | Mendel statement |
| --- | --- |
| Multi-file (`--file priors.py`) | 6 `register_prior` calls in sibling `priors.py` |
| `pkg add-module` | scaffolding `priors.py` before authoring into it |
| `bayes` group | 2 `bayes.model` + 1 `bayes.compare` + 2 inline distribution literals (`Binomial`, `BetaBinomial`) |
| `author variable` | 2 `Variable(...)` declarations (`f2_total_count`, `f2_dominant_count`) |
| `author observe --value` | 1 Variable-targeted quantitative observation (`f2_count_observation`) |
| `--background` on relations | `exclusive`, every `observe`, every `derive`, every `equal`, every `contradict`, every `bayes.model`, `bayes.compare` |
| Inline-prose `derive --conclusion-prose` | every mendel `derive(...)` uses the inline-prose shape |
| Single-`--label` discipline (intrinsic) | every cli statement renders `label=` inside the call |
| Narrowed deprecation scan | hand-authored binding names like `competing_models` reused verbatim |

Mendel is therefore the empirical demonstration that the cli surface covers the full v0.5 engine. If anything that mendel reaches for is not directly cli-authorable, the capability claim has a hole; the equivalence test fails fast under that condition.

## Authoring sequence

The cli invocations below produce the cli-authored mirror. Each invocation is shown with its full flag set; in practice an agent scripts this from a JSON template. Output is JSON by default. `bayes model --distribution` takes the inline distribution expression directly — no pre-binding step.

### 1. Scaffold the package skeleton

```bash
gaia pkg scaffold \
    --target ./mendel-cli-mirror-gaia \
    --name mendel-v0-5-gaia \
    --namespace example
```

The `import_name` is derived from `--name` (strip `-gaia`,
hyphen→underscore: `mendel-v0-5-gaia` → `mendel_v0_5`); the cli does
not accept a separate `--import-name` override.

The scaffold writes:

- `pyproject.toml` with `[tool.gaia] type = "knowledge-package"` and `namespace = "example"` (no `uuid` by default; `--with-uuid` opts in).
- `src/mendel_v0_5/__init__.py` importing the full author-surface DSL (`bayes`, `Variable`, `Constant`, `Nat`, `equals`, `land`, ...) plus a placeholder `hypothesis = claim(...)` so the file is loadable immediately.
- `.gaia/.gitkeep`.

The placeholder `hypothesis` statement is not part of the Mendel example — strip it before authoring the real statements:

```bash
python -c "
import pathlib
p = pathlib.Path('mendel-cli-mirror-gaia/src/mendel_v0_5/__init__.py')
src = p.read_text()
end = src.find('hypothesis = claim(')
if end > 0:
    p.write_text(src[:end].rstrip() + '\n')
"
```

(The test fixture does the same edit.)

### 2. Declare the two `Variable(...)` typed terms

The Mendel package uses Variables for the F2 counts that feed the `Binomial(name, n=..., p=3/4)` observable and the quantitative observation. The cli renders `Variable(symbol=..., domain=..., value=...)` exactly:

```bash
gaia author variable \
  --label f2_total_count --symbol n_f2 --domain Nat --value 395 \
  --target ./mendel-cli-mirror-gaia

gaia author variable \
  --label f2_dominant_count --symbol k_dominant --domain Nat --value 295 \
  --target ./mendel-cli-mirror-gaia
```

`--value` accepts a literal expression (as shown) or a bare Python
identifier resolved against the package's module scope. The walkthrough
keeps literal values for readability; an agent mirroring the
hand-authored shape (which imports `TOTAL_COUNT` / `DOMINANT_COUNT`
from a sibling `probabilities.py`) can opt into the identifier path by
first scaffolding `probabilities.py` and then passing
`--value TOTAL_COUNT`. The cli forwards the identifier verbatim into
the rendered `value=` slot AND pushes it through pre-write reference
resolution. Numerically identical at the IR level either way.

### 3. Author the three contextual notes

```bash
gaia author note \
  "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。" \
  --label monohybrid_cross_setup \
  --target ./mendel-cli-mirror-gaia

gaia author note \
  "在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。" \
  --label dominance_background \
  --target ./mendel-cli-mirror-gaia

gaia author note \
  "F2 的显性/隐性计数是有限样本，因此用点似然（二项 PMF 在观测计数处的取值）衡量模型与数据的贴合度；对手理论取 p ~ Uniform[0,1] 的 diffuse 先验作为参考尺度，不引入任何具体的替代二项参数。" \
  --label finite_sample_background \
  --target ./mendel-cli-mirror-gaia
```

The prewrite deprecation scan is narrowed to call positions, so binding
names like `dominance_background` reuse the hand-authored spelling
verbatim.

### 4. Author the two competing model claims + the `exclusive` operator

```bash
gaia author claim \
  "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。" \
  --label mendelian_segregation_model \
  --target ./mendel-cli-mirror-gaia

gaia author claim \
  "混合遗传模型：亲本性状在后代中连续平均；一旦平均，离散的显性/隐性类别就不应在 F2 中作为可计数的类型存在。" \
  --label blending_inheritance_model \
  --target ./mendel-cli-mirror-gaia

gaia author exclusive \
  --a mendelian_segregation_model --b blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。" \
  --label competing_models \
  --target ./mendel-cli-mirror-gaia
```

### 5. Author the observations

The first three are qualitative prose observations. The fourth records the
quantitative F2 dominant-count measurement directly on the `Variable` that the
Bayes models use as their observable.

```bash
gaia author observe \
  --observation-prose "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F1 代的定性观察。" \
  --label f1_uniform_dominant_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --observation-prose "F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察：表型呈两类，不是连续分布。" \
  --label f2_has_discrete_classes_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --observation-prose "F1 自交得到的 F2 后代中，原隐性表型作为离散类别重新出现。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察。" \
  --label f2_recessive_reappears_observation \
  --target ./mendel-cli-mirror-gaia

gaia author observe \
  --conclusion f2_dominant_count \
  --value 295 \
  --background monohybrid_cross_setup,f2_has_discrete_classes_observation \
  --rationale "这是用于贝叶斯点似然比较的 F2 显性/隐性计数数据。" \
  --label f2_count_observation \
  --target ./mendel-cli-mirror-gaia
```

`gaia author observe --value` renders `observe(f2_dominant_count,
value=295, ...)`, which carries the `metadata["observation"]` payload that
`bayes.compare(...)` needs for likelihood evaluation.

### 6. Author the five Mendel qualitative derivations + three matches

Each `derive` uses **inline-prose** (`--conclusion-prose`), matching the hand-authored shape byte-for-byte at the conclusion-claim slot.

```bash
gaia author derive \
  --conclusion-prose "如果孟德尔分离模型成立，纯种显性亲本与纯种隐性亲本杂交后，F1 后代都应携带一个显性因子和一个隐性因子，并表现显性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "显性因子在杂合 F1 个体中遮蔽隐性因子。" \
  --label mendel_predicts_f1_dominance \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_f1_dominance --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F1 统一显性的预测与观察相符。" \
  --label f1_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "孟德尔分离模型下 F2 的基因型组合为 AA:Aa:aa = 1:2:1，显性因子遮蔽效应把这三个基因型映射到显性和隐性两个离散表型类别，因此 F2 应呈现清晰的两类离散表型而非连续谱。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "离散因子 + 遮蔽 → 两个离散表型类别。" \
  --label mendel_predicts_discrete_classes \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_discrete_classes --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。" \
  --label f2_discrete_classes_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果 F1 个体仍携带被遮蔽的隐性因子，那么 F1 自交后，部分 F2 个体会继承两个隐性因子并重新表现隐性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "分离模型保留了隐性因子，并允许它在 F2 中重新组合为纯合隐性。" \
  --label mendel_predicts_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia

gaia author equal \
  --a mendel_predicts_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F2 隐性重现的预测与观察相符。" \
  --label f2_reappearance_mendel_match \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果 F1 个体自交，成对因子分离会给出 AA:Aa:aa = 1:2:1 的基因型比例；由于 AA 和 Aa 都表现显性，F2 显性/隐性计数应服从 Binomial(N, 3/4)，期望表型比约为 3:1。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "F1 配子等概率结合，给出 1:2:1 的基因型分布，即每个 F2 个体独立以概率 3/4 表现为显性。" \
  --label mendel_predicts_three_to_one_ratio \
  --target ./mendel-cli-mirror-gaia
```

### 7. Author the quantitative bayes comparison

`bayes model --distribution` accepts an inline Distribution expression
(validated through the formula sandbox, which whitelists bare
`gaia.engine.lang` Distribution factories). The cli mirror inlines
`Binomial(...)` / `BetaBinomial(...)` directly inside
`bayes.model(distribution=...)`, byte-matching the hand-authored shape
— no helper `mendel_count_distribution` / `diffuse_count_distribution`
pre-binding step. Bare-identifier `--distribution <ident>` still works
when an author *does* want a separately-bound Distribution helper.

```bash
gaia bayes model \
  --hypothesis mendelian_segregation_model \
  --observable f2_dominant_count \
  --distribution 'Binomial("F2 dominant count under Mendel 3:1", n=395, p=3/4)' \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "孟德尔分离模型给出 F2 每个个体以概率 3/4 表现显性的生成模型，因此显性计数服从 Binomial(N, 3/4)。" \
  --label mendel_count_model \
  --target ./mendel-cli-mirror-gaia

gaia bayes model \
  --hypothesis blending_inheritance_model \
  --observable f2_dominant_count \
  --distribution 'BetaBinomial("F2 dominant count under p ~ Uniform[0, 1]", n=395, alpha=1.0, beta=1.0)' \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "把对照项写成 p ~ Uniform[0, 1] 下的 BetaBinomial(N, 1, 1) 预测分布；它给出任意具体计数的边际概率 1 / (N + 1)，不人为指定第二个二项参数。" \
  --label diffuse_count_model \
  --target ./mendel-cli-mirror-gaia

gaia bayes compare \
  --data f2_count_observation \
  --model mendel_count_model \
  --against diffuse_count_model \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "直接比较观测到的 F2 显性计数在 Mendel 点模型和 diffuse 参考模型下的 log likelihood；观测可靠性仍留在 f2_count_observation 的 prior 中。" \
  --label mendel_count_likelihood \
  --target ./mendel-cli-mirror-gaia
```

### 8. Author the three Blending derivations + three contradictions

```bash
gaia author derive \
  --conclusion-prose "如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均模型把亲本性状视为在后代中均化。" \
  --label blending_predicts_intermediate_f1 \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_intermediate_f1 --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "F1 统一显性与混合模型的中间表型预测相冲突。" \
  --label f1_blending_conflict \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "如果亲本性状在 F1 中连续平均，F2 应形成单峰连续分布，不能被划分为清晰的显性/隐性两个离散类别。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均不保留可重新组合的离散遗传单位，因此不给出离散的表型分类。" \
  --label blending_predicts_f2_continuous \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_f2_continuous --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 明确划分为两类离散表型，与混合模型的连续分布预测相冲突——这是 framework 级别的冲突：blending 否认的是 F2 可被分类这件事本身。" \
  --label f2_discrete_classes_blending_conflict \
  --target ./mendel-cli-mirror-gaia

gaia author derive \
  --conclusion-prose "连续平均的性状不保留可以重新组合的离散遗传单位，因此原隐性表型不应作为离散类别在 F2 中重新出现。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "混合模型没有保留可重新组合的离散隐性因子。" \
  --label blending_predicts_no_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia

gaia author contradict \
  --a blending_predicts_no_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 隐性表型作为离散类别重新出现，与混合模型的预测相冲突。" \
  --label f2_reappearance_blending_conflict \
  --target ./mendel-cli-mirror-gaia
```

### 9. Scaffold `priors.py` and register the six priors

```bash
gaia pkg add-module --name priors --imports register_prior \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim mendelian_segregation_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim blending_inheritance_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f1_uniform_dominant_observation --value 0.95 \
  --justification "把 F1 统一显性作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_has_discrete_classes_observation --value 0.95 \
  --justification "把 F2 呈两类离散表型作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_recessive_reappears_observation --value 0.95 \
  --justification "把 F2 隐性表型重新出现作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim f2_count_observation --value 0.95 \
  --justification "把 F2 显性/隐性计数作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia
```

The writer auto-inserts `from mendel_v0_5 import <claim>` for each newly referenced binding in `priors.py`, so the resulting file imports the same six claims that the hand-authored `priors.py` does. Because `--source-id` is omitted, the rendered calls also omit the `source_id=` kwarg — the engine default applies at load time, byte-matching the hand-authored `priors.py`.

**Numeric divergence** — the hand-authored
`register_prior(blending_inheritance_model, value=1.0 - PRIOR_MENDELIAN_MODEL, ...)`
references the `PRIOR_MENDELIAN_MODEL` constant from
`mendel_v0_5.probabilities`. The cli forwards `--value 0.5` verbatim.
Numerically identical; structurally a constant-reference vs literal-value
choice. See the divergence table at end-of-doc.

## Compile + check

```bash
cd mendel-cli-mirror-gaia
gaia build compile
# → Compiled 44 knowledge, 9 strategies, 7 operators
gaia build check
```

The counts match the hand-authored package compile (`44 / 9 / 7`).

## Documented divergences

All remaining divergences are either ratified intrinsic to the
single-`--label` discipline, or a non-semantic source-text difference
between literal-value and imported-constant authoring (both compile to
the same IR; the equivalence tests pass byte-text on every axis other
than the single-`--label` discipline).

### 1. LHS binding equals `label=` kwarg (intrinsic)

Same as the galileo intrinsic divergence. The cli enforces
`label_name = verb(..., label="label_name")` — the LHS Python binding
and the DSL `label=` kwarg are forced equal because the cli's single
`--label` flag drives both.

The current Mendel package no longer needs a post-binding label mutation for
the F2-count data. The CLI-authored source emits the same Variable-targeted
observation shape as the hand-authored package.

### 2. `Variable(value=<literal>)` vs `value=<imported-constant>` (numeric-equivalent)

The hand-authored Mendel file imports `TOTAL_COUNT` / `DOMINANT_COUNT`
from `mendel_v0_5.probabilities` and passes them through to
`Variable(value=TOTAL_COUNT)`. The cli's bare-identifier `--value`
support means `gaia author variable --value DOMINANT_COUNT` resolves
the identifier against module scope and emits it verbatim into the
rendered `value=` slot. The walkthrough still passes literal values for
self-containment; an agent that scaffolds `probabilities.py` first can
hit byte-text equivalence via the identifier path. Numerically
identical at the IR level either way.

### 3. `register_prior(value=<imported-constant>)` vs `value=<literal>` (numeric-equivalent)

Same root cause as §2. Bare-identifier `--value` resolution applies
equally to `register-prior --value`. The walkthrough's `priors.py`
step still passes literal values for self-containment; an agent that
scaffolds `probabilities.py` and imports `PRIOR_MENDELIAN_MODEL` first
can hit byte-text equivalence here too. Numerically identical.

### 4. Scaffold `__init__.py` carries full import block (intrinsic)

`gaia pkg scaffold` writes a `__init__.py` that imports the full
author-surface DSL (`bayes`, `Variable`, `Constant`, every primitive
Domain, every formula primitive, every relation verb) so subsequent
`gaia author <verb>` calls don't trip the postwrite `NameError` from
missing imports. The hand-authored Mendel `__init__.py` imports only
the names it actually uses (about 12 of the ~25 scaffold imports).
Source-text difference only; the IR doesn't care which imports the
module file declares. Pass `--minimal-imports` to opt into a
power-user-mode seed that only imports `claim`; the author then
manages imports manually.

## Equivalence guarantees

The pytest fixture at `tests/cli/mendel_demo/test_equivalence.py` runs the full cli sequence above against a fresh temp directory and asserts equivalence via the multi-level helper (`tests/cli/_equivalence_levels.py`):

| Axis | Tolerance | Why |
| --- | --- | --- |
| `user-authored-contents` | BYTE_TEXT | Every user-authored Claim or note content must appear byte-identical in both IRs. |
| `note-types-multiset` | BYTE_TEXT | The 3 notes have byte-identical contents on both sides. |
| `strategy-count` | BYTE_TEXT | 9 derives on both sides. |
| `operator-count` | BYTE_TEXT | 7 operators on both sides. |
| `total-knowledge-count` | BYTE_TEXT | 44 knowledge nodes on both sides. |
| `knowledge-type-multiset` | BYTE_TEXT | `{note: 3, claim: 41}` on both sides. |
| `label-bag` | CONTENT_SET | Single-`--label` discipline forces every cli statement to render `label=`; some hand-authored statements omit it when binding name == label. Set is identical; multiset differs by the `label=` rendering choice. |
| `bayes-model-count` | BYTE_TEXT | 2 `bayes.model` calls + 1 `bayes.compare` call on both sides. |
| `register-prior-count` | BYTE_TEXT | 6 `register_prior` calls in `priors.py` on both sides. |
| `source-id-count` | BYTE_TEXT | `register_prior` calls render zero `source_id=` mentions on both sides — the cli omits the kwarg when `--source-id` is not explicitly passed. |
| `variable-observation` | structural assertion | The F2-count data line uses `observe(f2_dominant_count, value=295, ...)`, producing the observation metadata required by Bayes compare. |
| `bayes-inline-distribution` | structural assertion | `bayes.model(...)` calls inline `Binomial(...)` / `BetaBinomial(...)` directly — no pre-bound `mendel_count_distribution` / `diffuse_count_distribution` helper bindings. |

The multi-level helper at `tests/cli/_equivalence_levels.py` underwrites both this mendel demo and the galileo demo's equivalence (galileo applies BYTE_TEXT on the resolvable axes, CONTENT_SET on the intrinsic single-`--label` axis; mendel adds the bayes / Variable-observation / multi-file axes on top).

## See also

- Hand-authored ground truth: [`src/mendel_v0_5/__init__.py`](src/mendel_v0_5/__init__.py)
- Hand-authored priors: [`src/mendel_v0_5/priors.py`](src/mendel_v0_5/priors.py)
- Equivalence test: [`tests/cli/mendel_demo/test_equivalence.py`](../../tests/cli/mendel_demo/test_equivalence.py)
- Multi-level tolerance helper: [`tests/cli/_equivalence_levels.py`](../../tests/cli/_equivalence_levels.py)
- Sibling galileo walkthrough: [`examples/galileo-v0-5-gaia/CLI-AUTHORED.md`](../galileo-v0-5-gaia/CLI-AUTHORED.md)
- Full cli reference: [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md)
