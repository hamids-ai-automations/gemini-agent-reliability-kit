"""Suite loading and execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .checks import run_checks
from .metrics import DEFAULT_PRICING, cost_usd, summarize
from .models import CaseResult, EvalCase
from .providers import Provider


@dataclass
class Suite:
    name: str
    cases: list[EvalCase]
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class SuiteResult:
    suite: str
    results: list[CaseResult]
    gate: float = 0.9
    pricing: dict[str, tuple[float, float]] = field(default_factory=lambda: dict(DEFAULT_PRICING))

    @property
    def summary(self) -> dict:
        return summarize(self.results, self.gate)


def _load_raw(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in {".yaml", ".yml"}:
        try:
            import yaml  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("PyYAML is required for YAML suites: pip install PyYAML") from exc
        return yaml.safe_load(text)
    return json.loads(text)


def load_suite(path: str | Path) -> Suite:
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"suite not found: {path}")
    data = _load_raw(path)
    if not isinstance(data, dict) or "cases" not in data:
        raise ValueError("a suite must be an object with a 'cases' list")
    cases = [EvalCase.from_dict(case) for case in data["cases"]]
    if not cases:
        raise ValueError("suite has no cases")
    ids = [c.id for c in cases]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        raise ValueError(f"duplicate case ids: {sorted(duplicates)}")
    return Suite(name=data.get("name", path.stem), cases=cases, meta=data.get("meta", {}) or {})


def run_suite(
    suite: Suite,
    provider: Provider,
    gate: float = 0.9,
    pricing: dict[str, tuple[float, float]] | None = None,
    progress: bool = False,
) -> SuiteResult:
    table = pricing or DEFAULT_PRICING
    results: list[CaseResult] = []
    for case in suite.cases:
        turn = provider.complete(case)
        checks = run_checks(case, turn)
        results.append(
            CaseResult(
                case_id=case.id,
                checks=checks,
                turn=turn,
                cost_usd=cost_usd(turn.model or getattr(provider, "name", ""), turn.usage, table),
                tags=list(case.tags),
            )
        )
        if progress:
            status = "PASS" if results[-1].passed else "FAIL"
            print(f"  [{status}] {case.id}")
    return SuiteResult(suite=suite.name, results=results, gate=gate, pricing=table)


__all__ = ["Suite", "SuiteResult", "load_suite", "run_suite"]
