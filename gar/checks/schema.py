"""Structured-output integrity: does the model's JSON satisfy the declared schema?

The validator is a deliberate subset of JSON Schema (draft-07 vocabulary) covering the keywords
that actually appear in agent response schemas. Unsupported keywords are ignored rather than
guessed at, so the check never fails a model for something it did not test.
"""

from __future__ import annotations

import json
import re
from typing import Any

from ..models import CheckResult, EvalCase, Turn

SUPPORTED_KEYWORDS = {
    "type",
    "required",
    "properties",
    "items",
    "enum",
    "minimum",
    "maximum",
    "minLength",
    "maxLength",
    "pattern",
    "additionalProperties",
}


def _type_matches(instance: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(instance, dict)
    if expected == "array":
        return isinstance(instance, list)
    if expected == "string":
        return isinstance(instance, str)
    if expected == "integer":
        return isinstance(instance, int) and not isinstance(instance, bool)
    if expected == "number":
        return isinstance(instance, (int, float)) and not isinstance(instance, bool)
    if expected == "boolean":
        return isinstance(instance, bool)
    if expected == "null":
        return instance is None
    return True  # unknown type keyword: do not penalise


def validate(instance: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    """Return a list of human-readable violations (empty list means valid)."""
    errors: list[str] = []
    if not isinstance(schema, dict):
        return errors

    if "enum" in schema and instance not in schema["enum"]:
        errors.append(f"{path}: {instance!r} not in enum {schema['enum']}")

    expected_type = schema.get("type")
    if expected_type and not _type_matches(instance, expected_type):
        errors.append(f"{path}: expected type {expected_type}, got {type(instance).__name__}")
        return errors

    if isinstance(instance, dict):
        props: dict[str, Any] = schema.get("properties", {}) or {}
        for name in schema.get("required", []) or []:
            if name not in instance:
                errors.append(f"{path}: missing required property {name!r}")
        for name, value in instance.items():
            if name in props:
                errors.extend(validate(value, props[name], f"{path}.{name}"))
            elif schema.get("additionalProperties") is False:
                errors.append(f"{path}: unexpected property {name!r}")

    if isinstance(instance, list) and "items" in schema:
        for index, item in enumerate(instance):
            errors.extend(validate(item, schema["items"], f"{path}[{index}]"))

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errors.append(f"{path}: length {len(instance)} < minLength {schema['minLength']}")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            errors.append(f"{path}: length {len(instance)} > maxLength {schema['maxLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errors.append(f"{path}: {instance!r} does not match pattern {schema['pattern']!r}")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errors.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errors.append(f"{path}: {instance} > maximum {schema['maximum']}")

    return errors


def check_schema(turn: Turn, case: EvalCase) -> CheckResult:
    schema = case.output_schema
    if schema is None:
        return CheckResult("schema", True, "no schema declared", weight=0.5)
    if turn.error:
        return CheckResult("schema", False, f"turn failed before output: {turn.error}", weight=1.5)
    if not turn.text.strip():
        return CheckResult("schema", False, "empty output where structured JSON was required", weight=1.5)
    try:
        instance = json.loads(turn.text)
    except json.JSONDecodeError as exc:
        return CheckResult("schema", False, f"output is not valid JSON: {exc.msg} at pos {exc.pos}", weight=1.5)
    errors = validate(instance, schema)
    if errors:
        return CheckResult("schema", False, "; ".join(errors[:4]), weight=1.5)
    return CheckResult("schema", True, "output satisfies schema", weight=1.5)


__all__ = ["check_schema", "validate", "SUPPORTED_KEYWORDS"]
