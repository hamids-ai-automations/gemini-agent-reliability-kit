"""Cost and latency aggregation.

Prices are per 1M tokens and are an editable estimate, not a contract. If a provider returns no
usage metadata the cost is 0 — the kit never extrapolates token counts.
"""

from __future__ import annotations

import math
from statistics import median
from typing import Iterable, Sequence

from .models import CaseResult, Usage

# USD per 1M tokens: (input, output). Update deliberately; verify against the billing console.
DEFAULT_PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.0-flash-lite": (0.075, 0.30),
    "gemini-2.5-flash": (0.30, 2.50),
    "mock-1": (0.0, 0.0),
}


def cost_usd(model: str, usage: Usage, pricing: dict[str, tuple[float, float]] | None = None) -> float:
    table = pricing or DEFAULT_PRICING
    if model not in table:
        return 0.0
    price_in, price_out = table[model]
    return (usage.input_tokens / 1_000_000) * price_in + (usage.output_tokens / 1_000_000) * price_out


def percentile(values: Sequence[float], pct: float) -> float:
    """Nearest-rank percentile (ceil(pct/100 * n)); returns 0.0 for an empty sample."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = math.ceil((pct / 100) * len(ordered)) - 1
    return ordered[max(0, min(len(ordered) - 1, rank))]


def summarize(results: Iterable[CaseResult], gate: float = 0.9) -> dict:
    results = list(results)
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    latencies = [r.turn.latency_ms for r in results]
    costs = [r.cost_usd for r in results]
    failures: dict[str, int] = {}
    for result in results:
        for check in result.checks:
            if not check.passed:
                failures[check.name] = failures.get(check.name, 0) + 1
    pass_rate = (passed / total) if total else 0.0
    return {
        "cases": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 4),
        "gate": gate,
        "gate_passed": pass_rate >= gate,
        "latency_ms": {
            "median": round(median(latencies), 1) if latencies else 0.0,
            "p50": round(percentile(latencies, 50), 1),
            "p95": round(percentile(latencies, 95), 1),
            "max": round(max(latencies), 1) if latencies else 0.0,
        },
        "cost_usd": round(sum(costs), 8),
        "checks_failed": failures,
    }


__all__ = ["DEFAULT_PRICING", "cost_usd", "percentile", "summarize"]
