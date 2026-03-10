"""Gaia Language CLI commands."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from libs.lang.executor import ActionExecutor
from libs.lang.runtime import GaiaRuntime


class StubExecutor(ActionExecutor):
    """Stub executor that echoes content (no real LLM)."""

    async def execute_infer(self, prompt: str) -> str:
        return prompt

    async def execute_lambda(self, content: str, input_text: str) -> str:
        return content

    async def execute_tool(self, tool: str, prompt: str) -> str:
        return f"[tool:{tool}] {prompt}"


async def load_cmd(path: str) -> None:
    """Load and validate a Gaia Language package."""
    runtime = GaiaRuntime()
    result = await runtime.load(Path(path))
    pkg = result.package

    print(f"Package: {pkg.name}")
    if pkg.version:
        print(f"Version: {pkg.version}")
    print(f"Loaded: {len(pkg.loaded_modules)} modules")
    for mod in pkg.loaded_modules:
        decl_count = len(mod.knowledge)
        export_count = len(mod.export)
        print(f"  {mod.type} {mod.name}: {decl_count} knowledge objects, {export_count} exports")
    print(f"Package exports: {', '.join(pkg.export)}")


async def run_cmd(path: str) -> None:
    """Load, execute, and run BP on a Gaia Language package."""
    runtime = GaiaRuntime(executor=StubExecutor())
    result = await runtime.run(Path(path))

    print(f"Package: {result.package.name}")
    summary = result.inspect()
    print(f"Variables: {summary['variables']}")
    print(f"Factors: {summary['factors']}")
    print()
    print("Beliefs after BP:")
    for name, belief in sorted(result.beliefs.items()):
        fg = result.factor_graph
        prior = fg.variables.get(name, "?")
        print(f"  {name}: prior={prior} -> belief={belief:.4f}")


async def execute_cmd(path: str) -> None:
    """Execute a Gaia Language package (fill claims via executor, no inference)."""
    runtime = GaiaRuntime(executor=StubExecutor())
    result = await runtime.load(path)
    await runtime.execute(result)
    print(f"Package: {result.package.name}")
    print(f"Executed with {len(result.package.loaded_modules)} modules")
    # Show filled claims
    for module in result.package.loaded_modules:
        for decl in module.knowledge:
            if hasattr(decl, "content") and decl.content:
                print(f"  {decl.name}: {decl.content[:80]}...")


async def inspect_cmd(path: str) -> None:
    """Inspect the factor graph structure of a Gaia Language package."""
    runtime = GaiaRuntime(executor=StubExecutor())
    result = await runtime.run(path)
    summary = result.inspect()
    print(f"Package: {summary['package']}")
    print(f"Modules: {summary['modules']}")
    print(f"Variables: {summary['variables']}")
    print(f"Factors: {summary['factors']}")
    print()
    print("Factor Graph:")
    for factor in result.factor_graph.factors:
        premises = ", ".join(factor["premises"])
        conclusions = ", ".join(factor["conclusions"])
        print(
            f"  {factor['name']}: [{premises}] -> [{conclusions}] "
            f"(p={factor['probability']}, type={factor.get('edge_type', 'deduction')})"
        )
    print()
    print("Beliefs:")
    for name, belief in sorted(result.beliefs.items()):
        var_prior = result.factor_graph.variables.get(name, "?")
        print(f"  {name}: prior={var_prior} -> belief={belief:.4f}")


async def validate_cmd(path: str) -> None:
    """Validate a Gaia Language package (check YAML, refs, types)."""
    from libs.lang.loader import load_package
    from libs.lang.resolver import resolve_refs

    try:
        pkg = load_package(Path(path))
        print(f"Package '{pkg.name}' loaded: {len(pkg.loaded_modules)} modules")
        pkg = resolve_refs(pkg)
        print("All references resolved")
        # Count knowledge objects by type
        type_counts: dict[str, int] = {}
        for mod in pkg.loaded_modules:
            for decl in mod.knowledge:
                type_counts[decl.type] = type_counts.get(decl.type, 0) + 1
        for t, c in sorted(type_counts.items()):
            print(f"  {t}: {c}")
        print("Package is valid.")
    except Exception as e:
        print(f"Validation failed: {e}")


def main() -> None:
    """CLI entry point for gaia-lang commands."""
    parser = argparse.ArgumentParser(prog="gaia-lang", description="Gaia Language Runtime CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # load
    p_load = subparsers.add_parser("load", help="Load and validate a Gaia Language package")
    p_load.add_argument("path", help="Path to the Gaia Language package directory")

    # run
    p_run = subparsers.add_parser("run", help="Run full pipeline: load -> execute -> infer")
    p_run.add_argument("path", help="Path to the Gaia Language package directory")

    # execute
    p_exec = subparsers.add_parser("execute", help="Execute chains (no inference)")
    p_exec.add_argument("path", help="Path to the Gaia Language package directory")

    # inspect
    p_insp = subparsers.add_parser("inspect", help="Inspect factor graph structure")
    p_insp.add_argument("path", help="Path to the Gaia Language package directory")

    # validate
    p_val = subparsers.add_parser("validate", help="Validate package YAML")
    p_val.add_argument("path", help="Path to the Gaia Language package directory")

    args = parser.parse_args()

    commands = {
        "load": load_cmd,
        "run": run_cmd,
        "execute": execute_cmd,
        "inspect": inspect_cmd,
        "validate": validate_cmd,
    }

    asyncio.run(commands[args.command](args.path))


if __name__ == "__main__":
    main()
