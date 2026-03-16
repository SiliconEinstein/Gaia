"""Tests for /papers API routes."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml
from fastapi.testclient import TestClient

import services.gateway.routes.papers as papers_mod
from services.gateway.app import create_app


@pytest.fixture()
def xml_dir(tmp_path: Path) -> Path:
    return tmp_path / "papers_xml"


@pytest.fixture()
def yaml_dir(tmp_path: Path) -> Path:
    return tmp_path / "gaia_language_packages"


@pytest.fixture()
def patched_dirs(monkeypatch, xml_dir: Path, yaml_dir: Path):
    """Redirect the module-level XML_DIR and YAML_DIR to tmp_path."""
    monkeypatch.setattr(papers_mod, "XML_DIR", xml_dir)
    monkeypatch.setattr(papers_mod, "YAML_DIR", yaml_dir)


@pytest.fixture()
def client(patched_dirs) -> TestClient:
    app = create_app()
    return TestClient(app)


# ── helpers ───────────────────────────────────────────────────────────────────

COMBINE_XML = textwrap.dedent("""\
    <inference_unit>
      <notations>
        <n>$x$: variable</n>
      </notations>
      <premises>
        <premise id="1" title="Premise One">Content of premise one.</premise>
        <premise id="2" title="Premise Two">Content of premise two.</premise>
      </premises>
      <reasoning>
        <step title="Step A">First reasoning step.</step>
        <step title="Step B">Second reasoning step.</step>
      </reasoning>
      <conclusion title="Main Conclusion">The final conclusion text.</conclusion>
    </inference_unit>
""")


def _make_paper_xml(xml_dir: Path, xml_slug: str) -> Path:
    paper_dir = xml_dir / xml_slug
    paper_dir.mkdir(parents=True)
    (paper_dir / "conclusion_1_reasoning_chain_combine.xml").write_text(COMBINE_XML)
    return paper_dir


def _make_paper_yaml(yaml_dir: Path, yaml_slug: str) -> Path:
    pkg_dir = yaml_dir / yaml_slug
    pkg_dir.mkdir(parents=True)
    setting = {
        "type": "setting_module",
        "name": "setting",
        "knowledge": [{"type": "setting", "name": "prem_one", "content": "Content.", "prior": 0.7}],
    }
    reasoning = {
        "type": "reasoning_module",
        "name": "reasoning",
        "knowledge": [
            {"type": "claim", "name": "conclusion", "content": "Conclusion.", "prior": 0.5}
        ],
    }
    (pkg_dir / "setting.yaml").write_text(yaml.dump(setting))
    (pkg_dir / "reasoning.yaml").write_text(yaml.dump(reasoning))
    return pkg_dir


# ── GET /papers ───────────────────────────────────────────────────────────────


class TestListPapers:
    def test_empty_dirs(self, client: TestClient):
        resp = client.get("/papers")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_xml_only_paper(self, client: TestClient, xml_dir: Path):
        _make_paper_xml(xml_dir, "10.1234_Test")
        resp = client.get("/papers")
        assert resp.status_code == 200
        papers = resp.json()
        assert len(papers) == 1
        assert papers[0]["has_xml"] is True
        assert papers[0]["has_yaml"] is False
        assert papers[0]["xml_slug"] == "10.1234_Test"

    def test_yaml_only_paper(self, client: TestClient, yaml_dir: Path):
        _make_paper_yaml(yaml_dir, "my_paper")
        resp = client.get("/papers")
        assert resp.status_code == 200
        papers = resp.json()
        assert len(papers) == 1
        assert papers[0]["slug"] == "my_paper"
        assert papers[0]["has_xml"] is False
        assert papers[0]["has_yaml"] is True

    def test_paper_with_both(self, client: TestClient, xml_dir: Path, yaml_dir: Path):
        _make_paper_xml(xml_dir, "10.1234_Test")
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Test")
        _make_paper_yaml(yaml_dir, yaml_slug)

        resp = client.get("/papers")
        papers = resp.json()
        assert len(papers) == 1
        assert papers[0]["has_xml"] is True
        assert papers[0]["has_yaml"] is True

    def test_result_is_sorted(self, client: TestClient, yaml_dir: Path):
        for slug in ("zzz_paper", "aaa_paper", "mmm_paper"):
            _make_paper_yaml(yaml_dir, slug)
        papers = client.get("/papers").json()
        slugs = [p["slug"] for p in papers]
        assert slugs == sorted(slugs)


# ── GET /papers/{slug}/xml ────────────────────────────────────────────────────


class TestGetPaperXml:
    def test_returns_chains(self, client: TestClient, xml_dir: Path):
        _make_paper_xml(xml_dir, "10.1234_Test")
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Test")
        resp = client.get(f"/papers/{yaml_slug}/xml")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == yaml_slug
        assert data["xml_slug"] == "10.1234_Test"
        assert len(data["chains"]) == 1

    def test_chain_structure(self, client: TestClient, xml_dir: Path):
        _make_paper_xml(xml_dir, "10.1234_Test")
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Test")
        chain = client.get(f"/papers/{yaml_slug}/xml").json()["chains"][0]
        assert len(chain["premises"]) == 2
        assert chain["premises"][0]["id"] == "1"
        assert chain["premises"][0]["title"] == "Premise One"
        assert len(chain["steps"]) == 2
        assert chain["conclusion"]["title"] == "Main Conclusion"

    def test_notations_parsed(self, client: TestClient, xml_dir: Path):
        _make_paper_xml(xml_dir, "10.1234_Test")
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Test")
        chain = client.get(f"/papers/{yaml_slug}/xml").json()["chains"][0]
        assert "$x$: variable" in chain["notations"]

    def test_not_found(self, client: TestClient):
        resp = client.get("/papers/nonexistent/xml")
        assert resp.status_code == 404

    def test_no_combine_files_returns_404(self, client: TestClient, xml_dir: Path):
        empty_dir = xml_dir / "10.1234_Empty"
        empty_dir.mkdir(parents=True)
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Empty")
        resp = client.get(f"/papers/{yaml_slug}/xml")
        assert resp.status_code == 404

    def test_multiple_chains(self, client: TestClient, xml_dir: Path):
        paper_dir = xml_dir / "10.1234_Multi"
        paper_dir.mkdir(parents=True)
        for i in (1, 2, 3):
            (paper_dir / f"conclusion_{i}_reasoning_chain_combine.xml").write_text(COMBINE_XML)
        yaml_slug = papers_mod._xml_slug_to_yaml_slug("10.1234_Multi")
        data = client.get(f"/papers/{yaml_slug}/xml").json()
        assert len(data["chains"]) == 3


# ── GET /papers/{slug}/yaml ───────────────────────────────────────────────────


class TestGetPaperYaml:
    def test_returns_modules(self, client: TestClient, yaml_dir: Path):
        _make_paper_yaml(yaml_dir, "my_paper")
        resp = client.get("/papers/my_paper/yaml")
        assert resp.status_code == 200
        data = resp.json()
        assert data["slug"] == "my_paper"
        assert "setting" in data["modules"]
        assert "reasoning" in data["modules"]

    def test_module_content(self, client: TestClient, yaml_dir: Path):
        _make_paper_yaml(yaml_dir, "my_paper")
        modules = client.get("/papers/my_paper/yaml").json()["modules"]
        assert modules["setting"]["type"] == "setting_module"
        assert len(modules["setting"]["knowledge"]) == 1

    def test_not_found(self, client: TestClient):
        resp = client.get("/papers/nonexistent/yaml")
        assert resp.status_code == 404


# ── slug conversion helpers ───────────────────────────────────────────────────


class TestSlugConversion:
    def test_xml_to_yaml_slug(self):
        assert (
            papers_mod._xml_slug_to_yaml_slug("10.1038332139a0_1988_Natu")
            == "paper_10_1038332139a0_1988_natu"
        )
        assert (
            papers_mod._xml_slug_to_yaml_slug("10.1038s41467-021-25372-2")
            == "paper_10_1038s41467_021_25372_2"
        )

    def test_yaml_to_xml_slug_not_found(self, xml_dir: Path, monkeypatch):
        monkeypatch.setattr(papers_mod, "XML_DIR", xml_dir)
        xml_dir.mkdir(parents=True, exist_ok=True)
        assert papers_mod._yaml_slug_to_xml_slug("nonexistent") is None

    def test_yaml_to_xml_slug_missing_dir(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(papers_mod, "XML_DIR", tmp_path / "does_not_exist")
        assert papers_mod._yaml_slug_to_xml_slug("anything") is None
