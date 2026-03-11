"""Load a Gaia Language package from YAML files."""

from __future__ import annotations

from pathlib import Path

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
    knowledge = [_parse_knowledge(d) for d in data.get("knowledge", [])]
    return Module(
        type=data["type"],
        name=data["name"],
        title=data.get("title"),
        knowledge=knowledge,
        export=data.get("export", []),
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
        return StepLambda(
            step=step_num,
            **{"lambda": data["lambda"]},
            prior=data.get("prior"),
        )

    if "ref" in data:
        return StepRef(step=step_num, ref=data["ref"])

    raise ValueError(f"Unknown step format: {data}")
