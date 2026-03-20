#!/usr/bin/env python3
"""End-to-end pipeline orchestrator that runs all 7 stages in order.

Supports running individual stages, resuming from a stage, and skipping stages.

Usage:
    # Run all stages
    python scripts/pipeline/run_full_pipeline.py \
        --papers-dir tests/fixtures/inputs/papers \
        --output-dir output

    # Run only one stage
    python scripts/pipeline/run_full_pipeline.py \
        --papers-dir tests/fixtures/inputs/papers \
        --stage build-graph-ir

    # Resume from a stage
    python scripts/pipeline/run_full_pipeline.py \
        --papers-dir tests/fixtures/inputs/papers \
        --from-stage persist
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

STAGES = [
    "xml-to-typst",
    "build-graph-ir",
    "local-bp",
    "global-canon",
    "persist",
    "curation",
    "global-bp",
]


def build_stage_command(
    stage: str,
    *,
    papers_dir: str,
    output_dir: str,
    db_path: str,
    graph_backend: str,
    use_embedding: bool,
    concurrency: int,
) -> list[str]:
    """Build the subprocess command for a given stage."""
    typst_packages = str(Path(output_dir) / "typst_packages")
    global_graph = str(Path(output_dir) / "global_graph")

    if stage == "xml-to-typst":
        cmd = [
            sys.executable,
            "scripts/paper_to_typst.py",
            papers_dir,
            "--skip-llm",
            "-o",
            typst_packages,
            "--concurrency",
            str(concurrency),
        ]
    elif stage == "build-graph-ir":
        cmd = [
            sys.executable,
            "scripts/pipeline/build_graph_ir.py",
            *_glob_subdirs(typst_packages),
        ]
    elif stage == "local-bp":
        cmd = [
            sys.executable,
            "scripts/pipeline/run_local_bp.py",
            *_glob_subdirs(typst_packages),
        ]
    elif stage == "global-canon":
        cmd = [
            sys.executable,
            "scripts/pipeline/canonicalize_global.py",
            *_glob_subdirs(typst_packages),
            "-o",
            global_graph,
        ]
        if use_embedding:
            cmd.append("--use-embedding")
    elif stage == "persist":
        cmd = [
            sys.executable,
            "scripts/pipeline/persist_to_db.py",
            "--packages-dir",
            typst_packages,
            "--global-graph-dir",
            global_graph,
            "--db-path",
            db_path,
            "--graph-backend",
            graph_backend,
        ]
    elif stage == "curation":
        cmd = [
            sys.executable,
            "scripts/pipeline/run_curation_db.py",
            "--db-path",
            db_path,
            "--graph-backend",
            graph_backend,
            "--report-path",
            str(Path(output_dir) / "curation_report.json"),
        ]
    elif stage == "global-bp":
        cmd = [
            sys.executable,
            "scripts/pipeline/run_global_bp_db.py",
            "--db-path",
            db_path,
            "--graph-backend",
            graph_backend,
            "--backup-path",
            str(Path(output_dir) / "global_beliefs.json"),
        ]
    else:
        raise ValueError(f"Unknown stage: {stage}")

    return cmd


def _glob_subdirs(directory: str) -> list[str]:
    """Return sorted subdirectory paths, or the glob pattern if dir doesn't exist yet."""
    d = Path(directory)
    if d.is_dir():
        subdirs = sorted(str(p) for p in d.iterdir() if p.is_dir())
        if subdirs:
            return subdirs
    # Fallback: return the glob pattern for shell expansion (won't work with
    # subprocess list mode, but signals the issue clearly)
    return [f"{directory}/*"]


def run_stage(
    stage: str,
    *,
    papers_dir: str,
    output_dir: str,
    db_path: str,
    graph_backend: str,
    use_embedding: bool,
    concurrency: int,
) -> tuple[bool, float]:
    """Run a single pipeline stage. Returns (success, elapsed_seconds)."""
    cmd = build_stage_command(
        stage,
        papers_dir=papers_dir,
        output_dir=output_dir,
        db_path=db_path,
        graph_backend=graph_backend,
        use_embedding=use_embedding,
        concurrency=concurrency,
    )

    header = f" Stage: {stage} "
    print(f"\n{'=' * 70}")
    print(f"{header:=^70}")
    print(f"{'=' * 70}")
    print(f"Command: {' '.join(cmd)}")
    print()

    t0 = time.monotonic()
    result = subprocess.run(cmd, cwd=str(REPO_ROOT))
    elapsed = time.monotonic() - t0

    if result.returncode == 0:
        print(f"\n[OK] Stage '{stage}' completed in {elapsed:.1f}s")
    else:
        print(
            f"\n[FAIL] Stage '{stage}' failed (exit code {result.returncode}) after {elapsed:.1f}s"
        )

    return result.returncode == 0, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the full Gaia pipeline (7 stages) end-to-end.",
    )
    parser.add_argument(
        "--papers-dir",
        required=True,
        help="Directory containing paper subdirs with XML files",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Output directory for all intermediate files (default: output)",
    )
    parser.add_argument(
        "--db-path",
        default="./data/lancedb/gaia",
        help="LanceDB path (default: ./data/lancedb/gaia)",
    )
    parser.add_argument(
        "--graph-backend",
        default="none",
        choices=["kuzu", "neo4j", "none"],
        help="Graph backend: kuzu, neo4j, or none (default: none)",
    )
    parser.add_argument(
        "--use-embedding",
        action="store_true",
        help="Use embedding service in canonicalization",
    )
    parser.add_argument(
        "--stage",
        choices=STAGES,
        help="Run only this specific stage",
    )
    parser.add_argument(
        "--from-stage",
        choices=STAGES,
        help="Run from this stage to the end",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=5,
        help="Max concurrent papers for xml-to-typst (default: 5)",
    )

    args = parser.parse_args()

    # Determine which stages to run
    if args.stage and args.from_stage:
        print("Error: --stage and --from-stage are mutually exclusive", file=sys.stderr)
        return 1

    if args.stage:
        stages_to_run = [args.stage]
    elif args.from_stage:
        idx = STAGES.index(args.from_stage)
        stages_to_run = STAGES[idx:]
    else:
        stages_to_run = list(STAGES)

    print(f"Pipeline stages to run: {', '.join(stages_to_run)}")
    print(f"Papers dir: {args.papers_dir}")
    print(f"Output dir: {args.output_dir}")
    print(f"DB path: {args.db_path}")
    print(f"Graph backend: {args.graph_backend}")

    # Run stages
    results: dict[str, tuple[bool, float]] = {}
    total_t0 = time.monotonic()

    for stage in stages_to_run:
        success, elapsed = run_stage(
            stage,
            papers_dir=args.papers_dir,
            output_dir=args.output_dir,
            db_path=args.db_path,
            graph_backend=args.graph_backend,
            use_embedding=args.use_embedding,
            concurrency=args.concurrency,
        )
        results[stage] = (success, elapsed)

        if not success:
            print(f"\nStopping pipeline: stage '{stage}' failed.")
            break

    total_elapsed = time.monotonic() - total_t0

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"{'  Pipeline Summary  ':=^70}")
    print(f"{'=' * 70}")

    for stage in stages_to_run:
        if stage in results:
            success, elapsed = results[stage]
            status = "OK" if success else "FAIL"
            print(f"  [{status:>4}] {stage:<20} {elapsed:>8.1f}s")
        else:
            print(f"  [SKIP] {stage:<20}      --")

    print(f"\n  Total elapsed: {total_elapsed:.1f}s")

    failed = [s for s, (ok, _) in results.items() if not ok]
    if failed:
        print(f"\n  Failed stages: {', '.join(failed)}")
        return 1

    print("\n  All stages completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
