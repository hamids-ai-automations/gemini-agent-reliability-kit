"""Retry-budget and latency checks."""

from gar.checks.latency import check_latency
from gar.checks.retry import check_retry
from gar.models import EvalCase, Turn


def case(**kwargs) -> EvalCase:
    defaults = {"id": "t", "prompt": "p", "max_attempts": 3}
    defaults.update(kwargs)
    return EvalCase(**defaults)


def test_first_attempt_success_passes():
    assert check_retry(Turn(attempts=1, backoff_ms=[]), case()).passed


def test_exponential_backoff_passes():
    turn = Turn(attempts=3, backoff_ms=[600.0, 1200.0])
    assert check_retry(turn, case()).passed


def test_attempt_budget_blowout_fails():
    turn = Turn(attempts=5, backoff_ms=[100.0, 200.0, 400.0, 800.0])
    result = check_retry(turn, case())
    assert not result.passed
    assert "budget of 3" in result.detail


def test_flat_backoff_fails():
    turn = Turn(attempts=3, backoff_ms=[40.0, 40.0])
    result = check_retry(turn, case())
    assert not result.passed
    assert "did not grow" in result.detail


def test_missing_backoff_evidence_fails():
    turn = Turn(attempts=3, backoff_ms=[600.0])
    result = check_retry(turn, case())
    assert not result.passed
    assert "backoff step" in result.detail


def test_backoff_not_required_when_case_allows():
    turn = Turn(attempts=2, backoff_ms=[10.0])
    assert check_retry(turn, case(require_backoff=False)).passed


def test_retried_then_failed_still_fails():
    turn = Turn(attempts=3, backoff_ms=[600.0, 1200.0], error="503 UNAVAILABLE")
    result = check_retry(turn, case())
    assert not result.passed
    assert "still failed" in result.detail


def test_latency_inside_budget_passes():
    assert check_latency(Turn(latency_ms=900), case(max_latency_ms=1000)).passed


def test_latency_over_budget_fails():
    result = check_latency(Turn(latency_ms=1500), case(max_latency_ms=1000))
    assert not result.passed
    assert "budget" in result.detail


def test_latency_neutral_without_budget():
    result = check_latency(Turn(latency_ms=99_999), case())
    assert result.passed
    assert result.weight < 1.0
