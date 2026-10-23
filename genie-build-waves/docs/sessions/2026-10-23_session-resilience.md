# Session Resilience Improvements (Batch B)

**Date:** 2026-10-23

## Problem

Feedback from a consumer Genie Code session identified two session resilience issues:

1. **Repairs silently fall back to the job's defaults.** The setup job's `jobs/reset` preserved the job parameter defaults from bundle deploy. If the original run used custom parameters (e.g. a different branch), a `repair_run` without `job_parameters` would silently use the wrong values. Repair 1 ran against the wrong branch and paths because of this.

2. **A cut-off session has no status file.** Session 12 hit the Genie Code turn limit before writing its status file. The gate then reported "never ran" plus stray files for the code the session had partially written.

## Root Cause

1. `reset_job_tasks` in the setup notebook preserved all existing settings including parameter defaults. The repair prompt and README had no mention of `job_parameters`.
2. The runner skill had no instruction to write an early provisional status file. The integrator treated missing status files as "never ran" and classified files under the session's `owned_paths` as strays.

## Changes

### src/notebooks/setup_build_waves_job.ipynb (cell 10)

* `reset_job_tasks` now accepts an optional `parameters` argument. When provided, it updates the job-level parameter defaults during `jobs/reset`.
* The build job reset now passes `build_params` with `branch` (from manifest default), `build_root`, and `manifest_path` — ensuring repair_run defaults are always correct even if the original deploy used placeholder values.

### docs/prompts/repair-failed-wave.md

* Added `job_parameters` to the repair_run SDK example.
* Added a note: "Pass `job_parameters` on every repair" explaining that repair_run falls back to job defaults when omitted.

### README.md

* Added the same `job_parameters` guidance to the Repairing a failed wave section.

### src/skills/genie-build-session-runner/SKILL.md

* Added instruction in step 4 to write a provisional `in_progress` status file before any work, with empty arrays for all fields.
* Update the file after each converge attempt (for converge mode) or after completing all tasks. Replace with the final version in step 7.

### src/skills/genie-build-wave-integrator/SKILL.md

* Step 2: `in_progress` status now counts as `error` (not just missing files). Added "Incomplete session file credit" logic: when a session is `error` due to missing or `in_progress` status, scan the working tree for files under its `owned_paths` and credit them to the session. This prevents stray detection from flagging code a partially-complete session left behind.
* Step 3: Files credited to an incomplete session are explicitly excluded from stray detection.

## Decisions

* The provisional status file is a prompt-level change (runner skill instruction), not a code change — the runner is a Genie Code session following the skill.
* The integrator credits files only when the session has `error` status (missing or `in_progress`), not when it has `fail` or `blocked` — those sessions wrote their own status files with explicit `files_changed`.
* The setup notebook reads the branch from `manifest.get("branch", "")` rather than from the build job's existing parameters, because the manifest is the source of truth.
* `job_parameters` is shown as optional in the repair examples but strongly recommended, to avoid breaking existing workflows that happen to match the defaults.

## Files Modified

* src/notebooks/setup_build_waves_job.ipynb — reset_job_tasks accepts parameters, build job passes parameter defaults
* docs/prompts/repair-failed-wave.md — added job_parameters to repair example and guidance
* README.md — added job_parameters guidance to repair section
* src/skills/genie-build-session-runner/SKILL.md — provisional in_progress status file instruction
* src/skills/genie-build-wave-integrator/SKILL.md — incomplete session file credit, stray exclusion