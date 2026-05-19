"""Phase 0 Layer 1 — CLI e2e snapshot baseline.

These tests capture stdout / stderr / exit code of `gaia <verb>` invocations
via real subprocess.run, so that subsequent engine ↔ CLI refactor commits
can be checked for byte-identity. See `projects/gaia/alpha-0/plan.md`
Stage A1 in the workspace, and the 协作单 Phase 0 contract.

Run baseline only:
    uv run pytest tests/baseline/ --no-cov

Update snapshots:
    uv run pytest tests/baseline/ --no-cov --snapshot-update
"""
