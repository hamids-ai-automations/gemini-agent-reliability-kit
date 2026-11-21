"""Latency budget: did the turn fit inside the per-case ceiling?"""

from __future__ import annotations

from ..models import CheckResult, EvalCase, Turn


def check_latency(turn: Turn, case: EvalCase) -> CheckResult:
    if case.max_latency_ms is None:
        return CheckResult("latency", True, "no budget declared", weight=0.5)
    if turn.latency_ms <= case.max_latency_ms:
        return CheckResult(
            "latency", True, f"{turn.latency_ms:.0f} ms <= {case.max_latency_ms:.0f} ms", weight=1.0
        )
    return CheckResult(
        "latency",
        False,
        f"{turn.latency_ms:.0f} ms > budget {case.max_latency_ms:.0f} ms",
        weight=1.0,
    )


__all__ = ["check_latency"]
