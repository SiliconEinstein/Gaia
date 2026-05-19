"""Published alpha-0 docs should teach the canonical surface.

Migration-context sections (those whose heading mentions "old" or
"migrat") are allowed to reference the removed flat verbs and legacy
import paths — that is the whole point of a migration section. The test
catches stale teaching surface elsewhere in the published docs.
"""

from __future__ import annotations

import re
from pathlib import Path

DOC_ROOTS = (Path("docs/for-users"), Path("docs/foundations"))
STALE_PATTERNS = {
    "legacy gaia.lang import": re.compile(r"from gaia\.lang import"),
    "legacy gaia.logic import": re.compile(r"from gaia\.logic import"),
    "legacy gaia.ir import": re.compile(r"from gaia\.ir import"),
    "legacy gaia.bp import": re.compile(r"from gaia\.bp import"),
    "legacy gaia.trace import": re.compile(r"from gaia\.trace import"),
    "legacy gaia.inquiry import": re.compile(r"from gaia\.inquiry import"),
    "legacy gaia namespace mention": re.compile(r"gaia\.(?:bp|ir|lang|logic|inquiry|trace)\b"),
    "flat gaia init": re.compile(r"\bgaia init\b"),
    "flat gaia compile": re.compile(r"\bgaia compile\b"),
    "flat gaia check": re.compile(r"\bgaia check\b"),
    "flat gaia infer": re.compile(r"\bgaia infer\b"),
    "flat gaia render": re.compile(r"\bgaia render\b"),
    "flat gaia starmap": re.compile(r"\bgaia starmap\b"),
    "flat gaia add": re.compile(r"\bgaia add\b"),
    "flat gaia register": re.compile(r"\bgaia register\b"),
}

# Headings that mark a migration-context section. A match anywhere under
# such a heading (until the next heading at the same-or-shallower depth)
# is exempt because the section's purpose is to enumerate the legacy
# surface.
_MIGRATION_HEADING = re.compile(
    r"(?i)^(#+)\s+.*\b(?:old|migrat|legacy|removed|tombstone)\b",
)
_HEADING = re.compile(r"^(#+)\s+")


def _migration_line_set(text: str) -> set[int]:
    """Return 1-based line numbers that fall inside a migration-context section."""
    lines = text.splitlines()
    exempt: set[int] = set()
    in_section_depth: int | None = None
    for idx, line in enumerate(lines, start=1):
        migration_match = _MIGRATION_HEADING.match(line)
        if migration_match:
            in_section_depth = len(migration_match.group(1))
            exempt.add(idx)
            continue
        if in_section_depth is not None:
            heading_match = _HEADING.match(line)
            if heading_match and len(heading_match.group(1)) <= in_section_depth:
                in_section_depth = None
                # fall through — the new heading itself is not exempt
            else:
                exempt.add(idx)
    return exempt


def test_published_docs_do_not_teach_tombstoned_alpha0_surface() -> None:
    stale_hits: list[str] = []
    for root in DOC_ROOTS:
        for path in sorted(root.rglob("*.md")):
            text = path.read_text()
            exempt_lines = _migration_line_set(text)
            for label, pattern in STALE_PATTERNS.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    if line in exempt_lines:
                        continue
                    stale_hits.append(f"{path}:{line}: {label}: {match.group(0)!r}")

    assert stale_hits == []
