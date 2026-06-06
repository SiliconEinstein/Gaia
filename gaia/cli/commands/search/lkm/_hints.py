"""Gaia CLI hints for raw LKM search responses."""

from __future__ import annotations

from typing import Any


def knowledge_hint(payload: dict[str, Any], *, index_id: str) -> str | None:
    """Return a stderr-only hint for an LKM knowledge search response."""
    inspect_cmd: str | None = None
    add_cmd: str | None = None
    for variable in _variables(payload):
        if inspect_cmd is None:
            claim_id = _claim_id_for_reasoning(variable)
            if claim_id is not None:
                inspect_cmd = f"gaia search lkm reasoning --index {index_id} --claim-id {claim_id}"
        if add_cmd is None:
            paper_id = _paper_id_from_variable(variable)
            if paper_id is not None:
                add_cmd = f"gaia pkg add --lkm-index {index_id} --lkm-paper {paper_id}"
        if inspect_cmd is not None and add_cmd is not None:
            break

    blocks: list[str] = []
    if inspect_cmd is not None:
        blocks.append(_hint_block("Hint: inspect claim reasoning:", inspect_cmd))
    if add_cmd is not None:
        blocks.append(_hint_block("Hint: materialize the backing paper package:", add_cmd))
    return "\n\n".join(blocks) or None


def reasoning_hint(
    payload: dict[str, Any],
    *,
    index_id: str,
    claim_id: str | None = None,
) -> str | None:
    """Return a stderr-only hint for an LKM reasoning response."""
    paper_id = _paper_id_from_reasoning(payload)
    if paper_id is not None:
        return _hint_block(
            "Hint: materialize the backing paper package:",
            f"gaia pkg add --lkm-index {index_id} --lkm-paper {paper_id}",
        )
    if claim_id is not None:
        return _hint_block(
            "Hint: resolve this claim to its backing paper package:",
            f"gaia pkg add --lkm-index {index_id} --lkm-claim {claim_id}",
        )
    return None


def package_hint(
    payload: dict[str, Any],
    *,
    index_id: str,
    requested_paper_id: str | None = None,
) -> str | None:
    """Return a stderr-only hint for an LKM paper graph response."""
    paper_id = requested_paper_id
    if paper_id is None:
        paper_ids = _paper_ids_from_papers(payload)
        paper_id = paper_ids[0] if len(paper_ids) == 1 else None
    if paper_id is None:
        return None
    return _hint_block(
        "Hint: materialize this paper as a local Gaia package:",
        f"gaia pkg add --lkm-index {index_id} --lkm-paper {paper_id}",
    )


def _hint_block(title: str, command: str) -> str:
    return f"{title}\n  {command}"


def _variables(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _dict(payload.get("data"))
    raw = data.get("variables", payload.get("variables"))
    return [item for item in _list(raw) if isinstance(item, dict)]


def _claim_id_for_reasoning(variable: dict[str, Any]) -> str | None:
    if _text(variable.get("type")) != "claim":
        return None
    if variable.get("has_reasoning") is not True:
        return None
    return _text(variable.get("id")) or _text(variable.get("global_id"))


def _paper_id_from_variable(variable: dict[str, Any]) -> str | None:
    for key in ("source_package", "package_id", "paper_id", "local_id"):
        if paper_id := _paper_id_from_any(variable.get(key)):
            return paper_id
    provenance = _dict(variable.get("provenance"))
    representative = _dict(provenance.get("representative_lcn"))
    for key in ("package_id", "local_id"):
        if paper_id := _paper_id_from_any(representative.get(key)):
            return paper_id
    for source_package in _list(provenance.get("source_packages")):
        if paper_id := _paper_id_from_any(source_package):
            return paper_id
    return None


def _paper_id_from_reasoning(payload: dict[str, Any]) -> str | None:
    for chain in _reasoning_chains(payload):
        for key in ("source_package", "paper_id"):
            if paper_id := _paper_id_from_any(chain.get(key)):
                return paper_id
        graph = _dict(chain.get("graph"))
        for node in _list(graph.get("nodes")):
            if not isinstance(node, dict):
                continue
            for key in ("id", "local_id"):
                if paper_id := _paper_id_from_any(node.get(key)):
                    return paper_id
    return _paper_id_from_papers(payload)


def _reasoning_chains(payload: dict[str, Any]) -> list[dict[str, Any]]:
    data = _dict(payload.get("data"))
    raw = data.get("reasoning_chains")
    return [item for item in _list(raw) if isinstance(item, dict)]


def _paper_id_from_papers(payload: dict[str, Any]) -> str | None:
    paper_ids = _paper_ids_from_papers(payload)
    return paper_ids[0] if paper_ids else None


def _paper_ids_from_papers(payload: dict[str, Any]) -> list[str]:
    data = _dict(payload.get("data"))
    raw = data.get("papers", payload.get("papers"))
    if isinstance(raw, dict):
        values: list[Any] = list(raw.values())
        values.extend(raw.keys())
    else:
        values = _list(raw)
    paper_ids: list[str] = []
    for item in values:
        paper_id = _paper_id_from_paper_item(item)
        if paper_id is not None and paper_id not in paper_ids:
            paper_ids.append(paper_id)
    return paper_ids


def _paper_id_from_paper_item(item: Any) -> str | None:
    if isinstance(item, str):
        return _paper_id_from_any(item)
    if not isinstance(item, dict):
        return None
    paper = _dict(item.get("paper")) or item
    for key in ("id", "package_id", "local_id"):
        if paper_id := _paper_id_from_any(paper.get(key)):
            return paper_id
    return None


def _paper_id_from_any(value: Any) -> str | None:
    text = _text(value)
    if text is None:
        return None
    if text.startswith("paper:"):
        paper_id = text.split("::", 1)[0].split(":", 1)[1]
        return paper_id or None
    return text if text.isdigit() else None


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
