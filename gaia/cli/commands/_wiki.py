"""Generate agent-optimized Wiki markdown pages from compiled IR."""

from __future__ import annotations


def generate_wiki_home(ir: dict, beliefs_data: dict | None = None) -> str:
    """Generate Wiki Home.md with package overview and claim index."""
    pkg = ir.get("package_name", "Package")
    lines = [f"# {pkg}", ""]

    # Module index
    modules: dict[str, list[dict]] = {}
    for k in ir["knowledges"]:
        mod = k.get("module", "Root")
        modules.setdefault(mod, []).append(k)

    lines.append("## Modules")
    lines.append("")
    for mod in modules:
        count = sum(1 for k in modules[mod] if not k.get("label", "").startswith("__"))
        page = f"Module-{mod.replace('_', '-')}"
        lines.append(f"- [{mod}]({page}) ({count} nodes)")
    lines.append("")

    # Claim index
    beliefs = {}
    if beliefs_data:
        beliefs = {b["knowledge_id"]: b["belief"] for b in beliefs_data.get("beliefs", [])}

    lines.append("## Claim Index")
    lines.append("")
    lines.append("| Label | Type | Module | Belief |")
    lines.append("|-------|------|--------|--------|")
    for k in ir["knowledges"]:
        label = k.get("label", "")
        if label.startswith("__"):
            continue
        kid = k["id"]
        ktype = k["type"]
        mod = k.get("module", "Root")
        belief = f"{beliefs[kid]:.2f}" if kid in beliefs else "\u2014"
        lines.append(f"| {label} | {ktype} | {mod} | {belief} |")

    lines.append("")
    return "\n".join(lines)
