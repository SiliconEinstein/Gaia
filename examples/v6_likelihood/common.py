"""Shared helpers for v6 likelihood examples."""

from __future__ import annotations

from dataclasses import dataclass

from gaia.bp import lower_local_graph
from gaia.bp.exact import exact_inference
from gaia.lang.compiler.compile import CompiledPackage, compile_package_artifact
from gaia.lang.runtime.package import CollectedPackage


@dataclass(frozen=True)
class ExampleResult:
    package: CollectedPackage
    compiled: CompiledPackage
    beliefs: dict[str, float]


def compile_and_infer(package: CollectedPackage) -> ExampleResult:
    compiled = compile_package_artifact(package)
    factor_graph = lower_local_graph(compiled.graph)
    beliefs, _ = exact_inference(factor_graph)
    return ExampleResult(package=package, compiled=compiled, beliefs=beliefs)
