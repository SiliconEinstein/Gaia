# `gaia inquiry`

Local semantic-inquiry loop for a package. Inquiry state is stored in
`.gaia` state files; these commands do not edit Python source, compiled IR,
priors, or beliefs.

```text
gaia inquiry focus <target>                Set or clear the current focus claim
gaia inquiry context [path]                Render focus-centered agent context
gaia inquiry review [path]                 Run the inquiry review pipeline
gaia inquiry obligation add <qid> ...      Record an open obligation
gaia inquiry obligation list               List open obligations
gaia inquiry obligation close <qid>        Close an obligation
gaia inquiry hypothesis add "<text>"       Record a working hypothesis
gaia inquiry hypothesis list               List active hypotheses
gaia inquiry hypothesis remove <id>        Remove a hypothesis
gaia inquiry tactics log                   Print the tactic event log
gaia inquiry reject <label> ...            Reject a strategy path with a reason
```

| Verb | Purpose |
|---|---|
| `focus` | Track or clear the current focus claim for the inquiry loop |
| `context` | Render a read-only focus-centered context packet as Markdown, or a JSON envelope with an IR slice |
| `review` | Run the inquiry review pipeline; emit text, JSON, or Markdown |
| `obligation` | Add / list / close open obligations |
| `hypothesis` | Add / list / remove working hypotheses |
| `tactics log` | Print the tactic event log for the package |
| `reject` | Mark a strategy path as rejected with a reason |

Option flags on `gaia inquiry review` (`--mode`, `--focus`, `--depth`,
`--since`, `--json`, `--markdown`, `--strict`, `--no-infer`) match the
pre-alpha-0 surface exactly. See
[CLI Workflow Command Guide](../../for-users/cli-commands.md) for examples.

The engine-side data model lives at [`gaia.engine.inquiry`](../engine/inquiry.md).

## Context packets

`gaia inquiry context` renders the current focus claim and the selected reasoning
trajectory behind it. Markdown is the default because the output is intended for
agent context. Use `--json` for tools; the JSON output is a thin envelope whose
`ir` field is a Gaia IR-shaped slice.

```bash
gaia inquiry focus acceleration_inquiry
gaia inquiry context .
gaia inquiry context . --trajectory shortest
gaia inquiry context . --focus acceleration_inquiry --json
```

The command is read-only: it does not save inquiry state, append tactic events,
run inference, or display beliefs.

`--trajectory most_uncertain` and `--trajectory shortest` select from the
currently enumerable backward support routes for the focus claim. Very large
packages with many parallel routes may need route caps or beam-style selection
in a future release.

## Implementation

::: gaia.cli.commands.inquiry
