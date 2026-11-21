"""Provider interface plus the two shipped implementations."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from ..models import EvalCase, Turn


@runtime_checkable
class Provider(Protocol):
    """Anything that can run one case and return a :class:`Turn`."""

    name: str

    def complete(self, case: EvalCase) -> Turn:  # pragma: no cover - protocol
        ...


def build_provider(kind: str, **kwargs: Any) -> Provider:
    """Factory used by the CLI. Keeps provider selection out of the runner."""
    kind = (kind or "mock").lower()
    if kind == "mock":
        from .mock import MockProvider

        return MockProvider(**kwargs)
    if kind == "gemini":
        from .gemini import GeminiProvider

        return GeminiProvider(**kwargs)
    raise ValueError(f"unknown provider {kind!r}; expected 'mock' or 'gemini'")


__all__ = ["Provider", "build_provider"]
