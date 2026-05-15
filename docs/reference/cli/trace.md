# `gaia trace`

Verify, review, and inspect ARM execution traces. Independent of the 6
groups; sub-app and its internals are **unchanged** in alpha 0.

```text
gaia trace verify <trace.jsonl>            Validate schema + hash chain + manifest
gaia trace review <trace.jsonl>            Run trace review; emit text/JSON/Markdown
gaia trace show <trace.jsonl>              Print events, optionally filtered by kind
```

| Verb | Purpose | Exit codes |
|---|---|---|
| `verify` | Validate schema, per-event hash chain, events root, manifest hash | `0` clean, `1` tampered, `2` schema or bad args |
| `review` | Full diagnostic report; auto-saves a snapshot under `.gaia/trace/reviews/` | `0` clean, `1` errors or strict warnings, `2` bad args |
| `show` | Stream raw events, optionally filtered by `--kind` | `0` clean, `2` un-loadable schema |

Use `verify` for the fast fail-fast check; `review` when you need the full
diagnostic report; `show` when you want to inspect the event stream.

The engine-side data model lives at [`gaia.engine.trace`](../engine/trace.md).

## Implementation

::: gaia.cli.commands.trace
