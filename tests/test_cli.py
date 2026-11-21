"""CLI behaviour: exit codes, report artefacts."""

import json
from pathlib import Path

from gar.cli import main

SUITE = Path(__file__).resolve().parents[1] / "suites" / "smoke.json"


def test_run_writes_reports_and_exits_zero(tmp_path):
    md = tmp_path / "report.md"
    js = tmp_path / "results.json"
    code = main(
        [
            "run",
            "--suite",
            str(SUITE),
            "--provider",
            "mock",
            "--report",
            str(md),
            "--json",
            str(js),
            "--fail-on-gate",
            "--quiet",
        ]
    )
    assert code == 0
    assert "# GAR Kit report card" in md.read_text(encoding="utf-8")
    payload = json.loads(js.read_text(encoding="utf-8"))
    assert payload["summary"]["gate_passed"] is True
    assert len(payload["results"]) == 6


def test_fail_on_gate_returns_one(tmp_path):
    code = main(
        [
            "run",
            "--suite",
            str(SUITE),
            "--provider",
            "mock",
            "--mock-profile",
            "retry_storm",
            "--fail-on-gate",
            "--quiet",
        ]
    )
    assert code == 1


def test_missing_suite_returns_two():
    assert main(["run", "--suite", "does/not/exist.json", "--quiet"]) == 2
