"""Configuration for the review pipeline — LLM models, embedding, provider routing."""

from __future__ import annotations

import os

from pydantic import BaseModel


class LLMModelConfig(BaseModel):
    """Configuration for a single LLM model."""

    provider: str = "openai"
    name: str = "gpt-5-mini"
    temperature: float = 1.0
    max_completion_tokens: int = 60480
    timeout: int = 200
    max_retries: int = 1


class ReviewPipelineSettings(BaseModel):
    """Top-level settings for the review pipeline."""

    embedding_provider: str = "dashscope"
    embedding_api_url: str = ""
    embedding_access_key: str = ""
    embedding_max_rps: int = 600
    embedding_http_timeout: int = 30

    join_model: LLMModelConfig = LLMModelConfig()
    verify_model: LLMModelConfig = LLMModelConfig()


# ---------------------------------------------------------------------------
# Provider → litellm model routing (adapted from reference config.py)
# ---------------------------------------------------------------------------

MODEL_MAPPING: dict[tuple[str, str], str] = {
    # deepseek
    ("deepseek", "deepseek-reasoner"): "deepseek/deepseek-reasoner",
    ("deepseek", "deepseek-chat"): "deepseek/deepseek-chat",
    # volcengine
    ("volcengine", "doubao-seed-1-6-250615"): "volcengine/doubao-seed-1-6-250615",
    ("volcengine", "deepseek-r1-250528"): "volcengine/deepseek-r1-250528",
    ("volcengine", "deepseek-v3-250324"): "volcengine/deepseek-v3-250324",
    ("volcengine", "kimi-k2-250905"): "volcengine/kimi-k2-250905",
    # openrouter
    ("openrouter", "deepseek-r1-0528"): "openrouter/deepseek/deepseek-r1-0528",
    ("openrouter", "deepseek-v3"): "openrouter/deepseek/deepseek-chat-v3-0324",
    ("openrouter", "gemini-2.5-pro"): "openrouter/google/gemini-2.5-pro",
    ("openrouter", "gemini-3-pro"): "openrouter/google/gemini-3-pro",
    # openai official
    ("openai", "gpt-5-mini"): "openai/gpt-5-mini",
    ("openai", "gpt-5"): "openai/gpt-5",
    ("openai", "o4-mini"): "openai/o4-mini",
    # dptech
    ("dptech", "o4-mini"): "openai/o4-mini",
    ("dptech", "gpt-5-mini"): "openai/gpt-5-mini",
    ("dptech", "gpt-5"): "openai/gpt-5",
    ("dptech", "gpt-5.1"): "openai/gpt-5.1",
    ("dptech", "gpt-5.2"): "openai/gpt-5.2",
    ("dptech", "gemini-2.5-pro"): "openai/gemini-2.5-pro",
    ("dptech", "gemini-3-pro"): "openai/gemini-3-pro",
    ("dptech", "gemini-3-flash"): "openai/gemini-3-flash",
    # dptech internal
    ("dptech_internal", "gpt-5-mini"): "openai/chenkun/gpt-5-mini",
    ("dptech_internal", "gpt-5"): "openai/gpt-5",
    ("dptech_internal", "gpt-5.1"): "openai/chenkun/gpt-5.1",
    ("dptech_internal", "gemini-3-pro"): "openai/gemini-3-pro",
    ("dptech_internal", "claude-sonnet-4-5"): "openai/claude-sonnet-4-5",
    ("dptech_internal", "claude-opus-4-6"): "openai/cds/Claude-4.6-opus",
    # scnet
    ("scnet", "DeepSeek-R1-671B"): "openai/DeepSeek-R1-671B",
    # maas
    ("maas", "DeepSeek-V3.1"): "openai/DeepSeek-V3.1",
    ("maas", "DeepSeek-R1"): "openai/DeepSeek-R1",
    ("maas", "Qwen3-235B-A22B-Instruct-2507"): "openai/Qwen3-235B-A22B-Instruct-2507",
    ("maas", "Kimi-K2"): "openai/Kimi-K2",
    ("maas", "GLM-4.5"): "openai/GLM-4.5",
}


def get_model_config(config: LLMModelConfig | dict) -> dict:
    """Build litellm-compatible call config from an LLMModelConfig.

    Returns a dict with keys like ``model``, ``timeout``, ``api_key``, etc.
    that can be unpacked into ``litellm.acompletion(**config)``.
    """
    if isinstance(config, LLMModelConfig):
        provider = config.provider
        name = config.name
        cfg: dict = config.model_dump()
    else:
        provider = config["provider"]
        name = config["name"]
        cfg = dict(config)

    model = MODEL_MAPPING.get((provider, name))
    if not model:
        raise ValueError(f"Model mapping not found for provider '{provider}' and model '{name}'")

    base: dict = {
        "model": model,
        "timeout": cfg.get("timeout", 600),
        "max_retries": cfg.get("max_retries", 2),
    }

    if provider == "dptech":
        base["temperature"] = cfg.get("temperature", 0.7)
        base["api_key"] = "dummy-key"
        if os.getenv("DP_BASE_URL") and os.getenv("DP_ACCESS_KEY"):
            base["api_base"] = os.getenv("DP_BASE_URL")
            base["extra_headers"] = {"accessKey": os.getenv("DP_ACCESS_KEY")}
        else:
            base["api_base"] = "http://localhost:8004/v1"

    elif provider == "openai":
        base["api_key"] = os.getenv("OPENAI_API_KEY")
        base["temperature"] = cfg.get("temperature", 0.7)

    elif provider == "dptech_internal":
        base["api_base"] = os.getenv("DP_INTERNAL_BASE_URL")
        base["api_key"] = os.getenv("DP_INTERNAL_API_KEY")
        if "temperature" in cfg:
            base["temperature"] = cfg["temperature"]

    elif provider == "scnet":
        base["api_base"] = "https://api.scnet.cn/api/llm/v1"
        base["api_key"] = os.getenv("SCNET_API_KEY")

    elif provider in ("volcengine", "deepseek", "openrouter"):
        base["max_completion_tokens"] = cfg.get("max_completion_tokens")
        base["temperature"] = cfg.get("temperature", 0.7)

    elif provider == "maas":
        base["api_base"] = os.getenv("MAAS_API_BASE")
        base["api_key"] = os.getenv("MAAS_API_KEY")
        base["max_completion_tokens"] = cfg.get("max_completion_tokens")
        base["temperature"] = cfg.get("temperature", 0.7)

    return base
