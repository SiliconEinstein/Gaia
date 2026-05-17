# CLI-authored Mendel — bayes + formula-claim + multi-file walkthrough

> **Companion to** [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md) and the hand-authored package at `src/mendel_v0_5/__init__.py`. This document shows how the Mendel single-factor cross example can be authored end-to-end through `gaia author <verb>`, `gaia bayes <verb>`, and `gaia pkg <verb>`, without hand-editing the Python source. It mirrors the galileo walkthrough at `examples/galileo-v0-5-gaia/CLI-AUTHORED.md` and exercises the harder of the two v0.5 example packages — the surface that R7 actually unlocked: `bayes` group + `Variable` + `claim --formula` + multi-file (`priors.py`) + `--background` on every relation verb.

## What you get

A scripted sequence of cli invocations produces a separately-scaffolded
`mendel-v0-5-gaia` package that compiles to a `LocalCanonicalGraph` with:

- **3 notes** + **23 user-authored claims** + **17 auto-generated warrant claims** + **1 auto-bayes-implication helper claim** = **44 knowledge nodes** total — same counts as the hand-authored package.
- **9 derive strategies** — same count and structure.
- **7 structural operators** (1 `exclusive` + 3 `equal` + 3 `contradict`) — same count and structure.
- **6 register-prior records** in a sibling `priors.py` module — same layout as the hand-authored package.

The two packages are **content-equivalent at the IR-content-set level** for every user-authored Claim or note. The pytest fixture at `tests/cli/mendel_demo/test_equivalence.py` re-runs the cli sequence fresh and asserts these invariants on every PR-gate run using the multi-level equivalence helper (`tests/cli/_equivalence_levels.py`).

## R7 features exercised end-to-end

Mendel touches every R7 capability gap that galileo did not:

| R7 gap | mendel statement |
| --- | --- |
| G1 multi-file (`--file priors.py`) | 6 `register_prior` calls in sibling `priors.py` |
| G1 `pkg add-module` | scaffolding `priors.py` before authoring into it |
| G2 `bayes` group | 2 `bayes.model` + 1 `bayes.likelihood` + 2 distribution literals (`Binomial`, `BetaBinomial`) |
| G3 `author variable` | 2 `Variable(...)` declarations (`f2_total_count`, `f2_dominant_count`) |
| G4 `claim --formula` | 1 predicate-mode claim (`f2_count_observation_claim`) wrapping `land(equals(...), equals(...))` |
| G5 `--background` on relations | `exclusive`, every `observe`, every `derive`, every `equal`, every `contradict`, every `bayes.model`, `bayes.likelihood` |
| G6 inline-prose `derive --conclusion-prose` | every mendel `derive(...)` uses the inline-prose shape |
| G7 single-`--label` discipline (intrinsic) | every cli statement renders `label=` inside the call (per R7·❓A=A ratification) |
| G8 narrowed deprecation scan | hand-authored binding names like `competing_models` reused verbatim |

Mendel is therefore the empirical demonstration of R7's "cli surface covers full engine" claim. If anything that mendel reaches for is not directly cli-authorable, the R7 capability claim has a hole; the equivalence test fails fast under that condition.

## Authoring sequence

The 35 cli invocations below produce the cli-authored mirror. Each invocation is shown with its full flag set; in practice an agent scripts this from a JSON template. Output is JSON by default.

### 1. Scaffold the package skeleton

```bash
gaia pkg scaffold \
    --target ./mendel-cli-mirror-gaia \
    --name mendel-v0-5-gaia \
    --import-name mendel_v0_5 \
    --namespace example \
    --no-check
```

The scaffold writes:

- `pyproject.toml` with `[tool.gaia] type = "knowledge-package"` and `namespace = "example"` (no uuid by default — R7 G11 made uuid opt-in to match the shipping examples).
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

The Mendel package uses Variables for the F2 counts that feed the `bayes.Binomial(n=..., p=3/4)` observable and the predicate-claim formula. The cli renders `Variable(symbol=..., domain=..., value=...)` exactly:

```bash
gaia author variable \
  --label f2_total_count --symbol n_f2 --domain Nat --value 395 \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author variable \
  --label f2_dominant_count --symbol k_dominant --domain Nat --value 295 \
  --target ./mendel-cli-mirror-gaia --no-check
```

**Documented divergence** — the hand-authored file imports `TOTAL_COUNT` and `DOMINANT_COUNT` from `mendel_v0_5.probabilities` and passes them through (`value=TOTAL_COUNT`). The cli does not (yet) know how to import a constant from a sibling module via a single author verb; it forwards the `--value` argument verbatim as a Python expression. Both shapes compile to the same IR (a `Variable` with `value=395` / `value=295`). See [Documented divergences](#documented-divergences) §2.

### 3. Author the three contextual notes

```bash
gaia author note \
  "单因子杂交实验从两个稳定亲本品系开始：一个亲本稳定表现显性表型，另一个亲本稳定表现隐性表型；二者杂交得到 F1，再让 F1 自交得到 F2。" \
  --label monohybrid_cross_setup \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author note \
  "在该性状上，显性遗传因子会在表型上遮蔽隐性遗传因子。" \
  --label dominance_background \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author note \
  "F2 的显性/隐性计数是有限样本，因此用点似然（二项 PMF 在观测计数处的取值）衡量模型与数据的贴合度；对手理论取 p ~ Uniform[0,1] 的 diffuse 先验作为参考尺度，不引入任何具体的替代二项参数。" \
  --label finite_sample_background \
  --target ./mendel-cli-mirror-gaia --no-check
```

R7 G8 narrowed the prewrite deprecation scan to call positions, so binding names like `dominance_background` reuse the hand-authored spelling verbatim.

### 4. Author the two competing model claims + the `exclusive` operator

```bash
gaia author claim \
  "孟德尔分离模型：遗传因子是离散的；每个个体对某一性状携带一对因子；形成配子时成对因子分离，受精时重新配对；显性因子会遮蔽隐性因子。" \
  --label mendelian_segregation_model \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author claim \
  "混合遗传模型：亲本性状在后代中连续平均；一旦平均，离散的显性/隐性类别就不应在 F2 中作为可计数的类型存在。" \
  --label blending_inheritance_model \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author exclusive \
  --a mendelian_segregation_model --b blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "在同一个单因子性状解释上，离散分离模型和连续混合模型是竞争解释。" \
  --label competing_models \
  --target ./mendel-cli-mirror-gaia --no-check
```

### 5. Author the four qualitative observations

The first three are simple identifier observations; the fourth uses **`claim --formula`** to bind a predicate-logic claim that the `observe(...)` call then references.

```bash
gaia author observe \
  --observation-prose "纯种显性亲本与纯种隐性亲本杂交后，F1 后代统一表现显性表型。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F1 代的定性观察。" \
  --label f1_uniform_dominant_observation \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author observe \
  --observation-prose "F2 个体可以被清晰地划分为显性和隐性两个离散表型类别，不存在连续中间态。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察：表型呈两类，不是连续分布。" \
  --label f2_has_discrete_classes_observation \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author observe \
  --observation-prose "F1 自交得到的 F2 后代中，原隐性表型作为离散类别重新出现。" \
  --background monohybrid_cross_setup \
  --rationale "这是单因子杂交实验中 F2 代的定性观察。" \
  --label f2_recessive_reappears_observation \
  --target ./mendel-cli-mirror-gaia --no-check
```

The fourth observation embeds Mendel's quantitative measurement as a formula-claim. The hand-authored source binds the predicate claim separately and then mutates its `.label` attribute; the cli emits the label inside the `claim(...)` call directly. Both compile to the same IR.

```bash
gaia author claim \
  "F2 计数为 295 个显性表型和 100 个隐性表型，共 395 个个体。" \
  --label f2_count_observation_binding \
  --references f2_total_count,f2_dominant_count \
  --formula 'land(equals(f2_total_count, Constant(395, Nat)), equals(f2_dominant_count, Constant(295, Nat)))' \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author observe \
  --conclusion f2_count_observation_binding \
  --background monohybrid_cross_setup,f2_has_discrete_classes_observation \
  --rationale "这是用于贝叶斯点似然比较的 F2 显性/隐性计数数据。" \
  --label f2_count_observation \
  --target ./mendel-cli-mirror-gaia --no-check
```

**Documented divergence** — `claim --references` performs two jobs: it whitelists the listed identifiers inside the formula sandbox **and** flows them through as `background=[...]` in the rendered claim. The hand-authored file uses formula-symbol references that are **not** in the claim's background list. Both shapes compile to the same IR claim (the rendered `background=[f2_total_count, f2_dominant_count]` references Variables; the IR drops Variables on the claim-background slot). See [Documented divergences](#documented-divergences) §3.

### 6. Author the five Mendel qualitative derivations + three matches

Each `derive` uses **inline-prose** (`--conclusion-prose`) per R7 G6, matching the hand-authored shape byte-for-byte at the conclusion-claim slot.

```bash
gaia author derive \
  --conclusion-prose "如果孟德尔分离模型成立，纯种显性亲本与纯种隐性亲本杂交后，F1 后代都应携带一个显性因子和一个隐性因子，并表现显性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "显性因子在杂合 F1 个体中遮蔽隐性因子。" \
  --label mendel_predicts_f1_dominance \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author equal \
  --a mendel_predicts_f1_dominance --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F1 统一显性的预测与观察相符。" \
  --label f1_mendel_match \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-prose "孟德尔分离模型下 F2 的基因型组合为 AA:Aa:aa = 1:2:1，显性因子遮蔽效应把这三个基因型映射到显性和隐性两个离散表型类别，因此 F2 应呈现清晰的两类离散表型而非连续谱。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "离散因子 + 遮蔽 → 两个离散表型类别。" \
  --label mendel_predicts_discrete_classes \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author equal \
  --a mendel_predicts_discrete_classes --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型预言的两类离散表型与观察到的 F2 两类表型一致。" \
  --label f2_discrete_classes_mendel_match \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-prose "如果 F1 个体仍携带被遮蔽的隐性因子，那么 F1 自交后，部分 F2 个体会继承两个隐性因子并重新表现隐性表型。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background \
  --rationale "分离模型保留了隐性因子，并允许它在 F2 中重新组合为纯合隐性。" \
  --label mendel_predicts_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author equal \
  --a mendel_predicts_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "孟德尔模型对 F2 隐性重现的预测与观察相符。" \
  --label f2_reappearance_mendel_match \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-prose "如果 F1 个体自交，成对因子分离会给出 AA:Aa:aa = 1:2:1 的基因型比例；由于 AA 和 Aa 都表现显性，F2 显性/隐性计数应服从 Binomial(N, 3/4)，期望表型比约为 3:1。" \
  --given mendelian_segregation_model \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "F1 配子等概率结合，给出 1:2:1 的基因型分布，即每个 F2 个体独立以概率 3/4 表现为显性。" \
  --label mendel_predicts_three_to_one_ratio \
  --target ./mendel-cli-mirror-gaia --no-check
```

### 7. Author the quantitative bayes comparison

The hand-authored file inlines `bayes.Binomial(n=TOTAL_COUNT, p=MENDELIAN_DOMINANT_PROBABILITY)` directly inside the `bayes.model(...)` call's `distribution=` slot. The cli's `bayes model` verb requires `--distribution <ident>`, so we pre-bind the two distributions as standalone statements.

```bash
gaia bayes binomial \
  --label mendel_count_distribution \
  --n 395 --p '3/4' \
  --target ./mendel-cli-mirror-gaia --no-check

gaia bayes beta-binomial \
  --label diffuse_count_distribution \
  --n 395 --alpha 1.0 --beta 1.0 \
  --target ./mendel-cli-mirror-gaia --no-check

gaia bayes model \
  --hypothesis mendelian_segregation_model \
  --observable f2_dominant_count \
  --distribution mendel_count_distribution \
  --background monohybrid_cross_setup,dominance_background,finite_sample_background \
  --rationale "孟德尔分离模型给出 F2 每个个体以概率 3/4 表现显性的生成模型，因此显性计数服从 Binomial(N, 3/4)。" \
  --label mendel_count_model \
  --target ./mendel-cli-mirror-gaia --no-check

gaia bayes model \
  --hypothesis blending_inheritance_model \
  --observable f2_dominant_count \
  --distribution diffuse_count_distribution \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "把对照项写成 p ~ Uniform[0, 1] 下的 BetaBinomial(N, 1, 1) 预测分布；它给出任意具体计数的边际概率 1 / (N + 1)，不人为指定第二个二项参数。" \
  --label diffuse_count_model \
  --target ./mendel-cli-mirror-gaia --no-check

gaia bayes likelihood \
  --data f2_count_observation \
  --model mendel_count_model \
  --against diffuse_count_model \
  --background monohybrid_cross_setup,finite_sample_background \
  --rationale "直接比较观测到的 F2 显性计数在 Mendel 点模型和 diffuse 参考模型下的 log likelihood；观测可靠性仍留在 f2_count_observation 的 prior 中。" \
  --exclusivity none \
  --label mendel_count_likelihood \
  --target ./mendel-cli-mirror-gaia --no-check
```

**Documented divergence** — the cli pre-binds `bayes.Binomial(...)` and `bayes.BetaBinomial(...)` as standalone bindings (`mendel_count_distribution`, `diffuse_count_distribution`); the hand-authored file inlines them inside `bayes.model(distribution=bayes.Binomial(...))`. Both compile to the same IR (the engine wraps inline Distribution literals into the same internal shape as a pre-bound one). See [Documented divergences](#documented-divergences) §4.

### 8. Author the three Blending derivations + three contradictions

```bash
gaia author derive \
  --conclusion-prose "如果混合遗传模型成立，F1 后代应倾向于中间或混合表型，而不是统一表现某一亲本表型。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均模型把亲本性状视为在后代中均化。" \
  --label blending_predicts_intermediate_f1 \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author contradict \
  --a blending_predicts_intermediate_f1 --b f1_uniform_dominant_observation \
  --background monohybrid_cross_setup \
  --rationale "F1 统一显性与混合模型的中间表型预测相冲突。" \
  --label f1_blending_conflict \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-prose "如果亲本性状在 F1 中连续平均，F2 应形成单峰连续分布，不能被划分为清晰的显性/隐性两个离散类别。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "连续平均不保留可重新组合的离散遗传单位，因此不给出离散的表型分类。" \
  --label blending_predicts_f2_continuous \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author contradict \
  --a blending_predicts_f2_continuous --b f2_has_discrete_classes_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 明确划分为两类离散表型，与混合模型的连续分布预测相冲突——这是 framework 级别的冲突：blending 否认的是 F2 可被分类这件事本身。" \
  --label f2_discrete_classes_blending_conflict \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author derive \
  --conclusion-prose "连续平均的性状不保留可以重新组合的离散遗传单位，因此原隐性表型不应作为离散类别在 F2 中重新出现。" \
  --given blending_inheritance_model \
  --background monohybrid_cross_setup \
  --rationale "混合模型没有保留可重新组合的离散隐性因子。" \
  --label blending_predicts_no_recessive_reappearance \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author contradict \
  --a blending_predicts_no_recessive_reappearance --b f2_recessive_reappears_observation \
  --background monohybrid_cross_setup \
  --rationale "F2 隐性表型作为离散类别重新出现，与混合模型的预测相冲突。" \
  --label f2_reappearance_blending_conflict \
  --target ./mendel-cli-mirror-gaia --no-check
```

### 9. Scaffold `priors.py` and register the six priors

```bash
gaia pkg add-module --name priors --imports register_prior \
  --target ./mendel-cli-mirror-gaia

gaia author register-prior \
  --claim mendelian_segregation_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让孟德尔分离模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author register-prior \
  --claim blending_inheritance_model --value 0.5 \
  --justification "在观察单因子杂交结果之前，让混合遗传模型保持中性先验。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author register-prior \
  --claim f1_uniform_dominant_observation --value 0.95 \
  --justification "把 F1 统一显性作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author register-prior \
  --claim f2_has_discrete_classes_observation --value 0.95 \
  --justification "把 F2 呈两类离散表型作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author register-prior \
  --claim f2_recessive_reappears_observation --value 0.95 \
  --justification "把 F2 隐性表型重新出现作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check

gaia author register-prior \
  --claim f2_count_observation --value 0.95 \
  --justification "把 F2 显性/隐性计数作为可靠的实验观察。" \
  --file priors.py \
  --target ./mendel-cli-mirror-gaia --no-check
```

The writer auto-inserts `from mendel_v0_5 import <claim>` for each newly referenced binding in `priors.py`, so the resulting file imports the same six claims that the hand-authored `priors.py` does.

**Documented divergence** — the hand-authored `register_prior(blending_inheritance_model, value=1.0 - PRIOR_MENDELIAN_MODEL, ...)` references the `PRIOR_MENDELIAN_MODEL` constant from `mendel_v0_5.probabilities`. The cli forwards `--value 0.5` verbatim. Numerically identical; structurally a constant-reference vs literal-value choice. See [Documented divergences](#documented-divergences) §5.

## Compile + check

```bash
cd mendel-cli-mirror-gaia
gaia build compile
# → Compiled 44 knowledge, 9 strategies, 7 operators
gaia build check
```

The counts match the hand-authored package compile (`44 / 9 / 7`).

## Documented divergences

R7 closed three of galileo's four R5/R6 divergences; mendel's surface (bayes, formula, multi-file) surfaces three additional intrinsic divergences. Every divergence below is either ratified intrinsic (G7) or a non-semantic source-text difference that compiles to the same IR.

### 1. LHS binding equals `label=` kwarg (intrinsic, R7·❓A=A)

Same as galileo Divergence #2. The cli enforces `label_name = verb(..., label="label_name")` — the LHS Python binding and the DSL `label=` kwarg are forced equal because the cli's single `--label` flag drives both.

The hand-authored Mendel file uses a distinctive variant of this gap for the F2-count predicate claim: it binds the claim with a leading-underscore Python identifier (`_f2_count_observation_binding`) and then **mutates the claim's `.label` attribute** to `"f2_count_observation"` so the IR-side label matches the corresponding observation. The cli can't replicate the post-binding `.label = ...` mutation — it issues `gaia author claim --label f2_count_observation_binding`, which renders `label='f2_count_observation_binding'` inside the claim call. The underlying IR claim ends up with label `f2_count_observation_binding` on the cli side vs `f2_count_observation` on the hand side — both reference the same content + formula, and the test's label-bag axis applies a per-axis CONTENT_SET tolerance that accepts the rename. **Compiles to IR-content-equivalent shape; the label-bag axis tolerates the rename.**

### 2. `Variable(value=<literal>)` vs `value=<imported-constant>` (intrinsic)

The hand-authored Mendel file imports `TOTAL_COUNT` / `DOMINANT_COUNT` from `mendel_v0_5.probabilities` and passes them through to `Variable(value=TOTAL_COUNT)`. The cli's `gaia author variable --value 395` forwards the argument verbatim, emitting `Variable(symbol='n_f2', domain=Nat, value=395)`. **Numerically identical at the IR level**; this is a source-text style choice (named constant vs literal).

### 3. `claim --references` flows into the rendered `background=[...]` (intrinsic)

The cli's `--references` flag has two jobs: it whitelists the listed identifiers inside the formula sandbox AND flows them through as the rendered claim's `background=[...]`. The hand-authored `claim(content, formula=land(equals(my_var, ...)))` references Variable identifiers inside the formula without listing them as background. Both shapes compile to the same IR — the rendered claim ingests Variables as background, but the engine drops Variables from the claim-background slot since they're typed terms rather than Knowledge nodes.

### 4. `bayes.model(distribution=<pre-bound>)` vs inline `bayes.Binomial(...)` (intrinsic)

The hand-authored file inlines `bayes.Binomial(n=TOTAL_COUNT, p=MENDELIAN_DOMINANT_PROBABILITY)` directly inside `bayes.model(distribution=...)`. The cli's `gaia bayes model --distribution <ident>` requires a pre-bound Distribution identifier; the cli-authored mirror adds two extra `mendel_count_distribution` / `diffuse_count_distribution` bindings ahead of the `bayes.model` calls. The engine wraps inline Distribution literals into the same internal shape as a pre-bound one, so **both compile to equivalent bayes-model IR**.

### 5. `register_prior(value=<imported-constant>)` vs `value=<literal>` (intrinsic)

Same root cause as §2 above. The hand-authored `priors.py` imports `PRIOR_MENDELIAN_MODEL` from `mendel_v0_5.probabilities` and references it as `value=PRIOR_MENDELIAN_MODEL` (and `value=1.0 - PRIOR_MENDELIAN_MODEL`). The cli forwards literal values. **Numerically identical**.

### 6. `register_prior` always renders `source_id='user_priors'` (intrinsic)

The cli always renders `register_prior(claim, value, justification=..., source_id='user_priors')` for source-id discoverability. The hand-authored file omits the kwarg when it would equal the default. Source-text-only difference; both engines parse to the same `PriorRecord.source_id`.

### 7. Scaffold `__init__.py` carries full import block (intrinsic)

`gaia pkg scaffold` writes a `__init__.py` that imports the full author-surface DSL (`bayes`, `Variable`, `Constant`, every primitive Domain, every formula primitive, every relation verb) so subsequent `gaia author <verb>` calls don't trip the postwrite `NameError` from missing imports. The hand-authored Mendel `__init__.py` imports only the names it actually uses (about 12 of the ~25 scaffold imports). Source-text difference only; the IR doesn't care which imports the module file declares.

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
| `bayes-model-count` | BYTE_TEXT | 2 `bayes.model` calls + 1 `bayes.likelihood` call on both sides. |
| `register-prior-count` | BYTE_TEXT | 6 `register_prior` calls in `priors.py` on both sides. |

The multi-level helper at `tests/cli/_equivalence_levels.py` underwrites both this mendel demo and the galileo demo's R8-tightened equivalence (galileo had been content-set on all axes; R7 closed 3 of 4 divergences, so R8 tightens to BYTE_TEXT on the R7-closed axes while keeping content-set on the intrinsic G7 axis).

## See also

- Hand-authored ground truth: [`src/mendel_v0_5/__init__.py`](src/mendel_v0_5/__init__.py)
- Hand-authored priors: [`src/mendel_v0_5/priors.py`](src/mendel_v0_5/priors.py)
- Equivalence test: [`tests/cli/mendel_demo/test_equivalence.py`](../../tests/cli/mendel_demo/test_equivalence.py)
- Multi-level tolerance helper: [`tests/cli/_equivalence_levels.py`](../../tests/cli/_equivalence_levels.py)
- Sibling galileo walkthrough: [`examples/galileo-v0-5-gaia/CLI-AUTHORED.md`](../galileo-v0-5-gaia/CLI-AUTHORED.md)
- Full cli reference: [`docs/reference/cli/author.md`](../../docs/reference/cli/author.md)
