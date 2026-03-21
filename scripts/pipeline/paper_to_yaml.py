#!/usr/bin/env python3
"""Convert a paper (Markdown) to a Gaia Language YAML package.

Pipeline: Paper MD → LLM Step 1-3 → XML → YAML

Usage:
    python scripts/paper_to_yaml.py path/to/paper_dir/
    python scripts/paper_to_yaml.py path/to/paper_dir/ --skip-llm
    python scripts/paper_to_yaml.py path/to/paper_dir/ -o output/
"""

from __future__ import annotations

import argparse
import asyncio
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from openai import AsyncOpenAI


# ── LLM Call Layer ─────────────────────────────────────────────────────


def _build_client(base_url: str | None = None, api_key: str | None = None) -> AsyncOpenAI:
    """Build OpenAI client configured for dptech proxy."""
    return AsyncOpenAI(
        base_url=base_url or os.getenv("DP_INTERNAL_BASE_URL", "http://localhost:8004/v1"),
        api_key=api_key or os.getenv("DP_INTERNAL_API_KEY", "dummy-key"),
        default_headers={"accessKey": os.getenv("DP_INTERNAL_API_KEY", "")},
    )


async def call_llm(
    client: AsyncOpenAI,
    system_prompt: str,
    user_prompt: str,
    model: str = "azure/gpt-5-mini",
) -> str:
    """Call LLM and return the response text."""
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=1.0,
        max_completion_tokens=60480,
    )
    return response.choices[0].message.content or ""


_XML_TAG_RE = re.compile(
    r"<"
    r"(?:!--.*?--|"  # XML comments
    r"\?.*?\?|"  # processing instructions (<?xml ...?>)
    r"/?\s*[a-zA-Z_][\w.-]*"  # tag name (with optional /)
    r'(?:\s+[\w.-]+\s*=\s*"[^"]*")*'  # attributes
    r"\s*/?)"  # optional self-closing /
    r">"
)


def _sanitize_xml(text: str) -> str:
    """Fix common XML issues in LLM output (unescaped &, <, > in LaTeX/text)."""
    # Fix unescaped & (but not already-escaped &amp; &lt; etc.)
    text = re.sub(r"&(?!amp;|lt;|gt;|apos;|quot;|#)", "&amp;", text)

    # Protect valid XML tags with placeholders, escape remaining < >, restore
    placeholders: list[str] = []

    def _protect(m: re.Match) -> str:
        # Also fix < > inside attribute values within the tag
        tag = m.group(0)
        tag = _fix_attr_values(tag)
        placeholders.append(tag)
        return f"\x00TAG{len(placeholders) - 1}\x00"

    text = _XML_TAG_RE.sub(_protect, text)
    text = text.replace("<", "&lt;").replace(">", "&gt;")
    for i, tag in enumerate(placeholders):
        text = text.replace(f"\x00TAG{i}\x00", tag)
    return text


def _fix_attr_values(tag: str) -> str:
    """Escape < > inside XML attribute values."""

    def _escape_attr(m: re.Match) -> str:
        name = m.group(1)
        val = m.group(2).replace("<", "&lt;").replace(">", "&gt;")
        return f'{name}="{val}"'

    return re.sub(r'([\w.-]+)\s*=\s*"([^"]*)"', _escape_attr, tag)


def _extract_inference_unit(text: str) -> str:
    """Extract <inference_unit>...</inference_unit> from LLM response."""
    match = re.search(r"<inference_unit>.*?</inference_unit>", text, re.DOTALL)
    if match:
        return _sanitize_xml(match.group(0))
    # Fallback: try wrapping if tags are missing
    if "<conclusions>" in text or "<conclusion_reasoning" in text or "<premises>" in text:
        return _sanitize_xml(f"<inference_unit>{text}</inference_unit>")
    return _sanitize_xml(text)


# ── Step Runners ───────────────────────────────────────────────────────


PROMPTS_DIR = Path(__file__).parent.parent / "libs" / "prompts"


async def run_step1(client: AsyncOpenAI, paper_md: str, model: str) -> str:
    """Step 1: Extract conclusions, motivation, open questions."""
    prompt = (PROMPTS_DIR / "step1_select_conclusions_status_v3.md").read_text()
    print("  Step 1: Extracting conclusions...")
    response = await call_llm(client, prompt, paper_md, model)
    return _extract_inference_unit(response)


async def run_step2(client: AsyncOpenAI, paper_md: str, step1_xml: str, model: str) -> str:
    """Step 2: Reconstruct reasoning chains."""
    prompt = (PROMPTS_DIR / "step2_build_reasoning_chain_v3.md").read_text()
    user_prompt = f"Conclusions XML:\n{step1_xml}\n\nPaper:\n{paper_md}"
    print("  Step 2: Reconstructing reasoning chains...")
    response = await call_llm(client, prompt, user_prompt, model)
    return _extract_inference_unit(response)


async def run_step3(client: AsyncOpenAI, paper_md: str, step2_xml: str, model: str) -> str:
    """Step 3: Review and probability assessment."""
    prompt = (PROMPTS_DIR / "step3_review_v2.md").read_text()
    user_prompt = f"Reasoning XML: {step2_xml}\n\nPaper: {paper_md}"
    print("  Step 3: Reviewing and assessing probabilities...")
    response = await call_llm(client, prompt, user_prompt, model)
    return _extract_inference_unit(response)


# ── XML Parsing Layer ──────────────────────────────────────────────────


def _element_full_text(el: ET.Element) -> str:
    """Get all text content from an element, including tail text of children.

    Preserves inline <ref> content within the text flow.
    """
    parts = []
    if el.text:
        parts.append(el.text)
    for child in el:
        # Include ref content inline
        if child.tag == "ref":
            ref_text = (child.text or "").strip()
            if ref_text:
                parts.append(f" [{ref_text}]")
        elif child.tag == "problem":
            pass  # Skip nested <problem> — parsed separately
        elif child.tag == "cross_ref":
            pass  # Parsed separately
        else:
            parts.append(_element_full_text(child))
        if child.tail:
            parts.append(child.tail)
    return "".join(parts).strip()


def parse_step1_xml(xml_str: str) -> dict | None:
    """Parse Step 1 output: motivation, conclusions, logic_graph, open_questions.

    Returns None if the paper was skipped (<pass/>).
    """
    root = ET.fromstring(_sanitize_xml(xml_str))

    # Check for <pass/>
    if root.find("pass") is not None:
        return None

    # Motivation (top-level <problem>)
    problem_el = root.find("problem")
    motivation = _element_full_text(problem_el) if problem_el is not None else ""

    # Conclusions
    conclusions = []
    for conc in root.findall(".//conclusions/conclusion"):
        # Extract nested <problem> (conclusion-specific)
        conc_problem_el = conc.find("problem")
        conc_problem = _element_full_text(conc_problem_el) if conc_problem_el is not None else ""

        # Extract <ref> (figure/table evidence)
        ref_el = conc.find("ref")
        ref_text = ref_el.text.strip() if ref_el is not None and ref_el.text else ""

        # Content: full text minus nested problem and ref
        content = _element_full_text(conc)

        conclusions.append(
            {
                "id": conc.get("id", ""),
                "title": conc.get("title", ""),
                "content": content,
                "problem": conc_problem,
                "ref": ref_text,
            }
        )

    # Logic graph
    logic_graph = []
    for edge in root.findall(".//logic_graph/edge"):
        logic_graph.append((edge.get("from", ""), edge.get("to", "")))

    # Open questions
    oq_el = root.find("open_question")
    open_questions = _element_full_text(oq_el) if oq_el is not None else ""

    return {
        "motivation": motivation,
        "conclusions": conclusions,
        "logic_graph": logic_graph,
        "open_questions": open_questions,
    }


def parse_step2_xml(xml_str: str) -> list[dict]:
    """Parse Step 2 output: per-conclusion reasoning chains.

    Returns list of dicts, each with:
        conclusion_id, conclusion_title, conclusion_content, steps[]
    Each step has: id, text, citations[], figures[]
    """
    root = ET.fromstring(_sanitize_xml(xml_str))
    chains = []

    for cr in root.findall("conclusion_reasoning"):
        conc_id = cr.get("conclusion_id", "")

        # Parse steps
        steps = []
        for step in cr.findall(".//reasoning/step"):
            step_id = step.get("id", "")

            # Extract ref blocks
            citations = []
            figures = []
            for ref in step.findall("ref"):
                ref_type = ref.get("type", "")
                ref_text = (ref.text or "").strip()
                if ref_type == "citation":
                    citations.append(ref_text)
                elif ref_type == "figure":
                    figures.append(ref_text)

            # Full text with inline refs
            text = _element_full_text(step)

            steps.append(
                {
                    "id": step_id,
                    "text": text,
                    "citations": citations,
                    "figures": figures,
                }
            )

        # Parse conclusion element
        conc_el = cr.find("conclusion")
        conc_title = conc_el.get("title", "") if conc_el is not None else ""
        conc_content = _element_full_text(conc_el) if conc_el is not None else ""

        chains.append(
            {
                "conclusion_id": conc_id,
                "conclusion_title": conc_title,
                "conclusion_content": conc_content,
                "steps": steps,
            }
        )

    return chains


def parse_step3_xml(xml_str: str) -> dict:
    """Parse Step 3 output: premises, contexts, conclusion assessments.

    Returns dict with:
        premises[]: id, conclusion_id, step_id, prior, name, title, content
        contexts[]: id, conclusion_id, step_id, name, title, content
        conclusions{id: {conditional_probability, cross_refs[]}}
    """
    root = ET.fromstring(_sanitize_xml(xml_str))

    premises = []
    for p in root.findall(".//premises/premise"):
        content = _element_full_text(p)
        # Inline citation refs into content
        for ref in p.findall("ref"):
            ref_text = (ref.text or "").strip()
            if ref_text and ref_text not in content:
                content += f" [{ref_text}]"

        premises.append(
            {
                "id": p.get("id", ""),
                "conclusion_id": p.get("conclusion_id", ""),
                "step_id": p.get("step_id", ""),
                "prior": float(p.get("prior_probability", "0.7")),
                "name": p.get("name", _slugify(p.get("title", ""))),
                "title": p.get("title", ""),
                "content": content,
            }
        )

    contexts = []
    for c in root.findall(".//contexts/context"):
        content = _element_full_text(c)
        for ref in c.findall("ref"):
            ref_text = (ref.text or "").strip()
            if ref_text and ref_text not in content:
                content += f" [{ref_text}]"

        contexts.append(
            {
                "id": c.get("id", ""),
                "conclusion_id": c.get("conclusion_id", ""),
                "step_id": c.get("step_id", ""),
                "name": c.get("name", _slugify(c.get("title", ""))),
                "title": c.get("title", ""),
                "content": content,
            }
        )

    # Conclusion assessments
    conclusions = {}
    for conc in root.findall(".//conclusions/conclusion"):
        cid = conc.get("id", "")
        cond_prob = float(conc.get("conditional_probability", "0.5"))

        # Parse cross_ref
        cross_refs = []
        xref_el = conc.find("cross_ref")
        if xref_el is not None and xref_el.text:
            # Format: [@conclusion-1], [@conclusion-2]
            cross_refs = re.findall(r"@conclusion-(\d+)", xref_el.text)

        conclusions[cid] = {
            "conditional_probability": cond_prob,
            "cross_refs": cross_refs,
        }

    return {
        "premises": premises,
        "contexts": contexts,
        "conclusions": conclusions,
    }


def _slugify(text: str) -> str:
    """Convert text to snake_case identifier (max 80 chars)."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80].strip("_")


# ── YAML Generation Layer ──────────────────────────────────────────────


def _doi_to_slug(dirname: str) -> str:
    return "paper_" + re.sub(r"[^a-zA-Z0-9]", "_", dirname).strip("_").lower()


def build_package(parsed: dict) -> dict[str, dict]:
    """Build Gaia YAML package from parsed Step 1+2+3 data.

    Args:
        parsed: dict with keys: slug, doi, step1, step2, step3

    Returns:
        dict mapping filename -> YAML content dict.
        Keys: "package.yaml", "motivation.yaml", "setting.yaml",
              "reasoning.yaml", and optionally "follow_up.yaml".
    """
    slug = parsed["slug"]
    doi = parsed["doi"]
    step1 = parsed["step1"]
    step2 = parsed["step2"]
    step3 = parsed["step3"]

    result = {}

    # ── motivation.yaml ──
    result["motivation.yaml"] = {
        "type": "setting_module",
        "name": "motivation",
        "title": f"Motivation — {doi}",
        "knowledge": [
            {
                "type": "setting",
                "name": "research_motivation",
                "content": step1["motivation"],
                "prior": 0.9,
            }
        ],
        "export": ["research_motivation"],
    }

    # ── setting.yaml ── (premises + contexts from Step 3)
    setting_knowledge = []
    for p in step3["premises"]:
        setting_knowledge.append(
            {
                "type": "setting",
                "name": p["name"],
                "content": p["content"],
                "prior": p["prior"],
                "dependency": "direct",
            }
        )
    for c in step3["contexts"]:
        setting_knowledge.append(
            {
                "type": "setting",
                "name": c["name"],
                "content": c["content"],
                "prior": 0.7,
                "dependency": "indirect",
            }
        )

    result["setting.yaml"] = {
        "type": "setting_module",
        "name": "setting",
        "title": f"Settings — {doi}",
        "knowledge": setting_knowledge,
        "export": [k["name"] for k in setting_knowledge],
    }

    # ── reasoning.yaml ──
    reasoning_knowledge = []

    # Build lookup: conclusion_id -> slug name
    conc_id_to_slug = {}
    for conc in step1["conclusions"]:
        conc_id_to_slug[conc["id"]] = _slugify(conc["title"])

    # Refs to motivation
    reasoning_knowledge.append(
        {
            "type": "ref",
            "name": "research_motivation",
            "target": "motivation.research_motivation",
        }
    )

    # Refs to settings (premises used by chains)
    setting_names_added = set()
    for p in step3["premises"]:
        if p["name"] not in setting_names_added:
            setting_names_added.add(p["name"])
            reasoning_knowledge.append(
                {
                    "type": "ref",
                    "name": p["name"],
                    "target": f"setting.{p['name']}",
                }
            )
    for c in step3["contexts"]:
        if c["name"] not in setting_names_added:
            setting_names_added.add(c["name"])
            reasoning_knowledge.append(
                {
                    "type": "ref",
                    "name": c["name"],
                    "target": f"setting.{c['name']}",
                }
            )

    # Cross-conclusion refs (from logic_graph)
    cross_ref_targets = set()
    for from_id, to_id in step1["logic_graph"]:
        upstream_slug = conc_id_to_slug.get(from_id)
        if upstream_slug:
            cross_ref_targets.add((from_id, upstream_slug))

    for _cid, cslug in sorted(cross_ref_targets):
        reasoning_knowledge.append(
            {
                "type": "ref",
                "name": cslug,
                "target": f"reasoning.{cslug}",
            }
        )

    # Claims (conclusions)
    for conc in step1["conclusions"]:
        cslug = conc_id_to_slug[conc["id"]]
        reasoning_knowledge.append(
            {
                "type": "claim",
                "name": cslug,
                "content": conc["content"],
                "prior": 0.5,
            }
        )

    # Chains (one per conclusion from Step 2)
    # Build lookup: (conclusion_id, step_id) -> premise names
    premise_lookup = {}
    for p in step3["premises"]:
        key = (p["conclusion_id"], p["step_id"])
        premise_lookup.setdefault(key, []).append(p["name"])
    for c in step3["contexts"]:
        key = (c["conclusion_id"], c["step_id"])
        premise_lookup.setdefault(key, []).append(c["name"])

    for chain in step2:
        cid = chain["conclusion_id"]
        cslug = conc_id_to_slug.get(cid, f"conclusion_{cid}")

        steps = []
        step_num = 1

        for s in chain["steps"]:
            # Check if this step has associated premises from Step 3
            prem_names = premise_lookup.get((cid, s["id"]), [])

            # Add ref steps for premises
            for pname in prem_names:
                steps.append({"step": step_num, "ref": pname})
                step_num += 1

            # Build refs list for this lambda step
            refs_list = [f"setting.{pn}" for pn in prem_names]

            step_dict = {
                "step": step_num,
                "lambda": s["text"],
                "prior": 0.7,
            }
            if refs_list:
                step_dict["refs"] = refs_list
            steps.append(step_dict)
            step_num += 1

        # Final ref to conclusion
        steps.append({"step": step_num, "ref": cslug})

        reasoning_knowledge.append(
            {
                "type": "chain_expr",
                "name": f"chain_{cslug}",
                "edge_type": "deduction",
                "steps": steps,
            }
        )

    result["reasoning.yaml"] = {
        "type": "reasoning_module",
        "name": "reasoning",
        "title": f"Reasoning — {doi}",
        "knowledge": reasoning_knowledge,
        "export": list(conc_id_to_slug.values()),
    }

    # ── follow_up.yaml ── (only if open questions exist)
    if step1["open_questions"].strip():
        result["follow_up.yaml"] = {
            "type": "setting_module",
            "name": "follow_up",
            "title": f"Open Questions — {doi}",
            "knowledge": [
                {
                    "type": "question",
                    "name": "open_questions",
                    "content": step1["open_questions"],
                    "prior": 0.5,
                }
            ],
            "export": ["open_questions"],
        }

    # ── package.yaml ──
    modules = ["motivation", "setting", "reasoning"]
    if "follow_up.yaml" in result:
        modules.append("follow_up")

    result["package.yaml"] = {
        "name": slug,
        "version": "1.0.0",
        "manifest": {
            "description": f"Formalized from paper {doi}",
            "authors": [],
            "license": "CC-BY-4.0",
        },
        "modules": modules,
        "export": list(conc_id_to_slug.values()),
    }

    return result


def write_package(data: dict[str, dict], output_dir: Path) -> Path:
    """Write YAML package files to output directory."""
    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in data.items():
        (output_dir / filename).write_text(
            yaml.dump(content, allow_unicode=True, sort_keys=False, width=120)
        )
    return output_dir


# ── Skip-LLM Mode: Read existing XML fixtures ─────────────────────────


def _find_paper_md(paper_dir: Path) -> Path | None:
    """Find the paper markdown file in a directory."""
    for f in paper_dir.glob("*.md"):
        if f.name != "metadata.md":
            return f
    return None


def _read_existing_xmls(paper_dir: Path) -> dict[str, str | None] | None:
    """Read existing XML files for --skip-llm mode.

    Returns dict with step1_xml, step2_xml, step3_xml or None if missing.
    """
    # Step 1: select_conclusion.xml
    step1_file = paper_dir / "select_conclusion.xml"
    if not step1_file.exists():
        print(f"  SKIP: no select_conclusion.xml in {paper_dir}")
        return None

    # Step 2: reasoning chain XML
    # Try single file first (from our pipeline), then per-conclusion files (old format)
    single_chain = paper_dir / "reasoning_chain.xml"
    if single_chain.exists():
        step2_xml = single_chain.read_text()
    else:
        chain_files = sorted(paper_dir.glob("conclusion_*_reasoning_chain.xml"))
        chain_files = [f for f in chain_files if "combine" not in f.name and "refine" not in f.name]
        if not chain_files:
            print(f"  SKIP: no reasoning chain XMLs in {paper_dir}")
            return None

        # Each reasoning chain file is a standalone inference_unit;
        # merge all conclusion_reasoning blocks into one
        step2_parts = []
        for f in chain_files:
            content = f.read_text()
            match = re.search(r"<inference_unit>(.*?)</inference_unit>", content, re.DOTALL)
            if match:
                step2_parts.append(match.group(1))
            else:
                step2_parts.append(content)

        step2_xml = f"<inference_unit>{''.join(step2_parts)}</inference_unit>"

    # Step 3: review XML — may not exist in fixtures
    # Look for review_*.xml or step3_*.xml
    step3_file = None
    for pattern in ["review*.xml", "step3*.xml"]:
        matches = list(paper_dir.glob(pattern))
        if matches:
            step3_file = matches[0]
            break

    step3_xml = step3_file.read_text() if step3_file else None

    return {
        "step1_xml": step1_file.read_text(),
        "step2_xml": step2_xml,
        "step3_xml": step3_xml,
    }


def _synthesize_step3(step1_data: dict, step2_data: list[dict]) -> dict:
    """Create synthetic Step 3 data when no review XML exists.

    Uses default priors. Without Step 3, we have no fine-grained
    premise/context classification — YAML will have conclusions only.
    """
    return {
        "premises": [],
        "contexts": [],
        "conclusions": {
            conc["id"]: {"conditional_probability": 0.5, "cross_refs": []}
            for conc in step1_data["conclusions"]
        },
    }


# ── Main Pipeline ──────────────────────────────────────────────────────


async def process_paper(
    paper_dir: Path,
    output_dir: Path,
    client: AsyncOpenAI | None = None,
    model: str = "azure/gpt-5-mini",
    skip_llm: bool = False,
) -> Path | None:
    """Process a single paper directory into a YAML package."""
    slug = _doi_to_slug(paper_dir.name)
    doi = paper_dir.name

    if skip_llm:
        # Read existing XMLs
        xmls = _read_existing_xmls(paper_dir)
        if xmls is None:
            return None
        step1_xml = xmls["step1_xml"]
        step2_xml = xmls["step2_xml"]
        step3_xml = xmls["step3_xml"]
    else:
        # Run LLM pipeline
        paper_md_path = _find_paper_md(paper_dir)
        if paper_md_path is None:
            print(f"  SKIP: no paper markdown in {paper_dir}")
            return None
        paper_md = paper_md_path.read_text()

        assert client is not None, "LLM client required when not using --skip-llm"
        step1_xml = await run_step1(client, paper_md, model)
        step2_xml = await run_step2(client, paper_md, step1_xml, model)
        step3_xml = await run_step3(client, paper_md, step2_xml, model)

        # Save intermediate XMLs alongside the paper markdown
        (paper_dir / "select_conclusion.xml").write_text(step1_xml)
        (paper_dir / "reasoning_chain.xml").write_text(step2_xml)
        (paper_dir / "review.xml").write_text(step3_xml)
        print(f"  Saved intermediate XMLs to {paper_dir}")

    # Parse XMLs
    step1_data = parse_step1_xml(step1_xml)
    if step1_data is None:
        print("  SKIP: paper passed (review/survey)")
        return None

    step2_data = parse_step2_xml(step2_xml)

    if step3_xml:
        step3_data = parse_step3_xml(step3_xml)
    else:
        step3_data = _synthesize_step3(step1_data, step2_data)

    # Build YAML
    parsed = {
        "slug": slug,
        "doi": doi,
        "step1": step1_data,
        "step2": step2_data,
        "step3": step3_data,
    }

    yaml_data = build_package(parsed)
    pkg_dir = write_package(yaml_data, output_dir / slug)

    n_settings = len(yaml_data.get("setting.yaml", {}).get("knowledge", []))
    n_chains = sum(
        1
        for k in yaml_data.get("reasoning.yaml", {}).get("knowledge", [])
        if k.get("type") == "chain_expr"
    )
    n_conclusions = len(step1_data["conclusions"])
    print(f"  OK -> {slug}: {n_conclusions} conclusions, {n_settings} settings, {n_chains} chains")
    return pkg_dir


async def main():
    from dotenv import load_dotenv

    load_dotenv()

    parser = argparse.ArgumentParser(description="Convert paper to Gaia YAML package")
    parser.add_argument(
        "paper_dirs", type=Path, nargs="+", help="Paper directories with .md and/or .xml files"
    )
    parser.add_argument(
        "-o",
        "--output-dir",
        type=Path,
        default=Path("output"),
        help="Output directory (default: output/)",
    )
    parser.add_argument(
        "--skip-llm", action="store_true", help="Skip LLM calls, use existing XML files"
    )
    parser.add_argument("--model", default="azure/gpt-5-mini", help="LLM model name")
    parser.add_argument("--base-url", help="LLM API base URL")
    parser.add_argument("--api-key", help="LLM API key")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=3,
        help="Max concurrent papers to process (default: 3)",
    )
    args = parser.parse_args()

    # Expand directories: if a dir contains subdirs with .md/.xml, treat each subdir as a paper
    paper_dirs = []
    for p in args.paper_dirs:
        if not p.exists():
            print(f"Warning: directory not found: {p}")
            continue
        # Check if this is a parent dir containing paper subdirs
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
                    client=client,
                    model=args.model,
                    skip_llm=args.skip_llm,
                )
            except Exception as e:
                print(f"  ERROR {paper_dir.name}: {e}")
                return None

    results = await asyncio.gather(*[process_with_limit(d) for d in paper_dirs])

    succeeded = [r for r in results if r is not None]
    print(f"\nDone: {len(succeeded)}/{len(paper_dirs)} papers processed.")


if __name__ == "__main__":
    asyncio.run(main())
