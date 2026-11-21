"""Live Gemini provider using the public REST endpoint.

Kept on ``urllib`` so the kit does not force an SDK on users. The retry loop is deliberately
explicit: it records every attempt and the backoff it used, because that evidence is what the
``retry`` check grades. Nothing here logs the API key.
"""

from __future__ import annotations

import json
import os
import random
import time
import urllib.error
import urllib.request
from typing import Any

from ..models import EvalCase, ToolCall, Turn, Usage

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUS = {408, 429, 500, 502, 503, 504}


class GeminiProvider:
    """Minimal, dependency-free Gemini client with first-class retry telemetry."""

    name = "gemini"

    def __init__(
        self,
        model: str = "gemini-2.0-flash",
        api_key: str | None = None,
        max_attempts: int = 3,
        base_delay_s: float = 0.6,
        timeout_s: float = 60.0,
        temperature: float = 0.0,
        jitter: bool = True,
        endpoint: str = ENDPOINT,
    ) -> None:
        self.model = model
        self.api_key = api_key or os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
        self.max_attempts = max(1, max_attempts)
        self.base_delay_s = base_delay_s
        self.timeout_s = timeout_s
        self.temperature = temperature
        self.jitter = jitter
        self.endpoint = endpoint

    # -- request building ----------------------------------------------------------------
    def _payload(self, case: EvalCase) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": case.prompt}]}],
            "generationConfig": {"temperature": self.temperature},
        }
        if case.tools:
            payload["tools"] = [
                {
                    "functionDeclarations": [
                        {k: v for k, v in tool.items() if k in {"name", "description", "parameters"}}
                        for tool in case.tools
                    ]
                }
            ]
        if case.output_schema:
            payload["generationConfig"]["responseMimeType"] = "application/json"
            payload["generationConfig"]["responseSchema"] = case.output_schema
        return payload

    def _post(self, case: EvalCase) -> dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set; export it or use --provider mock")
        url = self.endpoint.format(model=self.model)
        body = json.dumps(self._payload(case)).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": self.api_key},
        )
        with urllib.request.urlopen(request, timeout=self.timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))

    # -- response parsing ----------------------------------------------------------------
    @staticmethod
    def _parse(data: dict[str, Any]) -> tuple[str, list[ToolCall], Usage]:
        text_parts: list[str] = []
        calls: list[ToolCall] = []
        candidates = data.get("candidates") or []
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []) or []:
                if "text" in part:
                    text_parts.append(part["text"])
                elif "functionCall" in part:
                    fc = part["functionCall"]
                    calls.append(ToolCall(name=fc.get("name", ""), args=dict(fc.get("args") or {})))
        meta = data.get("usageMetadata", {}) or {}
        usage = Usage(
            input_tokens=int(meta.get("promptTokenCount", 0) or 0),
            output_tokens=int(meta.get("candidatesTokenCount", 0) or 0),
        )
        return "".join(text_parts), calls, usage

    # -- provider protocol ---------------------------------------------------------------
    def complete(self, case: EvalCase) -> Turn:
        backoff: list[float] = []
        last_error: str | None = None
        attempts = 0
        started = time.perf_counter()

        for attempt in range(1, self.max_attempts + 1):
            attempts = attempt
            try:
                data = self._post(case)
                text, calls, usage = self._parse(data)
                return Turn(
                    text=text,
                    tool_calls=calls,
                    usage=usage,
                    latency_ms=round((time.perf_counter() - started) * 1000, 1),
                    attempts=attempts,
                    backoff_ms=backoff,
                    model=self.model,
                    raw=data,
                )
            except urllib.error.HTTPError as exc:
                last_error = f"HTTP {exc.code}"
                if exc.code not in RETRY_STATUS or attempt == self.max_attempts:
                    break
            except (urllib.error.URLError, TimeoutError, RuntimeError) as exc:
                last_error = str(exc)
                if attempt == self.max_attempts:
                    break

            delay = self.base_delay_s * (2 ** (attempt - 1))
            if self.jitter:
                delay *= 0.8 + random.random() * 0.4  # +/-20%
            backoff.append(round(delay * 1000, 1))
            time.sleep(delay)

        return Turn(
            error=last_error or "unknown transport failure",
            usage=Usage(),
            latency_ms=round((time.perf_counter() - started) * 1000, 1),
            attempts=attempts,
            backoff_ms=backoff,
            model=self.model,
        )


__all__ = ["GeminiProvider", "RETRY_STATUS"]
