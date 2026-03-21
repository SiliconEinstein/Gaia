"""Tests for paper_to_typst.py."""

from __future__ import annotations

import sys
from pathlib import Path

# paper_to_typst.py imports from paper_to_yaml (which lives in scripts/pipeline/)
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts" / "pipeline"))


class TestReasoningStepsJson:
    """Test reasoning_steps.json sidecar generation."""

    def test_build_reasoning_steps(self):
        from scripts.paper_to_typst import build_reasoning_steps

        step2_data = [
            {
                "conclusion_id": "1",
                "conclusion_title": "Result A",
                "conclusion_content": "We found A.",
                "steps": [
                    {"id": "1", "text": "Starting from X.", "citations": [], "figures": []},
                    {"id": "2", "text": "Therefore A.", "citations": ["[3]"], "figures": []},
                ],
            },
        ]
        conclusion_names = {"1": "result_a"}

        result = build_reasoning_steps(step2_data, conclusion_names)

        assert "result_a" in result
        assert len(result["result_a"]) == 2
        assert result["result_a"][0]["step_index"] == 0
        assert result["result_a"][0]["reasoning"] == "Starting from X."
        assert result["result_a"][1]["step_index"] == 1
        assert result["result_a"][1]["reasoning"] == "Therefore A."

    def test_build_reasoning_steps_empty(self):
        from scripts.paper_to_typst import build_reasoning_steps

        result = build_reasoning_steps([], {})
        assert result == {}
