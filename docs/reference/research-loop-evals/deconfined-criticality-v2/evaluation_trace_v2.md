# Gaia Research Loop Live V2 Trace: Deconfined Criticality

## Run metadata

- Topic: deconfined criticality / DQCP / Neel-VBS transition
- Language: Chinese analysis, English queries
- Run directory: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2`
- Package: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia`
- Start: `2026-06-02T04:45:02Z`
- End: `2026-06-02T04:50:16Z`
- Elapsed live workflow time: about 5 min 14 sec
- Purpose: verify v2 focus/assessment prompts and report/stop CLI are not aspirin-specific.

## Implemented CLI features used in this run

- `gaia research focus --analysis-json`: validates LLM/agent focus synthesis.
- `gaia research assess --analysis-json`: validates typed relation assessment with strict grounding.
- `gaia research report --artifact --out`: renders focus, assessment, and stop artifacts into readable Markdown.
- `gaia research stop`: evaluates coverage, relation mix, unresolved obligations, and query novelty.

## Setup commands

```bash
mkdir -p /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/analysis \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace

uv run gaia pkg scaffold \
  --target /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --name deconfined-criticality-gaia \
  --namespace deconfined_criticality \
  --description "Live research loop evaluation for deconfined criticality" \
  --docstring "Research loop package for deconfined criticality live evaluation." \
  --no-check

uv run gaia research status \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia
```

## Broad scan

Initial hybrid query failed:

```bash
uv run gaia search lkm knowledge \
  "deconfined criticality Neel VBS anomalous scaling weak first order" \
  --retrieval-mode hybrid --limit 15 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/01-neel-vbs-scaling.json
```

Error: both semantic and lexical search hit LKM context deadline exceeded.

Semantic retry also failed:

```bash
uv run gaia search lkm knowledge \
  "deconfined criticality Neel VBS" \
  --retrieval-mode semantic --limit 8 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/01-neel-vbs-scaling.json
```

The successful broad scan used lexical queries with explicit domain anchors:

```bash
uv run gaia search lkm knowledge "deconfined criticality" \
  --retrieval-mode lexical --keywords deconfined --keywords criticality --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/01-deconfined-criticality.json

uv run gaia search lkm knowledge "SO5 emergent symmetry deconfined critical point" \
  --retrieval-mode lexical --keywords SO5 --keywords deconfined --keywords symmetry --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/02-so5-symmetry.json

uv run gaia search lkm knowledge "J-Q model deconfined critical point first order" \
  --retrieval-mode lexical --keywords J-Q --keywords deconfined --keywords first-order --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/03-jq-first-order.json

uv run gaia search lkm knowledge "easy-plane NCCP1 deconfined criticality duality" \
  --retrieval-mode lexical --keywords NCCP1 --keywords deconfined --keywords duality --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/04-nccp1-duality.json
```

One shell pitfall: unquoted `--keywords SO(5)` was parsed by zsh as a special file attribute. Retried with `SO5`.

Landscape command:

```bash
uv run gaia research explore \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --mode scan \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/01-deconfined-criticality.json \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/02-so5-symmetry.json \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/03-jq-first-order.json \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/04-nccp1-duality.json
```

Result:

- scan artifact: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/scan-20260602T044640732617Z.json`
- query batches: 4
- raw results: 40
- paper leads: 33

## Focus synthesis

Prompt source:

- `gaia/_skills/gaia-research-loop/references/focus-analysis-prompt.md`
- `gaia research contract focus --language zh`

Analysis JSON:

- `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/analysis/focus-analysis.json`

Validation/write command:

```bash
uv run gaia research focus \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --landscape /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/scan-20260602T044640732617Z.json \
  --analysis-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/analysis/focus-analysis.json \
  --language zh
```

Result:

- focus artifact: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/focuses/focuses-20260602T044759205529Z.json`
- focuses: 4
- coverage gaps: 3

Generated focuses:

1. `continuous_vs_weak_first_order`: continuous DQCP vs weak first-order transition.
2. `emergent_symmetry_and_anisotropy`: whether SO(5)/O(4)/U(1) symmetry is diagnostic or also pseudo-critical.
3. `nccp1_duality_field_theory_bridge`: how NCCP1/easy-plane/QED3 duality constrains lattice DQCP.
4. `microscopic_model_dependence`: whether transition order and symmetry depend on model details.

Coverage gaps:

- retrieval noise from non-condensed-matter "deconfined" or "SO5" meanings;
- missing conformal bootstrap / CFT fixed-point constraints;
- paper-overlap bias in NCCP1/duality snippets.

Rendered report:

```bash
uv run gaia research report \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --artifact /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/focuses/focuses-20260602T044759205529Z.json \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace/focus_report.md
```

## Targeted expand

Target: `continuous_vs_weak_first_order`.

```bash
uv run gaia search lkm knowledge \
  "weakly first order deconfined criticality J-Q model running exponent" \
  --retrieval-mode lexical --keywords weakly --keywords first-order --keywords deconfined --keywords J-Q --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/05-weak-first-order-running.json

uv run gaia search lkm knowledge \
  "Neel VBS deconfined critical point finite size scaling" \
  --retrieval-mode lexical --keywords Neel --keywords VBS --keywords scaling --keywords deconfined --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/06-finite-size-scaling.json

uv run gaia search lkm knowledge \
  "SO5 deconfined criticality conformal bootstrap fixed point" \
  --retrieval-mode lexical --keywords SO5 --keywords deconfined --keywords bootstrap --limit 10 \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/07-so5-bootstrap.json
```

Landscape command:

```bash
uv run gaia research explore \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --mode expand \
  --focus continuous_vs_weak_first_order \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/05-weak-first-order-running.json \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/06-finite-size-scaling.json \
  --search-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/searches/07-so5-bootstrap.json
```

Result:

- expand artifact: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/expand-20260602T044839228122Z.json`
- query batches: 3
- raw results: 30
- paper leads: 24
- new expand paper leads vs scan: 17
- new paper lead ratio: 0.7083

## Assessment

Prompt source:

- `gaia/_skills/gaia-research-loop/references/assess-analysis-prompt.md`
- `gaia research contract assess --language zh`

Analysis JSON:

- `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/analysis/assess-analysis.json`

Validation/write command:

```bash
uv run gaia research assess \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --focus continuous_vs_weak_first_order \
  --artifact-only \
  --landscape /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/scan-20260602T044640732617Z.json \
  --landscape /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/expand-20260602T044839228122Z.json \
  --analysis-json /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/analysis/assess-analysis.json
```

Result:

- assessment artifact: `/private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/assessments/assessment-20260602T044959144932Z.json`
- snippets: 70
- relations: 11
- relation mix: supports 3 / opposes 3 / qualifies 3 / undercuts 2
- review payload: true
- strict grounding: passed
- candidate obligations: 3

Assessment summary:

当前证据更支持一个谨慎结论：deconfined criticality 是解释二维 Néel-VBS 转变的重要理论框架，并且在若干 sign-problem-free 模型中有正面数值和对称性信号；但对最核心的方格 J-Q/SU(2) 类模型，证据包尚不足以把热力学极限连续 DQCP 判为已确立事实。弱一阶转变、有限尺寸慢漂移、模型依赖性和 monopole/IR flow 未定性仍是主要反证或限定。

Rendered report:

```bash
uv run gaia research report \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --artifact /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/assessments/assessment-20260602T044959144932Z.json \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace/assessment_report.md
```

## Stop criteria

```bash
uv run gaia research stop \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --focus-artifact /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/focuses/focuses-20260602T044759205529Z.json \
  --assessment /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/assessments/assessment-20260602T044959144932Z.json \
  --landscape /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/expand-20260602T044839228122Z.json \
  --previous-landscape /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia/.gaia/research/landscapes/scan-20260602T044640732617Z.json \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace/stop.json
```

Result:

- recommendation: `expand_focus`
- should_stop: false
- coverage: weak, because 3 coverage gaps and 2 focuses still need expansion.
- relation_mix: sufficient, because the selected focus has support and opposing/qualifying/undercutting evidence.
- unresolved_obligations: weak, because 3 obligations exceed threshold 2.
- query_novelty: sufficient, because expand added 17 new paper leads, ratio 0.7083.

Rendered report:

```bash
uv run gaia research report \
  /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/deconfined-criticality-gaia \
  --artifact /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace/stop.json \
  --out /private/tmp/gaia-research-eval-live-deconfined-criticality-v2/trace/stop_report.md
```

## Generality check

This run is not an aspirin prompt hack:

- Focuses use DQCP-native concepts: weak first-order transition, Neel-VBS, emergent SO(5)/O(4)/U(1), VBS anisotropy, NCCP1, QED3, monopole relevance, finite-size scaling.
- Assessment relation types are field-appropriate: support from QMC/field-theory signals, opposition from weak-first-order finite-size ambiguity, qualification by microscopic model dependence, and undercutting from diagnostic limitations.
- The stop criteria worked on non-medical metrics: coverage gaps, relation mix, unresolved obligations, and paper-lead novelty.

## Open issues discovered

- LKM semantic/hybrid search timed out on this topic; lexical with explicit keywords was more reliable.
- SO5 lexical queries can retrieve chemistry radical literature; agent must anchor `SO5` with `deconfined`, `NCCP1`, `Neel`, `VBS`, or `DQCP`.
- `gaia research stop` currently treats global focus coverage and selected assessment together. This is useful for loop-level guidance, but future CLI may need `--focus-id` to compute stop criteria for one focus versus the whole landscape.
- Assessment is review-grade at snippet level, but still needs paper pulling and primary extraction before source promotion into stable Gaia claims.
