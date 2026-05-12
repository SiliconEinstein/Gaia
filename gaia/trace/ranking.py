"""Rank ARM Trace diagnostics and next edits.

独立于 ``gaia.inquiry.ranking``，避免污染 inquiry 模式表（inquiry 测试要求
``supported_modes`` 集合精确等于 inquiry 那一套）。语义上完全平移 inquiry
的 ``rank_diagnostics`` / ``rank_next_edits``：

* ``mode`` 选 ``trace`` 或 ``publish``；后者把 warning 升级到 0 段排前。
* ``severity`` 是 tiebreaker：error < warning < info。
* 未知 kind 排最后，按 severity 排。
"""

from __future__ import annotations

from collections.abc import Callable

from gaia.inquiry.diagnostics import Diagnostic, NextEdit

# 与 ARM Trace v1 §1.4 优先级对齐：schema-violation 必前；hash chain /
# manifest hash 是抗作弊核心，紧随其后；causal / reference / observability
# 类按致命度递减。
_TRACE_KIND_ORDER: tuple[str, ...] = (
    "trace_schema_violation",
    "trace_hash_chain_broken",
    "trace_manifest_hash_mismatch",
    "trace_timestamp_disorder",
    "trace_seq_disorder",
    "decision_without_grounds",
    "tool_call_without_result",
    "unresolved_claim_ref",
    "retry_diverged",
    "orphan_event",
    "actor_switch_unexplained",
)

_MODE_RANK: dict[str, dict[str, int]] = {
    "trace": {kind: i for i, kind in enumerate(_TRACE_KIND_ORDER)},
    # publish 模式：与 trace 同表，但 warning 在排序键里被升级（_key 实现）
    "publish": {kind: i for i, kind in enumerate(_TRACE_KIND_ORDER)},
}

_SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}
_UNKNOWN_KIND_RANK = 99


def supported_modes() -> tuple[str, ...]:
    """Return the supported trace review ranking modes."""
    return tuple(_MODE_RANK.keys())


def _key(mode: str) -> Callable[[Diagnostic | NextEdit], tuple[int, int, str]]:
    table = _MODE_RANK.get(mode, _MODE_RANK["trace"])
    publish = mode == "publish"

    def _k(d: Diagnostic | NextEdit) -> tuple[int, int, str]:
        kind_rank = table.get(d.kind, _UNKNOWN_KIND_RANK)
        sev_rank = _SEVERITY_RANK.get(d.severity, 9)
        # publish：warning 与 error 同档（都是 0），保留 info 在后
        if publish and sev_rank == 1:
            sev_rank = 0
        return (kind_rank, sev_rank, d.kind)

    return _k


def rank_diagnostics(diags: list[Diagnostic], mode: str = "trace") -> list[Diagnostic]:
    """Rank diagnostics for trace or publish review mode."""
    return sorted(diags, key=_key(mode))


def rank_next_edits(edits: list[NextEdit], mode: str = "trace") -> list[NextEdit]:
    """Rank suggested next edits for trace or publish review mode."""
    return sorted(edits, key=_key(mode))
