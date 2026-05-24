# Build Check Refs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `gaia build check --refs` as the current grouped-CLI replacement for the old proposed `gaia lint --refs`.

**Architecture:** Keep refs diagnostics inside the existing package check command. Reuse `references.json` loading, the current reference extractor/resolver, and compiled IR provenance instead of creating a new top-level CLI group.

**Tech Stack:** Python 3.12, Typer, Gaia package loader/compiler, pytest.

---

## File Structure

- Modify `gaia/cli/commands/check.py`: add the `--refs` option and refs report helpers.
- Modify `tests/cli/test_check_refs.py`: cover the CLI-facing report for citation, knowledge, artifact, unresolved-bare, unused, missing-file, and legacy metadata cases.
- Modify `docs/specs/2026-05-23-references-system-consolidation.md`: record `gaia build check --refs` as the current CLI location for refs linting.

## Task 1: Refs Check CLI Report

- [x] Write a failing test for `gaia build check --refs`.
- [x] Verify the test fails because `--refs` does not exist.
- [x] Implement minimal refs diagnostics in `gaia/cli/commands/check.py`.
- [x] Verify focused tests pass.
- [x] Update the references consolidation spec.
- [x] Run lint/format and focused check tests.
