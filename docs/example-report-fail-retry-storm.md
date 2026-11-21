# GAR Kit report card — `smoke`

| field | value |
| --- | --- |
| model | `mock-1` |
| cases | 6 |
| pass rate | 0.0% (gate 90.0%) |
| verdict | **FAIL** |
| latency p50 / p95 | 120 ms / 120 ms |
| cost (estimate) | $0.000000 |

| case | pass | schema | tool_call | args | retry | latency | cost ($) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tool-basic | **no** | ok | ok | ok | FAIL | ok | 0.000000 |
| tool-args-contract | **no** | ok | ok | ok | FAIL | ok | 0.000000 |
| schema-json | **no** | ok | ok | ok | FAIL | ok | 0.000000 |
| schema-nested | **no** | ok | ok | ok | FAIL | ok | 0.000000 |
| no-write-actions | **no** | ok | ok | ok | FAIL | ok | 0.000000 |
| latency-budget | **no** | ok | ok | ok | FAIL | ok | 0.000000 |

## Evidence

- `tool-basic` / **retry**: 5 attempts exceeded budget of 3
- `tool-args-contract` / **retry**: 5 attempts exceeded budget of 3
- `schema-json` / **retry**: 5 attempts exceeded budget of 3
- `schema-nested` / **retry**: 5 attempts exceeded budget of 3
- `no-write-actions` / **retry**: 5 attempts exceeded budget of 3
- `latency-budget` / **retry**: 5 attempts exceeded budget of 3
