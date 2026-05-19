"""Executable examples from the Bayes foundation document."""

from __future__ import annotations

import re
from pathlib import Path


def test_bayes_foundation_examples_execute():
    doc_path = Path("docs/foundations/gaia-lang/bayes.md")
    content = doc_path.read_text()
    blocks = re.findall(r"```python testable\n(.*?)```", content, flags=re.S)

    assert blocks, "expected at least one python testable block in bayes.md"
    for block in blocks:
        namespace: dict[str, object] = {"__name__": "__bayes_doc_example__"}
        exec(block, namespace)
