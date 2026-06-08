# Benchmark And Trace Recording

Use this reference only when benchmark/live eval mode needs timing, token, retry,
or quality traces.

## Concept

Benchmarking is an observability layer. It should not change the scientific
meaning of `explore`, `focus`, `expand`, `assess`, `report`, `stop`, or
`promote`.

Use:

```bash
TRACE=$RUN/trace
```

Every `gaia research` command that supports it should receive:

```text
--trace-dir "$TRACE"
```

`trace.jsonl` is the source of truth: it records append-only step events with
start/end timestamps, actor, inputs, outputs, metrics, model, and token usage
when available. `benchmark.json` is a derived summary view with step counts,
wall time, modes, and token totals.

`benchmark.json` can be re-derived from `trace.jsonl` with:

```bash
gaia research trace summarize "$PKG" --trace-dir "$TRACE"
```

`summary.total_wall_seconds` is the sum of steps explicitly recorded in the
trace, not end-to-end agent elapsed time. Record run-envelope start/end time
separately in `evaluation_trace.md`, and explain any uninstrumented time spent
reading contracts, analyzing landscapes, writing JSON, recovering from errors,
or repairing artifacts.

Treat `trace.jsonl` as the source of truth and `benchmark.json` as a
materialized view. Trace append operations are serialized by the CLI, so
independent external search timings may be recorded after parallel searches.
Run `gaia research trace summarize` once after the final trace append and use
`benchmark.summary.steps == wc -l trace.jsonl` as the consistency check.

## Recording LKM Search

`gaia search lkm` is outside `gaia research`, so record it explicitly:

```bash
gaia research trace record "$PKG" \
  --trace-dir "$TRACE" \
  --step search.lkm.broad_01 \
  --kind search \
  --mode external \
  --wall-seconds <seconds> \
  --output-file "$RUN/searches/01.json"
```

When a search fails and is retried, record both the failed attempt in
`evaluation_trace.md` and the successful or failed external step here if timing
is available. Never expose credentials or signed URLs.

Parallel LKM searches are acceptable. Record their
`gaia research trace record --kind search` rows after the searches finish, then
run `gaia research trace summarize` after the last trace append. Use absolute
output paths so later trace readers can distinguish package-local artifacts
from accidental duplicates.

## Recording LLM Analysis

If a provider exposes token usage, append it:

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

Use `llm.assess_analysis` for assessment analysis. If token usage is not
available, still record wall time and input/output files when known.
When wall time is not known, omit token counts and do not invent timing. Instead
put the analysis step in `evaluation_trace.md` and, if useful, append a
zero-wall LLM marker with inputs/outputs/model so the trace shows provenance
without pretending to measure hidden work.

## Evaluation Trace Template

Write `$RUN/trace/evaluation_trace.md` as a readable audit log. Keep command
transcripts concise; do not paste credentials, huge JSON blobs, or old traces.

Suggested sections:

```markdown
# Evaluation Trace

## Run Envelope

- Topic:
- Language:
- Package:
- Run directory:
- Mode:
- Trace directory:
- Benchmark summary:
- Start:
- End:

## End-to-End Time Accounting

| Bucket | Approximate time | Counted in benchmark? | Notes |
| --- | ---: | --- | --- |
| Real searches |  | yes | Sum of explicit `search` rows. |
| Gaia CLI commands |  | yes | Internal command wall time, not whole agent turn time. |
| Agent analysis and JSON writing |  | no, unless separately measured | Focus/assessment reasoning may dominate elapsed time. |
| Recovery and artifact repair |  | no or partially | Record path/state/manifest repairs here. |

## CLI Artifacts

| Time | Step | Command summary | Outputs | Wall time | Notes |
| --- | --- | --- | --- | --- | --- |

## Raw LKM Searches

| Time | Query family | Query | Output JSON | Raw results | Paper leads | Retry notes |
| --- | --- | --- | --- | --- | --- | --- |

## Agent / LLM Analysis

| Time | Step | Model | Inputs | Output | Tokens | Wall time | Quality note |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Failures And Retries

| Time | Operation | Failure | Recovery | Residual risk |
| --- | --- | --- | --- | --- |

## Path Hygiene Checks

| Check | Result |
| --- | --- |
| Requested package path |  |
| Correct run directory |  |
| Removed accidental parent-checkout or nested package paths |  |
| Durable `/private/tmp` artifacts |  |
| Open inquiry obligations |  |

## Subjective Quality Notes

- Retrieval coverage:
- Focus quality:
- Assessment depth:
- Citation grounding:
- Candidate relation quality:
- Remaining obligations:

## Final Counts

- Search queries:
- Raw results:
- Paper leads:
- Focuses:
- Relations:
- Candidate obligations:
- Candidate relations written:
- Total wall-clock time:
- Total token usage:
```

## Quality Notes

Record subjective notes separately from measured timing. Useful categories:

- retrieval coverage and query family diversity;
- timeout/failure/retry behavior;
- whether search rank appeared misleading;
- whether focus synthesis narrowed too early;
- whether assessment produced relation diversity;
- whether candidate relations were absent for good reasons or because refs were
  too weak;
- unresolved obligations and why they were resolved, deferred, or left open.
