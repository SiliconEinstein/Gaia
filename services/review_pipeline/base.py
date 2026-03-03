"""Pipeline framework — Operator ABC, Pipeline orchestrator, ParallelStep."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

from services.review_pipeline.context import PipelineContext


class Operator(ABC):
    """Base class for all pipeline operators."""

    @abstractmethod
    async def execute(self, context: PipelineContext) -> PipelineContext:
        """Execute operator logic, reading from and writing to context."""
        ...

    async def cancel(self) -> None:
        """Cancel a running operation. Override if cleanup is needed."""
        pass


class ParallelStep:
    """Run multiple operators concurrently on the same context."""

    def __init__(self, *operators: Operator) -> None:
        self._operators = list(operators)

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if context.cancelled:
            return context
        await asyncio.gather(*(op.execute(context) for op in self._operators))
        return context

    async def cancel(self) -> None:
        await asyncio.gather(*(op.cancel() for op in self._operators))


class Pipeline:
    """Sequential pipeline that passes context through each step."""

    def __init__(self, steps: list[Operator | ParallelStep]) -> None:
        self._steps = steps
        self._cancelled = False

    async def execute(self, context: PipelineContext) -> PipelineContext:
        if self._cancelled:
            context.cancelled = True
        for step in self._steps:
            if context.cancelled:
                break
            context = await step.execute(context)
        return context

    async def cancel(self) -> None:
        self._cancelled = True
        for step in self._steps:
            await step.cancel()
