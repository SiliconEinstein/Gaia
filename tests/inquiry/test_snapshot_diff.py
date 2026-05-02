"""Step 4 — snapshot persistence + semantic diff + Round A3 review_id."""

from __future__ import annotations

import json
import re
from pathlib import Path

from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.inquiry.diff import compute_semantic_diff
from gaia.inquiry.review import run_review
from gaia.inquiry.snapshot import (
    list_snapshots,
    mint_review_id,
    resolve_baseline,
    reviews_dir,
)
from gaia.inquiry.state import inquiry_dir

runner = CliRunner()

REVIEW_ID_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}Z_[a-zA-Z0-9]+_[A-Za-z0-9._-]+$")


def _write_pkg(
    pkg_dir: Path,
    name: str = "diff_pkg",
    *,
    extra_claim: str | None = None,
    prior: float = 0.7,
) -> None:
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "pyproject.toml").write_text(
        f'[project]\nname = "{name}-gaia"\nversion = "0.1.0"\n\n'
        '[tool.gaia]\nnamespace = "github"\ntype = "knowledge-package"\n',
        encoding="utf-8",
    )
    src = pkg_dir / name
    src.mkdir(exist_ok=True)
    body = (
        "from gaia.lang import claim, support\n"
        f'main = claim("main hypothesis", metadata={{"prior": {prior}}})\n'
        'evidence = claim("supporting evidence", metadata={"prior": 0.6})\n'
        "sup = support(premises=[evidence], conclusion=main)\n"
    )
    if extra_claim:
        body += f'extra = claim("{extra_claim}")\n'
        body += '__all__ = ["main", "evidence", "sup", "extra"]\n'
    else:
        body += '__all__ = ["main", "evidence", "sup"]\n'
    (src / "__init__.py").write_text(body, encoding="utf-8")


# --------------------------------------------------------------------------- #
# review_id format (Round A3)                                                 #
# --------------------------------------------------------------------------- #


def test_mint_review_id_format():
    rid = mint_review_id("7c1a9f23bc", "auto")
    assert REVIEW_ID_RE.match(rid), rid
    assert "_7c1a9f23_auto" in rid


def test_mint_review_id_no_hash_fallback():
    rid = mint_review_id(None, "publish")
    assert "_nohash_publish" in rid


def test_mint_review_id_sanitizes_mode():
    rid = mint_review_id("abcd1234", "weird/mode")
    assert "/" not in rid
    assert rid.endswith("_weirdmode")


def test_run_review_uses_round_a3_id(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    assert REVIEW_ID_RE.match(report.review_id), report.review_id


# --------------------------------------------------------------------------- #
# Snapshot persistence                                                        #
# --------------------------------------------------------------------------- #


def test_snapshot_written_after_review(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    path = reviews_dir(pkg) / f"{report.review_id}.json"
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["review_id"] == report.review_id
    assert payload["ir_hash"] == report.ir_hash
    assert "knowledges" in payload["ir"]


def test_list_snapshots_returns_newest_first(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    r1 = run_review(pkg, no_infer=True)
    # Mutate package so ir_hash differs and id collision is avoided.
    _write_pkg(pkg, extra_claim="another claim")
    r2 = run_review(pkg, no_infer=True)
    ids = list_snapshots(pkg)
    assert r1.review_id in ids and r2.review_id in ids
    assert ids[0] >= ids[-1]  # sorted newest-first


def test_state_remembers_last_review_id(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    report = run_review(pkg, no_infer=True)
    state_file = inquiry_dir(pkg) / "state.json"
    state = json.loads(state_file.read_text(encoding="utf-8"))
    assert state["last_review_id"] == report.review_id


# --------------------------------------------------------------------------- #
# Baseline resolution                                                         #
# --------------------------------------------------------------------------- #


def test_resolve_baseline_none(tmp_path):
    assert resolve_baseline(tmp_path, "none", "anything") is None


def test_resolve_baseline_last_uses_state(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    r = run_review(pkg, no_infer=True)
    assert resolve_baseline(pkg, "last", r.review_id) == r.review_id


def test_resolve_baseline_explicit_missing(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    run_review(pkg, no_infer=True)
    assert resolve_baseline(pkg, "no_such_id", None) is None


# --------------------------------------------------------------------------- #
# Semantic diff (compute_semantic_diff is the unit under test)                #
# --------------------------------------------------------------------------- #


def test_diff_first_review_is_empty(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    r = run_review(pkg, no_infer=True)
    assert r.semantic_diff.is_empty
    assert r.semantic_diff.baseline_review_id is None


def test_diff_added_claim_detected(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    run_review(pkg, no_infer=True)  # baseline
    _write_pkg(pkg, extra_claim="brand new claim")
    r2 = run_review(pkg, no_infer=True)
    assert "extra" in r2.semantic_diff.added_claims
    assert r2.semantic_diff.baseline_review_id is not None


def test_diff_prior_change_detected(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg, prior=0.7)
    run_review(pkg, no_infer=True)
    _write_pkg(pkg, prior=0.95)
    r2 = run_review(pkg, no_infer=True)
    priors = {d.label: (d.before, d.after) for d in r2.semantic_diff.changed_priors}
    assert "main" in priors
    assert priors["main"] == ("0.7", "0.95")


def test_diff_removed_claim_detected(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg, extra_claim="will be removed")
    run_review(pkg, no_infer=True)
    _write_pkg(pkg)  # extra dropped
    r2 = run_review(pkg, no_infer=True)
    assert "extra" in r2.semantic_diff.removed_claims


def test_diff_unit_compute_against_synthetic_snapshot():
    cur = {
        "knowledges": [
            {
                "id": "p::a",
                "type": "claim",
                "label": "a",
                "content": "X",
                "metadata": {"prior": 0.5},
            },
            {"id": "p::b", "type": "claim", "label": "b", "content": "new", "metadata": {}},
        ],
        "strategies": [],
        "operators": [],
    }
    base_snap = {
        "review_id": "r-base",
        "ir": {
            "knowledges": [
                {
                    "id": "p::a",
                    "type": "claim",
                    "label": "a",
                    "content": "X",
                    "metadata": {"prior": 0.3},
                },
                {"id": "p::c", "type": "claim", "label": "c", "content": "gone", "metadata": {}},
            ],
            "strategies": [],
        },
    }
    d = compute_semantic_diff(cur, base_snap)
    assert d.baseline_review_id == "r-base"
    assert "b" in d.added_claims
    assert "c" in d.removed_claims
    priors = {x.label: (x.before, x.after) for x in d.changed_priors}
    assert priors["a"] == ("0.3", "0.5")


# --------------------------------------------------------------------------- #
# CLI integration                                                             #
# --------------------------------------------------------------------------- #


def test_cli_review_emits_diff_section_after_second_run(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    r1 = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer"])
    assert r1.exit_code == 0
    _write_pkg(pkg, extra_claim="cli extra")
    r2 = runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer", "--json"])
    assert r2.exit_code == 0
    data = json.loads(r2.output)
    assert "extra" in data["semantic_diff"]["added_claims"]
    assert data["semantic_diff"]["baseline_review_id"] is not None


def test_cli_since_none_disables_baseline(tmp_path):
    pkg = tmp_path / "p"
    _write_pkg(pkg)
    runner.invoke(app, ["inquiry", "review", str(pkg), "--no-infer"])
    _write_pkg(pkg, extra_claim="ignored")
    r = runner.invoke(
        app,
        ["inquiry", "review", str(pkg), "--no-infer", "--since", "none", "--json"],
    )
    assert r.exit_code == 0
    data = json.loads(r.output)
    assert data["semantic_diff"]["baseline_review_id"] is None
    assert data["semantic_diff"]["added_claims"] == []
