# `gaia extract`

Turn a local PDF into LKM-extracted knowledge. Where [`gaia search`](search.md)
queries papers LKM has already ingested, this group goes the other direction:
hand LKM a PDF you hold and get back the research questions, conclusions, and
reasoning steps it extracts from that file.

```text
gaia extract submit <file.pdf>       Upload a PDF and queue extraction
gaia extract submit <file.pdf> --wait
gaia extract status <task-id>        Read the task once
gaia extract result <task-id>        Fetch what the task produced
gaia extract docs                    Print API documentation links
```

This is a job surface, not a retrieval surface, which is why it sits beside
`search` rather than inside it. It is also knowledge extraction rather than
layout parsing: it returns claims and reasoning, not page text, tables, or
formulas.

Auth, index selection, output, and exit codes match `gaia search lkm` — the
same Bohrium access key (`gaia search lkm auth login`, or
`GAIA_LKM_ACCESS_KEY` / `LKM_ACCESS_KEY`), the same `--index` / `--server`
option, the same raw-JSON-to-stdout-or-`--out` contract with Gaia follow-up
suggestions on stderr, and the same
`0 ok / 1 business error / 2 transport / 3 no key / 4 bad args` codes.

## Submit

```bash
gaia extract submit paper.pdf
gaia extract submit paper.pdf --wait --poll-interval 5 --timeout 3600
```

The file must be a PDF of at most 64 MiB; the extension, size, and `%PDF`
header are checked locally before anything is uploaded. The response carries
`task_id`, `pdf_md5`, `status`, `cache_hit`, `cache_source`, and `created_at`.

Acceptance is not completion. Without `--wait`, `submit` returns immediately
with the full envelope above on stdout — save `data.task_id` from it and poll
yourself with `gaia extract status`. Resubmitting the same PDF reuses the existing extraction
instead of starting over — an already-processed PDF comes back terminal
immediately with `cache_hit: true`. Resubmitting is not a way to hurry a
running task along: extra submissions only mint extra task ids that share the
same progress and result.

`cache_source` is present only on a cache hit and says where the reuse came
from:

| `cache_source` | Meaning |
|---|---|
| `lkm` | The paper was already extracted in the LKM corpus; the graph is served from there and no pipeline runs |
| `local` | An earlier submission of this exact PDF (same md5) produced it |

An `lkm` hit is normally available immediately. A `local` hit depends on how
far that earlier task got, so still branch on `status`.

With `--wait` the CLI polls until the task is terminal and emits the final
status payload. A task that ends `failed` exits 1 with its `failed_reason`; a
wait that runs out of time exits 2 and says so — the remote task keeps running
and the task id stays valid.

| Option | Default | Purpose |
|---|---|---|
| `--wait` | off | Poll until the task reaches a terminal state |
| `--poll-interval` | 5 | Seconds between polls (1–300); the 5s default matches the service |
| `--timeout` | 1800 | Seconds to wait before giving up (max 86400) |

## Status

```bash
gaia extract status <task-id>
```

One read, no polling. Branch on `status`, not on `stage`:

| `status` | Meaning |
|---|---|
| `queued` / `running` | Still working; call again |
| `succeeded` | Terminal; the full graph is available |
| `partial` | Terminal; the pipeline stopped early but kept intermediate XML |
| `failed` | Terminal; see `failed_reason` |

`stage` (`metadata`, `ocr`, `step0`–`step4`, `graph`, `done`) is progress
narration for humans, not a control signal.

`step_durations` is the measured half of that progress: the pipeline steps
that have finished so far, in `ocr` → `step0` → `step1` → `step2` → `step3` →
`step4` → `graph` order, each as `{"step": ..., "duration_ms": ...}`. Only
succeeded and skipped steps appear, and `metadata` is excluded because that
work happens during submit. `status` and `result` both return it.

Extraction commonly takes several minutes to a quarter of an hour.

## Result

```bash
gaia extract result <task-id>
```

A succeeded task returns `variables` / `factors` / `motivations` / `stats`
directly under `data`, plus `step_durations`. That is not the `papers[]`
wrapper `gaia search lkm package` returns, and not a nodes/edges graph.

Node `local_id` values such as `paper:6::P1` are file-local. Only a non-null
`global_id` is an LKM id you can pass to `gaia search lkm nodes` or
`gaia pkg add`.

A partial or failed task returns `task_id`, `status`, `stage`,
`failed_reason`, `step_durations`, and `files` — expiring presigned links to
whatever intermediate XML exists. Reviews and abstract collections often stop before any
step produces output, so an empty `files` list is expected rather than a bug.

Asking for the result of a queued or running task is a business error (code
`290017`, exit 1). It does not mean the task was lost.
