"""Orchestrate GitHub output generation for a compiled Gaia package.

Combines wiki pages, graph.json, manifest.json, assets, section placeholders,
and a README skeleton into a single ``.github-output/`` directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from gaia.cli.commands._graph_json import write_graph_json
from gaia.cli.commands._manifest import generate_manifest
from gaia.cli.commands._render_priors import format_belief
from gaia.cli.commands._wiki import (
    generate_wiki_home,
    generate_wiki_inference,
    generate_wiki_module,
)
from gaia.engine.ir.coarsen import coarsen_ir

_MAX_MI_PREMISES = 12
_MAX_MI_GRAPH_ITEMS = 2500


def _write_meta_json(
    data_dir: Path,
    ir: dict[str, Any],
    pkg_metadata: dict[str, Any],
) -> None:
    """Write ``meta.json`` with package identity and description."""
    meta = {
        "package_name": ir.get("package_name", ""),
        "namespace": ir.get("namespace", ""),
        "name": pkg_metadata.get("name", ir.get("package_name", "")),
        "description": pkg_metadata.get("description", ""),
    }
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "meta.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def _copy_artifacts(artifacts_dir: Path, assets_dir: Path) -> list[str]:
    """Copy package artifacts into GitHub assets and return relative names."""
    asset_names: list[str] = []
    if not artifacts_dir.is_dir():
        return asset_names
    for item in sorted(artifacts_dir.rglob("*")):
        if item.is_file():
            rel = item.relative_to(artifacts_dir)
            dest = assets_dir / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, dest)
            asset_names.append(str(rel))
    return asset_names


def _wiki_module_names(ir: dict[str, Any]) -> list[str]:
    """Return stable wiki module names, including Root for module-less nodes."""
    return sorted({k.get("module") or "Root" for k in ir.get("knowledges", [])})


def _section_module_names(ir: dict[str, Any]) -> set[str]:
    """Return modules that should get SPA section files."""
    return {k["module"] for k in ir.get("knowledges", []) if k.get("module")}


def _write_wiki_pages_and_sections(
    *,
    ir: dict[str, Any],
    wiki_dir: Path,
    sections_dir: Path,
    beliefs_data: dict[str, Any] | None,
    param_data: dict[str, Any] | None,
) -> list[str]:
    """Write GitHub wiki pages and section markdown without retaining all pages."""
    wiki_page_names: list[str] = []

    (wiki_dir / "Home.md").write_text(
        generate_wiki_home(ir, beliefs_data=beliefs_data),
        encoding="utf-8",
    )
    wiki_page_names.append("Home.md")

    section_modules = _section_module_names(ir)
    for mod in _wiki_module_names(ir):
        filename = f"Module-{mod.replace('_', '-')}.md"
        content = generate_wiki_module(
            ir,
            mod,
            beliefs_data=beliefs_data,
            param_data=param_data,
        )
        (wiki_dir / filename).write_text(content, encoding="utf-8")
        wiki_page_names.append(filename)
        if mod in section_modules:
            (sections_dir / f"{mod}.md").write_text(content, encoding="utf-8")

    if beliefs_data is not None:
        (wiki_dir / "Inference-Results.md").write_text(
            generate_wiki_inference(ir, beliefs_data, param_data=param_data),
            encoding="utf-8",
        )
        wiki_page_names.append("Inference-Results.md")

    return wiki_page_names


def _default_outline_priors(
    ir: dict[str, Any],
    param_data: dict[str, Any] | None,
) -> dict[str, float]:
    """Build default priors for narrative outline generation."""
    node_priors: dict[str, float] = {}
    for k in ir["knowledges"]:
        kid = k["id"]
        meta = k.get("metadata") or {}
        helper_kind = meta.get("helper_kind", "")
        if helper_kind in (
            "implication_result",
            "equivalence_result",
            "contradiction_result",
            "complement_result",
        ):
            node_priors[kid] = 1.0 - 1e-3
        else:
            node_priors[kid] = 0.5
    if param_data:
        for p in param_data.get("priors", []):
            node_priors[p["knowledge_id"]] = p["value"]
    return node_priors


def _strategy_params_from_param_data(param_data: dict[str, Any] | None) -> dict[str, list[float]]:
    """Extract strategy conditional parameters from a parameterization payload."""
    strategy_params: dict[str, list[float]] = {}
    if not param_data:
        return strategy_params
    for item in param_data.get("strategy_params", []):
        strategy_id = item.get("strategy_id", "")
        if item.get("conditional_probabilities"):
            strategy_params[strategy_id] = item["conditional_probabilities"]
        elif item.get("conditional_probability") is not None:
            strategy_params[strategy_id] = [item["conditional_probability"]]
    return strategy_params


def _safe_mi_strategy_indices(ir: dict[str, Any], coarse: dict[str, Any]) -> set[int]:
    """Return coarse strategy indexes whose exact MI computation is bounded."""
    graph_items = (
        len(ir.get("knowledges", [])) + len(ir.get("strategies", [])) + len(ir.get("operators", []))
    )
    if graph_items > _MAX_MI_GRAPH_ITEMS:
        return set()
    return {
        i
        for i, strategy in enumerate(coarse.get("strategies", []))
        if len(strategy.get("premises", [])) <= _MAX_MI_PREMISES
    }


def _coarse_mi_map(
    *,
    ir: dict[str, Any],
    coarse: dict[str, Any],
    node_priors: dict[str, float],
    param_data: dict[str, Any] | None,
) -> dict[int, float]:
    """Best-effort MI map for bounded-size coarse strategies."""
    indices = _safe_mi_strategy_indices(ir, coarse)
    if not indices:
        return {}
    try:
        from gaia.engine.ir.coarsen import compute_coarse_cpts, mutual_information

        cpts = compute_coarse_cpts(
            ir,
            coarse,
            node_priors=node_priors,
            strategy_params=_strategy_params_from_param_data(param_data),
            strategy_indices=indices,
        )
        return {
            i: mutual_information(
                cpt,
                [node_priors.get(p, 0.5) for p in coarse["strategies"][i]["premises"]],
            )
            for i, cpt in cpts.items()
            if len(cpt) >= 2
        }
    except Exception:
        return {}


def _write_narrative_outline(
    *,
    ir: dict[str, Any],
    output_dir: Path,
    beliefs_data: dict[str, Any] | None,
    param_data: dict[str, Any] | None,
    exported: set[str],
) -> None:
    """Best-effort narrative outline generation for GitHub output."""
    try:
        from gaia.engine.ir.coarsen import coarsen_ir
        from gaia.engine.ir.linearize import linearize_narrative, render_narrative_outline

        coarse_for_outline = coarsen_ir(ir, exported)
        node_priors = _default_outline_priors(ir, param_data)
        beliefs = (
            {x["knowledge_id"]: x["belief"] for x in beliefs_data.get("beliefs", [])}
            if beliefs_data
            else {}
        )
        sections = linearize_narrative(
            coarse_for_outline,
            beliefs=beliefs,
            priors=node_priors,
            mi_per_strategy=_coarse_mi_map(
                ir=ir,
                coarse=coarse_for_outline,
                node_priors=node_priors,
                param_data=param_data,
            ),
        )
        (output_dir / "narrative-outline.md").write_text(
            render_narrative_outline(sections), encoding="utf-8"
        )
    except Exception:
        pass


def generate_github_output(
    ir: dict[str, Any],
    pkg_path: Path,
    *,
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
    pkg_metadata: dict[str, Any] | None = None,
) -> Path:
    """Generate the full ``.github-output/`` tree and return its path.

    Steps:
    0. Reset the output directory
    1. Create directory structure
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
    docs_dir = output_dir / "docs"
    data_dir = docs_dir / "public" / "data"
    assets_dir = docs_dir / "public" / "assets"
    sections_dir = data_dir / "sections"

    if output_dir.exists():
        shutil.rmtree(output_dir)

    for d in (wiki_dir, data_dir, assets_dir, sections_dir):
        d.mkdir(parents=True, exist_ok=True)

    # ── 1. Wiki pages + section content ──
    wiki_page_names = _write_wiki_pages_and_sections(
        ir=ir,
        wiki_dir=wiki_dir,
        sections_dir=sections_dir,
        beliefs_data=beliefs_data,
        param_data=param_data,
    )

    # ── 2. graph.json ──
    write_graph_json(
        data_dir / "graph.json",
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported,
    )

    # ── 3. beliefs.json (if available) ──
    if beliefs_data is not None:
        with (data_dir / "beliefs.json").open("w", encoding="utf-8") as f:
            json.dump(beliefs_data, f, indent=2, ensure_ascii=False)

    # ── 4. meta.json ──
    _write_meta_json(data_dir, ir, metadata)

    # ── 5. Copy artifacts to assets (recursive) ──
    asset_names = _copy_artifacts(pkg_path / "artifacts", assets_dir)

    # ── 7. manifest.json ──
    manifest_json = generate_manifest(
        ir,
        exported,
        wiki_page_names,
        assets=asset_names,
    )
    (output_dir / "manifest.json").write_text(manifest_json, encoding="utf-8")

    # ── 8. Narrative outline (for agent consumption) ──
    _write_narrative_outline(
        ir=ir,
        output_dir=output_dir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported=exported,
    )

    # ── 9. README.md skeleton ──
    readme = _generate_readme_skeleton(
        ir,
        beliefs_data=beliefs_data,
        param_data=param_data,
        exported_ids=exported,
        pkg_metadata=metadata,
    )
    (output_dir / "README.md").write_text(readme, encoding="utf-8")

    return output_dir


def _render_coarse_mermaid(
    ir: dict[str, Any],
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    param_data: dict[str, Any] | None = None,
) -> tuple[str, float]:
    """Render a coarse-grained Mermaid graph: leaf premises → exported conclusions."""
    coarse = coarsen_ir(ir, exported_ids)
    kid_to_k = {k["id"]: k for k in coarse["knowledges"]}

    lines = [
        "```mermaid",
        "---",
        "config:",
        "  flowchart:",
        "    rankSpacing: 80",
        "    nodeSpacing: 30",
        "---",
        "graph TB",
    ]

    for k in coarse["knowledges"]:
        kid = k["id"]
        label = k.get("title") or k.get("label", "?")
        safe = k.get("label", "x").replace("-", "_")
        b = beliefs.get(kid)
        p = priors.get(kid)
        is_exp = kid in exported_ids

        prior_val = p if p is not None else 0.5
        prior_str = format_belief(prior_val)
        if is_exp:
            ann = f"{prior_str} → {format_belief(b)}" if b is not None else ""
            display = f"★ {label}\\n({ann})" if ann else f"★ {label}"
            css = ":::exported"
        else:
            ann = f"{prior_str} → {format_belief(b)}" if b is not None else prior_str
            display = f"{label}\\n({ann})"
            css = ":::premise"

        display = display.replace('"', "#quot;").replace("*", "#ast;")
        lines.append(f'    {safe}["{display}"]{css}')

    strategy_lines, total_mi = _coarse_strategy_lines(
        ir=ir,
        coarse=coarse,
        kid_to_k=kid_to_k,
        beliefs=beliefs,
        priors=priors,
        param_data=param_data,
    )
    lines.extend(strategy_lines)
    lines.extend(_coarse_operator_lines(coarse, kid_to_k))

    lines.append("")
    lines.append("    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333")
    lines.append("    classDef exported fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#333")
    lines.append("    classDef weak fill:#fff9c4,stroke:#f9a825,stroke-dasharray: 5 5,color:#333")
    lines.append("    classDef contra fill:#ffebee,stroke:#c62828,color:#333")
    lines.append("```")
    return "\n".join(lines), total_mi


def _coarse_strategy_lines(
    *,
    ir: dict[str, Any],
    coarse: dict[str, Any],
    kid_to_k: dict[str, dict[str, Any]],
    beliefs: dict[str, float],
    priors: dict[str, float],
    param_data: dict[str, Any] | None,
) -> tuple[list[str], float]:
    """Render strategy intermediate nodes and return accumulated MI."""
    deterministic = {
        "deduction",
        "reductio",
        "elimination",
        "mathematical_induction",
        "case_analysis",
    }
    node_priors = _default_outline_priors(ir, param_data)
    node_priors.update(priors)
    mi_map = (
        _coarse_mi_map(ir=ir, coarse=coarse, node_priors=node_priors, param_data=param_data)
        if beliefs
        else {}
    )
    total_mi = 0.0
    lines: list[str] = []
    for i, s in enumerate(coarse["strategies"]):
        stype = s.get("type", "infer")
        mi = mi_map.get(i)
        ann = stype
        if mi is not None:
            total_mi += mi
            ann = f"{stype}\\n{mi:.2f} bits"
        css = "" if stype in deterministic else ":::weak"
        sid = f"strat_{i}"
        lines.append(f'    {sid}(["{ann}"]){css}')
        for p in s["premises"]:
            lines.append(f"    {kid_to_k.get(p, {}).get('label', '?').replace('-', '_')} --> {sid}")
        conc = kid_to_k.get(s["conclusion"], {}).get("label", "?").replace("-", "_")
        lines.append(f"    {sid} --> {conc}")
    return lines, total_mi


def _coarse_operator_lines(
    coarse: dict[str, Any],
    kid_to_k: dict[str, dict[str, Any]],
) -> list[str]:
    """Render coarse operator nodes and edges."""
    op_symbols = {
        "contradiction": "\u2297",
        "equivalence": "\u2261",
        "complement": "\u2295",
        "negation": "\u00ac",
        "disjunction": "\u2228",
        "conjunction": "\u2227",
        "implication": "\u2192",
    }
    undirected = {"equivalence", "contradiction", "complement", "implication"}
    lines: list[str] = []
    for i, o in enumerate(coarse.get("operators", [])):
        otype = o.get("operator", "")
        oid = f"oper_{i}"
        css = ":::contra" if otype == "contradiction" else ""
        lines.append(f'    {oid}{{{{"{op_symbols.get(otype, otype)}"}}}}{css}')
        edge = " --- " if otype in undirected else " --> "
        for v in o.get("variables", []):
            label = kid_to_k.get(v, {}).get("label", "?").replace("-", "_")
            lines.append(f"    {label}{edge}{oid}")
        conc = o.get("conclusion")
        if conc:
            label = kid_to_k.get(conc, {}).get("label", "?").replace("-", "_")
            lines.append(f"    {oid}{edge}{label}")
    return lines


def _generate_readme_skeleton(
    ir: dict[str, Any],
    *,
    beliefs_data: dict[str, Any] | None = None,
    param_data: dict[str, Any] | None = None,
    exported_ids: set[str] | None = None,
    pkg_metadata: dict[str, Any] | None = None,
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
        mermaid, total_mi = _render_coarse_mermaid(
            ir,
            beliefs,
            priors,
            exported,
            param_data=param_data,
        )
        if total_mi > 0:
            lines.append("> [!TIP]")
            lines.append(f"> **Reasoning graph information gain: `{total_mi:.1f} bits`**")
            lines.append(">")
            lines.append(
                "> Total mutual information between leaf premises and "
                "exported conclusions — measures how much the reasoning "
                "structure reduces uncertainty about the results."
            )
            lines.append("")
        lines.append(mermaid)
        lines.append("")

    # Exported conclusions table
    knowledge_by_id = {k["id"]: k for k in ir.get("knowledges", [])}
    exported_nodes = [knowledge_by_id[eid] for eid in sorted(exported) if eid in knowledge_by_id]
    if exported_nodes:
        lines.append("## Conclusions")
        lines.append("")
        lines.append("| Label | Content | Prior | Belief |")
        lines.append("|-------|---------|-------|--------|")
        for k in exported_nodes:
            label = k.get("label", "")
            content = k.get("content", "")
            if len(content) > 80:
                content = content[:77] + "..."
            kid = k["id"]
            prior = format_belief(priors.get(kid, 0.5))
            belief = format_belief(beliefs[kid]) if kid in beliefs else "\u2014"
            lines.append(f"| {label} | {content} | {prior} | {belief} |")
        lines.append("")

    # Placeholder markers
    lines.append("<!-- content:start -->")
    lines.append("<!-- content:end -->")
    lines.append("")

    return "\n".join(lines)
