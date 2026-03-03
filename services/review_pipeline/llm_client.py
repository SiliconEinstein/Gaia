"""Shared LLM client — thin async wrapper around litellm."""

from __future__ import annotations

import litellm

from services.review_pipeline.config import LLMModelConfig, get_model_config


class LLMClient:
    """Reusable async LLM caller backed by litellm.

    Usage::

        client = LLMClient(LLMModelConfig(provider="openai", name="gpt-5-mini"))
        answer = await client.complete("You are a logician.", "Classify …")
    """

    def __init__(self, config: LLMModelConfig) -> None:
        self._config = config
        self._call_config = get_model_config(config)

    async def complete(self, system_prompt: str, user_prompt: str) -> str:
        """Send a system+user prompt pair and return the assistant response text."""
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        call_kwargs = dict(self._call_config)
        call_kwargs["drop_params"] = True
        try:
            response = await litellm.acompletion(messages=messages, **call_kwargs)
            return response.choices[0].message.content
        except Exception as e:
            raise RuntimeError(f"LLM call failed: {e}") from e
