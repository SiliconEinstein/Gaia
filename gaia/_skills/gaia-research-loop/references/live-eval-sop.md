# Live Evaluation SOP

Use this reference only for benchmark/live eval mode.

## Setup

Use a package-local run directory:

```bash
PKG=$(realpath <path-to-existing-or-new-topic-gaia>)
RUN="$PKG/.gaia/research/runs/<topic>-$(date -u +%Y%m%dT%H%M%SZ)"
TRACE=$RUN/trace
LANG=<zh|en|...>
mkdir -p "$RUN/searches" "$RUN/analysis" "$RUN/trace"
```

Keep `$PKG`, `$RUN`, and `$TRACE` absolute in benchmark/live eval commands.
Relative `--trace-dir`, `--analysis-json`, or `--out` paths can be resolved
relative to the package root by some commands, producing accidental nested
package paths such as `<pkg>/<pkg>/.gaia/...`.

Create or seed the package when needed:

```bash
gaia pkg scaffold --target "$PKG" --name <topic>-gaia --namespace <topic>
gaia author question "<seed question>" --target "$PKG" \
  --dsl-binding-name <seed_binding> --title "<title>" --export --no-check
gaia research status "$PKG"
```

## Orchestrated Topic-Only Run

For benchmark/live eval runs on the package-native orchestrator, do not pass
fixed search queries into the command. The runner should own the machine path:

- no `--query`;
- no `--search-json`;
- no `--targeted-query`;
- no `--targeted-search-json`.
- no `--llm-max-tokens` for normal live runs.

With `--analysis-provider litellm`, the runner first writes
`analysis/query_plan.output.json` and uses those generated queries for broad
live search. It then writes `analysis/field_map_analysis.output.json`,
materializes `.gaia/research/field_maps/*.json`, and may run
`searches/coverage-*.json` to fill thin or missing review buckets before focus
synthesis. After focus synthesis, it uses the selected focus's
`suggested_queries` plus focus coverage-gap suggested queries for targeted
search. Before assessment, it writes `.gaia/research/evidence/selected-evidence-*.json`
and deep-materializes only the selected paper graphs or reasoning chains
required by that compact evidence packet. After assessment, fast
package-native LiteLLM runs write `report_plan`,
`report_section_*`, and `report_stitch` analysis JSON before emitting the final
Markdown report.
Keep the LLM path unconstrained by caller-side output caps; if a provider emits
oversized JSON, tighten the phase prompt or schema rather than adding
`--llm-max-tokens`.

```bash
gaia research run "$PKG" \
  --topic "<research topic>" \
  --mode fast-package-native \
  --language "$LANG" \
  --analysis-provider litellm \
  --model "$GAIA_RESEARCH_LLM_MODEL" \
  --focus-count 3 \
  --search-limit 10 \
  --trace-dir "$TRACE"
```

After the run, inspect open obligations with:

```bash
gaia inquiry obligation list --json --path "$PKG"
```

Ordinary focus coverage gaps and assessment `needs_more_evidence` items are
deferred assessment gaps by default; they should remain in JSON artifacts and
review limitations rather than becoming open inquiry obligations. Only close
open obligations when the assessment, stop report, or an explicit follow-up
expansion resolves or defers them with rationale:

```bash
gaia inquiry obligation close <obligation-qid> --path "$PKG"
```

Then run the final report step if the orchestrator did not already produce it
and run `gaia build check "$PKG"`.

When deciding whether to expand again, inspect both novelty and grounding.
High `new_paper_lead_ratio` means the search is finding new papers; it does
not mean those papers are useful. If `assessment_grounded_paper_lead_ratio` is
low, prefer human review, selected paper/chain materialization, or explicit
deferral over another broad topic-only expansion.

## Follow-Up Runs

If stop criteria recommends another expansion or obligations remain open, use a
natural continuation topic. The topic should describe the user's research intent
and refer to unresolved gaps at a high level; it should not smuggle in a
query-plan as comma-separated technical keywords.

Good:

```bash
gaia research run "$PKG" \
  --topic "Continue the DQCP evidence assessment, focusing on unresolved gaps from the previous run." \
  --mode fast-package-native \
  --language "$LANG" \
  --analysis-provider litellm \
  --model "$GAIA_RESEARCH_LLM_MODEL" \
  --focus-count 3 \
  --search-limit 10
```

Avoid:

```text
--topic "Resolve open obligations: exact query A, exact query B, exact query C"
```

The follow-up run should still omit `--query`, `--targeted-query`, and
`--llm-max-tokens`.

## Manual Breadth-First Explore

Run several independent query families before choosing a focus. For
package-native landscape building, search reasoning-backed evidence first so
the landscape has claim endpoints suitable for assessment and materialization.
Preserve every raw search JSON:

```bash
gaia search lkm knowledge "<broad query 1>" --reasoning-only --limit 10 \
  --out "$RUN/searches/01.json"
gaia search lkm knowledge "<broad query 2>" --reasoning-only --limit 10 \
  --out "$RUN/searches/02.json"
gaia search lkm knowledge "<broad query 3>" --reasoning-only --limit 10 \
  --out "$RUN/searches/03.json"
```

Default `gaia search lkm knowledge` recalls both claim and question nodes. That
can be useful for later question discovery, but it will produce question-heavy
shallow source packages when `explore` materializes sources. `--reasoning-only`
is the claim+conclusion retrieval shape for reasoning-backed landscape evidence
and candidate-relation-ready materialization.

If the reasoning-only landscape misses obvious coverage gaps, run a separate
supplemental broad/question discovery search and keep it labeled separately in
`$RUN/searches/`; do not let that supplemental pass silently define the
claim-materialized evidence surface.

Record each search with `gaia research trace record --kind search`; see
`benchmark-trace.md`.

Searches may run in parallel. Record their timing rows after the searches
finish. `trace.jsonl` remains the source of truth; rebuild derived
`benchmark.json` once at the end with `gaia research trace summarize`.

Then run scan:

```bash
gaia research explore "$PKG" --mode scan \
  --search-json "$RUN/searches/01.json" \
  --search-json "$RUN/searches/02.json" \
  --search-json "$RUN/searches/03.json" \
  --trace-dir "$TRACE"
```

## Focus Synthesis

Print the contract and use it as the only schema source:

```bash
gaia research contract focus --language "$LANG" > "$RUN/analysis/focus-contract.json"
```

Read `focus-analysis-prompt.md`, produce `$RUN/analysis/focus-analysis.json`,
and record LLM/provider usage with `gaia research trace record --kind llm` if
available.

Validate and sync:

```bash
gaia research focus "$PKG" \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --analysis-json "$RUN/analysis/focus-analysis.json" \
  --language "$LANG" \
  --trace-dir "$TRACE"
```

## Targeted Expand

Use focus gaps and suggested queries:

```bash
gaia search lkm knowledge "<targeted query>" --reasoning-only --limit 10 \
  --out "$RUN/searches/targeted-01.json"

gaia research expand "$PKG" \
  --focus <focus-id-or-question-binding> \
  --search-json "$RUN/searches/targeted-01.json" \
  --trace-dir "$TRACE"
```

For targeted evidence expansion that should become package claim endpoints,
keep `--reasoning-only` on the targeted search.

Continue expanding while coverage gaps block assessment or query novelty is
still high.

If stop criteria still reports `expand_focus` because an older focus artifact
contains stale `needs_expand` focuses, synthesize a post-expand focus artifact
from the expanded landscape. Use `--dry-run` only when you need to inspect the
planned package/inquiry writes without applying them.

## Assessment

Print the contract:

```bash
gaia research contract assess --language "$LANG" > "$RUN/analysis/assess-contract.json"
```

Read `assess-analysis-prompt.md`, produce `$RUN/analysis/assess-analysis.json`,
and record LLM/provider usage when available.

Validate and sync:

```bash
gaia research assess "$PKG" \
  --focus <focus-id-or-question-binding> \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --landscape "$PKG/.gaia/research/landscapes/<expand>.json" \
  --analysis-json "$RUN/analysis/assess-analysis.json" \
  --trace-dir "$TRACE"
```

Only during assessment, when the focus requires it, consider deep evidence:

```text
--materialize-paper <selected_lkm_paper_id>
--materialize-paper-from-claim <selected_lkm_claim_id>
--materialize-chain <selected_lkm_claim_id>
```

## Final Report And Stop Criteria

Keep intermediate focus, assessment, and stop outputs as JSON audit artifacts.
Do not render `focus_report.md`, `assessment_report.md`, or `stop_report.md`
as part of the normal live-run protocol. The reader-facing Markdown surface is
the final academic evidence report written at `$RUN/trace/final_report.md`
after the completed analyses have been recorded in `trace.jsonl`.

Evaluate stop criteria:

```bash
gaia research stop "$PKG" \
  --focus-artifact "$PKG/.gaia/research/focuses/<focuses>.json" \
  --assessment "$PKG/.gaia/research/assessments/<assessment>.json" \
  --landscape "$PKG/.gaia/research/landscapes/<latest>.json" \
  --previous-landscape "$PKG/.gaia/research/landscapes/<previous>.json" \
  --out "$RUN/trace/stop.json" \
  --trace-dir "$TRACE"

gaia research trace summarize "$PKG" --trace-dir "$TRACE"
```

If stop criteria recommends expand or assess another focus, continue unless the
user requested a bounded single-pass evaluation.

Close inquiry obligations only after the assessment or post-expand focus
artifact explicitly resolves or defers them. Close them sequentially with
`gaia inquiry obligation close`; the inquiry state file is not safe for
parallel mutation.

## Required Artifacts

Produce or preserve:

- `$RUN/searches/*.json`
- `$RUN/trace/evaluation_trace.md`
- `$RUN/trace/benchmark.json`
- `$RUN/trace/trace.jsonl`
- `$RUN/analysis/field_map_analysis.json` or `field_map_analysis.output.json`
- `.gaia/research/field_maps/*.json`
- `$RUN/searches/coverage-*.json` when field-map buckets require expansion
- `.gaia/research/evidence/selected-evidence-*.json`
- `$RUN/analysis/focus-contract.json`
- `$RUN/analysis/focus-analysis.json`
- `$RUN/analysis/assess-contract.json`
- `$RUN/analysis/assess-analysis.json`
- `$RUN/analysis/report_plan.output.json`
- `$RUN/analysis/report_section_*.output.json`
- `$RUN/analysis/report_stitch.output.json`
- `$RUN/trace/stop.json`
- `$RUN/trace/final_report.md`
- `.gaia/research/landscapes/*.json`
- `.gaia/research/focuses/*.json`
- `.gaia/research/assessments/*.json`
- `.gaia/research/events.jsonl`
- `.gaia/inquiry/state.json`

Finish with:

```bash
gaia build check "$PKG"
```

If a freshly scaffolded research package contains only `question(...)` and
`note(...)` declarations, `gaia build check` may report no checkable Gaia
claims. After assessment review, add at most one narrow, exported
assessment-scoped `claim(...)` that states the reviewed conclusion. Do not use
this as a shortcut to promote individual evidence relations.
