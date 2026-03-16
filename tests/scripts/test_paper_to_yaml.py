"""Tests for paper_to_yaml XML parsing and YAML generation."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Import from scripts directory
sys.path.insert(0, str(Path(__file__).parents[2] / "scripts"))


class TestParseStep1:
    def test_parses_motivation(self):
        xml = """<inference_unit>
        <problem>The field lacks a method for X.</problem>
        <conclusions>
            <conclusion id="1" title="Result A">Content A
                <problem>Specific gap A</problem>
                <ref>Fig. 1</ref>
            </conclusion>
            <conclusion id="2" title="Result B">Content B
                <problem>Specific gap B</problem>
            </conclusion>
        </conclusions>
        <logic_graph>
            <edge from="1" to="2"/>
        </logic_graph>
        <open_question>Future work remains.</open_question>
        </inference_unit>"""

        from paper_to_yaml import parse_step1_xml

        result = parse_step1_xml(xml)

        assert result["motivation"] == "The field lacks a method for X."
        assert len(result["conclusions"]) == 2
        assert result["conclusions"][0]["id"] == "1"
        assert result["conclusions"][0]["title"] == "Result A"
        assert "Content A" in result["conclusions"][0]["content"]
        assert result["conclusions"][0]["problem"] == "Specific gap A"
        assert result["conclusions"][0]["ref"] == "Fig. 1"
        assert result["logic_graph"] == [("1", "2")]
        assert result["open_questions"] == "Future work remains."

    def test_handles_pass(self):
        xml = """<inference_unit>
        <pass/>
        <reason>Review article, no original results.</reason>
        </inference_unit>"""

        from paper_to_yaml import parse_step1_xml

        result = parse_step1_xml(xml)
        assert result is None


class TestParseStep2:
    def test_parses_reasoning_chains(self):
        xml = """<inference_unit>
        <conclusion_reasoning conclusion_id="1">
        <reasoning>
        <step id="1">First reasoning step.
            <ref type="citation">[14]</ref>
            <ref type="figure">Fig. 2</ref>
        </step>
        <step id="2">Second step using [@premise-1].</step>
        </reasoning>
        <conclusion id="1" title="Result A">Content A</conclusion>
        </conclusion_reasoning>
        </inference_unit>"""

        from paper_to_yaml import parse_step2_xml

        result = parse_step2_xml(xml)

        assert len(result) == 1
        chain = result[0]
        assert chain["conclusion_id"] == "1"
        assert chain["conclusion_title"] == "Result A"
        assert chain["conclusion_content"] == "Content A"
        assert len(chain["steps"]) == 2
        assert chain["steps"][0]["id"] == "1"
        assert "[14]" in chain["steps"][0]["text"]
        assert "Fig. 2" in chain["steps"][0]["text"]
        assert chain["steps"][0]["citations"] == ["[14]"]
        assert chain["steps"][0]["figures"] == ["Fig. 2"]


class TestParseStep3:
    def test_parses_review(self):
        xml = """<inference_unit>
        <premises>
        <premise id="P1" conclusion_id="1" step_id="2" prior_probability="0.85"
                 title="Weak coupling" name="weak_coupling_approx">
            The system is in the weak-coupling regime.
            <ref type="citation">[3]</ref>
        </premise>
        </premises>
        <contexts>
        <context id="C1" conclusion_id="1" step_id="4"
                 title="Historical note" name="historical_context">
            Previous work used a similar approach.
        </context>
        </contexts>
        <conclusions>
        <conclusion id="1" conditional_probability="0.90">
            Reasoning is sound given premises.
            <cross_ref>[@conclusion-2]</cross_ref>
        </conclusion>
        <conclusion id="2" conditional_probability="0.85">
            Independent conclusion.
        </conclusion>
        </conclusions>
        </inference_unit>"""

        from paper_to_yaml import parse_step3_xml

        result = parse_step3_xml(xml)

        assert len(result["premises"]) == 1
        p = result["premises"][0]
        assert p["id"] == "P1"
        assert p["conclusion_id"] == "1"
        assert p["step_id"] == "2"
        assert p["prior"] == 0.85
        assert p["name"] == "weak_coupling_approx"
        assert "weak-coupling" in p["content"]
        assert "[3]" in p["content"]

        assert len(result["contexts"]) == 1
        c = result["contexts"][0]
        assert c["name"] == "historical_context"

        assert result["conclusions"]["1"]["conditional_probability"] == 0.90
        assert result["conclusions"]["1"]["cross_refs"] == ["2"]
        assert result["conclusions"]["2"]["cross_refs"] == []


class TestParseStep1WithFixture:
    """Test with real XML fixtures from tests/fixtures/inputs/papers_xml/."""

    def test_parse_real_select_conclusion(self):
        fixture = Path("tests/fixtures/inputs/papers_xml/363056a0/select_conclusion.xml")
        if not fixture.exists():
            pytest.skip("Fixture not available")

        from paper_to_yaml import parse_step1_xml

        result = parse_step1_xml(fixture.read_text())
        assert result is not None
        assert len(result["conclusions"]) >= 1
        assert all(c["title"] for c in result["conclusions"])


class TestParseStep2WithFixture:
    def test_parse_real_reasoning_chain(self):
        """Test with real fixture.

        Note: existing fixtures use a different XML format (premises + reasoning + conclusion)
        rather than the Step 2 prompt output format (conclusion_reasoning). This test verifies
        parsing works with properly structured Step 2 XML.
        """
        from paper_to_yaml import parse_step2_xml

        # Use synthetic XML matching Step 2 output format since fixtures use combine format
        xml = """<inference_unit>
        <conclusion_reasoning conclusion_id="1">
        <reasoning>
        <step id="1" title="Setup">Starting point.</step>
        <step id="2" title="Derivation">Key derivation step.
            <ref type="citation">[1]</ref>
        </step>
        </reasoning>
        <conclusion id="1" title="Main Result">The main finding.</conclusion>
        </conclusion_reasoning>
        <conclusion_reasoning conclusion_id="2">
        <reasoning>
        <step id="1" title="Extension">Building on result 1.</step>
        </reasoning>
        <conclusion id="2" title="Secondary Result">A secondary finding.</conclusion>
        </conclusion_reasoning>
        </inference_unit>"""

        result = parse_step2_xml(xml)
        assert len(result) == 2
        assert result[0]["conclusion_id"] == "1"
        assert len(result[0]["steps"]) == 2
        assert result[1]["conclusion_id"] == "2"


class TestBuildPackage:
    """Test YAML generation from parsed XML data."""

    @pytest.fixture
    def parsed_data(self):
        """Minimal parsed data combining all 3 steps."""
        return {
            "slug": "paper_test",
            "doi": "test_paper",
            "step1": {
                "motivation": "The field lacks method X.",
                "conclusions": [
                    {
                        "id": "1",
                        "title": "Result A",
                        "content": "We found A.",
                        "problem": "Gap A",
                        "ref": "Fig. 1",
                    },
                    {
                        "id": "2",
                        "title": "Result B",
                        "content": "We found B.",
                        "problem": "Gap B",
                        "ref": "",
                    },
                ],
                "logic_graph": [("1", "2")],
                "open_questions": "Future work on C.",
            },
            "step2": [
                {
                    "conclusion_id": "1",
                    "conclusion_title": "Result A",
                    "conclusion_content": "We found A.",
                    "steps": [
                        {
                            "id": "1",
                            "text": "Starting from assumption X.",
                            "citations": ["[3]"],
                            "figures": [],
                        },
                        {
                            "id": "2",
                            "text": "Therefore A holds.",
                            "citations": [],
                            "figures": ["Fig. 1"],
                        },
                    ],
                },
                {
                    "conclusion_id": "2",
                    "conclusion_title": "Result B",
                    "conclusion_content": "We found B.",
                    "steps": [
                        {
                            "id": "1",
                            "text": "Using result of conclusion 1.",
                            "citations": [],
                            "figures": [],
                        },
                        {
                            "id": "2",
                            "text": "We derive B.",
                            "citations": [],
                            "figures": [],
                        },
                    ],
                },
            ],
            "step3": {
                "premises": [
                    {
                        "id": "P1",
                        "conclusion_id": "1",
                        "step_id": "1",
                        "prior": 0.85,
                        "name": "assumption_x",
                        "title": "Assumption X",
                        "content": "System is in regime X. [[3]]",
                    },
                ],
                "contexts": [
                    {
                        "id": "C1",
                        "conclusion_id": "2",
                        "step_id": "1",
                        "name": "historical_note",
                        "title": "Historical Note",
                        "content": "Previous work used similar.",
                    },
                ],
                "conclusions": {
                    "1": {"conditional_probability": 0.90, "cross_refs": []},
                    "2": {"conditional_probability": 0.85, "cross_refs": ["1"]},
                },
            },
        }

    def test_package_yaml(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        pkg = result["package.yaml"]
        assert pkg["name"] == "paper_test"
        assert "motivation" in pkg["modules"]
        assert "setting" in pkg["modules"]
        assert "reasoning" in pkg["modules"]
        assert "follow_up" in pkg["modules"]

    def test_motivation_yaml(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        mot = result["motivation.yaml"]
        assert mot["type"] == "setting_module"
        assert mot["knowledge"][0]["content"] == "The field lacks method X."
        assert mot["knowledge"][0]["prior"] == 0.9

    def test_setting_yaml_has_premises_and_contexts(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        setting = result["setting.yaml"]
        names = [k["name"] for k in setting["knowledge"]]
        assert "assumption_x" in names
        assert "historical_note" in names

        # Premise has its own prior
        premise = next(k for k in setting["knowledge"] if k["name"] == "assumption_x")
        assert premise["prior"] == 0.85
        assert premise["dependency"] == "direct"

        # Context has default prior
        context = next(k for k in setting["knowledge"] if k["name"] == "historical_note")
        assert context["prior"] == 0.7
        assert context["dependency"] == "indirect"

    def test_reasoning_yaml_has_refs_claims_chains(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        reasoning = result["reasoning.yaml"]
        types = [k["type"] for k in reasoning["knowledge"]]
        assert "ref" in types
        assert "claim" in types
        assert "chain_expr" in types

    def test_reasoning_yaml_cross_conclusion_ref(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        reasoning = result["reasoning.yaml"]
        # Conclusion 2 depends on conclusion 1 (from logic_graph)
        refs = [k for k in reasoning["knowledge"] if k["type"] == "ref"]
        ref_targets = [r["target"] for r in refs]
        # Should have a cross-conclusion ref
        assert any("reasoning." in t for t in ref_targets)

    def test_follow_up_yaml(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        fu = result["follow_up.yaml"]
        assert fu["knowledge"][0]["type"] == "question"
        assert "Future work" in fu["knowledge"][0]["content"]

    def test_no_follow_up_when_empty(self, parsed_data):
        parsed_data["step1"]["open_questions"] = ""
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        assert "follow_up.yaml" not in result
        assert "follow_up" not in result["package.yaml"]["modules"]

    def test_chain_steps_preserve_refs(self, parsed_data):
        from paper_to_yaml import build_package

        result = build_package(parsed_data)

        reasoning = result["reasoning.yaml"]
        chains = [k for k in reasoning["knowledge"] if k["type"] == "chain_expr"]
        assert len(chains) == 2

        # First chain should have steps referencing premise
        chain1 = chains[0]
        step_types = [("ref" if "ref" in s else "lambda") for s in chain1["steps"]]
        assert "lambda" in step_types  # has reasoning steps
