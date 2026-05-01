"""Run BP inference at 4 time points for PVSK belief evolution analysis."""

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path

from gaia.bp import FactorGraph, lower_local_graph, merge_factor_graphs
from gaia.bp.engine import InferenceEngine
from gaia.cli._packages import (
    apply_package_priors,
    compile_loaded_package_artifact,
    load_gaia_package,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(
        Path(__file__).parent.parent / "results" / f"bp_timeseries-{time.strftime('%Y%m%d-%H%M%S')}.log"
    )],
    force=True,
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent.parent
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# Package definitions: (package_dir_name, year)
ALL_PACKAGES = [
    ("pvsk-meta-gaia", 2000),  # Meta package — always included
    ("pvsk-kojima2009-gaia", 2009),
    ("pvsk-kim2012-gaia", 2012),
    ("pvsk-lee2012-gaia", 2012),
    ("pvsk-burschka2013-gaia", 2013),
    ("pvsk-liu2013-gaia", 2013),
    ("pvsk-jeon2014-gaia", 2014),
    ("pvsk-jeon2015-gaia", 2015),
    ("pvsk-saliba2016-gaia", 2016),
    ("pvsk-grancini2017-gaia", 2017),
    ("pvsk-min2020-gaia", 2020),
    ("pvsk-jeong2021-gaia", 2021),
    ("pvsk-park2021-gaia", 2021),
    ("pvsk-lin2022-gaia", 2022),
    ("pvsk-zhao2022-gaia", 2022),
    ("pvsk-liu2023a-gaia", 2023),
    ("pvsk-gu2023-gaia", 2023),
    ("pvsk-lin2023-gaia", 2023),
    ("pvsk-hou2024-gaia", 2024),
    ("pvsk-li2024-gaia", 2024),
    ("pvsk-jelly2024-gaia", 2024),
    ("pvsk-he2025-gaia", 2025),
    ("pvsk-liu2025-gaia", 2025),
]

# Time points and cutoff years
TIME_POINTS = {
    "T1_2013": 2013,
    "T2_2017": 2017,
    "T3_2022": 2022,
    "T4_2026": 2026,
}

# Meta proposition QIDs to track
META_PROPS = [
    "pvsk:pvsk_meta::p_viability",
    "pvsk:pvsk_meta::p_efficiency",
    "pvsk:pvsk_meta::p_improvement",
    "pvsk:pvsk_meta::p_stability",
    "pvsk:pvsk_meta::p_industrialization",
]


def compile_package(pkg_dir: Path):
    """Load, apply priors, and compile a package."""
    loaded = load_gaia_package(str(pkg_dir))
    apply_package_priors(loaded)
    compiled = compile_loaded_package_artifact(loaded)
    return compiled


def main():
    logger.info("Log file: %s", RESULTS_DIR)
    logger.info("=== PVSK BP Time Series Analysis ===")

    # Step 1: Compile all packages
    logger.info("Step 1: Compiling all packages...")
    compiled_packages = {}
    for pkg_name, year in ALL_PACKAGES:
        pkg_dir = BASE_DIR / pkg_name
        if not pkg_dir.exists():
            logger.warning("Package %s not found, skipping", pkg_name)
            continue
        try:
            compiled = compile_package(pkg_dir)
            n_knowledge = len(compiled.graph.knowledges)
            n_strategies = len(compiled.graph.strategies)
            n_operators = len(compiled.graph.operators)
            logger.info(
                "Compiled %s: %d knowledge, %d strategies, %d operators",
                pkg_name, n_knowledge, n_strategies, n_operators,
            )
            compiled_packages[pkg_name] = (compiled, year)
        except Exception as e:
            logger.error("Failed to compile %s: %s", pkg_name, e)

    logger.info("Compiled %d packages total", len(compiled_packages))

    # Step 2: Run BP at each time point
    results = {}
    for time_label, cutoff_year in TIME_POINTS.items():
        logger.info("\n=== Time point: %s (cutoff year: %d) ===", time_label, cutoff_year)

        # Select packages up to cutoff year
        selected = {
            name: (comp, year)
            for name, (comp, year) in compiled_packages.items()
            if year <= cutoff_year
        }
        logger.info("Selected %d packages for %s", len(selected), time_label)

        if not selected:
            logger.warning("No packages for %s, skipping", time_label)
            continue

        # Lower all packages to factor graphs and merge
        # Start with meta package
        meta_compiled = compiled_packages.get("pvsk-meta-gaia")
        if meta_compiled is None:
            logger.error("Meta package not found, cannot proceed")
            continue

        meta_fg = lower_local_graph(meta_compiled[0].graph)
        meta_prefix = "pvsk:pvsk_meta::"

        # Lower paper packages
        dep_graphs = []
        for pkg_name, (compiled, year) in selected.items():
            if pkg_name == "pvsk-meta-gaia":
                continue
            pkg_prefix = f"pvsk:{compiled.graph.package_name}::"
            fg = lower_local_graph(compiled.graph)
            dep_graphs.append((pkg_name, fg, pkg_prefix))
            logger.info(
                "  %s: %d vars, %d factors",
                pkg_name, len(fg.variables), len(fg.factors),
            )

        # Merge: meta as local, papers as deps (reversed for proper prior handling)
        # Actually, we want papers to update meta beliefs, so we use papers as deps
        # and meta as local — but the shared meta proposition nodes need to be
        # properly merged.

        # Alternative: merge everything into one big factor graph
        merged = FactorGraph()

        # Add all variables from all packages
        for pkg_name, (compiled, year) in selected.items():
            fg = lower_local_graph(compiled.graph)
            pkg_prefix = f"pvsk:{compiled.graph.package_name}::"
            # Dep-owned variables take precedence for their prefix
            for var_id, prior in fg.variables.items():
                if var_id.startswith(pkg_prefix) or var_id not in merged.variables:
                    merged.add_variable(var_id, prior)

        # Add all factors with prefixed IDs
        for pkg_name, (compiled, year) in selected.items():
            fg = lower_local_graph(compiled.graph)
            for factor in fg.factors:
                from dataclasses import replace
                prefixed = replace(factor, factor_id=f"{pkg_name}_{factor.factor_id}")
                merged.factors.append(prefixed)

        logger.info(
            "Merged graph: %d variables, %d factors",
            len(merged.variables), len(merged.factors),
        )

        # Validate
        errors = merged.validate()
        if errors:
            for error in errors:
                logger.error("Factor graph error: %s", error)
            continue

        # Run BP
        engine = InferenceEngine()
        inference_result = engine.run(merged)

        bp_result = inference_result.bp_result
        logger.info(
            "Method: %s (%s), %.0fms",
            inference_result.method_used.upper(),
            "exact" if inference_result.is_exact else "approximate",
            inference_result.elapsed_ms,
        )
        if bp_result.diagnostics.iterations_run:
            logger.info(
                "Converged: %s after %d iterations",
                bp_result.diagnostics.converged,
                bp_result.diagnostics.iterations_run,
            )

        # Extract beliefs for meta propositions
        beliefs = bp_result.beliefs
        time_results = {
            "time_point": time_label,
            "cutoff_year": cutoff_year,
            "n_packages": len(selected),
            "n_variables": len(merged.variables),
            "n_factors": len(merged.factors),
            "method": inference_result.method_used,
            "is_exact": inference_result.is_exact,
            "elapsed_ms": inference_result.elapsed_ms,
            "converged": bp_result.diagnostics.converged,
            "meta_beliefs": {},
            "all_beliefs": {},
        }

        for prop_qid in META_PROPS:
            belief = beliefs.get(prop_qid)
            if belief is not None:
                time_results["meta_beliefs"][prop_qid] = round(belief, 6)
                logger.info("  %s: %.4f", prop_qid, belief)
            else:
                logger.warning("  %s: NOT FOUND in beliefs", prop_qid)

        # Record all beliefs for reference
        for var_id, belief in sorted(beliefs.items()):
            time_results["all_beliefs"][var_id] = round(belief, 6)

        results[time_label] = time_results

    # Step 3: Save results
    output_path = RESULTS_DIR / "belief_timeseries.json"
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info("\nResults saved to %s", output_path)

    # Print summary table
    logger.info("\n=== Summary: Meta Proposition Beliefs Over Time ===")
    header = f"{'Proposition':<25} | {'T1(2013)':>8} | {'T2(2017)':>8} | {'T3(2022)':>8} | {'T4(2026)':>8}"
    logger.info(header)
    logger.info("-" * len(header))

    for prop_qid in META_PROPS:
        label = prop_qid.split("::")[-1]
        values = []
        for time_label in TIME_POINTS:
            if time_label in results:
                v = results[time_label]["meta_beliefs"].get(prop_qid, "N/A")
                values.append(f"{v:.4f}" if isinstance(v, float) else str(v))
            else:
                values.append("N/A")
        logger.info("%-25s | %8s | %8s | %8s | %8s", label, *values)

    logger.info("=== Done ===")


if __name__ == "__main__":
    main()
