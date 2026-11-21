"""Suite loading, execution aggregation, metrics and the mock provider's failure profiles."""

import json
from pathlib import Path

import pytest

from gar.metrics import cost_usd, percentile, summarize
from gar.models import ToolCall, Turn, Usage
from gar.providers.mock import MockProvider
from gar.suite import load_suite, run_suite

SUITE = Path(__file__).resolve().parents[1] / "suites" / "smoke.json"


def test_load_smoke_suite():
    suite = load_suite(SUITE)
    assert suite.name == "smoke"
    assert len(suite.cases) == 6
    assert {c.id for c in suite.cases} >= {"tool-basic", "schema-json", "no-write-actions"}


def test_duplicate_case_ids_rejected(tmp_path):
    payload = {"name": "dup", "cases": [{"id": "a", "prompt": "p"}, {"id": "a", "prompt": "q"}]}
    path = tmp_path / "dup.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate case ids"):
        load_suite(path)


def test_unknown_case_field_rejected(tmp_path):
    payload = {"name": "x", "cases": [{"id": "a", "prompt": "p", "expect_tool": "typo"}]}
    path = tmp_path / "x.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(ValueError, match="unknown field"):
        load_suite(path)


def test_mock_good_profile_satisfies_the_smoke_suite():
    suite = load_suite(SUITE)
    result = run_suite(suite, MockProvider(profile="good"))
    assert result.summary["pass_rate"] == 1.0
    assert result.summary["gate_passed"] is True


@pytest.mark.parametrize(
    "profile, expected_check",
    [
        ("wrong_tool", "tool_call"),
        ("bad_args", "args"),
        ("invalid_json", "schema"),
        ("retry_storm", "retry"),
        ("slow", "latency"),
    ],
)
def test_each_failure_profile_is_caught_by_the_matching_check(profile, expected_check):
    suite = load_suite(SUITE)
    result = run_suite(suite, MockProvider(profile=profile))
    assert result.summary["gate_passed"] is False
    assert expected_check in result.summary["checks_failed"]


def test_summary_counts_and_percentiles():
    suite = load_suite(SUITE)
    result = run_suite(suite, MockProvider(profile="good"))
    summary = result.summary
    assert summary["cases"] == 6
    assert summary["failed"] == 0
    assert summary["latency_ms"]["p95"] >= summary["latency_ms"]["p50"]


def test_percentile_and_cost_maths():
    assert percentile([], 95) == 0.0
    assert percentile([10, 20, 30, 40], 50) == 20
    assert percentile([10, 20, 30, 40], 95) == 40
    assert cost_usd("gemini-2.0-flash", Usage(1_000_000, 1_000_000)) == pytest.approx(0.50)
    assert cost_usd("unknown-model", Usage(1000, 1000)) == 0.0


def test_summarize_reports_failed_checks_by_name():
    suite = load_suite(SUITE)
    result = run_suite(suite, MockProvider(profile="slow"))
    summary = summarize(result.results, gate=0.9)
    assert summary["checks_failed"].get("latency", 0) >= 1


def test_scripted_response_overrides_profile():
    suite = load_suite(SUITE)
    case_id = suite.cases[0].id
    scripted = Turn(tool_calls=[ToolCall("get_weather", {"city": "Karachi"})], latency_ms=50.0)
    result = run_suite(suite, MockProvider(responses={case_id: scripted}, profile="good"))
    first = result.results[0]
    assert first.case_id == case_id
    assert first.check("args").passed is False
