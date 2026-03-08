"""LLM client for chain review."""

from __future__ import annotations


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

    def _build_prompt(self, chain_data: dict) -> str:
        steps_desc = []
        for step in chain_data["steps"]:
            rendered = step.get("rendered", step.get("action", ""))
            args_desc = ", ".join(
                f"{a['ref']}({a.get('dependency', '?')})" for a in step.get("args", [])
            )
            steps_desc.append(
                f"Step {step['step']}: {rendered}\n  Args: {args_desc}\n  Prior: {step.get('prior', '?')}"
            )
        steps_text = "\n".join(steps_desc)

        return (
            f"Review this reasoning chain: {chain_data['name']}\n\n"
            f"Steps:\n{steps_text}\n\n"
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
            "        suggested: direct  # or indirect\n"
        )

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
    """Mock reviewer that echoes existing priors and dependencies (no LLM calls)."""

    def review_chain(self, chain_data: dict) -> dict:
        """Return a review that preserves all existing values."""
        steps = []
        for step in chain_data.get("steps", []):
            deps = []
            for arg in step.get("args", []):
                deps.append({
                    "ref": arg["ref"],
                    "suggested": arg.get("dependency", "direct"),
                })
            steps.append({
                "step": step["step"],
                "assessment": "valid",
                "suggested_prior": step.get("prior", 0.9),
                "rewrite": None,
                "dependencies": deps,
            })
        return {
            "chain": chain_data["name"],
            "steps": steps,
        }
