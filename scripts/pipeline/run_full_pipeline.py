#!/usr/bin/env python3
"""End-to-end pipeline orchestrator that runs all 7 stages in order.

Reads defaults from pipeline.toml. CLI args override config values.

Usage:
    # Run all stages (reads everything from pipeline.toml + .env)
    python scripts/pipeline/run_full_pipeline.py

    # Override papers_dir
    python scripts/pipeline/run_full_pipeline.py --papers-dir /data/papers

    # Run only one stage
    python scripts/pipeline/run_full_pipeline.py --stage build-graph-ir

    # Resume from a stage
    python scripts/pipeline/run_full_pipeline.py --from-stage persist
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

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


def _load_toml(path: Path) -> dict:
    """Load a single TOML file."""
    if not path.exists():
        return {}
    try:
        import tomllib
    except ModuleNotFoundError:
        import tomli as tomllib  # type: ignore[no-redef]
    with open(path, "rb") as f:
        return tomllib.load(f)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge override into base. Override values win."""
    result = dict(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = _deep_merge(result[key], val)
        else:
            result[key] = val
    return result


def _apply_env_mapping(cfg: dict) -> None:
    """Apply [storage.env_mapping] — copy .env vars to GAIA_* vars.

    e.g. TEST_GAIA_LANCEDB_URI → GAIA_LANCEDB_URI
    """
    import os

    mapping = cfg.get("storage", {}).pop("env_mapping", None)
    if not mapping:
        return
    for src_var, dst_var in mapping.items():
        value = os.getenv(src_var)
        if value:
            os.environ[dst_var] = value
            print(f"  env: {src_var} → {dst_var}")
        else:
            print(f"  env: {src_var} not set, skipping")


def _load_config(env: str | None = None) -> dict:
    """Load pipeline config: base pipeline.toml + env-specific override.

    Load order: pipeline.toml (base) ← pipeline.{env}.toml (override)
    Then applies [storage.env_mapping] to set GAIA_* env vars.
    Env is determined by: --env arg > GAIA_ENV env var > no override.
    """
    import os

    env = env or os.getenv("GAIA_ENV")

    base = _load_toml(REPO_ROOT / "pipeline.toml")

    if env:
        env_path = REPO_ROOT / f"pipeline.{env}.toml"
        if env_path.exists():
            override = _load_toml(env_path)
            base = _deep_merge(base, override)
            print(f"Config: pipeline.toml + pipeline.{env}.toml")
        else:
            print(f"Warning: pipeline.{env}.toml not found, using base only")
    else:
        print("Config: pipeline.toml (no env override)")

    _apply_env_mapping(base)

    return base


def build_stage_command(
    stage: str,
    *,
    papers_dir: str,
    output_dir: str,
    graph_backend: str,
    use_embedding: bool,
    canonicalizable_types: list[str] | None = None,
    concurrency: int = 5,
    gaia_lang_import: str = "../../../libs/typst/gaia-lang/v2.typ",
    clean: bool = False,
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
            "--gaia-lang-import",
            gaia_lang_import,
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
        if canonicalizable_types:
            cmd.extend(["--canonicalizable-types", *canonicalizable_types])
    elif stage == "persist":
        cmd = [
            sys.executable,
            "scripts/pipeline/persist_to_db.py",
            "--packages-dir",
            typst_packages,
            "--global-graph-dir",
            global_graph,
            "--graph-backend",
            graph_backend,
        ]
        if clean:
            cmd.append("--clean")
    elif stage == "curation":
        cmd = [
            sys.executable,
            "scripts/pipeline/run_curation_db.py",
            "--db-path",
            "unused",  # StorageConfig reads from .env
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
            "unused",  # StorageConfig reads from .env
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
    return [f"{directory}/*"]


def run_stage(stage: str, **kwargs) -> tuple[bool, float]:
    """Run a single pipeline stage. Returns (success, elapsed_seconds)."""
    cmd = build_stage_command(stage, **kwargs)

    header = f" Stage: {stage} "
    print(f"\n{'=' * 70}")
    print(f"{header:=^70}")
    print(f"{'=' * 70}")
    print(f"Command: {' '.join(cmd)}")
    print()

    proc_env = None
    if stage == "xml-to-typst":
        import os

        proc_env = {**os.environ, "PYTHONPATH": str(REPO_ROOT / "scripts" / "pipeline")}

    t0 = time.monotonic()
    result = subprocess.run(cmd, cwd=str(REPO_ROOT), env=proc_env)
    elapsed = time.monotonic() - t0

    if result.returncode == 0:
        print(f"\n[OK] Stage '{stage}' completed in {elapsed:.1f}s")
    else:
        print(
            f"\n[FAIL] Stage '{stage}' failed (exit code {result.returncode}) after {elapsed:.1f}s"
        )

    return result.returncode == 0, elapsed


def main() -> int:
    # Pre-parse --env before full argparse (needed to set config defaults)
    import os

    env_name = None
    for i, arg in enumerate(sys.argv[1:], 1):
        if arg == "--env" and i < len(sys.argv):
            env_name = sys.argv[i + 1]
            break
        if arg.startswith("--env="):
            env_name = arg.split("=", 1)[1]
            break
    env_name = env_name or os.getenv("GAIA_ENV")

    cfg = _load_config(env_name)
    pipeline_cfg = cfg.get("pipeline", {})
    storage_cfg = cfg.get("storage", {})
    canon_cfg = pipeline_cfg.get("canonicalization", {})

    parser = argparse.ArgumentParser(
        description="Run the full Gaia pipeline. Reads defaults from pipeline.toml.",
    )
    parser.add_argument(
        "--env",
        default=env_name,
        help="Environment: local, test, prod (loads pipeline.{env}.toml override)",
    )
    parser.add_argument(
        "--papers-dir",
        default=pipeline_cfg.get("papers_dir", "tests/fixtures/inputs/papers"),
        help=f"Paper input directory (default from config: {pipeline_cfg.get('papers_dir', 'N/A')})",
    )
    parser.add_argument(
        "--output-dir",
        default=pipeline_cfg.get("output_dir", "output"),
        help=f"Output directory (default from config: {pipeline_cfg.get('output_dir', 'N/A')})",
    )
    parser.add_argument(
        "--graph-backend",
        default=storage_cfg.get("graph_backend", "none"),
        choices=["kuzu", "neo4j", "none"],
    )
    parser.add_argument(
        "--use-embedding",
        action="store_true",
        default=canon_cfg.get("use_embedding", False),
    )
    parser.add_argument("--stage", choices=STAGES, help="Run only this stage")
    parser.add_argument("--from-stage", choices=STAGES, help="Run from this stage onwards")
    parser.add_argument(
        "--concurrency",
        type=int,
        default=pipeline_cfg.get("concurrency", 5),
    )
    parser.add_argument(
        "--gaia-lang-import",
        default=pipeline_cfg.get("gaia_lang_import", "../../../libs/typst/gaia-lang/v2.typ"),
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Drop all existing DB data before persist stage. Must be explicit.",
    )

    args = parser.parse_args()

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

    print(f"Pipeline stages: {', '.join(stages_to_run)}")
    print(f"Papers dir:      {args.papers_dir}")
    print(f"Output dir:      {args.output_dir}")
    print(f"Graph backend:   {args.graph_backend}")
    print(f"Config:          {REPO_ROOT / 'pipeline.toml'}")

    common_kwargs = {
        "papers_dir": args.papers_dir,
        "output_dir": args.output_dir,
        "graph_backend": args.graph_backend,
        "use_embedding": args.use_embedding,
        "canonicalizable_types": canon_cfg.get("canonicalizable_types", ["claim"]),
        "concurrency": args.concurrency,
        "gaia_lang_import": args.gaia_lang_import,
        "clean": args.clean,
    }

    results: dict[str, tuple[bool, float]] = {}
    total_t0 = time.monotonic()

    for stage in stages_to_run:
        success, elapsed = run_stage(stage, **common_kwargs)
        results[stage] = (success, elapsed)
        if not success:
            print(f"\nStopping pipeline: stage '{stage}' failed.")
            break

    total_elapsed = time.monotonic() - total_t0

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
