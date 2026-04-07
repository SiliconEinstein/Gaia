"""Orchestrate GitHub output generation for a compiled Gaia package.

Combines wiki pages, graph.json, manifest.json, assets, section placeholders,
a React SPA template, and a README skeleton into a single ``.github-output/`` directory.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from gaia.cli.commands._graph_json import generate_graph_json
from gaia.cli.commands._manifest import generate_manifest
from gaia.ir.coarsen import coarsen_ir
from gaia.cli.commands._wiki import generate_all_wiki


def _copy_react_template(docs_dir: Path) -> None:
    """Copy the React SPA template from ``gaia.cli.templates.pages`` to *docs_dir*.

    The template provides the scaffold (``package.json``, ``src/``, ``index.html``,
    etc.) on top of which data files (``public/data/``, ``public/assets/``) are
    overlaid by the caller.

    ``node_modules``, ``dist``, ``package-lock.json``, and Python bytecode are
    excluded from the copy so the output stays lightweight and reproducible.
    """
    import gaia.cli.templates.pages as pages_pkg

    template_path = Path(pages_pkg.__file__).parent

    if docs_dir.exists():
        shutil.rmtree(docs_dir)

    shutil.copytree(
        template_path,
        docs_dir,
        ignore=shutil.ignore_patterns(
            "node_modules", "dist", "package-lock.json", "__pycache__", "*.pyc"
        ),
    )


def _write_meta_json(
    data_dir: Path,
    ir: dict,
    pkg_metadata: dict,
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
    0. Copy React SPA template to ``docs/``
    1. Create remaining directory structure
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
    docs_dir = output_dir / "docs"
    wiki_dir = output_dir / "wiki"
    data_dir = docs_dir / "public" / "data"
    assets_dir = docs_dir / "public" / "assets"
    sections_dir = data_dir / "sections"

    # ── 0. Copy React template (provides package.json, src/, index.html, …) ──
    _copy_react_template(docs_dir)

    # Create remaining directory structure (template may already provide some)
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
    _write_meta_json(data_dir, ir, metadata)

    # ── 5. Copy artifacts to assets (recursive) ──
    artifacts_dir = pkg_path / "artifacts"
    asset_names: list[str] = []
    if artifacts_dir.is_dir():
        for item in sorted(artifacts_dir.rglob("*")):
            if item.is_file():
                rel = item.relative_to(artifacts_dir)
                dest = assets_dir / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, dest)
                asset_names.append(str(rel))

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

    # ── 8. Narrative outline (for agent consumption) ──
    # Split into two phases: outline (always fast) and MI (may be slow)
    try:
        from gaia.ir.linearize import linearize_narrative, render_narrative_outline

        coarse_for_outline = coarsen_ir(ir, exported)
        node_priors = {kid: 0.5 for k in ir["knowledges"] for kid in [k["id"]]}
        if param_data:
            for p in param_data.get("priors", []):
                node_priors[p["knowledge_id"]] = p["value"]

        # Phase 1: compute MI for small strategies (fast)
        mi_map: dict[int, float] = {}
        try:
            from gaia.ir.coarsen import compute_coarse_cpts, mutual_information

            sp: dict[str, list[float]] = {}
            if param_data:
                for s in param_data.get("strategy_params", []):
                    sid = s.get("strategy_id", "")
                    if s.get("conditional_probabilities"):
                        sp[sid] = s["conditional_probabilities"]
                    elif s.get("conditional_probability") is not None:
                        sp[sid] = [s["conditional_probability"]]
            cpts = compute_coarse_cpts(
                ir,
                coarse_for_outline,
                node_priors=node_priors,
                strategy_params=sp,
            )
            for i in cpts:
                pp = [
                    node_priors.get(p, 0.5) for p in coarse_for_outline["strategies"][i]["premises"]
                ]
                mi_map[i] = mutual_information(cpts[i], pp)
        except Exception:
            pass  # MI computation failed — outline still works without it

        # Phase 2: generate outline (always works, with or without MI)
        b = (
            {x["knowledge_id"]: x["belief"] for x in beliefs_data.get("beliefs", [])}
            if beliefs_data
            else {}
        )
        sections = linearize_narrative(
            coarse_for_outline, beliefs=b, priors=node_priors, mi_per_strategy=mi_map
        )
        outline = render_narrative_outline(sections)
        (output_dir / "narrative-outline.md").write_text(outline, encoding="utf-8")
    except Exception:
        pass  # Outline generation failed entirely

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
    ir: dict,
    beliefs: dict[str, float],
    priors: dict[str, float],
    exported_ids: set[str],
    param_data: dict | None = None,
) -> str:
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
        if is_exp:
            ann = f"{prior_val:.2f} → {b:.2f}" if b is not None else ""
            display = f"★ {label}\\n({ann})" if ann else f"★ {label}"
            css = ":::exported"
        else:
            ann = f"{prior_val:.2f} → {b:.2f}" if b is not None else f"{prior_val:.2f}"
            display = f"{label}\\n({ann})"
            css = ":::premise"

        display = display.replace('"', "#quot;").replace("*", "#ast;")
        lines.append(f'    {safe}["{display}"]{css}')

    # Strategy intermediate nodes (stadium shape) with CPT annotation
    _DETERMINISTIC = {
        "deduction",
        "reductio",
        "elimination",
        "mathematical_induction",
        "case_analysis",
    }

    # Compute coarse CPTs + mutual information if beliefs are available
    coarse_cpts: dict[int, list[float]] = {}
    if beliefs:
        try:
            from gaia.ir.coarsen import compute_coarse_cpts

            node_priors_for_cpt = {kid: priors.get(kid, 0.5) for kid in beliefs}
            strat_params: dict[str, list[float]] = {}
            if param_data:
                for sp in param_data.get("strategy_params", []):
                    sid = sp.get("strategy_id", "")
                    if sp.get("conditional_probabilities"):
                        strat_params[sid] = sp["conditional_probabilities"]
                    elif sp.get("conditional_probability") is not None:
                        strat_params[sid] = [sp["conditional_probability"]]
            coarse_cpts = compute_coarse_cpts(
                ir,
                coarse,
                node_priors=node_priors_for_cpt,
                strategy_params=strat_params,
            )
        except Exception:
            pass

    total_mi = 0.0
    for i, s in enumerate(coarse["strategies"]):
        stype = s.get("type", "infer")
        sid = f"strat_{i}"
        conc = kid_to_k.get(s["conclusion"], {}).get("label", "?").replace("-", "_")
        css = "" if stype in _DETERMINISTIC else ":::weak"

        # Mutual information annotation
        cpt = coarse_cpts.get(i)
        if cpt and len(cpt) >= 2:
            from gaia.ir.coarsen import mutual_information

            premise_priors_list = [priors.get(p, 0.5) for p in s["premises"]]
            mi = mutual_information(cpt, premise_priors_list)
            total_mi += mi
            ann = f"{stype}\\n{mi:.2f} bits"
        else:
            ann = stype

        lines.append(f'    {sid}(["{ann}"]){css}')
        for p in s["premises"]:
            prem = kid_to_k.get(p, {}).get("label", "?").replace("-", "_")
            lines.append(f"    {prem} --> {sid}")
        lines.append(f"    {sid} --> {conc}")

    # Operator nodes (hexagon shape)
    _OP_SYMBOLS = {
        "contradiction": "\u2297",
        "equivalence": "\u2261",
        "complement": "\u2295",
        "disjunction": "\u2228",
    }
    _UNDIRECTED = {"equivalence", "contradiction", "complement"}
    for i, o in enumerate(coarse.get("operators", [])):
        otype = o.get("operator", "")
        symbol = _OP_SYMBOLS.get(otype, otype)
        oid = f"oper_{i}"
        css = ":::contra" if otype == "contradiction" else ""
        lines.append(f'    {oid}{{{{"{symbol}"}}}}{css}')
        edge = " --- " if otype in _UNDIRECTED else " --> "
        for v in o.get("variables", []):
            v_label = kid_to_k.get(v, {}).get("label", "?").replace("-", "_")
            lines.append(f"    {v_label}{edge}{oid}")
        conc = o.get("conclusion")
        if conc:
            c_label = kid_to_k.get(conc, {}).get("label", "?").replace("-", "_")
            lines.append(f"    {oid}{edge}{c_label}")

    lines.append("")
    lines.append("    classDef premise fill:#ddeeff,stroke:#4488bb,color:#333")
    lines.append("    classDef exported fill:#d4edda,stroke:#28a745,stroke-width:2px,color:#333")
    lines.append("    classDef weak fill:#fff9c4,stroke:#f9a825,stroke-dasharray: 5 5,color:#333")
    lines.append("    classDef contra fill:#ffebee,stroke:#c62828,color:#333")
    lines.append("```")
    return "\n".join(lines), total_mi


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
            prior = f"{priors.get(kid, 0.5):.2f}"
            belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "\u2014"
            lines.append(f"| {label} | {content} | {prior} | {belief} |")
        lines.append("")

    # Placeholder markers
    lines.append("<!-- content:start -->")
    lines.append("<!-- content:end -->")
    lines.append("")

    return "\n".join(lines)
