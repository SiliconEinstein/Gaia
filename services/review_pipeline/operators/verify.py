"""Verify and Refine operators for abstraction trees."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from services.review_pipeline.base import Operator
from services.review_pipeline.context import AbstractionTree, PipelineContext
from services.review_pipeline.llm_client import LLMClient
from services.review_pipeline.xml_parser import parse_verify_output

_PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


def _load_prompt(name: str) -> str:
    return (_PROMPTS_DIR / f"{name}.md").read_text()


class VerifyLLM(ABC):
    @abstractmethod
    async def verify(self, trees: list[AbstractionTree]) -> list[AbstractionTree]:
        """Verify abstraction trees, setting verified=True/False on each."""
        ...


class StubVerifyLLM(VerifyLLM):
    """Auto-verifies all trees. For testing and Phase 1."""

    async def verify(self, trees: list[AbstractionTree]) -> list[AbstractionTree]:
        for tree in trees:
            tree.verified = True
        return trees


class LiteLLMVerifyClient(VerifyLLM):
    """Real verification via verify_abstraction prompt + litellm."""

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client
        self._prompt = _load_prompt("verify_abstraction")

    async def verify(self, trees: list[AbstractionTree]) -> list[AbstractionTree]:
        for tree in trees:
            user_input = self._build_input(tree)
            output = await self._llm.complete(self._prompt, user_input)
            result = parse_verify_output(output)
            tree.verified = result["passed"]
            # Pack quality info into reasoning
            quality = result.get("quality", {})
            parts: list[str] = []
            if result.get("checks"):
                for chk in result["checks"]:
                    entails = "entails" if chk["entails_parent"] else "does NOT entail"
                    parts.append(f"Child {chk['child']}: {entails}. {chk['reason']}")
            if quality.get("tightness"):
                parts.append(f"Tightness: {quality['tightness']}/5")
            if quality.get("substantiveness"):
                parts.append(f"Substantiveness: {quality['substantiveness']}/5")
            if quality.get("union_error"):
                parts.append(f"Union error: {quality.get('union_error_detail', '')}")
            tree.reasoning = " | ".join(parts) if parts else tree.reasoning
        return trees

    @staticmethod
    def _build_input(tree: AbstractionTree) -> str:
        lines = [
            "## PARENT (premises):",
            f"Content: {tree.source_content}",
            "",
            "## CHILDREN (conclusions):",
            f"### Child {tree.target_node_id}:",
            f"Content: {tree.target_content}",
            f"Relation: {tree.relation}",
            "",
        ]
        return "\n".join(lines)


class AbstractionTreeVerifyOperator(Operator):
    """First-pass verification of discovered abstraction trees."""

    def __init__(self, verify_llm: VerifyLLM | None = None) -> None:
        self._llm = verify_llm or StubVerifyLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        all_trees = context.cc_abstraction_trees + context.cp_abstraction_trees
        if all_trees:
            await self._llm.verify(all_trees)
        return context


class RefineOperator(Operator):
    """Refine abstraction trees — Phase 1: pass-through."""

    async def execute(self, context: PipelineContext) -> PipelineContext:
        return context


class VerifyAgainOperator(Operator):
    """Second verification pass. Collects all verified trees into verified_trees."""

    def __init__(self, verify_llm: VerifyLLM | None = None) -> None:
        self._llm = verify_llm or StubVerifyLLM()

    async def execute(self, context: PipelineContext) -> PipelineContext:
        all_trees = context.cc_abstraction_trees + context.cp_abstraction_trees
        if all_trees:
            await self._llm.verify(all_trees)
        context.verified_trees = [t for t in all_trees if t.verified]
        return context
