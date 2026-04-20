"""Formatting helpers for v6 strategy method payloads."""

from __future__ import annotations

import json
from typing import Any


def likelihood_score_by_id(ir: dict) -> dict[str, dict]:
    """Return likelihood score records keyed by score_id."""
    return {
        score["score_id"]: score
        for score in ir.get("likelihood_scores", [])
        if isinstance(score, dict) and score.get("score_id")
    }


def _format_scalar(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return value
    return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)


def _format_query(query: Any) -> str | None:
    if query is None:
        return None
    if isinstance(query, str):
        return query
    return json.dumps(query, sort_keys=True, ensure_ascii=False, default=str)


def _score_summary(score: dict | None) -> str | None:
    if not score:
        return None
    score_type = score.get("score_type")
    if not score_type or "value" not in score:
        return None
    return f"{score_type}={_format_scalar(score['value'])}"


def _score_for_ref(score_ref: str | None, scores_by_id: dict[str, dict]) -> dict | None:
    if not score_ref:
        return None
    return scores_by_id.get(score_ref)


def format_method_lines(
    strategy: dict,
    scores_by_id: dict[str, dict],
    *,
    indent: int = 0,
    include_rationale: bool = True,
) -> list[str]:
    """Format a v6 strategy method as plain, indented diagnostic lines."""
    method = strategy.get("method") or {}
    if not method:
        return []

    pad = " " * indent
    kind = method.get("kind")
    lines: list[str] = []

    if kind == "module_use":
        module_ref = method.get("module_ref")
        if module_ref:
            lines.append(f"{pad}method: {module_ref}")

        score_ref = (method.get("output_bindings") or {}).get("score")
        score = _score_for_ref(score_ref, scores_by_id)
        summary = _score_summary(score)
        if summary:
            lines.append(f"{pad}score: {summary}")
            query = _format_query(score.get("query"))
            if query:
                lines.append(f"{pad}query: {query}")
            if include_rationale and score.get("rationale"):
                lines.append(f"{pad}rationale: {score['rationale']}")
        elif score_ref:
            lines.append(f"{pad}score: {score_ref}")

    elif kind == "compute":
        function_ref = method.get("function_ref")
        if function_ref:
            lines.append(f"{pad}function: {function_ref}")

        output_ref = method.get("output")
        score = _score_for_ref(output_ref, scores_by_id)
        summary = _score_summary(score)
        if summary:
            lines.append(f"{pad}output: {summary}")
            query = _format_query(score.get("query"))
            if query:
                lines.append(f"{pad}query: {query}")
            if include_rationale and score.get("rationale"):
                lines.append(f"{pad}rationale: {score['rationale']}")
        elif output_ref:
            lines.append(f"{pad}output: {output_ref}")

    elif kind:
        lines.append(f"{pad}method: {kind}")

    return lines


def format_method_oneline(strategy: dict, scores_by_id: dict[str, dict]) -> str:
    """Format method details compactly for one-line strategy summaries."""
    lines = format_method_lines(
        strategy,
        scores_by_id,
        indent=0,
        include_rationale=False,
    )
    return "; ".join(lines)
