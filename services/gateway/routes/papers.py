"""Paper fixture viewer routes — serve parsed XML and YAML fixture data for visualization."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/papers", tags=["papers"])

_REPO_ROOT = Path(__file__).resolve().parents[3]
XML_DIR = _REPO_ROOT / "tests/fixtures/inputs/papers_xml"
YAML_DIR = _REPO_ROOT / "tests/fixtures/gaia_language_packages"


def _xml_slug_to_yaml_slug(xml_slug: str) -> str:
    """Map XML paper directory name → YAML package directory name."""
    return "paper_" + xml_slug.lower().replace("-", "_").replace(".", "_")


def _yaml_slug_to_xml_slug(yaml_slug: str) -> str | None:
    """Reverse-lookup YAML slug to XML slug (best-effort)."""
    if not XML_DIR.exists():
        return None
    for d in XML_DIR.iterdir():
        if not d.is_dir() or d.name == "images":
            continue
        if _xml_slug_to_yaml_slug(d.name) == yaml_slug:
            return d.name
    return None


# ── List ──────────────────────────────────────────────────────────────────────


@router.get("")
def list_papers() -> list[dict]:
    """List all available papers (union of XML and YAML fixtures)."""
    papers: dict[str, dict] = {}

    if XML_DIR.exists():
        for d in sorted(XML_DIR.iterdir()):
            if not d.is_dir() or d.name == "images":
                continue
            slug = d.name
            yaml_slug = _xml_slug_to_yaml_slug(slug)
            papers[yaml_slug] = {
                "slug": yaml_slug,
                "xml_slug": slug,
                "has_xml": True,
                "has_yaml": (YAML_DIR / yaml_slug).is_dir(),
            }

    if YAML_DIR.exists():
        for d in sorted(YAML_DIR.iterdir()):
            if not d.is_dir():
                continue
            yaml_slug = d.name
            if yaml_slug not in papers:
                xml_slug = _yaml_slug_to_xml_slug(yaml_slug)
                papers[yaml_slug] = {
                    "slug": yaml_slug,
                    "xml_slug": xml_slug,
                    "has_xml": xml_slug is not None,
                    "has_yaml": True,
                }

    return sorted(papers.values(), key=lambda p: p["slug"])


# ── XML ───────────────────────────────────────────────────────────────────────


def _parse_combine_xml(path: Path) -> dict:
    """Parse a *_combine.xml file into structured data."""
    tree = ET.parse(path)
    root = tree.getroot()

    # Notations
    notations = []
    for n in root.findall(".//notations/"):
        text = (n.text or "").strip()
        if text:
            notations.append(text)

    # Premises
    premises = []
    for p in root.findall(".//premises/premise"):
        premises.append(
            {
                "id": p.get("id"),
                "title": p.get("title", ""),
                "content": (p.text or "").strip(),
            }
        )

    # Reasoning steps
    steps = []
    for s in root.findall(".//reasoning/step"):
        steps.append(
            {
                "title": s.get("title", ""),
                "content": (s.text or "").strip(),
            }
        )

    # Conclusion
    conclusion_el = root.find(".//conclusion")
    conclusion = None
    if conclusion_el is not None:
        conclusion = {
            "title": conclusion_el.get("title", ""),
            "content": (conclusion_el.text or "").strip(),
        }

    return {
        "file": path.name,
        "notations": notations,
        "premises": premises,
        "steps": steps,
        "conclusion": conclusion,
    }


@router.get("/{slug}/xml")
def get_paper_xml(slug: str) -> dict:
    """Return parsed XML combine files for a paper."""
    # Resolve XML dir name
    xml_slug = _yaml_slug_to_xml_slug(slug)
    if xml_slug is None:
        # slug might already be the XML slug
        candidate = XML_DIR / slug
        if candidate.is_dir():
            xml_slug = slug
        else:
            raise HTTPException(status_code=404, detail=f"Paper XML not found: {slug}")

    paper_dir = XML_DIR / xml_slug
    if not paper_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Paper XML directory not found: {xml_slug}")

    combine_files = sorted(paper_dir.glob("*_combine.xml"))
    if not combine_files:
        raise HTTPException(status_code=404, detail="No *_combine.xml files found")

    chains = [_parse_combine_xml(f) for f in combine_files]
    return {"slug": slug, "xml_slug": xml_slug, "chains": chains}


# ── YAML ─────────────────────────────────────────────────────────────────────


def _parse_yaml_module(path: Path) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


@router.get("/{slug}/yaml")
def get_paper_yaml(slug: str) -> dict:
    """Return parsed YAML package for a paper."""
    pkg_dir = YAML_DIR / slug
    if not pkg_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"YAML package not found: {slug}")

    result: dict = {"slug": slug, "modules": {}}

    for yaml_file in sorted(pkg_dir.glob("*.yaml")):
        data = _parse_yaml_module(yaml_file)
        result["modules"][yaml_file.stem] = data

    return result
