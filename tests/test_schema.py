"""Schema check: JSON parsing plus the supported JSON Schema subset."""

from gar.checks.schema import check_schema, validate
from gar.models import EvalCase, Turn


def make_case(**kwargs) -> EvalCase:
    return EvalCase(id="t", prompt="p", **kwargs)


def test_valid_object_passes():
    schema = {
        "type": "object",
        "properties": {"a": {"type": "string"}},
        "required": ["a"],
    }
    assert validate({"a": "x"}, schema) == []


def test_missing_required_is_reported():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "required": ["a"]}
    errors = validate({}, schema)
    assert any("missing required property 'a'" in e for e in errors)


def test_wrong_type_short_circuits_nested_checks():
    schema = {"type": "object", "properties": {"a": {"type": "string", "maxLength": 3}}}
    errors = validate({"a": 5}, schema)
    assert len(errors) == 1
    assert "expected type string" in errors[0]


def test_additional_properties_false_is_enforced():
    schema = {"type": "object", "properties": {"a": {"type": "string"}}, "additionalProperties": False}
    errors = validate({"a": "x", "b": "y"}, schema)
    assert any("unexpected property 'b'" in e for e in errors)


def test_enum_min_max_pattern_and_length():
    schema = {
        "type": "object",
        "properties": {
            "level": {"type": "string", "enum": ["low", "high"]},
            "count": {"type": "integer", "minimum": 1, "maximum": 5},
            "slug": {"type": "string", "pattern": "^[a-z]+$", "minLength": 2},
        },
    }
    errors = validate({"level": "medium", "count": 9, "slug": "A"}, schema)
    assert len(errors) == 4  # enum, maximum, minLength, pattern


def test_array_items_are_validated_per_element():
    schema = {"type": "array", "items": {"type": "integer"}}
    assert validate([1, 2, 3], schema) == []
    assert validate([1, "two"], schema)


def test_boolean_is_not_an_integer():
    assert validate(True, {"type": "integer"})


def test_check_schema_passes_on_valid_json():
    case = make_case(output_schema={"type": "object", "required": ["a"], "properties": {"a": {"type": "string"}}})
    turn = Turn(text='{"a": "ok"}')
    assert check_schema(turn, case).passed


def test_check_schema_fails_on_truncated_json():
    case = make_case(output_schema={"type": "object"})
    result = check_schema(Turn(text='{"a": '), case)
    assert not result.passed
    assert "not valid JSON" in result.detail


def test_check_schema_fails_on_empty_output():
    case = make_case(output_schema={"type": "object"})
    result = check_schema(Turn(text="   "), case)
    assert not result.passed


def test_check_schema_is_neutral_when_no_schema_declared():
    result = check_schema(Turn(text="free text"), make_case())
    assert result.passed
    assert result.weight < 1.0
