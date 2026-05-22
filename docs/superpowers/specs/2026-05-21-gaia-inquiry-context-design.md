# Gaia Inquiry Context Design

## Summary

Add `gaia inquiry context` as a read-only, focus-centered context packet for agents.
The command answers one question:

> Given the current focus claim, what is the selected reasoning trajectory that explains why this claim is here?

Version 1 deliberately stays small. It selects one backward reasoning trajectory,
renders it as Markdown by default, and can emit a thin JSON envelope containing a
Gaia IR slice for tools. It does not run or display belief propagation, does not
modify inquiry state, and does not attempt graph cover planning or lateral
neighborhood expansion.

## Goals

- Give agents a compact context packet centered on the current focus claim.
- Include the focus claim content directly.
- Explain the selected trajectory with each step's conclusion, rationale,
  given premises, and background references.
- Use meaningful Markdown headings that map to how an agent reasons:
  `Focus`, `Why This Claim`, and `References`.
- Preserve Gaia labels as the only human-facing reference keys. Do not introduce
  temporary indexes such as `C1` or `B1`.
- Keep JSON machine-readable while reusing Gaia IR as the graph payload.

## Non-Goals

- No belief output and no `--use-belief` option.
- No `--around`, sibling expansion, or `Other Ways` section in version 1.
- No graph cover planning.
- No mutation of Python source, compiled IR, priors, beliefs, snapshots, or
  inquiry tactic logs.
- No custom graph schema replacing Gaia IR.

## Command Surface

```bash
gaia inquiry context [PATH] \
  --focus CLAIM \
  --trajectory most_uncertain|shortest \
  --order backward|forward \
  --json
```

Defaults:

```text
PATH: .
--focus: current .gaia/inquiry/state.json focus
--trajectory: most_uncertain
--order: backward
format: markdown
```

`--focus` is an override. If it is omitted and no current inquiry focus exists,
the command exits with a concise error that suggests `gaia inquiry focus <claim>`.

`--trajectory` selects one route:

- `most_uncertain`: choose the route with the highest structural uncertainty.
- `shortest`: choose the shortest backward route from focus to a boundary or leaf.

`--order` only affects rendering order:

- `backward`: start at the focus claim and ask "why this claim?" step by step.
- `forward`: start at the selected boundary or leaf and move toward the focus.

`--json` emits a context envelope whose `ir` field is a Gaia IR-shaped slice.

## Markdown Output

Default output is Markdown because the primary consumer is an agent prompt.

Required section order:

```markdown
## Focus

### `acceleration_inquiry`

Early Galilean reasoning favors acceleration-based inquiry over proportional-speed law.

## Why This Claim

### Why `acceleration_inquiry`?

**Claim**
Early Galilean reasoning favors acceleration-based inquiry over proportional-speed law.

**Because**
The refutation of proportional-speed scaling and pendulum regularity motivate a different inquiry target.

**Given**
- `reject_prop_speed`: The proportional-speed law for falling bodies is not reliable...
- `pendulum_timing`: Pendulum timing suggests short arcs are approximately isochronous.

**Background**
- `galileo_setting`

## References

### `reject_prop_speed`
The proportional-speed law for falling bodies is not a reliable account of free fall.

### `pendulum_timing`
Pendulum timing suggests short arcs are approximately isochronous.

### `galileo_setting`
...
```

Rendering rules:

- `Focus` always prints the resolved focus label and full content.
- Each `Why This Claim` step prints:
  - `Claim`: full conclusion content.
  - `Because`: full strategy rationale or joined `steps[].reasoning`.
  - `Given`: each premise label plus a short preview.
  - `Background`: label or title only by default.
- `References` expands the full content for all labels mentioned in `Given` and
  `Background`, in first-reference order.
- If a content field is long, Markdown may truncate previews in `Given`, but
  `References` should preserve full content unless a future explicit budget
  option is added.
- If a label is missing, use the QID tail. If that is ambiguous, use the full QID.

## JSON Output

JSON uses a thin envelope so tools can see both the selection metadata and the
IR-shaped subgraph used to render the packet.

```json
{
  "context_schema_version": 1,
  "focus": {
    "id": "context_demo:context_demo::acceleration_inquiry",
    "label": "acceleration_inquiry"
  },
  "selection": {
    "trajectory": "most_uncertain",
    "order": "backward"
  },
  "why_route": [
    {
      "edge_kind": "strategy",
      "target_id": "lcs_...",
      "label": "acceleration_route",
      "conclusion": "context_demo:context_demo::acceleration_inquiry",
      "premises": [
        "context_demo:context_demo::reject_prop_speed",
        "context_demo:context_demo::pendulum_timing"
      ],
      "background": []
    }
  ],
  "ir": {
    "namespace": "context_demo",
    "package_name": "context_demo",
    "scope": "local",
    "knowledges": [],
    "strategies": [],
    "operators": [],
    "composes": [],
    "formula_graphs": []
  }
}
```

The envelope does not duplicate full knowledge content outside `ir`. The `ir`
slice is the source of truth for claim, note, strategy, operator, compose, and
formula graph records. Because the slice is not the full package graph, it must
not reuse the full package `ir_hash`; omit `ir_hash` from the slice unless a
future slice hash is explicitly defined.

## Trajectory Selection

The implementation works on the compiled local graph converted to Gaia IR dict
shape. It builds indexes over:

- knowledge by id
- strategies by conclusion
- operators by conclusion
- composes by conclusion
- formalization manifest dependencies for `depends_on` scaffolds

Version 1 uses the existing inquiry tree edge model for traversal. Strategy
edges are the primary supported rich case because they carry the main
`derive(...)` rationale and premises used by current packages. Non-strategy
edges exposed by the existing inquiry tree use the same route entry shape with
`edge_kind`, `target_id`, `label`, direct inputs, and any available rationale.
When a non-strategy edge has no rationale, Markdown renders its label and direct
inputs without inventing a `Because` sentence. The first implementation should
keep scoring simple and testable rather than adding a new semantic graph layer.

`shortest`:

1. Start from the resolved focus claim.
2. Walk backward through incoming reasoning edges.
3. Stop at a boundary node with no incoming reasoning edge, or at a cycle guard.
4. Choose the route with the fewest reasoning steps.

`most_uncertain`:

1. Enumerate candidate backward routes from focus to boundary or leaf.
2. Score each route using structural signals only.
3. Select the highest scoring route.
4. Break ties by shorter route, then stable lexical strategy id.

Structural uncertainty signals:

- boundary claim has no support route
- strategy status is `unreviewed`, `needs_inputs`, or `rejected`
- strategy has no rationale and no `steps[].reasoning`
- strategy metadata lacks provenance or justification when expected
- route includes unresolved synthetic obligations targeting a route claim or strategy
- route includes synthetic rejection targeting a strategy
- premise or background reference cannot be resolved

Beliefs, posterior probabilities, and belief deltas are not inputs to this score.

## Data Flow

1. Load package and compile in memory, following existing inquiry/review patterns.
2. Resolve focus from `--focus` or inquiry state.
3. Load or generate review manifest.
4. Load inquiry state only to read focus and synthetic obligations/rejections.
5. Build the selected trajectory.
6. Build the IR slice containing:
   - focus knowledge
   - route conclusions
   - route premises
   - route background knowledge
   - route strategies
   - operators/composes/formula graph entries directly needed by those route records
7. Render Markdown or JSON.

No state file is written.

## Error Handling

- Missing focus: exit 2 with `No inquiry focus set; pass --focus or run gaia inquiry focus <claim>.`
- Unresolved focus: exit 2 and report the selector.
- Focus resolves to non-claim: exit 2 in v1.
- No incoming route: still render `Focus`, then say no supporting trajectory was found.
- Compile failure: surface the compile error and exit 1.
- Invalid `--trajectory` or `--order`: Typer validation exits 2.

## Tests

Add focused tests for:

- CLI help includes `context`.
- Markdown output includes `## Focus`, `## Why This Claim`, and `## References`.
- Focus content is printed before the why section.
- `Given` uses labels and previews, not temporary indexes.
- `References` expands full given/background content by label.
- JSON output is valid, has `context_schema_version`, `focus`, `selection`,
  `why_route`, and `ir`.
- JSON `why_route` entries identify the selected edge with `edge_kind`,
  `target_id`, and `label`.
- JSON `ir` has LocalCanonicalGraph-shaped fields and no full package `ir_hash`.
- `--trajectory shortest` and `--trajectory most_uncertain` choose different
  routes on a fixture where the shortest route is structurally less uncertain.
- No belief fields appear in Markdown or JSON.
- Command does not mutate `.gaia/inquiry/state.json`.

## Documentation

Update `docs/reference/cli/inquiry.md` and the user-facing CLI command list with
the new command and its default Markdown behavior.
