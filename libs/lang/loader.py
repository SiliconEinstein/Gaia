"""Load a Gaia Language package from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import (
    KNOWLEDGE_TYPE_MAP,
    Arg,
    ChainExpr,
    Knowledge,
    Module,
    Package,
    Step,
    StepApply,
    StepLambda,
    StepRef,
)


def load_package(path: Path) -> Package:
    """Load a package directory: package.yaml + module YAML files."""
    path = Path(path)
    pkg_file = path / "package.yaml"
    if not pkg_file.exists():
        raise FileNotFoundError(f"Package manifest not found: {pkg_file}")

    with open(pkg_file) as f:
        pkg_data = yaml.safe_load(f)

    pkg = Package.model_validate(pkg_data)

    # Load each module file
    for module_name in pkg.modules_list:
        mod_file = path / f"{module_name}.yaml"
        if not mod_file.exists():
            raise FileNotFoundError(f"Module file not found: {mod_file}")
        with open(mod_file) as f:
            mod_data = yaml.safe_load(f)
        module = _parse_module(mod_data)
        pkg.loaded_modules.append(module)

    return pkg


def _parse_module(data: dict) -> Module:
    """Parse a module YAML dict into a Module with typed knowledge items."""
    _validate_authoring_surface(data)

    knowledge = [_parse_knowledge(d) for d in data.get("knowledge", [])]
    knowledge.extend(_parse_knowledge(d) for d in data.get("premises", []))
    for chain_data in data.get("chains", []):
        knowledge.extend(_expand_inline_chain(chain_data))
    return Module(
        type=data["type"],
        name=data["name"],
        title=data.get("title"),
        knowledge=knowledge,
        export=data.get("export", []),
    )


def _validate_authoring_surface(data: dict[str, Any]) -> None:
    module_type = data["type"]

    if module_type == "reasoning_module" and "knowledge" in data:
        raise ValueError(
            "reasoning_module no longer accepts top-level 'knowledge'; "
            "use 'premises' and 'chains' instead"
        )

    authored_decls = list(data.get("knowledge", [])) + list(data.get("premises", []))
    for decl in authored_decls:
        if decl.get("type") == "chain_expr":
            raise ValueError(
                "authored 'chain_expr' declarations are no longer supported; use top-level "
                "'chains' blocks instead"
            )


def _parse_knowledge(data: dict) -> Knowledge:
    """Parse a single knowledge dict into the correct Knowledge subclass."""
    decl_type = data.get("type", "")
    cls = KNOWLEDGE_TYPE_MAP.get(decl_type)

    if cls is None:
        # Unknown type — return base Knowledge
        return Knowledge.model_validate(data)

    if cls is ChainExpr:
        # Parse steps specially
        raw_steps = data.get("steps", [])
        steps = [_parse_step(s) for s in raw_steps]
        return ChainExpr(
            name=data["name"],
            steps=steps,
            prior=data.get("prior"),
            metadata=data.get("metadata"),
            edge_type=data.get("edge_type"),
        )

    return cls.model_validate(data)


def _parse_step(data: dict) -> Step:
    """Parse a step dict into StepRef, StepApply, or StepLambda."""
    step_num = data.get("step", 0)

    if "apply" in data:
        args = [Arg.model_validate(a) for a in data.get("args", [])]
        return StepApply(
            step=step_num,
            apply=data["apply"],
            args=args,
            prior=data.get("prior"),
        )

    if "lambda" in data:
        args = [Arg.model_validate(a) for a in data.get("args", [])]
        return StepLambda(
            step=step_num,
            **{"lambda": data["lambda"]},
            args=args,
            prior=data.get("prior"),
        )

    if "ref" in data:
        return StepRef(step=step_num, ref=data["ref"])

    raise ValueError(f"Unknown step format: {data}")


def _expand_inline_chain(data: dict[str, Any]) -> list[Knowledge]:
    """Expand author-facing `chains:` blocks into internal declarations."""
    chain_name = data["name"]
    raw_steps = list(data.get("steps", []))
    conclusion = data.get("conclusion")
    if conclusion is None:
        raise ValueError(f"Chain '{chain_name}' is missing a conclusion block")

    node_specs = [
        {"data": step_data, "is_conclusion": False, "position": index}
        for index, step_data in enumerate(raw_steps, start=1)
    ]
    node_specs.append(
        {
            "data": conclusion,
            "is_conclusion": True,
            "position": len(raw_steps) + 1,
        }
    )

    local_names: dict[str, str] = {}
    for spec in node_specs:
        actual_name = _inline_node_name(
            spec["data"],
            chain_name=chain_name,
            position=spec["position"],
            is_conclusion=spec["is_conclusion"],
        )
        spec["actual_name"] = actual_name
        for alias in _inline_node_aliases(spec["data"], actual_name):
            existing = local_names.get(alias)
            if existing is not None and existing != actual_name:
                raise ValueError(
                    f"Chain '{chain_name}' uses duplicate local ref alias '{alias}'"
                )
            local_names[alias] = actual_name

    knowledge: list[Knowledge] = []
    chain_steps: list[Step] = []
    step_num = 1

    for spec in node_specs:
        decl = _parse_inline_node(
            spec["data"],
            actual_name=spec["actual_name"],
            chain_name=chain_name,
            is_conclusion=spec["is_conclusion"],
        )
        args = [_parse_chain_arg(arg, local_names) for arg in spec["data"].get("refs", [])]
        lambda_text = spec["data"].get("reasoning") or getattr(decl, "content", "") or ""

        knowledge.append(decl)
        chain_steps.append(
            StepLambda(
                step=step_num,
                **{"lambda": lambda_text},
                args=args,
                prior=spec["data"].get("prior"),
            )
        )
        chain_steps.append(StepRef(step=step_num + 1, ref=spec["actual_name"]))
        step_num += 2

    knowledge.append(
        ChainExpr(
            name=chain_name,
            steps=chain_steps,
            prior=data.get("prior"),
            metadata=data.get("metadata"),
            edge_type=data.get("edge_type"),
        )
    )
    return knowledge


def _parse_inline_node(
    data: dict[str, Any],
    *,
    actual_name: str,
    chain_name: str,
    is_conclusion: bool,
) -> Knowledge:
    payload = dict(data)
    payload.pop("id", None)
    payload.pop("refs", None)
    payload.pop("reasoning", None)
    payload["name"] = actual_name

    metadata = dict(payload.get("metadata") or {})
    metadata.setdefault("generated_from_chain", True)
    metadata.setdefault("chain_name", chain_name)
    metadata["chain_role"] = "conclusion" if is_conclusion else "step"
    payload["metadata"] = metadata

    if not payload.get("content") and data.get("reasoning"):
        payload["content"] = data["reasoning"]

    return _parse_knowledge(payload)


def _inline_node_name(
    data: dict[str, Any],
    *,
    chain_name: str,
    position: int,
    is_conclusion: bool,
) -> str:
    explicit_name = data.get("name")
    if explicit_name:
        return explicit_name

    local_id = data.get("id")
    if local_id:
        return f"{chain_name}__{local_id}"

    suffix = "conclusion" if is_conclusion else f"step_{position}"
    return f"{chain_name}__{suffix}"


def _inline_node_aliases(data: dict[str, Any], actual_name: str) -> list[str]:
    aliases = [actual_name]
    if data.get("id"):
        aliases.append(data["id"])
    if data.get("name"):
        aliases.append(data["name"])
    return list(dict.fromkeys(aliases))


def _parse_chain_arg(data: str | dict[str, Any], local_names: dict[str, str]) -> Arg:
    if isinstance(data, str):
        return Arg(ref=local_names.get(data, data), dependency="direct")

    payload = dict(data)
    ref = payload["ref"]
    payload["ref"] = local_names.get(ref, ref)
    return Arg.model_validate(payload)
