---
name: gaia-research-loop
description: |
  Use when running or evaluating Gaia research workflows that explore a field,
  synthesize focuses, expand around coverage gaps, assess evidence for a
  focus, promote mature scaffolds, or produce a live research trace. Applies
  to `gaia research`, LKM-backed literature discovery, package/inquiry-centric
  research state, and review-quality Chinese or English final evidence reports.
---

# Gaia Research Loop

## Intent

Run a package-native research loop without inventing a second research data
model. Canonical research state lives in Gaia package source and inquiry state;
`.gaia/research` is for landscapes, assessments, the final evidence report,
run traces, derived benchmark summaries, and other audit artifacts.

Use printed `gaia research contract ...` output as the schema source. Do not
copy, freestyle, or infer schemas from memory.

## Mode Selector

Choose the lightest mode that satisfies the user request.

- **Normal research mode**: use when the user wants to research a topic or
  advance a Gaia package. Benchmark artifacts are optional unless requested.
- **Benchmark/live eval mode**: use when the user says eval, benchmark, live
  evaluation, clean evaluation agent, end-to-end evaluation, or asks for timing
  and trace quality. Read `references/live-eval-sop.md` and
  `references/benchmark-trace.md`.
- **Fixture regression mode**: use only when the user explicitly asks for
  fixture/mock regression. Never substitute this for a requested live eval.

## Hard Boundaries

- Start broad. Run multiple query families before choosing a focus.
- Choose LKM search scope deliberately. For package-native landscape building,
  search reasoning-backed evidence first: default `gaia search lkm knowledge`
  searches both claim and question nodes, while `--reasoning-only` is the
  claim+conclusion retrieval shape for claims backed by reasoning chains.
- Do not use `gaia-lkm-explore` unless the user explicitly asks for legacy
  comparison.
- Do not treat search rank as confidence.
- Preserve raw LKM search JSON for live runs.
- Do not store durable live-run artifacts under `/private/tmp` or other
  OS-cleaned scratch locations; use a package-local run directory.
- For benchmark/live eval runs, prefer absolute `$PKG`, `$RUN`, and `$TRACE`
  paths in CLI arguments. Relative manifest or output paths may be resolved
  relative to the package root and create nested duplicate package paths.
- Do not invent `snippet`, `lkm_node`, `gaia_qid`, or local `item_N`
  references.
- Never write access keys into package files, traces, reports, commits, or docs.
- Treat package-local JSON state as single-writer. Do not run
  `gaia research trace record`, `gaia inquiry obligation close`, or other
  state/manifest mutations in parallel.
- During `assess`, do not write stable `claim(...)`, `derive(...)`,
  `contradict(...)`, or `equal(...)`; write scaffold state first.
- Write `candidate_relation(...)` only when a relation has concrete package
  claim endpoints: explicit `claim_refs`, or at least two `source_refs` with
  `kind: "package_ref"` whose source value type is `claim`.

## Minimal Envelope

At run start, infer or create:

```text
topic: <research topic>
language: <zh|en|...>
pkg: <Gaia package path>
run_dir: <package-local run directory>
seed_question: <broad research question>
mode: normal | benchmark | fixture
stop_when: coverage sufficient, relation mix adequate, obligations resolved or
  explicitly deferred, and query novelty low enough
```

For benchmark/live eval runs, initialize:

```bash
PKG=<path-to-existing-or-new-topic-gaia>
RUN=$PKG/.gaia/research/runs/<topic>-$(date -u +%Y%m%dT%H%M%SZ)
TRACE=$RUN/trace
mkdir -p "$RUN/searches" "$RUN/analysis" "$RUN/trace"
```

## Phase References

Load only the reference needed for the current phase:

- Full live-eval command flow and artifact checklist:
  `references/live-eval-sop.md`.
- Research trace, derived `benchmark.json`, timing, token usage, retries, and quality
  notes: `references/benchmark-trace.md`.
- Field-map induction JSON prompt:
  `references/field-map-analysis-prompt.md`.
- Focus analysis JSON prompt: `references/focus-analysis-prompt.md`.
- Assessment analysis JSON prompt and candidate relation rules:
  `references/assess-analysis-prompt.md`.
- Chinese scholarly final report and final eval summary:
  `references/final-report.md`.

## Normal Research Flow

For normal mode, keep the workflow lean:

1. Create or reuse a Gaia package and seed `question(...)`.
2. Use real LKM search when literature discovery is needed.
3. Run `gaia research explore`, then `focus`, then `expand` as needed.
4. Run `assess` on one selected focus.
5. Promote only after scaffold review.
6. Finish with `gaia build check "$PKG"` when package source changed.

Do not require full evaluation traces, token accounting, or raw search archives
unless the user requested benchmark/live eval.

## Benchmark Flow

For benchmark/live eval mode, follow `references/live-eval-sop.md`. In short:

1. Use a fresh package-local `$RUN`.
2. Prefer the package-native orchestrator:
   `gaia research run "$PKG" --topic "<topic>" --analysis-provider litellm --focus-count 3`.
   Do not pass broad `--query`, `--search-json`, `--targeted-query`, or
   `--targeted-search-json` unless the user explicitly asks to replay fixed
   inputs. Let the runner's `query_plan` LLM call generate broad searches, and
   let `field_map_analysis` induce a review taxonomy from primary evidence
   before focus selection. Thin or missing review buckets can trigger
   coverage-expansion searches; then `focus_analysis.suggested_queries` drives
   focus-targeted searches. Before assessment, let the runner select a compact
   evidence packet and deep-materialize only the highest-value paper graphs or
   reasoning chains needed to ground the selected focus.
   Do not pass `--llm-max-tokens` in normal live runs; the fixed prompts should
   stay compact, and provider truncation should be handled by prompt/schema
   tightening rather than caller-side caps.
3. Save every raw LKM search result under `$RUN/searches/`.
4. Use `--trace-dir "$TRACE"` for every `gaia research` command that
   supports it.
5. Use `gaia research trace record` for LKM search timing, LLM/provider token
   usage, retries, and other external steps.
6. After the final trace append, run `gaia research trace summarize "$PKG"
   --trace-dir "$TRACE"` to rebuild derived `benchmark.json` from `trace.jsonl`.
7. Produce `evaluation_trace.md`, `benchmark.json`, `trace.jsonl`, field-map,
   selected-evidence, focus and assess contracts, analysis JSON files, JSON
   stop criteria, report plan/section/stitch JSON, and one final scholarly
   evidence report at `$RUN/trace/final_report.md`.
8. In `evaluation_trace.md`, distinguish end-to-end elapsed time from the
   derived benchmark summary's sum of explicitly recorded trace step wall times.
9. Treat ordinary coverage gaps and `needs_more_evidence` items as deferred
   assessment gaps unless they are explicitly marked actionable/blocking.
   Continue until actionable obligations are resolved, explicitly deferred with
   rationale, or stop criteria recommends a justified terminal action.

For follow-up runs, keep `--topic` as a natural research instruction, not a
hidden query list. Good: "Continue the DQCP evidence assessment, focusing on
the unresolved evidence gaps from the previous run." Bad: a colon-separated
list of exact paper families, exponents, and search phrases copied from
obligations. The runner should generate the query plan.

Before deciding to expand again, check whether the latest landscape actually
grounds the assessment. A high new-paper-lead ratio by itself is not enough:
if the assessment cites only a small fraction of the new leads, prefer human
review, deep materialization, or explicit deferral over another broad expansion.

## Review Quality Bar

Before handoff:

1. `gaia build check "$PKG"` passes when package source changed.
2. Focus, assessment, and stop remain JSON audit artifacts; the only default
   Markdown report from a run is `$RUN/trace/final_report.md`.
3. Field-map buckets cover the topic's review-level taxonomy before narrow
   focus assessment begins.
4. Final review prose is written by report-plan/section/stitch phases and
   reads like a scholarly evidence review, not a command transcript or run
   summary.
5. Main review prose does not mention Gaia, LKM, CLI, artifact ids, or workflow
   jargon except in explicit provenance/trace sections.
6. Relations and obligations are explained in prose; raw tables stay in JSON
   artifacts.
7. The trace says what to do next: broaden search, expand a focus, assess
   another focus, deep-materialize selected papers/chains, defer known gaps, or
   stop.

## Common Mistakes

- Starting from one attractive paper and narrowing before the landscape is
  broad.
- Forgetting that default LKM knowledge search returns both claims and
  questions. This can make fast source materialization question-heavy even
  when the assessment needs claim endpoints. Start landscape searches with
  `--reasoning-only` before `explore`/`expand` materializes sources.
- Treating `assessment.json` as formal knowledge; it is scaffold trace until
  promoted.
- Treating artifact-local items as durable evidence. Use stable refs already
  present in the artifact, especially `package_ref.ref` when available.
- Rewriting JSON schemas in prompts instead of printing `gaia research
  contract`.
- Letting benchmark mode mutate the research semantics. Benchmarking is an
  observability layer; the research commands should mean the same thing.
- Parallelizing package-state or trace writes. Parallel searches are fine, but
  append search timings and close obligations sequentially.
- Assuming a scaffold seeded only with questions/notes will pass
  `gaia build check`. If the package source changed and the checker requires a
  claim-bearing public surface, add only a narrow assessment-scoped
  `claim(...)` after scaffold review; do not formalize assessment relations
  prematurely.
