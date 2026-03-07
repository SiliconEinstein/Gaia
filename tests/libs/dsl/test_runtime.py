"""Tests for the DSL Runtime — Load -> Execute -> Infer -> Inspect pipeline."""

from pathlib import Path

from libs.dsl.runtime import DSLRuntime, RuntimeResult
from libs.dsl.executor import ActionExecutor

FIXTURE_DIR = Path(__file__).parents[2] / "fixtures" / "dsl_packages" / "galileo_falling_bodies"


class MockExecutor(ActionExecutor):
    def execute_infer(self, content: str, args: dict[str, str]) -> str:
        result = content
        for k, v in args.items():
            result = result.replace(f"{{{k}}}", v)
        return f"[推理结果] {result}"

    def execute_lambda(self, content: str, input_text: str) -> str:
        return f"[Lambda结果] {content}"


def test_runtime_full_pipeline():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)

    assert isinstance(result, RuntimeResult)
    assert result.package.name == "galileo_falling_bodies"
    assert len(result.beliefs) > 0
    assert result.factor_graph is not None


def test_runtime_beliefs_computed():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)

    # heavier_falls_faster has prior=0.7, after BP it should change
    assert "heavier_falls_faster" in result.beliefs
    # vacuum_prediction has prior=0.5
    assert "vacuum_prediction" in result.beliefs


def test_runtime_load_only():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.load(FIXTURE_DIR)

    assert result.package.name == "galileo_falling_bodies"
    assert len(result.package.loaded_modules) == 5
    # No beliefs yet (not inferred)
    assert len(result.beliefs) == 0


def test_runtime_inspect():
    runtime = DSLRuntime(executor=MockExecutor())
    result = runtime.run(FIXTURE_DIR)
    summary = result.inspect()

    # Should contain variable and factor counts
    assert "variables" in summary
    assert "factors" in summary
    assert "beliefs" in summary
