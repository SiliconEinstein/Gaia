# Research Loop Live Eval

This guide separates two evaluation modes:

- **Fixture regression** checks schemas, CLI wiring, provenance, and validation.
- **Live quality eval** checks whether the workflow produces useful research
  judgment on real LKM retrieval results.

Do not replace live quality eval with fixtures. Fixtures are stable and cheap;
live runs reveal retrieval latency, hydration failures, query planning problems,
focus quality, and assessment depth.

## Directory layout

Use a fresh package-local run directory. Do not place live run artifacts under
`/private/tmp` or another OS-cleaned scratch location unless the run is truly
throwaway:

```bash
PKG=<path-to-existing-or-new-topic-gaia>
RUN=$PKG/.gaia/research/runs/<topic>-$(date -u +%Y%m%dT%H%M%SZ)
TRACE=$RUN/trace
mkdir -p "$RUN/searches" "$RUN/analysis" "$RUN/trace"
```

Every traced research command appends an execution row to
`$RUN/trace/trace.jsonl`. Use `gaia research trace record` to record non-CLI
steps such as LLM analysis generation, raw LKM searches timed by the agent,
retries, or other external work. After the final trace write, run
`gaia research trace summarize` once to rebuild `$RUN/trace/benchmark.json` as
the derived summary.

If you need a clean run, delete only this run directory.

## Package setup

```bash
gaia pkg scaffold --target "$PKG" --name <topic>-gaia --namespace <topic>
gaia author question "<中文研究问题>" \
  --target "$PKG" \
  --dsl-binding-name <binding> \
  --title "<标题>" \
  --export \
  --no-check
gaia research status "$PKG"
```

## Breadth-first scan

Run multiple query families and preserve raw JSON:

```bash
gaia search lkm knowledge "<broad query 1>" --limit 10 --out "$RUN/searches/01.json"
gaia search lkm knowledge "<broad query 2>" --limit 10 --out "$RUN/searches/02.json"
gaia search lkm knowledge "<broad query 3>" --limit 10 --out "$RUN/searches/03.json"

/usr/bin/time -p gaia research explore "$PKG" --mode scan \
  --search-json "$RUN/searches/01.json" \
  --search-json "$RUN/searches/02.json" \
  --search-json "$RUN/searches/03.json" \
  --trace-dir "$TRACE"
```

Record:

- query count;
- raw result count;
- paper lead count;
- item count;
- timeout/retry behavior.

## Focus synthesis

Print the contract:

```bash
gaia research contract focus --language zh > "$RUN/analysis/focus-contract.json"
```

Ask the agent/LLM to read the scan landscape and write:

```text
$RUN/analysis/focus-analysis.json
```

Use the printed contract as the schema source. The active agent/LLM prompt
should be written for the current run and should not rely on old trace prompts.

Validate and write the artifact:

```bash
gaia research focus "$PKG" \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --analysis-json "$RUN/analysis/focus-analysis.json" \
  --language zh \
  --trace-dir "$TRACE"
```

If the focus analysis was produced by an external agent or LLM provider, append
the token/time usage to the same trace directory:

```bash
gaia research trace record "$PKG" \
  --trace-dir "$TRACE" \
  --step llm.focus_analysis \
  --kind llm \
  --mode fast_package_native \
  --model <model-name> \
  --input-tokens <n> \
  --output-tokens <n> \
  --wall-seconds <seconds> \
  --input-file "$PKG/.gaia/research/landscapes/<scan>.json" \
  --output-file "$RUN/analysis/focus-analysis.json"
```

Review:

- Are there 3-8 meaningful focuses?
- Are they real assessable questions, not query rewrites?
- Are the top accepted focuses the right 1-3 questions to write as package
  `question(...)` declarations?
- Does each focus have evidence refs?
- Are `needs_expand` focuses paired with targeted queries?

## Targeted expand

Use focus-generated queries:

```bash
gaia search lkm knowledge "<targeted query>" --limit 10 --out "$RUN/searches/07.json"

/usr/bin/time -p gaia research expand "$PKG" \
  --focus <focus-id> \
  --search-json "$RUN/searches/07.json" \
  --trace-dir "$TRACE"
```

Stop when coverage is enough to classify support, opposition, qualification,
and undercutting for the selected focus.

## Assessment

Print the contract:

```bash
gaia research contract assess --language zh > "$RUN/analysis/assess-contract.json"
```

Ask the agent/LLM to write:

```text
$RUN/analysis/assess-analysis.json
```

Use the printed contract as the schema source. The active agent/LLM prompt
should ask for a review-grade Chinese synthesis while preserving grounded refs.

The analysis must include:

- typed relations;
- grounded source refs;
- review-grade Chinese synthesis;
- limitations;
- next queries;
- candidate obligations.

Validate and write the artifact:

```bash
gaia research assess "$PKG" \
  --focus <focus-id> \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --landscape "$PKG/.gaia/research/landscapes/<expand>.json" \
  --analysis-json "$RUN/analysis/assess-analysis.json" \
  --trace-dir "$TRACE"
```

Append the assessment LLM usage in the same way:

```bash
gaia research trace record "$PKG" \
  --trace-dir "$TRACE" \
  --step llm.assess_analysis \
  --kind llm \
  --mode fast_package_native \
  --model <model-name> \
  --input-tokens <n> \
  --output-tokens <n> \
  --wall-seconds <seconds> \
  --input-file "$PKG/.gaia/research/landscapes/<scan>.json" \
  --input-file "$PKG/.gaia/research/landscapes/<expand>.json" \
  --output-file "$RUN/analysis/assess-analysis.json"
```

Record relation type counts. A healthy assess run should usually have a mix of
`supports`, `opposes`, `qualifies`, and `undercuts`, not only
`background_for`. When relations include concrete package claim refs, confirm
that candidate relation scaffolds were written; otherwise they should remain
in inquiry hypotheses plus the assessment review note.

## Reports

Write:

```text
$RUN/trace/evaluation_trace.md
$RUN/trace/assessment_review_zh.md
```

The trace should distinguish:

- CLI-generated artifacts;
- agent/LLM-generated analysis JSON;
- manual interpretation added by the agent;
- failed live queries and retries.

The Chinese review should read as a compact scholarly review. It should not be
only a command transcript.

Render validated artifacts to Markdown:

```bash
gaia research report "$PKG" \
  --artifact "$PKG/.gaia/research/focuses/<focuses>.json" \
  --out "$RUN/trace/focus_report.md" \
  --trace-dir "$TRACE"

gaia research report "$PKG" \
  --artifact "$PKG/.gaia/research/assessments/<assessment>.json" \
  --out "$RUN/trace/assessment_report.md" \
  --trace-dir "$TRACE"
```

Evaluate stop criteria:

```bash
gaia research stop "$PKG" \
  --focus-artifact "$PKG/.gaia/research/focuses/<focuses>.json" \
  --assessment "$PKG/.gaia/research/assessments/<assessment>.json" \
  --landscape "$PKG/.gaia/research/landscapes/<latest>.json" \
  --previous-landscape "$PKG/.gaia/research/landscapes/<previous>.json" \
  --out "$RUN/trace/stop.json" \
  --trace-dir "$TRACE"

gaia research report "$PKG" \
  --artifact "$RUN/trace/stop.json" \
  --out "$RUN/trace/stop_report.md" \
  --trace-dir "$TRACE"

gaia research trace summarize "$PKG" --trace-dir "$TRACE"
```

The stop artifact is a heuristic checkpoint, not a substitute for research
judgment. It summarizes:

- coverage;
- relation mix;
- unresolved obligations;
- query novelty.

## Benchmark modes

Run the same query set in three modes when you need to compare overhead:

```bash
# A. Artifact-only baseline: no inquiry/source sync, no shallow source package.
gaia research explore "$PKG" --mode scan \
  --search-json "$RUN/searches/01.json" \
  --artifact-only \
  --no-materialize-sources \
  --trace-dir "$TRACE"
```

```bash
# B. Fast package-native default: shallow source packages plus inquiry sync.
gaia research explore "$PKG" --mode scan \
  --search-json "$RUN/searches/01.json" \
  --trace-dir "$TRACE"
```

```bash
# C. Deep assessment: explicitly materialize paper/chain evidence.
gaia research assess "$PKG" \
  --focus <focus-id> \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --analysis-json "$RUN/analysis/assess-analysis.json" \
  --materialize-chain <claim_id> \
  --trace-dir "$TRACE"
```

`trace.jsonl` records append-only step events with start/end timestamps, actor,
inputs, outputs, metrics, model, and token usage when available.
`benchmark.json` is a derived summary of step timing and structural metrics,
rebuilt from `trace.jsonl` with `gaia research trace summarize`.
Token usage is recorded only when the agent or caller appends it with
`gaia research trace record`, because current Gaia research commands validate
and sync artifacts but do not call an LLM provider directly.

For meeting review, a live run can also be bundled into a self-contained HTML
viewer. Example:

[Hubble tension trace viewer](research-loop-evals/hubble-tension-v2/trace-viewer.html)

## Verification

Run:

```bash
gaia build check "$PKG"
```

For repository regression:

```bash
uv run pytest tests/gaia/test_research_focus.py tests/gaia/test_research_assessment.py tests/cli/test_research.py -q
```

## Live V2 Example: Deconfined Criticality

Historical run directory pattern, now superseded by package-local runs:

```text
<PKG>/.gaia/research/runs/deconfined-criticality-v2
```

Trace:

```text
<PKG>/.gaia/research/runs/deconfined-criticality-v2/trace/evaluation_trace_v2.md
```

This run verifies that the v2 workflow is not an aspirin-specific prompt hack.
The focus and assessment prompts produced DQCP-native artifacts around:

- continuous DQCP versus weak first-order transition;
- emergent SO(5)/O(4)/U(1) symmetry and anisotropy;
- NCCP1/easy-plane/QED3 duality and anomaly constraints;
- microscopic model dependence.

Observed live metrics:

- broad scan: 4 query batches, 40 raw results, 33 paper leads;
- targeted expand: 3 query batches, 30 raw results, 24 paper leads;
- expand novelty: 17 new paper leads, ratio 0.7083;
- focus synthesis: 4 focuses, 3 coverage gaps;
- assessment: 70 items, 11 typed relations;
- relation mix: supports 3 / opposes 3 / qualifies 3 / undercuts 2;
- candidate obligations: 3;
- stop recommendation: `expand_focus`.

Important live pitfalls:

- hybrid and semantic LKM search timed out for the initial broad query;
- lexical search with explicit domain anchors was more reliable;
- `SO5` queries can retrieve chemistry radical literature, so future searches
  should anchor with `deconfined`, `NCCP1`, `Neel`, `VBS`, or `DQCP`;
- current stop criteria are loop-level, not focus-local; future work may add a
  `--focus-id` option.
