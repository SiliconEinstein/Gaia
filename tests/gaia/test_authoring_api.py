"""Public engine authoring API tests."""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pytest

from gaia.engine.authoring import ProposedAuthorOp, run_author_batch

pytestmark = pytest.mark.pr_gate


def _write_package(root: Path) -> Path:
    import_name = "authoring_fixture"
    source_root = root / "src" / import_name
    source_root.mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        "[project]\n"
        'name = "authoring-fixture-gaia"\n'
        'version = "0.1.0"\n\n'
        "[tool.gaia]\n"
        'type = "knowledge-package"\n'
        f'uuid = "{uuid4()}"\n',
        encoding="utf-8",
    )
    (source_root / "__init__.py").write_text(
        "from gaia.engine.lang import claim\n\nseed = claim('Seed claim.')\n\n__all__ = ['seed']\n",
        encoding="utf-8",
    )
    return source_root


def _claim_op(label: str, *, references: list[str] | None = None) -> ProposedAuthorOp:
    background = f", background=[{', '.join(references)}]" if references else ""
    return ProposedAuthorOp(
        verb="claim",
        kind="reasoning",
        label=label,
        references=references or [],
        generated_code=f"{label} = claim({label.replace('_', ' ')!r}{background})",
        required_imports=("claim",),
        export=True,
    )


def test_run_author_batch_writes_ordered_ops_with_one_final_check(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    source_root = _write_package(tmp_path)
    calls = 0

    from gaia.engine.authoring import _batch as batch_mod

    real_postwrite_check = batch_mod.postwrite_check

    def counting_postwrite_check(target: str | Path):
        nonlocal calls
        calls += 1
        return real_postwrite_check(target)

    monkeypatch.setattr(batch_mod, "postwrite_check", counting_postwrite_check)

    result = run_author_batch(
        tmp_path,
        [
            _claim_op("first_claim"),
            _claim_op("second_claim", references=["first_claim"]),
        ],
    )

    assert result.ok, [diagnostic.message for diagnostic in result.diagnostics]
    assert calls == 1
    assert [write.label for write in result.writes] == ["first_claim", "second_claim"]
    authored_source = (source_root / "authored" / "__init__.py").read_text(encoding="utf-8")
    assert "first_claim = claim('first claim')" in authored_source
    assert "second_claim = claim('second claim', background=[first_claim])" in authored_source
    assert "__all__ = [\n    'first_claim',\n    'second_claim',\n]" in authored_source


def test_run_author_batch_rolls_back_when_later_op_fails(tmp_path: Path) -> None:
    source_root = _write_package(tmp_path)

    result = run_author_batch(
        tmp_path,
        [
            _claim_op("first_claim"),
            _claim_op("broken_claim", references=["missing_claim"]),
        ],
    )

    assert not result.ok
    assert result.diagnostics[0].kind == "prewrite.reference_unresolved"
    authored_init = source_root / "authored" / "__init__.py"
    assert not authored_init.exists()
    assert "first_claim" not in (source_root / "__init__.py").read_text(encoding="utf-8")
