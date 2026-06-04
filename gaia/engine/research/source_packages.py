"""Materialize shallow research evidence as local Gaia source packages."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from gaia.engine.research.artifacts import ResearchPackage

JsonDict = dict[str, Any]

_SLUG_RE = re.compile(r"[^A-Za-z0-9_]+")
_DIST_RE = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class ResearchSourcePackage:
    """One shallow local package generated from a research landscape."""

    root: Path
    dist_name: str
    import_name: str
    namespace: str
    claim_count: int
    question_count: int
    note_count: int
    item_refs: list[JsonDict]

    def to_payload(self) -> JsonDict:
        """Return a JSON-compatible event payload."""
        return {
            "path": str(self.root),
            "package": self.dist_name,
            "import_name": self.import_name,
            "namespace": self.namespace,
            "claim_count": self.claim_count,
            "question_count": self.question_count,
            "note_count": self.note_count,
            "item_refs": list(self.item_refs),
        }


def _short_hash(value: object) -> str:
    payload = json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:10]


def _slug(value: object, *, max_len: int = 48) -> str:
    text = str(value or "").strip().lower()
    text = _SLUG_RE.sub("_", text).strip("_")
    if not text:
        text = "item"
    if text[0].isdigit():
        text = f"r_{text}"
    return text[:max_len].strip("_") or "item"


def _dist_slug(value: object, *, max_len: int = 56) -> str:
    text = str(value or "").strip().lower()
    text = _DIST_RE.sub("-", text).strip("-")
    return text[:max_len].strip("-") or "research"


def _toml_str(value: object) -> str:
    return json.dumps(str(value), ensure_ascii=False)


def _py_expr(value: object) -> str:
    return f"json.loads({json.dumps(value, ensure_ascii=False, sort_keys=True)!r})"


def _text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _item_source(item: JsonDict) -> JsonDict:
    source = item.get("source")
    return dict(source) if isinstance(source, dict) else {}


def _item_provenance(item: JsonDict) -> JsonDict:
    provenance = item.get("provenance")
    return dict(provenance) if isinstance(provenance, dict) else {}


def _item_variable_id(item: JsonDict) -> str | None:
    raw = item.get("id")
    if isinstance(raw, str) and raw:
        return raw
    return None


def _call_for_item(item: JsonDict) -> str:
    if item.get("kind") == "variable":
        variable_type = item.get("variable_type")
        if variable_type == "question":
            return "question"
        if variable_type == "claim" or variable_type is None:
            return "claim"
    return "note"


def _content_for_item(item: JsonDict) -> str | None:
    content = _text(item.get("content"))
    if content:
        return content
    title = _text(item.get("title"))
    if title:
        return title
    item_id = _text(item.get("id")) or _text(item.get("item_id"))
    if item_id:
        return f"Retrieved research item {item_id}."
    return None


def _metadata_for_item(
    pkg: ResearchPackage,
    item: JsonDict,
    *,
    landscape_artifact: Path,
) -> JsonDict:
    source = _item_source(item)
    provenance = _item_provenance(item)
    return {
        "gaia_research": {
            "kind": "shallow_search_item",
            "consumer_package": pkg.project_name,
            "landscape_artifact": str(landscape_artifact),
            "item_id": item.get("item_id"),
            "item_kind": item.get("kind"),
            "variable_type": item.get("variable_type"),
            "variable_id": _item_variable_id(item),
            "paper_id": source.get("paper_id"),
            "paper_title": source.get("paper_title"),
            "doi": source.get("doi"),
            "index_id": source.get("index_id"),
            "source": source,
            "provenance": provenance,
        }
    }


def _source_stat_key(call_name: str) -> str:
    if call_name == "claim":
        return "claim_count"
    if call_name == "question":
        return "question_count"
    return "note_count"


def _package_identity(pkg: ResearchPackage, landscape: JsonDict) -> tuple[str, str, str]:
    action = str(landscape.get("action") or "explore").replace(".", "-")
    digest = _short_hash(
        {
            "action": landscape.get("action"),
            "query_provenance": landscape.get("query_provenance", []),
            "items": landscape.get("items", []),
            "target": landscape.get("target"),
        }
    )
    consumer = _dist_slug(pkg.project_name.removesuffix("-gaia"), max_len=36)
    action_slug = _dist_slug(action, max_len=24)
    dist_name = f"{consumer}-research-{action_slug}-{digest}-gaia"
    import_name = dist_name.removesuffix("-gaia").replace("-", "_")
    namespace = f"{pkg.namespace}_research_{action_slug.replace('-', '_')}_{digest}"
    return dist_name, import_name, namespace


def _pyproject(
    *,
    dist_name: str,
    import_name: str,
    namespace: str,
    pkg: ResearchPackage,
    landscape: JsonDict,
) -> str:
    action = str(landscape.get("action") or "explore")
    description = f"Shallow Gaia research source package for {pkg.project_name}"
    return (
        "[project]\n"
        f"name = {_toml_str(dist_name)}\n"
        'version = "0.1.0"\n'
        f"description = {_toml_str(description)}\n"
        'requires-python = ">=3.12"\n'
        "dependencies = []\n\n"
        "[build-system]\n"
        'requires = ["hatchling"]\n'
        'build-backend = "hatchling.build"\n\n'
        "[tool.hatch.build.targets.wheel]\n"
        f'packages = ["src/{import_name}"]\n\n'
        "[tool.gaia]\n"
        'type = "knowledge-package"\n'
        f"namespace = {_toml_str(namespace)}\n\n"
        "[tool.gaia.research_source]\n"
        'kind = "shallow-search-results"\n'
        f"consumer_package = {_toml_str(pkg.project_name)}\n"
        f"landscape_action = {_toml_str(action)}\n"
    )


def _init_source(
    pkg: ResearchPackage,
    landscape: JsonDict,
    *,
    landscape_artifact: Path,
) -> tuple[str, int, int, int, list[JsonDict]]:
    lines = [
        '"""Shallow source package generated from a Gaia research landscape."""',
        "",
        "import json",
        "",
        "from gaia.engine.lang import claim, note, question",
        "",
    ]
    exports: list[str] = []
    stats = {"claim_count": 0, "question_count": 0, "note_count": 0}
    item_refs: list[JsonDict] = []
    raw_items = landscape.get("items")
    items = (
        [item for item in raw_items if isinstance(item, dict)]
        if isinstance(raw_items, list)
        else []
    )

    for index, item in enumerate(items):
        content = _content_for_item(item)
        if content is None:
            continue
        call_name = _call_for_item(item)
        symbol = f"source_{_slug(item.get('item_id') or item.get('id') or index, max_len=32)}"
        while symbol in exports:
            symbol = f"{symbol}_{len(exports)}"
        title = _text(item.get("title")) or _text(item.get("id")) or symbol
        metadata = _metadata_for_item(pkg, item, landscape_artifact=landscape_artifact)
        lines.append(
            f"{symbol} = {call_name}({content!r}, title={title!r}, metadata={_py_expr(metadata)})"
        )
        exports.append(symbol)
        stats[_source_stat_key(call_name)] += 1
        item_refs.append(
            {
                "item_id": item.get("item_id"),
                "kind": item.get("kind"),
                "variable_type": item.get("variable_type"),
                "variable_id": _item_variable_id(item),
                "paper_id": _item_source(item).get("paper_id"),
                "symbol": symbol,
            }
        )

    lines.append("")
    lines.append(f"__all__ = {exports!r}")
    lines.append("")
    return (
        "\n".join(lines),
        stats["claim_count"],
        stats["question_count"],
        stats["note_count"],
        item_refs,
    )


def materialize_landscape_source_package(
    pkg: ResearchPackage,
    landscape: JsonDict,
    *,
    landscape_artifact: Path,
) -> ResearchSourcePackage | None:
    """Write a shallow local source package from ``landscape`` items.

    The package is intentionally cheap: it reuses the already-normalized search
    output and does not fetch LKM reasoning chains or paper graphs.
    """
    raw_items = landscape.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        return None

    dist_name, import_name, namespace = _package_identity(pkg, landscape)
    root = pkg.path / ".gaia" / "research" / "source_packages" / dist_name
    if root.exists():
        shutil.rmtree(root)
    source_dir = root / "src" / import_name
    source_dir.mkdir(parents=True, exist_ok=True)

    init_source, claim_count, question_count, note_count, item_refs = _init_source(
        pkg,
        landscape,
        landscape_artifact=landscape_artifact,
    )
    if not item_refs:
        shutil.rmtree(root)
        return None

    (root / "pyproject.toml").write_text(
        _pyproject(
            dist_name=dist_name,
            import_name=import_name,
            namespace=namespace,
            pkg=pkg,
            landscape=landscape,
        ),
        encoding="utf-8",
    )
    (source_dir / "__init__.py").write_text(init_source, encoding="utf-8")
    (root / "README.md").write_text(
        "# Gaia Research Source Package\n\n"
        "This package was generated from a breadth-first research landscape. "
        "It stores shallow search-result evidence only; use LKM paper/chain "
        "materialization for deep assessment.\n",
        encoding="utf-8",
    )

    return ResearchSourcePackage(
        root=root,
        dist_name=dist_name,
        import_name=import_name,
        namespace=namespace,
        claim_count=claim_count,
        question_count=question_count,
        note_count=note_count,
        item_refs=item_refs,
    )


__all__ = [
    "ResearchSourcePackage",
    "materialize_landscape_source_package",
]
