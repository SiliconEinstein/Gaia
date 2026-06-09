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

Before choosing focuses, ask the agent/LLM to read the broad scan landscape and
write a review field map:

```bash
gaia research contract field_map --language zh > "$RUN/analysis/field-map-contract.json"
```

```text
$RUN/analysis/field_map_analysis.json
```

The field map should infer the review taxonomy from primary retrieved evidence:
model families, methods, diagnostics, theory constraints, experimental systems,
controversy axes, and review-coverage gaps. If it recommends high-value
coverage searches for thin or missing buckets, run those searches and add the
coverage landscape before focus synthesis.

Then ask the agent/LLM to read the scan landscape, any coverage landscape, and
the field map, and write:

```text
$RUN/analysis/focus-analysis.json
```

Use the printed contract as the schema source. The active agent/LLM prompt
should be written for the current run and should not rely on old trace prompts.

Validate and write the artifact:

```bash
gaia research focus "$PKG" \
  --landscape "$PKG/.gaia/research/landscapes/<scan>.json" \
  --landscape "$PKG/.gaia/research/landscapes/<coverage>.json" \
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

Keep validated focus, assessment, and stop artifacts as JSON audit records.
The normal live-run protocol writes one reader-facing Markdown report at the
end: `$RUN/trace/final_report.md`. That report synthesizes all traced
assessment JSON artifacts into an academic evidence review rather than a
workflow transcript.

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

## Verification

Run:

```bash
gaia build check "$PKG"
```

For repository regression:

```bash
uv run pytest tests/gaia/test_research_focus.py tests/gaia/test_research_assessment.py tests/cli/test_research.py -q
```
