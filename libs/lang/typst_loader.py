"""Load a Typst-based Gaia package and extract the knowledge graph as JSON."""

from __future__ import annotations

import json
from pathlib import Path

import typst


def _flatten_content(node: dict | str | list) -> str:
    """Recursively flatten a Typst content tree to plain text."""
    if isinstance(node, str):
        return node
    if isinstance(node, list):
        return "".join(_flatten_content(child) for child in node)
    if isinstance(node, dict):
        func = node.get("func", "")
        if func == "text":
            return node.get("text", "")
        if func == "space":
            return " "
        if func == "parbreak":
            return "\n\n"
        if func == "linebreak":
            return "\n"
        if func == "smartquote":
            return '"'
        if func == "ref":
            target = node.get("target", "")
            # Strip angle brackets: "<foo-bar>" → "foo-bar", then restore underscores
            return target.strip("<>").replace("-", "_")
        children = node.get("children", [])
        if children:
            return "".join(_flatten_content(c) for c in children)
        body = node.get("body")
        if body:
            return _flatten_content(body)
    return ""


def load_typst_package(pkg_path: Path) -> dict:
    """Compile a Typst package and extract the knowledge graph via metadata query.

    Args:
        pkg_path: Path to directory containing typst.toml and lib.typ.

    Returns:
        Dict with keys: nodes, factors, refs, modules, exports.
        Also includes proof_traces and constraints for v2 packages.
        Node content is flattened to plain text strings.
    """
    pkg_path = Path(pkg_path)
    entrypoint = pkg_path / "lib.typ"
    if not entrypoint.exists():
        raise FileNotFoundError(f"No lib.typ found in {pkg_path}")

    # Find repository root by walking up to find pyproject.toml
    root = pkg_path.resolve()
    while root != root.parent:
        if (root / "pyproject.toml").exists():
            break
        root = root.parent

    raw = typst.query(str(entrypoint), "<gaia-graph>", field="value", one=True, root=str(root))
    data = json.loads(raw) if isinstance(raw, str) else raw

    # Normalize hyphenated keys to snake_case
    if "module-titles" in data:
        data["module_titles"] = data.pop("module-titles")
    if "proof-traces" in data:
        data["proof_traces"] = data.pop("proof-traces")

    # Flatten content in nodes
    for node in data.get("nodes", []):
        if isinstance(node.get("content"), (dict, list)):
            node["content"] = _flatten_content(node["content"]).strip()
        # Normalize ctx -> context key for downstream consumers (v1 compat)
        if "ctx" in node:
            node["context"] = node.pop("ctx")

    # Normalize ctx -> context in factors (v1 compat)
    for factor in data.get("factors", []):
        if "ctx" in factor:
            factor["context"] = factor.pop("ctx")

    # Flatten content in proof trace steps
    for trace in data.get("proof_traces", []):
        for step in trace.get("steps", []):
            if isinstance(step.get("content"), (dict, list)):
                step["content"] = _flatten_content(step["content"]).strip()

    # Ensure v2 keys exist (default to empty for v1 packages)
    data.setdefault("proof_traces", [])
    data.setdefault("constraints", [])

    return data
