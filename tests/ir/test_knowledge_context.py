from gaia.ir.knowledge import KnowledgeType, Parameter


def test_context_knowledge_type():
    assert KnowledgeType.CONTEXT == "context"


def test_parameter_value_field():
    p = Parameter(name="experiment", type="Setting", value="github:pkg::exp_123")
    assert p.value == "github:pkg::exp_123"


def test_parameter_value_default_none():
    p = Parameter(name="x", type="int")
    assert p.value is None
