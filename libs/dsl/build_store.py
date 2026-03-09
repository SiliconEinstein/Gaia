"""Serialize/deserialize elaborated packages to .gaia/build/."""

from __future__ import annotations

from pathlib import Path

from .elaborator import ElaboratedPackage
from .models import ChainExpr


def save_build(elaborated: ElaboratedPackage, build_dir: Path) -> Path:
    """Serialize elaborated package to per-module Markdown files in build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)

    pkg = elaborated.package

    # Index prompts by chain name
    prompts_by_chain: dict[str, list[dict]] = {}
    for p in elaborated.prompts:
        prompts_by_chain.setdefault(p["chain"], []).append(p)

    for mod in pkg.loaded_modules:
        chains = [d for d in mod.declarations if isinstance(d, ChainExpr)]
        if not chains:
            continue

        lines = [f"# Module: {mod.name}\n"]

        for chain in chains:
            ctx = elaborated.chain_contexts.get(chain.name, {})
            edge_type = ctx.get("edge_type", "deduction")
            lines.append(f"## {chain.name} ({edge_type})\n")

            # Premises
            for pref in ctx.get("premise_refs", []):
                snippet = (pref.get("content") or "").strip()
                prior_str = f", prior={pref['prior']}" if pref.get("prior") is not None else ""
                lines.append(f"**Premise:** {pref['name']} ({pref.get('type', '?')}{prior_str})")
                if snippet:
                    lines.append(f"> {snippet}\n")
                else:
                    lines.append("")

            # Steps
            for prompt in prompts_by_chain.get(chain.name, []):
                action = prompt["action"]
                step_num = prompt["step"]
                prior_str = ""
                for s in chain.steps:
                    if s.step == step_num and hasattr(s, "prior") and s.prior is not None:
                        prior_str = f" (prior={s.prior})"
                        break

                if action == "__lambda__":
                    lines.append(f"**Step {step_num}**{prior_str}\n")
                else:
                    lines.append(f"**Step {step_num} — {action}**{prior_str}\n")

                lines.append(prompt["rendered"].strip() + "\n")

                # Evidence / Context
                direct = [a for a in prompt.get("args", []) if a.get("dependency") == "direct"]
                indirect = [a for a in prompt.get("args", []) if a.get("dependency") != "direct"]
                if direct:
                    evidence = ", ".join(
                        f"{a['ref']} ({a.get('decl_type', '?')}, prior={a.get('prior', '?')})"
                        for a in direct
                    )
                    lines.append(f"- Evidence: {evidence}")
                if indirect:
                    context = ", ".join(f"{a['ref']} ({a.get('decl_type', '?')})" for a in indirect)
                    lines.append(f"- Context: {context}")
                if direct or indirect:
                    lines.append("")

            # Conclusions
            for cref in ctx.get("conclusion_refs", []):
                prior_str = f", prior={cref['prior']}" if cref.get("prior") is not None else ""
                lines.append(
                    f"**Conclusion:** {cref['name']} ({cref.get('type', '?')}{prior_str})\n"
                )

        out_path = build_dir / f"{mod.name}.md"
        out_path.write_text("\n".join(lines))

    return build_dir
