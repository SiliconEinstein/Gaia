"""Gaia Language Elaborator — deterministic template expansion.

Walks ChainExprs and produces rendered prompts for each StepApply/StepLambda.
Does NOT call any LLM — purely deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .models import (
    Arg,
    Action,
    ChainExpr,
    Knowledge,
    Package,
    Ref,
    StepApply,
    StepLambda,
    StepRef,
)


@dataclass
class ElaboratedPackage:
    """Result of elaboration: the resolved package + rendered prompts."""

    package: Package
    prompts: list[dict] = field(default_factory=list)
    chain_contexts: dict[str, dict] = field(default_factory=dict)


def elaborate_package(pkg: Package) -> ElaboratedPackage:
    """Elaborate a resolved package: substitute templates, record rendered prompts.

    The original package is NOT modified — a deep copy is used internally.
    """
    pkg_copy = copy.deepcopy(pkg)

    # Build name->declaration index, resolving Refs to their targets
    decls_by_name: dict[str, Knowledge] = {}
    for mod in pkg_copy.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, Ref) and decl._resolved is not None:
                decls_by_name[decl.name] = decl._resolved
            else:
                decls_by_name[decl.name] = decl

    # Walk chains and elaborate
    prompts: list[dict] = []
    chain_contexts: dict[str, dict] = {}
    for mod in pkg_copy.loaded_modules:
        for decl in mod.knowledge:
            if isinstance(decl, ChainExpr):
                chain_prompts = _elaborate_chain(decl, decls_by_name)
                prompts.extend(chain_prompts)
                chain_contexts[decl.name] = _build_chain_context(decl, decls_by_name)

    return ElaboratedPackage(package=pkg_copy, prompts=prompts, chain_contexts=chain_contexts)


def _build_chain_context(chain: ChainExpr, decls: dict[str, Knowledge]) -> dict:
    """Extract chain-level context: edge_type, premise_refs, conclusion_refs."""
    premise_refs = []
    conclusion_refs = []
    seen_outputs: set[str] = set()
    seen_premises: set[str] = set()
    final_output = None

    for i, step in enumerate(chain.steps):
        if not isinstance(step, (StepApply, StepLambda)):
            continue

        for arg in _step_args(chain.steps, i, step):
            if arg.dependency != "direct":
                continue
            if arg.ref in seen_outputs or arg.ref in seen_premises:
                continue
            seen_premises.add(arg.ref)
            target = decls.get(arg.ref)
            premise_refs.append(
                {
                    "name": arg.ref,
                    "type": target.type if target else None,
                    "prior": target.prior if target else None,
                    "content": getattr(target, "content", "") if target else "",
                }
            )

        output_ref = _output_ref(chain.steps, i)
        if output_ref is not None:
            seen_outputs.add(output_ref)
            final_output = output_ref

    if final_output is not None:
        target = decls.get(final_output)
        conclusion_refs.append(
            {
                "name": final_output,
                "type": target.type if target else None,
                "prior": target.prior if target else None,
                "content": getattr(target, "content", "") if target else "",
            }
        )

    return {
        "edge_type": chain.edge_type or "deduction",
        "premise_refs": premise_refs,
        "conclusion_refs": conclusion_refs,
    }


def _elaborate_chain(chain: ChainExpr, decls: dict[str, Knowledge]) -> list[dict]:
    """Elaborate a single chain's steps, returning rendered prompt dicts."""
    prompts = []

    for i, step in enumerate(chain.steps):
        if isinstance(step, StepApply):
            action = decls.get(step.apply)
            if not action or not isinstance(action, Action):
                continue

            # Resolve args to content
            arg_records = []
            resolved_contents: list[str] = []
            for arg in step.args:
                target = decls.get(arg.ref)
                content = getattr(target, "content", "") if target else ""
                resolved_contents.append(content)
                arg_records.append(
                    {
                        "ref": arg.ref,
                        "dependency": arg.dependency,
                        "content": content,
                        "decl_type": target.type if target else None,
                        "prior": target.prior if target else None,
                    }
                )

            # Substitute {param} templates
            rendered = action.content
            for param, content in zip(action.params, resolved_contents):
                rendered = rendered.replace(f"{{{param.name}}}", content)

            prompt_dict: dict = {
                "chain": chain.name,
                "step": step.step,
                "action": step.apply,
                "rendered": rendered,
                "args": arg_records,
            }
            if action.return_type:
                prompt_dict["return_type"] = action.return_type
            prompts.append(prompt_dict)

        elif isinstance(step, StepLambda):
            arg_records = _arg_records(_step_args(chain.steps, i, step), decls)
            prompts.append(
                {
                    "chain": chain.name,
                    "step": step.step,
                    "action": "__lambda__",
                    "rendered": step.lambda_,
                    "args": arg_records,
                }
            )

    return prompts


def _output_ref(steps: list, index: int) -> str | None:
    if index + 1 < len(steps):
        next_step = steps[index + 1]
        if isinstance(next_step, StepRef):
            return next_step.ref
    return None


def _step_args(steps: list, index: int, step: StepApply | StepLambda) -> list[Arg]:
    if isinstance(step, StepApply):
        return step.args
    if step.args:
        return step.args
    if index > 0:
        prev = steps[index - 1]
        if isinstance(prev, StepRef):
            return [Arg(ref=prev.ref, dependency="direct")]
    return []


def _arg_records(args: list[Arg], decls: dict[str, Knowledge]) -> list[dict]:
    arg_records = []
    for arg in args:
        target = decls.get(arg.ref)
        content = getattr(target, "content", "") if target else ""
        arg_records.append(
            {
                "ref": arg.ref,
                "dependency": arg.dependency,
                "content": content,
                "decl_type": target.type if target else None,
                "prior": target.prior if target else None,
            }
        )
    return arg_records
