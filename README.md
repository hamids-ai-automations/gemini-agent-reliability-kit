# Gemini Agent Reliability Kit (GAR Kit)

A dependency-light Python kit that measures how reliable a Gemini / Vertex AI agent is at the things that actually
break in production: **tool calling, structured output, retry behaviour, latency and cost**.

It ships a labelled eval suite format, a report-card renderer, and a CLI that exits non-zero when an agent drops
below your quality gate — so it can run in CI before an agent change reaches users.

```
$ gar run --suite suites/smoke.json --provider mock --report reports/smoke.md
```

```
GAR KIT REPORT CARD  suite=smoke  provider=mock  cases=6
---------------------------------------------------------------------
ID                 PASS  SCHEMA  TOOLS  ARGS  RETRY  LATENCY  COST($)
smoke/tool-basic    yes     ok     ok    ok     ok      ok    0.000042
smoke/schema-json   yes     ok     ok    ok     ok      ok    0.000038
...
---------------------------------------------------------------------
pass rate   100.0%  (gate 90.0%)  -> PASS
p50 latency   412 ms   p95 latency   980 ms   total cost $0.00031
```

## Why this exists

Most agent demos are graded by eyeballing chat output. That is not a measurement. GAR Kit turns "the agent looked
fine" into a number that fails a build when it regresses.

Four checks, each independently scored so you can see *which* dimension broke:

| Check | Question it answers |
| --- | --- |
| `schema` | Did the structured output satisfy the declared JSON schema? |
| `tool_call` | Did the agent call the right tool, with arguments that match the contract? |
| `retry` | Did transient failures recover without exceeding the attempt budget or collapsing the backoff curve? |
| `latency` | Did the turn finish inside the case budget? |

## Install

```bash
git clone https://github.com/hamids-ai-automations/gemini-agent-reliability-kit
cd gemini-agent-reliability-kit
python -m venv .venv
# Windows: .venv\Scripts\activate      POSIX: source .venv/bin/activate
pip install -e ".[dev]"
```

The core kit uses only the standard library. `google-genai` is optional and only needed for the live Gemini
provider; the `mock` provider runs the whole pipeline with zero network calls and zero credentials.

## Run against a real model

```bash
set GEMINI_API_KEY=...            # PowerShell: $env:GEMINI_API_KEY = "..."
gar run --suite suites/smoke.json --provider gemini --model gemini-2.0-flash \
        --report reports/gemini-smoke.md --json reports/gemini-smoke.json
```

Never commit a key. `.env` is gitignored, and the kit never logs request headers.

## Suite format

A suite is JSON (or YAML if PyYAML is installed) describing labelled cases:

```json
{
  "name": "smoke",
  "cases": [
    {
      "id": "tool-basic",
      "prompt": "What is the weather in Lahore right now?",
      "tools": [{"name": "get_weather", "parameters": {"type": "object", "properties": {"city": {"type": "string"}}}}],
      "expected_tool": "get_weather",
      "expected_args": {"city": "Lahore"},
      "max_latency_ms": 4000
    }
  ]
}
```

`expected_args` is a **subset** match: extra arguments the model supplies are reported but do not fail the case,
because over-specified arguments are usually harmless while missing ones are not.

## Architecture

```
suite.json --> Runner --> Provider (mock | gemini)
                 |            |
                 |            +--> Turn(text, tool_calls, usage, latency, attempts, backoff)
                 |
                 +--> checks: schema | tool_call | retry | latency
                 |
                 +--> CaseResult --> aggregates --> report card (text / markdown / json) --> CI exit code
```

See [docs/architecture.md](docs/architecture.md) for the design decisions and the failure modes each check targets.

## Cost model

Cost is computed from a small, explicit pricing table in `gar/metrics.py`. Prices are per 1M tokens, configurable,
and **reported as an estimate** — always confirm against your billing console before quoting a number. The kit never
invents usage: if the provider does not return `usageMetadata`, token counts stay at zero and cost is reported as 0.

## Status

- [x] Eval suite format + runner
- [x] Four reliability checks with per-case evidence
- [x] Mock provider (offline, deterministic) and live Gemini REST provider
- [x] Report card: text, markdown, JSON; CI gate via exit code
- [x] pytest suite (no network, no credentials)
- [ ] Vertex AI provider (in progress)
- [ ] HTML report card published to Firebase Hosting

## License

MIT — see [LICENSE](LICENSE).

Built and maintained by [Muhammad Hamid](https://me.developers.google.com/u/hamidautomations).
