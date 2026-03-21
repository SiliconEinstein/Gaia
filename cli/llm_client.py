"""LLM client for package review."""

from __future__ import annotations

import re
from pathlib import Path


class ReviewClient:
    """LLM-based package reviewer using litellm."""

    _CODE_FENCE_RE = re.compile(r"```(?:yaml|yml)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
    _STEP_ID_RE = re.compile(r"^[\w.-]+\.\d+$")

    def __init__(self, model: str = "gpt-5-mini"):
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

        text = response.strip()
        fenced = self._CODE_FENCE_RE.search(text)
        if fenced:
            text = fenced.group(1).strip()

        try:
            parsed = yaml.safe_load(text)
            normalized = self._normalize_review_payload(parsed)
            if normalized is not None:
                return normalized
        except Exception:
            pass
        return {"summary": "Parse error — falling back to defaults.", "chains": []}

    def _normalize_review_payload(self, parsed: object) -> dict | None:
        """Normalize several YAML shapes into the sidecar schema used by the CLI."""
        if not isinstance(parsed, dict):
            return None

        if "chains" in parsed:
            return {
                "summary": parsed.get("summary", "") or "",
                "chains": self._normalize_chain_entries(parsed.get("chains", [])),
            }

        flat_chains = self._normalize_flat_step_map(parsed)
        if flat_chains:
            summary = parsed.get("summary", "")
            return {"summary": summary if isinstance(summary, str) else "", "chains": flat_chains}

        return None

    def _normalize_chain_entries(self, chains: object) -> list[dict]:
        """Normalize mixed chain entry formats into {chain, steps} objects."""
        if isinstance(chains, dict):
            chain_items = list(chains.values())
        elif isinstance(chains, list):
            chain_items = chains
        else:
            return []

        normalized: list[dict] = []
        for chain_entry in chain_items:
            if not isinstance(chain_entry, dict):
                continue

            chain_name = chain_entry.get("chain") or chain_entry.get("name")
            if not isinstance(chain_name, str) or not chain_name:
                continue

            steps = self._normalize_step_entries(chain_entry.get("steps", []))
            if not steps:
                continue

            normalized.append({"chain": chain_name, "steps": steps})

        return normalized

    def _normalize_step_entries(self, steps: object) -> list[dict]:
        """Normalize step payloads, preserving the fields consumed downstream."""
        if isinstance(steps, dict):
            step_items = list(steps.values())
        elif isinstance(steps, list):
            step_items = steps
        else:
            return []

        normalized: list[dict] = []
        for step_entry in step_items:
            if not isinstance(step_entry, dict):
                continue

            step_id = step_entry.get("step") or step_entry.get("step_id")
            if not isinstance(step_id, str) or not step_id:
                continue

            step: dict[str, object] = {
                "step": step_id,
                "weak_points": step_entry.get("weak_points", []) or [],
                "explanation": step_entry.get("explanation", "") or "",
            }

            conditional_prior = step_entry.get("conditional_prior")
            if conditional_prior is None:
                conditional_prior = step_entry.get("suggested_prior")
            if conditional_prior is not None:
                step["conditional_prior"] = conditional_prior

            normalized.append(step)

        return normalized

    def _normalize_flat_step_map(self, parsed: dict) -> list[dict]:
        """Handle flat YAML like `chain_name.2: {conditional_prior: ...}`."""
        grouped: dict[str, list[dict]] = {}
        for key, value in parsed.items():
            if key == "summary" or not isinstance(key, str) or not isinstance(value, dict):
                continue
            if not self._STEP_ID_RE.match(key):
                continue

            chain_name = key.rsplit(".", 1)[0]
            step = {
                "step": key,
                "weak_points": value.get("weak_points", []) or [],
                "explanation": value.get("explanation", "") or "",
            }
            conditional_prior = value.get("conditional_prior")
            if conditional_prior is None:
                conditional_prior = value.get("suggested_prior")
            if conditional_prior is not None:
                step["conditional_prior"] = conditional_prior
            grouped.setdefault(chain_name, []).append(step)

        normalized = []
        for chain_name, steps in grouped.items():
            steps.sort(
                key=lambda step: (
                    int(str(step["step"]).rsplit(".", 1)[1]) if "." in str(step["step"]) else 0
                )
            )
            normalized.append({"chain": chain_name, "steps": steps})
        return normalized

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

    def review_from_graph_data(self, graph_data: dict) -> dict:
        """Generate mock review from v3 Typst graph_data."""
        chains = []
        for factor in graph_data.get("factors", []):
            if factor.get("type") != "reasoning":
                continue
            conclusion = factor["conclusion"]
            chains.append(
                {
                    "chain": conclusion,
                    "steps": [
                        {
                            "step": f"{conclusion}.1",
                            "conditional_prior": 0.85,
                            "weak_points": [],
                            "explanation": "Mock review — accepted at default prior.",
                        }
                    ],
                }
            )
        return {
            "summary": "Mock review — all factors accepted at default priors.",
            "chains": chains,
        }

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
