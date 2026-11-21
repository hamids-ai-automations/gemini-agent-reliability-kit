"""Report card rendering: plain text for humans, markdown for PRs, JSON for machines."""

from __future__ import annotations

import json
from typing import Any

from .suite import SuiteResult

CHECK_ORDER = ("schema", "tool_call", "args", "retry", "latency")
HEADERS = ("ID", "PASS", "SCHEMA", "TOOLS", "ARGS", "RETRY", "LATENCY", "COST($)")


def _cell(value: bool | None) -> str:
    if value is None:
        return "-"
    return "ok" if value else "FAIL"


def _row(result) -> list[str]:
    return [
        result.case_id,
        "yes" if result.passed else "no",
        _cell(result.check("schema").passed if result.check("schema") else None),
        _cell(result.check("tool_call").passed if result.check("tool_call") else None),
        _cell(result.check("args").passed if result.check("args") else None),
        _cell(result.check("retry").passed if result.check("retry") else None),
        _cell(result.check("latency").passed if result.check("latency") else None),
        f"{result.cost_usd:.6f}",
    ]


def _table_rows(suite_result: SuiteResult) -> list[list[str]]:
    return [_row(result) for result in suite_result.results]


def render_text(suite_result: SuiteResult) -> str:
    summary = suite_result.summary
    model = suite_result.results[0].turn.model if suite_result.results else "?"
    rows = _table_rows(suite_result)
    widths = [max(len(HEADERS[i]), *(len(row[i]) for row in rows)) if rows else len(HEADERS[i]) for i in range(len(HEADERS))]
    widths[0] = max(widths[0], 18)

    def fmt(cells: list[str]) -> str:
        return "  ".join(cell.ljust(width) for cell, width in zip(cells, widths)).rstrip()

    lines = [
        f"GAR KIT REPORT CARD  suite={suite_result.suite}  model={model}  cases={summary['cases']}",
        "-" * 78,
        fmt(list(HEADERS)),
    ]
    for row in rows:
        lines.append(fmt(row))
    lines.append("-" * 78)
    verdict = "PASS" if summary["gate_passed"] else "FAIL"
    lines.append(
        f"pass rate {summary['pass_rate'] * 100:.1f}%  (gate {summary['gate'] * 100:.1f}%)  -> {verdict}"
    )
    lat = summary["latency_ms"]
    lines.append(
        f"p50 {lat['p50']:.0f} ms   p95 {lat['p95']:.0f} ms   max {lat['max']:.0f} ms   "
        f"total cost ${summary['cost_usd']:.6f} (estimate)"
    )
    if summary["checks_failed"]:
        breakdown = ", ".join(f"{name}={count}" for name, count in sorted(summary["checks_failed"].items()))
        lines.append(f"failures by check: {breakdown}")
    failing = [r for r in suite_result.results if not r.passed]
    if failing:
        lines.append("")
        lines.append("EVIDENCE")
        for result in failing:
            for check in result.checks:
                if not check.passed:
                    lines.append(f"  {result.case_id} / {check.name}: {check.detail}")
    return "\n".join(lines)


def render_markdown(suite_result: SuiteResult) -> str:
    summary = suite_result.summary
    model = suite_result.results[0].turn.model if suite_result.results else "?"
    verdict = "PASS" if summary["gate_passed"] else "FAIL"
    lines = [
        f"# GAR Kit report card — `{suite_result.suite}`",
        "",
        f"| field | value |",
        f"| --- | --- |",
        f"| model | `{model}` |",
        f"| cases | {summary['cases']} |",
        f"| pass rate | {summary['pass_rate'] * 100:.1f}% (gate {summary['gate'] * 100:.1f}%) |",
        f"| verdict | **{verdict}** |",
        f"| latency p50 / p95 | {summary['latency_ms']['p50']:.0f} ms / {summary['latency_ms']['p95']:.0f} ms |",
        f"| cost (estimate) | ${summary['cost_usd']:.6f} |",
        "",
        "| case | pass | " + " | ".join(CHECK_ORDER) + " | cost ($) |",
        "| --- | --- | " + " | ".join("---" for _ in CHECK_ORDER) + " | --- |",
    ]
    for result in suite_result.results:
        cells = [
            result.case_id,
            "yes" if result.passed else "**no**",
        ]
        for name in CHECK_ORDER:
            check = result.check(name)
            cells.append(_cell(check.passed if check else None))
        cells.append(f"{result.cost_usd:.6f}")
        lines.append("| " + " | ".join(cells) + " |")
    failing = [r for r in suite_result.results if not r.passed]
    if failing:
        lines += ["", "## Evidence", ""]
        for result in failing:
            for check in result.checks:
                if not check.passed:
                    lines.append(f"- `{result.case_id}` / **{check.name}**: {check.detail}")
    return "\n".join(lines) + "\n"


def render_json(suite_result: SuiteResult) -> dict[str, Any]:
    return {
        "suite": suite_result.suite,
        "summary": suite_result.summary,
        "results": [r.as_dict() for r in suite_result.results],
    }


def dumps_json(suite_result: SuiteResult, indent: int = 2) -> str:
    return json.dumps(render_json(suite_result), indent=indent)


__all__ = ["render_text", "render_markdown", "render_json", "dumps_json", "CHECK_ORDER"]
