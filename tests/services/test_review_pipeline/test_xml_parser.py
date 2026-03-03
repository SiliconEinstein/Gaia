"""Tests for XML parsing utilities."""

from services.review_pipeline.xml_parser import parse_join_output, parse_verify_output


# ---------------------------------------------------------------------------
# parse_join_output
# ---------------------------------------------------------------------------

SAMPLE_JOIN_XML = """\
<analysis anchor="0">
  <candidate id="42" relation="equivalence">
    <reason>Both state the same result for band gap of MoS2.</reason>
  </candidate>
  <candidate id="99" relation="subsumption" direction="candidate_more_specific">
    <reason>Candidate specifies monolayer while anchor is general.</reason>
  </candidate>
  <candidate id="101" relation="subsumption" direction="anchor_more_specific">
    <reason>Anchor specifies temperature while candidate is general.</reason>
  </candidate>
  <candidate id="55" relation="contradiction">
    <reason>Anchor says 1.8 eV, candidate says 2.1 eV for same system.</reason>
  </candidate>
  <candidate id="77" relation="unrelated">
    <reason>Different topic entirely.</reason>
  </candidate>
</analysis>
"""


def test_parse_join_output_basic():
    trees = parse_join_output(SAMPLE_JOIN_XML, anchor_index=3)
    assert len(trees) == 4  # unrelated is excluded

    by_target = {t.target_node_id: t for t in trees}
    assert by_target[42].relation == "equivalent"
    assert by_target[99].relation == "subsumed_by"
    assert by_target[101].relation == "subsumes"
    assert by_target[55].relation == "contradiction"

    # All have same source index
    for t in trees:
        assert t.source_node_index == 3
        assert t.verified is False
        assert t.reasoning != ""


def test_parse_join_output_markdown_wrapped():
    wrapped = f"```xml\n{SAMPLE_JOIN_XML}\n```"
    trees = parse_join_output(wrapped, anchor_index=0)
    assert len(trees) == 4


def test_parse_join_output_empty_analysis():
    xml = '<analysis anchor="0"></analysis>'
    trees = parse_join_output(xml, anchor_index=0)
    assert trees == []


def test_parse_join_output_special_chars_in_reason():
    xml = """\
<analysis anchor="0">
  <candidate id="1" relation="equivalence">
    <reason>Both use E = mc^2 &amp; discuss energy-mass relation.</reason>
  </candidate>
</analysis>
"""
    trees = parse_join_output(xml, anchor_index=0)
    assert len(trees) == 1
    assert "&" in trees[0].reasoning


# ---------------------------------------------------------------------------
# parse_verify_output
# ---------------------------------------------------------------------------

SAMPLE_VERIFY_XML = """\
<verification edge_id="10" type="join">
  <result>pass</result>
  <checks>
    <check child="5" entails_parent="true">
      <reason>Child directly implies the parent claim.</reason>
    </check>
    <check child="6" entails_parent="false">
      <reason>Child discusses different property.</reason>
    </check>
  </checks>
  <quality>
    <classification_correct>true</classification_correct>
    <suggested_classification>partial_overlap</suggested_classification>
    <union_error>false</union_error>
    <union_error_detail></union_error_detail>
    <tightness>4</tightness>
    <substantiveness>5</substantiveness>
  </quality>
</verification>
"""


def test_parse_verify_output_pass():
    result = parse_verify_output(SAMPLE_VERIFY_XML)
    assert result["passed"] is True
    assert len(result["checks"]) == 2
    assert result["checks"][0]["child"] == 5
    assert result["checks"][0]["entails_parent"] is True
    assert result["checks"][1]["entails_parent"] is False
    assert result["quality"]["tightness"] == 4
    assert result["quality"]["substantiveness"] == 5
    assert result["quality"]["union_error"] is False
    assert result["quality"]["classification_correct"] is True


def test_parse_verify_output_fail():
    xml = """\
<verification edge_id="20" type="join">
  <result>fail</result>
  <checks>
    <check child="7" entails_parent="false">
      <reason>No entailment.</reason>
    </check>
  </checks>
  <quality>
    <classification_correct>false</classification_correct>
    <suggested_classification>unrelated</suggested_classification>
    <union_error>true</union_error>
    <union_error_detail>Parent combines claims from different children.</union_error_detail>
    <tightness>2</tightness>
    <substantiveness>1</substantiveness>
  </quality>
</verification>
"""
    result = parse_verify_output(xml)
    assert result["passed"] is False
    assert result["quality"]["union_error"] is True
    assert result["quality"]["tightness"] == 2
    assert result["quality"]["substantiveness"] == 1


def test_parse_verify_output_markdown_wrapped():
    wrapped = f"```xml\n{SAMPLE_VERIFY_XML}\n```"
    result = parse_verify_output(wrapped)
    assert result["passed"] is True
