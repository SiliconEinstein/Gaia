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

## Breadth-First Explore

Run several independent query families before choosing a focus. Preserve every
raw search JSON:

```bash
gaia search lkm knowledge "<broad query 1>" --limit 10 \
  --out "$RUN/searches/01.json"
gaia search lkm knowledge "<broad query 2>" --limit 10 \
  --out "$RUN/searches/02.json"
gaia search lkm knowledge "<broad query 3>" --limit 10 \
  --out "$RUN/searches/03.json"
```

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

For artifact-only benchmark mode, add:

```text
--artifact-only --no-materialize-sources
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
gaia search lkm knowledge "<targeted query>" --limit 10 \
  --out "$RUN/searches/targeted-01.json"

gaia research expand "$PKG" \
  --focus <focus-id-or-question-binding> \
  --search-json "$RUN/searches/targeted-01.json" \
  --trace-dir "$TRACE"
```

For artifact-only benchmark mode, add:

```text
--artifact-only --no-materialize-sources
```

Continue expanding while coverage gaps block assessment or query novelty is
still high.

If stop criteria still reports `expand_focus` because an older focus artifact
contains stale `needs_expand` focuses, synthesize a post-expand focus artifact
from the expanded landscape. In artifact-only evals, run this update with
`gaia research focus --artifact-only` so it refreshes readiness without adding
new package questions or inquiry obligations.

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

Do not use deep materialization in artifact-only benchmark mode unless the user
explicitly overrides that constraint.

## Reports And Stop Criteria

Render focus and assessment artifacts:

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
- `$RUN/analysis/focus-contract.json`
- `$RUN/analysis/focus-analysis.json`
- `$RUN/analysis/assess-contract.json`
- `$RUN/analysis/assess-analysis.json`
- `$RUN/trace/focus_report.md`
- `$RUN/trace/assessment_report.md`
- `$RUN/trace/stop.json`
- `$RUN/trace/stop_report.md`
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
