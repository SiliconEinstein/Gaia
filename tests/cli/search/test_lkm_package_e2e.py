"""E2E coverage for materialized LKM paper packages."""

from __future__ import annotations

import json
import subprocess
import tomllib
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from gaia.cli.commands.pkg.lkm_materialize import materialize_lkm_paper_package
from gaia.cli.main import app
from gaia.engine.packaging import GaiaPackagingError

pytestmark = pytest.mark.pr_gate

runner = CliRunner()


def _paper_graph_payload() -> dict[str, Any]:
    return {
        "code": 0,
        "data": {
            "papers": [
                {
                    "paper": {
                        "doi": "10.1016/j.jpcs.2021.110374",
                        "en_abstract": "A generated fixture paper about FAPbI3 processing.",
                        "en_title": "Controlling phase and morphology",
                        "id": "811827932371615744",
                        "package_id": "paper:811827932371615744",
                    },
                    "variables": [
                        {
                            "content": "Which phase conversion pathway dominates?",
                            "global_id": "gq_phase",
                            "local_id": "paper:811827932371615744::Q1",
                            "type": "question",
                        }
                    ],
                    "factors": [
                        {
                            "conclusion": {
                                "content": "Annealing at 120 C improves alpha-phase purity.",
                                "global_id": "gcn_conclusion",
                                "local_id": "paper:811827932371615744::conclusion_1",
                                "type": "claim",
                            },
                            "factor_type": "strategy",
                            "global_id": "gfac_phase",
                            "local_id": "lfac_phase",
                            "premises": [
                                {
                                    "content": (
                                        "The 120 C condition increases alpha-FAPbI3 fraction."
                                    ),
                                    "global_id": "gcn_premise",
                                    "local_id": "paper:811827932371615744::P1",
                                    "type": "claim",
                                }
                            ],
                            "steps": [
                                {
                                    "reasoning": (
                                        "Use the measured phase fraction to support the "
                                        "annealing conclusion."
                                    ),
                                    "step_id": "1",
                                }
                            ],
                            "subtype": "noisy_and",
                        }
                    ],
                    "motivations": [],
                    "stats": {
                        "factors_total": 1,
                        "type_counts": {"claim": 2, "question": 1},
                        "variables_total": 3,
                    },
                }
            ]
        },
    }


def _write_consumer_package(
    root: Path,
    *,
    dependency: str,
    import_name: str,
    symbol: str,
    uv_source_path: Path | None = None,
) -> None:
    root.mkdir()
    uv_sources = ""
    if uv_source_path is not None:
        uv_sources = (
            f'\n[tool.uv.sources]\n"{dependency}" = {{ path = "{uv_source_path.as_posix()}" }}\n'
        )
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "lkm-consumer-gaia"\n'
        'version = "0.1.0"\n'
        f'dependencies = ["{dependency}"]\n\n'
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n'
        f"{uv_sources}",
        encoding="utf-8",
    )
    src = root / "lkm_consumer"
    src.mkdir()
    (src / "__init__.py").write_text(
        "from gaia.engine.lang import derive\n"
        f"from {import_name} import {symbol}\n\n"
        "referenced_lkm_claim = derive(\n"
        '    "A downstream Gaia package can cite the imported LKM paper claim.",\n'
        f"    given={symbol},\n"
        '    rationale="The local package cites the materialized LKM package.",\n'
        '    label="cite_lkm_paper",\n'
        ")\n\n"
        '__all__ = ["referenced_lkm_claim"]\n',
        encoding="utf-8",
    )


def _write_empty_gaia_package(root: Path) -> None:
    root.mkdir()
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "lkm-consumer-gaia"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n',
        encoding="utf-8",
    )


def _paper_graph_payload_with_skipped_factors() -> dict[str, Any]:
    payload = _paper_graph_payload()
    paper_item = payload["data"]["papers"][0]
    paper_item["factors"].extend(
        [
            {
                "conclusion": {
                    "content": "Which phase conversion pathway dominates?",
                    "global_id": "gq_phase",
                    "type": "question",
                },
                "global_id": "gfac_question_conclusion",
                "local_id": "lfac_question_conclusion",
                "premises": [
                    {
                        "content": "The 120 C condition increases alpha-FAPbI3 fraction.",
                        "global_id": "gcn_premise",
                        "type": "claim",
                    }
                ],
            },
            {
                "conclusion": {
                    "content": "Annealing at 120 C improves alpha-phase purity.",
                    "global_id": "gcn_conclusion",
                    "type": "claim",
                },
                "global_id": "gfac_question_premise",
                "local_id": "lfac_question_premise",
                "premises": [
                    {
                        "content": "Which phase conversion pathway dominates?",
                        "global_id": "gq_phase",
                        "type": "question",
                    }
                ],
            },
        ]
    )
    return payload


def test_materialized_lkm_package_can_be_imported_and_referenced(tmp_path: Path) -> None:
    materialized = materialize_lkm_paper_package(
        _paper_graph_payload(),
        project_root=tmp_path,
        index_id="bohrium",
        paper_id="811827932371615744",
    )
    assert materialized.exported_symbol is not None
    assert (materialized.root / ".gaia" / "manifests" / "premises.json").exists()
    generated_source = (
        materialized.root / "src" / materialized.import_name / "__init__.py"
    ).read_text()
    assert "from gaia.engine.lang import claim, depends_on, question" in generated_source
    assert "lfac_phase = depends_on(" in generated_source
    formalization = json.loads(
        (materialized.root / ".gaia" / "formalization_manifest.json").read_text()
    )
    assert formalization["dependencies"][0]["kind"] == "depends_on"
    assert formalization["dependencies"][0]["status"] == "unformalized"

    consumer = tmp_path / "consumer"
    _write_consumer_package(
        consumer,
        dependency=f"{materialized.dist_name} @ {materialized.root.as_uri()}",
        import_name=materialized.import_name,
        symbol=materialized.exported_symbol,
    )

    result = runner.invoke(app, ["build", "compile", str(consumer)])
    assert result.exit_code == 0, result.output

    ir = json.loads((consumer / ".gaia" / "ir.json").read_text())
    labels = {item.get("label") for item in ir["knowledges"]}
    qids = {item["id"] for item in ir["knowledges"]}
    assert "referenced_lkm_claim" in labels
    assert any(qid.startswith(f"lkm:{materialized.import_name}::") for qid in qids)


def test_materialized_lkm_package_can_be_imported_from_uv_sources(
    tmp_path: Path,
) -> None:
    materialized = materialize_lkm_paper_package(
        _paper_graph_payload(),
        project_root=tmp_path,
        index_id="bohrium",
        paper_id="811827932371615744",
    )
    assert materialized.exported_symbol is not None

    consumer = tmp_path / "consumer"
    _write_consumer_package(
        consumer,
        dependency=materialized.dist_name,
        import_name=materialized.import_name,
        symbol=materialized.exported_symbol,
        uv_source_path=Path("..") / ".gaia" / "lkm_packages" / materialized.dist_name,
    )

    result = runner.invoke(app, ["build", "compile", str(consumer)])
    assert result.exit_code == 0, result.output

    ir = json.loads((consumer / ".gaia" / "ir.json").read_text())
    assert any(
        item["id"].startswith(f"lkm:{materialized.import_name}::") for item in ir["knowledges"]
    )


def test_materialize_lkm_paper_rejects_mismatched_paper_id(tmp_path: Path) -> None:
    payload = _paper_graph_payload()
    paper = payload["data"]["papers"][0]["paper"]
    paper["id"] = "999"
    paper["package_id"] = "paper:999"

    with pytest.raises(GaiaPackagingError, match="requested paper id"):
        materialize_lkm_paper_package(
            payload,
            project_root=tmp_path,
            index_id="bohrium",
            paper_id="811827932371615744",
        )


def test_materialize_lkm_paper_counts_skipped_factors(tmp_path: Path) -> None:
    materialized = materialize_lkm_paper_package(
        _paper_graph_payload_with_skipped_factors(),
        project_root=tmp_path,
        index_id="bohrium",
        paper_id="811827932371615744",
    )

    assert materialized.dependency_count == 1
    assert materialized.skipped_factor_count == 2


def test_materialize_lkm_paper_writes_toml_basic_strings_for_unicode_metadata(
    tmp_path: Path,
) -> None:
    payload = _paper_graph_payload()
    payload["data"]["papers"][0]["paper"]["en_title"] = 'Unicode "quoted" title 🔬'

    materialized = materialize_lkm_paper_package(
        payload,
        project_root=tmp_path,
        index_id="bohrium",
        paper_id="811827932371615744",
    )

    pyproject = tomllib.loads((materialized.root / "pyproject.toml").read_text())
    assert pyproject["project"]["description"] == 'LKM paper package: Unicode "quoted" title 🔬'
    assert pyproject["tool"]["gaia"]["source"]["title"] == 'Unicode "quoted" title 🔬'


def test_pkg_add_lkm_paper_materializes_and_adds_editable_dependency(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gaia.cli.commands.add as add_mod

    consumer = tmp_path / "consumer"
    _write_consumer_package(
        consumer,
        dependency="",
        import_name="unused",
        symbol="unused",
    )
    (consumer / "pyproject.toml").write_text(
        "[project]\n"
        'name = "lkm-consumer-gaia"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n',
        encoding="utf-8",
    )

    def fake_run_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        index_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        assert method == "POST"
        assert path == "/papers/graph"
        assert json_body is not None
        assert json_body["paper_id"] == "811827932371615744"
        assert json_body["include"] == ["paper", "variables", "factors", "motivations"]
        assert index_id == "bohrium"
        return _paper_graph_payload()

    uv_calls: list[tuple[list[str], Path | None]] = []

    def fake_run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        uv_calls.append((args, kwargs.get("cwd")))
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(add_mod, "run_request", fake_run_request)
    monkeypatch.setattr(add_mod, "_run_uv", fake_run_uv)
    monkeypatch.chdir(consumer)

    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )

    assert result.exit_code == 0, result.output
    assert "Materialized lkm:bohrium:paper:811827932371615744" in result.output
    assert "Import hint: from lkm_bohrium_controlling_phase_and_morphology_811827932371615744" in (
        result.output
    )
    assert "1 depends_on scaffold dependencies" in result.output
    assert "unformalized counterpart of `derive(...)`" in result.output
    assert len(uv_calls) == 1
    uv_args, uv_cwd = uv_calls[0]
    assert uv_args[:3] == ["uv", "add", "--editable"]
    assert uv_cwd == consumer
    materialized_root = Path(uv_args[3])
    assert materialized_root.exists()
    assert (materialized_root / ".gaia" / "manifests" / "premises.json").exists()


def test_pkg_add_lkm_paper_warns_when_response_has_no_paper_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gaia.cli.commands.add as add_mod

    consumer = tmp_path / "consumer"
    _write_empty_gaia_package(consumer)

    def fake_run_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        index_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        del method, path, json_body, index_id
        payload = _paper_graph_payload()
        paper = payload["data"]["papers"][0]["paper"]
        paper.pop("id")
        paper.pop("package_id")
        return payload

    def fake_run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(add_mod, "run_request", fake_run_request)
    monkeypatch.setattr(add_mod, "_run_uv", fake_run_uv)
    monkeypatch.chdir(consumer)

    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )

    assert result.exit_code == 0, result.output
    assert "Warning: LKM response did not include a paper id" in result.output
    assert "811827932371615744" in result.output


def test_pkg_add_lkm_paper_warns_when_regenerating_existing_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gaia.cli.commands.add as add_mod

    consumer = tmp_path / "consumer"
    _write_empty_gaia_package(consumer)
    materialize_lkm_paper_package(
        _paper_graph_payload(),
        project_root=consumer,
        index_id="bohrium",
        paper_id="811827932371615744",
    )

    def fake_run_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        index_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        del method, path, json_body, index_id
        return _paper_graph_payload()

    def fake_run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(add_mod, "run_request", fake_run_request)
    monkeypatch.setattr(add_mod, "_run_uv", fake_run_uv)
    monkeypatch.chdir(consumer)

    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )

    assert result.exit_code == 0, result.output
    assert "regenerated an existing LKM package" in result.output


def test_pkg_add_lkm_paper_reports_skipped_factor_count(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gaia.cli.commands.add as add_mod

    consumer = tmp_path / "consumer"
    _write_empty_gaia_package(consumer)

    def fake_run_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        index_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        del method, path, json_body, index_id
        return _paper_graph_payload_with_skipped_factors()

    def fake_run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(add_mod, "run_request", fake_run_request)
    monkeypatch.setattr(add_mod, "_run_uv", fake_run_uv)
    monkeypatch.chdir(consumer)

    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )

    assert result.exit_code == 0, result.output
    assert "1 depends_on scaffold dependencies" in result.output
    assert "skipped 2 LKM factor(s)" in result.output


def test_pkg_add_lkm_paper_reports_materialized_path_when_uv_add_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import gaia.cli.commands.add as add_mod

    consumer = tmp_path / "consumer"
    consumer.mkdir()
    (consumer / "pyproject.toml").write_text(
        "[project]\n"
        'name = "lkm-consumer-gaia"\n'
        'version = "0.1.0"\n'
        "dependencies = []\n\n"
        "[tool.gaia]\n"
        'namespace = "github"\n'
        'type = "knowledge-package"\n',
        encoding="utf-8",
    )

    def fake_run_request(
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        index_id: str,
        **_: Any,
    ) -> dict[str, Any]:
        del method, path, json_body, index_id
        return _paper_graph_payload()

    def fake_run_uv(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        del kwargs
        return subprocess.CompletedProcess(args, 1, "", "resolver exploded")

    monkeypatch.setattr(add_mod, "run_request", fake_run_request)
    monkeypatch.setattr(add_mod, "_run_uv", fake_run_uv)
    monkeypatch.chdir(consumer)

    result = runner.invoke(
        app,
        ["pkg", "add", "--lkm-index", "bohrium", "--lkm-paper", "811827932371615744"],
    )

    assert result.exit_code == 1
    assert "uv add failed after materializing lkm:bohrium:paper:811827932371615744" in (
        result.output
    )
    assert "Generated package left at:" in result.output
    assert "resolver exploded" in result.output
    assert any((consumer / ".gaia" / "lkm_packages").iterdir())
