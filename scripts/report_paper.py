#!/usr/bin/env python3
"""Generate a readable report for one paper's v2 data.

Usage:
    python scripts/report_paper.py paper_363056a0
    python scripts/report_paper.py paper_363056a0 --out report.md
    python scripts/report_paper.py  # lists available packages
"""

from __future__ import annotations

import asyncio
import sys
import textwrap
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from libs.storage_v2.config import StorageConfig
from libs.storage_v2.manager import StorageManager


def wrap(text: str, width: int = 90, indent: str = "") -> str:
    return textwrap.fill(text.replace("\n", " "), width=width, initial_indent=indent,
                         subsequent_indent=indent)


class Report:
    def __init__(self) -> None:
        self._buf = StringIO()

    def h1(self, text: str) -> None:
        self._buf.write(f"\n# {text}\n\n")

    def h2(self, text: str) -> None:
        self._buf.write(f"\n## {text}\n\n")

    def h3(self, text: str) -> None:
        self._buf.write(f"\n### {text}\n\n")

    def kv(self, key: str, value: object) -> None:
        self._buf.write(f"- **{key}:** {value}\n")

    def text(self, s: str) -> None:
        self._buf.write(s + "\n")

    def quote(self, s: str) -> None:
        for line in s.strip().split("\n"):
            self._buf.write(f"> {line}\n")
        self._buf.write("\n")

    def hr(self) -> None:
        self._buf.write("\n---\n\n")

    def result(self) -> str:
        return self._buf.getvalue()


async def main() -> None:
    config = StorageConfig()
    mgr = StorageManager(config)
    await mgr.initialize()

    # List mode
    all_knowledge = await mgr.list_knowledge()
    pkg_ids = sorted({k.source_package_id for k in all_knowledge})

    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print("Available packages:")
        for pid in pkg_ids:
            count = sum(1 for k in all_knowledge if k.source_package_id == pid)
            print(f"  {pid}  ({count} knowledge items)")
        print(f"\nUsage: python {sys.argv[0]} <package_id> [--out file.md]")
        await mgr.close()
        return

    pkg_id = sys.argv[1]
    out_path = None
    if "--out" in sys.argv:
        out_path = sys.argv[sys.argv.index("--out") + 1]

    r = Report()

    # ── Package ──
    pkg = await mgr.get_package(pkg_id)
    if not pkg:
        print(f"Package '{pkg_id}' not found.")
        await mgr.close()
        sys.exit(1)

    r.h1(f"Paper Report: {pkg.name}")
    r.kv("Package ID", f"`{pkg.package_id}`")
    r.kv("Version", pkg.version)
    r.kv("Status", pkg.status)
    r.kv("Description", pkg.description)
    r.kv("Submitter", pkg.submitter)
    r.kv("Submitted at", pkg.submitted_at)
    r.kv("Exports", f"{len(pkg.exports)} items")

    # ── Module ──
    for mid in pkg.modules:
        mod = await mgr.get_module(mid)
        if not mod:
            continue
        r.h2(f"Module: {mod.name}")
        r.kv("Module ID", f"`{mod.module_id}`")
        r.kv("Role", mod.role)
        r.kv("Chains", f"{len(mod.chain_ids)}")
        r.kv("Exports", f"{len(mod.export_ids)}")

    # ── Knowledge Items ──
    pkg_knowledge = sorted(
        [k for k in all_knowledge if k.source_package_id == pkg_id],
        key=lambda k: k.knowledge_id,
    )
    r.h2(f"Knowledge Items ({len(pkg_knowledge)})")

    for i, k in enumerate(pkg_knowledge, 1):
        short_id = k.knowledge_id.split("/")[-1]
        r.h3(f"{i}. {short_id}")
        r.kv("ID", f"`{k.knowledge_id}`")
        r.kv("Type", k.type)
        r.kv("Version", k.version)
        r.kv("Prior", k.prior)

        # Belief
        beliefs = await mgr.get_belief_history(k.knowledge_id)
        if beliefs:
            latest = beliefs[-1]
            r.kv("Belief", f"{latest.belief} (run: {latest.bp_run_id})")

        r.text("")
        r.quote(k.content)

    # ── Chains ──
    all_chains = await mgr.list_chains()
    pkg_chains = sorted(
        [c for c in all_chains if c.package_id == pkg_id],
        key=lambda c: c.chain_id,
    )
    r.h2(f"Reasoning Chains ({len(pkg_chains)})")

    for ci, chain in enumerate(pkg_chains, 1):
        short_chain = chain.chain_id.split(".")[-1]
        r.h3(f"Chain {ci}: {short_chain}")
        r.kv("ID", f"`{chain.chain_id}`")
        r.kv("Type", chain.type)
        r.kv("Steps", len(chain.steps))
        r.text("")

        for step in chain.steps:
            premise_names = [p.knowledge_id.split("/")[-1] for p in step.premises]
            conclusion_name = step.conclusion.knowledge_id.split("/")[-1]

            r.text(f"**Step {step.step_index}:**")
            if premise_names:
                r.text(f"  Premises: {', '.join(f'`{p}`' for p in premise_names)}")
            r.text(f"  Conclusion: `{conclusion_name}`")
            r.text("")
            r.quote(step.reasoning)

            # Step probability
            probs = await mgr.get_probability_history(chain.chain_id, step.step_index)
            if probs:
                p = probs[-1]
                r.text(f"  *Probability: {p.value} (source: {p.source})*\n")

    # ── Graph Topology ──
    if mgr.graph_store is not None:
        r.h2("Graph Topology")
        # Pick the most connected knowledge node
        best_kid, best_degree = "", 0
        for k in pkg_knowledge:
            sub = await mgr.get_neighbors(k.knowledge_id)
            degree = len(sub.knowledge_ids) + len(sub.chain_ids)
            if degree > best_degree:
                best_kid, best_degree = k.knowledge_id, degree

        if best_kid:
            sub = await mgr.get_subgraph(best_kid, max_knowledge=50)
            short = best_kid.split("/")[-1]
            r.text(f"Subgraph from most-connected node `{short}`:")
            r.text("")
            r.kv("Knowledge nodes", len(sub.knowledge_ids))
            r.kv("Chain nodes", len(sub.chain_ids))
            r.text("")
            r.text("Connected knowledge:")
            for kid in sorted(sub.knowledge_ids):
                r.text(f"  - `{kid.split('/')[-1]}`")

    # ── Summary ──
    r.hr()
    r.text(f"*Report generated from `{config.lancedb_path}`*")
    if config.graph_backend != "none":
        r.text(f"*Graph backend: {config.graph_backend}*")

    output = r.result()
    if out_path:
        Path(out_path).write_text(output)
        print(f"Report saved to {out_path}")
    else:
        print(output)

    await mgr.close()


if __name__ == "__main__":
    asyncio.run(main())
