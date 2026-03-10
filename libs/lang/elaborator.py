"""Gaia Language Elaborator — deterministic template expansion.

Walks ChainExprs and produces rendered prompts for each StepApply/StepLambda.
Does NOT call any LLM — purely deterministic.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field

from .models import (
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
    # Find the index boundaries of StepApply/StepLambda steps
    first_apply_idx = None
    last_apply_idx = None
    for i, step in enumerate(chain.steps):
        if isinstance(step, (StepApply, StepLambda)):
            if first_apply_idx is None:
                first_apply_idx = i
            last_apply_idx = i

    # StepRef steps before first apply are premises, after last apply are conclusions
    premise_refs = []
    conclusion_refs = []
    for i, step in enumerate(chain.steps):
        if not isinstance(step, StepRef):
            continue
        target = decls.get(step.ref)
        ref_info = {
            "name": step.ref,
            "type": target.type if target else None,
            "prior": target.prior if target else None,
            "content": getattr(target, "content", "") if target else "",
        }
        if first_apply_idx is not None and i < first_apply_idx:
            premise_refs.append(ref_info)
        elif last_apply_idx is not None and i > last_apply_idx:
            conclusion_refs.append(ref_info)

    return {
        "edge_type": chain.edge_type or "deduction",
        "premise_refs": premise_refs,
        "conclusion_refs": conclusion_refs,
    }


def _elaborate_chain(chain: ChainExpr, decls: dict[str, Knowledge]) -> list[dict]:
    """Elaborate a single chain's steps, returning rendered prompt dicts."""
    prompts = []

    for step in chain.steps:
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
            prompts.append(
                {
                    "chain": chain.name,
                    "step": step.step,
                    "action": "__lambda__",
                    "rendered": step.lambda_,
                    "args": [],
                }
            )

    return prompts
