# Runtime Target Extensions

Design record for extending `runtime_targets` beyond `app | job | pipeline`. Origin: a request from another Genie Code session using the framework (2026-10-22). Decisions below were made by the framework owner.

## Status

| Phase | Scope | Status |
|---|---|---|
| 1 | `dashboard` type; wave `validate_bundles` | **Implemented** (2026-10-22) |
| 2 | `app` probes (HTTP, MCP initialize) + `traces_table` / `min_traces` | Planned |
| 3 | `genie_space` type, static checks | Planned |
| 4 | `genie_space` probe questions | Planned |

## Decisions

| Question | Decision |
|---|---|
| Dashboard dataset check default | `EXPLAIN` (no data scanned). Option `execute_datasets: true` runs `SELECT * FROM (<query>) LIMIT 1`. |
| Per-wave `bundle_target` vs structured list | Structured wave field `validate_bundles: [{root, target}]` instead of a per-wave override. Runtime targets already carry `bundle_root` / `bundle_target`. |
| Genie probe questions default | `probe_mode: warn`. `fail` is opt-in. |
| Custom agents | Stay `type: app`; probes add agent-level health without a new type. |
| Genie space / dashboard deploy default | `bundle deploy --target <t>` only, no `bundle run`. |

## Phase 1 (implemented)

**`dashboard`.** Gate notebook `check_dashboard`: published revision created after the build run started (`require_fresh_deployment`), warehouse set (target `warehouse_id` or the published one), every dataset resolves. Query datasets use the dataset's `catalog`/`schema` and single-value default parameters; multi-value/range parameters are reported `skipped`. `asset_name` datasets (tables, metric views) must resolve via `w.tables.get`. No soak; gate timeout adds 10 minutes per dashboard target.

Verified behavior that shaped the design: `EXPLAIN` on a query with an analysis error returns `SUCCEEDED` with a first row `Error occurred during query planning:` and the error on row 2 (both `spark.sql` and the Statement Execution API). A status-only check would pass broken dashboards; the gate inspects the plan text. Tested against workspace dashboards: a real stale column (`run_timestamp`) was caught in both modes.

**`validate_bundles`.** The integrator runs `bundle validate --strict --target <target>` from each entry's `root` and reports `bundle_validations` in the gate file. The gate notebook fails the wave if any declared entry is missing or not `pass` (roots compared after resolving against `build_root`). The setup notebook rejects entries without `root` and `target`.

## Phase 2 (planned): app probes for custom agents

Fields on `app` targets:

```json
"probes": [
  {"path": "/api/health", "method": "GET", "expect_status": 200, "response_regex": "ok"},
  {"path": "/mcp", "mcp_initialize": true}
],
"telemetry": {"traces_table": "cat.sch.my_app_otel_spans"},
"stability": {"min_traces": 1}
```

* Probes run from the gate notebook with the build job's identity, using `WorkspaceClient().config.authenticate()` headers (plain Bearer tokens get 403 from the Apps auth sidecar). The identity needs `CAN_USE` on the app.
* **Prerequisite:** extend `capability_probe` to prove an authenticated app request works under a job run-as identity before relying on it.
* Run probes at the start of the soak, then require `min_traces` spans for the deployment **since the probe time**. An idle agent emits no traces, so a trace floor without probe traffic would fail healthy apps.
* MCP: POST a JSON-RPC `initialize` with `Accept: application/json, text/event-stream`; pass = a result with `serverInfo`.

## Phase 3 (planned): `genie_space` static checks

* Require `id` (space titles are not unique; a name lookup must match exactly one).
* Checks: warehouse attached, every referenced table and metric view resolves in UC.
* "Deployed in this run": needs a reliable timestamp on the space. Verify what the Genie space API exposes before committing to this check; fall back to `require_fresh_deployment: false` if it has none.
* Deploy default: `bundle deploy` only.

## Phase 4 (planned): `genie_space` probe questions

```json
"probe_questions": ["How many orders last week?"],
"probe_mode": "warn",
"probe_timeout_seconds": 120
```

* Pass = the Conversation API produced a SQL query and it ran successfully within the timeout. Never judge answer correctness (LLM output is not deterministic).
* One retry per question. `warn` records failures in `wave_<N>_runtime.json` without failing the wave; `fail` fails it.
* Add each question's timeout to the gate task timeout.

## Files touched by each new type

`VALID_TARGET_TYPES` and validation (setup notebook), a `check_<type>` function and the `checkers` map (gate notebook), deploy/wait/diagnose defaults (runner skill), capability probe, `manifest-schema.md`, README, an example.
