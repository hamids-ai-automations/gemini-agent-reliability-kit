"""Tool-calling reliability: right tool, right arguments, no ambiguity, no forbidden calls."""

from __future__ import annotations

from typing import Any

from ..models import CheckResult, EvalCase, Turn


def _subset_mismatch(expected: Any, actual: Any, path: str = "args") -> list[str]:
    """Recursive subset match. Extra keys in ``actual`` are tolerated; wrong values are not."""
    problems: list[str] = []
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: expected object, got {type(actual).__name__}"]
        for key, value in expected.items():
            if key not in actual:
                problems.append(f"{path}.{key}: missing")
            else:
                problems.extend(_subset_mismatch(value, actual[key], f"{path}.{key}"))
        return problems
    if isinstance(expected, list):
        if not isinstance(actual, list):
            return [f"{path}: expected list, got {type(actual).__name__}"]
        if len(actual) < len(expected):
            return [f"{path}: expected at least {len(expected)} item(s), got {len(actual)}"]
        for index, value in enumerate(expected):
            problems.extend(_subset_mismatch(value, actual[index], f"{path}[{index}]"))
        return problems
    if isinstance(expected, bool) or isinstance(actual, bool):
        if expected != actual:
            problems.append(f"{path}: expected {expected!r}, got {actual!r}")
        return problems
    if expected != actual:
        problems.append(f"{path}: expected {expected!r}, got {actual!r}")
    return problems


def check_tool_call(turn: Turn, case: EvalCase) -> CheckResult:
    if turn.error:
        return CheckResult("tool_call", False, f"turn failed: {turn.error}", weight=2.0)

    called = [c.name for c in turn.tool_calls]
    forbidden = [name for name in called if name in set(case.forbid_tools)]
    if forbidden:
        return CheckResult("tool_call", False, f"called forbidden tool(s): {forbidden}", weight=3.0)

    if case.expected_tool is None:
        allowed = {t.get("name") for t in case.tools}
        unknown = [name for name in called if allowed and name not in allowed]
        if unknown:
            return CheckResult("tool_call", False, f"called undeclared tool(s): {unknown}", weight=2.0)
        return CheckResult("tool_call", True, "no tool expectation declared", weight=0.5)

    if not called:
        return CheckResult("tool_call", False, f"expected a call to {case.expected_tool!r}, none made", weight=2.5)
    if len(called) > 1:
        return CheckResult(
            "tool_call", False, f"ambiguous: {len(called)} calls {called} for a single-intent case", weight=2.0
        )
    if called[0] != case.expected_tool:
        return CheckResult("tool_call", False, f"expected {case.expected_tool!r}, got {called[0]!r}", weight=2.5)
    return CheckResult("tool_call", True, f"called {case.expected_tool!r}", weight=2.0)


def check_args(turn: Turn, case: EvalCase) -> CheckResult:
    if turn.error:
        return CheckResult("args", False, f"turn failed: {turn.error}", weight=1.5)
    if not case.expected_args:
        return CheckResult("args", True, "no argument contract declared", weight=0.5)
    matching = [c for c in turn.tool_calls if c.name == (case.expected_tool or c.name)]
    if not matching:
        return CheckResult("args", False, "no call to inspect arguments on", weight=1.5)
    problems = _subset_mismatch(case.expected_args, matching[0].args)
    if problems:
        return CheckResult("args", False, "; ".join(problems[:4]), weight=2.0)
    return CheckResult("args", True, "arguments match contract", weight=1.5)


__all__ = ["check_tool_call", "check_args", "_subset_mismatch"]
