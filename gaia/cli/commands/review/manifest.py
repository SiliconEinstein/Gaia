# ruff: noqa: RUF001, RUF002, RUF003, D415, B904, E501, D412, D301, C420
"""gaia review manifest — 查看和更新 ReviewManifest 审查状态。

这是 gaia review 的核心命令，提供对编译后推理步骤的逐条审查能力。
系统为每个 derive/observe/compute/infer/equal/contradict/exclusive/decompose
自动生成审查问题(audit_question)，审查者通过本命令标记
ACCEPTED/REJECTED/NEEDS_INPUTS 并附加审查笔记。

设计原则：
- 审查结果持久化到 .gaia/review_manifest.json
- 每次审查递增 round 编号
- 支持 list/show/accept/reject/needs-inputs 五种操作
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import typer

from gaia.engine.inquiry.review_manifest import (
    REVIEW_MANIFEST_REL_PATH,
    latest_reviews,
    load_or_generate_review_manifest,
)
from gaia.engine.ir import Review, ReviewManifest, ReviewStatus
from gaia.engine.packaging import (
    GaiaPackagingError,
    apply_package_priors,
    compile_loaded_package_artifact,
    ensure_package_env,
    load_gaia_package,
)

manifest_app = typer.Typer(
    name="manifest",
    help="Review and update action audit records (list / show / accept / reject / needs-inputs).",
    no_args_is_help=True,
)


def _utcnow_iso() -> str:
    return datetime.now(tz=UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def _load_compiled(project_dir: Path) -> Any:
    """编译知识包并返回 compiled artifact。"""
    ensure_package_env(project_dir)
    loaded = load_gaia_package(str(project_dir))
    apply_package_priors(loaded)
    return loaded, compile_loaded_package_artifact(loaded)


def _load_manifest(project_dir: Path) -> tuple[ReviewManifest, Path]:
    """加载或生成 ReviewManifest，返回 (manifest, file_path)。"""
    loaded, compiled = _load_compiled(project_dir)
    manifest = load_or_generate_review_manifest(loaded.pkg_path, compiled)
    manifest_path = project_dir / REVIEW_MANIFEST_REL_PATH
    return manifest, manifest_path


def _save_manifest(manifest: ReviewManifest, manifest_path: Path) -> None:
    """持久化 ReviewManifest 到 .gaia/review_manifest.json。"""
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    data = manifest.model_dump(mode="json")
    tmp = manifest_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(manifest_path)


def _find_review_by_label(reviews: list[Review], label: str) -> Review | None:
    """通过 action_label 查找审查记录（支持模糊匹配）。"""
    # 精确匹配
    for r in reviews:
        if r.action_label == label:
            return r
    # 后缀匹配（去掉 namespace 前缀）
    for r in reviews:
        short = r.action_label.split("::")[-1] if "::" in r.action_label else r.action_label
        if short == label:
            return r
    # 包含匹配
    for r in reviews:
        if label in r.action_label:
            return r
    return None


# ---------------------------------------------------------------------------
# list — 列出所有审查记录
# ---------------------------------------------------------------------------


@manifest_app.command("list")
def manifest_list(
    path: str = typer.Argument(".", help="Path to Gaia package"),
    status_filter: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status: unreviewed/accepted/rejected/needs_inputs",
    ),
    format: str = typer.Option("text", "--format", "-f", help="Output format: text or json"),
    brief: bool = typer.Option(
        False, "--brief", "-b", help="Brief mode: only AQ + status, no context"
    ),
) -> None:
    """List all reviewable actions with causal context from all review layers.

    Each review item shows:
    - Audit question and current status
    - Related structural findings (from inquiry diagnostics)
    - Belief shift context (from calibration Δ)
    - Causal chain (auto-derived)
    - Risk level (high/medium/low)

    Use --brief for the old compact view without context.

    Example:

        gaia review manifest list
        gaia review manifest list --status unreviewed
        gaia review manifest list --brief
        gaia review manifest list --format json
    """
    project_dir = Path(path).resolve()

    try:
        manifest, _ = _load_manifest(project_dir)
    except (GaiaPackagingError, Exception) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    all_reviews = latest_reviews(manifest)

    # 过滤
    filtered_reviews = all_reviews
    if status_filter:
        try:
            target_status = ReviewStatus(status_filter)
        except ValueError:
            typer.echo(
                f"Error: invalid status '{status_filter}'. "
                f"Valid: {', '.join(s.value for s in ReviewStatus)}",
                err=True,
            )
            raise typer.Exit(2)
        filtered_reviews = [r for r in filtered_reviews if r.status == target_status]

    # 统计（总是基于全部，不是过滤后的）
    counts = {s: 0 for s in ReviewStatus}
    for r in all_reviews:
        counts[r.status] += 1
    total = sum(counts.values())
    reviewed = total - counts[ReviewStatus.UNREVIEWED]
    coverage = (reviewed / total * 100) if total > 0 else 0

    # Brief 模式或 JSON 模式不需要合成
    if brief or format == "json":
        if format == "json":
            data = [r.model_dump(mode="json") for r in filtered_reviews]
            print(json.dumps(data, ensure_ascii=False, indent=2))
            return
        _print_brief_list(filtered_reviews, counts, total, reviewed, coverage)
        return

    # 完整模式：合成三层 context
    try:
        enriched_items = _build_enriched_items(project_dir, manifest)

        # 过滤
        if status_filter:
            target_status = ReviewStatus(status_filter)
            enriched_items = [
                item for item in enriched_items if item.review.status == target_status
            ]
    except Exception:
        # 合成失败时 fallback 到 brief 模式
        typer.echo("(无法合成因果 context，回退到简要模式)", err=True)
        _print_brief_list(filtered_reviews, counts, total, reviewed, coverage)
        return

    _print_enriched_list(enriched_items, counts, total, reviewed, coverage)


def _build_enriched_items(project_dir: Path, manifest: ReviewManifest) -> list[Any]:
    """运行 inquiry review + calibration，合成 EnrichedReviewItem。"""
    from gaia.engine.inquiry.review import run_review as run_inquiry_review
    from gaia.engine.review.calibration import compute_calibration_deltas
    from gaia.engine.review.synthesis import synthesize_review_items

    # 编译获取 graph
    _, compiled = _load_compiled(project_dir)

    # 运行 inquiry review 获取 diagnostics
    inquiry_report = run_inquiry_review(project_dir, mode="auto", no_infer=False)

    # 运行 calibration 获取完整 Δ 集（top_k=None），否则大包里多数审查项会
    # 静默丢失 belief context 并被低估风险等级。
    computation = compute_calibration_deltas(project_dir, top_k=None)

    # 合成
    return synthesize_review_items(
        manifest=manifest,
        diagnostics=list(inquiry_report.diagnostics),
        calibration_deltas=computation.deltas,
        graph=compiled.graph,
    )


def _print_brief_list(
    reviews: list[Review],
    counts: dict[ReviewStatus, int],
    total: int,
    reviewed: int,
    coverage: float,
) -> None:
    """Brief 模式：只显示 AQ + status。"""
    status_icon = {
        ReviewStatus.UNREVIEWED: "·",
        ReviewStatus.ACCEPTED: "✓",
        ReviewStatus.REJECTED: "✗",
        ReviewStatus.NEEDS_INPUTS: "?",
    }

    typer.echo(f"\nReview Coverage: {reviewed}/{total} ({coverage:.0f}%)")
    typer.echo(
        f"  ✓ {counts[ReviewStatus.ACCEPTED]}  "
        f"✗ {counts[ReviewStatus.REJECTED]}  "
        f"? {counts[ReviewStatus.NEEDS_INPUTS]}  "
        f"· {counts[ReviewStatus.UNREVIEWED]}"
    )
    typer.echo("")

    for i, r in enumerate(reviews, 1):
        icon = status_icon.get(r.status, "·")
        short_label = r.action_label.split("::")[-1] if "::" in r.action_label else r.action_label
        typer.echo(f"  {icon} [{r.status.value:13}] {short_label}")
        typer.echo(f"    AQ: {r.audit_question}")
        if r.reviewer_notes:
            typer.echo(f"    Notes: {r.reviewer_notes}")
        if i < len(reviews):
            typer.echo("")


def _print_enriched_list(
    items: list[Any],
    counts: dict[ReviewStatus, int],
    total: int,
    reviewed: int,
    coverage: float,
) -> None:
    """完整模式：显示每个审查项的因果 context。"""
    status_icon = {
        ReviewStatus.UNREVIEWED: "·",
        ReviewStatus.ACCEPTED: "✓",
        ReviewStatus.REJECTED: "✗",
        ReviewStatus.NEEDS_INPUTS: "?",
    }
    risk_icon = {"high": "✗", "medium": "⚠", "low": "✓"}

    typer.echo(f"\nReview Coverage: {reviewed}/{total} ({coverage:.0f}%)")
    typer.echo(
        f"  ✓ {counts[ReviewStatus.ACCEPTED]}  "
        f"✗ {counts[ReviewStatus.REJECTED]}  "
        f"? {counts[ReviewStatus.NEEDS_INPUTS]}  "
        f"· {counts[ReviewStatus.UNREVIEWED]}"
    )
    typer.echo("")

    for i, item in enumerate(items):
        r = item.review
        icon = status_icon.get(r.status, "·")
        r_icon = risk_icon.get(item.risk_level, "·")

        typer.echo(
            f"  {icon} [{r.status.value:13}] {item.action_label_short}  (risk: {r_icon} {item.risk_level})"
        )
        typer.echo(f"    AQ: {r.audit_question}")

        if r.reviewer_notes:
            typer.echo(f"    Notes: {r.reviewer_notes}")

        # Structural findings
        if item.structural_findings:
            typer.echo("    Context:")
            for sf in item.structural_findings:
                sev_icon = {"error": "✗", "warning": "⚠", "info": "ℹ"}.get(sf.severity, "·")
                typer.echo(f"      {sev_icon} {sf.message}")

        # Belief context
        if item.conclusion_belief and item.conclusion_belief.abs_delta > 0.01:
            bc = item.conclusion_belief
            typer.echo(
                f"      ⚠ Conclusion belief shift: {bc.label} "
                f"Δ={bc.delta:+.3f} ({bc.prior:.3f} → {bc.posterior:.3f})"
            )

        # Causal chain
        if item.causal_chain:
            chain_str = " → ".join(item.causal_chain)
            typer.echo(f"    Causal: {chain_str}")

        if i < len(items) - 1:
            typer.echo("")


# ---------------------------------------------------------------------------
# show — 展示单条审查记录的详情
# ---------------------------------------------------------------------------


@manifest_app.command("show")
def manifest_show(
    label: str = typer.Argument(..., help="Action label (or substring) to show"),
    path: str = typer.Option(".", help="Path to Gaia package"),
) -> None:
    """Show detailed info for a single reviewable action.

    Example:

        gaia review manifest show aristotle_daily_observation_path
        gaia review manifest show aristotle_paradox
    """
    project_dir = Path(path).resolve()

    try:
        manifest, _ = _load_manifest(project_dir)
    except (GaiaPackagingError, Exception) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    reviews = latest_reviews(manifest)
    review = _find_review_by_label(reviews, label)

    if review is None:
        typer.echo(f"Error: no review found matching '{label}'", err=True)
        typer.echo("Available actions:", err=True)
        for r in reviews:
            short = r.action_label.split("::")[-1] if "::" in r.action_label else r.action_label
            typer.echo(f"  - {short}", err=True)
        raise typer.Exit(1)

    print(json.dumps(review.model_dump(mode="json"), ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# accept — 标记审查为 ACCEPTED
# ---------------------------------------------------------------------------


@manifest_app.command("accept")
def manifest_accept(
    label: str = typer.Argument(..., help="Action label to accept"),
    notes: str = typer.Option(None, "--notes", "-n", help="Reviewer notes explaining acceptance"),
    path: str = typer.Option(".", help="Path to Gaia package"),
) -> None:
    """Mark an action as ACCEPTED after review.

    The reviewer has verified the reasoning step is valid.

    Example:

        gaia review manifest accept aristotle_daily_observation_path \\
            --notes "Premises are sufficient, observation path is well-grounded"
    """
    _update_status(path, label, ReviewStatus.ACCEPTED, notes)


# ---------------------------------------------------------------------------
# reject — 标记审查为 REJECTED
# ---------------------------------------------------------------------------


@manifest_app.command("reject")
def manifest_reject(
    label: str = typer.Argument(..., help="Action label to reject"),
    notes: str = typer.Option(None, "--notes", "-n", help="Reviewer notes explaining rejection"),
    path: str = typer.Option(".", help="Path to Gaia package"),
) -> None:
    """Mark an action as REJECTED after review.

    The reviewer has determined the reasoning step is invalid or flawed.

    Example:

        gaia review manifest reject aristotle_paradox \\
            --notes "The contradiction is not well-established; weight difference is insufficient"
    """
    _update_status(path, label, ReviewStatus.REJECTED, notes)


# ---------------------------------------------------------------------------
# needs-inputs — 标记审查为 NEEDS_INPUTS
# ---------------------------------------------------------------------------


@manifest_app.command("needs-inputs")
def manifest_needs_inputs(
    label: str = typer.Argument(..., help="Action label that needs more inputs"),
    notes: str = typer.Option(None, "--notes", "-n", help="Describe what inputs are needed"),
    path: str = typer.Option(".", help="Path to Gaia package"),
) -> None:
    """Mark an action as NEEDS_INPUTS — requires more information to decide.

    The reviewer cannot make a judgment without additional evidence,
    clarification, or computation results.

    Example:

        gaia review manifest needs-inputs medium_vacuum_equal_fall_prediction \\
            --notes "Need experimental data from vacuum chamber experiment"
    """
    _update_status(path, label, ReviewStatus.NEEDS_INPUTS, notes)


# ---------------------------------------------------------------------------
# 共用：状态更新逻辑
# ---------------------------------------------------------------------------


def _update_status(
    path: str,
    label: str,
    new_status: ReviewStatus,
    notes: str | None,
) -> None:
    """更新某条审查记录的状态，并持久化到磁盘。"""
    project_dir = Path(path).resolve()

    try:
        manifest, manifest_path = _load_manifest(project_dir)
    except (GaiaPackagingError, Exception) as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1)

    current_reviews = latest_reviews(manifest)
    target = _find_review_by_label(current_reviews, label)

    if target is None:
        typer.echo(f"Error: no review found matching '{label}'", err=True)
        typer.echo("Available actions:", err=True)
        for r in current_reviews:
            short = r.action_label.split("::")[-1] if "::" in r.action_label else r.action_label
            typer.echo(f"  - {short}", err=True)
        raise typer.Exit(1)

    old_status = target.status

    # 创建新的审查 round
    new_review = Review(
        review_id=target.review_id,
        action_label=target.action_label,
        target_kind=target.target_kind,
        target_id=target.target_id,
        status=new_status,
        audit_question=target.audit_question,
        reviewer_notes=notes,
        timestamp=_utcnow_iso(),
        round=target.round + 1,
    )

    # 追加到 manifest
    manifest.reviews.append(new_review)

    # 持久化
    _save_manifest(manifest, manifest_path)

    short_label = (
        target.action_label.split("::")[-1] if "::" in target.action_label else target.action_label
    )
    typer.echo(f"{short_label}: {old_status.value} → {new_status.value} (round {new_review.round})")
    if notes:
        typer.echo(f"  Notes: {notes}")
    typer.echo(f"  Saved to {manifest_path}")
