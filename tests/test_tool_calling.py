"""Tool-calling and argument-contract checks."""

from gar.checks.tool_calling import check_args, check_tool_call
from gar.models import EvalCase, ToolCall, Turn


def case(**kwargs) -> EvalCase:
    defaults = {"id": "t", "prompt": "p"}
    defaults.update(kwargs)
    return EvalCase(**defaults)


def test_correct_single_call_passes():
    c = case(expected_tool="get_weather", expected_args={"city": "Lahore"})
    turn = Turn(tool_calls=[ToolCall("get_weather", {"city": "Lahore", "units": "metric"})])
    assert check_tool_call(turn, c).passed
    assert check_args(turn, c).passed


def test_no_call_fails_when_a_call_was_expected():
    c = case(expected_tool="get_weather")
    result = check_tool_call(Turn(text="It is hot."), c)
    assert not result.passed
    assert "none made" in result.detail


def test_wrong_tool_fails():
    c = case(expected_tool="get_weather")
    result = check_tool_call(Turn(tool_calls=[ToolCall("get_time", {})]), c)
    assert not result.passed
    assert "get_time" in result.detail


def test_multiple_calls_are_ambiguous_for_single_intent_case():
    c = case(expected_tool="get_weather")
    turn = Turn(tool_calls=[ToolCall("get_weather", {}), ToolCall("get_time", {})])
    result = check_tool_call(turn, c)
    assert not result.passed
    assert "ambiguous" in result.detail


def test_forbidden_tool_is_a_hard_failure():
    c = case(expected_tool="read_invoice", forbid_tools=["delete_invoice"])
    turn = Turn(tool_calls=[ToolCall("delete_invoice", {})])
    result = check_tool_call(turn, c)
    assert not result.passed
    assert result.weight >= 3.0


def test_undeclared_tool_fails_without_expectation():
    c = case(tools=[{"name": "read_invoice"}])
    result = check_tool_call(Turn(tool_calls=[ToolCall("wire_money", {})]), c)
    assert not result.passed
    assert "undeclared" in result.detail


def test_missing_argument_fails():
    c = case(expected_tool="search", expected_args={"query": "x", "limit": 3})
    result = check_args(Turn(tool_calls=[ToolCall("search", {"query": "x"})]), c)
    assert not result.passed
    assert "limit" in result.detail


def test_wrong_argument_value_fails():
    c = case(expected_tool="search", expected_args={"limit": 3})
    result = check_args(Turn(tool_calls=[ToolCall("search", {"limit": 10})]), c)
    assert not result.passed
    assert "expected 3" in result.detail


def test_extra_arguments_are_tolerated():
    c = case(expected_tool="search", expected_args={"query": "x"})
    result = check_args(Turn(tool_calls=[ToolCall("search", {"query": "x", "trace": "abc"})]), c)
    assert result.passed


def test_nested_argument_subset():
    c = case(expected_tool="update", expected_args={"payload": {"status": "open"}})
    turn = Turn(tool_calls=[ToolCall("update", {"payload": {"status": "open", "note": "n"}})])
    assert check_args(turn, c).passed
    bad = Turn(tool_calls=[ToolCall("update", {"payload": {"status": "closed"}})])
    assert not check_args(bad, c).passed


def test_transport_error_fails_both_checks():
    c = case(expected_tool="get_weather")
    turn = Turn(error="HTTP 429")
    assert not check_tool_call(turn, c).passed
    assert not check_args(turn, c).passed
