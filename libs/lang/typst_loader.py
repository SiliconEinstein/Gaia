"""Load a Typst-based Gaia package and extract the knowledge graph as JSON."""

from __future__ import annotations

import json
from pathlib import Path

import typst


def _flatten_fraction_part(node: dict | str | list | None) -> str:
    flat = _flatten_content(node).strip()
    if not flat:
        return ""
    if any(ch.isspace() for ch in flat):
        return f"({flat})"
    return flat


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
        if func == "symbol":
            return node.get("text", "")
        if func == "space":
            return " "
        if func == "parbreak":
            return "\n\n"
        if func == "linebreak":
            return "\n"
        if func == "smartquote":
            return '"'
        if func == "primes":
            return "'" * node.get("count", 0)
        if func == "ref":
            target = node.get("target", "")
            # Strip angle brackets: "<foo-bar>" → "foo-bar", then restore underscores
            return target.strip("<>").replace("-", "_")
        if func == "equation":
            return _flatten_content(node.get("body")).strip()
        if func == "frac":
            num = _flatten_fraction_part(node.get("num"))
            denom = _flatten_fraction_part(node.get("denom"))
            if num and denom:
                return f"{num}/{denom}"
            return num or denom
        if func == "attach":
            parts = [_flatten_content(node.get("base"))]
            for key, prefix in (("b", "_"), ("t", "^"), ("tr", "")):
                value = node.get(key)
                if value is None:
                    continue
                flat = _flatten_content(value).strip()
                if flat:
                    parts.append(f"{prefix}{flat}")
            return "".join(parts)
        children = node.get("children", [])
        if children:
            return "".join(_flatten_content(c) for c in children)
        body = node.get("body")
        if body is not None:
            return _flatten_content(body)
    return ""


def load_typst_package(pkg_path: Path) -> dict:
    """Compile a Typst package and extract the knowledge graph via metadata query.

    Args:
        pkg_path: Path to directory containing typst.toml and lib.typ.

    Returns:
        Dict with keys: nodes, factors, refs, modules, exports, constraints.
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

    # Flatten content in nodes
    for node in data.get("nodes", []):
        if node.get("content") is None:
            node["content"] = ""
        elif isinstance(node.get("content"), (dict, list)):
            node["content"] = _flatten_content(node["content"]).strip()
        # Normalize ctx -> context key for downstream consumers (v1 compat)
        if "ctx" in node:
            node["context"] = node.pop("ctx")

    # Normalize ctx -> context in factors (v1 compat)
    for factor in data.get("factors", []):
        if "ctx" in factor:
            factor["context"] = factor.pop("ctx")

    # Ensure keys exist (default to empty for v1 packages)
    data.setdefault("constraints", [])

    return data
