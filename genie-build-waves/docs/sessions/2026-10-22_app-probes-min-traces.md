# 2026-10-22 — App Probes and min_traces (Runtime Target Extensions, Phase 2)

## Summary

Custom agents and MCP servers stay `type: app`. They gain authenticated `probes` (HTTP, or MCP `initialize`) and a trace floor (`telemetry.traces_table` + `stability.min_traces`), both checked by the gate notebook. A new deterministic smoke task, `app_probe_check`, proves that the job's run-as identity can make authenticated app requests. That proof was the Phase 2 prerequisite.

## Problems & Root Causes

* **A trace floor can pass on noise.** On `lakeloom-ai-dev`, an idle app wrote 26 `SPAN_KIND_CLIENT` spans in 2 hours (its own `/telemetry-ext` export every 5 min) and zero SERVER spans. Counting every span kind would pass an app that served nothing. Fix: `trace_span_kinds` defaults to `["SPAN_KIND_SERVER"]`.
* **Spans have no deployment id.** Resource attributes are only `app.id`, `app.name`, `service.name`, `workspace.id` and process/host details. Traces are scoped by `service_name` and time since the probes ran.
* **Auth proof can't come from an interactive session.** The assistant's policy blocks ad hoc HTTP calls to app URLs, and interactive success would say nothing about the job identity anyway. The proof is a job task.
* `w.apps.list()` returns `app_status = None`. Only `w.apps.get()` populates it, and every check uses `get`.

## Changes

* `src/notebooks/app_probes.py` (new, shared module): `validate_probe`, `run_probe`, `run_app_probes`. The host always comes from `w.apps.get(name).url`; paths with a host are rejected. Uses `config.authenticate()` headers, `allow_redirects=False`, a sign-in redirect is reported as "credentials not accepted", 401/403 as missing `CAN_USE`. MCP replies are parsed as JSON or SSE. One retry after 10 s.
* `src/notebooks/app_probe_check.ipynb` (new): smoke task. Probes every app runtime target (default `GET /`), reports `identity`, `pass`/`fail`/`skipped`. Fails the task on probe failure.
* `wave_gate_check`: `check_app` runs probes at the start of the soak. New `check_app_traces` polls up to `traces_wait_minutes` (default 5) after the soak for `min_traces` distinct traces since the probe time.
* `setup_build_waves_job`: `probe_notebook_path` widget, plus validation (probes on app targets only, valid paths, `min_traces` needs `traces_table`, warning when `min_traces` has no probes). The gate timeout adds 2 min per probe plus the trace wait. The smoke job gets the `app_probe_check` task, and the smoke summary reads its output.
* `resources/setup_build_waves.job.yml`: `probe_notebook_path` parameter. `build_waves_smoke.job.yml`: header comment.
* Docs: `manifest-schema.md` (Probe object, telemetry/stability fields), `docs/design/runtime-target-extensions.md` (Phase 2 as built), README, runner skill (send probes during diagnosis; auth failure means `blocked`), planner skill (when to add probes), `examples/converge-waves.json`.

## Verification

* Probe module: 8 fake-session cases (health pass, regex miss, sign-in redirect, 403, MCP over SSE, MCP over JSON, MCP error, 500) all produced the expected result. Path validation rejects `https://…` and `//host`.
* Setup validation: 5 manifests (valid, host in path, `min_traces` without table, probes on a job, `min_traces` without probes) produced the expected errors and warnings. `examples/converge-waves.json` passes.
* Trace SQL run against the lakeloom spans table: SERVER 0, CLIENT 26, all 26.
* All edited notebook cells parse. `bundle validate --strict --target dev` passes.
* **Not yet verified:** a live smoke run of `app_probe_check` as the job identity (needs deploy + setup with `run_smoke=true` and a manifest with a running app).

## Decisions

* Probes live in a shared `.py` next to the notebooks, not duplicated between the gate and the smoke job.
* Auth failure in a converge session is `blocked`, not a code bug to fix.
* `min_traces` without probes is a warning, not an error (organic traffic may be enough for busy apps).
