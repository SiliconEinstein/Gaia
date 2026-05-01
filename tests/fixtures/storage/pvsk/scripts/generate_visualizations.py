"""Generate visualizations for PVSK knowledge graph BP time series results."""

from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Setup paths
# ---------------------------------------------------------------------------

BASE = Path(__file__).parent.parent
RESULTS_DIR = BASE / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

TIMESERIES_PATH = RESULTS_DIR / "belief_timeseries.json"
with open(TIMESERIES_PATH) as f:
    TIMESERIES = json.load(f)

TIME_POINTS = ["T1_2013", "T2_2017", "T3_2022", "T4_2026"]
YEARS = [2013, 2017, 2022, 2026]

META_LABELS = {
    "pvsk:pvsk_meta::p_viability": "Viability",
    "pvsk:pvsk_meta::p_efficiency": "Efficiency",
    "pvsk:pvsk_meta::p_improvement": "Improvement",
    "pvsk:pvsk_meta::p_stability": "Stability",
    "pvsk:pvsk_meta::p_industrialization": "Industrialization",
}

META_LABELS_CN = {
    "pvsk:pvsk_meta::p_viability": "Viability (能不能做出来)",
    "pvsk:pvsk_meta::p_efficiency": "Efficiency (能不能高效率)",
    "pvsk:pvsk_meta::p_improvement": "Improvement (能不能持续改进)",
    "pvsk:pvsk_meta::p_stability": "Stability (能不能稳定)",
    "pvsk:pvsk_meta::p_industrialization": "Industrialization (能不能产业化)",
}

META_COLORS = {
    "pvsk:pvsk_meta::p_viability": "#2196F3",
    "pvsk:pvsk_meta::p_efficiency": "#4CAF50",
    "pvsk:pvsk_meta::p_improvement": "#FF9800",
    "pvsk:pvsk_meta::p_stability": "#9C27B0",
    "pvsk:pvsk_meta::p_industrialization": "#F44336",
}

# ---------------------------------------------------------------------------
# 1. Meta proposition time series chart
# ---------------------------------------------------------------------------


def generate_meta_timeseries_chart() -> str:
    """Generate matplotlib line chart for meta proposition beliefs over time."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(12, 7))

    for meta_id, label in META_LABELS.items():
        beliefs = [TIMESERIES[tp]["meta_beliefs"][meta_id] for tp in TIME_POINTS]
        ax.plot(YEARS, beliefs, marker="o", linewidth=2.5, markersize=8,
                label=label, color=META_COLORS[meta_id])
        for x, y in zip(YEARS, beliefs):
            ax.annotate(f"{y:.3f}", (x, y), textcoords="offset points",
                        xytext=(0, 10), ha="center", fontsize=8)

    ax.set_xlabel("Year", fontsize=12)
    ax.set_ylabel("Posterior Belief", fontsize=12)
    ax.set_title("PVSK Meta Proposition Belief Evolution (2013-2026)", fontsize=14, fontweight="bold")
    ax.set_ylim(0.0, 1.05)
    ax.set_xticks(YEARS)
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=10)

    # Add annotations for time point descriptions
    tp_descriptions = {
        2013: "5 papers\n(2009-2013)",
        2017: "9 papers\n(+2014-2017)",
        2022: "14 papers\n(+2020-2022)",
        2026: "22 papers\n(+2023-2025)",
    }
    for year in YEARS:
        ax.annotate(tp_descriptions[year], (year, 0.02), ha="center", fontsize=8,
                    color="gray", style="italic")

    plt.tight_layout()
    out_path = RESULTS_DIR / "meta_timeseries.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# 2. Knowledge accumulation chart
# ---------------------------------------------------------------------------


def generate_knowledge_accumulation_chart() -> str:
    """Generate bar chart showing knowledge graph growth over time."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    n_packages = [TIMESERIES[tp]["n_packages"] for tp in TIME_POINTS]
    n_variables = [TIMESERIES[tp]["n_variables"] for tp in TIME_POINTS]
    n_factors = [TIMESERIES[tp]["n_factors"] for tp in TIME_POINTS]

    fig, ax1 = plt.subplots(figsize=(10, 6))

    x = np.arange(len(YEARS))
    width = 0.25

    bars1 = ax1.bar(x - width, n_variables, width, label="Variables (nodes)", color="#2196F3", alpha=0.8)
    bars2 = ax1.bar(x, n_factors, width, label="Factors (edges)", color="#4CAF50", alpha=0.8)
    ax1.set_ylabel("Graph Size (nodes / factors)", fontsize=12)
    ax1.set_xticks(x)
    ax1.set_xticklabels([str(y) for y in YEARS])

    ax2 = ax1.twinx()
    line = ax2.plot(x, n_packages, color="#F44336", marker="D", linewidth=2.5,
                    markersize=8, label="Packages (papers)")
    ax2.set_ylabel("Number of Packages", fontsize=12, color="#F44336")
    ax2.tick_params(axis="y", labelcolor="#F44336")

    # Add value labels on bars
    for bar in bars1:
        height = bar.get_height()
        ax1.annotate(f"{int(height)}", xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)
    for bar in bars2:
        height = bar.get_height()
        ax1.annotate(f"{int(height)}", xy=(bar.get_x() + bar.get_width() / 2, height),
                     xytext=(0, 3), textcoords="offset points", ha="center", fontsize=8)

    ax1.set_xlabel("Year", fontsize=12)
    ax1.set_title("Knowledge Graph Growth Over Time", fontsize=14, fontweight="bold")

    # Combined legend
    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, loc="upper left")

    ax1.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    out_path = RESULTS_DIR / "knowledge_growth.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# 3. Top claims belief change chart
# ---------------------------------------------------------------------------


def generate_top_claims_chart() -> str:
    """Generate horizontal bar chart of claims with largest belief increase."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Compute belief changes from T1 to T4 for non-meta, non-helper claims
    t1_beliefs = TIMESERIES["T1_2013"]["all_beliefs"]
    t4_beliefs = TIMESERIES["T4_2026"]["all_beliefs"]

    changes = []
    for kid, t4_belief in t4_beliefs.items():
        if "pvsk_meta::" in kid:
            continue
        if kid.startswith("_") or "__conjunction" in kid or "_anon_" in kid:
            continue
        t1_belief = t1_beliefs.get(kid, 0.5)
        change = t4_belief - t1_belief
        label = kid.split("::")[-1]
        pkg = kid.split("::")[0].replace("pvsk:", "")
        changes.append((change, t4_belief, t1_belief, label, pkg))

    changes.sort(reverse=True)
    top_positive = changes[:15]
    top_negative = changes[-10:]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(16, 8))

    # Top positive changes
    labels_pos = [f"{c[3]}\n({c[4]})" for c in top_positive]
    vals_pos = [c[0] for c in top_positive]
    colors_pos = ["#4CAF50" if v > 0 else "#F44336" for v in vals_pos]
    ax1.barh(range(len(vals_pos)), vals_pos, color=colors_pos, alpha=0.8)
    ax1.set_yticks(range(len(vals_pos)))
    ax1.set_yticklabels(labels_pos, fontsize=8)
    ax1.invert_yaxis()
    ax1.set_xlabel("Belief Change (T4 - T1)", fontsize=11)
    ax1.set_title("Top 15 Claims: Largest Belief Increase", fontsize=12, fontweight="bold")
    ax1.grid(True, alpha=0.3, axis="x")

    # Top negative changes
    labels_neg = [f"{c[3]}\n({c[4]})" for c in top_negative]
    vals_neg = [c[0] for c in top_negative]
    colors_neg = ["#F44336" if v < 0 else "#4CAF50" for v in vals_neg]
    ax2.barh(range(len(vals_neg)), vals_neg, color=colors_neg, alpha=0.8)
    ax2.set_yticks(range(len(vals_neg)))
    ax2.set_yticklabels(labels_neg, fontsize=8)
    ax2.invert_yaxis()
    ax2.set_xlabel("Belief Change (T4 - T1)", fontsize=11)
    ax2.set_title("Top 10 Claims: Largest Belief Decrease", fontsize=12, fontweight="bold")
    ax2.grid(True, alpha=0.3, axis="x")

    plt.tight_layout()
    out_path = RESULTS_DIR / "top_claims_change.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# 4. Network graph visualization (using one representative IR)
# ---------------------------------------------------------------------------


def generate_network_graph() -> str:
    """Generate networkx graph showing meta propositions and their supporters."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    # Build graph from T4 beliefs - connect meta propositions to papers that support them
    G = nx.DiGraph()

    # Add meta nodes
    for meta_id, label in META_LABELS.items():
        belief = TIMESERIES["T4_2026"]["meta_beliefs"][meta_id]
        G.add_node(meta_id, label=label.split(" (")[0], belief=belief, node_type="meta")

    # Find which papers contribute to each meta proposition
    # Strategy: look at claims in each paper that have high belief and are connected to meta
    t4_beliefs = TIMESERIES["T4_2026"]["all_beliefs"]

    # Group claims by package
    pkg_claims: dict[str, list[tuple[str, float]]] = defaultdict(list)
    for kid, belief in t4_beliefs.items():
        if "pvsk_meta::" in kid:
            continue
        if kid.startswith("_") or "__conjunction" in kid or "_anon_" in kid:
            continue
        parts = kid.split("::")
        if len(parts) >= 2:
            pkg = parts[0].replace("pvsk:", "")
            label = parts[-1]
            pkg_claims[pkg].append((label, belief))

    # Add top claims per package as nodes, connect to meta based on naming heuristics
    meta_keywords = {
        "pvsk:pvsk_meta::p_viability": ["viability", "sensitize", "photovoltaic", "absorber"],
        "pvsk:pvsk_meta::p_efficiency": ["efficiency", "pce", "efficient", "output"],
        "pvsk:pvsk_meta::p_improvement": ["improvement", "improve", "enhance", "engineering"],
        "pvsk:pvsk_meta::p_stability": ["stability", "stable", "durability", "degradation"],
        "pvsk:pvsk_meta::p_industrialization": ["industrial", "module", "scalable", "manufactur"],
    }

    added_pkgs = set()
    for pkg, claims in pkg_claims.items():
        claims.sort(key=lambda x: x[1], reverse=True)
        top_claim = claims[0] if claims else ("", 0)
        if top_claim[1] < 0.7:
            continue

        pkg_node = f"pkg_{pkg}"
        year = pkg.replace("pvsk_", "").replace("pvsk-", "")
        # Extract year from package name like pvsk_kojima2009 -> 2009
        yr = "".join(filter(str.isdigit, pkg))
        if not yr:
            yr = "20??"

        if pkg_node not in added_pkgs:
            G.add_node(pkg_node, label=f"{pkg}\n({yr})", belief=top_claim[1],
                       node_type="paper")
            added_pkgs.add(pkg_node)

        # Connect to meta propositions based on claim keywords
        for meta_id, keywords in meta_keywords.items():
            for claim_label, claim_belief in claims[:5]:
                if any(kw in claim_label.lower() for kw in keywords):
                    if not G.has_edge(pkg_node, meta_id):
                        G.add_edge(pkg_node, meta_id, weight=claim_belief)
                    break

    # Also connect based on explicit support in IR if available
    # For now, use the heuristic above

    fig, ax = plt.subplots(figsize=(18, 14))

    # Layout
    pos = nx.spring_layout(G, k=2, iterations=50, seed=42)

    # Draw nodes by type
    meta_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "meta"]
    paper_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "paper"]

    nx.draw_networkx_nodes(G, pos, nodelist=meta_nodes, node_color="#FF9800",
                           node_size=3000, alpha=0.9, ax=ax)
    nx.draw_networkx_nodes(G, pos, nodelist=paper_nodes, node_color="#2196F3",
                           node_size=1200, alpha=0.7, ax=ax)

    # Draw edges
    nx.draw_networkx_edges(G, pos, alpha=0.3, arrows=True,
                           arrowsize=15, width=1.5, ax=ax,
                           connectionstyle="arc3,rad=0.1")

    # Labels
    meta_labels = {n: G.nodes[n]["label"] for n in meta_nodes}
    paper_labels = {n: G.nodes[n]["label"] for n in paper_nodes}
    nx.draw_networkx_labels(G, pos, meta_labels, font_size=10, font_weight="bold", ax=ax)
    nx.draw_networkx_labels(G, pos, paper_labels, font_size=7, ax=ax)

    ax.set_title("PVSK Knowledge Graph: Papers → Meta Propositions\n(T4 2026)",
                 fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    out_path = RESULTS_DIR / "network_graph.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# 4b. Improved network graph using actual IR strategy data
# ---------------------------------------------------------------------------


def generate_network_graph_from_ir() -> str:
    """Generate networkx graph using actual IR strategy data for meta connections."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import networkx as nx

    G = nx.DiGraph()

    # Add meta nodes
    for meta_id, label in META_LABELS.items():
        belief = TIMESERIES["T4_2026"]["meta_beliefs"][meta_id]
        G.add_node(meta_id, label=label, belief=belief, node_type="meta")

    # Read IR files from all packages
    ir_files = sorted(BASE.glob("pvsk-*/.gaia/ir.json"))
    t4_beliefs = TIMESERIES["T4_2026"]["all_beliefs"]

    meta_ids = set(META_LABELS.keys())

    for ir_path in ir_files:
        with open(ir_path) as f:
            ir = json.load(f)

        pkg_name = ir.get("package_name", "unknown")
        yr = "".join(filter(str.isdigit, pkg_name))
        if not yr:
            yr = "20??"

        # Find strategies that conclude to a meta proposition
        pkg_node = f"pkg_{pkg_name}"
        has_meta_support = False

        for s in ir.get("strategies", []):
            conc = s.get("conclusion", "")
            if conc in meta_ids:
                has_meta_support = True
                # Add package node if not exists
                if pkg_node not in G:
                    G.add_node(pkg_node, label=f"{pkg_name}\n({yr})",
                               node_type="paper", year=int(yr) if yr.isdigit() else 0)
                # Edge from package to meta
                premises = s.get("premises", [])
                reason = s.get("reason", "")
                G.add_edge(pkg_node, conc, weight=len(premises), reason=reason)

        # Also add edges for claims that are premises to meta-supporting strategies
        # Find claims in this package that support meta propositions
        for k in ir.get("knowledges", []):
            kid = k.get("id", "")
            label = k.get("label", "")
            if kid in meta_ids:
                continue
            if label.startswith("_") or "__conjunction" in label or "_anon_" in label:
                continue
            # Check if this claim is a premise for a meta-supporting strategy
            for s in ir.get("strategies", []):
                conc = s.get("conclusion", "")
                if conc in meta_ids and kid in s.get("premises", []):
                    claim_node = f"claim_{kid}"
                    if claim_node not in G:
                        belief = t4_beliefs.get(kid, 0.5)
                        G.add_node(claim_node, label=label, belief=belief,
                                  node_type="claim", pkg=pkg_name)
                    if pkg_node not in G:
                        G.add_node(pkg_node, label=f"{pkg_name}\n({yr})",
                                  node_type="paper", year=int(yr) if yr.isdigit() else 0)
                    G.add_edge(pkg_node, claim_node, weight=1)
                    G.add_edge(claim_node, conc, weight=1)

    if len(G.nodes) <= 5:
        # Fallback to heuristic graph if no IR connections found
        return generate_network_graph()

    fig, ax = plt.subplots(figsize=(20, 16))

    # Layout using Kamada-Kawai for better structure, or spring
    try:
        pos = nx.kamada_kawai_layout(G)
    except Exception:
        pos = nx.spring_layout(G, k=1.5, iterations=100, seed=42)

    meta_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "meta"]
    paper_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "paper"]
    claim_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type") == "claim"]

    # Draw edges with different alpha
    nx.draw_networkx_edges(G, pos, alpha=0.25, arrows=True,
                           arrowsize=12, width=1.0, ax=ax,
                           connectionstyle="arc3,rad=0.05")

    # Draw nodes
    nx.draw_networkx_nodes(G, pos, nodelist=meta_nodes, node_color="#FF9800",
                           node_size=4000, alpha=0.95, ax=ax, edgecolors="#E65100", linewidths=2)
    nx.draw_networkx_nodes(G, pos, nodelist=paper_nodes, node_color="#2196F3",
                           node_size=1500, alpha=0.8, ax=ax, edgecolors="#1565C0", linewidths=1.5)
    nx.draw_networkx_nodes(G, pos, nodelist=claim_nodes, node_color="#4CAF50",
                           node_size=600, alpha=0.6, ax=ax)

    # Labels
    meta_labels = {n: f"{G.nodes[n]['label']}\n({G.nodes[n]['belief']:.3f})" for n in meta_nodes}
    paper_labels = {n: G.nodes[n]["label"] for n in paper_nodes}
    claim_labels = {n: G.nodes[n]["label"] for n in claim_nodes}

    nx.draw_networkx_labels(G, pos, meta_labels, font_size=11, font_weight="bold", ax=ax)
    nx.draw_networkx_labels(G, pos, paper_labels, font_size=8, ax=ax)
    if len(claim_nodes) <= 30:
        nx.draw_networkx_labels(G, pos, claim_labels, font_size=6, ax=ax, font_color="#2E7D32")

    ax.set_title("PVSK Knowledge Graph: Papers & Claims → Meta Propositions\n(T4 2026, from IR)",
                 fontsize=14, fontweight="bold")
    ax.axis("off")

    plt.tight_layout()
    out_path = RESULTS_DIR / "network_graph_ir.png"
    fig.savefig(out_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return str(out_path)


# ---------------------------------------------------------------------------
# 5. Generate Mermaid diagram for meta propositions
# ---------------------------------------------------------------------------


def generate_meta_mermaid() -> str:
    """Generate a Mermaid diagram showing meta propositions and their relationships."""
    lines = ["```mermaid", "graph TB"]

    # Meta nodes
    for meta_id, label in META_LABELS.items():
        short = meta_id.split("::")[-1]
        t4_belief = TIMESERIES["T4_2026"]["meta_beliefs"][meta_id]
        display = f"{label.split(' (')[0]}\\n({t4_belief:.3f})"
        lines.append(f'    {short}["{display}"]')

    # Add some conceptual connections between meta propositions
    lines.append("    p_viability --> p_efficiency")
    lines.append("    p_efficiency --> p_improvement")
    lines.append("    p_improvement --> p_stability")
    lines.append("    p_stability --> p_industrialization")
    lines.append("    p_viability -.-> p_industrialization")

    lines.append("")
    lines.append("    classDef meta fill:#FF9800,stroke:#E65100,color:#fff")
    lines.append("    class p_viability,p_efficiency,p_improvement,p_stability,p_industrialization meta")
    lines.append("```")

    out_path = RESULTS_DIR / "meta_mermaid.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)


# ---------------------------------------------------------------------------
# 6. Generate HTML report
# ---------------------------------------------------------------------------


def generate_html_report(image_paths: dict[str, str], mermaid_path: str,
                         cross_mermaid_path: str = "") -> str:
    """Generate an HTML report combining all visualizations."""

    # Read mermaid content
    mermaid_content = Path(mermaid_path).read_text(encoding="utf-8")
    cross_mermaid_content = ""
    if cross_mermaid_path:
        cross_mermaid_content = Path(cross_mermaid_path).read_text(encoding="utf-8")

    # Build belief tables
    table_rows = []
    for meta_id in META_LABELS_CN:
        short = meta_id.split("::")[-1]
        label = META_LABELS_CN[meta_id]
        beliefs = [TIMESERIES[tp]["meta_beliefs"][meta_id] for tp in TIME_POINTS]
        row = f"<tr><td><b>{label}</b></td>"
        for b in beliefs:
            color = f"rgb({int(255*(1-b))},{int(255*b)},100)"
            row += f'<td style="background-color:{color};color:#fff">{b:.4f}</td>'
        row += "</tr>"
        table_rows.append(row)

    # Growth table
    growth_rows = []
    for tp, year in zip(TIME_POINTS, YEARS):
        data = TIMESERIES[tp]
        growth_rows.append(
            f"<tr><td>{year}</td><td>{data['n_packages']}</td>"
            f"<td>{data['n_variables']}</td><td>{data['n_factors']}</td>"
            f"<td>{data['method']}</td><td>{data['converged']}</td></tr>"
        )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PVSK Knowledge Graph Visualization Report</title>
<style>
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
         max-width: 1200px; margin: 0 auto; padding: 20px; line-height: 1.6; }}
  h1 {{ color: #333; border-bottom: 3px solid #2196F3; padding-bottom: 10px; }}
  h2 {{ color: #444; margin-top: 40px; border-left: 4px solid #4CAF50; padding-left: 12px; }}
  table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
  th, td {{ border: 1px solid #ddd; padding: 12px; text-align: center; }}
  th {{ background-color: #f5f5f5; font-weight: 600; }}
  img {{ max-width: 100%; border: 1px solid #eee; border-radius: 4px; margin: 20px 0; }}
  .meta-table td {{ font-family: monospace; font-size: 14px; }}
  .mermaid {{ background: #fafafa; padding: 20px; border-radius: 4px; overflow-x: auto; }}
  .summary {{ background: #e3f2fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
  .summary h3 {{ margin-top: 0; color: #1565c0; }}
</style>
<script type="module">
  import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
  mermaid.initialize({{ startOnLoad: true }});
</script>
</head>
<body>
<h1>PVSK Perovskite Solar Cell Knowledge Graph Visualization</h1>
<p>Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}</p>

<div class="summary">
<h3>Summary</h3>
<p>This report visualizes the belief propagation results across 22 perovskite solar cell research papers
(2009-2025) formalized as Gaia knowledge packages. The 5 meta propositions represent core questions
about the viability of perovskite photovoltaics.</p>
<ul>
<li><b>Time points:</b> 2013, 2017, 2022, 2026 (cumulative)</li>
<li><b>Papers:</b> 22 milestone papers from Kojima 2009 to Liu 2025</li>
<li><b>Inference method:</b> Junction Tree (exact)</li>
<li><b>Meta propositions:</b> Viability, Efficiency, Improvement, Stability, Industrialization</li>
</ul>
</div>

<h2>1. Meta Proposition Belief Evolution</h2>
<p>Posterior beliefs for the 5 meta propositions across 4 time points. All propositions converge
to near-certainty (belief &gt; 0.99) by 2022.</p>
<table class="meta-table">
<tr><th>Meta Proposition</th><th>2013 (T1)</th><th>2017 (T2)</th><th>2022 (T3)</th><th>2026 (T4)</th></tr>
{''.join(table_rows)}
</table>
<img src="meta_timeseries.png" alt="Meta Proposition Time Series">

<h2>2. Knowledge Graph Growth</h2>
<p>As more papers are incorporated, the factor graph grows in complexity.</p>
<table>
<tr><th>Year</th><th>Packages</th><th>Variables</th><th>Factors</th><th>Method</th><th>Converged</th></tr>
{''.join(growth_rows)}
</table>
<img src="knowledge_growth.png" alt="Knowledge Graph Growth">

<h2>3. Claim Belief Changes (T1 → T4)</h2>
<p>Claims with the largest belief increases and decreases from the earliest to latest time point.</p>
<img src="top_claims_change.png" alt="Top Claims Change">

<h2>4. Network Graph: Papers → Meta Propositions (Heuristic)</h2>
<p>Visual representation based on keyword matching between paper claims and meta propositions.</p>
<img src="network_graph.png" alt="Network Graph">

<h2>4b. Network Graph from IR Strategy Data</h2>
<p>Visual representation using actual support/deduction strategies from compiled IR.
Orange nodes = meta propositions, blue = papers, green = key claims.</p>
<img src="network_graph_ir.png" alt="Network Graph from IR">

<h2>5. Meta Proposition Relationship Diagram (Mermaid)</h2>
<div class="mermaid">
{mermaid_content}
</div>

<h2>5b. Cross-Package Support Graph (Mermaid)</h2>
<p>Papers (blue) supporting each meta proposition (orange) via actual IR strategy data.</p>
<div class="mermaid">
{cross_mermaid_content}
</div>

<h2>6. Key Insights</h2>
<ul>
<li><b>Viability</b> started moderate (0.41 at T1), climbed to 0.63 by T2, and reached &gt;0.99 by T3 —
the field became credible through accumulating experimental evidence.</li>
<li><b>Efficiency</b> saw the steepest rise: from 0.33 (T1) to 0.85 (T2) to &gt;0.99 (T3),
driven by papers crossing 15%, 20%, and 25% PCE thresholds.</li>
<li><b>Stability</b> was initially the weakest (0.22 at T1), reflecting genuine uncertainty in 2013.
It jumped to 0.80 by T2 after Grancini 2017 demonstrated 1-year stability.</li>
<li><b>Industrialization</b> was the slowest to converge: 0.06 (T1) → 0.27 (T2) → 0.81 (T3) → 0.99 (T4),
reflecting the real-world lag between lab efficiency and module-scale manufacturing.</li>
<li>With lowered priors (meta: 0.01-0.05; strategy propagation: 60% of original),
the belief curves show a realistic S-shaped adoption trajectory.</li>
</ul>

<h2>7. Methodology</h2>
<p>Each paper was formalized as an independent Gaia knowledge package with 10-20 claims,
internal reasoning chains (support/deduction), and connections to 5 meta propositions.
Belief propagation was run using Junction Tree exact inference on cumulative factor graphs
at each time point.</p>
<p><b>Prior settings:</b> Meta proposition priors are set very low (0.01-0.05) to represent
genuine initial uncertainty. Strategy propagation strength is scaled to 60% of default,
so each supporting paper contributes moderate (not overwhelming) evidence.
Claim priors retain their original values (0.5-0.9) based on evidence strength.</p>

</body>
</html>"""

    out_path = RESULTS_DIR / "visualization_report.html"
    out_path.write_text(html, encoding="utf-8")
    return str(out_path)


# ---------------------------------------------------------------------------
# 7. Cross-package Mermaid diagram (from actual IR data)
# ---------------------------------------------------------------------------


def generate_cross_package_mermaid() -> str:
    """Generate a Mermaid diagram showing papers supporting each meta proposition."""
    lines = ["```mermaid", "graph TB"]

    t4_beliefs = TIMESERIES["T4_2026"]["all_beliefs"]
    meta_ids = set(META_LABELS.keys())

    # Collect papers that support each meta proposition
    meta_supporters: dict[str, list[tuple[str, str, float]]] = defaultdict(list)

    ir_files = sorted(BASE.glob("pvsk-*/.gaia/ir.json"))
    for ir_path in ir_files:
        with open(ir_path) as f:
            ir = json.load(f)
        pkg_name = ir.get("package_name", "unknown")
        yr = "".join(filter(str.isdigit, pkg_name))
        if not yr:
            yr = "20??"

        for s in ir.get("strategies", []):
            conc = s.get("conclusion", "")
            if conc in meta_ids:
                premises = s.get("premises", [])
                # Find the best premise belief for weight
                best_belief = 0.0
                for p in premises:
                    b = t4_beliefs.get(p, 0.5)
                    if b > best_belief:
                        best_belief = b
                meta_supporters[conc].append((pkg_name, yr, best_belief))

    # Render meta proposition nodes
    for meta_id, label in META_LABELS.items():
        short = meta_id.split("::")[-1]
        t4_belief = TIMESERIES["T4_2026"]["meta_beliefs"][meta_id]
        lines.append(f'    {short}["{label} ({t4_belief:.3f})"]')

    # Render paper nodes and edges
    _safe_cache: dict[str, str] = {}

    def _safe_id(pkg: str) -> str:
        if pkg not in _safe_cache:
            _safe_cache[pkg] = pkg.replace("-", "_").replace(".", "_")
        return _safe_cache[pkg]

    meta_short = {meta_id.split("::")[-1]: meta_id for meta_id in META_LABELS}

    for meta_id, label in META_LABELS.items():
        short = meta_id.split("::")[-1]
        supporters = meta_supporters.get(meta_id, [])
        # Sort by year for clean layout
        supporters.sort(key=lambda x: x[1])
        for pkg_name, yr, belief in supporters:
            safe = _safe_id(pkg_name)
            # Only add node definition once
            node_def = f'    {safe}["{pkg_name} ({yr})"]'
            if node_def not in lines:
                lines.append(node_def)
            lines.append(f"    {safe} --> {short}")

    lines.append("")
    lines.append("    classDef meta fill:#FF9800,stroke:#E65100,color:#fff")
    lines.append(
        "    class "
        + ",".join(m.split("::")[-1] for m in META_LABELS)
        + " meta"
    )
    lines.append("```")

    out_path = RESULTS_DIR / "cross_package_mermaid.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return str(out_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Generating PVSK knowledge graph visualizations...")
    print(f"Output directory: {RESULTS_DIR}")

    img_paths = {}

    print("1. Meta proposition time series chart...")
    img_paths["meta_timeseries"] = generate_meta_timeseries_chart()
    print(f"   -> {img_paths['meta_timeseries']}")

    print("2. Knowledge accumulation chart...")
    img_paths["knowledge_growth"] = generate_knowledge_accumulation_chart()
    print(f"   -> {img_paths['knowledge_growth']}")

    print("3. Top claims belief change chart...")
    img_paths["top_claims_change"] = generate_top_claims_chart()
    print(f"   -> {img_paths['top_claims_change']}")

    print("4. Network graph visualization (heuristic)...")
    img_paths["network_graph"] = generate_network_graph()
    print(f"   -> {img_paths['network_graph']}")

    print("4b. Network graph from IR strategies...")
    img_paths["network_graph_ir"] = generate_network_graph_from_ir()
    print(f"   -> {img_paths['network_graph_ir']}")

    print("5. Meta proposition Mermaid diagram...")
    mermaid_path = generate_meta_mermaid()
    print(f"   -> {mermaid_path}")

    print("6. Cross-package Mermaid diagram...")
    cross_mermaid = generate_cross_package_mermaid()
    print(f"   -> {cross_mermaid}")

    print("7. HTML report...")
    report_path = generate_html_report(img_paths, mermaid_path, cross_mermaid)
    print(f"   -> {report_path}")

    print("\nAll visualizations generated successfully!")
    print(f"Open {report_path} in a browser to view the full report.")


if __name__ == "__main__":
    main()
