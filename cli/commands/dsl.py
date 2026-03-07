"""Gaia DSL CLI commands."""

from __future__ import annotations

from pathlib import Path

from libs.dsl.executor import ActionExecutor
from libs.dsl.runtime import DSLRuntime


class StubExecutor(ActionExecutor):
    """Stub executor that echoes content (no real LLM)."""

    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return result

    def execute_lambda(self, content: str, input_text: str) -> str:
        return content


def load_cmd(path: str) -> None:
    """Load and validate a DSL package."""
    runtime = DSLRuntime()
    result = runtime.load(Path(path))
    pkg = result.package

    print(f"Package: {pkg.name}")
    if pkg.version:
        print(f"Version: {pkg.version}")
    print(f"Loaded: {len(pkg.loaded_modules)} modules")
    for mod in pkg.loaded_modules:
        decl_count = len(mod.declarations)
        export_count = len(mod.export)
        print(f"  {mod.type} {mod.name}: {decl_count} declarations, {export_count} exports")
    print(f"Package exports: {', '.join(pkg.export)}")


def run_cmd(path: str) -> None:
    """Load, execute, and run BP on a DSL package."""
    runtime = DSLRuntime(executor=StubExecutor())
    result = runtime.run(Path(path))

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
