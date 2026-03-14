#!/usr/bin/env python3
"""Convert paper XML fixtures to Gaia Language YAML packages.

Converts tests/fixtures/papers/ → tests/fixtures/gaia_language_packages/<slug>/

Usage:
    python scripts/xml_to_yaml.py                                  # convert all papers
    python scripts/xml_to_yaml.py 10.1038332139a0_1988_Natu        # single paper
"""

from __future__ import annotations

import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

PAPERS_DIR = Path("tests/fixtures/papers")
OUTPUT_DIR = Path("tests/fixtures/gaia_language_packages")


def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80].strip("_")


def _doi_to_slug(dirname: str) -> str:
    return "paper_" + re.sub(r"[^a-zA-Z0-9]", "_", dirname).strip("_").lower()


def _parse_combine_xml(path: Path) -> dict:
    """Parse a conclusion_*_reasoning_chain_combine.xml file."""
    tree = ET.parse(path)
    root = tree.getroot()

    premises = []
    for tag in ("premise", "assumption"):
        for el in root.findall(f".//{tag}"):
            text = "".join(el.itertext()).strip()
            for ref in el.findall("ref"):
                ref_text = ref.text or ""
                text = text.replace(ref_text, "").strip()
            premises.append(
                {
                    "id": el.get("id"),
                    "title": el.get("title", ""),
                    "content": text,
                }
            )

    steps = []
    for s in root.findall(".//reasoning/step"):
        text = "".join(s.itertext()).strip()
        refs = re.findall(r"@premise-(\d+)", text)
        steps.append(
            {
                "title": s.get("title", ""),
                "text": text,
                "premise_refs": refs,
            }
        )

    conclusion_el = root.find(".//conclusion")
    conclusion = {
        "title": conclusion_el.get("title", "") if conclusion_el is not None else "",
        "content": "".join(conclusion_el.itertext()).strip() if conclusion_el is not None else "",
    }
    return {"premises": premises, "reasoning_steps": steps, "conclusion": conclusion}


def convert_paper(paper_dir: Path) -> dict | None:
    """Convert a paper directory to Gaia Language YAML package data.

    Returns dict with keys: slug, package_yaml, setting_yaml, reasoning_yaml.
    Returns None if no combine XMLs found.
    """
    slug = _doi_to_slug(paper_dir.name)

    combine_files = sorted(paper_dir.glob("conclusion_*_reasoning_chain_combine.xml"))
    if not combine_files:
        return None

    # Collect all premises across chains (deduplicated by title)
    all_premises: dict[str, dict] = {}  # title → {name, content}
    chain_data: list[dict] = []

    for i, f in enumerate(combine_files, 1):
        parsed = _parse_combine_xml(f)
        local_id_to_name: dict[str, str] = {}

        for p in parsed["premises"]:
            title = p["title"]
            if title not in all_premises:
                name = _slugify(title)
                all_premises[title] = {"name": name, "content": p["content"]}
            local_id_to_name[p["id"]] = all_premises[title]["name"]

        chain_data.append(
            {
                "index": i,
                "parsed": parsed,
                "local_to_name": local_id_to_name,
            }
        )

    # Build setting module knowledge (deduplicated premises)
    setting_knowledge = []
    for title, info in all_premises.items():
        setting_knowledge.append(
            {
                "type": "setting",
                "name": info["name"],
                "content": info["content"],
                "prior": 0.7,
            }
        )

    setting_yaml = {
        "type": "setting_module",
        "name": "setting",
        "title": f"Settings — {paper_dir.name}",
        "knowledge": setting_knowledge,
        "export": [info["name"] for info in all_premises.values()],
    }

    # Build reasoning module knowledge (chains with conclusions)
    reasoning_knowledge: list[dict] = []

    # Add refs to setting premises
    premise_names_used: set[str] = set()
    for cd in chain_data:
        for p in cd["parsed"]["premises"]:
            name = cd["local_to_name"].get(p["id"])
            if name and name not in premise_names_used:
                premise_names_used.add(name)
                reasoning_knowledge.append(
                    {
                        "type": "ref",
                        "name": name,
                        "target": f"setting.{name}",
                    }
                )

    # Add conclusions (deduplicated)
    seen_conclusions: dict[str, str] = {}  # title → name
    for cd in chain_data:
        conc_title = cd["parsed"]["conclusion"]["title"]
        if conc_title not in seen_conclusions:
            conc_name = _slugify(conc_title)
            seen_conclusions[conc_title] = conc_name
            reasoning_knowledge.append(
                {
                    "type": "claim",
                    "name": conc_name,
                    "content": cd["parsed"]["conclusion"]["content"],
                    "prior": 0.5,
                }
            )

    # Add chains
    for cd in chain_data:
        parsed = cd["parsed"]
        conc_name = seen_conclusions[parsed["conclusion"]["title"]]
        chain_name = f"chain_{cd['index']}"

        steps: list[dict] = []
        step_num = 1

        for si, step in enumerate(parsed["reasoning_steps"]):
            # Find premise refs for this step
            premise_refs = []
            for ref_id in step["premise_refs"]:
                name = cd["local_to_name"].get(ref_id)
                if name:
                    premise_refs.append(name)

            if premise_refs:
                # Add ref to first premise as entry point
                steps.append({"step": step_num, "ref": premise_refs[0]})
                step_num += 1

            # Add lambda step with reasoning text
            steps.append(
                {
                    "step": step_num,
                    "lambda": step["text"],
                    "prior": 0.7,
                }
            )
            step_num += 1

        # Final ref to conclusion
        steps.append({"step": step_num, "ref": conc_name})

        reasoning_knowledge.append(
            {
                "type": "chain_expr",
                "name": chain_name,
                "edge_type": "deduction",
                "steps": steps,
            }
        )

    reasoning_yaml = {
        "type": "reasoning_module",
        "name": "reasoning",
        "title": f"Reasoning — {paper_dir.name}",
        "knowledge": reasoning_knowledge,
        "export": list(seen_conclusions.values()),
    }

    # Build package.yaml
    package_yaml = {
        "name": slug,
        "version": "1.0.0",
        "manifest": {
            "description": f"Reasoning chains extracted from paper {paper_dir.name}",
            "authors": [],
            "license": "CC-BY-4.0",
        },
        "modules": ["setting", "reasoning"],
        "export": list(seen_conclusions.values()),
    }

    return {
        "slug": slug,
        "package_yaml": package_yaml,
        "setting_yaml": setting_yaml,
        "reasoning_yaml": reasoning_yaml,
    }


def write_package(data: dict, output_dir: Path) -> Path:
    """Write converted package data to YAML files."""
    pkg_dir = output_dir / data["slug"]
    pkg_dir.mkdir(parents=True, exist_ok=True)

    for filename, content in [
        ("package.yaml", data["package_yaml"]),
        ("setting.yaml", data["setting_yaml"]),
        ("reasoning.yaml", data["reasoning_yaml"]),
    ]:
        (pkg_dir / filename).write_text(
            yaml.dump(content, allow_unicode=True, sort_keys=False, width=120)
        )

    return pkg_dir


def main():
    filter_name = sys.argv[1] if len(sys.argv) > 1 else None

    if not PAPERS_DIR.exists():
        print(f"Error: papers directory not found: {PAPERS_DIR}")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    converted = 0
    for paper_dir in sorted(PAPERS_DIR.iterdir()):
        if not paper_dir.is_dir() or paper_dir.name == "images":
            continue
        if filter_name and filter_name not in paper_dir.name:
            continue

        data = convert_paper(paper_dir)
        if data is None:
            print(f"  SKIP {paper_dir.name}: no combine XMLs found")
            continue

        pkg_dir = write_package(data, OUTPUT_DIR)
        n_settings = len(data["setting_yaml"]["knowledge"])
        n_chains = sum(
            1 for k in data["reasoning_yaml"]["knowledge"] if k.get("type") == "chain_expr"
        )
        print(f"  OK {paper_dir.name} → {pkg_dir.name}: {n_settings} settings, {n_chains} chains")
        converted += 1

    print(f"\nConverted {converted} papers to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
