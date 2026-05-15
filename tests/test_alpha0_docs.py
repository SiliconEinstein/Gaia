"""Published alpha-0 docs should teach the canonical surface."""

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


def test_published_docs_do_not_teach_tombstoned_alpha0_surface() -> None:
    stale_hits: list[str] = []
    for root in DOC_ROOTS:
        for path in sorted(root.rglob("*.md")):
            text = path.read_text()
            for label, pattern in STALE_PATTERNS.items():
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    stale_hits.append(f"{path}:{line}: {label}: {match.group(0)!r}")

    assert stale_hits == []
