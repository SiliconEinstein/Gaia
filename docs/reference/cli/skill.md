# `gaia skill`

Materialize bundled Gaia skills into the current project.

```text
gaia skill register [--target auto|claude|agent|both] [--dry-run]
gaia skill list
```

`register` copies the shipped skill registry into `.gaia-skills/` and creates
per-skill symlinks under `.claude/skills/` and/or `.agent/skills/`, depending on
the selected target. Existing foreign files, directories, and symlinks at those
entry points are reported as collisions and skipped.

`list` compares the shipped registry with the current project and prints the
status without changing files.
