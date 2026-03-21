#!/usr/bin/env python3
"""Convert raw data sources to v2 storage fixture JSON.

Supported sources:
  paper   — Convert XML reasoning chains via Gaia Language pipeline
              (xml_to_yaml → build → review → infer → convert_to_storage)
  lancedb — Convert sampled remote LanceDB JSON from tests/fixtures/remote_lancedb/

Usage:
    python scripts/ingest.py paper
    python scripts/ingest.py lancedb
"""

from __future__ import annotations

import json
import sys
from abc import ABC, abstractmethod
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.storage.models import (
    BeliefSnapshot,
    Chain,
    Knowledge,
    Module,
    Package,
    ProbabilityRecord,
    factors_from_chains,
)

NOW = datetime(2026, 3, 12, tzinfo=timezone.utc).isoformat()

# ── Shared data container ──


class V2PackageData:
    """Intermediate container holding all v2 entities for one package."""

    def __init__(
        self,
        package: dict,
        modules: list[dict],
        knowledge: list[dict],
        chains: list[dict],
        probabilities: list[dict],
        beliefs: list[dict],
        embeddings: list[dict] | None = None,
    ):
        self.package = package
        self.modules = modules
        self.knowledge = knowledge
        self.chains = chains
        self.probabilities = probabilities
        self.beliefs = beliefs
        self.embeddings = embeddings or []


# ── Source ABC ──


class Source(ABC):
    """Base class for data sources that produce v2 fixture data."""

    @abstractmethod
    def convert(self) -> list[V2PackageData]:
        """Parse the source and return a list of V2PackageData (one per package)."""
        ...


# ── Paper XML Source — uses full Gaia Language pipeline ──


class PaperXMLSource(Source):
    """Convert XML reasoning chains via xml_to_yaml + pipeline_build/review/infer."""

    PAPERS_DIR = Path("tests/fixtures/inputs/papers_xml")

    def convert(self) -> list[V2PackageData]:
        raise NotImplementedError(
            "PaperXMLSource requires the YAML pipeline which has been removed. "
            "Use Typst packages with `pipeline_build` / `pipeline_publish` instead."
        )


# ── Remote LanceDB Source ──


class RemoteLanceDBSource(Source):
    """Convert sampled remote LanceDB JSON fixtures to v2 format."""

    SRC_DIR = Path("tests/fixtures/remote_lancedb")

    @staticmethod
    def _slugify(s: str) -> str:
        return s.lower().replace(" ", "_").replace("–", "_").replace("'", "").replace(",", "")

    def _load(self, name: str) -> list[dict]:
        with open(self.SRC_DIR / f"{name}.json") as f:
            return json.load(f)

    def convert(self) -> list[V2PackageData]:
        nodes_raw = self._load("nodes")
        edges_raw = self._load("edges")
        embeddings_raw: dict[str, list[float]] = json.loads(
            (self.SRC_DIR / "embeddings.json").read_text()
        )

        nodes_by_id = {n["id"]: n for n in nodes_raw}

        # Group edges by topic
        edges_by_topic: dict[str, list[dict]] = defaultdict(list)
        for e in edges_raw:
            loc = e["metadata"].get("location", "")
            parts = loc.split("/")
            topic = "/".join(parts[:2]) if len(parts) >= 2 else loc
            edges_by_topic[topic].append(e)

        node_to_kid: dict[int, str] = {}
        used_kids: set[str] = set()
        results = []

        for topic, topic_edges in edges_by_topic.items():
            topic_slug = self._slugify(topic.split("/")[-1])
            pkg_id = topic_slug

            premise_ids = set()
            conclusion_ids = set()
            for e in topic_edges:
                premise_ids.update(e["initial_reasoning"]["tail"])
                conclusion_ids.update(e["initial_reasoning"]["head"])
            all_node_ids = premise_ids | conclusion_ids

            # Group edges by location → module
            edges_by_loc: dict[str, list[dict]] = defaultdict(list)
            for e in topic_edges:
                loc = e["metadata"].get("location", "unknown")
                edges_by_loc[loc].append(e)

            module_names = {}
            for loc in sorted(edges_by_loc.keys()):
                loc_id = loc.split("/")[-1] if "/" in loc else loc
                module_names[loc] = f"problem_{loc_id}"

            # Knowledge items
            knowledge_items = []
            embeddings = []
            for nid in sorted(all_node_ids):
                node = nodes_by_id.get(nid)
                if not node or nid in node_to_kid:
                    continue

                node_type = node["metadata"].get("node_type", "premise")
                node_loc = node["metadata"].get("location", "unknown")
                mod_name = module_names.get(node_loc, list(module_names.values())[0])

                slug = self._slugify(node["title"])[:60].rstrip("_")
                kid = f"{pkg_id}.{mod_name}.{slug}"
                base_kid = kid
                counter = 1
                while kid in used_kids:
                    kid = f"{base_kid}_{counter}"
                    counter += 1
                used_kids.add(kid)
                node_to_kid[nid] = kid

                k_type = "claim" if node_type == "conclusion" else "setting"
                knowledge_items.append(
                    {
                        "knowledge_id": kid,
                        "version": 1,
                        "type": k_type,
                        "content": node["content"],
                        "prior": 1.0 if k_type == "setting" else 0.5,
                        "keywords": node.get("keywords", []),
                        "source_package_id": pkg_id,
                        "source_package_version": "1.0.0",
                        "source_module_id": f"{pkg_id}.{mod_name}",
                        "created_at": NOW,
                        "embedding": None,
                    }
                )

                vec = embeddings_raw.get(str(nid))
                if vec:
                    embeddings.append({"knowledge_id": kid, "version": 1, "embedding": vec})

            # Chains
            chains = []
            chain_ids_by_module: dict[str, list[str]] = defaultdict(list)
            export_ids_by_module: dict[str, list[str]] = defaultdict(list)

            for e in topic_edges:
                loc = e["metadata"].get("location", "unknown")
                mod_name = module_names.get(loc, "unknown")
                chain_id = f"{pkg_id}.{mod_name}.chain_{e['id']}"

                tail_ids = e["initial_reasoning"]["tail"]
                head_ids = e["initial_reasoning"]["head"]

                reasoning_steps = e.get("reasoning", [])
                reasoning_text = (
                    "\n\n".join(
                        f"**{rs['title']}**: {rs['content']}"
                        if rs.get("title")
                        else rs.get("content", "")
                        for rs in reasoning_steps
                    )
                    if reasoning_steps
                    else ""
                )

                premises = [
                    {"knowledge_id": node_to_kid[nid], "version": 1}
                    for nid in tail_ids
                    if nid in node_to_kid
                ]
                conclusion_nid = head_ids[0] if head_ids else None
                if not conclusion_nid or conclusion_nid not in node_to_kid:
                    continue

                chains.append(
                    {
                        "chain_id": chain_id,
                        "module_id": f"{pkg_id}.{mod_name}",
                        "package_id": pkg_id,
                        "package_version": "1.0.0",
                        "type": "deduction",
                        "steps": [
                            {
                                "step_index": 0,
                                "premises": premises,
                                "reasoning": reasoning_text,
                                "conclusion": {
                                    "knowledge_id": node_to_kid[conclusion_nid],
                                    "version": 1,
                                },
                            }
                        ],
                    }
                )
                chain_ids_by_module[mod_name].append(chain_id)
                for hid in head_ids:
                    if hid in node_to_kid:
                        export_ids_by_module[mod_name].append(node_to_kid[hid])

            # Modules
            modules = []
            for loc, mod_name in module_names.items():
                module_id = f"{pkg_id}.{mod_name}"
                mod_node_ids = set()
                for e in edges_by_loc[loc]:
                    mod_node_ids.update(e["initial_reasoning"]["tail"])
                    mod_node_ids.update(e["initial_reasoning"]["head"])

                mod_imports = [
                    {"knowledge_id": node_to_kid[nid], "version": 1, "strength": "strong"}
                    for nid in sorted(mod_node_ids)
                    if nid in node_to_kid and nid in premise_ids
                ]
                modules.append(
                    {
                        "module_id": module_id,
                        "package_id": pkg_id,
                        "package_version": "1.0.0",
                        "name": mod_name,
                        "role": "reasoning",
                        "imports": mod_imports,
                        "chain_ids": chain_ids_by_module.get(mod_name, []),
                        "export_ids": list(set(export_ids_by_module.get(mod_name, []))),
                    }
                )

            all_exports = [kid for ids in export_ids_by_module.values() for kid in ids]
            package = {
                "package_id": pkg_id,
                "name": topic_slug,
                "version": "1.0.0",
                "description": f"Knowledge package for {topic.replace('_', ' ')}",
                "modules": [f"{pkg_id}.{mn}" for mn in module_names.values()],
                "exports": list(set(all_exports)),
                "submitter": "propositional_logic_pipeline",
                "submitted_at": NOW,
                "status": "merged",
            }

            probabilities = [
                {
                    "chain_id": c["chain_id"],
                    "step_index": 0,
                    "value": 0.9,
                    "source": "author",
                    "source_detail": None,
                    "recorded_at": NOW,
                }
                for c in chains
            ]

            beliefs = [
                {
                    "knowledge_id": k["knowledge_id"],
                    "version": 1,
                    "belief": k["prior"],
                    "bp_run_id": "mock_bp_run",
                    "computed_at": NOW,
                }
                for k in knowledge_items
            ]

            print(f"  OK {topic}: {len(knowledge_items)} knowledge, {len(chains)} chains")
            results.append(
                V2PackageData(
                    package=package,
                    modules=modules,
                    knowledge=knowledge_items,
                    chains=chains,
                    probabilities=probabilities,
                    beliefs=beliefs,
                    embeddings=embeddings,
                )
            )

        return results


# ── Output ──

OUTPUT_DIRS = {
    "paper": Path("tests/fixtures/storage/papers"),
    "lancedb": Path("tests/fixtures/remote_lancedb/v2"),
}


def save_package(pkg_data: V2PackageData, out_dir: Path) -> None:
    """Save one package's v2 data to a directory."""
    pkg_dir = out_dir / pkg_data.package["package_id"]
    pkg_dir.mkdir(parents=True, exist_ok=True)

    (pkg_dir / "package.json").write_text(
        json.dumps(pkg_data.package, indent=2, ensure_ascii=False)
    )
    for name, data in [
        ("modules", pkg_data.modules),
        ("knowledge", pkg_data.knowledge),
        ("chains", pkg_data.chains),
        ("probabilities", pkg_data.probabilities),
        ("beliefs", pkg_data.beliefs),
    ]:
        (pkg_dir / f"{name}.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if pkg_data.embeddings:
        (pkg_dir / "embeddings.json").write_text(
            json.dumps(pkg_data.embeddings, ensure_ascii=False)
        )

    # Derive and save factors from chains
    chain_models = [Chain.model_validate(c) for c in pkg_data.chains]
    factors = factors_from_chains(chain_models, pkg_data.package["package_id"])
    if factors:
        (pkg_dir / "factors.json").write_text(
            json.dumps([f.model_dump() for f in factors], indent=2, ensure_ascii=False)
        )


def validate_package(pkg_dir: Path) -> None:
    """Validate a package directory against v2 Pydantic models."""
    from libs.storage.models import FactorNode

    pkg = Package.model_validate_json((pkg_dir / "package.json").read_text())
    mods = [Module.model_validate(m) for m in json.loads((pkg_dir / "modules.json").read_text())]
    knowledge = [
        Knowledge.model_validate(k) for k in json.loads((pkg_dir / "knowledge.json").read_text())
    ]
    chains = [Chain.model_validate(c) for c in json.loads((pkg_dir / "chains.json").read_text())]
    probs = [
        ProbabilityRecord.model_validate(p)
        for p in json.loads((pkg_dir / "probabilities.json").read_text())
    ]
    beliefs = [
        BeliefSnapshot.model_validate(b) for b in json.loads((pkg_dir / "beliefs.json").read_text())
    ]
    factors_path = pkg_dir / "factors.json"
    factors = (
        [FactorNode.model_validate(f) for f in json.loads(factors_path.read_text())]
        if factors_path.exists()
        else []
    )
    print(
        f"  ✓ {pkg_dir.name}: {pkg.package_id} "
        f"({len(mods)} modules, {len(knowledge)} knowledge, "
        f"{len(chains)} chains, {len(factors)} factors, "
        f"{len(probs)} probs, {len(beliefs)} beliefs)"
    )


# ── CLI ──

SOURCES: dict[str, type[Source]] = {
    "paper": PaperXMLSource,
    "lancedb": RemoteLanceDBSource,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in SOURCES:
        print(f"Usage: {sys.argv[0]} <{'|'.join(SOURCES.keys())}>")
        sys.exit(1)

    source_name = sys.argv[1]
    source = SOURCES[source_name]()
    out_dir = OUTPUT_DIRS[source_name]

    print(f"Converting source: {source_name}")
    packages = source.convert()

    if not packages:
        print("No packages produced.")
        sys.exit(1)

    print(f"\nSaving {len(packages)} packages to {out_dir} …")
    out_dir.mkdir(parents=True, exist_ok=True)
    for pkg_data in packages:
        save_package(pkg_data, out_dir)

    print("\nValidating …")
    for pkg_dir in sorted(out_dir.iterdir()):
        if pkg_dir.is_dir():
            validate_package(pkg_dir)

    print("\n✓ Done.")


if __name__ == "__main__":
    main()
