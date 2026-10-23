# 2026-10-22 Runtime gate phases 5, 4, 6, 7

Request: add phases 5 to 7 to the design doc, then implement the remaining phases in the order 5, 4, 6, 7, committing and pushing after each, then write this summary. Branch `mg-genie-build-waves-init`, remote `mkgs-databricks-demos/mbp`.

## Commits

| Commit | Scope |
|---|---|
| `7ca3c2d` | Phase 3: `genie_space` static checks (summary: [genie-space-static-checks](2026-10-22_genie-space-static-checks.md)) |
| `d3530d4` | Design doc: phases 5 to 7; agents run only on Apps (no `serving_endpoint` type) |
| `80b25ef` | Phase 5: smoke Genie space access; `probe_auth` required |
| `40e6d93` | Phase 4: Genie probe questions |
| `b689bcf` | Phase 6: pipeline data quality budgets |
| `ac6d7a3` | Phase 7: `table` runtime target |

Each phase was checked with `bundle validate --strict --target dev`, a parse of every notebook code cell, setup-validation cases, and all three examples validating clean.

## Phase 5: live proof and smoke coverage

**Problem.** Probes ran as the job's identity when `probe_auth` was missing, and that path had never run from a job.

**Root cause (from real one-time job runs of `app_probe_check` against `lakeloom-ai-dev`).** Apps accept only OAuth tokens. A job's own credential is redirected to sign-in (302) even though that identity has `CAN_MANAGE` on the app. So the fallback could never work.

| Case | Result |
|---|---|
| Job identity, no `probe_auth` | 302 to sign-in |
| Service principal with a valid secret but no `CAN_USE` | Token issued, then 302 (not 403) |
| Service principal with a rotated secret (`lakeloom-xcode-dev_...`, the only scoped SP with `CAN_USE`) | `invalid_client` |
| Missing secret key | One-line `Secret does not exist` error (was a Py4J stack trace) |
| Genie space by id, by title, not yet created | pass, pass, skipped |
| App with no probes; OTel traces and logs tables | pass (not probed); both readable |

**Changes.**
* `app_probes.probe_client` raises without `probe_auth`; secret read errors are cut to one line; the redirect message names both causes (no `CAN_USE`, or not an OAuth token).
* Setup: `probes` without `probe_auth` is now an error (was a warning).
* `app_probe_check`: checks `CAN_EDIT` on every `genie_space` target, and only probes apps that have `probes` or `probe_auth`. Its failure message names the identity for each target.

**Open.** No accepted (200) request as a service principal yet. That needs a `CAN_USE` grant to a scoped SP, or a fresh secret for the xcode SP. This is the owner's call, so no permissions were changed.

## Phase 4: Genie probe questions

**Changes.** `probe_questions`, `probe_mode` (`warn` default, or `fail`) and `probe_timeout_seconds` on `genie_space` targets. Questions are asked after the static checks pass, each in a new conversation with one retry. Pass = a query attachment whose statement `SUCCEEDED`; answers are never judged. In `warn` mode failures go to `warnings` in the gate output; in `fail` mode they fail the wave. Setup validates the fields and adds `2 × timeout` per question to the gate timeout.

**Findings (real space).** Data question: 13 to 25 s, a `MEASURE()` query, `SUCCEEDED`. Off-topic question: `COMPLETED` in about 5 s with only a text attachment, so status alone would pass it. Timeout: `TimeoutError` (`ASKING_AI`) is reported as a failure.

**Decision.** The gate does not delete probe conversations. Deleting was blocked as destructive, and the conversations only sit in the build identity's history. Two test conversations from this session remain in the owner's history on that space.

## Phase 6: pipeline data quality

**Changes.** `stability.max_failed_records` and `max_dropped_records` on `pipeline` targets. `_pipeline_data_quality` sums the checked update's `flow_progress` `data_quality` and lists failing expectations by count.

**Findings.**
* The events API filter rejects `event_type = ...` and `IN (...)`. `update_id = '...'` works, so event type is filtered client-side.
* Pipelines that publish their event log to Unity Catalog returned nothing from the API, while their tables keep full history. The gate reads the table when `spec.event_log` is set.
* `warned_records` counts rows and `failed_records` counts rule hits (29 rows against 131 hits on one flow). The budget uses `failed_records`.
* Real update of `ncpdp_segments_etl`: 145 failed records over 11 expectations, which matches an independent SQL `explode` sum.

**Not verified.** The events API path on an update that has expectation metrics (none exists in this workspace).

## Phase 7: `table` target

**Changes.** `type: table` with `required_columns`, `min_rows` and freshness, usable in any wave's `runtime_gate` without a converge session. `COUNT(*)` runs on the notebook's Spark, so no warehouse is needed (a change from the plan). `examples/workspace-waves.json` now uses `runtime_gate` instead of free-text "> 0 rows" lines.

**Findings.** `DESCRIBE HISTORY` works on Delta and streaming tables and fails on materialized views ("is a view"), views, metric views and foreign tables. Materialized view freshness comes from `DESCRIBE EXTENDED ... AS JSON` `refresh_information.last_refreshed_at`. Views, metric views and foreign tables skip freshness. History read through `unix_millis` matches UC `updated_at`. 11 cases pass as expected.

## Files modified

* `src/notebooks/app_probes.py`, `src/notebooks/app_probe_check.ipynb` (phase 5)
* `src/notebooks/wave_gate_check.ipynb`: `_ask_genie`, `_pipeline_data_quality`, `_table_last_write`, `check_table`, warnings in the report (phases 4, 6, 7)
* `src/notebooks/setup_build_waves_job.ipynb`: validation and gate timeouts (all phases)
* `docs/manifest-schema.md`, `docs/design/runtime-target-extensions.md`, `README.md`
* `src/skills/genie-build-session-runner/SKILL.md`, `src/skills/genie-build-planner/SKILL.md`
* `examples/converge-waves.json`, `examples/workspace-waves.json`
* `.gitignore` (`.scratch/`, which holds the phase 5 test manifests)
