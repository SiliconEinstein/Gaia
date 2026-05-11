# Contributing

Gaia is a Python 3.12 project managed with `uv`. The main architecture and user-facing
workflow live in `README.md` and `docs/foundations/`; this guide covers the local developer
loop.

## Local Setup

Install dependencies, including development tools:

```bash
uv sync --extra dev
```

Install the Git hooks once per clone:

```bash
uv run pre-commit install
```

The same setup is available through the `Makefile`:

```bash
make bootstrap
```

## Daily Checks

Run the standard local gate before committing:

```bash
make check
```

`make check` runs:

- `make lint` (`uv run pre-commit run --all-files`)
- `make test` (`uv run pytest`)

The pytest configuration enforces strict markers, coverage for `gaia`, and
`--cov-fail-under=90`.

## Type Checking

Strict mypy is configured for `gaia` and `tests`:

```bash
make typecheck
```

During the v0.5 quality refactor, strict mypy is available as an explicit target while annotation
backfill is completed. Keep new or touched code type-friendly, use PEP 604 annotations
(`X | None`), and avoid changing public APIs just to satisfy the checker.

## Style

Use the repository tooling rather than ad hoc formatter or linter commands:

```bash
make lint
```

Code should follow the project defaults in `pyproject.toml`: Ruff formatting, line length 100,
Python 3.12, Google-style docstrings, and Pydantic v2 APIs (`model_dump`, `model_validate`,
`model_validate_json`).

## Refactor Discipline

The v0.5 quality baseline refactor is intentionally scoped to tooling, type annotations,
docstrings, and tests. Do not change Gaia IR semantics, DSL surface, CLI command behavior,
algorithms, public names, or persisted artifact shapes as part of quality cleanup. If code appears
to contradict `docs/foundations/**` or `docs/specs/**`, record the contradiction in
`.refactor/STATE.md` instead of resolving semantics in passing.
