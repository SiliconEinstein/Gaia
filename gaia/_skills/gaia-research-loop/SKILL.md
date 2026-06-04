---
name: gaia-research-loop
description: |
  Use when running or evaluating Gaia research workflows that explore a field,
  synthesize focuses, expand around coverage gaps, assess evidence for a
  focus, promote mature scaffolds, or produce a live research trace. Applies to
  `gaia research`, LKM-backed literature discovery, package/inquiry-centric
  research state, and review-quality Chinese or English mini-reviews.
---

# Gaia Research Loop

## Intent

Run a package-native research loop without inventing a second research data
model. The canonical state lives in:

- Gaia package source: `question(...)`, `note(...)`,
  `claim(...)` / `note(...)` from shallow source packages,
  `candidate_relation(...)`, `materialize(...)`.
- Gaia inquiry state: active focus, hypotheses, obligations, tactic log.
- `.gaia/research`: trace, cache, reports, timing, and audit artifacts only.

Use `gaia research` as the thin workflow layer. Use the printed CLI contracts as
the JSON schema source; do not copy or freestyle schemas in the skill.

## Hard Boundaries

- Start broad. Do not deep-pull papers during initial Explore or Expand.
- During Explore and Expand, default to shallow source packages from search
  items; reserve full paper/chain pulls for focused assessment.
- Do not use `gaia-lkm-explore` for this workflow unless the user explicitly asks
  for legacy comparison.
- Do not treat search rank as confidence.
- Do not write formal `claim(...)`, `derive(...)`, `contradict(...)`, or
  `equal(...)` during `assess`; write scaffold state first.
- Write `candidate_relation(...)` only when the assessment relation includes
  concrete package claim refs.
- Keep raw LKM search JSON. It is the source for later audit.
- Never write access keys into package files, traces, reports, commits, or docs.

## Minimal Task Envelope

At the start of a run, create or infer this envelope:

```text
topic: <research topic>
language: <zh|en|...>
pkg: <Gaia package path>
run_dir: <trace directory>
seed_question: <one broad research question>
mode: fixture | live
review_depth: concise | review
stop_when: coverage sufficient, relation mix adequate, obligations manageable,
  and query novelty low enough
```

If `mode=live`, no fixture or mock data should enter the run. Preserve every CLI
command, timing, raw search file, generated analysis JSON, rendered report, and
notable failure in the trace.

## Loop

### 1. Setup

Create a package and seed question if none exists.

```bash
gaia pkg scaffold --target "$PKG" --name <topic>-gaia --namespace <topic>
gaia author question "<seed question>" --target "$PKG" \
  --dsl-binding-name <seed_binding> --title "<title>" --export --no-check
gaia research status "$PKG"
```

Success criteria:

- `gaia research status` works.
- Package path and run directory are recorded.
- The seed question is package source, not just trace prose.

### 2. Broad Explore

Run multiple query families before selecting a focus. For live runs, use real
LKM search output and save every raw result.

```bash
gaia search lkm knowledge "<broad query family>" --limit 10 \
  --out "$RUN/searches/01.json"

gaia research explore "$PKG" --mode scan \
  --search-json "$RUN/searches/01.json" \
  --search-json "$RUN/searches/02.json"
```

Success criteria:

- Landscape artifact exists under `.gaia/research/landscapes/`.
- A shallow source package exists under `.gaia/research/source_packages/` and is
  added through the local package dependency contract.
- Landscape items include `source_package_ref.ref` when materialized; use those
  refs for assessment `claim_refs` only when a concrete scaffold relation is
  justified.
- CLI reports `pull_budget: 0`.
- Candidate focuses and coverage gaps are synced to inquiry hypotheses /
  obligations.
- Raw search JSON remains available.

### 3. Focus Synthesis

Use the CLI contract as the schema and ask the active agent/LLM to synthesize
real assessment questions.

```bash
gaia research contract focus --language "$LANG" > "$RUN/analysis/focus-contract.json"
gaia research focus "$PKG" \
  --landscape "$SCAN" \
  --analysis-json "$RUN/analysis/focus-analysis.json" \
  --language "$LANG"
```

Success criteria:

- Focuses are questions, not query rewrites.
- Top accepted focuses are at most 3 and become package `question(...)`
  statements.
- The first accepted question becomes the inquiry focus.
- Gaps become inquiry obligations.
- Non-accepted focuses remain hypotheses or trace-only candidates.

### 4. Targeted Expand

Use focus gaps and suggested queries to expand coverage around one focus or
obligation.

```bash
gaia search lkm knowledge "<targeted query>" --limit 10 \
  --out "$RUN/searches/targeted-01.json"

gaia research expand "$PKG" \
  --focus <accepted_question_binding_or_focus_id> \
  --search-json "$RUN/searches/targeted-01.json"
```

Success criteria:

- Targeted landscape exists.
- Expand still does not pull papers.
- Expand still writes only shallow source packages, not paper graphs.
- New gaps/hypotheses are written to inquiry state.
- The landscape adds information that changes assessment readiness or stop
  criteria.

### 5. Assess

Assess one selected focus. The agent/LLM should read the evidence packet deeply
enough to write a review-quality mini-synthesis in the requested language.

```bash
gaia research contract assess --language "$LANG" > "$RUN/analysis/assess-contract.json"
gaia research assess "$PKG" \
  --focus <accepted_question_binding_or_focus_id> \
  --landscape "$SCAN" \
  --landscape "$EXPAND" \
  --analysis-json "$RUN/analysis/assess-analysis.json"

gaia research report "$PKG" \
  --artifact "$ASSESSMENT" \
  --out "$RUN/trace/assessment_report.md"
```

Success criteria:

- Review prose is readable as a mini-review, not a table dump.
- Relations are grounded in artifact item refs.
- Unresolved issues become inquiry obligations.
- Natural-language findings become inquiry hypotheses or `note(...)`.
- `candidate_relation(...)` appears only for relations with concrete
  `claim_refs`.

### 6. Stop Or Continue

Evaluate whether to expand, assess another focus, promote, or stop.

```bash
gaia research stop "$PKG" \
  --focus-artifact "$FOCUS_ARTIFACT" \
  --assessment "$ASSESSMENT" \
  --landscape "$EXPAND" \
  --previous-landscape "$SCAN" \
  --out "$RUN/trace/stop.json"
```

Continue when coverage is weak, obligations remain high, relation mix is thin,
or new queries still produce many novel paper leads.

### 7. Promote

Promote only after scaffold review. `promote` is narrow: it links an existing
scaffold to formal Gaia records.

```bash
gaia research promote "$PKG" \
  --scaffold <candidate_relation_binding> \
  --by <formal_record_binding> \
  --rationale "<why this scaffold is now formalized>"
```

Success criteria:

- `materialize(...)` is written in package source.
- No hidden explore/assess/report work happens inside promote.
- `gaia build check "$PKG"` still passes.

## Live Run Trace Checklist

For every live run, save:

- `searches/*.json`: raw LKM search results.
- `analysis/focus-contract.json` and `analysis/assess-contract.json`.
- `analysis/focus-analysis.json` and `analysis/assess-analysis.json`.
- `.gaia/research/landscapes/*.json`.
- `.gaia/research/focuses/*.json`.
- `.gaia/research/assessments/*.json`.
- `.gaia/research/events.jsonl`.
- `.gaia/inquiry/state.json` and `.gaia/inquiry/tactics.jsonl` snapshot.
- rendered reports under `trace/`.
- one `trace/evaluation_trace.md` that lists commands, timing, counts, failures,
  and subjective quality notes.

## Review Quality Bar

Before handing off:

1. `gaia build check "$PKG"` passes.
2. `gaia research report` renders focus, assessment, and stop artifacts.
3. The report body does not mention Gaia, LKM, artifact ids, or workflow jargon
   unless in an explicit provenance section.
4. Citations appear after the main body.
5. Relations and obligations are explained in prose; raw tables stay in JSON
   artifacts.
6. The trace says what to do next: broaden search, expand a focus, assess another
   focus, promote scaffolds, or stop.

## Common Mistakes

- Starting from one attractive paper and narrowing before the landscape is broad.
- Treating `focuses.json` as the focus registry. The registry is package
  `question(...)` plus inquiry focus.
- Treating `assessment.json` as formal knowledge. It is review/scaffold trace
  until promoted.
- Inventing `snippet`, `lkm_node`, or `gaia_qid` terminology. Use neutral
  `items` for artifact-local references; use `variable`, `paper`, or `factor`
  only when the source object is actually that type.
- Treating artifact-local `items` as the durable evidence store. They are trace
  references; the durable shallow evidence bundle is the generated local source
  package.
- Rewriting schemas in prompts. Always print and follow `gaia research contract`.
