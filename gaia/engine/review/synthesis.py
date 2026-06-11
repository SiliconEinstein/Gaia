# ruff: noqa: RUF002, RUF003, D102, D415, C901, ARG001
"""Review synthesis — 把 structural / probabilistic / manifest 三层数据合成为带因果链的审查项。

这是 gaia review 的核心：不是三层并列，而是一条因果联动的审查流水线。

    Structural (inquiry 14 detectors)
        ↓ findings
    Probabilistic (calibration Δ)
        ↓ enriched findings
    Manifest Synthesis
        ↓ 每个 audit question 附带因果 context
    Human/Agent Decision
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from gaia.engine.inquiry.diagnostics import Diagnostic
from gaia.engine.ir.review import Review, ReviewManifest
from gaia.engine.review._schemas import CalibrationDelta

# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #


@dataclass
class BeliefContext:
    """单个 claim 的信念 context：prior → posterior → Δ。"""

    claim_id: str
    label: str
    prior: float
    posterior: float
    delta: float

    @property
    def abs_delta(self) -> float:
        return abs(self.delta)


@dataclass
class StructuralFinding:
    """从 inquiry diagnostic 提取的、与某个审查项相关的结构性发现。"""

    kind: str  # prior_hole / blocked_warrant_path / orphaned_claim / ...
    severity: str  # error / warning / info
    message: str
    target: str  # 受影响的节点 ID


@dataclass
class EnrichedReviewItem:
    """manifest 审查项 + structural/probabilistic context + 因果链。

    审查者看到的不再是孤立的 audit question，
    而是附带完整 context 的审查项。
    """

    # 基本信息（来自 ReviewManifest）
    review: Review
    action_label_short: str  # 去掉 namespace 的简短 label

    # 结构层 context（来自 inquiry diagnostics）
    structural_findings: list[StructuralFinding] = field(default_factory=list)

    # 概率层 context（来自 calibration）
    conclusion_belief: BeliefContext | None = None
    premise_beliefs: list[BeliefContext] = field(default_factory=list)

    # 因果链（自动推导）
    causal_chain: list[str] = field(default_factory=list)

    # 风险等级（自动计算）
    risk_level: str = "low"  # high / medium / low


# --------------------------------------------------------------------------- #
# 因果链推导
# --------------------------------------------------------------------------- #


def _find_related_diagnostics(
    target_id: str,
    premises: list[str],
    conclusion: str | None,
    diagnostics: list[Diagnostic],
    labels: dict[str, str],
) -> list[StructuralFinding]:
    """找出与某个 strategy/operator 相关的 inquiry diagnostics。

    匹配规则：
    1. diagnostic.target 包含 strategy_id 本身
    2. diagnostic.target 包含 premise claim_id
    3. diagnostic.target 包含 conclusion claim_id
    """
    findings: list[StructuralFinding] = []
    match_ids = {target_id} | set(premises)
    if conclusion:
        match_ids.add(conclusion)

    for diag in diagnostics:
        diag_target = getattr(diag, "target", "") or ""
        # 检查是否与本审查项相关
        if any(mid in diag_target for mid in match_ids if mid):
            findings.append(
                StructuralFinding(
                    kind=diag.kind,
                    severity=diag.severity,
                    message=diag.message,
                    target=diag_target,
                )
            )

    return findings


def _build_belief_context(
    claim_id: str,
    labels: dict[str, str],
    delta_map: dict[str, CalibrationDelta],
) -> BeliefContext | None:
    """为一个 claim 构建 BeliefContext。"""
    delta = delta_map.get(claim_id)
    if delta is None:
        return None

    return BeliefContext(
        claim_id=claim_id,
        label=delta.claim_label,
        prior=delta.prior,
        posterior=delta.posterior,
        delta=delta.delta,
    )


def trace_causal_chain(
    target_id: str,
    premises: list[str],
    conclusion: str | None,
    structural_findings: list[StructuralFinding],
    conclusion_belief: BeliefContext | None,
    labels: dict[str, str],
) -> list[str]:
    """从一个 strategy 出发，追踪因果链。

    因果链逻辑：
    1. 前提有 prior_hole → 描述缺失
    2. 自身有 blocked_warrant_path → 推理路径被阻塞
    3. 结论有大 Δ → 信念异常偏移
    4. 前提有 orphaned_claim → 前提未被使用
    """
    chain: list[str] = []

    # 1. 前提问题
    for finding in structural_findings:
        if finding.kind == "prior_hole":
            # 找出是哪个前提缺 prior
            for premise_id in premises:
                if premise_id in finding.target:
                    label = labels.get(premise_id, premise_id.split("::")[-1])
                    chain.append(f"前提 {label} 没有 prior")
                    break

    # 2. Warrant path 问题
    for finding in structural_findings:
        if finding.kind == "blocked_warrant_path" and target_id in finding.target:
            chain.append("warrant path 被 block")
            break

    # 3. 结论信念异常
    if conclusion_belief and conclusion_belief.abs_delta > 0.05:
        label = labels.get(conclusion_belief.claim_id, conclusion_belief.label)
        chain.append(f"结论 {label} 信念 Δ={conclusion_belief.delta:+.3f}")

    return chain


def _compute_risk_level(
    structural_findings: list[StructuralFinding],
    conclusion_belief: BeliefContext | None,
    causal_chain: list[str],
) -> str:
    """基于 findings + delta + 因果链长度计算风险等级。

    high:   有 error 级 finding，或 |Δ| > 0.2，或因果链 ≥ 3 步
    medium: 有 warning 级 finding，或 |Δ| > 0.1，或因果链 ≥ 2 步
    low:    其他
    """
    has_error = any(f.severity == "error" for f in structural_findings)
    has_warning = any(f.severity == "warning" for f in structural_findings)
    abs_delta = conclusion_belief.abs_delta if conclusion_belief else 0.0

    if has_error or abs_delta > 0.2 or len(causal_chain) >= 3:
        return "high"
    if has_warning or abs_delta > 0.1 or len(causal_chain) >= 2:
        return "medium"
    return "low"


# --------------------------------------------------------------------------- #
# 主入口
# --------------------------------------------------------------------------- #


def _resolve_strategy_parts(
    strategy: Any,
) -> tuple[str, list[str], str | None]:
    """从 strategy 对象提取 (strategy_id, premises, conclusion)。"""
    sid = getattr(strategy, "strategy_id", None) or ""
    premises = list(getattr(strategy, "premises", []) or [])
    conclusion = getattr(strategy, "conclusion", None)
    return sid, premises, conclusion


def _resolve_operator_parts(
    operator: Any,
) -> tuple[str, list[str], str | None]:
    """从 operator 对象提取 (operator_id, variables, conclusion)。"""
    oid = getattr(operator, "operator_id", None) or ""
    variables = list(getattr(operator, "variables", []) or [])
    conclusion = getattr(operator, "conclusion", None)
    return oid, variables, conclusion


def synthesize_review_items(
    manifest: ReviewManifest,
    diagnostics: list[Diagnostic],
    calibration_deltas: list[CalibrationDelta],
    graph: Any,
) -> list[EnrichedReviewItem]:
    """把三层数据合成为带 context 的审查项。

    Args:
        manifest: ReviewManifest（审查记录列表）
        diagnostics: inquiry review 产出的 diagnostics
        calibration_deltas: calibration 产出的 Δ 列表
        graph: 编译后的 LocalCanonicalGraph

    Returns:
        按 risk_level 排序的 EnrichedReviewItem 列表（high 在前）
    """
    # 建索引
    labels: dict[str, str] = {}
    for knowledge in getattr(graph, "knowledges", []) or []:
        if knowledge.id:
            labels[knowledge.id] = knowledge.label or knowledge.id.split("::")[-1]

    delta_map: dict[str, CalibrationDelta] = {}
    for d in calibration_deltas:
        delta_map[d.claim_qid] = d

    # strategy_id → (premises, conclusion) 映射
    strategy_parts: dict[str, tuple[list[str], str | None]] = {}
    for strategy in getattr(graph, "strategies", []) or []:
        sid, premises, conclusion = _resolve_strategy_parts(strategy)
        if sid:
            strategy_parts[sid] = (premises, conclusion)

    # operator_id → (variables, conclusion) 映射
    operator_parts: dict[str, tuple[list[str], str | None]] = {}
    for operator in getattr(graph, "operators", []) or []:
        oid, variables, conclusion = _resolve_operator_parts(operator)
        if oid:
            operator_parts[oid] = (variables, conclusion)

    # 取每个 target_id 的最新 review
    latest: dict[str, Review] = {}
    for review in manifest.reviews:
        current = latest.get(review.target_id)
        if current is None or review.round > current.round:
            latest[review.target_id] = review

    # 为每个审查项合成 context
    items: list[EnrichedReviewItem] = []

    for target_id, review in latest.items():
        # 确定这个审查项对应的 premises 和 conclusion
        if review.target_kind == "strategy":
            parts = strategy_parts.get(target_id)
        elif review.target_kind == "operator":
            parts = operator_parts.get(target_id)
        else:
            parts = None

        premises = parts[0] if parts else []
        conclusion = parts[1] if parts else None

        # 简短 label
        short_label = review.action_label
        if "::" in short_label:
            short_label = short_label.split("::")[-1]

        # 1. 收集相关的 structural findings
        structural = _find_related_diagnostics(
            target_id,
            premises,
            conclusion,
            diagnostics,
            labels,
        )

        # 2. 收集 belief context
        conclusion_belief = (
            _build_belief_context(conclusion, labels, delta_map) if conclusion else None
        )
        premise_beliefs = [
            bc for p in premises if (bc := _build_belief_context(p, labels, delta_map)) is not None
        ]

        # 3. 推导因果链
        causal_chain = trace_causal_chain(
            target_id,
            premises,
            conclusion,
            structural,
            conclusion_belief,
            labels,
        )

        # 4. 计算风险等级
        risk_level = _compute_risk_level(structural, conclusion_belief, causal_chain)

        items.append(
            EnrichedReviewItem(
                review=review,
                action_label_short=short_label,
                structural_findings=structural,
                conclusion_belief=conclusion_belief,
                premise_beliefs=premise_beliefs,
                causal_chain=causal_chain,
                risk_level=risk_level,
            )
        )

    # 按 risk_level 排序：high > medium > low
    risk_order = {"high": 0, "medium": 1, "low": 2}
    items.sort(key=lambda item: (risk_order.get(item.risk_level, 3), item.action_label_short))

    return items
