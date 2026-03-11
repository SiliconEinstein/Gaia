"""Serialize elaborated package to a single package.md file."""

from __future__ import annotations

from pathlib import Path

from .elaborator import ElaboratedPackage
from .models import (
    ChainExpr,
    Claim,
    Contradiction,
    Equivalence,
    Knowledge,
    Question,
    Ref,
    Setting,
    StepApply,
    StepLambda,
    Subsumption,
)

# Chinese ordinal numbers for module headers
_CHINESE_ORDINALS = ["一", "二", "三", "四", "五", "六", "七", "八", "九", "十"]

# Knowledge types shown as standalone declarations (not chains/actions)
_DECLARATION_TYPES = (Claim, Setting, Question, Contradiction, Equivalence, Subsumption)


def save_build(elaborated: ElaboratedPackage, build_dir: Path) -> Path:
    """Serialize elaborated package to a single package.md file in build_dir."""
    build_dir.mkdir(parents=True, exist_ok=True)

    pkg = elaborated.package

    # Build a lookup from knowledge name -> resolved Knowledge object
    decl_index: dict[str, Knowledge] = dict(pkg._index) if pkg._index else {}
    # Also index by bare name for convenience
    for key, decl in list(decl_index.items()):
        _, _, bare = key.partition(".")
        if bare and bare not in decl_index:
            decl_index[bare] = decl

    # Index prompts by chain name -> list of prompt dicts
    prompts_by_chain: dict[str, list[dict]] = {}
    for p in elaborated.prompts:
        prompts_by_chain.setdefault(p["chain"], []).append(p)

    lines: list[str] = []

    # Title
    description = ""
    if pkg.manifest and pkg.manifest.description:
        description = pkg.manifest.description.strip()
    version = pkg.version or "0.0.0"
    if description:
        lines.append(f"# {description} ({pkg.name} v{version})")
        lines.append("")
        lines.append(f"> {description}")
    else:
        lines.append(f"# {pkg.name} v{version}")
    lines.append("")

    # Modules
    for mod_idx, mod in enumerate(pkg.loaded_modules):
        if mod_idx > 0:
            lines.append("---")
            lines.append("")

        ordinal = (
            _CHINESE_ORDINALS[mod_idx] if mod_idx < len(_CHINESE_ORDINALS) else str(mod_idx + 1)
        )
        title = mod.title or mod.name
        lines.append(f"## {ordinal}、{title} [module:{mod.name}]")
        lines.append("")

        # Separate knowledge into declarations and chains
        declarations: list[Knowledge] = []
        chains: list[ChainExpr] = []
        for decl in mod.knowledge:
            actual = decl
            if isinstance(decl, Ref) and decl._resolved is not None:
                actual = decl._resolved
            if isinstance(decl, ChainExpr):
                chains.append(decl)
            elif isinstance(actual, _DECLARATION_TYPES) and not isinstance(decl, Ref):
                declarations.append(actual)

        # Knowledge declarations section
        if declarations:
            lines.append("### Knowledge declarations")
            lines.append("")
            for decl in declarations:
                prior_str = f" (prior={decl.prior})" if decl.prior is not None else ""
                content = getattr(decl, "content", "").strip()
                lines.append(f"**[{decl.type}] {decl.name}**{prior_str}")
                if content:
                    lines.append(f"> {content}")
                lines.append("")

        # Chain sections
        for chain in chains:
            ctx = elaborated.chain_contexts.get(chain.name, {})
            edge_type = ctx.get("edge_type", "deduction")
            lines.append(f"### Chain: {chain.name} [chain:{chain.name}] ({edge_type})")
            lines.append("")

            # Gather all prompts for this chain to find indirect deps (context)
            chain_prompts = prompts_by_chain.get(chain.name, [])
            indirect_refs = _collect_indirect_refs(chain_prompts)
            if indirect_refs:
                lines.append("**Context (indirect reference):**")
                for ref_info in indirect_refs:
                    decl = _resolve_name(ref_info["ref"], decl_index)
                    if decl:
                        prior_str = f" (prior={decl.prior})" if decl.prior is not None else ""
                        content = getattr(decl, "content", "").strip()
                        lines.append(f"> **[{decl.type}] {decl.name}**{prior_str}")
                        if content:
                            lines.append(f"> {content}")
                    else:
                        lines.append(f"> **[?] {ref_info['ref']}**")
                lines.append("")

            # Steps
            for prompt in chain_prompts:
                step_num = prompt["step"]

                # Find step prior
                step_prior = None
                for s in chain.steps:
                    if isinstance(s, (StepApply, StepLambda)) and s.step == step_num:
                        step_prior = s.prior
                        break

                prior_str = f" (prior={step_prior})" if step_prior is not None else ""
                lines.append(f"**[step:{chain.name}.{step_num}]**{prior_str}")
                lines.append("")

                # Direct references for this step
                direct = [a for a in prompt.get("args", []) if a.get("dependency") == "direct"]
                if direct:
                    lines.append("**Direct references:**")
                    for a in direct:
                        decl = _resolve_name(a["ref"], decl_index)
                        if decl:
                            a_prior_str = f" (prior={decl.prior})" if decl.prior is not None else ""
                            content = getattr(decl, "content", "").strip()
                            lines.append(f"> **[{decl.type}] {decl.name}**{a_prior_str}")
                            if content:
                                lines.append(f"> {content}")
                        else:
                            lines.append(f"> **[?] {a['ref']}**")
                    lines.append("")

                # Reasoning (rendered prompt text)
                rendered = prompt["rendered"].strip()
                if rendered:
                    lines.append("**Reasoning:**")
                    lines.append(f"> {rendered}")
                    lines.append("")

            # Conclusion
            for cref in ctx.get("conclusion_refs", []):
                decl = _resolve_name(cref["name"], decl_index)
                if decl:
                    prior_str = f" (prior={decl.prior})" if decl.prior is not None else ""
                    content = getattr(decl, "content", "").strip()
                    lines.append(f"**Conclusion:** [{decl.type}] {decl.name}{prior_str}")
                    if content:
                        lines.append(f"> {content}")
                else:
                    cprior = cref.get("prior")
                    ctype = cref.get("type", "?")
                    prior_str = f" (prior={cprior})" if cprior is not None else ""
                    lines.append(f"**Conclusion:** [{ctype}] {cref['name']}{prior_str}")
                lines.append("")

    out_path = build_dir / "package.md"
    out_path.write_text("\n".join(lines))
    return build_dir


def _collect_indirect_refs(prompts: list[dict]) -> list[dict]:
    """Collect unique indirect (context) references across all steps of a chain."""
    seen: set[str] = set()
    result: list[dict] = []
    for prompt in prompts:
        for a in prompt.get("args", []):
            if a.get("dependency") != "direct" and a["ref"] not in seen:
                seen.add(a["ref"])
                result.append(a)
    return result


def _resolve_name(name: str, index: dict[str, Knowledge]) -> Knowledge | None:
    """Resolve a knowledge name to its object, trying multiple key formats."""
    if name in index:
        return index[name]
    # Try searching all keys that end with .name
    for key, decl in index.items():
        if key.endswith(f".{name}"):
            return decl
    return None
