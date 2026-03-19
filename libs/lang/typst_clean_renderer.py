"""Render a Typst-based Gaia package to clean Typst for review.

Outputs readable Typst with native cross-references (@label),
stripping away DSL commands while preserving referencing and math.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11
    import tomli as tomllib  # type: ignore[no-redef]

from .typst_loader import load_typst_package

_TYPE_LABELS = {
    "claim": "主张",
    "setting": "设定",
    "observation": "观察",
    "question": "问题",
    "contradiction": "矛盾",
    "corroboration": "印证",
    "equivalence": "等价",
}


def _clean_text(text: str) -> str:
    text = re.sub(r"[ \t]+", " ", text).strip()
    text = re.sub(r"([。！？；：，、」』】）]) ", r"\1", text)
    return text


def _first_sentence(text: str, max_len: int = 80) -> str:
    text = _clean_text(text)
    best = len(text)
    for sep in ("。", ".", "！", "!", "？", "?"):
        idx = text.find(sep)
        if 0 < idx < best:
            best = idx
    if best < len(text) and best < max_len:
        return text[: best + 1]
    if len(text) > max_len:
        return text[:max_len] + "…"
    return text


def _read_pkg_meta(pkg_path: Path) -> dict:
    toml_path = pkg_path / "typst.toml"
    if not toml_path.exists():
        return {}
    with open(toml_path, "rb") as f:
        data = tomllib.load(f)
    return data.get("package", {})


def _aid(name: str) -> str:
    """Convert node name to Typst label ID."""
    return name.replace("_", "-")


def _ref(name: str) -> str:
    """Format a Typst reference."""
    return f"@{_aid(name)}"


def _label(name: str) -> str:
    """Format a Typst label."""
    return f"<{_aid(name)}>"


def _join_refs(names: list[str]) -> str:
    refs = [_ref(n) for n in names]
    if len(refs) == 1:
        return refs[0]
    if len(refs) == 2:
        return f"{refs[0]} 和 {refs[1]}"
    return "、".join(refs[:-1]) + " 和 " + refs[-1]


def _type_label(node_type: str) -> str:
    return _TYPE_LABELS.get(node_type, node_type)


def _build_overview(chains: dict[str, list[dict]], node_map: dict) -> list[str]:
    lines: list[str] = []
    if not chains:
        return lines

    chain_conclusions: dict[str, str] = {}
    chain_summaries: dict[str, str] = {}
    for chain_name, factors in chains.items():
        sorted_factors = sorted(factors, key=lambda f: f.get("step", 0))
        if not sorted_factors:
            continue
        conclusion = sorted_factors[-1]["conclusion"]
        chain_conclusions[chain_name] = conclusion
        node = node_map.get(conclusion)
        if node:
            chain_summaries[chain_name] = _first_sentence(node["content"])

    conclusion_to_chain = {v: k for k, v in chain_conclusions.items()}

    chain_deps: dict[str, list[str]] = {name: [] for name in chains}
    for chain_name, factors in chains.items():
        for factor in factors:
            for p in factor.get("premise", []):
                dep: str | None = None
                if p in chains and p != chain_name:
                    dep = p
                elif p in conclusion_to_chain and conclusion_to_chain[p] != chain_name:
                    dep = conclusion_to_chain[p]
                if dep and dep not in chain_deps[chain_name]:
                    chain_deps[chain_name].append(dep)

    roots = [name for name in chains if not chain_deps[name]]

    lines.append("== 论证结构")
    rendered: set[str] = set()

    def _render_chain(name: str, depth: int) -> None:
        indent = "  " * depth
        connector = "└─ " if depth > 0 else "- "
        if name in rendered:
            lines.append(f"{indent}{connector}*{name}*（见上）")
            return
        rendered.add(name)
        summary = chain_summaries.get(name, "")
        lines.append(f"{indent}{connector}*{name}* → {summary}")
        children = [c for c in chains if name in chain_deps.get(c, [])]
        for child in children:
            _render_chain(child, depth + 1)

    for root in roots:
        _render_chain(root, 0)
    for name in chains:
        if name not in rendered:
            _render_chain(name, 0)

    return lines


def render_typst_to_clean_typst(pkg_path: Path, output: Path | None = None) -> str:
    """Render a Typst package to a clean Typst document with native cross-references."""
    pkg_path = Path(pkg_path)
    graph = load_typst_package(pkg_path)
    meta = _read_pkg_meta(pkg_path)
    lines: list[str] = []

    # ── Package header ──
    pkg_name = meta.get("name", pkg_path.name)
    lines.append(f"= {pkg_name.replace('_', ' ')}")
    if meta.get("description"):
        lines.append(f"_{meta['description']}_")
    meta_parts = []
    if meta.get("authors"):
        meta_parts.append(f"Authors: {', '.join(meta['authors'])}")
    if meta.get("version"):
        meta_parts.append(f"Version: {meta['version']}")
    if meta_parts:
        lines.append(f"{' | '.join(meta_parts)}")
    lines.append("")

    # ── Pre-compute ──
    node_map = {n["name"]: n for n in graph["nodes"]}

    factor_by_conclusion = {
        factor["conclusion"]: factor
        for factor in graph.get("factors", [])
        if factor.get("conclusion")
    }
    proved_nodes = set(factor_by_conclusion)

    chains: dict[str, list[dict]] = {}
    for factor in graph.get("factors", []):
        chain_name = factor.get("chain", "")
        if chain_name:
            chains.setdefault(chain_name, []).append(factor)

    chain_conclusion_map: dict[str, str] = {}
    for chain_name, factors in chains.items():
        sorted_factors = sorted(factors, key=lambda f: f.get("step", 0))
        if sorted_factors:
            chain_conclusion_map[chain_name] = sorted_factors[-1]["conclusion"]

    # ── Overview ──
    lines.extend(_build_overview(chains, node_map))

    # ── Render by module ──
    modules = graph.get("modules", [])
    module_titles = graph.get("module_titles", {})

    nodes_by_module: dict[str, list[dict]] = {}
    for node in graph["nodes"]:
        mod = node.get("module", "")
        nodes_by_module.setdefault(mod, []).append(node)

    chains_by_module: dict[str, list[str]] = {}
    for factor in graph.get("factors", []):
        mod_name = node_map.get(factor.get("conclusion", ""), {}).get("module", "")
        chain_name = factor.get("chain", "")
        if chain_name and chain_name not in chains_by_module.get(mod_name, []):
            chains_by_module.setdefault(mod_name, []).append(chain_name)

    for mod_name in modules:
        lines.append("")
        title = module_titles.get(mod_name)
        label = _label(mod_name)
        if title:
            lines.append(f"== {title} {label}")
        else:
            lines.append(f"== {mod_name.replace('_', ' ')} {label}")

        # ── Independent knowledge ──
        mod_nodes = nodes_by_module.get(mod_name, [])
        independent = [n for n in mod_nodes if n["name"] not in proved_nodes]

        groups: list[list[dict]] = []
        for node in independent:
            if groups and groups[-1][0]["type"] == node["type"]:
                groups[-1].append(node)
            else:
                groups.append([node])

        for group in groups:
            if len(group) > 1:
                tl = _type_label(group[0]["type"])
                lines.append(f"=== 可能用到的{tl}")
            for node in group:
                tl = _type_label(node["type"])
                content = _clean_text(node["content"])
                lines.append(f"- {content}（{tl}） {_label(node['name'])}")

        # ── v3 single-claim proofs (no chain field) ──
        for node in mod_nodes:
            factor = factor_by_conclusion.get(node["name"])
            if factor is None or factor.get("chain"):
                continue

            lines.append("")
            lines.append(f"=== {node['name'].replace('_', ' ')} {_label(node['name'])}")
            _render_single_step(
                lines,
                factor,
                _clean_text(node["content"]),
                _type_label(node["type"]),
                node["name"],
            )

        # ── Chains ──
        for chain_name in chains_by_module.get(mod_name, []):
            factor_list = chains[chain_name]
            sorted_factors = sorted(factor_list, key=lambda f: f.get("step", 0))
            is_single_step = len(sorted_factors) == 1

            lines.append("")
            lines.append(f"=== Chain: {chain_name.replace('_', ' ')} {_label(chain_name)}")

            seen_premises: set[str] = set()
            seen_context: set[str] = set()
            chain_step_conclusions: set[str] = set()

            for i, factor in enumerate(sorted_factors):
                conclusion = factor["conclusion"]
                node = node_map.get(conclusion)
                if node is None:
                    continue

                is_last = i == len(sorted_factors) - 1
                tl = _type_label(node["type"])
                content = _clean_text(node["content"])

                if is_single_step:
                    _render_single_step(
                        lines,
                        factor,
                        content,
                        tl,
                        node["name"],
                    )
                else:
                    if i > 0:
                        lines.append("")
                    lines.append(f"*第 {i + 1} 步*（{tl}）")

                    premise = factor.get("premise", [])
                    new_premises = [p for p in premise if p not in seen_premises]
                    context = factor.get("context", [])
                    new_context = [c for c in context if c not in seen_context]

                    internal = [p for p in new_premises if p in chain_step_conclusions]
                    external = [p for p in new_premises if p not in chain_step_conclusions]

                    _render_step(
                        lines,
                        internal,
                        external,
                        new_context,
                        content,
                        node["name"],
                        is_last,
                    )

                    seen_premises.update(premise)
                    seen_context.update(context)
                    chain_step_conclusions.add(conclusion)

    result = "\n".join(lines)

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(result)

    return result


def _render_single_step(
    lines: list[str],
    factor: dict,
    content: str,
    type_label: str,
    name: str,
) -> None:
    premise = factor.get("premise", [])
    context = factor.get("context", [])

    if len(premise) == 1 and not context:
        lines.append(f"基于 {_ref(premise[0])}，得出：")
    elif len(premise) == 1 and len(context) == 1:
        lines.append(f"基于 {_ref(premise[0])}，在 {_ref(context[0])} 下，得出：")
    elif premise:
        lines.append("基于以下前提：")
        for p in premise:
            lines.append(f"+ {_ref(p)}")
        if context:
            lines.append(f"在 {_join_refs(context)} 下，得出：")
        else:
            lines.append("得出：")

    lines.append(f"*结论*（{type_label}）: {content} {_label(name)}")


def _render_step(
    lines: list[str],
    internal: list[str],
    external: list[str],
    new_context: list[str],
    content: str,
    name: str,
    is_conclusion: bool,
) -> None:
    transition = "得到结论" if is_conclusion else "可以推出"

    ref_prefix = ""
    if internal:
        ref_prefix = f"结合 {_join_refs(internal)}，"

    has_ext = len(external) > 0
    has_ctx = len(new_context) > 0

    if internal and not has_ext and not has_ctx:
        lines.append(f"{ref_prefix}{transition}：")
    elif not has_ext and not has_ctx:
        pass  # no premises, no context — just content
    elif has_ext and len(external) == 1 and not has_ctx:
        lines.append(f"{ref_prefix}如果 {_ref(external[0])} 成立，{transition}：")
    elif has_ext and len(external) == 1 and has_ctx and len(new_context) == 1:
        lines.append(
            f"{ref_prefix}如果 {_ref(external[0])} 成立，"
            f"在 {_ref(new_context[0])} 下，{transition}："
        )
    else:
        if has_ext:
            if len(external) == 1:
                lines.append(f"{ref_prefix}如果 {_ref(external[0])} 成立，")
            else:
                if ref_prefix:
                    lines.append(ref_prefix)
                lines.append("如果以下前提都成立：")
                for p in external:
                    lines.append(f"+ {_ref(p)}")

        if has_ctx:
            if len(new_context) == 1:
                lines.append(f"在 {_ref(new_context[0])} 下，{transition}：")
            else:
                lines.append("在以下背景下：")
                for c in new_context:
                    lines.append(f"+ {_ref(c)}")
                lines.append(f"{transition}：")
        else:
            lines.append(f"{transition}：")

    lines.append(f"{content} {_label(name)}")
