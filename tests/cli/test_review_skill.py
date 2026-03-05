"""Tests for review skill input/output formatting."""

from cli.review_skill import format_review_input, parse_review_output


def test_format_review_input():
    claim = {
        "id": 5007,
        "content": "矛盾",
        "type": "deduction",
        "why": "两个推导矛盾",
        "premise": [5005, 5006],
        "context": [],
    }
    all_claims = {
        5005: {"id": 5005, "content": "推导A"},
        5006: {"id": 5006, "content": "推导B"},
        5007: claim,
    }
    result = format_review_input(claim, all_claims)
    assert "5007" in result
    assert "推导A" in result
    assert "推导B" in result


def test_parse_review_output():
    raw = """
score: 0.95
justification: "纯逻辑演绎"
confirmed_premises: [5005, 5006]
downgraded_premises: []
upgraded_context: []
irrelevant: []
suggested_premise: []
suggested_context: []
"""
    result = parse_review_output(raw)
    assert result["score"] == 0.95
    assert result["confirmed_premises"] == [5005, 5006]


def test_parse_review_output_with_yaml_fence():
    """LLM may wrap output in ```yaml``` fences."""
    raw = "```yaml\nscore: 0.80\njustification: \"test\"\nconfirmed_premises: []\ndowngraded_premises: []\nupgraded_context: []\nirrelevant: []\nsuggested_premise: []\nsuggested_context: []\n```"
    result = parse_review_output(raw)
    assert result["score"] == 0.80


def test_load_skill_prompt():
    from cli.review_skill import load_skill_prompt
    prompt = load_skill_prompt("v1.0")
    assert "科学推理评审员" in prompt
    assert "score" in prompt
