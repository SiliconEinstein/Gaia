"""Serialize/deserialize elaborated packages to .gaia/build/."""

from __future__ import annotations

from pathlib import Path

import yaml

from .elaborator import ElaboratedPackage
from .models import ChainExpr


def save_build(elaborated: ElaboratedPackage, build_dir: Path) -> Path:
    """Serialize elaborated package to build_dir/elaborated.yaml."""
    build_dir.mkdir(parents=True, exist_ok=True)
    out_path = build_dir / "elaborated.yaml"

    pkg = elaborated.package
    pkg_data = {
        "name": pkg.name,
        "version": pkg.version,
        "export": pkg.export,
        "modules": [],
    }
    for mod in pkg.loaded_modules:
        mod_data = {
            "type": mod.type,
            "name": mod.name,
            "export": mod.export,
            "declarations": [],
        }
        for decl in mod.declarations:
            d = decl.model_dump(by_alias=True, exclude_none=True)
            if isinstance(decl, ChainExpr):
                steps_out = []
                for step in decl.steps:
                    s = step.model_dump(by_alias=True, exclude_none=True)
                    steps_out.append(s)
                d["steps"] = steps_out
            mod_data["declarations"].append(d)
        pkg_data["modules"].append(mod_data)

    data = {
        "package": pkg_data,
        "prompts": elaborated.prompts,
        "chain_contexts": elaborated.chain_contexts,
    }
    out_path.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False))
    return out_path
