"""Deterministic offline provider.

Purpose: run the *pipeline* (suite -> checks -> report) with no network, no credentials and no
flakiness. It is a test double, not a model. It never counts as evidence of model behaviour —
each failure profile exists so the checks themselves can be proven to catch that failure.
"""

from __future__ import annotations

import hashlib
from typing import Any

from ..models import EvalCase, ToolCall, Turn, Usage

PROFILES = ("good", "wrong_tool", "bad_args", "invalid_json", "retry_storm", "slow")


def _synthesize(schema: dict[str, Any] | None) -> Any:
    """Build the smallest instance that satisfies the subset of JSON Schema the checks support."""
    if not schema:
        return {}
    kind = schema.get("type", "object")
    if "enum" in schema and schema["enum"]:
        return schema["enum"][0]
    if kind == "object":
        props = schema.get("properties", {})
        out: dict[str, Any] = {}
        for name in schema.get("required", list(props)):
            out[name] = _synthesize(props.get(name, {}))
        return out
    if kind == "array":
        return [_synthesize(schema.get("items", {}))]
    if kind == "string":
        return schema.get("default", "ok")
    if kind == "integer":
        return int(schema.get("default", schema.get("minimum", 0)))
    if kind == "number":
        return float(schema.get("default", schema.get("minimum", 0.0)))
    if kind == "boolean":
        return bool(schema.get("default", True))
    if kind == "null":
        return None
    return {}


def _fill_expected(turn: Turn, case: EvalCase, expected_tool: str | None, expected_args: dict[str, Any]) -> Turn:
    """Give a turn the output the case asked for: schema-conformant JSON and/or the expected call."""
    if case.output_schema:
        import json

        turn.text = json.dumps(_synthesize(case.output_schema))
    if expected_tool:
        turn.tool_calls = [ToolCall(name=expected_tool, args=expected_args)]
    return turn


class MockProvider:
    """Scripted provider.

    ``responses`` maps a case id to a fully-formed :class:`Turn` and always wins.
    Otherwise ``profile`` decides what a case yields, so every failure mode has a fixture.
    """

    name = "mock"

    def __init__(
        self,
        responses: dict[str, Turn] | None = None,
        profile: str = "good",
        latency_ms: float = 120.0,
        model: str = "mock-1",
    ) -> None:
        if profile not in PROFILES:
            raise ValueError(f"unknown mock profile {profile!r}; expected one of {PROFILES}")
        self.responses = responses or {}
        self.profile = profile
        self.latency_ms = latency_ms
        self.model = model

    # -- helpers -------------------------------------------------------------------------
    def _usage_for(self, case: EvalCase) -> Usage:
        # Stable pseudo-usage so cost maths is exercised without pretending to be real.
        digest = hashlib.sha256(case.id.encode("utf-8")).hexdigest()
        return Usage(input_tokens=int(digest[:4], 16) % 400 + 120, output_tokens=int(digest[4:8], 16) % 120 + 20)

    def _base(self, case: EvalCase) -> Turn:
        return Turn(
            text="",
            usage=self._usage_for(case),
            latency_ms=self.latency_ms,
            attempts=1,
            backoff_ms=[],
            model=self.model,
        )

    # -- provider protocol ---------------------------------------------------------------
    def complete(self, case: EvalCase) -> Turn:
        if case.id in self.responses:
            return self.responses[case.id]

        turn = self._base(case)
        expected_tool = case.expected_tool or (case.tools[0]["name"] if case.tools else None)
        expected_args = dict(case.expected_args)

        if self.profile == "good":
            return _fill_expected(turn, case, expected_tool, expected_args)

        if self.profile == "wrong_tool":
            turn.tool_calls = [ToolCall(name="delete_everything", args=expected_args)]
            return turn

        if self.profile == "bad_args":
            turn.tool_calls = [ToolCall(name=expected_tool or "noop", args={})]
            return turn

        if self.profile == "invalid_json":
            turn.text = '{"confidence": "very high", '  # truncated + wrong type: two schema errors
            return turn

        if self.profile == "retry_storm":
            # The answer eventually arrives; it is the transport behaviour that must fail the case.
            turn.attempts = 5
            turn.backoff_ms = [40.0, 40.0, 40.0, 40.0]  # budget blown, backoff never grew
            return _fill_expected(turn, case, expected_tool, expected_args)

        if self.profile == "slow":
            turn.latency_ms = 9_500.0
            if expected_tool:
                turn.tool_calls = [ToolCall(name=expected_tool, args=expected_args)]
            return turn

        raise AssertionError("unreachable profile")  # pragma: no cover


__all__ = ["MockProvider", "PROFILES"]
