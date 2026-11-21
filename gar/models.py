"""Core data model for GAR Kit.

Everything here is a plain dataclass so the kit stays importable with zero third-party
dependencies. Providers return a :class:`Turn`; checks return :class:`CheckResult`;
the runner stitches both into a :class:`CaseResult`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolCall:
    """A single tool/function call requested by the model."""

    name: str
    args: dict[str, Any] = field(default_factory=dict)
    raw_arguments: str | None = None


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def as_dict(self) -> dict[str, int]:
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "total_tokens": self.total_tokens,
        }


@dataclass
class Turn:
    """One agent turn, including the transport evidence the retry check needs."""

    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: Usage = field(default_factory=Usage)
    latency_ms: float = 0.0
    attempts: int = 1
    backoff_ms: list[float] = field(default_factory=list)
    error: str | None = None
    model: str = ""
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


@dataclass
class EvalCase:
    """A labelled expectation about one agent turn."""

    id: str
    prompt: str
    tools: list[dict[str, Any]] = field(default_factory=list)
    expected_tool: str | None = None
    expected_args: dict[str, Any] = field(default_factory=dict)
    forbid_tools: list[str] = field(default_factory=list)
    output_schema: dict[str, Any] | None = None
    max_latency_ms: float | None = None
    max_attempts: int = 3
    require_backoff: bool = True
    tags: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "EvalCase":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        unknown = set(data) - known
        if unknown:
            raise ValueError(f"case {data.get('id')!r}: unknown field(s) {sorted(unknown)}")
        if "id" not in data or "prompt" not in data:
            raise ValueError("every case needs 'id' and 'prompt'")
        return cls(**data)


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""
    weight: float = 1.0

    def as_dict(self) -> dict[str, Any]:
        return {"name": self.name, "passed": self.passed, "detail": self.detail, "weight": self.weight}


@dataclass
class CaseResult:
    case_id: str
    checks: list[CheckResult]
    turn: Turn
    cost_usd: float = 0.0
    tags: list[str] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    @property
    def score(self) -> float:
        total = sum(c.weight for c in self.checks)
        if total == 0:
            return 1.0
        return sum(c.weight for c in self.checks if c.passed) / total

    def check(self, name: str) -> CheckResult | None:
        for c in self.checks:
            if c.name == name:
                return c
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "passed": self.passed,
            "score": round(self.score, 4),
            "cost_usd": self.cost_usd,
            "tags": self.tags,
            "latency_ms": round(self.turn.latency_ms, 1),
            "attempts": self.turn.attempts,
            "checks": [c.as_dict() for c in self.checks],
        }
