"""Tests for review sidecar I/O and review merger."""

from pathlib import Path

import pytest

from cli.review_store import (
    find_latest_review,
    merge_review,
    read_review,
    write_review,
)
from libs.lang.loader import load_package
from libs.lang.resolver import resolve_refs


FIXTURE_PATH = Path("tests/fixtures/gaia_language_packages/galileo_falling_bodies")


def _sample_review() -> dict:
    return {
        "package": "galileo_falling_bodies",
        "model": "test-model",
        "timestamp": "2026-03-08T14:30:00Z",
        "chains": [
            {
                "chain": "drag_prediction_chain",
                "steps": [
                    {
                        "step": 2,
                        "assessment": "valid",
                        "suggested_prior": 0.95,
                        "rewrite": None,
                        "dependencies": [
                            {"ref": "heavier_falls_faster", "suggested": "direct"},
                            {"ref": "thought_experiment_env", "suggested": "direct"},
                        ],
                    }
                ],
            }
        ],
    }


def test_write_and_read_review(tmp_path):
    review = _sample_review()
    path = write_review(review, tmp_path)
    assert path.exists()
    assert path.suffix == ".yaml"
    loaded = read_review(path)
    assert loaded["package"] == "galileo_falling_bodies"
    assert len(loaded["chains"]) == 1


def test_find_latest_review(tmp_path):
    r1 = _sample_review()
    r1["timestamp"] = "2026-03-01T10:00:00Z"
    write_review(r1, tmp_path, filename="review_2026-03-01.yaml")
    r2 = _sample_review()
    r2["timestamp"] = "2026-03-08T14:30:00Z"
    p2 = write_review(r2, tmp_path, filename="review_2026-03-08.yaml")
    latest = find_latest_review(tmp_path)
    assert latest == p2


def test_find_latest_review_empty_dir(tmp_path):
    with pytest.raises(FileNotFoundError):
        find_latest_review(tmp_path)


def test_merge_review_updates_prior():
    """merge_review should update step priors from review suggestions."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    merged = merge_review(pkg, review)
    for mod in merged.loaded_modules:
        for decl in mod.knowledge:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                assert step2.prior == 0.95
                break


def test_merge_review_updates_dependency():
    """merge_review should update arg dependency types from review."""
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    merged = merge_review(pkg, review)
    for mod in merged.loaded_modules:
        for decl in mod.knowledge:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                env_arg = next(a for a in step2.args if a.ref == "thought_experiment_env")
                assert env_arg.dependency == "direct"
                break


def test_merge_review_warns_on_fingerprint_mismatch():
    """merge_review should warn when source fingerprint doesn't match."""
    import warnings

    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    review["source_fingerprint"] = "0000000000000000"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        merge_review(pkg, review, source_fingerprint="aaaaaaaaaaaaaaaa")
        assert len(w) == 1
        assert "fingerprint mismatch" in str(w[0].message).lower()


def test_merge_review_no_warning_when_fingerprint_matches():
    """merge_review should not warn when fingerprints match."""
    import warnings

    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    review["source_fingerprint"] = "abcdef1234567890"
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        merge_review(pkg, review, source_fingerprint="abcdef1234567890")
        assert len(w) == 0


def test_merge_review_does_not_modify_original():
    pkg = load_package(FIXTURE_PATH)
    pkg = resolve_refs(pkg)
    review = _sample_review()
    orig_prior = None
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                orig_prior = step2.prior
    merge_review(pkg, review)
    for mod in pkg.loaded_modules:
        for decl in mod.knowledge:
            if hasattr(decl, "steps") and decl.name == "drag_prediction_chain":
                step2 = next(s for s in decl.steps if s.step == 2)
                assert step2.prior == orig_prior
