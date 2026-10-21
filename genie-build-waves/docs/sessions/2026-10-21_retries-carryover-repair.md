# 2026-10-21: task retries, carryover stray handling, repair with dependents

## Problem
The Semantic Ground Truth build session (build job 1079028753739581, runs 376065156883918 and 187770715982911) reported three framework issues:
1. Integrators failed with the transient `INTERNAL_ERROR: start_agent_run`. The session summaries already written for that wave stayed uncommitted, and the next fresh run's wave 0 gate failed on them as strays ("untracked, not in any session status file for this run"). This happened twice and needed a manual commit before each retry.
2. `repair_run(rerun_tasks=["w0_gate"])` re-ran the gate notebook but not `w0_gate_check`, so waves 1-8 stayed Excluded and a fresh run was needed.
3. The `start_agent_run` error recurred on `w3_integrate`; it cleared on retry each time.

The same handover also mentioned a mid-run branch switch that swapped `pnpm-lock.yaml` under the converge session.

## Root causes
* No Genie Code task had `max_retries`, so every transient agent start-up failure turned into a failed task and a manual repair or fresh run.
* The integrator's stray check only accepted files claimed by the current run's status files. Earlier runs leave files behind by design (failed sessions' code stays uncommitted for repair) or by accident (an integrator that never started), so every fresh run after a failure inherited strays.
* A repair only re-runs the tasks named. Once an If/else task has evaluated to `false`, it and its Excluded descendants are only re-run with `rerun_dependent_tasks`. The README listed the tasks to repair but not this.
* The session runner checked the branch once at start. A converge loop can run for hours, and nothing stopped it from deploying after the Git folder was switched to another branch.

## Changes
* `src/notebooks/setup_build_waves_job` (task graph cell): `GENIE_TASK_RETRIES` added to every `genie_task` (inner session task and integrator): `max_retries` 2, `min_retry_interval_millis` 60000, `retry_on_timeout` false. Override with manifest `task_retries` (`max_retries`, `min_retry_interval_seconds`); `max_retries: 0` disables. Gate notebooks are not retried.
* `src/skills/genie-build-session-runner/SKILL.md`: retry awareness (an existing status file or summary for this run means a retry: continue, keep finished work, update the same files). Converge loop re-checks the branch before every deploy attempt and stops with `error` if it changed.
* `src/skills/genie-build-wave-integrator/SKILL.md`: carryover classification in step 3 (`summary`, `prior_run_code`, `owned_by_later_wave`), which doesn't fail the gate. Step 6 stages summary carryover (and adds missing INDEX lines) but leaves code carryover for its owning session. New `carryover_files` in the gate JSON. In the manifest's last wave, unclaimed code carryover fails the gate so a human decides.
* `src/notebooks/wave_gate_check`: independent last-wave check for unclaimed carryover; prints `carryover_files`.
* `README.md`: new "Repairing a failed wave" section: `repair_run(..., rerun_dependent_tasks=True)` (SDK and CLI), `latest_repair_id` for repeat repairs, which tasks to name per failure type, automatic retries for transient errors, carryover on fresh runs.
* `docs/manifest-schema.md`: `task_retries` top-level field.

## Decisions
* Retry at the task level rather than teach the integrator to commit on failure: an integrator that never starts can't commit anything.
* Classify carryover from evidence (status files from earlier runs, the runner summary naming convention, later-wave ownership) rather than a filename pattern alone, so leftover code is covered too.
* Don't retry on timeout: a converge loop that ran out of time should surface, not restart from scratch.
* Never auto-discard carryover; the last wave is the backstop.

## Checks
* Dry-run of `generate_wave_tasks` with three manifests: default gives `max_retries` 2 / 60000 ms / no retry on timeout on `w0_session` and `w0_integrate`, none on `w0_gate`; `max_retries: 0` gives no retry fields; an override of 3 / 30 s is applied.
* All code cells of both edited notebooks parse (`ast.parse`).
* `JobsAPI.repair_run` signature confirmed to have `rerun_dependent_tasks`, `rerun_tasks`, `latest_repair_id`.
* `bundle validate --strict --target dev`: Validation OK.

## Open items
* Not yet verified live: that `max_retries` is honoured for a `genie_task` inside `for_each`, and that `rerun_dependent_tasks` un-excludes downstream tasks after an If/else evaluated `false`. Verify both on the next failure in the Semantic Ground Truth build.
* The running sGt build (run 187770715982911) uses the old task graph. The new retries and skills apply after the next `bundle deploy` + setup run. Don't redeploy or re-run setup mid-run: both replace the build job's tasks (and setup republishes the skills the running tasks read), which blocks repair of that run.
* The sGt run restarted from wave 0 although waves 0-5 were already merged; follow-up runs should use `only` from the first unfinished wave.

## Files modified
* `src/notebooks/setup_build_waves_job.ipynb`
* `src/notebooks/wave_gate_check.ipynb`
* `src/skills/genie-build-session-runner/SKILL.md`
* `src/skills/genie-build-wave-integrator/SKILL.md`
* `README.md`
* `docs/manifest-schema.md`
* `docs/sessions/2026-10-21_retries-carryover-repair.md` (this file), `docs/sessions/INDEX.md`
