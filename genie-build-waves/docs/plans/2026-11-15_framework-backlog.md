# genie-build-waves framework backlog

**Status:** open backlog, not scheduled. Each item has a proposed decision (adopt / defer / drop) for the owner to confirm.
**Date:** 2026-11-15 (items first reported 2026-10-31 by a consumer project's fourth build; see `docs/sessions/2026-11-15_framework-backlog.md` for the source)
**Scope:** framework changes found by running real builds. Each item is independent; pick and order them.

State on `main` is as of the date above.

## Summary

| # | Item | State on `main` | Proposed | Before a new level 4 project? |
|---|---|---|---|---|
| 1 | Freshness is measured from the run start | Open | Adopt | Planner rule now; code change later |
| 2 | Tracked gate waivers and gate preconditions | Open | Adopt (planner guidance now, `waivers` block later) | Planner guidance |
| 3 | Owner-interactive steps | Partly (destroy and deletes only) | Adopt (planner list now, `owner_steps` field later) | Planner list |
| 4 | Sessions cannot edit dashboard objects | Open | Adopt (planner guidance) | Only if the project has dashboards |
| 5 | One request schema and routing to later sessions | Open | Adopt | Schema now |
| 6 | Non-standard session status values | Partly | Adopt (small) | Optional |
| 7 | Failed or blocked sessions end SUCCESS | Documented; design note | Defer (design note) | No |
| 8 | Error patterns that match the redaction placeholder | Open | Adopt (planner note) | Only if telemetry gates are used |
| 9 | Tooling versions (CLI, Node) | Partly | Defer | Only for JS projects |

## 1. Freshness is measured from the run start

`src/notebooks/wave_gate_check.ipynb` compares app deployments, job runs, pipeline updates and table commits with the build run's start (`check_app`, `check_job`, `check_pipeline`, `check_table`, all take `run_start`). A fresh run started with `only` (README "Fresh runs") fails every `require_fresh_deployment` target that was deployed or written in the earlier run and not again in the fresh one, even when the data is minutes old. Repairing the original run passes.

This matters more now that the level 4 monitor starts fresh runs (monitor skill section 8 step 4). A fresh run from the failed wave re-runs that wave's sessions, so targets they redeploy are fresh. Targets deployed by an earlier wave, or written only by an outside schedule, are not.

Proposed:

* **Now (planner):** a runtime target with `require_fresh_deployment: true` must be deployed or written by a session in the same wave. Otherwise set `require_fresh_deployment: false` and check something else (row counts, columns, a recent timestamp column).
* **Later (gate):** measure freshness from the wave start (first `w<wave>_sync` or `w<wave>_sessions` task start in this run), or add a per-target `fresh_since` (`run_start` | `wave_start` | ISO timestamp). Document the repair-the-original rule in the README until then.

## 2. Gates that depend on outside conditions

Some gate lines cannot be met for reasons outside the code: data that only exists under a business condition (for example no rows because nothing happened today), a span emitted only on one branch of the logic, a job that has never succeeded. The only way through today is hand-editing a status file under `.build-status/<run>/` (not in Git) and noting it in the manifest. A level 4 monitor cannot do that (manifest and plan edits are stop conditions), so every such line becomes an escalation.

Proposed:

* **Now (planner):** write the precondition into the gate line ("if X, then Y; otherwise evidence Z") and a fallback evidence path in the plan. Never gate on a job with no known-good run.
* **Later:** a manifest `waivers` block (`wave`, `gate_line` or target, `waived_by`, `reason`, `request_id`, `expires`) that the gate applies and reports as `waived`, not `pass`, in the gate file and the build verdict.

## 3. Owner-interactive steps

Unattended Genie Code tasks are refused for some operations: creating an app and some app updates (`Invalid delegation claim`), `bundle run` of jobs that change grants, account group changes, `bundle destroy`, file and folder deletes. Each costs a repair cycle when a session discovers it at run time. The planner skill's "Owner-only steps" tip covers only destroy and deletes.

Proposed:

* **Now (planner):** list the known-refused operations; plan them as `manual_prereqs` (before the wave) or as owner steps with exact commands and a verification, never as session work.
* **Later:** a session field such as `owner_steps: [{when: before|after, commands: [...], verify: ...}]` that setup renders into the plan header and the integrator checks for evidence before failing the session.

## 4. Sessions cannot edit dashboard objects

A `.lvdash.json` stored as a dashboard workspace object cannot be edited as a file, and a Lakeview API write replaces the whole definition.

Proposed (planner): dashboard edits are owner steps, or one dedicated session with an approved API path. The integrator notes requests that target a dashboard object.

## 5. One request schema and routing to later sessions

The runner skill's status example uses `{path, change, why}` for `requests`; the integrator skill's gate file uses `{from, path, change}`. Sessions also wrote other shapes (`{to, path, ask}`, `{to, what}`, `{to, text}`). A request addressed to a later session reaches it only if a person edits that session's plan, which a level 4 monitor may not do.

Proposed:

* **Now:** one schema in both skills: `{from, to, path, change, why, priority}`.
* **Later:** the integrator lists open requests per target session in the wave summary, and warns (or fails, by manifest option) when a request names a later session whose plan or `context_notes` does not mention it. Requests against files no session may edit (for example the project memory file) are listed separately for the owner.

## 6. Non-standard session status values

Sessions sometimes write `done` or `completed`. Only `pass`, `fail`, `blocked` and `error` are final (`session_outcome` in `session_status.py`); anything else counts as incomplete, so a continuation pass re-runs the session, and if it is still not final the gate reports it as `error`. That is safe but costs a session run.

Proposed: the runner skill states the allowed values explicitly next to its status example; optionally the integrator names the fix ("use `pass`") when it sees `done` or `completed`.

## 7. Failed or blocked sessions end SUCCESS

A session that writes `fail` or `blocked` still ends its `for_each` iteration SUCCESS, so repairing `w<wave>_sessions` re-runs nothing. README "Why not repair?" documents it, the level 4 monitor starts a fresh run instead (monitor skill section 8 step 4), and `2026-11-15_failing-session-iterations-design.md` describes how to make such iterations fail.

Proposed: defer to the design note.

## 8. Error patterns that match the redaction placeholder

A project's telemetry error pattern such as `api_token=[A-Za-z0-9]{8,}` also matches the redacted form `api_token=REDACTED`, so every redacted line is a false positive. `DEFAULT_IGNORE_PATTERNS` in the gate notebook does not have the problem (it only ignores app shutdown noise).

Proposed (planner and examples): use a negative lookahead, for example `api_token=(?!REDACTED)[A-Za-z0-9]{8,}`, or add the placeholder to `ignore_patterns`.

## 9. Tooling versions

An integrator once ran a Databricks CLI older than the bundle's fields required (`workspace.sync_mode` needs v1.23.0), and downloading a newer CLI was blocked. On serverless, `npm` and `npx` were broken symlinks; a working route was `pip install nodejs-wheel-binaries` plus `npm-cli.js`. The smoke job's `capability_probe` checks CLI access, not its version.

Proposed: defer. When picked up, add the CLI version (and, for JS projects, a working Node route) to `capability_probe`, and a planner note on toolchain setup.

## Done when

The owner has confirmed adopt / defer / drop for each item, with a branch or plan for the adopted ones.
