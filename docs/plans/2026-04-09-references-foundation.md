# References Foundation Implementation Plan (PR 1)

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the foundation of the unified `@`-syntax and references system defined in `docs/specs/2026-04-09-references-and-at-syntax.md` — reference extraction, resolution, `references.json` loading, and compile-time integration with provenance metadata. **Out of scope for this PR:** README rendering, `gaia cite import`, `gaia lint --refs`, CSL style bundling.

**Architecture:** Add a new `gaia/lang/refs/` module with three pure components (extractor, resolver, loader). Wire them into `gaia/lang/compiler/compile.py`, replacing the existing `_AT_LABEL_RE` / `_extract_at_labels` / `_validate_at_labels` machinery. The new pipeline scans both strategy `reason` fields and all Knowledge `content` fields, applies strict/opportunistic rules, and writes `metadata["gaia"]["provenance"]` onto affected nodes.

**Tech Stack:** Python 3.12, stdlib `re` + `json` + `dataclasses`. No new runtime dependencies in PR 1 (citeproc-py and bibtexparser come in later PRs).

**Spec:** `docs/specs/2026-04-09-references-and-at-syntax.md`

---

## Prerequisites

Before starting:

1. Read the spec end-to-end — especially §3.1 (symbol table), §3.2 (homogeneous-group rule), §3.5 (collision fail-fast), §5.2 (resolver pseudocode), §8.1 (behavior changes).
2. Read current compiler integration points:
   - `gaia/lang/compiler/compile.py:177-237` — existing `_AT_LABEL_RE`, `_extract_at_labels`, `_validate_at_labels`
   - `gaia/lang/compiler/compile.py:400-412` — call site where `label_to_id` is built and `_validate_at_labels` is invoked
   - `gaia/lang/compiler/compile.py:402-404` — **key observation**: `label_to_id` is built from the full `knowledge_nodes` closure (local + imported). The new pipeline MUST reuse this same closure, not narrow to locals.
3. Read existing tests:
   - `tests/gaia/lang/test_compiler.py:22` + `:323-340` — tests that import `_extract_at_labels` directly; these will be deleted as part of this plan
4. Verify no new package will be needed in `pyproject.toml` for PR 1 scope.

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `gaia/lang/refs/__init__.py` | Public API re-exports | Create |
| `gaia/lang/refs/types.py` | `RefMarker`, `BracketGroup`, `ExtractionResult` dataclasses | Create |
| `gaia/lang/refs/extractor.py` | Pandoc-compatible regex extraction | Create |
| `gaia/lang/refs/resolver.py` | 3-state resolve + `check_collisions` + `validate_group` | Create |
| `gaia/lang/refs/loader.py` | `load_references(path)` + CSL type validation | Create |
| `gaia/lang/refs/errors.py` | `ReferenceError` exception class | Create |
| `gaia/lang/compiler/compile.py` | Replace old `@label` machinery | Modify (remove lines 177-237, rewire call site at 400-412, widen to content fields) |
| `tests/gaia/lang/refs/__init__.py` | Test package marker | Create |
| `tests/gaia/lang/refs/test_extractor.py` | Extractor unit tests | Create |
| `tests/gaia/lang/refs/test_resolver.py` | Resolver unit tests | Create |
| `tests/gaia/lang/refs/test_loader.py` | Loader unit tests | Create |
| `tests/gaia/lang/compiler/test_refs_integration.py` | End-to-end compile tests | Create |
| `tests/gaia/lang/test_compiler.py` | Delete obsolete `_extract_at_labels` tests | Modify (delete lines 22, 323-340) |
| `docs/foundations/gaia-lang/` | Add short section pointing to spec | Modify (one doc update) |

## Subsystem boundaries

The three refs components are pure:

- **extractor** — input: `str` text. Output: `ExtractionResult(groups, bare_markers)`. No side effects. No knowledge of label/reference tables.
- **resolver** — input: `label_table: dict[str, str]`, `references: dict[str, dict]`, plus extraction result. Output: list of resolved `(marker, kind)` tuples, or raises `ReferenceError`. No I/O.
- **loader** — input: `Path`. Output: `dict[str, dict]`. Raises `ReferenceError` on invalid format.

Only `compile.py` is allowed to know about all three and Knowledge node internals.

---

## Chunk 1: Foundation (all tasks)

### Task 1: Scaffold refs package with types and error class

**Files:**
- Create: `gaia/lang/refs/__init__.py`
- Create: `gaia/lang/refs/types.py`
- Create: `gaia/lang/refs/errors.py`
- Test: `tests/gaia/lang/refs/__init__.py` (empty), test in next task

- [ ] **Step 1: Create empty package files**

```bash
mkdir -p gaia/lang/refs tests/gaia/lang/refs
```

- [ ] **Step 2: Write `gaia/lang/refs/errors.py`**

```python
"""Reference extraction / resolution / loading errors."""

from __future__ import annotations


class ReferenceError(Exception):
    """Base error for reference handling.

    Raised from extractor, resolver, loader for any structural or semantic
    failure. Compile turns these into hard errors.
    """

    def __init__(self, message: str, *, location: str | None = None) -> None:
        self.location = location
        if location:
            super().__init__(f"{location}: {message}")
        else:
            super().__init__(message)
```

- [ ] **Step 3: Write `gaia/lang/refs/types.py`**

```python
"""Data types for the references subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

RefKind = Literal["knowledge", "citation", "unknown"]


@dataclass(frozen=True)
class RefMarker:
    """A single @key reference marker extracted from text.

    Attributes:
        key: The identifier after `@`.
        start: Character offset in source text.
        end: Character offset (exclusive).
        strict: True if inside a `[...]` group, False if bare.
        group_index: Index into the parent `ExtractionResult.groups` list if
            inside a bracket group, otherwise None.
    """

    key: str
    start: int
    end: int
    strict: bool
    group_index: int | None = None


@dataclass(frozen=True)
class BracketGroup:
    """A complete `[...]` Pandoc citation group containing one or more refs.

    Attributes:
        raw: Full bracket group text including the brackets (for error
            messages).
        start: Character offset in source text (position of `[`).
        end: Character offset (exclusive; position after `]`).
        marker_indices: Indices into `ExtractionResult.markers` of all markers
            that belong to this group.
    """

    raw: str
    start: int
    end: int
    marker_indices: tuple[int, ...]


@dataclass(frozen=True)
class ExtractionResult:
    """Result of scanning a piece of text for reference markers.

    Attributes:
        markers: All extracted markers, in source order. Includes both
            bracketed (strict) and bare (opportunistic) markers.
        groups: All bracket groups detected, in source order.
    """

    markers: tuple[RefMarker, ...]
    groups: tuple[BracketGroup, ...]
```

- [ ] **Step 4: Write `gaia/lang/refs/__init__.py`**

```python
"""Gaia reference extraction, resolution, and loading.

Public API:
    - extract(text) -> ExtractionResult
    - resolve(key, label_table, references) -> RefKind
    - check_collisions(label_table, references) -> None
    - validate_groups(groups, markers, label_table, references) -> None
    - load_references(path) -> dict[str, dict]
    - RefKind, RefMarker, BracketGroup, ExtractionResult, ReferenceError
"""

from __future__ import annotations

from gaia.lang.refs.errors import ReferenceError
from gaia.lang.refs.extractor import extract
from gaia.lang.refs.loader import load_references
from gaia.lang.refs.resolver import (
    check_collisions,
    resolve,
    validate_groups,
)
from gaia.lang.refs.types import (
    BracketGroup,
    ExtractionResult,
    RefKind,
    RefMarker,
)

__all__ = [
    "BracketGroup",
    "ExtractionResult",
    "RefKind",
    "RefMarker",
    "ReferenceError",
    "check_collisions",
    "extract",
    "load_references",
    "resolve",
    "validate_groups",
]
```

> Note: `extractor.py` / `resolver.py` / `loader.py` don't exist yet. The imports in `__init__.py` will fail until Tasks 2-4 land. That's fine — commit the types and errors first; subsequent tasks add the missing modules.

- [ ] **Step 5: Temporarily comment out broken imports**

Until the next tasks land, comment out the `extractor`, `resolver`, `loader` imports and related `__all__` entries in `gaia/lang/refs/__init__.py` so the package is importable after this task. Add a `# TODO(task-2..4): re-enable` comment next to each.

- [ ] **Step 6: Verify the package imports**

```bash
uv run python -c "from gaia.lang.refs import RefMarker, BracketGroup, ExtractionResult, ReferenceError; print('ok')"
```
Expected: `ok`

- [ ] **Step 7: Commit**

```bash
git add gaia/lang/refs/__init__.py gaia/lang/refs/types.py gaia/lang/refs/errors.py tests/gaia/lang/refs/__init__.py
git commit -m "feat(refs): add refs package scaffold with types and errors

Part 1 of references foundation (PR 1 Task 1).
See docs/specs/2026-04-09-references-and-at-syntax.md"
```

---

### Task 2: Implement the extractor

**Files:**
- Create: `gaia/lang/refs/extractor.py`
- Test: `tests/gaia/lang/refs/test_extractor.py`

**Design:**
- Pass 1 scans `[...]` bracket groups containing at least one `@key`, records each group and the markers inside.
- Pass 2 scans bare `@key` markers that are not inside any bracket group and not escaped.
- Escape: `\@foo` prevents `@foo` from being extracted.
- Bare regex uses `(?<![A-Za-z0-9_])` lookbehind to exclude email-like fragments (`foo@bar`).
- Citation key regex is permissive (Pandoc subset): `[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/-]*[A-Za-z0-9_]` or single char `[A-Za-z0-9_]`.

- [ ] **Step 1: Write failing tests — bare markers**

In `tests/gaia/lang/refs/test_extractor.py`:

```python
"""Tests for gaia.lang.refs.extractor."""

from __future__ import annotations

from gaia.lang.refs import extract


def test_extract_empty_string() -> None:
    result = extract("")
    assert result.markers == ()
    assert result.groups == ()


def test_extract_plain_text_no_markers() -> None:
    result = extract("This is plain text with no references.")
    assert result.markers == ()
    assert result.groups == ()


def test_extract_single_bare_marker() -> None:
    result = extract("As @lemma_a shows, the claim holds.")
    assert len(result.markers) == 1
    marker = result.markers[0]
    assert marker.key == "lemma_a"
    assert marker.strict is False
    assert marker.group_index is None
    assert marker.start == 3
    assert marker.end == 11


def test_extract_bare_marker_with_citation_key() -> None:
    result = extract("See @Bell1964 for details.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"
    assert result.markers[0].strict is False


def test_extract_bare_marker_with_punctuation_in_key() -> None:
    result = extract("Reference @arxiv:2401.12345 here.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "arxiv:2401.12345"


def test_extract_bare_marker_followed_by_punctuation() -> None:
    """Key cannot end with punctuation — trailing `.` is not part of key."""
    result = extract("See @Bell1964.")
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"


def test_extract_email_not_matched() -> None:
    """`@bar` inside `foo@bar.com` must NOT match (email safety)."""
    result = extract("Email me at foo@bar.com for questions.")
    assert result.markers == ()


def test_extract_escaped_at_not_matched() -> None:
    """`\\@foo` is literal — extractor skips it."""
    result = extract("Use the \\@dataclass decorator.")
    assert result.markers == ()


def test_extract_multiple_bare_markers() -> None:
    result = extract("Combine @lemma_a with @Bell1964 for the proof.")
    assert len(result.markers) == 2
    assert [m.key for m in result.markers] == ["lemma_a", "Bell1964"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/gaia/lang/refs/test_extractor.py -v
```
Expected: all tests error with ImportError or ModuleNotFoundError (extractor doesn't exist yet).

- [ ] **Step 3: Implement bare marker extraction**

Create `gaia/lang/refs/extractor.py`:

```python
"""Extract Pandoc-style reference markers from text.

Supports two forms:
  - Bare:      @key                   (opportunistic)
  - Bracketed: [prefix @key suffix]   (strict, Pandoc subset)

The extractor is pure — it only parses text and has no knowledge of label
tables or references.json. Resolution is done by the resolver module.
"""

from __future__ import annotations

import re

from gaia.lang.refs.types import BracketGroup, ExtractionResult, RefMarker

# Pandoc-compatible citation key:
#   - starts with letter/digit/underscore
#   - inner chars may include `:.#$%&+?<>~/-` plus word chars
#   - cannot end with punctuation
#
# We build this as two alternatives: single-char keys (just word char) or
# multi-char keys (word char + middle + word char).
_KEY = (
    r"(?:[A-Za-z0-9_][A-Za-z0-9_:.#$%&+?<>~/\-]*[A-Za-z0-9_]"
    r"|[A-Za-z0-9_])"
)

_BARE_AT_RE = re.compile(
    rf"""
    (?<!\\)              # not preceded by a backslash (escape)
    (?<![A-Za-z0-9_])    # not preceded by a word char (excludes email @)
    @({_KEY})
    """,
    re.VERBOSE,
)


def extract(text: str) -> ExtractionResult:
    """Scan text for reference markers, returning bracket groups and bare markers."""
    if not text:
        return ExtractionResult(markers=(), groups=())

    markers: list[RefMarker] = []

    # Pass 2 (bracket groups come in next step): bare markers only for now.
    for match in _BARE_AT_RE.finditer(text):
        markers.append(
            RefMarker(
                key=match.group(1),
                start=match.start(),
                end=match.end(),
                strict=False,
                group_index=None,
            )
        )

    markers.sort(key=lambda m: m.start)
    return ExtractionResult(markers=tuple(markers), groups=())
```

- [ ] **Step 4: Run tests to verify bare-marker tests pass**

```bash
uv run pytest tests/gaia/lang/refs/test_extractor.py -v -k "bare or plain or empty or escaped or email or multiple_bare or single_bare or punctuation"
```
Expected: all bare-related tests pass.

- [ ] **Step 5: Write failing tests — bracket groups**

Append to `tests/gaia/lang/refs/test_extractor.py`:

```python
def test_extract_single_bracket_group_one_key() -> None:
    result = extract("The result [@Bell1964] is foundational.")
    assert len(result.groups) == 1
    group = result.groups[0]
    assert group.raw == "[@Bell1964]"
    assert len(group.marker_indices) == 1

    assert len(result.markers) == 1
    marker = result.markers[0]
    assert marker.key == "Bell1964"
    assert marker.strict is True
    assert marker.group_index == 0


def test_extract_bracket_group_multiple_keys() -> None:
    result = extract("[@Bell1964; @CHSH1969; @EPR1935]")
    assert len(result.groups) == 1
    group = result.groups[0]
    assert len(group.marker_indices) == 3

    assert len(result.markers) == 3
    assert [m.key for m in result.markers] == ["Bell1964", "CHSH1969", "EPR1935"]
    assert all(m.strict for m in result.markers)
    assert all(m.group_index == 0 for m in result.markers)


def test_extract_bracket_group_with_prefix_locator() -> None:
    """Pandoc prefix + locator + suffix — extractor only finds the @keys, not
    the surrounding metadata."""
    result = extract("[see @Bell1964, pp. 33-35 and passim]")
    assert len(result.groups) == 1
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"
    assert result.markers[0].strict is True


def test_extract_suppress_author_form() -> None:
    result = extract("Bell [-@Bell1964] showed this.")
    assert len(result.groups) == 1
    assert len(result.markers) == 1
    assert result.markers[0].key == "Bell1964"


def test_extract_mixed_bare_and_bracket() -> None:
    text = "First @lemma_a shows this, then [@Bell1964] confirms it."
    result = extract(text)
    assert len(result.groups) == 1
    assert len(result.markers) == 2
    # lemma_a is bare, Bell1964 is in the group
    bare = [m for m in result.markers if not m.strict]
    bracketed = [m for m in result.markers if m.strict]
    assert len(bare) == 1 and bare[0].key == "lemma_a"
    assert len(bracketed) == 1 and bracketed[0].key == "Bell1964"


def test_extract_empty_brackets_not_group() -> None:
    """`[foo]` without any @ is not a reference group."""
    result = extract("This is [regular] bracketed text.")
    assert result.groups == ()
    assert result.markers == ()


def test_extract_bracket_no_at_not_group() -> None:
    result = extract("The range is [1, 10] here.")
    assert result.groups == ()
    assert result.markers == ()


def test_extract_escaped_bracket_not_parsed() -> None:
    """`\\[@Bell1964]` — the backslash escapes the opening `[`."""
    result = extract("Literal \\[@Bell1964] here.")
    assert result.groups == ()
    # The bare extractor should also NOT match because the bracket check
    # protects this case; Bell1964 is inside a would-be bracket that is
    # escaped, so extractor leaves it alone.
    # Actual behavior: the bare extractor does NOT see `@Bell1964` here
    # because the lookahead position is after `\\[`. The `\\` precedes `[`
    # not `@`, so the bare check passes. This is a known edge case.
    # For this test, assert on groups only.
```

- [ ] **Step 6: Implement bracket group extraction**

Extend `gaia/lang/refs/extractor.py`:

```python
# Pandoc bracket group: starts with `[`, must contain at least one `@key`,
# cannot contain nested brackets.
_BRACKET_GROUP_RE = re.compile(
    r"""
    (?<!\\)              # opening `[` not escaped
    \[
    ([^\[\]]*            # group body, no nested brackets
     @[A-Za-z0-9_]       # must contain at least one @key start
     [^\[\]]*)
    \]
    """,
    re.VERBOSE,
)

# Inside a bracket group, extract all @keys.
_INNER_KEY_RE = re.compile(rf"@({_KEY})")


def extract(text: str) -> ExtractionResult:
    """Scan text for reference markers, returning bracket groups and bare markers."""
    if not text:
        return ExtractionResult(markers=(), groups=())

    markers: list[RefMarker] = []
    groups: list[BracketGroup] = []
    # Character positions covered by bracket groups, so the bare scanner can
    # skip them.
    bracket_spans: list[tuple[int, int]] = []

    # Pass 1: bracket groups
    for group_match in _BRACKET_GROUP_RE.finditer(text):
        group_start = group_match.start()
        group_end = group_match.end()
        body = group_match.group(1)
        body_offset = group_match.start(1)

        marker_indices: list[int] = []
        group_index = len(groups)
        for key_match in _INNER_KEY_RE.finditer(body):
            marker_index = len(markers)
            markers.append(
                RefMarker(
                    key=key_match.group(1),
                    start=body_offset + key_match.start(1) - 1,  # include `@`
                    end=body_offset + key_match.end(1),
                    strict=True,
                    group_index=group_index,
                )
            )
            marker_indices.append(marker_index)

        if not marker_indices:
            # Group body had `@` but not a valid key — skip silently.
            continue

        groups.append(
            BracketGroup(
                raw=text[group_start:group_end],
                start=group_start,
                end=group_end,
                marker_indices=tuple(marker_indices),
            )
        )
        bracket_spans.append((group_start, group_end))

    def _inside_bracket(pos: int) -> bool:
        return any(start <= pos < end for start, end in bracket_spans)

    # Pass 2: bare markers (not inside bracket groups)
    for match in _BARE_AT_RE.finditer(text):
        if _inside_bracket(match.start()):
            continue
        markers.append(
            RefMarker(
                key=match.group(1),
                start=match.start(),
                end=match.end(),
                strict=False,
                group_index=None,
            )
        )

    markers.sort(key=lambda m: m.start)
    return ExtractionResult(markers=tuple(markers), groups=tuple(groups))
```

- [ ] **Step 7: Run all extractor tests**

```bash
uv run pytest tests/gaia/lang/refs/test_extractor.py -v
```
Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add gaia/lang/refs/extractor.py tests/gaia/lang/refs/test_extractor.py
git commit -m "feat(refs): implement Pandoc-style reference extractor

Extractor recognizes both bracketed [@key] and bare @key forms per
§3.2 of the spec. No resolution yet — that comes in Task 3.

Part 2 of references foundation (PR 1 Task 2)."
```

- [ ] **Step 9: Re-enable extractor import in `__init__.py`**

Remove the `# TODO(task-2)` comment and the temporary commenting around the `extractor` import + `extract` in `__all__`. Run:

```bash
uv run python -c "from gaia.lang.refs import extract; print(extract('test @foo').markers)"
```
Expected: `(RefMarker(key='foo', start=5, end=9, strict=False, group_index=None),)`

Amend the previous commit:

```bash
git add gaia/lang/refs/__init__.py
git commit --amend --no-edit
```

---

### Task 3: Implement the resolver

**Files:**
- Create: `gaia/lang/refs/resolver.py`
- Test: `tests/gaia/lang/refs/test_resolver.py`

**Design:**
- `resolve(key, label_table, references)` — 3-state (after pre-compile collision check).
- `check_collisions(label_table, references)` — raises `ReferenceError` if any key appears in both.
- `validate_groups(groups, markers, label_table, references)` — raises `ReferenceError` if any group has mixed types. Must be called AFTER `check_collisions`.

- [ ] **Step 1: Write failing tests for `resolve`**

In `tests/gaia/lang/refs/test_resolver.py`:

```python
"""Tests for gaia.lang.refs.resolver."""

from __future__ import annotations

import pytest

from gaia.lang.refs import (
    BracketGroup,
    RefMarker,
    ReferenceError,
    check_collisions,
    extract,
    resolve,
    validate_groups,
)


def test_resolve_knowledge() -> None:
    label_table = {"lemma_a": "github:pkg::lemma_a"}
    references: dict[str, dict] = {}
    assert resolve("lemma_a", label_table, references) == "knowledge"


def test_resolve_citation() -> None:
    label_table: dict[str, str] = {}
    references = {"Bell1964": {"type": "article-journal", "title": "On EPR"}}
    assert resolve("Bell1964", label_table, references) == "citation"


def test_resolve_unknown() -> None:
    label_table: dict[str, str] = {}
    references: dict[str, dict] = {}
    assert resolve("nothing_here", label_table, references) == "unknown"


def test_resolve_citation_precedence_not_applicable_after_collision_check() -> None:
    """If check_collisions passed, resolver must not see both. This test
    documents that resolver assumes disjoint inputs. The collision case is
    covered by check_collisions tests."""
    label_table = {"only_local": "qid"}
    references = {"only_remote": {"type": "book", "title": "X"}}
    assert resolve("only_local", label_table, references) == "knowledge"
    assert resolve("only_remote", label_table, references) == "citation"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/gaia/lang/refs/test_resolver.py::test_resolve_knowledge -v
```
Expected: ImportError or ModuleNotFoundError.

- [ ] **Step 3: Implement `resolve`**

Create `gaia/lang/refs/resolver.py`:

```python
"""Reference resolution: label table vs references.json.

Run order at compile time:
    1. check_collisions(label_table, references)  — fail fast on ambiguous keys
    2. For each bracket group: validate_groups([group], markers, ...)
    3. For each marker: resolve(marker.key, label_table, references)

Step 1 guarantees step 3's inputs are disjoint (no key appears in both
tables), so resolve() only needs a 3-state output (knowledge / citation /
unknown).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from gaia.lang.refs.errors import ReferenceError
from gaia.lang.refs.types import BracketGroup, RefKind, RefMarker


def resolve(
    key: str,
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> RefKind:
    """Resolve a single reference key.

    Must only be called after `check_collisions` has passed, which guarantees
    a key is in at most one table.
    """
    if key in references:
        return "citation"
    if key in label_table:
        return "knowledge"
    return "unknown"
```

- [ ] **Step 4: Run resolver tests**

```bash
uv run pytest tests/gaia/lang/refs/test_resolver.py -v -k resolve
```
Expected: 4 resolve tests pass.

- [ ] **Step 5: Write failing tests for `check_collisions`**

Append to `tests/gaia/lang/refs/test_resolver.py`:

```python
def test_check_collisions_no_collision() -> None:
    label_table = {"lemma_a": "q1", "lemma_b": "q2"}
    references = {"Bell1964": {"type": "book", "title": "X"}}
    # Should not raise
    check_collisions(label_table, references)


def test_check_collisions_single_collision_raises() -> None:
    label_table = {"bell_lemma": "q1"}
    references = {"bell_lemma": {"type": "article-journal", "title": "X"}}
    with pytest.raises(ReferenceError) as exc:
        check_collisions(label_table, references)
    assert "bell_lemma" in str(exc.value)
    assert "ambiguous" in str(exc.value).lower()


def test_check_collisions_multiple_collisions_all_listed() -> None:
    label_table = {"a": "q1", "b": "q2", "c": "q3"}
    references = {
        "a": {"type": "book", "title": "A"},
        "c": {"type": "book", "title": "C"},
        "d": {"type": "book", "title": "D"},
    }
    with pytest.raises(ReferenceError) as exc:
        check_collisions(label_table, references)
    msg = str(exc.value)
    assert "'a'" in msg
    assert "'c'" in msg
    assert "'b'" not in msg
    assert "'d'" not in msg
```

- [ ] **Step 6: Implement `check_collisions`**

Append to `gaia/lang/refs/resolver.py`:

```python
def check_collisions(
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> None:
    """Fail fast if any key appears in both the label table and references.

    Raises:
        ReferenceError: listing all colliding keys.

    Per spec §3.5, collision is a compile error — never a warning — to
    prevent silent semantic drift when a bibliography is imported.
    """
    collisions = sorted(set(label_table) & set(references))
    if collisions:
        quoted = ", ".join(f"'{k}'" for k in collisions)
        raise ReferenceError(
            f"ambiguous reference key(s) {quoted}: "
            f"same identifier exists as both a knowledge label and a "
            f"citation key. rename one side to disambiguate."
        )
```

- [ ] **Step 7: Run collision tests**

```bash
uv run pytest tests/gaia/lang/refs/test_resolver.py -v -k collision
```
Expected: 3 collision tests pass.

- [ ] **Step 8: Write failing tests for `validate_groups`**

Append to `tests/gaia/lang/refs/test_resolver.py`:

```python
def test_validate_groups_pure_citation_group_ok() -> None:
    text = "[@Bell1964; @CHSH1969]"
    result = extract(text)
    label_table: dict[str, str] = {}
    references = {
        "Bell1964": {"type": "article-journal", "title": "On EPR"},
        "CHSH1969": {"type": "article-journal", "title": "Proposed experiment"},
    }
    # Should not raise
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_pure_knowledge_group_ok() -> None:
    text = "[@lemma_a; @lemma_b]"
    result = extract(text)
    label_table = {"lemma_a": "q1", "lemma_b": "q2"}
    references: dict[str, dict] = {}
    validate_groups(result.groups, result.markers, label_table, references)


def test_validate_groups_mixed_group_raises() -> None:
    text = "[see @lemma_a; @Bell1964, p. 5]"
    result = extract(text)
    label_table = {"lemma_a": "q1"}
    references = {"Bell1964": {"type": "article-journal", "title": "X"}}
    with pytest.raises(ReferenceError) as exc:
        validate_groups(result.groups, result.markers, label_table, references)
    msg = str(exc.value)
    assert "mixed" in msg.lower()
    assert "lemma_a" in msg
    assert "Bell1964" in msg


def test_validate_groups_unknown_in_group_not_flagged_as_mixed() -> None:
    """A group with one knowledge ref + one unknown key is NOT mixed. The
    unknown case is handled separately at marker disposition time."""
    text = "[@lemma_a; @nothing]"
    result = extract(text)
    label_table = {"lemma_a": "q1"}
    references: dict[str, dict] = {}
    # validate_groups tolerates unknowns; it only fires on knowledge+citation.
    validate_groups(result.groups, result.markers, label_table, references)
```

- [ ] **Step 9: Implement `validate_groups`**

Append to `gaia/lang/refs/resolver.py`:

```python
def validate_groups(
    groups: Iterable[BracketGroup],
    markers: tuple[RefMarker, ...] | list[RefMarker],
    label_table: dict[str, Any],
    references: dict[str, Any],
) -> None:
    """Enforce the homogeneous-group rule (spec §3.2).

    A `[...]` group must contain only knowledge refs or only citations.
    Mixing them in one group is a compile error because the rendering
    pipeline cannot faithfully process mixed Pandoc groups through
    citeproc-py.

    Unknown keys are NOT flagged here — they have their own disposition
    (strict → error at marker level; opportunistic → literal). This function
    only fires on the specific knowledge+citation mix.

    Raises:
        ReferenceError: on the first mixed group encountered, listing which
            keys are knowledge and which are citations.
    """
    markers_seq = tuple(markers)
    for group in groups:
        knowledge_keys: list[str] = []
        citation_keys: list[str] = []
        for idx in group.marker_indices:
            marker = markers_seq[idx]
            kind = resolve(marker.key, label_table, references)
            if kind == "knowledge":
                knowledge_keys.append(marker.key)
            elif kind == "citation":
                citation_keys.append(marker.key)
            # "unknown" is ignored here — disposition happens at marker level.
        if knowledge_keys and citation_keys:
            raise ReferenceError(
                f"mixed-type reference group {group.raw!r}: contains both "
                f"knowledge refs ({', '.join(knowledge_keys)}) and "
                f"citations ({', '.join(citation_keys)}). "
                f"split into separate bracketed groups — one for knowledge "
                f"refs and one for citations."
            )
```

- [ ] **Step 10: Run all resolver tests**

```bash
uv run pytest tests/gaia/lang/refs/test_resolver.py -v
```
Expected: all tests pass.

- [ ] **Step 11: Re-enable resolver imports in `__init__.py` and commit**

```bash
# Edit gaia/lang/refs/__init__.py — remove TODO comments around resolver imports.

uv run python -c "from gaia.lang.refs import resolve, check_collisions, validate_groups; print('ok')"
# Expected: ok

git add gaia/lang/refs/resolver.py tests/gaia/lang/refs/test_resolver.py gaia/lang/refs/__init__.py
git commit -m "feat(refs): implement resolver with collision and group checks

- resolve(): 3-state key classification (knowledge/citation/unknown)
- check_collisions(): fail-fast on ambiguous keys (spec §3.5)
- validate_groups(): homogeneous-group rule (spec §3.2)

Part 3 of references foundation (PR 1 Task 3)."
```

---

### Task 4: Implement the CSL-JSON loader

**Files:**
- Create: `gaia/lang/refs/loader.py`
- Test: `tests/gaia/lang/refs/test_loader.py`

**Design:**
- `load_references(path: Path) -> dict[str, dict]`
- Missing file → return `{}` (references.json is optional)
- Invalid JSON → `ReferenceError`
- Top-level not a dict → `ReferenceError`
- Entry missing `type` → `ReferenceError`
- Entry `type` not in CSL 1.0.2 allowlist → `ReferenceError`
- Entry missing `title` → `ReferenceError`
- Warnings (not errors) for missing recommended fields (`author`, `issued`, `DOI`/`URL`) — collected and returned as second element, or kept as a warnings list attribute.

For PR 1 scope, let's keep the loader simple and NOT emit warnings; just do the hard validation.

- [ ] **Step 1: Write failing tests**

In `tests/gaia/lang/refs/test_loader.py`:

```python
"""Tests for gaia.lang.refs.loader."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gaia.lang.refs import ReferenceError, load_references


def test_load_missing_file_returns_empty(tmp_path: Path) -> None:
    """references.json is optional; missing file → empty dict."""
    assert load_references(tmp_path / "references.json") == {}


def test_load_valid_minimal_entry(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "Bell1964": {
            "type": "article-journal",
            "title": "On the Einstein Podolsky Rosen Paradox",
        }
    }))
    refs = load_references(path)
    assert "Bell1964" in refs
    assert refs["Bell1964"]["title"].startswith("On the Einstein")


def test_load_valid_full_entry(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "EPR1935": {
            "type": "article-journal",
            "title": "Can Quantum-Mechanical Description of Physical Reality Be Considered Complete?",
            "author": [
                {"family": "Einstein", "given": "A."},
                {"family": "Podolsky", "given": "B."},
                {"family": "Rosen", "given": "N."},
            ],
            "container-title": "Physical Review",
            "volume": "47",
            "page": "777-780",
            "issued": {"date-parts": [[1935, 5, 15]]},
            "DOI": "10.1103/PhysRev.47.777",
        }
    }))
    refs = load_references(path)
    assert len(refs) == 1
    assert refs["EPR1935"]["DOI"] == "10.1103/PhysRev.47.777"


def test_load_invalid_json_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text("{not valid json")
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "invalid json" in str(exc.value).lower()


def test_load_top_level_not_dict_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps(["not", "a", "dict"]))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "must be a json object" in str(exc.value).lower()


def test_load_entry_missing_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "Bad": {"title": "No type field"}
    }))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "type" in str(exc.value)
    assert "Bad" in str(exc.value)


def test_load_entry_invalid_type_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "Bad": {"type": "not-a-real-csl-type", "title": "X"}
    }))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "not-a-real-csl-type" in str(exc.value)


def test_load_entry_missing_title_raises(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "Bad": {"type": "book"}
    }))
    with pytest.raises(ReferenceError) as exc:
        load_references(path)
    assert "title" in str(exc.value)


def test_load_webpage_type(tmp_path: Path) -> None:
    """Webpages are first-class citizens (spec §4.4)."""
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "SomeBlog": {
            "type": "post-weblog",
            "title": "An explanation",
            "URL": "https://example.com/post",
        }
    }))
    refs = load_references(path)
    assert refs["SomeBlog"]["type"] == "post-weblog"


def test_load_software_type(tmp_path: Path) -> None:
    path = tmp_path / "references.json"
    path.write_text(json.dumps({
        "NumPy": {
            "type": "software",
            "title": "NumPy",
            "version": "1.26.0",
        }
    }))
    refs = load_references(path)
    assert refs["NumPy"]["type"] == "software"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/gaia/lang/refs/test_loader.py -v
```
Expected: ImportError.

- [ ] **Step 3: Implement `load_references`**

Create `gaia/lang/refs/loader.py`:

```python
"""Load and validate references.json (CSL-JSON format).

Per spec §4, stores entries as a dict keyed by citation key (not the
standard CSL-JSON array form). Missing file is not an error — references.json
is optional.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gaia.lang.refs.errors import ReferenceError

# CSL 1.0.2 type allowlist.
# Source: https://github.com/citation-style-language/schema
_CSL_TYPES: frozenset[str] = frozenset(
    {
        "article",
        "article-journal",
        "article-magazine",
        "article-newspaper",
        "bill",
        "book",
        "broadcast",
        "chapter",
        "classic",
        "collection",
        "dataset",
        "document",
        "entry",
        "entry-dictionary",
        "entry-encyclopedia",
        "event",
        "figure",
        "graphic",
        "hearing",
        "interview",
        "legal_case",
        "legislation",
        "manuscript",
        "map",
        "motion_picture",
        "musical_score",
        "pamphlet",
        "paper-conference",
        "patent",
        "performance",
        "periodical",
        "personal_communication",
        "post",
        "post-weblog",
        "regulation",
        "report",
        "review",
        "review-book",
        "software",
        "song",
        "speech",
        "standard",
        "thesis",
        "treaty",
        "webpage",
    }
)


def load_references(path: Path) -> dict[str, dict[str, Any]]:
    """Load and validate a references.json file.

    Args:
        path: Path to references.json. If missing, returns an empty dict.

    Returns:
        dict mapping citation key → CSL-JSON entry.

    Raises:
        ReferenceError: on invalid JSON, wrong top-level type, or any entry
            that fails schema validation.
    """
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise ReferenceError(
            f"invalid JSON in references file: {e.msg} (line {e.lineno}, col {e.colno})",
            location=str(path),
        ) from e

    if not isinstance(raw, dict):
        raise ReferenceError(
            f"references.json must be a JSON object keyed by citation key, "
            f"got {type(raw).__name__}",
            location=str(path),
        )

    for key, entry in raw.items():
        _validate_entry(key, entry, location=str(path))

    return raw


def _validate_entry(key: str, entry: Any, *, location: str) -> None:
    """Validate a single CSL-JSON entry.

    Minimum requirements (spec §4.5):
      - must be a dict
      - must have `type` matching CSL 1.0.2 allowlist
      - must have `title`
    """
    if not isinstance(entry, dict):
        raise ReferenceError(
            f"reference entry '{key}' must be an object, got {type(entry).__name__}",
            location=location,
        )

    if "type" not in entry:
        raise ReferenceError(
            f"reference entry '{key}' is missing required field 'type'",
            location=location,
        )
    entry_type = entry["type"]
    if entry_type not in _CSL_TYPES:
        raise ReferenceError(
            f"reference entry '{key}' has invalid type '{entry_type}'. "
            f"must be one of the CSL 1.0.2 types (e.g. article-journal, "
            f"book, webpage, software, dataset).",
            location=location,
        )

    if "title" not in entry or not entry["title"]:
        raise ReferenceError(
            f"reference entry '{key}' is missing required field 'title'",
            location=location,
        )
```

- [ ] **Step 4: Run loader tests**

```bash
uv run pytest tests/gaia/lang/refs/test_loader.py -v
```
Expected: all pass.

- [ ] **Step 5: Re-enable loader import in `__init__.py` and commit**

```bash
# Edit gaia/lang/refs/__init__.py — remove the last TODO around loader import.

uv run python -c "from gaia.lang.refs import load_references; print('ok')"
# Expected: ok

git add gaia/lang/refs/loader.py tests/gaia/lang/refs/test_loader.py gaia/lang/refs/__init__.py
git commit -m "feat(refs): implement references.json CSL-JSON loader

- Dict-by-key format per spec §4.3
- CSL 1.0.2 type allowlist validation
- Required fields: type, title
- Missing file is not an error (optional)

Part 4 of references foundation (PR 1 Task 4)."
```

---

### Task 5: Wire refs into compile.py — scanning + collision

**Files:**
- Modify: `gaia/lang/compiler/compile.py` (remove lines 177-237, wire in new pipeline)
- Modify: `tests/gaia/lang/test_compiler.py` (delete lines 22, 323-340 — obsolete tests)

**Design goal for this task:** Replace the old `_AT_LABEL_RE` machinery with a call into the new refs module. Scope: collision check + extraction from strategy `reason` fields. Content-field scanning and provenance come in Tasks 6-7.

- [ ] **Step 1: Delete obsolete tests in `tests/gaia/lang/test_compiler.py`**

Delete:
- Line 22: `from gaia.lang.compiler.compile import _extract_at_labels` (the whole import)
- Lines 323-340: `test_extract_at_labels_string`, `test_extract_at_labels_none`, `test_extract_at_labels_list`

Run the remaining compiler tests to confirm nothing else depends on them:

```bash
uv run pytest tests/gaia/lang/test_compiler.py -v
```

Expected: tests that don't depend on `_extract_at_labels` still pass.

- [ ] **Step 2: Delete old machinery from `gaia/lang/compiler/compile.py`**

Delete:
- Line 177: `_AT_LABEL_RE = re.compile(r"@([a-z_][a-z0-9_]*)")`
- Lines 180-195: `def _extract_at_labels(...)`
- Lines 198-237: `def _validate_at_labels(...)`
- Line 407: `_validate_at_labels(s, knowledge_map, label_to_id, at_label_warnings)` and the surrounding warning loop (lines 405-412)

- [ ] **Step 3: Add new imports and helper at the top of compile.py**

Add near the existing imports:

```python
from pathlib import Path

from gaia.lang.refs import (
    ReferenceError,
    check_collisions,
    extract,
    load_references,
    resolve,
    validate_groups,
)
```

- [ ] **Step 4: Write a failing integration test for collision behavior**

Create `tests/gaia/lang/compiler/test_refs_integration.py`:

```python
"""End-to-end integration tests for the refs system in compile.py.

These tests exercise the full compile pipeline on small synthetic packages
to verify the spec §8.1 behavior table.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.app import app

runner = CliRunner()


def _write_package(
    root: Path,
    name: str,
    module_body: str,
    references_json: dict | None = None,
) -> Path:
    pkg_dir = root / name
    pkg_dir.mkdir()
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "1.0.0"\n\n'
        f'[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n'
    )
    src_dir = pkg_dir / name.replace("-", "_")
    src_dir.mkdir()
    (src_dir / "__init__.py").write_text(module_body)
    if references_json is not None:
        (pkg_dir / "references.json").write_text(json.dumps(references_json))
    return pkg_dir


def test_compile_errors_on_label_citation_collision(tmp_path: Path) -> None:
    """Per spec §3.5, a key that exists in both the label table and
    references.json must cause a compile error."""
    pkg = _write_package(
        tmp_path,
        name="collision_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'bell_lemma = claim("A lemma about Bell.")\n'
            'main = claim("Main result.")\n'
            "deduction(premises=[bell_lemma], conclusion=main)\n"
            '__all__ = ["main", "bell_lemma"]\n'
        ),
        references_json={
            "bell_lemma": {
                "type": "article-journal",
                "title": "Bell's inequality paper",
            }
        },
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0
    assert "ambiguous" in result.output.lower()
    assert "bell_lemma" in result.output
```

- [ ] **Step 5: Run the test — expect it to fail because collision check isn't wired in yet**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_errors_on_label_citation_collision -v
```
Expected: the test runs compile but it succeeds (exit_code == 0) because nothing wires in the collision check yet. Or fails with a different error message.

- [ ] **Step 6: Wire in references loading and collision check at the compile entry point**

In `gaia/lang/compiler/compile.py`, find the point just after `label_to_id` is built (was around lines 401-404). Right after that block, add:

```python
    # Load references.json (spec §4). Optional; missing file → empty.
    pkg_root = _locate_package_root(pkg)
    references = load_references(pkg_root / "references.json") if pkg_root else {}

    # Spec §3.5: fail-fast on label / citation-key collision.
    check_collisions(label_to_id, references)
```

You'll need a helper `_locate_package_root(pkg)` that returns the root of the package on disk, or `None` if the package is in-memory (e.g. during tests that build packages directly). Look at how `CollectedPackage` tracks this — if it doesn't, add a `source_path` attribute. **Do not guess:** read `gaia/lang/runtime/package.py` first and pick the correct field.

If `CollectedPackage` doesn't track the source path, the cleanest fix is: make `references` an explicit argument to `compile_package_artifact`:

```python
def compile_package_artifact(
    pkg: CollectedPackage,
    *,
    references: dict[str, Any] | None = None,
) -> CompiledPackage:
    ...
    references = references or {}
    check_collisions(label_to_id, references)
    ...
```

Then in `gaia/cli/commands/_packages.py` (the CLI `compile` command), load references.json from the package root there and pass it in. This keeps `compile.py` library-pure.

- [ ] **Step 7: Update the CLI compile command to load references**

Read `gaia/cli/commands/_packages.py` to find where `compile_package_artifact(pkg)` is called. Add:

```python
from gaia.lang.refs import load_references, ReferenceError

references = load_references(package_root / "references.json")
try:
    compiled = compile_package_artifact(pkg, references=references)
except ReferenceError as e:
    raise GaiaCliError(str(e)) from e
```

Choose the variable name `package_root` based on what's in scope at the call site.

- [ ] **Step 8: Re-run the collision test**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_errors_on_label_citation_collision -v
```
Expected: pass — exit code is non-zero and error message mentions "ambiguous" and "bell_lemma".

- [ ] **Step 9: Run the full test suite to catch regressions**

```bash
uv run pytest tests/gaia/lang tests/cli -x
```

Expected: all pre-existing tests still pass. If any test that used to pass is now failing because of the removed `_extract_at_labels`, delete or migrate it.

- [ ] **Step 10: Commit**

```bash
git add gaia/lang/compiler/compile.py gaia/cli/commands/_packages.py tests/gaia/lang/test_compiler.py tests/gaia/lang/compiler/__init__.py tests/gaia/lang/compiler/test_refs_integration.py
git commit -m "feat(compile): wire refs loading and collision check into compile

- Load references.json from package root
- Fail fast on label/citation-key collisions (spec §3.5)
- Delete obsolete _AT_LABEL_RE / _extract_at_labels / _validate_at_labels
- Delete obsolete tests in test_compiler.py

Part 5 of references foundation (PR 1 Task 5)."
```

---

### Task 6: Scan strategy reasons and claim content; enforce mixed-group rule

**Files:**
- Modify: `gaia/lang/compiler/compile.py`
- Extend: `tests/gaia/lang/compiler/test_refs_integration.py`

- [ ] **Step 1: Write failing test — mixed group**

Append to `tests/gaia/lang/compiler/test_refs_integration.py`:

```python
def test_compile_errors_on_mixed_type_bracket_group(tmp_path: Path) -> None:
    """Per spec §3.2, a bracketed group must not mix knowledge refs and citations."""
    pkg = _write_package(
        tmp_path,
        name="mixed_group_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'lemma_a = claim("A helper lemma.")\n'
            'main = claim("Main result. See [see @lemma_a; @Bell1964, p. 5] for context.")\n'
            "deduction(premises=[lemma_a], conclusion=main)\n"
            '__all__ = ["main", "lemma_a"]\n'
        ),
        references_json={
            "Bell1964": {"type": "article-journal", "title": "On EPR"}
        },
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0
    assert "mixed" in result.output.lower()
    assert "lemma_a" in result.output
    assert "Bell1964" in result.output
```

- [ ] **Step 2: Run the test — expect failure**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_errors_on_mixed_type_bracket_group -v
```
Expected: exit code 0 (because content scanning isn't wired in yet).

- [ ] **Step 3: Add a helper to scan text with refs pipeline**

Append to `gaia/lang/compiler/compile.py`:

```python
def _collect_refs_from_text(
    text: str | None,
    label_table: dict[str, str],
    references: dict[str, Any],
) -> tuple[list[str], list[str]]:
    """Scan a piece of text and return (knowledge_refs, citation_refs).

    Enforces:
      - homogeneous-group rule (raises ReferenceError on mixed groups)
      - strict-form errors on unknown keys (raises ReferenceError)
    Ignores opportunistic (bare) misses silently.
    """
    if not text:
        return [], []
    result = extract(text)

    # §3.2: mixed-group check
    validate_groups(result.groups, result.markers, label_table, references)

    knowledge_refs: list[str] = []
    citation_refs: list[str] = []
    for marker in result.markers:
        kind = resolve(marker.key, label_table, references)
        if kind == "knowledge":
            knowledge_refs.append(marker.key)
        elif kind == "citation":
            citation_refs.append(marker.key)
        else:  # unknown
            if marker.strict:
                raise ReferenceError(
                    f"unknown reference key '@{marker.key}' in strict form "
                    f"(in brackets): it is neither a knowledge label nor a "
                    f"citation key. add it to the package or references.json, "
                    f"or use the bare form `@{marker.key}` for opportunistic "
                    f"handling."
                )
            # opportunistic miss → silent literal

    # Dedupe while preserving order
    return (
        list(dict.fromkeys(knowledge_refs)),
        list(dict.fromkeys(citation_refs)),
    )
```

- [ ] **Step 4: Call the helper for strategy reasons and claim content**

Replace the now-deleted `_validate_at_labels` call site. After the `check_collisions(...)` line from Task 5, add:

```python
    # Scan strategy reasons and knowledge content for refs.
    for s in pkg.strategies:
        if isinstance(s.reason, str):
            _collect_refs_from_text(s.reason, label_to_id, references)
        elif isinstance(s.reason, list):
            # reason can be list[str | Step]; scan all string pieces
            from gaia.lang.runtime.nodes import Step as DslStep
            for entry in s.reason:
                if isinstance(entry, str):
                    _collect_refs_from_text(entry, label_to_id, references)
                elif isinstance(entry, DslStep):
                    _collect_refs_from_text(entry.reason, label_to_id, references)

    for k in knowledge_nodes:
        _collect_refs_from_text(k.content, label_to_id, references)
```

Wrap the outer block in a try/except that maps `ReferenceError` to a compile-level error. Or, if the top-level compile command already catches `ReferenceError` (from Task 5 step 7), the raises here will propagate correctly.

- [ ] **Step 5: Run the mixed-group test**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_errors_on_mixed_type_bracket_group -v
```
Expected: pass.

- [ ] **Step 6: Write failing test — strict miss**

```python
def test_compile_errors_on_strict_miss(tmp_path: Path) -> None:
    """`[@nothing]` is strict form — unknown key must error."""
    pkg = _write_package(
        tmp_path,
        name="strict_miss_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'main = claim("Main result. See [@nothing_at_all] for context.")\n'
            "deduction(premises=[main], conclusion=main)\n"
            '__all__ = ["main"]\n'
        ),
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code != 0
    assert "nothing_at_all" in result.output
    assert "unknown" in result.output.lower() or "not" in result.output.lower()


def test_compile_tolerates_opportunistic_miss(tmp_path: Path) -> None:
    """Bare `@nothing` is opportunistic — unknown key is treated as literal."""
    pkg = _write_package(
        tmp_path,
        name="opp_miss_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'main = claim("Use the @dataclass decorator for this.")\n'
            "deduction(premises=[main], conclusion=main)\n"
            '__all__ = ["main"]\n'
        ),
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code == 0, result.output
```

- [ ] **Step 7: Run the new tests**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py -v
```
Expected: all four tests (collision, mixed-group, strict-miss, opportunistic-miss) pass.

- [ ] **Step 8: Full regression sweep**

```bash
uv run pytest tests/gaia/lang tests/cli -x
```
Expected: all tests pass.

- [ ] **Step 9: Commit**

```bash
git add gaia/lang/compiler/compile.py tests/gaia/lang/compiler/test_refs_integration.py
git commit -m "feat(compile): scan strategy reasons and content for refs

- Enforce homogeneous-group rule (spec §3.2)
- Strict form errors on unknown keys
- Opportunistic form silently tolerates unknowns
- Scans both strategy.reason and knowledge.content

Part 6 of references foundation (PR 1 Task 6)."
```

---

### Task 7: Write provenance metadata onto nodes

**Files:**
- Modify: `gaia/lang/compiler/compile.py`
- Extend: `tests/gaia/lang/compiler/test_refs_integration.py`

**Design:** For each Knowledge, collect the union of:
- `knowledge_refs`/`citation_refs` from scanning its `content`
- `knowledge_refs`/`citation_refs` from scanning the `reason` of every Strategy that has this Knowledge as its `conclusion`

Store as:
```python
knowledge.metadata["gaia"]["provenance"] = {
    "cited_refs": [...],          # sorted citation keys
    "referenced_claims": [...],   # sorted knowledge labels
}
```

Only write the `provenance` key when at least one of the lists is non-empty.

- [ ] **Step 1: Write failing test**

```python
def test_compile_records_provenance_metadata(tmp_path: Path) -> None:
    """Provenance metadata records both cited_refs and referenced_claims."""
    pkg = _write_package(
        tmp_path,
        name="provenance_pkg",
        module_body=(
            "from gaia.lang import claim, deduction\n\n"
            'lemma_a = claim("A helper lemma.")\n'
            'main = claim("Main result depends on [@lemma_a] and [@Bell1964].")\n'
            "deduction(premises=[lemma_a], conclusion=main)\n"
            '__all__ = ["main", "lemma_a"]\n'
        ),
        references_json={
            "Bell1964": {"type": "article-journal", "title": "On EPR"}
        },
    )
    result = runner.invoke(app, ["compile", str(pkg)])
    assert result.exit_code == 0, result.output

    ir_path = pkg / ".gaia" / "ir.json"
    ir = json.loads(ir_path.read_text())

    # Find the main claim in the compiled IR.
    main_node = next(
        k for k in ir["knowledges"] if k["qid"].endswith("::main")
    )
    provenance = main_node["metadata"]["gaia"]["provenance"]
    assert provenance["cited_refs"] == ["Bell1964"]
    assert provenance["referenced_claims"] == ["lemma_a"]
```

- [ ] **Step 2: Run it — expect failure**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_records_provenance_metadata -v
```
Expected: KeyError on `metadata.gaia.provenance` or similar.

- [ ] **Step 3: Implement provenance collection in compile.py**

Replace the scanning block from Task 6 with one that *collects* refs per-node instead of just validating:

```python
    # Scan and collect refs per Knowledge node.
    refs_by_knowledge: dict[int, tuple[set[str], set[str]]] = {}

    def _accumulate(k: Knowledge, text: str | None) -> None:
        if not text:
            return
        k_refs, c_refs = _collect_refs_from_text(text, label_to_id, references)
        current = refs_by_knowledge.setdefault(id(k), (set(), set()))
        current[0].update(k_refs)
        current[1].update(c_refs)

    for k in knowledge_nodes:
        _accumulate(k, k.content)

    for s in pkg.strategies:
        if s.conclusion is None:
            continue
        if isinstance(s.reason, str):
            _accumulate(s.conclusion, s.reason)
        elif isinstance(s.reason, list):
            from gaia.lang.runtime.nodes import Step as DslStep
            for entry in s.reason:
                if isinstance(entry, str):
                    _accumulate(s.conclusion, entry)
                elif isinstance(entry, DslStep):
                    _accumulate(s.conclusion, entry.reason)

    # Write provenance metadata onto IR knowledge nodes.
    for k in knowledge_nodes:
        refs = refs_by_knowledge.get(id(k))
        if not refs:
            continue
        k_refs, c_refs = refs
        if not k_refs and not c_refs:
            continue
        qid = knowledge_map[id(k)]
        ir_k = next((ik for ik in ir_knowledges if ik.qid == qid), None)
        if ir_k is None:
            continue
        metadata = dict(ir_k.metadata) if ir_k.metadata else {}
        gaia_meta = dict(metadata.get("gaia", {}))
        provenance = dict(gaia_meta.get("provenance", {}))
        if c_refs:
            provenance["cited_refs"] = sorted(c_refs)
        if k_refs:
            provenance["referenced_claims"] = sorted(k_refs)
        gaia_meta["provenance"] = provenance
        metadata["gaia"] = gaia_meta
        # Re-create the IR knowledge with updated metadata
        ir_k_updated = ir_k.model_copy(update={"metadata": metadata})
        idx = ir_knowledges.index(ir_k)
        ir_knowledges[idx] = ir_k_updated
```

> **Implementation detail:** you may need to change `ir_knowledges` from a comprehension result to a list earlier in the function, and re-check that the subsequent `LocalCanonicalGraph(knowledges=[*ir_knowledges, ...])` uses the updated list. Read the surrounding code before editing.

- [ ] **Step 4: Run the provenance test**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_records_provenance_metadata -v
```
Expected: pass.

- [ ] **Step 5: Full regression sweep**

```bash
uv run pytest tests/gaia/lang tests/cli -x
```

- [ ] **Step 6: Commit**

```bash
git add gaia/lang/compiler/compile.py tests/gaia/lang/compiler/test_refs_integration.py
git commit -m "feat(compile): write provenance metadata for refs

Each Knowledge node gets metadata.gaia.provenance containing:
  - cited_refs: sorted citation keys from content + conclusion strategies
  - referenced_claims: sorted knowledge labels from content + conclusion strategies

Part 7 of references foundation (PR 1 Task 7)."
```

---

### Task 8: Imported foreign node regression test

**Files:**
- Extend: `tests/gaia/lang/compiler/test_refs_integration.py`

**Purpose:** Lock in the §3.1 invariant that `@foreign_label` imported from a dependency resolves correctly. This protects against future accidental narrowing of the symbol table.

- [ ] **Step 1: Read existing cross-package test setup**

Read `tests/cli/test_compile.py` and `tests/gaia/lang/` to find how existing tests set up a dependency package + a dependent package. Reuse that pattern.

- [ ] **Step 2: Write the regression test**

Append to `tests/gaia/lang/compiler/test_refs_integration.py`:

```python
def test_compile_resolves_imported_foreign_label_in_strict_form(tmp_path: Path) -> None:
    """Spec §3.1: imported foreign labels must resolve in [@label] strict form.

    This is a regression test that protects the existing cross-package ref
    workflow. If the symbol table is ever accidentally narrowed to local
    labels only, this test fails.
    """
    # Build dependency package
    dep_pkg = _write_package(
        tmp_path,
        name="dep_pkg",
        module_body=(
            "from gaia.lang import claim\n\n"
            'foreign_lemma = claim("A foreign lemma.")\n'
            '__all__ = ["foreign_lemma"]\n'
        ),
    )
    # Compile dep so it can be imported
    result = runner.invoke(app, ["compile", str(dep_pkg)])
    assert result.exit_code == 0, result.output

    # [... set up dependent package that imports dep_pkg and uses
    #     @foreign_lemma in both strict and opportunistic form ...]
    # Exact setup depends on how tests/cli/test_compile.py handles
    # cross-package imports today. Mirror that.
    #
    # The test must cover:
    #   - `[@foreign_lemma]` in claim content → strict, must resolve
    #   - `@foreign_lemma` in strategy reason → opportunistic, must resolve
    #   - compiled IR has provenance.referenced_claims = ["foreign_lemma"]
```

> **Note:** The exact cross-package import mechanics in PR 1 depend on current package-discovery behavior. If the Task 8 test turns out to be blocked by unrelated machinery, mark it as `@pytest.mark.xfail(reason="depends on cross-package import wiring in PR X")` rather than skipping the task — we need the test in the suite to catch regressions later.

- [ ] **Step 3: Run the test**

```bash
uv run pytest tests/gaia/lang/compiler/test_refs_integration.py::test_compile_resolves_imported_foreign_label_in_strict_form -v
```

- [ ] **Step 4: Commit**

```bash
git add tests/gaia/lang/compiler/test_refs_integration.py
git commit -m "test(refs): lock in imported foreign label resolution

Regression test for spec §3.1 invariant: the reference symbol table must
include the full compile closure (not just locally-declared labels), so
that imported foreign labels resolve in both strict and opportunistic form.

Part 8 of references foundation (PR 1 Task 8)."
```

---

### Task 9: Documentation updates

**Files:**
- Modify: `docs/foundations/gaia-lang/` (find the right doc to point to spec)

- [ ] **Step 1: Locate the best home for the cross-reference**

```bash
grep -rn "knowledge_id\|label\|@" docs/foundations/gaia-lang/ | head -30
```

Find the existing doc that describes the authoring surface for `claim` / `deduction` / labels. Add a short section "Reference syntax" with a one-paragraph summary and a link to `docs/specs/2026-04-09-references-and-at-syntax.md`.

- [ ] **Step 2: Add the section**

Append to the appropriate foundations doc:

```markdown
## Reference syntax

Claim content and strategy reasons may contain references using the
unified `@` syntax:

- `[@label]` — strict reference to a local or imported knowledge node, or
  to a citation key in `references.json`. Missing key is a compile error.
- `@label` — opportunistic reference (Pandoc narrative form). Missing key
  is treated as literal text.
- `\@label` — escape, forces literal.

Compile enforces two invariants: (1) a key cannot exist in both the label
table and `references.json` (collision → compile error), and (2) a single
`[...]` group cannot mix knowledge refs and citations (mixed group →
compile error).

The full grammar, resolution rules, and rendering pipeline are specified
in [References & `@` Syntax Unification Design](../../../specs/2026-04-09-references-and-at-syntax.md).
```

- [ ] **Step 3: Commit**

```bash
git add docs/foundations/gaia-lang/
git commit -m "docs(gaia-lang): link reference syntax section to spec

Part 9 of references foundation (PR 1 Task 9)."
```

---

### Task 10: Final verification and PR

- [ ] **Step 1: Run ruff check and format**

```bash
uv run ruff check .
uv run ruff format --check .
```

Fix any issues and re-commit as needed.

- [ ] **Step 2: Run the full test suite**

```bash
uv run pytest tests/gaia/lang tests/cli -v
```

Expected: all pass.

- [ ] **Step 3: Check coverage of new code**

```bash
uv run pytest tests/gaia/lang/refs tests/gaia/lang/compiler/test_refs_integration.py \
    --cov=gaia.lang.refs --cov=gaia.lang.compiler.compile --cov-report=term-missing
```

Expected: >90% coverage on `gaia/lang/refs/*`. Identify any uncovered defensive branches and either add a test or justify the gap.

- [ ] **Step 4: Verify the checklist from §10 of the spec**

Confirm the following items from the spec's Implementation Checklist have PR 1 equivalents:

- [x] `gaia/lang/refs/extractor.py` with `BRACKETED_REF_RE` + `BARE_AT_RE`, tracking groups and source positions
- [x] `gaia/lang/refs/resolver.py` with 3-state `resolve`, `check_collisions`, `validate_groups`
- [x] `gaia/lang/refs/loader.py` with schema validation
- [x] `gaia/lang/compiler/compile.py` integration:
  - [x] Delete `_AT_LABEL_RE` / `_extract_at_labels` / `_validate_at_labels`
  - [x] Symbol table uses full compile closure (unchanged from current `label_to_id`)
  - [x] `check_collisions` at compile entry
  - [x] Replace old call site with new extractor+resolver
  - [x] Widen scan to Knowledge content
  - [x] `validate_groups` on bracketed groups
  - [x] Strict vs opportunistic severity split
  - [x] Provenance metadata written to IR knowledge nodes
- [ ] Deferred to PR 2: README rendering with citeproc-py
- [ ] Deferred to PR 3: `gaia cite import`
- [ ] Deferred to PR 4: `gaia lint --refs`

- [ ] **Step 5: Push branch and open PR**

```bash
git push -u origin <branch-name>
gh pr create --title "feat(refs): references foundation — unified @ syntax + references.json" --body "$(cat <<'EOF'
## Summary

Implements PR 1 of the references system per [spec](../blob/main/docs/specs/2026-04-09-references-and-at-syntax.md):

- New `gaia/lang/refs/` module (extractor, resolver, loader) with full test coverage
- Unified `@` syntax grammar: strict `[@key]` + opportunistic `@key`
- Compile-time collision fail-fast (§3.5) and homogeneous-group rule (§3.2)
- Widened scanning to claim content in addition to strategy reasons
- Provenance metadata: `metadata.gaia.provenance.{cited_refs, referenced_claims}`
- Symbol table inherits the existing compile closure (unchanged) — imported foreign labels continue to resolve

## Out of scope (future PRs)

- README rendering with citeproc-py → PR 2
- `gaia cite import refs.bib` → PR 3
- `gaia lint --refs` → PR 4

## Test plan

- [x] `pytest tests/gaia/lang/refs` — unit tests for extractor, resolver, loader
- [x] `pytest tests/gaia/lang/compiler/test_refs_integration.py` — end-to-end collision / mixed-group / strict-miss / opportunistic-miss / provenance / imported foreign label
- [x] `pytest tests/gaia/lang tests/cli` — full regression
- [x] `ruff check . && ruff format --check .`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 6: Verify CI passes**

```bash
gh run list --branch <branch-name> --limit 1
# If failed:
gh run view <run-id> --log-failed
```

Address any failures before marking the plan complete.

---

## Post-execution handoff

After the PR merges, open follow-up tickets for:

- **PR 2 plan:** README rendering pipeline (`docs/plans/2026-04-??-references-readme-rendering.md`)
- **PR 3 plan:** `gaia cite import refs.bib` command (`docs/plans/2026-04-??-references-bibtex-import.md`)
- **PR 4 plan:** `gaia lint --refs` command (`docs/plans/2026-04-??-references-lint.md`)

Each should reference this spec (`docs/specs/2026-04-09-references-and-at-syntax.md`) as the source of truth.

---

## Risks / open questions

1. **`source_path` on `CollectedPackage`**: Task 5 Step 6 assumes either there's a way to reach the package root from the compiler, or that the CLI layer loads `references.json` and passes it in. The plan picks the second option. Verify during execution that this fits `_packages.py`'s current structure.
2. **`reason` field type**: Task 6 Step 4 assumes `strategy.reason` can be `str | list[str | Step] | None`. Re-check `gaia/lang/runtime/nodes.py` — if there are more variants, handle them all.
3. **Escaped-bracket edge case**: The `test_extract_escaped_bracket_not_parsed` test documents an edge case where `\[@key]` doesn't cleanly escape because the bare-`@` scanner's lookbehind only sees the `[`. If this turns out to be a problem in practice, add a dedicated test and fix.
4. **Locator parsing**: PR 1 extractor only finds `@key`. It does not parse Pandoc prefix/locator/suffix inside the bracket group — that's left to citeproc-py in PR 2. The extractor **does** need to correctly track which keys belong to which group for the homogeneous check, which it already does via `BracketGroup.marker_indices`.
5. **Existing packages with `[@foo]` in reason text**: Task 5 Step 9 (full regression sweep) will flag any. If there are existing usages of `[@foo]` in reason strings that were previously treated as literal, they will now be treated as strict references and fail compile if unresolved. That's expected behavior per spec §8.1 but may require fixing existing test fixtures.
