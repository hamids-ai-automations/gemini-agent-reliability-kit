# GAR Kit report card — `smoke`

| field | value |
| --- | --- |
| model | `mock-1` |
| cases | 6 |
| pass rate | 16.7% (gate 90.0%) |
| verdict | **FAIL** |
| latency p50 / p95 | 120 ms / 120 ms |
| cost (estimate) | $0.000000 |

| case | pass | schema | tool_call | args | retry | latency | cost ($) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| tool-basic | **no** | ok | FAIL | FAIL | ok | ok | 0.000000 |
| tool-args-contract | **no** | ok | FAIL | FAIL | ok | ok | 0.000000 |
| schema-json | **no** | FAIL | ok | ok | ok | ok | 0.000000 |
| schema-nested | **no** | FAIL | ok | ok | ok | ok | 0.000000 |
| no-write-actions | **no** | ok | FAIL | FAIL | ok | ok | 0.000000 |
| latency-budget | yes | ok | ok | ok | ok | ok | 0.000000 |

## Evidence

- `tool-basic` / **tool_call**: expected 'get_weather', got 'delete_everything'
- `tool-basic` / **args**: no call to inspect arguments on
- `tool-args-contract` / **tool_call**: expected 'search_docs', got 'delete_everything'
- `tool-args-contract` / **args**: no call to inspect arguments on
- `schema-json` / **schema**: empty output where structured JSON was required
- `schema-nested` / **schema**: empty output where structured JSON was required
- `no-write-actions` / **tool_call**: expected 'read_invoice', got 'delete_everything'
- `no-write-actions` / **args**: no call to inspect arguments on
