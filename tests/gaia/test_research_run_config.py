"""Tests for typed research workflow configuration."""

from __future__ import annotations

import json
from pathlib import Path

from gaia.engine.research.run_config import resolve_research_run_config


def test_review_profile_uses_wider_evidence_selection_defaults() -> None:
    config = resolve_research_run_config(profile="review")

    assert config.profile == "review"
    assert config.search.limit == 10
    assert config.focus.count == 3
    assert config.evidence.selection_mode == "review"
    assert config.evidence.max_items == 32
    assert config.evidence.max_papers == 12
    assert config.evidence.max_chains == 12


def test_config_file_and_overrides_deep_merge(tmp_path: Path) -> None:
    config_path = tmp_path / "research.json"
    config_path.write_text(
        json.dumps(
            {
                "profile": "review",
                "search": {"limit": 7},
                "evidence": {"max_items": 24},
                "llm": {"provider": "litellm", "model": "openai/test"},
            }
        ),
        encoding="utf-8",
    )

    config = resolve_research_run_config(
        profile="quick",
        config_file=config_path,
        overrides={"evidence": {"max_papers": 9}, "report": {"section_concurrency": 2}},
    )

    assert config.profile == "review"
    assert config.search.limit == 7
    assert config.focus.count == 3
    assert config.evidence.selection_mode == "review"
    assert config.evidence.max_items == 24
    assert config.evidence.max_papers == 9
    assert config.llm.provider == "litellm"
    assert config.llm.model == "openai/test"
    assert config.report.section_concurrency == 2
