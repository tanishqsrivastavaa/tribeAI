import pytest

from tribe.tools.base import (
    Tool,
    ToolContext,
    ToolResult,
    ToolValidationError,
    validate_args,
)


def test_result_ok_and_fail():
    ok = ToolResult.ok("out", n=1)
    assert not ok.is_error and ok.output == "out" and ok.metadata["n"] == 1
    bad = ToolResult.fail("boom")
    assert bad.is_error and bad.error == "boom"


def test_validate_requires_fields():
    schema = {"type": "object", "properties": {"p": {"type": "string"}}, "required": ["p"]}
    with pytest.raises(ToolValidationError):
        validate_args({}, schema)
    validate_args({"p": "x"}, schema)


def test_validate_checks_types():
    schema = {"type": "object", "properties": {"n": {"type": "integer"}}}
    with pytest.raises(ToolValidationError):
        validate_args({"n": "not-int"}, schema)
    validate_args({"n": 5}, schema)


def test_invoke_validates_before_running():
    class Dummy(Tool):
        name = "dummy"
        description = "d"
        input_schema = {"type": "object", "properties": {}, "required": ["x"]}

        def run(self, args, ctx):
            return ToolResult.ok("ran")

    with pytest.raises(ToolValidationError):
        Dummy().invoke({}, ToolContext(workspace=None))


def test_spec_shape():
    class Dummy(Tool):
        name = "dummy"
        description = "d"
        input_schema = {"type": "object", "properties": {}}

        def run(self, args, ctx):
            return ToolResult.ok()

    spec = Dummy().spec()
    assert spec == {"name": "dummy", "description": "d", "input_schema": {"type": "object", "properties": {}}}
