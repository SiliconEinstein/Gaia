"""Execute a DSL package — walk chains, call actions."""

from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    Action,
    ChainExpr,
    Declaration,
    Package,
    Ref,
    StepApply,
    StepLambda,
    StepRef,
    ToolCallAction,
)


class ActionExecutor(ABC):
    """Abstract interface for executing actions (LLM, tools, etc.)."""

    @abstractmethod
    async def execute_infer(self, prompt: str) -> str:
        """Execute an InferAction. Returns the reasoning result text."""

    @abstractmethod
    async def execute_lambda(self, content: str, input_text: str) -> str:
        """Execute a Lambda step. Returns the reasoning result text."""

    @abstractmethod
    async def execute_tool(self, tool: str, prompt: str) -> str:
        """Execute a ToolCallAction. Returns the tool output text."""


def _topo_sort_chains(chains: list[ChainExpr], decls: dict[str, Declaration]) -> list[ChainExpr]:
    """Sort chains by data dependency: producers before consumers."""
    # Map: chain_name -> set of claim names it writes
    writes: dict[str, set[str]] = {}
    # Map: chain_name -> set of claim names it reads
    reads: dict[str, set[str]] = {}

    for chain in chains:
        w: set[str] = set()
        r: set[str] = set()
        for i, step in enumerate(chain.steps):
            if isinstance(step, StepRef):
                # If next step is Apply/Lambda, this is a read
                if i + 1 < len(chain.steps) and isinstance(
                    chain.steps[i + 1], (StepApply, StepLambda)
                ):
                    r.add(step.ref)
                # If prev step is Apply/Lambda, this is a write
                if i > 0 and isinstance(chain.steps[i - 1], (StepApply, StepLambda)):
                    w.add(step.ref)
        writes[chain.name] = w
        reads[chain.name] = r

    # Build adjacency: chain A must come before chain B if A writes something B reads
    chain_by_name = {c.name: c for c in chains}
    in_degree = {c.name: 0 for c in chains}
    dependents: dict[str, list[str]] = {c.name: [] for c in chains}

    for consumer in chains:
        for producer in chains:
            if consumer.name != producer.name:
                if reads[consumer.name] & writes[producer.name]:
                    dependents[producer.name].append(consumer.name)
                    in_degree[consumer.name] += 1

    # Kahn's algorithm
    queue = [name for name, deg in in_degree.items() if deg == 0]
    result: list[ChainExpr] = []
    while queue:
        name = queue.pop(0)
        result.append(chain_by_name[name])
        for dep in dependents[name]:
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    # If cycle detected, fall back to original order
    if len(result) != len(chains):
        return chains
    return result


async def execute_package(pkg: Package, executor: ActionExecutor) -> None:
    """Execute all ChainExprs in the package, filling in empty claims.

    Walks each chain's steps in order. For Application and Lambda steps,
    calls the executor and writes the result to the output claim.
    Chains are topologically sorted by data dependencies so that
    producers execute before consumers.
    """
    # Build lookup: name -> Declaration (across all modules, resolving refs)
    decls: dict[str, Declaration] = {}
    actions: dict[str, Action] = {}

    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, Ref):
                if decl._resolved is not None:
                    decls[decl.name] = decl._resolved
            else:
                decls[decl.name] = decl
                if isinstance(decl, Action):
                    actions[decl.name] = decl

    # Collect all chains across modules
    all_chains: list[ChainExpr] = []
    for module in pkg.loaded_modules:
        for decl in module.declarations:
            if isinstance(decl, ChainExpr):
                all_chains.append(decl)

    # Topological sort by data dependencies
    sorted_chains = _topo_sort_chains(all_chains, decls)

    # Execute in sorted order
    for chain in sorted_chains:
        await _execute_chain(chain, decls, actions, executor)


async def _execute_chain(
    chain: ChainExpr,
    decls: dict[str, Declaration],
    actions: dict[str, Action],
    executor: ActionExecutor,
) -> None:
    """Execute a single ChainExpr."""
    steps = chain.steps

    for i, step in enumerate(steps):
        if isinstance(step, StepApply):
            action = actions.get(step.apply)
            if action is None:
                continue

            # Build args dict: param_name -> content
            args_content: dict[str, str] = {}
            for j, arg in enumerate(step.args):
                ref_decl = decls.get(arg.ref)
                if ref_decl is not None and hasattr(ref_decl, "content"):
                    param_name = action.params[j].name if j < len(action.params) else arg.ref
                    args_content[param_name] = ref_decl.content

            # Template substitution (language-level semantic)
            prompt = action.content
            for param_name, value in args_content.items():
                prompt = prompt.replace(f"{{{param_name}}}", value)

            # Execute — dispatch by action type
            if isinstance(action, ToolCallAction):
                result = await executor.execute_tool(action.tool or action.name, prompt)
            else:
                result = await executor.execute_infer(prompt)

            # Write result to the next step's claim (if empty)
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef):
                    target = decls.get(next_step.ref)
                    if target is not None and hasattr(target, "content"):
                        if not target.content or not target.content.strip():
                            target.content = result

        elif isinstance(step, StepLambda):
            # Get input from previous step
            input_text = ""
            if i > 0:
                prev = steps[i - 1]
                if isinstance(prev, StepRef):
                    prev_decl = decls.get(prev.ref)
                    if prev_decl is not None and hasattr(prev_decl, "content"):
                        input_text = prev_decl.content

            result = await executor.execute_lambda(step.lambda_, input_text)

            # Write result to the next step's claim (if empty)
            if i + 1 < len(steps):
                next_step = steps[i + 1]
                if isinstance(next_step, StepRef):
                    target = decls.get(next_step.ref)
                    if target is not None and hasattr(target, "content"):
                        if not target.content or not target.content.strip():
                            target.content = result
