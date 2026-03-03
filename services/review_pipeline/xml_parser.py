"""XML parsing utilities for LLM outputs in the review pipeline.

Handles the messy reality of LLM-generated XML: markdown code fences,
unescaped special characters, and inconsistent formatting.
"""

from __future__ import annotations

import re

from lxml import etree

from services.review_pipeline.context import JoinTree

# ---------------------------------------------------------------------------
# XML cleaning helpers (adapted from reference xml_utils.py)
# ---------------------------------------------------------------------------

_MARKDOWN_CODE_BLOCK_RE = re.compile(r"```xml\s*(.*?)\s*```", re.DOTALL)

_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9:_\.\-]*"
    r"(\s+[A-Za-z_:][A-Za-z0-9_\-:.]*"
    r"(=(\"[^\"]*\"|'[^']*'|[^\s<>]+))?)*\s*/?>"
)

_ENTITY_RE = re.compile(r"&(?:[A-Za-z]+|#\d+|#x[0-9A-Fa-f]+);")


def _escape_raw(s: str) -> str:
    s = s.replace("&", "&amp;")
    s = s.replace("<", "&lt;")
    s = s.replace(">", "&gt;")
    s = s.replace('"', "&quot;")
    s = s.replace("'", "&apos;")
    return s


def _remove_xml_wrapper(text: str) -> str:
    """Strip markdown ````xml ... ``` `` fences if present."""
    m = _MARKDOWN_CODE_BLOCK_RE.search(text.strip())
    return m.group(1).strip() if m else text.strip()


def _md_text_to_xml(md_text: str) -> str:
    """Escape bare special characters in text segments while preserving XML tags."""
    md_text = _remove_xml_wrapper(md_text)
    result: list[str] = []
    last_end = 0

    for tag in _TAG_RE.finditer(md_text):
        start, end = tag.span()
        text_chunk = md_text[last_end:start]
        result.append(_escape_text_preserving_entities(text_chunk))
        result.append(tag.group(0))
        last_end = end

    result.append(_escape_text_preserving_entities(md_text[last_end:]))
    return "".join(result)


def _escape_text_preserving_entities(text: str) -> str:
    """Escape raw text but don't double-escape existing XML entities."""
    parts: list[str] = []
    pos = 0
    for ent in _ENTITY_RE.finditer(text):
        s, e = ent.span()
        parts.append(_escape_raw(text[pos:s]))
        parts.append(ent.group(0))
        pos = e
    parts.append(_escape_raw(text[pos:]))
    return "".join(parts)


def _parse_xml(text: str) -> etree._Element:
    """Clean LLM output and parse into an lxml Element."""
    cleaned = _md_text_to_xml(text)
    return etree.fromstring(cleaned.encode("utf-8"))


# ---------------------------------------------------------------------------
# Join (asymmetric) output parsing
# ---------------------------------------------------------------------------

# Maps (relation, direction) from XML to our JoinTree.relation vocabulary
_RELATION_MAP = {
    ("equivalence", None): "equivalent",
    ("subsumption", "candidate_more_specific"): "subsumed_by",
    ("subsumption", "anchor_more_specific"): "subsumes",
    ("contradiction", None): "contradiction",
}


def parse_join_output(xml_text: str, anchor_index: int) -> list[JoinTree]:
    """Parse asymmetric join XML into JoinTree objects.

    Args:
        xml_text: Raw LLM output (possibly wrapped in markdown fences).
        anchor_index: The ``source_node_index`` for every resulting tree.

    Returns:
        List of JoinTree for non-unrelated candidates.
    """
    root = _parse_xml(xml_text)
    trees: list[JoinTree] = []

    for cand in root.findall("candidate"):
        relation = (cand.get("relation") or "").strip().lower()
        if relation == "unrelated":
            continue

        direction = (cand.get("direction") or "").strip().lower() or None
        mapped = _RELATION_MAP.get((relation, direction))
        if mapped is None:
            continue

        try:
            target_id = int(cand.get("id", "0"))
        except ValueError:
            continue

        reason = (cand.findtext("reason") or "").strip()

        trees.append(
            JoinTree(
                source_node_index=anchor_index,
                target_node_id=target_id,
                relation=mapped,
                reasoning=reason,
            )
        )

    return trees


# ---------------------------------------------------------------------------
# Verify-join output parsing
# ---------------------------------------------------------------------------


def parse_verify_output(xml_text: str) -> dict:
    """Parse verify-join XML into a result dict.

    Returns:
        Dict with keys: ``passed`` (bool), ``checks`` (list[dict]),
        ``quality`` (dict with tightness, substantiveness, etc.).
    """
    root = _parse_xml(xml_text)

    result_text = (root.findtext("result") or "").strip().lower()
    passed = result_text == "pass"

    checks: list[dict] = []
    checks_elem = root.find("checks")
    if checks_elem is not None:
        for check in checks_elem.findall("check"):
            child_raw = check.get("child", "0")
            try:
                child_id = int(child_raw)
            except ValueError:
                child_id = 0
            checks.append(
                {
                    "child": child_id,
                    "entails_parent": check.get("entails_parent", "true").lower() == "true",
                    "reason": (check.findtext("reason") or "").strip(),
                }
            )

    quality: dict = {}
    qe = root.find("quality")
    if qe is not None:
        quality["classification_correct"] = (
            qe.findtext("classification_correct") or "true"
        ).strip().lower() == "true"
        quality["suggested_classification"] = (
            qe.findtext("suggested_classification") or ""
        ).strip()
        quality["union_error"] = (qe.findtext("union_error") or "false").strip().lower() == "true"
        quality["union_error_detail"] = (qe.findtext("union_error_detail") or "").strip()
        try:
            quality["tightness"] = int((qe.findtext("tightness") or "3").strip())
        except ValueError:
            quality["tightness"] = 3
        try:
            quality["substantiveness"] = int((qe.findtext("substantiveness") or "3").strip())
        except ValueError:
            quality["substantiveness"] = 3

    return {"passed": passed, "checks": checks, "quality": quality}
