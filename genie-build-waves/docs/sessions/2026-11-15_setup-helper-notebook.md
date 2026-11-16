# 2026-11-15: Generic setup helper notebook

## Problem

A new project's session wrote a project-specific setup notebook because `deploy_instance.py` and `bundle run` failed on serverless (the CLI is blocked there) and manifest errors only showed when the setup job ran. Review found: it re-implemented two validator rules that `waves_manifest.validate_manifest()` already enforces (and `docs/manifest-schema.md` documents), extracted the user's API token for raw REST polling, looked jobs up with an exact-name filter that misses dev-prefixed names, polled for at most 10 minutes, could start a build run (conflicts with a level 4 monitor), and overwrote the project's starter notebook. The owner asked for a generic version with widget parameters.

## Changes

* New `scripts/setup_helper` notebook. Everything project-specific comes from the vars file. Widgets: `vars_file`, `target`, `action` (`check` | `run_setup`), `run_smoke`, `wait_minutes`, optional `bundle_dir` (default: this notebook's bundle) and `root_path` (default: the dev root; required for other targets).
  * Loads the bundle's own helpers (`waves_manifest`, `instance_guard`, `monitor_grants`); checks required vars and `monitor_var_problems`.
  * Validates with `validate_manifest()` plus plan-file, context-file and branch checks.
  * Prints the `deploy_instance.py --check-only` and deploy commands for the web terminal.
  * Finds the instance's jobs from `<root_path>/state/resources.json` (`instance_guard.state_job_ids`), checks `deployment.metadata_file_path` and the build job's `manifest_path` default.
  * `run_setup`: refuses when a setup run is active; `w.jobs.run_now(...).result(timeout=...)`; reads the setup task's notebook output; raises with the error on failure.
  * Results: job IDs and URL, published skills, automations, patched task counts, monitor grants, smoke result.
  * `WorkspaceClient()` notebook auth only; never deploys, starts a build run or changes permissions.
* `README.md`: deploy script row says to run it in the web terminal; new row and paragraph for the helper; where the CLI works.

## Verification

* Ran the parameter, configuration, validation, deploy-command, job-lookup, setup (check mode) and results cells against the test project's vars file (stubbed widgets): manifest OK (8 waves, 4 runnable, 37 tasks), deploy commands printed, and the three jobs found from the remote state with the expected IDs and names; no guard problems.
* Not run: `action = run_setup` (would run a project's setup job), the SDK install cell, and a non-dev target.

## Files

`scripts/setup_helper.ipynb` (new), `README.md`, `docs/sessions/2026-11-15_setup-helper-notebook.md`, `docs/sessions/INDEX.md`.
