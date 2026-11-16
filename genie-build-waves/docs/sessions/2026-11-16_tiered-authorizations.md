# 2026-11-16: Tiered authorizations

## Problem

underwritingGenie Build 0 blocked three times on Auto Mode refusals (run-now on its own setup job, UC Skills publish) and needed owner commits to `context_notes`. A spike (`/Users/matthew.giglia@databricks.com/genie-authz-spike`, request v2 in `underwritingGenie/docs/prompts/genie-build-waves-owner-authorizations-request.v2.md`) found:

* Approval in the task prompt: job run 3 of 3. Approval only in a file the session reads: 0 of 3. No approval, run requested only by a file: 0 of 3.
* A run-now / repair job parameter replaces the same-named task parameter in every task, even when the job does not declare it.
* SQL file tasks replace `{{p}}` with a quoted literal everywhere, comments included.
* Job-task sessions share the owner's Genie Code memory (one wrote to it unasked).

## Changes

* `src/notebooks/authorizations.py` (new): action vocabulary, owner-only actions (rejected everywhere), `validate_authorizations`, tier 1 `implied_authorizations` (converge / allow_deploy: deploy own bundle, run own job / pipeline targets; `authorize_run: false` opts out), tier 2 owner entries, tier 3 `filter_monitor_grants` (allowlist + session's own targets + evidence), one-line `render_authorizations`, `inputs_authorizations`, `parameter_overrides`.
* `waves_manifest.py`: `authorizations` first in `RUNNER_PARAMS`; validation includes the authorization rules; each session's for_each input carries its rendered approvals; runner parameter `{{input.authorizations}}`.
* Setup: reads the monitor grants file (default `<plans_dir>/authorizations.monitor.json`), prints kept / dropped grants and every session's approvals, passes them to the task graph; runner prompt starts with `{{authorizations}}`.
* `find_incomplete_sessions`: continuation passes copy approvals from the job's `w<wave>_sessions` inputs (never re-rendered from files).
* `build_verdict`: adds `PARAMETER_OVERRIDE` (warning, not failure) for job parameters that differ from the job's defaults or are undeclared.
* Skills: runner (approvals from prompt only, `blocked_actions`, `resolved_targets`, no memory writes), integrator (no memory writes), monitor (job parameters only the run's own values; section 9 tier 3 grants via the grants file, owner runs setup), planner (plan approvals, SQL `:param`, `.genie_agents/` in `.gitignore`).
* Docs: `manifest-schema.md` (Authorizations section, `authorization_policy`, `defaults`, `authorizations`, `authorize_run`), README paragraph.

## Verification

* 197 tests pass (18 new in `tests/test_authorizations.py`); `bundle validate --strict --target dev` OK; changed notebook cells parse.
* Real Build 0 manifest: validates with no errors; warns on approval wording in sessions 06 and 08 `context_notes`; session 06 renders tier 1 deploy + run-now of `setup_demo_job`; session 08 gets no skills-publish approval until an `authorizations` entry is added.
* Not run live: setup, find_incomplete and verdict changes (no build job run).

## Decisions and open items

* `PARAMETER_OVERRIDE` warns instead of failing; the owner decides.
* Tier 3 unattended (follow-up, same day): setup's new first cell pulls the build branch (Repos API, the build job's deployed `branch` default; skipped in workspace mode or with `sync_branch: false`; a failed pull prints `SETUP_SYNC_FAILED` and setup continues). The setup job now declares the monitor at `monitor_job_level`, so a level 4 monitor with CAN_MANAGE_RUN runs setup with no job parameters to apply its own grant, then checks `setup_sync` and `monitor_authorization_grants.kept` in the setup output. Below level 4 it reports `GRANT_PROPOSED`. Not run live.
* Untested: whether for_each inputs accept long approval text on large manifests; whether a runner reached through the UC Skill treats manifest text differently.

## Files

`src/notebooks/authorizations.py` (new), `tests/test_authorizations.py` (new), `src/notebooks/branch_sync.py`, `tests/test_branch_sync.py`, `resources/setup_build_waves.job.yml`, `databricks.yml`, `src/notebooks/waves_manifest.py`, `setup_build_waves_job.ipynb`, `find_incomplete_sessions.ipynb`, `build_verdict.ipynb`, four `SKILL.md` files, `docs/manifest-schema.md`, `README.md`, this file, `docs/sessions/INDEX.md`.
