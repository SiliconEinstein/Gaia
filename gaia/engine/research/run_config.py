"""Typed workflow configuration for package-native research runs."""

from __future__ import annotations

import json
import tomllib
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchWorkflowProfile = Literal["evidence-assessment", "quick", "review", "deep"]
EvidenceSelectionMode = Literal["fast", "review"]
AnalysisProvider = Literal["checkpoint", "command", "litellm"]


class SearchConfig(BaseModel):
    """Live search settings."""

    model_config = ConfigDict(extra="forbid")

    limit: int = 20
    index: str | None = None
    reasoning_only: bool = True


class FocusConfig(BaseModel):
    """Focus selection settings."""

    model_config = ConfigDict(extra="forbid")

    count: int = 1


class EvidenceConfig(BaseModel):
    """Selected-evidence packet settings."""

    model_config = ConfigDict(extra="forbid")

    selection_mode: EvidenceSelectionMode = "fast"
    max_items: int = 12
    max_papers: int = 6
    max_chains: int = 6


class ReportConfig(BaseModel):
    """Final report writing settings."""

    model_config = ConfigDict(extra="forbid")

    section_concurrency: int = 4


class LLMConfig(BaseModel):
    """Analysis provider and LiteLLM settings."""

    model_config = ConfigDict(extra="forbid")

    provider: AnalysisProvider = "checkpoint"
    model: str | None = None
    focus_model: str | None = None
    assess_model: str | None = None
    temperature: float = 0.0
    timeout: float = 120.0
    max_retries: int = 2
    max_tokens: int | None = None


class ResearchRunConfig(BaseModel):
    """Resolved workflow configuration for one research run."""

    model_config = ConfigDict(extra="forbid")

    profile: ResearchWorkflowProfile = "evidence-assessment"
    search: SearchConfig = Field(default_factory=SearchConfig)
    focus: FocusConfig = Field(default_factory=FocusConfig)
    evidence: EvidenceConfig = Field(default_factory=EvidenceConfig)
    report: ReportConfig = Field(default_factory=ReportConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)


def profile_defaults(profile: str) -> ResearchRunConfig:
    """Return built-in defaults for a workflow profile."""
    if profile == "evidence-assessment":
        return ResearchRunConfig(profile="evidence-assessment")
    if profile == "quick":
        return ResearchRunConfig(
            profile="quick",
            search=SearchConfig(limit=10),
            focus=FocusConfig(count=1),
            evidence=EvidenceConfig(
                selection_mode="fast",
                max_items=12,
                max_papers=6,
                max_chains=6,
            ),
        )
    if profile == "review":
        return ResearchRunConfig(
            profile="review",
            search=SearchConfig(limit=10),
            focus=FocusConfig(count=3),
            evidence=EvidenceConfig(
                selection_mode="review",
                max_items=32,
                max_papers=12,
                max_chains=12,
            ),
        )
    if profile == "deep":
        return ResearchRunConfig(
            profile="deep",
            search=SearchConfig(limit=20),
            focus=FocusConfig(count=5),
            evidence=EvidenceConfig(
                selection_mode="review",
                max_items=48,
                max_papers=20,
                max_chains=20,
            ),
        )
    msg = "profile must be one of: evidence-assessment, quick, review, deep"
    raise ValueError(msg)


def load_research_run_config_file(path: Path) -> dict[str, Any]:
    """Load a JSON or TOML research run config file."""
    if not path.exists():
        msg = f"config file not found: {path}"
        raise FileNotFoundError(msg)
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
    elif suffix == ".toml":
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        msg = "research config must be JSON or TOML"
        raise ValueError(msg)
    if not isinstance(payload, dict):
        msg = "research config root must be an object"
        raise ValueError(msg)
    return payload


def resolve_research_run_config(
    *,
    profile: str,
    config_file: Path | None = None,
    overrides: Mapping[str, Any] | None = None,
) -> ResearchRunConfig:
    """Resolve profile defaults, optional config file, and CLI overrides."""
    file_payload = load_research_run_config_file(config_file) if config_file is not None else {}
    effective_profile = str(file_payload.get("profile") or profile)
    payload = profile_defaults(effective_profile).model_dump()
    payload = _deep_merge(payload, file_payload)
    if overrides:
        payload = _deep_merge(payload, dict(overrides))
    return ResearchRunConfig.model_validate(payload)


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if value is None:
            continue
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, Mapping):
            merged[key] = _deep_merge(existing, value)
        else:
            merged[key] = value
    return merged
