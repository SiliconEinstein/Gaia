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
        context = chain_data.get("context")
        parts = [f"Review this reasoning chain: {chain_data['name']}"]

        # Chain type from context
        if context:
            parts.append(f"Chain type: {context.get('edge_type', 'deduction')}")

            # Premises
            premises = context.get("premise_refs", [])
            if premises:
                parts.append("\nPremises:")
                for p in premises:
                    snippet = (p.get("content") or "").strip()[:80]
                    prior_str = f", prior={p['prior']}" if p.get("prior") is not None else ""
                    parts.append(f"  - {p['name']} ({p.get('type', '?')}{prior_str}): \"{snippet}\"")

        # Steps
        parts.append("\nSteps:")
        for step in chain_data["steps"]:
            rendered = step.get("rendered", step.get("action", ""))
            parts.append(f"  Step {step['step']}: {rendered}")

            # Split args into direct (Evidence) and indirect (Context)
            direct_args = [a for a in step.get("args", []) if a.get("dependency") == "direct"]
            indirect_args = [a for a in step.get("args", []) if a.get("dependency") != "direct"]

            if direct_args:
                parts.append("    Evidence (direct):")
                for a in direct_args:
                    snippet = (a.get("content") or "").strip()[:60]
                    dtype = a.get("decl_type", "?")
                    prior_str = f", prior={a['prior']}" if a.get("prior") is not None else ""
                    parts.append(f"      - {a['ref']} ({dtype}{prior_str}): \"{snippet}\"")
            if indirect_args:
                parts.append("    Context (indirect):")
                for a in indirect_args:
                    snippet = (a.get("content") or "").strip()[:60]
                    dtype = a.get("decl_type", "?")
                    parts.append(f"      - {a['ref']} ({dtype}): \"{snippet}\"")

            prior = step.get("prior")
            if prior is not None:
                parts.append(f"    Step prior: {prior}")

        # Conclusions from context
        if context:
            conclusions = context.get("conclusion_refs", [])
            if conclusions:
                parts.append("\nConclusion:")
                for c in conclusions:
                    prior_str = f", prior={c['prior']}" if c.get("prior") is not None else ""
                    parts.append(f"  - {c['name']} ({c.get('type', '?')}{prior_str})")

        # Assessment instructions
        parts.append(
            "\nFor each step, assess whether the reasoning is logically valid.\n"
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

        return "\n".join(parts)

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

    async def areview_chain(self, chain_data: dict) -> dict:
        """Async version — delegates to sync (no I/O)."""
        return self.review_chain(chain_data)

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
