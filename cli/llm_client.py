"""LLM client for chain review."""

from __future__ import annotations

import re


class ReviewClient:
    """LLM-based chain reviewer using litellm."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self._model = model

    def review_chain(self, chain_data: dict) -> dict:
        """Review a single chain and return assessment."""
        import litellm

        prompt = self._build_prompt(chain_data)
        response = litellm.completion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(chain_data, response.choices[0].message.content)

    async def areview_chain(self, chain_data: dict) -> dict:
        """Async review a single chain and return assessment."""
        import litellm

        prompt = self._build_prompt(chain_data)
        response = await litellm.acompletion(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._parse_response(chain_data, response.choices[0].message.content)

    def _build_prompt(self, chain_data: dict) -> str:
        md = chain_data.get("markdown", "")
        if md:
            return (
                f"Review this reasoning chain:\n\n{md}\n\n"
                "For each step, assess whether the reasoning is logically valid.\n"
                "For each dependency, decide if it is 'direct' (conclusion depends on it) "
                "or 'indirect' (conclusion may still hold without it).\n\n"
                "Reply with ONLY a YAML document (no markdown fences, no extra text) "
                "in this exact format:\n\n"
                "steps:\n"
                "  - step: <number>\n"
                "    assessment: valid  # or questionable\n"
                "    suggested_prior: <float 0-1>\n"
                "    rewrite: null\n"
                "    dependencies:\n"
                "      - ref: <arg_name>\n"
                "        suggested: direct  # or indirect"
            )
        # Fallback for old-format chain_data (backward compat)
        return f"Review: {chain_data.get('name', '?')}"

    def _parse_response(self, chain_data: dict, response: str) -> dict:
        """Parse LLM response into review dict. Falls back to passthrough on failure."""
        import yaml

        try:
            parsed = yaml.safe_load(response)
            if isinstance(parsed, dict) and "steps" in parsed:
                parsed["chain"] = chain_data["name"]
                return parsed
        except Exception:
            pass

        return MockReviewClient().review_chain(chain_data)


class MockReviewClient:
    """Mock reviewer that parses step info from Markdown (no LLM calls)."""

    async def areview_chain(self, chain_data: dict) -> dict:
        """Async version — delegates to sync (no I/O)."""
        return self.review_chain(chain_data)

    def review_chain(self, chain_data: dict) -> dict:
        """Return a review that preserves all existing values from Markdown."""
        steps = []
        md = chain_data.get("markdown", "")
        for match in re.finditer(r"\*\*Step (\d+)", md):
            step_num = int(match.group(1))
            # Extract prior if present: (prior=0.93)
            after = md[match.end() : match.end() + 50]
            prior_match = re.search(r"prior=([\d.]+)", after)
            prior = float(prior_match.group(1)) if prior_match else 0.9
            steps.append(
                {
                    "step": step_num,
                    "assessment": "valid",
                    "suggested_prior": prior,
                    "rewrite": None,
                    "dependencies": [],
                }
            )
        return {"chain": chain_data["name"], "steps": steps}
