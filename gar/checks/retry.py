"""Retry behaviour: did recovery stay inside the attempt budget and did the backoff actually grow?

A provider that retries forever, or retries five times with a flat 40 ms delay, is worse than one
that fails fast: it burns quota and hides an outage behind latency. This check grades the transport
evidence on the turn rather than the final answer.
"""

from __future__ import annotations

from ..models import CheckResult, EvalCase, Turn

GROWTH_FACTOR = 1.5


def check_retry(turn: Turn, case: EvalCase) -> CheckResult:
    budget = max(1, case.max_attempts)

    if turn.attempts > budget:
        return CheckResult(
            "retry", False, f"{turn.attempts} attempts exceeded budget of {budget}", weight=2.0
        )

    if turn.attempts <= 1:
        return CheckResult("retry", True, "recovered first attempt", weight=1.0)

    expected_backoffs = turn.attempts - 1
    if len(turn.backoff_ms) < expected_backoffs:
        return CheckResult(
            "retry",
            False,
            f"{expected_backoffs} retry(ies) but only {len(turn.backoff_ms)} backoff step(s) recorded",
            weight=1.5,
        )

    steps = turn.backoff_ms[:expected_backoffs]
    if any(step <= 0 for step in steps):
        return CheckResult("retry", False, f"non-positive backoff in {steps}", weight=1.5)

    if case.require_backoff:
        for previous, current in zip(steps, steps[1:]):
            if current < previous * GROWTH_FACTOR:
                return CheckResult(
                    "retry",
                    False,
                    f"backoff did not grow (>= {GROWTH_FACTOR}x): {steps}",
                    weight=1.5,
                )

    if turn.error:
        return CheckResult("retry", False, f"retried {turn.attempts}x and still failed: {turn.error}", weight=2.0)

    return CheckResult("retry", True, f"{turn.attempts} attempts, backoff {steps} ms", weight=1.0)


__all__ = ["check_retry", "GROWTH_FACTOR"]
