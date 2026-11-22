# Let the failure name itself: report cards for Gemini tool-calling agents

*A working note on the Gemini Agent Reliability Kit — why agent failures are rarely the model being "dumb", and what a
checkable report card buys you that a pass rate does not.*

Most Gemini tool-calling agents do not fail in interesting ways. They fail in the same four boring ways, over and over:

- the model picks the right tool and drops a required argument,
- it emits JSON that is 95% correct and completely unusable,
- it retries the same call four times with the same flat backoff and burns your quota,
- one case quietly takes nine seconds, and nobody notices until it is in production.

None of those are reasoning failures. They are contract violations, and contract violations are testable offline,
without a network call and without an API key. That is the whole premise behind the
[Gemini Agent Reliability Kit](https://github.com/hamids-ai-automations/gemini-agent-reliability-kit) (GAR Kit): take a
handful of labelled cases, run them against a provider, and emit a report card that names the failure — on the case, in
CI, before a user finds it.

## The problem with "it passed"

A pass rate is a lagging signal. Knowing that your agent suite is at 84% tells you nothing you can act on; knowing that
*three cases failed on the `retry` check and every other check was clean* tells you exactly which line of your retry
policy to open. So the unit of output in GAR Kit is not a score, it is a named failure with a one-line evidence string:

```
EVIDENCE
  tool-basic / retry: 5 attempts exceeded budget of 3
  tool-basic / tool_call: expected 'get_weather', got 'delete_everything'
```

That second line is the difference between "the agent is unreliable" and "the agent called a destructive tool where a
read-only one was expected". The first sentence gets a ticket closed as `cannot reproduce`. The second gets fixed
before lunch.

## Four checks, not forty

The kit deliberately ships a small check set, because a check you cannot explain is a check your team will mute:

| check | question it answers | what a failure looks like |
| --- | --- | --- |
| `schema` | Does the structured output satisfy the declared JSON Schema subset? | missing key, wrong type, unparsable JSON |
| `tool_call` | Did the model pick the expected tool and avoid a dangerous one? | `delete_everything` instead of `get_weather` |
| `args` | Did the call carry every required argument with the expected value? | `{}` sent to a tool that needs `city` |
| `retry` | Did the turn stay inside the attempt budget with growing backoff? | 5 attempts, flat 40 ms spacing |
| `latency` | Did the case stay inside `max_latency_ms`? | a p95 regression nobody caught in review |

A case asserts only what it declares. Omit `expected_tool` and the tool checks are skipped rather than guessed at —
which matters, because a harness that invents expectations is worse than no harness.

## What a real card looks like

This is unedited output from the committed smoke suite, run against the deterministic mock provider with its
`retry_storm` failure profile — the "quota burner" case:

```
GAR KIT REPORT CARD  suite=smoke  model=mock-1  cases=6
------------------------------------------------------------------------------
ID                  PASS  SCHEMA  TOOLS  ARGS  RETRY  LATENCY  COST($)
tool-basic          no    ok      ok     ok    FAIL   ok       0.000000
tool-args-contract  no    ok      ok     ok    FAIL   ok       0.000000
schema-json         no    ok      ok     ok    FAIL   ok       0.000000
no-write-actions    no    ok      ok     ok    FAIL   ok       0.000000
------------------------------------------------------------------------------
pass rate 0.0%  (gate 90.0%)  -> FAIL
failures by check: retry=6
```

Every schema check is green. Every tool selection is correct. Every argument contract holds. The *only* thing wrong is
that the retry policy is blowing the budget — and the card says so per case, instead of collapsing five different
reliability guarantees into one number that a reviewer has to reverse-engineer.

Swap the profile to `wrong_tool` and the card changes shape immediately:

```
pass rate 16.7%  (gate 90.0%)  -> FAIL
failures by check: args=3, schema=2, tool_call=3
```

Same suite, same provider, different named pathology. That is the property worth having: a failure mode you can
reproduce on demand, and a card that proves your checks actually catch it.

## Retry telemetry has to come from the response, not from hope

The live provider talks to the Gemini REST endpoint over `urllib` — no SDK, no transitive dependency tree — and reports
what actually happened: `attempts`, `backoff_ms`, token counts out of `usageMetadata`, and measured latency. The one
number that is estimated is cost, from a small price table, and when a response carries no usage metadata the cost is
reported as `0` rather than invented. A harness that quietly fabricates the metric it is supposed to police is not a
harness.

The same rule shapes the exit code. The gate fails the build only when you ask it to:

```bash
gar run --suite suites/smoke.json --provider gemini --model gemini-2.0-flash \
        --report reports/gemini-smoke.md --json reports/gemini-smoke.json --fail-on-gate
```

Without `--fail-on-gate`, a FAIL card exits `0` — useful for exploratory runs, wrong for CI. With it, a missed gate
exits `1` and drops straight into a workflow step with no wrapper script.

## Three things this kit refuses to do

- **No leaderboard of model scores.** A benchmark ages badly within weeks; a suite you own does not.
- **No LLM-as-judge.** Judging with a model makes the harness exactly as flaky as the thing it measures. Every
  assertion here is deterministic string, schema or numeric comparison.
- **No dashboard.** A markdown card diffed inside a pull request is a better review artefact than a chart nobody opens.

## What is honest about the current state

The repository is 32 files, MIT licensed, 53 tests, CI green on Python 3.10 / 3.11 / 3.12, and the default path needs
no network and no credentials. The mock provider is deterministic: the same suite in gives the same card out.

Which is also the limit worth stating plainly: **a green card from the mock provider proves the harness works, not that
a given model behaves well.** The mock exists so the checks themselves can be proven to catch a known failure. Real
model verdicts require the `gemini` provider with your own key, and verdicts change when model versions change — that
is precisely why the suite is yours to version, not a score borrowed from someone else's blog post.

Two items remain open on the roadmap: a Vertex AI provider and an HTML card format. Neither is promised here as done.

## Adopting it in ten minutes

```bash
git clone https://github.com/hamids-ai-automations/gemini-agent-reliability-kit
cd gemini-agent-reliability-kit
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
gar run --suite suites/smoke.json --provider mock --report reports/smoke.md
```

Then replace the smoke suite with five cases you actually care about — the tool your agent must never call, the
argument it always forgets, the latency ceiling your users will notice — and wire the report into the pull request
description. The value is not in this repository's cases. It is in the three minutes it takes to write yours.

---

Built by Muhammad Hamid. Code: [gemini-agent-reliability-kit](https://github.com/hamids-ai-automations/gemini-agent-reliability-kit) ·
Profile: [me.developers.google.com/u/hamidautomations](https://me.developers.google.com/u/hamidautomations)
