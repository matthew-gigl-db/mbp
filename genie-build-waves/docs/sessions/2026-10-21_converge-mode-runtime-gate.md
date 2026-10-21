# 2026-10-21: converge mode, runtime gate, per-project instances

## Problem
Initial build waves (AgenticTrading trading-agent-app, Semantic Ground Truth) "passed" on static gates only: files existed and the bundle validated. The first real deploy of trading-agent-app-dev failed on ~18 TypeScript errors. A pass needs to mean the thing deploys and runs stably.

## Root causes
* No session mode could deploy, read telemetry and iterate; gates were LLM-interpreted text.
* Parallel sessions share one working tree and one live deployed resource, so deploy loops cannot run in parallel.
* The bundle was single-instance per target: deploying for a second project replaced the first project's jobs.
* Automation reuse never worked: API-created automations are hidden from the list endpoint (0 of 3 job-referenced automations were listed), so every setup run created new ones.

## Decisions (approved by the user)
* Initial builds stay wide and parallel; follow-up builds append sequential `converge` waves (one session each) that deploy, read OTel logs, fix and redeploy until stable.
* A passing stable build is part of the pass criteria, checked deterministically by the gate notebook (`runtime_gate`).
* The planner may take context from the interactive Genie Code session itself (known errors, decisions, IDs).

## Changes
* `docs/manifest-schema.md`: build phases, `converge` mode, `runtime_targets` (type, name, deploy_commands, telemetry, stability), wave `runtime_gate` and `timeout_minutes`, session `runtime_targets` / `max_attempts` / `timeout_minutes` / `context_notes`, rules 7-9 (single-writer deploys, deterministic runtime gates, no build job in the converged bundle).
* Runner skill: converge guardrail, deploy guardrails, "fix causes not symptoms" with recorded `suppressions`, bounded converge loop, `attempts` / `runtime` in the status file.
* Integrator skill: never deploys; converge treated as edit for staging/strays; copies suppressions; runtime checks deferred to the gate notebook.
* `wave_gate_check`: SDK install cell; converge pass must end with a `stable` attempt; runtime gate for app (deployment SUCCEEDED and fresh, RUNNING/ACTIVE, soak, OTel error lines by deployment id + body regex, required markers), job (latest run since build start SUCCESS) and pipeline (latest update COMPLETED or RUNNING); writes `wave_<id>_runtime.json`.
* `setup_build_waves_job`: manifest validation cell; per-task `timeout_seconds`; forced concurrency 1 for deploying waves; automation reuse via direct GET of job-referenced automations (fixes the leak) across build + smoke jobs; new read-only `capability_probe` smoke task.
* Planner skill: follow-up planning, conversation context as input, Known issues section, `instance_suffix`.
* `databricks.yml`: `instance_suffix` variable in dev/prod `root_path` (empty keeps the existing path).
* README and new `examples/converge-waves.json`.

## Checks
* `bundle validate --strict` passes for dev (default path unchanged: `.bundle/genie-build-waves/dev`) and dev/prod with `instance_suffix=-agentic-trading` (`.bundle/genie-build-waves-agentic-trading/<target>`).
* App runtime-check logic run live against `trading-agent-app-dev`: reports deployment FAILED, app UNAVAILABLE, 11 error lines (TS errors have severity UNKNOWN, caught by body regex), missing marker, so the gate would fail as expected.
* Manifest validation: all three examples and the sGt manifest pass. The old in-repo AgenticTrading manifest fails rule 7 (wave 4a has two `allow_deploy` sessions) and must be adjusted when it moves to this bundle.
* Automation lookup: confirmed job-referenced automations are retrievable by GET with `user_prompt` and `etag`.
* Not yet run end-to-end: setup job, capability probe, and a real converge wave.

## Open items
* Run setup with `run_smoke=true` and read the `capability_probe` output before the first converge run.
* Existing deployment for Semantic Ground Truth stays on the default instance (no suffix); AgenticTrading should deploy with `instance_suffix=-agentic-trading`.
