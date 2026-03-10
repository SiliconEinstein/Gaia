"""Shared test fixtures for Gaia Language tests."""

from libs.lang.executor import ActionExecutor


class MockExecutor(ActionExecutor):
    """Mock executor with call tracking and prefixed responses."""

    def __init__(self):
        self.calls: list[dict] = []

    async def execute_infer(self, prompt: str) -> str:
        self.calls.append({"type": "infer", "prompt": prompt})
        return f"[推理结果] {prompt}"

    async def execute_lambda(self, content: str, input_text: str) -> str:
        self.calls.append({"type": "lambda", "content": content, "input": input_text})
        return f"[Lambda结果] {content}"

    async def execute_tool(self, tool: str, prompt: str) -> str:
        self.calls.append({"type": "tool", "tool": tool, "prompt": prompt})
        return f"[Tool结果] {tool}: {prompt}"


class PassthroughExecutor(ActionExecutor):
    """Executor that returns content as-is (no prefix). For integration tests."""

    async def execute_infer(self, prompt: str) -> str:
        return prompt

    async def execute_lambda(self, content: str, input_text: str) -> str:
        return content

    async def execute_tool(self, tool: str, prompt: str) -> str:
        return prompt
