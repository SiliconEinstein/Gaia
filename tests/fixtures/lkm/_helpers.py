"""Shared helpers for constructing LKM fixture data."""

from __future__ import annotations

import hashlib

from gaia.lkm.models import LocalFactorNode, LocalVariableNode, Step, compute_content_hash


def var(
    label: str,
    content: str,
    package: str,
    type_: str = "claim",
    visibility: str = "public",
    namespace: str = "reg",
) -> LocalVariableNode:
    """Construct a LocalVariableNode with auto-computed content_hash."""
    qid = f"{namespace}:{package}::{label}"
    ch = compute_content_hash(type_, content, [])
    return LocalVariableNode(
        id=qid,
        type=type_,
        visibility=visibility,
        content=content,
        content_hash=ch,
        parameters=[],
        source_package=package,
    )


def _lfac_id(package: str, name: str) -> str:
    """Deterministic local factor ID from package + name."""
    payload = f"{package}|{name}"
    return f"lfac_{hashlib.sha256(payload.encode()).hexdigest()[:16]}"


def strategy(
    name: str,
    premises: list[str],
    conclusion: str,
    package: str,
    subtype: str = "infer",
    background: list[str] | None = None,
    steps: list[Step] | None = None,
) -> LocalFactorNode:
    """Construct a strategy LocalFactorNode."""
    return LocalFactorNode(
        id=_lfac_id(package, name),
        factor_type="strategy",
        subtype=subtype,
        premises=premises,
        conclusion=conclusion,
        background=background,
        steps=steps,
        source_package=package,
    )


def operator(
    name: str,
    variables: list[str],
    conclusion: str,
    package: str,
    subtype: str = "contradiction",
) -> LocalFactorNode:
    """Construct an operator LocalFactorNode."""
    return LocalFactorNode(
        id=_lfac_id(package, name),
        factor_type="operator",
        subtype=subtype,
        premises=variables,
        conclusion=conclusion,
        source_package=package,
    )
