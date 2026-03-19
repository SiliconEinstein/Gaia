#!/usr/bin/env python3
"""Convert a paper (Markdown) to a Gaia Language Typst v3 package.

Reuses the LLM pipeline (Steps 1–3) from paper_to_yaml.py, replaces the
YAML generation layer with Typst v3 output.

Usage:
    python scripts/paper_to_typst.py path/to/paper_dir/
    python scripts/paper_to_typst.py path/to/paper_dir/ --skip-llm
    python scripts/paper_to_typst.py path/to/paper_dir/ -o output/
"""

from __future__ import annotations

import argparse
import asyncio
import re
import textwrap
from pathlib import Path

from paper_to_yaml import (
    _build_client,
    _doi_to_slug,
    _find_paper_md,
    _read_existing_xmls,
    _slugify,
    _synthesize_step3,
    parse_step1_xml,
    parse_step2_xml,
    parse_step3_xml,
    run_step1,
    run_step2,
    run_step3,
)

# ── Typst Escaping ────────────────────────────────────────────────────


def _escape_typst(text: str) -> str:
    """Escape special Typst characters and convert LaTeX math to mitex calls.

    Replaces $...$ with #mi("...") and $$...$$ with #mitex("...") for
    rendering LaTeX math in Typst via the mitex package.
    Escapes #, @ in text segments.
    """

    # First handle display math $$...$$
    def _replace_display(m: re.Match) -> str:
        latex = m.group(1).strip()
        # Escape quotes inside the LaTeX
        latex = latex.replace('"', '\\"')
        return f"\n#mitex(`{latex}`)\n"

    text = re.sub(r"\$\$\s*(.*?)\s*\$\$", _replace_display, text, flags=re.DOTALL)

    # Then handle inline math $...$
    def _replace_inline(m: re.Match) -> str:
        latex = m.group(1)
        latex = latex.replace('"', '\\"')
        return f"#mi(`{latex}`)"

    text = re.sub(r"\$([^$]+?)\$", _replace_inline, text)

    # Escape Typst specials in remaining text (but not inside #mi/#mitex calls)
    # Split by mitex/mi calls to avoid double-escaping
    parts = re.split(r"(#mi(?:tex)?\(`[^`]*`\))", text)
    result = []
    for part in parts:
        if part.startswith("#mi"):
            result.append(part)
        else:
            part = part.replace("#", "\\#")
            part = part.replace("@", "\\@")
            result.append(part)
    return "".join(result)


def _truncate_name(name: str, max_len: int = 60) -> str:
    """Truncate a snake_case name to max_len, cutting at word boundary."""
    if len(name) <= max_len:
        return name
    truncated = name[:max_len]
    last_underscore = truncated.rfind("_")
    if last_underscore > 20:
        truncated = truncated[:last_underscore]
    return truncated


def _wrap_content(text: str, width: int = 90) -> str:
    """Wrap long content text for readability, preserving paragraph breaks."""
    paragraphs = text.split("\n\n")
    wrapped = []
    for para in paragraphs:
        # Don't wrap lines that look like math blocks
        if para.strip().startswith("$$") or para.strip().startswith("$"):
            wrapped.append(para)
        else:
            wrapped.append(textwrap.fill(para.strip(), width=width))
    return "\n\n".join(wrapped)


# ── Typst Package Generation ─────────────────────────────────────────


def build_typst_package(parsed: dict, gaia_lang_import: str) -> dict[str, str]:
    """Build Typst v3 package files from parsed Step 1+2+3 data.

    Returns dict mapping filename -> file content string.
    """
    slug = parsed["slug"]
    doi = parsed["doi"]
    step1 = parsed["step1"]
    step2 = parsed["step2"]
    step3 = parsed["step3"]

    result = {}

    # Build conclusion slug lookup
    conc_id_to_slug = {}
    for conc in step1["conclusions"]:
        conc_id_to_slug[conc["id"]] = _truncate_name(_slugify(conc["title"]))

    # Build premise lookup: (conclusion_id, step_id) -> premise names
    premise_lookup: dict[tuple[str, str], list[str]] = {}
    for p in step3["premises"]:
        key = (p["conclusion_id"], p["step_id"])
        premise_lookup.setdefault(key, []).append(p["name"])
    for c in step3["contexts"]:
        key = (c["conclusion_id"], c["step_id"])
        premise_lookup.setdefault(key, []).append(c["name"])

    # All setting names (for #use imports)
    setting_names = set()
    for p in step3["premises"]:
        setting_names.add(p["name"])
    for c in step3["contexts"]:
        setting_names.add(c["name"])

    # Cross-conclusion deps from logic_graph
    cross_conc_deps: dict[str, list[str]] = {}  # conclusion_slug -> [dep_slugs]
    for from_id, to_id in step1["logic_graph"]:
        from_slug = conc_id_to_slug.get(from_id)
        to_slug = conc_id_to_slug.get(to_id)
        if from_slug and to_slug:
            cross_conc_deps.setdefault(to_slug, []).append(from_slug)

    # ── typst.toml ──
    result["typst.toml"] = _gen_typst_toml(slug, doi)

    # ── lib.typ ──
    modules = ["motivation", "setting", "reasoning"]
    has_follow_up = bool(step1["open_questions"].strip())
    if has_follow_up:
        modules.append("follow_up")

    export_names = list(conc_id_to_slug.values())
    if has_follow_up:
        export_names.append("open_questions")

    result["lib.typ"] = _gen_lib_typ(
        slug,
        doi,
        gaia_lang_import,
        modules,
        export_names,
    )

    # ── motivation.typ ──
    result["motivation.typ"] = _gen_motivation_typ(
        gaia_lang_import,
        step1["motivation"],
    )

    # ── setting.typ ──
    result["setting.typ"] = _gen_setting_typ(
        gaia_lang_import,
        step3["premises"],
        step3["contexts"],
    )

    # ── reasoning.typ ──
    result["reasoning.typ"] = _gen_reasoning_typ(
        gaia_lang_import,
        step1["conclusions"],
        step2,
        step3,
        conc_id_to_slug,
        setting_names,
        cross_conc_deps,
        premise_lookup,
    )

    # ── follow_up.typ ──
    if has_follow_up:
        result["follow_up.typ"] = _gen_follow_up_typ(
            gaia_lang_import,
            step1["open_questions"],
        )

    return result


def _gen_typst_toml(slug: str, doi: str) -> str:
    return (
        f"[package]\n"
        f'name = "{slug}"\n'
        f'version = "1.0.0"\n'
        f'entrypoint = "lib.typ"\n'
        f"authors = []\n"
        f'description = "Formalized from paper {doi} — Gaia Lang v3"\n'
    )


def _gen_lib_typ(
    slug: str,
    doi: str,
    gaia_lang_import: str,
    modules: list[str],
    export_names: list[str],
) -> str:
    lines = [
        f'#import "{gaia_lang_import}": *',
        '#import "@preview/mitex:0.2.5": mitex, mi',
        "#show: gaia-style",
        "",
        f'#package("{slug}",',
        f'  title: "{doi}",',
        '  version: "1.0.0",',
        "  modules: ({}),".format(", ".join('"' + m + '"' for m in modules)),
        "  export: (",
    ]
    for name in export_names:
        lines.append(f'    "{name}",')
    lines.append("  ),")
    lines.append(")")
    lines.append("")

    for mod in modules:
        lines.append(f'#include "{mod}.typ"')

    lines.append("")
    lines.append("#export-graph()")
    lines.append("")
    return "\n".join(lines)


def _gen_motivation_typ(gaia_lang_import: str, motivation: str) -> str:
    content = _escape_typst(motivation.strip())
    return (
        f'#import "{gaia_lang_import}": *\n'
        f'#import "@preview/mitex:0.2.5": mitex, mi\n'
        f"\n"
        f'#module("motivation", title: "Research Motivation")\n'
        f"\n"
        f'#setting("research_motivation")[\n'
        f"  {_wrap_content(content, 88)}\n"
        f"]\n"
    )


def _gen_setting_typ(
    gaia_lang_import: str,
    premises: list[dict],
    contexts: list[dict],
) -> str:
    lines = [
        f'#import "{gaia_lang_import}": *',
        '#import "@preview/mitex:0.2.5": mitex, mi',
        "",
        '#module("setting", title: "Settings and Premises")',
    ]

    seen_names: set[str] = set()

    for p in premises:
        name = _truncate_name(p["name"])
        if name in seen_names:
            continue
        seen_names.add(name)
        content = _escape_typst(p["content"].strip())
        lines.append("")
        lines.append(f'#setting("{name}")[')
        lines.append(f"  {_wrap_content(content, 88)}")
        lines.append("]")

    for c in contexts:
        name = _truncate_name(c["name"])
        if name in seen_names:
            continue
        seen_names.add(name)
        content = _escape_typst(c["content"].strip())
        lines.append("")
        lines.append(f'#setting("{name}")[')
        lines.append(f"  {_wrap_content(content, 88)}")
        lines.append("]")

    lines.append("")
    return "\n".join(lines)


def _gen_reasoning_typ(
    gaia_lang_import: str,
    conclusions: list[dict],
    chains: list[dict],
    step3: dict,
    conc_id_to_slug: dict[str, str],
    setting_names: set[str],
    cross_conc_deps: dict[str, list[str]],
    premise_lookup: dict[tuple[str, str], list[str]],
) -> str:
    lines = [
        f'#import "{gaia_lang_import}": *',
        '#import "@preview/mitex:0.2.5": mitex, mi',
        "",
        '#module("reasoning", title: "Reasoning and Conclusions")',
    ]

    # Collect all settings used by any chain → #use imports
    used_settings: set[str] = set()
    chain_by_conc_id: dict[str, dict] = {}
    for chain in chains:
        chain_by_conc_id[chain["conclusion_id"]] = chain
        cid = chain["conclusion_id"]
        for step in chain["steps"]:
            prem_names = premise_lookup.get((cid, step["id"]), [])
            for pn in prem_names:
                if pn in setting_names:
                    used_settings.add(pn)

    # Also add settings that are directly referenced by Step 3 premises
    for p in step3["premises"]:
        used_settings.add(p["name"])
    for c in step3["contexts"]:
        used_settings.add(c["name"])

    if used_settings:
        lines.append("")
        lines.append("// ── Cross-module imports ──")
        for sname in sorted(used_settings):
            lines.append(f'#use("setting.{_truncate_name(sname)}")')

    # Topologically sort conclusions: if A depends on B, B comes first
    ordered_slugs = _topo_sort_conclusions(conc_id_to_slug, cross_conc_deps)
    slug_to_conc = {_truncate_name(_slugify(c["title"])): c for c in conclusions}

    for cslug in ordered_slugs:
        conc = slug_to_conc.get(cslug)
        if conc is None:
            continue

        cid = conc["id"]
        chain = chain_by_conc_id.get(cid)

        # Collect all premises for this claim
        claim_premises: list[str] = []

        # From cross-conclusion deps
        for dep_slug in cross_conc_deps.get(cslug, []):
            if dep_slug not in claim_premises:
                claim_premises.append(dep_slug)

        # From chain steps
        if chain:
            for step in chain["steps"]:
                prem_names = premise_lookup.get((cid, step["id"]), [])
                for pn in prem_names:
                    tn = _truncate_name(pn)
                    if tn not in claim_premises:
                        claim_premises.append(tn)

        # Build reasoning text from chain lambda steps
        reasoning_parts = []
        if chain:
            for step in chain["steps"]:
                text = step.get("text", "").strip()
                if text:
                    reasoning_parts.append(text)

        content = _escape_typst(conc["content"].strip())

        lines.append("")
        if claim_premises and reasoning_parts:
            # Claim with proof block
            lines.append(f'#claim("{cslug}")[')
            lines.append(f"  {_wrap_content(content, 88)}")
            lines.append("][")
            for pname in claim_premises:
                lines.append(f'  #premise("{pname}")')
            lines.append("")
            reasoning_text = _escape_typst("\n\n".join(reasoning_parts))
            lines.append(f"  {_wrap_content(reasoning_text, 88)}")
            lines.append("]")
        elif claim_premises:
            # Claim with premises but no reasoning text
            lines.append(f'#claim("{cslug}")[')
            lines.append(f"  {_wrap_content(content, 88)}")
            lines.append("][")
            for pname in claim_premises:
                lines.append(f'  #premise("{pname}")')
            lines.append("]")
        else:
            # Claim without proof block
            lines.append(f'#claim("{cslug}")[')
            lines.append(f"  {_wrap_content(content, 88)}")
            lines.append("]")

    lines.append("")
    return "\n".join(lines)


def _gen_follow_up_typ(gaia_lang_import: str, open_questions: str) -> str:
    content = _escape_typst(open_questions.strip())
    return (
        f'#import "{gaia_lang_import}": *\n'
        f'#import "@preview/mitex:0.2.5": mitex, mi\n'
        f"\n"
        f'#module("follow_up", title: "Open Questions")\n'
        f"\n"
        f'#question("open_questions")[\n'
        f"  {_wrap_content(content, 88)}\n"
        f"]\n"
    )


def _topo_sort_conclusions(
    conc_id_to_slug: dict[str, str],
    cross_conc_deps: dict[str, list[str]],
) -> list[str]:
    """Topologically sort conclusion slugs so dependencies come first."""
    all_slugs = list(conc_id_to_slug.values())
    in_degree: dict[str, int] = {s: 0 for s in all_slugs}
    for slug, deps in cross_conc_deps.items():
        if slug in in_degree:
            in_degree[slug] = len(deps)

    queue = [s for s in all_slugs if in_degree.get(s, 0) == 0]
    result = []
    visited = set()

    while queue:
        node = queue.pop(0)
        if node in visited:
            continue
        visited.add(node)
        result.append(node)
        for slug, deps in cross_conc_deps.items():
            if node in deps and slug not in visited:
                in_degree[slug] -= 1
                if in_degree[slug] <= 0:
                    queue.append(slug)

    # Add any remaining (cycles or disconnected)
    for s in all_slugs:
        if s not in visited:
            result.append(s)

    return result


# ── Write Package ─────────────────────────────────────────────────────


def write_typst_package(data: dict[str, str], output_dir: Path) -> Path:
    """Write Typst package files to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in data.items():
        (output_dir / filename).write_text(content, encoding="utf-8")
    return output_dir


# ── Main Pipeline ─────────────────────────────────────────────────────


async def process_paper(
    paper_dir: Path,
    output_dir: Path,
    gaia_lang_import: str,
    client=None,
    model: str = "gpt-5-mini",
    skip_llm: bool = False,
) -> Path | None:
    """Process a single paper directory into a Typst v3 package."""
    slug = _doi_to_slug(paper_dir.name)
    doi = paper_dir.name

    if skip_llm:
        xmls = _read_existing_xmls(paper_dir)
        if xmls is None:
            return None
        step1_xml = xmls["step1_xml"]
        step2_xml = xmls["step2_xml"]
        step3_xml = xmls["step3_xml"]
    else:
        paper_md_path = _find_paper_md(paper_dir)
        if paper_md_path is None:
            print(f"  SKIP: no paper markdown in {paper_dir}")
            return None
        paper_md = paper_md_path.read_text()

        assert client is not None, "LLM client required when not using --skip-llm"
        step1_xml = await run_step1(client, paper_md, model)
        step2_xml = await run_step2(client, paper_md, step1_xml, model)
        step3_xml = await run_step3(client, paper_md, step2_xml, model)

        (paper_dir / "select_conclusion.xml").write_text(step1_xml)
        (paper_dir / "reasoning_chain.xml").write_text(step2_xml)
        (paper_dir / "review.xml").write_text(step3_xml)
        print(f"  Saved intermediate XMLs to {paper_dir}")

    step1_data = parse_step1_xml(step1_xml)
    if step1_data is None:
        print("  SKIP: paper passed (review/survey)")
        return None

    step2_data = parse_step2_xml(step2_xml)
    step3_data = (
        parse_step3_xml(step3_xml) if step3_xml else _synthesize_step3(step1_data, step2_data)
    )

    parsed = {
        "slug": slug,
        "doi": doi,
        "step1": step1_data,
        "step2": step2_data,
        "step3": step3_data,
    }

    typst_data = build_typst_package(parsed, gaia_lang_import)
    pkg_dir = write_typst_package(typst_data, output_dir / slug)

    n_settings = sum(1 for p in step3_data["premises"]) + sum(1 for c in step3_data["contexts"])
    n_conclusions = len(step1_data["conclusions"])
    n_files = len(typst_data)
    print(f"  OK -> {slug}: {n_conclusions} claims, {n_settings} settings, {n_files} .typ files")
    return pkg_dir


async def main():
    parser = argparse.ArgumentParser(description="Convert paper to Gaia Typst v3 package")
    parser.add_argument(
        "paper_dirs", type=Path, nargs="+", help="Paper directories with .md and/or .xml files"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output_typst"),
        help="Output directory (default: output_typst/)",
    )
    parser.add_argument("--skip-llm", action="store_true", help="Skip LLM, use existing XMLs")
    parser.add_argument("--model", default="gpt-5-mini", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument(
        "--gaia-lang-import",
        default="../../libs/typst/gaia-lang/v2.typ",
        help="Import path for gaia-lang v2.typ (relative to output package)",
    )
    parser.add_argument("--concurrency", type=int, default=3, help="Max concurrent papers")
    args = parser.parse_args()

    paper_dirs = []
    for p in args.paper_dirs:
        if not p.exists():
            print(f"Warning: directory not found: {p}")
            continue
        subdirs = [d for d in sorted(p.iterdir()) if d.is_dir() and d.name != "images"]
        has_own_files = any(p.glob("*.md")) or any(p.glob("*.xml"))
        if subdirs and not has_own_files:
            paper_dirs.extend(subdirs)
        else:
            paper_dirs.append(p)

    if not paper_dirs:
        print("No paper directories found.")
        return

    client = None
    if not args.skip_llm:
        client = _build_client(args.base_url, args.api_key)

    semaphore = asyncio.Semaphore(args.concurrency)

    async def process_with_limit(paper_dir: Path) -> Path | None:
        async with semaphore:
            print(f"Processing: {paper_dir.name}")
            try:
                return await process_paper(
                    paper_dir,
                    args.output_dir,
                    args.gaia_lang_import,
                    client=client,
                    model=args.model,
                    skip_llm=args.skip_llm,
                )
            except Exception as e:
                print(f"  ERROR {paper_dir.name}: {e}")
                import traceback

                traceback.print_exc()
                return None

    results = await asyncio.gather(*[process_with_limit(d) for d in paper_dirs])
    succeeded = [r for r in results if r is not None]
    print(f"\nDone: {len(succeeded)}/{len(paper_dirs)} papers processed.")


if __name__ == "__main__":
    asyncio.run(main())
