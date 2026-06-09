# Research Run Orchestrator Design

## Context

Recent live research-loop runs show that `gaia research explore`, `focus`,
`expand`, `assess`, `report`, `stop`, and `trace summarize` are individually
fast. Most elapsed time is spent in the agent's cognitive path: reading
contracts, choosing phase commands, writing analysis JSON, validating grounded
refs, recovering from materialization failures, and translating stop output into
handoff prose.

The medium-term goal is to make the research loop a CLI-owned pipeline so an
agent or UI can supervise instead of manually orchestrating every step.

## Goals

- Add a single `gaia research run` entry point for package-local research runs.
- Make the run observable by UI clients through structured files and optional
  JSON-line stdout.
- Define stable phase, event, state, and checkpoint shapes while moving search
  and fixed-shape analysis generation into the CLI path.
- Preserve existing package-native commands as the implementation substrate.
- Keep `trace.jsonl` the benchmark source of truth; run-state events are for UI
  orchestration and resume.

## Non-Goals

- Do not build the long-term daemon/state-machine scheduler in the first slice.
- Do not replace `gaia research explore/focus/expand/assess`; the run command
  composes them.
- Do not require a specific hosted LLM provider in the first slice; use a
  command-provider adapter so the CLI owns orchestration while provider choice
  remains external.
- Do not make UI clients parse human stdout.

## Medium-Term Shape

The target command is:

```bash
gaia research run "$PKG" \
  --topic "deconfined quantum critical point evidence assessment" \
  --mode fast-package-native \
  --language zh \
  --profile evidence-assessment \
  --json-stream
```

The command creates a package-local run directory:

```text
$PKG/.gaia/research/runs/<slug>-<utcstamp>/
  state.json
  events.ndjson
  checkpoints/
  searches/
  analysis/
  trace/
```

The run envelope always records state, events, checkpoints, searches, analysis,
and trace files. With `--analysis-provider litellm` and no search input, the
command runs a fixed `query_plan` LLM call, executes live broad search from that
plan, then uses focus `suggested_queries` for targeted search. With checkpoint
or file-provider modes, missing inputs pause the run at the next checkpoint.
`gaia build check "$PKG"` remains an explicit caller-side closed-loop
verification step for now.

The first executable slice also supports a file-provider loop:

```bash
gaia research run "$PKG" \
  --topic "aspirin primary prevention evidence" \
  --mode artifact-only \
  --search-json "$RUN/searches/broad.json" \
  --focus-analysis-json "$RUN/analysis/focus-analysis.json" \
  --targeted-search-json "$RUN/searches/targeted.json" \
  --focus elderly_net_benefit \
  --assess-analysis-json "$RUN/analysis/assess-analysis.json"
```

When the file-provider inputs are complete, the command executes scan,
field-map induction, optional coverage expansion, focus, optional targeted
expand, assess, stop, final report, and trace summary. When an input is
missing, it writes the next checkpoint and leaves `state.json` at
`status=waiting_for_input`.

Manual replay can still provide fixed live-search inputs, but this is not the
default benchmark path and should not appear in clean live-run prompts unless
the user explicitly asks to replay fixed inputs.

Live search writes normalized Gaia search JSON to `searches/broad-NN.json` and
`searches/targeted-NN.json`, appends `kind=search` trace rows, and emits
`search.started` / `search.completed` events. Command providers receive
`GAIA_RESEARCH_PHASE`, `GAIA_RESEARCH_INPUT`, `GAIA_RESEARCH_OUTPUT`, and
`GAIA_RESEARCH_RUN_DIR`; they write contract-shaped JSON to the output path.
The run records provider calls as `kind=llm` trace rows and emits
`provider.started` / `provider.completed` events.

For in-process model calls, the run command supports a topic-only LiteLLM
provider path:

```bash
uv sync --extra llm

gaia research run "$PKG" \
  --topic "deconfined quantum critical point evidence assessment" \
  --mode fast-package-native \
  --analysis-provider litellm \
  --model "openai/deepseek-v4-flash" \
  --env-file /Users/dp/Projects/gaia-project/Gaia/.env
```

`--focus-model` and `--assess-model` can override the shared `--model`.
If no model flag is passed, `GAIA_RESEARCH_LLM_MODEL` is used. `--env-file`
loads dotenv-style `KEY=VALUE` files before search/provider calls; shell
environment variables win on conflicts, and `GAIA_RESEARCH_ENV_FILE` can provide
a default path. LiteLLM is an optional extra rather than a default dependency.
Normal live runs should not pass `--llm-max-tokens`; compact phase prompts and
schema validation should keep outputs bounded without caller-side truncation.
The provider sets `LITELLM_LOCAL_MODEL_COST_MAP=True`, suppresses LiteLLM debug
output, disables cost calculation, writes `analysis/<phase>.input.json` and
`analysis/<phase>.output.json`, and records token/request metadata when the
response exposes it. For the DP internal OpenAI-compatible gateway, use model
names like `openai/deepseek-v4-flash` with `OPENAI_API_BASE` and
`OPENAI_API_KEY` in the env file.

The LiteLLM provider should reduce structure failures before retrying by:

- passing `response_format={"type": "json_object"}` by default;
- using phase-specific JSON-only prompts and compact output-shape hints;
- writing `analysis/<phase>.raw.txt` before parsing provider output;
- recording failed provider calls in `trace.jsonl` with `status=failed`, model,
  token usage, raw path, and error metadata.

This means UI clients can display both the human timeline (`events.ndjson`) and
the raw failed model output without guessing what happened.

## Layering Model

Gaia should support two execution styles without forking the implementation:

1. **Rigid fast workflows**: `gaia research run` owns the phase graph, event
   stream, state snapshots, checkpoints, trace rows, and final summary. This is
   the path for production UI flows, repeated live runs, large graph sweeps, and
   benchmarks where predictability and latency matter more than agent freedom.
2. **Atomic agent primitives**: `gaia search lkm`, `gaia research explore`,
   `gaia research focus`, `gaia research assess`, materialization helpers, and
   future provider subcommands remain callable directly. Flexible agents use
   these when they need unusual branching, manual evidence repair, or
   opportunistic exploration.
3. **Shared execution core**: both styles use the same search adapters,
   provider adapters, materializers, artifact builders, sync logic, and trace
   writer. The rigid workflow is an orchestrator over these primitives; it is
   not a second implementation.

The practical boundary is: put deterministic, latency-sensitive, repeatedly
measured work in the machine path; expose each machine step as a small command
or provider interface so agents can still take over at checkpoints or compose
custom paths. UI clients should read `state.json` for the current snapshot,
`events.ndjson` for progress, checkpoint JSON for user choices, and
`trace/benchmark.json` for performance profiles.

## UI-Facing Files

### `state.json`

`state.json` is a compact current snapshot for dashboards and resume:

```json
{
  "schema_version": 1,
  "run_id": "dqcp-20260608T143226Z",
  "status": "waiting_for_input",
  "phase": "query_plan",
  "mode": "fast-package-native",
  "profile": "evidence-assessment",
  "language": "zh",
  "topic": "deconfined quantum critical point evidence assessment",
  "package": {"path": "...", "project_name": "...", "import_name": "..."},
  "run_dir": ".../.gaia/research/runs/dqcp-20260608T143226Z",
  "trace_dir": ".../.gaia/research/runs/dqcp-20260608T143226Z/trace",
  "pending_checkpoint": ".../checkpoints/query_plan.request.json",
  "artifacts": {},
  "metrics": {}
}
```

### `events.ndjson`

`events.ndjson` is append-only and intended for UI timelines:

```json
{"schema_version":1,"type":"run.created","phase":"setup","ts":"...","run_id":"..."}
{"schema_version":1,"type":"checkpoint.created","phase":"query_plan","ts":"...","path":"..."}
{"schema_version":1,"type":"run.waiting_for_input","phase":"query_plan","ts":"..."}
{"schema_version":1,"type":"search.completed","phase":"live_search","ts":"...","query":"..."}
{"schema_version":1,"type":"provider.completed","phase":"focus_analysis","ts":"...","output":"..."}
```

When `--json-stream` is set, the same events are printed to stdout as NDJSON.

### Checkpoints

Checkpoints are explicit interaction requests. The first checkpoint is
`query_plan`:

```json
{
  "schema_version": 1,
  "type": "checkpoint.query_plan",
  "checkpoint_id": "query_plan_001",
  "phase": "query_plan",
  "prompt": "Review or edit broad query families before live search.",
  "choices": [
    {"id": "continue", "label": "Continue with defaults", "recommended": true}
  ],
  "default_action": {"action": "continue", "queries": []}
}
```

Later checkpoints should include `focus_choice`, `expand_plan`,
`assessment_review`, and `stop_decision`.

## Modes

- `fast-package-native`: do not pass `--artifact-only`; keep default shallow
  source materialization for `explore` and `expand`.
- `artifact-only`: pass `--artifact-only`; for `explore` and `expand`, also pass
  `--no-materialize-sources`.

The run state records these decisions so a UI can show whether package source
will be mutated.

## Phase Plan

The medium-term pipeline phases are:

1. `setup`: validate package and create run directories.
2. `query_plan`: fixed LLM call or user checkpoint for broad queries.
   With `--analysis-provider litellm`, omitting `--query` and
   `--search-json` triggers this call automatically and persists
   `analysis/query_plan.output.json`.
3. `search_broad`: execute searches, preserve raw JSON, append trace rows.
4. `explore_scan`: run package-native or artifact-only scan.
5. `field_map_analysis`: fixed LLM call inducing a review taxonomy from
   primary broad-search evidence.
6. `field_map_sync`: write `.gaia/research/field_maps/*.json`.
7. `search_coverage`: execute field-map recommended expansions for thin or
   missing review buckets.
8. `explore_coverage`: build coverage landscape and sync/materialize if needed.
9. `focus_analysis`: fixed LLM call producing `focus-analysis.json` from the
   scan, coverage landscape, and field map.
10. `focus_sync`: run `gaia research focus`.
11. `expand_plan`: focus-output `suggested_queries` or user-supplied targeted
   queries.
12. `search_targeted`: execute targeted searches. When neither
   `--targeted-query` nor `--targeted-search-json` is supplied, the runner
   takes the selected focus's `suggested_queries` plus coverage-gap suggested
   queries from `focus_analysis`.
13. `explore_expand`: run targeted expand.
14. `evidence_select`: build a compact selected-evidence packet from the
    selected focus and available landscapes.
15. `deep_expand`: materialize only selected paper graphs or reasoning chains
    needed to ground assessment.
16. `assess_analysis`: fixed LLM call producing `assess-analysis.json` from
    selected evidence rather than full landscapes.
17. `assess_sync`: run `gaia research assess`.
18. `report_plan`: fixed LLM call producing the final article outline from the
    field map, selected evidence, and assessment judgment.
19. `report_section`: fixed LLM calls writing one grounded section at a time.
20. `report_stitch`: fixed LLM call stitching sections into the final scholarly
    report without re-assessing evidence.
21. `reports_stop`: write stop JSON and one final trace-backed evidence report.
22. `summarize_check`: run one final trace summary; callers still run build
    check explicitly.

The first envelope-only slice stops at `query_plan` with
`status=waiting_for_input`. The litellm provider can continue from a topic-only
invocation because broad queries and targeted queries are generated in fixed
machine-readable calls. The file-provider and command-provider slices can
continue through trace summary when required inputs are supplied or generated,
or pause at `focus_analysis` / `assess_analysis` when provider outputs are
missing.

Coverage gaps and ordinary assessment `needs_more_evidence` items are deferred
gaps by default. They remain visible in artifacts and sync payloads as
`obligations_deferred`, but they do not become open inquiry obligations unless
the provider explicitly marks an item actionable/blocking. Stop criteria also
tracks how many latest-landscape paper leads are grounded in assessment refs;
high paper novelty with low assessment grounding should lead to review,
selected deep materialization, or explicit deferral rather than automatic
expansion.

## Error Handling

Later execution phases should write a `run.failed` event and update
`state.json` with `status=failed` for validation errors or failed phase
execution. Existing subcommands remain responsible for their own detailed
diagnostics.

## Testing Strategy

- CLI help exposes `gaia research run`.
- Starting a run writes `state.json`, `events.ndjson`, `trace/`, `analysis/`,
  `searches/`, and a query-plan checkpoint.
- `--json-stream` emits machine-readable NDJSON matching the persisted events.
- `--mode artifact-only` and `--mode fast-package-native` are recorded
  distinctly in state.
- Topic-only `litellm` runs execute `query_plan`, broad live search,
  `field_map_analysis`, optional field-map coverage search, focus analysis,
  suggested-query targeted live search, selected-evidence/deep expansion,
  assessment, sectioned report writing, stop, final evidence report, and trace
  summary without caller-supplied queries.
- `--analysis-provider command` records provider input/output files and `llm`
  trace rows while preserving the same downstream sync path as file-provider
  inputs.
