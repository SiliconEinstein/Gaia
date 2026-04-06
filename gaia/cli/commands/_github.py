"""Orchestrate GitHub output generation for a compiled Gaia package.

Combines wiki pages, graph.json, manifest.json, assets, section placeholders,
and a README skeleton into a single ``.github-output/`` directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gaia.cli.commands._graph_json import generate_graph_json
from gaia.cli.commands._manifest import generate_manifest
from gaia.cli.commands._simplified_mermaid import render_simplified_mermaid
from gaia.cli.commands._wiki import generate_all_wiki


def generate_github_output(
    ir: dict,
    pkg_path: Path,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
    exported_ids: set[str] | None = None,
    pkg_metadata: dict | None = None,
) -> Path:
    """Generate the full ``.github-output/`` tree and return its path.

    Steps:
    1. Create directory structure under ``pkg_path / .github-output``
    2. Write wiki pages
    3. Write ``docs/public/data/graph.json``
    4. Copy ``beliefs.json`` if beliefs_data is available
    5. Write ``docs/public/data/meta.json``
    6. Copy artifacts to ``docs/public/assets/``
    7. Create section placeholder files (one per module)
    8. Write ``manifest.json``
    9. Generate README.md skeleton
    10. Return the output directory path
    """
    exported = exported_ids or set()
    metadata = pkg_metadata or {}

    output_dir = pkg_path / ".github-output"
    wiki_dir = output_dir / "wiki"
    data_dir = output_dir / "docs" / "public" / "data"
    assets_dir = output_dir / "docs" / "public" / "assets"
    sections_dir = data_dir / "sections"

    # Create directory structure
    for d in (wiki_dir, data_dir, assets_dir, sections_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── 1. Wiki pages ──
    wiki_pages = generate_all_wiki(ir, beliefs_data=beliefs_data, param_data=param_data)
    for filename, content in wiki_pages.items():
        (wiki_dir / filename).write_text(content, encoding="utf-8")

    # ── 2. graph.json ──
    graph_json = generate_graph_json(
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported,
    )
    (data_dir / "graph.json").write_text(graph_json, encoding="utf-8")

    # ── 3. beliefs.json (if available) ──
    if beliefs_data is not None:
        (data_dir / "beliefs.json").write_text(
            json.dumps(beliefs_data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    # ── 4. meta.json ──
    meta = {
        "name": metadata.get("name", ir.get("package_name", "")),
        "description": metadata.get("description", ""),
    }
    (data_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # ── 5. Copy artifacts to assets ──
    artifacts_dir = pkg_path / "artifacts"
    asset_names: list[str] = []
    if artifacts_dir.is_dir():
        for item in sorted(artifacts_dir.iterdir()):
            if item.is_file():
                shutil.copy2(item, assets_dir / item.name)
                asset_names.append(item.name)

    # ── 6. Section placeholders (one per unique module) ──
    modules: set[str] = set()
    for k in ir.get("knowledges", []):
        mod = k.get("module")
        if mod:
            modules.add(mod)
    for mod in sorted(modules):
        placeholder = sections_dir / f"{mod}.md"
        if not placeholder.exists():
            placeholder.write_text(
                f"# {mod}\n\n<!-- Section placeholder for module: {mod} -->\n",
                encoding="utf-8",
            )

    # ── 7. manifest.json ──
    manifest_json = generate_manifest(
        ir,
        exported,
        list(wiki_pages.keys()),
        assets=asset_names,
    )
    (output_dir / "manifest.json").write_text(manifest_json, encoding="utf-8")

    # ── 8. README.md skeleton ──
    readme = _generate_readme_skeleton(
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported,
        pkg_metadata=metadata,
    )
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    return output_dir


def _generate_readme_skeleton(
    ir: dict,
    *,
    beliefs_data: dict | None = None,
    param_data: dict | None = None,
    exported_ids: set[str] | None = None,
    pkg_metadata: dict | None = None,
) -> str:
    """Build a README.md with Mermaid overview, conclusion table, and placeholders."""
    exported = exported_ids or set()
    metadata = pkg_metadata or {}
    pkg_name = metadata.get("name", ir.get("package_name", "Package"))
    description = metadata.get("description", "")

    lines: list[str] = []

    # Title and description
    lines.append(f"# {pkg_name}")
    lines.append("")
    if description:
        lines.append(description)
        lines.append("")

    # Badges placeholder
    lines.append("<!-- badges:start -->")
    lines.append("<!-- badges:end -->")
    lines.append("")

    # Simplified Mermaid graph (only when beliefs are available)
    beliefs: dict[str, float] = {}
    priors: dict[str, float] = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}
    if param_data:
        priors = {p["knowledge_id"]: p["value"] for p in param_data.get("priors", [])}

    if beliefs:
        lines.append("## Overview")
        lines.append("")
        mermaid = render_simplified_mermaid(ir, beliefs, priors, exported)
        lines.append(mermaid)
        lines.append("")

    # Exported conclusions table
    knowledge_by_id = {k["id"]: k for k in ir.get("knowledges", [])}
    exported_nodes = [knowledge_by_id[eid] for eid in sorted(exported) if eid in knowledge_by_id]
    if exported_nodes:
        lines.append("## Conclusions")
        lines.append("")
        lines.append("| Label | Content | Belief |")
        lines.append("|-------|---------|--------|")
        for k in exported_nodes:
            label = k.get("label", "")
            content = k.get("content", "")
            # Truncate long content for table readability
            if len(content) > 80:
                content = content[:77] + "..."
            kid = k["id"]
            belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "\u2014"
            lines.append(f"| {label} | {content} | {belief} |")
        lines.append("")

    # Placeholder markers
    lines.append("<!-- content:start -->")
    lines.append("<!-- content:end -->")
    lines.append("")

    return "\n".join(lines)
