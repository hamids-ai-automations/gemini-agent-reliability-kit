"""Checks. Each one answers a single question and never inspects another check's verdict."""

from __future__ import annotations

from ..models import CheckResult, EvalCase, Turn
from .latency import check_latency
from .retry import check_retry
from .schema import check_schema
from .tool_calling import check_args, check_tool_call


def run_checks(case: EvalCase, turn: Turn) -> list[CheckResult]:
    """Run the full check set for one case. Order is stable for report readability."""
    return [
        check_schema(turn, case),
        check_tool_call(turn, case),
        check_args(turn, case),
        check_retry(turn, case),
        check_latency(turn, case),
    ]


__all__ = [
    "run_checks",
    "check_schema",
    "check_tool_call",
    "check_args",
    "check_retry",
    "check_latency",
]
