"""ARM Trace — 7th modality of ARM v1 (4/27).

提供：
- Trace / TraceEvent / TraceManifest / ClaimRef pydantic schema
- canonical-json + sha256 hash chain（事件级抗作弊）
- 11 个确定性 detector（无 LLM 参与）
- TraceReviewReport 八段 review（与 gaia.inquiry 设计同质）
- run_trace_review(path, *, mode="trace") 端到端入口

目标：审计/debug/学习一段 ARM 执行轨迹时，给出可解释、可重算、不易作弊的报告。
"""

from gaia.engine.trace.diagnostics import TraceDiagnosticKind
from gaia.engine.trace.review import TraceReviewReport, run_trace_review
from gaia.engine.trace.schema import ClaimRef, Trace, TraceEvent, TraceManifest

__all__ = [
    "ClaimRef",
    "Trace",
    "TraceDiagnosticKind",
    "TraceEvent",
    "TraceManifest",
    "TraceReviewReport",
    "run_trace_review",
]
