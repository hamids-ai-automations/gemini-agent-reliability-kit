# Architecture and design decisions

## The problem

An agent can produce a convincing answer while being unfit for production. The failure hides in the gaps between
"looks right" and "behaves correctly":

| Hidden failure | What a human demo sees | What production sees |
| --- | --- | --- |
| Calls the right tool with the wrong argument | A plausible answer | Wrong record updated |
| Retries five times on a flat 40 ms delay | Slower answer | Quota burn, outage masked |
| Emits JSON that almost matches the schema | Text that reads fine | Parser exception downstream |
| Calls two tools when one intent was expressed | Verbose answer | Duplicate side effects |

GAR Kit exists to make each of those a distinct, scored failure with evidence, so a change to a prompt, model
version or tool schema cannot regress silently.

## Component map

```
suites/*.json
    |
    v
gar.suite.load_suite  -->  EvalCase[]  -->  gar.suite.run_suite
                                                |
                            +-------------------+-------------------+
                            |                                       |
                    gar.providers.*                        gar.checks.*
              (mock | gemini REST + retry)        schema | tool_call | args | retry | latency
                            |                                       |
                            +---------------> Turn ------------------+
                                                |
                                          CaseResult
                                                |
                                   gar.metrics.summarize
                                                |
                                   gar.report.render_*  -->  text / markdown / json
                                                |
                                   gar.cli exit code 0/1  -->  CI gate
```

## Decisions

**Standard library only in the core.** Agent tooling is usually installed into environments already close to their
dependency limits. `urllib` plus dataclasses keeps the kit importable anywhere; `google-genai` is an extra, never a
requirement, and it is not even used by the shipped provider.

**Retry telemetry is a first-class output, not a log line.** Most kits grade the final answer. Reliability problems
usually live in the transport: attempt count and backoff shape. `Turn.attempts` and `Turn.backoff_ms` are part of the
contract, so the `retry` check can grade behaviour that never appears in the response text.

**Argument matching is a subset match, on purpose.** If the model supplies extra arguments they are recorded, not
fatal; missing or wrong values are fatal. Over-specification is usually harmless, under-specification is not.

**Ambiguity is a failure.** A single-intent case that returns two tool calls fails even if one of them is correct,
because duplicate calls mean duplicate side effects in a real system.

**Neutral checks carry lower weight.** When a case declares no schema, no argument contract or no latency budget, the
check returns a pass with reduced weight instead of inflating the score. Scoring is weighted so `tool_call` failures
outweigh cosmetic ones.

**The mock provider is a test double, never evidence.** Its `good` profile synthesises the expected behaviour from the
case itself, which proves the pipeline end-to-end and proves nothing about any model. The five failure profiles exist
so each check can be shown to catch the failure it claims to catch.

**Cost is an estimate with a visible table.** `gar.metrics.DEFAULT_PRICING` is small and editable. If the provider
returns no `usageMetadata`, tokens stay at zero and cost is reported as zero rather than inferred.

## Extension points

- **New provider**: implement `name` and `complete(case) -> Turn`; register it in `gar.providers.build_provider`.
  Vertex AI is the next one, reusing the same retry loop with the regional endpoint.
- **New check**: add a module under `gar/checks/`, return a `CheckResult` with a deliberate weight, and append it in
  `run_checks`. Reports pick it up automatically through `CaseResult`.
- **New suite**: drop a JSON/YAML file in `suites/`. Case ids must be unique; unknown fields are rejected loudly so a
  typo like `expect_tool` cannot silently disable an assertion.

## Known limits

- The schema validator implements a JSON Schema subset; unsupported keywords are ignored rather than guessed.
- Token accounting trusts the provider payload; there is no local tokenizer.
- One turn per case: multi-turn agent loops are not yet modelled, which is why the roadmap lists them as open.
