# `gaia inquiry`

Local semantic-inquiry loop for a package. Inquiry state is stored in
`.gaia` state files; these commands do not edit Python source, compiled IR,
priors, or beliefs. The sub-app and its internals are **unchanged** in
alpha 0.

```text
gaia inquiry focus <target>                Set or clear the current focus claim
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
| `review` | Run the inquiry review pipeline; emit text, JSON, or Markdown |
| `obligation` | Add / list / close open obligations |
| `hypothesis` | Add / list / remove working hypotheses |
| `tactics log` | Print the tactic event log for the package |
| `reject` | Mark a strategy path as rejected with a reason |

Option flags on `gaia inquiry review` (`--mode`, `--focus`, `--depth`,
`--since`, `--json`, `--markdown`, `--strict`, `--no-infer`) match the
pre-alpha-0 surface exactly. See
[CLI Commands](../../for-users/cli-commands.md) for examples.

The engine-side data model lives at [`gaia.engine.inquiry`](../engine/inquiry.md).

## Implementation

::: gaia.cli.commands.inquiry
