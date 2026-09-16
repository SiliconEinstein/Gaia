# `gaia extract`

Turn a local PDF into LKM-extracted knowledge. Where [`gaia search`](search.md)
searches Bohrium's shared-knowledge layer, this group goes the other direction:
hand LKM a PDF you hold and get back the research questions, conclusions, and
reasoning steps it extracts from that file.

```text
gaia extract submit <file.pdf>       Upload a PDF and queue extraction
gaia extract submit <file.pdf> --wait
gaia extract status <task-id>        Read the task once
gaia extract result <task-id>        Fetch what the task produced
gaia extract docs                    Print API documentation links
```

These verbs extract from a PDF you hold. A paper already in LKM is
`gaia search lkm`, not this group.

This is a job surface, not a retrieval surface, which is why it sits beside
`search` rather than inside it. It is also knowledge extraction rather than
layout parsing: it returns claims and reasoning, not page text, tables, or
formulas.

Extract costs 1.00 CNY per successful paper, or 0.10 CNY on a cache hit.

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

The file must be a PDF of at most 64 MiB and 50 pages. The response carries
`task_id`, `pdf_md5`, `status`, `cache_hit`, `cache_source`, and `created_at`.
Extract costs 1.00 CNY per successful paper, or 0.10 CNY on a cache hit.

Acceptance is not completion. Without `--wait`, `submit` returns immediately
with the full envelope above on stdout — save `data.task_id` from it and poll
yourself with `gaia extract status`. `--wait` only polls the upload you are
submitting now; an existing `task_id` is polled by calling `status` again.
Resubmitting the same PDF reuses the existing extraction instead of starting
over; still branch on `status`. Resubmitting is not a way to hurry a
running task along: the same user and PDF still `queued` or `running`
returns business error `290020` with the existing `task_id`.

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
| `partial` | Terminal, non-retryable business failure; do not resubmit the same PDF |
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
gaia extract result <task-id> --format graph
```

`--format local` (default) returns `variables` / `factors` / `motivations` /
`stats` under `data`. `--format graph` returns `addressed_problems`,
`open_questions`, and `graph.nodes` / `graph.edges` under `data` — the same
field kinds as `gaia search lkm package`, not that command's envelope.
Format only changes a succeeded payload; an unknown value exits 4 before any
request.

Extract costs 1.00 CNY per successful paper, or 0.10 CNY on a cache hit.
If billing fails, retry the same `task_id` and do not resubmit the PDF.

Node `local_id` values and graph node `id`s such as `paper:6::P1` are
file-local. Only a non-null `global_id` is an LKM id you can pass to
`gaia search lkm nodes` or `gaia pkg add`.

A partial or failed task ignores `--format` and returns `task_id`, `status`,
`stage`, `failed_reason`, `step_durations`, and `files`. `partial` is a
non-retryable business failure (review, too short, collection); do not
resubmit the same PDF. `failed` is technical and the same file may be
submitted again. Empty `files` on partial is expected.

Asking for the result of a queued or running task is a business error (code
`290017`, exit 1). It does not mean the task was lost. A task id that does not
exist, or belongs to another user, is `290016`. A PDF over 50 pages is
`290022`.
