"""Gaia-owned LKM request policy.

Apifox is the source of truth for endpoint parameters and response shapes.
This module captures Gaia CLI's consumer-owned defaults and request-body
construction so those choices do not live in Typer command plumbing.
"""

from __future__ import annotations

from typing import Any

DEFAULT_SEARCH_SORT_BY = "comprehensive"
DEFAULT_LIMIT_PUBLICATION_DATE = True


def build_knowledge_search_body(
    *,
    query: str,
    retrieval_mode: str,
    sort_by: str,
    offset: int,
    limit: int,
    scopes: list[str] | None,
    keywords: list[str] | None,
    reasoning_only: bool,
    include_paper_enrich: bool,
    visibility: str,
    role: str | None,
    paper_ids: list[str] | None,
    dois: list[str] | None,
    title: str | None,
    publication_date_start: str | None,
    publication_date_end: str | None,
    limit_publication_date: bool,
) -> dict[str, Any]:
    """Build Gaia's POST /search body."""
    body: dict[str, Any] = {
        "query": query,
        "retrieval_mode": retrieval_mode,
        "offset": offset,
        "limit": limit,
        "sort_by": sort_by,
    }
    if scopes:
        body["scopes"] = scopes
    if keywords:
        body["keywords"] = list(keywords)
    if reasoning_only:
        body["reasoning_only"] = True
    if include_paper_enrich:
        body["include_paper_enrich"] = True
    body["filters"] = build_lkm_filters(
        visibility=visibility,
        role=role,
        paper_ids=paper_ids,
        dois=dois,
        title=title,
        publication_date_start=publication_date_start,
        publication_date_end=publication_date_end,
        limit_publication_date=limit_publication_date,
    )
    return body


def build_reasoning_search_body(
    *,
    query: str,
    retrieval_mode: str,
    sort_by: str,
    offset: int,
    limit: int,
    keywords: list[str] | None,
    paper_ids: list[str] | None,
    dois: list[str] | None,
    title: str | None,
    publication_date_start: str | None,
    publication_date_end: str | None,
    limit_publication_date: bool,
) -> dict[str, Any]:
    """Build Gaia's POST /reasoning/search body."""
    body: dict[str, Any] = {
        "query": query,
        "format": "graph",
        "retrieval_mode": retrieval_mode,
        "sort_by": sort_by,
        "offset": offset,
        "limit": limit,
    }
    if keywords:
        body["keywords"] = list(keywords)
    filters = build_lkm_filters(
        visibility=None,
        role=None,
        paper_ids=paper_ids,
        dois=dois,
        title=title,
        publication_date_start=publication_date_start,
        publication_date_end=publication_date_end,
        limit_publication_date=limit_publication_date,
    )
    if filters:
        body["filters"] = filters
    return body


def build_lkm_filters(
    *,
    visibility: str | None,
    role: str | None,
    paper_ids: list[str] | None,
    dois: list[str] | None,
    title: str | None,
    publication_date_start: str | None,
    publication_date_end: str | None,
    limit_publication_date: bool,
) -> dict[str, Any]:
    """Build shared LKM filters using Gaia's explicit-default policy."""
    filters: dict[str, Any] = {}
    optional_fields: tuple[tuple[str, Any], ...] = (
        ("visibility", visibility),
        ("role", role),
        ("paper_ids", list(paper_ids) if paper_ids else None),
        ("dois", list(dois) if dois else None),
        ("title", title),
        ("publication_date_start", publication_date_start),
        ("publication_date_end", publication_date_end),
    )
    filters.update({key: value for key, value in optional_fields if value})
    if not limit_publication_date:
        filters["limit_publication_date"] = False
    return filters


def build_feedback_body(
    *,
    feedback_type: str,
    content: str,
    gcn_id: str | None,
    paper_metadata_id: str | None,
) -> dict[str, Any]:
    """Build POST /feedback body after command-level validation."""
    body: dict[str, Any] = {"type": feedback_type, "content": content}
    if gcn_id:
        body["gcn_id"] = gcn_id
    if paper_metadata_id:
        body["paper_metadata_id"] = paper_metadata_id
    return body


__all__ = [
    "DEFAULT_LIMIT_PUBLICATION_DATE",
    "DEFAULT_SEARCH_SORT_BY",
    "build_feedback_body",
    "build_knowledge_search_body",
    "build_lkm_filters",
    "build_reasoning_search_body",
]
