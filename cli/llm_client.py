"""LLM client for package review."""

from __future__ import annotations

import re
from pathlib import Path


class ReviewClient:
    """LLM-based package reviewer using litellm."""

    def __init__(self, model: str = "claude-sonnet-4-20250514"):
        self._model = model
        self._system_prompt = self._load_system_prompt()

    def _load_system_prompt(self) -> str:
        prompt_path = Path(__file__).parent / "prompts" / "review_system.md"
        return prompt_path.read_text()

    def review_package(self, package_data: dict) -> dict:
        """Review entire package in one LLM call."""
        import litellm

        md = package_data.get("markdown", "")
        response = litellm.completion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Review the following knowledge package:\n\n{md}"},
            ],
        )
        return self._parse_response(response.choices[0].message.content)

    async def areview_package(self, package_data: dict) -> dict:
        """Async version of review_package."""
        import litellm

        md = package_data.get("markdown", "")
        response = await litellm.acompletion(
            model=self._model,
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": f"Review the following knowledge package:\n\n{md}"},
            ],
        )
        return self._parse_response(response.choices[0].message.content)

    def _parse_response(self, response: str) -> dict:
        """Parse LLM YAML response."""
        import yaml

        try:
            parsed = yaml.safe_load(response)
            if isinstance(parsed, dict) and "chains" in parsed:
                return parsed
        except Exception:
            pass
        return {"summary": "Parse error — falling back to defaults.", "chains": []}

    # Backward compat
    def review_chain(self, chain_data: dict) -> dict:
        """Review a single chain (backward compat — delegates to MockReviewClient)."""
        return MockReviewClient().review_chain(chain_data)

    async def areview_chain(self, chain_data: dict) -> dict:
        """Async review a single chain (backward compat)."""
        return MockReviewClient().review_chain(chain_data)


class MockReviewClient:
    """Mock reviewer that parses step info from Markdown (no LLM calls)."""

    _STEP_RE = re.compile(r"\*\*\[step:([\w.]+\.(\d+))\]\*\*\s*\(prior=([\d.]+)\)")

    def review_package(self, package_data: dict) -> dict:
        """Parse all chains from package markdown."""
        md = package_data.get("markdown", "")
        chains = self._extract_chains(md)
        return {
            "summary": "Mock review — all steps accepted at author priors.",
            "chains": chains,
        }

    async def areview_package(self, package_data: dict) -> dict:
        """Async version — delegates to sync (no I/O)."""
        return self.review_package(package_data)

    def review_chain(self, chain_data: dict) -> dict:
        """Review a single chain (backward compat)."""
        md = chain_data.get("markdown", "")
        chains = self._extract_chains(md)
        if chains:
            return chains[0]
        return {"chain": chain_data.get("name", "?"), "steps": []}

    async def areview_chain(self, chain_data: dict) -> dict:
        """Async version — delegates to sync (no I/O)."""
        return self.review_chain(chain_data)

    def _extract_chains(self, md: str) -> list[dict]:
        """Extract chain reviews from markdown using [step:] anchors."""
        chain_steps: dict[str, list[dict]] = {}
        for match in self._STEP_RE.finditer(md):
            full_id = match.group(1)  # e.g. "synthesis_chain.2"
            prior = float(match.group(3))  # e.g. 0.94
            chain_name = full_id.rsplit(".", 1)[0]  # e.g. "synthesis_chain"

            chain_steps.setdefault(chain_name, []).append(
                {
                    "step": full_id,
                    "weak_points": [],
                    "conditional_prior": prior,
                    "explanation": "",
                }
            )

        return [{"chain": name, "steps": steps} for name, steps in chain_steps.items()]
