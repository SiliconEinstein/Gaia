"""Unified LLM client for all Gaia LLM calls.

Handles model name normalization (adding openai/ prefix for gateway compatibility)
and api_base configuration from environment.

Usage:
    from gaia.libs.llm import llm_completion

    response = await llm_completion(
        model="chenkun/gpt-5-mini",
        messages=[{"role": "user", "content": "Hello"}],
    )
    text = response.choices[0].message.content
"""

from __future__ import annotations

import os

import litellm

# Configure litellm from environment on import
_api_base = os.getenv("OPENAI_API_BASE")
if _api_base:
    litellm.api_base = _api_base

# Default model for curation/review tasks
DEFAULT_MODEL = "openai/chenkun/gpt-5-mini"


def _normalize_model(model: str) -> str:
    """Ensure model name has the openai/ prefix for gateway compatibility."""
    if model.startswith("openai/"):
        return model
    known_providers = (
        "anthropic/",
        "azure/",
        "bedrock/",
        "vertex_ai/",
        "huggingface/",
        "ollama/",
        "together_ai/",
        "replicate/",
    )
    if any(model.startswith(p) for p in known_providers):
        return model
    return f"openai/{model}"


async def llm_completion(
    model: str | None = None,
    messages: list[dict] | None = None,
    **kwargs,
) -> object:
    """Call LLM via litellm with normalized model name and api_base."""
    resolved_model = _normalize_model(model or DEFAULT_MODEL)
    return await litellm.acompletion(
        model=resolved_model,
        messages=messages or [],
        **kwargs,
    )
