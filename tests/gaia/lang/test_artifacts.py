from __future__ import annotations

import warnings

import pytest

from gaia.engine.ir.knowledge import KnowledgeType
from gaia.engine.lang import artifact, claim, figure
from gaia.engine.lang.compiler import compile_package_artifact
from gaia.engine.lang.runtime.package import CollectedPackage


def test_artifact_returns_note_with_gaia_artifact_metadata() -> None:
    node = artifact(
        kind="attachment",
        source="Liu2015",
        locator="Supplementary Data 1",
        path="artifacts/attachments/liu2015.xlsx",
        description="Digitized source data.",
    )

    assert node.type == KnowledgeType.NOTE
    assert node.content == "Digitized source data."
    assert node.metadata["gaia"]["artifact"] == {
        "kind": "attachment",
        "source": "Liu2015",
        "locator": "Supplementary Data 1",
        "path": "artifacts/attachments/liu2015.xlsx",
        "description": "Digitized source data.",
    }


def test_figure_is_artifact_sugar() -> None:
    node = figure(
        source="Liu2015",
        locator="Fig. 3",
        path="artifacts/figures/liu2015_fig3.png",
        caption="Fibonacci scaling.",
    )

    assert node.type == KnowledgeType.NOTE
    assert node.content == "Fibonacci scaling."
    assert node.metadata["gaia"]["artifact"]["kind"] == "figure"
    assert node.metadata["gaia"]["artifact"]["caption"] == "Fibonacci scaling."


def test_artifact_rejects_unknown_kind() -> None:
    with pytest.raises(ValueError, match="artifact kind"):
        artifact(kind="movie", path="artifacts/movie.mp4")


def test_artifact_requires_source_or_path() -> None:
    with pytest.raises(ValueError, match="source or path"):
        artifact(kind="dataset", description="No anchor.")


def test_figure_requires_source_bound_locator() -> None:
    with pytest.raises(ValueError, match="locator"):
        figure(source="Liu2015", caption="Missing locator.")


def test_compile_rejects_artifact_source_missing_from_references() -> None:
    with CollectedPackage("artifact_source_missing") as pkg:
        fig = figure(source="Missing2015", locator="Fig. 3")
        fig.label = "fig3"

    with pytest.raises(Exception, match="Missing2015"):
        compile_package_artifact(pkg, references={})


def test_compile_resolves_artifact_label_as_local_reference() -> None:
    with CollectedPackage("artifact_reference") as pkg:
        fig = figure(source="Liu2015", locator="Fig. 3", caption="A figure.")
        c = claim("See [@fig3].")
        fig.label = "fig3"
        c.label = "claim1"

    compiled = compile_package_artifact(
        pkg,
        references={"Liu2015": {"id": "Liu2015", "type": "article-journal", "title": "T"}},
    )
    by_id = {k.id: k for k in compiled.graph.knowledges}
    provenance = by_id["github:artifact_reference::claim1"].metadata["gaia"]["provenance"]
    assert provenance["artifact_refs"] == ["fig3"]
    assert "referenced_claims" not in provenance


def test_compile_splits_artifact_refs_from_claim_refs() -> None:
    with CollectedPackage("artifact_and_claim_reference") as pkg:
        fig = figure(source="Liu2015", locator="Fig. 3", caption="A figure.")
        lemma = claim("A local lemma.")
        c = claim("See [@fig3] and [@lemma].")
        fig.label = "fig3"
        lemma.label = "lemma"
        c.label = "claim1"

    compiled = compile_package_artifact(
        pkg,
        references={"Liu2015": {"id": "Liu2015", "type": "article-journal", "title": "T"}},
    )
    by_id = {k.id: k for k in compiled.graph.knowledges}
    provenance = by_id["github:artifact_and_claim_reference::claim1"].metadata["gaia"]["provenance"]
    assert provenance["artifact_refs"] == ["fig3"]
    assert provenance["referenced_claims"] == ["lemma"]


def test_compile_warns_on_legacy_refs_metadata() -> None:
    with CollectedPackage("legacy_refs") as pkg:
        c = claim("Legacy metadata.", refs=[{"type": "citation", "key": "Liu2015"}])
        c.label = "legacy"

    with pytest.warns(DeprecationWarning, match="refs"):
        compile_package_artifact(pkg)


def test_compile_allows_source_paper_as_audit_metadata_without_legacy_warning() -> None:
    with CollectedPackage("legacy_source_paper") as pkg:
        c = claim("Legacy source paper.", source_paper="Liu2015")
        c.label = "legacy"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        compile_package_artifact(pkg)

    assert not [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]


def test_compile_allows_unrelated_caption_metadata_without_legacy_warning() -> None:
    with CollectedPackage("caption_metadata") as pkg:
        c = claim("Caption is domain metadata, not an artifact.", caption="not an artifact")
        c.label = "caption_claim"

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always", DeprecationWarning)
        compile_package_artifact(pkg)

    assert not [warning for warning in caught if issubclass(warning.category, DeprecationWarning)]
