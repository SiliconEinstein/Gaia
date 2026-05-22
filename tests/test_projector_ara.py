"""Tests for the spec §7 ARA → Gaia deterministic projector.

These tests exercise the projector against synthetic ARA hosts so the
detection rules, claim/evidence/related-work parsing, and source-map
shape can be tested without depending on a real ResNet-style artifact.

Two acceptance criteria are load-bearing:

1. **Determinism**: same inputs ⇒ byte-stable generated files +
   source-map records. This is what spec §11 demands.

2. **Conservatism**: the projector must never emit
   ``derive`` / ``infer`` / ``equal`` / ``contradict`` / ``exclusive``
   on its own. This is what spec §2.2 demands. The test enforces it by
   scanning the generated Python source for forbidden DSL verbs.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gaia.cli.main import app
from gaia.engine.projector import HostKind, detect_host_kind, project_host, render_source_map

pytestmark = pytest.mark.pr_gate


def _run_gaia(*args: str) -> str:
    runner = CliRunner()
    result = runner.invoke(app, list(args))
    if result.exit_code != 0:
        raise AssertionError(
            f"gaia {' '.join(args)} failed (rc={result.exit_code}):\n"
            f"output:\n{result.output}\n"
            f"exception: {result.exception}"
        )
    return result.output


@pytest.fixture()
def fake_ara(tmp_path: Path) -> Path:
    """A synthetic ARA-shaped host with claims, evidence, related work."""
    host = tmp_path / "fake-ara"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\nAbstract.\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text(
        "# Claims\n\n"
        "## C01: First claim text.\n"
        "Status: supported\n"
        "Proof: [E01]\n\n"
        "## C02: Second claim text.\n"
        "Status: refuted\n"
        "Proof: [E01, E02]\n"
    )
    (host / "logic" / "related_work.md").write_text(
        "# Related work\n\n## RW01: Highway networks\nType: refutes\nIDs: [arXiv:1505.00387]\n"
    )
    (host / "evidence").mkdir()
    (host / "evidence" / "tables").mkdir()
    (host / "evidence" / "tables" / "table1.md").write_text("| a | b |\n| 1 | 2 |\n")
    return host


def test_detect_host_kind_ara(fake_ara: Path) -> None:
    """ARA detection fires on PAPER.md + logic/ together."""
    assert detect_host_kind(fake_ara) is HostKind.ARA


def test_detect_host_kind_requires_both_markers(tmp_path: Path) -> None:
    """A bare PAPER.md without logic/ is not enough to mark a host as ARA."""
    only_paper = tmp_path / "paper-only"
    only_paper.mkdir()
    (only_paper / "PAPER.md").write_text("# Paper\n")
    assert detect_host_kind(only_paper) is HostKind.GENERIC


def test_detect_host_kind_arm(tmp_path: Path) -> None:
    """arm_manifest.json alone is enough to mark a host as ARM."""
    host = tmp_path / "fake-arm"
    host.mkdir()
    (host / "arm_manifest.json").write_text('{"title": "demo", "version": "1"}')
    assert detect_host_kind(host) is HostKind.ARM


def test_ara_projector_emits_typed_modules(fake_ara: Path) -> None:
    """ARA projection writes claims/evidence/related_work modules."""
    result = project_host(fake_ara)
    paths = sorted(f.path for f in result.files)
    assert "gaia/from_ara/__init__.py" in paths
    assert "gaia/from_ara/claims.py" in paths
    assert "gaia/from_ara/evidence.py" in paths
    assert "gaia/from_ara/related_work.py" in paths


def test_ara_projector_is_conservative(fake_ara: Path) -> None:
    """Generated DSL never emits derive/infer/equal/contradict/exclusive (spec §2.2)."""
    result = project_host(fake_ara)
    forbidden = re.compile(r"\b(?:derive|infer|equal|contradict|exclusive)\s*\(", re.MULTILINE)
    for generated in result.files:
        if not generated.path.endswith(".py"):
            continue
        assert forbidden.search(generated.body) is None, (
            f"Projector generated a forbidden warrant in {generated.path}:\n{generated.body}"
        )


def test_ara_projector_records_refuted_claim_for_review(fake_ara: Path) -> None:
    """Refuted claims must be flagged for reviewer attention (spec §7.1)."""
    result = project_host(fake_ara)
    refuted_records = [
        r for r in result.source_map if r.source_id == "ARA:C02" and r.requires_review
    ]
    assert refuted_records, "refuted claim C02 must require review"
    assert any(r.extras.get("ara_status") == "refuted" for r in refuted_records)


def test_ara_projector_queue_seeds_warrant_upgrade_paths(fake_ara: Path) -> None:
    """Each Proof: [Exx] link seeds a queue item with infer/derive candidates."""
    result = project_host(fake_ara)
    depends_on_items = [q for q in result.queue if q.current_action == "depends_on"]
    assert depends_on_items
    for item in depends_on_items:
        assert set(item.candidate_actions) == {"infer", "derive"}


def test_ara_projector_is_deterministic(fake_ara: Path) -> None:
    """Same host ⇒ byte-identical generated files (spec §11 idempotence)."""
    first = project_host(fake_ara)
    second = project_host(fake_ara)
    assert [(f.path, f.body) for f in first.files] == [(f.path, f.body) for f in second.files]
    assert [r.to_json() for r in first.source_map] == [r.to_json() for r in second.source_map]


def test_ara_source_map_has_schema_version(fake_ara: Path) -> None:
    """``source_map.json`` must include schema_version + host_kind + projection_mode."""
    result = project_host(fake_ara)
    rendered = render_source_map(result, host=fake_ara, generated_at="2026-01-01T00:00:00Z")
    assert rendered["schema_version"] == 1
    assert rendered["host_kind"] == "ara"
    assert rendered["projection_mode"] == "scaffold"
    assert rendered["host_root"] == "."


def test_ara_end_to_end_through_cli(fake_ara: Path) -> None:
    """`gaia build init --embedded` on an ARA host produces a compilable package."""
    _run_gaia("build", "init", "--embedded", str(fake_ara), "--namespace", "example")
    manifest = fake_ara / "gaia" / "gaia.toml"
    assert manifest.exists()
    assert 'host_kind = "ara"' in manifest.read_text()

    _run_gaia("build", "compile", str(fake_ara))
    ir = json.loads((fake_ara / ".gaia" / "ir.json").read_text())
    labels = {k.get("label") for k in ir["knowledges"] if k.get("label")}
    assert "ara_c01" in labels
    assert "ara_c02" in labels
    assert "ara_rw_rw01" in labels


def test_ara_projector_separates_claim_heading_from_body(tmp_path: Path) -> None:
    """ARA projector should use ``heading`` as ``title`` and body as ``content``.

    The earlier draft duplicated the heading into both fields, losing
    the assertion text. This regression test pins the new behavior.
    """
    host = tmp_path / "ara-body"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text(
        "## C99: Short heading.\n"
        "Status: supported\n\n"
        "This is the actual scientific assertion body that the projector "
        "should put into the claim's content field.\n"
    )
    result = project_host(host)
    claims_module = next(f for f in result.files if f.path.endswith("claims.py"))
    body = claims_module.body
    # title= must carry the heading
    assert "title='Short heading.'" in body
    # The claim content must be the body paragraph, not the heading
    assert "actual scientific assertion body" in body


def test_ara_projector_picks_up_paper_frontmatter(tmp_path: Path) -> None:
    """PAPER.md frontmatter must be projected into a paper.py note."""
    host = tmp_path / "ara-paper"
    host.mkdir()
    (host / "PAPER.md").write_text("---\ntitle: My Paper\ndoi: 10.0/x\n---\n\nAbstract body.\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text("")  # ARA marker
    result = project_host(host)
    paper_module = next(f for f in result.files if f.path.endswith("paper.py"))
    body = paper_module.body
    assert "ara_paper" in body
    assert "Abstract body." in body
    assert "10.0/x" in body
    assert "My Paper" in body


def test_ara_projector_picks_up_problem_and_experiments(tmp_path: Path) -> None:
    """``logic/problem.md`` and ``logic/experiments.md`` project as notes."""
    host = tmp_path / "ara-narr"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text("")
    (host / "logic" / "problem.md").write_text("# Problem\nWhat we set out to solve.\n")
    (host / "logic" / "experiments.md").write_text("# Experiments\n- E01\n- E02\n")
    result = project_host(host)
    narrative = next(f for f in result.files if f.path.endswith("narrative.py"))
    body = narrative.body
    assert "ara_problem" in body
    assert "ara_experiments" in body
    assert "What we set out to solve" in body


def test_ara_projector_picks_up_trace_dead_ends(tmp_path: Path) -> None:
    """`trace/exploration_tree.yaml` dead_end nodes become trace.py notes."""
    host = tmp_path / "ara-trace"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text("")
    (host / "trace").mkdir()
    (host / "trace" / "exploration_tree.yaml").write_text(
        "- id: T01\n"
        "  dead_end: true\n"
        "  note: Tried this and it did not work.\n"
        "- id: T02\n"
        "  dead_end: false\n"
        "  note: This one worked.\n"
    )
    result = project_host(host)
    trace_module = next(f for f in result.files if f.path.endswith("trace.py"))
    body = trace_module.body
    assert "ara_trace_t01" in body
    assert "Tried this and it did not work." in body
    # Live (non-dead-end) branches must NOT be projected.
    assert "ara_trace_t02" not in body
    # A queue item must be raised so the reviewer can promote dead-ends.
    queue_kinds = [q.current_action for q in result.queue if q.queue_id.startswith("FQT")]
    assert queue_kinds, "dead_end should seed a queue item"


def test_ara_projector_parses_pipe_table_headers(tmp_path: Path) -> None:
    """Evidence pipe tables surface their column headers in observe(...) rationale."""
    host = tmp_path / "ara-table"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text("")
    (host / "evidence" / "tables").mkdir(parents=True)
    (host / "evidence" / "tables" / "t.md").write_text(
        "| Depth | Plain | Residual |\n"
        "| --- | --- | --- |\n"
        "| 18 | 27.9 | 27.9 |\n"
        "| 34 | 28.5 | 25.0 |\n"
    )
    result = project_host(host)
    evidence = next(f for f in result.files if f.path.endswith("evidence.py"))
    body = evidence.body
    # Headers should be visible in the generated observe(...) call.
    assert "Depth" in body
    assert "Plain" in body
    assert "Residual" in body
    # Row count too.
    assert "2 body rows" in body or "rows=2" in body


def test_ara_projector_refutes_seeds_contradict_candidates(tmp_path: Path) -> None:
    """``Refutes: [Cxx]`` should propose contradict in queue candidates."""
    host = tmp_path / "ara-refutes"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text(
        "## C01: Original claim.\n"
        "Status: supported\n\n"
        "## C02: Refuter.\n"
        "Status: supported\n"
        "Refutes: [C01]\n"
    )
    result = project_host(host)
    items = [q for q in result.queue if q.queue_id.startswith("FQC")]
    assert items
    # At least one item should propose contradict() as the upgrade.
    assert any("contradict" in q.candidate_actions for q in items)
    # And it should list C01 as something to contradict against.
    refuter = next(q for q in items if "C02" in q.source_id)
    assert any("C01" in ref for ref in refuter.source_refs)


def test_ara_projector_three_segment_chain_via_experiments(tmp_path: Path) -> None:
    """When experiments.md defines Exx, claim Proof: [Exx] links to the experiment.

    Verifies the Ara paper §2.2 forensic binding chain
    ``claims.md → experiments.md → /evidence/`` is materialised in
    the IR rather than collapsing claim → evidence directly.
    """
    host = tmp_path / "ara-chain"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text(
        "## C01: Residual nets converge faster.\n"
        "Status: supported\n"
        "Proof: [E01]\n\n"
        "Skip connections accelerate optimisation.\n"
    )
    (host / "logic" / "experiments.md").write_text(
        "## E01: ImageNet ResNet-18 vs Plain-18\n"
        "Verifies: [C01]\n"
        "Procedure: train both for 90 epochs\n"
        "Expected outcome: ResNet beats plain top-1\n"
        "Evidence: [evidence/tables/conv.md]\n"
    )
    (host / "evidence" / "tables").mkdir(parents=True)
    (host / "evidence" / "tables" / "conv.md").write_text("| a | b |\n| --- | --- |\n| 1 | 2 |\n")

    result = project_host(host)
    paths = sorted(f.path for f in result.files)
    assert "gaia/from_ara/experiments.py" in paths

    experiments_body = next(
        f.body for f in result.files if f.path.endswith("from_ara/experiments.py")
    )
    # Three-segment chain proof: experiment node exists, and it carries
    # a depends_on(experiment, given=[evidence]) for the second hop.
    assert "ara_experiment_e01" in experiments_body
    assert "ara_kind" in experiments_body
    assert "'verification_plan'" in experiments_body
    assert "depends_on(ara_experiment_e01" in experiments_body
    assert "ara_evidence_evidence_tables_conv" in experiments_body

    claims_body = next(f.body for f in result.files if f.path.endswith("from_ara/claims.py"))
    # First hop: claim → experiment (NOT claim → evidence as in two-segment fallback).
    assert "from .experiments import ara_experiment_e01" in claims_body
    assert "depends_on(ara_c01, given=[ara_experiment_e01]" in claims_body

    # The source_map records the chain shape and projection_rule.
    rules = {r.projection_rule for r in result.source_map}
    assert "ara.experiment_block.v1" in rules
    assert "ara.claim_proof_experiment_chain.v1" in rules
    # And the experiment carries its Verifies/Procedure/Expected/Evidence
    # in the source_map extras for downstream auditing.
    exp_records = [r for r in result.source_map if r.source_id.startswith("ARA:EXPERIMENT:")]
    assert exp_records and exp_records[0].extras["ara_verifies"] == ["C01"]
    assert exp_records[0].extras["ara_kind"] == "verification_plan"


def test_ara_projector_two_segment_fallback_without_experiments(tmp_path: Path) -> None:
    """When experiments.md is absent, the claim still links to an evidence placeholder.

    Backward-compatible behaviour for minimal ARA hosts that have not
    written experiments.md yet — the projector must not regress to
    "empty depends_on" or fabricate experiment names.
    """
    host = tmp_path / "ara-no-exp"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text(
        "## C01: Claim with proof but no experiments.md.\n"
        "Status: supported\nProof: [E01]\n\nBody.\n"
    )
    result = project_host(host)
    claims_body = next(f.body for f in result.files if f.path.endswith("from_ara/claims.py"))
    # Should still produce a two-segment link claim → evidence placeholder.
    assert "from .evidence import ara_evidence_e01" in claims_body
    assert "depends_on(ara_c01, given=[ara_evidence_e01]" in claims_body
    # And NOT pretend an experiment exists.
    assert "from .experiments import ara_experiment_e01" not in claims_body
    # The experiments module is still emitted (as a placeholder) so
    # the loader's import chain stays connected.
    experiments_body = next(
        f.body for f in result.files if f.path.endswith("from_ara/experiments.py")
    )
    assert "_ara_experiments_placeholder" in experiments_body


def test_ara_related_work_typed_edge_candidate_actions(tmp_path: Path) -> None:
    """Each `Type:` value seeds a tailored queue item per Ara paper §2.2.

    - `imports` / `extends` / `bounds` → `gaia_pkg_add` (dependency)
    - `baseline` → `baseline_regression_check`
    - `refutes` → `contradict`
    - unknown / missing → `gaia_pkg_add` fallback (`source_only` kind)
    """
    host = tmp_path / "ara-rw"
    host.mkdir()
    (host / "PAPER.md").write_text("# Paper\n")
    (host / "logic").mkdir()
    (host / "logic" / "claims.md").write_text("")
    (host / "logic" / "related_work.md").write_text(
        "## RW01: Refuter\nType: refutes\nIDs: [arXiv:1]\n\n"
        "## RW02: Importer\nType: imports\nIDs: [arXiv:2]\n\n"
        "## RW03: Extender\nType: extends\nIDs: [arXiv:3]\n\n"
        "## RW04: Constraint provider\nType: bounds\nIDs: [arXiv:4]\n\n"
        "## RW05: Baseline\nType: baseline\nIDs: [arXiv:5]\n\n"
        "## RW06: Untyped\nIDs: [arXiv:6]\n"
    )
    result = project_host(host)
    by_id = {q.source_id: q for q in result.queue}
    assert by_id["ARA:RW01"].candidate_actions[0] == "contradict"
    assert by_id["ARA:RW02"].candidate_actions[0] == "gaia_pkg_add"
    assert by_id["ARA:RW03"].candidate_actions[0] == "gaia_pkg_add"
    assert by_id["ARA:RW04"].candidate_actions[0] == "gaia_pkg_add"
    assert by_id["ARA:RW05"].candidate_actions[0] == "baseline_regression_check"
    # Untyped → source_only kind → gaia_pkg_add fallback.
    assert by_id["ARA:RW06"].candidate_actions[0] == "gaia_pkg_add"

    # The source_map carries the kind classification so downstream
    # tools can branch without re-parsing the raw Type string.
    rw_records = {r.source_id: r for r in result.source_map if r.source_id.startswith("ARA:RW")}
    assert rw_records["ARA:RW01"].extras["related_work_kind"] == "candidate_contradict"
    assert rw_records["ARA:RW02"].extras["related_work_kind"] == "dependency"
    assert rw_records["ARA:RW04"].extras["related_work_kind"] == "dependency_with_constraints"
    assert rw_records["ARA:RW05"].extras["related_work_kind"] == "baseline"
    assert rw_records["ARA:RW06"].extras["related_work_kind"] == "source_only"


def test_arm_projector_handles_minimal_manifest(tmp_path: Path) -> None:
    """ARM projection works on a manifest-only bundle (no knowledge/claims.json)."""
    host = tmp_path / "fake-arm"
    host.mkdir()
    (host / "arm_manifest.json").write_text(
        json.dumps({"title": "Demo ARM", "version": "0.1", "doi": "10.0/demo"})
    )
    result = project_host(host)
    assert result.host_kind is HostKind.ARM
    paths = sorted(f.path for f in result.files)
    assert "gaia/from_arm/manifest.py" in paths
    assert "gaia/from_arm/claims.py" in paths
