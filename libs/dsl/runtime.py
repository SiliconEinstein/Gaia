"""Gaia DSL Runtime — Load -> Execute -> Infer -> Inspect."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from libs.inference.bp import BeliefPropagation
from libs.inference.factor_graph import FactorGraph

from .compiler import DSLFactorGraph, compile_factor_graph
from .executor import ActionExecutor, execute_package
from .loader import load_package
from .models import Declaration, Package, Ref
from .resolver import resolve_refs


@dataclass
class RuntimeResult:
    """Result of running the DSL pipeline."""

    package: Package
    factor_graph: DSLFactorGraph | None = None
    beliefs: dict[str, float] = field(default_factory=dict)

    def inspect(self) -> dict:
        """Return a summary of the runtime result."""
        return {
            "package": self.package.name,
            "modules": len(self.package.loaded_modules),
            "variables": len(self.factor_graph.variables) if self.factor_graph else 0,
            "factors": len(self.factor_graph.factors) if self.factor_graph else 0,
            "beliefs": dict(self.beliefs),
        }


class DSLRuntime:
    """Main runtime: Load -> Execute -> Infer -> Inspect."""

    def __init__(self, executor: ActionExecutor | None = None):
        self._executor = executor

    async def load(self, path: Path | str) -> RuntimeResult:
        """Load and validate a package (no execution or inference)."""
        pkg = load_package(Path(path))
        pkg = resolve_refs(pkg)
        return RuntimeResult(package=pkg)

    async def execute(self, result: RuntimeResult) -> RuntimeResult:
        """Execute all chains in a loaded package (no inference)."""
        if self._executor:
            await execute_package(result.package, self._executor)
        return result

    async def infer(self, result: RuntimeResult) -> RuntimeResult:
        """Build factor graph and run BP on a loaded package."""
        # Compile DSL factor graph
        dsl_fg = compile_factor_graph(result.package)
        result.factor_graph = dsl_fg

        # Convert DSLFactorGraph to inference engine FactorGraph
        bp_fg = FactorGraph()
        name_to_id: dict[str, int] = {}
        for i, (name, prior) in enumerate(dsl_fg.variables.items()):
            node_id = i + 1
            name_to_id[name] = node_id
            bp_fg.add_variable(node_id, prior)

        for j, factor in enumerate(dsl_fg.factors):
            tail_ids = [name_to_id[n] for n in factor["tail"] if n in name_to_id]
            head_ids = [name_to_id[n] for n in factor["head"] if n in name_to_id]
            bp_fg.add_factor(
                edge_id=j + 1,
                tail=tail_ids,
                head=head_ids,
                probability=factor["probability"],
                edge_type=factor.get("edge_type", "deduction"),
            )

        # Run BP
        bp = BeliefPropagation()
        beliefs = bp.run(bp_fg)

        # Map back to names
        id_to_name = {v: k for k, v in name_to_id.items()}
        result.beliefs = {id_to_name[nid]: belief for nid, belief in beliefs.items()}

        # Write posteriors back to declaration objects
        all_decls_by_name: dict[str, Declaration] = {}
        for module in result.package.loaded_modules:
            for decl in module.declarations:
                if isinstance(decl, Ref) and decl._resolved is not None:
                    all_decls_by_name[decl.name] = decl._resolved
                else:
                    all_decls_by_name[decl.name] = decl

        for name, belief_val in result.beliefs.items():
            target = all_decls_by_name.get(name)
            if target is not None and hasattr(target, "belief"):
                target.belief = belief_val

        return result

    async def run(self, path: Path | str) -> RuntimeResult:
        """Full pipeline: Load -> Execute -> Infer."""
        result = await self.load(path)
        await self.execute(result)
        await self.infer(result)
        return result
