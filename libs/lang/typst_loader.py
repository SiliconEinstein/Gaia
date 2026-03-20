"""Load a Typst-based Gaia package and extract the knowledge graph as JSON."""

from __future__ import annotations

import json
import tomllib
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
    data.setdefault("package", None)
    data.setdefault("version", None)

    return data


def _find_project_root(pkg_path: Path) -> str:
    """Find repository root by walking up to find pyproject.toml."""
    root = pkg_path.resolve()
    while root != root.parent:
        if (root / "pyproject.toml").exists():
            return str(root)
        root = root.parent
    return str(pkg_path.resolve())


def _strip_label(label_str: str) -> str:
    """Strip angle brackets from Typst label string: '<foo_bar>' → 'foo_bar'."""
    return label_str.strip("<>")


def _extract_metadata_from_figure(figure: dict) -> dict | None:
    """Extract hidden metadata dict from a figure's body children."""
    body = figure.get("body", {})
    children = body.get("children", [body]) if body.get("func") == "sequence" else [body]
    for child in children:
        if child.get("func") == "hide":
            inner = child.get("body", {})
            if inner.get("func") == "metadata":
                return inner.get("value")
    return None


def _extract_text_from_figure(figure: dict) -> str:
    """Extract visible text content from a figure body (skip hidden metadata)."""
    body = figure.get("body", {})
    children = body.get("children", [body]) if body.get("func") == "sequence" else [body]
    parts = []
    for child in children:
        if child.get("func") == "hide":
            continue
        if child.get("func") == "block":
            continue  # skip proof block
        parts.append(_flatten_content(child))
    return " ".join(parts).strip()


# Supplement text → normalized type
_SUPPLEMENT_TYPE_MAP = {
    "Setting": "setting",
    "Question": "question",
    "Claim": "claim",
    "Action": "action",
    "Contradiction": "relation",
    "Equivalence": "relation",
}


def load_typst_package_v4(pkg_path: Path) -> dict:
    """Load a v4 Typst package using typst query on figure elements.

    v4 packages use Typst labels for identity, from: for premises,
    and gaia-bibliography for cross-package references.
    """
    pkg_path = Path(pkg_path)
    entrypoint = pkg_path / "lib.typ"
    if not entrypoint.exists():
        raise FileNotFoundError(f"No lib.typ found in {pkg_path}")

    # Read package metadata from typst.toml
    toml_path = pkg_path / "typst.toml"
    with open(toml_path, "rb") as f:
        toml_data = tomllib.load(f)
    pkg_meta = toml_data.get("package", {})
    package_name = pkg_meta.get("name", pkg_path.name)
    version = pkg_meta.get("version", "0.0.0")

    root = _find_project_root(pkg_path)

    # Query gaia-node figures (local knowledge nodes)
    raw_nodes_json = typst.query(str(entrypoint), 'figure.where(kind: "gaia-node")', root=root)
    raw_nodes = json.loads(raw_nodes_json) if isinstance(raw_nodes_json, str) else raw_nodes_json

    # Query gaia-ext figures (external references from gaia-bibliography)
    raw_ext_json = typst.query(str(entrypoint), 'figure.where(kind: "gaia-ext")', root=root)
    raw_ext = json.loads(raw_ext_json) if isinstance(raw_ext_json, str) else raw_ext_json

    nodes = []
    factors = []
    constraints = []

    for figure in raw_nodes:
        label = _strip_label(figure.get("label", ""))
        supplement = figure.get("supplement", {})
        sup_text = supplement.get("text", "") if isinstance(supplement, dict) else str(supplement)
        node_type = _SUPPLEMENT_TYPE_MAP.get(sup_text, "claim")
        content = _extract_text_from_figure(figure)
        meta = _extract_metadata_from_figure(figure) or {}

        node = {
            "name": label,
            "type": node_type,
            "content": content,
            "kind": meta.get("kind"),
        }
        nodes.append(node)

        # Process from: parameter → reasoning factor
        from_labels = meta.get("from", [])
        if from_labels:
            premises = [_strip_label(lbl) for lbl in from_labels]
            factors.append(
                {
                    "type": "reasoning",
                    "premises": premises,
                    "conclusion": label,
                }
            )

        # Process relation between: → constraint
        gaia_type = meta.get("gaia-type", "")
        if gaia_type == "relation":
            between_labels = meta.get("between", [])
            rel_type = meta.get("rel-type", "contradiction")
            constraints.append(
                {
                    "name": label,
                    "type": rel_type,
                    "between": [_strip_label(lbl) for lbl in between_labels],
                }
            )

    # Process external nodes
    ext_nodes = []
    for figure in raw_ext:
        label = _strip_label(figure.get("label", ""))
        meta = _extract_metadata_from_figure(figure) or {}
        ext_nodes.append(
            {
                "name": label,
                "type": meta.get("ext-content-type", "claim"),
                "content": "",
                "kind": None,
                "external": True,
                "ext_package": meta.get("ext-package", ""),
                "ext_version": meta.get("ext-version", ""),
                "ext_node": meta.get("ext-node", label),
            }
        )

    return {
        "package": package_name,
        "version": version,
        "nodes": nodes + ext_nodes,
        "factors": factors,
        "constraints": constraints,
        "refs": [],
        "modules": [],
        "module_titles": {},
    }
