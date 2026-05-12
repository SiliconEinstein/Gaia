"""Persist trace review report snapshots under `.gaia/trace/reviews`."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gaia.trace.review import TraceReviewReport


def _default_dir() -> Path:
    return Path.cwd() / ".gaia" / "trace" / "reviews"


def save_trace_review_snapshot(
    report: TraceReviewReport,
    *,
    snapshot_dir: str | Path | None = None,
) -> Path:
    """Write a trace review JSON snapshot and return its path.

    与 inquiry snapshot 同样的目录布局，便于工具链统一遍历。
    """
    base = Path(snapshot_dir) if snapshot_dir else _default_dir()
    base.mkdir(parents=True, exist_ok=True)
    target = base / f"{report.trace_review_id}.json"
    target.write_text(
        json.dumps(report.to_json_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return target
