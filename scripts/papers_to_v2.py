#!/usr/bin/env python3
"""Convert paper XML reasoning chains to v2 storage fixture JSON.

Usage:
    python scripts/papers_to_v2.py

Reads from: tests/fixtures/papers/*/conclusion_*_reasoning_chain_combine.xml
Writes to:  tests/fixtures/storage_v2/papers/<doi_slug>/{package,modules,knowledge,chains,probabilities,beliefs}.json
"""

import json
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path

PAPERS_DIR = Path("tests/fixtures/papers")
OUTPUT_DIR = Path("tests/fixtures/storage_v2/papers")

NOW = datetime(2026, 3, 12, tzinfo=timezone.utc).isoformat()


def doi_to_slug(dirname: str) -> str:
    """Convert DOI directory name to a safe package_id slug."""
    return "paper_" + re.sub(r"[^a-zA-Z0-9]", "_", dirname).strip("_").lower()


def _slugify(text: str) -> str:
    """Convert a title to a URL-safe slug."""
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "_", text)
    return text[:80].strip("_")


def parse_combine_xml(path: Path) -> dict:
    """Parse a conclusion_N_reasoning_chain_combine.xml file.

    Returns dict with keys: premises (list), reasoning_steps (list), conclusion (dict).
    """
    tree = ET.parse(path)
    root = tree.getroot()

    premises = []
    for p in root.findall(".//premise"):
        text = "".join(p.itertext()).strip()
        # Remove <ref> content from the text
        for ref in p.findall("ref"):
            ref_text = ref.text or ""
            text = text.replace(ref_text, "").strip()
        premises.append(
            {
                "id": p.get("id"),
                "title": p.get("title", ""),
                "content": text,
            }
        )

    # Also handle <assumption> tags (same structure as premise)
    for a in root.findall(".//assumption"):
        text = "".join(a.itertext()).strip()
        for ref in a.findall("ref"):
            ref_text = ref.text or ""
            text = text.replace(ref_text, "").strip()
        premises.append(
            {
                "id": a.get("id"),
                "title": a.get("title", ""),
                "content": text,
            }
        )

    steps = []
    for s in root.findall(".//reasoning/step"):
        text = "".join(s.itertext()).strip()
        # Extract @premise-N references
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
    """Convert one paper directory to v2 fixture data.

    Returns dict with keys: package, modules, knowledge, chains, probabilities, beliefs.
    """
    slug = doi_to_slug(paper_dir.name)
    module_id = f"{slug}.reasoning"

    # Collect all combine XMLs
    combine_files = sorted(paper_dir.glob("conclusion_*_reasoning_chain_combine.xml"))
    if not combine_files:
        return None

    # Parse all chains, dedup premises by title
    all_premises: dict[str, dict] = {}  # title -> premise data
    chain_data: list[dict] = []

    for i, f in enumerate(combine_files, 1):
        parsed = parse_combine_xml(f)
        # Dedup premises by title
        local_id_to_global: dict[str, str] = {}
        for p in parsed["premises"]:
            title = p["title"]
            if title not in all_premises:
                kid = f"{slug}/{_slugify(title)}"
                all_premises[title] = {**p, "knowledge_id": kid}
            local_id_to_global[p["id"]] = all_premises[title]["knowledge_id"]
        chain_data.append(
            {
                "index": i,
                "parsed": parsed,
                "local_to_global": local_id_to_global,
            }
        )

    # Build Knowledge items (premises + conclusions)
    knowledge_items = []
    for _title, p in all_premises.items():
        knowledge_items.append(
            {
                "knowledge_id": p["knowledge_id"],
                "version": 1,
                "type": "claim",
                "content": p["content"],
                "prior": 0.7,
                "keywords": [],
                "source_package_id": slug,
                "source_package_version": "1.0.0",
                "source_module_id": module_id,
                "created_at": NOW,
                "embedding": None,
            }
        )

    # Add conclusion knowledge items + build chains
    chains = []
    for cd in chain_data:
        parsed = cd["parsed"]
        local_to_global = cd["local_to_global"]
        conc_title = parsed["conclusion"]["title"]
        conc_kid = f"{slug}/{_slugify(conc_title)}"

        # Add conclusion as knowledge (dedup)
        if not any(k["knowledge_id"] == conc_kid for k in knowledge_items):
            knowledge_items.append(
                {
                    "knowledge_id": conc_kid,
                    "version": 1,
                    "type": "claim",
                    "content": parsed["conclusion"]["content"],
                    "prior": 0.5,
                    "keywords": [],
                    "source_package_id": slug,
                    "source_package_version": "1.0.0",
                    "source_module_id": module_id,
                    "created_at": NOW,
                    "embedding": None,
                }
            )

        # Build chain steps
        chain_id = f"{slug}.reasoning.chain_{cd['index']}"
        steps = []
        for si, step in enumerate(parsed["reasoning_steps"]):
            premise_refs = []
            for ref_id in step["premise_refs"]:
                if ref_id in local_to_global:
                    premise_refs.append(
                        {
                            "knowledge_id": local_to_global[ref_id],
                            "version": 1,
                        }
                    )
            steps.append(
                {
                    "step_index": si,
                    "premises": premise_refs,
                    "reasoning": step["text"],
                    "conclusion": {"knowledge_id": conc_kid, "version": 1},
                }
            )

        if steps:
            chains.append(
                {
                    "chain_id": chain_id,
                    "module_id": module_id,
                    "package_id": slug,
                    "package_version": "1.0.0",
                    "type": "deduction",
                    "steps": steps,
                }
            )

    # Build module
    modules = [
        {
            "module_id": module_id,
            "package_id": slug,
            "package_version": "1.0.0",
            "name": "reasoning",
            "role": "reasoning",
            "imports": [],
            "chain_ids": [c["chain_id"] for c in chains],
            "export_ids": [k["knowledge_id"] for k in knowledge_items if k["prior"] == 0.5],
        }
    ]

    # Build package
    package = {
        "package_id": slug,
        "name": slug,
        "version": "1.0.0",
        "description": f"Reasoning chains extracted from paper {paper_dir.name}",
        "modules": [module_id],
        "exports": modules[0]["export_ids"],
        "submitter": "paper_extractor",
        "submitted_at": NOW,
        "status": "merged",
    }

    # Mock probabilities (0.7 for each step)
    probabilities = []
    for chain in chains:
        for step in chain["steps"]:
            probabilities.append(
                {
                    "chain_id": chain["chain_id"],
                    "step_index": step["step_index"],
                    "value": 0.7,
                    "source": "author",
                    "source_detail": None,
                    "recorded_at": NOW,
                }
            )

    # Mock beliefs (belief = prior for each knowledge item)
    beliefs = []
    for k in knowledge_items:
        beliefs.append(
            {
                "knowledge_id": k["knowledge_id"],
                "version": 1,
                "belief": k["prior"],
                "bp_run_id": "mock_bp_run",
                "computed_at": NOW,
            }
        )

    return {
        "package": package,
        "modules": modules,
        "knowledge": knowledge_items,
        "chains": chains,
        "probabilities": probabilities,
        "beliefs": beliefs,
    }


def validate_fixtures():
    """Validate all generated fixtures load as v2 Pydantic models."""
    from libs.storage_v2.models import (
        BeliefSnapshot,
        Chain,
        Knowledge,
        Module,
        Package,
        ProbabilityRecord,
    )

    for paper_dir in sorted(OUTPUT_DIR.iterdir()):
        if not paper_dir.is_dir():
            continue
        pkg = Package.model_validate_json((paper_dir / "package.json").read_text())
        mods = [
            Module.model_validate(m) for m in json.loads((paper_dir / "modules.json").read_text())
        ]
        knowledge = [
            Knowledge.model_validate(k)
            for k in json.loads((paper_dir / "knowledge.json").read_text())
        ]
        chains = [
            Chain.model_validate(c) for c in json.loads((paper_dir / "chains.json").read_text())
        ]
        probs = [
            ProbabilityRecord.model_validate(p)
            for p in json.loads((paper_dir / "probabilities.json").read_text())
        ]
        beliefs = [
            BeliefSnapshot.model_validate(b)
            for b in json.loads((paper_dir / "beliefs.json").read_text())
        ]
        print(
            f"  Validated {paper_dir.name}: {pkg.package_id} "
            f"({len(mods)} modules, {len(knowledge)} knowledge, "
            f"{len(chains)} chains, {len(probs)} probs, {len(beliefs)} beliefs)"
        )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    papers = sorted(PAPERS_DIR.iterdir())
    for paper_dir in papers:
        if not paper_dir.is_dir() or paper_dir.name == "images":
            continue
        result = convert_paper(paper_dir)
        if result is None:
            print(f"SKIP {paper_dir.name}: no combine XMLs found")
            continue

        out_dir = OUTPUT_DIR / doi_to_slug(paper_dir.name)
        out_dir.mkdir(parents=True, exist_ok=True)

        for key, data in result.items():
            path = out_dir / f"{key}.json"
            path.write_text(json.dumps(data, ensure_ascii=False, indent=2))

        n_k = len(result["knowledge"])
        n_c = len(result["chains"])
        print(f"OK {paper_dir.name} -> {out_dir.name}: {n_k} knowledge, {n_c} chains")

    print("\nValidating fixtures...")
    validate_fixtures()


if __name__ == "__main__":
    main()
