from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.inquiry.review import run_review
from gaia.engine.review.calibration import check_honesty, compute_calibration_deltas

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _copy_galileo(tmp_path: Path) -> Path:
    root = Path(__file__).resolve().parents[2]
    src = root / "examples" / "galileo-v0-5-gaia"
    dst = tmp_path / "galileo-v0-5-gaia"
    shutil.copytree(src, dst, ignore=shutil.ignore_patterns(".gaia", "__pycache__"))
    return dst


def _json_stdout(result) -> dict:
    return json.loads(result.stdout)


def test_review_status_json_reports_manifest_counts(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(app, ["review", "status", str(pkg), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["review_type"] == "status"
    assert payload["metadata"]["compile_status"] == "ok"
    assert payload["metadata"]["manifest"]["total"] > 0
    assert payload["metadata"]["manifest"]["unreviewed"] > 0


def test_review_node_json_includes_belief_context(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(
        app,
        ["review", "node", "daily_observation", "--path", str(pkg), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["node_kind"] == "claim"
    assert payload["belief"]["claim_label"] == "daily_observation"
    assert payload["belief"]["has_prior"] is True
    assert payload["belief"]["prior"] == pytest.approx(0.9)
    assert 0.0 <= payload["belief"]["posterior"] <= 1.0


def test_review_node_without_authored_prior_shows_posterior_only(tmp_path: Path) -> None:
    # aristotle_model is an independent claim with no register_prior -> MaxEnt.
    # It must still show a posterior, but with no invented prior / Δ.
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(
        app,
        ["review", "node", "aristotle_model", "--path", str(pkg), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["node_kind"] == "claim"
    assert payload["belief"]["has_prior"] is False
    assert payload["belief"]["prior"] is None
    assert payload["belief"]["delta"] is None
    assert 0.0 <= payload["belief"]["posterior"] <= 1.0


def test_review_red_team_scans_solution_artifact(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)
    solution = pkg / "FINAL_ANSWER.md"
    solution.write_text("This proof uses an axiom shortcut and sorry.", encoding="utf-8")

    result = runner.invoke(
        app,
        ["review", "red-team", str(pkg), "--solution", str(solution), "--format", "json"],
    )

    assert result.exit_code == 1, result.output
    payload = _json_stdout(result)
    assert payload["review_type"] == "redteam"
    assert payload["metadata"]["verdict"] == "vulnerable"
    assert any(finding["detector"] == "redteam_shortcut" for finding in payload["findings"])


def test_calibration_only_reports_explicit_priors(tmp_path: Path) -> None:
    # galileo registers exactly one explicit prior (daily_observation=0.9). The
    # neutral 0.5 display measure on derived / anon / helper variables must NOT
    # be reported as an authored prior.
    pkg = _copy_galileo(tmp_path)

    computation = compute_calibration_deltas(pkg, top_k=None)

    assert [d.claim_label for d in computation.deltas] == ["daily_observation"]
    assert computation.deltas[0].prior == pytest.approx(0.9)
    assert not any("_anon_" in d.claim_qid for d in computation.deltas)
    # galileo is small => exact junction tree: converged, no iterations.
    assert computation.is_exact is True
    assert computation.converged is True
    assert computation.iterations == 0
    assert computation.method_used == "jt"


def test_review_calibration_json_exposes_inference_metadata(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(app, ["review", "calibration", str(pkg), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["method_used"] == "jt"
    assert payload["is_exact"] is True
    assert payload["converged"] is True
    assert payload["iterations"] == 0
    assert payload["metadata"]["reliable"] is True
    assert len(payload["top_deltas"]) == 1
    assert payload["top_deltas"][0]["claim_label"] == "daily_observation"


def test_gate_calibration_suppresses_unreliable_deltas(monkeypatch: pytest.MonkeyPatch) -> None:
    # An approximate run that did not converge must NOT surface large-delta
    # warnings as authoritative; the gate emits a single reliability warning.
    from gaia.engine.review import gate as gate_mod
    from gaia.engine.review._schemas import CalibrationDelta, CalibrationReport

    unreliable = CalibrationReport(
        review_id="rid",
        created_at="2026-01-01T00:00:00Z",
        path="/tmp/pkg",
        converged=False,
        iterations=200,
        method_used="trw_bp",
        is_exact=False,
        top_deltas=[
            CalibrationDelta(
                claim_qid="q::c",
                claim_label="c",
                prior=0.5,
                posterior=0.9,
                delta=0.4,
                abs_delta=0.4,
            )
        ],
        honesty_check=None,
        metadata={"reliable": False},
    )
    monkeypatch.setattr(gate_mod, "run_calibration_review", lambda *_a, **_k: unreliable)

    report = gate_mod.run_gate_review("/tmp/pkg", "calibration")

    detectors = {f.detector for f in report.findings}
    assert "gate_calibration_unreliable" in detectors
    assert "gate_calibration" not in detectors
    assert report.metadata["components"]["calibration"]["reliable"] is False


def test_review_package_no_infer_skips_calibration(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(
        app, ["review", "package", str(pkg), "--no-infer", "--format", "json"]
    )

    assert result.exit_code in (0, 1), result.output
    payload = _json_stdout(result)
    # --no-infer means "skip BP"; calibration is a BP run and must be skipped too.
    assert "calibration" not in payload["metadata"]


def test_review_gate_calibration_json(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(
        app,
        ["review", "gate", "calibration", str(pkg), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["review_type"] == "gate"
    assert payload["metadata"]["gate"] == "calibration"
    assert "calibration" in payload["metadata"]["component_statuses"]


def test_review_query_missing_priors_json(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)

    result = runner.invoke(
        app,
        ["review", "query", "missing-priors", str(pkg), "--format", "json"],
    )

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["review_type"] == "query"
    assert payload["metadata"]["query"] == "missing-priors"


def test_review_report_writes_markdown(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)
    output = tmp_path / "review.md"

    result = runner.invoke(
        app,
        ["review", "report", str(pkg), "--no-infer", "--output", str(output)],
    )

    assert result.exit_code == 0, result.output
    assert output.exists()
    assert output.read_text(encoding="utf-8").startswith("# Gaia Review Report:")


def test_check_honesty_scans_all_python_diffs(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        calls.append(cmd)
        if cmd[:3] == ["git", "rev-parse", "--git-dir"]:
            return subprocess.CompletedProcess(cmd, 0, stdout=".git\n", stderr="")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=(
                "diff --git a/src/pkg/priors.py b/src/pkg/priors.py\n"
                "+register_prior(claim, value=0.8, justification='new')\n"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = check_honesty(tmp_path)

    assert result is not None
    assert result["status"] == "suspicious"
    assert ["git", "diff", "HEAD", "--", "*.py"] in calls


def test_review_diff_reports_added_claim_since_last_review(tmp_path: Path) -> None:
    pkg = _copy_galileo(tmp_path)
    run_review(pkg, no_infer=True)

    source = pkg / "src" / "galileo_v0_5" / "__init__.py"
    source.write_text(
        source.read_text(encoding="utf-8")
        + '\nextra_review_claim = claim("An extra review diff claim.")\n'
        + '__all__.append("extra_review_claim")\n',
        encoding="utf-8",
    )

    result = runner.invoke(app, ["review", "diff", str(pkg), "--format", "json"])

    assert result.exit_code == 0, result.output
    payload = _json_stdout(result)
    assert payload["review_type"] == "diff"
    assert payload["status"] == "warning"
    assert payload["metadata"]["semantic_diff"]["added_claims"]
